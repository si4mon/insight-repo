#!/usr/bin/env python3
"""五维评分与评级派生。

为什么评级不能由模型直接给：2026-10-30 同一窗口，三份报告对同一批事件给出的
评级分布是 A+1/A7、A+1/A6、A+1/A8，但重叠的事件只有 4 个——不是标准严不严的
差别，是每份报告各自在心里拿了一把不同的尺子。其中一份把 OpenAI 融资缩水、
Intel 暴跌、S&P 下调 Meta 评为 A/B，与 Cursor 投毒并列，技术简报于是变成了
市场简报。

所以：模型给五个维度的分和证据，评级由本模块按固定规则派生。模型可以不同意
派生结果，但必须去改某一维的分并写出理由，而不是直接改评级。
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

DIMENSIONS = (
    "source_authority",       # 首发源的权威性与独立性
    "magnitude",              # 影响面
    "mechanism_novelty",      # 机制新颖度
    "quantitative_evidence",  # 可核量化证据
    "strategic_adjacency",    # 战略相关度（按根技术清单，见 references/root-tech-scoring.md）
)

# 事件类别。后四类是"非技术命题"类，受硬上限约束。
EVENT_CLASSES = {
    "technical": "技术事件：发布、机制、实证、事故",
    "funding": "融资、估值、并购",
    "market": "股价、营收、评级、产能、债市",
    "regulatory": "立法、诉讼、监管、合规裁决",
    "opinion": "观点、评论、预测、人事",
}
CAPPED_CLASSES = ("funding", "market", "regulatory", "opinion")

RATINGS = ("A+", "A", "B", "C")

# 聚合与社交源不是首发源：它们的条目指向别处。证据独立性按被指向的那个域计。
AGGREGATOR_HOSTS = {
    "news.ycombinator.com", "ycombinator.com", "techmeme.com",
    "reddit.com", "x.com", "twitter.com", "t.co", "bsky.app",
    "news.google.com", "flipboard.com", "hn.algolia.com",
}
# 同一篇原文的镜像/策展层：折叠到原始域，不单独计数。
# (可注册域, 路径前缀或 "" 表示整域, 折叠到)
MIRROR_RULES = (
    ("huggingface.co", "/papers", "arxiv.org"),   # HF Papers 是 arXiv 的策展层
    ("alphaxiv.org", "", "arxiv.org"),
    ("paperswithcode.com", "", "arxiv.org"),
    ("arxiv.org", "", "arxiv.org"),
)


def _fold_mirror(url: str, dom: str) -> str:
    path = urlsplit(url).path or "/"
    for host, prefix, canon in MIRROR_RULES:
        if dom == host and (not prefix or path.startswith(prefix)):
            return canon
    return dom


def registrable(url: str) -> str:
    """取可注册域。够用就好：这里只需要把 blog.x.com 与 x.com 归成一个。"""
    host = (urlsplit(url).netloc or "").lower().split(":")[0]
    host = host[4:] if host.startswith("www.") else host
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    # 处理 co.uk / com.cn 这类二级后缀
    if parts[-2] in ("co", "com", "org", "net", "gov", "edu", "ac") and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def independent_sources(urls: list[str]) -> list[str]:
    """归并后的独立首发源域名列表。

    一份报告用 HN 上 876 / 655 / 399 三个帖子论证"多源共振"从而给出 A+，而三帖
    指向的是同一篇 Phorion 分析——那是一个源，不是三个。归并规则：
      - 聚合/社交域本身不计（它们不是首发源）；
      - 已知镜像域折叠到原始域；
      - 其余按可注册域去重。
    """
    out: list[str] = []
    for u in urls:
        if not isinstance(u, str) or not u.startswith("http"):
            continue
        dom = registrable(u)
        if dom in AGGREGATOR_HOSTS:
            continue
        dom = _fold_mirror(u, dom)
        if dom not in out:
            out.append(dom)
    return out


def source_authority(independent: list[str], first_party: bool) -> int:
    """一手官方首发，或 ≥2 个独立首发源 → 2；单一非一手源 → 1；无可定位首发 → 0。"""
    if not independent:
        return 0
    if first_party or len(independent) >= 2:
        return 2
    return 1


def total(scores: dict) -> int:
    return sum(int(scores.get(d, {}).get("score", 0)) for d in DIMENSIONS)


def _s(scores: dict, dim: str) -> int:
    return int(scores.get(dim, {}).get("score", 0))


def derive_rating(scores: dict, event_class: str = "technical",
                  has_thesis: bool = False) -> tuple[str, str]:
    """返回 (评级, 判据)。判据写进事件 JSON，供复核。"""
    t = total(scores)
    nov = _s(scores, "mechanism_novelty")
    adj = _s(scores, "strategic_adjacency")

    if t >= 9 and nov == 2 and adj == 2:
        rating, why = "A+", f"总分 {t}，机制新颖度与战略相关度均为 2"
    elif t >= 8 and nov >= 1 and adj >= 1:
        rating, why = "A", f"总分 {t}，机制新颖度 {nov}、战略相关度 {adj} 均 ≥1"
    elif t >= 4:
        rating, why = "B", f"总分 {t}"
    else:
        rating, why = "C", f"总分 {t}"

    # 硬上限：非技术命题类事件不因"影响大"而升到技术简报的高位。
    # Intel 暴跌的 Magnitude 与 Quantitative Evidence 都能拿满分，但它没有
    # 技术机制；没有这条上限，分数会把它抬到 A。
    if event_class in CAPPED_CLASSES:
        cap = "B" if (nov >= 1 and has_thesis) else "C"
        if RATINGS.index(rating) < RATINGS.index(cap):
            why = (f"{why}；受 {event_class} 类硬上限约束降至 {cap}"
                   + ("（已写出技术命题且有机制证据）" if cap == "B"
                      else "（未写出技术命题或无机制证据）"))
            rating = cap
    return rating, why


def validate(ev: dict) -> list[str]:
    """校验事件 JSON 的评分块。返回错误列表，空表示通过。"""
    eid = ev.get("event_id", "?")
    errs: list[str] = []
    sc = ev.get("scoring")
    if not isinstance(sc, dict):
        return [f"{eid}: 缺少 scoring 块（五维评分）"]

    for d in DIMENSIONS:
        cell = sc.get(d)
        if not isinstance(cell, dict):
            errs.append(f"{eid}: scoring.{d} 缺失")
            continue
        v = cell.get("score")
        if not isinstance(v, int) or not 0 <= v <= 2:
            errs.append(f"{eid}: scoring.{d}.score={v!r} 不在 0–2")
        if v and not str(cell.get("evidence") or "").strip():
            errs.append(f"{eid}: scoring.{d} 得 {v} 分但没写证据")

    cls = ev.get("event_class") or "technical"
    if cls not in EVENT_CLASSES:
        errs.append(f"{eid}: event_class={cls!r} 不在封闭集合 {sorted(EVENT_CLASSES)}")
        cls = "technical"

    # 独立首发源必须与事件链接归并后的结果一致——不能自报一个更大的数字
    declared = ev.get("independent_sources")
    urls = [str(ev.get("source") or ""), str(ev.get("canonical_source") or "")]
    urls += [str(c.get("url")) for c in (ev.get("claims") or [])
             if isinstance(c, dict) and c.get("url")]
    urls += [str(u) for u in (ev.get("corroborating_urls") or [])]
    computed = independent_sources(urls)
    if declared is not None:
        extra = [d for d in declared if d not in computed]
        if extra:
            errs.append(f"{eid}: independent_sources 多报 {extra}，"
                        f"按链接归并只有 {computed}")

    sa = _s(sc, "source_authority")
    if sa == 2 and len(computed) < 2 and not ev.get("first_party_source"):
        errs.append(f"{eid}: source_authority=2 需要一手官方首发或 ≥2 个独立首发源，"
                    f"归并后只有 {computed}")

    # Strategic Adjacency 由根技术命中列表派生，不由模型自报。
    # 判据见 references/root-tech-scoring.md：命中切换信号 2 分、当前代进展 1 分。
    adj = _s(sc, "strategic_adjacency")
    hits = ev.get("root_tech")
    if adj and not hits:
        errs.append(f"{eid}: strategic_adjacency={adj} 但未写命中的根技术编号"
                    f"（事件 JSON 的 root_tech 字段）")
    elif hits:
        try:
            import root_tech as rt
            errs += [f"{eid}: {m}" for m in
                     rt.validate_hits(hits, str(ev.get("primary_path") or ""))]
            want = rt.derive_adjacency(hits)
            if adj != want:
                errs.append(f"{eid}: strategic_adjacency={adj} 与根技术命中派生值 "
                            f"{want} 不一致；要改分就去改 relation 并写证据")
            for cid in rt.candidate_hits(hits):
                errs.append(f"{eid}: {cid} 是候选根，只记录不计分，"
                            f"命中应写入第 5 章而不是 root_tech")
        except Exception as e:
            errs.append(f"{eid}: 根技术清单不可用（{e}）")

    want, why = derive_rating(sc, cls, bool(str(ev.get("product_to_thesis") or "").strip()))
    if ev.get("rating") and ev["rating"] != want:
        errs.append(f"{eid}: rating={ev['rating']} 与派生值 {want} 不一致（{why}）。"
                    f"要改评级就去改某一维的分并写理由，不要直接改 rating")
    return errs


# ----- 成对排序 -----

def pair_candidates(events: list[dict], band: int = 1) -> list[tuple[str, str]]:
    """列出需要两两比较的候选对：总分相差 ≤ band 的相邻事件。

    模型在"这两条谁更改变技术判断"上比在绝对分值上稳定得多。Top N 的次序因此
    不直接按总分排，而是对分数接近的相邻对做一次显式比较。
    """
    ranked = sorted(events, key=lambda e: -total(e.get("scoring") or {}))
    pairs = []
    for a, b in zip(ranked, ranked[1:]):
        ta = total(a.get("scoring") or {})
        tb = total(b.get("scoring") or {})
        if ta - tb <= band:
            pairs.append((a.get("event_id", "?"), b.get("event_id", "?")))
    return pairs


def apply_pairwise(order: list[str], decisions: list[dict]) -> list[str]:
    """按成对比较结果调整次序。

    decisions: [{"pair": ["EV-03","EV-05"], "winner": "EV-05", "why": "..."}]
    只做相邻交换：一次比较只表达"这两条谁更靠前"，不足以支撑整体重排。
    """
    out = list(order)
    for d in decisions:
        pair = d.get("pair") or []
        w = d.get("winner")
        if len(pair) != 2 or w not in pair:
            continue
        loser = pair[0] if pair[1] == w else pair[1]
        if w not in out or loser not in out:
            continue
        iw, il = out.index(w), out.index(loser)
        if iw > il:
            out[il], out[iw] = out[iw], out[il]
    return out
