import json
import re
import time
import uuid
from pathlib import Path

import keyboard
import pyperclip

try:
    import pyautogui
except ImportError:
    pyautogui = None

if pyautogui is not None:
    pyautogui.PAUSE = 0.02

try:
    import uiautomation as auto
except ImportError:
    auto = None

try:
    from pywinauto import Desktop
except ImportError:
    Desktop = None


CONFIG_PATH = Path("qianniu_config.json")
BASKET_PATH = Path("qianniu_order_basket.json")
PENDING_REMARK_TEXT = ""
USE_CONFIG_FILE = False

DEFAULT_CONFIG = {
    "quick_copy_button": None,
    "quick_copy_save_button": None,
    "buyer_copy_button": None,
    "right_orders_panel": None,
    "chat_input": None,
    "remark_button": None,
    "remark_textarea": None,
    "remark_save_button": None,
    "transfer_button": None,
    "transfer_target": None,
}

QIANNIU_WINDOW_KEYWORDS = ("接待中心",)
EXCLUDED_WINDOW_KEYWORDS = ("Google Chrome", "myseller.taobao.com", "Visual Studio Code", "PyCharm")

DEFAULT_RELATIVE_POINTS = {
    # Based on the Qianniu reception layout in the provided screenshot.
    # These are used only when no manual coordinate is configured.
    "quick_copy_button": {"x": 0.72, "y": 0.89},
    "quick_copy_save_button": {"x": 0.74, "y": 0.90},
    "buyer_copy_button": {"x": 0.80, "y": 0.33},
    "right_orders_panel": {"x": 0.83, "y": 0.55},
    "chat_input": {"x": 0.42, "y": 0.86},
    "remark_button": {"x": 0.895, "y": 0.885},
    "remark_textarea": {"x": 0.56, "y": 0.52},
    "remark_save_button": {"x": 0.73, "y": 0.90},
    "transfer_button": {"x": 0.80, "y": 0.33},
    "transfer_target": {"x": 0.80, "y": 0.45},
}

QUICK_COPY_FALLBACK_POINTS = (
    {"x": 0.72, "y": 0.89},
    {"x": 0.70, "y": 0.89},
    {"x": 0.74, "y": 0.89},
    {"x": 0.72, "y": 0.84},
)

CHAT_INPUT_FALLBACK_POINTS = (
    {"x": 0.42, "y": 0.86},
    {"x": 0.42, "y": 0.80},
    {"x": 0.52, "y": 0.86},
)

RIGHT_ORDERS_FALLBACK_POINTS = (
    {"x": 0.83, "y": 0.55},
    {"x": 0.83, "y": 0.46},
    {"x": 0.83, "y": 0.65},
    {"x": 0.77, "y": 0.55},
    {"x": 0.89, "y": 0.55},
)


ORDER_ID_PATTERNS = [
    re.compile(r"(?:订单编号|订单号)\s*[:：]?\s*([0-9]{10,30}(?:/[0-9]{10,30})*)"),
    re.compile(r"(?:待发货|未完成|已完成|已关闭)?\s*([0-9]{15,30})\s*(?:详情|开票|订单|备注)"),
]
PRICE_PATTERNS = [
    re.compile(r"(?:接单价格|订单总价|订单总付款|实付金额|实付)\s*[:：]\s*[￥¥]?\s*([0-9]+(?:\.[0-9]+)?)"),
    re.compile(r"订单总价\s*[：:]\s*[￥¥]\s*([0-9]+(?:\.[0-9]+)?)"),
]
PROJECT_PATTERNS = [
    re.compile(r"(?:购买项目|商品|宝贝|标题)\s*[:：]\s*(.+)"),
    re.compile(r"(?:商品名称|商品标题)\s*[:：]\s*(.+)"),
]
PHONE_RE = re.compile(r"\b1[3-9]\d{9}\b")
ORDER_ID_RE = re.compile(r"\b\d{10,30}\b")
BUYER_RE = re.compile(r"(?:淘宝旺旺|买家|旺旺)\s*[:：]\s*([^\s\r\n]+)")
PENDING_STATUS_WORDS = ("待发货",)
ORDER_STATUS_WORDS = ("待发货", "待付款", "未付款", "已付款", "已完成", "已关闭", "交易关闭", "退款", "售后")
ORDER_BLOCK_START_RE = re.compile(
    r"(?=^(?:待发货|待付款|未付款|已付款|已完成|已关闭|交易关闭|退款|售后)\b)",
    re.MULTILINE,
)
ORDER_ID_BLOCK_START_RE = re.compile(r"(?=^(?:订单编号|订单号)\b)", re.MULTILINE)
PRICE_LABEL_PRIORITY = ("接单价格", "订单总付款", "订单总价", "实付金额", "实付")

FIELD_LABELS = {
    "order_id": ("订单编号", "订单号"),
    "buyer": ("淘宝旺旺", "旺旺", "买家"),
    "price": ("接单价格", "订单总价", "订单总付款", "实付金额", "实付"),
    "project": ("购买项目", "商品名称", "商品标题", "商品", "宝贝", "标题"),
    "system": ("系统", "游戏系统"),
    "role": ("角色名", "角色名称"),
    "phone": ("联系电话", "手机", "手机号", "电话"),
    "account": ("游戏账号", "账号"),
    "password": ("游戏密码", "密码"),
    "server": ("游戏区服", "区服", "大区"),
    "insurance": ("保险倍数", "保险格数", "保险"),
}


def load_config():
    if not USE_CONFIG_FILE:
        return dict(DEFAULT_CONFIG)

    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)

    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        loaded = json.load(f)

    config = dict(DEFAULT_CONFIG)
    config.update(loaded)
    if config != loaded:
        save_config(config)
    return config


def save_config(config):
    if not USE_CONFIG_FILE:
        return

    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def load_basket():
    if not BASKET_PATH.exists():
        return {}
    with BASKET_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_basket(basket):
    with BASKET_PATH.open("w", encoding="utf-8") as f:
        json.dump(basket, f, ensure_ascii=False, indent=2)


def clear_basket():
    global PENDING_REMARK_TEXT

    save_basket({})
    PENDING_REMARK_TEXT = ""
    print("订单篮子已清空。")


