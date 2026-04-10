"""
Georgia General Assembly API client.

Auth: SHA512-based token scheme derived from the site's public JS bundle.
Token endpoint: GET /api/authentication/token?key={sha512}&ms={timestamp}
"""

import hashlib
import json
import time
import urllib.error
import urllib.request
from typing import Any

BASE_URL = "https://www.legis.ga.gov/api/"
_OBSCURE_KEY = "jVEXFFwSu36BwwcP83xYgxLAhLYmKk"
_SALT = "QFpCwKfd7f"
_LABEL = "letvarconst"


def _generate_key(ms: int) -> str:
    raw = _SALT + _OBSCURE_KEY + _LABEL + str(ms)
    return hashlib.sha512(raw.encode()).hexdigest()


class Client:
    def __init__(self):
        self._token: str | None = None
        self._token_expires: float = 0

    def _get_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expires:
            return self._token

        ms = int(now * 1000)
        key = _generate_key(ms)
        url = f"{BASE_URL}authentication/token?key={key}&ms={ms}"
        req = urllib.request.Request(url, headers={"User-Agent": "ga-law/1.0"})
        with urllib.request.urlopen(req) as resp:
            self._token = json.loads(resp.read())
        # Tokens expire in 5 minutes per the JWT exp claim; refresh at 4 min
        self._token_expires = now + 240
        return self._token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Accept": "application/json",
            "User-Agent": "ga-law/1.0",
        }

    def get(self, path: str, **params) -> Any:
        url = BASE_URL + path
        if params:
            qs = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{qs}"
        req = urllib.request.Request(url, headers=self._headers())
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())

    def post(self, path: str, body: dict) -> Any:
        url = BASE_URL + path
        data = json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, headers={
            **self._headers(),
            "Content-Type": "application/json",
        })
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
