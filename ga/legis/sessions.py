from __future__ import annotations
from dataclasses import dataclass

from .client import Client


@dataclass
class Session:
    id: int
    description: str
    library: str        # e.g. "20252026" — used in document URLs
    is_current: bool
    type: int           # 0 = regular, nonzero = special

    @classmethod
    def from_api(cls, data: dict) -> Session:
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


def get_sessions(client: Client) -> list[Session]:
    return [Session.from_api(s) for s in client.get("sessions")]


def get_current_session(client: Client) -> Session:
    return next(s for s in get_sessions(client) if s.is_current)
