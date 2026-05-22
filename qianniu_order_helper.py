import time
import re
import keyboard
import pyperclip
import uiautomation as auto

try:
    import pythoncom
except ImportError:
    pythoncom = None

try:
    import comtypes
except ImportError:
    comtypes = None


QIANNIU_WINDOW_PATTERNS = [
    r".*接待中心.*",
    r".*千牛.*",
    r".*接待.*",
    r".*工作台.*",
]

QUICK_COPY_NAME = "快捷复制"
ROLE_NAME_MAX_LENGTH = 30
INVALID_ROLE_TEXT_KEYWORDS = (
    "有可能",
    "那么",
    "默认值",
    "订单编号",
    "系统区服",
    "购买项目",
    "联系电话",
    "游戏账号",
    "游戏密码",
    "订单来源",
)


def co_initialize():
    try:
        if pythoncom:
            pythoncom.CoInitialize()
            return "pythoncom"
    except Exception:
        pass

    try:
        if comtypes:
            comtypes.CoInitialize()
            return "comtypes"
    except Exception:
        pass

    return None


def co_uninitialize(mode):
    try:
        if mode == "pythoncom" and pythoncom:
            pythoncom.CoUninitialize()
        elif mode == "comtypes" and comtypes:
            comtypes.CoUninitialize()
    except Exception:
        pass


def send_ctrl_key(key, fallback="{Ctrl}"):
    try:
        keyboard.press_and_release(f"ctrl+{key}")
        return
    except Exception:
        pass

    auto.SendKeys(f"{fallback}{key}")


def find_qianniu_window():
    for pattern in QIANNIU_WINDOW_PATTERNS:
        try:
            win = auto.WindowControl(searchDepth=1, RegexName=pattern)
            if win.Exists(1):
                return win
        except Exception:
            pass
    return None


def print_top_windows():
    print("\n当前顶层窗口：")
    try:
        root = auto.GetRootControl()
        for win in root.GetChildren():
            try:
                name = win.Name
                if name:
                    print("-", name)
            except Exception:
                pass
    except Exception as e:
        print("读取窗口列表失败:", e)


def get_rect(control):
    try:
        r = control.BoundingRectangle
        return r.left, r.top, r.right, r.bottom
    except Exception:
        return 0, 0, 0, 0


def top_value(control):
    return get_rect(control)[1]


def find_controls_by_name(control, target_name, depth=0, max_depth=18):
    result = []
    if depth > max_depth:
        return result

    try:
        name = control.Name or ""
        if name.strip() == target_name:
            result.append(control)
    except Exception:
        pass

    try:
        for child in control.GetChildren():
            result.extend(find_controls_by_name(child, target_name, depth + 1, max_depth))
    except Exception:
        pass

    return result


def find_controls_contains_name(control, keyword, depth=0, max_depth=18):
    result = []
    if depth > max_depth:
        return result

    try:
        name = control.Name or ""
        if keyword in name:
            result.append(control)
    except Exception:
        pass

    try:
        for child in control.GetChildren():
            result.extend(find_controls_contains_name(child, keyword, depth + 1, max_depth))
    except Exception:
        pass

    return result



def is_visible_control(control):
    try:
        l, t, r, b = get_rect(control)
        return r > l and b > t
    except Exception:
        return False


def get_control_name(control):
    try:
        return control.Name or ""
    except Exception:
        return ""


def get_control_type(control):
    try:
        return control.ControlTypeName or ""
    except Exception:
        return ""



def collect_visible_text_controls(control, depth=0, max_depth=18):
    """
    收集当前窗口可见文本控件，用于判断订单状态。
    """
    result = []
    if depth > max_depth:
        return result

    try:
        name = get_control_name(control).strip()
        ct = get_control_type(control)
        l, t, r, b = get_rect(control)

        if name and r > l and b > t:
            result.append({
                "name": name,
                "type": ct,
                "rect": (l, t, r, b),
                "top": t,
                "bottom": b,
                "left": l,
                "right": r,
            })
    except Exception:
        pass

    try:
        for child in control.GetChildren():
            result.extend(collect_visible_text_controls(child, depth + 1, max_depth))
    except Exception:
        pass

    return result


