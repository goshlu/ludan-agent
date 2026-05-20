import json
import re
import pyperclip
import keyboard
from DrissionPage import ChromiumPage,ChromiumOptions
import time
from plyer import notification
import requests




def show_toast(page_obj, message, level='info', duration=4500):

    try:
        # 1. Prepare styles based on level
        if level == 'error':
            color_theme = {
                'text': '#d93025',  # Red text
                'bg': '#fce8e6',  # Light red bg
                'border': '#f5c2c7',  # Red border
                'icon': '<path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0zM5.354 4.646a.5.5 0 1 0-.708.708L7.293 8l-2.647 2.646a.5.5 0 0 0 .708.708L8 8.707l2.646 2.647a.5.5 0 0 0 .708-.708L8.707 8l2.647-2.646a.5.5 0 0 0-.708-.708L8 7.293 5.354 4.646z"/>'
            }
        else:
            color_theme = {
                'text': '#137333',  # Green text
                'bg': '#e6f4ea',  # Light green bg
                'border': '#b7eb8f',  # Green border
                'icon': '<path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0zm-3.97-3.03a.75.75 0 0 0-1.08.022L7.477 9.417 5.384 7.323a.75.75 0 0 0-1.06 1.06L6.97 11.03a.75.75 0 0 0 1.079-.02l3.992-4.99a.75.75 0 0 0-.01-1.05z"/>'
            }

        # 2. Safe serialization of message
        safe_message = json.dumps(message)

        # 3. JS Injection
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


def extract_order_price(order_str):
    """
    提取订单字符串中的接单价格（数字）和购买项目（字符串）
    以回车换行(\r\n/\n)作为字段结束标识，不依赖后续固定文本
    :param order_str: 原始订单字符串
    :return: 包含接单价格、购买项目的字典，未匹配到返回'未找到'
    """
    # 提取接单价格：匹配"接单价格:"后到换行前的所有数字，\s*匹配可能的空格
    price_pattern = r'接单价格:\s*(\d+\.?\d*)\s*[\r\n]'
    price_match = re.search(price_pattern, order_str, re.IGNORECASE)
    price = price_match.group(1) if price_match else '未找到'

    # 提取购买项目：匹配"购买项目:"后到换行前的所有内容，.*?非贪婪匹配，strip去首尾空格/制表符
    item_pattern = r'购买项目:\s*(.*?)\s*[\r\n]'
    item_match = re.search(item_pattern, order_str, re.DOTALL | re.IGNORECASE)
    item = item_match.group(1).strip() if item_match else '未找到'

    # 提取订单编号：匹配"订单编号:"后固定19位数字，\s*匹配可能的空格，\d{19}匹配19位数字
    order_id_pattern = r'订单编号:\s*([\d/]+)\s*[\r\n]'
    order_id_match = re.search(order_id_pattern, order_str, re.IGNORECASE)
    order_id = order_id_match.group(1) if order_id_match else '未找到'

    return {'接单价格': price, '购买项目': item, '订单编号': order_id}
def show_order_notification(text_notification,result):
    """显示订单提交完成的Windows通知"""
    try:
        # 配置通知参数
        notification.notify(
            title=f'{result}',          # 通知标题
            message=f'{text_notification}',  # 通知内容
            app_name="佳佳拍懒狗系统",        # 应用名称（显示在通知设置中）
            timeout=10,                    # 通知显示时长（秒）
        )
    except Exception as e:
        print(f"发送通知失败：{str(e)}")


# 检测订单是否存在
def is_order_missing(order_phone_seat, cookies):
    url = "http://ldl.jjpdoudian.cqwangyou.com/orderManage/getResponse"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        # 这里删掉硬编码的 Cookie，交由 requests 的 cookies 参数处理
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
            show_order_notification(f"服务器响应错误，状态码: {response.status_code}", '订单处理失败')
            return None

        res_data = response.json()

        # 逻辑判断
        if "data" in res_data and len(res_data["data"]) == 0:
            return True
        else:
            print ('该订单已存在!')
            show_order_notification('订单已存在!', '订单处理失败')
            return False

    except requests.exceptions.JSONDecodeError:
        print("解析 JSON 失败！服务器可能返回了登录页面或错误 HTML，请检查 Cookie 是否过期。")
        show_order_notification("解析 JSON 失败！服务器可能返回了登录页面或错误 HTML，请检查 Cookie 是否过期。", '订单处理失败')
        return None
    except Exception as e:
        print(f"请求发生异常: {e}")
        show_order_notification(f"请求发生异常: {e}",
                                '订单处理失败')
        return None
