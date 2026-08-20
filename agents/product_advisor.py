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

        # Pure LLM Intent Routing (Zero Hardcoding)
        if intent == "customer_buy":
            return self._handle_customer_sale_order(current_msg, product_names, quantity)
        elif intent == "product_comparison":
            return self._handle_comparison(current_msg, product_names)
        else:
            return self._handle_inquiry(current_msg, product_names)

    def _handle_customer_sale_order(
        self, current_msg: str, product_names: List[str], quantity: Optional[int]
    ) -> Dict[str, Any]:
        """Process customer order request via Prompt-Engineered LLM response."""
        target_product = product_names[0] if product_names else current_msg
        qty = quantity if (quantity and quantity > 0) else 1

        # Check inventory first
        inv_json = query_inventory(product_name=target_product, limit=1)
        try:
            inv_items = json.loads(inv_json)
        except Exception:
            inv_items = []

        if not inv_items or "error" in inv_items[0]:
            # Fallback search product catalog
            prod_json = query_products(search_term=target_product, limit=1)
            try:
                inv_items = json.loads(prod_json)
            except Exception:
                inv_items = []

        if inv_items and isinstance(inv_items, list) and "qty_available" in inv_items[0]:
            available_qty = inv_items[0]["qty_available"]
            prod_name = inv_items[0].get("product_name") or inv_items[0].get("name", target_product)
            price_val = inv_items[0].get("list_price") or inv_items[0].get("price", 0.0)
            cat_name = inv_items[0].get("category") or "Sản phẩm ERP"
            desc_val = inv_items[0].get("description") or "N/A"

            # Case A: Out of Stock -> LLM Prompt for Polite Out-of-Stock Customer Notice
            if available_qty < qty:
                prompt_out_of_stock = f"""You are a warm, courteous, professional Sales Consultant for an ERP store (Sale Agent).
The customer requested to purchase '{prod_name}', but it is currently OUT OF STOCK (0 units in stock).

Product Details:
- Product Name: {prod_name}
- Category: {cat_name}
- Price: {price_val:,.0f} VND
- Description: {desc_val}

Instructions:
1. Respond in the same language as the customer (Vietnamese/English).
2. Politely inform the customer that '{prod_name}' is currently out of stock.
3. Reassure the customer that our ERP system has automatically notified our Procurement Department to import fresh inventory as soon as possible.
4. Invite them to leave contact or ask about alternative products.
5. DO NOT include any internal technical debug logs, draft PO numbers, LLM instructions, or Slack status.

Customer Message: "{current_msg}"
"""
                try:
                    res = self.llm.invoke(prompt_out_of_stock)
                    response = clean_llm_text(res.content)
                except Exception as e:
                    print(f"[ProductAdvisor Error] Out-of-stock LLM failed: {e}")
                    response = f"Kính chào Quý khách,\n\nRất tiếc sản phẩm **{prod_name}** hiện tại đang tạm hết hàng trong kho. Hệ thống đã tự động gửi thông báo đến Bộ phận Mua hàng để nhập bổ sung sản phẩm trong thời gian sớm nhất.\n\nTrân trọng,\n**Đội ngũ Tư vấn Bán hàng ERP**"

                return {
                    "response": response,
                    "stock_status": "out_of_stock",
                    "out_of_stock_product": prod_name,
                    "needs_restock_signal": True,
                }

            # Case B: In Stock -> Create Draft Sale Order + LLM Prompt for Natural Closing Response
            so_res = create_sale_order(product_name=prod_name, quantity=qty, customer_name="Khách Hàng Retail")
            if so_res.get("success"):
                so_code = so_res.get("order_name", "SO-DRAFT")

                # Send Slack notification to sales team silently
                send_slack_notification(
                    order_code=so_code,
                    order_type="sale_order",
                    product_name=prod_name,
                    quantity=qty,
                    status="Draft (Chờ nhân viên sales duyệt)",
                )

                prompt_in_stock = f"""You are a warm, courteous Sales Consultant for an ERP store (Sale Agent).
The customer has placed an order for '{prod_name}' ({qty} unit(s)).

Order Details:
- Product Name: {prod_name}
- Quantity: {qty} unit(s)
- Unit Price: {price_val:,.0f} VND

Instructions:
1. Respond in the same language as the customer (Vietnamese/English).
2. Warmly confirm the order details: Product Name, Quantity, and Price.
3. Stop naturally after confirming the product quantity & price.
4. Add 1-2 polite closing sentences thanking the customer and assuring them that our Sales team will contact them shortly to process delivery.
5. DO NOT mention internal system jargon, internal order codes (like {so_code}), Odoo menu paths, draft statuses, or Slack notifications. Keep it 100% customer-facing and natural.

Customer Message: "{current_msg}"
"""
                try:
                    res = self.llm.invoke(prompt_in_stock)
                    response = clean_llm_text(res.content)
                except Exception as e:
                    print(f"[ProductAdvisor Error] In-stock LLM failed: {e}")
                    response = f"Cảm ơn Quý khách đã đặt hàng! Chúng tôi xin xác nhận đơn hàng **{prod_name}** với số lượng **{qty} cái**. Đội ngũ Bán hàng sẽ nhanh chóng liên hệ với bạn để hỗ trợ giao hàng!"

                return {
                    "response": response,
                    "stock_status": "in_stock",
                    "sale_order_created": so_code,
                    "needs_restock_signal": False,
                }
            else:
                err = so_res.get("error", "Lỗi không xác định")
                return {
                    "response": f"Dạ, tạo đơn bán hàng cho sản phẩm '{prod_name}' thất bại: {err}",
                    "needs_restock_signal": False,
                }

        # Product not found
        return {
            "response": f"Dạ, không tìm thấy thông tin sản phẩm '{target_product}' trong hệ thống Odoo.",
            "needs_restock_signal": False,
        }

    def _handle_inquiry(self, current_msg: str, product_names: List[str]) -> Dict[str, Any]:
        """Query Odoo for product recommendations and build natural language response via LLM."""
        search_term = product_names[0] if product_names else ""
        raw_products = query_products(search_term=search_term, limit=10)

        out_of_stock_prod = None
        try:
            p_list = json.loads(raw_products)
            if isinstance(p_list, list):
                for p in p_list:
                    if p.get("qty_available", 1) == 0:
                        out_of_stock_prod = p.get("name") or search_term
                        break
        except Exception:
            pass

        prompt = f"""You are a professional, helpful ERP Sales Consultant (Sale Agent).
Answer the customer's inquiry based strictly on our internal Odoo ERP product catalog below.

Rules:
1. Respond in the same language as the customer's message (Vietnamese or English).
2. List available products with price (formatted nicely in VND), stock availability (`qty_available`), and brief specs/description.
3. If a product is out of stock (`qty_available == 0`), explicitly note that it is out of stock and inform the customer that our system automatically notifies the Procurement Department to restock.
4. Keep the tone courteous, professional, and natural. DO NOT mention internal debug logs or system order codes.

Customer Message: "{current_msg}"

Odoo Product Catalog Data:
{raw_products}
"""
        try:
            res = self.llm.invoke(prompt)
            clean_resp = clean_llm_text(res.content)
        except Exception as e:
            print(f"[ProductAdvisor Error] Inquiry LLM failed: {e}")
            clean_resp = f"Dạ, đây là danh sách sản phẩm từ hệ thống Odoo ERP:\n```json\n{raw_products}\n```"

        if out_of_stock_prod:
            return {
                "response": clean_resp,
                "stock_status": "out_of_stock",
                "out_of_stock_product": out_of_stock_prod,
                "needs_restock_signal": True,
            }

        return {"response": clean_resp, "needs_restock_signal": False}

    def _handle_comparison(self, current_msg: str, product_names: List[str]) -> Dict[str, Any]:
        """Query Odoo for 2+ products and build a structured Markdown comparison table via LLM."""
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
            clean_resp = clean_llm_text(res.content)
        except Exception as e:
            print(f"[ProductAdvisor Error] Comparison LLM failed: {e}")
            clean_resp = f"Bảng so sánh sản phẩm Odoo ERP:\n```json\n{catalog_str}\n```"

        return {"response": clean_resp, "needs_restock_signal": False}
