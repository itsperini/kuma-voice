from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .config import Settings
from .models import (
    Device,
    DeviceAuthorization,
    ProviderSecret,
    StudioSession,
    User,
    UserProfile,
    utcnow,
)
from .security import (
    SecretBox,
    display_user_code,
    hash_password,
    new_device_code,
    new_device_token,
    new_session_token,
    new_user_code,
    normalize_email,
    normalize_user_code,
    token_hash,
    verify_password,
)


studio_router = APIRouter(prefix="/studio/v1", tags=["studio"])
device_router = APIRouter(prefix="/device/v1", tags=["device pairing"])


class AuthInput(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)


class ProfileInput(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    role: str = Field(min_length=2, max_length=80)
    primary_goal: str | None = Field(default=None, min_length=10, max_length=160)
    use_cases: list[
        Literal[
            "personal-assistant",
            "workflows-approvals",
            "reminders-planning",
            "smart-home",
            "hands-free-access",
            "fitness-outdoors",
            "voice-mcp",
            "exploring",
        ]
    ] = Field(min_length=1, max_length=3)
    technical_comfort: Literal["everyday", "tinkerer", "developer"]
    discovery_source: Literal[
        "x",
        "tiktok",
        "instagram",
        "youtube",
        "reddit",
        "hacker-news",
        "github",
        "product-hunt",
        "friend",
        "search",
        "other",
    ]
    response_style: Literal["brief", "balanced", "detailed"]


class PairingApprovalInput(BaseModel):
    user_code: str = Field(min_length=6, max_length=12)


class ProviderKeyInput(BaseModel):
    api_key: str = Field(min_length=20, max_length=512)


class DeviceAuthorizationInput(BaseModel):
    device_name: str = Field(default="Apple Watch", min_length=2, max_length=80)


class DeviceTokenInput(BaseModel):
    device_code: str = Field(min_length=20, max_length=256)


@dataclass(frozen=True)
class StudioIdentity:
    user: User
    session: StudioSession


@dataclass(frozen=True)
class DevicePrincipal:
    user_id: str
    device_id: str


@dataclass(frozen=True)
class DeviceRuntime:
    openai_api_key: str | None
    full_name: str | None
    response_style: str


async def database_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.database
    async with factory() as session:
        yield session


def settings_from(request: Request) -> Settings:
    return request.app.state.settings


def secret_box_from(request: Request) -> SecretBox:
    return request.app.state.secret_box


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _bearer_token(authorization: str | None) -> str | None:
    prefix = "Bearer "
    if not authorization or not authorization.startswith(prefix):
        return None
    value = authorization[len(prefix) :].strip()
    return value or None


async def require_studio_identity(
    request: Request,
    session: AsyncSession = Depends(database_session),
) -> StudioIdentity:
    settings = settings_from(request)
    raw_token = request.cookies.get(settings.kuma_session_cookie_name)
    if not raw_token:
        raise HTTPException(status_code=401, detail="Sign in to continue")

    result = await session.execute(
        select(StudioSession, User)
        .join(User, User.id == StudioSession.user_id)
        .where(StudioSession.token_hash == token_hash(raw_token))
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=401, detail="Your session has expired")

    studio_session, user = row
    if _aware(studio_session.expires_at) <= utcnow():
        await session.delete(studio_session)
        await session.commit()
        raise HTTPException(status_code=401, detail="Your session has expired")
    return StudioIdentity(user=user, session=studio_session)


def _set_session_cookie(response: Response, settings: Settings, token: str) -> None:
    domain = settings.kuma_session_cookie_domain.strip() or None
    max_age = settings.kuma_session_days * 24 * 60 * 60
    response.set_cookie(
        key=settings.kuma_session_cookie_name,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=settings.kuma_session_cookie_secure,
        samesite="lax",
        path="/",
        domain=domain,
    )


async def _create_studio_session(
    session: AsyncSession, settings: Settings, user_id: str
) -> str:
    raw_token = new_session_token()
    session.add(
        StudioSession(
            user_id=user_id,
            token_hash=token_hash(raw_token),
            expires_at=utcnow() + timedelta(days=settings.kuma_session_days),
        )
    )
    await session.commit()
    return raw_token


def _user_payload(user: User) -> dict[str, object]:
    return {
        "id": user.id,
        "email": user.email,
    }


def _profile_payload(profile: UserProfile) -> dict[str, object]:
    return {
        "full_name": profile.full_name,
        "role": profile.role,
        "primary_goal": profile.primary_goal,
        "use_cases": profile.use_cases,
        "technical_comfort": profile.technical_comfort,
        "discovery_source": profile.discovery_source,
        "response_style": profile.response_style,
    }


def _device_payload(device: Device) -> dict[str, object]:
    return {
        "id": device.id,
        "name": device.name,
        "created_at": device.created_at.isoformat(),
        "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None,
    }


async def _bootstrap_payload(session: AsyncSession, user: User) -> dict[str, object]:
    profile = await session.get(UserProfile, user.id)
    devices = list(
        (
            await session.scalars(
                select(Device)
                .where(Device.user_id == user.id, Device.revoked_at.is_(None))
                .order_by(Device.created_at.desc())
            )
        ).all()
    )
    provider = await session.scalar(
        select(ProviderSecret).where(
            ProviderSecret.user_id == user.id,
            ProviderSecret.provider == "openai",
        )
    )
    profile_complete = profile is not None
    if not profile_complete:
        next_step = "profile"
    elif not devices:
        next_step = "watch"
    elif provider is None:
        next_step = "provider"
    else:
        next_step = "complete"

    return {
        "user": _user_payload(user),
        "profile": _profile_payload(profile) if profile else None,
        "profile_complete": profile_complete,
        "devices": [_device_payload(device) for device in devices],
        "openai": {
            "configured": provider is not None,
            "last_four": provider.last_four if provider else None,
        },
        "next_step": next_step,
    }


@studio_router.post("/auth/signup", status_code=201)
async def signup(
    body: AuthInput,
    response: Response,
    request: Request,
    session: AsyncSession = Depends(database_session),
) -> dict[str, object]:
    try:
        email = normalize_email(body.email)
        password_hash = hash_password(body.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if await session.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account already uses this email")

    user = User(email=email, password_hash=password_hash)
    session.add(user)
    await session.flush()
    raw_token = await _create_studio_session(session, settings_from(request), user.id)
    _set_session_cookie(response, settings_from(request), raw_token)
    return await _bootstrap_payload(session, user)


@studio_router.post("/auth/signin")
async def signin(
    body: AuthInput,
    response: Response,
    request: Request,
    session: AsyncSession = Depends(database_session),
) -> dict[str, object]:
    try:
        email = normalize_email(body.email)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Email or password is incorrect") from exc

    user = await session.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect")

    raw_token = await _create_studio_session(session, settings_from(request), user.id)
    _set_session_cookie(response, settings_from(request), raw_token)
    return await _bootstrap_payload(session, user)


@studio_router.post("/auth/signout", status_code=204)
async def signout(
    response: Response,
    request: Request,
    identity: StudioIdentity = Depends(require_studio_identity),
    session: AsyncSession = Depends(database_session),
) -> Response:
    await session.delete(identity.session)
    await session.commit()
    settings = settings_from(request)
    response.delete_cookie(
        settings.kuma_session_cookie_name,
        path="/",
        domain=settings.kuma_session_cookie_domain.strip() or None,
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@studio_router.get("/bootstrap")
async def bootstrap(
    identity: StudioIdentity = Depends(require_studio_identity),
    session: AsyncSession = Depends(database_session),
) -> dict[str, object]:
    return await _bootstrap_payload(session, identity.user)


@studio_router.put("/profile")
async def update_profile(
    body: ProfileInput,
    identity: StudioIdentity = Depends(require_studio_identity),
    session: AsyncSession = Depends(database_session),
) -> dict[str, object]:
    profile = await session.get(UserProfile, identity.user.id)
    values = {
        "full_name": body.full_name.strip(),
        "role": body.role.strip(),
        "primary_goal": body.primary_goal.strip() if body.primary_goal else None,
        "use_cases": body.use_cases,
        "technical_comfort": body.technical_comfort,
        "discovery_source": body.discovery_source,
        "response_style": body.response_style,
    }
    if profile is None:
        profile = UserProfile(user_id=identity.user.id, **values)
        session.add(profile)
    else:
        for field, value in values.items():
            setattr(profile, field, value)
        profile.updated_at = utcnow()
    await session.commit()
    return await _bootstrap_payload(session, identity.user)


@studio_router.post("/pairings/approve")
async def approve_pairing(
    body: PairingApprovalInput,
    request: Request,
    identity: StudioIdentity = Depends(require_studio_identity),
    session: AsyncSession = Depends(database_session),
) -> dict[str, object]:
    if await session.get(UserProfile, identity.user.id) is None:
        raise HTTPException(status_code=409, detail="Complete your profile before pairing a Watch")

    try:
        code = normalize_user_code(body.user_code)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    authorization = await session.scalar(
        select(DeviceAuthorization).where(DeviceAuthorization.user_code == code)
    )
    if authorization is None or _aware(authorization.expires_at) <= utcnow():
        raise HTTPException(status_code=404, detail="That pairing code has expired")
    if authorization.user_id and authorization.user_id != identity.user.id:
        raise HTTPException(status_code=409, detail="That pairing code is already in use")

    if authorization.device_id:
        device = await session.get(Device, authorization.device_id)
        if device is None:
            raise HTTPException(status_code=409, detail="The paired device is unavailable")
    else:
        access_token = new_device_token()
        device = Device(
            user_id=identity.user.id,
            name=authorization.requested_name,
            access_token_hash=token_hash(access_token),
        )
        session.add(device)
        await session.flush()
        authorization.user_id = identity.user.id
        authorization.device_id = device.id
        authorization.issued_token_encrypted = secret_box_from(request).encrypt(access_token)
        authorization.approved_at = utcnow()
        await session.commit()

    return {"device": _device_payload(device), "status": "approved"}


@studio_router.put("/providers/openai")
async def save_openai_key(
    body: ProviderKeyInput,
    request: Request,
    identity: StudioIdentity = Depends(require_studio_identity),
    session: AsyncSession = Depends(database_session),
) -> dict[str, object]:
    if await session.get(UserProfile, identity.user.id) is None:
        raise HTTPException(status_code=409, detail="Complete your profile before adding a provider")
    device_id = await session.scalar(
        select(Device.id).where(
            Device.user_id == identity.user.id,
            Device.revoked_at.is_(None),
        )
    )
    if device_id is None:
        raise HTTPException(status_code=409, detail="Pair a Watch before adding a provider")

    api_key = body.api_key.strip()
    if len(api_key) < 20 or any(character.isspace() for character in api_key):
        raise HTTPException(status_code=422, detail="Enter a valid OpenAI API key")

    provider = await session.scalar(
        select(ProviderSecret).where(
            ProviderSecret.user_id == identity.user.id,
            ProviderSecret.provider == "openai",
        )
    )
    encrypted_value = secret_box_from(request).encrypt(api_key)
    if provider is None:
        provider = ProviderSecret(
            user_id=identity.user.id,
            provider="openai",
            encrypted_value=encrypted_value,
            last_four=api_key[-4:],
        )
        session.add(provider)
    else:
        provider.encrypted_value = encrypted_value
        provider.last_four = api_key[-4:]
        provider.updated_at = utcnow()

    await session.commit()
    return await _bootstrap_payload(session, identity.user)


@device_router.post("/authorizations", status_code=201)
async def create_device_authorization(
    body: DeviceAuthorizationInput,
    request: Request,
    session: AsyncSession = Depends(database_session),
) -> dict[str, object]:
    code = ""
    for _ in range(8):
        candidate = new_user_code()
        if not await session.scalar(
            select(DeviceAuthorization.id).where(DeviceAuthorization.user_code == candidate)
        ):
            code = candidate
            break
    if not code:
        raise HTTPException(status_code=503, detail="Could not create a pairing code")

    device_code = new_device_code()
    expires_at = utcnow() + timedelta(minutes=settings_from(request).kuma_pairing_minutes)
    authorization = DeviceAuthorization(
        device_code_hash=token_hash(device_code),
        user_code=code,
        requested_name=body.device_name.strip(),
        expires_at=expires_at,
        interval_seconds=3,
    )
    session.add(authorization)
    await session.commit()
    return {
        "device_code": device_code,
        "user_code": display_user_code(code),
        "verification_uri": settings_from(request).kuma_studio_url,
        "expires_in": settings_from(request).kuma_pairing_minutes * 60,
        "interval": authorization.interval_seconds,
    }


@device_router.post("/token")
async def exchange_device_token(
    body: DeviceTokenInput,
    request: Request,
    session: AsyncSession = Depends(database_session),
) -> Response:
    authorization = await session.scalar(
        select(DeviceAuthorization).where(
            DeviceAuthorization.device_code_hash == token_hash(body.device_code)
        )
    )
    if authorization is None or _aware(authorization.expires_at) <= utcnow():
        raise HTTPException(status_code=410, detail="The pairing code has expired")
    if not authorization.issued_token_encrypted:
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"status": "pending", "interval": authorization.interval_seconds},
        )

    if authorization.first_redeemed_at is None:
        authorization.first_redeemed_at = utcnow()
        await session.commit()
    access_token = secret_box_from(request).decrypt(authorization.issued_token_encrypted)
    return JSONResponse(
        content={
            "access_token": access_token,
            "token_type": "Bearer",
            "device_id": authorization.device_id,
        }
    )


async def resolve_device_principal(
    factory: async_sessionmaker[AsyncSession],
    authorization: str | None,
    *,
    touch: bool = False,
) -> DevicePrincipal | None:
    raw_token = _bearer_token(authorization)
    if not raw_token or not raw_token.startswith("kuma_device_"):
        return None

    async with factory() as session:
        device = await session.scalar(
            select(Device).where(
                Device.access_token_hash == token_hash(raw_token),
                Device.revoked_at.is_(None),
            )
        )
        if device is None:
            return None
        if touch:
            device.last_seen_at = utcnow()
            await session.commit()
        return DevicePrincipal(user_id=device.user_id, device_id=device.id)


async def load_device_runtime(
    factory: async_sessionmaker[AsyncSession],
    secret_box: SecretBox,
    user_id: str,
) -> DeviceRuntime:
    async with factory() as session:
        profile = await session.get(UserProfile, user_id)
        provider = await session.scalar(
            select(ProviderSecret).where(
                ProviderSecret.user_id == user_id,
                ProviderSecret.provider == "openai",
            )
        )
        return DeviceRuntime(
            openai_api_key=(
                secret_box.decrypt(provider.encrypted_value) if provider is not None else None
            ),
            full_name=profile.full_name if profile else None,
            response_style=profile.response_style if profile else "brief",
        )
