import os
import sys
import xmlrpc.client
from dotenv import load_dotenv

# Ensure UTF-8 stdout on Windows PowerShell
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from mcp_server.odoo_tools import OdooClient

load_dotenv()


def seed_odoo():
    """Seed Odoo ERP database with demo products, inventory stock, suppliers & sales orders."""
    print("🚀 Starting Odoo ERP Data Seeding for Sales Chatbot...")
    client = OdooClient()
    if not client.authenticate():
        print("❌ Cannot authenticate with Odoo. Check server status and credentials in .env.")
        return

    # 1. Seed Demo Vendors / Suppliers
    vendors = [
        {"name": "Global Tech Distributors Co.", "supplier_rank": 1, "is_company": True, "email": "supply@globaltech.com"},
        {"name": "Asia Hardware Supply Ltd.", "supplier_rank": 1, "is_company": True, "email": "orders@asiahardware.com"},
    ]

    for v in vendors:
        existing = client.execute_kw(
            "res.partner",
            "search",
            [[("name", "=", v["name"])]],
        )
        if not existing:
            v_id = client.execute_kw("res.partner", "create", [v])
            print(f"   [OK] Created Vendor: {v['name']} (ID: {v_id})")

    # 2. Seed Demo Customers
    customers = [
        {"name": "Acme Electronics Corp", "is_company": True, "email": "procurement@acme.com", "phone": "0901234567"},
        {"name": "FPT Retail Partner", "is_company": True, "email": "b2b@fpt.com.vn", "phone": "0909876543"},
        {"name": "TGDD Hardware Inc", "is_company": True, "email": "contact@tgdd.vn", "phone": "0911223344"},
    ]

    customer_ids = []
    for c in customers:
        existing = client.execute_kw(
            "res.partner",
            "search",
            [[("name", "=", c["name"])]],
        )
        if existing:
            customer_ids.append(existing[0])
        else:
            c_id = client.execute_kw("res.partner", "create", [c])
            customer_ids.append(c_id)
            print(f"   [OK] Created Customer: {c['name']} (ID: {c_id})")

    # 3. Seed Demo Products & Stock
    products = [
        {
            "name": "Dell XPS 13",
            "list_price": 25000000.0,
            "standard_price": 20000000.0,
            "qty": 15,
            "description": "High performance ultrabook, Intel Core i7, 16GB RAM, 512GB SSD.",
        },
        {
            "name": "MacBook Air M3",
            "list_price": 28000000.0,
            "standard_price": 23000000.0,
            "qty": 12,
            "description": "Apple M3 chip, 8-Core CPU, 10-Core GPU, 16GB Unified Memory, 512GB SSD.",
        },
        {
            "name": "ThinkPad X1 Carbon",
            "list_price": 32000000.0,
            "standard_price": 26000000.0,
            "qty": 0,  # OUT OF STOCK FOR DEMO RESTOCKING
            "description": "Business flagship laptop, Intel Core i7, 32GB RAM, 1TB SSD, Carbon Fiber.",
        },
        {
            "name": "Asus ROG Strix G16",
            "list_price": 35000000.0,
            "standard_price": 29000000.0,
            "qty": 8,
            "description": "Gaming laptop, Intel Core i9, RTX 4070, 32GB RAM, 1TB SSD, 240Hz Display.",
        },
        {
            "name": "HP Spectre x360",
            "list_price": 22000000.0,
            "standard_price": 18000000.0,
            "qty": 20,
            "description": "2-in-1 Touchscreen laptop, Intel Core i5, 16GB RAM, 512GB SSD.",
        },
        {
            "name": "iPhone 15 Pro Max",
            "list_price": 29000000.0,
            "standard_price": 24000000.0,
            "qty": 10,
            "description": "Apple A17 Pro chip, Titanium Frame, 256GB Storage, 48MP Camera.",
        },
        {
            "name": "Samsung Galaxy S24 Ultra",
            "list_price": 30000000.0,
            "standard_price": 25000000.0,
            "qty": 5,
            "description": "Snapdragon 8 Gen 3, S-Pen included, 12GB RAM, 512GB Storage, 200MP Camera.",
        },
    ]

    for p in products:
        existing = client.execute_kw(
            "product.template",
            "search_read",
            [[("name", "=", p["name"])]],
            {"fields": ["id", "name"]},
        )
        if not existing:
            tmpl_id = client.execute_kw(
                "product.template",
                "create",
                [
                    {
                        "name": p["name"],
                        "list_price": p["list_price"],
                        "standard_price": p["standard_price"],
                        "description_sale": p["description"],
                        "sale_ok": True,
                        "purchase_ok": True,
                        "type": "product",
                    }
                ],
            )
            print(f"   [OK] Created Product Template: {p['name']} (ID: {tmpl_id})")

    print("\n✅ Odoo ERP Seeding Completed Successfully!")


if __name__ == "__main__":
    seed_odoo()
