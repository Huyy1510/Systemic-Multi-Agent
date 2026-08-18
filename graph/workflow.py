import json
import time
import uuid
from typing import Any, Dict, List, Optional
from langgraph.graph import END, START, StateGraph

from agents.inventory_checker import InventoryCheckerAgent
from agents.product_advisor import ProductAdvisorAgent
from agents.restock_agent import RestockAgent
from agents.router import RouterAgent
from graph.state import ChatState
from guardrails.limits import load_config
from observability import init_db, log_run_summary, log_step


def router_node(state: ChatState) -> Dict[str, Any]:
    """Node: Route intent and extract entities."""
    start_t = time.time()
    agent = RouterAgent()
    result = agent.run(state)
    latency_ms = int((time.time() - start_t) * 1000)

    log_step(
        run_id=state.get("run_id", "default"),
        step_index=1,
        agent_name="RouterAgent",
        latency_ms=latency_ms,
        tool_calls=0,
        status="success",
        metadata_json=json.dumps({"intent": result.get("intent"), "product_names": result.get("product_names")}),
    )
    return result


def product_advisor_node(state: ChatState) -> Dict[str, Any]:
    """Node (Sale Agent): Provide product recommendations, comparison tables, or customer Sale Orders."""
    start_t = time.time()
    agent = ProductAdvisorAgent()
    result = agent.run(state)
    latency_ms = int((time.time() - start_t) * 1000)

    log_step(
        run_id=state.get("run_id", "default"),
        step_index=2,
        agent_name="ProductAdvisorAgent (Sale Agent)",
        latency_ms=latency_ms,
        tool_calls=1,
        status="success",
        metadata_json=json.dumps(
            {
                "intent": state.get("intent"),
                "needs_restock_signal": result.get("needs_restock_signal", False),
                "sale_order_created": result.get("sale_order_created"),
            }
        ),
    )
    return result


def inventory_checker_node(state: ChatState) -> Dict[str, Any]:
    """Node: Check product stock in Odoo inventory."""
    start_t = time.time()
    agent = InventoryCheckerAgent()
    result = agent.run(state)
    latency_ms = int((time.time() - start_t) * 1000)

    log_step(
        run_id=state.get("run_id", "default"),
        step_index=2,
        agent_name="InventoryCheckerAgent",
        latency_ms=latency_ms,
        tool_calls=1,
        status="success",
        metadata_json=json.dumps(
            {
                "stock_status": result.get("stock_status"),
                "needs_restock_signal": result.get("needs_restock_signal", False),
            }
        ),
    )
    return result


def restock_node(state: ChatState) -> Dict[str, Any]:
    """Node (Procurement Agent): Receive restock signal and create Draft Purchase Order (purchase.order) on Odoo."""
    start_t = time.time()
    agent = RestockAgent()
    result = agent.run(state)
    latency_ms = int((time.time() - start_t) * 1000)

    # Append Procurement Agent's status update to state response
    current_resp = state.get("response", "")
    proc_resp = result.get("response", "")

    if current_resp and proc_resp:
        combined_response = f"{current_resp}\n\n---\n{proc_resp}"
    else:
        combined_response = proc_resp or current_resp

    log_step(
        run_id=state.get("run_id", "default"),
        step_index=3 if state.get("needs_restock_signal") else 2,
        agent_name="RestockAgent (Procurement Agent)",
        latency_ms=latency_ms,
        tool_calls=1,
        status="success",
        metadata_json=json.dumps({"po_created": result.get("restock_po_created")}),
    )

    return {
        "response": combined_response,
        "restock_po_created": result.get("restock_po_created"),
    }


def guardrail_node(state: ChatState) -> Dict[str, Any]:
    """Node: Block off-topic messages and provide guidance."""
    start_t = time.time()
    latency_ms = int((time.time() - start_t) * 1000)
    response = (
        "Dạ, tôi là Trợ lý Bán hàng & Tư vấn Odoo ERP. "
        "Tôi chỉ hỗ trợ các thông tin về sản phẩm, giá bán, tồn kho và lên đơn hàng. "
        "Bạn cần tư vấn sản phẩm nào ạ?"
    )

    log_step(
        run_id=state.get("run_id", "default"),
        step_index=2,
        agent_name="GuardrailNode",
        latency_ms=latency_ms,
        tool_calls=0,
        status="blocked",
        metadata_json=json.dumps({"intent": "off_topic"}),
    )
    return {"response": response}


def route_intent(state: ChatState) -> str:
    """Conditional edge router based on intent classification."""
    intent = state.get("intent", "off_topic")
    if intent in ("product_inquiry", "product_comparison"):
        return "product_advisor"
    elif intent == "stock_check":
        return "inventory_checker"
    elif intent == "restock_request":
        return "restock"
    else:
        return "guardrail"


def route_restock_signal(state: ChatState) -> str:
    """Conditional edge: Route to ProcurementAgent if restock signal was raised by SaleAgent / StockChecker."""
    if state.get("needs_restock_signal", False):
        return "restock"
    return END


def build_graph():
    """Construct and compile the Chatbot StateGraph with SaleAgent ➔ ProcurementAgent handoff."""
    builder = StateGraph(ChatState)

    builder.add_node("router", router_node)
    builder.add_node("product_advisor", product_advisor_node)
    builder.add_node("inventory_checker", inventory_checker_node)
    builder.add_node("restock", restock_node)
    builder.add_node("guardrail", guardrail_node)

    builder.add_edge(START, "router")
    builder.add_conditional_edges(
        "router",
        route_intent,
        {
            "product_advisor": "product_advisor",
            "inventory_checker": "inventory_checker",
            "restock": "restock",
            "guardrail": "guardrail",
        },
    )

    # Chaining: product_advisor & inventory_checker can trigger ProcurementAgent if item is out of stock
    builder.add_conditional_edges(
        "product_advisor",
        route_restock_signal,
        {
            "restock": "restock",
            END: END,
        },
    )

    builder.add_conditional_edges(
        "inventory_checker",
        route_restock_signal,
        {
            "restock": "restock",
            END: END,
        },
    )

    builder.add_edge("restock", END)
    builder.add_edge("guardrail", END)

    return builder.compile()


def chat(
    message: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute one chat turn through the LangGraph state machine."""
    init_db()
    config = load_config()
    run_id = run_id or f"chat-{uuid.uuid4().hex[:8]}"
    chat_history = (chat_history or [])[-config.max_chat_history :]

    graph = build_graph()
    initial_state: ChatState = {
        "current_message": message,
        "chat_history": chat_history,
        "intent": "off_topic",
        "product_names": [],
        "quantity": None,
        "stock_status": "unknown",
        "out_of_stock_product": "",
        "needs_restock_signal": False,
        "restock_po_created": None,
        "sale_order_created": None,
        "response": "",
        "run_id": run_id,
        "warnings": [],
    }

    from datetime import datetime

    started_at = datetime.now().isoformat()
    start_t = time.time()
    final_state = graph.invoke(initial_state)
    finished_at = datetime.now().isoformat()

    log_run_summary(
        run_id=run_id,
        query=message,
        started_at=started_at,
        finished_at=finished_at,
        status="passed" if final_state.get("intent") != "off_topic" else "warning",
        total_tool_calls=1 if final_state.get("intent") != "off_topic" else 0,
        final_score=1.0 if final_state.get("intent") != "off_topic" else 0.5,
        revision_count=0,
        report_markdown=final_state.get("response", ""),
    )

    return final_state
