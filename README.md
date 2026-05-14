# SQLite MCP Lab - Implementation Guide

This repository now contains a working FastMCP + SQLite implementation directly in the existing `pseudocode/` files.

## Implemented Components

- `pseudocode/init_db.py`
  - Creates and seeds SQLite database (`lab.db`) with:
    - `students`
    - `courses`
    - `enrollments`
  - Seed is idempotent (`INSERT OR IGNORE`).

- `pseudocode/db.py`
  - `SQLiteAdapter` with:
    - `list_tables`
    - `get_table_schema`
    - `search`
    - `insert`
    - `aggregate`
  - Validation and safe SQL:
    - reject unknown table/column
    - reject unsupported filter operators
    - reject invalid aggregate metric
    - reject empty inserts
    - use parameterized query values (`?`)

- `pseudocode/mcp_server.py`
  - FastMCP server: `FastMCP("SQLite Lab MCP Server")`
  - Tools:
    - `search`
    - `insert`
    - `aggregate`
  - Resources:
    - `schema://database`
    - `schema://table/{table_name}`

## Setup

1. Create virtual environment (optional but recommended):

```bash
python -m venv .venv
```

2. Activate environment:

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

3. Install dependencies:

```bash
pip install fastmcp
```

## Run Server

From project root:

```bash
python pseudocode/mcp_server.py
```

Default transport is stdio via `mcp.run()`.

## Quick Tool Examples (through MCP client)

- `search` students in cohort A1:

```json
{
  "table": "students",
  "filters": [
    {"column": "cohort", "op": "eq", "value": "A1"}
  ],
  "order_by": "score",
  "descending": true,
  "limit": 10,
  "offset": 0
}
```

- `insert` new student:

```json
{
  "table": "students",
  "values": {
    "student_code": "S099",
    "full_name": "Vo Thi Demo",
    "cohort": "A3",
    "score": 8.8
  }
}
```

- `aggregate` average score by cohort:

```json
{
  "table": "students",
  "metric": "avg",
  "column": "score",
  "group_by": ["cohort"]
}
```

## Resource Examples

- `schema://database`
- `schema://table/students`

## Codex MCP Config Example

`~/.codex/config.toml`

```toml
[mcp_servers.sqlite_lab]
command = "python"
args = ["C:/ABSOLUTE/PATH/TO/pseudocode/mcp_server.py"]
```

Use absolute path and the Python interpreter where `fastmcp` is installed.

## Verification Checklist

- Server starts without crash.
- Tools discoverable: `search`, `insert`, `aggregate`.
- Resources discoverable: `schema://database`, `schema://table/{table_name}`.
- Valid call returns rows/results.
- Invalid call returns clear validation error.
- At least one MCP client can connect and call tools/resources.
