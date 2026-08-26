import base64
import hmac
import json
from contextlib import asynccontextmanager
from pathlib import Path

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
from starlette.websockets import WebSocketState
from websockets.exceptions import ConnectionClosed

from .calendar import GoogleCalendarClient
from .config import Settings, get_settings
from .conversations import ConversationNotFoundError, ConversationStore
from .exa import ExaClient
from .notion import NotionClient
from .openai_realtime import (
    OpenAIRealtimeConnector,
    RealtimeProtocolError,
    bridge_realtime_session,
)
from .openrouter import OpenRouterClient, OpenRouterError
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
    app.state.openrouter = OpenRouterClient(settings)
    app.state.openai_realtime = OpenAIRealtimeConnector(settings)
    app.state.tools = ToolRegistry(
        search=ExaClient(settings) if settings.web_search_api_key else None,
        notion=NotionClient(settings) if settings.notion_api_key.strip() else None,
        calendar=GoogleCalendarClient(settings) if settings.calendar_configured else None,
    )
    app.state.exa = app.state.tools.search
    yield
    await app.state.openrouter.aclose()
    await app.state.tools.aclose()


app = FastAPI(
    title="Kuma Voice API",
    version="0.1.0",
    description="Local voice assistant backend for the Kuma Voice watchOS prototype.",
    lifespan=lifespan,
)


def api_token_matches(authorization: str | None) -> bool:
    expected = settings.kuma_api_token.strip()
    if not expected:
        return True
    prefix = "Bearer "
    if not authorization or not authorization.startswith(prefix):
        return False
    provided = authorization[len(prefix) :].strip()
    return bool(provided) and hmac.compare_digest(provided, expected)


@app.middleware("http")
async def authenticate_api_request(request: Request, call_next):
    path = request.url.path
    is_api_request = path == "/api/v1" or path.startswith("/api/v1/")
    if is_api_request and not api_token_matches(request.headers.get("authorization")):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Unauthorized"},
        )
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


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@app.websocket("/api/v1/realtime")
async def realtime_voice(websocket: WebSocket) -> None:
    if not api_token_matches(websocket.headers.get("authorization")):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept()
    try:
        await bridge_realtime_session(
            websocket,
            websocket.app.state.openai_realtime,
            settings.kuma_max_audio_bytes,
            tools=getattr(websocket.app.state, "tools", None),
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