def add_clipboard_order_to_basket():
    text = normalize_text(pyperclip.paste())
    with Path("qianniu_last_quick_copy.txt").open("w", encoding="utf-8") as f:
        f.write(text)

    info = parse_order_text(text)
    if not info.get("order_id") or not info.get("price"):
        print("当前剪贴板没有识别到订单编号/价格。请先手动快捷复制一笔待发货订单。")
        return

    basket = load_basket()
    order_ids = [order_id for order_id in info["order_id"].split("/") if order_id]
    if len(order_ids) != 1:
        print("这次复制内容里不是单笔订单，暂不加入篮子。")
        return

    order_id = order_ids[0]
    basket[order_id] = {
        "order_id": order_id,
        "price": info["price"],
        "buyer": info.get("buyer", ""),
        "raw": text,
    }
    save_basket(basket)

    total = sum(float(item["price"]) for item in basket.values())
    print(f"已加入订单篮子: {order_id}，当前 {len(basket)} 笔，总价 {format_price(total)}。")


def basket_to_order_info():
    basket = load_basket()
    if not basket:
        return {}

    items = list(basket.values())
    total = sum(float(item["price"]) for item in items)
    buyer = next((item.get("buyer", "") for item in items if item.get("buyer")), "")
    return {
        "order_id": "/".join(item["order_id"] for item in items),
        "price": format_price(total),
        "buyer": buyer,
    }


def format_price(value):
    value = float(value)
    return str(int(value)) if value.is_integer() else f"{value:.2f}".rstrip("0").rstrip(".")


def click_point(point_name):
    if pyautogui is None:
        print("未安装 pyautogui，无法点击客户端坐标。")
        return False

    config = load_config()
    point = config.get(point_name)
    if point:
        pyautogui.click(point["x"], point["y"])
        time.sleep(0.2)
        return True

    relative_point = DEFAULT_RELATIVE_POINTS.get(point_name)
    window_rect = get_qianniu_window_rect()
    if not relative_point or not window_rect:
        print(f"还没有配置坐标: {point_name}。自动定位也没找到千牛窗口，请按 Ctrl+9 校准。")
        return False

    x = int(window_rect["left"] + window_rect["width"] * relative_point["x"])
    y = int(window_rect["top"] + window_rect["height"] * relative_point["y"])
    pyautogui.click(x, y)
    time.sleep(0.2)
    return True


def paste_text(text):
    pyperclip.copy(text)
    time.sleep(0.1)
    keyboard.press_and_release("ctrl+v")


def paste_text_strict(text):
    pyperclip.copy(text)
    time.sleep(0.15)
    keyboard.press_and_release("ctrl+a")
    time.sleep(0.05)
    keyboard.press_and_release("ctrl+v")


def release_keyboard_modifiers():
    if pyautogui is None:
        return

    for key in ("ctrl", "shift", "alt"):
        try:
            pyautogui.keyUp(key)
        except Exception:
            pass


def press_hotkey(*keys):
    release_keyboard_modifiers()
    if pyautogui is not None:
        pyautogui.hotkey(*keys)
    else:
        keyboard.press_and_release("+".join(keys))


def wait_for_clipboard_change(marker, timeout=0.35, interval=0.03):
    deadline = time.time() + timeout
    while time.time() < deadline:
        copied_text = pyperclip.paste()
        if copied_text != marker:
            return copied_text
        time.sleep(interval)
    return pyperclip.paste()


def point_inside_rect(point, rect, margin=0):
    return (
        rect["left"] - margin <= point["x"] <= rect["right"] + margin
        and rect["top"] - margin <= point["y"] <= rect["bottom"] + margin
    )


def focus_qianniu_window_by_pywinauto():
    if Desktop is None:
        return False

    try:
        windows = Desktop(backend="uia").windows()
    except Exception:
        return False

    for window in windows:
        try:
            name = str(window.window_text() or "")
        except Exception:
            name = ""

        if any(excluded in name for excluded in EXCLUDED_WINDOW_KEYWORDS):
            continue
        if not any(keyword_name in name for keyword_name in QIANNIU_WINDOW_KEYWORDS):
            continue

        try:
            window.set_focus()
            time.sleep(0.15)
            return True
        except Exception:
            continue

    return False


def focus_chat_input_by_hotkey():
    focused = focus_qianniu_window_by_pywinauto()
    press_hotkey("ctrl", "i")
    time.sleep(0.12)
    return focused


def get_chat_input_click_points(include_relative=True):
    config_point = load_config().get("chat_input")
    yielded = []
    window_rect = get_qianniu_window_rect()

    if config_point:
        if not window_rect or point_inside_rect(config_point, window_rect, margin=2):
            yielded.append((config_point["x"], config_point["y"]))
            yield config_point
        else:
            print("chat_input 配置坐标不在当前千牛窗口内，已改用窗口相对位置。")

    if not window_rect:
        return

    if not include_relative:
        return

    for relative_point in CHAT_INPUT_FALLBACK_POINTS:
        x = int(window_rect["left"] + window_rect["width"] * relative_point["x"])
        y = int(window_rect["top"] + window_rect["height"] * relative_point["y"])
        if any(abs(x - old_x) <= 3 and abs(y - old_y) <= 3 for old_x, old_y in yielded):
            continue
        yielded.append((x, y))
        yield {"x": x, "y": y}


def paste_text_to_focused_input(text):
    pyperclip.copy(text)
    time.sleep(0.06)
    press_hotkey("ctrl", "a")
    time.sleep(0.03)
    press_hotkey("ctrl", "v")
    time.sleep(0.12)
    pyperclip.copy(text)


def paste_at_chat_input_point(point, text):
    focus_chat_input_by_hotkey()
    paste_text_to_focused_input(text)
    return True

def paste_to_chat_input_by_click(text):
    for point in get_chat_input_click_points(include_relative=False):
        focus_qianniu_window_by_pywinauto()
        pyautogui.click(point["x"], point["y"])
        time.sleep(0.08)
        paste_text_to_focused_input(text)
        return True
    return False


def paste_to_chat_input_by_hotkey(text):
    focus_chat_input_by_hotkey()
    paste_text_to_focused_input(text)
    return True


def paste_to_chat_input(text):
    if pyautogui is None:
        pyperclip.copy(text)
        print("模板已复制到剪贴板，但没有找到千牛窗口，无法自动粘贴。")
        return False

    return paste_to_chat_input_by_hotkey(text)


def normalize_text(text):
    return (
        text.replace("\u00a0", " ")
        .replace("：", ":")
        .replace("￥", "¥")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )


