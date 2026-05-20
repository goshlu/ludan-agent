# Agents.md

## 项目目标

这个项目主要是给客服工作流做自动化辅助，当前重点是千牛桌面客户端：

- 从当前客户右侧订单数据获取订单编号和接单价格。
- 把多笔订单合并成一个客服录单模板。
- 从队友/聊天输入框文本中补充区服、角色、电话、账号、密码等字段。
- 自动把模板粘贴到千牛聊天框。
- 自动把聊天框里的模板写入订单备注，并避免重复写入。

## 当前主脚本

- `qianniu_client.py`：千牛桌面客户端主脚本。
- `qianniu_config.json`：固定坐标配置，优先级高于代码默认相对坐标。
- `qianniu_order_basket.json`：当前客户订单篮子。
- `qianniu_last_chat_input_text.txt`：最近一次从聊天输入框复制到的内容。
- `qianniu_last_teammate_text.txt`：最近一次从队友文本复制到的内容。
- `qianniu_last_quick_copy.txt`：最近一次手动/自动快捷复制订单后的内容。
- `qianniu_last_right_orders_text.txt`：最近一次右侧订单区域复制到的内容。

历史/辅助脚本：

- `script1.py`：旧飞鸽客服页面脚本。
- `ludan.py`：旧录单后台脚本。
- `qianniu_web_orders_capture.py`、`qianniu_orders_cache.py`：网页订单接口探索用，目前不是 `Ctrl+1` 的准源。
- `qianniu_mitm_orders.py`：mitmproxy 抓包探索用，目前不是主路线。

## 重要业务约定

订单编号和接单价格必须以**当前千牛桌面客户端右侧订单数据**为准。

不要默认使用网页订单缓存作为最终来源，因为它可能：

- 不是当前客户。
- 不是当天聊天对应客户。
- 数据不是最新。

当前可靠流程有两条路径：

**路径一：自动快捷复制（Ctrl+1 主路径）**

1. `Ctrl+1` 调用 `copy_visible_quick_copy_orders_info()`。
2. 先重置右侧面板到顶部（`reset_right_panel_to_top()`）。
3. 通过 pywinauto 自动发现当前可见区域所有"快捷复制"按钮。
4. 逐个点击按钮，读取剪贴板中的订单文本，解析订单号和价格。
5. 如果还有更多订单，滚动面板（`scroll_right_orders_panel_down()`）继续查找。
6. 多笔订单自动合并，生成录单模板并粘贴到聊天输入框。

**路径二：订单篮子手动流程**

1. 当前客户右侧订单区域中，对每笔要录入的待发货订单手动快捷复制。
2. 每复制一笔，按 `Ctrl+6` 加入订单篮子。
3. 多笔订单全部加入后，按 `Ctrl+1` 生成模板（如果自动路径失败会 fallback 到篮子）。

网页订单接口可以继续研究，但接入主流程前必须确保能准确定位"当前千牛聊天客户"的订单。

## 快捷键

- `Ctrl+1`：自动发现右侧快捷复制按钮并采集订单，合并订单号/价格，生成模板并粘贴到聊天输入框。
- `Ctrl+2`：读取聊天输入框里的模板，打开订单备注，若备注中没有相同订单号则写入并确认。
- `Ctrl+3`：转接客服。
- `Ctrl+4`：手动打开备注窗口后，继续执行 Ctrl+2 的写入逻辑。
- `Ctrl+5`：排查 UIAutomation / pywinauto 是否能找到"快捷复制"控件。
- `Ctrl+6`：把当前剪贴板里的单笔待发货订单加入订单篮子。
- `Ctrl+7`：清空订单篮子。
- `Ctrl+8`：保存当前千牛窗口可读文字，便于排查。
- `Ctrl+9`：校准坐标，写入 `qianniu_config.json`。
- `Ctrl+0`：退出脚本。

## pywinauto 自动快捷复制流程

`Ctrl+1` 的核心流程在 `copy_visible_quick_copy_orders_info()` 中：

1. `reset_right_panel_to_top()`：点击面板区域 + `Ctrl+Home` + `Home` + `scroll(30)` 回到顶部。
2. `get_expected_quick_copy_order_count()`：通过 pywinauto 读取千牛 UI 中的"待发货(N)"或"全部(N)"标签，获取预期订单数。
3. 循环最多 6 次扫描（首次可见 + 5 次下滑后）：
   - `find_quick_copy_button_candidates()`：调用 `find_pywinauto_controls_by_keyword("快捷复制")`，筛选精确文本、小尺寸按钮。
   - 用 `is_button_already_seen()` 做 20px 容差去重，避免滚动后重复点击。
   - 逐个按钮调用 `copy_order_text_from_quick_copy_button()` 点击并读取剪贴板。
   - 达到预期订单数时提前终止。
4. `scroll_right_orders_panel_down()`：把鼠标移到面板中心 (0.83, 0.50) + click + 5 次 `scroll(-60)` 大幅滚动。

### pywinauto 控件查找

`find_pywinauto_controls_by_keyword(keyword)` 使用 `pywinauto.Desktop(backend="uia")` 遍历千牛窗口的所有 descendant 控件，匹配 `window_text()` 中包含 keyword 的控件，排除窗口左侧 55% 区域。

