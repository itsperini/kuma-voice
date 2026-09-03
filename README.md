# Kuma Voice

<p align="center">
  <img src="assets/watchos-header-banner.png" alt="Kuma Voice watchOS assistant" width="80%">
</p>

Kuma Voice is a watch-only voice assistant with a local-first Studio. FastAPI
authenticates the Watch and creates a short-lived OpenAI Realtime session; the
Watch then streams audio directly to OpenAI without receiving the user's
long-lived provider key. FastAPI still executes allowlisted tools and remains an
automatic streaming fallback. The Next.js Studio handles accounts, onboarding,
Watch pairing, and provider setup. Optional tools add web search, Notion notes,
and Google Calendar access.

This repository does not include a public backend or any credentials. Run your
own server and point the Watch app at it.

<p align="center">
  <a href="https://x.com/itsperini">
    <img src="https://img.shields.io/badge/%40itsperini-000000?style=for-the-badge&amp;logo=x&amp;logoColor=white" alt="@itsperini on X">
  </a>
</p>

## Project layout

- `watchos/KumaVoice.xcodeproj` — watch-only SwiftUI app
- `backend/app` — FastAPI server and provider integrations
- `backend/tests` — tests that use fakes and do not consume API credits
- `web` — landing page and authenticated Kuma Studio
- `compose.yaml` — local Postgres, MinIO, API, and web stack

## Requirements

- Xcode 16 or later and an Apple Watch simulator or device
- Docker Desktop for the complete local platform
- An OpenAI API key entered during Studio onboarding

