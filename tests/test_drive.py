"""
Tests for Drive tools.

Tests cover:
- Query normalization for Drive API syntax
"""

from unittest.mock import MagicMock, patch

from g_workspace_mcp.src.tools.drive_tools import _normalize_drive_query


class TestNormalizeDriveQuery:
    """Tests for _normalize_drive_query function."""

    def test_plain_text_query_gets_wrapped(self):
        """Plain text queries should be wrapped in fullText contains."""
        query = "Better AI role for prompts"
        result = _normalize_drive_query(query)
        assert result == 'fullText contains "Better AI role for prompts"'

    def test_query_with_contains_operator_unchanged(self):
        """Queries with 'contains' operator should not be modified."""
        query = 'name contains "Better AI role"'
        result = _normalize_drive_query(query)
        assert result == query

    def test_query_with_equals_operator_unchanged(self):
        """Queries with '=' operator should not be modified."""
        query = "mimeType = 'application/vnd.google-apps.document'"
        result = _normalize_drive_query(query)
        assert result == query

    def test_query_with_in_operator_unchanged(self):
        """Queries with 'in' operator should not be modified."""
        query = "'root' in parents"
        result = _normalize_drive_query(query)
        assert result == query

    def test_query_with_and_operator_unchanged(self):
        """Queries with 'and' operator should not be modified."""
        query = "name contains 'test' and trashed = false"
        result = _normalize_drive_query(query)
        assert result == query

    def test_query_with_or_operator_unchanged(self):
        """Queries with 'or' operator should not be modified."""
        query = "name contains 'test' or name contains 'example'"
        result = _normalize_drive_query(query)
        assert result == query

    def test_query_with_not_operator_unchanged(self):
        """Queries with 'not' operator should not be modified."""
        query = "not trashed = true"
        result = _normalize_drive_query(query)
        assert result == query

    def test_empty_string_returns_empty(self):
        """Empty string should be returned as-is."""
        assert _normalize_drive_query("") == ""

    def test_whitespace_only_returns_unchanged(self):
        """Whitespace-only string should be returned as-is."""
        assert _normalize_drive_query("   ") == "   "

    def test_query_with_quotes_gets_escaped(self):
        """Quotes in plain text queries should be escaped."""
        query = 'document with "quotes"'
        result = _normalize_drive_query(query)
        assert result == 'fullText contains "document with \\"quotes\\""'

    def test_single_word_query(self):
        """Single word queries should be wrapped."""
        query = "README"
        result = _normalize_drive_query(query)
        assert result == 'fullText contains "README"'

    def test_case_insensitive_operator_detection(self):
        """Operator detection should be case-insensitive."""
        query = "name CONTAINS 'test'"
        result = _normalize_drive_query(query)
        assert result == query


class TestDriveListPagination:
    """Tests for drive_list pagination support."""

    @patch("g_workspace_mcp.src.tools.drive_tools.get_auth")
    def test_single_page_returns_all_files(self, mock_get_auth):
        """Should return files from a single page when no nextPageToken."""
        from g_workspace_mcp.src.tools.drive_tools import drive_list

        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        mock_service.files.return_value.list.return_value.execute.return_value = {
            "files": [{"id": "f1", "name": "file1"}, {"id": "f2", "name": "file2"}],
        }

        result = drive_list("root", max_results=25)

        assert result["status"] == "success"
        assert result["count"] == 2

    @patch("g_workspace_mcp.src.tools.drive_tools.get_auth")
    def test_multiple_pages_fetched(self, mock_get_auth):
        """Should follow nextPageToken to get all pages up to max_results."""
        from g_workspace_mcp.src.tools.drive_tools import drive_list

        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        # First page returns 2 files + nextPageToken
        # Second page returns 1 file + no token
        mock_service.files.return_value.list.return_value.execute.side_effect = [
            {
                "files": [{"id": "f1", "name": "file1"}, {"id": "f2", "name": "file2"}],
                "nextPageToken": "token123",
            },
            {
                "files": [{"id": "f3", "name": "file3"}],
            },
        ]

        result = drive_list("root", max_results=200)

        assert result["status"] == "success"
        assert result["count"] == 3
        # Should have made 2 API calls
        assert mock_service.files.return_value.list.return_value.execute.call_count == 2

    @patch("g_workspace_mcp.src.tools.drive_tools.get_auth")
    def test_stops_at_max_results(self, mock_get_auth):
        """Should stop fetching pages when max_results is reached."""
        from g_workspace_mcp.src.tools.drive_tools import drive_list

        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        # First page returns 3 files, which meets max_results=3
        mock_service.files.return_value.list.return_value.execute.return_value = {
            "files": [{"id": f"f{i}", "name": f"file{i}"} for i in range(3)],
            "nextPageToken": "more_data",
        }

        result = drive_list("root", max_results=3)

        assert result["status"] == "success"
        assert result["count"] == 3
        # Should only make 1 API call since we already have enough
        assert mock_service.files.return_value.list.return_value.execute.call_count == 1
