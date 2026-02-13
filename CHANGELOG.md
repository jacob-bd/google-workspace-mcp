# Changelog

All notable changes to the Google Workspace MCP Server will be documented in this file.

## [0.2.0] - 2026-02-13

### Critical Fixes

- **Logging no longer corrupts MCP protocol** — Redirected all log output from `sys.stdout` to `sys.stderr`. MCP uses stdout for JSON-RPC communication; logging to it could corrupt the protocol stream. FastMCP itself uses stderr for the same reason.
- **ADC credential refresh no longer crashes the server** — `_load_adc_credentials()` now catches `RefreshError` and `TransportError` during token refresh, matching the OAuth path which already handled these gracefully.
- **Sheets error handler no longer masks errors** — Fixed an `UnboundLocalError` in `sheets_read` where the error handler tried to use `service` before it was assigned (e.g., when auth fails).
- **Non-UTF-8 content no longer crashes tools** — Added `errors='replace'` to all `.decode('utf-8')` calls in Gmail body extraction and Drive file content download. Emails in ISO-8859-1, Windows-1252, etc. now decode with replacement characters instead of raising `UnicodeDecodeError`.
- **Gmail search is 100x faster** — Replaced sequential per-message API calls (N+1 problem) with a single batched HTTP request using `service.new_batch_http_request()`. For 100 search results, this reduces HTTP roundtrips from 101 to 2.

### Data Integrity Improvements

- **Gmail now extracts bodies from all email types** — The MIME body parser now recurses into `multipart/mixed`, `multipart/related`, and any other `multipart/*` container. Previously only `multipart/alternative` was handled, causing common emails (with attachments or inline images) to return empty bodies.
- **Sheets reads all columns and rows** — Removed the hardcoded `A1:Z1000` default range that silently truncated data beyond column Z (26) or row 1000. Now uses the full sheet, with the existing `row_limit` parameter for vertical bounds.
- **Drive folder listings are complete** — `drive_list` now follows `nextPageToken` to paginate through large folders. Previously, folders with more than 100 files silently returned only the first page.
- **Gmail message body truncation** — Added optional `max_length` parameter to `gmail_get_message` (matching `drive_get_content`'s existing pattern). Large HTML newsletters no longer blow out LLM context windows. Response includes `body_length` and `body_truncated` fields.

### Resilience Improvements

- **Large files rejected before download** — `drive_get_content` now checks `file_meta["size"]` before downloading. Files over 10 MB return a helpful message instead of exhausting process memory.
- **Graceful server shutdown** — `main.py` now catches `KeyboardInterrupt`, `BrokenPipeError` (parent process disconnected), and unexpected exceptions with `sys.exit(1)` instead of raw tracebacks.
- **Recursive Drive listing retries on auth errors** — `drive_list_recursive` now retries once with cache clear on 401/403 errors mid-traversal, matching `_execute_drive_search`'s existing pattern. Previously, a transient auth error lost all accumulated results.

### Code Cleanup

- **Removed dead code** — Deleted unused `_normalize_drive_query()` (logic was duplicated inline in `drive_search`), `get_uvicorn_log_config()`, `force_reconfigure_all_loggers()`, and the `backports.zoneinfo` import (Python 3.11+ is required).
- **Extracted shared token-save helper** — Token file writing was duplicated in `_save_token()` and `run_oauth_flow()`. Consolidated into `_save_token_secure()` used by both.
- **Hardened config directory permissions** — `CONFIG_DIR` now created with `mode=0o700` (owner-only) instead of the default `0o755`.
- **Dynamic tool count** — MCP server log message now computes tool count instead of hardcoding "10".
- **Fixed misleading docstring** — Removed `http_app()` reference from `WorkspaceMCPServer` docstring (project is stdio-only).
- **CLI version from package metadata** — `--version` now reads from `importlib.metadata.version()` instead of a hardcoded string.
- **O(1) BFS in drive_list_recursive** — Replaced `list.pop(0)` with `collections.deque.popleft()`.

### Test Suite

- **102 tests, 0 failures** (up from 69 tests with 1 pre-existing failure)
- Added 33 new tests covering: logging stream, ADC refresh errors, sheets error handling, Unicode decoding, Gmail batching, MIME traversal, body truncation, Drive pagination, file size guard, server shutdown, and Drive search behavior
- Fixed pre-existing broken test (`test_config_json_outputs_json` — was checking wrong JSON nesting level)

### Other

- Removed GitLab as a push remote (GitHub only going forward)
