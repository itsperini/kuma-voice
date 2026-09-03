import base64
import hashlib
import hmac
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.websockets import WebSocketState
from websockets.exceptions import ConnectionClosed

from .calendar import GoogleCalendarClient
from .config import Settings, get_settings
from .conversations import ConversationNotFoundError, ConversationStore
from .database import open_database
from .exa import ExaClient
from .mcp_gateway import MCPGateway, MCPGatewayError, UserToolExecutor
from .mcp_routes import mcp_metadata_router, mcp_router
from .notion import NotionClient
from .openai_realtime import (
    OpenAIRealtimeConnector,
    OpenAIRealtimeSessionIssuer,
    RealtimeProtocolError,
    RealtimeSessionError,
    bridge_realtime_session,
)
from .openrouter import OpenRouterClient, OpenRouterError
from .platform import (
    DevicePrincipal,
    device_router,
    load_device_runtime,
    resolve_device_principal,
    studio_router,
)
from .security import SecretBox
from .schemas import (
    ChatRequest,
    ChatResponse,
    ConversationCreated,
    HealthResponse,
    SpeechRequest,
    TranscriptionResponse,
    VoiceTurnResponse,
)
from .tools import ToolRegistry


settings: Settings = get_settings()
conversation_store = ConversationStore(settings.kuma_system_prompt)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = settings
    app.state.secret_box = SecretBox.from_settings(settings)
    database_engine, database = await open_database(settings)
    app.state.database_engine = database_engine
    app.state.database = database
    app.state.openrouter = OpenRouterClient(settings)
    app.state.openai_realtime = OpenAIRealtimeConnector(settings)
    app.state.openai_realtime_sessions = OpenAIRealtimeSessionIssuer(settings)
    app.state.tools = ToolRegistry(
        search=ExaClient(settings) if settings.web_search_api_key else None,
        notion=NotionClient(settings) if settings.notion_api_key.strip() else None,
        calendar=GoogleCalendarClient(settings) if settings.calendar_configured else None,
    )
    app.state.exa = app.state.tools.search
    app.state.mcp = MCPGateway(settings, database, app.state.secret_box)
    yield
    await app.state.openrouter.aclose()
    await app.state.openai_realtime_sessions.aclose()
    await app.state.tools.aclose()
    await app.state.database_engine.dispose()


app = FastAPI(
    title="Kuma Voice API",
    version="0.1.0",
    description="Local voice assistant backend for the Kuma Voice watchOS prototype.",
    lifespan=lifespan,
)
app.include_router(studio_router)
app.include_router(device_router)
app.include_router(mcp_router)
app.include_router(mcp_metadata_router)


def api_token_matches(authorization: str | None) -> bool:
    expected = settings.kuma_api_token.strip()
    if not expected:
        return False
    prefix = "Bearer "
    if not authorization or not authorization.startswith(prefix):
        return False
    provided = authorization[len(prefix) :].strip()
    return bool(provided) and hmac.compare_digest(provided, expected)


async def authorize_api_request(
    authorization: str | None,
    *,
    touch_device: bool = False,
) -> tuple[bool, DevicePrincipal | None]:
    if api_token_matches(authorization):
        return True, None

    principal = await resolve_device_principal(
        app.state.database,
        authorization,
        touch=touch_device,
    )
    if principal is not None:
        return True, principal

    shared_token_configured = bool(settings.kuma_api_token.strip())
    if not shared_token_configured and not settings.kuma_require_device_auth:
        return True, None
    return False, None


@app.middleware("http")
async def authenticate_api_request(request: Request, call_next):
    path = request.url.path
    is_api_request = path == "/api/v1" or path.startswith("/api/v1/")
    if is_api_request:
        authorized, principal = await authorize_api_request(
            request.headers.get("authorization"),
            touch_device=True,
        )
        if not authorized:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Unauthorized"},
            )
        request.state.device_principal = principal
    return await call_next(request)


@app.exception_handler(OpenRouterError)
async def handle_openrouter_error(_: Request, exc: OpenRouterError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"detail": str(exc)},
    )


def openrouter_from(request: Request) -> OpenRouterClient:
    return request.app.state.openrouter


async def read_audio(upload: UploadFile) -> tuple[bytes, str]:
    audio = await upload.read(settings.kuma_max_audio_bytes + 1)
    if not audio:
        raise HTTPException(status_code=400, detail="The audio file is empty")
    if len(audio) > settings.kuma_max_audio_bytes:
        raise HTTPException(status_code=413, detail="The audio file is too large")

    suffix = Path(upload.filename or "voice.m4a").suffix.lower().lstrip(".")
    audio_format = suffix or "m4a"
    if audio_format == "caf":
        audio_format = "wav"
    return audio, audio_format


class RealtimeToolRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)


async def realtime_connector_for(
    application: FastAPI,
    principal: DevicePrincipal | None,
) -> OpenAIRealtimeConnector:
    if principal is None:
        return application.state.openai_realtime

    runtime = await load_device_runtime(
        application.state.database,
        application.state.secret_box,
        principal.user_id,
    )
    personalized_prompt = settings.kuma_system_prompt.rstrip()
    if runtime.full_name:
        personalized_prompt += f" The user's name is {runtime.full_name}."
    style_instructions = {
        "brief": " Prefer short spoken answers.",
        "balanced": " Give enough spoken context to be useful without rambling.",
        "detailed": " Give a more complete answer when the request benefits from it.",
    }
    personalized_prompt += style_instructions.get(runtime.response_style, "")
    mcp_tools = await application.state.mcp.openai_tools(principal.user_id)
    return OpenAIRealtimeConnector(
        settings.model_copy(
            update={
                "openai_api_key": runtime.openai_api_key or "",
                "kuma_system_prompt": personalized_prompt,
            }
        ),
        extra_tools=mcp_tools,
    )


