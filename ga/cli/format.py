from datetime import datetime

from ga.render import paint, _BOLD, _RED, _GREEN, _YELLOW, _BLUE


def party(p: str) -> str:
    if p == "D":
        return paint(p, _BOLD, _BLUE)
    if p == "R":
        return paint(p, _BOLD, _RED)
    return p


def colorize_status(status) -> str:
    text = f"{status.name[:44]:<44}"
    if status.is_enacted:
        return paint(text, _BOLD, _GREEN)
    if status.is_vetoed:
        return paint(text, _BOLD, _RED)
    if "Passed" in status.name or "Adopted" in status.name:
        return paint(text, _YELLOW)
    return text


def fmt_status_date(date_str: str) -> str:
    if not date_str:
        return "        "
    try:
        return datetime.strptime(date_str, "%m/%d/%Y").strftime("%m/%d/%y")
    except ValueError:
        return "        "