def get_focused_top_window():
    if auto is None:
        return None

    try:
        focused = auto.GetFocusedControl()
        if focused:
            top = focused.GetTopLevelControl()
            if top:
                return top
    except Exception:
        pass

    return None


def get_desktop_windows():
    try:
        root = auto.GetRootControl()
        return root.GetChildren() if root else []
    except Exception:
        return []


def get_control_name(control):
    try:
        return str(control.Name or "").strip()
    except Exception:
        return ""


def looks_like_qianniu_window(control):
    name = get_control_name(control)
    if any(keyword in name for keyword in EXCLUDED_WINDOW_KEYWORDS):
        return False
    return any(keyword in name for keyword in QIANNIU_WINDOW_KEYWORDS)


def get_qianniu_window_rect():
    if auto is None:
        return None

    candidates = []
    focused = get_focused_top_window()
    if focused and looks_like_qianniu_window(focused):
        candidates.append(focused)

    candidates.extend(window for window in get_desktop_windows() if looks_like_qianniu_window(window))

    for window in candidates:
        try:
            rect = window.BoundingRectangle
            width = rect.right - rect.left
            height = rect.bottom - rect.top
            if width > 300 and height > 300:
                return {
                    "left": rect.left,
                    "top": rect.top,
                    "right": rect.right,
                    "bottom": rect.bottom,
                    "width": width,
                    "height": height,
                }
        except Exception:
            continue

    return None


def get_window_roots():
    if auto is None:
        return []

    roots = []
    focused = get_focused_top_window()
    if focused:
        roots.append(focused)

    windows = get_desktop_windows()
    with Path("qianniu_window_names.txt").open("w", encoding="utf-8") as f:
        for window in windows:
            name = get_control_name(window)
            if name:
                f.write(name + "\n")
            if looks_like_qianniu_window(window) and window not in roots:
                roots.append(window)

    return roots


def collect_control_text(control, max_depth=12, max_nodes=5000):
    if control is None:
        return ""

    lines = []
    seen = set()

    def add_text(value):
        value = str(value or "").strip()
        if value and value not in seen:
            seen.add(value)
            lines.append(value)

    def walk(node, depth):
        if len(lines) >= max_nodes or depth > max_depth:
            return

        try:
            add_text(node.Name)
        except Exception:
            pass

        for pattern_getter, attr_name in (
            ("GetValuePattern", "Value"),
            ("GetLegacyIAccessiblePattern", "Value"),
        ):
            try:
                pattern = getattr(node, pattern_getter)()
                if pattern:
                    add_text(getattr(pattern, attr_name, ""))
            except Exception:
                pass

        try:
            text_pattern = node.GetTextPattern()
            if text_pattern:
                add_text(text_pattern.DocumentRange.GetText(-1))
        except Exception:
            pass

        try:
            children = node.GetChildren()
        except Exception:
            return

        for child in children:
            walk(child, depth + 1)

    walk(control, 0)
    return "\n".join(lines)


def get_control_text(control):
    values = []

    try:
        values.append(str(control.Name or ""))
    except Exception:
        pass

    for pattern_getter, attr_name in (
        ("GetValuePattern", "Value"),
        ("GetLegacyIAccessiblePattern", "Value"),
    ):
        try:
            pattern = getattr(control, pattern_getter)()
            if pattern:
                values.append(str(getattr(pattern, attr_name, "") or ""))
        except Exception:
            pass

    return "\n".join(value.strip() for value in values if value and value.strip())


def iter_controls(control, max_depth=12, max_nodes=3000):
    if control is None:
        return

    count = 0
    stack = [(control, 0)]
    while stack and count < max_nodes:
        node, depth = stack.pop()
        count += 1
        yield node

        if depth >= max_depth:
            continue

        try:
            children = node.GetChildren()
        except Exception:
            continue

        for child in reversed(children):
            stack.append((child, depth + 1))


def click_control(control):
    try:
        control.Click()
        return True
    except Exception:
        pass

    try:
        pattern = control.GetInvokePattern()
        if pattern:
            pattern.Invoke()
            return True
    except Exception:
        pass

    if pyautogui is None:
        return False

    try:
        rect = control.BoundingRectangle
        x = int((rect.left + rect.right) / 2)
        y = int((rect.top + rect.bottom) / 2)
        pyautogui.click(x, y)
        return True
    except Exception:
        return False


def find_controls_by_keyword(keyword, right_side_only=True):
    if auto is None:
        return []

    candidates = []
    window_rect = get_qianniu_window_rect()

    for root in get_window_roots():
        for control in iter_controls(root):
            text = get_control_text(control)
            if keyword not in text:
                continue

            try:
                rect = control.BoundingRectangle
            except Exception:
                continue

            if rect.right <= rect.left or rect.bottom <= rect.top:
                continue

            if (
                right_side_only
                and window_rect
                and rect.left < window_rect["left"] + window_rect["width"] * 0.55
            ):
                continue

            candidates.append({
                "control": control,
                "text": text,
                "left": rect.left,
                "top": rect.top,
                "right": rect.right,
                "bottom": rect.bottom,
                "center_x": int((rect.left + rect.right) / 2),
                "center_y": int((rect.top + rect.bottom) / 2),
            })

    return candidates


def read_qianniu_visible_text():
    roots = get_window_roots()
    text_blocks = [collect_control_text(root) for root in roots]
    text = "\n".join(block for block in text_blocks if block.strip())
    text = normalize_text(text)
    with Path("qianniu_last_visible_text.txt").open("w", encoding="utf-8") as f:
        f.write(text)
    return text


def pick_first(patterns, text):
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return ""


def pick_phone(text):
    match = PHONE_RE.search(text)
    return match.group(0) if match else ""


def pick_phone_field(text):
    labeled = pick_labeled_field(text, "phone")
    return pick_phone(labeled) or pick_phone(text) or labeled


def clean_chat_value(value):
    return str(value or "").strip(" \t\r\n:：,，;；。")


def looks_like_role_candidate(value):
    value = clean_chat_value(value)
    if not value:
        return False
    if PHONE_RE.search(value) or ORDER_ID_RE.search(value):
        return False
    if re.fullmatch(r"[0-9.\-_/]+", value):
        return False
    if len(value) > 30:
        return False

    excluded_keywords = (
        "订单", "价格", "接单", "付款", "旺旺", "淘宝", "买家",
        "电话", "手机", "联系", "账号", "密码", "区服", "系统",
        "保险", "项目", "购买", "商品", "代练",
    )
    if any(keyword in value for keyword in excluded_keywords):
        return False

    return bool(re.search(r"[\u4e00-\u9fffA-Za-z]", value))


