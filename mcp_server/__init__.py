from .odoo_tools import (
    check_odoo_connection,
    query_customers,
    query_inventory,
    query_sales,
)
from .search_tools import execute_web_fetch, execute_web_search

__all__ = [
    "execute_web_search",
    "execute_web_fetch",
    "query_sales",
    "query_inventory",
    "query_customers",
    "check_odoo_connection",
]
