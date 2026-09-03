import base64
import json
import secrets
from datetime import timedelta, timezone
from typing import Any, Literal
from urllib.parse import quote, urlencode, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from mcp.client.auth.oauth2 import PKCEParameters, check_registration_usable
from mcp.client.auth.utils import (
    build_oauth_authorization_server_metadata_discovery_urls,
    build_protected_resource_metadata_discovery_urls,
    credentials_match_issuer,
    is_valid_client_metadata_url,
    validate_metadata_issuer,
)
from mcp.shared.auth import (
    OAuthClientInformationFull,
    OAuthClientMetadata,
    OAuthMetadata,
    OAuthToken,
    ProtectedResourceMetadata,
)
from mcp.shared.auth_utils import check_resource_allowed, resource_url_from_server_url
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .mcp_gateway import (
    MAX_MCP_CONNECTIONS,
    DatabaseOAuthStorage,
    MCPGatewayError,
    validate_mcp_destination,
)
from .models import MCPConnection, MCPOAuthFlow, MCPTool, utcnow
from .platform import (
    StudioIdentity,
    database_session,
    require_studio_identity,
    secret_box_from,
    settings_from,
)
from .security import token_hash


mcp_router = APIRouter(prefix="/studio/v1/mcp", tags=["studio mcp"])
mcp_metadata_router = APIRouter(tags=["mcp oauth"])


