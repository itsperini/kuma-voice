from typing import Any, Protocol

from .calendar import GoogleCalendarClient
from .exa import ExaClient
from .notion import NotionClient


class ToolClient(Protocol):
    async def aclose(self) -> None: ...


class ToolRegistry:
    def __init__(
        self,
        search: ExaClient | None = None,
        notion: NotionClient | None = None,
        calendar: GoogleCalendarClient | None = None,
    ) -> None:
        self.search = search
        self.notion = notion
        self.calendar = calendar

    async def run(self, name: str, arguments: dict[str, Any]) -> str:
        if name == "web_search":
            if self.search is None:
                raise RuntimeError("Web search is not configured")
            query = _text(arguments.get("query"))
            if not query:
                raise RuntimeError("web_search requires a query")
            return await self.search.search(query)

        if name == "notion_search":
            if self.notion is None:
                raise RuntimeError("Notion is not configured")
            return await self.notion.search(_text(arguments.get("query")))

        if name == "notion_read_page":
            if self.notion is None:
                raise RuntimeError("Notion is not configured")
            return await self.notion.read_page(
                page_id=_text(arguments.get("page_id")),
                query=_text(arguments.get("query")),
            )

        if name == "notion_add_note":
            if self.notion is None:
                raise RuntimeError("Notion is not configured")
            return await self.notion.add_note(
                text=_text(arguments.get("text")),
                page_id=_text(arguments.get("page_id")),
                query=_text(arguments.get("query")),
            )

        if name == "calendar_upcoming":
            if self.calendar is None:
                raise RuntimeError("Calendar is not configured")
            return await self.calendar.upcoming(
                days=_int(arguments.get("days"), 1),
                max_events=_int(arguments.get("max_events"), 5),
            )

        if name == "calendar_create_event":
            if self.calendar is None:
                raise RuntimeError("Calendar is not configured")
            return await self.calendar.create_event(
                title=_text(arguments.get("title")),
                start=_text(arguments.get("start")),
                end=_text(arguments.get("end")),
                duration_minutes=_int(arguments.get("duration_minutes"), 30),
            )

        raise RuntimeError(f"Unknown tool: {name!r}")

    async def aclose(self) -> None:
        for client in (self.search, self.notion, self.calendar):
            if client is not None:
                await client.aclose()


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return default
