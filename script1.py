import json
import re
import pyperclip
import keyboard
from DrissionPage import ChromiumPage,ChromiumOptions
import time
import datetime
import requests



from openpyxl.worksheet import page
from plyer import notification


def show_toast(page_obj, message, level='info', duration=4500):
    try:
        if level == 'error':
            color_theme = {
                'text': '#d93025',
                'bg': '#fce8e6',
                'border': '#f5c2c7',
                'icon': '<path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0zM5.354 4.646a.5.5 0 1 0-.708.708L7.293 8l-2.647 2.646a.5.5 0 0 0 .708.708L8 8.707l2.646 2.647a.5.5 0 0 0 .708-.708L8.707 8l2.647-2.646a.5.5 0 0 0-.708-.708L8 7.293 5.354 4.646z"/>'
            }
        else:
            color_theme = {
                'text': '#137333',
                'bg': '#e6f4ea',
                'border': '#b7eb8f',
                'icon': '<path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0zm-3.97-3.03a.75.75 0 0 0-1.08.022L7.477 9.417 5.384 7.323a.75.75 0 0 0-1.06 1.06L6.97 11.03a.75.75 0 0 0 1.079-.02l3.992-4.99a.75.75 0 0 0-.01-1.05z"/>'
            }

        safe_message = json.dumps(message)

        fancy_js = f"""
        (function() {{
            const existing = document.getElementById('dp-custom-toast');
            if (existing) existing.remove();

            const toast = document.createElement('div');
            toast.id = 'dp-custom-toast';

            toast.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 16 16" style="margin-right: 15px; color: {color_theme['text']}; flex-shrink: 0;">
                    {color_theme['icon']}
                </svg>
                <span style="font-weight: 500; letter-spacing: 0.5px; line-height: 1.5;"></span>
            `;

            toast.querySelector('span').innerText = {safe_message};

            Object.assign(toast.style, {{
                position: 'fixed',
                top: '20px',
                left: '50%',
                transform: 'translateX(-50%)',
                zIndex: '2147483647',
                minWidth: '400px',
                maxWidth: '800px',
                padding: '20px 30px',
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'flex-start',
                backgroundColor: '{color_theme['bg']}', 
                border: '1px solid {color_theme['border']}', 
                color: '{color_theme['text']}',           
                borderRadius: '8px',
                boxShadow: '0 8px 24px rgba(0,0,0,0.15)',
                fontFamily: '"Microsoft YaHei", "Segoe UI", sans-serif',
                fontSize: '16px',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                height: 'auto',
                maxHeight: '80vh',
                overflowY: 'auto',
                opacity: '0',
                transition: 'all 0.4s cubic-bezier(0.215, 0.610, 0.355, 1.000)'
            }});

            document.body.appendChild(toast);

            setTimeout(() => {{
                toast.style.opacity = '1';
                toast.style.top = '50px'; 
            }}, 50);

            setTimeout(() => {{
                toast.style.opacity = '0';
                toast.style.transform = 'translateX(-50%) scale(0.9)';
                setTimeout(() => {{ if(toast) toast.remove(); }}, 400);
            }}, {duration}); 
        }})();
        """
        page_obj.run_js(fancy_js)
    except Exception as e:
        print(f"弹窗注入失败: {e}")


def show_order_notification(text_notification, result):
    try:
        notification.notify(
            title=f'{result}',
            message=f'{text_notification}',
            app_name="佳佳拍懒狗系统",
            timeout=10,
        )
        print("通知已成功发送")
    except Exception as e:
        print(f"发送通知失败：{str(e)}")