class MCPConnectionInput(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    server_url: str = Field(min_length=8, max_length=2048)
    auth_type: Literal["none", "bearer", "oauth"] = "none"
    bearer_token: str | None = Field(default=None, min_length=1, max_length=4096)
    oauth_client_id: str | None = Field(default=None, max_length=2048)
    oauth_client_secret: str | None = Field(default=None, max_length=4096)
    oauth_token_endpoint_auth_method: Literal[
        "none", "client_secret_basic", "client_secret_post"
    ] = "none"


class MCPConnectionUpdate(BaseModel):
    enabled: bool


class MCPToolUpdate(BaseModel):
    enabled: bool
    risk: Literal["read", "write"] = "read"


def _tool_payload(tool: MCPTool) -> dict[str, Any]:
    return {
        "id": tool.id,
        "remote_name": tool.remote_name,
        "name": tool.exposed_name,
        "title": tool.title,
        "description": tool.description,
        "input_schema": tool.input_schema,
        "enabled": tool.enabled,
        "risk": tool.risk,
    }


async def _connection_payload(
    session: AsyncSession,
    connection: MCPConnection,
) -> dict[str, Any]:
    tools = list(
        (
            await session.scalars(
                select(MCPTool)
                .where(MCPTool.connection_id == connection.id)
                .order_by(MCPTool.remote_name)
            )
        ).all()
    )
    return {
        "id": connection.id,
        "name": connection.name,
        "server_url": connection.server_url,
        "auth_type": connection.auth_type,
        "enabled": connection.enabled,
        "status": connection.status,
        "last_error": connection.last_error,
        "catalog_expires_at": (
            connection.catalog_expires_at.isoformat()
            if connection.catalog_expires_at
            else None
        ),
        "tools": [_tool_payload(tool) for tool in tools],
    }


@mcp_router.get("/connections")
async def list_connections(
    identity: StudioIdentity = Depends(require_studio_identity),
    session: AsyncSession = Depends(database_session),
) -> dict[str, Any]:
    connections = list(
        (
            await session.scalars(
                select(MCPConnection)
                .where(MCPConnection.user_id == identity.user.id)
                .order_by(MCPConnection.created_at)
            )
        ).all()
    )
    return {
        "connections": [
            await _connection_payload(session, connection)
            for connection in connections
        ]
    }


@mcp_router.post("/connections", status_code=201)
async def create_connection(
    body: MCPConnectionInput,
    request: Request,
    identity: StudioIdentity = Depends(require_studio_identity),
    session: AsyncSession = Depends(database_session),
) -> dict[str, Any]:
    try:
        server_url = await validate_mcp_destination(
            body.server_url, settings_from(request)
        )
    except MCPGatewayError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    existing = await session.scalar(
        select(func.count())
        .select_from(MCPConnection)
        .where(MCPConnection.user_id == identity.user.id)
    )
    if (existing or 0) >= MAX_MCP_CONNECTIONS:
        raise HTTPException(
            status_code=409,
            detail=f"You can connect up to {MAX_MCP_CONNECTIONS} MCP servers",
        )

    credentials: dict[str, Any] = {}
    if body.auth_type == "bearer":
        if not body.bearer_token:
            raise HTTPException(status_code=422, detail="Enter a bearer token")
        credentials["bearer_token"] = body.bearer_token
    elif body.auth_type == "oauth":
        if body.oauth_client_secret and not body.oauth_client_id:
            raise HTTPException(
                status_code=422,
                detail="An OAuth client secret requires a client ID",
            )
        if body.oauth_client_id:
            credentials["oauth_client_id"] = body.oauth_client_id
            credentials["oauth_client_secret"] = body.oauth_client_secret
            credentials["oauth_token_endpoint_auth_method"] = (
                body.oauth_token_endpoint_auth_method
            )

    encrypted = (
        secret_box_from(request).encrypt(json.dumps(credentials, separators=(",", ":")))
        if credentials
        else None
    )
    connection = MCPConnection(
        user_id=identity.user.id,
        name=body.name.strip(),
        server_url=server_url,
        auth_type=body.auth_type,
        encrypted_credentials=encrypted,
        status="authorization_required" if body.auth_type == "oauth" else "pending",
    )
    session.add(connection)
    await session.commit()
    return await _connection_payload(session, connection)


@mcp_router.patch("/connections/{connection_id}")
async def update_connection(
    connection_id: str,
    body: MCPConnectionUpdate,
    identity: StudioIdentity = Depends(require_studio_identity),
    session: AsyncSession = Depends(database_session),
) -> dict[str, Any]:
    connection = await _owned_connection(session, identity.user.id, connection_id)
    connection.enabled = body.enabled
    connection.updated_at = utcnow()
    await session.commit()
    return await _connection_payload(session, connection)


@mcp_router.delete("/connections/{connection_id}", status_code=204)
async def delete_connection(
    connection_id: str,
    identity: StudioIdentity = Depends(require_studio_identity),
    session: AsyncSession = Depends(database_session),
) -> None:
    connection = await _owned_connection(session, identity.user.id, connection_id)
    await session.execute(delete(MCPTool).where(MCPTool.connection_id == connection.id))
    await session.execute(
        delete(MCPOAuthFlow).where(MCPOAuthFlow.connection_id == connection.id)
    )
    await session.delete(connection)
    await session.commit()


@mcp_router.post("/connections/{connection_id}/discover")
async def discover_connection(
    connection_id: str,
    request: Request,
    identity: StudioIdentity = Depends(require_studio_identity),
) -> dict[str, Any]:
    try:
        await request.app.state.mcp.discover(identity.user.id, connection_id)
    except MCPGatewayError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    async with request.app.state.database() as session:
        connection = await _owned_connection(session, identity.user.id, connection_id)
        return await _connection_payload(session, connection)


@mcp_router.patch("/connections/{connection_id}/tools/{tool_id}")
async def update_tool(
    connection_id: str,
    tool_id: str,
    body: MCPToolUpdate,
    identity: StudioIdentity = Depends(require_studio_identity),
    session: AsyncSession = Depends(database_session),
) -> dict[str, Any]:
    await _owned_connection(session, identity.user.id, connection_id)
    tool = await session.scalar(
        select(MCPTool).where(
            MCPTool.id == tool_id,
            MCPTool.connection_id == connection_id,
        )
    )
    if tool is None:
        raise HTTPException(status_code=404, detail="MCP tool not found")
    tool.enabled = body.enabled
    tool.risk = body.risk
    tool.updated_at = utcnow()
    await session.commit()
    return _tool_payload(tool)


@mcp_router.post("/connections/{connection_id}/oauth/start")
async def start_oauth(
    connection_id: str,
    request: Request,
    identity: StudioIdentity = Depends(require_studio_identity),
    session: AsyncSession = Depends(database_session),
) -> dict[str, str]:
    connection = await _owned_connection(session, identity.user.id, connection_id)
    if connection.auth_type != "oauth":
        raise HTTPException(status_code=409, detail="This connection does not use OAuth")

    try:
        prm, oauth = await _discover_oauth(connection.server_url, request)
    except (MCPGatewayError, ValidationError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Kuma could not discover OAuth for that MCP server",
        ) from exc

    try:
        client_info = await _resolve_oauth_client(connection, oauth, request)
    except MCPGatewayError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except HTTPException:
        raise
    client_id = client_info.client_id
    client_secret = client_info.client_secret
    auth_method = client_info.token_endpoint_auth_method or "none"

    scopes = list(prm.scopes_supported or oauth.scopes_supported or [])
    if oauth.scopes_supported and "offline_access" in oauth.scopes_supported:
        if "offline_access" not in scopes:
            scopes.append("offline_access")
    scope = " ".join(scopes) or None
    resource = str(prm.resource)
    expected_resource = resource_url_from_server_url(connection.server_url)
    if not check_resource_allowed(
        requested_resource=expected_resource,
        configured_resource=resource,
    ):
        raise HTTPException(status_code=502, detail="MCP OAuth resource mismatch")

    try:
        await validate_mcp_destination(
            str(oauth.authorization_endpoint), settings_from(request)
        )
        await validate_mcp_destination(str(oauth.token_endpoint), settings_from(request))
    except MCPGatewayError as exc:
        raise HTTPException(
            status_code=502,
            detail="Kuma could not use that OAuth server",
        ) from exc

    pkce = PKCEParameters.generate()
    state_value = secrets.token_urlsafe(32)
    flow = MCPOAuthFlow(
        connection_id=connection.id,
        user_id=identity.user.id,
        state_hash=token_hash(state_value),
        encrypted_code_verifier=secret_box_from(request).encrypt(pkce.code_verifier),
        issuer=str(oauth.issuer),
        issuer_required=bool(oauth.authorization_response_iss_parameter_supported),
        token_endpoint=str(oauth.token_endpoint),
        client_id=client_id,
        encrypted_client_secret=(
            secret_box_from(request).encrypt(client_secret)
            if isinstance(client_secret, str) and client_secret
            else None
        ),
        token_endpoint_auth_method=auth_method,
        resource=resource,
        scope=scope,
        expires_at=utcnow() + timedelta(minutes=10),
    )
    session.add(flow)
    if not client_info.issuer:
        client_info.issuer = str(oauth.issuer)
    await session.commit()
    storage = DatabaseOAuthStorage(
        request.app.state.database,
        secret_box_from(request),
        connection.id,
    )
    await storage.set_client_info(client_info)

    parameters = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": settings_from(request).kuma_mcp_oauth_callback_url,
        "state": state_value,
        "code_challenge": pkce.code_challenge,
        "code_challenge_method": "S256",
        "resource": resource,
    }
    if scope:
        parameters["scope"] = scope
    authorization_url = f"{oauth.authorization_endpoint}?{urlencode(parameters)}"
    connection.oauth_issuer = str(oauth.issuer)
    connection.oauth_token_endpoint = str(oauth.token_endpoint)
    connection.oauth_resource = resource
    connection.oauth_scope = scope
    await session.commit()
    return {"authorization_url": authorization_url}


