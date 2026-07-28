from typing import Any, Dict
from observability.logger import DEFAULT_DB_PATH, get_connection


def calculate_all_metrics(db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """Calculate agent-level metrics from SQLite run_summary and agent_logs."""
    from observability.logger import init_db
    init_db(db_path)

    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as total FROM run_summary")
        total_runs = cursor.fetchone()["total"] or 0

        if total_runs == 0:
            return {
                "total_runs": 0,
                "passed_runs": 0,
                "task_success_rate": 0.0,
                "avg_revision_loops": 0.0,
                "avg_tool_calls": 0.0,
                "avg_quality_score": 0.0,
            }

        cursor.execute(
            "SELECT COUNT(*) as passed FROM run_summary WHERE status = 'passed'"
        )
        passed_runs = cursor.fetchone()["passed"] or 0

        cursor.execute(
            """
            SELECT 
                AVG(revision_count) as avg_revisions,
                AVG(total_tool_calls) as avg_tool_calls,
                AVG(final_score) as avg_score
            FROM run_summary
        """
        )
        row = cursor.fetchone()

        avg_revisions = round(row["avg_revisions"] or 0.0, 2)
        avg_tool_calls = round(row["avg_tool_calls"] or 0.0, 2)
        avg_score = round(row["avg_score"] or 0.0, 2)
        success_rate = round((passed_runs / total_runs) * 100, 2)

        return {
            "total_runs": total_runs,
            "passed_runs": passed_runs,
            "task_success_rate": success_rate,
            "avg_revision_loops": avg_revisions,
            "avg_tool_calls": avg_tool_calls,
            "avg_quality_score": avg_score,
        }


def generate_report(metrics: Dict[str, Any]) -> str:
    """Generate markdown table summary of evaluation metrics."""
    return f"""# 📊 Agent Evaluation & Benchmark Metrics

| Metric | Result | Target / Description |
|---|---|---|
| **Total Benchmark Runs** | `{metrics['total_runs']}` | Evaluated test cases |
| **Task Success Rate** | `{metrics['task_success_rate']}%` | Target ≥ 80% pass threshold |
| **Avg Quality Score** | `{metrics['avg_quality_score']}` | Scale 0.0 - 1.0 (Groundedness, Coverage, Coherence, Faithfulness) |
| **Avg Revision Loops** | `{metrics['avg_revision_loops']}` | Self-reflection loops before passing |
| **Avg Tool Calls / Task** | `{metrics['avg_tool_calls']}` | Search & fetch MCP tool calls used |
"""
