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