@mcp_router.get("/oauth/callback")
async def oauth_callback(
    request: Request,
    code: str = Query(min_length=1, max_length=4096),
    state_value: str = Query(alias="state", min_length=20, max_length=512),
    iss: str | None = Query(default=None, max_length=2048),
    session: AsyncSession = Depends(database_session),
) -> RedirectResponse:
    flow = await session.scalar(
        select(MCPOAuthFlow).where(MCPOAuthFlow.state_hash == token_hash(state_value))
    )
    expires_at = flow.expires_at if flow is not None else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if flow is None or expires_at is None or expires_at <= utcnow():
        raise HTTPException(status_code=400, detail="The OAuth request expired")
    if flow.issuer_required and not iss:
        raise HTTPException(status_code=400, detail="OAuth issuer is missing")
    if iss is not None and not secrets.compare_digest(iss, flow.issuer):
        raise HTTPException(status_code=400, detail="OAuth issuer mismatch")

    verifier = secret_box_from(request).decrypt(flow.encrypted_code_verifier)
    client_secret = (
        secret_box_from(request).decrypt(flow.encrypted_client_secret)
        if flow.encrypted_client_secret
        else None
    )
    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings_from(request).kuma_mcp_oauth_callback_url,
        "client_id": flow.client_id,
        "code_verifier": verifier,
        "resource": flow.resource,
    }
    token_headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if flow.token_endpoint_auth_method == "client_secret_post" and client_secret:
        token_data["client_secret"] = client_secret
    elif flow.token_endpoint_auth_method == "client_secret_basic" and client_secret:
        credentials = f"{quote(flow.client_id, safe='')}:{quote(client_secret, safe='')}"
        token_headers["Authorization"] = (
            "Basic " + base64.b64encode(credentials.encode()).decode()
        )

    try:
        await validate_mcp_destination(flow.token_endpoint, settings_from(request))
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            response = await client.post(
                flow.token_endpoint,
                data=token_data,
                headers=token_headers,
            )
        if response.status_code not in {200, 201}:
            raise MCPGatewayError("OAuth token exchange failed")
        token = OAuthToken.model_validate(response.json())
    except (httpx.HTTPError, ValueError, ValidationError, MCPGatewayError) as exc:
        raise HTTPException(status_code=502, detail="OAuth token exchange failed") from exc

    storage = DatabaseOAuthStorage(
        request.app.state.database,
        secret_box_from(request),
        flow.connection_id,
    )
    await storage.set_tokens(token)
    connection = await session.get(MCPConnection, flow.connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="MCP connection not found")
    connection.status = "pending"
    connection.last_error = None
    await session.delete(flow)
    await session.commit()
    destination = settings_from(request).kuma_studio_url.rstrip("/")
    return RedirectResponse(f"{destination}/settings?mcp=connected", status_code=303)