def pick_unlabeled_role(text):
    text = normalize_text(text)
    text = PHONE_RE.sub(" ", text)

    parts = []
    for line in text.splitlines():
        line = clean_chat_value(line)
        if not line:
            continue
        parts.append(line)
        parts.extend(clean_chat_value(part) for part in re.split(r"[\s,，;；|]+", line))

    for part in parts:
        if looks_like_role_candidate(part):
            return clean_chat_value(part)
    return ""


def pick_buyer(text):
    match = BUYER_RE.search(text)
    if match:
        return match.group(1).strip()

    for line in text.splitlines():
        line = line.strip()
        if line and not re.fullmatch(r"[0-9.%-]+", line):
            return line

    return ""


def pick_project(text):
    for pattern in PROJECT_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        if any(key in line for key in ("购买项目", "商品", "标题", "宝贝")):
            return line.split(":", 1)[-1].strip()
    return ""


def has_order_status(text):
    return any(word in text for word in ORDER_STATUS_WORDS)


def is_pending_order_block(block):
    return any(word in block for word in PENDING_STATUS_WORDS)


def filter_pending_order_text(text):
    return "\n".join(get_relevant_order_blocks(text))


def get_relevant_order_blocks(text):
    if not has_order_status(text):
        blocks = [block.strip() for block in ORDER_ID_BLOCK_START_RE.split(text) if block.strip()]
        return blocks or [text]

    blocks = [block.strip() for block in ORDER_BLOCK_START_RE.split(text) if block.strip()]
    return [block for block in blocks if is_pending_order_block(block)]


def pick_labeled_field(text, field_name):
    labels = FIELD_LABELS[field_name]
    label_pattern = "|".join(re.escape(label) for label in labels)
    pattern = re.compile(rf"(?:{label_pattern})\s*(?:[:：]|\s+)\s*([^\r\n,，;；]+)")
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def pick_labeled_fields(text, field_name):
    labels = FIELD_LABELS[field_name]
    label_pattern = "|".join(re.escape(label) for label in labels)
    pattern = re.compile(rf"(?:{label_pattern})\s*(?:[:：]|\s+)\s*([^\r\n,，;；]+)")
    return [match.strip() for match in pattern.findall(text) if match.strip()]


def unique_keep_order(values):
    result = []
    seen = set()
    for value in values:
        value = str(value or "").strip()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def pick_order_ids(text):
    values = []
    for field_value in pick_labeled_fields(text, "order_id"):
        values.extend(part.strip() for part in re.split(r"[/,，\s]+", field_value) if part.strip())

    for pattern in ORDER_ID_PATTERNS:
        for match in pattern.findall(text):
            if isinstance(match, tuple):
                match = next((item for item in match if item), "")
            values.extend(part.strip() for part in re.split(r"[/,，\s]+", match) if part.strip())

    values.extend(re.findall(r"(?m)^\s*([0-9]{15,30})\s*$", text))

    values = [value for value in values if re.fullmatch(r"\d{10,30}", value)]
    return "/".join(unique_keep_order(values))


def pick_total_price(text):
    blocks = get_relevant_order_blocks(text)
    values = []
    for block in blocks:
        for label in PRICE_LABEL_PRIORITY:
            pattern = re.compile(rf"{re.escape(label)}\s*[:：]\s*[￥¥]?\s*([0-9]+(?:\.[0-9]+)?)")
            match = pattern.search(block)
            if match:
                values.append(float(match.group(1)))
                break

    if not values:
        return ""

    return format_price(sum(values))


def parse_order_text(text):
    text = normalize_text(text)
    full_text = text
    text = filter_pending_order_text(text)
    return {
        "order_id": pick_order_ids(text),
        "buyer": pick_labeled_field(full_text, "buyer") or pick_buyer(full_text),
        "price": pick_total_price(text),
        "project": "",
        "system": pick_labeled_field(text, "system"),
        "role": pick_labeled_field(text, "role"),
        "phone": pick_phone_field(text),
        "account": pick_labeled_field(text, "account"),
        "password": pick_labeled_field(text, "password"),
        "server": pick_labeled_field(text, "server"),
        "insurance": pick_labeled_field(text, "insurance"),
    }


def merge_info(primary, fallback):
    return {key: primary.get(key) or fallback.get(key, "") for key in set(primary) | set(fallback)}


def parse_chat_input_text(text):
    text = normalize_text(text)
    return {
        "system": pick_labeled_field(text, "system"),
        "role": pick_labeled_field(text, "role") or pick_unlabeled_role(text),
        "phone": pick_phone_field(text),
        "account": pick_labeled_field(text, "account"),
        "password": pick_labeled_field(text, "password"),
        "server": pick_labeled_field(text, "server"),
        "insurance": pick_labeled_field(text, "insurance"),
    }


def merge_order_info_with_chat_input(order_info, chat_input_text):
    chat_info = parse_chat_input_text(chat_input_text) if chat_input_text.strip() else {}
    merged = merge_info(order_info, chat_info)
    # Order number and price must always come from the current right-side order data.
    for key in ("order_id", "price", "buyer", "project"):
        if order_info.get(key):
            merged[key] = order_info[key]
    return merged


def build_order_template(info):
    return f"""订单编号:{info["order_id"]}
淘宝旺旺:{info.get("buyer", "")}
接单价格:{info["price"]}
购买项目:{info["project"]}
系统:{info.get("system", "")}
游戏区服:{info.get("server", "")}
保险倍数:{info.get("insurance", "")}
角色名:{info.get("role", "")}
联系电话:{info.get("phone", "")}
游戏账号:{info.get("account") or "扫码"}
游戏密码:{info.get("password") or "扫码"}
"""


def get_order_info():
    quick_copy_info = copy_visible_quick_copy_orders_info()
    if quick_copy_info.get("order_id") and quick_copy_info.get("price"):
        return quick_copy_info

    right_orders_text = copy_right_orders_text()
    info = parse_order_text(right_orders_text)
    info["_right_orders_text_empty"] = not right_orders_text.strip()
    return info


def copy_right_orders_text():
    copied_text = ""

    for point in get_right_orders_click_points():
        copied_text = copy_selected_text_from_point(point)
        if copied_text.strip():
            break

    with Path("qianniu_last_right_orders_text.txt").open("w", encoding="utf-8") as f:
        f.write(copied_text)

    return copied_text


