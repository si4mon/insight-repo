#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给没有摘要的 arXiv 条目补抓摘要，让 must_review 的打分可比。

为什么需要：`must_review.arxiv_score` 打的是标题加摘要。主通道 RSS 的条目带摘要，
归档页回退召回的条目只有标题，于是同一篇论文在两条通道里能差出几分——差的不是
信号强弱，是可打分文本的长度。2026-11-03 一轮实测：窗口内 1840 篇去重条目里
1459 篇（79%）没有摘要，却只占到 top-40 的 45%；得分 ≥6 的比例 4.2% vs 15.2%，
差 3.6 倍。而那一轮的一个 A 级事件（J-Space 串谋）正出自归档批次。

为什么不按"有无摘要"分车道配名额：试过，有实测反例。那篇 A 级论文得 8 分且
**有**摘要，按池内占比分配会把有摘要车道压到 8 个名额、截断线抬到 9 分，它反而
被挤出清单——把一种偏差换成了另一种。摘要缺失是测量问题，不是分布问题，所以
补测量，不调名额。

走 arXiv 官方批量接口（export.arxiv.org/api/query?id_list=...），一次 100 篇，
按官方要求在调用之间留间隔。结果落盘成快照，重跑不重抓；抓不到的条目老实保留
标题分，由 must_review 把残量报出来——不编造摘要。

  python arxiv_abstracts.py --raw-dir raw_2026-11-06
  python arxiv_abstracts.py --raw-dir raw_2026-11-06 --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
from pathlib import Path

import build_pool
import collect_sources as cs
import sources as src_reg

API = "http://export.arxiv.org/api/query"
BATCH = 100              # 官方接口单次 id_list 上限量级
PAUSE = 3.0              # 官方要求的调用间隔（秒）
CACHE_NAME = build_pool.ABSTRACT_CACHE

_ENTRY = re.compile(r"<entry>([\s\S]*?)</entry>")
_ID = re.compile(r"<id>\s*https?://arxiv\.org/abs/([0-9]{4}\.[0-9]{4,5})")
_SUMMARY = re.compile(r"<summary[^>]*>([\s\S]*?)</summary>")


arxiv_id = build_pool.arxiv_id          # 编号解析与摘要判定归 build_pool


def _unescape(s: str) -> str:
    import html
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def parse_feed(body: bytes) -> dict[str, str]:
    """从 Atom 响应里取 {arxiv_id: 摘要}。"""
    out: dict[str, str] = {}
    text = body.decode("utf-8", errors="replace")
    for entry in _ENTRY.findall(text):
        mid = _ID.search(entry)
        msum = _SUMMARY.search(entry)
        if mid and msum:
            s = _unescape(msum.group(1))
            if s:
                out[mid.group(1)] = s
    return out


def missing_ids(pool: list[dict]) -> list[str]:
    """窗口内、无摘要、能解析出 arXiv 编号的条目，按编号去重。"""
    out, seen = [], set()
    for row in pool:
        if (row.get("channel") or "") != "B_arxiv":
            continue
        if not (row.get("in_window") is True
                or row.get("window_match") == "no_date"):
            continue
        if build_pool.has_abstract(row):
            continue
        aid = arxiv_id(row)
        if aid and aid not in seen:
            seen.add(aid)
            out.append(aid)
    return out


def fetch_abstracts(ids: list[str], opener, ua: str, timeout: int = 30,
                    pause: float = PAUSE, log=print) -> tuple[dict[str, str], list[str]]:
    """批量取摘要。返回 (命中, 失败的批次说明)。"""
    got: dict[str, str] = {}
    errs: list[str] = []
    batches = [ids[i:i + BATCH] for i in range(0, len(ids), BATCH)]
    for n, batch in enumerate(batches, 1):
        q = urllib.parse.urlencode({"id_list": ",".join(batch),
                                    "max_results": len(batch)})
        status, body, err = cs.fetch(opener, f"{API}?{q}", ua, timeout)
        if status != "ok":
            errs.append(f"批次 {n}/{len(batches)}: {status} {err}")
            log(f"  批次 {n}/{len(batches)} 失败: {status} {err}")
        else:
            hit = parse_feed(body)
            got.update(hit)
            log(f"  批次 {n}/{len(batches)}: 请求 {len(batch)} 篇，拿到 {len(hit)} 条摘要")
        if n < len(batches):
            time.sleep(pause)
    return got, errs


def load_cache(raw_dir: Path) -> dict[str, str]:
    f = raw_dir / CACHE_NAME
    if not f.exists():
        return {}
    try:
        return (json.loads(f.read_text(encoding="utf-8")) or {}).get("abstracts") or {}
    except Exception:
        return {}


def save_cache(raw_dir: Path, abstracts: dict[str, str], errs: list[str]) -> Path:
    f = raw_dir / CACHE_NAME
    f.write_text(json.dumps(
        {"_doc": "arXiv 摘要补抓快照。无摘要条目的打分文本只有标题，分数系统性偏低；"
                 "这里按 abs 编号补齐，重跑不重抓。",
         "source": API, "count": len(abstracts), "errors": errs,
         "abstracts": abstracts}, ensure_ascii=False, indent=2), encoding="utf-8")
    return f


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw-dir", required=True, help="raw_<date>/ 目录")
    ap.add_argument("--dry-run", action="store_true", help="只报需要补抓的数量，不发请求")
    ap.add_argument("--no-proxy", action="store_true")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--pause", type=float, default=PAUSE)
    args = ap.parse_args()

    raw = Path(args.raw_dir)
    pool, _ = build_pool.build(raw)
    ids = missing_ids(pool)
    cache = load_cache(raw)
    todo = [i for i in ids if i not in cache]
    print(f"窗口内 arXiv 无摘要条目 {len(ids)} 篇；快照已有 {len(ids) - len(todo)} 篇，"
          f"待抓 {len(todo)} 篇（{-(-len(todo) // BATCH)} 次请求）")
    if args.dry_run or not todo:
        return 0

    proxies, proxy_src = cs.resolve_proxies(args.no_proxy)
    print(f"出网: {proxy_src}")
    got, errs = fetch_abstracts(todo, cs.build_opener(proxies), src_reg.DEFAULT_UA,
                                args.timeout, args.pause)
    cache.update(got)
    f = save_cache(raw, cache, errs)
    miss = [i for i in ids if i not in cache]
    print(f"补抓 {len(got)} 条 → {f}")
    if miss:
        print(f"! 仍有 {len(miss)} 篇没有摘要，打分按标题计（偏低）: {miss[:5]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
