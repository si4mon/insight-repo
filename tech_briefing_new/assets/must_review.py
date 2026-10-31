#!/usr/bin/env python3
"""必审清单：候选池里哪些条目必须逐条留痕。

候选池一轮 2000+ 条，逐条台账不可执行；全凭模型自行取舍，则同一窗口不同
模型会漏掉不同的事件（2026-10-30 回测：一份报告漏掉 Glance、VeriCUA、
Claude Code 2.1.314，另一份漏掉 Masked Erosion，都不是判断分歧，而是根本
没看到）。折中方案是分层：

  清单内  —— 强制逐条留痕，必须在 8.2（入选）或 8.3（丢弃 + 封闭集合理由）出现；
  清单外  —— 按池筛规则统计留痕，不要求逐条。

清单只决定"要不要留痕"，不决定评级，也不做任何价值判断。

用法:
    python3 must_review.py --raw-dir raw_2026-10-31 --out must_review.json
门禁:
    verify_gates.py 读 must_review.json，核对每一条都已留痕。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import build_pool

# 这些阈值决定人工复核的工作量，改动要同步 references/must-review.md
HN_MIN_POINTS = 50      # HN 条目进清单的最低分数
ARXIV_TOP_K = 40        # arXiv 按打分取前 K 篇

TIERS = ("T1_official", "T2_hf_papers", "T3_hn", "T4_techmeme",
         "T5_cn_media", "T6_arxiv")

# 趋势榜单类源不是事件源：同一批条目会连日在场，进必审只会每天重复一遍
_RANKING_SRCS = {"hf_trending_models", "gh_trending"}


def load_terms(path: Path | None) -> dict:
    if path and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    for cand in (Path(__file__).parent.parent / "data" / "review_terms.json",
                 Path(__file__).parent / "review_terms.json"):
        if cand.exists():
            return json.loads(cand.read_text(encoding="utf-8"))
    raise SystemExit("找不到 review_terms.json（词表缺失则清单不可复算）")


def _text(row: dict) -> str:
    return f"{row.get('title') or ''} {row.get('snippet') or ''}".lower()


def is_ai_relevant(row: dict, terms: dict) -> str:
    """返回命中的词，未命中返回空串。宁宽勿窄：漏判整条不留痕。"""
    t = _text(row)
    rel = terms["ai_relevance"]
    for w in rel["en"]:
        if w in t:
            return w
    for w in rel["zh"]:
        if w in t:
            return w
    return ""


def hn_points(row: dict) -> int | None:
    m = re.search(r"points=(\d+)", row.get("snippet") or "")
    return int(m.group(1)) if m else None


def arxiv_score(row: dict, terms: dict) -> tuple[int, list[str]]:
    """arXiv 打分：high 2 分 / med 1 分 / 新公告 1 分。分值只用于排序取前 K。"""
    t = _text(row)
    hits, score = [], 0
    for w in terms["arxiv_score"]["high"]:
        if w in t:
            score += 2
            hits.append(w)
    for w in terms["arxiv_score"]["med"]:
        if w in t:
            score += 1
            hits.append(w)
    if row.get("announce_type") == "new":
        score += 1
        hits.append("announce:new")
    return score, hits


def _fresh_enough(row: dict) -> bool:
    """窗口内，或无日期但本轮才出现。carried_over 的无日期条目不进清单。"""
    if row.get("in_window") is True:
        return True
    if row.get("window_match") == "no_date":
        return row.get("freshness") == "new_since_last_run"
    return False


def build(in_pool: list[dict], terms: dict,
          hn_min_points: int = HN_MIN_POINTS,
          arxiv_top_k: int = ARXIV_TOP_K) -> dict:
    rows: list[dict] = []

    def add(row, tier, why):
        rows.append({
            "tier": tier,
            "uid": row.get("uid") or "",
            "src": row.get("src") or "",
            "channel": row.get("channel") or "",
            "title": (row.get("title") or "").strip(),
            "url": row.get("url") or "",
            "published": row.get("published") or "",
            "why": why,
        })

    arxiv_scored: list[tuple[int, list[str], dict]] = []

    for row in in_pool:
        src = row.get("src") or ""
        ch = row.get("channel") or ""
        if src in _RANKING_SRCS:
            continue

        if src == "hf_daily_papers":
            # HF Daily Papers 是人工策划的当日论文榜，量小且信噪比高，全部必审
            add(row, "T2_hf_papers", "HF Daily Papers 全量必审")
            continue

        if ch == "B_arxiv":
            if _fresh_enough(row):
                sc, hits = arxiv_score(row, terms)
                arxiv_scored.append((sc, hits, row))
            continue

        if not _fresh_enough(row):
            continue

        if ch in ("A_entity", "G_official_surface"):
            add(row, "T1_official", f"官方首发面（{ch}）条目全量必审")
            continue

        if src in ("hn_front", "hn_newest"):
            pts = hn_points(row)
            hit = is_ai_relevant(row, terms)
            if hit and pts is not None and pts >= hn_min_points:
                add(row, "T3_hn", f"HN points={pts}≥{hn_min_points}，命中「{hit}」")
            continue

        if src == "techmeme":
            hit = is_ai_relevant(row, terms)
            if hit:
                add(row, "T4_techmeme", f"Techmeme 条目命中「{hit}」")
            continue

        if ch == "F_cn_media":
            hit = is_ai_relevant(row, terms)
            if hit:
                add(row, "T5_cn_media", f"中文媒体条目命中「{hit}」")
            continue

    arxiv_scored.sort(key=lambda x: (-x[0], x[2].get("uid") or ""))
    cutoff = arxiv_scored[arxiv_top_k - 1][0] if len(arxiv_scored) >= arxiv_top_k else None
    for sc, hits, row in arxiv_scored[:arxiv_top_k]:
        add(row, "T6_arxiv",
            f"arXiv 打分 {sc}（前 {arxiv_top_k}，命中 {','.join(hits[:4])}）")

    # 同一条目可能被多个源召回（HN front 与 newest 是同一 uid）。台账按 uid 记，
    # 所以清单也按 uid 去重，否则"清单条数"与"台账条数"永远差几条，门禁没法比。
    dedup: dict[str, dict] = {}
    for r in rows:
        prev = dedup.get(r["uid"])
        if prev is None:
            dedup[r["uid"]] = r
        else:
            # 保留排序更靠前的层，另一层记在 also_tiers 里，不丢信息
            keep, drop = ((prev, r) if TIERS.index(prev["tier"]) <= TIERS.index(r["tier"])
                          else (r, prev))
            keep.setdefault("also_tiers", []).append(drop["tier"])
            keep.setdefault("also_srcs", []).append(drop["src"])
            dedup[r["uid"]] = keep
    rows = sorted(dedup.values(), key=lambda r: (TIERS.index(r["tier"]),
                                                 r.get("published") or ""))

    by_tier = {t: sum(1 for r in rows if r["tier"] == t) for t in TIERS}
    return {
        "generated_by": "must_review.py",
        "thresholds": {"hn_min_points": hn_min_points,
                       "arxiv_top_k": arxiv_top_k,
                       "arxiv_score_cutoff": cutoff},
        "pool_size": len(in_pool),
        "arxiv_candidates": len(arxiv_scored),
        "by_tier": by_tier,
        "total": len(rows),
        "items": rows,
    }


# 留痕处置的封闭集合。discarded 的理由与 task_def 8.3 一致。
DISPOSITIONS = {
    "selected": "入选为独立事件（必须给出 ev）",
    "merged": "并入其他事件（必须给出 ev）",
    "chapter5": "写入第 5 章（Active Event / Early Signal / 线索）",
    "discarded": "丢弃（必须给出封闭集合 reason）",
}
DISCARD_REASONS = (
    "未验证", "重复", "低影响", "首发早于 WINDOW_START", "首发晚于 WINDOW_END",
    "Active Event 非新事件", "错误年份", "媒体转载误判", "已并入其他事件",
    "技术命题未发生变化",
)


def trace_template(mr: dict) -> dict:
    """生成待填的逐条处置台账骨架。

    清单上百条不适合全部塞进 8.3（那一节是给人读的摘录），所以完整台账落在
    这份 JSON 里，8.3 仍按 task_def 的范围写 Tier-1 与共振条目。门禁核对的是
    这份台账的完整性——清单内一条没填，门禁就不过。
    """
    return {
        "_doc": "必审清单逐条处置台账。disposition ∈ "
                + "/".join(DISPOSITIONS)
                + "；discarded 的 reason 必须取 task_def 8.3 的封闭集合。",
        "must_review_total": mr["total"],
        "dispositions": {
            r["uid"]: {"disposition": "", "ev": "", "reason": "",
                       "_title": r["title"][:80], "_tier": r["tier"]}
            for r in mr["items"]
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="生成必审清单")
    ap.add_argument("--raw-dir", required=True)
    ap.add_argument("--out", default="must_review.json")
    ap.add_argument("--terms", default="")
    ap.add_argument("--hn-min-points", type=int, default=HN_MIN_POINTS)
    ap.add_argument("--arxiv-top-k", type=int, default=ARXIV_TOP_K)
    ap.add_argument("--trace-out", default="",
                    help="同时写出待填的逐条处置台账骨架（已存在则不覆盖）")
    args = ap.parse_args()

    terms = load_terms(Path(args.terms) if args.terms else None)
    in_pool, _ = build_pool.build(Path(args.raw_dir))
    out = build(in_pool, terms, args.hn_min_points, args.arxiv_top_k)
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    print(f"必审清单 {out['total']} 条 → {args.out}")
    for t in TIERS:
        print(f"  {t:14} {out['by_tier'][t]:4}")
    print(f"  （arXiv 候选 {out['arxiv_candidates']} 篇，分数截断于 "
          f"{out['thresholds']['arxiv_score_cutoff']}）")

    if args.trace_out:
        tp = Path(args.trace_out)
        if tp.exists():
            print(f"台账已存在，不覆盖: {tp}（要重建先删掉）")
        else:
            tp.write_text(json.dumps(trace_template(out), ensure_ascii=False,
                                     indent=2), encoding="utf-8")
            print(f"待填台账 → {tp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