@mcp_metadata_router.get("/.well-known/oauth-client/kumavoice.json")
async def oauth_client_metadata(request: Request) -> dict[str, Any]:
    callback = settings_from(request).kuma_mcp_oauth_callback_url
    return {
        "client_name": "Kuma Voice",
        "client_uri": settings_from(request).kuma_studio_url,
        "redirect_uris": [callback],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
        "application_type": _oauth_application_type(callback),
    }


async def _resolve_oauth_client(
    connection: MCPConnection,
    oauth: OAuthMetadata,
    request: Request,
) -> OAuthClientInformationFull:
    settings = settings_from(request)
    callback = settings.kuma_mcp_oauth_callback_url
    credentials = _credentials(connection, request)
    metadata_url = settings.kuma_mcp_client_metadata_url.strip()
    storage = DatabaseOAuthStorage(
        request.app.state.database,
        secret_box_from(request),
        connection.id,
    )
    issuer = str(oauth.issuer)

    supplied_id = credentials.get("oauth_client_id")
    if isinstance(supplied_id, str) and supplied_id:
        supplied_secret = credentials.get("oauth_client_secret")
        supplied_method = credentials.get("oauth_token_endpoint_auth_method", "none")
        return OAuthClientInformationFull(
            client_id=supplied_id,
            client_secret=supplied_secret if isinstance(supplied_secret, str) else None,
            token_endpoint_auth_method=(
                supplied_method if isinstance(supplied_method, str) else "none"
            ),
            redirect_uris=[callback],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            application_type=_oauth_application_type(callback),
            issuer=issuer,
        )

    if oauth.client_id_metadata_document_supported and metadata_url:
        if not is_valid_client_metadata_url(metadata_url):
            raise HTTPException(
                status_code=503,
                detail="Kuma's OAuth client metadata URL is not configured correctly",
            )
        return OAuthClientInformationFull(
            client_id=metadata_url,
            token_endpoint_auth_method="none",
            redirect_uris=[callback],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            application_type=_oauth_application_type(callback),
            issuer=issuer,
        )

    stored = await storage.get_client_info()
    if (
        stored is not None
        and stored.client_id
        and credentials_match_issuer(stored, issuer, metadata_url or None)
    ):
        return stored

    if oauth.registration_endpoint is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "This OAuth server does not allow automatic sign-in. "
                "Enter a client ID if the server issued one."
            ),
        )
    return await _register_oauth_client(oauth, request)


