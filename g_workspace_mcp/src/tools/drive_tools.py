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


def _normalize_drive_query(query: str) -> str:
    """
    Normalize a search query to proper Drive API syntax.

    If the query already contains Drive operators (contains, =, in, etc.),
    return it as-is. Otherwise, wrap it in fullText contains syntax.

    Args:
        query: User's search query

    Returns:
        Properly formatted Drive API query string
    """
    if not query or not query.strip():
        return query

    # Check if query already has Drive API operators
    # Common operators: contains, =, !=, <, >, in, and, or, not
    drive_operators = [
        " contains ",
        " = ",
        " != ",
        " < ",
        " > ",
        " in ",
        " and ",
        " or ",
        "not ",
    ]

    query_lower = query.lower()
    has_operators = any(op in query_lower for op in drive_operators)

    if has_operators:
        # Already formatted, return as-is
        return query

    # Plain text query - wrap in fullText contains for broad search
    # fullText searches both file name and content
    escaped_query = query.replace('"', '\\"')
    return f'fullText contains "{escaped_query}"'


def _build_file_type_filter(file_type: Optional[str]) -> Optional[str]:
    """Build mimeType filter clause for Drive API query."""
    if not file_type:
        return None
    mime_type_map = {
        "document": "application/vnd.google-apps.document",
        "spreadsheet": "application/vnd.google-apps.spreadsheet",
        "presentation": "application/vnd.google-apps.presentation",
        "folder": "application/vnd.google-apps.folder",
        "pdf": "application/pdf",
    }
    if file_type.lower() in mime_type_map:
        return f"mimeType='{mime_type_map[file_type.lower()]}'"
    return None


def _execute_drive_search(
    service, query: str, max_results: int, fields: str
) -> list[Dict[str, Any]]:
    """Execute a Drive API search with retry on auth errors."""
    try:
        results = (
            service.files()
            .list(
                q=query,
                pageSize=min(max_results, 100),
                fields=fields,
                orderBy="modifiedTime desc",
            )
            .execute()
        )
        return results.get("files", [])
    except HttpError as e:
        if e.resp.status in [401, 403]:
            logger.info("Auth/Quota error, clearing cache and retrying...")
            get_auth().clear_cache()
            service = get_auth().get_service("drive", "v3")
            results = (
                service.files()
                .list(
                    q=query,
                    pageSize=min(max_results, 100),
                    fields=fields,
                    orderBy="modifiedTime desc",
                )
                .execute()
            )
            return results.get("files", [])
        raise e


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
        fields = "files(id, name, mimeType, webViewLink, modifiedTime, size)"

        # Check if query already has Drive API operators
        query_lower = query.lower()
        drive_operators = [
            " contains ",
            " = ",
            " != ",
            " < ",
            " > ",
            " in ",
            " and ",
            " or ",
            "not ",
        ]
        has_operators = any(op in query_lower for op in drive_operators)

        if has_operators:
            # Already formatted query - execute as-is
            search_query = query
            if file_type:
                type_filter = _build_file_type_filter(file_type)
                if type_filter:
                    search_query = f"{search_query} and {type_filter}"

            files = _execute_drive_search(service, search_query, max_results, fields)
            logger.info(f"Drive search found {len(files)} files for query: {query}")

            return {
                "status": "success",
                "query": query,
                "file_type": file_type,
                "count": len(files),
                "files": files,
            }

        # Plain text query - search both title and content, prioritize title matches
        escaped_query = query.replace('"', '\\"')
        type_filter = _build_file_type_filter(file_type)

        # Build title search query
        title_query = f'name contains "{escaped_query}"'
        if type_filter:
            title_query = f"{title_query} and {type_filter}"

        # Build fullText search query
        content_query = f'fullText contains "{escaped_query}"'
        if type_filter:
            content_query = f"{content_query} and {type_filter}"

        # Execute both searches
        title_files = _execute_drive_search(service, title_query, max_results, fields)
        content_files = _execute_drive_search(service, content_query, max_results, fields)

        # Merge results: title matches first, then content-only matches
        seen_ids = set()
        merged_files = []

        # Add title matches first (highest priority)
        for f in title_files:
            if f["id"] not in seen_ids:
                seen_ids.add(f["id"])
                merged_files.append(f)

        # Add content-only matches (not already in title matches)
        for f in content_files:
            if f["id"] not in seen_ids:
                seen_ids.add(f["id"])
                merged_files.append(f)

        # Limit to max_results
        merged_files = merged_files[:max_results]

        logger.info(
            f"Drive search found {len(merged_files)} files for query: {query} "
            f"(title: {len(title_files)}, content: {len(content_files)})"
        )

        return {
            "status": "success",
            "query": query,
            "file_type": file_type,
            "count": len(merged_files),
            "files": merged_files,
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
                fields="files(id, name, mimeType, webViewLink, modifiedTime, size, shortcutDetails)",
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
    max_length: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Get content of a Google Drive file.

    TOOL_NAME=drive_get_content
    DISPLAY_NAME=Drive Get Content
    USECASE=Read content from a Google Drive file
    INPUT_DESCRIPTION=file_id (string), export_format (text/html/csv), max_length (optional int to truncate content)
    OUTPUT_DESCRIPTION=File content as string with metadata

    Supports:
    - Google Docs (exported as text/html)
    - Google Sheets (exported as CSV)
    - Text files (read directly)
    - PDF files (returns metadata only)

    Args:
        file_id: The ID of the file to read
        export_format: Export format for Google Docs (text, html, csv)
        max_length: Optional maximum content length in characters. If content exceeds
                   this length, it will be truncated with a notice appended.

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
                "content_length": 0,
                "truncated": False,
                "message": f"Cannot extract text content from {mime_type}. Use webViewLink to view.",
            }

        logger.info(f"Retrieved content from: {file_name}")

        # Track original content length
        content_length = len(content) if content else 0
        truncated = False

        # Apply truncation if max_length specified and content exceeds it
        if max_length and content and len(content) > max_length:
            content = (
                content[:max_length]
                + "\n\n... [content truncated - original length: {:,} characters, showing first {:,}]".format(
                    content_length, max_length
                )
            )
            truncated = True

        return {
            "status": "success",
            "file_id": file_id,
            "file_name": file_name,
            "mime_type": mime_type,
            "content": content,
            "content_length": content_length,
            "truncated": truncated,
        }

    except Exception as e:
        logger.error(f"Drive get content failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "message": "Failed to get file content",
        }


