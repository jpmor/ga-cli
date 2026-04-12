from __future__ import annotations
import urllib.error
from dataclasses import dataclass, field

from .client import Client
from .committees import Chamber


@dataclass
class MemberCommittee:
    id: int
    name: str
    chamber: Chamber
    role: str

    @classmethod
    def from_api(cls, data: dict) -> MemberCommittee:
        c = data["committee"]
        return cls(id=c["id"], name=c["name"], chamber=Chamber(c["chamber"]), role=data.get("role", "Member"))


@dataclass
class Member:
    id: int
    name: str
    chamber_type: Chamber
    district: str           # e.g. "43rd"
    party: int              # 0 = Democrat, 1 = Republican
    city: str
    occupation: str = ""
    phone: str = ""
    residence: str = ""
    committees: list[MemberCommittee] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict) -> Member:
        number = data.get("districtNumber") or data["district"]["number"]
        return cls(
            id=data["id"],
            name=data.get("fullName", "").strip(),
            chamber_type=Chamber(data["district"]["chamberType"]),
            district=f"{number}{data['district'].get('suffix', '')}",
            party=data.get("party", -1),
            city=data.get("city", ""),
        )

    @classmethod
    def from_detail(cls, data: dict) -> Member:
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
            chamber_type=Chamber(data["chamber"]),
            district=f"{data.get('districtNumber', '')}{data.get('districtSuffix', '')}",
            party=data.get("party", -1),
            city=data.get("residence", "").strip(),
            occupation=data.get("occupation", "") or "",
            phone=addr.get("phone", "") or "",
            residence=data.get("residence", "").strip(),
            committees=committees,
        )

    @property
    def title(self) -> str:
        return "Representative" if self.chamber_type == Chamber.House else "Senator"

    @property
    def party_name(self) -> str:
        return {0: "D", 1: "R"}.get(self.party, "?")

    def __str__(self) -> str:
        return f"{self.title} {self.name}"


def get_members(client: Client, session_id: int, chamber: Chamber | None = None) -> list[Member]:
    path = f"members/list/{session_id}"
    if chamber:
        path += f"?chamber={chamber.name.lower()}"
    return [Member.from_api(m) for m in client.get(path)]


def get_member(client: Client, member_id: int, session_id: int) -> Member:
    for chamber in ("house", "senate"):
        try:
            data = client.get(f"members/detail/{member_id}?session={session_id}&chamber={chamber}")
            return Member.from_detail(data)
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
    raise ValueError(f"Member {member_id} not found in session {session_id}")
