# Kuma Voice agent instructions

## Project

Kuma Voice is a self-hosted Apple Watch voice-assistant prototype. The watchOS
app streams audio to a FastAPI backend, which talks to configured model and tool
providers without putting provider credentials on the Watch.

- `watchos/` contains the watch-only SwiftUI app.
- `backend/` contains the FastAPI server, provider integrations, and tests.
- `assets/` contains public repository media.
- `.agents/skills/` contains reusable project workflows.

Keep the public project scrappy and understandable. Prefer a small, verified
change over adding infrastructure for hypothetical future needs.

## Security and privacy

- Never commit provider keys, OAuth credentials, API tokens, `.env` files, or
  `watchos/Local.xcconfig`.
- Keep checked-in defaults self-hosted and generic. Do not add a personal Fly
  hostname, app name, region, Apple development-team ID, or private endpoint.
- Internet-facing `/api/v1` HTTP and WebSocket endpoints must remain protected
  by `KUMA_API_TOKEN`. An empty token is acceptable only for local development.
- Keep `/health` public and minimal: it must reveal only `{"status":"ok"}`.
- Do not print secret values during diagnostics. Report names, status, or
  digests only.
- Keep Notion and Google Calendar credentials server-side and least-privilege.

## Backend contract

- Preserve the realtime protocol unless the Watch client and tests are updated
  in the same change. The Watch sends `start`, `audio`, and `commit`; the server
  sends `audio_delta`, `transcript_delta`, and `response_done`.
- Realtime audio is 24 kHz, mono, signed 16-bit PCM.
- Send the bearer token from both REST and WebSocket clients when configured.
- Conversations are intentionally in memory and may disappear on restart.
- Provider integrations must remain optional. Tests must use fakes and must not
  consume provider credits unless the user explicitly requests a live check.
- Avoid returning upstream response bodies when they may disclose sensitive
  configuration or provider data.

## Watch app

- Keep the app watch-only and usable on the small display.
- Put public defaults in `watchos/KumaVoice.xcconfig`; put deployment-specific
  values only in the ignored `watchos/Local.xcconfig`.
- Preserve microphone permission messaging, streaming playback, and the current
  tap/Double Tap interaction unless a requested product change requires more.
- Do not add provider credentials to the app bundle. `KUMA_API_TOKEN` is only a
  shared backend gate, not user authentication.

## Validation

Run checks proportional to the files changed. The normal commands are:

```sh
cd backend && uv run pytest
xcodebuild -project watchos/KumaVoice.xcodeproj -scheme KumaVoice \
  -sdk watchsimulator -configuration Debug CODE_SIGNING_ALLOWED=NO build
git diff --check
```

Backend-contract changes require backend tests. Watch source, plist, or Xcode
configuration changes require a Watch simulator build. Documentation-only
changes require link/path checks and `git diff --check`.

## External operations

Read-only inspection of GitHub and Fly.io is allowed when relevant. Deploying,
rotating secrets, rewriting history, deleting or recreating a repository, and
changing repository visibility require explicit user intent. Never make a
repository public as an inferred follow-up to “make it ready.”

Use the focused project skills when their descriptions match:

- [`release-readiness`](skills/release-readiness/SKILL.md)
- [`backend-contract`](skills/backend-contract/SKILL.md)
- [`fly-deploy-verify`](skills/fly-deploy-verify/SKILL.md)

## Definition of done

A change is done when the requested behavior is implemented, relevant checks
pass, tracked configuration contains no private deployment data, documentation
matches the behavior, and unrelated user changes remain intact. Report any
unrun check or external action still awaiting authorization.
