from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterator

from enum import IntEnum

from .client import Client
from .committees import Chamber
from .sessions import Session
from .committees import Committee


class DocumentType(IntEnum):
    Bill = 1
    Resolution = 2

    def abbreviation(self, chamber: Chamber) -> str:
        prefix = "H" if chamber == Chamber.House else "S"
        suffix = "B" if self == DocumentType.Bill else "R"
        return prefix + suffix


# ---------------------------------------------------------------------------
# Supporting types
# ---------------------------------------------------------------------------

class BillStatus:
    ENACTED = frozenset({
        "House Date Signed by Governor",
        "Senate Date Signed by Governor",
        "House Read and Adopted",
        "Senate Read and Adopted",
    })
    VETOED = frozenset({
        "House Date Vetoed by Governor",
        "Senate Date Vetoed by Governor",
    })

    def __init__(self, name: str):
        self.name = name.strip()

    @property
    def is_enacted(self) -> bool:
        return self.name in self.ENACTED

    @property
    def is_vetoed(self) -> bool:
        return self.name in self.VETOED

    def __str__(self) -> str:
        return self.name


@dataclass
class BillVersion:
    id: int
    name: str
    version_number: int
    is_current: bool

    @classmethod
    def from_api(cls, data: dict) -> BillVersion:
        return cls(
            id=data["id"],
            name=data["name"],
            version_number=data["versionNumber"],
            is_current=data.get("isCurrent", False),
        )


@dataclass
class Sponsor:
    member_id: int
    name: str
    district: str
    sequence: int
    sponsor_type: int   # 1 = author/primary, 2 = co-sponsor

    @classmethod
    def from_api(cls, data: dict) -> Sponsor:
        return cls(
            member_id=data["memberId"],
            name=data["name"].strip(),
            district=data.get("district", ""),
            sequence=data["sequence"],
            sponsor_type=data["sponsorType"],
        )

    def __str__(self) -> str:
        return f"{self.name} ({self.district})"


@dataclass
class StatusEvent:
    date: datetime
    name: str

    @classmethod
    def from_api(cls, data: dict) -> StatusEvent:
        return cls(date=datetime.fromisoformat(data["date"]), name=data["name"])

    def __str__(self) -> str:
        return f"{self.date.date()} — {self.name}"


# ---------------------------------------------------------------------------
# Bill
# ---------------------------------------------------------------------------

@dataclass
class Bill:
    id: int
    session: Session
    chamber: Chamber
    document_type: DocumentType
    number: int
    suffix: str
    title: str
    status: BillStatus
    status_date: str
    sponsors: list[Sponsor] = field(default_factory=list)
    house_committee: Committee | None = None
    senate_committee: Committee | None = None
    versions: list[BillVersion] = field(default_factory=list)
    status_history: list[StatusEvent] = field(default_factory=list)
    first_reader: str = ""
    act_veto_number: str = ""

    @classmethod
    def from_search(cls, data: dict) -> Bill:
        return cls(
            id=data["legislationId"],
            session=Session.from_api(data["session"]),
            chamber=Chamber(data["chamberType"]),
            document_type=DocumentType(data["documentType"]),
            number=int(data["number"]),
            suffix=data.get("suffix", ""),
            title=data.get("caption", ""),
            status=BillStatus(data.get("status", "")),
            status_date=data.get("statusDate", ""),
            sponsors=[Sponsor.from_api(s) for s in data.get("sponsors", [])],
            house_committee=Committee.from_api(data["houseCommittee"]) if data.get("houseCommittee") else None,
            senate_committee=Committee.from_api(data["senateCommittee"]) if data.get("senateCommittee") else None,
        )

    @classmethod
    def from_detail(cls, data: dict) -> Bill:
        committees = data.get("committees", [])
        return cls(
            id=data["id"],
            session=Session.from_api(data["session"]),
            chamber=Chamber(data["chamber"]),
            document_type=DocumentType(data["documentType"]),
            number=int(data["number"]),
            suffix=data.get("suffix", ""),
            title=data.get("title", ""),
            status=BillStatus(data.get("status", "")),
            status_date="",
            sponsors=[Sponsor.from_api(s) for s in data.get("sponsors", [])],
            house_committee=next((Committee.from_api(c) for c in committees if c.get("chamber") == 1), None),
            senate_committee=next((Committee.from_api(c) for c in committees if c.get("chamber") == 2), None),
            versions=[BillVersion.from_api(v) for v in data.get("versions", [])],
            status_history=[StatusEvent.from_api(e) for e in data.get("statusHistory", [])],
            first_reader=data.get("firstReader", "").strip(),
            act_veto_number=data.get("actVetoNumber", ""),
        )

    @property
    def label(self) -> str:
        return f"{self.document_type.abbreviation(self.chamber)} {self.number}{self.suffix}"

    @property
    def latest_version(self) -> BillVersion | None:
        current = [v for v in self.versions if v.is_current]
        if current:
            return current[0]
        return max(self.versions, key=lambda v: v.version_number, default=None)

    def pdf_url(self) -> str | None:
        v = self.latest_version
        return f"https://www.legis.ga.gov/api/legislation/document/{self.session.library}/{v.id}" if v else None

    def __str__(self) -> str:
        return f"{self.label} — {self.title}"


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def get_bill(client: Client, legislation_id: int) -> Bill:
    return Bill.from_detail(client.get(f"legislation/detail/{legislation_id}"))


