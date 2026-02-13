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
    def test_default_range_uses_full_sheet_not_a1_z1000(self, mock_get_auth):
        """When no range specified, should use just the sheet name (no A1:Z1000 limit)."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        mock_service.spreadsheets.return_value.get.return_value.execute.return_value = {
            "properties": {"title": "My Spreadsheet"},
            "sheets": [{"properties": {"title": "Custom Name"}}],
        }

        mock_service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
            "values": [["a", "b"], ["c", "d"]],
            "range": "'Custom Name'",
            "majorDimension": "ROWS",
        }

        result = sheets_read("fake-id")

        assert result["status"] == "success"
        # Verify the range is just the sheet name, not A1:Z1000
        call_kwargs = mock_service.spreadsheets.return_value.values.return_value.get.call_args
        used_range = call_kwargs.kwargs.get("range", call_kwargs[1].get("range", ""))
        assert "Custom Name" in used_range
        assert "A1:Z1000" not in used_range

    @patch("g_workspace_mcp.src.tools.sheets_tools.get_auth")
    def test_sheet_name_only_does_not_append_cell_range(self, mock_get_auth):
        """When only sheet name given (no !), should not append A1:Z1000."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        mock_service.spreadsheets.return_value.get.return_value.execute.return_value = {
            "properties": {"title": "Test"},
            "sheets": [{"properties": {"title": "Data"}}],
        }

        mock_service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
            "values": [["x"]],
            "range": "Data",
            "majorDimension": "ROWS",
        }

        result = sheets_read("fake-id", range_notation="Data")

        assert result["status"] == "success"
        call_kwargs = mock_service.spreadsheets.return_value.values.return_value.get.call_args
        used_range = call_kwargs.kwargs.get("range", call_kwargs[1].get("range", ""))
        assert used_range == "Data"
        assert "A1:Z1000" not in used_range

    @patch("g_workspace_mcp.src.tools.sheets_tools.get_auth")
    def test_explicit_range_passed_through_unchanged(self, mock_get_auth):
        """When explicit A1 notation with ! is given, it should be used as-is."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        mock_service.spreadsheets.return_value.get.return_value.execute.return_value = {
            "properties": {"title": "Test"},
            "sheets": [{"properties": {"title": "Sheet1"}}],
        }

        mock_service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
            "values": [["a"]],
            "range": "Sheet1!A1:ZZ5000",
            "majorDimension": "ROWS",
        }

        result = sheets_read("fake-id", range_notation="Sheet1!A1:ZZ5000")

        assert result["status"] == "success"
        call_kwargs = mock_service.spreadsheets.return_value.values.return_value.get.call_args
        used_range = call_kwargs.kwargs.get("range", call_kwargs[1].get("range", ""))
        assert used_range == "Sheet1!A1:ZZ5000"
