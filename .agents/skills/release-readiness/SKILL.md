---
name: release-readiness
description: Audit and prepare Kuma Voice for a public or open-source release. Use for release-readiness, repository privacy, credential exposure, public documentation, or Git-history cleanup; do not use for ordinary feature work.
---

# Release Readiness

Produce a public-safe snapshot without silently publishing it.

## Audit

1. Read the root and canonical agent guidance, then inspect `git status`, the
   reachable history, tracked files, ignored configuration, and remote metadata.
   Preserve unrelated local changes.
2. Search tracked content and reachable commits for credentials and personal
   deployment identifiers. Avoid commands that print a discovered secret;
   report the affected path and credential type, then rotate the credential.
3. Confirm that tracked Watch settings use local/generic defaults and that
   `backend/.env`, `watchos/Local.xcconfig`, signing-team IDs, personal Fly app
   details, and live tokens are absent from the snapshot.
4. Review public surfaces: README, assets, example configuration, license,
   security policy, commit author email, repository description, and topics.

## Security invariants

- `/health` returns only `{"status":"ok"}`.
- Every `/api/v1` HTTP and WebSocket endpoint requires the shared token when
  `KUMA_API_TOKEN` is configured.
- The README clearly says the project is self-hosted, remote deployments require
  HTTPS and a token, and provider data leaves the user's backend.
- Examples use placeholders and never a real hostname, account, region, or ID.

## Verify

Run backend tests, a code-signing-disabled Watch simulator build, and
`git diff --check`. Verify README image paths and ensure `assets/` contains only
intentional public media. Re-run tracked secret and deployment-identifier scans
against the final snapshot.

If a live deployment is in scope, use the `fly-deploy-verify` skill. Otherwise
do not deploy merely because the repository is being prepared.

## History and visibility

Do not amend, force-push, delete/recreate a repository, or change visibility
without explicit user intent. When a secret was committed, rotating it is the
first requirement; rewriting history alone does not revoke it. After an
authorized history rewrite, verify the remote branch and confirm that unwanted
objects are no longer accessible when strict purging was requested.

Finish by stating whether the repository is still private, which checks passed,
and any manual step that must occur before publication.
