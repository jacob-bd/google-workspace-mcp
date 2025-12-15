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
    range_notation: str = "",
    value_render_option: str = "FORMATTED_VALUE",
    row_limit: int = 100,
) -> Dict[str, Any]:
    """
    Read data from a Google Spreadsheet.

    TOOL_NAME=sheets_read
    DISPLAY_NAME=Sheets Read
    USECASE=Read data from a Google Spreadsheet
    INPUT_DESCRIPTION=spreadsheet_id, range_notation (A1 notation, optional), value_render_option, row_limit
    OUTPUT_DESCRIPTION=Spreadsheet data with title, range, and 2D array of values

    Args:
        spreadsheet_id: The ID of the spreadsheet (from the URL)
        range_notation: A1 notation range (e.g., "Sheet1!A1:D10"). If empty, reads first sheet.
        value_render_option: How to render values:
            - FORMATTED_VALUE: As displayed in UI (default)
            - UNFORMATTED_VALUE: Raw values
            - FORMULA: Show formulas instead of values
        row_limit: Maximum number of rows to return (default: 100) to prevent large context usage.

    Returns:
        Dictionary with status, spreadsheet metadata, and values
    """
    try:
        service = get_auth().get_service("sheets", "v4")

        # Get spreadsheet metadata
        spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()

        title = spreadsheet.get("properties", {}).get("title", "Untitled")

        # If no range specified, use first sheet with full range
        if not range_notation:
            sheets = spreadsheet.get("sheets", [])
            if sheets:
                first_sheet_name = sheets[0].get("properties", {}).get("title", "Sheet1")
                range_notation = f"'{first_sheet_name}'!A1:Z1000"
            else:
                range_notation = "A1:Z1000"
        # If only sheet name provided (no "!"), append default range
        elif "!" not in range_notation:
            # Quote sheet name if it contains spaces and append range
            sheet_name = range_notation
            if " " in sheet_name and not sheet_name.startswith("'"):
                range_notation = f"'{sheet_name}'!A1:Z1000"
            else:
                range_notation = f"{sheet_name}!A1:Z1000"

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

        all_values = result.get("values", [])
        total_count = len(all_values)

        # Apply row limit
        values = all_values[:row_limit]
        is_truncated = total_count > row_limit

        logger.info(f"Read {total_count} rows from spreadsheet: {title} (returned {len(values)})")

        return {
            "status": "success",
            "spreadsheet_id": spreadsheet_id,
            "title": title,
            "range": result.get("range", range_notation),
            "majorDimension": result.get("majorDimension", "ROWS"),
            "total_rows": total_count,
            "returned_rows": len(values),
            "is_truncated": is_truncated,
            "values": values,
        }

    except Exception as e:
        logger.error(f"Sheets read failed: {e}")

        # Try to get sheet names to provide a better error message
        try:
            metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            sheet_names = [
                s.get("properties", {}).get("title", "Unknown") for s in metadata.get("sheets", [])
            ]
            available_sheets = ", ".join(f"'{n}'" for n in sheet_names)
            error_msg = f"Failed to read range '{range_notation}'. Available sheets: [{available_sheets}]. Error: {e}"
        except Exception:
            # If we can't get metadata, just return the original error
            error_msg = str(e)
            sheet_names = []

        return {
            "status": "error",
            "error": error_msg,
            "message": "Failed to read spreadsheet",
            "available_sheets": sheet_names,
        }
