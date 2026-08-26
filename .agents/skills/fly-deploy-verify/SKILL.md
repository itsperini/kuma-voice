---
name: fly-deploy-verify
description: Deploy or verify the Kuma Voice FastAPI backend on Fly.io while protecting secrets and the private deployment identity. Use when the user explicitly requests a Fly deployment, live-server verification, or deployment troubleshooting.
---

# Fly Deploy Verify

Deploy only within the app and account the user placed in scope. Skill selection
does not itself authorize a deployment, secret rotation, scaling change, or
machine deletion.

## Preflight

1. Resolve the exact Fly app from user context or read-only CLI state. If more
   than one app is plausible, stop instead of guessing.
2. Inspect repository status, `fly.toml`, current machine health, and secret
   names/status. Do not print secret values.
3. Run backend tests and validate the Fly configuration. Confirm that the
   tracked `fly.toml` contains no personal app name or region and that the live
   app has `KUMA_API_TOKEN` before exposing provider-backed endpoints.
4. Warn that rotating the shared token requires rebuilding installed Watch apps
   with the matching ignored local configuration.

## Deploy

Use an explicit app selector, for example `fly deploy -a "$KUMA_FLY_APP"`, so a
local config change cannot target the wrong app. Monitor the rollout until the
machine reaches a healthy state. Do not detach unless the user asked for an
asynchronous deployment.

If the deployment fails, inspect status and logs without leaking environment
values. Do not remove secrets, change regions, scale machines, or destroy an
unhealthy machine as an improvised fix.

## Verify

After a healthy rollout:

- Confirm `/health` returns exactly `{"status":"ok"}` over HTTPS.
- Confirm an anonymous request to `/api/v1` is rejected with `401`.
- Confirm an authorized, low-impact request succeeds, loading the token from an
  existing protected source without echoing it or placing it in tracked files.
- Confirm Fly reports the expected machine healthy and `KUMA_API_TOKEN` as
  deployed.

Avoid creating persistent test data. If a verification request creates an
in-memory conversation, allow restart cleanup or delete it through the API when
safe.

Report the deployment result, health/authentication checks, and any Watch
rebuild required. Never add the live hostname, app name, region, machine ID, or
token to public repository files.
