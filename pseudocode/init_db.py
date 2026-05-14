import sqlite3
from pathlib import Path
from typing import Optional, Union


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_code TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    cohort TEXT NOT NULL,
    score REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    credits INTEGER NOT NULL DEFAULT 3
);

CREATE TABLE IF NOT EXISTS enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    semester TEXT NOT NULL,
    grade REAL,
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (course_id) REFERENCES courses(id),
    UNIQUE(student_id, course_id, semester)
);
"""

SEED_STUDENTS = [
    ("S001", "Nguyen Van An", "A1", 8.2),
    ("S002", "Tran Thi Binh", "A1", 7.6),
    ("S003", "Le Quoc Cuong", "A2", 9.1),
    ("S004", "Pham Minh Dung", "A2", 6.8),
]

SEED_COURSES = [
    ("CS101", "Introduction to Programming", 3),
    ("DB201", "Database Systems", 4),
    ("AI301", "Foundations of AI", 3),
]

SEED_ENROLLMENTS = [
    (1, 1, "2026A", 8.0),
    (1, 2, "2026A", 8.5),
    (2, 1, "2026A", 7.2),
    (3, 2, "2026A", 9.0),
    (4, 3, "2026A", 6.7),
]


def create_database(db_path: Optional[Union[str, Path]] = None) -> str:
    """
    Create tables and seed sample data in an idempotent way.

    If db_path is omitted, the database file is created at:
    pseudocode/lab.db
    """
    path = Path(db_path) if db_path else Path(__file__).with_name("lab.db")
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        conn = sqlite3.connect(path)
    except sqlite3.OperationalError as exc:
        raise RuntimeError(
            f"Cannot open SQLite database at '{path}'. "
            "Try another writable location via SQLITE_LAB_DB_PATH."
        ) from exc
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(SCHEMA_SQL)

        conn.executemany(
            """
            INSERT OR IGNORE INTO students(student_code, full_name, cohort, score)
            VALUES (?, ?, ?, ?)
            """,
            SEED_STUDENTS,
        )
        conn.executemany(
            """
            INSERT OR IGNORE INTO courses(course_code, title, credits)
            VALUES (?, ?, ?)
            """,
            SEED_COURSES,
        )
        conn.executemany(
            """
            INSERT OR IGNORE INTO enrollments(student_id, course_id, semester, grade)
            VALUES (?, ?, ?, ?)
            """,
            SEED_ENROLLMENTS,
        )
        conn.commit()
    finally:
        conn.close()

    return str(path.resolve())
