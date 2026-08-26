import asyncio
import base64
import binascii
import json
from typing import Any, Protocol
from urllib.parse import urlencode

from fastapi import WebSocket
from websockets.asyncio.client import connect

from .config import Settings
from .tools import ToolRegistry


class RealtimeProtocolError(Exception):
    pass


class RealtimeUpstream(Protocol):
    async def send(self, message: str) -> None: ...

    async def recv(self) -> str | bytes: ...


WEB_SEARCH_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "web_search",
    "description": (
        "Search the live web for current facts, news, sports, prices, "
        "or anything you are not certain about."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural-language search query.",
            }
        },
        "required": ["query"],
    },
}

NOTION_SEARCH_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "notion_search",
    "description": "Search the user's Notion workspace for pages matching a query.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Words from the page title or contents.",
            }
        },
        "required": ["query"],
    },
}

NOTION_READ_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "notion_read_page",
    "description": "Read a Notion page. Prefer page_id from notion_search when you have it.",
    "parameters": {
        "type": "object",
        "properties": {
            "page_id": {"type": "string", "description": "Notion page id."},
            "query": {
                "type": "string",
                "description": "Page title search if page_id is unknown.",
            },
        },
    },
}

NOTION_ADD_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "notion_add_note",
    "description": (
        "Append a short bullet to a Notion page. Uses the default notes page "
        "unless page_id or query is provided."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "The note to save."},
            "page_id": {"type": "string", "description": "Notion page id."},
            "query": {"type": "string", "description": "Page title search if needed."},
        },
        "required": ["text"],
    },
}

CALENDAR_UPCOMING_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "calendar_upcoming",
    "description": "List upcoming events on the user's primary Google Calendar.",
    "parameters": {
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "description": "How many days ahead to look. Default 1.",
            },
            "max_events": {
                "type": "integer",
                "description": "Maximum events to return. Default 5.",
            },
        },
    },
}

CALENDAR_CREATE_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "calendar_create_event",
    "description": "Create an event on the user's primary Google Calendar.",
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Event title."},
            "start": {
                "type": "string",
                "description": "Start time as ISO-8601, for example 2026-08-25T16:00.",
            },
            "end": {
                "type": "string",
                "description": "Optional end time as ISO-8601.",
            },
            "duration_minutes": {
                "type": "integer",
                "description": "Used when end is omitted. Default 30.",
            },
        },
        "required": ["title", "start"],
    },
}

WEB_SEARCH_INSTRUCTIONS = (
    "When the user asks about current events, live facts, sports, news, prices, "
    "or anything you are not sure about, call web_search first. After the results "
    "arrive, speak a brief answer. Mention a source name if it helps. "
    "Do not read URLs aloud."
)
NOTION_INSTRUCTIONS = (
    "Use Notion tools for the user's notes, docs, and saved decisions. "
    "Search first, then read a page if you need the contents. "
    "When they ask to save an idea, call notion_add_note. "
    "Speak titles and a short summary. Do not read page IDs or URLs aloud."
)
CALENDAR_INSTRUCTIONS = (
    "Use calendar_upcoming for schedule questions and calendar_create_event "
    "when they ask to add a meeting or reminder on the calendar. "
    "Speak times in a natural way. Do not read event IDs aloud."
)


class OpenAIRealtimeConnector:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def connect(self):
        if not self.settings.openai_api_key:
            raise RealtimeProtocolError(
                "OPENAI_API_KEY is not configured on the Kuma Voice server."
            )

        query = urlencode({"model": self.settings.openai_realtime_model})
        url = f"{self.settings.openai_realtime_url}?{query}"
        return connect(
            url,
            additional_headers={
                "Authorization": f"Bearer {self.settings.openai_api_key}",
            },
            max_size=None,
            open_timeout=15,
            ping_interval=20,
            ping_timeout=20,
        )

    def session_update(self) -> dict[str, Any]:
        instructions = self.settings.kuma_system_prompt.rstrip()
        tools: list[dict[str, Any]] = []
        extras: list[str] = []
        if self.settings.web_search_api_key:
            tools.append(WEB_SEARCH_TOOL)
            extras.append(WEB_SEARCH_INSTRUCTIONS)
        if self.settings.notion_api_key.strip():
            tools.extend([NOTION_SEARCH_TOOL, NOTION_READ_TOOL, NOTION_ADD_TOOL])
            extras.append(NOTION_INSTRUCTIONS)
        if self.settings.calendar_configured:
            tools.extend([CALENDAR_UPCOMING_TOOL, CALENDAR_CREATE_TOOL])
            extras.append(CALENDAR_INSTRUCTIONS)
        session: dict[str, Any] = {
            "type": "realtime",
            "instructions": " ".join([instructions, *extras]),
            "output_modalities": ["audio"],
            "audio": {
                "input": {
                    "format": {"type": "audio/pcm", "rate": 24_000},
                    "turn_detection": None,
                },
                "output": {
                    "format": {"type": "audio/pcm", "rate": 24_000},
                    "voice": self.settings.openai_realtime_voice,
                },
            },
        }
        if tools:
            session["tools"] = tools
            session["tool_choice"] = "auto"
        return {"type": "session.update", "session": session}


async def bridge_realtime_session(
    watch: WebSocket,
    connector: OpenAIRealtimeConnector,
    max_audio_bytes: int,
    tools: ToolRegistry | None = None,
    search: Any | None = None,
) -> None:
    registry = tools or ToolRegistry(search=search)
    async with connector.connect() as upstream:
        await send_upstream(upstream, connector.session_update())
        await watch.send_json(
            {
                "type": "ready",
                "audio_format": "pcm16",
                "sample_rate": 24_000,
                "channels": 1,
            }
        )

        watch_task = asyncio.create_task(
            forward_watch_events(watch, upstream, max_audio_bytes)
        )
        upstream_task = asyncio.create_task(
            forward_openai_events(upstream, watch, registry)
        )
        tasks = {watch_task, upstream_task}
        try:
            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )
        finally:
            pending = {task for task in tasks if not task.done()}
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

        for task in done:
            exception = task.exception()
            if exception is not None:
                raise exception