def run_extraction_task(page):
        try:
            if not page.url:
                print("浏览器已关闭或断开连接")
                return

            price_map = {}
            try:
                # 获取所有备注图标元素
                page.set.timeouts(0.1)
                remarks = page.eles('@class:i-icon i-icon-look-note')

                for remark in remarks:
                    try:
                        order_node = remark.parent(4).child(2).child(1).child(1)
                        order_id = order_node.text.strip()

                        # 定位价格节点的公共父级
                        price_base_node = order_node.parent(5).child(2).child(1).child(1).child(1).child(2).child(
                            1).child(1).child(2).child(1).child(1)

                        # 获取整数部分(含小数点) 和 小数部分
                        # child(2) 是 zs, child(3) 是 xs
                        price_str_zs = price_base_node.child(2).text
                        price_str_xs = price_base_node.child(3).text
                        # 拼接并转换为浮点数
                        full_price = float(price_str_zs + price_str_xs)

                        # 存入字典
                        price_map[order_id] = full_price

                    except Exception as inner_e:
                        continue
            except Exception as e:
                print(f"获取页面订单价格失败: {e}")
            # --- 步骤2: 处理聊天记录 ---
            elements = page.eles('@class:leaveMessage messageIsMe')

            # 修改后的正则：不再匹配末尾的价格数字，只匹配 ID组合 和 剩余文本(项目名)
            # 注意：结尾可能有多余空格，使用 \s* 处理
            pattern = re.compile(r'((?:69\d{17})(?:\/69\d{17})*)\s+(.+?)\s*$')

            elements.reverse()  # 从最新的消息开始找

            for ele in elements:
                text = ele.text
                match = pattern.search(text)

                if match:
                    raw_ids = match.group(1)  # 原始ID字符串，可能是 "ID1/ID2"
                    product_name = match.group(2).strip()  # 项目名称

                    # --- 步骤3: 计算总价 ---
                    id_list = raw_ids.split('/')  # 分割ID
                    total_price = 0.0
                    not_found_ids = []
                    stop_input = 0

                    for single_id in id_list:
                        if single_id in price_map:
                            total_price += price_map[single_id]
                        else:
                            not_found_ids.append(single_id)
                            print(f"警告: 订单号 {single_id} 未在当前页面列表中找到对应的价格信息。")
                            show_toast(page,
                                       f'警告: 订单号 {single_id} 未在当前页面列表中找到对应的价格信息。\n警告: 订单号 {single_id} 未在当前页面列表中找到对应的价格信息。\n警告: 订单号 {single_id} 未在当前页面列表中找到对应的价格信息。',
                                       level='error',
                                       duration=5000)
                            stop_input = 1

                    # 如果有没找到价格的订单，可能需要人工干预，这里默认计算能找到的
                    final_price_str = f"{total_price:.2f}"  # 保留两位小数，例如 20.00

                    item_info = {
                        "id": raw_ids,
                        "name": product_name,
                        "price": final_price_str
                    }

                    # 构建回复消息
                    record_message = f'''订单编号:{item_info["id"]}
旺旺/YY:抖音
接单价格:{item_info["price"]}
购买项目:{item_info["name"]}
系统:
角色名:
联系电话:
游戏账号:扫码
游戏密码:扫码
注：未成年禁止下单，点击查看更多阅读注意事项。\r\n注：切勿私下添加代练，所有资金均在抖音本店产生交易，如私下交易造成资金损失，小店一律不予补偿交易损失，谨防上当受骗。\r\n注：如代练期间产生封号十年情况，小店会第一时间进行核实，如情况属实会对您的账号进行评估并赔偿。\r\n注：车快慢与技术无关 正常都会在规定时间完成，具体效率和账号是否被官方黑屋有关（黑屋解释：可抖音搜索相关视频了解）如出现黑屋可直接进行进度结算，或转化为代肝订单不会产生此类问题。'''

                    try:
                        if stop_input == 1:
                            print('已阻止输入')
                        else:
                            # 填入输入框
                            page.ele('xpath://*[@id="im-input-box"]/div[3]/textarea').input(record_message)
                            print(f'已对订单编号:{item_info["id"]}应用模板到客服对话框。计算价格为: {item_info["price"]}')

                        if not_found_ids:
                            show_toast(page, f'部分订单({",".join(not_found_ids)})未找到价格。可能的原因:\n1.有部分订单号不是该用户的订单。\n2.尝试下滑订单页面，使需录制的订单全部加载到页面。', level='error',
                                       duration=5000)
                        else:
                            show_toast(page, f'已对订单编号:{item_info["id"]}应用模板到客服对话框。计算价格为: {item_info["price"]}', level='info', duration=2000)

                    except Exception as e:
                        print(f"输入框操作错误: {e}")

                    # 找到并处理完最新的匹配消息后退出循环
                    break

        except Exception as e:
            print(f"提取任务执行失败：{str(e)}")
            # 假设 show_toast 是外部定义的函数
            try:
                show_toast(page, "提取失败，查看控制台日志", level='error', duration=3000)
            except:
                pass
