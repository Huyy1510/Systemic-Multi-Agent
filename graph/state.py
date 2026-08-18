from typing import Any, Dict, List, Optional, TypedDict


class ChatState(TypedDict):
    # Conversation
    current_message: str  # Current user message
    chat_history: List[Dict[str, str]]  # [{"role": "user"/"assistant", "content": "..."}]

    # Router output
    intent: str  # product_inquiry / product_comparison / stock_check / restock_request / off_topic
    product_names: List[str]  # Product names mentioned by user
    quantity: Optional[int]  # Quantity if stated by user

    # Inventory check & Restock signals
    stock_status: str  # in_stock / out_of_stock / unknown
    out_of_stock_product: str  # Product out of stock (if any)
    needs_restock_signal: bool  # Signal from SaleAgent to ProcurementAgent
    restock_po_created: Optional[str]  # Draft Purchase Order code if created by ProcurementAgent
    sale_order_created: Optional[str]  # Draft Sale Order code if created for customer

    # Response
    response: str  # Bot final response

    # Meta
    run_id: str
    warnings: List[str]
