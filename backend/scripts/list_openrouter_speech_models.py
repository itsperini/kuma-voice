import httpx

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    response = httpx.get(
        f"{settings.openrouter_base_url.rstrip('/')}/models",
        params={"output_modalities": "speech"},
        headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
        timeout=30,
    )
    response.raise_for_status()
    for model in response.json().get("data", []):
        print(model.get("id"))


if __name__ == "__main__":
    main()

