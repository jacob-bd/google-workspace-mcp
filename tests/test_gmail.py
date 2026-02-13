"""
Tests for Gmail MCP tools.

Tests cover:
- gmail_search uses batch API instead of N+1 sequential calls
- gmail_search handles empty results
- gmail_search handles partial batch failures
- gmail_get_message basic functionality
- gmail_list_labels basic functionality
"""

from unittest.mock import MagicMock, call, patch

from g_workspace_mcp.src.tools.gmail_tools import gmail_search, gmail_get_message, gmail_list_labels


class TestGmailSearchBatching:
    """Tests for gmail_search batch message fetching."""

    @patch("g_workspace_mcp.src.tools.gmail_tools.get_auth")
    def test_search_uses_batch_request(self, mock_get_auth):
        """gmail_search should use new_batch_http_request instead of sequential calls."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        # messages.list returns 3 message IDs
        mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": [
                {"id": "msg1", "threadId": "t1"},
                {"id": "msg2", "threadId": "t2"},
                {"id": "msg3", "threadId": "t3"},
            ]
        }

        mock_batch = MagicMock()
        mock_service.new_batch_http_request.return_value = mock_batch

        gmail_search("test query")

        # Verify batch was created and executed
        mock_service.new_batch_http_request.assert_called_once()
        assert mock_batch.add.call_count == 3
        mock_batch.execute.assert_called_once()

    @patch("g_workspace_mcp.src.tools.gmail_tools.get_auth")
    def test_search_does_not_make_sequential_get_calls(self, mock_get_auth):
        """gmail_search should NOT call messages.get().execute() sequentially."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": [
                {"id": "msg1", "threadId": "t1"},
                {"id": "msg2", "threadId": "t2"},
            ]
        }

        mock_batch = MagicMock()
        mock_service.new_batch_http_request.return_value = mock_batch

        gmail_search("test")

        # The individual .get().execute() should NOT be called directly
        # Only .get() (without .execute()) should be called to create request objects for batch
        get_mock = mock_service.users.return_value.messages.return_value.get
        # get() is called to create request objects, but execute() should NOT be called on them
        if get_mock.return_value.execute.called:
            # This would mean the old N+1 pattern is still in use
            assert False, "messages.get().execute() was called directly — batch not used"

    @patch("g_workspace_mcp.src.tools.gmail_tools.get_auth")
    def test_search_empty_results(self, mock_get_auth):
        """gmail_search should handle zero results gracefully."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": []
        }

        result = gmail_search("nonexistent query")

        assert result["status"] == "success"
        assert result["count"] == 0
        assert result["messages"] == []
        # Batch should not be created for empty results
        mock_service.new_batch_http_request.assert_not_called()

    @patch("g_workspace_mcp.src.tools.gmail_tools.get_auth")
    def test_search_no_messages_key(self, mock_get_auth):
        """gmail_search should handle response with no 'messages' key."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {}

        result = gmail_search("empty query")

        assert result["status"] == "success"
        assert result["count"] == 0

    @patch("g_workspace_mcp.src.tools.gmail_tools.get_auth")
    def test_search_batch_callback_populates_results(self, mock_get_auth):
        """Batch callbacks should correctly populate message details."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": [
                {"id": "msg1", "threadId": "t1"},
            ]
        }

        # Capture the callback when batch.add is called
        captured_callbacks = []

        def capture_add(request, callback=None):
            captured_callbacks.append(callback)

        mock_batch = MagicMock()
        mock_batch.add.side_effect = capture_add

        # When batch.execute() is called, invoke the captured callbacks
        def execute_callbacks():
            for cb in captured_callbacks:
                cb(
                    "req1",
                    {
                        "payload": {
                            "headers": [
                                {"name": "Subject", "value": "Test Subject"},
                                {"name": "From", "value": "sender@test.com"},
                                {"name": "Date", "value": "Mon, 1 Jan 2026"},
                            ]
                        },
                        "snippet": "Preview text",
                    },
                    None,  # no exception
                )

        mock_batch.execute.side_effect = execute_callbacks
        mock_service.new_batch_http_request.return_value = mock_batch

        result = gmail_search("test")

        assert result["status"] == "success"
        assert result["count"] == 1
        msg = result["messages"][0]
        assert msg["id"] == "msg1"
        assert msg["subject"] == "Test Subject"
        assert msg["from"] == "sender@test.com"
        assert msg["snippet"] == "Preview text"

    @patch("g_workspace_mcp.src.tools.gmail_tools.get_auth")
    def test_search_batch_partial_failure(self, mock_get_auth):
        """If some batch requests fail, successful ones should still be returned."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": [
                {"id": "msg1", "threadId": "t1"},
                {"id": "msg2", "threadId": "t2"},
            ]
        }

        captured_callbacks = []

        def capture_add(request, callback=None):
            captured_callbacks.append(callback)

        mock_batch = MagicMock()
        mock_batch.add.side_effect = capture_add

        def execute_callbacks():
            # First message succeeds
            captured_callbacks[0](
                "req1",
                {
                    "payload": {"headers": [{"name": "Subject", "value": "Good"}]},
                    "snippet": "OK",
                },
                None,
            )
            # Second message fails
            captured_callbacks[1](
                "req2",
                None,
                Exception("Not found"),
            )

        mock_batch.execute.side_effect = execute_callbacks
        mock_service.new_batch_http_request.return_value = mock_batch

        result = gmail_search("test")

        assert result["status"] == "success"
        assert result["count"] == 1  # Only the successful one
        assert result["messages"][0]["subject"] == "Good"


