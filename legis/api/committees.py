from ..client import Client
from ..models import Chamber, Committee


def get_committees(client: Client, session_id: int, chamber: Chamber | None = None) -> list[Committee]:
    data = client.get(f"committees/list/{session_id}")
    committees = [Committee.from_api(c) for c in data]
    if chamber:
        committees = [c for c in committees if c.chamber == chamber]
    return sorted(committees, key=lambda c: (c.chamber.value, c.name))


def get_committee(client: Client, committee_id: int, session_id: int) -> Committee:
    data = client.get(f"committees/details/{committee_id}/{session_id}")
    # Detail endpoint omits top-level chamber; infer from first active member's district
    chamber_type = 1
    for m in data.get("members", []):
        if not m.get("dateVacated"):
            chamber_type = m.get("district", {}).get("chamberType", 1)
            break
    data["chamber"] = chamber_type
    return Committee.from_detail(data)