def realtime_tools_for(
    application: FastAPI,
    principal: DevicePrincipal | None,
) -> UserToolExecutor:
    return UserToolExecutor(
        application.state.tools,
        application.state.mcp,
        principal.user_id if principal is not None else None,
    )


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@app.post("/api/v1/realtime/session")
async def create_realtime_session(request: Request) -> dict[str, Any]:
    if not settings.kuma_direct_realtime:
        raise HTTPException(status_code=404, detail="Direct realtime is disabled")

    principal = getattr(request.state, "device_principal", None)
    connector = await realtime_connector_for(request.app, principal)
    safety_identifier = None
    if principal is not None:
        digest = hashlib.sha256(f"user:{principal.user_id}".encode()).hexdigest()
        safety_identifier = f"kuma_{digest[:32]}"

    try:
        issued = await request.app.state.openai_realtime_sessions.issue(
            connector,
            safety_identifier=safety_identifier,
        )
    except RealtimeSessionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    query = urlencode({"model": connector.settings.openai_realtime_model})
    return {
        "url": f"{connector.settings.openai_realtime_url}?{query}",
        "client_secret": issued["value"],
        "expires_at": issued["expires_at"],
        "session_id": issued["session_id"],
        "audio_format": "pcm16",
        "sample_rate": 24_000,
        "channels": 1,
    }


@app.post("/api/v1/realtime/tools/{tool_name}")
async def execute_realtime_tool(
    request: Request,
    tool_name: str,
    body: RealtimeToolRequest,
) -> dict[str, str]:
    argument_bytes = len(
        json.dumps(body.arguments, separators=(",", ":")).encode("utf-8")
    )
    if argument_bytes > 64 * 1024:
        raise HTTPException(status_code=413, detail="Tool arguments are too large")

    try:
        principal = getattr(request.state, "device_principal", None)
        output = await realtime_tools_for(request.app, principal).run(
            tool_name, body.arguments
        )
    except (RuntimeError, MCPGatewayError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="The tool request failed") from exc
    return {"output": output}


@app.websocket("/api/v1/realtime")
async def realtime_voice(websocket: WebSocket) -> None:
    authorized, principal = await authorize_api_request(
        websocket.headers.get("authorization"),
        touch_device=True,
    )
    if not authorized:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    connector = await realtime_connector_for(websocket.app, principal)

    await websocket.accept()
    try:
        await bridge_realtime_session(
            websocket,
            connector,
            settings.kuma_max_audio_bytes,
            tools=realtime_tools_for(websocket.app, principal),
            search=getattr(websocket.app.state, "exa", None),
        )
    except WebSocketDisconnect:
        return
    except ConnectionClosed:
        await _send_websocket_error(websocket, "The OpenAI realtime connection closed.")
    except (RealtimeProtocolError, json.JSONDecodeError) as exc:
        await _send_websocket_error(websocket, str(exc))
    except Exception:
        await _send_websocket_error(websocket, "The realtime voice session failed.")
    finally:
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.close()
            except (RuntimeError, WebSocketDisconnect):
                pass


async def _send_websocket_error(websocket: WebSocket, message: str) -> None:
    if websocket.client_state != WebSocketState.CONNECTED:
        return
    try:
        await websocket.send_json({"type": "error", "message": message})
    except (RuntimeError, WebSocketDisconnect):
        pass


@app.post("/api/v1/transcriptions", response_model=TranscriptionResponse)
async def transcribe(
    request: Request,
    audio: UploadFile = File(...),
    language: str | None = Form(default=None),
) -> TranscriptionResponse:
    audio_bytes, audio_format = await read_audio(audio)
    text = await openrouter_from(request).transcribe(audio_bytes, audio_format, language)
    return TranscriptionResponse(text=text)


@app.post("/api/v1/responses", response_model=ChatResponse)
async def create_response(request: Request, body: ChatRequest) -> ChatResponse:
    messages = [message.model_dump() for message in body.messages]
    text = await openrouter_from(request).chat(messages)
    return ChatResponse(text=text)


@app.post("/api/v1/speech")
async def create_speech(request: Request, body: SpeechRequest) -> Response:
    audio = await openrouter_from(request).synthesize(body.text)
    return Response(content=audio, media_type="audio/mpeg")


@app.post("/api/v1/conversations", response_model=ConversationCreated, status_code=201)
async def create_conversation() -> ConversationCreated:
    conversation_id = await conversation_store.create()
    return ConversationCreated(conversation_id=conversation_id)


@app.post(
    "/api/v1/conversations/{conversation_id}/turns",
    response_model=VoiceTurnResponse,
)
async def create_voice_turn(
    request: Request,
    conversation_id: str,
    audio: UploadFile = File(...),
    language: str | None = Form(default=None),
) -> VoiceTurnResponse:
    try:
        existing_messages = await conversation_store.messages(conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found") from exc

    audio_bytes, audio_format = await read_audio(audio)
    client = openrouter_from(request)
    user_text = await client.transcribe(audio_bytes, audio_format, language)

    await conversation_store.append(conversation_id, "user", user_text)
    reply_messages = [*existing_messages, {"role": "user", "content": user_text}]
    assistant_text = await client.chat(reply_messages)
    reply_audio = await client.synthesize(assistant_text)
    await conversation_store.append(conversation_id, "assistant", assistant_text)

    return VoiceTurnResponse(
        conversation_id=conversation_id,
        user_text=user_text,
        assistant_text=assistant_text,
        audio_base64=base64.b64encode(reply_audio).decode("ascii"),
    )


@app.delete("/api/v1/conversations/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: str) -> Response:
    deleted = await conversation_store.delete(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return Response(status_code=204)
