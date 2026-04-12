from __future__ import annotations
import re
from dataclasses import dataclass, field
from enum import IntEnum

from .client import Client


class Chamber(IntEnum):
    House = 1
    Senate = 2


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
        return cls(
            id=data["id"],
            name=data["name"],
            role=data.get("role", "Member"),
            district=f"{d.get('number', '')}{d.get('suffix', '')}",
            vacated=bool(data.get("dateVacated")),
        )


@dataclass
class Committee:
    id: int
    name: str
    chamber: Chamber
    description: str = ""
    phone: str = ""
    members: list[CommitteeMember] = field(default_factory=list)
    subcommittees: list[str] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict) -> Committee:
        return cls(id=data["id"], name=data["name"], chamber=Chamber(data["chamber"]))

    @classmethod
    def from_detail(cls, data: dict) -> Committee:
        addr = data.get("address") or {}
        members = [
            CommitteeMember.from_api(m)
            for m in data.get("members", [])
            if not m.get("dateVacated")
        ]
        members.sort(key=lambda m: (m.role != "Chairman", m.role != "Vice Chairman", m.name))
        return cls(
            id=data["id"],
            name=data["name"],
            chamber=Chamber(data["chamber"]) if "chamber" in data else Chamber(
                data.get("members", [{}])[0].get("district", {}).get("chamberType", 1)
            ),
            description=re.sub(r'<[^>]+>', '', data.get("description") or "").strip(),
            phone=addr.get("phone", ""),
            members=members,
            subcommittees=[s["name"] for s in data.get("subcommittees", [])],
        )

    def __str__(self) -> str:
        return f"{self.chamber.name} {self.name}"


def get_committees(client: Client, session_id: int, chamber: Chamber | None = None) -> list[Committee]:
    committees = [Committee.from_api(c) for c in client.get(f"committees/list/{session_id}")]
    if chamber:
        committees = [c for c in committees if c.chamber == chamber]
    return sorted(committees, key=lambda c: (c.chamber.value, c.name))


def get_committee(client: Client, committee_id: int, session_id: int) -> Committee:
    data = client.get(f"committees/details/{committee_id}/{session_id}")
    # Detail endpoint omits top-level chamber; infer from first active member
    chamber_type = next(
        (m["district"]["chamberType"] for m in data.get("members", []) if not m.get("dateVacated")),
        1,
    )
    data["chamber"] = chamber_type
    return Committee.from_detail(data)
