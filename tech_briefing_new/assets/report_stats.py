#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 events_run_<date>/ 派生简报的全部统计口径，供成稿与门禁共用。

为什么要有这个脚本：手写的统计一定会和事实源漂移。2026-10-31 的一次运行里，
正文自报 15 个事件、索引只列了 14 行，自报 A+/A 为 1/5、实际是 1/6。
Dashboard、8.2 索引、第 2 章 Top N 现在都从同一份事件目录派生，
门禁再用同一个函数复算一遍，对不上就 FAIL。

  python report_stats.py --events events_run_2026-10-30 --report raw_.../collect_report.json
  python report_stats.py --events ... --out stats.json --markdown
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import taxonomy as tax_mod

RATING_ORDER = ("A+", "A", "B", "C")
CHANGE_OBJECTS = ("Model", "Harness", "运行平台", "交互·应用", "尚未披露")


def load_events(events_dir: Path) -> dict:
    out = {}
    for f in sorted(events_dir.glob("EV-*.json")):
        try:
            out[f.stem] = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"{f.name} 解析失败: {e}", file=sys.stderr)
    return out


def compute(events: dict, report: dict | None = None,
            thesis_report: dict | None = None) -> dict:
    ws = ((report or {}).get("target_window") or {}).get("start", "")
    rating = Counter(ev.get("rating", "?") for ev in events.values())
    signal = Counter(ev.get("signal", "") for ev in events.values() if ev.get("signal"))
    obj = Counter(ev.get("change_object", "尚未披露") for ev in events.values())

    columns = Counter()
    for ev in events.values():
        try:
            columns[tax_mod.TAXONOMY.resolve(ev.get("primary_path", ""))] += 1
        except Exception:
            columns["?"] += 1

    def is_active(ev) -> bool:
        fp = str(ev.get("first_publish_shanghai", ""))
        return bool(ws and fp and fp < ws)

    rows = []
    for eid in sorted(events, key=lambda x: (len(x), x)):
        ev = events[eid]
        try:
            col = tax_mod.TAXONOMY.resolve(ev.get("primary_path", ""))
        except Exception:
            col = "?"
        rows.append({
            "id": eid, "rating": ev.get("rating", ""),
            "title": ev.get("event_title", ""),
            "first_publish": ev.get("first_publish_shanghai", ""),
            "precision": ev.get("date_precision", ""),
            "column": col, "signal": ev.get("signal", ""),
            "active": is_active(ev),
            "theses": sorted({l for l in [(ev.get("thesis_decision") or {}).get("thesis_id")] if l}),
        })

    top = [r for r in rows if r["rating"] in ("A+", "A")]
    top.sort(key=lambda r: (RATING_ORDER.index(r["rating"]), r["id"]))

    return {
        "events_total": len(events),
        "by_rating": {k: rating.get(k, 0) for k in RATING_ORDER},
        "by_signal": dict(sorted(signal.items())),
        "by_change_object": {k: obj.get(k, 0) for k in CHANGE_OBJECTS},
        "by_column": dict(sorted(columns.items())),
        "active_events": sum(1 for r in rows if r["active"]),
        "top_candidates": [r["id"] for r in top],
        "index_rows": rows,
        "core_judgments": [t["id"] for t in (thesis_report or {}).get("theses", [])
                           if t.get("core_judgment")],
        "target_window": (report or {}).get("target_window", {}),
    }


def dashboard_markdown(st: dict) -> str:
    tw = st.get("target_window") or {}
    L = ["| 指标 | 数值 |", "|---|---|"]
    if tw:
        L.append(f"| TARGET_WINDOW | {tw.get('start','')} → {tw.get('end','')} |")
    L.append(f"| 事件总数 | {st['events_total']} |")
    L.append(f"| A+ / A | {st['by_rating']['A+']} / {st['by_rating']['A']} |")
    for k, v in st["by_signal"].items():
        L.append(f"| {k} Signal | {v} |")
    L.append(f"| Active Event | {st['active_events']} |")
    for k, v in st["by_change_object"].items():
        L.append(f"| change_object：{k} | {v} |")
    return "\n".join(L)


def index_markdown(st: dict) -> str:
    L = ["| EV | 评级 | 事件 | 首发（Asia/Shanghai） | 精度 | 栏目 |", "|---|---|---|---|---|---|"]
    for r in st["index_rows"]:
        t = r["title"].replace("|", "｜")
        L.append(f"| {r['id']} | {r['rating']} | {t} | "
                 f"{r['first_publish'][:16].replace('T', ' ')} | {r['precision']} | {r['column']} |")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="从事件目录派生简报统计")
    ap.add_argument("--events", required=True)
    ap.add_argument("--report", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--markdown", action="store_true", help="同时打印可直接粘贴的表格")
    args = ap.parse_args()

    ed = Path(args.events)
    if not ed.exists():
        print(f"事件目录不存在: {ed}", file=sys.stderr)
        return 2
    report = json.loads(Path(args.report).read_text(encoding="utf-8")) if args.report else None
    tr = ed / "thesis_report.json"
    st = compute(load_events(ed), report,
                 json.loads(tr.read_text(encoding="utf-8")) if tr.exists() else None)

    if args.out:
        Path(args.out).write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"→ {args.out}")
    if args.markdown:
        print("\n### Dashboard\n");  print(dashboard_markdown(st))
        print("\n### 8.2 事件索引\n"); print(index_markdown(st))
    else:
        print(json.dumps({k: v for k, v in st.items() if k != "index_rows"},
                         ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