def old_run_extraction_task(page):
    try:
        if not page.url:
            print("浏览器已关闭或断开连接")
            return

        elements = page.eles('@class:leaveMessage messageIsMe')
        pattern = re.compile(r'((?:69\d{17})(?:\/69\d{17})*)\s+(.+?)\s*(\d+\.?\d*)$')

        elements.reverse()
        for ele in elements:
            text = ele.text
            match = pattern.search(text)

            if match:
                product_id = match.group(1)
                product_name = match.group(2)
                product_price = match.group(3)

                item_info = {
                    "id": product_id,
                    "name": product_name,
                    "price": product_price
                }
                record_message = f'''订单编号:{item_info["id"]}
旺旺/YY:抖音
接单价格:{item_info["price"]}
购买项目:{item_info["name"]}
系统:
角色名:
联系电话:
游戏账号:扫码
游戏密码:扫码
注：切勿私下添加代练，所有资金均在抖音本店产生交易，如私下交易造成资金损失，小店一律不予补偿交易损失，谨防上当受骗。\r\n注：如代练期间产生封号十年情况，小店会第一时间进行核实，如情况属实会对您的账号进行评估并赔偿。\r\n注：车快慢与技术无关 正常都会在规定时间完成，具体效率和账号是否被官方黑屋有关（黑屋解释：可抖音搜索相关视频了解）如出现黑屋可直接进行进度结算，或转化为代肝订单不会产生此类问题。'''
                try:
                    page.ele('xpath://*[@id="im-input-box"]/textarea').input(record_message)
                    print(f'已对订单编号:{item_info["id"]}应用模板到客服对话框。')
                except Exception as e:
                    print(f"错误: {e}")
                show_toast(page, f'已对订单编号:{item_info["id"]}应用模板到客服对话框。',
                           level='info', duration=2000)
                break

    except Exception as e:
        print(f"提取任务执行失败：{str(e)}")
        show_toast(page, "提取失败，查看控制台日志", level='error', duration=3000)
def check_order_id(order_id,file_path='order_ids.txt'):
    # 读取文件中的所有订单编号（文件不存在则创建空列表）
    existing_ids = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            # 读取每行并去除换行符和空格，过滤空行
            existing_ids = [line.strip() for line in f.readlines() if line.strip()]
    except FileNotFoundError:
        # 文件不存在，说明是首次运行，直接创建空文件
        with open(file_path, 'w', encoding='utf-8') as f:
            pass
    # 检查编号是否已存在
    if order_id in existing_ids:
        return True
    else:
        return False
def is_order_missing(order_phone_seat, cookies):
    url = "http://ldl.jjpdoudian.cqwangyou.com/orderManage/getResponse"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    params = {
        "page": "1",
        "limit": "15",
        "gameId": "47",
        "userType": "1",
        "isAdvanceOrder": "0",
        "isTeamOrder": "0",
        "orderPhoneSeat": order_phone_seat,
        "creationTimeStart": "2025-10-26 00:00:00",
        "creationTimeEnd": "2036-02-26 23:59:59"
    }

    try:
        response = requests.get(url, params=params, headers=headers, cookies=cookies, timeout=10)


        # 检查状态码
        if response.status_code != 200:
            print(f"服务器响应错误，状态码: {response.status_code}")
            return False

        res_data = response.json()

        # 逻辑判断
        if "data" in res_data and len(res_data["data"]) == 0:
            return True
        else:
            return False

    except requests.exceptions.JSONDecodeError:
        print("解析 JSON 失败！服务器可能返回了登录页面或错误 HTML，请检查 Cookie 是否过期。")
        return False
    except Exception as e:
        print(f"请求发生异常: {e}")
        return False


def login_task(page):
    target_url = 'https://fxg.jinritemai.com/login/common?channel=zhaoshang'
    try:
        page.get(target_url)
        page.run_cdp('Network.clearBrowserCookies')
        page.run_js('localStorage.clear(); sessionStorage.clear();')
        page.get(target_url)
        show_toast(page, "已清除历史登录状态，请扫码/登录后重启main_chat_v2.py", level='info', duration=3000)

    except Exception as e:
        print(f"清除登录状态失败: {e}")



