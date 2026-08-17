import os
from typing import Any, Dict, Optional
from dotenv import load_dotenv

from graph.state import ChatState
from guardrails.limits import load_config
from mcp_server.odoo_tools import create_purchase_order

load_dotenv()


class RestockAgent:
    def __init__(self):
        self.config = load_config()

    def run(self, state: ChatState) -> Dict[str, Any]:
        """LangGraph node function for Restock Agent."""
        product_names = state.get("product_names", [])
        out_of_stock_prod = state.get("out_of_stock_product", "")
        quantity = state.get("quantity")

        target_product = (
            out_of_stock_prod
            if out_of_stock_prod
            else (product_names[0] if product_names else "sản phẩm")
        )

        if not quantity:
            # Check if user mentioned number in message
            current_msg = state.get("current_message", "")
            import re
            nums = re.findall(r"\b\d+\b", current_msg)
            if nums:
                quantity = int(nums[0])

        if not quantity or quantity <= 0:
            return {
                "response": (
                    f"Dạ, bạn muốn tạo đơn nhập hàng cho **{target_product}** với số lượng bao nhiêu? "
                    f"(Ví dụ: 'Đặt 30 cái')"
                )
            }

        # Cap quantity at max_restock_quantity
        if quantity > self.config.max_restock_quantity:
            quantity = self.config.max_restock_quantity

        # Create draft purchase order on Odoo
        res = create_purchase_order(product_name=target_product, quantity=quantity)

        if res.get("success"):
            order_name = res.get("order_name", "PO-DRAFT")
            response = (
                f"✅ **Đã tạo thành công Yêu cầu Nhập hàng (Draft Purchase Order)!**\n\n"
                f"- **Sản phẩm**: {target_product}\n"
                f"- **Số lượng đặt**: {quantity} đơn vị\n"
                f"- **Mã đơn hàng Odoo**: `{order_name}`\n"
                f"- **Trạng thái**: ⏳ **Draft (Chờ nhân viên duyệt)**\n\n"
                f"ℹ️ *Đơn hàng đã được lưu trên Odoo tại menu `Purchase -> Orders`. Nhân viên quản lý kho chỉ cần kiểm tra và bấm 'Confirm Order' để tiến hành nhập kho.*"
            )
        else:
            err = res.get("error", "Unknown error")
            response = f"❌ **Tạo đơn nhập hàng thất bại**: {err}"

        return {"response": response}
