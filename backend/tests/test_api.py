import base64
import asyncio
import json
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.calendar import compact_event, parse_datetime
from app.config import Settings
from app.exa import compact_exa_results
from app.main import app, settings
from app.notion import blocks_to_text, page_title
from app.openai_realtime import (
    CALENDAR_CREATE_TOOL,
    CALENDAR_UPCOMING_TOOL,
    NOTION_ADD_TOOL,
    NOTION_READ_TOOL,
    NOTION_SEARCH_TOOL,
    WEB_SEARCH_TOOL,
    OpenAIRealtimeConnector,
)
from app.security import SecretBox
from app.tools import ToolRegistry


@pytest.fixture(autouse=True)
def isolated_platform_storage(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        settings,
        "database_url",
        f"sqlite+aiosqlite:///{tmp_path / 'kuma-test.db'}",
    )
    monkeypatch.setattr(
        settings,
        "kuma_encryption_key_file",
        str(tmp_path / "encryption.key"),
    )
    monkeypatch.setattr(settings, "kuma_environment", "local")
    monkeypatch.setattr(settings, "kuma_require_device_auth", False)


class FakeOpenRouter:
    async def transcribe(self, audio: bytes, audio_format: str, language: str | None = None) -> str:
        assert audio == b"fake-audio"
        assert audio_format == "m4a"
        return "What is the weather like?"

    async def chat(self, messages: list[dict[str, str]]) -> str:
        assert messages[-1]["role"] == "user"
        return "It looks sunny today."

    async def synthesize(self, text: str) -> bytes:
        assert text
        return b"fake-mp3"

    async def aclose(self) -> None:
        return None


class FakeRealtimeConnection:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.incoming: asyncio.Queue[str] = asyncio.Queue()

    async def send(self, message: str) -> None:
        self.sent.append(json.loads(message))

    async def recv(self) -> str:
        return await self.incoming.get()

    def queue(self, event: dict) -> None:
        self.incoming.put_nowait(json.dumps(event))


class FakeRealtimeConnector:
    def __init__(self) -> None:
        self.connection = FakeRealtimeConnection()

    def session_update(self) -> dict:
        return {"type": "session.update", "session": {"type": "realtime"}}

    def connect(self):
        @asynccontextmanager
        async def connection_context():
            yield self.connection

        return connection_context()


class FakeExa:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def search(self, query: str) -> str:
        self.queries.append(query)
        return json.dumps(
            {
                "results": [
                    {
                        "title": "Weather",
                        "url": "https://example.com/weather",
                        "snippet": "It is sunny.",
                    }
                ]
            }
        )

    async def aclose(self) -> None:
        return None


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_token_protects_http_and_websocket(monkeypatch) -> None:
    monkeypatch.setattr(settings, "kuma_api_token", "test-token")

    with TestClient(app) as client:
        unauthorized = client.post("/api/v1/conversations")
        authorized = client.post(
            "/api/v1/conversations",
            headers={"Authorization": "Bearer test-token"},
        )
        with pytest.raises(WebSocketDisconnect) as rejected:
            with client.websocket_connect("/api/v1/realtime"):
                pass

    assert unauthorized.status_code == 401
    assert authorized.status_code == 201
    assert rejected.value.code == 1008


