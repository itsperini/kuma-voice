# Security

Kuma Voice is a self-hosted prototype, not a hosted multi-user service.

## Reporting a vulnerability

Please use the repository's private security-advisory feature to report a
vulnerability. Do not include credentials, access tokens, or private audio in a
public issue.

## Deployment guidance

- Never commit `backend/.env` or `watchos/Local.xcconfig`.
- Set `KUMA_API_TOKEN` whenever the backend is reachable from the internet.
- Use HTTPS outside local development.
- Treat the Watch token as a shared secret, not as full user authentication.
- Use separate, least-privilege Notion and Google credentials for this app.
- Rotate provider credentials immediately if they are ever exposed.