Python 3.12 and [uv](https://docs.astral.sh/uv/) are only required when running
the backend outside Docker. OpenRouter powers the older REST fallback. Exa,
Notion, and Google Calendar are optional.

## Start the local platform

```sh
cp .env.example .env
docker compose up --build
```

Then open:

- [Kuma Voice](http://localhost:3001) — landing page
- [Kuma Studio signup](http://localhost:3001/studio/signup) — account and setup
- [FastAPI documentation](http://localhost:8000/docs) — backend API
- [MinIO console](http://localhost:9001) — local object storage

Postgres listens on port `5432`, MinIO's S3 endpoint on `9000`, and FastAPI on
`8000`. MinIO is provisioned for future conversation media but is not used by
the first onboarding flow yet. The Compose credentials are deliberately simple
local defaults; change them before sharing the environment.

The first-run flow is:

1. Create an account or sign in with email and password.
2. Add your name, role, technical comfort, use cases, discovery source, and
   preferred response length. You can optionally describe what you are most
   excited to solve. Studio saves these answers together as one complete profile.
3. Open Kuma on the Watch and enter its six-digit code in Studio.
4. Add an OpenAI API key. It is encrypted before it is written to Postgres and
   never enters the Watch app bundle.

Docker persists Postgres, MinIO data, and the locally generated encryption key
in named volumes. To run only the backend without Docker:

```sh
cd backend
cp .env.example .env
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The liveness check is at
[`http://127.0.0.1:8000/health`](http://127.0.0.1:8000/health), and local API
documentation is at [`http://127.0.0.1:8000/docs`](http://127.0.0.1:8000/docs).

## Run the Watch app

1. Open `watchos/KumaVoice.xcodeproj` in Xcode.
2. Select the `KumaVoice` target and choose your development team under
   Signing & Capabilities.
3. Start the local platform, select an Apple Watch simulator, and press Run.
4. Enter the code shown by the Watch at
   [`localhost:3001/studio`](http://localhost:3001/studio).
5. Tap the microphone button, or use Double Tap on supported hardware, to start
   and stop a turn.

The checked-in configuration uses `http://127.0.0.1:8000`. For a physical Watch
or hosted server, create a private local configuration:

```sh
cp watchos/Local.xcconfig.example watchos/Local.xcconfig
```

Edit `watchos/Local.xcconfig` with a backend URL reachable by the Watch. Leave
`KUMA_API_TOKEN` empty to use the Studio pairing flow. For the simulator this
can be your Mac's local address; a physical Watch needs a LAN address or HTTPS
host. This file is ignored by Git. Local HTTP is allowed for development;
remote deployments must use HTTPS.

## Protect an internet-facing backend

The Compose stack sets `KUMA_REQUIRE_DEVICE_AUTH=true`, so each paired Watch
receives its own revocable credential. For the older self-hosted mode,
`KUMA_API_TOKEN` can still be used as a shared backend gate. If neither device
authentication nor a shared token is enabled, the API accepts requests without
authentication and must remain local-only.

Authentication protects every `/api/v1` HTTP and WebSocket endpoint. `/health`
remains public but returns only `{"status":"ok"}`. Email/password Studio auth is
an intentionally small local implementation; add rate limiting, email
verification, password recovery, audit events, and managed key rotation before
exposing it as a production service.

For a hosted setup, provide an explicit `KUMA_ENCRYPTION_KEY` from a secret
manager rather than relying on the local key file, enable secure cookies, and
serve the three surfaces as:

- `kumavoice.com` — public Next.js pages
- `studio.kumavoice.com` — Next.js Studio
- `api.kumavoice.com` — FastAPI and realtime WebSocket API

Set `NEXT_PUBLIC_STUDIO_ORIGIN=https://studio.kumavoice.com` in Next.js,
`KUMA_API_INTERNAL_URL=https://api.kumavoice.com` on the Next.js server, and
`KUMA_STUDIO_URL=https://studio.kumavoice.com` in FastAPI. The Studio already
supports host-based routing for the dedicated subdomain.

Direct Realtime is enabled by default. Set `KUMA_DIRECT_REALTIME=false` to keep
all audio on the existing Watch → FastAPI → OpenAI WebSocket path. With the
default enabled, FastAPI mints a short-lived OpenAI client secret and returns it
only to an authenticated Watch. Tool calls still return to the authenticated
FastAPI API, where the fixed server-side allowlist is enforced. If the direct
session cannot be established, the Watch falls back to the existing proxy.

## MCP servers

Kuma acts as the MCP client and host. The Watch never receives connector
credentials and does not speak MCP: OpenAI emits a function call, the Watch
relays it to its authenticated FastAPI backend, and FastAPI calls the selected
MCP server for that user. The proxy realtime path uses the same executor.

This first version uses the MCP `2026-07-28` stateless core over Streamable
HTTP. It deliberately does not support local `stdio` servers or the deprecated
standalone SSE transport. Add a connection in Studio Settings, discover
its catalog, and explicitly enable individual tools. Newly discovered tools
remain disabled by default.

Connections may be unauthenticated, use an encrypted bearer token, or use OAuth
2.1 with authorization-server discovery, PKCE, resource indicators, issuer
validation, encrypted token storage, and refresh tokens. Studio prefers a
redirect sign-in: it uses a client ID metadata document when the server
advertises CIMD, otherwise it registers dynamically at the authorization
server's `registration_endpoint`. Enter a client ID only if that server does
not support either.

For hosted OAuth, set:

- `KUMA_MCP_OAUTH_CALLBACK_URL=https://api.kumavoice.com/studio/v1/mcp/oauth/callback`
- `KUMA_MCP_CLIENT_METADATA_URL=https://api.kumavoice.com/.well-known/oauth-client/kumavoice.json`

Both URLs must exactly match the public deployment. Production MCP and OAuth
URLs must use HTTPS and resolve to public addresses. Connector secrets and
tokens are encrypted with `KUMA_ENCRYPTION_KEY`.

## Deploy to Fly.io

The included `fly.toml` deliberately contains no app name or personal region.
Choose your own globally unique name:

```sh
KUMA_FLY_APP=your-unique-app-name
fly auth login
fly apps create "$KUMA_FLY_APP"
fly secrets set -a "$KUMA_FLY_APP" OPENAI_API_KEY=... KUMA_API_TOKEN=...
fly deploy -a "$KUMA_FLY_APP"
```

Set `KUMA_BACKEND_URL` in `watchos/Local.xcconfig` to your assigned HTTPS URL,
then rebuild the Watch app. Use `openssl rand -hex 32` to generate a suitable
token and keep it in a password manager.

## Optional integrations

Provider secrets belong only in `backend/.env` locally or in your host's secret
store. The full list and safe placeholders are in `backend/.env.example`.

### Web search

Set `EXA_API_KEY` to let the realtime assistant search the web.

### Notion

1. Create an internal integration at
   [notion.so/my-integrations](https://www.notion.so/my-integrations).
2. Share only the pages Kuma should access with that integration.
3. Set `NOTION_API_KEY` and, optionally, `NOTION_NOTES_PAGE_ID`.

### Google Calendar

1. Enable the Google Calendar API and create a Desktop OAuth client in the
   [Google Cloud Console](https://console.cloud.google.com/).
2. Set `GOOGLE_CALENDAR_CLIENT_ID` and `GOOGLE_CALENDAR_CLIENT_SECRET` locally.
3. Run `uv run python -m scripts.google_calendar_auth` from `backend` and save
   the resulting `GOOGLE_CALENDAR_REFRESH_TOKEN`.
4. Set `GOOGLE_CALENDAR_TIMEZONE` to an IANA zone such as `UTC`.

Use a dedicated test calendar and least-privilege Notion pages when evaluating
the prototype.

## Privacy notes

Microphone audio and conversation content are sent to the providers configured
on your backend. Web searches, notes, and calendar requests may also be sent to
their respective services. Tool arguments, relevant conversation context, and
tool results may be processed by each MCP server a user enables. Review those
providers' permissions, privacy terms, and retention settings before using
personal or sensitive data.

Never commit `backend/.env` or `watchos/Local.xcconfig`. If a credential is ever
exposed, rotate it rather than merely deleting it from Git.

## API endpoints

- `GET /health` — minimal liveness response
- `POST /studio/v1/auth/signup` — create a local Studio account
- `POST /studio/v1/auth/signin` — start an HTTP-only cookie session
- `GET /studio/v1/bootstrap` — load account state plus a complete profile or `null`
- `PUT /studio/v1/profile` — atomically create or replace all required onboarding answers
- `POST /studio/v1/pairings/approve` — bind a Watch code to the account
- `POST /studio/v1/providers/openai` — encrypt and store an OpenAI key
- `GET|POST /studio/v1/mcp/connections` — list or add remote MCP servers
- `POST /studio/v1/mcp/connections/{id}/oauth/start` — begin OAuth with PKCE
- `POST /studio/v1/mcp/connections/{id}/discover` — refresh a tool catalog
- `PATCH /studio/v1/mcp/connections/{id}/tools/{tool_id}` — allowlist a tool
- `POST /device/v1/authorizations` — request a Watch pairing code
- `POST /device/v1/token` — poll for the paired device credential
- `POST /api/v1/realtime/session` — mint a short-lived direct Realtime session
- `POST /api/v1/realtime/tools/{name}` — execute one allowlisted Realtime tool
- `WS /api/v1/realtime` — realtime PCM voice conversation
- `POST /api/v1/transcriptions` — audio file to text
- `POST /api/v1/responses` — messages to assistant text
- `POST /api/v1/speech` — text to MP3 audio
- `POST /api/v1/conversations` — start an in-memory conversation
- `POST /api/v1/conversations/{id}/turns` — run a complete voice turn
- `DELETE /api/v1/conversations/{id}` — end a conversation

Conversations are kept only in memory and disappear when the backend restarts.
Realtime audio is 24 kHz mono, 16-bit PCM.

## Tests

```sh
cd backend
uv run pytest
```

## License

[MIT](LICENSE)
