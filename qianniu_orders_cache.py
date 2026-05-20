import json
from pathlib import Path


CAPTURE_RAW_DIR = Path("qianniu_web_captures/raw")
PENDING_STATUS_TEXTS = ("买家已付款", "待发货")


def format_price(value):
    value = float(value)
    return str(int(value)) if value.is_integer() else f"{value:.2f}".rstrip("0").rstrip(".")


def latest_order_capture_file():
    if not CAPTURE_RAW_DIR.exists():
        return None

    files = [
        path
        for path in CAPTURE_RAW_DIR.glob("*.json")
        if "trade_itemlist_asyncSold" in path.name or "asyncSold" in path.name
    ]
    if not files:
        return None
    return max(files, key=lambda path: path.stat().st_mtime)


def load_latest_orders():
    path = latest_order_capture_file()
    if not path:
        return []

    payload = json.loads(path.read_text(encoding="utf-8"))
    response = payload.get("response", {})
    main_orders = response.get("mainOrders", [])
    return [normalize_order(order, path) for order in main_orders]


def normalize_order(order, source_path):
    order_id = str(order.get("orderInfo", {}).get("id") or order.get("id") or "")
    status = str(order.get("statusInfo", {}).get("text") or "")
    buyer = order.get("buyer", {}) or {}
    pay_info = order.get("payInfo", {}) or {}
    sub_orders = order.get("subOrders", []) or []

    price = pay_info.get("actualFee")
    if price in (None, ""):
        price = sum(float((sub.get("priceInfo", {}) or {}).get("realTotal") or 0) for sub in sub_orders)

    return {
        "order_id": order_id,
        "status": status,
        "buyer": buyer.get("nick") or buyer.get("encodeNick") or "",
        "buyer_phone": buyer.get("phoneNum") or "",
        "price": format_price(price or 0),
        "create_time": order.get("orderInfo", {}).get("createTime") or "",
        "source_path": str(source_path),
    }


def is_pending_order(order):
    return any(text in order.get("status", "") for text in PENDING_STATUS_TEXTS)


def summarize_pending_orders(buyer=None):
    orders = load_latest_orders()
    pending_orders = [order for order in orders if is_pending_order(order)]

    if buyer:
        buyer = str(buyer).strip()
        filtered = [order for order in pending_orders if buyer and buyer in order.get("buyer", "")]
        if filtered:
            pending_orders = filtered

    if not pending_orders:
        return {}

    total = sum(float(order["price"]) for order in pending_orders)
    return {
        "order_id": "/".join(order["order_id"] for order in pending_orders if order["order_id"]),
        "price": format_price(total),
        "buyer": pending_orders[0].get("buyer", ""),
        "orders": pending_orders,
    }
