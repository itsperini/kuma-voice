import asyncio
import ipaddress
import json
import re
import socket
import time
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any, AsyncIterator
from urllib.parse import urlparse

import httpx2
from mcp import Client
from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.client.auth.utils import is_valid_client_metadata_url
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .config import Settings
from .models import MCPConnection, MCPTool, utcnow
from .security import SecretBox
from .tools import ToolRegistry


class MCPGatewayError(Exception):
    pass


MAX_MCP_CONNECTIONS = 10
MAX_TOOLS_PER_CONNECTION = 40
MAX_TOOL_PAGES = 8
MAX_TOOL_SCHEMA_BYTES = 16 * 1024
MAX_TOOL_RESULT_BYTES = 64 * 1024
_TOOL_DESCRIPTOR_BULKY_KEYS = {
    "annotations",
    "inputSchema",
    "input_schema",
    "instructions",
}
_TOOL_DESCRIPTOR_DESCRIPTION_CHARS = 240
_UNPARSED = object()


def validate_mcp_url(value: str, settings: Settings) -> str:
    value = value.strip()
    parsed = urlparse(value)
    if parsed.username or parsed.password:
        raise MCPGatewayError("MCP URLs cannot contain credentials")
    if not parsed.hostname or parsed.scheme not in {"http", "https"}:
        raise MCPGatewayError("Enter a valid Streamable HTTP MCP URL")
    if parsed.scheme != "https" and settings.kuma_environment != "local":
        raise MCPGatewayError("Production MCP servers must use HTTPS")
    return value


