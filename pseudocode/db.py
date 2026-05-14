import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union


class ValidationError(Exception):
    """Raised when a request cannot be safely executed."""


class SQLiteAdapter:
    """
    SQLite data adapter with strict input validation for MCP tools.
    """

    SUPPORTED_OPERATORS = {
        "eq": "=",
        "ne": "!=",
        "gt": ">",
        "gte": ">=",
        "lt": "<",
        "lte": "<=",
        "like": "LIKE",
        "in": "IN",
    }
    SUPPORTED_METRICS = {"count", "avg", "sum", "min", "max"}
    IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    def __init__(self, db_path: Union[str, Path]):
        self.db_path = str(db_path)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
        finally:
            conn.close()

    def list_tables(self) -> List[str]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
        return [row["name"] for row in rows]

    def get_table_schema(self, table: str) -> List[Dict[str, Any]]:
        safe_table = self._validate_table(table)
        with self.connect() as conn:
            rows = conn.execute(f'PRAGMA table_info("{safe_table}")').fetchall()
        return [
            {
                "cid": row["cid"],
                "name": row["name"],
                "type": row["type"],
                "notnull": bool(row["notnull"]),
                "default_value": row["dflt_value"],
                "primary_key": bool(row["pk"]),
            }
            for row in rows
        ]

    def search(
        self,
        table: str,
        columns: Optional[Sequence[str]] = None,
        filters: Optional[Sequence[Dict[str, Any]]] = None,
        limit: int = 20,
        offset: int = 0,
        order_by: Optional[str] = None,
        descending: bool = False,
    ) -> Dict[str, Any]:
        safe_table = self._validate_table(table)
        available_columns = self._get_columns(safe_table)
        selected_columns = (
            self._validate_columns(safe_table, columns, available_columns)
            if columns
            else available_columns
        )

        if not isinstance(limit, int) or limit <= 0 or limit > 500:
            raise ValidationError("limit must be an integer in range 1..500")
        if not isinstance(offset, int) or offset < 0:
            raise ValidationError("offset must be a non-negative integer")

        where_sql, params = self._build_where_clause(
            safe_table, filters, available_columns
        )

        order_sql = ""
        if order_by is not None:
            if order_by not in available_columns:
                raise ValidationError(f"Unknown order_by column: {order_by}")
            direction = "DESC" if descending else "ASC"
            order_sql = f' ORDER BY "{order_by}" {direction}'

        cols_sql = ", ".join(f'"{c}"' for c in selected_columns)
        query = (
            f'SELECT {cols_sql} FROM "{safe_table}"{where_sql}{order_sql} LIMIT ? OFFSET ?'
        )
        params.extend([limit, offset])

        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        data = [dict(row) for row in rows]
        return {
            "table": safe_table,
            "rows": data,
            "count": len(data),
            "limit": limit,
            "offset": offset,
            "order_by": order_by,
            "descending": bool(descending),
        }

    def insert(self, table: str, values: Dict[str, Any]) -> Dict[str, Any]:
        safe_table = self._validate_table(table)
        if not isinstance(values, dict) or not values:
            raise ValidationError("insert values must be a non-empty object")

        available_columns = self._get_columns(safe_table)
        columns = self._validate_columns(safe_table, list(values.keys()), available_columns)
        placeholders = ", ".join("?" for _ in columns)
        quoted_columns = ", ".join(f'"{c}"' for c in columns)
        params = [values[c] for c in columns]

        query = f'INSERT INTO "{safe_table}" ({quoted_columns}) VALUES ({placeholders})'
        with self.connect() as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            inserted_rowid = cursor.lastrowid

        inserted_payload = dict(values)
        if "id" in available_columns and "id" not in inserted_payload and inserted_rowid:
            inserted_payload["id"] = inserted_rowid

        return {
            "table": safe_table,
            "rowid": inserted_rowid,
            "values": inserted_payload,
        }

    def aggregate(
        self,
        table: str,
        metric: str,
        column: Optional[str] = None,
        filters: Optional[Sequence[Dict[str, Any]]] = None,
        group_by: Optional[Union[str, Sequence[str]]] = None,
    ) -> Dict[str, Any]:
        safe_table = self._validate_table(table)
        metric_lower = str(metric).lower()
        if metric_lower not in self.SUPPORTED_METRICS:
            raise ValidationError(
                f"Unsupported metric: {metric}. Allowed: {sorted(self.SUPPORTED_METRICS)}"
            )

        available_columns = self._get_columns(safe_table)
        if metric_lower == "count":
            metric_expr = "COUNT(*)"
            metric_column = None
        else:
            if not column:
                raise ValidationError(f"column is required for metric '{metric_lower}'")
            if column not in available_columns:
                raise ValidationError(f"Unknown column for aggregate: {column}")
            metric_expr = f'{metric_lower.upper()}("{column}")'
            metric_column = column

        group_columns: List[str] = []
        if group_by:
            if isinstance(group_by, str):
                group_candidates = [group_by]
            elif isinstance(group_by, Iterable):
                group_candidates = list(group_by)
            else:
                raise ValidationError("group_by must be a string or list of strings")
            group_columns = self._validate_columns(
                safe_table, group_candidates, available_columns
            )

        where_sql, params = self._build_where_clause(
            safe_table, filters, available_columns
        )

        select_parts = [metric_expr + " AS value"]
        if group_columns:
            select_parts = [f'"{c}"' for c in group_columns] + select_parts
            group_sql = " GROUP BY " + ", ".join(f'"{c}"' for c in group_columns)
        else:
            group_sql = ""

        query = (
            f'SELECT {", ".join(select_parts)} FROM "{safe_table}"{where_sql}{group_sql}'
        )
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return {
            "table": safe_table,
            "metric": metric_lower,
            "column": metric_column,
            "group_by": group_columns or None,
            "rows": [dict(row) for row in rows],
            "count": len(rows),
        }

    def _validate_table(self, table: str) -> str:
        if not isinstance(table, str) or not table:
            raise ValidationError("table name is required")
        if not self.IDENTIFIER_PATTERN.match(table):
            raise ValidationError(f"Invalid table identifier: {table}")
        tables = set(self.list_tables())
        if table not in tables:
            raise ValidationError(f"Unknown table: {table}")
        return table

    def _get_columns(self, table: str) -> List[str]:
        return [col["name"] for col in self.get_table_schema(table)]

    def _validate_columns(
        self,
        table: str,
        columns: Sequence[str],
        available_columns: Optional[Sequence[str]] = None,
    ) -> List[str]:
        if not columns:
            raise ValidationError("columns cannot be empty")
        if available_columns is None:
            available_columns = self._get_columns(table)
        available = set(available_columns)
        clean_columns: List[str] = []
        for col in columns:
            if not isinstance(col, str) or not col:
                raise ValidationError("column names must be non-empty strings")
            if not self.IDENTIFIER_PATTERN.match(col):
                raise ValidationError(f"Invalid column identifier: {col}")
            if col not in available:
                raise ValidationError(f"Unknown column '{col}' for table '{table}'")
            clean_columns.append(col)
        return clean_columns

    def _build_where_clause(
        self,
        table: str,
        filters: Optional[Sequence[Dict[str, Any]]],
        available_columns: Sequence[str],
    ) -> Tuple[str, List[Any]]:
        if not filters:
            return "", []
        if not isinstance(filters, Sequence):
            raise ValidationError("filters must be a list of filter objects")

        parts: List[str] = []
        params: List[Any] = []
        for filter_item in filters:
            if not isinstance(filter_item, dict):
                raise ValidationError("each filter must be an object")
            column = filter_item.get("column")
            op = str(filter_item.get("op", "")).lower()
            value = filter_item.get("value")

            if column is None or op == "":
                raise ValidationError("each filter needs: column, op, value")
            self._validate_columns(table, [column], available_columns)

            if op not in self.SUPPORTED_OPERATORS:
                raise ValidationError(
                    f"Unsupported operator '{op}'. Allowed: {sorted(self.SUPPORTED_OPERATORS)}"
                )
            if op == "in":
                if not isinstance(value, (list, tuple)) or not value:
                    raise ValidationError("operator 'in' requires a non-empty list value")
                placeholders = ", ".join("?" for _ in value)
                parts.append(f'"{column}" IN ({placeholders})')
                params.extend(list(value))
            else:
                parts.append(f'"{column}" {self.SUPPORTED_OPERATORS[op]} ?')
                params.append(value)

        return " WHERE " + " AND ".join(parts), params
