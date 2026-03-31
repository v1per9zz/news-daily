"""
每日新闻抓取脚本 v2
纯 Python 内置库（urllib, json, re）实现，无需安装额外依赖
每天运行，生成当日新闻 HTML 页面
"""
import os
import re
import json
import time
import html.parser
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime

# ========== 配置 ==========
OUTPUT_DIR = r"D:\龙瞎生成文件\news_daily"
INDEX_FILE = os.path.join(OUTPUT_DIR, "index.html")
CATEGORIES = ["金融·市场", "社会·民生", "国际·外交", "文艺·娱乐"]

# 订阅源配置（基于新浪滚动新闻，所有源均可国内直连）
RSS_SOURCES = {
    "金融·市场": [
        ("新浪财经", "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&num=15&page=1"),
        ("新浪财经2", "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2517&num=15&page=1"),
        ("36氪", "https://36kr.com/feed"),
    ],
    "社会·民生": [
        ("新浪社会", "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2515&num=15&page=1"),
    ],
    "国际·外交": [
        ("新浪国际外交", "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2511&num=15&page=1"),
        ("新浪国际军事", "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2514&num=15&page=1"),
    ],
    "文艺·娱乐": [
        ("新浪娱乐", "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2518&num=15&page=1"),
        ("新浪港台", "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2669&num=10&page=1"),
    ],
}


