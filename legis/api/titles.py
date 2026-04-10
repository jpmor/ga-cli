from ..client import Client
from ..models import CodeTitle


def get_code_titles(client: Client) -> list[CodeTitle]:
    return [CodeTitle.from_api(t) for t in client.get("georgia-code/titles")]
