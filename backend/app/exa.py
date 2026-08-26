import json
from typing import Any

import httpx

from .config import Settings


class ExaError(RuntimeError):
    pass


class ExaClient:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(
            base_url="https://api.exa.ai",
            timeout=httpx.Timeout(20.0, connect=10.0),
        )

    async def search(self, query: str) -> str:
        query = query.strip()
        if not query:
            raise ExaError("web_search requires a non-empty query")

        api_key = self.settings.web_search_api_key
        if not api_key:
            raise ExaError("EXA_API_KEY is not configured on the Kuma Voice server.")

        try:
            response = await self._http.post(
                "/search",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                },
                json={
                    "query": query,
                    "type": "auto",
                    "numResults": 5,
                    "contents": {"highlights": True},
                },
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            raise ExaError(
                f"Exa search failed with {exc.response.status_code}: {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ExaError(f"Could not reach Exa: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise ExaError("Exa returned invalid JSON") from exc

        return json.dumps(compact_exa_results(payload), separators=(",", ":"))

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http.aclose()


def compact_exa_results(payload: dict[str, Any]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        return {"results": results}

    for item in raw_results[:5]:
        if not isinstance(item, dict):
            continue
        results.append(
            {
                "title": _as_text(item.get("title")),
                "url": _as_text(item.get("url")),
                "published": _as_text(
                    item.get("publishedDate") or item.get("published_date")
                ),
                "snippet": _snippet_from(item),
            }
        )
    return {"results": results}


def _snippet_from(item: dict[str, Any]) -> str:
    highlights = item.get("highlights")
    if isinstance(highlights, list):
        parts = [_as_text(part) for part in highlights[:2]]
        snippet = " ".join(part for part in parts if part)
        if snippet:
            return snippet[:500]
    summary = item.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()[:500]
    text = item.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()[:500]
    return ""


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""
