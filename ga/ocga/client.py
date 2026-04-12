import os
import re
import threading
import urllib.error

from curl_cffi import requests as cffi_requests

from .limiter import AdaptiveLimiter

_HOST = "https://law.justia.com"
GA_CODE_BASE = f"{_HOST}/codes/georgia"

_local = threading.local()
_limiter = AdaptiveLimiter()


def set_initial_concurrency(n: int):
    _limiter.set_initial(n)


def _session() -> cffi_requests.Session:
    if not hasattr(_local, "session"):
        _local.session = cffi_requests.Session(impersonate="firefox")
        cf_clearance = os.environ.get("CF_CLEARANCE")
        if cf_clearance:
            _local.session.cookies.set("cf_clearance", cf_clearance, domain=".justia.com")
    return _local.session


def _reset_session():
    if hasattr(_local, "session"):
        del _local.session
    if hasattr(_local, "last_url"):
        del _local.last_url


def fetch_html(url: str) -> str:
    _limiter.acquire()
    try:
        session = _session()
        headers = {}
        last_url = getattr(_local, "last_url", None)
        if last_url:
            headers["Referer"] = last_url

        try:
            resp = session.get(url, headers=headers, timeout=(1, 1), allow_redirects=True)
        except Exception:
            _limiter.on_rate_limit()
            _reset_session()
            raise

        if resp.status_code == 404:
            _limiter.on_success()
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        if resp.status_code in (403, 429):
            _limiter.on_rate_limit()
            _reset_session()
            raise urllib.error.HTTPError(url, resp.status_code, "Rate limited", {}, None)
        if resp.status_code >= 400:
            _limiter.on_success()
            raise urllib.error.HTTPError(url, resp.status_code, "HTTP error", {}, None)

        _limiter.on_success()
        _local.last_url = url
        return resp.text
    finally:
        _limiter.release()


def _chapter_base(title_num: str, chapter_num: str, year: int | None) -> str:
    base = f"{GA_CODE_BASE}/{year}" if year else GA_CODE_BASE
    ch = chapter_num.lower()
    prefix = "" if ch.startswith("article-") else "chapter-"
    return f"{base}/title-{title_num.lower()}/{prefix}{ch}"


def resolve_section_url(section_id: str, year: int | None = None) -> str:
    """Return the URL for a section, resolving article sub-levels if needed."""
    sid = section_id.lower()
    parts = sid.split("-", 2)
    title_num, chapter_num = parts[0], parts[1]
    chapter_base = _chapter_base(title_num, chapter_num, year)
    direct = f"{chapter_base}/section-{sid}/"

    try:
        fetch_html(direct)
        return direct
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise

    # Some titles use article-N instead of chapter-N (e.g. Title 11 - UCC)
    base = f"{GA_CODE_BASE}/{year}" if year else GA_CODE_BASE
    article_direct = f"{base}/title-{title_num}/article-{chapter_num}/section-{sid}/"
    if article_direct != direct:
        try:
            fetch_html(article_direct)
            return article_direct
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise

    # Decimal section IDs (e.g. 2-23-3.1) may use hyphens in URLs
    if "." in sid:
        hyphenated = f"{chapter_base}/section-{sid.replace('.', '-')}/"
        try:
            fetch_html(hyphenated)
            return hyphenated
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise

    # Chapter has article/part sub-levels — discover them and search
    chapter_html = None
    chapter_path = None
    for candidate in [chapter_base, f"{base}/title-{title_num}/article-{chapter_num}"]:
        try:
            chapter_html = fetch_html(f"{candidate}/")
            chapter_path = candidate.replace(_HOST, "")
            break
        except urllib.error.HTTPError:
            continue
    if chapter_html is None:
        raise urllib.error.HTTPError(direct, 404, f"Section {section_id} not found", {}, None)
    sub_paths = re.findall(
        rf'href="({re.escape(chapter_path)}/(?:article|part)-[\w-]+/)"', chapter_html
    )
    if not sub_paths:
        raise urllib.error.HTTPError(direct, 404, f"Section {section_id} not found", {}, None)

    targets = [f"section-{sid}/"]
    if "." in sid:
        targets.append(f"section-{sid.replace('.', '-')}/")

    def _search_page(page_url: str, page_html: str, depth: int = 0) -> str | None:
        for target in targets:
            if target in page_html:
                return f"{page_url}{target}"
        if depth >= 3:
            return None
        page_path = page_url.replace(_HOST, "")
        deeper = re.findall(rf'href="({re.escape(page_path)}(?:article|part|subpart)-[\w-]+/)"', page_html)
        for sub in dict.fromkeys(deeper):
            try:
                sub_html = fetch_html(f"https://law.justia.com{sub}")
            except urllib.error.HTTPError:
                continue
            result = _search_page(f"https://law.justia.com{sub}", sub_html, depth + 1)
            if result:
                return result
        return None

    for sub_path in dict.fromkeys(sub_paths):
        sub_url = f"https://law.justia.com{sub_path}"
        try:
            sub_html = fetch_html(sub_url)
        except urllib.error.HTTPError:
            continue
        result = _search_page(sub_url, sub_html)
        if result:
            return result

    raise urllib.error.HTTPError(direct, 404, f"Section {section_id} not found", {}, None)
