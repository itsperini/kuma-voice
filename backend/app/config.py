from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    kuma_environment: str = "local"
    database_url: str = "sqlite+aiosqlite:///./.kuma/kuma.db"
    kuma_encryption_key: str = ""
    kuma_encryption_key_file: str = ".kuma/encryption.key"
    kuma_require_device_auth: bool = False
    kuma_session_cookie_name: str = "kuma_session"
    kuma_session_cookie_domain: str = ""
    kuma_session_cookie_secure: bool = False
    kuma_session_days: int = 30
    kuma_pairing_minutes: int = 10
    kuma_studio_url: str = "http://localhost:3001/studio"
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_stt_model: str = "openai/whisper-large-v3"
    openrouter_llm_model: str = "openai/gpt-4o-mini"
    openrouter_tts_model: str = "microsoft/mai-voice-2"
    openrouter_tts_voice: str = "en-US-Harper:MAI-Voice-2"
    openai_api_key: str = ""
    openai_realtime_url: str = "wss://api.openai.com/v1/realtime"
    openai_realtime_model: str = "gpt-realtime-2.1-mini"
    openai_realtime_voice: str = "marin"
    exa_api_key: str = ""
    exact_api_key: str = ""
    notion_api_key: str = ""
    notion_notes_page_id: str = ""
    google_calendar_client_id: str = ""
    google_calendar_client_secret: str = ""
    google_calendar_refresh_token: str = ""
    google_calendar_timezone: str = "UTC"
    kuma_api_token: str = ""
    kuma_system_prompt: str = (
        "You are Kuma Voice, a concise, warm voice assistant. "
        "Keep answers brief and easy to understand when spoken aloud."
    )
    kuma_max_audio_bytes: int = 10 * 1024 * 1024

    @property
    def web_search_api_key(self) -> str:
        return (self.exa_api_key or self.exact_api_key).strip()

    @property
    def calendar_configured(self) -> bool:
        return bool(
            self.google_calendar_client_id.strip()
            and self.google_calendar_client_secret.strip()
            and self.google_calendar_refresh_token.strip()
        )

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
