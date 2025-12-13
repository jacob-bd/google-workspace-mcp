"""
Google Sheets MCP Tools.

Provides:
- sheets_read: Read data from a spreadsheet
"""

from typing import Any, Dict

from g_workspace_mcp.src.auth.google_oauth import get_auth
from g_workspace_mcp.utils.pylogger import get_python_logger

logger = get_python_logger()


def sheets_read(
    spreadsheet_id: str,
    range_notation: str = "Sheet1",
    value_render_option: str = "FORMATTED_VALUE",
) -> Dict[str, Any]:
    """
    Read data from a Google Spreadsheet.

    TOOL_NAME=sheets_read
    DISPLAY_NAME=Sheets Read
    USECASE=Read data from a Google Spreadsheet
    INPUT_DESCRIPTION=spreadsheet_id, range_notation (A1 notation), value_render_option
    OUTPUT_DESCRIPTION=Spreadsheet data with title, range, and 2D array of values

    Args:
        spreadsheet_id: The ID of the spreadsheet (from the URL)
        range_notation: A1 notation range (e.g., "Sheet1!A1:D10", "Sheet1")
        value_render_option: How to render values:
            - FORMATTED_VALUE: As displayed in UI (default)
            - UNFORMATTED_VALUE: Raw values
            - FORMULA: Show formulas instead of values

    Returns:
        Dictionary with status, spreadsheet metadata, and values
    """
    try:
        service = get_auth().get_service("sheets", "v4")

        # Get spreadsheet metadata
        spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()

        title = spreadsheet.get("properties", {}).get("title", "Untitled")

        # Get values
        result = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=spreadsheet_id,
                range=range_notation,
                valueRenderOption=value_render_option,
            )
            .execute()
        )

        values = result.get("values", [])

        logger.info(f"Read {len(values)} rows from spreadsheet: {title}")

        return {
            "status": "success",
            "spreadsheet_id": spreadsheet_id,
            "title": title,
            "range": result.get("range", range_notation),
            "majorDimension": result.get("majorDimension", "ROWS"),
            "row_count": len(values),
            "values": values,
        }

    except Exception as e:
        logger.error(f"Sheets read failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "message": "Failed to read spreadsheet",
        }
