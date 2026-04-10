"""
Data models for Georgia General Assembly legislative objects.

API endpoints discovered:
  GET  /api/sessions                              -> list[Session]
  GET  /api/georgia-code/titles                   -> list[CodeTitle]
  GET  /api/committees/list?sessionId=&chamber=   -> list[Committee]
  GET  /api/members/search-options                -> list[Member]
  GET  /api/legislation/detail/{id}               -> Bill (full)
  GET  /api/legislation/html/{library}/{version}  -> list[str] (HTML pages)
  POST /api/Legislation/Search/{page_size}/{page} -> SearchResult
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import Client


class Chamber(IntEnum):
    House = 1
    Senate = 2


class DocumentType(IntEnum):
    Bill = 1
    Resolution = 2

    def abbreviation(self, chamber: Chamber) -> str:
        prefix = "H" if chamber == Chamber.House else "S"
        suffix = "B" if self == DocumentType.Bill else "R"
        return prefix + suffix


@dataclass
class Session:
    id: int
    description: str
    library: str        # e.g. "20252026" — used in document URLs
    is_current: bool
    type: int           # 0 = regular, nonzero = special

    @classmethod
    def from_api(cls, data: dict) -> Session:
        # library comes back as a full URL; extract just the key part
        raw = data.get("library", "")
        library = raw.rstrip("/").split("/")[-1] if raw else ""
        return cls(
            id=data["id"],
            description=data["description"],
            library=library,
            is_current=data.get("isCurrent", False),
            type=data.get("type", 0),
        )

    def __str__(self) -> str:
        return self.description


@dataclass
class CodeTitle:
    id: int
    code: str           # zero-padded, e.g. "01"
    name: str
    display_name: str

    @classmethod
    def from_api(cls, data: dict) -> CodeTitle:
        return cls(
            id=data["id"],
            code=data["code"],
            name=data["name"].strip(),
            display_name=data["displayName"].strip(),
        )

    def __str__(self) -> str:
        return self.display_name


@dataclass
class CommitteeMember:
    id: int
    name: str
    role: str           # "Chairman", "Vice Chairman", "Member", etc.
    district: str       # e.g. "134th"
    vacated: bool

    @classmethod
    def from_api(cls, data: dict) -> CommitteeMember:
        d = data.get("district", {})
        district = f"{d.get('number', '')}{d.get('suffix', '')}"
        return cls(
            id=data["id"],
            name=data["name"],
            role=data.get("role", "Member"),
            district=district,
            vacated=bool(data.get("dateVacated")),
        )


@dataclass
class Committee:
    id: int
    name: str
    chamber: Chamber
    # Populated from detail endpoint:
    description: str = ""
    phone: str = ""
    members: list[CommitteeMember] = field(default_factory=list)
    subcommittees: list[str] = field(default_factory=list)  # subcommittee names

    @classmethod
    def from_api(cls, data: dict) -> Committee:
        return cls(
            id=data["id"],
            name=data["name"],
            chamber=Chamber(data["chamber"]),
        )

    @classmethod
    def from_detail(cls, data: dict) -> Committee:
        import re
        addr = data.get("address") or {}
        members = [
            CommitteeMember.from_api(m)
            for m in data.get("members", [])
            if not m.get("dateVacated")
        ]
        members.sort(key=lambda m: (m.role != "Chairman", m.role != "Vice Chairman", m.name))
        subcommittees = [s["name"] for s in data.get("subcommittees", [])]
        description = re.sub(r'<[^>]+>', '', data.get("description") or "").strip()
        return cls(
            id=data["id"],
            name=data["name"],
            chamber=Chamber(data["chamber"]) if "chamber" in data else Chamber(
                data.get("members", [{}])[0].get("district", {}).get("chamberType", 1)
            ),
            description=description,
            phone=addr.get("phone", ""),
            members=members,
            subcommittees=subcommittees,
        )

    def __str__(self) -> str:
        return f"{self.chamber.name} {self.name}"


@dataclass
class MemberCommittee:
    id: int
    name: str
    chamber: Chamber
    role: str

    @classmethod
    def from_api(cls, data: dict) -> MemberCommittee:
        c = data["committee"]
        return cls(
            id=c["id"],
            name=c["name"],
            chamber=Chamber(c["chamber"]),
            role=data.get("role", "Member"),
        )


@dataclass
class Member:
    id: int
    name: str
    chamber_type: Chamber
    district: str           # e.g. "43rd"
    party: int              # 0 = Democrat, 1 = Republican
    city: str
    # Populated from detail endpoint:
    occupation: str = ""
    phone: str = ""
    residence: str = ""
    committees: list[MemberCommittee] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict) -> Member:
        """Construct from the full members/list/{sessionId} response."""
        chamber_type = Chamber(data["district"]["chamberType"])
        number = data.get("districtNumber") or data["district"]["number"]
        suffix = data["district"].get("suffix", "")
        return cls(
            id=data["id"],
            name=data.get("fullName", "").strip(),
            chamber_type=chamber_type,
            district=f"{number}{suffix}",
            party=data.get("party", -1),
            city=data.get("city", ""),
        )

    @classmethod
    def from_detail(cls, data: dict) -> Member:
        """Construct from the members/detail/{id} response."""
        chamber_type = Chamber(data["chamber"])
        district = f"{data.get('districtNumber', '')}{data.get('districtSuffix', '')}"
        addr = data.get("capitolAddress") or {}
        committees = [
            MemberCommittee.from_api(m)
            for m in data.get("committeeMemberships", [])
            if not m.get("dateVacated")
        ]
        committees.sort(key=lambda c: (c.role != "Chairman", c.role != "Vice Chairman", c.name))
        return cls(
            id=data.get("id", 0),
            name=data.get("displayName", "").strip(),
            chamber_type=chamber_type,
            district=district,
            party=data.get("party", -1),
            city=data.get("residence", "").strip(),
            occupation=data.get("occupation", "") or "",
            phone=addr.get("phone", "") or "",
            residence=data.get("residence", "").strip(),
            committees=committees,
        )

    @classmethod
    def from_search_options(cls, data: dict) -> Member:
        """Construct from the lightweight members/search-options response."""
        return cls(
            id=data["id"],
            name=data["name"].strip(),
            chamber_type=Chamber(data["chamberType"]),
            district="",
            party=-1,
            city="",
        )

    @property
    def title(self) -> str:
        return "Representative" if self.chamber_type == Chamber.House else "Senator"

    @property
    def party_name(self) -> str:
        return {0: "D", 1: "R"}.get(self.party, "?")

    def __str__(self) -> str:
        return f"{self.title} {self.name}"


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
        return cls(
            date=datetime.fromisoformat(data["date"]),
            name=data["name"],
        )

    def __str__(self) -> str:
        return f"{self.date.date()} — {self.name}"


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


class BillStatus:
    # Statuses that indicate the bill was enacted into law
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
    # Populated only from detail endpoint:
    versions: list[BillVersion] = field(default_factory=list)
    status_history: list[StatusEvent] = field(default_factory=list)
    first_reader: str = ""
    act_veto_number: str = ""

    @classmethod
    def from_search(cls, data: dict) -> Bill:
        """Construct from a search result row (lightweight)."""
        session = Session.from_api(data["session"])
        return cls(
            id=data["legislationId"],
            session=session,
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
        """Construct from the full detail endpoint response."""
        session = Session.from_api(data["session"])
        committees = data.get("committees", [])
        house_committee = next((Committee.from_api(c) for c in committees if c.get("chamber") == 1), None)
        senate_committee = next((Committee.from_api(c) for c in committees if c.get("chamber") == 2), None)
        return cls(
            id=data["id"],
            session=session,
            chamber=Chamber(data["chamber"]),
            document_type=DocumentType(data["documentType"]),
            number=int(data["number"]),
            suffix=data.get("suffix", ""),
            title=data.get("title", ""),
            status=BillStatus(data.get("status", "")),
            status_date="",
            sponsors=[Sponsor.from_api(s) for s in data.get("sponsors", [])],
            house_committee=house_committee,
            senate_committee=senate_committee,
            versions=[BillVersion.from_api(v) for v in data.get("versions", [])],
            status_history=[StatusEvent.from_api(e) for e in data.get("statusHistory", [])],
            first_reader=data.get("firstReader", "").strip(),
            act_veto_number=data.get("actVetoNumber", ""),
        )

    @property
    def label(self) -> str:
        """e.g. 'HB 1' or 'SR 42'"""
        abbr = self.document_type.abbreviation(self.chamber)
        return f"{abbr} {self.number}{self.suffix}"

    @property
    def latest_version(self) -> BillVersion | None:
        current = [v for v in self.versions if v.is_current]
        if current:
            return current[0]
        return max(self.versions, key=lambda v: v.version_number, default=None)

    def pdf_url(self) -> str | None:
        v = self.latest_version
        if not v:
            return None
        return f"https://www.legis.ga.gov/api/legislation/document/{self.session.library}/{v.id}"

    def __str__(self) -> str:
        return f"{self.label} — {self.title}"