def get_right_orders_click_points():
    config_point = load_config().get("right_orders_panel")
    if config_point:
        yield config_point

    window_rect = get_qianniu_window_rect()
    if not window_rect:
        return

    for relative_point in RIGHT_ORDERS_FALLBACK_POINTS:
        yield {
            "x": int(window_rect["left"] + window_rect["width"] * relative_point["x"]),
            "y": int(window_rect["top"] + window_rect["height"] * relative_point["y"]),
        }


def copy_selected_text_from_point(point):
    marker = f"__QIANNIU_RIGHT_ORDERS_MARKER_{uuid.uuid4()}__"
    pyperclip.copy(marker)
    time.sleep(0.05)

    if pyautogui is None:
        return ""

    pyautogui.click(point["x"], point["y"])
    time.sleep(0.15)
    keyboard.press_and_release("ctrl+a")
    time.sleep(0.08)
    keyboard.press_and_release("ctrl+c")
    time.sleep(0.25)

    copied_text = pyperclip.paste()
    return "" if copied_text == marker else normalize_text(copied_text)


def copy_buyer_text():
    marker = f"__QIANNIU_BUYER_COPY_MARKER_{uuid.uuid4()}__"
    pyperclip.copy(marker)
    time.sleep(0.05)

    if not click_point("buyer_copy_button"):
        return ""

    time.sleep(0.25)
    copied_text = pyperclip.paste()
    if copied_text == marker:
        return ""

    return normalize_text(copied_text).strip()


def copy_order_system_text():
    marker = f"__QIANNIU_ORDER_COPY_MARKER_{uuid.uuid4()}__"
    pyperclip.copy(marker)
    time.sleep(0.05)

    copied_text = ""
    if click_quick_copy_button():
        time.sleep(0.5)
        copied_text = pyperclip.paste()
        if copied_text == marker:
            click_point("quick_copy_save_button")
            time.sleep(0.5)
            click_quick_copy_button()
            time.sleep(0.5)
            copied_text = pyperclip.paste()
        copied_text = "" if copied_text == marker else normalize_text(copied_text)

    with Path("qianniu_last_quick_copy.txt").open("w", encoding="utf-8") as f:
        f.write(copied_text)

    return copied_text


def copy_visible_quick_copy_orders_info():
    reset_right_panel_to_top()

    expected_count = get_expected_quick_copy_order_count()
    copied_texts = []
    order_items = {}
    buyer = ""
    seen_button_centers = []
    index = 0

    for scan_index in range(6):
        scan_name = "当前可见区域" if scan_index == 0 else f"下滑后第 {scan_index} 次可见区域"
        if scan_index > 0:
            scroll_right_orders_panel_down()

        buttons = [
            button for button in find_quick_copy_button_candidates()
            if not is_button_already_seen(button, seen_button_centers)
        ]
        if scan_index > 0:
            buttons.sort(key=lambda item: (item["center_y"], item["center_x"]), reverse=True)

        if not buttons:
            print(f"{scan_name}没有找到新的快捷复制按钮。")
            continue

        if expected_count and len(order_items) >= expected_count:
            print(f"已拿到 {len(order_items)}/{expected_count} 个订单，停止继续查找快捷复制。")
            break

        print(f"{scan_name}找到 {len(buttons)} 个新的快捷复制按钮。")
        for button in buttons:
            if expected_count and len(order_items) >= expected_count:
                print(f"已拿到 {len(order_items)}/{expected_count} 个订单，停止点击快捷复制。")
                break

            seen_button_centers.append((button["center_x"], button["center_y"]))
            index += 1
            text = copy_order_text_from_quick_copy_button(button, index)
            if not text.strip():
                print(f"第 {index} 个快捷复制按钮没有复制到内容。")
                continue

            copied_texts.append(text)
            info = parse_order_text(text)
            if not buyer and info.get("buyer"):
                buyer = info["buyer"]

            order_ids = [order_id for order_id in info.get("order_id", "").split("/") if order_id]
            if not order_ids or not info.get("price"):
                print(f"第 {index} 个快捷复制内容没有解析到订单号/价格。")
                continue

            price = float(info["price"])
            price_each = price / len(order_ids)
            new_order_added = False
            for order_id in order_ids:
                if order_id in order_items:
                    print(f"订单 {order_id} 已复制过，跳过重复计入。")
                    continue
                order_items[order_id] = {
                    "order_id": order_id,
                    "price": price_each,
                }
                new_order_added = True

            if scan_index > 0 and expected_count and len(order_items) < expected_count:
                if new_order_added:
                    print("本次下滑已拿到新订单，继续下滑找下一笔，避免反复点同屏旧订单。")
                else:
                    print("本次点到的是已有订单，直接继续下滑找新订单。")
                break

        if expected_count and len(order_items) >= expected_count:
            break

    if copied_texts:
        text = "\n\n".join(copied_texts)
        with Path("qianniu_last_quick_copy.txt").open("w", encoding="utf-8") as f:
            f.write(text)

    if not order_items:
        return {}

    total = sum(item["price"] for item in order_items.values())
    return {
        "order_id": "/".join(order_items),
        "price": format_price(total),
        "buyer": buyer,
        "project": "",
    }


def get_expected_quick_copy_order_count():
    text = get_pywinauto_right_side_text()
    match = re.search(r"待发货\((\d+)\)", text)
    if match:
        count = int(match.group(1))
        print(f"pywinauto 识别到待发货订单数: {count}。")
        return count

    match = re.search(r"全部\((\d+)\)", text)
    if match:
        count = int(match.group(1))
        print(f"pywinauto 识别到全部订单数: {count}。")
        return count

    return 0


def get_pywinauto_right_side_text():
    if Desktop is None:
        return ""

    window_rect = get_qianniu_window_rect()
    texts = []

    try:
        windows = Desktop(backend="uia").windows()
    except Exception:
        return ""

    for window in windows:
        try:
            name = str(window.window_text() or "")
        except Exception:
            name = ""

        if any(excluded in name for excluded in EXCLUDED_WINDOW_KEYWORDS):
            continue
        if not any(keyword_name in name for keyword_name in QIANNIU_WINDOW_KEYWORDS):
            continue

        try:
            descendants = window.descendants()
        except Exception:
            continue

        for control in descendants:
            try:
                text = str(control.window_text() or "").strip()
            except Exception:
                continue

            if not text:
                continue

            if window_rect:
                try:
                    rect = control.rectangle()
                except Exception:
                    continue

                if rect.left < window_rect["left"] + window_rect["width"] * 0.55:
                    continue

            texts.append(text)

    return "\n".join(texts)


