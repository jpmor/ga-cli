import re

from .client import resolve_section_url, fetch_html
from .models import Section
from .parser import parse_section

from .client import _HOST as _BASE


def _parse_links(html: str, path_prefix: str) -> list[tuple[str, str]]:
    """Return (href_path, link_text) for all links under path_prefix."""
    escaped = re.escape(path_prefix)
    matches = re.findall(rf'href="({escaped}[^"/]+/)"[^>]*>\s*([^<]+)', html)
    seen = {}
    for path, name in matches:
        if path not in seen:
            seen[path] = name.strip()
    return list(seen.items())


def _is_chapter_path(path: str) -> bool:
    return bool(re.search(r'/(chapter|article)-', path))


def get_title_toc(title_num: str) -> list[tuple[str, str]]:
    """List chapters for a title, expanding grouping pages (e.g. Title 36)."""
    path = f"/codes/georgia/title-{title_num.lower()}/"
    html = fetch_html(f"{_BASE}{path}")
    entries = _parse_links(html, path)

    # Some titles (e.g. Title 36) have grouping pages instead of chapters at the top level.
    # Detect by checking whether any link looks like a chapter/article path.
    if entries and not any(_is_chapter_path(p) for p, _ in entries):
        expanded = []
        for grp_path, _ in entries:
            try:
                grp_html = fetch_html(f"{_BASE}{grp_path}")
                expanded.extend(_parse_links(grp_html, grp_path))
            except Exception:
                pass
        if expanded:
            entries = expanded

    return entries


def get_chapter_toc(title_num: str, chapter_num: str, chapter_path: str | None = None) -> list[tuple[str, str]]:
    """List sections (or articles) for a chapter."""
    if chapter_path is None:
        ch = chapter_num.lower()
        prefix = "" if ch.startswith("article-") else "chapter-"
        chapter_path = f"/codes/georgia/title-{title_num.lower()}/{prefix}{ch}/"
    html = fetch_html(f"{_BASE}{chapter_path}")
    return _parse_links(html, chapter_path)


def _section_id_from_name(name: str) -> str | None:
    """Extract dotted section ID from link text like 'Section 6-2-5.1 - ...'"""
    m = re.match(r'[Ss]ection\s+([\d]+-[\d]+-[\d.]+[a-zA-Z]*)', name)
    return m.group(1).lower() if m else None


def _collect_sections(entries: list[tuple[str, str]], delay: float = 0.0) -> list[tuple[str, str, str]]:
    """Recursively collect sections from a list of (path, name) entries."""
    import time
    result = []
    for path, name in entries:
        if "/section-" in path:
            section_id = _section_id_from_name(name) or path.rstrip("/").split("/section-")[-1]
            result.append((section_id, name, f"{_BASE}{path}"))
        else:
            # Sub-level (article-, part-, etc.) — fetch and recurse one level
            try:
                time.sleep(delay)
                sub_html = fetch_html(f"{_BASE}{path}")
                sub_entries = _parse_links(sub_html, path)
                result.extend(_collect_sections(sub_entries, delay))
            except Exception:
                pass
    return result


def get_sections_for_chapter(title_num: str, chapter_num: str, delay: float = 0.0, chapter_path: str | None = None) -> list[tuple[str, str, str]]:
    """
    Return (section_id, section_name, url) for all sections in a chapter.
    Handles chapters with article/part sub-levels. Section IDs are lowercase.
    """
    entries = get_chapter_toc(title_num, chapter_num, chapter_path=chapter_path)
    return _collect_sections(entries, delay)


def get_section(section_id: str, year: int | None = None, url: str | None = None) -> Section:
    if url is None:
        url = resolve_section_url(section_id, year)
    html = fetch_html(url)
    return parse_section(section_id, html, year, url)


def section_to_markdown(section: Section) -> str:
    display_id = section.id.upper()
    lines = [f"# § {display_id}. {section.title}", "", section.body]
    if section.history:
        lines += ["", "## History", "", section.history]
    return "\n".join(lines) + "\n"
