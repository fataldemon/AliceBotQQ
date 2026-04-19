import base64
import random
import re
import subprocess
import traceback

import html2text
from playwright.async_api import async_playwright, Browser
import playwright
import time
import asyncio

# 访问网页前，请保证你有装Chrome
# 打开终端（cmd、PowerShell 或 Terminal），执行以下命令（根据你的系统选择）：
#
# Windows
#
# cmd
# "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\temp\chrome-debug-profile"
# macOS
#
# bash
# /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="/tmp/chrome-debug-profile"
# Linux
#
# bash
# google-chrome --remote-debugging-port=9222 --user-data-dir="/tmp/chrome-debug-profile"
# 执行后，会弹出一个全新的 Chrome 窗口（它的标题栏可能会显示“测试”或没有登录你的账号）。这个窗口和你日常的 Chrome 窗口完全独立。
# 在访问需要登录的网页时，你需要手动登录以让浏览器将token记录下来


# 全局变量，用于保存浏览器进程和连接
_browser_process: subprocess.Popen | None = None
_playwright = None
_browser: Browser | None = None


def _launch_debug_chrome():
    """启动一个独立的 Chrome 调试实例（仅启动一次）"""
    global _browser_process

    # 根据你的操作系统配置路径（这里以 Windows 为例）
    chrome_path = "C:/Program Files/Google/Chrome/Application/chrome.exe"
    user_data_dir = "C:/temp/chrome_debug_profile"  # 独立的 profile 目录
    cmd = [
        chrome_path,
        f"--user-data-dir={user_data_dir}",
        "--remote-debugging-port=9222",
        "--remote-allow-origins=*",
        "--noerrdialogs",
        "--disable-session-crashed-bubble",   # 禁用恢复弹窗
        "--disable-crash-reporter"
    ]
    _browser_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)  # 等待浏览器完全启动


async def _get_browser() -> Browser:
    """获取或创建连接到的调试浏览器（单例）"""
    global _playwright, _browser

    if _browser is not None:
        # 检查连接是否仍然有效
        try:
            await _browser.contexts  # 简单操作测试连接
            return _browser
        except:
            # 连接已断开，重新连接
            _browser = None

    if _playwright is None:
        _playwright = await async_playwright().start()

    # 尝试连接到已存在的调试浏览器
    try:
        _browser = await _playwright.chromium.connect_over_cdp("http://localhost:9222")
        print("连接到已存在的 Chrome 调试实例")
        return _browser
    except:
        # 连接失败，启动新的浏览器实例
        print("未检测到 Chrome 调试实例，正在启动...")
        _launch_debug_chrome()
        _browser = await _playwright.chromium.connect_over_cdp("http://localhost:9222")
        print("新 Chrome 调试实例已启动并连接")
        return _browser


def image_to_base64(image_path: str) -> str:
    """读取本地图片，返回 base64 编码字符串"""
    with open(image_path, 'rb') as img_file:
        # 读取二进制数据并编码为 base64
        b64_bytes = base64.b64encode(img_file.read())
        # 将 bytes 转为字符串
        b64_string = b64_bytes.decode('utf-8')
    return b64_string


# 注意：整个程序结束时，可以调用一个清理函数关闭浏览器（可选）
async def cleanup():
    global _playwright, _browser, _browser_process
    if _browser:
        await _browser.close()
        _browser = None
    if _playwright:
        await _playwright.stop()
        _playwright = None
    if _browser_process:
        _browser_process.terminate()
        _browser_process = None