def copy_order_text_from_quick_copy_button(button, index=None):
    marker = f"__QIANNIU_ORDER_COPY_MARKER_{uuid.uuid4()}__"
    pyperclip.copy(marker)
    time.sleep(0.01)

    control = button["control"]
    copied_text = invoke_quick_copy_control_by_pywinauto(control, marker)
    if copied_text == marker:
        print("pywinauto invoke 快捷复制未生效，改用坐标点击兜底。")
        if pyautogui is None:
            return ""
        pyautogui.click(button["center_x"], button["center_y"])
        copied_text = wait_for_clipboard_change(marker, timeout=0.28, interval=0.02)

    copied_text = "" if copied_text == marker else normalize_text(copied_text)
    if copied_text:
        order_id = parse_order_text(copied_text).get("order_id") or "未识别订单号"
        prefix = f"第 {index} 个" if index is not None else ""
        print(f"{prefix}已点击快捷复制: ({button['center_x']}, {button['center_y']}), {order_id}。")
    return copied_text


def invoke_quick_copy_control_by_pywinauto(control, marker):
    for action in (
        lambda: control.invoke(),
        lambda: control.iface_invoke.Invoke(),
    ):
        try:
            action()
        except Exception:
            continue

        copied_text = wait_for_clipboard_change(marker, timeout=0.18, interval=0.02)
        if copied_text != marker:
            return copied_text

    return marker


def find_quick_copy_button_candidates():
    candidates = find_pywinauto_controls_by_keyword("快捷复制")
    exact = [item for item in candidates if item["text"].strip() == "快捷复制"]
    small = [
        item for item in exact
        if (item["right"] - item["left"]) <= 180 and (item["bottom"] - item["top"]) <= 80
    ]

    buttons = small or exact
    buttons = unique_controls_by_center(buttons)
    buttons.sort(key=lambda item: (item["center_y"], item["center_x"]))
    if buttons:
        print(f"找到 {len(buttons)} 个可见快捷复制按钮，将按从上到下合并。")
    return buttons


def is_button_already_seen(button, seen_list, tolerance=20):
    """检查按钮是否已在已见列表中（使用容差匹配，避免滚动后坐标偏移导致重复点击）"""
    cx, cy = button["center_x"], button["center_y"]
    for seen_cx, seen_cy in seen_list:
        if abs(cx - seen_cx) <= tolerance and abs(cy - seen_cy) <= tolerance:
            return True
    return False


def unique_controls_by_center(items):
    result = []
    seen = set()
    for item in items:
        key = (item["center_x"], item["center_y"])
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def scroll_right_orders_panel_to_bottom():
    if pyautogui is None:
        return

    point = next(get_right_orders_click_points(), None)
    if not point:
        return

    pyautogui.click(point["x"], point["y"])
    time.sleep(0.1)
    keyboard.press_and_release("ctrl+end")
    time.sleep(0.1)
    keyboard.press_and_release("end")
    time.sleep(0.1)
    pyautogui.scroll(-30)
    time.sleep(0.35)


def scroll_right_orders_panel_down():
    if pyautogui is None:
        return

    point = next(get_right_orders_click_points(), None)
    if not point:
        return

    # 先把鼠标移到面板区域中心偏上位置，确保滚轮事件作用于正确区域
    window_rect = get_qianniu_window_rect()
    if window_rect:
        scroll_x = int(window_rect["left"] + window_rect["width"] * 0.83)
        scroll_y = int(window_rect["top"] + window_rect["height"] * 0.50)
    else:
        scroll_x, scroll_y = point["x"], point["y"]

    pyautogui.moveTo(scroll_x, scroll_y)
    time.sleep(0.04)
    pyautogui.click(scroll_x, scroll_y)
    time.sleep(0.04)
    # 多次大幅滚动，确保翻过至少一个订单卡
    for _ in range(4):
        pyautogui.scroll(-80)
        time.sleep(0.03)
    time.sleep(0.25)


def click_quick_copy_button():
    if click_quick_copy_button_by_pywinauto():
        return True

    config = load_config()
    point = config.get("quick_copy_button")
    if point and pyautogui is not None:
        pyautogui.click(point["x"], point["y"])
        time.sleep(0.2)
        return True

    if pyautogui is None:
        print("未安装 pyautogui，无法点击快捷复制。")
        return False

    window_rect = get_qianniu_window_rect()
    if not window_rect:
        print("没有找到千牛桌面端接待中心窗口，无法自动点击快捷复制。")
        return False

    for relative_point in QUICK_COPY_FALLBACK_POINTS:
        x = int(window_rect["left"] + window_rect["width"] * relative_point["x"])
        y = int(window_rect["top"] + window_rect["height"] * relative_point["y"])
        pyautogui.click(x, y)
        time.sleep(0.2)
        return True

    return False


def click_quick_copy_button_by_pywinauto():
    candidates = find_pywinauto_controls_by_keyword("快捷复制")
    target = choose_quick_copy_candidate(candidates)
    if not target:
        return False

    control = target["control"]
    try:
        control.click_input()
    except Exception:
        try:
            control.click()
        except Exception as exc:
            print(f"pywinauto 点击快捷复制失败: {exc}")
            return False

    time.sleep(0.2)
    print(f"已通过 pywinauto 点击快捷复制: ({target['center_x']}, {target['center_y']})。")
    return True


def choose_quick_copy_candidate(candidates):
    if not candidates:
        return None

    exact = [item for item in candidates if item["text"].strip() == "快捷复制"]
    small = [
        item for item in (exact or candidates)
        if (item["right"] - item["left"]) <= 180 and (item["bottom"] - item["top"]) <= 80
    ]
    pool = small or exact or candidates

    config_point = load_config().get("quick_copy_button")
    if config_point:
        return min(
            pool,
            key=lambda item: (item["center_x"] - config_point["x"]) ** 2
            + (item["center_y"] - config_point["y"]) ** 2,
        )

    return min(pool, key=lambda item: (item["right"] - item["left"]) * (item["bottom"] - item["top"]))