def get_bill_text(client: Client, bill: Bill) -> str:
    v = bill.latest_version
    if not v:
        return ""
    pages = client.get(f"legislation/html/{bill.session.library}/{v.id}")
    return _pages_to_markdown(pages)


def search_bills(client: Client, session_id: int, page_size: int = 250, **filters) -> Iterator[Bill]:
    body = {"sessionId": session_id, **filters}
    page = 0
    while True:
        data = client.post(f"Legislation/Search/{page_size}/{page}", body)
        results = data.get("results", [])
        if not results:
            break
        for row in results:
            yield Bill.from_search(row)
        if len(results) < page_size:
            break
        page += 1


# ---------------------------------------------------------------------------
# Bill text extraction from PDF-rendered HTML
# ---------------------------------------------------------------------------

def _pages_to_markdown(pages: list[str]) -> str:
    """Extract bill text as markdown from PDF-rendered HTML.

    Integer spans are PDF line-numbers used as delimiters. Content before
    line 1 (title/sponsor header) is dropped. Lines are joined into flowing
    paragraphs; SECTION/PART headings become ## markdown headers.
    """
    lines = _collect_lines(pages)
    lines = _heal_page_breaks(lines)
    return _to_markdown(lines)


def _collect_lines(pages: list[str]) -> list[str]:
    lines: list[str] = []
    current: list[str] = []
    for page in pages:
        for span in re.findall(r'<span[^>]*>([^<]*)</span>', page):
            text = span.replace('&nbsp;', ' ').strip()
            if not text:
                continue
            if re.fullmatch(r'\d+', text):
                lines.append(_join_fragments(current))
                current = []
                continue
            if re.fullmatch(r'(\d{2}\s+)?LC\s+\d+\s+\d+[\w/]*', text):
                continue
            if re.fullmatch(r'[HS]\. [BR]\. \d+.*', text):
                continue
            if re.fullmatch(r'-\s*\d+\s*-', text):
                continue
            # Strip leading legislative line number bundled into span (e.g. "10 Article" → "Article")
            text = re.sub(r'^\d{1,3} ', '', text)
            if not text:
                continue
            # Enum markers at span start (e.g. "(1)", "(a)", "(b)(1)") begin a new logical line
            if _ENUM_START.match(text):
                lines.append(_join_fragments(current))
                current = []
            current.append(text)
    if current:
        lines.append(_join_fragments(current))
    return lines


def _join_fragments(tokens: list[str]) -> str:
    if not tokens:
        return ''
    result = tokens[0]
    for token in tokens[1:]:
        # Concatenate without space only for short fragments (single chars or 2-char
        # suffixes like 'th'/'nd') — avoids merging full words after line-number stripping.
        if result[-1].isalnum() and token[0].isalpha() and len(token) <= 2:
            result += token
        else:
            result += ' ' + token
    return result


