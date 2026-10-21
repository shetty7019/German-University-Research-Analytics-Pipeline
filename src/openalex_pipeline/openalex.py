"""Small OpenAlex API client with cursor pagination and bounded retries."""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://api.openalex.org"
WORK_FIELDS = (
    "id,doi,title,publication_year,publication_date,type,language,cited_by_count,"
    "is_retracted,open_access,primary_topic,authorships,fwci,updated_date"
)


class OpenAlexError(RuntimeError):
    """An API request failed without exposing credentials in its message."""


def redact(text: str, secret: str | None) -> str:
    return text.replace(secret, "***") if secret else text


def short_id(value: str | None) -> str | None:
    """Convert an OpenAlex URL or id to its final id component."""
    if not value:
        return None
    return value.rstrip("/").rsplit("/", maxsplit=1)[-1]


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers["User-Agent"] = "openalex-research-pipeline (portfolio project)"
    return session


class OpenAlexClient:
    def __init__(self, api_key: str | None = None, min_interval: float = 0.2):
        self.api_key = api_key or os.getenv("OPENALEX_API_KEY")
        self.session = build_session()
        self.min_interval = min_interval
        self._last_call = 0.0

    def _throttle(self) -> None:
        wait = self.min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def _get(self, path: str, params: dict[str, Any]) -> requests.Response:
        request_params = dict(params)
        if self.api_key:
            request_params["api_key"] = self.api_key
        self._throttle()
        try:
            response = self.session.get(
                f"{BASE_URL}/{path}", params=request_params, timeout=60
            )
        except requests.RequestException as exc:
            raise OpenAlexError(f"Request to /{path} failed ({type(exc).__name__}).") from None
        if response.status_code == 429:
            raise OpenAlexError("HTTP 429: OpenAlex rate limit or daily budget reached.")
        if response.status_code >= 400:
            snippet = redact(response.text[:300], self.api_key)
            raise OpenAlexError(f"HTTP {response.status_code} on /{path}: {snippet}")
        return response

    def resolve_institution(self, ror: str) -> dict[str, str | None]:
        """Resolve a ROR identifier to its OpenAlex id and display name."""
        normalized_ror = ror.rstrip("/").rsplit("/", maxsplit=1)[-1]
        data = self._get(f"institutions/ror:{normalized_ror}", {}).json()
        return {"institution_id": short_id(data.get("id")), "name": data["display_name"]}

    def iter_work_pages(
        self,
        institution_id: str,
        start: str,
        end: str,
        per_page: int = 100,
        max_works: int = 0,
    ) -> Iterator[tuple[int, dict[str, Any]]]:
        """Yield result pages in cursor order until exhausted or capped."""
        if not 1 <= per_page <= 200:
            raise ValueError("per_page must be between 1 and 200")
        cursor: str | None = "*"
        page_number = 0
        fetched = 0
        while cursor:
            params = {
                "filter": (
                    f"institutions.id:{institution_id},from_publication_date:{start},"
                    f"to_publication_date:{end}"
                ),
                "per_page": per_page,
                "cursor": cursor,
                "select": WORK_FIELDS,
            }
            payload = self._get("works", params).json()
            results = payload.get("results", [])
            page_number += 1
            fetched += len(results)
            yield page_number, payload
            cursor = payload.get("meta", {}).get("next_cursor")
            if not results or (max_works and fetched >= max_works):
                break