def test_local_account_onboarding_pairing_and_encrypted_key(
    monkeypatch, tmp_path: Path
) -> None:
    api_key = "sk-test-this-is-not-a-real-openai-key"

    with TestClient(app) as client:
        signup = client.post(
            "/studio/v1/auth/signup",
            json={"email": "kuma@example.com", "password": "warm-paws-123"},
        )
        assert signup.status_code == 201
        assert signup.json()["next_step"] == "profile"
        assert signup.json()["profile"] is None
        assert "httponly" in signup.headers["set-cookie"].lower()

        duplicate = client.post(
            "/studio/v1/auth/signup",
            json={"email": "KUMA@example.com", "password": "warm-paws-123"},
        )
        assert duplicate.status_code == 409

        provider_before_profile = client.put(
            "/studio/v1/providers/openai",
            json={"api_key": api_key},
        )
        assert provider_before_profile.status_code == 409

        incomplete_profile = client.put(
            "/studio/v1/profile",
            json={
                "full_name": "Marco",
                "role": "Founder",
                "primary_goal": "Handle everyday tasks without reaching for my phone",
                "response_style": "brief",
            },
        )
        assert incomplete_profile.status_code == 422

        authorization = client.post(
            "/device/v1/authorizations",
            json={"device_name": "Marco's Apple Watch"},
        )
        assert authorization.status_code == 201
        pairing = authorization.json()
        assert len(pairing["user_code"].replace(" ", "")) == 6

        pending = client.post(
            "/device/v1/token",
            json={"device_code": pairing["device_code"]},
        )
        assert pending.status_code == 202

        pairing_before_profile = client.post(
            "/studio/v1/pairings/approve",
            json={"user_code": pairing["user_code"]},
        )
        assert pairing_before_profile.status_code == 409

        profile = client.put(
            "/studio/v1/profile",
            json={
                "full_name": "Marco",
                "role": "Founder",
                "use_cases": ["personal-assistant", "workflows-approvals"],
                "technical_comfort": "tinkerer",
                "discovery_source": "tiktok",
                "response_style": "brief",
            },
        )
        assert profile.status_code == 200
        assert profile.json()["next_step"] == "watch"
        profile_data = profile.json()["profile"]
        assert profile_data["use_cases"] == [
            "personal-assistant",
            "workflows-approvals",
        ]
        assert profile_data["technical_comfort"] == "tinkerer"
        assert profile_data["discovery_source"] == "tiktok"
        assert profile_data["primary_goal"] is None

        too_many_use_cases = client.put(
            "/studio/v1/profile",
            json={
                "full_name": "Marco",
                "role": "Founder",
                "primary_goal": "Keep the Watch useful",
                "use_cases": [
                    "personal-assistant",
                    "workflows-approvals",
                    "reminders-planning",
                    "smart-home",
                ],
                "technical_comfort": "everyday",
                "discovery_source": "instagram",
                "response_style": "brief",
            },
        )
        assert too_many_use_cases.status_code == 422

        provider_before_watch = client.put(
            "/studio/v1/providers/openai",
            json={"api_key": api_key},
        )
        assert provider_before_watch.status_code == 409

        approval = client.post(
            "/studio/v1/pairings/approve",
            json={"user_code": pairing["user_code"]},
        )
        assert approval.status_code == 200

        token_exchange = client.post(
            "/device/v1/token",
            json={"device_code": pairing["device_code"]},
        )
        assert token_exchange.status_code == 200
        device_token = token_exchange.json()["access_token"]
        assert device_token.startswith("kuma_device_")

        monkeypatch.setattr(settings, "kuma_require_device_auth", True)
        assert client.post("/api/v1/conversations").status_code == 401
        device_request = client.post(
            "/api/v1/conversations",
            headers={"Authorization": f"Bearer {device_token}"},
        )
        assert device_request.status_code == 201

        provider = client.put(
            "/studio/v1/providers/openai",
            json={"api_key": api_key},
        )
        assert provider.status_code == 200
        assert provider.json()["next_step"] == "complete"
        assert provider.json()["openai"] == {
            "configured": True,
            "last_four": "-key",
        }
        assert api_key not in provider.text

        signout = client.post("/studio/v1/auth/signout")
        assert signout.status_code == 204
        assert client.get("/studio/v1/bootstrap").status_code == 401

    database = sqlite3.connect(tmp_path / "kuma-test.db")
    encrypted_key = database.execute(
        "SELECT encrypted_value FROM provider_secrets WHERE provider = 'openai'"
    ).fetchone()[0]
    password_hash = database.execute("SELECT password_hash FROM users").fetchone()[0]
    stored_device_token = database.execute(
        "SELECT access_token_hash FROM devices"
    ).fetchone()[0]
    database.close()

    assert api_key not in encrypted_key
    assert "warm-paws-123" not in password_hash
    assert device_token not in stored_device_token
    assert SecretBox.from_settings(settings).decrypt(encrypted_key) == api_key