async def forward_watch_events(
    watch: WebSocket,
    upstream: RealtimeUpstream,
    max_audio_bytes: int,
) -> None:
    audio_bytes = 0

    while True:
        event = await watch.receive_json()
        event_type = event.get("type")

        if event_type == "start":
            audio_bytes = 0
            await send_upstream(upstream, {"type": "input_audio_buffer.clear"})
        elif event_type == "audio":
            audio = event.get("audio")
            if not isinstance(audio, str) or not audio:
                raise RealtimeProtocolError("An audio event must contain base64 audio.")

            try:
                chunk_size = len(base64.b64decode(audio, validate=True))
            except (binascii.Error, ValueError) as exc:
                raise RealtimeProtocolError("An audio event contained invalid base64.") from exc

            audio_bytes += chunk_size
            if audio_bytes > max_audio_bytes:
                raise RealtimeProtocolError("The realtime audio turn is too large.")

            await send_upstream(
                upstream,
                {"type": "input_audio_buffer.append", "audio": audio},
            )
        elif event_type == "commit":
            if audio_bytes < 4_800:
                raise RealtimeProtocolError("Please speak for at least a tenth of a second.")
            await send_upstream(upstream, {"type": "input_audio_buffer.commit"})
            await send_upstream(upstream, {"type": "response.create"})
            audio_bytes = 0
        elif event_type == "cancel":
            audio_bytes = 0
            await send_upstream(upstream, {"type": "response.cancel"})
            await send_upstream(upstream, {"type": "input_audio_buffer.clear"})
        elif event_type == "ping":
            await watch.send_json({"type": "pong"})
        elif event_type == "close":
            return
        else:
            raise RealtimeProtocolError(f"Unsupported realtime event: {event_type!r}")


async def forward_openai_events(
    upstream: RealtimeUpstream,
    watch: WebSocket,
    tools: ToolRegistry,
) -> None:
    spoken_started = False

    while True:
        raw_event = await upstream.recv()
        if isinstance(raw_event, bytes):
            raw_event = raw_event.decode("utf-8")
        event = json.loads(raw_event)
        event_type = event.get("type")

        if event_type == "response.created":
            spoken_started = False
        elif event_type in {"response.output_audio.delta", "response.audio.delta"}:
            if not spoken_started:
                await watch.send_json({"type": "response_started"})
                spoken_started = True
            await watch.send_json(
                {"type": "audio_delta", "audio": event.get("delta", "")}
            )
        elif event_type in {
            "response.output_audio_transcript.delta",
            "response.audio_transcript.delta",
        }:
            if not spoken_started:
                await watch.send_json({"type": "response_started"})
                spoken_started = True
            await watch.send_json(
                {"type": "transcript_delta", "text": event.get("delta", "")}
            )
        elif event_type == "response.done":
            response = event.get("response", {})
            status = response.get("status") if isinstance(response, dict) else None
            calls = function_calls_from(response)
            if calls and status != "cancelled":
                await fulfill_function_calls(upstream, watch, calls, tools)
                continue
            if status == "cancelled":
                await watch.send_json({"type": "response_cancelled"})
            elif status in {"failed", "incomplete"}:
                details = response.get("status_details", {})
                message = _message_from(details) or f"OpenAI response {status}."
                await watch.send_json({"type": "error", "message": message})
            else:
                await watch.send_json({"type": "response_done"})
        elif event_type == "error":
            if _is_ignorable_cancel_error(event):
                continue
            await watch.send_json(
                {
                    "type": "error",
                    "message": _message_from(event.get("error"))
                    or "The OpenAI realtime session failed.",
                }
            )


async def fulfill_function_calls(
    upstream: RealtimeUpstream,
    watch: WebSocket,
    calls: list[dict[str, Any]],
    tools: ToolRegistry,
) -> None:
    await watch.send_json({"type": "status", "message": "searching"})
    for call in calls:
        call_id = call.get("call_id")
        if not isinstance(call_id, str) or not call_id:
            continue
        output = await run_tool(call, tools)
        await send_upstream(
            upstream,
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": output,
                },
            },
        )
    await send_upstream(upstream, {"type": "response.create"})


async def run_tool(call: dict[str, Any], tools: ToolRegistry) -> str:
    name = call.get("name") if isinstance(call.get("name"), str) else ""
    arguments = parse_tool_arguments(call.get("arguments"))
    try:
        return await tools.run(name, arguments)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def parse_tool_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def function_calls_from(response: Any) -> list[dict[str, Any]]:
    if not isinstance(response, dict):
        return []
    output = response.get("output")
    if not isinstance(output, list):
        return []
    return [
        item
        for item in output
        if isinstance(item, dict) and item.get("type") == "function_call"
    ]


async def send_upstream(
    upstream: RealtimeUpstream,
    event: dict[str, Any],
) -> None:
    await upstream.send(json.dumps(event, separators=(",", ":")))


def _message_from(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return None
    message = value.get("message")
    if isinstance(message, str):
        return message
    error = value.get("error")
    return _message_from(error)


def _is_ignorable_cancel_error(event: dict[str, Any]) -> bool:
    error = event.get("error")
    if not isinstance(error, dict):
        return False
    code = str(error.get("code") or "")
    message = (_message_from(error) or "").lower()
    return code in {"response_cancel_not_active"} or "cancellation failed" in message