def make_request(url, referer=None):
    """通用 HTTP 请求"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    return req


def fetch_json(url, referer=None):
    """获取 JSON 数据"""
    try:
        req = make_request(url, referer)
        with urllib.request.urlopen(req, timeout=10) as r:
            charset = r.headers.get_content_charset() or "utf-8"
            return json.loads(r.read().decode(charset))
    except Exception as e:
        print(f"[JSON获取失败] {url}: {e}")
    return None


def fetch_sina_roll(url):
    """抓取新浪滚动新闻（JSON 格式）"""
    data = fetch_json(url)
    if not data:
        return []
    items = data.get("result", {}).get("data", [])
    result = []
    for item in items:
        title = item.get("title", "").strip()
        intro = item.get("intro", "").strip()[:150]
        url_link = item.get("url", "")
        if title:
            result.append((title, intro, url_link))
    return result


def fetch_rss(url):
    """抓取标准 RSS XML"""
    try:
        req = make_request(url)
        with urllib.request.urlopen(req, timeout=10) as r:
            charset = r.headers.get_content_charset() or "utf-8"
            xml_data = r.read().decode(charset)

        # 解析 XML
        root = ET.fromstring(xml_data)

        # 通用 RSS 命名空间处理
        ns = {"rss": "http://purl.org/rss/1.0/"}
        items = []
        for item in root.iter("item"):
            title = ""
            link = ""
            desc = ""
            for child in item:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag == "title":
                    title = child.text or ""
                elif tag == "link":
                    link = child.text or ""
                elif tag in ("description", "summary", "content"):
                    text = child.text or ""
                    # 去除 HTML 标签
                    text = re.sub(r"<[^>]+>", "", text).strip()[:150]
                    if text and not desc:
                        desc = text
            if title:
                items.append((title.strip(), desc, link))
        return items
    except Exception as e:
        print(f"[RSS解析失败] {url}: {e}")
    return []


def fetch_douban():
    """抓取豆瓣热门电影"""
    data = fetch_json("https://movie.douban.com/j/search_subject_jsoon?tag=%E7%83%AD%E9%97%A8&type=o")
    if not data:
        return []
    result = []
    for s in data.get("subjects", [])[:8]:
        title = s.get("title", "")
        rate = s.get("rate", "暂无")
        url = s.get("url", "")
        if title:
            result.append((title, f"豆瓣评分: {rate}", url))
    return result


def fetch_news_for_category(category):
    """抓取某个分类的新闻"""
    results = []
    sources = RSS_SOURCES.get(category, [])
    for name, url in sources:
        try:
            if "sina" in url:
                items = fetch_sina_roll(url)
            elif "douban" in url:
                items = fetch_douban()
            else:
                items = fetch_rss(url)
            results.extend(items)
            print(f"  [{name}] -> {len(items)} 条")
        except Exception as e:
            print(f"  [{name}] 失败: {e}")
    # 去重（按标题）
    seen = set()
    deduped = []
    for item in results:
        if item[0] not in seen:
            seen.add(item[0])
            deduped.append(item)
    return deduped[:8]


def get_day_name():
    day_map = {
        "Monday": "周一", "Tuesday": "周二", "Wednesday": "周三",
        "Thursday": "周四", "Friday": "周五", "Saturday": "周六", "Sunday": "周日",
    }
    return day_map.get(datetime.now().strftime("%A"), "")


def escape_html(text):
    """HTML 转义"""
    if not text:
        return ""
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;"))


def generate_html(news_data, today_str):
    """生成 HTML 页面"""
    day_name = get_day_name()
    today_display = datetime.now().strftime(f"%Y年%m月%d日 {day_name}")
    update_time = datetime.now().strftime("%H:%M:%S")
    emoji_map = {"金融·市场": "💰", "社会·民生": "🏛️", "国际·外交": "🌏", "文艺·娱乐": "🎨"}

    category_sections = ""
    for cat, items in news_data.items():
        emoji = emoji_map.get(cat, "📰")
        cat_id = re.sub(r"·", "", cat).replace(" ", "")

        if items:
            news_cards = ""
            for title, snippet, url in items:
                title = escape_html(title)
                snippet = escape_html(snippet)
                if not snippet:
                    snippet = "点击查看详情"
                safe_url = escape_html(url)
                news_cards += f"""
            <div class="news-item" onclick="window.open('{safe_url}', '_blank')">
                <div class="news-title">{title}</div>
                <div class="news-snippet">{snippet}</div>
            </div>"""

            category_sections += f"""
        <div class="category-section" id="cat-{cat_id}">
            <h2 class="cat-title">{emoji} {cat}</h2>
            <div class="news-list">{news_cards}
            </div>
        </div>"""

    tabs_html = "".join(
        f'<span class="tab" data-cat="{re.sub(r"·", "", c).replace(" ", "")}" '
        f'onclick="switchTab(this, \'{re.sub(r"·", "", c).replace(" ", "")}\')">{c}</span>'
        for c in CATEGORIES
    )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>每日新闻速览 {today_str}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif; background: #f0f2f5; color: #1a1a2e; min-height: 100vh; }}
        .header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%); color: white; padding: 28px 24px 20px; position: sticky; top: 0; z-index: 100; box-shadow: 0 4px 20px rgba(0,0,0,0.25); }}
        .header-top {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px; }}
        .site-name {{ font-size: 20px; font-weight: 700; letter-spacing: 2px; display: flex; align-items: center; gap: 8px; }}
        .update-info {{ font-size: 12px; opacity: 0.5; text-align: right; line-height: 1.6; }}
        .date-display {{ font-size: 32px; font-weight: 900; margin-bottom: 4px; letter-spacing: 1px; background: linear-gradient(90deg, #fff, #a8d8ea); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }}
        .day-display {{ font-size: 14px; opacity: 0.6; margin-bottom: 14px; }}
        .tabs {{ display: flex; gap: 8px; flex-wrap: wrap; }}
        .tab {{ padding: 7px 15px; border-radius: 22px; background: rgba(255,255,255,0.1); font-size: 13px; cursor: pointer; transition: all 0.25s; border: 1px solid rgba(255,255,255,0.15); color: rgba(255,255,255,0.8); backdrop-filter: blur(4px); }}
        .tab:hover {{ background: rgba(255,255,255,0.2); color: white; }}
        .tab.active {{ background: rgba(255,255,255,0.95); color: #1a1a2e; font-weight: 700; border-color: transparent; }}
        .main {{ max-width: 920px; margin: 0 auto; padding: 22px 16px 56px; }}
        .category-section {{ margin-bottom: 30px; display: none; }}
        .category-section:first-of-type {{ display: block; }}
        .cat-title {{ font-size: 17px; font-weight: 700; margin-bottom: 14px; padding-bottom: 8px; border-bottom: 3px solid #e94560; display: inline-block; color: #1a1a2e; }}
        .news-list {{ display: flex; flex-direction: column; gap: 10px; }}
        .news-item {{ background: white; border-radius: 12px; padding: 16px 18px; cursor: pointer; transition: all 0.22s; box-shadow: 0 1px 4px rgba(0,0,0,0.07); border: 1px solid #e8e8e8; }}
        .news-item:hover {{ box-shadow: 0 8px 24px rgba(233,69,96,0.14); transform: translateY(-2px); border-color: #e94560; }}
        .news-title {{ font-size: 15px; font-weight: 600; color: #1a1a2e; margin-bottom: 7px; line-height: 1.55; }}
        .news-snippet {{ font-size: 13px; color: #777; line-height: 1.65; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
        .footer {{ text-align: center; font-size: 12px; color: #ccc; padding: 20px 0 36px; }}
        @keyframes fadeInUp {{ from {{ opacity: 0; transform: translateY(12px); }} to {{ opacity: 1; transform: translateY(0); }} }}
        .category-section:first-of-type .news-item {{ animation: fadeInUp 0.4s ease both; }}
        .category-section:first-of-type .news-item:nth-child(2) {{ animation-delay: 0.07s; }}
        .category-section:first-of-type .news-item:nth-child(3) {{ animation-delay: 0.14s; }}
        .category-section:first-of-type .news-item:nth-child(4) {{ animation-delay: 0.21s; }}
        .category-section:first-of-type .news-item:nth-child(5) {{ animation-delay: 0.28s; }}
        .category-section:first-of-type .news-item:nth-child(6) {{ animation-delay: 0.35s; }}
        @media (max-width: 600px) {{ .date-display {{ font-size: 24px; }} .site-name {{ font-size: 17px; }} .main {{ padding: 14px 10px 40px; }} .header {{ padding: 20px 16px 16px; }} }}
    </style>
</head>
<body>
    <div class="header">
        <div class="header-top">
            <div class="site-name">📰 每日新闻速览</div>
            <div class="update-info">自动更新<br>{update_time}</div>
        </div>
        <div class="date-display">{today_str}</div>
        <div class="day-display">{today_display}</div>
        <div class="tabs">{tabs_html}
        </div>
    </div>
    <div class="main">{category_sections}
    </div>
    <div class="footer">内容综合自公开 RSS 订阅源 · 点击卡片跳转原文</div>
    <script>
        function switchTab(el, cat) {{
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            el.classList.add('active');
            document.querySelectorAll('.category-section').forEach(s => s.style.display = 'none');
            const section = document.getElementById('cat-' + cat);
            if (section) section.style.display = 'block';
        }}
    </script>
</body>
</html>"""
    return html


def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] === 每日新闻抓取开始 ===")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"[目录] {OUTPUT_DIR}")

    today_str = datetime.now().strftime("%Y年%m月%d日")
    all_data = {}
    total = 0

    for cat in CATEGORIES:
        print(f"\n[抓取中] {cat}")
        items = fetch_news_for_category(cat)
        all_data[cat] = items
        total += len(items)
        print(f"[完成] {cat} -> {len(items)} 条")

    if total == 0:
        print("\n[警告] 所有源均未获取到数据，请检查网络")

    html_content = generate_html(all_data, today_str)

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\n[完成] index.html -> {INDEX_FILE}")
    print(f"[总计] 共 {total} 条 | {datetime.now().strftime('%H:%M:%S')}] === 完成 ===")


if __name__ == "__main__":
    main()
