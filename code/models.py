from dataclasses import dataclass


@dataclass
class Section:
    id: str         # e.g. "1-1-1"
    title: str      # e.g. "Enactment of Code"
    body: str       # statute text
    history: str    # history line(s), empty if none
    year: int | None
    url: str