def run_remark_task(page):
    try:
        remarks = page.eles('@class:i-icon i-icon-look-note')
        original_str = pyperclip.paste()
        order_id_pattern = r'订单编号:\s*([\d/]+)\s*[\r\n]'
        order_id_match = re.search(order_id_pattern, original_str, re.IGNORECASE)
        order_id = order_id_match.group(1) if order_id_match else '未找到'
        if check_order_id(order_id, file_path='order_ids.txt'):
            for remark in remarks:
                if remark.parent(4).child(2).child(1).child(1).text in original_str:
                    remark.click(by_js=True)
                    page.ele('xpath://*[@id="textareaID"]').input(original_str, clear=True)
                    page.ele('xpath://*[@id="workStation"]/div[3]/div/div/div/div/div[3]/div/div/button[1]').click(by_js=True)
                    page.ele('xpath://*[@id="workspace-chat"]/div[2]/div[1]/div/div[1]/div[1]/div[3]').click()
                    time.sleep(0.5)
                    transfer_one = page.eles('@data-qa-id:qa-transfer-customer')
                    for ele in transfer_one:
                        if '双子星' in pyperclip.paste():
                            if ele.child(2).child(1).text == '吕郑豪':
                                ele.click(by_js=True)
                            elif ele.child(2).child(1).text == '吕郑豪':
                                ele.click(by_js=True)
                        elif '未满足一直打' in pyperclip.paste():
                            if ele.child(2).child(1).text == '吕郑豪':
                                ele.click(by_js=True)
                            elif ele.child(2).child(1).text == '吕郑豪':
                                ele.click(by_js=True)
                        else:
                            if ele.child(2).child(1).text == ('板蓝根'):
                                ele.click(by_js=True)
                    break
        else:
            print (f'order_ids.txt没有{order_id},阻止运行ctrl+3')
            show_toast(page, "必须要先进行写入订单才能执行备注转接\n请按下ctrl+2执行备注转接", level='error', duration=3000)

    except Exception as e:
        print(f"错误: {e}")


def init_clipboard_window(page):
    """初始化并注入剪切板监控窗体"""
    js_logic = """
    (function() {
        if (document.getElementById('dp-clipboard-box')) return;

        const box = document.createElement('div');
        box.id = 'dp-clipboard-box';
        const baseBgColor = 'rgba(255, 255, 255, 0.9)';

        Object.assign(box.style, {
            position: 'fixed',
            top: '20px',
            right: '20px',
            width: '220px',
            height: '150px',
            minWidth: '150px',
            minHeight: '80px',
            backgroundColor: baseBgColor,
            backdropFilter: 'blur(8px)',
            webkitBackdropFilter: 'blur(8px)',
            borderRadius: '8px',
            boxShadow: '0 4px 16px rgba(0, 0, 0, 0.15)',
            border: '1px solid rgba(200, 200, 200, 0.5)',
            zIndex: '999999',
            fontFamily: 'sans-serif',
            overflow: 'hidden',
            display: 'none',
            flexDirection: 'column',
            transition: 'opacity 0.2s, transform 0.2s'
        });

        const header = document.createElement('div');
        header.id = 'dp-clipboard-header';
        header.innerText = '监控就绪...';
        Object.assign(header.style, {
            padding: '4px 8px',
            fontSize: '11px',
            fontWeight: '800',
            color: '#555',
            backgroundColor: 'rgba(0,0,0,0.03)',
            borderBottom: '1px solid rgba(0,0,0,0.05)',
            cursor: 'move',
            userSelect: 'none',
            textAlign: 'center',
            flexShrink: '0',
            transition: 'color 0.4s ease' // 仅对文字颜色设置过渡
        });
        box.appendChild(header);

        const content = document.createElement('div');
        content.id = 'dp-clipboard-content';
        Object.assign(content.style, {
            padding: '8px 10px',
            fontSize: '12px',
            color: '#333',
            lineHeight: '1.4',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-all',
            overflowY: 'auto',
            flex: '1',
            transition: 'background-color 0.4s ease' // 仅对背景颜色设置过渡
        });
        box.appendChild(content);

        const resizer = document.createElement('div');
        resizer.innerHTML = '◢'; 
        Object.assign(resizer.style, {
            position: 'absolute', bottom: '2px', right: '2px', width: '15px', height: '15px',
            cursor: 'nwse-resize', fontSize: '10px', color: '#aaa', userSelect: 'none'
        });
        box.appendChild(resizer);
        document.body.appendChild(box);

        let isMoving = false, isResizing = false;
        let startX, startY, initL, initT, initW, initH;

        header.addEventListener('mousedown', (e) => {
            isMoving = true; startX = e.clientX; startY = e.clientY;
            const rect = box.getBoundingClientRect(); initL = rect.left; initT = rect.top;
            e.preventDefault();
        });

        resizer.addEventListener('mousedown', (e) => {
            isResizing = true; startX = e.clientX; startY = e.clientY;
            const rect = box.getBoundingClientRect(); initW = rect.width; initH = rect.height;
            e.stopPropagation(); e.preventDefault();
        });

        window.addEventListener('mousemove', (e) => {
            if (isMoving) {
                box.style.right = 'auto';
                box.style.left = (initL + e.clientX - startX) + 'px';
                box.style.top = (initT + e.clientY - startY) + 'px';
            }
            if (isResizing) {
                box.style.width = (initW + e.clientX - startX) + 'px';
                box.style.height = (initH + e.clientY - startY) + 'px';
            }
        });

        window.addEventListener('mouseup', () => { isMoving = false; isResizing = false; });

        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === '8') {
                e.preventDefault();
                box.style.display = (box.style.display === 'none') ? 'flex' : 'none';
            }
        });

        window.updateDpClipboard = function(text, timeStr) {
            const cEl = document.getElementById('dp-clipboard-content');
            const hEl = document.getElementById('dp-clipboard-header');

            if(cEl && cEl.innerText !== text) {
                cEl.innerText = text;
                hEl.innerText = 'UPDATE: ' + timeStr;

                hEl.style.color = '#10b981'; 
                // 确保背景保持原来的淡灰色
                hEl.style.backgroundColor = 'rgba(0,0,0,0.03)'; 

                // 2. 内容区：仅背景变绿
                cEl.style.backgroundColor = 'rgba(52, 211, 153, 0.25)'; 
                cEl.style.color = '#333'; // 确保文字颜色不变

                // 3. 延时 600ms 后恢复原状
                setTimeout(() => { 
                    hEl.style.color = '#555'; 
                    cEl.style.backgroundColor = 'transparent'; 
                }, 600);
            }
        };
    })();
    """
    page.run_js(js_logic)


