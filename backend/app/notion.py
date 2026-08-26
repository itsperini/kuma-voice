import json
from typing import Any

import httpx

from .config import Settings

NOTION_VERSION = "2022-06-28"


class NotionError(RuntimeError):
    pass


class NotionClient:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(
            base_url="https://api.notion.com/v1",
            timeout=httpx.Timeout(20.0, connect=10.0),
        )

    @property
    def headers(self) -> dict[str, str]:
        key = self.settings.notion_api_key.strip()
        if not key:
            raise NotionError("NOTION_API_KEY is not configured on the Kuma Voice server.")
        return {
            "Authorization": f"Bearer {key}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    async def search(self, query: str) -> str:
        query = query.strip()
        if not query:
            raise NotionError("notion_search requires a query")
        payload = await self._request(
            "POST",
            "/search",
            json={"query": query, "page_size": 5},
        )
        results = []
        for item in payload.get("results") or []:
            if not isinstance(item, dict) or item.get("object") != "page":
                continue
            results.append(
                {
                    "id": item.get("id") or "",
                    "title": page_title(item),
                    "url": item.get("url") or "",
                }
            )
        return json.dumps({"results": results}, separators=(",", ":"))

    async def read_page(self, page_id: str = "", query: str = "") -> str:
        resolved_id = await self._resolve_page_id(page_id, query)
        page = await self._request("GET", f"/pages/{resolved_id}")
        blocks = await self._request(
            "GET",
            f"/blocks/{resolved_id}/children",
            params={"page_size": 50},
        )
        text = blocks_to_text(blocks.get("results") or [])
        return json.dumps(
            {
                "id": resolved_id,
                "title": page_title(page),
                "url": page.get("url") or "",
                "text": text[:2_000],
            },
            separators=(",", ":"),
        )

    async def add_note(self, text: str, page_id: str = "", query: str = "") -> str:
        note = text.strip()
        if not note:
            raise NotionError("notion_add_note requires text")
        resolved_id = await self._resolve_page_id(
            page_id,
            query,
            default=self.settings.notion_notes_page_id.strip(),
        )
        await self._request(
            "PATCH",
            f"/blocks/{resolved_id}/children",
            json={
                "children": [
                    {
                        "object": "block",
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {
                            "rich_text": [{"type": "text", "text": {"content": note[:1_800]}}]
                        },
                    }
                ]
            },
        )
        return json.dumps(
            {"ok": True, "page_id": resolved_id, "saved": note[:1_800]},
            separators=(",", ":"),
        )

    async def _resolve_page_id(self, page_id: str, query: str, default: str = "") -> str:
        if page_id.strip():
            return page_id.strip()
        if default:
            return default
        if not query.strip():
            raise NotionError(
                "No Notion page specified. Share a page with the integration "
                "and set NOTION_NOTES_PAGE_ID, or pass page_id/query."
            )
        payload = json.loads(await self.search(query))
        results = payload.get("results") or []
        if not results:
            raise NotionError(f"No Notion page matched {query!r}")
        return results[0]["id"]

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = await self._http.request(method, path, headers=self.headers, **kwargs)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            raise NotionError(
                f"Notion request failed with {exc.response.status_code}: {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise NotionError(f"Could not reach Notion: {exc}") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise NotionError("Notion returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise NotionError("Notion returned an unexpected payload")
        return payload

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http.aclose()


def page_title(page: dict[str, Any]) -> str:
    properties = page.get("properties")
    if not isinstance(properties, dict):
        return ""
    for value in properties.values():
        if isinstance(value, dict) and value.get("type") == "title":
            return rich_text(value.get("title"))
    return ""


def blocks_to_text(blocks: list[Any]) -> str:
    parts: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        body = block.get(block_type) if isinstance(block_type, str) else None
        if not isinstance(body, dict):
            continue
        text = rich_text(body.get("rich_text"))
        if text:
            parts.append(text)
    return "\n".join(parts)


def rich_text(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    return "".join(
        item.get("plain_text", "")
        for item in value
        if isinstance(item, dict)
    ).strip()
