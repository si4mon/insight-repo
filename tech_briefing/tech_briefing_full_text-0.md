assets/build_pool.py
----------------------------------------
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P1 候选池构建：把 items_<source>.json 合并、去重、归窗，产出 candidate_pool.json。

为什么要有这个脚本：候选人池构建原本写在 SKILL.md 里由 LLM 手工完成，
结果出现了三类静默丢失，每一类都让报告"看起来正常但事件变少"：

  1. **无日期源被整源丢弃**。HF Trending / GitHub Trending / Google Dev Blog
     的条目没有 published 字段，`if not published: continue` 把它们全扔了。
     而这类源恰恰承载"模型热度、新仓库、官方新工具"这类事件 ——
     v0 报告有 6 个事件的素材来自这里，新版一个都没有。
  2. **窗口外条目被丢弃而未留痕**。8.3 的丢弃日志需要"为什么没进正文"，
     但池里连条目都没有，就永远写不出理由。
  3. **dedup 只按 uid**。同一事件在不同源的 uid 不同，会重复进入池子，
     下游要靠 points 排序时又会把低分的那份当成噪声。

因此本脚本：
  - 无日期条目**保留**，标 window_match=no_date + 走 snapshot 差分判断新旧；
  - 窗口外条目**保留在池外文件** pool_out_of_window.json，供 8.3 引证；
  - 同源去重按 uid，跨源不合并（合并是 P2 的语义工作，不该在 P1 做）。

用法：
  python build_pool.py --raw-dir raw_2026-10-26
  python build_pool.py --raw-dir raw_2026-10-26 --out raw_2026-10-26/candidate_pool.json
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from extract import window_match  # noqa: E402

SH_TZ = timezone(__import__("datetime").timedelta(hours=8))


def load_report(raw_dir: Path) -> dict:
    p = raw_dir / "collect_report.json"
    if not p.exists():
        raise SystemExit(f"缺少 {p}，先跑 collect_sources.py")
    return json.loads(p.read_text(encoding="utf-8"))


def build(raw_dir: Path) -> tuple[list, list]:
    rep = load_report(raw_dir)
    ws = rep["target_window"]["start"]
    we = rep["target_window"]["end"]
    meta = {s["id"]: s for s in rep["sources"]}
    diff = rep.get("diff") or {}

    in_pool, out_pool = [], []
    seen = set()

    for f in sorted(raw_dir.glob("items_*.json")):
        sid = f.stem[len("items_"):]
        m = meta.get(sid, {})
        try:
            items = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for it in items:
            uid = it.get("uid") or ""
            dedup_key = (sid, uid)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            row = {
                **it,
                "src": sid,
                "entity": m.get("entity"),
                "surface": m.get("surface"),
                "channel": m.get("channel"),
            }
            # sitemap 只产出 URL，没有标题与摘要，无法判断语义 —— 它的用途是
    # surface diff（"有没有新页面"），不是候选事件。放进候选池只会淹没真实条目。
            if m.get("mode") == "sitemap" or not (it.get("title") or "").strip():
                row["window_match"] = "no_title"
                out_pool.append(row)
                continue

            if not it.get("published"):
                # 无日期：不丢弃，但必须用快照差分回答"它是不是本轮才出现的"。
                # 定时任务每天跑，Trending 榜单里的条目会连续多天在场；
                # 不加这一步，同一批模型/仓库每天都会被当成新事件重复入选。
                row["window_match"] = "no_date"
                row["in_window"] = None
                d = diff.get(sid) or {}
                new_uids = set(d.get("new_uids") or [])
                is_first = bool(d.get("is_first_run"))
                if is_first:
                    # 首次运行没有基线，无法判断新旧 —— 不能声称是"本轮新增"
                    row["freshness"] = "baseline_unknown"
                elif uid in new_uids:
                    row["freshness"] = "new_since_last_run"
                else:
                    row["freshness"] = "carried_over"
                in_pool.append(row)
                continue

            wm = window_match(it, ws, we)
            if wm:
                row["window_match"] = wm
                row["in_window"] = True
                in_pool.append(row)
            else:
                row["window_match"] = None
                row["in_window"] = False
                out_pool.append(row)

    # 排序：有时间的按时间倒序，无日期的排在后面（它们没有"新近度"可比）
    in_pool.sort(key=lambda x: (x.get("published") or "", x.get("src", "")),
                 reverse=True)
    out_pool.sort(key=lambda x: (x.get("published") or ""), reverse=True)
    return in_pool, out_pool


