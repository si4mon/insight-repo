#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把覆盖缺口转换成可执行补检任务。

修机制缺陷 M4：零覆盖此前只要求"在 8.1 写原因"，不产生任何动作。
结果是补检永远是 event-driven（围绕已发现的事件深挖），而漏检恰恰发生在
"没有发现任何事件"的那些面上 —— 补检永远打不到那里。

这里的做法：每个 blocking gap 必须生成一条任务，任务带
  - 检索式（query）：针对该实体该面，而不是针对已发现事件
  - 目标面（surface）：证明"该面被检查过"
  - 验收条件（acceptance）：什么算这条任务完成

产出 gap_tasks.json，供 P1 阶段执行；未完成的任务在 8.3 必须逐条交代。

用法：
  python gap_tasks.py --report raw_2026-10-23/collect_report.json --out gap_tasks.json
  python gap_tasks.py --report ... --mark-done openai_api_changelog --note "..."
"""
import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

SH_TZ = timezone(timedelta(hours=8))

# 每个 surface 对应的检索模板。
# 注意：这些模板刻意不包含具体产品名或事件名 —— 目的就是覆盖"未知的未知"。
SURFACE_QUERIES = {
    "developer": [
        '"{entity}" API changelog OR release notes OR deprecation 2026',
        '"{entity}" developer docs new endpoint OR new parameter',
        'site:github.com "{entity}" sdk releases 2026',
    ],
    "company": [
        '"{entity}" announcement OR blog news 2026',
        '"{entity}" press release OR official statement 2026',
    ],
    "product": [
        '"{entity}" product update OR feature launch 2026',
        '"{entity}" app update OR new capability 2026',
    ],
    "code": [
        'site:github.com "{entity}" releases atom 2026',
        '"{entity}" open source release 2026',
    ],
    "research": [
        '"{entity}" research paper OR technical report 2026',
        '"{entity}" arxiv 2026',
    ],
    "model": [
        '"{entity}" model card OR model release 2026',
        '"{entity}" new model announcement 2026',
    ],
    "support": [
        '"{entity}" help center release notes 2026',
        '"{entity}" support update OR known issue 2026',
    ],
    "aggregator": [
        '"{entity}" trending OR front page 2026',
    ],
    "community": [
        '"{entity}" blog post OR discussion 2026',
    ],
}

# 代理拦截类缺口：检索无效，必须换通道
PROXY_FALLBACK_HINT = {
    "Anthropic": "官方站被 HIS 代理拦截：改用 claude.com sitemap 差分 + "
                 "第三方转载（Techmeme/HN/Simon Willison）+ LinkedIn/X 官方账号镜像",
    "MiniMax": "minimax.io 被拦截：改用 GitHub org releases + HN/Techmeme 回溯",
}


def _as_dt(s: str) -> datetime:
    """解析 ISO 时刻用于比较；无法解析时退化为"极晚"，不参与最宽缺口竞争。"""
    try:
        dt = datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return datetime.max.replace(tzinfo=SH_TZ)
    return dt if dt.tzinfo else dt.replace(tzinfo=SH_TZ)


def build_tasks(report: dict, run_date: str) -> dict:
    """从 collect_report 的 gaps 生成任务清单。"""
    tasks = []
    # 旧版 report 的 window_partial gap 不带 covered_from，退回源记录上取，
    # 这样补检任务仍能写出"从哪一刻到窗口起点"的可验收区间。
    src_by_id = {r.get("id"): r for r in report.get("sources", [])}

    # blocking  → 阻断 gate，必须关闭才能交付
    # action_required → 不阻断，但必须有人对"这段时间有没有东西"给出结论
    # window_partial 属于后者：源读到了内容，只是窗口前半段从未被检索。
    # 只按 blocking 过滤会让它静默消失（历史缺陷：arXiv 按天批量发布，
    # 每个分类只覆盖窗口后半段，report 里记了 note，8.3 却完全没有这一行）。
    # 兼容旧版 collect_report（其 gaps 里没有 action_required 字段）。
    candidates = [g for g in report.get("gaps", [])
                  if g.get("blocking") or g.get("action_required")
                  or g.get("type") == "window_partial"]
    # 阻断缺口先编号：GAP-01.. 必须稳定对应"最严重的那几个"，
    # 否则补检记录跨 run 无法对齐。
    candidates.sort(key=lambda g: 0 if g.get("blocking") else 1)

    # 窗口截断按 (实体, 面) 合并成一条任务。
    # arXiv 五个分类源各自 partial，拆开会得到 5 条实质相同的检索任务，
    # 让真正的失明缺口被自己的重复项淹没。
    merged: dict[tuple, dict] = {}
    ordered = []
    for g in candidates:
        if g.get("type") == "window_partial":
            key = (g.get("entity", ""), g.get("surface", ""))
            group = merged.get(key)
            if group is None:
                group = {
                    "entity": g.get("entity", ""), "surface": g.get("surface", ""),
                    "type": "window_partial", "blocking": bool(g.get("blocking")),
                    "verdict": "PARTIAL_WINDOW",
                    "sources": [], "covered_from": "",
                }
                merged[key] = group
                ordered.append(group)
            group["sources"].append(g.get("source", ""))
            cf = (g.get("covered_from")
                  or src_by_id.get(g.get("source", ""), {}).get("covered_from", ""))
            # 合并后要报"最宽的缺口"，也就是最早的那个 covered_from。
            # 必须按时间比较：各源时区不同（arXiv -04:00 / HN Z / 其余 +08:00），
            # 字符串比较会挑错。
            if cf and (not group["covered_from"]
                       or _as_dt(cf) < _as_dt(group["covered_from"])):
                group["covered_from"] = cf
            group["blocking"] = group["blocking"] or bool(g.get("blocking"))
        else:
            ordered.append(g)

    for tid0, g in enumerate(ordered, start=1):
        tid = tid0
        entity = g.get("entity", "")
        surface = g.get("surface", "")
        source = g.get("source", "")
        verdict = g.get("verdict", "")

        queries = [q.format(entity=entity) for q in
                   SURFACE_QUERIES.get(surface, ['"{entity}" 2026'])]
        if g.get("type") == "entity_blind":
            queries = [f'"{t}" 发布 OR 上线 OR 更新 OR release OR launch'
                       for t in g.get("search_terms") or [entity]]

        # window_partial 不是"整面失明"，而是"某一段时间没被检索到"，
        # 检索式的目标必须是那段时间，而不是整个面。
        if g.get("type") == "window_partial":
            sources = g.get("sources") or [source]
            covered_from = (g.get("covered_from")
                            or src_by_id.get(source, {}).get("covered_from", ""))
            acceptance = (
                f"能给出 {entity}/{surface} 面在 窗口起点 至 "
                f"{covered_from[:16] or '最早条目'} 之间的明确结论："
                f"有 N 条发布（附原始 URL 与首发时刻），"
                f"或确认该时段确实无发布（附翻页/归档检查证据）"
            )
        elif g.get("type") == "entity_blind":
            sources = []
            acceptance = (
                f"{entity} 官方面全部不可达：用检索式覆盖 SCAN_WINDOW，给出明确结论——"
                f"有 N 条发布（经中文媒体 / 聚合源回溯到官方原文，附原始 URL 与首发时刻），"
                f"或确认 0 条（附检索式与检查范围）"
            )
        else:
            sources = [source]
            acceptance = (
                f"能给出 {entity}/{surface} 面在 SCAN_WINDOW 内的明确结论："
                f"有 N 条更新（附原始 URL 与首发时刻），或确认 0 条更新（附检查证据）"
            )

        # 代理拦截：检索补不了，必须换通道。明确写出来，避免"搜了但搜不到"。
        fallback = ""
        if verdict in ("PROXY_BLOCKED", "ALL_BLIND") and entity in PROXY_FALLBACK_HINT:
            fallback = PROXY_FALLBACK_HINT[entity]

        tasks.append({
            "id": f"GAP-{tid:02d}",
            "priority": "P0" if g.get("type") == "critical_blind" else "P1",
            "type": g.get("type"),
            "entity": entity,
            "surface": surface,
            "failing_source": source,
            "failing_verdict": verdict,
            "status": "open",
            "blocking": bool(g.get("blocking")),
            # 一个任务可能覆盖多个源（窗口截断按实体的面合并），
            # verify_gates 用它核对"每个 partial 源都有任务"。
            "failing_sources": sources,
            "queries": queries,
            "fallback_channel": fallback,
            "acceptance": acceptance,
        })

    open_tasks = [t for t in tasks if t["status"] == "open"]
    open_blocking = [t for t in open_tasks if t.get("blocking")]
    return {
        "generated_at": datetime.now(SH_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "run_date": run_date,
        "target_window": report.get("target_window"),
        "gate_pass_at_generation": report.get("summary", {}).get("gate_pass", False),
        "tasks_total": len(tasks),
        "tasks_open": len(open_tasks),
        # 阻断 gate 的开放任务（整面失明）。window_partial 不在其中：
        # 它不阻断交付，但必须给出"那段时间有没有东西"的结论后才能关闭。
        "tasks_blocking_open": len(open_blocking),
        "tasks_action_open": len(open_tasks) - len(open_blocking),
        "tasks": tasks,
    }


def mark_done(bundle: dict, task_id: str, note: str,
              findings: list | None = None) -> dict:
    for t in bundle["tasks"]:
        if t["id"] == task_id:
            t["status"] = "done"
            t["note"] = note
            t["findings"] = findings or []
            break
    open_tasks = [t for t in bundle["tasks"] if t["status"] == "open"]
    bundle["tasks_open"] = len(open_tasks)
    bundle["tasks_blocking_open"] = sum(1 for t in open_tasks if t.get("blocking"))
    bundle["tasks_action_open"] = bundle["tasks_open"] - bundle["tasks_blocking_open"]
    return bundle


def print_tasks(bundle: dict) -> None:
    print(f"\n补检任务  total={bundle['tasks_total']}  open={bundle['tasks_open']}"
          f"  (blocking={bundle.get('tasks_blocking_open', 0)}"
          f" / action={bundle.get('tasks_action_open', 0)})")
    for t in bundle["tasks"]:
        flag = "OPEN" if t["status"] == "open" else "done"
        print(f"\n[{flag}] {t['id']} {t['priority']} {t['entity']}/{t['surface']} "
              f"({t['type']})")
        print(f"   失败源: {t['failing_source']} → {t['failing_verdict']}")
        for q in t["queries"]:
            print(f"   query: {q}")
        if t["fallback_channel"]:
            print(f"   换通道: {t['fallback_channel']}")
        print(f"   验收: {t['acceptance']}")


def main():
    ap = argparse.ArgumentParser(description="覆盖缺口 → 补检任务")
    ap.add_argument("--report", required=True, help="collect_report.json 路径")
    ap.add_argument("--out", default="gap_tasks.json")
    ap.add_argument("--mark-done", default="", help="标记完成的任务 ID")
    ap.add_argument("--note", default="", help="完成说明")
    args = ap.parse_args()

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    out = Path(args.out)

    if args.mark_done:
        if not out.exists():
            print(f"{out} 不存在，无法标记")
            return 2
        bundle = json.loads(out.read_text(encoding="utf-8"))
        bundle = mark_done(bundle, args.mark_done, args.note)
    else:
        bundle = build_tasks(report, report.get("run_date", ""))

    out.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    print_tasks(bundle)
    print(f"\n任务文件: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