def is_pending_delivery_order_button(btn, win, visible_texts=None):
    """
    判断某个【快捷复制】按钮是否属于【待发货】订单。

    逻辑：
    1. 取按钮所在行的坐标
    2. 在按钮左侧同行区域查找状态文本（±40px 垂直范围）
    3. 左侧同行找到坏状态 → 跳过；找到待发货 → 通过
    4. 左侧同行未找到状态 → 扩大到 ±200px 检查附近有无坏状态
    5. 附近无坏状态 → 默认通过（待发货订单的状态标签可能在tab而非卡片内）
    """
    bl, bt, br, bb = get_rect(btn)
    if br <= bl or bb <= bt:
        return False

    row_center_y = (bt + bb) / 2
    texts = visible_texts if visible_texts is not None else collect_visible_text_controls(win)

    bad_status = [
        "交易成功", "已完成", "已关闭", "交易关闭", "已取消",
        "退款", "退款成功", "售后", "待付款", "待评价"
    ]
    pending_status = "待发货"

    # 第一步：在按钮左侧同行区域（±40px 垂直，按钮左侧 60~300px）查找状态
    left_row_status = None
    left_row_status_type = None
    left_row_status_dist = float("inf")

    for item in texts:
        name = item["name"]
        il, it, ir, ib = item["rect"]
        item_cy = (it + ib) / 2
        v_dist = abs(item_cy - row_center_y)

        if v_dist > 40:
            continue
        if ir > bl - 20 or il < bl - 400:
            continue

        for status in bad_status:
            if status in name:
                h_dist = bl - ir
                dist = h_dist + v_dist
                if dist < left_row_status_dist:
                    left_row_status_dist = dist
                    left_row_status = name
                    left_row_status_type = "bad"
                break

        if pending_status in name and "(" not in name:
            h_dist = bl - ir
            dist = h_dist + v_dist
            if dist < left_row_status_dist:
                left_row_status_dist = dist
                left_row_status = name
                left_row_status_type = "pending"

    if left_row_status_type == "bad":
        print(f"跳过订单：左侧同行找到坏状态「{left_row_status}」(d={left_row_status_dist:.0f})")
        return False
    if left_row_status_type == "pending":
        return True

    # 第二步：左侧同行未找到状态，扩大范围检查附近有无坏状态（±200px）
    nearest_bad_dist = float("inf")
    nearest_bad_name = None
    nearest_pending_dist = float("inf")

    for item in texts:
        name = item["name"]
        il, it, ir, ib = item["rect"]
        item_cy = (it + ib) / 2
        v_dist = abs(item_cy - row_center_y)

        if v_dist > 200:
            continue

        for status in bad_status:
            if status in name:
                h_dist = max(0, il - br) if il > br else max(0, bl - ir)
                dist = h_dist + v_dist * 2
                if dist < nearest_bad_dist:
                    nearest_bad_dist = dist
                    nearest_bad_name = name
                break

        if pending_status in name and "(" not in name:
            h_dist = max(0, il - br) if il > br else max(0, bl - ir)
            dist = h_dist + v_dist * 2
            if dist < nearest_pending_dist:
                nearest_pending_dist = dist

    if nearest_bad_dist < float("inf") and nearest_pending_dist >= float("inf"):
        print(f"跳过订单：附近找到坏状态「{nearest_bad_name}」(d={nearest_bad_dist:.0f})，无待发货")
        return False
    if nearest_bad_dist < float("inf") and nearest_pending_dist < float("inf"):
        if nearest_pending_dist <= nearest_bad_dist:
            return True
        print(f"跳过订单：坏状态(d={nearest_bad_dist:.0f}) < 待发货(d={nearest_pending_dist:.0f})")
        return False

    # 第三步：附近无坏状态也无待发货 → 默认通过
    return True






    edit = find_remark_input_control(root)

    if not edit:
        print("已打开备注窗口，但未找到【请输入备注内容】输入控件")
        return False

    try:
        edit.SetFocus()
        time.sleep(0.01)
    except Exception:
        pass

    # 优先 ValuePattern
    wrote = False
    try:
        edit.GetValuePattern().SetValue(text)
        wrote = True
        print("已通过 ValuePattern 写入备注")
        time.sleep(0.02)
    except Exception:
        pass

    # ValuePattern 不行再 Ctrl+V
    if not wrote:
        try:
            edit.Click(simulateMove=False)
            time.sleep(0.01)
        except Exception:
            try:
                edit.Click()
                time.sleep(0.01)
            except Exception:
                pass

        try:
            auto.SendKeys("{Ctrl}a")
            time.sleep(0.02)
            auto.SendKeys("{Ctrl}v")
            time.sleep(0.03)
            wrote = True
            print("已通过 Ctrl+V 粘贴备注")
        except Exception as e:
            print("粘贴备注失败:", e)
            return False

    btn = find_confirm_button_for_remark(root)

    if not btn:
        print("已写入备注，但未找到【确定】控件，请手动点确定")
        return False

    if invoke_or_click(btn):
        print("已点击确定")
        time.sleep(0.02)
        return True

    print("确定控件点击失败")
    return False


