import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Literal

from langgraph.graph import StateGraph, START, END

from agents.critic import CriticAgent
from agents.planner import PlannerAgent
from agents.researcher import ResearcherAgent
from agents.writer import WriterAgent
from graph.state import GraphState
from guardrails.limits import load_config
from observability import init_db, log_run_summary, log_step


def planner_node(state: GraphState) -> Dict[str, Any]:
    run_id = state.get("run_id", "default-run")
    step_idx = state.get("_step_index", 1)
    start_t = time.time()

    planner = PlannerAgent()
    result = planner.run(state)

    latency = int((time.time() - start_t) * 1000)
    log_step(
        run_id=run_id,
        agent_name="planner",
        step_index=step_idx,
        status="success" if "error" not in result else "error",
        latency_ms=latency,
        error_message=result.get("error"),
    )
    result["_step_index"] = step_idx + 1
    return result


def researcher_node(state: GraphState) -> Dict[str, Any]:
    run_id = state.get("run_id", "default-run")
    step_idx = state.get("_step_index", 2)
    start_t = time.time()

    researcher = ResearcherAgent()
    result = researcher.run(state)

    latency = int((time.time() - start_t) * 1000)
    total_tool_calls = sum(
        item.get("tool_calls_used", 0)
        for item in result.get("research_results", [])
    )
    log_step(
        run_id=run_id,
        agent_name="researcher",
        step_index=step_idx,
        status="success" if "error" not in result else "error",
        tool_calls=total_tool_calls,
        latency_ms=latency,
        error_message=result.get("error"),
    )
    result["_step_index"] = step_idx + 1
    return result


def writer_node(state: GraphState) -> Dict[str, Any]:
    run_id = state.get("run_id", "default-run")
    step_idx = state.get("_step_index", 3)
    start_t = time.time()

    writer = WriterAgent()
    result = writer.run(state)

    latency = int((time.time() - start_t) * 1000)
    log_step(
        run_id=run_id,
        agent_name="writer",
        step_index=step_idx,
        status="success" if "error" not in result else "error",
        latency_ms=latency,
        error_message=result.get("error"),
    )
    result["_step_index"] = step_idx + 1
    return result


def critic_node(state: GraphState) -> Dict[str, Any]:
    run_id = state.get("run_id", "default-run")
    step_idx = state.get("_step_index", 4)
    start_t = time.time()

    critic = CriticAgent()
    result = critic.run(state)

    latency = int((time.time() - start_t) * 1000)
    scores = result.get("critic_scores", {})
    metadata = {
        "scores": scores,
        "feedback": result.get("critic_feedback", ""),
        "passed": result.get("passed", False),
    }

    import json

    log_step(
        run_id=run_id,
        agent_name="critic",
        step_index=step_idx,
        status="success" if result.get("passed") else "rejected",
        latency_ms=latency,
        metadata_json=json.dumps(metadata),
    )
    result["_step_index"] = step_idx + 1
    return result


def route_critic(
    state: GraphState,
) -> Literal["finalize", "writer", "force_finalize"]:
    passed = state.get("passed", False)
    revision_count = state.get("revision_count", 0)
    config = load_config()

    if passed:
        return "finalize"
    elif revision_count < config.max_critic_loops:
        return "writer"
    else:
        return "force_finalize"


def finalize_node(state: GraphState) -> Dict[str, Any]:
    run_id = state.get("run_id", "default-run")
    draft = state.get("draft_report", "")
    scores = state.get("critic_scores", {})
    final_score = scores.get("average_score", 0.0)

    started_at = state.get("_started_at", datetime.now().isoformat())
    finished_at = datetime.now().isoformat()

    import json

    log_run_summary(
        run_id=run_id,
        query=state.get("user_query", ""),
        started_at=started_at,
        finished_at=finished_at,
        status="passed",
        revision_count=state.get("revision_count", 0),
        final_score=final_score,
        warnings=json.dumps(state.get("warnings", [])),
        report_markdown=draft,
    )
    return {"final_report": draft}


def force_finalize_node(state: GraphState) -> Dict[str, Any]:
    run_id = state.get("run_id", "default-run")
    draft = state.get("draft_report", "")
    warnings = list(state.get("warnings", []))

    warning_notice = (
        "\n\n---\n> ⚠️ **Quality Warning**: This report reached the maximum allowed revision limit "
        "and was finalized automatically. Manual review is recommended."
    )
    final_report = draft + warning_notice

    scores = state.get("critic_scores", {})
    final_score = scores.get("average_score", 0.0)

    started_at = state.get("_started_at", datetime.now().isoformat())
    finished_at = datetime.now().isoformat()

    import json

    warnings.append("Report force-finalized due to max critic revision limit.")

    log_run_summary(
        run_id=run_id,
        query=state.get("user_query", ""),
        started_at=started_at,
        finished_at=finished_at,
        status="passed_with_warnings",
        revision_count=state.get("revision_count", 0),
        final_score=final_score,
        warnings=json.dumps(warnings),
        report_markdown=final_report,
    )
    return {"final_report": final_report, "warnings": warnings}


def build_graph():
    """Build and compile the LangGraph workflow graph."""
    builder = StateGraph(GraphState)

    # Nodes
    builder.add_node("planner", planner_node)
    builder.add_node("researcher", researcher_node)
    builder.add_node("writer", writer_node)
    builder.add_node("critic", critic_node)
    builder.add_node("finalize", finalize_node)
    builder.add_node("force_finalize", force_finalize_node)

    # Edges
    builder.add_edge(START, "planner")
    builder.add_edge("planner", "researcher")
    builder.add_edge("researcher", "writer")
    builder.add_edge("writer", "critic")

    # Conditional Routing from Critic
    builder.add_conditional_edges(
        "critic",
        route_critic,
        {
            "finalize": "finalize",
            "writer": "writer",
            "force_finalize": "force_finalize",
        },
    )

    builder.add_edge("finalize", END)
    builder.add_edge("force_finalize", END)

    return builder.compile()


def run_research(
    query: str, run_id: Optional[str] = None
) -> Dict[str, Any]:
    """Convenience function to run the full research pipeline."""
    init_db()
    actual_run_id = run_id or str(uuid.uuid4())
    started_at = datetime.now().isoformat()

    graph = build_graph()

    initial_state = {
        "user_query": query,
        "run_id": actual_run_id,
        "_started_at": started_at,
        "_step_index": 1,
        "sub_questions": [],
        "research_results": [],
        "draft_report": "",
        "critic_scores": {},
        "critic_feedback": "",
        "passed": False,
        "revision_count": 0,
        "final_report": "",
        "error": None,
        "warnings": [],
    }

    final_state = graph.invoke(initial_state)
    return final_state
