#!/usr/bin/env python3
"""根技术清单的加载与校验，供 Strategic Adjacency 一维使用。

数据：`data/root_tech.json`（由《小艺业务部根技术清单_26年刷新版》转换）。
规则：`references/root-tech-scoring.md`。

为什么战略相关度挂在根技术清单上，而不是另写一份"关注领域"：关注领域只能回答
"这条新闻跟我们有不有关"，各自理解，方差不收敛。根技术清单每一项都写了**切换
信号**——一个可证伪的条件，说明出现什么证据时投入应从当前代转向下一代。那正好
是事件价值的判据：一个事件值不值 A，取决于它是否构成某项根技术切换信号的证据。
"""
from __future__ import annotations

import json
from pathlib import Path

PREFIX = "RT:"      # 根技术编号与 taxonomy 叶子编号有 11 处重名，必须带前缀区分

_SEARCH = (
    Path(__file__).parent.parent / "data" / "root_tech.json",
    Path(__file__).parent / "root_tech.json",
)

RELATIONS = {
    "switch_evidence": "构成切换信号的证据（支持或否证），计 2 分",
    "current_gen": "当前代进展，不改变代际判断，计 1 分",
}
DIRECTIONS = ("supports", "contradicts")

_CACHE: dict | None = None


class RootTechError(Exception):
    pass


def load(path: Path | None = None) -> dict:
    global _CACHE
    if path is None and _CACHE is not None:
        return _CACHE
    cands = (path,) if path else _SEARCH
    for p in cands:
        if p and p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            index = {r["id"]: r for r in data.get("roots") or []}
            cand_index = {r["id"]: r for r in data.get("candidates") or []}
            out = {**data, "index": index, "candidate_index": cand_index}
            if path is None:
                _CACHE = out
            return out
    raise RootTechError(f"找不到 root_tech.json（查过 {[str(p) for p in cands]}）")


def strip_prefix(rid: str) -> str:
    return rid[len(PREFIX):] if rid.startswith(PREFIX) else rid


def resolve(rid: str, data: dict | None = None) -> dict:
    """取根技术条目。编号必须带 RT: 前缀。"""
    data = data or load()
    if not str(rid).startswith(PREFIX):
        raise RootTechError(
            f"{rid!r} 缺 RT: 前缀。根技术编号与 taxonomy 叶子编号有 11 处重名"
            f"（根技术 B1.1 = 个人媒体语料检索，叶子 B1.1 = 判断与动作选择），"
            f"不加前缀两者会混用")
    bare = strip_prefix(rid)
    if bare in data["index"]:
        return data["index"][bare]
    if bare in data["candidate_index"]:
        raise RootTechError(f"{rid} 是候选根（只记录不计分，命中写入第 5 章）")
    raise RootTechError(f"{rid} 不在根技术清单里")


def score_for(relation: str) -> int:
    return {"switch_evidence": 2, "current_gen": 1}.get(relation, 0)


def validate_hits(hits, primary_path: str = "", data: dict | None = None) -> list[str]:
    """校验事件 JSON 的 root_tech 命中列表。返回错误列表。"""
    data = data or load()
    errs: list[str] = []
    if hits is None:
        return errs
    if not isinstance(hits, list):
        return ["root_tech 应为列表"]
    for h in hits:
        if not isinstance(h, dict):
            errs.append(f"root_tech 条目应为对象，实际 {h!r}")
            continue
        rid = str(h.get("id") or "")
        try:
            root = resolve(rid, data)
        except RootTechError as e:
            errs.append(str(e))
            continue
        rel = h.get("relation") or ""
        if rel not in RELATIONS:
            errs.append(f"{rid}: relation={rel!r} 不在 {sorted(RELATIONS)}")
            continue
        if rel == "switch_evidence":
            if h.get("direction") not in DIRECTIONS:
                errs.append(f"{rid}: switch_evidence 必须声明 direction "
                            f"∈ {DIRECTIONS}（否证与支持同分，但要分清）")
            quote = str(h.get("signal_quote") or "").strip()
            want = str(root.get("switch_signal") or "").strip()
            if not quote:
                errs.append(f"{rid}: switch_evidence 必须引用切换信号原文")
            elif quote != want:
                errs.append(f"{rid}: signal_quote 与清单原文不一致。"
                            f"清单写的是「{want}」")
        if not str(h.get("why") or "").strip():
            errs.append(f"{rid}: 缺 why（一句话说明事件如何构成该信号的证据）")
        # 叶子落点不一致时允许，但必须在 why 里讲清楚理由
        if primary_path:
            leaves = set(root.get("leaves_core") or []) | set(root.get("leaves_related") or [])
            if leaves and primary_path not in leaves:
                if "落点" not in str(h.get("why") or ""):
                    errs.append(
                        f"{rid}: 事件 primary_path={primary_path} 不在该根技术的"
                        f"叶子集合 {sorted(leaves)} 内，why 里要写明落点为何不一致")
    return errs


def derive_adjacency(hits) -> int:
    """Strategic Adjacency 得分由命中列表派生，不由模型自报。"""
    if not hits:
        return 0
    return max((score_for((h or {}).get("relation", "")) for h in hits
                if isinstance(h, dict)), default=0)


def candidate_hits(hits, data: dict | None = None) -> list[str]:
    """命中的候选根（B6.x）。只记录不计分，写入第 5 章作为候选根升格信号。"""
    data = data or load()
    out = []
    for h in hits or []:
        if isinstance(h, dict):
            bare = strip_prefix(str(h.get("id") or ""))
            if bare in data["candidate_index"]:
                out.append(bare)
    return out
