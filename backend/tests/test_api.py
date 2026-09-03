import base64
import asyncio
import json
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.calendar import compact_event, parse_datetime
from app.config import Settings
from app.exa import compact_exa_results
from app.main import app, settings
from app.mcp_gateway import (
    MAX_TOOL_RESULT_BYTES,
    MCPGateway,
    MCPGatewayError,
    validate_mcp_destination,
    validate_mcp_url,
)
from app.models import MCPConnection
from app import mcp_routes
from mcp.shared.auth import OAuthMetadata, ProtectedResourceMetadata
from app.notion import blocks_to_text, page_title
from app.openai_realtime import (
    CALENDAR_CREATE_TOOL,
    CALENDAR_UPCOMING_TOOL,
    NOTION_ADD_TOOL,
    NOTION_READ_TOOL,
    NOTION_SEARCH_TOOL,
    WEB_SEARCH_TOOL,
    OpenAIRealtimeConnector,
    OpenAIRealtimeSessionIssuer,
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


class FakeRealtimeSessionIssuer:
    def __init__(self) -> None:
        self.connector: OpenAIRealtimeConnector | None = None
        self.safety_identifier: str | None = None

    async def issue(
        self,
        connector: OpenAIRealtimeConnector,
        *,
        safety_identifier: str | None = None,
    ) -> dict:
        self.connector = connector
        self.safety_identifier = safety_identifier
        return {
            "value": "ek_test_short_lived",
            "expires_at": 1_800_000_000,
            "session_id": "sess_test",
        }

    async def aclose(self) -> None:
        return None


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


class FakeMCPClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def list_tools(self, cursor: str | None = None):
        assert cursor is None
        return SimpleNamespace(
            tools=[
                SimpleNamespace(
                    name="search_workspace",
                    title="Search workspace",
                    description="Search the connected workspace.",
                    input_schema={
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                )
            ],
            ttl_ms=60_000,
            next_cursor=None,
        )

    async def call_tool(self, name: str, arguments: dict):
        self.calls.append((name, arguments))
        return SimpleNamespace(
            structured_content={"matches": ["Launch plan"]},
            content=[],
            is_error=False,
        )


class FakeMCPGateway(MCPGateway):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.client = FakeMCPClient()

    @asynccontextmanager
    async def _client(self, connection):
        yield self.client


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_token_protects_http_and_websocket(monkeypatch) -> None:
    monkeypatch.setattr(settings, "kuma_api_token", "test-token")

    with TestClient(app) as client:
        unauthorized = client.post("/api/v1/conversations")
        unauthorized_direct = client.post("/api/v1/realtime/session")
        unauthorized_tool = client.post(
            "/api/v1/realtime/tools/web_search",
            json={"arguments": {"query": "private query"}},
        )
        authorized = client.post(
            "/api/v1/conversations",
            headers={"Authorization": "Bearer test-token"},
        )
        with pytest.raises(WebSocketDisconnect) as rejected:
            with client.websocket_connect("/api/v1/realtime"):
                pass

    assert unauthorized.status_code == 401
    assert unauthorized_direct.status_code == 401
    assert unauthorized_tool.status_code == 401
    assert authorized.status_code == 201
    assert rejected.value.code == 1008


def test_local_account_onboarding_pairing_and_encrypted_key(
    monkeypatch, tmp_path: Path
) -> None:
    api_key = "sk-test-this-is-not-a-real-openai-key"
    issuer = FakeRealtimeSessionIssuer()

    with TestClient(app) as client:
        app.state.openai_realtime_sessions = issuer
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

        mcp = FakeMCPGateway(settings, app.state.database, app.state.secret_box)
        app.state.mcp = mcp
        connection = client.post(
            "/studio/v1/mcp/connections",
            json={
                "name": "Workspace",
                "server_url": "https://mcp.example.com/mcp",
                "auth_type": "none",
            },
        )
        assert connection.status_code == 201
        connection_id = connection.json()["id"]
        discovered = client.post(
            f"/studio/v1/mcp/connections/{connection_id}/discover"
        )
        assert discovered.status_code == 200
        discovered_tool = discovered.json()["tools"][0]
        assert discovered_tool["enabled"] is False
        disabled_call = client.post(
            f"/api/v1/realtime/tools/{discovered_tool['name']}",
            headers={"Authorization": f"Bearer {device_token}"},
            json={"arguments": {"query": "launch"}},
        )
        assert disabled_call.status_code == 400
        enabled = client.patch(
            f"/studio/v1/mcp/connections/{connection_id}/tools/"
            f"{discovered_tool['id']}",
            json={"enabled": True, "risk": "read"},
        )
        assert enabled.status_code == 200

        direct_session = client.post(
            "/api/v1/realtime/session",
            headers={"Authorization": f"Bearer {device_token}"},
        )
        assert direct_session.status_code == 200
        assert api_key not in direct_session.text
        assert issuer.connector is not None
        assert issuer.connector.settings.openai_api_key == api_key
        assert issuer.safety_identifier is not None
        assert "Marco" in issuer.connector.settings.kuma_system_prompt
        assert issuer.connector.extra_tools == [
            {
                "type": "function",
                "name": discovered_tool["name"],
                "description": "Search the connected workspace.",
                "parameters": discovered_tool["input_schema"],
            }
        ]

        tool_result = client.post(
            f"/api/v1/realtime/tools/{discovered_tool['name']}",
            headers={"Authorization": f"Bearer {device_token}"},
            json={"arguments": {"query": "launch"}},
        )
        assert tool_result.status_code == 200
        assert json.loads(tool_result.json()["output"]) == {
            "matches": ["Launch plan"]
        }
        assert mcp.client.calls == [("search_workspace", {"query": "launch"})]

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


def test_studio_settings_manage_password_devices_and_account(
    monkeypatch, tmp_path: Path
) -> None:
    original_password = "warm-paws-123"
    new_password = "new-warm-paws-456"

    with TestClient(app) as client:
        signup = client.post(
            "/studio/v1/auth/signup",
            json={"email": "settings@example.com", "password": original_password},
        )
        assert signup.status_code == 201
        first_session = client.cookies.get(settings.kuma_session_cookie_name)
        assert first_session

        second_signin = client.post(
            "/studio/v1/auth/signin",
            json={"email": "settings@example.com", "password": original_password},
        )
        assert second_signin.status_code == 200

        wrong_password = client.put(
            "/studio/v1/account/password",
            json={
                "current_password": "wrong-password",
                "new_password": new_password,
            },
        )
        assert wrong_password.status_code == 401

        reused_password = client.put(
            "/studio/v1/account/password",
            json={
                "current_password": original_password,
                "new_password": original_password,
            },
        )
        assert reused_password.status_code == 422

        changed = client.put(
            "/studio/v1/account/password",
            json={
                "current_password": original_password,
                "new_password": new_password,
            },
        )
        assert changed.status_code == 204
        assert client.get("/studio/v1/bootstrap").status_code == 200
        assert (
            client.get(
                "/studio/v1/bootstrap",
                headers={
                    "cookie": f"{settings.kuma_session_cookie_name}={first_session}"
                },
            ).status_code
            == 401
        )

        assert client.post("/studio/v1/auth/signout").status_code == 204
        assert (
            client.post(
                "/studio/v1/auth/signin",
                json={"email": "settings@example.com", "password": original_password},
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/studio/v1/auth/signin",
                json={"email": "settings@example.com", "password": new_password},
            ).status_code
            == 200
        )

        profile = client.put(
            "/studio/v1/profile",
            json={
                "full_name": "Settings Tester",
                "role": "Personal use",
                "use_cases": ["personal-assistant"],
                "technical_comfort": "everyday",
                "discovery_source": "search",
                "response_style": "brief",
            },
        )
        assert profile.status_code == 200

        authorization = client.post(
            "/device/v1/authorizations",
            json={"device_name": "Test Apple Watch"},
        ).json()
        approval = client.post(
            "/studio/v1/pairings/approve",
            json={"user_code": authorization["user_code"]},
        )
        device_id = approval.json()["device"]["id"]
        device_token = client.post(
            "/device/v1/token",
            json={"device_code": authorization["device_code"]},
        ).json()["access_token"]

        monkeypatch.setattr(settings, "kuma_require_device_auth", True)
        assert (
            client.post(
                "/api/v1/conversations",
                headers={"Authorization": f"Bearer {device_token}"},
            ).status_code
            == 201
        )
        assert client.delete("/studio/v1/devices/not-this-watch").status_code == 404

        revoked = client.delete(f"/studio/v1/devices/{device_id}")
        assert revoked.status_code == 200
        assert revoked.json()["devices"] == []
        assert revoked.json()["next_step"] == "watch"
        assert (
            client.post(
                "/api/v1/conversations",
                headers={"Authorization": f"Bearer {device_token}"},
            ).status_code
            == 401
        )

        mcp_connection = client.post(
            "/studio/v1/mcp/connections",
            json={
                "name": "Workspace",
                "server_url": "https://mcp.example.com/mcp",
                "auth_type": "none",
            },
        )
        assert mcp_connection.status_code == 201

        wrong_delete = client.request(
            "DELETE",
            "/studio/v1/account",
            json={"current_password": original_password},
        )
        assert wrong_delete.status_code == 401

        deleted = client.request(
            "DELETE",
            "/studio/v1/account",
            json={"current_password": new_password},
        )
        assert deleted.status_code == 204
        assert client.get("/studio/v1/bootstrap").status_code == 401
        assert (
            client.post(
                "/studio/v1/auth/signin",
                json={"email": "settings@example.com", "password": new_password},
            ).status_code
            == 401
        )

    database = sqlite3.connect(tmp_path / "kuma-test.db")
    remaining = {
        table: database.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in (
            "users",
            "user_profiles",
            "studio_sessions",
            "devices",
            "device_authorizations",
            "mcp_connections",
            "mcp_tools",
            "mcp_oauth_flows",
        )
    }
    database.close()
    assert remaining == {
        "users": 0,
        "user_profiles": 0,
        "studio_sessions": 0,
        "devices": 0,
        "device_authorizations": 0,
        "mcp_connections": 0,
        "mcp_tools": 0,
        "mcp_oauth_flows": 0,
    }


def test_mcp_oauth_flow_uses_pkce_and_encrypts_tokens(monkeypatch, tmp_path: Path) -> None:
    async def discover_oauth(server_url: str, request):
        assert server_url == "https://mcp.example.com/mcp"
        return (
            ProtectedResourceMetadata(
                resource="https://mcp.example.com/mcp",
                authorization_servers=["https://auth.example.com"],
                scopes_supported=["workspace:read"],
            ),
            OAuthMetadata(
                issuer="https://auth.example.com",
                authorization_endpoint="https://auth.example.com/authorize",
                token_endpoint="https://auth.example.com/token",
                scopes_supported=["workspace:read", "offline_access"],
                authorization_response_iss_parameter_supported=True,
            ),
        )

    class FakeOAuthHTTPClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def post(self, url: str, *, data: dict, headers: dict):
            assert url == "https://auth.example.com/token"
            assert data["resource"] == "https://mcp.example.com/mcp"
            assert data["client_id"] == "kuma-test-client"
            assert data["client_secret"] == "client-secret-value"
            assert len(data["code_verifier"]) >= 43
            return httpx.Response(
                200,
                json={
                    "access_token": "oauth-access-token",
                    "refresh_token": "oauth-refresh-token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": "workspace:read offline_access",
                },
            )

    monkeypatch.setattr(mcp_routes, "_discover_oauth", discover_oauth)

    with TestClient(app) as client:
        signup = client.post(
            "/studio/v1/auth/signup",
            json={"email": "oauth@example.com", "password": "warm-paws-123"},
        )
        assert signup.status_code == 201
        created = client.post(
            "/studio/v1/mcp/connections",
            json={
                "name": "OAuth workspace",
                "server_url": "https://mcp.example.com/mcp",
                "auth_type": "oauth",
                "oauth_client_id": "kuma-test-client",
                "oauth_client_secret": "client-secret-value",
                "oauth_token_endpoint_auth_method": "client_secret_post",
            },
        )
        assert created.status_code == 201
        assert "client-secret-value" not in created.text
        connection_id = created.json()["id"]

        started = client.post(
            f"/studio/v1/mcp/connections/{connection_id}/oauth/start"
        )
        assert started.status_code == 200
        authorization_url = urlparse(started.json()["authorization_url"])
        parameters = parse_qs(authorization_url.query)
        assert parameters["resource"] == ["https://mcp.example.com/mcp"]
        assert parameters["scope"] == ["workspace:read offline_access"]
        assert parameters["code_challenge_method"] == ["S256"]
        assert len(parameters["code_challenge"][0]) >= 43
        state_value = parameters["state"][0]

        monkeypatch.setattr(mcp_routes.httpx, "AsyncClient", FakeOAuthHTTPClient)
        callback = client.get(
            "/studio/v1/mcp/oauth/callback",
            params={
                "code": "authorization-code",
                "state": state_value,
                "iss": "https://auth.example.com",
            },
            follow_redirects=False,
        )
        assert callback.status_code == 303
        assert callback.headers["location"].endswith(
            "/studio/settings?mcp=connected"
        )

    database = sqlite3.connect(tmp_path / "kuma-test.db")
    encrypted = database.execute(
        "SELECT encrypted_credentials FROM mcp_connections WHERE id = ?",
        (connection_id,),
    ).fetchone()[0]
    database.close()
    assert "client-secret-value" not in encrypted
    assert "oauth-access-token" not in encrypted
    decrypted = SecretBox.from_settings(settings).decrypt(encrypted)
    assert "oauth-access-token" in decrypted
    assert "oauth-refresh-token" in decrypted


def test_mcp_oauth_registers_dynamically_without_client_id(monkeypatch) -> None:
    async def discover_oauth(server_url: str, request):
        assert server_url == "https://mcp.example.com/mcp"
        return (
            ProtectedResourceMetadata(
                resource="https://mcp.example.com/mcp",
                authorization_servers=["https://auth.example.com"],
                scopes_supported=["workspace:read"],
            ),
            OAuthMetadata(
                issuer="https://auth.example.com",
                authorization_endpoint="https://auth.example.com/authorize",
                token_endpoint="https://auth.example.com/token",
                registration_endpoint="https://auth.example.com/register",
                scopes_supported=["workspace:read", "offline_access"],
            ),
        )

    class FakeRegisterClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def post(self, url: str, *, json=None, data=None, headers=None):
            assert url == "https://auth.example.com/register"
            assert json["token_endpoint_auth_method"] == "none"
            assert json["application_type"] == "native"
            return httpx.Response(
                201,
                json={
                    "client_id": "dyn-kuma",
                    "token_endpoint_auth_method": "none",
                    "redirect_uris": json["redirect_uris"],
                },
            )

    monkeypatch.setattr(mcp_routes, "_discover_oauth", discover_oauth)

    with TestClient(app) as client:
        monkeypatch.setattr(mcp_routes.httpx, "AsyncClient", FakeRegisterClient)
        signup = client.post(
            "/studio/v1/auth/signup",
            json={"email": "dcr@example.com", "password": "warm-paws-123"},
        )
        assert signup.status_code == 201
        created = client.post(
            "/studio/v1/mcp/connections",
            json={
                "name": "OAuth workspace",
                "server_url": "https://mcp.example.com/mcp",
                "auth_type": "oauth",
            },
        )
        assert created.status_code == 201
        started = client.post(
            f"/studio/v1/mcp/connections/{created.json()['id']}/oauth/start"
        )

    assert started.status_code == 200
    parameters = parse_qs(urlparse(started.json()["authorization_url"]).query)
    assert parameters["client_id"] == ["dyn-kuma"]
    assert parameters["code_challenge_method"] == ["S256"]


def test_mcp_compacts_oversized_tool_catalog_results() -> None:
    items = [
        {
            "name": f"tool_{index}",
            "title": f"Tool {index}",
            "description": "x" * 4000,
            "inputSchema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
            },
            "annotations": {"readOnlyHint": True},
        }
        for index in range(30)
    ]
    result = SimpleNamespace(
        structured_content=None,
        content=[SimpleNamespace(type="text", text=json.dumps(items))],
        is_error=False,
    )

    output = MCPGateway._serialize_result(result)
    parsed = json.loads(output)

    assert len(json.dumps(items).encode("utf-8")) > MAX_TOOL_RESULT_BYTES
    assert len(output.encode("utf-8")) <= MAX_TOOL_RESULT_BYTES
    assert parsed[0]["name"] == "tool_0"
    assert parsed[0]["title"] == "Tool 0"
    assert "inputSchema" not in parsed[0]
    assert "annotations" not in parsed[0]
    assert len(parsed[0]["description"]) <= 240


def test_mcp_truncates_oversized_text_results() -> None:
    result = SimpleNamespace(
        structured_content=None,
        content=[
            SimpleNamespace(type="text", text="n" * (MAX_TOOL_RESULT_BYTES + 2048))
        ],
        is_error=False,
    )

    output = MCPGateway._serialize_result(result)

    assert len(output.encode("utf-8")) <= MAX_TOOL_RESULT_BYTES
    assert output.startswith("nnn")
    assert "[truncated from" in output


def test_mcp_rejects_private_urls_outside_local() -> None:
    production = Settings(_env_file=None, kuma_environment="production")
    with pytest.raises(MCPGatewayError, match="HTTPS"):
        validate_mcp_url("http://127.0.0.1:9/mcp", production)
    with pytest.raises(MCPGatewayError, match="Private"):
        asyncio.run(validate_mcp_destination("https://127.0.0.1/mcp", production))


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


def test_direct_realtime_session_returns_only_short_lived_credentials(
    monkeypatch,
) -> None:
    issuer = FakeRealtimeSessionIssuer()
    monkeypatch.setattr(settings, "openai_api_key", "server-secret-never-returned")
    monkeypatch.setattr(settings, "kuma_direct_realtime", True)

    with TestClient(app) as client:
        app.state.openai_realtime = OpenAIRealtimeConnector(settings)
        app.state.openai_realtime_sessions = issuer
        response = client.post("/api/v1/realtime/session")

    assert response.status_code == 200
    assert response.json() == {
        "url": (
            "wss://api.openai.com/v1/realtime?model="
            "gpt-realtime-2.1-mini"
        ),
        "client_secret": "ek_test_short_lived",
        "expires_at": 1_800_000_000,
        "session_id": "sess_test",
        "audio_format": "pcm16",
        "sample_rate": 24_000,
        "channels": 1,
    }
    assert "server-secret-never-returned" not in response.text
    assert issuer.connector is not None
    assert issuer.connector.session_configuration(include_model=True)["model"] == (
        "gpt-realtime-2.1-mini"
    )
    assert issuer.safety_identifier is None


def test_direct_realtime_session_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "kuma_direct_realtime", False)

    with TestClient(app) as client:
        response = client.post("/api/v1/realtime/session")

    assert response.status_code == 404


