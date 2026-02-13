"""
Tests for Unicode/encoding handling in Gmail and Drive tools.

Tests cover:
- Non-UTF-8 email bodies don't crash with UnicodeDecodeError
- Non-UTF-8 Drive file content doesn't crash
- UTF-8 content still works correctly
"""

import base64
from unittest.mock import MagicMock, patch

from g_workspace_mcp.src.tools.gmail_tools import gmail_get_message
from g_workspace_mcp.src.tools.drive_tools import drive_get_content


class TestGmailUnicodeHandling:
    """Tests for Gmail body decoding with various encodings."""

    @patch("g_workspace_mcp.src.tools.gmail_tools.get_auth")
    def test_non_utf8_email_body_does_not_crash(self, mock_get_auth):
        """Email body with non-UTF-8 bytes should be decoded with replacement chars, not crash."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        # Latin-1 encoded text: "café résumé" in ISO-8859-1
        latin1_bytes = "café résumé".encode("latin-1")
        encoded_body = base64.urlsafe_b64encode(latin1_bytes).decode("ascii")

        mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
            "id": "msg1",
            "threadId": "thread1",
            "payload": {
                "headers": [{"name": "Subject", "value": "Test"}],
                "body": {"data": encoded_body},
            },
            "labelIds": [],
        }

        result = gmail_get_message("msg1")

        assert result["status"] == "success"
        # Should contain replacement characters but not crash
        assert isinstance(result["body"], str)

    @patch("g_workspace_mcp.src.tools.gmail_tools.get_auth")
    def test_utf8_email_body_works_normally(self, mock_get_auth):
        """Normal UTF-8 email bodies should decode correctly."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        utf8_body = "Hello, this is a normal email with unicode: 日本語"
        encoded_body = base64.urlsafe_b64encode(utf8_body.encode("utf-8")).decode("ascii")

        mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
            "id": "msg1",
            "threadId": "thread1",
            "payload": {
                "headers": [{"name": "Subject", "value": "Test"}],
                "body": {"data": encoded_body},
            },
            "labelIds": [],
        }

        result = gmail_get_message("msg1")

        assert result["status"] == "success"
        assert result["body"] == utf8_body

    @patch("g_workspace_mcp.src.tools.gmail_tools.get_auth")
    def test_multipart_non_utf8_plain_text(self, mock_get_auth):
        """Multipart email with non-UTF-8 plain text part should not crash."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        # Windows-1252 bytes with smart quotes
        win1252_bytes = b"He said \x93hello\x94"
        encoded_body = base64.urlsafe_b64encode(win1252_bytes).decode("ascii")

        mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
            "id": "msg2",
            "threadId": "thread2",
            "payload": {
                "headers": [{"name": "Subject", "value": "Quotes"}],
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {"data": encoded_body},
                    },
                ],
            },
            "labelIds": [],
        }

        result = gmail_get_message("msg2")

        assert result["status"] == "success"
        assert isinstance(result["body"], str)


class TestDriveUnicodeHandling:
    """Tests for Drive file content decoding with various encodings."""

    @patch("g_workspace_mcp.src.tools.drive_tools.MediaIoBaseDownload")
    @patch("g_workspace_mcp.src.tools.drive_tools.get_auth")
    def test_non_utf8_text_file_does_not_crash(self, mock_get_auth, mock_downloader_class):
        """Text file with non-UTF-8 content should be decoded with replacement chars."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        mock_service.files.return_value.get.return_value.execute.return_value = {
            "id": "file1",
            "name": "legacy.txt",
            "mimeType": "text/plain",
            "size": "100",
        }

        # Simulate downloading a Latin-1 encoded file
        latin1_content = "Ünîcödé tëst".encode("latin-1")

        mock_downloader = MagicMock()
        mock_downloader.next_chunk.return_value = (None, True)
        mock_downloader_class.return_value = mock_downloader

        # Patch io.BytesIO to return our Latin-1 content
        import io
        with patch("g_workspace_mcp.src.tools.drive_tools.io.BytesIO") as mock_bytesio:
            mock_buffer = io.BytesIO(latin1_content)
            mock_bytesio.return_value = mock_buffer
            # Override getvalue to return our content after "download"
            mock_buffer.getvalue = lambda: latin1_content

            result = drive_get_content("file1")

        assert result["status"] == "success"
        assert isinstance(result["content"], str)
        # Should not crash - content may have replacement chars

    @patch("g_workspace_mcp.src.tools.drive_tools.get_auth")
    def test_google_doc_export_handles_encoding(self, mock_get_auth):
        """Google Docs export should handle bytes decoding gracefully."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        mock_service.files.return_value.get.return_value.execute.return_value = {
            "id": "doc1",
            "name": "My Doc",
            "mimeType": "application/vnd.google-apps.document",
        }

        # Export returns UTF-8 bytes
        doc_content = "Document content with émojis 🎉"
        mock_service.files.return_value.export.return_value.execute.return_value = doc_content.encode("utf-8")

        result = drive_get_content("doc1")

        assert result["status"] == "success"
        assert result["content"] == doc_content


class TestDriveFileSizeGuard:
    """Tests for file size check before download."""

    @patch("g_workspace_mcp.src.tools.drive_tools.get_auth")
    def test_large_file_rejected_before_download(self, mock_get_auth):
        """Files exceeding 10 MB should be rejected without downloading."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        mock_service.files.return_value.get.return_value.execute.return_value = {
            "id": "big1",
            "name": "huge.json",
            "mimeType": "application/json",
            "size": str(50 * 1024 * 1024),  # 50 MB
        }

        result = drive_get_content("big1")

        assert result["status"] == "success"
        assert result["content"] is None
        assert "too large" in result["message"]
        # Should NOT have attempted to download
        mock_service.files.return_value.get_media.assert_not_called()

    @patch("g_workspace_mcp.src.tools.drive_tools.MediaIoBaseDownload")
    @patch("g_workspace_mcp.src.tools.drive_tools.get_auth")
    def test_small_file_allowed_to_download(self, mock_get_auth, mock_downloader_class):
        """Files under 10 MB should proceed to download normally."""
        mock_service = MagicMock()
        mock_get_auth.return_value.get_service.return_value = mock_service

        mock_service.files.return_value.get.return_value.execute.return_value = {
            "id": "small1",
            "name": "small.txt",
            "mimeType": "text/plain",
            "size": str(1024),  # 1 KB
        }

        mock_downloader = MagicMock()
        mock_downloader.next_chunk.return_value = (None, True)
        mock_downloader_class.return_value = mock_downloader

        import io
        with patch("g_workspace_mcp.src.tools.drive_tools.io.BytesIO") as mock_bytesio:
            mock_buffer = io.BytesIO(b"small content")
            mock_bytesio.return_value = mock_buffer
            mock_buffer.getvalue = lambda: b"small content"

            result = drive_get_content("small1")

        assert result["status"] == "success"
        assert result["content"] == "small content"
