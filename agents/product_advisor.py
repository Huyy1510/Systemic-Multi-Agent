import json
import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from graph.state import ChatState
from integrations import send_slack_notification
from mcp_server.odoo_tools import create_sale_order, query_inventory, query_products
from utils import clean_llm_text

load_dotenv()


class ProductAdvisorAgent:
    """Sale Agent: Consults products, generates comparison tables, and creates Draft Sale Orders (sale.order) for customers."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        api_key = os.getenv("GOOGLE_API_KEY")
        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=api_key,
            temperature=0.2,
        )

    def run(self, state: ChatState) -> Dict[str, Any]:
        """LangGraph node function for Product Advisor (Sale Agent)."""
        intent = state.get("intent", "product_inquiry")
        current_msg = state.get("current_message", "")
        product_names = state.get("product_names", [])
        quantity = state.get("quantity")

        # Check if user wants to place a customer Sale Order (buy)
        lower_msg = current_msg.lower()
        if any(k in lower_msg for k in ["mua", "đặt mua", "lấy", "chốt đơn", "buy"]):
            return self._handle_customer_sale_order(current_msg, product_names, quantity)

        if intent == "product_comparison":
            response = self._handle_comparison(current_msg, product_names)
            return {"response": response, "needs_restock_signal": False}
        else:
            response = self._handle_inquiry(current_msg, product_names)
            return {"response": response, "needs_restock_signal": False}

    def _handle_customer_sale_order(
        self, current_msg: str, product_names: List[str], quantity: Optional[int]
    ) -> Dict[str, Any]:
        """Process customer order request. Create Draft Sale Order if in stock, or signal Procurement if out of stock."""
        target_product = product_names[0] if product_names else current_msg
        qty = quantity if (quantity and quantity > 0) else 1

        # Check inventory first
        inv_json = query_inventory(product_name=target_product, limit=1)
        try:
            inv_items = json.loads(inv_json)
        except Exception:
            inv_items = []

        if inv_items and "qty_available" in inv_items[0]:
            available_qty = inv_items[0]["qty_available"]
            prod_name = inv_items[0].get("product_name", target_product)

            if available_qty < qty:
                # Out of stock or insufficient stock -> Notify customer & Signal Procurement
                response = (
                    f"❌ **{prod_name}**: Rất tiếc sản phẩm hiện chỉ còn {int(available_qty)} cái (không đủ {qty} cái bạn cần).\n\n"
                    f"📢 *Tôi (Sale Agent) đã gửi thông báo yêu cầu Restock hàng tới Bộ phận Mua hàng (Procurement Agent) để lên đơn nhập kho từ Nhà cung cấp.*"
                )
                return {
                    "response": response,
                    "stock_status": "out_of_stock",
                    "out_of_stock_product": prod_name,
                    "needs_restock_signal": True,
                }

            # In stock -> Create Draft Sale Order (sale.order)
            so_res = create_sale_order(product_name=prod_name, quantity=qty, customer_name="Khách Hàng Retail")
            if so_res.get("success"):
                so_code = so_res.get("order_name", "SO-DRAFT")

                # Send Slack notification to sales team
                send_slack_notification(
                    order_code=so_code,
                    order_type="sale_order",
                    product_name=prod_name,
                    quantity=qty,
                    status="Draft (Chờ nhân viên sales duyệt)",
                )

                response = (
                    f"🛒 **Đã tạo thành công Đơn Bán Hàng (Draft Sale Order)!**\n\n"
                    f"- **Sản phẩm**: {prod_name}\n"
                    f"- **Số lượng mua**: {qty} cái\n"
                    f"- **Mã đơn hàng Odoo**: `{so_code}`\n"
                    f"- **Trạng thái**: ⏳ **Bản thảo (Chờ nhân viên duyệt xuất kho)**\n\n"
                    f"💬 *Đã bắn thông báo nhắc nhở nhân viên Sales trên kênh Slack!*"
                    f"ℹ️ *Đơn hàng bán đã được lưu trên Odoo tại menu `Sales -> Orders`. Nhân viên bán hàng chỉ cần kiểm tra và bấm 'Confirm Order' để xuất kho cho bạn.*"
                )
                return {
                    "response": response,
                    "stock_status": "in_stock",
                    "sale_order_created": so_code,
                    "needs_restock_signal": False,
                }
            else:
                err = so_res.get("error", "Lỗi không xác định")
                return {
                    "response": f"❌ Tạo đơn bán hàng thất bại: {err}",
                    "needs_restock_signal": False,
                }

        # Product not found
        return {
            "response": f"Dạ, không tìm thấy thông tin sản phẩm '{target_product}' trong hệ thống Odoo.",
            "needs_restock_signal": False,
        }

    def _handle_inquiry(self, current_msg: str, product_names: List[str]) -> str:
        """Query Odoo for product recommendations and build natural language response."""
        search_term = product_names[0] if product_names else ""
        raw_products = query_products(search_term=search_term, limit=10)

        prompt = f"""You are a professional, helpful ERP Sales Consultant (Sale Agent).
Answer the customer's inquiry based strictly on our internal Odoo ERP product catalog below.

Rules:
1. Respond in the same language as the customer's message (Vietnamese or English).
2. List available products with price (formatted nicely in VND), stock availability (`qty_available`), and brief specs/description.
3. If a product is out of stock (`qty_available == 0`), explicitly note that it is out of stock and inform the customer that our system automatically notifies the Procurement Department to restock.
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

        if not product_datas:
            all_json = query_products(limit=6)
            try:
                product_datas = json.loads(all_json)
            except Exception:
                product_datas = []

        catalog_str = json.dumps(product_datas, ensure_ascii=False)

        prompt = f"""You are an expert Hardware Product Consultant (Sale Agent).
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
