"""MySQL access helpers (PyMySQL).

One connection is opened lazily per request and closed on teardown.
All queries are parameterised, which prevents SQL injection.
"""
import time
from pathlib import Path

import pymysql
from flask import current_app, g
from pymysql.cursors import DictCursor

SCHEMA_FILE = Path(__file__).resolve().parent.parent / "schema.sql"


def _connect(cfg: dict):
    return pymysql.connect(
        **cfg,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=True,
        connect_timeout=10,
        init_command="SET time_zone = '+00:00'",  # store/read all timestamps as UTC
    )


def get_db():
    """Return this request's DB connection, creating it on first use."""
    if "db" not in g:
        g.db = _connect(current_app.config["DB"])
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def query_one(sql: str, args=()):
    with get_db().cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchone()


def query_all(sql: str, args=()):
    with get_db().cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall()


def execute(sql: str, args=()) -> int:
    """Run a write statement and return the last inserted id."""
    with get_db().cursor() as cur:
        cur.execute(sql, args)
        return cur.lastrowid


def init_schema(cfg: dict, retries: int = 10, delay: float = 3.0) -> None:
    """Create tables if missing. Retries so the app survives a slow-starting DB."""
    statements = [s.strip() for s in SCHEMA_FILE.read_text().split(";") if s.strip()]
    last_err = None
    for _ in range(retries):
        try:
            conn = _connect(cfg)
            try:
                with conn.cursor() as cur:
                    for stmt in statements:
                        cur.execute(stmt)
            finally:
                conn.close()
            return
        except pymysql.MySQLError as err:
            last_err = err
            time.sleep(delay)
    raise RuntimeError(f"Could not initialise database: {last_err}")
