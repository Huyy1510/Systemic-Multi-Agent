import os
import sys
import random
from datetime import datetime, timedelta

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mcp_server.odoo_tools import OdooClient


def seed_odoo():
    print("🌱 Connecting to Odoo ERP...")
    client = OdooClient()
    if not client.authenticate():
        print("❌ Cannot connect/authenticate with Odoo server. Make sure Odoo is running and credentials in .env are correct.")
        return

    print("✅ Authenticated with Odoo ERP!")

    # 1. Seed Products
    print("\n📦 Seeding Demo Products...")
    demo_products = [
        {"name": "TechVN Pro Laptop 15", "list_price": 1200.0, "standard_price": 850.0},
        {"name": "TechVN Air Ultra Laptop", "list_price": 950.0, "standard_price": 650.0},
        {"name": "TechVN Gaming Monster X", "list_price": 1800.0, "standard_price": 1300.0},
        {"name": "TechVN Smartphone Pro 14", "list_price": 800.0, "standard_price": 500.0},
        {"name": "TechVN Smartphone Lite", "list_price": 400.0, "standard_price": 250.0},
        {"name": "TechVN Tablet Max 11", "list_price": 600.0, "standard_price": 400.0},
        {"name": "TechVN Wireless Earbuds Pro", "list_price": 120.0, "standard_price": 60.0},
        {"name": "TechVN Mechanical Keyboard RGB", "list_price": 150.0, "standard_price": 80.0},
        {"name": "TechVN Ergonomic Gaming Mouse", "list_price": 80.0, "standard_price": 40.0},
        {"name": "TechVN 4K UHD Monitor 27inch", "list_price": 350.0, "standard_price": 220.0},
    ]

    product_ids = []
    for p_info in demo_products:
        existing = client.search_read("product.template", [("name", "=", p_info["name"])], ["id"])
        if existing:
            p_id = existing[0]["id"]
        else:
            p_id = client.execute_kw("product.template", "create", [p_info])
            print(f"  + Created product: {p_info['name']} (ID: {p_id})")
        product_ids.append(p_id)

    # 2. Seed Customers
    print("\n👥 Seeding Demo Customers...")
    demo_customers = [
        {"name": "FPT Digital Corp", "email": "contact@fpt-digital.vn", "phone": "+84 24 7300 7373"},
        {"name": "Viettel Enterprise Solutions", "email": "b2b@viettel.vn", "phone": "+84 24 6255 6789"},
        {"name": "Vingroup Technology Partner", "email": "tech@vingroup.net", "phone": "+84 24 3974 9999"},
        {"name": "CMC Global Solutions", "email": "info@cmcglobal.vn", "phone": "+84 24 3795 8668"},
        {"name": "MISA Joint Stock Co", "email": "sales@misa.com.vn", "phone": "+84 24 3795 9595"},
        {"name": "Nguyen Van A", "email": "nguyenvana@gmail.com", "phone": "+84 90 123 4567"},
        {"name": "Tran Thi B", "email": "tranthib@gmail.com", "phone": "+84 91 876 5432"},
        {"name": "Le Hoang C", "email": "lehoangc@outlook.com", "phone": "+84 98 999 8888"},
    ]

    customer_ids = []
    for c_info in demo_customers:
        existing = client.search_read("res.partner", [("name", "=", c_info["name"])], ["id"])
        if existing:
            c_id = existing[0]["id"]
        else:
            c_info["customer_rank"] = 1
            c_id = client.execute_kw("res.partner", "create", [c_info])
            print(f"  + Created customer: {c_info['name']} (ID: {c_id})")
        customer_ids.append(c_id)

    # 3. Seed Sale Orders
    print("\n🛍️ Seeding Demo Sales Orders...")
    start_date = datetime.now() - timedelta(days=90)
    for i in range(15):
        order_date = (start_date + timedelta(days=random.randint(1, 88))).strftime("%Y-%m-%d %H:%M:%S")
        cust_id = random.choice(customer_ids)

        # Check existing orders to keep script idempotent
        existing_orders = client.search_read("sale.order", [("partner_id", "=", cust_id), ("date_order", "=", order_date)], ["id"])
        if not existing_orders:
            order_vals = {
                "partner_id": cust_id,
                "date_order": order_date,
                "state": "sale",
            }
            order_id = client.execute_kw("sale.order", "create", [order_vals])

            # Add order lines
            selected_products = random.sample(product_ids, k=random.randint(1, 3))
            for p_tmpl_id in selected_products:
                tmpl = client.search_read("product.template", [("id", "=", p_tmpl_id)], ["list_price", "name"])[0]
                line_vals = {
                    "order_id": order_id,
                    "name": tmpl["name"],
                    "product_uom_qty": random.randint(1, 10),
                    "price_unit": tmpl["list_price"],
                }
                client.execute_kw("sale.order.line", "create", [line_vals])

            print(f"  + Created confirmed order #{order_id} for partner ID {cust_id}")

    print("\n🎉 Seed script execution finished successfully!")


if __name__ == "__main__":
    seed_odoo()
