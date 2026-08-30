import hashlib
import os
import re
import secrets
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from pwdlib import PasswordHash

from .config import Settings
from .database import resolve_backend_path


PASSWORD_HASH = PasswordHash.recommended()
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if len(email) > 320 or not EMAIL_PATTERN.fullmatch(email):
        raise ValueError("Enter a valid email address")
    return email


def hash_password(value: str) -> str:
    if not 8 <= len(value) <= 128:
        raise ValueError("Password must be between 8 and 128 characters")
    return PASSWORD_HASH.hash(value)


def verify_password(value: str, hashed: str) -> bool:
    return PASSWORD_HASH.verify(value, hashed)


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def new_session_token() -> str:
    return f"kuma_session_{secrets.token_urlsafe(32)}"


def new_device_token() -> str:
    return f"kuma_device_{secrets.token_urlsafe(32)}"


def new_device_code() -> str:
    return secrets.token_urlsafe(32)


def new_user_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def normalize_user_code(value: str) -> str:
    code = "".join(character for character in value if character.isdigit())
    if len(code) != 6:
        raise ValueError("Enter the six-digit code shown on your Watch")
    return code


def display_user_code(value: str) -> str:
    return f"{value[:3]} {value[3:]}"


class SecretBox:
    def __init__(self, fernet: Fernet) -> None:
        self._fernet = fernet

    @classmethod
    def from_settings(cls, settings: Settings) -> "SecretBox":
        configured = settings.kuma_encryption_key.strip()
        if configured:
            return cls(Fernet(configured.encode("ascii")))

        if settings.kuma_environment.lower() != "local":
            raise RuntimeError("KUMA_ENCRYPTION_KEY is required outside local mode")

        key_path = resolve_backend_path(settings.kuma_encryption_key_file)
        key_path.parent.mkdir(parents=True, exist_ok=True)
        if key_path.exists():
            key = key_path.read_bytes().strip()
        else:
            key = Fernet.generate_key()
            file_descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(file_descriptor, "wb") as key_file:
                key_file.write(key + b"\n")
        return cls(Fernet(key))

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise RuntimeError("The stored credential could not be decrypted") from exc