def _heal_page_breaks(raw_lines: list[str]) -> list[str]:
    """Skip blank runs that are mid-sentence page breaks (next line starts lowercase)."""
    merged: list[str] = []
    i = 0
    while i < len(raw_lines):
        line = raw_lines[i]
        if not line and merged and merged[-1]:
            j = i
            while j < len(raw_lines) and not raw_lines[j]:
                j += 1
            if j < len(raw_lines) and raw_lines[j][0].islower():
                i = j
                continue
        merged.append(line)
        i += 1
    return merged


_HEAD = re.compile(r'\b(?:SECTION \d+(?:-\d+)?\.?|PART (?:[IVX]+|\d+)(?:\s|$))')
_HEAD_SPLIT = re.compile(r'(?=\b(?:SECTION \d+(?:-\d+)?\.?|PART (?:[IVX]+|\d+)(?:\s|$)))')
_ENUM_START = re.compile(r'^\((?:[a-zA-Z]|\d+)\)')
_ENUM_MARKER = re.compile(r'^((?:\([a-zA-Z0-9]+\))+)\s*(.*)', re.DOTALL)

# Georgia statute enumeration hierarchy (determined by last component of marker):
#   (a)/(b)/(c)         single lowercase letter   → level 1
#   (1)/(2)/(3)         digits                    → level 2
#   (A)/(B)/(C)         single uppercase letter   → level 3
#   (i)/(ii)/(iii)      multi-char lowercase Roman → level 4
#   (I)/(II)/(III)      multi-char uppercase Roman → level 4
_ENUM_LEVELS = [
    (re.compile(r'^\d+$'),               2),
    (re.compile(r'^[A-Z]$'),             3),
    (re.compile(r'^[ivxlcdm]{2,}$'),     4),
    (re.compile(r'^[IVXLCDM]{2,}$'),     4),
]

def _enum_level(marker: str) -> int:
    last = re.findall(r'\(([a-zA-Z0-9]+)\)', marker)[-1]
    for pattern, level in _ENUM_LEVELS:
        if pattern.match(last):
            return level
    return 1  # single lowercase letter


def _to_markdown(raw_lines: list[str]) -> str:
    skip = 0
    while skip < len(raw_lines) and not raw_lines[skip]:
        skip += 1
    skip += 1

    out: list[str] = []
    para: list[str] = []
    for line in raw_lines[skip:]:
        if not line:
            _flush(para, out)
            if out and out[-1] != '':
                out.append('')
        elif _ENUM_START.match(line):
            _flush(para, out)
            para.append(line)
        else:
            para.append(line)
    _flush(para, out)

    result: list[str] = []
    for line in out:
        if not line and result and not result[-1]:
            continue
        result.append(line)
    return '\n'.join(result).strip()


def _flush(para: list[str], out: list[str]) -> None:
    if para:
        _emit(' '.join(para), out)
        para.clear()


def _emit(text: str, out: list[str]) -> None:
    for part in _HEAD_SPLIT.split(text):
        part = part.strip()
        if not part:
            continue
        m = re.match(r'((?:SECTION \d+(?:-\d+)?\.?|PART (?:[IVX]+|\d+)))\s*(.*)', part, re.DOTALL)
        if m and _HEAD.match(m.group(1)):
            if out and out[-1] != '':
                out.append('')
            out.append(f'## {m.group(1)}')
            out.append('')
            if m.group(2).strip():
                out.append(m.group(2).strip())
            continue
        m = _ENUM_MARKER.match(part)
        if m:
            components = re.findall(r'\([a-zA-Z0-9]+\)', m.group(1))
            if out and out[-1] != '':
                out.append('')
            for comp in components:
                level = _enum_level(comp)
                hdr = '#' * (level + 2)
                out.append(f'{hdr} {comp}')
            if m.group(2).strip():
                out.append(m.group(2).strip())
        else:
            out.append(part)
