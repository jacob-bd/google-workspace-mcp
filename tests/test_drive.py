"""
Tests for Drive tools.

Tests cover:
- Query normalization for Drive API syntax
"""

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