async def validate_mcp_destination(value: str, settings: Settings) -> str:
    value = validate_mcp_url(value, settings)
    if settings.kuma_environment == "local":
        return value

    hostname = urlparse(value).hostname
    assert hostname is not None
    try:
        addresses = await asyncio.to_thread(
            socket.getaddrinfo,
            hostname,
            None,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise MCPGatewayError("The MCP server hostname could not be resolved") from exc

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise MCPGatewayError("Private network MCP addresses are not allowed")
    return value


def exposed_tool_name(connection_id: str, remote_name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", remote_name).strip("_") or "tool"
    return f"mcp_{connection_id.replace('-', '')[:8]}_{slug}"[:64]


class DatabaseOAuthStorage(TokenStorage):
    def __init__(
        self,
        factory: async_sessionmaker[AsyncSession],
        secret_box: SecretBox,
        connection_id: str,
    ) -> None:
        self.factory = factory
        self.secret_box = secret_box
        self.connection_id = connection_id

    async def _read(self) -> dict[str, Any]:
        async with self.factory() as session:
            connection = await session.get(MCPConnection, self.connection_id)
            if connection is None or not connection.encrypted_credentials:
                return {}
            return json.loads(self.secret_box.decrypt(connection.encrypted_credentials))

    async def _write(self, values: dict[str, Any]) -> None:
        async with self.factory() as session:
            connection = await session.get(MCPConnection, self.connection_id)
            if connection is None:
                raise MCPGatewayError("The MCP connection no longer exists")
            current: dict[str, Any] = {}
            if connection.encrypted_credentials:
                current = json.loads(
                    self.secret_box.decrypt(connection.encrypted_credentials)
                )
            current.update(values)
            connection.encrypted_credentials = self.secret_box.encrypt(
                json.dumps(current, separators=(",", ":"))
            )
            connection.updated_at = utcnow()
            await session.commit()

    async def get_tokens(self) -> OAuthToken | None:
        stored = await self._read()
        raw = stored.get("oauth_token")
        if not isinstance(raw, dict):
            return None
        token = OAuthToken.model_validate(raw)
        obtained_at = stored.get("oauth_obtained_at")
        if token.expires_in is not None and isinstance(obtained_at, (int, float)):
            elapsed = max(0, int(time.time() - obtained_at))
            token.expires_in = max(0, token.expires_in - elapsed)
        return token

    async def set_tokens(self, tokens: OAuthToken) -> None:
        await self._write(
            {
                "oauth_token": tokens.model_dump(mode="json", exclude_none=True),
                "oauth_obtained_at": int(time.time()),
            }
        )

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        raw = (await self._read()).get("oauth_client_info")
        return OAuthClientInformationFull.model_validate(raw) if isinstance(raw, dict) else None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        await self._write(
            {
                "oauth_client_info": client_info.model_dump(
                    mode="json", exclude_none=True
                )
            }
        )


class MCPGateway:
    def __init__(
        self,
        settings: Settings,
        factory: async_sessionmaker[AsyncSession],
        secret_box: SecretBox,
    ) -> None:
        self.settings = settings
        self.factory = factory
        self.secret_box = secret_box

    async def openai_tools(self, user_id: str) -> list[dict[str, Any]]:
        async with self.factory() as session:
            rows = (
                await session.execute(
                    select(MCPTool, MCPConnection)
                    .join(MCPConnection, MCPConnection.id == MCPTool.connection_id)
                    .where(
                        MCPConnection.user_id == user_id,
                        MCPConnection.enabled.is_(True),
                        MCPConnection.status == "connected",
                        MCPTool.enabled.is_(True),
                    )
                    .order_by(MCPTool.exposed_name)
                )
            ).all()
        return [
            {
                "type": "function",
                "name": tool.exposed_name,
                "description": tool.description or tool.title or tool.remote_name,
                "parameters": tool.input_schema,
            }
            for tool, _ in rows
        ]

    async def discover(self, user_id: str, connection_id: str) -> list[MCPTool]:
        async with self.factory() as session:
            connection = await session.scalar(
                select(MCPConnection).where(
                    MCPConnection.id == connection_id,
                    MCPConnection.user_id == user_id,
                )
            )
        if connection is None:
            raise MCPGatewayError("MCP connection not found")

        await validate_mcp_destination(connection.server_url, self.settings)
        try:
            async with self._client(connection) as client:
                pages = []
                cursor: str | None = None
                ttl_ms = 0
                for _ in range(MAX_TOOL_PAGES):
                    result = await client.list_tools(cursor=cursor)
                    pages.extend(result.tools)
                    if result.ttl_ms:
                        ttl_ms = result.ttl_ms
                    cursor = result.next_cursor
                    if cursor is None:
                        break
                pages = pages[:MAX_TOOLS_PER_CONNECTION]
        except Exception as exc:
            await self._mark_failure(connection.id)
            raise MCPGatewayError("Kuma could not connect to that MCP server") from exc

        async with self.factory() as session:
            connection = await session.get(MCPConnection, connection_id)
            assert connection is not None
            existing = {
                tool.remote_name: tool
                for tool in (
                    await session.scalars(
                        select(MCPTool).where(MCPTool.connection_id == connection_id)
                    )
                ).all()
            }
            seen: set[str] = set()
            for discovered in pages:
                seen.add(discovered.name)
                tool = existing.get(discovered.name)
                if tool is None:
                    tool = MCPTool(
                        connection_id=connection_id,
                        remote_name=discovered.name,
                        exposed_name=exposed_tool_name(connection_id, discovered.name),
                        input_schema=_tool_schema(discovered.input_schema),
                        enabled=False,
                    )
                    session.add(tool)
                tool.title = discovered.title
                tool.description = discovered.description
                tool.input_schema = _tool_schema(discovered.input_schema)
                tool.updated_at = utcnow()

            removed = [tool.id for name, tool in existing.items() if name not in seen]
            if removed:
                await session.execute(delete(MCPTool).where(MCPTool.id.in_(removed)))
            ttl_seconds = max(
                1,
                min(
                    int(ttl_ms / 1000) if ttl_ms else self.settings.kuma_mcp_catalog_seconds,
                    24 * 60 * 60,
                ),
            )
            connection.catalog_expires_at = utcnow() + timedelta(seconds=ttl_seconds)
            connection.status = "connected"
            connection.last_error = None
            connection.updated_at = utcnow()
            await session.commit()
            return list(
                (
                    await session.scalars(
                        select(MCPTool)
                        .where(MCPTool.connection_id == connection_id)
                        .order_by(MCPTool.remote_name)
                    )
                ).all()
            )

    async def execute(
        self,
        user_id: str,
        exposed_name: str,
        arguments: dict[str, Any],
    ) -> str:
        async with self.factory() as session:
            row = (
                await session.execute(
                    select(MCPTool, MCPConnection)
                    .join(MCPConnection, MCPConnection.id == MCPTool.connection_id)
                    .where(
                        MCPTool.exposed_name == exposed_name,
                        MCPTool.enabled.is_(True),
                        MCPConnection.user_id == user_id,
                        MCPConnection.enabled.is_(True),
                        MCPConnection.status == "connected",
                    )
                )
            ).first()
        if row is None:
            raise MCPGatewayError("That MCP tool is not enabled")
        tool, connection = row
        await validate_mcp_destination(connection.server_url, self.settings)

        try:
            async with self._client(connection) as client:
                result = await client.call_tool(tool.remote_name, arguments)
        except Exception as exc:
            raise MCPGatewayError("The MCP tool request failed") from exc
        return self._serialize_result(result)

    @asynccontextmanager
    async def _client(self, connection: MCPConnection) -> AsyncIterator[Client]:
        credentials = self._credentials(connection)
        auth = None
        headers: dict[str, str] = {}
        if connection.auth_type == "bearer":
            token = credentials.get("bearer_token")
            if not isinstance(token, str) or not token:
                raise MCPGatewayError("The MCP bearer token is missing")
            headers["Authorization"] = f"Bearer {token}"
        elif connection.auth_type == "oauth":
            storage = DatabaseOAuthStorage(
                self.factory, self.secret_box, connection.id
            )
            metadata = OAuthClientMetadata(
                redirect_uris=[self.settings.kuma_mcp_oauth_callback_url],
                client_name="Kuma Voice",
                grant_types=["authorization_code", "refresh_token"],
                response_types=["code"],
                scope=connection.oauth_scope,
                application_type="web",
            )
            raw_metadata_url = self.settings.kuma_mcp_client_metadata_url.strip()
            metadata_url = (
                raw_metadata_url
                if is_valid_client_metadata_url(raw_metadata_url)
                else None
            )
            auth = OAuthClientProvider(
                connection.server_url,
                metadata,
                storage,
                client_metadata_url=metadata_url,
            )

        timeout = httpx2.Timeout(30, read=60)
        async with httpx2.AsyncClient(
            auth=auth,
            headers=headers,
            # Redirect targets would need the same SSRF validation as the
            # configured endpoint. Streamable HTTP does not require them.
            follow_redirects=False,
            timeout=timeout,
        ) as http_client:
            transport = streamable_http_client(
                connection.server_url,
                http_client=http_client,
            )
            async with Client(transport, mode="auto") as client:
                yield client

    def _credentials(self, connection: MCPConnection) -> dict[str, Any]:
        if not connection.encrypted_credentials:
            return {}
        return json.loads(self.secret_box.decrypt(connection.encrypted_credentials))

    async def _mark_failure(self, connection_id: str) -> None:
        async with self.factory() as session:
            connection = await session.get(MCPConnection, connection_id)
            if connection is not None:
                connection.status = "error"
                connection.last_error = "Connection failed"
                connection.updated_at = utcnow()
                await session.commit()

    @staticmethod
    def _serialize_result(result: Any) -> str:
        parsed: Any = _UNPARSED
        if result.structured_content is not None:
            parsed = result.structured_content
            output = _dump_json(parsed)
        else:
            text = [
                block.text
                for block in result.content
                if getattr(block, "type", None) == "text"
                and isinstance(getattr(block, "text", None), str)
            ]
            output = "\n".join(text)
            parsed = _try_parse_json(output)
        if result.is_error:
            output = _dump_json({"error": output or "The MCP tool failed"})
            parsed = _UNPARSED
        return _limit_tool_output(output, parsed)


def _dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _try_parse_json(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return _UNPARSED


def _looks_like_tool_descriptor(item: Any) -> bool:
    return isinstance(item, dict) and (
        "inputSchema" in item or "input_schema" in item
    )


def _slim_tool_descriptor(item: dict[str, Any]) -> dict[str, Any]:
    slim = {
        key: value
        for key, value in item.items()
        if key not in _TOOL_DESCRIPTOR_BULKY_KEYS
    }
    description = slim.get("description")
    if (
        isinstance(description, str)
        and len(description) > _TOOL_DESCRIPTOR_DESCRIPTION_CHARS
    ):
        slim["description"] = description[: _TOOL_DESCRIPTOR_DESCRIPTION_CHARS - 3] + "..."
    return slim


def _compact_tool_descriptors(value: Any) -> Any:
    if isinstance(value, list):
        if value and all(_looks_like_tool_descriptor(item) for item in value):
            return [_slim_tool_descriptor(item) for item in value]
        return [_compact_tool_descriptors(item) for item in value]
    if isinstance(value, dict):
        return {key: _compact_tool_descriptors(item) for key, item in value.items()}
    return value


def _fit_json_list(items: list[Any], limit: int) -> str | None:
    low = 1
    high = len(items)
    best: str | None = None
    while low <= high:
        mid = (low + high) // 2
        omitted = len(items) - mid
        payload: list[Any] = items[:mid]
        if omitted:
            payload = payload + [{"_truncated": True, "omitted": omitted}]
        encoded = _dump_json(payload)
        if len(encoded.encode("utf-8")) <= limit:
            best = encoded
            low = mid + 1
        else:
            high = mid - 1
    return best


def _truncate_utf8(text: str, limit: int, suffix: str) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= limit:
        return text
    suffix_bytes = suffix.encode("utf-8")
    if len(suffix_bytes) >= limit:
        suffix = "[truncated]"
        suffix_bytes = suffix.encode("utf-8")
    budget = max(0, limit - len(suffix_bytes))
    clipped = encoded[:budget]
    while clipped:
        try:
            return clipped.decode("utf-8") + suffix
        except UnicodeDecodeError:
            clipped = clipped[:-1]
    return suffix


def _limit_tool_output(output: str, parsed: Any = _UNPARSED) -> str:
    output = output or "{}"
    encoded_len = len(output.encode("utf-8"))
    if encoded_len <= MAX_TOOL_RESULT_BYTES:
        return output
    candidate = parsed
    if candidate is _UNPARSED:
        candidate = _try_parse_json(output)
    if candidate is not _UNPARSED:
        compacted = _compact_tool_descriptors(candidate)
        compacted_text = _dump_json(compacted)
        if len(compacted_text.encode("utf-8")) <= MAX_TOOL_RESULT_BYTES:
            return compacted_text
        if isinstance(compacted, list):
            fitted = _fit_json_list(compacted, MAX_TOOL_RESULT_BYTES)
            if fitted is not None:
                return fitted
        output = compacted_text
    return _truncate_utf8(
        output,
        MAX_TOOL_RESULT_BYTES,
        f"\n[truncated from {encoded_len} bytes]",
    )


def _tool_schema(value: Any) -> dict[str, Any]:
    schema = value if isinstance(value, dict) else {"type": "object", "properties": {}}
    encoded = json.dumps(schema, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_TOOL_SCHEMA_BYTES:
        return {"type": "object", "properties": {}}
    return schema


class UserToolExecutor:
    def __init__(
        self,
        native: ToolRegistry,
        mcp: MCPGateway,
        user_id: str | None,
    ) -> None:
        self.native = native
        self.mcp = mcp
        self.user_id = user_id

    async def run(self, name: str, arguments: dict[str, Any]) -> str:
        if name.startswith("mcp_"):
            if self.user_id is None:
                raise MCPGatewayError("MCP tools require a paired Watch")
            return await self.mcp.execute(self.user_id, name, arguments)
        return await self.native.run(name, arguments)
