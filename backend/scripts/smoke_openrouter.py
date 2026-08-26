import asyncio

from app.config import get_settings
from app.openrouter import OpenRouterClient


async def main() -> None:
    client = OpenRouterClient(get_settings())
    try:
        reply = await client.chat(
            [
                {"role": "system", "content": "Reply very briefly."},
                {"role": "user", "content": "Say Kuma ready."},
            ]
        )
        audio = await client.synthesize(reply)
        transcript = await client.transcribe(audio, "mp3", "en")
        print(
            {
                "reply": reply,
                "audio_bytes": len(audio),
                "transcript": transcript,
            }
        )
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())

