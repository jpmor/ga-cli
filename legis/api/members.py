from ..client import Client
from ..models import Chamber, Member


def get_members(client: Client, session_id: int, chamber: Chamber | None = None) -> list[Member]:
    path = f"members/list/{session_id}"
    if chamber:
        path += f"?chamber={chamber.name.lower()}"
    return [Member.from_api(m) for m in client.get(path)]


def get_member(client: Client, member_id: int, session_id: int) -> Member:
    """Fetch full member detail. Chamber is required by the API; discovered from the member list."""
    members = get_members(client, session_id)
    match = next((m for m in members if m.id == member_id), None)
    if not match:
        raise ValueError(f"Member {member_id} not found in session {session_id}")
    chamber_name = match.chamber_type.name.lower()
    data = client.get(f"members/detail/{member_id}?session={session_id}&chamber={chamber_name}")
    return Member.from_detail(data)