def test_realtime_session_issuer_sends_configured_session() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("authorization")
        captured["safety_identifier"] = request.headers.get(
            "openai-safety-identifier"
        )
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "value": "ek_test",
                "expires_at": 1_800_000_000,
                "session": {"id": "sess_test"},
            },
        )

    configured = Settings(
        _env_file=None,
        openai_api_key="standard-secret",
        exa_api_key="exa-test",
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    issuer = OpenAIRealtimeSessionIssuer(configured, client=client)
    async def issue() -> dict:
        result = await issuer.issue(
            OpenAIRealtimeConnector(configured),
            safety_identifier="kuma_user_hash",
        )
        await client.aclose()
        return result

    issued = asyncio.run(issue())

    assert issued == {
        "value": "ek_test",
        "expires_at": 1_800_000_000,
        "session_id": "sess_test",
    }
    assert captured["authorization"] == "Bearer standard-secret"
    assert captured["safety_identifier"] == "kuma_user_hash"
    assert captured["body"]["session"]["model"] == "gpt-realtime-2.1-mini"
    assert captured["body"]["session"]["audio"]["input"]["format"] == {
        "type": "audio/pcm",
        "rate": 24_000,
    }
    assert captured["body"]["session"]["tools"] == [WEB_SEARCH_TOOL]


def test_direct_realtime_tool_relay_is_allowlisted() -> None:
    search = FakeExa()

    with TestClient(app) as client:
        app.state.tools = ToolRegistry(search=search)
        success = client.post(
            "/api/v1/realtime/tools/web_search",
            json={"arguments": {"query": "weather in milan"}},
        )
        rejected = client.post(
            "/api/v1/realtime/tools/not_a_tool",
            json={"arguments": {}},
        )

    assert success.status_code == 200
    assert json.loads(success.json()["output"])["results"][0]["title"] == "Weather"
    assert search.queries == ["weather in milan"]
    assert rejected.status_code == 400
    assert rejected.json() == {"detail": "Unknown tool: 'not_a_tool'"}


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
