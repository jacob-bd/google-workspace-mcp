"""
Tests for Calendar tools.

Tests cover:
- Timestamp normalization
- Timezone fetching and caching
- Event retrieval
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from g_workspace_mcp.src.tools.calendar_tools import (
    _get_user_timezone,
    _normalize_timestamp,
    _user_timezone_cache,
    calendar_get_events,
    calendar_list,
)


class TestNormalizeTimestamp:
    """Tests for _normalize_timestamp function."""

    def test_already_has_z_suffix(self):
        """Timestamps with Z suffix should be returned as-is."""
        ts = "2025-12-15T00:00:00Z"
        assert _normalize_timestamp(ts) == ts

    def test_already_has_positive_offset(self):
        """Timestamps with positive offset should be returned as-is."""
        ts = "2025-12-15T00:00:00+05:00"
        assert _normalize_timestamp(ts) == ts

    def test_already_has_negative_offset(self):
        """Timestamps with negative offset should be returned as-is."""
        ts = "2025-12-15T21:00:00-05:00"
        assert _normalize_timestamp(ts) == ts

    def test_offset_without_colon(self):
        """Timestamps with offset without colon should be returned as-is."""
        ts = "2025-12-15T00:00:00+0530"
        assert _normalize_timestamp(ts) == ts

    def test_no_timezone_appends_z(self):
        """Timestamps without timezone info should get Z appended."""
        ts = "2025-12-15T00:00:00"
        assert _normalize_timestamp(ts) == "2025-12-15T00:00:00Z"

    def test_date_only_converts_to_datetime(self):
        """Date-only strings should be converted to datetime at midnight UTC."""
        ts = "2025-12-15"
        assert _normalize_timestamp(ts) == "2025-12-15T00:00:00Z"

    def test_empty_string_returns_empty(self):
        """Empty string should be returned as-is."""
        assert _normalize_timestamp("") == ""

    def test_none_handling(self):
        """None should be returned as falsy value."""
        # The function checks 'if not timestamp' which handles None
        result = _normalize_timestamp(None)
        assert not result

    def test_date_with_dashes_not_confused_with_offset(self):
        """Dates with dashes should not be confused with negative timezone offset."""
        # This was the original bug - the dash in 2025-12-15 was detected as timezone
        ts = "2025-12-15T18:00:00"
        result = _normalize_timestamp(ts)
        assert result == "2025-12-15T18:00:00Z"
        # Should NOT be returned as-is (which would happen if dash was detected as offset)


class TestGetUserTimezone:
    """Tests for _get_user_timezone function."""

    def setup_method(self):
        """Reset timezone cache before each test."""
        import g_workspace_mcp.src.tools.calendar_tools as calendar_module
        calendar_module._user_timezone_cache = None

    @patch("g_workspace_mcp.src.tools.calendar_tools.get_auth")
    def test_fetches_timezone_from_calendar(self, mock_get_auth):
        """Should fetch timezone from primary calendar."""
        mock_service = MagicMock()
        mock_service.calendars().get().execute.return_value = {
            "timeZone": "America/New_York"
        }
        mock_get_auth.return_value.get_service.return_value = mock_service

        result = _get_user_timezone()

        assert result == "America/New_York"
        mock_service.calendars().get.assert_called_with(calendarId="primary")

    @patch("g_workspace_mcp.src.tools.calendar_tools.get_auth")
    def test_caches_timezone(self, mock_get_auth):
        """Should cache timezone to avoid repeated API calls."""
        mock_service = MagicMock()
        mock_service.calendars().get().execute.return_value = {
            "timeZone": "America/Los_Angeles"
        }
        mock_get_auth.return_value.get_service.return_value = mock_service

        # First call should hit API
        result1 = _get_user_timezone()
        # Second call should use cache
        result2 = _get_user_timezone()

        assert result1 == "America/Los_Angeles"
        assert result2 == "America/Los_Angeles"
        # API should only be called once
        assert mock_service.calendars().get().execute.call_count == 1

    @patch("g_workspace_mcp.src.tools.calendar_tools.get_auth")
    def test_defaults_to_utc_on_error(self, mock_get_auth):
        """Should default to UTC when API call fails."""
        mock_get_auth.return_value.get_service.side_effect = Exception("API error")

        result = _get_user_timezone()

        assert result == "UTC"

    @patch("g_workspace_mcp.src.tools.calendar_tools.get_auth")
    def test_defaults_to_utc_when_missing(self, mock_get_auth):
        """Should default to UTC when timezone field is missing."""
        mock_service = MagicMock()
        mock_service.calendars().get().execute.return_value = {}
        mock_get_auth.return_value.get_service.return_value = mock_service

        result = _get_user_timezone()

        assert result == "UTC"


class TestCalendarGetEvents:
    """Tests for calendar_get_events function."""

    def setup_method(self):
        """Reset timezone cache before each test."""
        import g_workspace_mcp.src.tools.calendar_tools as calendar_module
        calendar_module._user_timezone_cache = None

    @patch("g_workspace_mcp.src.tools.calendar_tools._get_user_timezone")
    @patch("g_workspace_mcp.src.tools.calendar_tools.get_auth")
    def test_includes_user_timezone_in_response(self, mock_get_auth, mock_get_tz):
        """Response should include user's timezone."""
        mock_get_tz.return_value = "America/New_York"
        mock_service = MagicMock()
        mock_service.events().list().execute.return_value = {"items": []}
        mock_get_auth.return_value.get_service.return_value = mock_service

        result = calendar_get_events()

        assert result["status"] == "success"
        assert result["user_timezone"] == "America/New_York"

    @patch("g_workspace_mcp.src.tools.calendar_tools._get_user_timezone")
    @patch("g_workspace_mcp.src.tools.calendar_tools.get_auth")
    def test_normalizes_input_timestamps(self, mock_get_auth, mock_get_tz):
        """Should normalize input timestamps to RFC3339 format."""
        mock_get_tz.return_value = "UTC"
        mock_service = MagicMock()
        mock_service.events().list().execute.return_value = {"items": []}
        mock_get_auth.return_value.get_service.return_value = mock_service

        # Pass timestamps without timezone info
        result = calendar_get_events(
            time_min="2025-12-15T00:00:00",
            time_max="2025-12-16T00:00:00"
        )

        assert result["status"] == "success"
        # Timestamps should be normalized with Z suffix
        assert result["time_min"] == "2025-12-15T00:00:00Z"
        assert result["time_max"] == "2025-12-16T00:00:00Z"

    @patch("g_workspace_mcp.src.tools.calendar_tools._get_user_timezone")
    @patch("g_workspace_mcp.src.tools.calendar_tools.get_auth")
    def test_handles_date_only_input(self, mock_get_auth, mock_get_tz):
        """Should handle date-only input by converting to datetime."""
        mock_get_tz.return_value = "UTC"
        mock_service = MagicMock()
        mock_service.events().list().execute.return_value = {"items": []}
        mock_get_auth.return_value.get_service.return_value = mock_service

        result = calendar_get_events(
            time_min="2025-12-15",
            time_max="2025-12-16"
        )

        assert result["status"] == "success"
        assert result["time_min"] == "2025-12-15T00:00:00Z"
        assert result["time_max"] == "2025-12-16T00:00:00Z"

    @patch("g_workspace_mcp.src.tools.calendar_tools._get_user_timezone")
    @patch("g_workspace_mcp.src.tools.calendar_tools.get_auth")
    def test_preserves_timezone_offset_input(self, mock_get_auth, mock_get_tz):
        """Should preserve timestamps that already have timezone offsets."""
        mock_get_tz.return_value = "America/New_York"
        mock_service = MagicMock()
        mock_service.events().list().execute.return_value = {"items": []}
        mock_get_auth.return_value.get_service.return_value = mock_service

        result = calendar_get_events(
            time_min="2025-12-15T00:00:00-05:00",
            time_max="2025-12-16T00:00:00-05:00"
        )

        assert result["status"] == "success"
        assert result["time_min"] == "2025-12-15T00:00:00-05:00"
        assert result["time_max"] == "2025-12-16T00:00:00-05:00"

    @patch("g_workspace_mcp.src.tools.calendar_tools._get_user_timezone")
    @patch("g_workspace_mcp.src.tools.calendar_tools.get_auth")
    def test_returns_error_on_api_failure(self, mock_get_auth, mock_get_tz):
        """Should return error status when API call fails."""
        mock_get_tz.return_value = "UTC"
        mock_get_auth.return_value.get_service.side_effect = Exception("API error")

        result = calendar_get_events()

        assert result["status"] == "error"
        assert "error" in result
        assert "message" in result


class TestCalendarList:
    """Tests for calendar_list function."""

    @patch("g_workspace_mcp.src.tools.calendar_tools.get_auth")
    def test_returns_calendar_list(self, mock_get_auth):
        """Should return list of calendars."""
        mock_service = MagicMock()
        mock_service.calendarList().list().execute.return_value = {
            "items": [
                {
                    "id": "primary",
                    "summary": "My Calendar",
                    "primary": True,
                    "accessRole": "owner",
                }
            ]
        }
        mock_get_auth.return_value.get_service.return_value = mock_service

        result = calendar_list()

        assert result["status"] == "success"
        assert result["count"] == 1
        assert result["calendars"][0]["id"] == "primary"
        assert result["calendars"][0]["primary"] is True

    @patch("g_workspace_mcp.src.tools.calendar_tools.get_auth")
    def test_returns_error_on_api_failure(self, mock_get_auth):
        """Should return error status when API call fails."""
        mock_get_auth.return_value.get_service.side_effect = Exception("API error")

        result = calendar_list()

        assert result["status"] == "error"
        assert "error" in result