### 按钮去重

`is_button_already_seen(button, seen_list, tolerance=20)` 使用 20px 容差匹配 `(center_x, center_y)`，避免滚动后坐标微小偏移导致同一个按钮被重复点击或遗漏。

## 坐标规则

`click_point()` 会优先读取 `qianniu_config.json` 中的绝对坐标。

如果配置为 `null`，才使用 `DEFAULT_RELATIVE_POINTS` 的窗口相对坐标。

因此，当用户明确说"这个坐标是对的"，应优先修改 `qianniu_config.json`，不要只改代码默认值。

当前备注相关流程依赖：

- `remark_button`
- `remark_textarea`
- `remark_save_button`

如果点错"详情/订单"导致弹出"阿里网站打开方式"，通常是 `remark_button` 或 `remark_textarea` 坐标错误，不要用按 `Esc` 清理弹窗来掩盖问题。

## 备注写入规则

`Ctrl+2` 的正确流程：

1. 从聊天输入框复制当前模板。
2. 通过 pywinauto 查找并点击"备注"按钮（`click_remark_button_by_pywinauto()`）。
3. 如果 pywinauto 找不到备注按钮，提示用户手动打开备注窗口后按 `Ctrl+4`。
4. 读取备注输入框里已有内容。
5. 如果已有相同订单号，则跳过。
6. 如果没有相同订单号，则写入聊天输入框复制到的模板。
7. 点击确定。

`Ctrl+4` 用于手动打开备注窗口后继续写入（复用 `PENDING_REMARK_TEXT` 中暂存的内容）。

注意：

- 不要直接拿系统剪贴板写备注，剪贴板可能是旧内容。
- 不要用整个千牛窗口可见文字判断备注是否重复，因为聊天输入框里也有模板，会误判。
- 重复判断应尽量基于备注输入框内容中的订单号。

## 订单篮子规则

`Ctrl+6` 从当前剪贴板读取单笔订单快捷复制文本。

加入篮子时：

- 必须识别到订单编号和价格。
- 单次复制内容应该是一笔订单。
- 同一订单号重复加入时覆盖，不重复计价。

`Ctrl+1` 使用时：

- 多个订单号用 `/` 合并。
- 多笔价格求和。
- 购买项目留空，人工填写。
- 旺旺号可以从坐标1322，303点击复制获取。
- 将录单模板粘贴到聊天框里。

## 价格解析规则

价格只应从明确价格字段读取，例如：

- `接单价格`
- `订单总付款`
- `订单总价`
- `实付金额`
- `实付`

同一订单块内如果同时出现 `订单总价` 和 `订单总付款`，只能取一个价格。当前优先级：

```text
接单价格 > 订单总付款 > 订单总价 > 实付金额 > 实付
```

不要使用"看到任意 ¥数字 就当价格"的兜底逻辑，容易把优惠、商品价、统计金额算进去。

## 千牛客户端限制

千牛桌面客户端的聊天气泡、右侧订单卡内部文字大多不能通过 UIAutomation 可靠读取。

已验证的问题：

- `qianniu_last_visible_text.txt` 往往只能读到窗口标题或有限控件。
- 不能依赖 UIAutomation 自动遍历聊天记录。
- OCR 不适合作为多订单算价主路径，可能漏单、错配订单号和金额。
- 客户端抓包不一定可行，可能不走系统代理或存在证书校验。

**pywinauto 相比 UIAutomation 的优势**：pywinauto 的 `Desktop(backend="uia")` 可以更好地发现千牛右侧订单区域的"快捷复制"、"备注"等按钮控件，是当前 Ctrl+1 和 Ctrl+2 的核心依赖。

## COM 初始化

`keyboard` 的热键回调在线程中执行。凡是会调用 UIAutomation / pywinauto 的热键，必须用：

```python
run_with_uia_initialized(...)
```

否则可能报：

```text
尚未调用 CoInitialize
Can not load UIAutomationCore.dll
```

目前 `Ctrl+1`、`Ctrl+2`、`Ctrl+3`、`Ctrl+4`、`Ctrl+5`、`Ctrl+8` 都应该包 UIAutomation 初始化。

## 开发注意事项

- 文件编码使用 UTF-8。
- 不要继续扩大对 `qianniu_last_visible_text.txt` 的依赖，它只能辅助排查。
- 修改坐标相关行为时，同时检查 `qianniu_config.json` 是否已有覆盖值。
- 修改下滑滚动相关代码时，注意 `scroll_right_orders_panel_down()` 的 `scroll(-60)` 乘以循环次数就是总滚动量，需要根据千牛实际面板高度调整。
- 按钮去重使用 `is_button_already_seen()` 的 20px 容差，不要改回精确像素匹配。
- 改完脚本后至少运行：

```powershell
.\.venv\Scripts\python.exe -m py_compile qianniu_client.py
```

涉及网页订单探索时，也检查：

```powershell
.\.venv\Scripts\python.exe -m py_compile qianniu_web_orders_capture.py qianniu_orders_cache.py