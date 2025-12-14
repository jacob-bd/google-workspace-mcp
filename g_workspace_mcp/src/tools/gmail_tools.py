"""
Gmail MCP Tools.

Provides:
- gmail_search: Search emails by query
- gmail_get_message: Get full email content
- gmail_list_labels: List available labels
"""

import base64
from typing import Any, Dict, Optional

from g_workspace_mcp.src.auth.google_oauth import get_auth
from g_workspace_mcp.utils.pylogger import get_python_logger

logger = get_python_logger()


def gmail_search(
    query: str,
    max_results: int = 10,
    include_spam_trash: bool = False,
) -> Dict[str, Any]:
    """
    Search emails in Gmail.

    TOOL_NAME=gmail_search
    DISPLAY_NAME=Gmail Search
    USECASE=Search emails by query
    INPUT_DESCRIPTION=query (Gmail search), max_results (int), include_spam_trash (bool)
    OUTPUT_DESCRIPTION=List of messages with id, subject, from, date, snippet

    Args:
        query: Gmail search query (supports Gmail search operators)
               Examples: "from:user@example.com", "subject:meeting", "is:unread"
        max_results: Maximum number of results (default: 10, max: 100)
        include_spam_trash: Include spam and trash (default: False)

    Returns:
        Dictionary with status and list of messages
    """
    try:
        service = get_auth().get_service("gmail", "v1")

        results = (
            service.users()
            .messages()
            .list(
                userId="me",
                q=query,
                maxResults=min(max_results, 100),
                includeSpamTrash=include_spam_trash,
            )
            .execute()
        )

        messages = results.get("messages", [])

        # Get details for each message
        detailed_messages = []
        for msg in messages[:max_results]:
            msg_detail = (
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=msg["id"],
                    format="metadata",
                    metadataHeaders=["Subject", "From", "Date"],
                )
                .execute()
            )

            headers = {
                h["name"]: h["value"] for h in msg_detail.get("payload", {}).get("headers", [])
            }

            detailed_messages.append(
                {
                    "id": msg["id"],
                    "threadId": msg["threadId"],
                    "subject": headers.get("Subject", "(No Subject)"),
                    "from": headers.get("From", "Unknown"),
                    "date": headers.get("Date", ""),
                    "snippet": msg_detail.get("snippet", ""),
                    "webLink": f"https://mail.google.com/mail/u/0/#inbox/{msg['id']}",
                }
            )

        logger.info(f"Gmail search found {len(detailed_messages)} messages for query: {query}")

        return {
            "status": "success",
            "query": query,
            "count": len(detailed_messages),
            "messages": detailed_messages,
        }

    except Exception as e:
        logger.error(f"Gmail search failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "message": "Failed to search Gmail",
        }


def gmail_get_message(message_id: str) -> Dict[str, Any]:
    """
    Get full content of an email message.

    TOOL_NAME=gmail_get_message
    DISPLAY_NAME=Gmail Get Message
    USECASE=Get full email content by message ID
    INPUT_DESCRIPTION=message_id (string from gmail_search)
    OUTPUT_DESCRIPTION=Full email with subject, from, to, cc, date, body, labels

    Args:
        message_id: The ID of the message to retrieve

    Returns:
        Dictionary with status and full email content
    """
    try:
        service = get_auth().get_service("gmail", "v1")

        message = (
            service.users().messages().get(userId="me", id=message_id, format="full").execute()
        )

        # Extract headers
        headers = {
            h["name"]: h["value"] for h in message.get("payload", {}).get("headers", [])
        }

        # Extract body
        def get_body(payload: dict) -> str:
            """Recursively extract body from message payload."""
            if "body" in payload and payload["body"].get("data"):
                return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")

            if "parts" in payload:
                for part in payload["parts"]:
                    if part["mimeType"] == "text/plain":
                        if part.get("body", {}).get("data"):
                            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
                    elif part["mimeType"] == "multipart/alternative":
                        result = get_body(part)
                        if result:
                            return result

                # If no plain text, try HTML
                for part in payload["parts"]:
                    if part["mimeType"] == "text/html":
                        if part.get("body", {}).get("data"):
                            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")

            return ""

        body = get_body(message.get("payload", {}))

        logger.info(f"Retrieved message: {message_id}")

        return {
            "status": "success",
            "id": message["id"],
            "threadId": message["threadId"],
            "subject": headers.get("Subject", "(No Subject)"),
            "from": headers.get("From", "Unknown"),
            "to": headers.get("To", ""),
            "cc": headers.get("Cc", ""),
            "date": headers.get("Date", ""),
            "body": body,
            "labels": message.get("labelIds", []),
        }

    except Exception as e:
        logger.error(f"Gmail get message failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "message": "Failed to get Gmail message",
        }


def gmail_list_labels() -> Dict[str, Any]:
    """
    List all Gmail labels.

    TOOL_NAME=gmail_list_labels
    DISPLAY_NAME=Gmail List Labels
    USECASE=List all available Gmail labels
    INPUT_DESCRIPTION=None
    OUTPUT_DESCRIPTION=List of labels with id, name, type

    Returns:
        Dictionary with status and list of labels
    """
    try:
        service = get_auth().get_service("gmail", "v1")

        results = service.users().labels().list(userId="me").execute()
        labels = results.get("labels", [])

        # Format labels
        formatted_labels = []
        for label in labels:
            formatted_labels.append(
                {
                    "id": label["id"],
                    "name": label["name"],
                    "type": label.get("type", "user"),
                }
            )

        logger.info(f"Listed {len(formatted_labels)} Gmail labels")

        return {
            "status": "success",
            "count": len(formatted_labels),
            "labels": formatted_labels,
        }

    except Exception as e:
        logger.error(f"Gmail list labels failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "message": "Failed to list Gmail labels",
        }