def update_clipboard_logic(page, last_text):
    """检测剪切板并更新UI"""
    try:
        current_text = pyperclip.paste()
        if current_text != last_text:
            now_time = datetime.datetime.now().strftime("%H:%M:%S")
            safe_text = json.dumps(current_text)
            page.run_js(f"window.updateDpClipboard({safe_text}, '{now_time}')")
            return current_text
    except Exception:
        pass
    return last_text

def init_key_guide_window(page):
    js_logic = """
    (function() {
        if (document.getElementById('dp-key-guide')) return;

        const guide = document.createElement('div');
        guide.id = 'dp-key-guide';

        // CSS 样式
        const style = document.createElement('style');
        style.textContent = `
            #dp-key-guide {
                position: fixed; bottom: 20px; left: 20px; width: 180px;
                background: rgba(30, 30, 30, 0.85); backdrop-filter: blur(2px);
                border-radius: 8px; padding: 10px; color: #eee;
                font-family: 'Segoe UI', sans-serif; font-size: 13px;
                z-index: 999998; border: 1px solid rgba(255,255,255,0.1);
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                user-select: none; 
                /* 1. 移除原有pointer-events: none，否则无法触发鼠标拖拽事件 */
                cursor: move; /* 鼠标悬浮显示拖拽光标，提升体验 */
            }
            .key-item {
                display: flex; justify-content: space-between;
                padding: 4px 8px; margin-bottom: 2px;
                border-radius: 4px; transition: all 0.1s ease;
                pointer-events: none; /* 2. 给功能项恢复鼠标穿透，不影响底层页面操作 */
            }
            .key-item span:first-child { font-weight: bold; color: #aaa; }
            .key-item.active {
                background: #10b981; color: white; transform: scale(1.02);
                box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            }
            .key-item.active span:first-child { color: white; }
        `;
        document.head.appendChild(style);

        guide.innerHTML = `
            <div class="key-item" id="guide-ctrl-1"><span>Ctrl+1</span> <span>提取订单</span></div>
            <div class="key-item" id="guide-ctrl-2"><span>Ctrl+2</span> <span>写入订单</span></div>
            <div class="key-item" id="guide-ctrl-3"><span>Ctrl+3</span> <span>备注转接</span></div>
            <div class="key-item" id="guide-ctrl-4"><span>Ctrl+4</span> <span>提取订单(旧)</span></div>
            <div class="key-item" id="guide-ctrl-5"><span>Ctrl+5</span> <span>跳转登录</span></div>
            <div class="key-item" id="guide-ctrl-8"><span>Ctrl+8</span> <span>剪切板窗</span></div>
            <div class="key-item" id="guide-ctrl-0" style="margin-top:5px;border-top:1px solid #444;padding-top:5px"><span>Ctrl+0</span> <span>退出程序</span></div>
        `;
        document.body.appendChild(guide);

        // ========== 新增：拖拽功能核心逻辑 ==========
        let isDragging = false;
        let startX, startY, offsetX, offsetY;
        // 鼠标按下时开始拖拽
        guide.addEventListener('mousedown', (e) => {
            isDragging = true;
            // 获取鼠标初始位置（相对于浏览器视口）
            startX = e.clientX;
            startY = e.clientY;
            // 获取提示窗当前的偏移量（排除margin/padding，用getBoundingClientRect更准确）
            const rect = guide.getBoundingClientRect();
            offsetX = startX - rect.left;
            offsetY = startY - rect.top;
            // 拖拽时提升层级，避免被遮挡
            guide.style.zIndex = 999999;
            // 拖拽时改变光标，提升体验
            guide.style.cursor = 'grabbing';
            // 阻止事件冒泡，避免触发底层页面的鼠标事件
            e.preventDefault();
        });
        // 鼠标移动时更新位置
        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            // 计算新的位置（减去偏移量，让鼠标始终在点击的位置拖拽）
            const newLeft = e.clientX - offsetX;
            const newTop = e.clientY - offsetY;
            // 赋值给提示窗（用left/top，保持fixed定位）
            guide.style.left = `${newLeft}px`;
            guide.style.top = `${newTop}px`;
            // 清除原有bottom，避免定位冲突
            guide.style.bottom = 'auto';
            e.preventDefault();
        });
        // 鼠标松开/离开浏览器时结束拖拽
        document.addEventListener('mouseup', () => {
            if (isDragging) {
                isDragging = false;
                guide.style.zIndex = 999998; // 恢复原有层级
                guide.style.cursor = 'move'; // 恢复原有光标
            }
        });
        document.addEventListener('mouseleave', () => {
            if (isDragging) {
                isDragging = false;
                guide.style.zIndex = 999998;
                guide.style.cursor = 'move';
            }
        });
        // ========== 拖拽功能结束 ==========

        // 高亮接口
        window.highlightKey = function(keyId) {
            const el = document.getElementById(keyId);
            if(el) {
                el.classList.add('active');
                setTimeout(() => el.classList.remove('active'), 300);
            }
        }
    })();
    """
    page.run_js(js_logic)

