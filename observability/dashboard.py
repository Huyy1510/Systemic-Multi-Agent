import json
import os
import sys
import pandas as pd
import streamlit as st

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from graph.workflow import run_research
from observability.logger import get_all_runs, get_run_details, get_stats, init_db
from utils import clean_llm_text

st.set_page_config(
    page_title="Multi-Agent Research Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()

st.title("🤖 Multi-Agent Research & Report Assistant")
st.caption(
    "Automated Research, Synthesis, Self-Reflection Loop & Observability Dashboard"
)

tab1, tab2 = st.tabs(["🔬 Research Workspace", "📊 Observability Dashboard"])

# ==========================================
# TAB 1: RESEARCH WORKSPACE
# ==========================================
with tab1:
    st.subheader("Start New Research Query")
    query_input = st.text_input(
        "Enter Research Topic or Question:",
        value="Compare agentic AI trends in 2026 between the US and Vietnam",
        placeholder="e.g. Compare LLM reasoning benchmarks in 2026",
    )

    if st.button("🚀 Run Multi-Agent Research", type="primary"):
        if not query_input.strip():
            st.warning("Please enter a research question.")
        else:
            with st.status(
                "Running Multi-Agent Workflow...", expanded=True
            ) as status:
                st.write("1️⃣ **Planner**: Generating structured sub-questions...")
                start_time = pd.Timestamp.now()

                final_state = run_research(query_input)

                st.write("2️⃣ **Researcher**: Web searching & extracting sources...")
                st.write("3️⃣ **Writer**: Drafting comprehensive markdown report...")
                st.write(
                    "4️⃣ **Critic**: Chấm điểm 4 tiêu chuẩn quality (Groundedness, Coverage, Coherence, Faithfulness)..."
                )

                if final_state.get("passed"):
                    status.update(
                        label="✅ Research Completed & Passed Quality Checks!",
                        state="complete",
                    )
                else:
                    status.update(
                        label="⚠️ Completed with Warnings / Revisions",
                        state="complete",
                    )

            st.divider()

            # Display Results
            col_main, col_side = st.columns([3, 1])

            with col_main:
                st.subheader("📄 Generated Research Report")
                final_report = clean_llm_text(final_state.get("final_report", ""))
                st.markdown(final_report)

                st.download_button(
                    label="📥 Download Report (.md)",
                    data=final_report,
                    file_name="research_report.md",
                    mime="text/markdown",
                )

            with col_side:
                st.subheader("🔍 Execution Summary")
                scores = final_state.get("critic_scores", {})
                st.metric("Overall Score", f"{scores.get('average_score', 0.0):.2f}")
                st.metric(
                    "Revision Loops",
                    f"{final_state.get('revision_count', 0)} / 3",
                )

                st.markdown("**Metric Breakdown:**")
                st.progress(
                    scores.get("groundedness", 0.0),
                    text=f"Groundedness: {scores.get('groundedness', 0.0):.2f}",
                )
                st.progress(
                    scores.get("coverage", 0.0),
                    text=f"Coverage: {scores.get('coverage', 0.0):.2f}",
                )
                st.progress(
                    scores.get("coherence", 0.0),
                    text=f"Coherence: {scores.get('coherence', 0.0):.2f}",
                )
                st.progress(
                    scores.get("faithfulness", 0.0),
                    text=f"Faithfulness: {scores.get('faithfulness', 0.0):.2f}",
                )

                warnings = final_state.get("warnings", [])
                if warnings:
                    st.warning("**Warnings:**\n" + "\n".join([f"- {w}" for w in warnings]))

# ==========================================
# TAB 2: OBSERVABILITY DASHBOARD
# ==========================================
with tab2:
    st.subheader("📈 System Observability & Execution Analytics")

    stats = get_stats()

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Tasks Run", stats["total_runs"])
    m2.metric("Pass Rate", f"{stats['pass_rate']}%")
    m3.metric("Avg Score", stats["avg_score"])
    m4.metric("Avg Revisions", stats["avg_revisions"])
    m5.metric("Avg Tool Calls", stats["avg_tool_calls_per_run"])

    st.divider()

    runs_data = get_all_runs()
    if not runs_data:
        st.info("No research runs logged yet. Execute a research query to see analytics.")
    else:
        df_runs = pd.DataFrame(runs_data)

        st.subheader("📜 Run History")
        st.dataframe(
            df_runs[
                [
                    "run_id",
                    "started_at",
                    "status",
                    "final_score",
                    "revision_count",
                    "total_tool_calls",
                    "query",
                ]
            ],
            use_container_width=True,
        )

        # Inspect specific run details
        st.subheader("🔎 Inspect Run Step Trace")
        selected_run_id = st.selectbox(
            "Select Run ID to view step-by-step trace:",
            options=df_runs["run_id"].tolist(),
        )

        if selected_run_id:
            steps = get_run_details(selected_run_id)
            if steps:
                df_steps = pd.DataFrame(steps)
                st.table(
                    df_steps[
                        [
                            "step_index",
                            "agent_name",
                            "status",
                            "latency_ms",
                            "tool_calls",
                            "timestamp",
                        ]
                    ]
                )

                # Show metadata json if present
                with st.expander("Show detailed step metadata"):
                    for step in steps:
                        if step.get("metadata_json"):
                            st.json(json.loads(step["metadata_json"]))
