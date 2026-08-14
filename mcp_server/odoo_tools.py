import json
import os
import xmlrpc.client
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()


class OdooClient:
    """Wrapper for Odoo XML-RPC API."""

    def __init__(
        self,
        url: Optional[str] = None,
        db: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.url = (url or os.getenv("ODOO_URL", "http://localhost:8069")).rstrip("/")
        self.db = db or os.getenv("ODOO_DB", "odoo_demo")
        self.user = user or os.getenv("ODOO_USER", "admin")
        self.password = password or os.getenv("ODOO_PASSWORD", "admin")
        self.uid: Optional[int] = None
        self._authenticated = False

    def authenticate(self) -> bool:
        """Authenticate with Odoo XML-RPC common endpoint with fast timeout."""
        import socket
        try:
            # Set fast socket timeout for Odoo connection check
            socket.setdefaulttimeout(3.0)
            common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
            self.uid = common.authenticate(
                self.db, self.user, self.password, {}
            )
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
        """Execute method on Odoo object model via XML-RPC."""
        if not self._authenticated and not self.authenticate():
            raise ConnectionError("Failed to authenticate with Odoo server.")

        models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")
        return models.execute_kw(
            self.db, self.uid, self.password, model, method, args, kwargs or {}
        )

    def search_read(
        self,
        model: str,
        domain: List[Any],
        fields: List[str],
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search and read records from an Odoo model."""
        return self.execute_kw(
            model,
            "search_read",
            [domain],
            {"fields": fields, "limit": limit},
        )


def check_odoo_connection() -> bool:
    """Helper function to check if Odoo server is accessible (fast 1s check)."""
    import urllib.request
    odoo_url = os.getenv("ODOO_URL", "http://localhost:8069")
    try:
        req = urllib.request.Request(odoo_url, headers={"User-Agent": "OdooCheck"})
        with urllib.request.urlopen(req, timeout=1.0) as response:
            return response.status in (200, 303, 302, 404)
    except Exception:
        return False


def query_sales(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    product_name: Optional[str] = None,
    limit: int = 20,
) -> str:
    """Query sale orders from Odoo ERP."""
    client = OdooClient()
    if not client.authenticate():
        return json.dumps(
            {"error": "Odoo server not connected or invalid credentials."},
            ensure_ascii=False,
        )

    try:
        domain = [("state", "in", ["sale", "done"])]
        if date_from:
            domain.append(("date_order", ">=", date_from))
        if date_to:
            domain.append(("date_order", "<=", date_to))

        fields = ["name", "date_order", "partner_id", "amount_total", "order_line"]
        orders = client.search_read("sale.order", domain, fields, limit=limit)

        results = []
        for order in orders:
            partner_name = (
                order["partner_id"][1]
                if isinstance(order.get("partner_id"), (list, tuple))
                else str(order.get("partner_id"))
            )
            results.append(
                {
                    "order_name": order.get("name"),
                    "date": order.get("date_order"),
                    "customer": partner_name,
                    "total_amount": order.get("amount_total"),
                }
            )

        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Failed to query Odoo sales: {str(e)}"}, ensure_ascii=False)


def query_inventory(
    product_name: Optional[str] = None,
    warehouse: Optional[str] = None,
    limit: int = 20,
) -> str:
    """Query current product inventory levels from Odoo ERP."""
    client = OdooClient()
    if not client.authenticate():
        return json.dumps(
            {"error": "Odoo server not connected or invalid credentials."},
            ensure_ascii=False,
        )

    try:
        domain = []
        if product_name:
            domain.append(("product_id.name", "ilike", product_name))

        fields = ["product_id", "quantity", "reserved_quantity", "location_id"]
        quants = client.search_read("stock.quant", domain, fields, limit=limit)

        results = []
        for q in quants:
            p_name = (
                q["product_id"][1]
                if isinstance(q.get("product_id"), (list, tuple))
                else str(q.get("product_id"))
            )
            loc_name = (
                q["location_id"][1]
                if isinstance(q.get("location_id"), (list, tuple))
                else str(q.get("location_id"))
            )
            results.append(
                {
                    "product": p_name,
                    "location": loc_name,
                    "qty_on_hand": q.get("quantity", 0),
                    "qty_reserved": q.get("reserved_quantity", 0),
                }
            )

        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Failed to query Odoo inventory: {str(e)}"}, ensure_ascii=False)


def query_customers(
    name: Optional[str] = None,
    country: Optional[str] = None,
    limit: int = 20,
) -> str:
    """Query customer contact details and order metrics from Odoo ERP."""
    client = OdooClient()
    if not client.authenticate():
        return json.dumps(
            {"error": "Odoo server not connected or invalid credentials."},
            ensure_ascii=False,
        )

    try:
        domain = [("customer_rank", ">", 0)]
        if name:
            domain.append(("name", "ilike", name))

        fields = ["name", "email", "phone", "country_id"]
        partners = client.search_read("res.partner", domain, fields, limit=limit)

        results = []
        for p in partners:
            c_name = (
                p["country_id"][1]
                if isinstance(p.get("country_id"), (list, tuple))
                else str(p.get("country_id", ""))
            )
            results.append(
                {
                    "name": p.get("name"),
                    "email": p.get("email"),
                    "phone": p.get("phone"),
                    "country": c_name,
                }
            )

        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Failed to query Odoo customers: {str(e)}"}, ensure_ascii=False)


# FastMCP tool integration
try:
    from mcp.server.fastmcp import FastMCP

    mcp_odoo_app = FastMCP("OdooERPTools")

    @mcp_odoo_app.tool()
    def mcp_query_sales(
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        product_name: Optional[str] = None,
        limit: int = 20,
    ) -> str:
        """Query sales orders and revenue metrics from Odoo ERP."""
        return query_sales(date_from, date_to, product_name, limit)

    @mcp_odoo_app.tool()
    def mcp_query_inventory(
        product_name: Optional[str] = None,
        warehouse: Optional[str] = None,
        limit: int = 20,
    ) -> str:
        """Query inventory stock levels from Odoo ERP."""
        return query_inventory(product_name, warehouse, limit)

    @mcp_odoo_app.tool()
    def mcp_query_customers(
        name: Optional[str] = None,
        country: Optional[str] = None,
        limit: int = 20,
    ) -> str:
        """Query customer details from Odoo ERP."""
        return query_customers(name, country, limit)

except ImportError:
    mcp_odoo_app = None


if __name__ == "__main__":
    if mcp_odoo_app:
        mcp_odoo_app.run(transport="stdio")
    else:
        print("mcp package standard server runner for Odoo not configured.")