def test_full_voice_turn() -> None:
    with TestClient(app) as client:
        app.state.openrouter = FakeOpenRouter()
        created = client.post("/api/v1/conversations")
        conversation_id = created.json()["conversation_id"]

        response = client.post(
            f"/api/v1/conversations/{conversation_id}/turns",
            files={"audio": ("voice.m4a", b"fake-audio", "audio/mp4")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["user_text"] == "What is the weather like?"
    assert body["assistant_text"] == "It looks sunny today."
    assert base64.b64decode(body["audio_base64"]) == b"fake-mp3"


def test_unknown_conversation_returns_404() -> None:
    with TestClient(app) as client:
        app.state.openrouter = FakeOpenRouter()
        response = client.post(
            "/api/v1/conversations/missing/turns",
            files={"audio": ("voice.m4a", b"fake-audio", "audio/mp4")},
        )

    assert response.status_code == 404


def test_realtime_voice_bridge() -> None:
    realtime = FakeRealtimeConnector()
    realtime.connection.queue({"type": "session.updated"})
    realtime.connection.queue({"type": "response.created"})
    realtime.connection.queue(
        {
            "type": "response.output_audio.delta",
            "delta": base64.b64encode(b"reply-pcm").decode("ascii"),
        }
    )
    realtime.connection.queue(
        {"type": "response.output_audio_transcript.delta", "delta": "Hello!"}
    )
    realtime.connection.queue(
        {"type": "response.done", "response": {"status": "completed"}}
    )

    with TestClient(app) as client:
        app.state.openai_realtime = realtime
        with client.websocket_connect("/api/v1/realtime") as websocket:
            ready = websocket.receive_json()
            assert ready == {
                "type": "ready",
                "audio_format": "pcm16",
                "sample_rate": 24_000,
                "channels": 1,
            }

            websocket.send_json({"type": "start"})
            websocket.send_json(
                {
                    "type": "audio",
                    "audio": base64.b64encode(b"\0" * 4_800).decode("ascii"),
                }
            )
            websocket.send_json({"type": "commit"})

            events = [websocket.receive_json() for _ in range(4)]
            websocket.send_json({"type": "close"})
            websocket.receive()

    assert [event["type"] for event in events] == [
        "response_started",
        "audio_delta",
        "transcript_delta",
        "response_done",
    ]
    assert realtime.connection.sent == [
        {"type": "session.update", "session": {"type": "realtime"}},
        {"type": "input_audio_buffer.clear"},
        {
            "type": "input_audio_buffer.append",
            "audio": base64.b64encode(b"\0" * 4_800).decode("ascii"),
        },
        {"type": "input_audio_buffer.commit"},
        {"type": "response.create"},
    ]


def test_realtime_session_uses_watch_pcm_format() -> None:
    connector = OpenAIRealtimeConnector(
        Settings(_env_file=None, openai_api_key="test-key")
    )
    audio = connector.session_update()["session"]["audio"]

    assert audio["input"]["format"] == {"type": "audio/pcm", "rate": 24_000}
    assert audio["output"]["format"] == {"type": "audio/pcm", "rate": 24_000}
    assert "tools" not in connector.session_update()["session"]


def test_realtime_cancel_interrupts_response() -> None:
    realtime = FakeRealtimeConnector()
    realtime.connection.queue({"type": "session.updated"})
    realtime.connection.queue({"type": "response.created"})
    realtime.connection.queue(
        {
            "type": "response.output_audio.delta",
            "delta": base64.b64encode(b"reply-pcm").decode("ascii"),
        }
    )
    realtime.connection.queue(
        {"type": "response.done", "response": {"status": "cancelled"}}
    )
    realtime.connection.queue(
        {
            "type": "error",
            "error": {
                "code": "response_cancel_not_active",
                "message": "Cancellation failed: no active response.",
            },
        }
    )

    with TestClient(app) as client:
        app.state.openai_realtime = realtime
        with client.websocket_connect("/api/v1/realtime") as websocket:
            assert websocket.receive_json()["type"] == "ready"
            websocket.send_json({"type": "start"})
            websocket.send_json(
                {
                    "type": "audio",
                    "audio": base64.b64encode(b"\0" * 4_800).decode("ascii"),
                }
            )
            websocket.send_json({"type": "commit"})
            assert websocket.receive_json()["type"] == "response_started"
            assert websocket.receive_json()["type"] == "audio_delta"
            websocket.send_json({"type": "cancel"})
            assert websocket.receive_json() == {"type": "response_cancelled"}
            websocket.send_json({"type": "close"})
            websocket.receive()

    assert {"type": "response.cancel"} in realtime.connection.sent
    assert realtime.connection.sent.count({"type": "input_audio_buffer.clear"}) >= 2


def test_realtime_session_includes_web_search_when_exa_configured() -> None:
    connector = OpenAIRealtimeConnector(
        Settings(_env_file=None, openai_api_key="test-key", exa_api_key="exa-key")
    )
    session = connector.session_update()["session"]

    assert session["tools"] == [WEB_SEARCH_TOOL]
    assert session["tool_choice"] == "auto"
    assert "web_search" in session["instructions"]


def test_realtime_session_includes_notion_and_calendar_tools() -> None:
    connector = OpenAIRealtimeConnector(
        Settings(
            _env_file=None,
            openai_api_key="test-key",
            notion_api_key="ntn-key",
            google_calendar_client_id="id",
            google_calendar_client_secret="secret",
            google_calendar_refresh_token="refresh",
        )
    )
    session = connector.session_update()["session"]
    names = [tool["name"] for tool in session["tools"]]
    assert names == [
        "notion_search",
        "notion_read_page",
        "notion_add_note",
        "calendar_upcoming",
        "calendar_create_event",
    ]
    assert NOTION_SEARCH_TOOL in session["tools"]
    assert NOTION_READ_TOOL in session["tools"]
    assert NOTION_ADD_TOOL in session["tools"]
    assert CALENDAR_UPCOMING_TOOL in session["tools"]
    assert CALENDAR_CREATE_TOOL in session["tools"]
    assert "Notion" in session["instructions"]
    assert "calendar" in session["instructions"]


def test_exact_api_key_alias_enables_web_search() -> None:
    settings = Settings(_env_file=None, exact_api_key="exa-key")
    assert settings.web_search_api_key == "exa-key"


def test_compact_exa_results_keeps_title_url_and_highlights() -> None:
    compacted = compact_exa_results(
        {
            "results": [
                {
                    "title": "Fed rate",
                    "url": "https://example.com/fed",
                    "publishedDate": "2026-08-18",
                    "highlights": ["The federal funds rate is 4.25%."],
                    "text": "long unused body",
                }
            ]
        }
    )

    assert compacted == {
        "results": [
            {
                "title": "Fed rate",
                "url": "https://example.com/fed",
                "published": "2026-08-18",
                "snippet": "The federal funds rate is 4.25%.",
            }
        ]
    }


def test_realtime_voice_bridge_runs_web_search_tool() -> None:
    realtime = FakeRealtimeConnector()
    search = FakeExa()
    realtime.connection.queue({"type": "session.updated"})
    realtime.connection.queue({"type": "response.created"})
    realtime.connection.queue(
        {
            "type": "response.done",
            "response": {
                "status": "completed",
                "output": [
                    {
                        "type": "function_call",
                        "name": "web_search",
                        "call_id": "call_weather",
                        "arguments": '{"query":"weather in milan"}',
                    }
                ],
            },
        }
    )
    realtime.connection.queue({"type": "response.created"})
    realtime.connection.queue(
        {
            "type": "response.output_audio.delta",
            "delta": base64.b64encode(b"reply-pcm").decode("ascii"),
        }
    )
    realtime.connection.queue(
        {"type": "response.output_audio_transcript.delta", "delta": "It is sunny."}
    )
    realtime.connection.queue(
        {"type": "response.done", "response": {"status": "completed"}}
    )

    with TestClient(app) as client:
        app.state.openai_realtime = realtime
        app.state.exa = search
        app.state.tools = ToolRegistry(search=search)
        with client.websocket_connect("/api/v1/realtime") as websocket:
            assert websocket.receive_json()["type"] == "ready"
            websocket.send_json({"type": "start"})
            websocket.send_json(
                {
                    "type": "audio",
                    "audio": base64.b64encode(b"\0" * 4_800).decode("ascii"),
                }
            )
            websocket.send_json({"type": "commit"})

            events = [websocket.receive_json() for _ in range(5)]
            websocket.send_json({"type": "close"})
            websocket.receive()

    assert [event["type"] for event in events] == [
        "status",
        "response_started",
        "audio_delta",
        "transcript_delta",
        "response_done",
    ]
    assert events[0] == {"type": "status", "message": "searching"}
    assert search.queries == ["weather in milan"]
    assert {
        "type": "conversation.item.create",
        "item": {
            "type": "function_call_output",
            "call_id": "call_weather",
            "output": json.dumps(
                {
                    "results": [
                        {
                            "title": "Weather",
                            "url": "https://example.com/weather",
                            "snippet": "It is sunny.",
                        }
                    ]
                }
            ),
        },
    } in realtime.connection.sent
    assert realtime.connection.sent.count({"type": "response.create"}) == 2


def test_page_title_and_blocks_to_text() -> None:
    page = {
        "properties": {
            "Name": {
                "type": "title",
                "title": [{"plain_text": "Launch notes"}],
            }
        }
    }
    blocks = [
        {
            "type": "paragraph",
            "paragraph": {"rich_text": [{"plain_text": "Ship on Friday."}]},
        }
    ]
    assert page_title(page) == "Launch notes"
    assert blocks_to_text(blocks) == "Ship on Friday."


def test_compact_calendar_event() -> None:
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("Europe/Rome")
    event = compact_event(
        {
            "id": "evt_1",
            "summary": "Demo",
            "location": "Office",
            "start": {"dateTime": "2026-08-25T16:00:00+02:00"},
            "end": {"dateTime": "2026-08-25T16:30:00+02:00"},
        },
        tz,
    )
    assert event["title"] == "Demo"
    assert event["start"] == "2026-08-25 16:00"
    parsed = parse_datetime("2026-08-25T16:00", tz)
    assert parsed.hour == 16
    assert str(parsed.tzinfo) == "Europe/Rome"
