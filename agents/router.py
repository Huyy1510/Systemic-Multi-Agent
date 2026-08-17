import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from graph.state import ChatState
from guardrails.limits import load_config
from utils import clean_llm_text

load_dotenv()


class RouterOutput(BaseModel):
    intent: str = Field(
        description=(
            "Exact intent classification: "
            "'product_inquiry' (asking for product advice, recommendations, prices), "
            "'product_comparison' (comparing 2 or more products), "
            "'stock_check' (asking if a specific product is in stock / inventory levels), "
            "'restock_request' (requesting to order/buy/restock products, e.g. 'đặt 30 cái', 'tạo đơn nhập hàng'), "
            "or 'off_topic' (general chitchat, weather, coding questions unrelated to products/orders)"
        )
    )
    product_names: List[str] = Field(
        default_factory=list,
        description="List of product names mentioned in the user message or conversation context",
    )
    quantity: Optional[int] = Field(
        default=None,
        description="Quantity stated by user if requesting purchase/restock (e.g. 30 for 'đặt 30 cái')",
    )
    reasoning: str = Field(description="Brief explanation of the classification decision")


class RouterAgent:
    def __init__(self, model_name: Optional[str] = None):
        self.config = load_config()
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        api_key = os.getenv("GOOGLE_API_KEY")
        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=api_key,
            temperature=0.1,
        )

    def run(self, state: ChatState) -> Dict[str, Any]:
        """LangGraph node function for Router Agent."""
        current_msg = state.get("current_message", "")
        chat_history = state.get("chat_history", [])[-self.config.max_chat_history :]

        history_str = "\n".join(
            [f"{msg.get('role', 'user')}: {msg.get('content', '')}" for msg in chat_history]
        )

        prompt = f"""You are an elite Intent Router for an ERP Sales & Inventory Chatbot.
Analyze the current user message along with recent conversation history and classify the user's intent.

Intent categories:
- "product_inquiry": User asking for product recommendations, prices, features, or browsing laptops/tech hardware.
- "product_comparison": User asking to compare 2 or more specific products (e.g. "So sánh Dell XPS 13 và MacBook Air").
- "stock_check": User asking if a specific product is available/in stock (e.g. "Còn ThinkPad X1 không?").
- "restock_request": User requesting to place a restock order, purchase, or order units (e.g. "Đặt 30 cái", "Ừ tạo đơn đi", "Tạo yêu cầu nhập 50 Dell XPS").
- "off_topic": User asking about weather, sports, politics, math, or anything unrelated to our hardware products & orders.

Recent Chat History:
{history_str if history_str else "(No previous history)"}

Current User Message: "{current_msg}"

Determine the exact intent, extract any product names mentioned, and extract numeric quantity if user requests restock/ordering.
"""

        try:
            structured_llm = self.llm.with_structured_output(RouterOutput)
            result: RouterOutput = structured_llm.invoke(prompt)

            return {
                "intent": result.intent,
                "product_names": result.product_names,
                "quantity": result.quantity,
            }
        except Exception as e:
            print(f"[RouterAgent Error] Structured output failed: {e}")
            # Fallback heuristic logic
            lower_msg = current_msg.lower()
            if any(k in lower_msg for k in ["đặt", "nhập", "order", "buy", "purchase", "cái"]):
                intent = "restock_request"
            elif any(k in lower_msg for k in ["so sánh", "compare", "vs", "khác gì"]):
                intent = "product_comparison"
            elif any(k in lower_msg for k in ["còn", "stock", "tồn kho", "hết hàng"]):
                intent = "stock_check"
            elif any(k in lower_msg for k in ["thời tiết", "weather", "chào", "hello", "code"]):
                intent = "off_topic"
            else:
                intent = "product_inquiry"

            return {
                "intent": intent,
                "product_names": [],
                "quantity": None,
                "warnings": state.get("warnings", []) + [f"Router fallback used: {e}"],
            }
