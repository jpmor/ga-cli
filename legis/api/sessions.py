from ..client import Client
from ..models import Session


def get_sessions(client: Client) -> list[Session]:
    return [Session.from_api(s) for s in client.get("sessions")]


def get_current_session(client: Client) -> Session:
    return next(s for s in get_sessions(client) if s.is_current)