def _resolve_shortcut(service, shortcut_details: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Resolve a shortcut to get the target file's metadata.

    Args:
        service: Google Drive API service instance
        shortcut_details: The shortcutDetails object from a shortcut file

    Returns:
        Target file metadata with id, name, mimeType, size, or None if resolution fails
    """
    try:
        target_id = shortcut_details.get("targetId")
        if not target_id:
            return None

        target_meta = (
            service.files()
            .get(fileId=target_id, fields="id, name, mimeType, size, webViewLink")
            .execute()
        )
        return target_meta
    except Exception as e:
        logger.warning(f"Failed to resolve shortcut to {shortcut_details.get('targetId')}: {e}")
        return None


def _bytes_to_mb(size_bytes: Optional[str]) -> Optional[float]:
    """Convert size in bytes (as string) to MB (rounded to 2 decimal places)."""
    if size_bytes is None:
        return None
    try:
        return round(int(size_bytes) / (1024 * 1024), 2)
    except (ValueError, TypeError):
        return None


def drive_list_recursive(
    folder_id: str = "root",
    max_depth: int = 5,
    resolve_shortcuts: bool = True,
    max_files: Optional[int] = None,
    include_trashed: bool = False,
    compact: bool = False,
) -> Dict[str, Any]:
    """
    Recursively list all files in a folder and its subfolders.

    TOOL_NAME=drive_list_recursive
    DISPLAY_NAME=Drive List Recursive
    USECASE=Recursively list all files in a folder tree with sizes
    INPUT_DESCRIPTION=folder_id, max_depth (int), resolve_shortcuts (bool), max_files (optional int), include_trashed (bool), compact (bool)
    OUTPUT_DESCRIPTION=Flat list of all files with path, size in bytes and MB

    Args:
        folder_id: Root folder ID to start from (default: "root" for My Drive root)
        max_depth: Maximum folder depth to traverse (default: 5, max: 10)
        resolve_shortcuts: If True, follow shortcuts and get target file size (default: True)
        max_files: Stop after collecting this many files (default: None = no limit)
        include_trashed: Include trashed files (default: False)
        compact: If True, return minimal fields (name, path, size_mb, type) to reduce response size

    Returns:
        Dictionary with status, total count, total size, and flat list of files
    """
    try:
        service = get_auth().get_service("drive", "v3")

        # Clamp max_depth to reasonable limits
        max_depth = min(max(1, max_depth), 10)

        all_files: list[Dict[str, Any]] = []
        folders_to_process = [(folder_id, "", 0)]  # (folder_id, path, depth)
        total_size_bytes = 0
        shortcuts_resolved = 0
        shortcuts_failed = 0

        while folders_to_process:
            if max_files and len(all_files) >= max_files:
                break

            current_folder_id, current_path, current_depth = folders_to_process.pop(0)

            # Build query
            query = f"'{current_folder_id}' in parents"
            if not include_trashed:
                query += " and trashed=false"

            # Fetch all files in this folder (paginate if needed)
            page_token = None
            while True:
                if max_files and len(all_files) >= max_files:
                    break

                results = (
                    service.files()
                    .list(
                        q=query,
                        pageSize=100,
                        fields="nextPageToken, files(id, name, mimeType, size, shortcutDetails, webViewLink)",
                        pageToken=page_token,
                    )
                    .execute()
                )

                files = results.get("files", [])

                for file in files:
                    if max_files and len(all_files) >= max_files:
                        break

                    file_id = file.get("id")
                    file_name = file.get("name", "Unknown")
                    mime_type = file.get("mimeType", "")
                    size_bytes = file.get("size")
                    shortcut_details = file.get("shortcutDetails")
                    file_path = f"{current_path}/{file_name}" if current_path else file_name

                    # Handle folders - add to queue for recursion
                    if mime_type == "application/vnd.google-apps.folder":
                        if current_depth < max_depth:
                            folders_to_process.append((file_id, file_path, current_depth + 1))
                        # Add folder to results (folders have no size)
                        if compact:
                            all_files.append(
                                {
                                    "name": file_name,
                                    "path": file_path,
                                    "size_mb": None,
                                    "type": "folder",
                                }
                            )
                        else:
                            all_files.append(
                                {
                                    "id": file_id,
                                    "name": file_name,
                                    "path": file_path,
                                    "mimeType": mime_type,
                                    "size_bytes": None,
                                    "size_mb": None,
                                    "is_folder": True,
                                    "is_shortcut": False,
                                    "shortcut_target": None,
                                }
                            )
                        continue

                    # Handle shortcuts
                    if mime_type == "application/vnd.google-apps.shortcut" and shortcut_details:
                        target_info = None
                        if resolve_shortcuts:
                            target_info = _resolve_shortcut(service, shortcut_details)
                            if target_info:
                                shortcuts_resolved += 1
                                size_bytes = target_info.get("size")
                            else:
                                shortcuts_failed += 1

                        if compact:
                            all_files.append(
                                {
                                    "name": file_name,
                                    "path": file_path,
                                    "size_mb": _bytes_to_mb(size_bytes),
                                    "type": "shortcut",
                                }
                            )
                        else:
                            all_files.append(
                                {
                                    "id": file_id,
                                    "name": file_name,
                                    "path": file_path,
                                    "mimeType": mime_type,
                                    "size_bytes": int(size_bytes) if size_bytes else None,
                                    "size_mb": _bytes_to_mb(size_bytes),
                                    "is_folder": False,
                                    "is_shortcut": True,
                                    "shortcut_target": {
                                        "id": shortcut_details.get("targetId"),
                                        "mimeType": shortcut_details.get("targetMimeType"),
                                        "resolved_name": target_info.get("name")
                                        if target_info
                                        else None,
                                    },
                                }
                            )
                        if size_bytes:
                            total_size_bytes += int(size_bytes)
                        continue

                    # Regular files
                    if compact:
                        all_files.append(
                            {
                                "name": file_name,
                                "path": file_path,
                                "size_mb": _bytes_to_mb(size_bytes),
                                "type": "file",
                            }
                        )
                    else:
                        all_files.append(
                            {
                                "id": file_id,
                                "name": file_name,
                                "path": file_path,
                                "mimeType": mime_type,
                                "size_bytes": int(size_bytes) if size_bytes else None,
                                "size_mb": _bytes_to_mb(size_bytes),
                                "is_folder": False,
                                "is_shortcut": False,
                                "shortcut_target": None,
                            }
                        )
                    if size_bytes:
                        total_size_bytes += int(size_bytes)

                page_token = results.get("nextPageToken")
                if not page_token:
                    break

        total_size_mb = round(total_size_bytes / (1024 * 1024), 2)

        logger.info(
            f"Recursive list found {len(all_files)} items, "
            f"total size: {total_size_mb} MB, "
            f"shortcuts resolved: {shortcuts_resolved}, failed: {shortcuts_failed}"
        )

        return {
            "status": "success",
            "folder_id": folder_id,
            "max_depth": max_depth,
            "total_items": len(all_files),
            "total_size_bytes": total_size_bytes,
            "total_size_mb": total_size_mb,
            "shortcuts_resolved": shortcuts_resolved,
            "shortcuts_failed": shortcuts_failed,
            "truncated": max_files is not None and len(all_files) >= max_files,
            "files": all_files,
        }

    except Exception as e:
        logger.error(f"Drive recursive list failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "message": "Failed to recursively list Drive folder",
        }