def invoke_or_click(control):
    try:
        control.GetInvokePattern().Invoke()
        return True
    except Exception:
        pass

    try:
        control.Click(simulateMove=False)
        return True
    except Exception:
        pass

    try:
        control.Click()
        return True
    except Exception as e:
        print("点击控件失败:", e)
        return False





def find_current_wangwang_name(win):
    """
    获取右侧顶部当前买家旺旺名。
    识别你箭头指向的右侧顶部昵称，例如：爱读书的小胖纸。
    """
    candidates = []

    exclude_keywords = [
        "客服", "设置", "邀请关注", "添加备注", "邀请入会",
        "历史订单", "近3个月订单", "优惠券", "普通", "好评", "非会员",
        "足迹", "推荐", "商品", "订单", "备注", "详情", "开票", "工单",
        "待发货", "未完成", "已完成", "已关闭", "全部", "搜索",
        "店铺身份", "店铺消费", "暂无交易成功", "操作指南"
    ]

    def clean_name(name):
        name = (name or "").strip()
        name = re.sub(r'好评\d+(\.\d+)?%', '', name)
        name = name.replace("普通", "")
        name = re.sub(r'[💎⭐❤]+', '', name)
        name = re.sub(r'\s+', '', name).strip()
        return name

    def looks_like_wangwang(name):
        if not name:
            return False

        if any(k in name for k in exclude_keywords):
            return False

        if len(name) > 24:
            return False

        if not re.search(r'[\u4e00-\u9fa5A-Za-z0-9]', name):
            return False

        if re.fullmatch(r'[\d\.\-:￥¥/]+', name):
            return False

        return True

    def walk(control, depth=0):
        if depth > 18:
            return

        try:
            name_raw = control.Name or ""
            name = clean_name(name_raw)
            ct = control.ControlTypeName or ""
            l, t, r, b = get_rect(control)
            w = r - l
            h = b - t

            if name and looks_like_wangwang(name):
                # 右侧顶部买家昵称区域
                if l >= 850 and 80 <= t <= 280 and w > 20 and h > 8:
                    score = 0

                    if re.search(r'[\u4e00-\u9fa5]', name):
                        score += 1000

                    score += max(0, 300 - t)
                    score += max(0, 30 - abs(len(name) - 7))

                    if "Text" in ct:
                        score += 200
                    if "Group" in ct or "Pane" in ct:
                        score += 80
                    if "Button" in ct:
                        score += 50

                    candidates.append((score, name, ct, (l, t, r, b), name_raw))

        except Exception:
            pass

        try:
            for child in control.GetChildren():
                walk(child, depth + 1)
        except Exception:
            pass

    walk(win)

    if not candidates:
        print("未识别到旺旺名")
        return ""

    candidates.sort(key=lambda x: x[0], reverse=True)

    print("\\n============= 旺旺名候选 =============")
    for i, (score, name, ct, rect, raw) in enumerate(candidates[:10], 1):
        print(f"{i}. score={score}, name={name}, type={ct}, rect={rect}, raw={raw}")
    print("=====================================\\n")

    return candidates[0][1]



