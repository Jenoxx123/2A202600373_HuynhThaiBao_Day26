import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP

from db import SQLiteAdapter, ValidationError
from init_db import create_database

# Create the server object.
mcp = FastMCP("SQLite Lab MCP Server")

DB_PATH = Path(__file__).with_name("lab.db")
env_db_path = os.getenv("SQLITE_LAB_DB_PATH")
if env_db_path:
    DB_PATH = Path(env_db_path)
else:
    # Default to project root to avoid permission issues in some locked folders.
    DB_PATH = Path.cwd() / "sqlite_lab.db"

try:
    create_database(DB_PATH)
except Exception:
    fallback_db = Path(tempfile.gettempdir()) / "sqlite_lab.db"
    create_database(fallback_db)
    DB_PATH = fallback_db

adapter = SQLiteAdapter(DB_PATH)


def _error_payload(exc: Exception) -> str:
    return f"{exc.__class__.__name__}: {exc}"


@mcp.tool(name="search")
def search(
    table: str,
    filters: Optional[List[Dict[str, Any]]] = None,
    columns: Optional[List[str]] = None,
    limit: int = 20,
    offset: int = 0,
    order_by: Optional[str] = None,
    descending: bool = False,
):
    try:
        return adapter.search(
            table=table,
            columns=columns,
            filters=filters,
            limit=limit,
            offset=offset,
            order_by=order_by,
            descending=descending,
        )
    except ValidationError as exc:
        raise ValueError(_error_payload(exc))


@mcp.tool(name="insert")
def insert(table: str, values: Dict[str, Any]):
    try:
        return adapter.insert(table=table, values=values)
    except ValidationError as exc:
        raise ValueError(_error_payload(exc))


@mcp.tool(name="aggregate")
def aggregate(
    table: str,
    metric: str,
    column: Optional[str] = None,
    filters: Optional[List[Dict[str, Any]]] = None,
    group_by: Optional[List[str]] = None,
):
    try:
        return adapter.aggregate(
            table=table,
            metric=metric,
            column=column,
            filters=filters,
            group_by=group_by,
        )
    except ValidationError as exc:
        raise ValueError(_error_payload(exc))


@mcp.resource("schema://database")
def database_schema() -> str:
    schema = {table: adapter.get_table_schema(table) for table in adapter.list_tables()}
    return json.dumps(schema, indent=2, ensure_ascii=False)


@mcp.resource("schema://table/{table_name}")
def table_schema(table_name: str) -> str:
    try:
        data = {table_name: adapter.get_table_schema(table_name)}
        return json.dumps(data, indent=2, ensure_ascii=False)
    except ValidationError as exc:
        raise ValueError(_error_payload(exc))


if __name__ == "__main__":
    mcp.run()