def copy_teammate_message_text():
    marker = f"__QIANNIU_COPY_MARKER_{uuid.uuid4()}__"
    pyperclip.copy(marker)
    time.sleep(0.05)
    keyboard.press_and_release("ctrl+c")
    time.sleep(0.25)

    copied_text = pyperclip.paste()
    if copied_text == marker:
        copied_text = ""
    else:
        copied_text = normalize_text(copied_text)

    return copied_text


def generate_template():
    chat_input_text = copy_chat_input_text()
    info = get_order_info()
    info = merge_order_info_with_chat_input(info, chat_input_text)

    missing = [name for name in ("order_id", "price") if not info.get(name)]
    if missing:
        if info.get("_right_orders_text_empty"):
            print("没有复制到右侧订单区域文本。请确认右侧近3个月订单区域可见，或按 Ctrl+9 校准 right_orders_panel。")
            print("Ctrl+1 已保存空内容到 qianniu_last_right_orders_text.txt。")
            return

        print(f"缺少字段: {', '.join(missing)}")
        print("Ctrl+1 已复制右侧订单区域，并保存到 qianniu_last_right_orders_text.txt。")
        print("请检查该文件里是否包含订单编号和明确价格字段，例如 接单价格/订单总付款/订单总价/实付金额/实付。")
        return

    template = build_order_template(info)
    pyperclip.copy(template)
    print(f"已自动读取订单 {info['order_id']}，价格 {info['price']}，并生成模板。")

    if paste_to_chat_input(template):
        print("已粘贴到千牛聊天输入框。")
    else:
        print("模板已复制到剪贴板，但未能自动粘贴。请按 Ctrl+9 校准 chat_input。")


def write_remark_from_clipboard():
    global PENDING_REMARK_TEXT

    text = copy_chat_input_text()
    if not text.strip():
        print("聊天输入框为空或未复制到内容，无法写备注。")
        return

    PENDING_REMARK_TEXT = text
    reset_right_panel_to_top()
    if click_remark_button_by_pywinauto():
        continue_write_remark_after_manual_open()
        return

    print("已暂存聊天输入框模板，但没有通过 pywinauto 找到备注按钮。")
    print("请手动点击右侧订单里的备注按钮，打开备注窗口后按 Ctrl+4 继续写入。")
    print("如需取消本次写备注，请按 Ctrl+7 清空暂存，或按 Ctrl+0 退出脚本。")

def continue_write_remark_after_manual_open():
    global PENDING_REMARK_TEXT

    text = PENDING_REMARK_TEXT
    if not text.strip():
        print("没有待写入的备注内容。请先按 Ctrl+2 读取聊天输入框模板。")
        return

    time.sleep(0.2)
    existing_remark = copy_existing_remark_text()
    if remark_already_has_order_info(existing_remark, text):
        print("备注里已经存在录单信息，跳过写入。")
        PENDING_REMARK_TEXT = ""
        return

    if click_point("remark_textarea"):
        time.sleep(0.3)
        if pyautogui is not None:
            point = load_config().get("remark_textarea")
            if point:
                pyautogui.click(point["x"], point["y"])
                time.sleep(0.1)
        paste_text_strict(text)
    click_point("remark_save_button")
    PENDING_REMARK_TEXT = ""
    print("已尝试写入备注。")


def click_remark_button_by_pywinauto():
    candidates = find_pywinauto_controls_by_keyword("备注")
    target = choose_remark_button_candidate(candidates)
    if not target:
        return False

    control = target["control"]
    if pyautogui is not None:
        pyautogui.click(target["center_x"], target["center_y"])
        time.sleep(0.12)

    try:
        control.click_input()
    except Exception:
        try:
            control.click()
        except Exception as exc:
            print(f"pywinauto 点击备注按钮失败: {exc}")
            return False

    time.sleep(0.35)
    print(f"已通过 pywinauto 点击备注按钮: ({target['center_x']}, {target['center_y']})。")
    return True


def choose_remark_button_candidate(candidates):
    if not candidates:
        return None

    exact = [item for item in candidates if item["text"].strip() == "备注"]
    small = [
        item for item in exact
        if (item["right"] - item["left"]) <= 140 and (item["bottom"] - item["top"]) <= 80
    ]
    pool = small or exact
    if not pool:
        return None

    config_point = load_config().get("remark_button")
    if config_point:
        return min(
            pool,
            key=lambda item: (item["center_x"] - config_point["x"]) ** 2
            + (item["center_y"] - config_point["y"]) ** 2,
        )

    return min(pool, key=lambda item: (item["center_y"], item["center_x"]))


def reset_right_panel_to_top():
    if pyautogui is None:
        return

    point = next(get_right_orders_click_points(), None)
    if not point:
        return

    pyautogui.click(point["x"], point["y"])
    time.sleep(0.1)
    keyboard.press_and_release("ctrl+home")
    time.sleep(0.1)
    keyboard.press_and_release("home")
    time.sleep(0.1)
    pyautogui.scroll(30)
    time.sleep(0.2)


def copy_chat_input_text():
    focus_chat_input_by_hotkey()

    marker = f"__QIANNIU_CHAT_INPUT_MARKER_{uuid.uuid4()}__"
    pyperclip.copy(marker)
    time.sleep(0.02)
    press_hotkey("ctrl", "a")
    time.sleep(0.03)
    press_hotkey("ctrl", "c")
    copied = wait_for_clipboard_change(marker, timeout=0.18, interval=0.03)
    copied = "" if copied == marker else normalize_text(copied)

    with Path("qianniu_last_chat_input_text.txt").open("w", encoding="utf-8") as f:
        f.write(copied)

    return copied


def copy_existing_remark_text():
    if not click_point("remark_textarea"):
        return ""

    marker = f"__QIANNIU_REMARK_MARKER_{uuid.uuid4()}__"
    pyperclip.copy(marker)
    time.sleep(0.05)
    keyboard.press_and_release("ctrl+a")
    time.sleep(0.05)
    keyboard.press_and_release("ctrl+c")
    time.sleep(0.15)
    copied = pyperclip.paste()
    return "" if copied == marker else normalize_text(copied)


def remark_already_has_order_info(existing_text, new_text):
    existing_text = normalize_text(existing_text or "")
    new_text = normalize_text(new_text or "")
    if not existing_text.strip():
        return False

    existing_digits = set(re.findall(r"\d{10,30}", existing_text))
    new_digits = set(re.findall(r"\d{10,30}", new_text))
    return bool(existing_digits & new_digits)


def transfer_customer():
    if not click_point("transfer_button"):
        return
    click_point("transfer_target")
    print("已尝试执行转接。")