def extract_order_id(text):
    if not text:
        return ""

    m = re.search(r"订单编号[:：]?\s*([0-9/]+)", text)
    if m:
        return m.group(1)

    m = re.search(r"订单号[:：]?\s*([0-9/]+)", text)
    if m:
        return m.group(1)

    m = re.search(r"5\d{17,20}", text)
    if m:
        return m.group(0)

    return ""


def copy_from_quick_copy_button(btn, index=1):
    old_clipboard = pyperclip.paste()

    if not invoke_or_click(btn):
        print(f"第 {index} 个快捷复制按钮执行失败")
        return ""

    time.sleep(0.03)

    copied = pyperclip.paste()

    if copied and copied != old_clipboard:
        print(f"第 {index} 个订单快捷复制成功")
        return copied

    if copied:
        print(f"第 {index} 个订单剪切板未变化，但仍读取当前剪切板")
        return copied

    print(f"第 {index} 个订单快捷复制为空")
    return ""


def is_pending_delivery_from_copied_text(text):
    """
    从快捷复制的文本内容中判断是否为【待发货】订单。
    快捷复制的文本通常包含订单状态信息，如"待发货"、"已完成"等。
    """
    bad_status = [
        "交易成功", "已完成", "已关闭", "交易关闭", "已取消",
        "退款", "退款成功", "售后", "待付款", "待评价"
    ]
    for status in bad_status:
        if status in text:
            return False
    return True


def copy_all_visible_orders(win):
    quick_buttons = sorted(find_controls_by_name(win, QUICK_COPY_NAME), key=top_value)

    if not quick_buttons:
        print("未找到【快捷复制】按钮，请展开右侧近3个月订单。")
        return []

    print(f"找到 {len(quick_buttons)} 个【快捷复制】按钮，开始复制并检查状态。")

    copied_list = []
    seen = set()

    for index, btn in enumerate(quick_buttons, 1):
        copied = copy_from_quick_copy_button(btn, index)

        if not copied:
            continue

        # 从复制的文本内容判断是否为待发货订单
        if not is_pending_delivery_from_copied_text(copied):
            order_id = extract_order_id(copied) or "未知"
            print(f"第 {index} 个订单不是【待发货】（订单号：{order_id}），跳过。")
            continue

        order_id = extract_order_id(copied)
        key = order_id if order_id else str(hash(copied))

        if key in seen:
            print(f"第 {index} 个待发货订单已复制过，跳过")
            continue

        seen.add(key)
        copied_list.append(copied)
        print(f"第 {index} 个订单状态为【待发货】，已复制（订单号：{order_id}）。")

    if not copied_list:
        print("当前可见订单中未找到【待发货】订单，停止复制。")
        return []

    print(f"共找到 {len(copied_list)} 个【待发货】订单，开始合并。")
    return copied_list







    roots.sort(key=lambda x: 0 if "订单备注" in (x.Name or "") else 1)

    for root in roots:
        try:
            edit = find_remark_input_control(root)

            if edit:
                print("找到备注输入控件:", edit.Name, edit.ControlTypeName)
                try:
                    edit.SetFocus()
                except Exception:
                    pass
                try:
                    invoke_or_click(edit)
                except Exception:
                    pass
            else:
                print("未找到标准备注输入控件，使用弹窗区域兜底点击。")
                click_remark_textarea_by_dialog_rect(root)

            time.sleep(0.01)

            auto.SendKeys("{Ctrl}a")
            time.sleep(0.02)
            auto.SendKeys("{Ctrl}v")
            time.sleep(0.02)

            btn = find_confirm_button(root)

            if not btn:
                print("未找到确定按钮，内容已粘贴，请手动点确定。")
                return False

            if invoke_or_click(btn):
                print("已点击确定")
                time.sleep(0.03)
                return True

        except Exception as e:
            print("处理备注弹窗失败:", e)

    print("所有备注弹窗处理失败。")
    return False




