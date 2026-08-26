---
name: backend-contract
description: Modify Kuma Voice backend routes, authentication, realtime WebSockets, audio handling, conversations, or provider tools without breaking the Watch client. Use for backend contract changes; do not use for unrelated Python cleanup.
---

# Backend Contract

Treat the Watch and backend as one versioned contract even though they live in
the same repository.

## Before changing code

Trace the affected request or event through the FastAPI route, schema, provider
client, Watch client, and existing tests. Decide whether the change is backward
compatible. If it is not, update both ends in the same change and document the
transition.

## Preserve these boundaries

- `/health` is unauthenticated and returns only `{"status":"ok"}`.
- When `KUMA_API_TOKEN` is non-empty, all `/api/v1` REST and WebSocket traffic
  requires `Authorization: Bearer <token>`. Compare tokens safely and never log
  them.
- The Watch sends realtime `start`, `audio`, and `commit` events. The backend
  returns `audio_delta`, `transcript_delta`, and `response_done`.
- Audio crossing the realtime boundary is 24 kHz, mono, signed 16-bit PCM.
- REST conversations remain in memory unless persistence is explicitly in
  scope.
- OpenAI, OpenRouter, Exa, Notion, and Google Calendar credentials stay on the
  server and their integrations remain optional.

Validate sizes and user-controlled fields at the boundary. Map provider errors
to concise client-safe failures; do not pass through credentials, full upstream
bodies, or private configuration.

## Tests

Add or update tests for success, malformed input, authentication, and the event
sequence affected by the change. Use fake clients and deterministic fixtures;
do not call paid or personal services in the test suite.

Run:

```sh
cd backend && uv run pytest
```

If a schema, route, auth header, WebSocket event, or audio assumption changes on
the Watch side, also run the Watch simulator build from the canonical agent
guidance. Finish with `git diff --check` and summarize the client-visible
contract change.