async def _register_oauth_client(
    oauth: OAuthMetadata,
    request: Request,
) -> OAuthClientInformationFull:
    settings = settings_from(request)
    callback = settings.kuma_mcp_oauth_callback_url
    registration_url = str(oauth.registration_endpoint)
    await validate_mcp_destination(registration_url, settings)
    metadata = OAuthClientMetadata(
        redirect_uris=[callback],
        client_name="Kuma Voice",
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        token_endpoint_auth_method="none",
        application_type=_oauth_application_type(callback),
    )
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            response = await client.post(
                registration_url,
                json=metadata.model_dump(by_alias=True, mode="json", exclude_none=True),
                headers={"Content-Type": "application/json"},
            )
        if response.status_code not in {200, 201}:
            raise MCPGatewayError("Kuma could not register with that OAuth server")
        body = response.json()
        if isinstance(body, dict):
            body.pop("issuer", None)
        client_info = OAuthClientInformationFull.model_validate(body)
        check_registration_usable(client_info)
    except (httpx.HTTPError, ValueError, ValidationError) as exc:
        raise MCPGatewayError("Kuma could not register with that OAuth server") from exc
    return client_info


def _oauth_application_type(callback: str) -> Literal["web", "native"]:
    host = (urlparse(callback).hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        return "native"
    return "web"


async def _owned_connection(
    session: AsyncSession,
    user_id: str,
    connection_id: str,
) -> MCPConnection:
    connection = await session.scalar(
        select(MCPConnection).where(
            MCPConnection.id == connection_id,
            MCPConnection.user_id == user_id,
        )
    )
    if connection is None:
        raise HTTPException(status_code=404, detail="MCP connection not found")
    return connection


def _credentials(connection: MCPConnection, request: Request) -> dict[str, Any]:
    if not connection.encrypted_credentials:
        return {}
    return json.loads(
        secret_box_from(request).decrypt(connection.encrypted_credentials)
    )


async def _discover_oauth(
    server_url: str,
    request: Request,
) -> tuple[ProtectedResourceMetadata, OAuthMetadata]:
    settings = settings_from(request)
    await validate_mcp_destination(server_url, settings)
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
        prm = await _first_metadata(
            client,
            build_protected_resource_metadata_discovery_urls(None, server_url),
            ProtectedResourceMetadata,
            settings,
        )
        authorization_server = str(prm.authorization_servers[0])
        oauth = await _first_metadata(
            client,
            build_oauth_authorization_server_metadata_discovery_urls(
                authorization_server, server_url
            ),
            OAuthMetadata,
            settings,
        )
    validate_metadata_issuer(oauth, authorization_server)
    return prm, oauth


async def _first_metadata(
    client: httpx.AsyncClient,
    urls: list[str],
    model: Any,
    settings: Any,
) -> Any:
    for url in urls:
        await validate_mcp_destination(url, settings)
        try:
            response = await client.get(url, headers={"Accept": "application/json"})
        except httpx.HTTPError:
            continue
        if response.status_code == status.HTTP_200_OK and len(response.content) <= 128 * 1024:
            try:
                return model.model_validate(response.json())
            except (ValueError, ValidationError):
                continue
    raise MCPGatewayError("OAuth metadata was not found")
