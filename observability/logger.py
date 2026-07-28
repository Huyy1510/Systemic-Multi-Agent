from contextlib import contextmanager
import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

DEFAULT_DB_PATH = "observability.db"


@contextmanager
def get_connection(db_path: str = DEFAULT_DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initialize SQLite tables for agent logs and run summaries."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # agent_logs table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                status TEXT NOT NULL,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                tool_calls INTEGER DEFAULT 0,
                latency_ms INTEGER DEFAULT 0,
                error_message TEXT,
                metadata_json TEXT
            );
        """
        )

        # run_summary table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS run_summary (
                run_id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL,
                status TEXT NOT NULL,
                total_tokens INTEGER DEFAULT 0,
                total_tool_calls INTEGER DEFAULT 0,
                revision_count INTEGER DEFAULT 0,
                final_score REAL DEFAULT 0.0,
                warnings TEXT,
                report_markdown TEXT
            );
        """
        )
        conn.commit()


def log_step(
    run_id: str,
    agent_name: str,
    step_index: int,
    status: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    tool_calls: int = 0,
    latency_ms: int = 0,
    error_message: Optional[str] = None,
    metadata_json: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> None:
    """Log an individual agent step into agent_logs."""
    timestamp = datetime.now().isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO agent_logs (
                run_id, timestamp, agent_name, step_index, status,
                input_tokens, output_tokens, tool_calls, latency_ms,
                error_message, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                run_id,
                timestamp,
                agent_name,
                step_index,
                status,
                input_tokens,
                output_tokens,
                tool_calls,
                latency_ms,
                error_message,
                metadata_json,
            ),
        )
        conn.commit()


def log_run_summary(
    run_id: str,
    query: str,
    started_at: str,
    finished_at: str,
    status: str,
    total_tokens: int = 0,
    total_tool_calls: int = 0,
    revision_count: int = 0,
    final_score: float = 0.0,
    warnings: Optional[str] = None,
    report_markdown: str = "",
    db_path: str = DEFAULT_DB_PATH,
) -> None:
    """Log or update overall pipeline run summary."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO run_summary (
                run_id, query, started_at, finished_at, status,
                total_tokens, total_tool_calls, revision_count,
                final_score, warnings, report_markdown
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                run_id,
                query,
                started_at,
                finished_at,
                status,
                total_tokens,
                total_tool_calls,
                revision_count,
                final_score,
                warnings,
                report_markdown,
            ),
        )
        conn.commit()


def get_all_runs(db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Fetch summary of all runs ordered by start time descending."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM run_summary ORDER BY started_at DESC"
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_run_details(
    run_id: str, db_path: str = DEFAULT_DB_PATH
) -> List[Dict[str, Any]]:
    """Fetch step logs for a specific run_id ordered by step_index."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM agent_logs WHERE run_id = ? ORDER BY step_index ASC",
            (run_id,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_stats(db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """Calculate aggregated stats for observability dashboard."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as total_runs FROM run_summary")
        total_runs = cursor.fetchone()["total_runs"] or 0

        if total_runs == 0:
            return {
                "total_runs": 0,
                "passed_runs": 0,
                "pass_rate": 0.0,
                "avg_tokens_per_run": 0.0,
                "avg_tool_calls_per_run": 0.0,
                "avg_revisions": 0.0,
                "avg_score": 0.0,
            }

        cursor.execute(
            "SELECT COUNT(*) as passed_runs FROM run_summary WHERE status = 'passed'"
        )
        passed_runs = cursor.fetchone()["passed_runs"] or 0

        cursor.execute(
            """
            SELECT 
                AVG(total_tokens) as avg_tokens,
                AVG(total_tool_calls) as avg_tool_calls,
                AVG(revision_count) as avg_revisions,
                AVG(final_score) as avg_score
            FROM run_summary
        """
        )
        averages = cursor.fetchone()

        return {
            "total_runs": total_runs,
            "passed_runs": passed_runs,
            "pass_rate": round(passed_runs / total_runs * 100, 2),
            "avg_tokens_per_run": round(averages["avg_tokens"] or 0, 1),
            "avg_tool_calls_per_run": round(averages["avg_tool_calls"] or 0, 1),
            "avg_revisions": round(averages["avg_revisions"] or 0, 2),
            "avg_score": round(averages["avg_score"] or 0.0, 2),
        }
