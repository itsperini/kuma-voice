from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from app.config import get_settings

REDIRECT_PORT = 8765
REDIRECT_URI = f"http://127.0.0.1:{REDIRECT_PORT}/"
SCOPE = "https://www.googleapis.com/auth/calendar.events"


def main() -> None:
    settings = get_settings()
    if not settings.google_calendar_client_id or not settings.google_calendar_client_secret:
        raise SystemExit(
            "Set GOOGLE_CALENDAR_CLIENT_ID and GOOGLE_CALENDAR_CLIENT_SECRET in backend/.env first."
        )

    params = urlencode(
        {
            "client_id": settings.google_calendar_client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": SCOPE,
            "access_type": "offline",
            "prompt": "consent",
        }
    )
    authorize_url = f"https://accounts.google.com/o/oauth2/v2/auth?{params}"
    code_holder: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            query = parse_qs(urlparse(self.path).query)
            code = (query.get("code") or [""])[0]
            code_holder["code"] = code
            body = b"You can close this tab and return to the terminal."
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", REDIRECT_PORT), Handler)
    thread = Thread(target=server.handle_request, daemon=True)
    thread.start()

    print("Open this URL, choose your Google account, and allow calendar access:\n")
    print(authorize_url)
    print("\nWaiting for Google to redirect back...")
    thread.join(timeout=180)
    server.server_close()

    code = code_holder.get("code")
    if not code:
        raise SystemExit("Did not receive an OAuth code. Try the script again.")

    response = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": settings.google_calendar_client_id,
            "client_secret": settings.google_calendar_client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        },
        timeout=20,
    )
    response.raise_for_status()
    token = response.json().get("refresh_token")
    if not token:
        raise SystemExit(
            "Google did not return a refresh_token. Revoke the app at "
            "https://myaccount.google.com/permissions and run the script again."
        )

    env_path = Path(__file__).resolve().parents[1] / ".env"
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    wrote = False
    updated = []
    for line in lines:
        if line.startswith("GOOGLE_CALENDAR_REFRESH_TOKEN="):
            updated.append(f"GOOGLE_CALENDAR_REFRESH_TOKEN={token}")
            wrote = True
        else:
            updated.append(line)
    if not wrote:
        updated.append(f"GOOGLE_CALENDAR_REFRESH_TOKEN={token}")
    env_path.write_text("\n".join(updated) + "\n")
    print("\nSaved GOOGLE_CALENDAR_REFRESH_TOKEN to backend/.env")


if __name__ == "__main__":
    main()
