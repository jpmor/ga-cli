from html.parser import HTMLParser

from .models import Section


class _LiNode:
    __slots__ = ("depth", "buf", "children")

    def __init__(self, depth: int):
        self.depth = depth
        self.buf = ""
        self.children: list["_LiNode"] = []


def _flatten(node: _LiNode) -> list[tuple[int, str]]:
    """Pre-order traversal: parent text, then children."""
    result = []
    text = " ".join(node.buf.split())
    if text:
        result.append((node.depth, text))
    for child in node.children:
        result.extend(_flatten(child))
    return result


class _SectionParser(HTMLParser):
    """Extract title, body, and history from a Georgia Code section page."""

    def __init__(self):
        super().__init__()
        self.section_title = ""

        self._in_h1 = False
        self._h1_cur = ""
        self._h1_lines: list[str] = []

        self._in_content = False   # inside div#codes-content
        self._div_depth = 0
        self._ul_depth = 0
        self._li_stack: list[_LiNode] = []
        self._roots: list[_LiNode] = []

        self._in_em = False
        self._em_buf = ""
        self._history: list[str] = []

        self._p_depth = 0            # <p> nesting depth inside codes-content
        self._p_buf = ""             # text buffer for prose sections (no <ul>)
        self._paras: list[str] = []  # collected prose paragraphs

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)

        if tag == "h1" and "heading-1" in attrs_d.get("class", ""):
            self._in_h1 = True
            return

        if tag == "br" and self._in_h1:
            line = self._h1_cur.strip()
            if line:
                self._h1_lines.append(line)
            self._h1_cur = ""
            return

        if tag == "div" and attrs_d.get("id") == "codes-content":
            self._in_content = True
            return

        if not self._in_content:
            return

        if tag == "div":
            self._div_depth += 1
        elif tag == "ul":
            self._ul_depth += 1
        elif tag == "li":
            self._li_stack.append(_LiNode(self._ul_depth))
        elif tag == "p" and not self._li_stack:
            self._p_depth += 1
        elif tag == "em" and not self._li_stack:
            self._in_em = True
            self._em_buf = ""

    def handle_endtag(self, tag):
        if tag == "h1" and self._in_h1:
            if self._h1_cur.strip():
                self._h1_lines.append(self._h1_cur.strip())
            self._in_h1 = False
            if self._h1_lines:
                last = self._h1_lines[-1]
                self.section_title = last.split(" - ", 1)[-1]
            return

        if not self._in_content:
            return

        if tag == "div":
            if self._div_depth == 0:
                self._in_content = False
            else:
                self._div_depth -= 1
        elif tag == "ul":
            self._ul_depth = max(0, self._ul_depth - 1)
        elif tag == "li":
            if self._li_stack:
                node = self._li_stack.pop()
                if self._li_stack:
                    self._li_stack[-1].children.append(node)
                else:
                    self._roots.append(node)
        elif tag == "p" and not self._li_stack and self._p_depth > 0:
            self._p_depth -= 1
            text = " ".join(self._p_buf.split())
            if text:
                self._paras.append(text)
            self._p_buf = ""
        elif tag == "em" and self._in_em:
            self._in_em = False
            text = " ".join(self._em_buf.split())
            if text:
                self._history.append(text)

    def handle_data(self, data):
        if self._in_h1:
            self._h1_cur += data
        elif self._in_content:
            if self._li_stack:
                self._li_stack[-1].buf += data
            elif self._in_em:
                self._em_buf += data
            elif self._p_depth > 0:
                self._p_buf += data


def parse_section(section_id: str, html: str, year: int | None, url: str) -> Section:
    p = _SectionParser()
    p.feed(html)

    if p._roots:
        parts = []
        for root in p._roots:
            parts.extend(_flatten(root))
        lines = []
        for depth, text in parts:
            indent = "  " * (depth - 1)
            lines.append(f"{indent}{text}")
        body = "\n".join(lines)
    else:
        body = "\n\n".join(p._paras)

    return Section(
        id=section_id,
        title=p.section_title,
        body=body,
        history="\n".join(p._history),
        year=year,
        url=url,
    )
