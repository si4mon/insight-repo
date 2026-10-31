#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""冻结 TARGET_WINDOW，产出 window.json（SKILL.md 步骤 1 的第一条命令）。

窗口只冻结一次，之后采集、建池、归窗、门禁全部读这一份。各脚本各自再算一遍
会产生秒级漂移（实测 22 秒），让产物之间的窗口口径对不上。

  python freeze_window.py                      # 冻结到 ./window.json
  python freeze_window.py --out raw_<date>/window.json
  python freeze_window.py --date 2026-10-27    # 补跑：把那天当作「今天」
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

SH_TZ = datetime.timezone(datetime.timedelta(hours=8))
SCAN_BUFFER_HOURS = 6      # task_def §0.1


def freeze(now: datetime.datetime, target_date: datetime.date) -> dict:
    window_start = (datetime.datetime.combine(target_date, datetime.time.min)
                    - datetime.timedelta(days=1)).replace(tzinfo=SH_TZ)
    return {
        "window_start": window_start.isoformat(),
        "window_end": now.isoformat(),
        "scan_start": (window_start
                       - datetime.timedelta(hours=SCAN_BUFFER_HOURS)).isoformat(),
        "scan_buffer_hours": SCAN_BUFFER_HOURS,
        "tz": "Asia/Shanghai",
        "run_date": target_date.strftime("%Y-%m-%d"),
        "window_start_date": window_start.strftime("%Y-%m-%d"),
        "frozen_at": now.isoformat(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="冻结 TARGET_WINDOW")
    ap.add_argument("--out", default="window.json")
    ap.add_argument("--date", default="", help="把哪一天当作「今天」（补跑用）")
    args = ap.parse_args()

    now = datetime.datetime.now(SH_TZ)
    if args.date:
        try:
            target_date = datetime.datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"无效日期: {args.date}", file=sys.stderr)
            return 2
    else:
        target_date = now.date()

    win = freeze(now, target_date)
    out = Path(args.out)
    if out.exists():
        print(f"{out} 已存在，拒绝覆盖（窗口一轮只能冻结一次）。"
              f"确需重来请先删除它。", file=sys.stderr)
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(win, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"TARGET_WINDOW : {win['window_start']} → {win['window_end']}")
    print(f"SCAN_WINDOW   : {win['scan_start']} → {win['window_end']}")
    print(f"WINDOW_START_DATE : {win['window_start_date']}   （events_run_ 与报告文件名用它）")
    print(f"→ {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
