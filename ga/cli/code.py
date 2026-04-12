import concurrent.futures
import os
import random
import sys
import time

from dataclasses import dataclass

import ga.ocga as gacode
from ga.legis import Client
from ga.render import MarkdownRenderer


@dataclass
class _CodeTitle:
    code: str   # zero-padded, e.g. "01"
    name: str

    @classmethod
    def from_api(cls, data: dict) -> "_CodeTitle":
        return cls(code=data["code"], name=data["name"].strip())


def _get_code_titles(client: Client) -> list[_CodeTitle]:
    return [_CodeTitle.from_api(t) for t in client.get("georgia-code/titles")]

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OCGA_DIR = os.path.join(_REPO_ROOT, "docs", "ocga")


def _local_section_path(section_id: str) -> str:
    parts = section_id.lower().split("-", 2)
    return os.path.join(OCGA_DIR, parts[0], parts[1], f"{section_id.lower()}.md")


def _local_index_path(*parts) -> str:
    return os.path.join(OCGA_DIR, *[p.lower() for p in parts], "index.md")


def cmd_code(client: Client, args):
    if args.fetch:
        _cmd_codefetch(client, args)
        return

    renderer = MarkdownRenderer()
    id = args.id

    if id is None:
        renderer.print(open(_local_index_path()).read())
        return

    parts = id.split("-")

    if len(parts) == 1:
        path = _local_index_path(parts[0])
        if not os.path.exists(path):
            print(f"Title {parts[0]} not fetched yet. Run: ./ga-cli code --fetch --title {parts[0]}", file=sys.stderr)
            sys.exit(1)
        renderer.print(open(path).read())
        return

    if len(parts) == 2:
        path = _local_index_path(parts[0], parts[1])
        if not os.path.exists(path):
            print(f"Title {parts[0]} not fetched yet. Run: ./ga-cli code --fetch --title {parts[0]}", file=sys.stderr)
            sys.exit(1)
        renderer.print(open(path).read())
        return

    local = _local_section_path(id)
    if args.year:
        section = gacode.api.get_section(id, args.year)
        renderer.print(gacode.api.section_to_markdown(section))
        return
    if not os.path.exists(local):
        print(f"Section {id} not fetched yet. Run: ./ga-cli code --fetch --title {id.split('-')[0]}", file=sys.stderr)
        sys.exit(1)
    renderer.print(open(local).read())


def _fetch_chapter(chapter_dir, chapter_num, ch_name, title_num, sections, args):
    """Fetch all sections in one chapter. Runs in its own thread."""
    os.makedirs(chapter_dir, exist_ok=True)
    with open(os.path.join(chapter_dir, "index.md"), "w") as f:
        f.write(f"# {ch_name}\n\n")
        for sec_id, sec_name, _url in sections:
            f.write(f"- {sec_name}\n")

    print(f"  {ch_name} ({len(sections)} sections)", flush=True)

    written = skipped = 0
    for sec_id, sec_name, sec_url in sections:
        sec_file = os.path.join(chapter_dir, f"{sec_id}.md")

        if os.path.exists(sec_file):
            with open(sec_file) as f:
                content = f.read()
            if [l for l in content.splitlines() if l.strip() and not l.startswith("#")]:
                skipped += 1
                continue

        try:
            section = gacode.api.get_section(sec_id, url=sec_url)
            with open(sec_file, "w") as f:
                f.write(gacode.api.section_to_markdown(section))
            written += 1
            print(f"    {sec_id}", flush=True)
        except Exception as e:
            print(f"    Warning: {sec_id}: {e}", file=sys.stderr, flush=True)

        time.sleep(args.delay + random.uniform(0, args.delay * 0.5))

    if skipped:
        print(f"    ({skipped} skipped, already fetched)", flush=True)


def _cmd_codefetch(client: Client, args):
    out = args.out or OCGA_DIR
    titles = _get_code_titles(client)
    if args.title:
        titles = [t for t in titles if int(t.code) == args.title]
        if not titles:
            print(f"Error: title {args.title} not found.", file=sys.stderr)
            sys.exit(1)

    for title in titles:
        title_num = str(int(title.code))
        print(f"Title {title_num} — {title.name}", flush=True)

        time.sleep(args.delay)
        try:
            chapter_entries = gacode.api.get_title_toc(title_num)
        except Exception as e:
            print(f"  Warning: could not fetch TOC for title {title_num}: {e}", file=sys.stderr)
            continue

        title_dir = os.path.join(out, title_num)
        os.makedirs(title_dir, exist_ok=True)
        with open(os.path.join(title_dir, "index.md"), "w") as f:
            f.write(f"# Title {title_num} — {title.name}\n\n")
            for _, ch_name in chapter_entries:
                f.write(f"- {ch_name}\n")

        chapters = []
        for ch_path, ch_name in chapter_entries:
            slug = ch_path.rstrip("/").split("/")[-1]
            chapter_num = slug[len("chapter-"):] if slug.startswith("chapter-") else slug
            chapter_dir = os.path.join(title_dir, chapter_num)
            try:
                sections = gacode.api.get_sections_for_chapter(title_num, chapter_num, delay=args.delay, chapter_path=ch_path)
                chapters.append((chapter_dir, chapter_num, ch_name, title_num, sections))
            except Exception as e:
                print(f"  Warning: could not fetch chapter {chapter_num}: {e}", file=sys.stderr)
            time.sleep(args.delay)

        if args.dry_run:
            for chapter_dir, chapter_num, ch_name, title_num, sections in chapters:
                for sec_id, *_ in sections:
                    print(f"  {os.path.join(chapter_dir, sec_id)}.md")
            continue

        gacode.client.set_initial_concurrency(args.workers)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(args.workers, 16)) as pool:
            futures = [pool.submit(_fetch_chapter, *ch_args, args=args) for ch_args in chapters]
            for f in concurrent.futures.as_completed(futures):
                if f.exception():
                    print(f"  Error: {f.exception()}", file=sys.stderr)
