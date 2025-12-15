"""
Google Drive MCP Tools.

Provides:
- drive_search: Search files by query
- drive_list: List files in a folder
- drive_get_content: Get file content (Docs, Sheets, text files)
"""

import io
from typing import Any, Dict, Literal, Optional

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

from g_workspace_mcp.src.auth.google_oauth import get_auth
from g_workspace_mcp.utils.pylogger import get_python_logger

logger = get_python_logger()


def drive_search(
    query: str,
    max_results: int = 10,
    file_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Search for files in Google Drive.

    TOOL_NAME=drive_search
    DISPLAY_NAME=Drive Search
    USECASE=Search files in Google Drive by query
    INPUT_DESCRIPTION=query (search string), max_results (int), file_type (optional: document/spreadsheet/folder/pdf)
    OUTPUT_DESCRIPTION=List of matching files with id, name, mimeType, webViewLink

    Args:
        query: Search query (supports Drive search operators)
        max_results: Maximum number of results (default: 10, max: 100)
        file_type: Optional filter by type (document, spreadsheet, folder, pdf)

    Returns:
        Dictionary with status and list of matching files
    """
    try:
        service = get_auth().get_service("drive", "v3")

        # Build search query
        search_query = query
        if file_type:
            mime_type_map = {
                "document": "application/vnd.google-apps.document",
                "spreadsheet": "application/vnd.google-apps.spreadsheet",
                "presentation": "application/vnd.google-apps.presentation",
                "folder": "application/vnd.google-apps.folder",
                "pdf": "application/pdf",
            }
            if file_type.lower() in mime_type_map:
                search_query = f"{query} and mimeType='{mime_type_map[file_type.lower()]}'"

        # Execute search
        try:
            results = (
                service.files()
                .list(
                    q=search_query,
                    pageSize=min(max_results, 100),
                    fields="files(id, name, mimeType, webViewLink, modifiedTime, size)",
                    orderBy="modifiedTime desc",
                )
                .execute()
            )
        except HttpError as e:
            if e.resp.status in [401, 403]:
                logger.info("Auth/Quota error, clearing cache and retrying...")
                get_auth().clear_cache()
                service = get_auth().get_service("drive", "v3")
                results = (
                    service.files()
                    .list(
                        q=search_query,
                        pageSize=min(max_results, 100),
                        fields="files(id, name, mimeType, webViewLink, modifiedTime, size)",
                        orderBy="modifiedTime desc",
                    )
                    .execute()
                )
            else:
                raise e

        files = results.get("files", [])
        logger.info(f"Drive search found {len(files)} files for query: {query}")

        return {
            "status": "success",
            "query": query,
            "file_type": file_type,
            "count": len(files),
            "files": files,
        }

    except Exception as e:
        logger.error(f"Drive search failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "message": "Failed to search Drive",
        }


def drive_list(
    folder_id: str = "root",
    max_results: int = 25,
    include_trashed: bool = False,
) -> Dict[str, Any]:
    """
    List files in a Google Drive folder.

    TOOL_NAME=drive_list
    DISPLAY_NAME=Drive List Folder
    USECASE=List files in a Google Drive folder
    INPUT_DESCRIPTION=folder_id (default: root), max_results (int), include_trashed (bool)
    OUTPUT_DESCRIPTION=List of files in the folder with metadata

    Args:
        folder_id: Folder ID to list (default: "root" for My Drive root)
        max_results: Maximum number of results (default: 25, max: 100)
        include_trashed: Include trashed files (default: False)

    Returns:
        Dictionary with status and list of files
    """
    try:
        service = get_auth().get_service("drive", "v3")

        query = f"'{folder_id}' in parents"
        if not include_trashed:
            query += " and trashed=false"

        results = (
            service.files()
            .list(
                q=query,
                pageSize=min(max_results, 100),
                fields="files(id, name, mimeType, webViewLink, modifiedTime, size)",
                orderBy="name",
            )
            .execute()
        )

        files = results.get("files", [])
        logger.info(f"Listed {len(files)} files in folder: {folder_id}")

        return {
            "status": "success",
            "folder_id": folder_id,
            "count": len(files),
            "files": files,
        }

    except Exception as e:
        logger.error(f"Drive list failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "message": "Failed to list Drive folder",
        }


def drive_get_content(
    file_id: str,
    export_format: Literal["text", "html", "csv"] = "text",
) -> Dict[str, Any]:
    """
    Get content of a Google Drive file.

    TOOL_NAME=drive_get_content
    DISPLAY_NAME=Drive Get Content
    USECASE=Read content from a Google Drive file
    INPUT_DESCRIPTION=file_id (string), export_format (text/html/csv)
    OUTPUT_DESCRIPTION=File content as string with metadata

    Supports:
    - Google Docs (exported as text/html)
    - Google Sheets (exported as CSV)
    - Text files (read directly)
    - PDF files (returns metadata only)

    Args:
        file_id: The ID of the file to read
        export_format: Export format for Google Docs (text, html, csv)

    Returns:
        Dictionary with status, file metadata, and content
    """
    try:
        service = get_auth().get_service("drive", "v3")

        # Get file metadata
        file_meta = service.files().get(fileId=file_id, fields="id, name, mimeType, size").execute()

        mime_type = file_meta.get("mimeType", "")
        file_name = file_meta.get("name", "Unknown")

        content = None

        # Handle Google Docs
        if mime_type == "application/vnd.google-apps.document":
            export_mime = {
                "text": "text/plain",
                "html": "text/html",
                "csv": "text/plain",
            }.get(export_format, "text/plain")

            content_bytes = service.files().export(fileId=file_id, mimeType=export_mime).execute()
            content = (
                content_bytes.decode("utf-8") if isinstance(content_bytes, bytes) else content_bytes
            )

        # Handle Google Sheets
        elif mime_type == "application/vnd.google-apps.spreadsheet":
            content_bytes = service.files().export(fileId=file_id, mimeType="text/csv").execute()
            content = (
                content_bytes.decode("utf-8") if isinstance(content_bytes, bytes) else content_bytes
            )

        # Handle Google Slides
        elif mime_type == "application/vnd.google-apps.presentation":
            content_bytes = service.files().export(fileId=file_id, mimeType="text/plain").execute()
            content = (
                content_bytes.decode("utf-8") if isinstance(content_bytes, bytes) else content_bytes
            )

        # Handle regular files (text, json, etc.)
        elif mime_type.startswith("text/") or mime_type == "application/json":
            request = service.files().get_media(fileId=file_id)
            file_handle = io.BytesIO()
            downloader = MediaIoBaseDownload(file_handle, request)

            done = False
            while not done:
                _, done = downloader.next_chunk()

            content = file_handle.getvalue().decode("utf-8")

        # Unsupported file types
        else:
            logger.info(f"Unsupported MIME type for content extraction: {mime_type}")
            return {
                "status": "success",
                "file_id": file_id,
                "file_name": file_name,
                "mime_type": mime_type,
                "content": None,
                "message": f"Cannot extract text content from {mime_type}. Use webViewLink to view.",
            }

        logger.info(f"Retrieved content from: {file_name}")

        return {
            "status": "success",
            "file_id": file_id,
            "file_name": file_name,
            "mime_type": mime_type,
            "content": content,
        }

    except Exception as e:
        logger.error(f"Drive get content failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "message": "Failed to get file content",
        }
