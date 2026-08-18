import json
import os
from typing import Any, Dict, Optional
from dotenv import load_dotenv

load_dotenv()


def send_slack_notification(
    order_code: str,
    order_type: str,  # "purchase_order" or "sale_order"
    product_name: str,
    quantity: int,
    status: str = "Draft (Chờ duyệt)",
    webhook_url: Optional[str] = None,
    channel: Optional[str] = None,
    mention_user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Send a rich Block Kit notification message to Slack via Incoming Webhook.

    Args:
        order_code: e.g. "P00015" or "S00012"
        order_type: "purchase_order" (Draft PO) or "sale_order" (Draft SO)
        product_name: Name of product
        quantity: Item quantity
        status: Order status string
        webhook_url: Slack Incoming Webhook URL (reads SLACK_WEBHOOK_URL env if None)
        channel: Optional channel override
        mention_user_id: Optional Slack Member ID to @mention (e.g. "U12345678")

    Returns:
        {"success": True} or {"success": False, "error": "..."}
    """
    url = webhook_url or os.getenv("SLACK_WEBHOOK_URL", "")

    if not url:
        print("[Slack Integration] SLACK_WEBHOOK_URL not configured. Skipping live Slack push.")
        return {
            "success": False,
            "reason": "SLACK_WEBHOOK_URL is empty in .env. Skipping push.",
        }

    target_channel = channel or os.getenv(
        "SLACK_CHANNEL", "#general"
    )

    # Format user tag if provided
    tag_str = ""
    user_id = mention_user_id or os.getenv("SLACK_STAFF_MEMBER_ID", "")
    if user_id:
        user_id_clean = user_id.replace("@", "").strip()
        tag_str = f" <@{user_id_clean}>"

    odoo_url = os.getenv("ODOO_URL", "http://localhost:8069")

    if order_type == "purchase_order":
        header_text = "📦 [Procurement Agent] Yêu Cầu Nhập Hàng Mới (Draft PO)"
        color_emoji = "🟧"
        odoo_menu = "Purchase -> Orders -> Requests for Quotation"
        order_title = "Đơn Mua Hàng (Purchase Order)"
        action_msg = f"🔔 Vui lòng đăng nhập Odoo và duyệt đơn hàng nhập này cho kho!{tag_str}"
    else:
        header_text = "🛒 [Sale Agent] Đơn Bán Hàng Mới (Draft SO)"
        color_emoji = "🟩"
        odoo_menu = "Sales -> Orders -> Quotations"
        order_title = "Đơn Bán Hàng (Sale Order)"
        action_msg = f"🔔 Vui lòng kiểm tra và xác nhận xuất kho cho khách hàng!{tag_str}"

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{color_emoji} {header_text}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Loại đơn:* {order_title}"},
                {"type": "mrkdwn", "text": f"*Mã Odoo:* `{order_code}`"},
                {"type": "mrkdwn", "text": f"*Sản phẩm:* {product_name}"},
                {"type": "mrkdwn", "text": f"*Số lượng:* {quantity} cái"},
                {"type": "mrkdwn", "text": f"*Trạng thái:* {status}"},
                {"type": "mrkdwn", "text": f"*Odoo Menu:* `{odoo_menu}`"},
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": action_msg,
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"📍 Systemic Multi Agent System | Odoo Link: {odoo_url}",
                }
            ],
        },
        {"type": "divider"},
    ]

    payload = {
        "text": f"{header_text}: {order_code} - {product_name} (Qty: {quantity})",
        "blocks": blocks,
    }

    try:
        import urllib.request

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            status_code = resp.getcode()
            if status_code in (200, 204):
                print(f"[Slack Integration] Successfully posted notification for {order_code} to Slack!")
                return {"success": True, "status_code": status_code}
            else:
                return {"success": False, "status_code": status_code}
    except Exception as e:
        print(f"[Slack Integration Error] Failed to send Slack webhook: {e}")
        return {"success": False, "error": str(e)}
