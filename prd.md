# ctrl + 1 详细步骤

## 1. 人工输入客户信息
在聊天输入框中输入固定格式文本：

```text
角色名 手机号
```

示例：

```text
黑白 15712347593
```

格式要求：角色名 + 至少一个空格 + 11 位手机号，手机号必须在文本末尾。

## 2. 触发脚本（Ctrl+1）

按下 `Ctrl+1`，调用主函数 `copy_visible_quick_copy_orders_info()`。

## 3. 读取输入框文本

脚本通过 pywinauto 读取聊天输入框当前文本内容。

```python
raw_input = get_chat_input_text()
```

## 4. 解析角色名与电话

使用正则表达式从文本末尾提取手机号，兼容角色名包含空格的情况。

解析规则：

- 从末尾匹配 11 位手机号：`1[3-9]\d{9}`
- 手机号前面的所有内容（去除首尾空格）作为角色名

```python
import re

def parse_customer_info(text: str):
    text = text.strip()
    if not text:
        return None, None
    # 角色名可含空格，手机号必须在最后
    match = re.search(r'^(.*)\s+(1[3-9]\d{9})\s*$', text)
    if not match:
        return None, None
    return match.group(1).strip(), match.group(2)
```

### 解析示例

| 输入文本 | 角色名 | 电话 |
| --- | --- | --- |
| 黑白 15712347593 | 黑白 | 15712347593 |
| 黑 白 15712347593 | 黑 白 | 15712347593 |
| 黑白15712347593 | ❌ 解析失败 | — |

## 5. 格式校验与阻断

- 若解析成功：继续执行后续步骤。
- 若解析失败（未识别到手机号）：终止流程，并在输入框提示错误。

```python
if not phone:
    set_chat_input_text("【系统提示】请输入格式：角色名 手机号，再按 Ctrl+1")
    return
```

## 6. 清空输入框

关键步骤：解析完成后立即清空输入框，防止原始客户信息随录单模板一起发送。

```python
set_chat_input_text("")
```

## 7. 重置右侧面板

将右侧面板滚动回顶部，确保从第一笔订单开始采集。

```python
reset_right_panel_to_top()
```

## 8. 采集可见区域订单

通过 pywinauto 扫描当前可见区域所有“快捷复制”按钮，逐个点击并读取剪贴板内容。

```python
orders = []

while True:
    buttons = find_quick_copy_buttons()
    if not buttons:
        break

    for btn in buttons:
        btn.click()
        time.sleep(0.3)  # 等待剪贴板刷新
        clipboard_text = clipboard.GetData()
        order_id, price = parse_order(clipboard_text)
        orders.append({"id": order_id, "price": price})

    if not scroll_right_orders_panel_down():
        break  # 已滚动到底部
```

## 9. 生成录单模板

将客户信息与订单信息合并，生成标准录单模板。

```python
template_lines = [
    f"角色：{role_name}",
    f"电话：{phone}",
    "-" * 20,
]

total = 0
for idx, order in enumerate(orders, 1):
    template_lines.append(f"订单{idx}：{order['id']}  ￥{order['price']}")
    total += order['price']

if len(orders) > 1:
    template_lines.append(f"合计：￥{total}")

template = "\n".join(template_lines)
```

### 输出示例（单笔）

```text
订单编号：6952944928341759083
系统区服：B服
抖音号：11
购买项目：等级白银二上到三
游戏大区 :QQ
角色名：明早八点睡#53757
当前等级：11
接单价格：22
联系电话：150****8275
游戏账号：扫码
游戏密码：扫码
订单来源：宝珠姐
```

### 输出示例（多笔）

```text
订单编号：6952944928341759083/3302367675575069299
系统区服：B服
抖音号：11
购买项目：等级白银二上到三
游戏大区 :QQ
角色名：明早八点睡#53757
当前等级：11
接单价格：22 ## 2笔订单合计
联系电话：150****8275
游戏账号：扫码
游戏密码：扫码
订单来源：宝珠姐
```

## 10. 粘贴到聊天框

将生成的录单模板写入聊天输入框，由人工确认后发送。

```python
set_chat_input_text(template)
```

# 三、边界情况处理

| 场景 | 处理策略 |
| --- | --- |
| 格式错误（无手机号 / 无空格） | 终止流程，输入框提示格式要求 |
| 角色名为空（如只输入手机号） | 角色名显示为【待补充】，继续执行 |
| 右侧面板无订单 | 模板中仅显示客户信息，并追加提示：`【未检测到可见订单，请确认右侧面板已展开】` |
| 订单采集为空 | 不报错，正常生成带客户信息的模板 |
| 角色名超长（>20字） | 直接截取前 20 字，防止破坏模板格式 |

# 四、关键注意事项

- 必须使用正则从末尾提取手机号，不能简单用 `split(" ")`，否则角色名含空格时会解析错误。
- 读取输入框后必须清空，否则原始文本会与录单模板一起发送给客户。
- 格式校验失败时必须阻断，避免在无客户信息的情况下执行订单采集。
- 每次 `Ctrl+1` 都是独立流程，客户信息不跨会话保留，单次触发单次使用。