async def access_page_func(url: str, max_scrolls: int = 3):
    """复用同一个调试浏览器访问页面"""
    print(f"访问网站{url}")
    browser = await _get_browser()
    # 获取第一个上下文（通常调试浏览器只有一个）
    context = browser.contexts[0]
    page = await context.new_page()
    try:
        # 1. 访问页面
        await page.goto(url, wait_until="domcontentloaded")
        # 2. 等待懒加载内容（如滚动加载评论区）
        # 模拟滚动到底部，触发懒加载（可根据需要选择）
        # 可选：有限滚动，而不是无限滚动
        if max_scrolls > 0:
            for _ in range(max_scrolls):
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await page.wait_for_timeout(2000)  # 等待新内容加载

        # 3. 获取页面标题（用于截图文件名）
        title = await page.title()
        safe_title = re.sub(r'[\\/*?:"<>|]', "_", title)
        # 4. 获取页面可见文本
        text_content = await page.inner_text('body')
        # 5. 获取所有链接及名称
        links = await page.evaluate('''() => {
                        const anchors = document.querySelectorAll('a');
                        const result = [];
                        for (const a of anchors) {
                            const text = a.innerText.trim();
                            const href = a.href;   // 自动转为绝对 URL
                            if (href && href !== '#' && !href.startsWith('javascript:')) {
                                result.push({ text: text, href: href });
                            }
                        }
                        return result;
                    }''')
        # 提取视频链接（B站专用）
        if url.startswith("https://www.bilibili.com"):
            video_links = await page.evaluate('''() => {
                            const videoLinks = new Map();
                            const anchors = document.querySelectorAll('a[href*="/video/"]');
                            for (const a of anchors) {
                                let text = a.innerText.trim();
                                const href = a.href;
                                if (text && href && href.includes('/video/')) {
                                    text = text.split('\\n')[0].slice(0, 100);
                                    videoLinks.set(href, text);
                                }
                            }
                            return Array.from(videoLinks.entries()).map(([href, text]) => ({ text, href }));
                        }''')
            links = video_links
        # 过滤掉 text 为空的链接
        links = [link for link in links if link.get('text', '').strip()]

        # 6. 截图并转 base64
        screenshot_path = f"screenshots/{safe_title}.png"
        await page.screenshot(path=screenshot_path, full_page=True)
        screenshot_base64 = image_to_base64(screenshot_path)

        return text_content, links, screenshot_base64
    except Exception as e:
        print(f"处理页面时出错: {e}")
        return None, None, None
    finally:
        # 注意：不要关闭 browser，否则会杀掉整个调试浏览器
        # 只关闭你操作的页面即可
        await page.close()
        await context.close()
        # 如果希望脚本结束后浏览器保持打开，可以保留；否则可以手动终止
        await cleanup()  # 可选：关闭浏览器


