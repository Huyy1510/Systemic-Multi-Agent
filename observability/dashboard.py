import json
import os
import sys
import pandas as pd
import streamlit as st

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from graph import chat
from mcp_server.odoo_tools import check_odoo_connection
from observability.logger import get_all_runs, get_run_details, init_db

st.set_page_config(
    page_title="ERP Sales Chatbot Assistant",
    page_icon="🤖",
    layout="wide",
)

init_db()

st.title("🤖 Odoo ERP Sales & Inventory Chatbot")
st.caption("Multi-Agent Sales Consultant, Inventory Tracker & Purchase Order Automation")

tab1, tab2 = st.tabs(["💬 Chat Workspace", "📊 Observability Dashboard"])

# ==========================================
# TAB 1: CHAT WORKSPACE
# ==========================================
with tab1:
    col_chat, col_sidebar = st.columns([3, 1])

    with col_sidebar:
        st.subheader("⚙️ System Status")
        is_odoo_online = check_odoo_connection()

        if is_odoo_online:
            st.success("🏢 **Odoo ERP Connected**\n\nLive XML-RPC Connection Active")
        else:
            st.warning("⚠️ **Odoo ERP Offline**\n\nServer unreachable at http://localhost:8069")

        st.divider()
        st.subheader("🔍 Active Session Info")

        if "last_intent" in st.session_state:
            st.info(f"**Intent Detected:**\n`{st.session_state.last_intent}`")
        if "last_products" in st.session_state and st.session_state.last_products:
            st.write(f"**Products Extracted:**\n{', '.join(st.session_state.last_products)}")
        if "last_stock_status" in st.session_state and st.session_state.last_stock_status:
            st.write(f"**Stock Status:**\n`{st.session_state.last_stock_status}`")

        if st.button("🗑️ Clear Chat History"):
            st.session_state.chat_history = []
            st.session_state.pop("last_intent", None)
            st.session_state.pop("last_products", None)
            st.session_state.pop("last_stock_status", None)
            st.rerun()

    with col_chat:
        st.subheader("Chat with Sales Assistant")

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = [
                {
                    "role": "assistant",
                    "content": (
                        "Xin chào! Tôi là Trợ lý Tư vấn Bán hàng & Quản lý Kho Odoo ERP. "
                        "Tôi có thể giúp bạn tìm kiếm laptop, so sánh sản phẩm, kiểm tra tồn kho và tạo yêu cầu nhập hàng. "
                        "Bạn cần hỗ trợ gì hôm nay?"
                    ),
                }
            ]

        # Render chat messages
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # Input box
        if prompt := st.chat_input("Nhập yêu cầu (ví dụ: 'Tư vấn laptop 20 triệu', 'So sánh Dell XPS với Mac Air', 'Đặt 30 ThinkPad X1')..."):
            # Display user message
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            # Generate response via graph.chat
            with st.chat_message("assistant"):
                with st.spinner("🤖 Đang kiểm tra Odoo ERP & phân tích..."):
                    history_payload = [
                        {"role": m["role"], "content": m["content"]}
                        for m in st.session_state.chat_history[:-1]
                    ]
                    result = chat(message=prompt, chat_history=history_payload)
                    bot_response = result.get("response", "Dạ, tôi chưa nhận được phản hồi.")

                    st.markdown(bot_response)

                    # Update sidebar metadata in session_state
                    st.session_state.last_intent = result.get("intent", "N/A")
                    st.session_state.last_products = result.get("product_names", [])
                    st.session_state.last_stock_status = result.get("stock_status", "N/A")

            # Append bot response to history
            st.session_state.chat_history.append({"role": "assistant", "content": bot_response})
            st.rerun()

# ==========================================
# TAB 2: OBSERVABILITY DASHBOARD
# ==========================================
with tab2:
    st.subheader("📊 Multi-Agent System Analytics")

    runs = get_all_runs(limit=100)
    if not runs:
        st.info("No chat logs recorded in SQLite database yet.")
    else:
        df_runs = pd.DataFrame(runs)

        # Metrics overview
        total_chats = len(df_runs)
        passed_chats = len(df_runs[df_runs["status"] == "passed"])
        pass_rate = round((passed_chats / total_chats) * 100, 1) if total_chats > 0 else 0.0

        col1, col2, col3 = st.columns(3)
        col1.metric("Total User Turn Executions", total_chats)
        col2.metric("On-Topic Success Rate", f"{pass_rate}%")
        col3.metric("SQLite DB File", "observability.db")

        st.divider()

        display_cols = [c for c in ["run_id", "started_at", "query", "status", "total_tool_calls"] if c in df_runs.columns]
        st.dataframe(
            df_runs[display_cols],
            use_container_width=True,
        )

        st.divider()

        st.subheader("🔍 Inspect Step Trajectory Trace")
        selected_run_id = st.selectbox(
            "Select Run ID to Inspect:",
            options=df_runs["run_id"].tolist(),
        )

        if selected_run_id:
            steps = get_run_details(selected_run_id)
            if not steps:
                st.info("No step trajectory details found for this run.")
            else:
                for step in steps:
                    agent_name = step.get("agent_name", "Agent")
                    status = step.get("status", "success")
                    latency = step.get("latency_ms", 0)

                    with st.expander(
                        f"Step {step.get('step_number')}: {agent_name} | Latency: {latency}ms | Status: {status}"
                    ):
                        meta = step.get("metadata_json", "{}")
                        try:
                            st.json(json.loads(meta))
                        except Exception:
                            st.text(meta)
