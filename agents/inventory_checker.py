import json
import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

from graph.state import ChatState
from mcp_server.odoo_tools import query_inventory

load_dotenv()


class InventoryCheckerAgent:
    """Agent: Checks product stock in Odoo inventory."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

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
                "needs_restock_signal": False,
            }

        # Check stock status of matching item
        match_item = items[0]
        prod_name = match_item.get("product_name", target_product)
        qty = match_item.get("qty_available", 0.0)

        if qty > 0:
            response = (
                f"✅ **{prod_name}**: Hiện tại còn **{int(qty)}** sản phẩm trong kho Odoo.\n"
                f"Giá niêm yết: {match_item.get('price', 0):,.0f} VND. "
                f"Bạn có muốn đặt mua (tạo đơn hàng Sale Order) không?"
            )
            return {
                "response": response,
                "stock_status": "in_stock",
                "needs_restock_signal": False,
            }
        else:
            response = (
                f"❌ **{prod_name}**: Hiện tại sản phẩm đang **tạm hết hàng** trong kho Odoo.\n"
                f"📢 *Tôi đã tự động gửi thông báo nhu cầu Restock sản phẩm này tới Bộ phận Mua hàng & Quản lý Kho (Procurement Agent) để tạo đơn nhập hàng từ Nhà cung cấp.*"
            )
            return {
                "response": response,
                "stock_status": "out_of_stock",
                "out_of_stock_product": prod_name,
                "needs_restock_signal": True,
            }
