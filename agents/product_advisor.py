import json
import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from graph.state import ChatState
from mcp_server.odoo_tools import query_inventory, query_products
from utils import clean_llm_text

load_dotenv()


class ProductAdvisorAgent:
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        api_key = os.getenv("GOOGLE_API_KEY")
        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=api_key,
            temperature=0.2,
        )

    def run(self, state: ChatState) -> Dict[str, Any]:
        """LangGraph node function for Product Advisor Agent."""
        intent = state.get("intent", "product_inquiry")
        current_msg = state.get("current_message", "")
        product_names = state.get("product_names", [])

        if intent == "product_comparison":
            response = self._handle_comparison(current_msg, product_names)
        else:
            response = self._handle_inquiry(current_msg, product_names)

        return {"response": response}

    def _handle_inquiry(self, current_msg: str, product_names: List[str]) -> str:
        """Query Odoo for product recommendations and build natural language response."""
        search_term = product_names[0] if product_names else ""
        raw_products = query_products(search_term=search_term, limit=10)

        prompt = f"""You are a professional, helpful ERP Sales Product Consultant.
Answer the customer's inquiry based strictly on our internal Odoo ERP product catalog below.

Rules:
1. Respond in the same language as the customer's message (Vietnamese or English).
2. List available products with price (formatted nicely in VND or USD), stock availability (`qty_available`), and brief specs/description.
3. If a product is out of stock (`qty_available == 0`), explicitly note that it is out of stock and let the user know they can request a restock/purchase order.
4. Keep the tone courteous, professional, and clear.

Customer Message: "{current_msg}"

Odoo Product Catalog Data:
{raw_products}
"""
        try:
            res = self.llm.invoke(prompt)
            return clean_llm_text(res.content)
        except Exception as e:
            print(f"[ProductAdvisor Error] Inquiry LLM failed: {e}")
            return f"Dạ, đây là danh sách sản phẩm từ hệ thống Odoo ERP:\n```json\n{raw_products}\n```"

    def _handle_comparison(self, current_msg: str, product_names: List[str]) -> str:
        """Query Odoo for 2+ products and build a structured Markdown comparison table."""
        product_datas = []
        if product_names:
            for pname in product_names[:4]:
                p_json = query_products(search_term=pname, limit=2)
                try:
                    items = json.loads(p_json)
                    if items and isinstance(items, list) and "error" not in items[0]:
                        product_datas.extend(items)
                except Exception:
                    pass

        # If product_names search didn't yield items, fetch all products
        if not product_datas:
            all_json = query_products(limit=6)
            try:
                product_datas = json.loads(all_json)
            except Exception:
                product_datas = []

        catalog_str = json.dumps(product_datas, ensure_ascii=False)

        prompt = f"""You are an expert Hardware Product Consultant.
Compare the products requested by the user based strictly on the Odoo ERP database below.

Requirements:
1. Respond in the same language as the user (Vietnamese or English).
2. Generate a clean, structured Markdown Comparison Table comparing key attributes:
   | Metric / Attribute | Product A | Product B | ... |
   | Price | ... | ... |
   | Stock Available | ... | ... |
   | Category & Specs | ... | ... |
3. Provide a clear, objective conclusion recommending which product fits best based on user needs.

User Message: "{current_msg}"

Odoo Product Data:
{catalog_str}
"""
        try:
            res = self.llm.invoke(prompt)
            return clean_llm_text(res.content)
        except Exception as e:
            print(f"[ProductAdvisor Error] Comparison LLM failed: {e}")
            return f"Bảng so sánh sản phẩm Odoo ERP:\n```json\n{catalog_str}\n```"
