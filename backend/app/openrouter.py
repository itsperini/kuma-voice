import base64
from collections.abc import Sequence

import httpx

from .config import Settings


class OpenRouterError(RuntimeError):
    pass


class OpenRouterClient:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(
            base_url=settings.openrouter_base_url.rstrip("/"),
            timeout=httpx.Timeout(90.0, connect=15.0),
        )

    @property
    def headers(self) -> dict[str, str]:
        if not self.settings.openrouter_api_key:
            raise OpenRouterError("OPENROUTER_API_KEY is not configured")
        return {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "HTTP-Referer": "https://kuma.voice.local",
            "X-Title": "Kuma Voice Prototype",
        }

    async def transcribe(
        self,
        audio: bytes,
        audio_format: str,
        language: str | None = None,
    ) -> str:
        payload: dict[str, object] = {
            "model": self.settings.openrouter_stt_model,
            "input_audio": {
                "data": base64.b64encode(audio).decode("ascii"),
                "format": audio_format,
            },
        }
        if language:
            payload["language"] = language

        response = await self._post("/audio/transcriptions", json=payload)
        data = response.json()
        text = data.get("text")
        if not isinstance(text, str) or not text.strip():
            raise OpenRouterError("OpenRouter returned an empty transcription")
        return text.strip()

    async def chat(self, messages: Sequence[dict[str, str]]) -> str:
        response = await self._post(
            "/chat/completions",
            json={
                "model": self.settings.openrouter_llm_model,
                "messages": list(messages),
                "temperature": 0.6,
                "max_tokens": 350,
            },
        )
        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise OpenRouterError("OpenRouter returned an invalid chat response") from exc

        if not isinstance(content, str) or not content.strip():
            raise OpenRouterError("OpenRouter returned an empty chat response")
        return content.strip()

    async def synthesize(self, text: str) -> bytes:
        response = await self._post(
            "/audio/speech",
            json={
                "model": self.settings.openrouter_tts_model,
                "input": text,
                "voice": self.settings.openrouter_tts_voice,
                "response_format": "mp3",
                "speed": 1.0,
            },
        )
        if not response.content:
            raise OpenRouterError("OpenRouter returned empty speech audio")
        return response.content

    async def _post(self, path: str, **kwargs: object) -> httpx.Response:
        try:
            response = await self._http.post(path, headers=self.headers, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            raise OpenRouterError(
                f"OpenRouter request failed with {exc.response.status_code}: {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise OpenRouterError(f"Could not reach OpenRouter: {exc}") from exc

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http.aclose()

