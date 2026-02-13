"""
Tests for Google Sheets MCP tools.

Tests cover:
- Error handling when auth fails before service is assigned
- Successful read with row limiting
- Range notation handling
"""

from unittest.mock import MagicMock, patch

from g_workspace_mcp.src.tools.sheets_tools import sheets_read


class TestSheetsReadErrorHandling:
    """Tests for sheets_read error recovery."""

    @patch("g_workspace_mcp.src.tools.sheets_tools.get_auth")
    def test_auth_failure_does_not_raise_name_error(self, mock_get_auth):
        """When auth fails, error handler should not crash with NameError on 'service'."""
        mock_get_auth.return_value.get_service.side_effect = ValueError(
            "Google authentication not configured"
        )

        result = sheets_read("fake-spreadsheet-id")

        assert result["status"] == "error"
        assert "authentication" in result["error"].lower()
        assert result["available_sheets"] == []

    @patch("g_workspace_mcp.src.tools.sheets_tools.get_auth")
    def test_api_error_shows_available_sheets(self, mock_get_auth):
        """When read fails but service exists, error should include available sheet names."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        # First call to spreadsheets().get() succeeds (metadata)
        # but values().get() fails
        mock_spreadsheet_get = MagicMock()
        mock_values_get = MagicMock()

        # Set up the spreadsheet metadata chain
        mock_service.spreadsheets.return_value.get.return_value.execute.side_effect = [
            # First call: initial metadata fetch in try block
            {"properties": {"title": "Test Sheet"}, "sheets": [{"properties": {"title": "Sheet1"}}]},
            # Second call: metadata fetch in except block for error message
            {"sheets": [{"properties": {"title": "Sheet1"}}, {"properties": {"title": "Data"}}]},
        ]

        # Make values().get().execute() raise an error
        mock_service.spreadsheets.return_value.values.return_value.get.return_value.execute.side_effect = Exception(
            "Unable to parse range"
        )

        result = sheets_read("fake-id", range_notation="BadRange!A1:Z1000")

        assert result["status"] == "error"
        assert "Sheet1" in result["available_sheets"]
        assert "Data" in result["available_sheets"]


class TestSheetsReadSuccess:
    """Tests for successful sheets_read operations."""

    @patch("g_workspace_mcp.src.tools.sheets_tools.get_auth")
    def test_row_limit_truncates_results(self, mock_get_auth):
        """Should truncate rows when result exceeds row_limit."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        mock_service.spreadsheets.return_value.get.return_value.execute.return_value = {
            "properties": {"title": "Big Sheet"},
            "sheets": [{"properties": {"title": "Sheet1"}}],
        }

        # Return 150 rows
        mock_service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
            "values": [["row"] for _ in range(150)],
            "range": "Sheet1!A1:Z150",
            "majorDimension": "ROWS",
        }

        result = sheets_read("fake-id", row_limit=50)

        assert result["status"] == "success"
        assert result["total_rows"] == 150
        assert result["returned_rows"] == 50
        assert result["is_truncated"] is True
        assert len(result["values"]) == 50

    @patch("g_workspace_mcp.src.tools.sheets_tools.get_auth")
    def test_default_range_uses_first_sheet(self, mock_get_auth):
        """When no range specified, should use first sheet name."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        mock_service.spreadsheets.return_value.get.return_value.execute.return_value = {
            "properties": {"title": "My Spreadsheet"},
            "sheets": [{"properties": {"title": "Custom Name"}}],
        }

        mock_service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
            "values": [["a", "b"], ["c", "d"]],
            "range": "'Custom Name'!A1:Z1000",
            "majorDimension": "ROWS",
        }

        result = sheets_read("fake-id")

        assert result["status"] == "success"
        # Verify the range was constructed with the actual sheet name
        call_kwargs = mock_service.spreadsheets.return_value.values.return_value.get.call_args
        assert "Custom Name" in call_kwargs.kwargs.get("range", call_kwargs[1].get("range", ""))
