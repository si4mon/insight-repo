"""测试共用的装置构造器。

评级改为由五维评分派生、战略相关度改为由根技术命中派生之后，几乎每个造事件的
测试都要同时给出互相一致的 scoring 与 root_tech。放在一处，免得三份测试各写一遍
又各自漂移。不以 test_ 开头，所以 unittest discover 不会把它当测试收集。
"""
from __future__ import annotations

import scoring as _sc
import root_tech as _rt

# 派生值等于键名的评分计划：(权威, 影响, 机制, 量化, 战略)
_PLAN = {"A+": (2, 2, 2, 2, 2), "A": (2, 2, 2, 1, 1),
         "B": (1, 1, 1, 1, 1), "C": (0, 0, 0, 0, 0)}


def scoring_for(rating: str) -> dict:
    out = {}
    for dim, v in zip(_sc.DIMENSIONS, _PLAN[rating]):
        out[dim] = {"score": v, "evidence": "固定装置" if v else ""}
    return out


def adjacency_of(scoring: dict) -> int:
    return int((scoring.get("strategic_adjacency") or {}).get("score", 0))


def rt_hits(adj: int) -> list:
    """造与 adjacency 分值一致的根技术命中：2 = 切换信号证据，1 = 当前代进展。"""
    if not adj:
        return []
    root = _rt.load()["roots"][0]
    h = {"id": _rt.PREFIX + root["id"], "why": "固定装置"}
    if adj >= 2:
        h.update(relation="switch_evidence", direction="supports",
                 signal_quote=root["switch_signal"])
    else:
        h.update(relation="current_gen")
    return [h]


def leaf0() -> str:
    """第一条根技术的核心叶子——用它当 primary_path，落点就不会不一致。"""
    return (_rt.load()["roots"][0].get("leaves_core") or ["B1.1"])[0]


def decorate(ev: dict, rating: str | None = None) -> dict:
    """给事件补上互相一致的 scoring / root_tech / primary_path。"""
    r = rating or ev.get("rating") or "A+"
    ev.setdefault("scoring", scoring_for(r))
    adj = adjacency_of(ev["scoring"])
    ev.setdefault("root_tech", rt_hits(adj))
    if adj:
        ev["primary_path"] = leaf0()
    ev.setdefault("first_party_source", True)
    return ev
