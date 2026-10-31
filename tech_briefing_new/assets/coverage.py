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
    if rec.get("extract") == "internal_error":
        return "INTERNAL_ERROR"
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
        # 归档回退补回来的批次要能被看见：8.1 里"靠回退才拿到"和"主通道正常"
        # 是两种不同的覆盖状况，合并成 OK_IN_WINDOW 会掩盖主通道的故障。
        return "OK_BATCH_FROM_ARCHIVE" if rec.get("from_archive") else "OK_IN_WINDOW"
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
    "OK_BATCH_FROM_ARCHIVE": "主通道 0 条，改读归档页后取到窗口内批次",
    "INTERNAL_ERROR":   "采集器自身异常（代码缺陷），不是源不可达",
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
BLIND_VERDICTS = {"TRANSPORT_FAIL", "PROXY_BLOCKED", "PARSE_FAILED", "EMPTY",
                  "INTERNAL_ERROR"}


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
        if v in ("OK_IN_WINDOW", "OK_NEW_VIA_DIFF", "OK_BATCH_FROM_ARCHIVE"):
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
        if v in ("OK_IN_WINDOW", "OK_NEW_VIA_DIFF", "OK_BATCH_FROM_ARCHIVE"):
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
                    continue  # 已在 UNCOVERABLE 登记；整实体失明的情况在下面单独产出任务
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

    # 2b. 整实体失明：Tier-1 实体没有任何一个面读到内容（全部登记不可达或全部失明）。
    # 登记不可达只说明"官方面看不到"，不说明"这个实体今天没动静"——必须每天用检索补。
    # 不阻断交付，但作为 action 任务必须关闭（给出"有 N 条 / 确认 0 条"的结论）。
    seen_ok = {k.split("/", 1)[0] for k, v in surfaces.items() if v.get("checked", 0) > 0}
    terms = {}
    for u in uncoverable:
        terms.setdefault(u["entity"], []).extend(u.get("search_terms") or [u["entity"]])
    for entity in required_surfaces:
        if entity == "default" or entity in seen_ok:
            continue
        if all((entity, s_) in unc for s_ in required_surfaces[entity]):
            gaps.append({
                "type": "entity_blind", "blocking": False, "action_required": True,
                "entity": entity, "surface": "company", "source": "",
                "verdict": "ENTITY_BLIND",
                "search_terms": terms.get(entity, [entity]),
                "suggestion": f'"{entity}" 官方面全部不可达，按 search_terms 检索 SCAN_WINDOW 内的发布',
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
