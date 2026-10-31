#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
条目提取层：把 HTTP 响应转换成结构化条目。

设计原则（对应机制缺陷 M1：三层混淆）：
  1. 传输成功 != 内容可用 != 窗口内有条目。三者必须分别可见，不得压成一个 bool。
  2. 每个源声明 extract 模式；模式跑完但 0 条目，必须显式报 empty，
     解析器抛错必须显式报 parse_failed，不得静默返回空列表冒充成功。
  3. 条目统一为 {uid, title, url, published, date_precision, snippet}，
     published 统一为 ISO 8601（带时区），便于窗口比对。

支持模式：
  rss              RSS 2.0 / RSS 1.0 (RDF)
  atom             Atom 1.0
  json_api         已知 JSON schema（hn_algolia / hf_daily_papers / generic_list）
  markdown_dated   Markdown changelog（"## October, 2026" + "### Oct 22"）
  html_cards       通用 HTML 卡片扫描（<a> 内含日期文本）
  sitemap          只产出 URL 集合，用于 surface diff，不计入条目数

用法：
  from extract import extract_items, classify
  meta = classify(body)
  result = extract_items(body, mode="atom", source_url=url)
"""
import hashlib
import html
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

# 代理拦截页特征。HIS = Huawei Internal Proxy，是 MWG/HIS 网关的实际返回页标题。
# 这三个签名必须同时覆盖，否则拦截页会被当成正常 HTML 落盘并记为 success。
BLOCK_SIGNATURES = (
    "HIS Proxy",
    "Huawei Proxy",
    "mwg-internal",
    "访问外部AI大模型",
)

# 常见日期格式
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MONTH_NAMES = {v: k for k, v in _MONTHS.items()}

_RE_DATE_MDY = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})\b",
    re.I)
_RE_DATE_DMY = re.compile(r"\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{4})\b", re.I)
_RE_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?(Z|[+-]\d{2}:?\d{2})?\b")


def _local(tag: str) -> str:
    """去掉 XML 命名空间，返回 local name。"""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _find_child(node, name):
    for c in node:
        if _local(c.tag) == name:
            return c
    return None


def _text(node) -> str:
    if node is None:
        return ""
    return (node.text or "").strip()


def _strip_html(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", s or "")).strip()


def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def make_uid(url: str, title: str, published: str) -> str:
    raw = (url or "").strip() or f"{title}|{published}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _precision_of(dt: datetime) -> str:
    """
    从解析出的时刻反推真实精度。

    RSS 的 pubDate 语法上精确到秒，但大量源实际只填到日，表现为 00:00:00
    （arXiv 全部 370 条、hf_blog 759/889、openai_news_rss 387/1316）。
    把这种"整点零点"当 second，等于给一个只有日的信息加了 50 小时的
    虚假确定性，窗口边界上会成批误判。

    判定：00:00:00 视为 day。代价是真正的 UTC 零点发布会被低估精度，
    这恰是我们要的方向——宁可标模糊，不可漏扫描。
    """
    if dt.hour == 0 and dt.minute == 0 and dt.second == 0 and dt.microsecond == 0:
        return "day"
    return "second"


def parse_date(value: str):
    """
    尽量把各种日期字符串归一为 (ISO8601 with tz, precision)。
    precision: 'second' | 'day' | 'none'
    零点时刻一律降级为 day（见 _precision_of）。
    邮件格式优先用 parsedate（RFC 2822），其余走正则。
    """
    s = _squash(value)
    if not s:
        return "", "none"

    # RFC 2822（RSS pubDate）
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(s)
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat(), _precision_of(dt)
    except Exception:
        pass

    # ISO 8601
    m = _RE_ISO.search(s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hh = int(m.group(4) or 0)
        mm = int(m.group(5) or 0)
        ss = int(m.group(6) or 0)
        tzs = m.group(7)
        try:
            if tzs and tzs != "Z":
                sign = 1 if tzs[0] == "+" else -1
                tzs = tzs.replace(":", "")
                tz = timezone(sign * timedelta(hours=int(tzs[1:3]), minutes=int(tzs[3:5])))
            elif tzs == "Z":
                tz = timezone.utc
            else:
                tz = timezone.utc
            dt = datetime(y, mo, d, hh, mm, ss, tzinfo=tz)
            bare_date = not m.group(4)     # 字符串本身只给到日
            return dt.isoformat(), "day" if bare_date else _precision_of(dt)
        except ValueError:
            return "", "none"

    # "Oct 22, 2026"
    m = _RE_DATE_MDY.search(s)
    if m:
        mo = _MONTHS[m.group(1)[:3].lower()]
        return datetime(int(m.group(3)), mo, int(m.group(2)), tzinfo=timezone.utc).isoformat(), "day"

    # "22 Oct 2026"
    m = _RE_DATE_DMY.search(s)
    if m:
        mo = _MONTHS[m.group(2)[:3].lower()]
        return datetime(int(m.group(3)), mo, int(m.group(1)), tzinfo=timezone.utc).isoformat(), "day"

    return "", "none"


def classify(body: bytes, url: str = "") -> str:
    """
    判定内容形态。顺序很重要：拦截页优先级最高，因为它是 200 + HTML，
    如果先判 html 就会把拦截页当成正常页面。
    """
    head = body[:4000].decode("utf-8", "ignore")
    if any(sig in head for sig in BLOCK_SIGNATURES):
        return "block_page"

    stripped = head.lstrip()
    low = stripped[:400].lower()
    if stripped.startswith("<?xml") or "<rss" in low or "<feed" in low or "<rdf" in low:
        return "atom" if "<feed" in low else "rss"
    if url.endswith(".md") or stripped.startswith("# "):
        return "markdown"
    if stripped.startswith("{") or stripped.startswith("["):
        return "json"
    if "<html" in low or "<!doctype html" in low:
        return "html"
    return "unknown"


def _item_from(title, url, published_raw, snippet, precision=None):
    published, detected = parse_date(published_raw)
    precision = precision or detected
    title = _squash(_strip_html(title))
    snippet = _squash(_strip_html(snippet))[:300]
    return {
        "uid": make_uid(url, title, published),
        "title": title,
        "url": (url or "").strip(),
        "published": published,
        "date_precision": precision,
        "snippet": snippet,
    }


# ---------- XML feeds ----------
def _extract_xml(body: bytes, kind: str):
    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        raise ValueError(f"XML parse error: {e}")

    node_name = "item" if kind == "rss" else "entry"
    nodes = [n for n in root.iter() if _local(n.tag) == node_name]
    if not nodes and kind == "rss":
        # RDF 里 item 直接挂在根下，iter 已覆盖；兜底再找一次
        nodes = [n for n in root if _local(n.tag) == "item"]

    items = []
    for n in nodes:
        title = _text(_find_child(n, "title"))

        # Atom: <link href=.../>；RSS: <link>...</link>
        url = ""
        link = _find_child(n, "link")
        if link is not None:
            url = link.get("href") or _text(link)
        if not url:
            for c in n:
                if _local(c.tag) == "link" and c.get("href"):
                    url = c.get("href")
                    break
        if not url:
            url = _text(_find_child(n, "guid")) or _text(_find_child(n, "id"))

        published = ""
        for key in ("pubDate", "published", "updated", "date", "dc:date"):
            v = _text(_find_child(n, key))
            if v:
                published = v
                break

        snippet = ""
        for key in ("description", "summary", "content"):
            v = _text(_find_child(n, key))
            if v:
                snippet = v
                break

        if title or url:
            items.append(_item_from(title, url, published, snippet))
    return items


# ---------- JSON APIs ----------
def _extract_json(body: bytes, mode: str):
    try:
        data = json.loads(body.decode("utf-8", "ignore"))
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON parse error: {e}")

    rows = []
    if mode == "hf_trending":
        # {"recentlyTrending": [{"repoData": {"id": "org/name", ...}}]}
        for entry in data.get("recentlyTrending", []):
            rd = entry.get("repoData", entry)
            rid = rd.get("id") or rd.get("modelId") or ""
            rows.append({
                "title": rid,
                "url": f"https://huggingface.co/{rid}" if rid else "",
                # trending 无发布时间，只有趋势位次；这不是"无日期源"而是"趋势源"
                "published": "",
                "snippet": f"downloads={rd.get('downloads','?')} likes={rd.get('likes','?')}",
            })
    elif mode == "hn_algolia":
        rows = [{
            "title": h.get("title") or h.get("story_title") or "",
            "url": h.get("url") or h.get("story_url") or
                   f"https://news.ycombinator.com/item?id={h.get('objectID','')}",
            "published": h.get("created_at", ""),
            "snippet": f"points={h.get('points')} comments={h.get('num_comments')}",
        } for h in data.get("hits", [])]
    elif mode == "hf_daily_papers":
        src = data if isinstance(data, list) else data.get("papers", [])
        for p in src:
            paper = p.get("paper", p)
            rows.append({
                "title": paper.get("title", ""),
                "url": f"https://huggingface.co/papers/{paper.get('id','')}",
                "published": paper.get("publishedAt") or p.get("publishedAt", ""),
                "snippet": (paper.get("summary") or "")[:300],
            })
    else:  # generic_list
        # 常见包裹键：hn_algolia 用 hits，其余用 items/data/results/papers
        src = data if isinstance(data, list) else (
            data.get("items") or data.get("data") or data.get("results")
            or data.get("hits") or data.get("papers") or [])
        for row in src:
            if not isinstance(row, dict):
                continue
            rows.append({
                "title": row.get("title") or row.get("name") or "",
                "url": row.get("url") or row.get("link") or row.get("html_url") or "",
                "published": (row.get("published") or row.get("created_at") or
                              row.get("updated_at") or row.get("date") or ""),
                "snippet": (row.get("description") or row.get("summary") or "")[:300],
            })
    return [_item_from(r["title"], r["url"], r["published"], r["snippet"])
            for r in rows if r.get("title") or r.get("url")]


# ---------- Markdown changelog ----------
_RE_MD_MONTH = re.compile(r"^##\s+([A-Za-z]+),?\s+(\d{4})\s*$")
_RE_MD_DAY = re.compile(r"^###\s+([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2})\s*$")
# ISO 日期标题： "### 2026-10-14: GPT-4 series model deprecations"
_RE_MD_ISO_HEADING = re.compile(
    r"^#{2,4}\s+(\d{4})-(\d{2})-(\d{2})\s*[:：]?\s*(.*)$")
# Markdown 表格： deprecation 页的主体是表格，日期在单元格里
_RE_MD_TABLE_ROW = re.compile(r"^\|(.+)\|\s*$")


def _extract_markdown_iso_headings(body: bytes, source_url: str):
    """
    适配 "### 2026-10-14: 标题" 结构（OpenAI deprecations 页）。
    日期直接内嵌在标题里，不需要跨行拼装年份。
    """
    text = body.decode("utf-8", "ignore")
    lines = text.splitlines()
    items = []
    cur = None
    buf = []

    def flush():
        nonlocal cur, buf
        if cur:
            y, m, d, rest = cur
            title = _squash(_strip_html(rest)) or f"{y}-{m:02d}-{d:02d}"
            snippet = _squash(_strip_html(" ".join(buf)))[:300]
            pub = datetime(y, m, d, tzinfo=timezone.utc).isoformat()
            items.append(_item_from(
                title, f"{source_url}#{y}-{m:02d}-{d:02d}", pub, snippet,
                precision="day"))
        cur, buf = None, []

    for ln in lines:
        m = _RE_MD_ISO_HEADING.match(ln)
        if m:
            flush()
            cur = (int(m.group(1)), int(m.group(2)), int(m.group(3)),
                   m.group(4).strip())
            continue
        if cur:
            buf.append(ln)
    flush()
    return items


def extract_markdown_any(body: bytes, source_url: str) -> list[dict]:
    """
    Markdown 解析总入口：两种结构都试，取条目多的那个。
    changelog 用 月/日 两级标题；deprecations 用 ISO 日期标题。
    """
    a = _extract_markdown_dated(body, source_url)
    b = _extract_markdown_iso_headings(body, source_url)
    return b if len(b) > len(a) else a


def _extract_markdown_dated(body: bytes, source_url: str):
    """
    适配 "## October, 2026" + "### Oct 22" 结构的 changelog。
    这类页面（OpenAI API changelog）只有月/日两级标题，年份在二级标题里，
    必须把上下文串起来才能得到完整日期。
    """
    text = body.decode("utf-8", "ignore")
    lines = text.splitlines()

    cur_year = cur_month = None
    cur_day = None
    buf = []
    items = []

    def flush():
        nonlocal buf, cur_day
        if cur_day is None:
            buf = []
            return
        lines = [ln.strip() for ln in buf if ln.strip()]
        if not lines:
            buf = []
            return

        # 这类 changelog 的第一行是"类型头"（Feature / Update · Model: x · API: y），
        # 常常过于简短（例如只有 "Feature"），单用它作标题不可用于候选池判断。
        # 因此标题 = 类型头 + 描述首句。
        header = _squash(_strip_html(lines[0]))
        body_lines = lines[1:] or [lines[0]]
        body_text = _squash(_strip_html(" ".join(body_lines)))
        first_sentence = re.split(r"(?<=[.!?])\s+", body_text)[0] if body_text else ""
        first_sentence = first_sentence[:140]

        if header and first_sentence and first_sentence != header:
            title = f"{header} — {first_sentence}"
        else:
            title = header or first_sentence

        snippet = _squash(_strip_html(" ".join(lines)))[:300]
        if title:
            pub = datetime(cur_year, cur_month, cur_day, tzinfo=timezone.utc).isoformat()
            items.append(_item_from(
                title, f"{source_url}#{cur_year}-{cur_month:02d}-{cur_day:02d}",
                pub, snippet, precision="day"))
        buf = []

    for ln in lines:
        m = _RE_MD_MONTH.match(ln)
        if m:
            flush()
            cur_day = None
            cur_year = int(m.group(2))
            mon = _MONTHS.get(m.group(1)[:3].lower())
            cur_month = mon
            continue
        m = _RE_MD_DAY.match(ln)
        if m and cur_year and cur_month:
            flush()
            cur_day = int(m.group(2))
            continue
        if cur_day is not None:
            buf.append(ln)
    flush()
    return items


# ---------- HTML cards ----------
_RE_A_TAG = re.compile(r"<a\b([^>]*)>(.*?)</a>", re.S | re.I)
_RE_HREF = re.compile(r'href\s*=\s*["\']([^"\']+)["\']', re.I)


def _extract_html_articles(body: bytes, base_url: str):
    """
    <article> 结构：<h2><a href>标题</a></h2> ... <time datetime="">日期</time>
    这是 WordPress / 技术博客搜索页的常见结构（NVIDIA developer blog 搜索页等）。
    比通用 <a> 扫描精确：标题与日期来自同一容器，不会串到导航链接。
    """
    text = body.decode("utf-8", "ignore")
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)

    items = []
    for am in re.finditer(r"<article\b[^>]*>(.*?)</article>", text, re.S | re.I):
        art = am.group(1)
        hm = re.search(r"<h[1-4][^>]*>\s*<a\b([^>]*)>(.*?)</a>", art, re.S | re.I)
        if not hm:
            continue
        href_m = _RE_HREF.search(hm.group(1))
        if not href_m:
            continue
        href = href_m.group(1).strip()
        title = _squash(_strip_html(hm.group(2)))
        if not title:
            continue

        published_raw = ""
        tm = re.search(r"<time\b([^>]*)>(.*?)</time>", art, re.S | re.I)
        if tm:
            dm = re.search(r'datetime\s*=\s*["\']([^"\']+)["\']', tm.group(1))
            published_raw = (dm.group(1) if dm and dm.group(1) else
                             _squash(_strip_html(tm.group(2))))

        pm = re.search(r"<p[^>]*>(.*?)</p>", art, re.S | re.I)
        snippet = _squash(_strip_html(pm.group(1))) if pm else ""

        if href.startswith("/"):
            mm = re.match(r"(https?://[^/]+)", base_url)
            href = (mm.group(1) if mm else "") + href

        items.append(_item_from(title, href, published_raw, snippet))
    return items


def _extract_html_cards(body: bytes, base_url: str):
    """
    通用卡片扫描：抽出所有 <a>，若其可见文本里含日期，则产出一条。
    这能覆盖 claude.com/blog 这类 ResourceCard 结构（文本形如
    "Article Oct 22, 2026 Building agents: ..."），而不依赖站点私有 class 名。
    """
    text = body.decode("utf-8", "ignore")
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)

    items = []
    for m in _RE_A_TAG.finditer(text):
        attrs, inner = m.group(1), m.group(2)
        href_m = _RE_HREF.search(attrs)
        if not href_m:
            continue
        href = href_m.group(1).strip()
        if href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:"):
            continue
        visible = _squash(_strip_html(inner))
        if len(visible) < 12:
            continue

        dm = _RE_DATE_MDY.search(visible)
        if not dm:
            continue
        # 必须把 parse_date 判定的精度一起传下去。
        # 只传 ISO 串会导致 _item_from 二次解析："2026-10-21T00:00:00+00:00"
        # 带 T，会被认成 second，日粒度就此伪装成精确到秒 —— 于是
        # "Oct 21" 被当成 10-21 00:00Z（= 08:00 +08），落在窗口外被丢弃。
        published, prec = parse_date(dm.group(0))

        # 优先用卡片内的语义化标题元素（h2/h3 或 class 含 title 的节点）。
        # 这是真实结构，比从拼接文本里猜标题/正文分界可靠得多。
        title = ""
        hm = re.search(r"<h[1-6][^>]*>(.*?)</h[1-6]>", inner, re.S | re.I)
        if hm:
            title = _squash(_strip_html(hm.group(1)))
        if not title:
            tm = re.search(
                r'<[^>]+class="[^"]*(?:title|Title)[^"]*"[^>]*>(.*?)</[^>]+>',
                inner, re.S)
            if tm:
                title = _squash(_strip_html(tm.group(1)))

        # 摘要 = 卡片全文去掉标题、类型词、日期后的剩余
        snippet = visible.replace(dm.group(0), " ")
        snippet = re.sub(r"^\s*(Article|Blog|News|Post|Update)\s+", " ", snippet,
                         flags=re.I)
        if title:
            snippet = snippet.replace(title, " ", 1)
        snippet = _squash(snippet)

        # 兜底：结构里没有标题元素时，从文本推断
        if not title:
            rest = snippet
            mm2 = re.search(r"^(.*?[?:])\s+(.{20,})$", rest)
            if mm2 and 15 <= len(mm2.group(1)) <= 120:
                title, snippet = _squash(mm2.group(1)), _squash(mm2.group(2))
            elif len(rest) > 120:
                cut = rest.rfind(" ", 0, 120)
                cut = cut if cut > 40 else 120
                title, snippet = rest[:cut].rstrip(",;"), rest[cut:].strip()
            else:
                title, snippet = rest, ""

        if href.startswith("/"):
            mm3 = re.match(r"(https?://[^/]+)", base_url)
            href = (mm3.group(1) if mm3 else "") + href

        if title:
            items.append(_item_from(title, href, published, snippet, precision=prec))
    return items


def _extract_sitemap(body: bytes):
    """sitemap 只产出 URL，用于 surface diff。"""
    text = body.decode("utf-8", "ignore")
    return [_item_from("", u, "", "") for u in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", text)]


# ---------- 总入口 ----------
_ARXIV_BATCH = re.compile(
    r'<h3>\s*(?:\w{3}),\s*(\d{1,2}\s+\w{3}\s+\d{4})[^<]*</h3>(.*?)(?=<h3>|\Z)',
    re.S | re.I)
_ARXIV_ID = re.compile(r'href\s*=\s*"/abs/(\d{4}\.\d{4,5})"', re.I)
_ARXIV_TITLE = re.compile(
    r"<div class='list-title mathjax'>\s*<span[^>]*>Title:</span>\s*(.*?)\s*</div>", re.S)
_ARXIV_TYPE = re.compile(r'\(\s*(cross-list|replaced?|replace-cross)\b', re.I)


def _extract_gh_releases(body: bytes, source_url: str = "") -> list:
    """解析 api.github.com/repos/<org>/<repo>/releases。

    published_at 是秒级且带时区，可直接归窗；releases 页的 HTML 不带年份，
    抓下来只能当线索，不能当结论。草稿版（draft）不算已发布。
    """
    data = json.loads(body.decode("utf-8", "ignore"))
    if not isinstance(data, list):
        return []
    out = []
    for r in data:
        if not isinstance(r, dict) or r.get("draft"):
            continue
        pub = r.get("published_at") or r.get("created_at")
        if not pub:
            continue
        tag = r.get("tag_name") or ""
        out.append({
            "uid": str(r.get("id") or tag),
            "title": (r.get("name") or tag or "release").strip(),
            "url": r.get("html_url") or source_url,
            "published": pub.replace("Z", "+00:00"),
            "date_precision": "second",
            "prerelease": bool(r.get("prerelease")),
            "tag": tag,
            "snippet": (r.get("body") or "")[:300],
        })
    return out


def _extract_arxiv_listing(body: bytes, source_url: str = "") -> list:
    """解析 arXiv 的 /list/<cat>/pastweek 归档页。

    周末 RSS 返回合法但空的 feed，整批论文会被漏掉（实测 cs.CL/LG/MA/RO 共 709 篇）。
    归档页按 <h3>Fri, 30 Oct 2026</h3> 分批，每批就是一次公告。

    published 一律写该批次的公告时刻（上海 12:00，对应美东前一日 20:00 的公告），
    精度 batch —— 不用论文的提交时刻：论文在公告前不可见，"首次公开"只能是公告时刻，
    否则同一批次内会按提交先后产生随机的归窗边界（task_def §9）。
    cross-list 与 replaced 条目不是本轮新论文，标 announce_type 供下游过滤。
    """
    html_text = body.decode("utf-8", "ignore")
    out, seen = [], set()
    for date_str, seg in _ARXIV_BATCH.findall(html_text):
        try:
            d = datetime.strptime(date_str.strip(), "%d %b %Y").date()
        except ValueError:
            continue
        published = f"{d.isoformat()}T12:00:00+08:00"
        ids = _ARXIV_ID.findall(seg)
        titles = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", t)).strip()
                  for t in _ARXIV_TITLE.findall(seg)]
        types = _ARXIV_TYPE.findall(seg)
        for n, aid in enumerate(ids):
            if aid in seen:
                continue
            seen.add(aid)
            out.append({
                "uid": aid,
                "title": html.unescape(titles[n]) if n < len(titles) else aid,
                "url": f"https://arxiv.org/abs/{aid}",
                "published": published,
                "date_precision": "batch",
                "announce_type": (types[n].lower() if n < len(types) else "new"),
                "snippet": f"arXiv 公告批次 {d.isoformat()}",
            })
    return out


def extract_items(body: bytes, mode: str, source_url: str = "", json_mode: str = "") -> dict:
    """
    返回 {status, items, error}。
    status:
      ok            解析成功且产出条目
      empty         解析成功但 0 条目（源确实没有内容，或站点结构变了）
      parse_failed  解析器报错（内容形态与声明模式不匹配）
      blocked       代理拦截页
      skipped       非采集类（sitemap 之外需要跳过的）
    """
    kind = classify(body, source_url)
    if kind == "block_page":
        return {"status": "blocked", "items": [], "error": "proxy block page detected"}

    try:
        if mode in ("rss", "atom"):
            if kind not in ("rss", "atom"):
                return {"status": "parse_failed", "items": [],
                        "error": f"expected feed, got {kind}"}
            items = _extract_xml(body, kind)
        elif mode == "json_api":
            if kind != "json":
                return {"status": "parse_failed", "items": [],
                        "error": f"expected json, got {kind}"}
            items = _extract_json(body, json_mode)
        elif mode == "markdown_dated":
            if kind != "markdown":
                return {"status": "parse_failed", "items": [],
                        "error": f"expected markdown, got {kind}"}
            items = extract_markdown_any(body, source_url)
        elif mode == "html_cards":
            if kind != "html":
                return {"status": "parse_failed", "items": [],
                        "error": f"expected html, got {kind}"}
            # 先试精确的 <article> 结构，再退回通用 <a> 扫描，取条目多的
            arts = _extract_html_articles(body, source_url)
            cards = _extract_html_cards(body, source_url)
            items = arts if len(arts) >= len(cards) else cards
        elif mode == "github_releases":
            items = _extract_gh_releases(body, source_url)
            return {"status": "ok" if items else "empty", "items": items,
                    "error": "", "structure_ok": body.lstrip()[:1] in (b"[", b"{")}
        elif mode == "arxiv_listing":
            items = _extract_arxiv_listing(body, source_url)
            return {"status": "ok" if items else "empty", "items": items,
                    "error": "", "structure_ok": b"<h3>" in body or bool(items)}
        elif mode == "sitemap":
            items = _extract_sitemap(body)
            return {"status": "ok" if items else "empty", "items": items, "error": ""}
        else:
            return {"status": "skipped", "items": [], "error": f"unknown mode {mode}"}
    except ValueError as e:
        return {"status": "parse_failed", "items": [], "error": str(e)}
    except Exception as e:  # 防御：解析器不能把整个采集流程带崩
        return {"status": "parse_failed", "items": [], "error": f"{type(e).__name__}: {e}"}

    # 0 条目时区分"源结构正常但没内容"与"内容不对劲"：
    #   前者（arXiv 周日返回合法但空的 RSS、发布稀疏的厂商 blog）不是失明；
    #   后者是空响应 / 结构被换掉，必须补检。
    structure_ok = bool(items) or _structure_matches(kind, mode, body)
    return {"status": "ok" if items else "empty", "items": items, "error": "",
            "structure_ok": structure_ok}


_MIN_DOC_BYTES = {"rss": 300, "atom": 300, "json": 50, "markdown": 50, "html": 800}


def _structure_matches(kind: str, mode: str, body: bytes) -> bool:
    """响应是否具备声明的结构（不看有没有条目）。"""
    expected = {"rss": ("rss", "atom"), "atom": ("atom",),
                "json_api": ("json",), "markdown_dated": ("markdown",),
                "markdown": ("markdown",), "html_cards": ("html",)}
    want = expected.get(mode)
    if want and kind not in want:
        return False
    return len(body or b"") >= _MIN_DOC_BYTES.get(kind, 50)


# 日期只到"日"时，源站时区不可知。全球时区范围 UTC-12 ~ UTC+14，
# 日期串 "D" 表示"某时区的 D 日"，其真实 UTC 跨度：
#   时区 +14 → UTC [D 00:00 -14h, D+1 00:00 -14h) = [D-1 10:00Z, D 10:00Z)
#   时区 -12 → UTC [D 00:00 +12h, D+1 00:00 +12h) = [D 12:00Z, D+1 12:00Z)
# 合并即 [D-1 10:00Z, D+1 12:00Z)，共 50 小时。
# 因此下界 = d - 14h，上界 = d + 36h（不是 +12h——那只有 26 小时，会漏掉西半球整天）。
_DAY_UNCERTAINTY_EARLY = timedelta(hours=14)
_DAY_UNCERTAINTY_LATE = timedelta(hours=36)


def _as_utc(value: str) -> datetime | None:
    try:
        d = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)


def precision_span(item: dict) -> tuple[datetime, datetime] | None:
    """
    条目可能的真实时刻区间。精度为 second 时退化为一个点（起止相同）。

    day 精度必须返回区间：把"Oct 21"当成 10-21T00:00Z 是把不确定性
    伪装成精确值，会让日粒度源的窗口边界事件被静默判到窗口外。
    """
    d = _as_utc(item.get("published") or "")
    if d is None:
        return None
    if item.get("date_precision") == "day":
        return d - _DAY_UNCERTAINTY_EARLY, d + _DAY_UNCERTAINTY_LATE
    return d, d


def window_match(item: dict, start_iso: str, end_iso: str) -> str | None:
    """
    返回 'exact' / 'fuzzy' / None。

    exact — 时刻精确到秒，且落在窗口内（确定事件）；
    fuzzy — 日期只到日，其 50 小时不确定区间与窗口相交（可能事件）。
            这类条目必须保留：宁可多带一条待核实的，也不能让日粒度源
            的窗口边界事件静默掉出候选池。下游不得把它当确定事件计数，
            8.2 引用时必须同时标注 date_precision。

    day 精度一律判 fuzzy，即使区间端点恰好落在窗口内——"Oct 22" 本身
    不是任何确定时刻，把它标成 exact 等于把时区猜测伪装成事实。
    """
    span = precision_span(item)
    s = _as_utc(start_iso)
    e = _as_utc(end_iso)
    if span is None or s is None or e is None:
        return None
    lo, hi = span
    if item.get("date_precision") == "day":
        return "fuzzy" if lo < e and hi > s else None
    return "exact" if s <= lo <= e else None


def in_window(item: dict, start_iso: str, end_iso: str) -> bool:
    """
    是否可归入窗口。日粒度条目按"不确定区间与窗口相交"判定（模糊精度），
    避免日粒度源因时刻被钉在零点而整批掉出窗口。
    无日期返回 False（不可归窗，交由上层标 time_unknown）。
    """
    return window_match(item, start_iso, end_iso) is not None


if __name__ == "__main__":
    # 自检：跑一段 markdown changelog
    demo = b"""# Changelog

## October, 2026

### Oct 22

Update - Model: gpt-6-luna - API: v1/decisions

The Decisions API is now generally available.

### Oct 15

Feature - gpt-live-1
"""
    print(json.dumps(extract_items(demo, "markdown_dated", "https://x/docs/changelog.md"),
                     ensure_ascii=False, indent=2))