def main() -> int:
    ap = argparse.ArgumentParser(description="P1 候选池构建")
    ap.add_argument("--raw-dir", required=True)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    raw_dir = Path(args.raw_dir)
    in_pool, out_pool = build(raw_dir)
    out_path = Path(args.out) if args.out else raw_dir / "candidate_pool.json"
    out_path.write_text(json.dumps(in_pool, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    (raw_dir / "pool_out_of_window.json").write_text(
        json.dumps(out_pool, ensure_ascii=False, indent=1), encoding="utf-8")

    from collections import Counter
    print(f"候选池: {len(in_pool)} 条 -> {out_path}")
    print(f"  窗口外（留证）: {len(out_pool)} 条")
    print(f"  window_match: {dict(Counter(x['window_match'] for x in in_pool))}")
    print(f"  通道: {dict(Counter(x.get('channel') for x in in_pool))}")
    nodate = [x for x in in_pool if x["window_match"] == "no_date"]
    if nodate:
        from collections import Counter as _C
        fresh = _C(x.get("freshness") for x in nodate)
        print(f"  无日期条目 {len(nodate)} 条，来自: "
              f"{sorted({x['src'] for x in nodate})}")
        print(f"    新旧判定: {dict(fresh)}")
        print("    只有 freshness=new_since_last_run 的才能作为本轮新事件；"
              "carried_over 只能进第 5 章持续信号")
    return 0


if __name__ == "__main__":
    sys.exit(main())

assets/collect_sources.py
----------------------------------------
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多源技术热点简报 · 采集 + 提取 + 对账

与旧版的根本差别（这是机制修复，不是补三个源）：
  旧版：抓字节 → 落盘 → 记 success(bool)。于是"抓到代理拦截页"、"抓到 HTML 但
        解析不出条目"、"抓到但窗口内无条目"三种失败全部显示为成功，
        简报无法知道自己漏了什么。
  新版：抓字节 → 分类形态 → 按声明模式提取 → 与窗口/snapshot 对账 →
        产出三级状态 + 覆盖缺口 + 差分。失败是可见的、可驱动的。

三级状态（任一级失败都不会被下一级掩盖）：
  transport  ok | http_error | timeout | url_error
  extract    ok | empty | parse_failed | skipped | blocked
  window     OK_IN_WINDOW | OK_OUT_OF_WINDOW | OK_NO_DATES

网络：
  - 显式读取 Windows 注册表代理。Python 的 urllib.getproxies() 是 env-or-registry，
    本机 env 里存在 no_proxy 却无 http_proxy 时，env 字典非空 → registry 被忽略 →
    全部直连超时。这是旧版在某些环境"全源失败"的隐藏原因。
  - 代理拦截页按 HIS Proxy / Huawei Proxy / mwg-internal / 访问外部AI大模型 识别。

用法：
  python collect_sources.py                       # 采集到 ./raw_<today>/
  python collect_sources.py --out raw_2026-10-23
  python collect_sources.py --date 2026-10-22     # 补采
  python collect_sources.py --no-snapshot         # 不读写 ./snapshots/
  python collect_sources.py --only openai_api_changelog,anthropic_blog
  python collect_sources.py --no-proxy            # 强制直连（排查用）
"""
import argparse
import concurrent.futures
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import coverage
import extract
import sources as src_reg

SH_TZ = datetime.timezone(datetime.timedelta(hours=8))
MAX_RETRIES = 3
RETRY_DELAY = 2


# ============ 代理 ============
def resolve_proxies(force_direct: bool = False) -> tuple[dict, str]:
    """
    显式解析代理，修 env-or-registry 的坑。
    优先级：显式 env（HTTP_PROXY/HTTPS_PROXY）> Windows 注册表 > 直连。
    """
    if force_direct:
        return {}, "forced-direct"

    env_http = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    env_https = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if env_http or env_https:
        p = {}
        if env_http:
            p["http"] = env_http
        if env_https:
            p["https"] = env_https
        return p, "env"

    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
            enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
            if enabled:
                server, _ = winreg.QueryValueEx(key, "ProxyServer")
                if server:
                    if "=" in server:  # per-protocol 形式
                        p = {}
                        for part in server.split(";"):
                            if "=" in part:
                                proto, addr = part.split("=", 1)
                                p[proto.strip().lower()] = addr.strip()
                        if p:
                            return p, "registry(per-protocol)"
                    return {"http": server, "https": server}, "registry"
        except Exception:
            pass
    return {}, "direct"


def build_opener(proxies: dict):
    """按代理配置构造 opener。直连时显式置空，避免 urllib 自动读取环境。"""
    import ssl
    handlers = [urllib.request.ProxyHandler(proxies or {})]
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    handlers.append(urllib.request.HTTPSHandler(context=ctx))
    return urllib.request.build_opener(*handlers)


# ============ 抓取 ============
def fetch(opener, url: str, ua: str, timeout: int,
          retries: int = MAX_RETRIES, delay: int = RETRY_DELAY) -> tuple[str, bytes, str]:
    """
    返回 (transport_status, body, error)。
    transport_status: ok | http_error | timeout | url_error
    不在传输层判代理拦截页 —— 交给 extract.classify，保持职责分离。
    """
    last = ""
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": ua,
                "Accept": "text/html,application/json,application/xml,text/plain,*/*",
                "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
            })
            with opener.open(req, timeout=timeout) as resp:
                body = resp.read()
                if body:
                    return "ok", body, ""
                last = "empty body"
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code in (403, 451) and ua != src_reg.BROWSER_UA:
                ua = src_reg.BROWSER_UA
                time.sleep(1)
                continue
            if e.code in (404, 410):
                return "http_error", b"", last
        except (TimeoutError, urllib.error.URLError) as e:
            last = f"{type(e).__name__}: {e}"
            if attempt == retries and ("timed out" in str(e).lower()
                                       or isinstance(e, TimeoutError)):
                return "timeout", b"", last
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
        if attempt < retries:
            time.sleep(delay)
    return "timeout" if "timed out" in last.lower() else "url_error", b"", last


def collect_paginated(opener, src: dict, out_dir: Path, window_start: str,
                      window_end: str) -> tuple[list[dict], dict]:
    """
    分页采集，直到最早条目早于 window_start 或达到 max_pages。
    返回 (合并后的条目, 分页元信息)。

    存在的意义：单页 API（HN Algolia 100 条 ≈ 4 小时）不足以覆盖 30 小时窗口。
    如果不翻页，源会显示"OK_IN_WINDOW"，但只覆盖了窗口的一小段 —— 静默截断。
    """
    pg = src["paginate"]
    all_items = []
    seen = set()
    cover = {"requests": 0, "slices": 0, "hits_per_slice": [],
             "reached_window_start": False, "oldest_seen": "",
             "truncated": False, "errors": []}

    # 时间切片：把窗口切成 slice_hours 的片，逐片查询。
    # 必要性：Algolia 单查询最多返回 1000 条，30 小时窗口内实有 2000+ 条，
    # 不切片就会静默丢掉一半。切片后每片都远低于上限，可完整取回。
    slice_hours = pg.get("slice_hours", 0)
    slices = []
    if slice_hours:
        try:
            ws_dt = datetime.datetime.fromisoformat(window_start)
            we_dt = datetime.datetime.fromisoformat(window_end)
            step = datetime.timedelta(hours=slice_hours)
            cur = ws_dt
            while cur < we_dt:
                nxt = min(cur + step, we_dt)
                slices.append((cur, nxt))
                cur = nxt
        except ValueError:
            slices = []

    # 非切片模式下把整个窗口当作一片，保持统一处理
    if not slices:
        try:
            slices = [(datetime.datetime.fromisoformat(window_start),
                       datetime.datetime.fromisoformat(window_end))]
            sliced = False
        except ValueError:
            slices = []
            sliced = False
    else:
        sliced = True

    for (s_dt, e_dt) in slices:
        start_ts, end_ts = int(s_dt.timestamp()), int(e_dt.timestamp())
        slice_total = 0
        prev_last_key = None

        for page in range(pg.get("max_pages", 1)):
            url = pg["url_template"].format(
                page=page,
                per_page=pg.get("per_page", 100),
                start_ts=start_ts, end_ts=end_ts)
            t_status, body, err = fetch(opener, url,
                                        src.get("ua", src_reg.DEFAULT_UA),
                                        src.get("timeout", 20))
            cover["requests"] += 1
            if t_status != "ok":
                cover["truncated"] = True
                cover["errors"].append(f"slice {start_ts}: {t_status} {err[:100]}")
                break

            fname = pg["filename_template"].format(
                start_ts=start_ts, page=page)
            (out_dir / fname).write_bytes(body)

            res = extract.extract_items(body, src["mode"], source_url=url,
                                        json_mode=src.get("json_mode", ""))
            if res["status"] not in ("ok", "empty"):
                cover["truncated"] = True
                cover["errors"].append(
                    f"slice {start_ts}: {res['status']} {res['error'][:100]}")
                break

            page_items = res["items"]
            if not page_items:
                break   # 该片已取完

            # Algolia 分页在某些情况下会重复返回同一页，检测并终止避免死循环
            last_key = (page_items[-1].get("published"), page_items[-1].get("uid"))
            if last_key == prev_last_key:
                cover["truncated"] = True
                cover["errors"].append(f"slice {start_ts}: pagination stalled")
                break
            prev_last_key = last_key

            for it in page_items:
                if it["uid"] not in seen:
                    seen.add(it["uid"])
                    all_items.append(it)
            slice_total += len(page_items)

            # 该页不足 per_page，说明这片取完了
            if len(page_items) < pg.get("per_page", 100):
                break
        else:
            # 跑到 max_pages 仍未取完 → 该片被截断
            if slice_total >= pg.get("per_page", 100) * pg.get("max_pages", 1):
                cover["truncated"] = True

        cover["slices"] += 1
        cover["hits_per_slice"].append(slice_total)

    dated = [i for i in all_items if i.get("published")]
    if dated:
        parsed = []
        for i in dated:
            try:
                parsed.append(datetime.datetime.fromisoformat(i["published"]))
            except ValueError:
                continue
        if parsed:
            cover["oldest_seen"] = min(parsed).isoformat()

    # 切片模式下，只要所有片都成功，就认为窗口被完整覆盖
    cover["reached_window_start"] = sliced and not cover["truncated"] and not cover["errors"]

    # 合并文件写盘，供后续分析
    (out_dir / f"items_{src['id']}.json").write_text(
        json.dumps(all_items, ensure_ascii=False, indent=2), encoding="utf-8")

    return all_items, cover


def collect_one(opener, src: dict, out_dir: Path, window_start: str,
                window_end: str) -> dict:
    """
    采集单个源，返回含三级状态的记录。
    按 urls 顺序 fallback：第一个 transport=ok 且 extract 不是 blocked/parse_failed 的即采用。
    """
    rec = {
        "id": src["id"], "entity": src["entity"], "surface": src["surface"],
        "layer": src["layer"], "channel": src["channel"],
        "mode": src["mode"], "critical": src.get("critical", False),
        "transport": "", "extract": "", "verdict": "",
        "bytes": 0, "content_kind": "",
        "url": "", "file": "",
        "items_total": 0, "items_with_date": 0, "items_in_window": 0,
        "items_in_window_exact": 0, "items_in_window_fuzzy": 0,
        "earliest": "", "latest": "",
        "extract_error": "", "note": "", "attempts": [],
    }

    # 分页源单独处理（覆盖度由翻页深度保证，而不是单页条数）
    if src.get("paginate"):
        items, cover = collect_paginated(opener, src, out_dir,
                                         window_start, window_end)
        rec.update(transport="ok", extract="ok" if items else "empty",
                   url=src["paginate"]["url_template"],
                   content_kind="json", bytes=0,
                   items_total=len(items),
                   items_with_date=sum(1 for i in items if i.get("published")),
                   items_in_window=sum(1 for i in items
                                       if i.get("published")
                                       and extract.in_window(i, window_start, window_end)),
                   items_in_window_exact=sum(
                       1 for i in items
                       if i.get("published")
                       and extract.window_match(i, window_start, window_end) == "exact"),
                   items_in_window_fuzzy=sum(
                       1 for i in items
                       if i.get("published")
                       and extract.window_match(i, window_start, window_end) == "fuzzy"),
                   pagination=cover)
        dated = [i for i in items if i.get("published")]
        if dated:
            rec["earliest"] = min(i["published"] for i in dated)
            rec["latest"] = max(i["published"] for i in dated)
        if cover.get("truncated"):
            rec["note"] = (f"分页未覆盖到窗口起点：pages={cover['pages_fetched']} "
                           f"oldest={cover['oldest_seen'][:19]}，窗口内容可能不完整")
        rec["verdict"] = coverage.source_verdict(rec)
        return rec

    chosen = None
    for url, filename in src["urls"]:
        t_status, body, err = fetch(opener, url, src.get("ua", src_reg.DEFAULT_UA),
                                    src.get("timeout", 20))
        rec["attempts"].append({"url": url, "transport": t_status, "error": err[:200]})

        if t_status != "ok":
            rec.update(transport=t_status, url=url, extract_error=err[:200])
            continue

        kind = extract.classify(body, url)
        res = extract.extract_items(body, src["mode"], source_url=url,
                                    json_mode=src.get("json_mode", ""))
        rec.update(transport="ok", url=url, bytes=len(body), content_kind=kind)

        # 一定落盘：失败也要留证据，便于事后审计与人工回溯
        path = out_dir / filename
        path.write_bytes(body)
        rec["file"] = filename

        if res["status"] == "blocked":
            rec.update(extract="blocked", extract_error=res["error"],
                       note="代理拦截页（HIS/Huawei Proxy），内容不可用")
            continue  # 试下一个 fallback

        if res["status"] == "parse_failed":
            rec.update(extract="parse_failed", extract_error=res["error"])
            continue

        chosen = (url, res)
        break

    if chosen is None:
        if rec["transport"] != "ok":
            rec["extract"] = rec["extract"] or "skipped"
        rec["verdict"] = coverage.source_verdict(rec)
        return rec

    url, res = chosen
    items = res["items"]
    rec["extract"] = res["status"]
    # 结构正常但 0 条 ≠ 失明。区分依据由 extract 给出（见 _structure_matches）。
    rec["structure_ok"] = bool(res.get("structure_ok"))
    rec["daily_batch"] = bool(src.get("daily_batch"))

    dated = [i for i in items if i.get("published")]
    if src.get("daily_batch"):
        # 整批发布源：记录实际收到的批次日期，供 coverage 按"发布日"判定
        rec["batch_dates"] = sorted({(i["published"] or "")[:10] for i in dated
                                     if i.get("published")}, reverse=True)
    # 窗口内条目分两档：determinate（精确时刻在窗口内，可直接引用）
    # 与 fuzzy（仅日粒度、不确定区间与窗口相交，需人工确认）。
    # 旧实现把两者混成一个数字，导致日粒度源要么整批掉出（时刻被钉在零点），
    # 要么被当成确定事件使用（时区猜测伪装成事实）。
    matches = {id(i): extract.window_match(i, window_start, window_end) for i in dated}
    in_win = [i for i in dated if matches[id(i)]]
    rec["items_total"] = len(items)
    rec["items_with_date"] = len(dated)
    rec["items_in_window"] = len(in_win)
    rec["items_in_window_exact"] = sum(1 for i in in_win if matches[id(i)] == "exact")
    rec["items_in_window_fuzzy"] = sum(1 for i in in_win if matches[id(i)] == "fuzzy")
    if dated:
        rec["earliest"] = min(i["published"] for i in dated)
        rec["latest"] = max(i["published"] for i in dated)

    # 条目明细落盘，供 P1 候选池构建与人工复核
    if items:
        (out_dir / f"items_{src['id']}.json").write_text(
            json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    rec["verdict"] = coverage.source_verdict(rec)
    return rec


# ============ 主流程 ============
def main() -> int:
    ap = argparse.ArgumentParser(description="多源技术热点简报 · 采集/提取/对账")
    ap.add_argument("--out", default="", help="输出目录，默认 ./raw_<date>")
    ap.add_argument("--date", default="", help="采集日期 YYYY-MM-DD（默认今天）")
    ap.add_argument("--only", default="", help="只跑指定 source id（逗号分隔）")
    ap.add_argument("--no-snapshot", action="store_true", help="不读写 snapshots/")
    ap.add_argument("--no-proxy", action="store_true", help="强制直连（排查用）")
    ap.add_argument("--workers", type=int, default=6, help="并发数")
    ap.add_argument("--fail-on-gate", action="store_true",
                    help="覆盖 gate 失败时返回非零退出码（CI 用）")
    args = ap.parse_args()

    now = datetime.datetime.now(SH_TZ)
    if args.date:
        try:
            target_date = datetime.datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"无效日期: {args.date}")
            return 2
    else:
        target_date = now.date()

    out_dir = Path(args.out) if args.out else Path.cwd() / f"raw_{target_date:%Y-%m-%d}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 窗口：WINDOW_START = 昨日 00:00；SCAN_START = WINDOW_START - 6h；END = now
    window_start = (datetime.datetime.combine(target_date, datetime.time.min)
                    - datetime.timedelta(days=1))
    scan_start = window_start - datetime.timedelta(hours=6)
    ws = window_start.replace(tzinfo=SH_TZ).isoformat()
    we = now.isoformat()
    ss = scan_start.replace(tzinfo=SH_TZ).isoformat()

    proxies, proxy_src = resolve_proxies(args.no_proxy)
    opener = build_opener(proxies)

    all_sources = src_reg.build_sources()
    if args.only:
        want = {x.strip() for x in args.only.split(",") if x.strip()}
        all_sources = [s for s in all_sources if s["id"] in want]
        if not all_sources:
            print(f"--only 未匹配任何源: {want}")
            return 2

    print("=" * 72)
    print("多源技术热点简报 · 采集 + 提取 + 对账")
    print(f"TARGET_WINDOW : {ws} → {we}")
    print(f"SCAN_WINDOW   : {ss} → {we}")
    print(f"输出目录      : {out_dir}")
    print(f"代理          : {proxies or '直连'}  [{proxy_src}]")
    print(f"源数量        : {len(all_sources)}   并发 {args.workers}")
    print("=" * 72)

    snap_dir = out_dir.parent / "snapshots"
    snap_path = snap_dir / "surface_snapshot.json"
    snapshots = {} if args.no_snapshot else coverage.load_snapshot(snap_path)

    records = []
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(args.workers) as ex:
        futs = {ex.submit(collect_one, opener, s, out_dir, ws, we): s
                for s in all_sources}
        for fut in concurrent.futures.as_completed(futs):
            s = futs[fut]
            try:
                rec = fut.result()
            except Exception as e:
                rec = {"id": s["id"], "entity": s["entity"], "surface": s["surface"],
                       "layer": s["layer"], "channel": s["channel"],
                       "mode": s["mode"], "critical": s.get("critical", False),
                       "transport": "url_error", "extract": "skipped",
                       "verdict": "TRANSPORT_FAIL", "extract_error": str(e)[:200],
                       "items_total": 0, "items_with_date": 0, "items_in_window": 0,
                       "items_in_window_exact": 0, "items_in_window_fuzzy": 0}
            records.append(rec)
            print(f"  [{rec['verdict']:16}] {rec['id']:30} "
                  f"items={rec.get('items_in_window',0)}/{rec.get('items_total',0)}"
                  f"{'  *critical' if rec.get('critical') else ''}", flush=True)

    records.sort(key=lambda r: (r["entity"], r["id"]))

    # 差分（M3）：本轮条目与上一快照比对。
    # 差分同时参与 verdict 判决：无日期源靠"相对上次有新增"证明本轮有新内容。
    diffs = {}
    if not args.no_snapshot:
        for rec in records:
            items_path = out_dir / f"items_{rec['id']}.json"
            if not items_path.exists():
                continue
            try:
                items = json.loads(items_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            d = coverage.diff_against_snapshot(rec["id"], items, snapshots)
            diffs[rec["id"]] = d
            rec["verdict"] = coverage.source_verdict(rec, diff=d)
            rec["new_vs_snapshot"] = d["new_count"]
            rec["is_first_run"] = d["is_first_run"]
            snapshots = coverage.update_snapshots(
                snapshots, rec["id"], items, target_date.strftime("%Y-%m-%d"))
        snap_dir.mkdir(parents=True, exist_ok=True)
        snap_path.write_text(json.dumps(snapshots, ensure_ascii=False, indent=2),
                             encoding="utf-8")

    report = coverage.build_report(
        records,
        window_start=ws, window_end=we, scan_start=ss,
        out_dir=str(out_dir), run_date=target_date.strftime("%Y-%m-%d"),
        required_surfaces=src_reg.REQUIRED_SURFACES,
        uncoverable=src_reg.UNCOVERABLE,
        diffs=diffs)
    report["proxy"] = {"config": proxies, "source": proxy_src}
    report["elapsed_sec"] = round(time.time() - t0, 1)
    report["snapshot_path"] = str(snap_path) if not args.no_snapshot else ""

    new_items = sum(d.get("new_count", 0) for d in diffs.values())
    report["summary"]["new_items_vs_snapshot"] = new_items

    rp = coverage.write_report(report, out_dir)
    coverage.print_summary(report)
    print(f"报告: {rp}")
    if diffs:
        print(f"差分: 本轮新增条目 {new_items} 条（首次运行全量计为新增属正常）")

    if args.fail_on_gate and not report["summary"]["gate_pass"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

assets/coverage.py
----------------------------------------
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
覆盖对账 + 源码面差分。

修两个机制缺陷：
  M1 三层混淆：把"传输成功 / 内容可解析 / 窗口内有条目"拆成三级状态，
     任何一级失败都不得冒充成功。
  M3 无差分：tech_def §2.E 要求 Official Surface Diff，此前实现为零。
     这里提供 snapshot 对比，产出 new / updated / dropped 三类差分。

输出：
  collect_report.json
    └─ sources[]        每源三级状态 + 条目统计
    └─ tracks{}         每个召回通道的覆盖度
    └─ surfaces{}       每个实体×面的覆盖度
    └─ gaps[]           必须补检的缺口（驱动 gap-driven 检索）
    └─ diff{}           与上一快照的条目差分
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

SH_TZ = timezone(timedelta(hours=8))


def shanghai_now() -> datetime:
    return datetime.now(SH_TZ)


# ---------- 三级状态 ----------
# transport : ok | http_error | timeout | proxy_block
# extract   : ok | empty | parse_failed | skipped
# window    : has_in_window | all_out_of_window | no_dates

def source_verdict(rec: dict, diff: dict | None = None) -> str:
    """
    把三级状态压成一个可读判定，用于 8.1 展示与 gate 判定。
    注意这是"展示用"汇总，三级原始字段必须同时保留在 report 里。

    diff 传入时，无日期源可以用"相对上一快照新增"证明本轮确实有新内容，
    判为 OK_NEW_VIA_DIFF 而不是 OK_NO_DATES。
    这对无 pubDate 的 RSS（如 Google Developers Blog）和趋势型源（HF Trending）
    至关重要：它们无法用日期归窗，但 snapshot 差分能证明"有变化"。
    """
    if rec.get("transport") != "ok":
        return "TRANSPORT_FAIL"
    ext = rec.get("extract")
    if ext == "blocked":
        return "PROXY_BLOCKED"
    if ext == "parse_failed":
        return "PARSE_FAILED"
    if ext == "empty":
        # 0 条目分两种，必须区别对待：
        #   结构完好、只是当天没有内容（arXiv 周末、发布节奏稀疏的厂商 blog）
        #     → OK_EMPTY，源是健康的，不是失明；
        #   结构认不出来 / 空响应 / 截断
        #     → EMPTY，这是真的没看到内容，必须补检。
        # 旧实现一律判 EMPTY，于是 arXiv 五个源在周日造出 4 个阻断缺口。
        if rec.get("structure_ok"):
            return "OK_EMPTY"
        return "EMPTY"
    if ext == "skipped":
        return "SKIPPED"
    if rec.get("items_in_window", 0) > 0:
        return "OK_IN_WINDOW"
    if rec.get("items_with_date", 0) == 0:
        if diff and diff.get("new_count", 0) > 0 and not diff.get("is_first_run"):
            return "OK_NEW_VIA_DIFF"
        return "OK_NO_DATES"
    return "OK_OUT_OF_WINDOW"


VERDICT_LABEL = {
    "OK_IN_WINDOW":     "窗口内有条目",
    "OK_NEW_VIA_DIFF":  "无日期但差分证明有新增",
    "OK_OUT_OF_WINDOW": "有内容但不在窗口内",
    "OK_NO_DATES":      "有内容但无可解析日期（差分未发现新增）",
    "EMPTY":            "结构不可识别或空响应（真失明）",
    "OK_EMPTY":         "源结构正常但当天 0 条（非失明）",
    "PARSE_FAILED":     "内容形态与声明模式不符",
    "PROXY_BLOCKED":    "代理拦截页",
    "TRANSPORT_FAIL":   "传输失败",
    "SKIPPED":          "跳过",
}

# 这些判定意味着"这个面今天没被真正看到内容"
# 注意 OK_NO_DATES / OK_OUT_OF_WINDOW / OK_EMPTY 不算失明：
#   前两者内容是拿到的，只是无法归窗（前者首轮出现，后续靠 snapshot 差分
#   升级为 OK_NEW_VIA_DIFF）；OK_EMPTY 是源结构正常、当天确实没有内容
#   （arXiv 周末、发布稀疏的厂商 blog），把这类算失明会产生假缺口。
BLIND_VERDICTS = {"TRANSPORT_FAIL", "PROXY_BLOCKED", "PARSE_FAILED", "EMPTY"}


def window_coverage(rec: dict, window_start: str, window_end: str) -> dict:
    """
    第四级状态：窗口覆盖度。

    为什么需要它：单页 API 只返回最近 N 条，可能只覆盖窗口的一小段。
    此时源是"OK_IN_WINDOW"，但窗口的大部分从未被检索 —— 静默截断。
    这类问题无法通过"是否抓到条目"发现，只能通过"最早条目 vs 窗口起点"发现。

    返回 {covered_from, covered_quality}
    covered_quality:
      full    最早条目 ≤ 窗口起点（翻页已触底或源本身只覆盖短窗口）
      partial 最早条目 > 窗口起点（窗口前半段未覆盖）
      unknown 无日期，无法判断
    """
    # 分页/切片源：覆盖度由采集端保证（它已经遍历了整个窗口），
    # 不能再用"最早条目是否早于窗口起点"判断。
    # 窗口内可能确实没有更早的条目（例如该片本来就没有内容），
    # 这时的 partial 是误判。
    pag = rec.get("pagination")
    if pag is not None:
        if pag.get("truncated") or pag.get("errors"):
            return {"covered_from": pag.get("oldest_seen", ""),
                    "covered_quality": "partial"}
        return {"covered_from": pag.get("oldest_seen", ""),
                "covered_quality": "full"}

    earliest = rec.get("earliest") or ""
    if not earliest:
        return {"covered_from": "", "covered_quality": "unknown"}
    try:
        e = datetime.fromisoformat(earliest)
        s = datetime.fromisoformat(window_start)
        window_end_dt = datetime.fromisoformat(window_end)
        # 必须对齐到同一时区再比较。条目时刻来自各源的原始时区
        # （HN 是 Z，arxiv 是 +00:00，其余多为 +08:00），
        # 直接比较 aware datetime 是对的，但若一方 naive 就会抛错。
        if e.tzinfo is None:
            e = e.replace(tzinfo=SH_TZ)
        if s.tzinfo is None:
            s = s.replace(tzinfo=SH_TZ)
        if window_end_dt.tzinfo is None:
            window_end_dt = window_end_dt.replace(tzinfo=SH_TZ)
    except ValueError:
        return {"covered_from": earliest, "covered_quality": "unknown"}

    # 整批发布源（arXiv 等）：一天只发一次，时刻固定为当天 00:00 时钟。
    # 用"连续覆盖"判定必然误报——窗口里周末没有发布，最早条目自然晚于窗口起点。
    # 对这类源改按"发布日"判定：窗口内每个工作日都必须有对应批次。
    if rec.get("daily_batch"):
        return _batch_coverage(rec, s, window_end_dt, earliest)

    # 允许 1 小时误差（发布延迟、时区取整）
    if e <= s + timedelta(hours=1):
        return {"covered_from": earliest, "covered_quality": "full"}

    # 只有"窗口前半段整段缺失"才算 partial。
    # 例如窗口 30 小时、最早条目在窗口内第 18 小时，前 18 小时确实未检索。
    # 若最早条目已覆盖窗口 80% 以上（如 arXiv 按天发布，当天全部条目都在
    # 窗口内），则不应报警 —— 否则每个"按天批量发布"的源都会误报。
    span = (window_end_dt - s).total_seconds()
    if span <= 0:
        return {"covered_from": earliest, "covered_quality": "full"}
    covered = (window_end_dt - e).total_seconds() / span
    if covered < 0.8:
        return {"covered_from": earliest, "covered_quality": "partial"}
    return {"covered_from": earliest, "covered_quality": "full"}


def _batch_coverage(rec: dict, start: datetime, end: datetime,
                    earliest: str) -> dict:
    """
    整批发布源的覆盖度：按"发布日"而非"连续时间"判定。

    判据：窗口内每个工作日（周一至周五）都应有该源的一个批次。
    缺哪个工作日就报哪个，而不是笼统报"窗口前半段未检索"。
    """
    try:
        e = datetime.fromisoformat(earliest)
        if e.tzinfo is None:
            e = e.replace(tzinfo=SH_TZ)
    except ValueError:
        return {"covered_from": earliest, "covered_quality": "unknown"}

    batch_dates = {d[:10] for d in rec.get("batch_dates", [])} or {e.date().isoformat()}
    missing = []
    d = start.date()
    while d <= end.date():
        # arXiv 周末不发布；只要求工作日有批次
        if d.weekday() < 5 and d.isoformat() not in batch_dates:
            missing.append(d.isoformat())
        d += timedelta(days=1)

    if missing:
        return {"covered_from": earliest, "covered_quality": "partial",
                "missing_batch_days": missing}
    return {"covered_from": earliest, "covered_quality": "full"}


# ---------- 源快照差分（M3） ----------
def load_snapshot(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def diff_against_snapshot(source_id: str, items: list[dict], snapshots: dict) -> dict:
    """
    与上一快照比对新条目。
    快照只存 uid 集合（不存正文），因此只能判定 new / dropped，
    对同一 uid 的正文变化（updated）需要整篇 diff，这里不做——
    官方 changelog 的条目 uid 含日期锚点，正文更新会体现为新 uid。
    """
    prev = set(snapshots.get(source_id, {}).get("uids", []))
    cur = {i["uid"] for i in items if i.get("uid")}
    return {
        "new_uids": sorted(cur - prev),
        "dropped_uids": sorted(prev - cur),
        "is_first_run": not prev,
        "new_count": len(cur - prev),
    }


def update_snapshots(snapshots: dict, source_id: str, items: list[dict],
                     run_date: str) -> dict:
    """
    推进快照基线。

    **同一天重跑不得覆盖基线。** 定时任务可能因为失败重试、手工补跑而
    在同一自然日执行多次；若每次都把当前条目写成新基线，第二次运行的
    差分就变成"与几分钟前的自己比" —— 结果全部 carried_over，
    真正的新增被静默抹掉。基线只在跨日时前进。
    """
    prev = snapshots.get(source_id) or {}
    prev_run = prev.get("last_run") or ""
    if prev_run and run_date <= prev_run:
        # 同一日期（或更早）的重跑：保留昨天的基线，让差分仍然有意义
        return snapshots

    snapshots[source_id] = {
        "uids": sorted({i["uid"] for i in items if i.get("uid")}),
        "count": len(items),
        "last_run": run_date,
    }
    return snapshots


# ---------- 覆盖对账 ----------
def track_coverage(records: list[dict]) -> dict:
    """按召回通道统计覆盖度。"""
    out = {}
    for r in records:
        t = r.get("channel", "unknown")
        d = out.setdefault(t, {"sources": 0, "ok_in_window": 0, "blind": 0,
                               "items_in_window": 0, "items_in_window_fuzzy": 0})
        d["sources"] += 1
        v = r.get("verdict", "")
        if v in ("OK_IN_WINDOW", "OK_NEW_VIA_DIFF"):
            d["ok_in_window"] += 1
        if v in BLIND_VERDICTS:
            d["blind"] += 1
        d["items_in_window"] += r.get("items_in_window", 0)
        d["items_in_window_fuzzy"] += r.get("items_in_window_fuzzy", 0)
    return out


def surface_coverage(records: list[dict]) -> dict:
    """按 实体×面 统计覆盖度 —— 回答"OpenAI 的 developer 面今天查到东西了吗"。"""
    out = {}
    for r in records:
        key = f"{r.get('entity','?')}/{r.get('surface','?')}"
        d = out.setdefault(key, {"sources": [], "ok_in_window": 0, "checked": 0,
                                 "blind": 0, "items_in_window": 0,
                                 "items_in_window_fuzzy": 0})
        d["sources"].append(r.get("id"))
        v = r.get("verdict", "")
        if v in ("OK_IN_WINDOW", "OK_NEW_VIA_DIFF"):
            d["ok_in_window"] += 1
        # "读过"与"读到新内容"必须分开：OK_OUT_OF_WINDOW 表示源被成功读取、
        # 只是窗口内无新增，这不是失明。把两者混同会让"已检查无更新"
        # 被误报为"未覆盖"，导致补检永远打在已经查过的地方。
        if v not in BLIND_VERDICTS:
            d["checked"] += 1
        if v in BLIND_VERDICTS:
            d["blind"] += 1
        d["items_in_window"] += r.get("items_in_window", 0)
        d["items_in_window_fuzzy"] += r.get("items_in_window_fuzzy", 0)
    return out


def build_gaps(records: list[dict], required_surfaces: dict,
               uncoverable: list[dict], surfaces: dict) -> list[dict]:
    """
    产出必须补检的缺口。这是修 M4：零覆盖必须产生动作，不能只写理由。

    gap 类型：
      surface_blind    该实体该面有源但全部失明（gate 失败级）
      surface_missing  该实体该面没有登记任何源
      surface_uncoverable  已登记不可达原因（不阻断，但必须写进 8.1）
      source_blind     非关键源失明（不阻断）
      critical_blind   关键源失明（gate 失败级）
      window_partial   窗口前半段未被检索（critical 源阻断，其余转 action 任务）
    """
    gaps = []
    unc = {(u["entity"], u["surface"]): u["reason"] for u in uncoverable}

    # 1. 关键源失明
    for r in records:
        if r.get("critical") and r.get("verdict") in BLIND_VERDICTS:
            gaps.append({
                "type": "critical_blind", "blocking": True,
                "entity": r.get("entity"), "surface": r.get("surface"),
                "source": r.get("id"), "verdict": r.get("verdict"),
                "suggestion": _gap_query_hint(r),
            })

    # 1b. 静默截断：源"有条目"但窗口前半段从未被检索。
    # 这类问题最危险 —— 报告看起来是成功的，漏检藏在覆盖盲区里。
    for r in records:
        if r.get("covered_quality") == "partial":
            gaps.append({
                "type": "window_partial", "blocking": bool(r.get("critical")),
                # 非 critical 源的窗口截断不阻断 gate，但必须转成补检任务。
                # 否则它只留在 report.note 里，永远不进 8.3、也永远不会被补。
                "action_required": True,
                "entity": r.get("entity"), "surface": r.get("surface"),
                "source": r.get("id"), "verdict": "PARTIAL_WINDOW",
                # 缺口必须自带"哪一段没被检索"，否则补检任务写不出可验收的目标
                "covered_from": r.get("covered_from", ""),
                # 未检索的区间是 [窗口起点, 最早条目]，方向不能写反：
                # covered_from 晚于窗口起点，所以缺的是它前面那一段。
                "suggestion": (f'"{r.get("entity")}" 在 窗口起点 至 '
                               f'{r.get("covered_from","")[:16]} 之间的发布，'
                               f'需回溯该时段（翻页/日期过滤/站点归档）'),
            })

    # 2. 必须覆盖的实体×面
    for entity, req in required_surfaces.items():
        if entity == "default":
            continue
        for surf in req:
            key = f"{entity}/{surf}"
            cov = surfaces.get(key)
            if cov is None:
                if (entity, surf) in unc:
                    continue  # 已在 UNCOVERABLE 登记
                gaps.append({
                    "type": "surface_missing", "blocking": True,
                    "entity": entity, "surface": surf, "source": "",
                    "verdict": "NOT_REGISTERED",
                    "suggestion": f'"{entity}" {surf} changelog release notes 站点',
                })
                continue
            # 判定口径：
            #   checked>0 且 blind==0  → 该面已成功读取（窗口内无新增是正常结论，不阻断）
            #   blind>0 且 checked==0  → 完全失明，必须补检（阻断）
            #   blind>0 且 checked>0   → 部分失明，降级为警告（仍有源读到了内容）
            if cov["blind"] == 0 and cov["checked"] > 0:
                continue
            blocking = cov["checked"] == 0
            gaps.append({
                "type": "surface_blind", "blocking": blocking,
                "entity": entity, "surface": surf,
                "source": ",".join(cov["sources"]),
                "verdict": "ALL_BLIND" if blocking else "PARTIAL_BLIND",
                "suggestion": _surface_query_hint(entity, surf),
            })

    # 3. 非关键源失明（记录但不阻断）
    for r in records:
        if not r.get("critical") and r.get("verdict") in BLIND_VERDICTS:
            gaps.append({
                "type": "source_blind", "blocking": False,
                "entity": r.get("entity"), "surface": r.get("surface"),
                "source": r.get("id"), "verdict": r.get("verdict"),
                "suggestion": _gap_query_hint(r),
            })
    return gaps


def _gap_query_hint(rec: dict) -> str:
    ent = rec.get("entity", "")
    layer = rec.get("layer", "")
    return f'"{ent}" {layer} site:github.com OR changelog OR release notes 时间范围覆盖 SCAN_WINDOW'


def _surface_query_hint(entity: str, surface: str) -> str:
    kw = {
        "developer": "API changelog release notes deprecation",
        "company": "announcement blog news",
        "product": "product blog update",
        "code": "github releases",
        "research": "research blog paper",
        "model": "model card release",
        "support": "help center release notes",
    }.get(surface, "update")
    return f'"{entity}" {kw} 时间范围覆盖 SCAN_WINDOW'


# ---------- 报告生成 ----------
def build_report(records: list[dict], *, window_start: str, window_end: str,
                 scan_start: str, out_dir: str, run_date: str,
                 required_surfaces: dict, uncoverable: list[dict],
                 diffs: dict) -> dict:
    # 第四级：窗口覆盖度。标记"有条目但只覆盖窗口一小段"的静默截断。
    for r in records:
        wc = window_coverage(r, window_start, window_end)
        r["covered_from"] = wc["covered_from"]
        r["covered_quality"] = wc["covered_quality"]
        if wc["covered_quality"] == "partial" and not r.get("note"):
            r["note"] = (f"窗口覆盖不完整：最早条目 {wc['covered_from'][:19]} "
                         f"晚于窗口起点，前半段未检索")

    surfaces = surface_coverage(records)
    tracks = track_coverage(records)
    gaps = build_gaps(records, required_surfaces, uncoverable, surfaces)

    blocking = [g for g in gaps if g.get("blocking")]
    total_in_window = sum(r.get("items_in_window", 0) for r in records)

    # 汇总每种判定的数量，8.1 直接可用
    verdict_counts = {}
    for r in records:
        verdict_counts[r.get("verdict", "?")] = verdict_counts.get(r.get("verdict", "?"), 0) + 1

    return {
        "generated_at": shanghai_now().strftime("%Y-%m-%d %H:%M:%S"),
        "run_date": run_date,
        "target_window": {"start": window_start, "end": window_end},
        "scan_window": {"start": scan_start, "end": window_end},
        "out_dir": str(out_dir),
        "summary": {
            "sources_total": len(records),
            "sources_transport_ok": sum(1 for r in records if r.get("transport") == "ok"),
            "sources_extract_ok": sum(1 for r in records if r.get("extract") == "ok"),
            "sources_in_window": sum(1 for r in records if r.get("verdict") == "OK_IN_WINDOW"),
            "sources_blind": sum(1 for r in records if r.get("verdict") in BLIND_VERDICTS),
            "items_total": sum(r.get("items_total", 0) for r in records),
            "items_in_window": total_in_window,
            # 确定事件与"仅日粒度、区间与窗口相交"的待确认事件必须分开报。
            # 合并成一个数字会让 8.1 无法回答"哪些是需要人工核时间的"。
            "items_in_window_exact": sum(r.get("items_in_window_exact", 0) for r in records),
            "items_in_window_fuzzy": sum(r.get("items_in_window_fuzzy", 0) for r in records),
            "blocking_gaps": len(blocking),
            # 窗口截断不阻断 gate，但必须被计数 —— 否则 8.1 只报
            # "44 源 transport 成功"，读者无从知道其中 6 个源只覆盖了后半窗口。
            "window_partial_sources": sum(
                1 for r in records if r.get("covered_quality") == "partial"),
            "action_gaps": sum(1 for g in gaps if g.get("action_required")),
            "gate_pass": len(blocking) == 0,
        },
        "verdict_counts": verdict_counts,
        "verdict_labels": VERDICT_LABEL,
        "tracks": tracks,
        "surfaces": surfaces,
        "gaps": gaps,
        "diff": diffs,
        "sources": records,
    }


def write_report(report: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "collect_report.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def print_summary(report: dict) -> None:
    s = report["summary"]
    print("\n" + "=" * 72)
    print(f"采集对账  sources={s['sources_total']}  "
          f"transport_ok={s['sources_transport_ok']}  "
          f"extract_ok={s['sources_extract_ok']}  "
          f"in_window={s['sources_in_window']}")
    print(f"条目      total={s['items_total']}  in_window={s['items_in_window']}")
    print(f"Gate      {'PASS' if s['gate_pass'] else 'FAIL'}  "
          f"blocking_gaps={s['blocking_gaps']}  "
          f"window_partial_sources={s.get('window_partial_sources', 0)}  "
          f"action_gaps={s.get('action_gaps', 0)}")

    print("\n判定分布:")
    for v, n in sorted(report["verdict_counts"].items(), key=lambda x: -x[1]):
        print(f"  {v:18} {n:3}  {VERDICT_LABEL.get(v, '')}")

    blind = [r for r in report["sources"] if r.get("verdict") in BLIND_VERDICTS]
    if blind:
        print("\n失明源（含原因）:")
        for r in blind:
            print(f"  - {r['id']:32} {r['verdict']:15} {r.get('note', r.get('extract_error',''))[:50]}")

    if report["gaps"]:
        print("\n覆盖缺口（需 gap-driven 补检）:")
        for g in report["gaps"]:
            flag = "BLOCK" if g.get("blocking") else (
                "ACTION" if g.get("action_required") else "warn ")
            print(f"  [{flag}] {g['type']:18} {g.get('entity','')}/{g.get('surface','')} "
                  f"src={g.get('source','')}")
            if g.get("suggestion"):
                print(f"           → {g['suggestion'][:100]}")

    print("=" * 72)


if __name__ == "__main__":
    print("coverage.py 是库模块，由 collect_sources.py 调用。")

assets/extract.py
----------------------------------------
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