def execute_action(page, key_id, func=None):
    """执行动作并高亮对应的UI按键"""
    try:
        # 1. 触发 UI 高亮 (guide-ctrl-1 等)
        page.run_js(f"window.highlightKey('{key_id}')")

        # 2. 执行实际功能 (如果有)
        if func:
            func()

    except Exception as e:
        print(f"Action Error: {e}")


def main():
    print("连接聊天界面中..")
    co = ChromiumOptions().set_browser_path(r'C:\Program Files\Google\Chrome\Application\chrome.exe')
    page = ChromiumPage(addr_or_opts=co)
    page.get('https://im.jinritemai.com/pc_seller_v2/main/workspace?selfId=7593637832046452267')
    while page.title != '飞鸽客服系统':
        pass

    # 注册热键
    keyboard.add_hotkey('ctrl+1', lambda: execute_action(page, 'guide-ctrl-1', lambda: run_extraction_task(page)))
    keyboard.add_hotkey('ctrl+2', lambda: execute_action(page, 'guide-ctrl-2'))
    keyboard.add_hotkey('ctrl+4', lambda: execute_action(page, 'guide-ctrl-4', lambda: old_run_extraction_task(page)))
    keyboard.add_hotkey('ctrl+3', lambda: execute_action(page, 'guide-ctrl-3', lambda: run_remark_task(page)))
    keyboard.add_hotkey('ctrl+5', lambda: execute_action(page, 'guide-ctrl-5', lambda: login_task(page)))
    keyboard.add_hotkey('ctrl+8', lambda: execute_action(page, 'guide-ctrl-8'))

    init_clipboard_window(page)
    init_key_guide_window(page)

    print("程序已就绪。按 Ctrl+0 退出。")

    last_clipboard_text = ""

    while True:
        if keyboard.is_pressed('ctrl+0'):
            print("程序已退出。")
            break

        last_clipboard_text = update_clipboard_logic(page, last_clipboard_text)
        time.sleep(0.5)


if __name__ == "__main__":
    main()