def check_and_save_order_id(order_id, file_path='order_ids.txt'):
    # 处理未找到订单编号的情况
    if order_id == '未找到':
        print("未提取到有效的订单编号")
        return None

    # 读取文件中的所有订单编号（文件不存在则创建空列表）
    existing_ids = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            # 读取每行并去除换行符和空格，过滤空行
            existing_ids = [line.strip() for line in f.readlines() if line.strip()]
    except FileNotFoundError:
        # 文件不存在，说明是首次   运行，直接创建空文件
        with open(file_path, 'w', encoding='utf-8') as f:
            pass

    # 检查编号是否已存在
    if order_id in existing_ids:
        print(f"订单编号 {order_id} 已存在，跳过执行")
        show_order_notification('本地内有该订单的录入记录，可能的原因:\n1.尝试录单但因为信息不对应导致录单失败\n2.未复制下一单单号导致错误录入了上一单的单号', '订单处理失败')
        return False
    else:
        return True



def run_extraction_task(page):
    try:
        # 检查页面是否还活着
        if not page.url:
            print("浏览器已关闭或断开连接")
            return
        try:
            current_cookies = page.cookies().as_dict()
        except TypeError:
            current_cookies = page.cookies.as_dict()
        with open('cookies.txt', 'w', encoding='utf-8') as f:
            json.dump(current_cookies, f, ensure_ascii=False, indent=4)
        original_str = pyperclip.paste()
        order_id = extract_order_price(original_str)['订单编号']
        result = is_order_missing(order_id, current_cookies)
        if check_and_save_order_id(order_id, file_path='order_ids.txt'):
            if result:
                del_text = '注：切勿私下添加代练，所有资金均在抖音本店产生交易，如私下交易造成资金损失，小店一律不予补偿交易损失，谨防上当受骗。\r\n注：如代练期间产生封号十年情况，小店会第一时间进行核实，如情况属实会对您的账号进行评估并赔偿。\r\n注：车快慢与技术无关 正常都会在规定时间完成，具体效率和账号是否被官方黑屋有关（黑屋解释：可抖音搜索相关视频了解）如出现黑屋可直接进行进度结算，或转化为代肝订单不会产生此类问题。'''
                original_str = original_str.replace(del_text, "")
                page.ele('xpath://*[@id="originOrderData"]').input(original_str,clear=True)
                page.ele('xpath://*[@id="originOrderData"]').click(timeout=2)
                page.ele('xpath://*[@id="clickId"]/div[3]/div[1]/div[1]/div/div/div/input').click(timeout=2)
                time.sleep(0.3)
                page.ele('xpath://*[@id="clickId"]/div[3]/div[1]/div[1]/div/div/div/input').click(timeout=2)
                page.ele('xpath://*[@id="clickId"]/div[3]/div[1]/div[1]/div/div/dl').child(2).click(timeout=2)
                if '代肝' in extract_order_price(original_str)['购买项目']:
                   page.ele('xpath://*[@id="gameProject"]/div[2]').click(timeout=2)
                elif '撞车' in extract_order_price(original_str)['购买项目']:
                   page.ele('xpath://*[@id="gameProject"]/div[1]').click(timeout=2)
                elif '双子星' in extract_order_price(original_str)['购买项目']:
                   page.ele('xpath://*[@id="gameProject"]/div[3]').click(timeout=2)
                elif '包损耗' in extract_order_price(original_str)['购买项目']:
                   page.ele('xpath://*[@id="gameProject"]/div[4]').click(timeout=2)
                elif '3x3' in extract_order_price(original_str)['购买项目']:
                   page.ele('xpath://*[@id="gameProject"]/div[5]').click(timeout=2)
                else:
                   page.ele('xpath://*[@id="gameProject"]/div[2]').click(timeout=2)
                page.ele('xpath://*[@id="clickId"]/div[3]/div[8]/div/div[2]/div/label[2]/input').input(extract_order_price(original_str)['接单价格'],clear=True)
                page.ele('xpath://*[@id="clickId"]/div[4]/button').click(timeout=2)

                if page.ele('xpath://*[@id="layui-layer1"]/div').text =='录单成功':
                    # 编号不存在，写入文件
                    with open('order_ids.txt','a', encoding='utf-8') as f:
                        f.write(f"{order_id}\n")
                    print(f"订单编号 {order_id} 已保存到文件")
                    show_order_notification(order_id+'\n'+extract_order_price(original_str)['购买项目']+'\n价格:'+extract_order_price(original_str)['接单价格'],'订单处理成功')

                elif page.ele('xpath://*[@id="layui-layer1"]/div').text== '必填项不能为空':
                    time.sleep(1)
                    PHONE_REGEX = r'\b1[3-9]\d{9}\b'
                    phone_pattern = re.compile(PHONE_REGEX, re.IGNORECASE)
                    page.ele('@placeholder=请输入游戏账号').input('必填',clear=True)
                    page.ele('@placeholder=请输入游戏密码').input('必填',clear=True)
                    phone_match = phone_pattern.search(original_str)
                    phone_num = phone_match.group() if phone_match else '未找到'
                    try:
                        page.ele('xpath://*[@id="clickId"]/div[3]/div[13]/div[6]/div/input').input(
                            phone_num, clear=True)
                    except Exception as e:
                        print(f"手机号输入框操作失败：{str(e)}")
                        show_order_notification("元素操作异常", "手机号输入框未找到或无法输入")
                    page.ele('xpath://*[@id="clickId"]/div[4]/button').click(timeout=2)
                    if page.ele('  xpath://*[@id="layui-layer2"]/div').text == '录单成功':
                        # 编号不存在，写入文件
                        with open('order_ids.txt', 'a', encoding='utf-8') as f:
                            f.write(f"{order_id}\n")
                        print(f"订单编号 {order_id} 已保存到文件")
                        show_order_notification(
                            order_id + '\n' + extract_order_price(original_str)['购买项目'] + '\n价格:' +
                            extract_order_price(original_str)['接单价格'], '本来是不能成功的，但是通过程序识别填写了不被录单系统识别的信息反而录单成功了')
                    else:
                        show_order_notification(page.ele('xpath://*[@id="layui-layer2"]/div').text,
                                                '订单处理失败,重定向链接')
                        page.get('http://ldl.jjpdoudian.cqwangyou.com/orderManage/addOrder')

                    with open('order_ids.txt','a', encoding='utf-8') as f:
                        f.write(f"{order_id}\n")
                    print(f"订单编号 {order_id} 已保存到文件")

                elif page.ele('xpath://*[@id="layui-layer1"]/div').text =='电话号码只能输入11位':
                    page.ele('xpath://*[@id="clickId"]/div[3]/div[13]/div[6]/div/input').input('领导不要惩罚我是顾客自己填错电话号码的',clear=True)
                    page.ele('xpath://*[@id="clickId"]/div[4]/button').click(timeout=2)
                    show_order_notification('电话号码有误，已改为[领导不要惩罚我是顾客自己填错电话号码的]强行提交。\n'+order_id + '\n' + extract_order_price(original_str)['购买项目'] + '\n价格:' +
                                             extract_order_price(original_str)['接单价格'], '订单处理成功')
                    with open('order_ids.txt','a', encoding='utf-8') as f:
                        f.write(f"{order_id}\n")
                    print(f"订单编号 {order_id} 已保存到文件")
                else:
                    show_order_notification(page.ele('xpath://*[@id="layui-layer1"]/div').text,'订单处理失败,重定向链接')
                    page.get('http://ldl.jjpdoudian.cqwangyou.com/orderManage/addOrder')
            elif result is None:
                print('处理异常，请重试')
            else:
                print ('网络检测到 '+order_id+' 已存在，写入order_ids.txt')
                with open('order_ids.txt', 'a', encoding='utf-8') as f:
                    f.write(f"{order_id}\n")

        show_toast(page, "正在自动填录...", level='info', duration=2000)

    except Exception as e:
        # 新增：异常捕获，避免程序崩溃并提示错误
        print(f"提取任务执行失败：{str(e)}")
        page.refresh()
        show_toast(page, "提取失败，查看控制台日志", level='error', duration=3000)
        show_order_notification(f"提取任务执行失败：{str(e)}", '订单处理失败')

def main():
    print("连接服务器中..")
    co = ChromiumOptions().set_browser_path(r'C:\Program Files\Google\Chrome\Application\chrome.exe').set_local_port(555)
    page = ChromiumPage(addr_or_opts=co)
    page.get('http://ldl.jjpdoudian.cqwangyou.com/orderManage/addOrder')
    while page.title != '添加订单':
        if page.title == '佳佳拍抖店管理系统':
            page.get('http://ldl.jjpdoudian.cqwangyou.com/orderManage/addOrder')
        pass
    # 注册热键
    keyboard.add_hotkey('ctrl+2', lambda: run_extraction_task(page))
    keyboard.wait('ctrl+0')
    print("程序已退出。")

if __name__ == "__main__":
    main()

