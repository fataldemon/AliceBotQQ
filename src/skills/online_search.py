import base64
import random
import re
import traceback

import html2text
from playwright.async_api import async_playwright
import playwright
import time
import asyncio


def image_to_base64(image_path: str) -> str:
    """读取本地图片，返回 base64 编码字符串"""
    with open(image_path, 'rb') as img_file:
        # 读取二进制数据并编码为 base64
        b64_bytes = base64.b64encode(img_file.read())
        # 将 bytes 转为字符串
        b64_string = b64_bytes.decode('utf-8')
    return b64_string


async def access_page_func(url: str, max_scrolls: int = 3):
    print(url)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        page = await browser.new_page()
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
            await browser.close()


async def online_search_func(item: str) -> tuple[str, list]:
    async with async_playwright() as p:
        try:
            # 设置 User-Agent
            user_agent = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
            )

            # 启动浏览器并设置上下文
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(user_agent=user_agent)  # 设置 User-Agent
            page = await context.new_page()

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
                    elif url.startswith("https://zh.wikipedia.org") or url.startswith("https://en.wikipedia.org") and (not wiki_token):
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
            await context.close()
            await browser.close()
        except Exception as e:
            info = "ERROR"
        return info, url_list


if __name__ == "__main__":
    info = asyncio.run(online_search_func("JOJO的奇妙冒险"))
    print(info)
    # text, links, b64img = asyncio.run(access_page_func("https://www.bilibili.com/", max_scrolls=1))
    # print(len(links))
    # if links:
    #     for link in links:  # 只打印前10个
    #         print(f"名称: {link['text']}, 地址: {link['href']}")