class TestGmailGetMessage:
    """Tests for gmail_get_message."""

    @patch("g_workspace_mcp.src.tools.gmail_tools.get_auth")
    def test_get_message_returns_success(self, mock_get_auth):
        """Should return message details on success."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
            "id": "msg1",
            "threadId": "t1",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Hello"},
                    {"name": "From", "value": "test@test.com"},
                    {"name": "To", "value": "me@test.com"},
                ],
                "body": {},
            },
            "labelIds": ["INBOX"],
        }

        result = gmail_get_message("msg1")

        assert result["status"] == "success"
        assert result["subject"] == "Hello"
        assert result["from"] == "test@test.com"


class TestGmailGetMessageTruncation:
    """Tests for gmail_get_message body truncation."""

    def _b64(self, text):
        import base64
        return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii")

    @patch("g_workspace_mcp.src.tools.gmail_tools.get_auth")
    def test_max_length_truncates_body(self, mock_get_auth):
        """Body exceeding max_length should be truncated with notice."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        long_body = "x" * 5000
        mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
            "id": "msg1", "threadId": "t1",
            "payload": {"headers": [], "body": {"data": self._b64(long_body)}},
            "labelIds": [],
        }

        result = gmail_get_message("msg1", max_length=100)

        assert result["status"] == "success"
        assert result["body_truncated"] is True
        assert result["body_length"] == 5000
        assert len(result["body"]) < 5000
        assert "truncated" in result["body"]

    @patch("g_workspace_mcp.src.tools.gmail_tools.get_auth")
    def test_no_truncation_when_under_max_length(self, mock_get_auth):
        """Body under max_length should not be truncated."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        short_body = "Short email"
        mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
            "id": "msg1", "threadId": "t1",
            "payload": {"headers": [], "body": {"data": self._b64(short_body)}},
            "labelIds": [],
        }

        result = gmail_get_message("msg1", max_length=1000)

        assert result["status"] == "success"
        assert result["body_truncated"] is False
        assert result["body"] == short_body

    @patch("g_workspace_mcp.src.tools.gmail_tools.get_auth")
    def test_no_max_length_returns_full_body(self, mock_get_auth):
        """Without max_length, full body should be returned."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        long_body = "y" * 10000
        mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
            "id": "msg1", "threadId": "t1",
            "payload": {"headers": [], "body": {"data": self._b64(long_body)}},
            "labelIds": [],
        }

        result = gmail_get_message("msg1")

        assert result["status"] == "success"
        assert result["body_truncated"] is False
        assert result["body"] == long_body


