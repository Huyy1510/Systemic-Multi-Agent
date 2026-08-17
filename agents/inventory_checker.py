import json
import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from graph.state import ChatState
from mcp_server.odoo_tools import query_inventory
from utils import clean_llm_text

load_dotenv()


class InventoryCheckerAgent:
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        api_key = os.getenv("GOOGLE_API_KEY")
        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=api_key,
            temperature=0.1,
        )

    def run(self, state: ChatState) -> Dict[str, Any]:
        """LangGraph node function for Inventory Checker Agent."""
        product_names = state.get("product_names", [])
        current_msg = state.get("current_message", "")

        target_product = product_names[0] if product_names else current_msg

        raw_inventory = query_inventory(product_name=target_product, limit=5)
        try:
            items = json.loads(raw_inventory)
        except Exception:
            items = []

        if not items or "error" in items[0]:
            return {
                "response": f"Dạ, không tìm thấy thông tin sản phẩm '{target_product}' trong hệ thống Odoo kho.",
                "stock_status": "unknown",
            }

        # Check stock status of matching item
        match_item = items[0]
        prod_name = match_item.get("product_name", target_product)
        qty = match_item.get("qty_available", 0.0)

        if qty > 0:
            response = (
                f"✅ **{prod_name}**: Hiện tại còn **{int(qty)}** sản phẩm trong kho Odoo.\n"
                f"Giá niêm yết: {match_item.get('price', 0):,.0f} VND. Bạn có cần đặt hàng không?"
            )
            return {
                "response": response,
                "stock_status": "in_stock",
            }
        else:
            response = (
                f"❌ **{prod_name}**: Hiện tại đã **hết hàng** trong kho Odoo.\n"
                f"Bạn có muốn tôi tạo yêu cầu nhập hàng (Purchase Order draft) cho sản phẩm này không? "
                f"Nếu có, xin vui lòng cho biết số lượng cần đặt (ví dụ: 'Đặt 30 cái')."
            )
            return {
                "response": response,
                "stock_status": "out_of_stock",
                "out_of_stock_product": prod_name,
            }
