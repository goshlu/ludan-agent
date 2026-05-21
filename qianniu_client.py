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

QIANNIU_WINDOW_KEYWORDS = ("接待中心",)
EXCLUDED_WINDOW_KEYWORDS = ("Google Chrome", "myseller.taobao.com", "Visual Studio Code", "PyCharm")

RIGHT_ORDERS_FALLBACK_POINTS = (
    {"x": 0.83, "y": 0.55},
    {"x": 0.83, "y": 0.65},
    {"x": 0.77, "y": 0.55},
    {"x": 0.89, "y": 0.55},
)


ORDER_ID_PATTERNS = [
    re.compile(r"(?:订单编号|订单号)\s*[:：]?\s*([0-9]{10,30}(?:/[0-9]{10,30})*)"),
    re.compile(r"(?:待发货|未完成|已完成|已关闭)?\s*([0-9]{15,30})\s*(?:详情|开票|订单|备注)"),
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


def format_price(value):
    value = float(value)
    return str(int(value)) if value.is_integer() else f"{value:.2f}".rstrip("0").rstrip(".")


def release_keyboard_modifiers():
    for key in ("ctrl", "shift", "alt"):
        try:
            keyboard.release(key)
        except Exception:
            pass

    if pyautogui is None:
        return

    for key in ("ctrl", "shift", "alt"):
        try:
            pyautogui.keyUp(key)
        except Exception:
            pass


def wait_for_modifier_keys_released(timeout=1.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if not any(keyboard.is_pressed(key) for key in ("ctrl", "shift", "alt")):
                return True
        except Exception:
            return False
        time.sleep(0.03)
    return False


def wait_for_clipboard_change(marker, timeout=0.35, interval=0.03):
    deadline = time.time() + timeout
    while time.time() < deadline:
        copied_text = pyperclip.paste()
        if copied_text != marker:
            return copied_text
        time.sleep(interval)
    return pyperclip.paste()


def get_qianniu_pywinauto_window():
    if Desktop is None:
        return None

    try:
        windows = Desktop(backend="uia").windows()
    except Exception:
        return None

    for window in windows:
        try:
            name = str(window.window_text() or "")
        except Exception:
            name = ""

        if any(excluded in name for excluded in EXCLUDED_WINDOW_KEYWORDS):
            continue
        if not any(keyword_name in name for keyword_name in QIANNIU_WINDOW_KEYWORDS):
            continue

        return window

    return None


def focus_qianniu_window_by_pywinauto():
    window = get_qianniu_pywinauto_window()
    if not window:
        return False

    try:
        window.restore()
    except Exception:
        pass

    try:
        window.set_focus()
        time.sleep(0.15)
        return True
    except Exception:
        return False


def send_qianniu_hotkey(keys):
    focused = focus_qianniu_window_by_pywinauto()
    send_hotkey(keys)
    return focused


def send_hotkey(keys):
    release_keyboard_modifiers()
    time.sleep(0.03)
    key_map = {
        "^i": ("ctrl", "i"),
        "^a": ("ctrl", "a"),
        "^c": ("ctrl", "c"),
        "^v": ("ctrl", "v"),
    }
    if pyautogui is not None and keys in key_map:
        pyautogui.hotkey(*key_map[keys])
        return

    if keys == "^i":
        keyboard.press_and_release("ctrl+i")
    elif keys == "^a":
        keyboard.press_and_release("ctrl+a")
    elif keys == "^c":
        keyboard.press_and_release("ctrl+c")
    elif keys == "^v":
        keyboard.press_and_release("ctrl+v")
    else:
        keyboard.press_and_release(keys.replace("^", "ctrl+"))


def focus_chat_input_by_hotkey():
    focused = send_qianniu_hotkey("^i")
    time.sleep(0.28)
    return focused


def paste_text_to_focused_input(text):
    pyperclip.copy(text)
    time.sleep(0.18)
    send_hotkey("^v")
    time.sleep(0.25)
    pyperclip.copy(text)


def paste_to_chat_input_by_hotkey(text):
    wait_for_modifier_keys_released(timeout=1.0)
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


def rect_to_dict(rect):
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width <= 300 or height <= 300:
        return None
    return {
        "left": rect.left,
        "top": rect.top,
        "right": rect.right,
        "bottom": rect.bottom,
        "width": width,
        "height": height,
    }


def get_qianniu_window_rect_by_pywinauto():
    if Desktop is None:
        return None

    try:
        windows = Desktop(backend="uia").windows()
    except Exception:
        return None

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
            rect = window.rectangle()
        except Exception:
            continue

        rect_dict = rect_to_dict(rect)
        if rect_dict:
            return rect_dict

    return None


def get_qianniu_window_rect():
    if auto is None:
        return get_qianniu_window_rect_by_pywinauto()

    candidates = []
    focused = get_focused_top_window()
    if focused and looks_like_qianniu_window(focused):
        candidates.append(focused)

    candidates.extend(window for window in get_desktop_windows() if looks_like_qianniu_window(window))

    for window in candidates:
        try:
            rect = window.BoundingRectangle
            rect_dict = rect_to_dict(rect)
            if rect_dict:
                return rect_dict
        except Exception:
            continue

    return get_qianniu_window_rect_by_pywinauto()


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


def copy_visible_quick_copy_orders_info():
    reset_right_panel_to_top()

    expected_count = get_expected_quick_copy_order_count()
    copied_texts = []
    order_items = {}
    buyer = ""
    seen_button_centers = []
    index = 0
    scroll_boost = 0

    max_scan_count = max(6, min(18, expected_count * 3 if expected_count else 6))
    for scan_index in range(max_scan_count):
        scan_name = "当前可见区域" if scan_index == 0 else f"下滑后第 {scan_index} 次可见区域"
        if scan_index > 0:
            print(f"准备下滑继续查找订单: 已拿到 {len(order_items)}/{expected_count or '?'}。")
            scroll_right_orders_panel_down(extra_steps=scroll_boost)
            scroll_boost = 0

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
                    scroll_boost = 1
                else:
                    print("本次点到的是已有订单，下一次加大下滑幅度找新订单。")
                    scroll_boost = 3
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


def scroll_right_orders_panel_down(extra_steps=0):
    if pyautogui is None:
        print("未安装 pyautogui，无法下滑右侧订单面板。")
        return

    point = next(get_right_orders_click_points(), None)
    if not point:
        print("没有定位到右侧订单面板，跳过本次下滑。")
        return

    # 多次大幅滚动，确保翻过至少一个订单卡；遇到重复订单后会加大幅度跳过重叠区域。
    steps = 4 + max(0, int(extra_steps))
    print(f"正在下滑右侧订单面板: {steps} 次。")
    pyautogui.moveTo(point["x"], point["y"])
    time.sleep(0.03)
    pyautogui.click(point["x"], point["y"])
    time.sleep(0.03)
    for _ in range(steps):
        pyautogui.scroll(-80)
        time.sleep(0.02)
    time.sleep(0.25 + min(0.12, max(0, extra_steps) * 0.03))


def generate_template():
    chat_input_text = copy_chat_input_text()
    info = get_order_info()
    info = merge_order_info_with_chat_input(info, chat_input_text)

    missing = [name for name in ("order_id", "price") if not info.get(name)]
    if missing:
        if info.get("_right_orders_text_empty"):
            print("没有复制到右侧订单区域文本。请确认右侧近3个月订单区域可见。")
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
        print("模板已复制到剪贴板，但未能自动粘贴。")


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
    send_hotkey("^a")
    time.sleep(0.03)
    send_hotkey("^c")
    copied = wait_for_clipboard_change(marker, timeout=0.18, interval=0.03)
    copied = "" if copied == marker else normalize_text(copied)

    with Path("qianniu_last_chat_input_text.txt").open("w", encoding="utf-8") as f:
        f.write(copied)

    return copied


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
    print("千牛客户端辅助已启动。")
    print("Ctrl+1: 读取右侧订单数据，生成录单模板并粘贴到聊天输入框")
    print("Ctrl+0: 退出")

    keyboard.add_hotkey("ctrl+1", lambda: run_with_uia_initialized(generate_template))
    keyboard.wait("ctrl+0")
    print("程序已退出。")


if __name__ == "__main__":
    main()