class TestGmailMimeTraversal:
    """Tests for MIME body extraction in gmail_get_message."""

    def _make_message_response(self, payload):
        """Helper to wrap a payload in a standard message response."""
        return {
            "id": "msg1",
            "threadId": "t1",
            "payload": {
                "headers": [{"name": "Subject", "value": "Test"}],
                **payload,
            },
            "labelIds": [],
        }

    def _b64(self, text):
        """Helper to base64url-encode a string."""
        import base64
        return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii")

    @patch("g_workspace_mcp.src.tools.gmail_tools.get_auth")
    def test_multipart_mixed_with_nested_alternative(self, mock_get_auth):
        """Should find text/plain inside multipart/mixed > multipart/alternative."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        # Structure: multipart/mixed > [multipart/alternative > [text/plain, text/html], attachment]
        mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = self._make_message_response({
            "mimeType": "multipart/mixed",
            "parts": [
                {
                    "mimeType": "multipart/alternative",
                    "parts": [
                        {"mimeType": "text/plain", "body": {"data": self._b64("Plain text body")}},
                        {"mimeType": "text/html", "body": {"data": self._b64("<p>HTML body</p>")}},
                    ],
                },
                {"mimeType": "application/pdf", "body": {"size": 12345}},
            ],
        })

        result = gmail_get_message("msg1")
        assert result["status"] == "success"
        assert result["body"] == "Plain text body"

    @patch("g_workspace_mcp.src.tools.gmail_tools.get_auth")
    def test_multipart_related_with_text(self, mock_get_auth):
        """Should find text inside multipart/related (inline images)."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        # Structure: multipart/related > [multipart/alternative > [text/plain, text/html], image]
        mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = self._make_message_response({
            "mimeType": "multipart/related",
            "parts": [
                {
                    "mimeType": "multipart/alternative",
                    "parts": [
                        {"mimeType": "text/plain", "body": {"data": self._b64("Related body")}},
                        {"mimeType": "text/html", "body": {"data": self._b64("<p>HTML</p>")}},
                    ],
                },
                {"mimeType": "image/png", "body": {"size": 5000}},
            ],
        })

        result = gmail_get_message("msg1")
        assert result["status"] == "success"
        assert result["body"] == "Related body"

    @patch("g_workspace_mcp.src.tools.gmail_tools.get_auth")
    def test_deeply_nested_multipart(self, mock_get_auth):
        """Should find text in deeply nested: mixed > related > alternative > text/plain."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = self._make_message_response({
            "mimeType": "multipart/mixed",
            "parts": [
                {
                    "mimeType": "multipart/related",
                    "parts": [
                        {
                            "mimeType": "multipart/alternative",
                            "parts": [
                                {"mimeType": "text/plain", "body": {"data": self._b64("Deep body")}},
                                {"mimeType": "text/html", "body": {"data": self._b64("<b>Deep</b>")}},
                            ],
                        },
                    ],
                },
            ],
        })

        result = gmail_get_message("msg1")
        assert result["status"] == "success"
        assert result["body"] == "Deep body"

    @patch("g_workspace_mcp.src.tools.gmail_tools.get_auth")
    def test_html_fallback_when_no_plain_text(self, mock_get_auth):
        """Should fall back to HTML when no text/plain part exists."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = self._make_message_response({
            "mimeType": "multipart/mixed",
            "parts": [
                {"mimeType": "text/html", "body": {"data": self._b64("<p>Only HTML</p>")}},
                {"mimeType": "application/pdf", "body": {"size": 999}},
            ],
        })

        result = gmail_get_message("msg1")
        assert result["status"] == "success"
        assert result["body"] == "<p>Only HTML</p>"

    @patch("g_workspace_mcp.src.tools.gmail_tools.get_auth")
    def test_empty_body_when_no_text_parts(self, mock_get_auth):
        """Should return empty string when no text parts exist at all."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = self._make_message_response({
            "mimeType": "multipart/mixed",
            "parts": [
                {"mimeType": "application/pdf", "body": {"size": 999}},
                {"mimeType": "image/jpeg", "body": {"size": 500}},
            ],
        })

        result = gmail_get_message("msg1")
        assert result["status"] == "success"
        assert result["body"] == ""


class TestGmailListLabels:
    """Tests for gmail_list_labels."""

    @patch("g_workspace_mcp.src.tools.gmail_tools.get_auth")
    def test_list_labels_returns_formatted_labels(self, mock_get_auth):
        """Should return properly formatted label list."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        mock_service.users.return_value.labels.return_value.list.return_value.execute.return_value = {
            "labels": [
                {"id": "INBOX", "name": "INBOX", "type": "system"},
                {"id": "Label_1", "name": "My Label"},
            ]
        }

        result = gmail_list_labels()

        assert result["status"] == "success"
        assert result["count"] == 2
        assert result["labels"][0]["name"] == "INBOX"
        assert result["labels"][1]["type"] == "user"  # default when not specified
