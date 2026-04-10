import re
from typing import Iterator

from ..client import Client
from ..models import Bill


def get_bill(client: Client, legislation_id: int) -> Bill:
    return Bill.from_detail(client.get(f"legislation/detail/{legislation_id}"))


def get_bill_text(client: Client, bill: Bill) -> str:
    """Return the bill's full text as plain text, extracted from the HTML pages."""
    v = bill.latest_version
    if not v:
        return ""
    pages = client.get(f"legislation/html/{bill.session.library}/{v.id}")
    return _html_pages_to_text(pages)


def search_bills(
    client: Client,
    session_id: int,
    page_size: int = 250,
    **filters,
) -> Iterator[Bill]:
    """
    Yield all bills for a session, paginating automatically.

    Optional filters (passed as keyword args to the POST body):
      sponsorIds, committeeIds, documentTypes, chamberTypes, keywords, etc.
    """
    body = {"sessionId": session_id, **filters}
    page = 0
    while True:
        data = client.post(f"Legislation/Search/{page_size}/{page}", body)
        results = data.get("results", [])
        if not results:
            break
        for row in results:
            yield Bill.from_search(row)
        if len(results) < page_size:
            break
        page += 1


def _html_pages_to_text(pages: list[str]) -> str:
    """Extract plain text from the positioned-span HTML returned by the API.

    The API returns PDF-rendered HTML with absolute-positioned spans. Spans
    containing only line numbers, LC draft headers, or page footers are stripped.
    """
    tokens = []
    for page in pages:
        for span in re.findall(r'<span[^>]*>([^<]*)</span>', page):
            text = span.replace('&nbsp;', ' ').strip()
            if not text:
                continue
            if re.fullmatch(r'\d+', text):
                continue
            if re.fullmatch(r'(\d{2}\s+)?LC\s+\d+\s+\d+(\w*)?', text):
                continue
            if re.fullmatch(r'[HS]\. [BR]\. \d+.*- \d+ -', text):
                continue
            tokens.append(text)
    return ' '.join(tokens)