async def online_search_func(item: str) -> tuple[str, list]:
    browser = await _get_browser()
    # 获取第一个上下文（通常调试浏览器只有一个）
    context = browser.contexts[0]
    page = await context.new_page()
    try:
        # 初始化变量
        pages = []
        info = ""
        page_no = 0
        moegirl_token = False
        baike_token = False
        wiki_token = False
        max_retries = 3
        retries = 0

        while retries < max_retries:
            try:
                await page.goto(f"https://duckduckgo.com/?q={item}&t=h_&ia=web")
                await asyncio.sleep(random.uniform(1.5, 2))  # 添加随机延迟
                # 检查页面是否加载成功（以搜索结果为例）
                results = await page.query_selector_all('[data-testid="result"]')

                url_list = []
                summary_list = []
                for idx, result in enumerate(results, 1):
                    # 提取链接和标题
                    title_link = await result.query_selector('a[data-testid="result-title-a"]')
                    if not title_link:
                        continue
                    url = await title_link.get_attribute('href')
                    title = await title_link.inner_text()

                    # 提取摘要
                    snippet_elem = await result.query_selector('[data-testid="result-snippet"]')
                    if not snippet_elem:
                        # 可能的结构是 <div data-result="snippet"> 或 span 等
                        snippet_elem = await result.query_selector(
                            'div[data-result="snippet"] span, .OgdwYG6KE2qthn9XQWFC span')
                    snippet = await snippet_elem.inner_text() if snippet_elem else ""
                    url_list.append(url)

                    extracted = {
                        "index": idx,
                        "title": title,
                        "url": url,
                        "snippet": snippet
                    }
                    # 合并两个列表
                    summary_list.append(extracted)
                if not results:
                    raise Exception("未找到搜索结果，重试中...")
                break
            except Exception as e:
                retries += 1
                print(f"尝试第 {retries} 次加载失败: {e}")
                if retries >= max_retries:
                    raise Exception("多次尝试加载失败，停止重试。")
                    return "ERROR", []

        for url in url_list:
            if page_no >= 2 or (moegirl_token and baike_token):
                break
            try:
                if url.startswith("https://zh.moegirl.org.cn") and (not moegirl_token):
                    pages.append(await context.new_page())
                    await pages[page_no].goto(url)
                    await asyncio.sleep(random.uniform(1, 2))
                    box_locator = await pages[page_no].query_selector(".mw-parser-output >> .moe-infobox")
                    box_content = await box_locator.text_content()
                    box_content = box_content.replace("\n\n\n", "")
                    info += f"根据萌娘百科{url}提供的信息如下：\n{box_content}\n"
                    context_locator = await pages[page_no].query_selector_all(
                        ".mw-parser-output > h2:not(table *), .mw-parser-output > h3:not(table *), "
                        ".mw-parser-output > h4:not(table *), .mw-parser-output > p:not(table *), "
                        ".mw-parser-output > ul:not(table *)")
                    for item in context_locator:
                        search_info = await item.text_content()
                        search_info = search_info.replace("\n\n", "")
                        info += search_info + "\n"
                    page_no += 1
                    moegirl_token = True
                elif url.startswith("https://baike.baidu") and (not baike_token):
                    pages.append(await context.new_page())
                    await pages[page_no].goto(url)
                    await asyncio.sleep(random.uniform(1, 2))
                    # context_locator = await pages[page_no].query_selector(".lemmaSummary_c2Xg9")
                    context_locator = await pages[page_no].query_selector(".J-summary")
                    summary = await context_locator.text_content()
                    box_locator = await pages[page_no].query_selector(".J-basic-info")
                    brief_info = await box_locator.text_content()
                    info += f"根据百度百科{url}提供的信息如下：\n{brief_info}\n{summary}\n"
                    page_no += 1
                    baike_token = True
                elif url.startswith("https://zh.wikipedia.org") or url.startswith("https://en.wikipedia.org") and (
                not wiki_token):
                    pages.append(await context.new_page())
                    await pages[page_no].goto(url)
                    await asyncio.sleep(random.uniform(1, 2))
                    context_locator = await pages[page_no].query_selector_all(
                        ".mw-parser-output > h2:not(table *), .mw-parser-output > h3:not(table *), "
                        ".mw-parser-output > h4:not(table *), .mw-parser-output > p:not(table *), "
                        ".mw-parser-output > ul:not(table *)")
                    for item in context_locator:
                        search_info = await item.text_content()
                        info += f"根据Wikipedia网站{url}提供的信息如下：\n{search_info}\n"
                        # print(search_info.replace("\n\n", ""))
                    page_no += 1
            except Exception as e:
                traceback.print_exc()
                info += f"地址{url}上或许能得到有用的信息，但是目前无法访问......\n"

        info += f"其他网站的摘要信息：\n"
        for summary_item in summary_list:
            url = summary_item.get("url")
            title = summary_item.get("title")
            content = summary_item.get("snippet")
            info += f"URL：{url} 标题：{title} 摘要：{content}"
            info += "\n"
    except Exception as e:
        info = "ERROR"
    finally:
        for _page in pages:
            await _page.close()
        await page.close()
        await context.close()
        await cleanup()
    return info, url_list


if __name__ == "__main__":
    info = asyncio.run(online_search_func("JOJO的奇妙冒险"))
    print(info)
    # text, links, b64img = asyncio.run(access_page_func("https://www.bilibili.com/", max_scrolls=1))
    # print(len(links))
    # if links:
    #     for link in links:  # 只打印前10个
    #         print(f"名称: {link['text']}, 地址: {link['href']}")
