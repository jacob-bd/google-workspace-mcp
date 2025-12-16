"""
Google Calendar MCP Tools.

Provides:
- calendar_list: List all calendars
- calendar_get_events: Get events in date range
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # Python < 3.9

from g_workspace_mcp.src.auth.google_oauth import get_auth
from g_workspace_mcp.utils.pylogger import get_python_logger

logger = get_python_logger()

# Cache for user's timezone
_user_timezone_cache: Optional[str] = None


def _get_user_timezone() -> str:
    """
    Fetch user's timezone from their primary calendar settings.
    Caches the result to avoid repeated API calls.

    Returns:
        Timezone string (e.g., 'America/New_York') or 'UTC' as fallback
    """
    global _user_timezone_cache

    if _user_timezone_cache is not None:
        return _user_timezone_cache

    try:
        service = get_auth().get_service("calendar", "v3")
        calendar = service.calendars().get(calendarId="primary").execute()
        _user_timezone_cache = calendar.get("timeZone", "UTC")
        logger.info(f"Fetched user timezone: {_user_timezone_cache}")
        return _user_timezone_cache
    except Exception as e:
        logger.warning(f"Failed to fetch user timezone, defaulting to UTC: {e}")
        return "UTC"


def _normalize_timestamp(timestamp: str, user_tz: str = "UTC") -> str:
    """
    Normalize a timestamp to RFC3339 format required by Google Calendar API.

    Handles various input formats:
    - ISO format with Z suffix: 2025-12-15T00:00:00Z (returned as-is)
    - ISO format with offset: 2025-12-15T00:00:00-05:00 (returned as-is)
    - ISO format without timezone: 2025-12-15T00:00:00 (interpreted in user's timezone, converted to UTC)
    - Date only: 2025-12-15 (converts to start of day in user's timezone, converted to UTC)

    Args:
        timestamp: Input timestamp string
        user_tz: User's timezone string (e.g., 'America/Toronto') for interpreting
                 timestamps without timezone info

    Returns:
        RFC3339 formatted timestamp string in UTC
    """
    if not timestamp:
        return timestamp

    # Already has Z suffix (UTC)
    if timestamp.endswith("Z"):
        return timestamp

    # Check for timezone offset pattern like +05:00, -05:00, +0530, -0530
    # Must check this BEFORE checking for dashes in the date portion
    offset_pattern = r'[+-]\d{2}:?\d{2}$'
    if re.search(offset_pattern, timestamp):
        return timestamp

    # Get the user's timezone object
    try:
        tz = ZoneInfo(user_tz)
    except Exception:
        tz = timezone.utc

    # If it's just a date (YYYY-MM-DD), convert to datetime at midnight in user's timezone
    date_only_pattern = r'^\d{4}-\d{2}-\d{2}$'
    if re.match(date_only_pattern, timestamp):
        # Parse as date, create datetime at midnight in user's timezone
        dt = datetime.strptime(timestamp, "%Y-%m-%d")
        dt_local = dt.replace(tzinfo=tz)
        dt_utc = dt_local.astimezone(timezone.utc)
        return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    # No timezone info - interpret in user's timezone and convert to UTC
    # Try common datetime formats
    for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"]:
        try:
            dt = datetime.strptime(timestamp, fmt)
            dt_local = dt.replace(tzinfo=tz)
            dt_utc = dt_local.astimezone(timezone.utc)
            return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue

    # Fallback: just append Z (shouldn't reach here for valid timestamps)
    return f"{timestamp}Z"


def calendar_list() -> Dict[str, Any]:
    """
    List all calendars accessible to the user.

    TOOL_NAME=calendar_list
    DISPLAY_NAME=Calendar List
    USECASE=List all accessible calendars
    INPUT_DESCRIPTION=None
    OUTPUT_DESCRIPTION=List of calendars with id, summary, description, primary status

    Returns:
        Dictionary with status and list of calendars
    """
    try:
        service = get_auth().get_service("calendar", "v3")

        results = service.calendarList().list().execute()
        calendars = results.get("items", [])

        calendar_list = []
        for cal in calendars:
            calendar_list.append(
                {
                    "id": cal["id"],
                    "summary": cal.get("summary", "Untitled"),
                    "description": cal.get("description", ""),
                    "primary": cal.get("primary", False),
                    "accessRole": cal.get("accessRole", ""),
                    "backgroundColor": cal.get("backgroundColor", ""),
                }
            )

        logger.info(f"Listed {len(calendar_list)} calendars")

        return {
            "status": "success",
            "count": len(calendar_list),
            "calendars": calendar_list,
        }

    except Exception as e:
        logger.error(f"Calendar list failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "message": "Failed to list calendars",
        }


def calendar_get_events(
    calendar_id: str = "primary",
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
    max_results: int = 25,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get events from a calendar within a date range.

    TOOL_NAME=calendar_get_events
    DISPLAY_NAME=Calendar Get Events
    USECASE=Get calendar events in a date range
    INPUT_DESCRIPTION=calendar_id, time_min (ISO), time_max (ISO), max_results, query (optional)
    OUTPUT_DESCRIPTION=List of events with id, summary, start, end, location, attendees

    Args:
        calendar_id: Calendar ID (default: "primary" for user's primary calendar)
        time_min: Start of range in ISO format (default: now)
        time_max: End of range in ISO format (default: 7 days from now)
        max_results: Maximum events to return (default: 25, max: 250)
        query: Optional text search query

    Returns:
        Dictionary with status and list of events

    Note:
        The response includes the user's calendar timezone. When querying for
        "today" or "tonight", callers should account for the user's timezone
        to ensure correct results.
    """
    try:
        service = get_auth().get_service("calendar", "v3")

        # Fetch user's timezone - used for interpreting timestamps without timezone info
        user_timezone = _get_user_timezone()

        # Set default time range using UTC
        now = datetime.now(timezone.utc)
        if time_min is None:
            time_min = now.isoformat().replace("+00:00", "Z")
        else:
            time_min = _normalize_timestamp(time_min, user_timezone)

        if time_max is None:
            time_max = (now + timedelta(days=7)).isoformat().replace("+00:00", "Z")
        else:
            time_max = _normalize_timestamp(time_max, user_timezone)

        # Build request
        request_params = {
            "calendarId": calendar_id,
            "timeMin": time_min,
            "timeMax": time_max,
            "maxResults": min(max_results, 250),
            "singleEvents": True,
            "orderBy": "startTime",
        }

        if query:
            request_params["q"] = query

        results = service.events().list(**request_params).execute()
        events = results.get("items", [])

        event_list = []
        for event in events:
            start = event.get("start", {})
            end = event.get("end", {})

            event_list.append(
                {
                    "id": event["id"],
                    "summary": event.get("summary", "(No Title)"),
                    "description": event.get("description", ""),
                    "start": start.get("dateTime", start.get("date", "")),
                    "end": end.get("dateTime", end.get("date", "")),
                    "location": event.get("location", ""),
                    "status": event.get("status", ""),
                    "htmlLink": event.get("htmlLink", ""),
                    "attendees": [
                        {
                            "email": a.get("email", ""),
                            "responseStatus": a.get("responseStatus", ""),
                        }
                        for a in event.get("attendees", [])
                    ],
                }
            )

        logger.info(f"Retrieved {len(event_list)} events from calendar: {calendar_id}")

        return {
            "status": "success",
            "calendar_id": calendar_id,
            "user_timezone": user_timezone,
            "time_min": time_min,
            "time_max": time_max,
            "count": len(event_list),
            "events": event_list,
        }

    except Exception as e:
        logger.error(f"Calendar get events failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "message": "Failed to get calendar events",
        }
