import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from graph.state import ChatState
from guardrails.limits import load_config

load_dotenv()


class RouterOutput(BaseModel):
    intent: str = Field(
        description=(
            "Exact intent classification across any language (Vietnamese, English, etc.):\n"
            "- 'customer_buy': User expresses any intent to purchase, buy, order, or request an item for themselves (e.g. 'Cho tôi 1 cái', 'Tôi muốn mua 2 chiếc', 'Ship me 1 unit', 'Order 2 XPS').\n"
            "- 'product_inquiry': User asks for recommendations, prices, features, descriptions, or browses hardware products.\n"
            "- 'product_comparison': User asks to compare 2 or more products (e.g. 'So sánh Dell XPS và MacBook').\n"
            "- 'stock_check': User specifically asks if a product is in stock or available in inventory (e.g. 'Còn ThinkPad X1 không?').\n"
            "- 'off_topic': User asks about weather, sports, coding, chitchat, or unrelated topics."
        )
    )
    product_names: List[str] = Field(
        default_factory=list,
        description="List of product names mentioned in the user message or conversation context",
    )
    quantity: Optional[int] = Field(
        default=None,
        description="Quantity requested by user if ordering/purchasing (e.g. 1 for 'Cho tôi 1 cái')",
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
        """LangGraph node function for Router Agent using Gemini Structured Output."""
        current_msg = state.get("current_message", "")
        chat_history = state.get("chat_history", [])[-self.config.max_chat_history :]

        history_str = "\n".join(
            [f"{msg.get('role', 'user')}: {msg.get('content', '')}" for msg in chat_history]
        )

        prompt = f"""You are an intelligent Intent Classifier for an ERP Sales Chatbot.
Analyze the user's input in ANY language and classify the intent into exactly one of:
- "customer_buy": User expresses any request to buy, order, get, take, or purchase items (e.g., "Cho tôi 1 cái Large Desk", "Tôi muốn mua 2 XPS", "I'd like 1 MacBook").
- "product_inquiry": User asks about product recommendations, specs, pricing, or catalog browsing.
- "product_comparison": User asks to compare two or more products.
- "stock_check": User asks strictly whether a product is currently in stock / available in inventory.
- "off_topic": Unrelated chitchat, weather, math, code questions.

Recent Chat History:
{history_str if history_str else "(No previous history)"}

Current User Input: "{current_msg}"

Output the structured intent classification, extracted product names, and numeric quantity.
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
            return {
                "intent": "product_inquiry",
                "product_names": [],
                "quantity": None,
                "warnings": state.get("warnings", []) + [f"Router LLM fallback used: {e}"],
            }
