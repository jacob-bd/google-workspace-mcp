"""
Google Calendar MCP Tools.

Provides:
- calendar_list: List all calendars
- calendar_get_events: Get events in date range
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from g_workspace_mcp.src.auth.google_oauth import get_auth
from g_workspace_mcp.utils.pylogger import get_python_logger

logger = get_python_logger()


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
    """
    try:
        service = get_auth().get_service("calendar", "v3")

        # Set default time range
        now = datetime.utcnow()
        if time_min is None:
            time_min = now.isoformat() + "Z"
        if time_max is None:
            time_max = (now + timedelta(days=7)).isoformat() + "Z"

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
