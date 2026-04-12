"""Terminal rendering for OCGA markdown output."""

import os
import re
import sys


_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_RED    = "\033[31m"
_GREEN  = "\033[32m"
_YELLOW = "\033[33m"
_BLUE   = "\033[34m"
_CYAN   = "\033[36m"


def _color_enabled() -> bool:
    return sys.stdout.isatty() and "NO_COLOR" not in os.environ


def paint(text: str, *codes: str) -> str:
    """Wrap *text* in ANSI *codes* when stdout is a TTY and NO_COLOR is unset."""
    if not codes or not _color_enabled():
        return text
    return "".join(codes) + text + _RESET


class MarkdownRenderer:
    """Render OCGA-flavored markdown with ANSI color when writing to a TTY.

    Plain text is passed through unchanged when stdout is not a terminal or
    when color is explicitly disabled (NO_COLOR env var).
    """

    def __init__(self, file=None):
        self._file = file or sys.stdout
        self._color = self._file.isatty() and "NO_COLOR" not in __import__("os").environ

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def print(self, text: str) -> None:
        """Render *text* (a markdown string) to the output file."""
        if not self._color:
            self._file.write(text)
            return
        self._file.write(self._render(text))

    # ------------------------------------------------------------------
    # Internal rendering
    # ------------------------------------------------------------------

    def _render(self, text: str) -> str:
        lines = text.split("\n")
        out = []
        for line in lines:
            out.append(self._render_line(line))
        return "\n".join(out)

    def _render_line(self, line: str) -> str:
        # H1  — section title (e.g. "# § 1-4-1. ...")
        if line.startswith("# "):
            return f"{_BOLD}{_CYAN}{line}{_RESET}"

        # H2  — SECTION/PART heading
        if line.startswith("## "):
            return f"{_BOLD}{_YELLOW}{line}{_RESET}"

        # H3-H6 — enumeration markers at levels 1-4, rendered with indentation
        for depth, prefix in enumerate(("### ", "#### ", "##### ", "###### "), start=0):
            if line.startswith(prefix):
                indent = "  " * depth
                label = line[len(prefix):]
                return f"{indent}{_BOLD}{_GREEN}{label}{_RESET}"

        # List items in a TOC (e.g. "- Chapter 1 — ...")
        if line.startswith("- "):
            # bold the leading "- " bullet
            return f"{_DIM}-{_RESET} {line[2:]}"

        # Subsection labels: (a), (b), (1), (2), etc. at start of line
        m = re.match(r"^(\s*)(\([a-z0-9]+\))(\s)", line)
        if m:
            rest = line[m.end():]
            return f"{m.group(1)}{_BOLD}{_GREEN}{m.group(2)}{_RESET}{m.group(3)}{rest}"

        # History amendment lines ("Amended by ...")
        if line.startswith("Amended by ") or line.startswith("Added by "):
            return f"{_DIM}{line}{_RESET}"

        return line
