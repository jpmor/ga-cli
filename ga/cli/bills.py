import os
import sys
import time

from ga.legis import Client, Bill, get_bill, get_bill_text, search_bills
from ga.render import MarkdownRenderer, paint, _BOLD, _RED, _GREEN

from ga.legis import Chamber, DocumentType
from ga.cli.sessions import resolve_session
from ga.cli.format import colorize_status, fmt_status_date

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# Markdown serialization
# ---------------------------------------------------------------------------

def _yaml_str(value: str) -> str:
    if any(c in value for c in ':{}[]|>&*!,#?-\'"') or value.startswith(' '):
        escaped = value.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'
    return value or '""'


def _frontmatter(bill: Bill) -> str:
    lines = ["---"]

    def kv(key, val):
        lines.append(f"{key}: {val}")

    kv("id", bill.id)
    kv("label", _yaml_str(bill.label))
    kv("session", _yaml_str(str(bill.session)))
    kv("session_id", bill.session.id)
    kv("chamber", bill.chamber.name)
    kv("document_type", bill.document_type.name)
    kv("number", bill.number)
    kv("title", _yaml_str(bill.title))
    kv("status", _yaml_str(bill.status.name))
    kv("status_date", _yaml_str(bill.status_date))
    kv("enacted", str(bill.status.is_enacted).lower())
    kv("vetoed", str(bill.status.is_vetoed).lower())
    kv("act_number", _yaml_str(bill.act_veto_number))

    lines.append("sponsors:")
    for s in sorted(bill.sponsors, key=lambda x: x.sequence):
        lines.append(f"  - name: {_yaml_str(s.name)}")
        lines.append(f"    district: {_yaml_str(s.district)}")
        lines.append(f"    primary: {str(s.sequence == 1).lower()}")

    lines.append("committees:")
    lines.append(f"  house: {_yaml_str(bill.house_committee.name) if bill.house_committee else 'null'}")
    lines.append(f"  senate: {_yaml_str(bill.senate_committee.name) if bill.senate_committee else 'null'}")

    lines.append("---")
    return "\n".join(lines)


def _history_section(bill: Bill) -> str:
    if not bill.status_history:
        return ""
    lines = ["## History", ""]
    for event in sorted(bill.status_history, key=lambda e: e.date):
        lines.append(f"- {event.date.strftime('%Y-%m-%d')} — {event.name}")
    return "\n".join(lines)


def bill_to_markdown(bill: Bill, text: str) -> str:
    parts = [_frontmatter(bill), "", f"# {bill.label} — {bill.title}", ""]
    if bill.first_reader:
        parts += [bill.first_reader, ""]
    if text:
        parts += [text, ""]
    history = _history_section(bill)
    if history:
        parts += [history, ""]
    return "\n".join(parts)


def bill_path(bill: Bill, base_dir: str) -> str:
    session_dir = str(bill.session).replace(" ", "-")
    type_dir = bill.document_type.abbreviation(bill.chamber)
    filename = f"{type_dir}-{bill.number:04d}{bill.suffix}.md"
    return os.path.join(base_dir, "bills", session_dir, type_dir, filename)


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

def cmd_bills(client: Client, args):
    if args.id is not None:
        _show_bill(client, args)
        return

    session = resolve_session(client, args.session)
    filters = {}
    if args.chamber:
        filters["chamberTypes"] = [Chamber[args.chamber.title()].value]
    if args.doc_type:
        filters["documentTypes"] = [DocumentType[args.doc_type.title()].value]

    if args.fetch:
        _fetch_bills(client, args, session, filters)
        return

    _list_bills(client, args, session, filters)


def _show_bill(client: Client, args):
    bill = get_bill(client, args.id)
    print(f"{bill.label} — {bill.title}")
    print(f"Session:   {bill.session}")
    enacted_str = paint("true", _BOLD, _GREEN) if bill.status.is_enacted else "false"
    vetoed_str  = paint("true", _BOLD, _RED)   if bill.status.is_vetoed  else "false"
    print(f"Status:    {bill.status}  (enacted={enacted_str}, vetoed={vetoed_str})")
    print(f"PDF:       {bill.pdf_url()}")
    print()
    print("Sponsors:")
    for s in sorted(bill.sponsors, key=lambda x: x.sequence):
        role = "primary" if s.sequence == 1 else "co-sponsor"
        print(f"  {s.name} ({s.district}) [{role}]")
    if bill.house_committee:
        print(f"House committee: {bill.house_committee.name}")
    if bill.senate_committee:
        print(f"Senate committee: {bill.senate_committee.name}")
    if bill.status_history:
        print()
        print("History:")
        for event in sorted(bill.status_history, key=lambda e: e.date):
            print(f"  {event}")
    if args.text:
        text = get_bill_text(client, bill)
        if text:
            print()
            MarkdownRenderer().print(text + "\n")
    elif bill.first_reader:
        print()
        print("Summary:")
        print(f"  {bill.first_reader}")


def _list_bills(client, args, session, filters):
    limit = None if args.all else (args.limit or 20)
    count = 0
    for bill in search_bills(client, session.id, **filters):
        if args.enacted and not bill.status.is_enacted:
            continue
        date = fmt_status_date(bill.status_date)
        print(f"{bill.id:6d}  {bill.label:8s}  {date}  {colorize_status(bill.status)}  {bill.title[:55]}")
        count += 1
        if limit and count >= limit:
            print("  ... (use --all or --limit N to see more)", file=sys.stderr)
            break


def _fetch_bills(client, args, session, filters):
    print(f"Session: {session}")
    out = args.out or os.path.join(_REPO_ROOT, "legislation")
    total = written = skipped = 0

    for bill in search_bills(client, session.id, **filters):
        total += 1
        if args.enacted and not bill.status.is_enacted:
            skipped += 1
            continue

        try:
            full_bill = get_bill(client, bill.id)
        except Exception as e:
            print(f"  Warning: could not fetch detail for {bill.label}: {e}", file=sys.stderr)
            full_bill = bill

        text = ""
        try:
            text = get_bill_text(client, full_bill)
        except Exception as e:
            print(f"  Warning: could not fetch text for {full_bill.label}: {e}", file=sys.stderr)

        path = bill_path(full_bill, out)

        if args.dry_run:
            print(path)
            continue

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(bill_to_markdown(full_bill, text))

        written += 1
        if written % 10 == 0:
            print(f"  {written} written ({full_bill.label})...")

        time.sleep(args.delay)

    print(f"\nDone. Total: {total}, written: {written}, skipped: {skipped}")
