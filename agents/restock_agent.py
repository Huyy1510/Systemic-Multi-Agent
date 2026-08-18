import os
from typing import Any, Dict, Optional
from dotenv import load_dotenv

from graph.state import ChatState
from guardrails.limits import load_config
from mcp_server.odoo_tools import create_purchase_order

load_dotenv()


class RestockAgent:
    """Procurement Agent (Back-office Agent): Receives restock signals from Sale Agent and automatically creates Draft Purchase Orders (purchase.order) on Odoo for staff review."""

    def __init__(self):
        self.config = load_config()

    def run(self, state: ChatState) -> Dict[str, Any]:
        """LangGraph node function for Procurement / Restock Agent."""
        product_names = state.get("product_names", [])
        out_of_stock_prod = state.get("out_of_stock_product", "")
        quantity = state.get("quantity")

        target_product = (
            out_of_stock_prod
            if out_of_stock_prod
            else (product_names[0] if product_names else "sản phẩm")
        )

        # Default restock batch quantity if not specified
        restock_qty = quantity if (quantity and quantity > 0) else 20

        if restock_qty > self.config.max_restock_quantity:
            restock_qty = self.config.max_restock_quantity

        # Create draft purchase order on Odoo (purchase.order)
        res = create_purchase_order(product_name=target_product, quantity=restock_qty)

        if res.get("success"):
            order_name = res.get("order_name", "PO-DRAFT")
            # If triggered via explicit user request
            response = (
                f"✅ **[Procurement Agent] Đã tạo thành công Yêu cầu Nhập hàng (Draft Purchase Order)!**\n\n"
                f"- **Sản phẩm nhập**: {target_product}\n"
                f"- **Số lượng lô nhập**: {restock_qty} đơn vị\n"
                f"- **Mã đơn mua hàng Odoo**: `{order_name}`\n"
                f"- **Trạng thái**: ⏳ **Draft (Chờ nhân viên kho kiểm tra & duyệt)**\n\n"
                f"ℹ️ *Đơn hàng nhập đã được chuyển lên Odoo tại menu `Purchase -> Orders`. Quản lý kho chỉ cần bấm 'Confirm Order' để xác nhận đặt hàng với Nhà cung cấp.*"
            )
            return {
                "response": response,
                "restock_po_created": order_name,
            }
        else:
            err = res.get("error", "Unknown error")
            response = f"❌ **[Procurement Agent] Tạo đơn nhập hàng thất bại**: {err}"
            return {"response": response}