def parse_money(value):
    try:
        return float(str(value).strip())
    except Exception:
        return 0.0


def parse_pay_time(text):
    m = re.search(r"付款时间[:：]\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", text)
    if not m:
        return None

    try:
        from datetime import datetime
        return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def extract_pay_amount(text):
    m = re.search(r"订单总付款[:：]\s*([0-9.]+)", text)
    if m:
        return parse_money(m.group(1))
    return 0.0


def extract_buyer_wangwang_from_order(text):
    m = re.search(r"买家旺旺[:：]\s*(.+)", text)
    if m:
        return m.group(1).strip()
    return ""


def attach_wangwang_to_orders(copied_list, wangwang_name):
    result = []

    for text in copied_list:
        item = text.strip()

        if "买家旺旺" not in item and wangwang_name:
            item = item + f"\n买家旺旺：{wangwang_name}"

        result.append(item)

    return result


def filter_orders_within_5_minutes(copied_list):
    """
    第一单永远保留。
    后续订单只有与第一单付款时间间隔 <= 5 分钟才保留。
    超过 5 分钟：不合并、不写备注。

    特殊情况：如果快捷复制的文本中不含付款时间字段（千牛快捷复制
    通常不包含付款时间），则全部保留，不做时间过滤。
    """
    if not copied_list:
        return []

    first_text = copied_list[0]
    first_time = parse_pay_time(first_text)

    if not first_time:
        print("未识别到付款时间，跳过时间过滤，保留全部订单。")
        return copied_list[:]

    result = [first_text]

    for index, text in enumerate(copied_list[1:], 2):
        pay_time = parse_pay_time(text)

        if not pay_time:
            print(f"第 {index} 单未识别到付款时间，保留该订单。")
            result.append(text)
            continue

        diff_seconds = abs((pay_time - first_time).total_seconds())
        diff_minutes = diff_seconds / 60

        if diff_minutes <= 50000:
            print(f"第 {index} 单付款时间间隔 {diff_minutes:.2f} 分钟，合并并备注。")
            result.append(text)
        else:
            print(f"第 {index} 单付款时间间隔 {diff_minutes:.2f} 分钟，超过 5 分钟，跳过，不备注。")

    return result



