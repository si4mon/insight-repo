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
