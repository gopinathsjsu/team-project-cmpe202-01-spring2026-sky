from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode


def _format_google_calendar_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.strftime("%Y%m%dT%H%M%SZ")


def build_google_calendar_url(
    *,
    title: str | None,
    start_time: datetime | Any,
    end_time: datetime | Any,
    description: str | None = None,
    location: str | None = None,
    location_address: str | None = None,
) -> str | None:
    if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
        return None

    if end_time <= start_time:
        return None

    event_location = ", ".join(
        part.strip()
        for part in (location, location_address)
        if isinstance(part, str) and part.strip()
    )

    params = {
        "action": "TEMPLATE",
        "text": title or "Event",
        "dates": (
            f"{_format_google_calendar_datetime(start_time)}"
            f"/{_format_google_calendar_datetime(end_time)}"
        ),
    }

    if description and description.strip():
        params["details"] = description.strip()

    if event_location:
        params["location"] = event_location

    return "https://calendar.google.com/calendar/render?" + urlencode(params)


def build_event_google_calendar_url(event: Any) -> str | None:
    return build_google_calendar_url(
        title=getattr(event, "title", None),
        start_time=getattr(event, "start_time", None),
        end_time=getattr(event, "end_time", None),
        description=getattr(event, "description", None),
        location=getattr(event, "location", None),
        location_address=getattr(event, "location_address", None),
    )
