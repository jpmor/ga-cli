import sys

from ga.legis import Client, Session, get_sessions, get_current_session


def resolve_session(client: Client, session_id: int | None) -> Session:
    if session_id is None:
        return get_current_session(client)
    session = next((s for s in get_sessions(client) if s.id == session_id), None)
    if not session:
        print(f"Error: session {session_id} not found.", file=sys.stderr)
        sys.exit(1)
    return session


def cmd_sessions(client: Client, args):
    for s in get_sessions(client):
        print(f"{s.id:4d}  {s.library:12s}  {s.description}{' (current)' if s.is_current else ''}")
