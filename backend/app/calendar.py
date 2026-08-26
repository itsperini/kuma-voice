import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from .config import Settings


class CalendarError(RuntimeError):
    pass


class GoogleCalendarClient:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=10.0))
        self._access_token = ""
        self._expires_at = 0.0

    async def upcoming(self, days: int = 1, max_events: int = 5) -> str:
        days = min(max(days, 1), 14)
        max_events = min(max(max_events, 1), 10)
        tz = self._timezone()
        now = datetime.now(tz)
        time_min = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        time_max = (
            (now + timedelta(days=days))
            .astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
        payload = await self._request(
            "GET",
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            params={
                "timeMin": time_min,
                "timeMax": time_max,
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": str(max_events),
            },
        )
        events = []
        for item in payload.get("items") or []:
            if not isinstance(item, dict):
                continue
            events.append(compact_event(item, tz))
        return json.dumps(
            {"timezone": str(tz), "events": events},
            separators=(",", ":"),
        )

    async def create_event(
        self,
        title: str,
        start: str,
        end: str = "",
        duration_minutes: int = 30,
    ) -> str:
        summary = title.strip()
        if not summary:
            raise CalendarError("calendar_create_event requires a title")
        tz = self._timezone()
        start_dt = parse_datetime(start, tz)
        if end.strip():
            end_dt = parse_datetime(end, tz)
        else:
            minutes = min(max(duration_minutes, 5), 240)
            end_dt = start_dt + timedelta(minutes=minutes)
        payload = await self._request(
            "POST",
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            json={
                "summary": summary,
                "start": {"dateTime": start_dt.isoformat(), "timeZone": str(tz)},
                "end": {"dateTime": end_dt.isoformat(), "timeZone": str(tz)},
            },
        )
        return json.dumps(
            {"ok": True, "event": compact_event(payload, tz)},
            separators=(",", ":"),
        )

    def _timezone(self) -> ZoneInfo:
        name = self.settings.google_calendar_timezone.strip() or "UTC"
        try:
            return ZoneInfo(name)
        except Exception as exc:
            raise CalendarError(f"Invalid GOOGLE_CALENDAR_TIMEZONE: {name}") from exc

    async def _access(self) -> str:
        if self._access_token and time.time() < self._expires_at - 60:
            return self._access_token
        if not self.settings.calendar_configured:
            raise CalendarError("Google Calendar is not configured on the Kuma Voice server.")
        try:
            response = await self._http.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self.settings.google_calendar_client_id,
                    "client_secret": self.settings.google_calendar_client_secret,
                    "refresh_token": self.settings.google_calendar_refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise CalendarError(
                f"Google token refresh failed with {exc.response.status_code}: {exc.response.text[:500]}"
            ) from exc
        except httpx.HTTPError as exc:
            raise CalendarError(f"Could not reach Google: {exc}") from exc
        data = response.json()
        token = data.get("access_token")
        if not isinstance(token, str) or not token:
            raise CalendarError("Google did not return an access token")
        self._access_token = token
        self._expires_at = time.time() + int(data.get("expires_in") or 3600)
        return token

    async def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        token = await self._access()
        headers = {"Authorization": f"Bearer {token}"}
        try:
            response = await self._http.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise CalendarError(
                f"Google Calendar request failed with {exc.response.status_code}: {exc.response.text[:500]}"
            ) from exc
        except httpx.HTTPError as exc:
            raise CalendarError(f"Could not reach Google Calendar: {exc}") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise CalendarError("Google Calendar returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise CalendarError("Google Calendar returned an unexpected payload")
        return payload

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http.aclose()


def compact_event(item: dict[str, Any], tz: ZoneInfo) -> dict[str, str]:
    start = item.get("start") if isinstance(item.get("start"), dict) else {}
    end = item.get("end") if isinstance(item.get("end"), dict) else {}
    return {
        "id": str(item.get("id") or ""),
        "title": str(item.get("summary") or "Busy"),
        "start": format_when(start, tz),
        "end": format_when(end, tz),
        "location": str(item.get("location") or ""),
    }


def format_when(value: dict[str, Any], tz: ZoneInfo) -> str:
    date = value.get("date")
    if isinstance(date, str) and date:
        return date
    raw = value.get("dateTime")
    if not isinstance(raw, str) or not raw:
        return ""
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(tz)
    except ValueError:
        return raw
    return parsed.strftime("%Y-%m-%d %H:%M")


def parse_datetime(value: str, tz: ZoneInfo) -> datetime:
    raw = value.strip()
    if not raw:
        raise CalendarError("A start time is required")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CalendarError(
            "Start/end must be ISO-8601, for example 2026-08-25T16:00"
        ) from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)
