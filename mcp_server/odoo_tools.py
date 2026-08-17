import json
import os
import urllib.request
import xmlrpc.client
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()


class OdooClient:
    """Client for interacting with Odoo ERP via standard XML-RPC protocol."""

    def __init__(
        self,
        url: Optional[str] = None,
        db: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.url = (url or os.getenv("ODOO_URL", "http://localhost:8069")).rstrip("/")
        self.db = db or os.getenv("ODOO_DB", "odoo_demo")
        self.user = user or os.getenv("ODOO_USER", "admin@example.com")
        self.password = password or os.getenv("ODOO_PASSWORD", "admin")
        self.uid: Optional[int] = None
        self._authenticated = False

    def authenticate(self) -> bool:
        """Authenticate with Odoo XML-RPC common endpoint with fast socket timeout."""
        import socket

        try:
            socket.setdefaulttimeout(3.0)
            common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
            self.uid = common.authenticate(self.db, self.user, self.password, {})
            self._authenticated = bool(self.uid)
            return self._authenticated
        except Exception as e:
            print(f"[OdooClient Warning] Authentication failed: {e}")
            self._authenticated = False
            return False
        finally:
            socket.setdefaulttimeout(None)

    def execute_kw(
        self, model: str, method: str, args: list, kwargs: Optional[dict] = None
    ) -> Any:
        """Execute a keyword method on an Odoo model via XML-RPC."""
        if not self._authenticated and not self.authenticate():
            raise ConnectionError("Failed to authenticate with Odoo server.")

        models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")
        kwargs = kwargs or {}
        return models.execute_kw(
            self.db, self.uid, self.password, model, method, args, kwargs
        )


def check_odoo_connection() -> bool:
    """Helper function to check if Odoo server is accessible (fast 1s check)."""
    odoo_url = os.getenv("ODOO_URL", "http://localhost:8069")
    try:
        req = urllib.request.Request(odoo_url, headers={"User-Agent": "OdooCheck"})
        with urllib.request.urlopen(req, timeout=1.0) as response:
            return response.status in (200, 303, 302, 404)
    except Exception:
        return False


def query_products(
    search_term: str = "",
    category: str = "",
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    limit: int = 10,
) -> str:
    """Query product catalog from Odoo product.template model."""
    try:
        client = OdooClient()
        domain: list = [("sale_ok", "=", True)]

        if search_term:
            domain.append(("name", "ilike", search_term))
        if category:
            domain.append(("categ_id.name", "ilike", category))
        if price_min is not None:
            domain.append(("list_price", ">=", price_min))
        if price_max is not None:
            domain.append(("list_price", "<=", price_max))

        fields = ["id", "name", "list_price", "qty_available", "description_sale", "categ_id"]
        products = client.execute_kw(
            "product.template",
            "search_read",
            [domain],
            {"fields": fields, "limit": limit},
        )

        results = []
        for p in products:
            categ_name = p["categ_id"][1] if isinstance(p.get("categ_id"), list) else "General"
            results.append(
                {
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "price": p.get("list_price", 0.0),
                    "qty_available": p.get("qty_available", 0.0),
                    "category": categ_name,
                    "description": p.get("description_sale") or "",
                }
            )
        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        print(f"[OdooTools Error] query_products failed: {e}")
        return json.dumps([{"error": str(e)}], ensure_ascii=False)


def query_inventory(product_name: str = "", limit: int = 10) -> str:
    """Query inventory stock level for a specific product name or overall stock."""
    try:
        client = OdooClient()
        domain: list = [("sale_ok", "=", True)]
        if product_name:
            domain.append(("name", "ilike", product_name))

        fields = ["id", "name", "qty_available", "virtual_available", "list_price"]
        products = client.execute_kw(
            "product.template",
            "search_read",
            [domain],
            {"fields": fields, "limit": limit},
        )

        results = []
        for p in products:
            results.append(
                {
                    "product_id": p.get("id"),
                    "product_name": p.get("name"),
                    "qty_available": p.get("qty_available", 0.0),
                    "forecast_qty": p.get("virtual_available", 0.0),
                    "price": p.get("list_price", 0.0),
                    "status": "in_stock" if p.get("qty_available", 0.0) > 0 else "out_of_stock",
                }
            )
        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        print(f"[OdooTools Error] query_inventory failed: {e}")
        return json.dumps([{"error": str(e)}], ensure_ascii=False)


def query_customers(limit: int = 10) -> str:
    """Query B2B customer accounts from Odoo res.partner model."""
    try:
        client = OdooClient()
        domain = [("is_company", "=", True)]
        fields = ["name", "email", "phone", "city", "country_id"]
        partners = client.execute_kw(
            "res.partner",
            "search_read",
            [domain],
            {"fields": fields, "limit": limit},
        )

        results = []
        for p in partners:
            country = p["country_id"][1] if isinstance(p.get("country_id"), list) else "N/A"
            results.append(
                {
                    "name": p.get("name"),
                    "email": p.get("email") or "N/A",
                    "phone": p.get("phone") or "N/A",
                    "city": p.get("city") or "N/A",
                    "country": country,
                }
            )
        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        print(f"[OdooTools Error] query_customers failed: {e}")
        return json.dumps([{"error": str(e)}], ensure_ascii=False)


def query_sales(limit: int = 10) -> str:
    """Query recent sales orders from Odoo sale.order model."""
    try:
        client = OdooClient()
        domain = [("state", "in", ["sale", "done"])]
        fields = ["name", "date_order", "partner_id", "amount_total", "state"]
        orders = client.execute_kw(
            "sale.order",
            "search_read",
            [domain],
            {"fields": fields, "limit": limit, "order": "date_order desc"},
        )

        results = []
        for o in orders:
            partner_name = o["partner_id"][1] if isinstance(o.get("partner_id"), list) else "Unknown"
            results.append(
                {
                    "order_name": o.get("name"),
                    "date": o.get("date_order"),
                    "customer": partner_name,
                    "total_amount": o.get("amount_total", 0.0),
                    "status": o.get("state"),
                }
            )
        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        print(f"[OdooTools Error] query_sales failed: {e}")
        return json.dumps([{"error": str(e)}], ensure_ascii=False)


def create_purchase_order(product_name: str, quantity: int) -> Dict[str, Any]:
    """Create a draft Purchase Order on Odoo (purchase.order model). Requires staff approval.

    Returns:
        {"success": True, "order_name": "PO-00125"} or {"success": False, "error": "..."}
    """
    try:
        client = OdooClient()

        # 1. Find product ID (from product.product or product.template)
        prod_domain = [("name", "ilike", product_name)]
        products = client.execute_kw(
            "product.product",
            "search_read",
            [prod_domain],
            {"fields": ["id", "name", "lst_price", "standard_price"], "limit": 1},
        )

        if not products:
            # Fallback search product.template
            templates = client.execute_kw(
                "product.template",
                "search_read",
                [prod_domain],
                {"fields": ["id", "name", "list_price", "standard_price"], "limit": 1},
            )
            if not templates:
                return {
                    "success": False,
                    "error": f"Product '{product_name}' not found in Odoo database.",
                }
            # Search product.product for this template
            prod_id = client.execute_kw(
                "product.product",
                "search",
                [[("product_tmpl_id", "=", templates[0]["id"])]],
                {"limit": 1},
            )
            if prod_id:
                product_id = prod_id[0]
                price_unit = templates[0].get("standard_price") or templates[0].get("list_price") or 100.0
            else:
                return {
                    "success": False,
                    "error": f"Product variant for '{product_name}' not found.",
                }
        else:
            product_id = products[0]["id"]
            price_unit = products[0].get("standard_price") or products[0].get("lst_price") or 100.0

        # 2. Find or create a default Supplier / Vendor partner
        vendor_domain = [("supplier_rank", ">", 0)]
        vendors = client.execute_kw(
            "res.partner",
            "search_read",
            [vendor_domain],
            {"fields": ["id", "name"], "limit": 1},
        )

        if vendors:
            vendor_id = vendors[0]["id"]
        else:
            # Search any partner or create default vendor
            any_partners = client.execute_kw(
                "res.partner",
                "search_read",
                [[]],
                {"fields": ["id", "name"], "limit": 1},
            )
            if any_partners:
                vendor_id = any_partners[0]["id"]
            else:
                vendor_id = client.execute_kw(
                    "res.partner",
                    "create",
                    [{"name": "Tech Hardware Supplier Co.", "supplier_rank": 1, "is_company": True}],
                )

        # 3. Create purchase.order in draft state
        po_id = client.execute_kw(
            "purchase.order",
            "create",
            [
                {
                    "partner_id": vendor_id,
                    "state": "draft",
                }
            ],
        )

        # Read the assigned PO order name (e.g. PO00012)
        po_data = client.execute_kw(
            "purchase.order",
            "read",
            [[po_id]],
            {"fields": ["name"]},
        )
        order_name = po_data[0]["name"] if po_data else f"PO-{po_id}"

        # 4. Create purchase.order.line
        client.execute_kw(
            "purchase.order.line",
            "create",
            [
                {
                    "order_id": po_id,
                    "product_id": product_id,
                    "name": f"Restock request: {product_name}",
                    "product_qty": float(quantity),
                    "price_unit": float(price_unit),
                }
            ],
        )

        return {
            "success": True,
            "order_name": order_name,
            "po_id": po_id,
            "product_name": product_name,
            "quantity": quantity,
        }

    except Exception as e:
        print(f"[OdooTools Error] create_purchase_order failed: {e}")
        return {"success": False, "error": str(e)}
