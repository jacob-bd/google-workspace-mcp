"""
Tests for Drive tools.

Tests cover:
- drive_search query handling (operator detection, title+content dual search)
- drive_list pagination
"""

from unittest.mock import MagicMock, patch


class TestDriveSearchQueryHandling:
    """Tests for drive_search operator detection and query building."""

    @patch("g_workspace_mcp.src.tools.drive_tools.get_auth")
    def test_plain_text_search_builds_title_and_content_queries(self, mock_get_auth):
        """Plain text queries should search both title and content."""
        from g_workspace_mcp.src.tools.drive_tools import drive_search

        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        mock_service.files.return_value.list.return_value.execute.return_value = {"files": []}

        result = drive_search("quarterly report")

        assert result["status"] == "success"
        # Should have made 2 API calls (title + content)
        assert mock_service.files.return_value.list.call_count == 2

    @patch("g_workspace_mcp.src.tools.drive_tools.get_auth")
    def test_operator_query_passed_through(self, mock_get_auth):
        """Queries with Drive operators should be passed through as-is."""
        from g_workspace_mcp.src.tools.drive_tools import drive_search

        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        mock_service.files.return_value.list.return_value.execute.return_value = {"files": []}

        result = drive_search("name contains 'budget'")

        assert result["status"] == "success"
        # Should have made only 1 API call (operator query passed through)
        assert mock_service.files.return_value.list.call_count == 1


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
        assert mock_service.files.return_value.list.return_value.execute.call_count == 2

    @patch("g_workspace_mcp.src.tools.drive_tools.get_auth")
    def test_stops_at_max_results(self, mock_get_auth):
        """Should stop fetching pages when max_results is reached."""
        from g_workspace_mcp.src.tools.drive_tools import drive_list

        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        mock_service.files.return_value.list.return_value.execute.return_value = {
            "files": [{"id": f"f{i}", "name": f"file{i}"} for i in range(3)],
            "nextPageToken": "more_data",
        }

        result = drive_list("root", max_results=3)

        assert result["status"] == "success"
        assert result["count"] == 3
        assert mock_service.files.return_value.list.return_value.execute.call_count == 1