def normalize_role_phone_text(text):
    text = (text or "").strip()
    text = text.replace("\u3000", " ")
    text = re.sub(r"[，,。;；]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_role_name(text):
    text = normalize_role_phone_text(text)
    text = re.sub(r"^(?:角色名|角色名称|角色|昵称)\s*[:：]\s*", "", text).strip()
    return text


def is_valid_role_name(text):
    text = clean_role_name(text)
    if not text:
        return False
    if len(text) > ROLE_NAME_MAX_LENGTH:
        return False
    if re.search(r"(?:^|\s)\d+[、.)．]", text):
        return False
    if any(keyword in text for keyword in INVALID_ROLE_TEXT_KEYWORDS):
        return False
    return True


def parse_selected_role_phone(text):
    """
    支持两类输入：
    1. 黑 白 15712347593
    2. 角色名：黑 白 联系电话：15712347593

    缺省规则：
    - 只有角色名：电话用“老板没输入号码”
    - 只有电话：角色名用“老板没有输入角色名”
    - 都没有：都返回空
    """
    selected = normalize_role_phone_text(text)
    if not selected:
        return "", ""

    labeled_phone = re.search(
        r"(?:联系电话|手机号|手机|电话)\s*[:：]\s*(1[3-9]\d{9})(?!\d)",
        selected,
    )
    labeled_role = re.search(
        r"(?:角色名|角色名称|角色|昵称)\s*[:：]\s*(.+?)(?=\s*(?:联系电话|手机号|手机|电话)\s*[:：]|$)",
        selected,
    )
    if labeled_phone or labeled_role:
        role_name = clean_role_name(labeled_role.group(1)) if labeled_role else ""
        if role_name and not is_valid_role_name(role_name):
            role_name = ""
        phone = labeled_phone.group(1) if labeled_phone else ""
        if role_name and not phone:
            phone = "老板没输入号码"
        elif phone and not role_name:
            role_name = "老板没有输入角色名"
        return role_name, phone

    match = re.search(r"^(.+?)\s+(1[3-9]\d{9})$", selected)
    if match:
        role_name = clean_role_name(match.group(1))
        if not is_valid_role_name(role_name):
            role_name = "老板没有输入角色名"
        return role_name, match.group(2)

    phone_match = re.search(r"^(1[3-9]\d{9})$", selected)
    if phone_match:
        return "老板没有输入角色名", phone_match.group(1)

    if selected and is_valid_role_name(selected):
        return clean_role_name(selected), "老板没输入号码"

    return "", ""


def read_selected_role_phone(win=None):
    """
    Ctrl+1执行时：
    先读取聊天输入框里的【角色名 + 电话】。
    示例：
        徐百 18724561112
        徐百，18724561112
        徐百　18724561112

    解析后写入固定格式：
        角色名：徐百
        联系电话：18724561112
    """
    old_clip = pyperclip.paste()

    try:
        marker = f"__QIANNIU_ROLE_PHONE_MARKER_{time.time()}__"
        pyperclip.copy(marker)

        if win:
            try:
                win.SetActive()
                time.sleep(0.005)
            except Exception:
                pass

        send_ctrl_key("i")
        time.sleep(0.005)
        send_ctrl_key("a")
        time.sleep(0.005)
        send_ctrl_key("c")
        time.sleep(0.01)

        selected = pyperclip.paste()
        if selected == marker:
            selected = ""

        role_name, phone = parse_selected_role_phone(selected)

        print(f"已读取输入区原文: {selected}")
        print(f"已读取角色名: {role_name}")
        print(f"已读取电话: {phone}")

        return role_name, phone

    except Exception as e:
        print("读取选中角色名和电话失败，使用默认值:", e)
        pyperclip.copy(old_clip)
        return "", ""


def format_final_order_remark(copied_list, wangwang_name="", role_name="", phone=""):
    order_ids = []
    total_amount = 0.0
    buyer_ww = ""

    for text in copied_list:
        order_id = extract_order_id(text)
        if order_id:
            order_ids.append(order_id)

        total_amount += extract_pay_amount(text)

        if not buyer_ww:
            buyer_ww = extract_buyer_wangwang_from_order(text)

    if not buyer_ww:
        buyer_ww = ""

    order_id_text = "/".join(order_ids)
    price_text = f"{total_amount:.2f}"

    return f"""订单编号：{order_id_text}
系统区服：B服
旺旺：{buyer_ww}
购买项目：原神6.6的9-10主线
游戏大区：QQ
角色名：{role_name}
当前等级：11
接单价格：{price_text}
联系电话：{phone}
游戏账号：扫码
游戏密码：扫码
订单来源：宝珠姐"""



def merge_order_texts(copied_list, role_name="", phone=""):
    return format_final_order_remark(copied_list, role_name=role_name, phone=phone)



def paste_to_qianniu_current_chat(text):
    """
    生成最终文案后：
    1. 复制到剪贴板
    2. 激活千牛窗口
    3. 直接发送 Ctrl+V 到当前聊天输入框

    不查找输入框控件，不用固定坐标，不移动鼠标。
    """
    try:
        pyperclip.copy(text)
        time.sleep(0.03)

        win = find_qianniu_window()
        if win:
            try:
                win.SetActive()
                time.sleep(0.03)
            except Exception:
                pass

        auto.SendKeys("{Ctrl}v")
        time.sleep(0.03)

        print("已复制最终文案，并向当前千牛窗口发送 Ctrl+V")
        return True

    except Exception as e:
        print("粘贴最终文案失败，内容已在剪贴板:", e)
        return False












    try:
        win.SetActive()
        time.sleep(0.15)
    except Exception:
        pass

    pyperclip.copy(text)
    time.sleep(0.08)

    chat_input = find_chat_input_control(win)
    if chat_input:
        try:
            chat_input.SetFocus()
            time.sleep(0.15)
        except Exception as e:
            print('聊天输入框 SetFocus 失败，继续尝试粘贴:', e)

        try:
            chat_input.GetLegacyIAccessiblePattern().Select(1)
            time.sleep(0.08)
        except Exception:
            pass

        try:
            auto.SendKeys('{Ctrl}a')
            time.sleep(0.04)
            auto.SendKeys('{Ctrl}v')
            time.sleep(0.12)
            print('已通过聊天输入框控件粘贴')
            return True
        except Exception as e:
            print('通过聊天输入框控件粘贴失败，进入发送按钮兜底:', e)

    # 兜底方案：很多千牛版本不暴露输入框，但暴露【发送】按钮。
    # 聚焦发送按钮后 Shift+Tab 通常会回到输入框。
    send_btn = find_chat_send_button(win)
    if send_btn:
        try:
            send_btn.SetFocus()
            time.sleep(0.12)
        except Exception as e:
            print('发送按钮 SetFocus 失败:', e)

        try:
            send_btn.GetLegacyIAccessiblePattern().Select(1)
            time.sleep(0.08)
        except Exception:
            pass

        # 从发送按钮回到输入框，不移动鼠标
        for keys in ['{Shift}{Tab}', '{Shift}{Tab}', '{Ctrl}v']:
            try:
                auto.SendKeys(keys)
                time.sleep(0.12)
                print(f'已发送按键: {keys}')
            except Exception as e:
                print(f'发送按键 {keys} 失败:', e)

        print('已尝试通过发送按钮兜底粘贴到聊天输入框')
        return True

    print('未找到聊天输入框/发送按钮，内容已复制到剪贴板，请手动 Ctrl+V')
    pyperclip.copy(text)
    return False


def copy_all_and_put_into_each_remark():
    """
    无备注版：
    1. 复制订单
    2. 5分钟规则过滤
    3. 生成最终文案
    4. 自动粘贴聊天输入框
    """
    mode = co_initialize()

    try:
        start_time = time.time()
        last_mark_time = start_time

        def mark_step(name):
            nonlocal last_mark_time
            now = time.time()
            print(f"[耗时] {name}: 本段 {now - last_mark_time:.2f}s，累计 {now - start_time:.2f}s")
            last_mark_time = now

        win = find_qianniu_window()

        if not win:
            print("未找到千牛窗口，请确认窗口标题包含：接待中心 / 千牛 / 接待 / 工作台")
            print_top_windows()
            return
        mark_step("查找千牛窗口")

        try:
            win.SetActive()
        except Exception:
            pass

        wangwang_name = ""

        # 读取当前选中的角色名和电话
        role_name, phone = read_selected_role_phone(win)
        mark_step("读取角色电话")

        copied_list = copy_all_visible_orders(win)
        mark_step("筛选并快捷复制订单")

        if not copied_list:
            print("没有复制到任何订单内容，停止。")
            return

        copied_list = attach_wangwang_to_orders(copied_list, wangwang_name)
        mark_step("补充旺旺信息")

        for item in copied_list:
            real_ww = extract_buyer_wangwang_from_order(item)
            if real_ww:
                wangwang_name = real_ww
                break

        copied_list = filter_orders_within_5_minutes(copied_list)
        mark_step("过滤5分钟订单")

        if not copied_list:
            print("没有符合 5 分钟规则的订单，停止。")
            return

        merged_text = format_final_order_remark(copied_list, wangwang_name, role_name, phone)

        pyperclip.copy(merged_text)

        with open("qianniu_merged_orders.txt", "w", encoding="utf-8") as f:
            f.write(merged_text)
        mark_step("生成模板")

        print("================ 最终文案 ================")
        print(merged_text)
        print("=========================================")
        print(f"最终处理 {len(copied_list)} 个订单")

        # 使用 Ctrl+I 聚焦聊天输入框
        try:
            win.SetActive()
            time.sleep(0.005)
        except Exception:
            pass

        send_ctrl_key("i")
        time.sleep(0.005)

        send_ctrl_key("a")
        time.sleep(0.005)

        send_ctrl_key("v")
        time.sleep(0.005)
        mark_step("粘贴聊天输入框")

        duration = round(time.time() - start_time, 2)

        print("已自动粘贴到聊天输入框")
        print(f"执行时长: {duration} 秒")
        print("当前版本已彻底删除添加备注功能。")

    except Exception as e:
        print("执行失败:", e)

    finally:
        co_uninitialize(mode)



def copy_all_only():
    mode = co_initialize()

    try:
        win = find_qianniu_window()

        if not win:
            print("未找到千牛窗口")
            print_top_windows()
            return

        # 旺旺名不再取右侧顶部昵称，只取快捷复制里的“买家旺旺”
        wangwang_name = ""

        copied_list = copy_all_visible_orders(win)

        if not copied_list:
            print("没有复制到订单内容")
            return

        copied_list = attach_wangwang_to_orders(copied_list, wangwang_name)

        # 从快捷复制内容中提取真实旺旺名
        for item in copied_list:
            real_ww = extract_buyer_wangwang_from_order(item)
            if real_ww:
                wangwang_name = real_ww
                break

        if wangwang_name:
            with open("qianniu_wangwang.txt", "w", encoding="utf-8") as f:
                f.write(wangwang_name)

            print(f"从复制订单中提取旺旺名: {wangwang_name}")

        copied_list = filter_orders_within_5_minutes(copied_list)

        merged_text = format_final_order_remark(copied_list, wangwang_name)
        pyperclip.copy(merged_text)

        with open("qianniu_merged_orders.txt", "w", encoding="utf-8") as f:
            f.write(merged_text)

        print("\n================ 最终备注内容 ================\n")
        print(merged_text)
        print("\n=============================================\n")
        print(f"已生成 {len(copied_list)} 个订单的最终备注，内容已放到剪切板。")

    except Exception as e:
        print("执行失败:", e)

    finally:
        co_uninitialize(mode)


def main():
    mode = co_initialize()

    keyboard.add_hotkey("ctrl+1", copy_all_and_put_into_each_remark)

    print("千牛订单备注助手已启动")
    print("Ctrl+1：只识别【待发货】订单，读取选中的角色名和电话，生成文案并自动粘贴聊天输入框")
    print("Ctrl+0：退出程序")
    print("")
    print("说明：")
    print("1. 旺旺名只取快捷复制内容里的【买家旺旺】")
    print("2. 只复制状态为【待发货】的订单")
    print("3. 第一单永远处理，后续订单付款时间间隔 <= 5 分钟才参与合并")
    print("4. 超过 5 分钟的订单跳过，不再执行任何备注操作")
    print("5. 最终文案会自动粘贴到底部聊天输入框")
    print("6. 最终文案会保存为 qianniu_merged_orders.txt")

    keyboard.wait("ctrl+0")

    co_uninitialize(mode)


if __name__ == "__main__":
    main()
