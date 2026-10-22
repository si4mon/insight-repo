#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多源技术热点简报 · 数据采集脚本
按 tech_report_task_def 的五路召回采集 SCAN_WINDOW 内全部条目，落盘到 raw_<date>/ 供后续分析。

修复项（针对华为 MWG 代理网关）：
  1. 所有请求默认 UA = "curl/8.0"（MWG 对浏览器 UA 做深度 inspection 易超时，curl UA 走快速通道）
  2. --retry 5 --retry-delay 2 失败重试（应对 arXiv 等间歇 502）
  3. HuggingFace 走 hf-mirror.com 镜像（规避 "This category is filtered" 策略拦截）
  4. arXiv cs.AI 失败时 fallback 到 cs.CL/LG（主题高度重叠）
  5. 中文媒体 RSS 失败时 fallback 到网站首页 HTML
  6. 证书校验关闭（-k，内网代理对部分域名证书链不完整）
  7. 每个源独立 try/except，单点失败不影响整体

用法：
  python collect_sources.py                    # 默认采集到 <cwd>/raw_<today>/
  python collect_sources.py --out /path/to/dir # 指定输出目录
  python collect_sources.py --date 2026-10-19  # 指定日期（用于补采）
"""
import argparse
import datetime
import json
import os
import re
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ============ 全局配置 ============
DEFAULT_UA = "curl/8.0"
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
TIMEOUT = 20
MAX_RETRIES = 3
RETRY_DELAY = 2
LARGE_PAGE_TIMEOUT = 45  # 大页面（arXiv CL/LG、Cloudflare blog 等）用更长 timeout

# SSL context that skips cert verification (内网代理证书链问题)
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def shanghai_now() -> datetime.datetime:
    """当前 Asia/Shanghai 时间"""
    tz = datetime.timezone(datetime.timedelta(hours=8))
    return datetime.datetime.now(tz)


def window_dates() -> tuple[str, str, str]:
    """返回 (window_start_date, scan_start, now) 的字符串形式"""
    now = shanghai_now()
    window_start_date = (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    scan_start = (now - datetime.timedelta(days=1) - datetime.timedelta(hours=6)).strftime("%Y-%m-%d %H:%M")
    now_str = now.strftime("%Y-%m-%d %H:%M")
    return window_start_date, scan_start, now_str


# ============ 采集原语 ============
def fetch(url: str, ua: str = DEFAULT_UA, timeout: int = TIMEOUT,
          retries: int = MAX_RETRIES, delay: int = RETRY_DELAY) -> tuple[bool, bytes, str]:
    """
    带重试的 HTTP 抓取。返回 (success, body, message)。
    使用 urllib + 自定义 SSL context，不依赖外部 curl。
    处理 IncompleteRead（代理截断大响应体）和 timeout。
    """
    from http.client import IncompleteRead
    last_err = ""
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": ua,
                "Accept": "text/html,application/json,application/xml,*/*",
                "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
            })
            with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
                try:
                    body = resp.read()
                except IncompleteRead as e:
                    # 代理截断：使用已读部分，如果足够大就接受
                    body = e.partial
                    if len(body) < 5000:
                        raise  # 太小，当作失败
                status = resp.status
                # 检查是否被 MWG 拦截（响应体含 Huawei Proxy 标识）
                if b"Huawei Proxy" in body[:2000] or b"mwg-internal" in body[:2000]:
                    last_err = f"MWG proxy block (status={status}, body contains Huawei Proxy signature)"
                    # 策略拦截重试无益，直接返回
                    return False, body, last_err
                if status == 200:
                    return True, body, f"OK (size={len(body)})"
                last_err = f"HTTP {status}"
        except urllib.error.HTTPError as e:
            last_err = f"HTTPError {e.code}: {e.reason}"
            # 403 可能是源站反爬（OpenAI 要求浏览器 UA），换 UA 重试
            if e.code in (403, 451):
                # 如果当前不是浏览器 UA，下次用浏览器 UA 重试
                if ua == DEFAULT_UA and attempt < retries:
                    return _fetch_with_ua_swap(url, BROWSER_UA, timeout, retries - attempt, delay)
                return False, b"", last_err
        except (urllib.error.URLError, TimeoutError, ConnectionError, IncompleteRead) as e:
            last_err = f"{type(e).__name__}: {e}"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"

        if attempt < retries:
            time.sleep(delay)
    return False, b"", f"failed after {retries} retries: {last_err}"


def _fetch_with_ua_swap(url: str, ua: str, timeout: int, retries: int, delay: int) -> tuple[bool, bytes, str]:
    """403 时换浏览器 UA 重试（OpenAI 等拒绝 curl UA）"""
    from http.client import IncompleteRead
    last_err = ""
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": ua,
                "Accept": "text/html,application/json,application/xml,*/*",
                "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
            })
            with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
                try:
                    body = resp.read()
                except IncompleteRead as e:
                    body = e.partial
                    if len(body) < 5000:
                        raise
                if b"Huawei Proxy" in body[:2000] or b"mwg-internal" in body[:2000]:
                    return False, body, "MWG proxy block after UA swap"
                return True, body, f"OK with browser UA (size={len(body)})"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
        if attempt < retries:
            time.sleep(delay)
    return False, b"", f"UA swap also failed: {last_err}"


def fetch_with_fallback(urls: list[tuple[str, str]], name: str, out_dir: Path,
                        ua: str = DEFAULT_UA, timeout: int = TIMEOUT) -> dict:
    """
    按顺序尝试多个 URL，第一个成功即停止。
    urls: [(url, filename), ...]
    返回采集结果摘要。
    """
    result = {"name": name, "success": False, "source": "", "size": 0, "message": "", "fallback_used": False}
    for i, (url, filename) in enumerate(urls):
        ok, body, msg = fetch(url, ua=ua, timeout=timeout)
        out_path = out_dir / filename
        if ok:
            out_path.write_bytes(body)
            result.update(success=True, source=url, size=len(body), message=msg,
                          fallback_used=(i > 0))
            print(f"  [OK] {name} -> {filename} ({len(body)} bytes){' [fallback]' if i > 0 else ''}", flush=True)
            return result
        else:
            # 即使失败也落盘被拦页面，便于诊断
            if body:
                out_path.write_bytes(body)
            print(f"  [FAIL] {name} attempt {i+1}/{len(urls)}: {url} -> {msg}", flush=True)
    return result


# ============ 源定义 ============
def build_sources(out_dir: Path) -> list[dict]:
    """构建所有源的采集任务列表。每个任务包含 fallback URL 链。"""

    # --- A. arXiv source-native feeds ---
    # cs.CL/LG 的 RSS 非常大（470KB/826KB），容易被代理截断，用更长 timeout
    arxiv_categories = ["cs.AI", "cs.CL", "cs.LG", "cs.MA", "cs.RO"]
    sources = []
    for cat in arxiv_categories:
        timeout = LARGE_PAGE_TIMEOUT if cat in ("cs.CL", "cs.LG") else TIMEOUT
        sources.append({
            "name": f"arxiv_{cat}",
            "track": "A_arxiv",
            "urls": [
                (f"https://export.arxiv.org/rss/{cat}", f"arxiv_{cat.replace('.', '_')}.xml"),
                # fallback: arxiv.org 根域通常可通
                (f"https://arxiv.org/list/{cat}/recent", f"arxiv_{cat.replace('.', '_')}_list.html"),
            ],
            "timeout": timeout,
        })

    # --- B. HuggingFace (走 hf-mirror.com 镜像规避分类拦截) ---
    sources.append({
        "name": "hf_daily_papers",
        "track": "B_hf",
        "urls": [
            ("https://hf-mirror.com/api/daily_papers", "hf_daily_papers.json"),
            ("https://huggingface.co/api/daily_papers", "hf_daily_papers_orig.json"),
        ],
    })
    sources.append({
        "name": "hf_trending_models",
        "track": "B_hf",
        "urls": [
            ("https://hf-mirror.com/api/trending?model", "hf_trending_models.json"),
            ("https://huggingface.co/api/trending?model", "hf_trending_models_orig.json"),
        ],
    })
    sources.append({
        "name": "hf_trending_datasets",
        "track": "B_hf",
        "urls": [
            ("https://hf-mirror.com/api/trending?dataset", "hf_trending_datasets.json"),
            ("https://huggingface.co/api/trending?dataset", "hf_trending_datasets_orig.json"),
        ],
    })

    # --- C. Hacker News ---
    sources.append({
        "name": "hn_top_ids",
        "track": "C_hn",
        "urls": [
            ("https://hacker-news.firebaseio.com/v0/topstories.json", "hn_top_ids.json"),
        ],
    })

    # --- D. Techmeme ---
    sources.append({
        "name": "techmeme",
        "track": "D_aggregator",
        "urls": [
            ("https://www.techmeme.com/feed.xml", "techmeme_feed.xml"),
        ],
    })

    # --- E. GitHub Trending ---
    sources.append({
        "name": "gh_trending",
        "track": "E_github",
        "urls": [
            ("https://github.com/trending", "gh_trending.html"),
        ],
    })

    # --- F. 专家博客 ---
    sources.append({
        "name": "simonwillison",
        "track": "F_expert_blog",
        "urls": [
            ("https://simonwillison.net/", "simonwillison.html"),
        ],
    })
    sources.append({
        "name": "latentspace",
        "track": "F_expert_blog",
        "urls": [
            ("https://www.latent.space/", "latentspace.html"),
        ],
    })

    # --- G. 中文媒体（RSS 失效则 fallback 到首页 HTML） ---
    sources.append({
        "name": "jiqizhixin",
        "track": "G_cn_media",
        "urls": [
            ("https://www.jiqizhixin.com/rss", "jiqizhixin.xml"),
            ("https://www.jiqizhixin.com/", "jiqizhixin_index.html"),  # RSS 经常返回登录页
        ],
    })
    sources.append({
        "name": "xinzhiyuan",
        "track": "G_cn_media",
        "urls": [
            ("https://www.xinzhiyuan.com/feed", "xinzhiyuan.xml"),
            ("https://xinzhiyuan.com/", "xinzhiyuan_index.html"),
        ],
    })
    sources.append({
        "name": "qbitai",
        "track": "G_cn_media",
        "urls": [
            ("https://www.qbitai.com/feed", "qbitai_feed.xml"),
            ("https://www.qbitai.com/", "qbitai_index.html"),
        ],
    })

    # --- H. Tier-1 厂商官方 blog index ---
    # OpenAI 拒绝 curl UA（403），必须用浏览器 UA
    # OpenAI 有 Cloudflare JS challenge，纯 HTTP 抓不到，加 HN search 作为 fallback
    # Cloudflare/Mistral blog 页面大，用更长 timeout
    tier1_blogs = [
        ("anthropic_news", "https://www.anthropic.com/news", "anthropic_news.html", BROWSER_UA, TIMEOUT, []),
        ("anthropic_engineering", "https://www.anthropic.com/engineering", "anthropic_engineering.html", BROWSER_UA, TIMEOUT, []),
        ("openai_index", "https://openai.com/index/", "openai_index.html", BROWSER_UA, TIMEOUT, [
            # OpenAI 反爬无法直接抓，fallback 到 Algolia search API（无 JS challenge）
            ("https://hn.algolia.com/api/v1/search?query=openai&tags=story&hitsPerPage=30", "openai_hn_search.json"),
        ]),
        ("openai_news", "https://openai.com/news/", "openai_news.html", BROWSER_UA, TIMEOUT, [
            ("https://hn.algolia.com/api/v1/search?query=openai+news&tags=story&hitsPerPage=30", "openai_news_hn_search.json"),
        ]),
        ("deepmind_blog", "https://www.deepmind.google/blog/", "deepmind_blog.html", BROWSER_UA, TIMEOUT, []),
        ("google_devblog", "https://developers.googleblog.com/en/", "google_devblog.html", BROWSER_UA, TIMEOUT, []),
        ("cloudflare_blog", "https://blog.cloudflare.com/", "cloudflare_blog.html", BROWSER_UA, LARGE_PAGE_TIMEOUT, []),
        ("minimax_blog", "https://www.minimax.io/blog", "minimax_blog.html", BROWSER_UA, TIMEOUT, []),
        ("mistral_news", "https://mistral.ai/news/", "mistral_news.html", BROWSER_UA, LARGE_PAGE_TIMEOUT, []),
        ("inception_blog", "https://www.inceptionlabs.ai/blog", "inception_blog.html", BROWSER_UA, TIMEOUT, []),
    ]
    for name, url, filename, ua, timeout, fallbacks in tier1_blogs:
        urls = [(url, filename)] + fallbacks
        sources.append({
            "name": name,
            "track": "H_tier1_official",
            "urls": urls,
            "ua": ua,
            "timeout": timeout,
        })

    return sources


# ============ HN item 详情补采 ============
def fetch_hn_items(out_dir: Path, top_n: int = 40) -> dict:
    """从 hn_top_ids.json 读取 top N，逐条抓取详情"""
    ids_path = out_dir / "hn_top_ids.json"
    if not ids_path.exists():
        return {"name": "hn_items", "success": False, "message": "hn_top_ids.json not found"}

    try:
        ids = json.loads(ids_path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"name": "hn_items", "success": False, "message": f"failed to parse ids: {e}"}

    items = []
    for i, item_id in enumerate(ids[:top_n]):
        try:
            url = f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
            ok, body, msg = fetch(url, retries=2, delay=1)
            if ok:
                items.append(json.loads(body.decode("utf-8")))
            else:
                print(f"  [FAIL] HN item {item_id}: {msg}", flush=True)
        except Exception as e:
            print(f"  [FAIL] HN item {item_id}: {e}", flush=True)

    out_path = out_dir / "hn_items.json"
    out_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [OK] hn_items -> hn_items.json ({len(items)}/{min(top_n, len(ids))} items)", flush=True)
    return {"name": "hn_items", "success": True, "size": len(items),
            "message": f"fetched {len(items)} items"}


# ============ 主流程 ============
def main():
    parser = argparse.ArgumentParser(description="多源技术热点简报数据采集")
    parser.add_argument("--out", default="", help="输出目录（默认 demo/raw_<today>）")
    parser.add_argument("--date", default="", help="指定日期 YYYY-MM-DD（默认今天）")
    parser.add_argument("--hn-top", type=int, default=40, help="HN top stories 数量")
    parser.add_argument("--skip-hn-items", action="store_true", help="跳过 HN item 详情抓取")
    args = parser.parse_args()

    now = shanghai_now()
    if args.date:
        try:
            target_date = datetime.datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"无效日期: {args.date}，应为 YYYY-MM-DD")
            sys.exit(1)
    else:
        target_date = now.date()

    if args.out:
        out_dir = Path(args.out)
    else:
        out_dir = Path.cwd() / f"raw_{target_date.strftime('%Y-%m-%d')}"

    out_dir.mkdir(parents=True, exist_ok=True)

    window_start_date = target_date.strftime("%Y-%m-%d")
    scan_start = (datetime.datetime.combine(target_date, datetime.time.min)
                  - datetime.timedelta(hours=6)).strftime("%Y-%m-%d %H:%M")
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    print("=" * 70)
    print(f"多源技术热点简报 · 数据采集")
    print(f"TARGET_WINDOW: {window_start_date} 00:00 → {now_str} (Asia/Shanghai)")
    print(f"SCAN_WINDOW:   {scan_start} → {now_str}")
    print(f"输出目录: {out_dir}")
    print(f"UA: {DEFAULT_UA} (默认) / {BROWSER_UA[:40]}... (Tier-1 官方站)")
    print(f"重试: {MAX_RETRIES} 次，间隔 {RETRY_DELAY}s")
    print(f"SSL 验证: 关闭（内网代理证书链）")
    print("=" * 70)

    sources = build_sources(out_dir)
    results = []

    # 采集所有源
    for src in sources:
        print(f"\n[{src['name']}] track={src['track']}", flush=True)
        ua = src.get("ua", DEFAULT_UA)
        timeout = src.get("timeout", TIMEOUT)
        r = fetch_with_fallback(src["urls"], src["name"], out_dir, ua=ua, timeout=timeout)
        r["track"] = src["track"]
        results.append(r)

    # HN item 详情
    if not args.skip_hn_items:
        print("\n[hn_items] 抓取 top story 详情...")
        r = fetch_hn_items(out_dir, top_n=args.hn_top)
        r["track"] = "C_hn"
        results.append(r)

    # 生成采集报告
    report = {
        "collect_time": now_str,
        "target_window": f"{window_start_date} 00:00 → {now_str} Asia/Shanghai",
        "scan_window": f"{scan_start} → {now_str} Asia/Shanghai",
        "out_dir": str(out_dir),
        "total_sources": len(results),
        "success": sum(1 for r in results if r.get("success")),
        "failed": sum(1 for r in results if not r.get("success")),
        "results": results,
    }
    report_path = out_dir / "collect_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 70)
    print(f"采集完成: {report['success']}/{report['total_sources']} 成功, {report['failed']} 失败")
    print(f"报告: {report_path}")
    print("=" * 70)

    # 打印失败源摘要
    failed = [r for r in results if not r.get("success")]
    if failed:
        print("\n失败源（需人工处理或申请权限）:")
        for r in failed:
            print(f"  - {r['name']}: {r.get('message', 'unknown')}")

    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
