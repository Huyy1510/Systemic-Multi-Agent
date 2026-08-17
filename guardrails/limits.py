import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class GuardrailConfig:
    # Chat limits
    max_chat_history: int = 10  # Sliding window size
    max_products_per_comparison: int = 4  # Max products per comparison
    max_restock_quantity: int = 500  # Max restock quantity limit

    # Odoo
    odoo_query_timeout: float = 10.0  # Timeout for Odoo queries (seconds)

    # General
    max_tokens_per_request: int = 8000


def load_config() -> GuardrailConfig:
    return GuardrailConfig(
        max_chat_history=int(os.getenv("MAX_CHAT_HISTORY", "10")),
        max_products_per_comparison=int(os.getenv("MAX_PRODUCTS_PER_COMPARISON", "4")),
        max_restock_quantity=int(os.getenv("MAX_RESTOCK_QUANTITY", "500")),
    )