def debug_find_quick_copy_controls():
    uia_candidates = find_controls_by_keyword("快捷复制")
    print_control_candidates("UIAutomation", uia_candidates)

    pywinauto_candidates = find_pywinauto_controls_by_keyword("快捷复制")
    print_control_candidates("pywinauto", pywinauto_candidates)

    if not uia_candidates and not pywinauto_candidates:
        print("UIAutomation 和 pywinauto 都没有找到“快捷复制”。右侧订单卡按钮大概率不是标准控件。")


def print_control_candidates(source, candidates):
    if not candidates:
        print(f"{source}: 没有找到“快捷复制”候选控件。")
        return

    print(f"{source}: 找到 {len(candidates)} 个“快捷复制”候选控件：")
    for index, item in enumerate(candidates, start=1):
        text = item["text"].replace("\n", " / ")
        print(
            f"{index}. center=({item['center_x']}, {item['center_y']}), "
            f"rect=({item['left']},{item['top']},{item['right']},{item['bottom']}), text={text}"
        )


def find_pywinauto_controls_by_keyword(keyword):
    if Desktop is None:
        print("未安装 pywinauto，无法使用 pywinauto 查找控件。")
        return []

    candidates = []
    window_rect = get_qianniu_window_rect()

    try:
        windows = Desktop(backend="uia").windows()
    except Exception as exc:
        print(f"pywinauto 获取窗口失败: {exc}")
        return []

    for window in windows:
        try:
            name = str(window.window_text() or "")
        except Exception:
            name = ""

        if any(excluded in name for excluded in EXCLUDED_WINDOW_KEYWORDS):
            continue
        if not any(keyword_name in name for keyword_name in QIANNIU_WINDOW_KEYWORDS):
            continue

        try:
            descendants = window.descendants()
        except Exception as exc:
            print(f"pywinauto 遍历窗口控件失败: {exc}")
            continue

        for control in descendants:
            try:
                text = str(control.window_text() or "")
            except Exception:
                text = ""

            if keyword not in text:
                continue

            try:
                rect = control.rectangle()
            except Exception:
                continue

            if rect.right <= rect.left or rect.bottom <= rect.top:
                continue

            if (
                window_rect
                and rect.left < window_rect["left"] + window_rect["width"] * 0.55
            ):
                continue

            candidates.append({
                "control": control,
                "text": text,
                "left": rect.left,
                "top": rect.top,
                "right": rect.right,
                "bottom": rect.bottom,
                "center_x": int((rect.left + rect.right) / 2),
                "center_y": int((rect.top + rect.bottom) / 2),
            })

    return candidates


def save_visible_text_for_debug():
    text = read_qianniu_visible_text()
    if text.strip():
        print("已保存当前千牛窗口可读文字到 qianniu_last_visible_text.txt。")
    else:
        print("没有读到千牛窗口文字，已写入空文件 qianniu_last_visible_text.txt。")


def calibrate_points():
    if not USE_CONFIG_FILE:
        print("坐标配置文件已停用，当前脚本使用快捷键、pywinauto 和窗口相对位置。")
        print("如需重新启用 qianniu_config.json，请把 USE_CONFIG_FILE 改为 True。")
        return

    if pyautogui is None:
        print("未安装 pyautogui，无法校准坐标。")
        return

    names = [
        ("quick_copy_button", "订单卡快捷复制按钮"),
        ("quick_copy_save_button", "快捷复制弹窗保存设置按钮"),
        ("buyer_copy_button", "旺旺号复制按钮"),
        ("right_orders_panel", "右侧近3个月订单区域"),
        ("chat_input", "聊天输入框"),
        ("remark_button", "订单备注按钮"),
        ("remark_textarea", "备注输入框"),
        ("remark_save_button", "备注保存按钮"),
        ("transfer_button", "转接按钮"),
        ("transfer_target", "转接目标客服"),
    ]

    config = load_config()
    print("开始校准。每一步把鼠标移动到对应位置，然后按 Enter。")
    for key, label in names:
        input(f"请把鼠标放到【{label}】位置，然后按 Enter...")
        x, y = pyautogui.position()
        config[key] = {"x": x, "y": y}
        print(f"{label}: x={x}, y={y}")

    save_config(config)
    print(f"校准完成，已保存到 {CONFIG_PATH}。")


def run_with_uia_initialized(action):
    if auto is None:
        action()
        return

    try:
        with auto.UIAutomationInitializerInThread():
            action()
    except AttributeError:
        action()
    except Exception as exc:
        print(f"执行失败: {exc}")


def main():
    load_config()

    print("千牛客户端辅助已启动。")
    print("Ctrl+1: 读取右侧订单数据，生成录单模板并粘贴到聊天输入框")
    print("Ctrl+2: 读取聊天输入框内容，等待手动打开备注后写入")
    print("Ctrl+3: 执行转接")
    print("Ctrl+4: 手动打开备注窗口后继续 Ctrl+2 写入")
    print("Ctrl+5: 排查 UIAutomation 是否能找到“快捷复制”控件")
    print("Ctrl+6: 将当前剪贴板里的单笔待发货订单加入订单篮子")
    print("Ctrl+7: 清空订单篮子")
    print("Ctrl+8: 保存当前窗口可读文字，便于排查")
    print("Ctrl+9: 可选校准。默认会按千牛窗口比例自动点击聊天输入框")
    print("Ctrl+0: 退出")

    keyboard.add_hotkey("ctrl+1", lambda: run_with_uia_initialized(generate_template))
    keyboard.add_hotkey("ctrl+2", lambda: run_with_uia_initialized(write_remark_from_clipboard))
    keyboard.add_hotkey("ctrl+3", lambda: run_with_uia_initialized(transfer_customer))
    keyboard.add_hotkey("ctrl+4", lambda: run_with_uia_initialized(continue_write_remark_after_manual_open))
    keyboard.add_hotkey("ctrl+5", lambda: run_with_uia_initialized(debug_find_quick_copy_controls))
    keyboard.add_hotkey("ctrl+6", add_clipboard_order_to_basket)
    keyboard.add_hotkey("ctrl+7", clear_basket)
    keyboard.add_hotkey("ctrl+8", lambda: run_with_uia_initialized(save_visible_text_for_debug))
    keyboard.add_hotkey("ctrl+9", calibrate_points)
    keyboard.wait("ctrl+0")
    print("程序已退出。")


if __name__ == "__main__":
    main()
