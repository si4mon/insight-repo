#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gate 校验器：把"必须满足的条件"变成机器可判的 pass/fail。

修机制缺陷 M5：此前 18 条验收清单写在 SKILL.md 里，由 LLM 自己读完 HTML
再自证"已通过"。LLM 自证有两个问题：
  1. 它倾向于报告通过（确认偏误），失败不会被发现；
  2. 检查项是自然语言，没有可执行的判定逻辑，等于没检查。

本脚本只做机器能确定的事，不代替人工判断：
  - 采集层：覆盖 gate（每个必须实体×面是否读到内容）、补检任务是否清空
  - 文档层：Markdown 源的结构、时间窗口一致性、8.2 事件时刻落在窗口内；
            渲染出的 HTML 只做轻量存在性断言
  - 追溯层：事件已规范化、A/A+ 有 claims
  - registry 层：召回由工具生成、本轮已入库、第 7 章引用与 registry 派生值一致

用法：
  python verify_gates.py --report raw_2026-10-23/collect_report.json
  python verify_gates.py --raw-dir raw_2026-10-23 \\
      --md reports/<标题 slug>-2026-10-22.md --events events_run_2026-10-22/
退出码：0 全部通过；1 有 FAIL；2 参数错误
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from taxonomy import AmbiguousPath, TAXONOMY, TaxonomyError  # noqa: E402
import sources as src_reg  # noqa: E402

SH_TZ = timezone(timedelta(hours=8))
EV_ID_RE = re.compile(r"EV-\d+")


class Check:
    def __init__(self):
        self.results = []

    def add(self, gate, name, ok, detail=""):
        self.results.append({"gate": gate, "name": name,
                             "status": "PASS" if ok else "FAIL", "detail": detail})

    def warn(self, gate, name, detail=""):
        self.results.append({"gate": gate, "name": name,
                             "status": "WARN", "detail": detail})

    @property
    def failed(self):
        return [r for r in self.results if r["status"] == "FAIL"]

    def print(self):
        by_gate = {}
        for r in self.results:
            by_gate.setdefault(r["gate"], []).append(r)
        for gate, items in by_gate.items():
            nf = sum(1 for i in items if i["status"] == "FAIL")
            nw = sum(1 for i in items if i["status"] == "WARN")
            print(f"\n[{gate}]  {len(items)-nf-nw} pass / {nf} fail / {nw} warn")
            for i in items:
                if i["status"] != "PASS":
                    mark = "x" if i["status"] == "FAIL" else "!"
                    print(f"   {mark} {i['name']}: {i['detail'][:160]}")
        print("\n" + "=" * 72)
        if self.failed:
            print(f"GATE FAIL — {len(self.failed)} 项未通过")
        else:
            print("GATE PASS — 全部检查通过")
        print("=" * 72)


# ---------- 采集层 ----------
def check_collection(c: Check, report: dict, gap_tasks_path: Path | None):
    s = report.get("summary", {})

    c.add("collection", "采集脚本已运行",
          report.get("summary") is not None, "")
    c.add("collection", "存在传输成功的源",
          s.get("sources_transport_ok", 0) > 0,
          f"transport_ok={s.get('sources_transport_ok',0)}")
    c.add("collection", "存在可提取条目的源",
          s.get("sources_extract_ok", 0) > 0,
          f"extract_ok={s.get('sources_extract_ok',0)}")
    c.add("collection", "窗口内有条目",
          s.get("items_in_window", 0) > 0,
          f"items_in_window={s.get('items_in_window',0)}")

    # 阻断性缺口：以 gap_tasks.json 为准，而不是 collect_report.json。
    # collect_report 记录的是"采集时刻发现了哪些缺口"（快照，不会因补检而改变）；
    # gap_tasks 记录的是"这些缺口现在处理到哪一步"（活状态）。
    # 用前者判定会导致：补检全部完成后 gate 永远 FAIL —— 它检查的是一个历史事实。
    blocking = [g for g in report.get("gaps", []) if g.get("blocking")]
    gt = None
    if gap_tasks_path and gap_tasks_path.exists():
        gt = json.loads(gap_tasks_path.read_text(encoding="utf-8"))

    if gt is not None:
        # 阻断缺口（整面失明）必须清零才能交付；
        # 窗口截断缺口（window_partial）不阻断交付，但同样必须有人给出
        # "那段时间到底有没有东西"的结论 —— 否则它只会躺在 note 里，
        # 永远不会出现在 8.3 的漏检回溯表上。
        # 旧版 gap_tasks.json 没有分档字段，按 tasks 现算，避免"缺字段 = 通过"。
        tasks = gt.get("tasks", [])
        open_tasks = [t for t in tasks if t.get("status") == "open"]
        blocking_open = sum(1 for t in open_tasks if t.get("blocking"))
        if "tasks_blocking_open" in gt:
            blocking_open = gt["tasks_blocking_open"]
        action_open = len(open_tasks) - blocking_open
        if "tasks_action_open" in gt:
            action_open = gt["tasks_action_open"]

        c.add("collection", "无未完成的阻断性缺口",
              blocking_open == 0,
              f"发现 {len(blocking)} 个阻断缺口，blocking_open={blocking_open}")
        c.add("collection", "无未完成的窗口截断补检",
              action_open == 0,
              f"action_open={action_open}"
              f"（窗口前半段未被检索的源，需给出补齐或 0 条结论）")
    else:
        c.add("collection", "无阻断性覆盖缺口",
              len(blocking) == 0,
              f"{len(blocking)} 个: " + ", ".join(
                  f"{g.get('entity')}/{g.get('surface')}" for g in blocking[:5])
              + "（未找到 gap_tasks.json，无法确认补检是否完成）")

    # 每个 critical 源必须读到内容
    crit_blind = [r for r in report.get("sources", [])
                  if r.get("critical") and r.get("verdict") in
                  ("TRANSPORT_FAIL", "PROXY_BLOCKED", "PARSE_FAILED", "EMPTY")]
    c.add("collection", "critical 源全部可用",
          len(crit_blind) == 0,
          ", ".join(r["id"] for r in crit_blind[:6]))

    # 代理拦截页必须被识别，不能算成功
    blocked = [r for r in report.get("sources", []) if r.get("verdict") == "PROXY_BLOCKED"]
    if blocked:
        c.warn("collection", "存在代理拦截源",
               ", ".join(r["id"] for r in blocked))

    # 静默截断
    partial = [r for r in report.get("sources", [])
               if r.get("covered_quality") == "partial"]
    c.add("collection", "无窗口覆盖不完整的 critical 源",
          not any(r.get("critical") for r in partial),
          ", ".join(r["id"] for r in partial[:6]))

    # 非 critical 源的窗口截断同样是漏检，只是不阻断交付。
    # 至少要有对应任务，否则"覆盖不完整"只存在于 report 里，正文看不到。
    if partial and gt is not None:
        covered = set()
        for t in gt.get("tasks", []):
            if t.get("type") != "window_partial":
                continue
            covered.update(t.get("failing_sources") or [t.get("failing_source")])
        missing = [r["id"] for r in partial if r["id"] not in covered]
        c.add("collection", "窗口截断源均已转为补检任务",
              not missing, ", ".join(missing[:6]))

    # 补检任务文件必须存在（阻断缺口须有对应任务）
    if blocking and gt is None:
        c.add("collection", "补检任务已生成", False,
              "存在阻断缺口但未生成 gap_tasks.json")


# ---------- 文档层 ----------
def _iso(s):
    try:
        dt = datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None
    # collect_report 的窗口串可能不带时区，统一补成 +08，否则与 8.2 表格里
    # 解析出的带时区 datetime 比较会抛 "can't compare offset-naive and
    # offset-aware datetimes"。
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=SH_TZ)
    return dt


def check_html_lightweight(c: Check, html_path: Path, report: dict):
    """MD 路线的 HTML 轻量断言。

    HTML 是 render_report.py 机械渲染的副本，DOM 结构随引擎版本变化，因此这里
    只校验"渲染确实发生了且产物是自包含 HTML"，不校验 DOM 结构；结构契约
    一律在 Markdown 源上校验（check_markdown / check_md_event_index）。
    """
    if not html_path.exists():
        c.add("html", "HTML 副本存在", False, str(html_path))
        return
    raw = html_path.read_text(encoding="utf-8", errors="ignore")
    size = len(raw)
    c.add("html", "HTML 副本 size > 0", size > 0, f"{size} bytes")
    c.add("html", "HTML 含 <title>", bool(re.search(r"<title[^>]*>", raw, re.I)), "")
    c.add("html", "HTML 内嵌源 Markdown",
          "source-md" in raw or "data-source-path" in raw,
          "渲染器应内嵌 <script id=\"source-md\">")
    ws = report.get("target_window", {}).get("start", "")
    if ws:
        c.add("html", "HTML 含窗口起始日期",
              ws[:10] in raw, f"expect {ws[:10]}")
    links = re.findall(r'href="(https?://[^"]+)"', raw)
    c.add("html", "HTML 原始来源链接 >= 10", len(set(links)) >= 10,
          f"{len(set(links))} unique links")


# ---------- 分类层 ----------
def check_taxonomy_definition(c: Check):
    """分类定义自身必须完整：54 叶子 / 11 栏目 / 8 章，且两张表互相一致。"""
    results = TAXONOMY.validate()
    bad = [r for r in results if not r["ok"]]
    c.add("taxonomy", "分类定义完整（54 叶子 / 11 栏目 / 8 章）",
          not bad,
          "; ".join(f"{r['name']}: {r['detail']}" for r in bad[:4]))


def check_source_coverage_definition(c: Check, report: dict | None = None):
    """
    Tier-1 实体必须"要么有源、要么登记不可达"，不允许静默缺失。

    这是 Kimi K3.1 Pro 漏检的根因：它在 ontology 的 tier1_entities 里，
    但既没登记源、也不在 REQUIRED_SURFACES，于是 coverage.build_gaps 的
    两条循环都不会访问它 —— 既不失明也不缺源，永远不产生缺口。
    """
    tier1 = [t for t in (TAXONOMY.ontology_tier1() if hasattr(TAXONOMY, "ontology_tier1") else [])]
    if not tier1:
        # taxonomy 不带 tier1，直接读 ontology
        raw = json.loads(TAXONOMY.ontology_path.read_text(encoding="utf-8"))
        tier1 = raw.get("tier1_entities", [])
    canonical = src_reg.TIER1_CANONICAL
    unmapped = [t for t in tier1 if t not in canonical]
    c.add("coverage", "tier1 实体都有源侧名字映射", not unmapped,
          f"未映射: {unmapped[:6]}")

    required = set(src_reg.REQUIRED_SURFACES) - {"default"}
    names = {canonical[t] for t in tier1 if t in canonical}
    drift = sorted(names.symmetric_difference(required))
    c.add("coverage", "REQUIRED_SURFACES 与 tier1_entities 一致", not drift,
          f"仅一侧存在: {drift[:8]}")

    built = src_reg.build_sources()
    have = {s["entity"] for s in built}
    registered = {(u["entity"], u["surface"]) for u in src_reg.UNCOVERABLE}
    # "有源"不区分 required：required=False 只表示"失败不阻断交付"，
    # 它仍然是一次真实采集，会在 report 里留下 verdict，
    # 因而 surface_coverage 能看见它。真正危险的是**一个源都没有**。
    silent = []
    for ent in required:
        for surf in src_reg.REQUIRED_SURFACES[ent]:
            if any(s["entity"] == ent and s["surface"] == surf for s in built):
                continue
            if (ent, surf) in registered:
                continue
            silent.append(f"{ent}/{surf}")
    c.add("coverage", "无静默实体×面（有源或已登记不可达）", not silent,
          f"{len(silent)} 个未登记: " + ", ".join(silent[:8]))

    # 不可达登记必须写补偿方式，并且未过复探期限（过期即强制重新探测该面）
    run_day = ((report or {}).get("target_window", {}).get("start") or "")[:10]
    no_comp, expired = [], []
    for u in src_reg.UNCOVERABLE:
        key = f"{u['entity']}/{u['surface']}"
        if not (u.get("compensate") and u.get("search_terms") and u.get("recheck_by")):
            no_comp.append(key)
        elif run_day and u["recheck_by"] < run_day:
            expired.append(f"{key}（{u['recheck_by']}）")
    c.add("coverage", "不可达登记写明了补偿方式与复探期限", not no_comp, ", ".join(no_comp[:6]))
    c.add("coverage", "不可达登记未过复探期限", not expired,
          "需重新探测并更新 sources.py: " + ", ".join(expired[:6]))

    if report is not None:
        # 报告里的实体是否覆盖了 tier1：不要求源成功，但要求"被尝试过"。
        # 已登记 UNCOVERABLE 且确实没有任何源的实体豁免——它们会在 8.1 里
        # 以"已登记不可达"出现，而不是以源的形态出现。
        seen = {s.get("entity") for s in report.get("sources", [])}
        no_source = {u["entity"] for u in src_reg.UNCOVERABLE}
        never = sorted(required - seen - no_source)
        c.add("coverage", "tier1 实体本轮均被尝试采集", not never,
              f"未出现在报告中: {never[:8]}")


def check_pool_retains_undated(c: Check, report: dict, pool_path: Path | None):
    """
    无日期源必须留下痕迹，不能被 `if not published: continue` 整源丢弃。

    HF Trending / GitHub Trending / Google Dev Blog 的条目没有 published 字段。
    它们承载"模型热度、新仓库、官方新工具"这类事件——按日期过滤会让
    整份报告的密度凭空下降，而且看不出少了什么（源状态仍是 OK_NO_DATES）。
    """
    # 这些 verdict 表示"读到了内容但无法按日期归窗"，条目仍须进池。
    # sitemap 例外：它只有 URL 没有标题，进池只会淹没真实条目，
    # 其用途是 surface diff，不是候选事件。
    undated_sources = {s["id"] for s in report.get("sources", [])
                       if s.get("verdict") in ("OK_NO_DATES", "OK_NEW_VIA_DIFF")
                       and s.get("items_total", 0) > 0
                       and s.get("mode") != "sitemap"}
    if not undated_sources:
        c.add("coverage", "无日期源条目已进入候选池", True, "无此类源")
        return

    if not pool_path or not pool_path.exists():
        c.warn("coverage", "未找到 candidate_pool.json", "跳过无日期源留存检查")
        return

    pool = json.loads(pool_path.read_text(encoding="utf-8"))
    in_pool = {x.get("src") for x in pool}
    missing = sorted(undated_sources - in_pool)
    c.add("coverage", "无日期源条目已进入候选池", not missing,
          f"整源缺失: {missing[:6]}（共 {len(undated_sources)} 个无日期源）")

    # sitemap 不得进池：它只有 URL、没有标题，会淹没真实条目
    sitemap_in_pool = sorted({x.get("src") for x in pool
                              if not (x.get("title") or "").strip()})
    c.add("coverage", "候选池不含无标题条目", not sitemap_in_pool,
          f"来自: {sitemap_in_pool[:4]}")


def _load_events(events_dir: Path | None) -> dict[str, dict]:
    if not events_dir or not events_dir.exists():
        return {}
    out = {}
    for f in sorted(events_dir.glob("EV-*.json")):
        try:
            out[f.stem] = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
    return out


def check_event_paths(c: Check, events_dir: Path | None):
    """
    每个事件的 primary_path 必须存在、可解析到栏目，且遵守归类精度规则。

    机器能判的只有形式约束（设计文档 §4.1/§4.2/§4.5）：
      必填、唯一、可解析、必须下钻的域不得停在二级、关联域 ≤2、变更对象合法。
    "归得对不对"仍要人看 —— 这里不假装能判语义。
    """
    events = _load_events(events_dir)
    if not events:
        c.warn("taxonomy", "未提供事件文件", "跳过 primary_path 检查")
        return

    missing, unknown, over_drill, too_many, bad_obj = [], [], [], [], []
    for eid, ev in events.items():
        path = ev.get("primary_path")
        if not path:
            missing.append(eid)
            continue
        try:
            TAXONOMY.resolve(path)
        except AmbiguousPath:
            over_drill.append(f"{eid}={path}")
        except TaxonomyError:
            unknown.append(f"{eid}={path}")

        rel = ev.get("related_domains") or []
        if len(rel) > TAXONOMY.rules()["max_related_domains"]:
            too_many.append(f"{eid}={len(rel)}")
        for r in rel:
            try:
                TAXONOMY.resolve(r)
            except TaxonomyError:
                unknown.append(f"{eid} related={r}")

        obj = ev.get("change_object")
        if obj not in TAXONOMY.change_objects():
            bad_obj.append(f"{eid}={obj}")

    c.add("taxonomy", "每个事件都有 primary_path", not missing,
          "缺: " + ", ".join(missing[:8]))
    c.add("taxonomy", "primary_path / related_domains 可解析", not unknown,
          ", ".join(unknown[:6]))
    c.add("taxonomy", "跨栏目的二级域已下钻到三级", not over_drill,
          ", ".join(over_drill[:6]))
    c.add("taxonomy", "关联技术域 <= 2", not too_many,
          ", ".join(too_many[:6]))
    c.add("taxonomy", "change_object 取值合法", not bad_obj,
          ", ".join(bad_obj[:6]))


def check_event_annotations(c: Check, events_dir: Path | None):
    """聚合栏目（4.6）的事件 JSON 必须写 annotation，且等于 primary_path 叶子对应的标签。

    标签与叶子一一对应（设计文档 §5.3），不能自选更宽或更窄的标签。
    只看事件 JSON，与正文写法无关；正文侧的标注义务由 check_markdown 校验。
    """
    events = _load_events(events_dir)
    if not events:
        return
    mismatch = []
    for eid, ev in events.items():
        path = ev.get("primary_path")
        if not path:
            continue
        try:
            col = TAXONOMY.resolve(path)
        except TaxonomyError:
            continue
        if not TAXONOMY.annotation_map(col):
            continue
        expect = TAXONOMY.annotation_label_for(path)
        if not expect:
            continue      # 叶子→标签映射由 taxonomy.validate 保证完整
        got = ev.get("annotation")
        if got != expect:
            mismatch.append(f"{eid} {path} 应标「{expect}」，实际「{got or '无'}」")
    c.add("taxonomy", "4.6 标注与 primary_path 一致", not mismatch,
          "; ".join(mismatch[:5]))


_RATING_OK = ("A+", "A", "B")
_MAINLINE = re.compile(r'^\s*(?:\d+\.|[-*])\s+\*\*')


def check_ch1_mainlines(c: Check, md_path: Path | None, events_dir: Path | None):
    """第 1 章的主线必须由技术事件支撑：每条至少引用 2 个 8.2 里的 EV。

    一条只靠感觉写出来的主线，读者无法回到证据；要求两个 EV，是因为一个事件
    撑不起"主线"这个词——那是单个事件，写在卡片里就够了。
    """
    if not (md_path and md_path.exists()):
        return
    text = md_path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r'^##\s+\S[^\n]*$', text, re.M)
    if not m:
        return
    seg = text[m.end():]
    nxt = re.search(r'^##\s+', seg, re.M)
    ch1 = seg[:nxt.start()] if nxt else seg

    lines = [ln for ln in ch1.splitlines() if _MAINLINE.match(ln)]
    if not lines:
        c.add("md", "第 1 章有主线", False,
              "第 1 章没找到主线条目（形如「1. **…**」）")
        return

    events = _load_events(events_dir)
    thin, missing, weak = [], [], []
    for ln in lines:
        ids = sorted(set(EV_ID_RE.findall(ln)))
        head = re.sub(r'\*+', '', ln).strip()[:28]
        if len(ids) < 2:
            thin.append(f"「{head}…」只引用 {len(ids)} 个 EV")
            continue
        for i in ids:
            if events and i not in events:
                missing.append(f"{head}…→{i}")
            elif events and events[i].get("rating") not in _RATING_OK:
                weak.append(f"{head}…→{i}({events[i].get('rating')})")

    c.add("md", "第 1 章主线各引用 ≥2 个 EV", not thin, "; ".join(thin[:4]))
    c.add("md", "第 1 章引用的 EV 都存在", not missing, "; ".join(missing[:4]))
    c.add("md", "第 1 章引用的 EV 评级不低于 B", not weak, "; ".join(weak[:4]))


def check_claim_evidence(c: Check, events_dir: Path | None, roots: list):
    """A/A+ 事件的每条 claim 必须绑定到快照里的原文片段。"""
    events = _load_events(events_dir)
    if not events:
        return
    try:
        import claim_evidence as cev
    except Exception as e:
        c.warn("trace", "claim 绑定原文片段", f"claim_evidence 不可用 {e}")
        return
    roots = [Path(r) for r in roots if r]
    if not roots:
        c.warn("trace", "claim 绑定原文片段", "未提供快照根目录，跳过比对")
        return
    errs, n = [], 0
    for eid, ev in sorted(events.items()):
        ev = {**ev, "event_id": ev.get("event_id") or eid}
        if cev.required_for(ev):
            n += 1
        errs += cev.verify(ev, roots)
    c.add("trace", "A/A+ 的 claim 绑定到快照原文片段", not errs,
          (f"{n} 个事件需绑定；" if n else "") + "; ".join(errs[:4]))


def check_root_tech_list(c: Check):
    """根技术清单自身的定义检查。

    战略相关度整维都挂在这份清单上，清单坏了整维就失效，所以每轮先查它。
    """
    try:
        import root_tech as rt
        data = rt.load()
    except Exception as e:
        c.add("taxonomy", "根技术清单可加载", False, str(e))
        return
    roots = data.get("roots") or []
    c.add("taxonomy", "根技术清单可加载", bool(roots),
          f"{len(roots)} 项根技术 + {len(data.get('candidates') or [])} 项候选根")

    ids = [r.get("id") for r in roots]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    c.add("taxonomy", "根技术编号唯一", not dup, f"重复: {dup[:5]}")

    no_signal = [r["id"] for r in roots if not str(r.get("switch_signal") or "").strip()]
    c.add("taxonomy", "每项根技术都有切换信号", not no_signal,
          f"缺切换信号: {no_signal[:5]}（切换信号是计 2 分的唯一判据）")

    bad_leaf = []
    for r in roots:
        for leaf in list(r.get("leaves_core") or []) + list(r.get("leaves_related") or []):
            try:
                TAXONOMY.resolve(leaf)
            except TaxonomyError:
                bad_leaf.append(f"{r['id']}→{leaf}")
    c.add("taxonomy", "根技术叶子落点在分类表内", not bad_leaf,
          "; ".join(bad_leaf[:5]))

    # 编号与叶子重名是已知事实（11 处），所以带 RT: 前缀是硬要求。
    # 这里断言前缀常量没被改掉，否则重名就会静默混用。
    c.add("taxonomy", "根技术编号带 RT: 前缀", rt.PREFIX == "RT:",
          f"PREFIX={rt.PREFIX!r}")


def check_scoring(c: Check, events_dir: Path | None, pairwise_path: Path | None):
    """评级必须由五维评分派生，且评分块自洽。

    2026-10-30 回测：一份报告把 OpenAI 融资缩水、Intel 暴跌、S&P 下调 Meta 评为
    A/B，与 Cursor 投毒并列。手给评级时没有任何机制能拦住这一类，所以评级改为
    由分数派生，这里核对事件产物是否遵守。
    """
    events = _load_events(events_dir)
    if not events:
        return
    try:
        import scoring
    except Exception as e:
        c.warn("trace", "评级可由评分派生", f"scoring 模块不可用 {e}")
        return

    errs, no_block = [], []
    for eid, ev in sorted(events.items()):
        ev = {**ev, "event_id": ev.get("event_id") or eid}
        if not ev.get("scoring"):
            no_block.append(eid)
            continue
        errs += scoring.validate(ev)

    c.add("trace", "事件都有五维评分块", not no_block,
          f"缺评分块: {', '.join(no_block[:6])}")
    c.add("trace", "评级可由评分派生且评分自洽", not errs, "; ".join(errs[:4]))

    # 非技术类事件的硬上限：这里只核对类别声明是否存在，上限由 derive_rating 施加
    unclassed = [eid for eid, ev in sorted(events.items())
                 if ev.get("scoring") and not ev.get("event_class")]
    if unclassed:
        c.warn("trace", "事件声明了 event_class",
                f"未声明（按 technical 处理，不受硬上限约束）: "
                f"{', '.join(unclassed[:6])}")

    # 成对比较：分差 ≤1 的相邻对必须有裁定，否则 Top N 的次序仍是绝对分直排
    evs = [{**ev, "event_id": eid} for eid, ev in sorted(events.items())
           if ev.get("scoring")]
    pairs = scoring.pair_candidates(evs)
    if not pairs:
        return
    decided = set()
    if pairwise_path and pairwise_path.exists():
        try:
            data = json.loads(pairwise_path.read_text(encoding="utf-8"))
            for d in data.get("decisions") or []:
                pr = d.get("pair") or []
                if len(pr) == 2 and d.get("winner") in pr and \
                        str(d.get("why") or "").strip():
                    decided.add(frozenset(pr))
        except Exception as e:
            c.add("trace", "成对比较可解析", False, f"{e}")
            return
    missing = [f"{a}/{b}" for a, b in pairs if frozenset((a, b)) not in decided]
    c.add("trace", "分数接近的候选已做成对比较", not missing,
          f"{len(missing)} 对未裁定: " + ", ".join(missing[:5])
          + ("（写进 pairwise.json，每对要有 winner 与 why）" if missing else ""))


# ---------- Markdown 通道 ----------
#
# MD 路线（render_report.py + report_engine）下，HTML 是机械渲染的副本，
# 不再承载结构契约。门禁改为直接校验 LLM 手写的 .md：
#
#   ## <章标题>            ← 八章之一（章号由顺序匹配 taxonomy.chapters()）
#   ### <栏目标题>          ← 三级锚点，对应 11 个栏目（"3.1 模型架构..." 形式）
#   #### <事件卡标题>       ← 四级标题即一张卡；A/A+ 卡必须含四节深拆
#   ##### 挑战与问题 / 机制与架构 / 效果与定量 / 对比其他方案的价值
#
# MD 是稳定的工作源，HTML 可能因渲染器升级而改 DOM；校验 MD 等于校验事实源
# 本身，不会被渲染器结构变更静默绕过。HTML 侧只保留 check_html_lightweight
# 的轻量断言（title/内嵌源/链接数/窗口日期），不做卡片切分。

_MD_HEADING = re.compile(r'^(#{1,6})\s+(.*?)\s*$', re.M)
_REQUIRED_DEEP_SECTIONS = ("挑战与问题", "机制与架构", "效果与定量", "对比其他方案的价值")


def _md_frontmatter(text: str) -> dict:
    m = re.match(r'^---\r?\n([\s\S]*?)\r?\n---\r?\n', text)
    if not m:
        return {}
    meta = {}
    for line in m.group(1).splitlines():
        mm = line.match(r'^([\w_-]+):\s*(.*)$') if False else re.match(r'^([\w_-]+):\s*(.*)$', line)
        if not mm:
            continue
        key, val = mm.group(1), mm.group(2).strip()
        if val.startswith('[') and val.endswith(']'):
            val = [s.strip().strip('"\'') for s in val[1:-1].split(',') if s.strip()]
        elif (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        meta[key] = val
    return meta


def _md_strip(fm_body: str) -> str:
    """去掉 frontmatter 与 markdown 语法残留，便于子串/链接检查。"""
    body = re.sub(r'^---\r?\n[\s\S]*?\r?\n---\r?\n', '', fm_body, count=1)
    # 去链接文本保留 URL，去图片，去强调标记
    body = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', body)
    body = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\2 \1', body)
    body = re.sub(r'[`*_>#|]', '', body)
    body = re.sub(r'\s+', ' ', body)
    return body.strip()


def _md_sections(text: str) -> list[tuple[int, str, str]]:
    """返回 [(级别, 标题, 偏移)]，级别=井号数。不含 frontmatter。"""
    body = re.sub(r'^---\r?\n[\s\S]*?\r?\n---\r?\n', '', text, count=1)
    out = []
    for m in _MD_HEADING.finditer(body):
        out.append((len(m.group(1)), m.group(2).strip(), m.start()))
    return out


def _md_section_body(text: str, start: int) -> str:
    """从某标题之后到下一个同级或更高级标题之间的正文。"""
    body = re.sub(r'^---\r?\n[\s\S]*?\r?\n---\r?\n', '', text, count=1)
    # 找当前标题级别
    m = _MD_HEADING.match(body, start)
    if not m:
        return ''
    level = len(m.group(1))
    after = m.end()
    nxt = re.search(rf'^#{{1,{level}}}\s+', body[after:], re.M)
    return body[after: after + nxt.start()] if nxt else body[after:]


def _md_column_id(title: str) -> str | None:
    """从 "3.1 模型架构..." 这类标题里取栏目编号。"""
    m = re.match(r'^\s*(\d+\.\d+)\b', title)
    return m.group(1) if m else None


def _md_card_event(title: str, body: str) -> str:
    """从卡片标题或标记区找 EV-NN 编号。

    只看标题 + body 前 200 字符的标记区（**A · Frontier · EV-04**），
    不扫整段正文 —— 正文深拆段落里出现的 EV 编号是交叉引用，
    把它当本卡事件会让「唯一主卡」检查把所有交叉引用都误判为重复。
    """
    m = EV_ID_RE.search(title)
    if m:
        return m.group(0)
    # 标记区：body 前 200 字符内、且 EV 编号出现在 **...** 标记里
    head = body[:200]
    mm = re.search(r'\*\*[^*]*\b(EV-\d+)\b[^*]*\*\*', head)
    return mm.group(1) if mm else ""


_RATINGS = ("A+", "A", "B", "C")


def _md_card_marker(body: str) -> str:
    """卡片标记区：body 前 200 字符里含 EV 编号的 **...** 段（去掉强调符号）。"""
    for seg in re.findall(r'\*\*([^*]+)\*\*', body[:200]):
        if EV_ID_RE.search(seg):
            return seg.strip()
    return ""


def _marker_rating(marker: str) -> str:
    first = re.split(r'[\s·|/]+', marker.strip())[0] if marker.strip() else ""
    return first if first in _RATINGS else ""


def _deep_dive_required(card: dict, events: dict, ws) -> bool:
    """深拆义务以事件 JSON 为准，不看卡片自报的文字（卡片写 B 或写 Convergence 都豁免不了）。

    承担义务：A / A+ 事件的主卡（分类栏目里的卡，或章 2 声明了归属的卡）。
    豁免：聚合卡（标记里有 ≥2 个 EV）、Active Event（首发早于 WINDOW_START 的背景事件）。
    没有事件文件时退回标记行的评级。
    """
    marker = _md_card_marker(card["body"])
    if len(set(EV_ID_RE.findall(marker))) >= 2:
        return False
    ev = events.get(card["eid"])
    if ev is None:
        return _marker_rating(marker) in ("A", "A+")
    if ev.get("rating") not in ("A", "A+"):
        return False
    fp = _iso(ev.get("first_publish_shanghai", ""))
    if ws is not None and fp is not None and fp < ws:
        return False
    return True


# 卡片在标记行里声明主栏目：**A · Frontier · EV-07 · 归属 4.5**
# 两种场景用它：栏目只有 1 条事件、折叠进相邻栏目（设计文档 §5.1）；
# 章 2 的 Top 卡承载唯一主卡、分类章只留交叉引用（SKILL P5）。
_DECL_RE = re.compile(r'归属\s*(\d+\.\d+)')


def _md_card_decl(body: str) -> str:
    """从卡片标记区（body 前 200 字符的 **...**）取「归属 N.M」声明。"""
    for seg in re.findall(r'\*\*([^*]+)\*\*', body[:200]):
        m = _DECL_RE.search(seg)
        if m:
            return m.group(1)
    return ""


def _md_layout(text: str) -> dict:
    """一次线性扫描切出分类栏目与章 2 焦点卡。

    每张卡用它在全文中的真实偏移取正文：此前按"栏目片段内偏移"去全文切片，
    只写在标记行里的 EV 编号会被读到错误位置而漏检。
    """
    known = set(TAXONOMY.column_ids())
    audit = {"8.1", "8.2", "8.3"}
    columns: dict[str, list[dict]] = {}   # 出现过 ### 标题的栏目 → 其下卡片（可为空）
    focus: list[dict] = []                # 章 2 中不在任何栏目下的卡片
    stray: list[str] = []
    chapter, cur = 0, None
    for level, title, off in _md_sections(text):
        if level <= 2:
            chapter += level == 2
            cur = None
        elif level == 3:
            cid = _md_column_id(title)
            if cid in known:
                cur = cid
                columns.setdefault(cid, [])
            else:
                if cid and cid not in audit:
                    stray.append(cid)
                cur = None
        elif level == 4:
            body = _md_section_body(text, off)
            eid = _md_card_event(title, body)
            if not eid:
                continue
            card = {"eid": eid, "decl": _md_card_decl(body), "body": body}
            if cur:
                columns[cur].append(card)
            elif chapter == 2:
                focus.append(card)
    return {"columns": columns, "focus": focus, "stray": stray, "known": known}


def _check_md_columns(c: Check, text: str, events_dir: Path | None):
    """分类呈现规则（设计文档 §5）：栏目合法、唯一主卡、主卡归位、空栏目、
    折叠声明、4.6 聚合栏目的标注义务。"""
    lay = _md_layout(text)
    columns, focus, known = lay["columns"], lay["focus"], lay["known"]

    c.add("taxonomy", "栏目编号均属 11 个栏目", not lay["stray"],
          f"未知栏目: {sorted(set(lay['stray']))}")

    # 折叠：声明的主栏目没有自己的 ### 小节时，这张卡才算折叠进来；
    # 主栏目已展开却声明归属它，说明卡写错了位置，按所在栏目计（随后报归位错误）。
    folded: dict[str, str] = {}
    ev_cols: dict[str, list[str]] = {}
    placed: list[tuple[str, dict]] = []    # (有效栏目, 卡片)
    for col, cards in columns.items():
        for card in cards:
            eff = col
            if card["decl"] and card["decl"] != col and card["decl"] not in columns:
                folded[card["eid"]] = card["decl"]
                eff = card["decl"]
            ev_cols.setdefault(card["eid"], []).append(eff)
            placed.append((eff, card))
    # 章 2 的卡片只有声明了归属才是主卡；未声明的是摘要卡，不计入。
    for card in focus:
        if card["decl"]:
            ev_cols.setdefault(card["eid"], []).append(card["decl"])
            placed.append((card["decl"], card))

    dup = {e: cols for e, cols in ev_cols.items() if len(set(cols)) > 1}
    c.add("taxonomy", "唯一主卡：事件不在多个栏目重复写全卡", not dup,
          "; ".join(f"{e} 出现在 {', '.join(cols)}" for e, cols in list(dup.items())[:4]))

    # 空栏目：标题下没有卡片，且没有任何主卡归属于它。章 2 承载主卡时，
    # 分类章的该栏目只留交叉引用，这是规定写法，不是空栏目。
    owned = {eff for eff, _ in placed}
    empty = sorted(col for col, cards in columns.items() if not cards and col not in owned)
    c.add("taxonomy", "空栏目不出现在正文", not empty,
          f"已渲染但无事件: {empty}")

    decls = [(card["eid"], card["decl"]) for cards in columns.values() for card in cards
             if card["decl"]] + [(card["eid"], card["decl"]) for card in focus if card["decl"]]
    bad_decl = [f"{e} 声明了不存在的栏目 {d}" for e, d in decls if d not in known]
    c.add("taxonomy", "归属声明是合法栏目", not bad_decl, "; ".join(bad_decl[:4]))

    per_target: dict[str, int] = {}
    for d in folded.values():
        per_target[d] = per_target.get(d, 0) + 1
    over = [f"{d} 折叠了 {n} 条" for d, n in sorted(per_target.items()) if n >= 2]
    c.add("taxonomy", "折叠栏目只折 1 条", not over, "; ".join(over[:4]))

    # 聚合栏目：主卡落在 4.6 的卡片正文必须写出具体技术域标签
    unlabeled = []
    for eff, card in placed:
        if eff not in known:
            continue          # 非法声明已由「归属声明是合法栏目」报出
        labels = TAXONOMY.annotation_labels(eff)
        if labels and not any(lb in card["body"] for lb in labels):
            unlabeled.append(f"{card['eid']}@{eff}")
    c.add("taxonomy", "聚合栏目卡片标注了具体技术域", not unlabeled,
          "未标注: " + ", ".join(unlabeled[:6]))

    events = _load_events(events_dir)
    if not events:
        c.warn("taxonomy", "未提供事件文件", "跳过主卡归位检查")
        return
    # 主卡归位：写了主卡的事件必须落在 primary_path 解析出的栏目；
    # A/A+ 必须有主卡。B 级及以下可只出现在章 5（值得关注），不强制主卡。
    misplaced = []
    for eid, ev in sorted(events.items()):
        try:
            expect = TAXONOMY.resolve(ev.get("primary_path") or "")
        except TaxonomyError:
            continue          # 不可解析的路径由 check_event_paths 报
        got = ev_cols.get(eid, [])
        if got and expect not in got:
            misplaced.append(f"{eid} primary={ev['primary_path']}→{expect}，实际在 {got}")
        elif not got and ev.get("rating") in ("A", "A+"):
            misplaced.append(f"{eid} primary={ev['primary_path']}→{expect}，未写主卡")
    c.add("taxonomy", "主卡落在 primary_path 对应的栏目", not misplaced,
          "; ".join(misplaced[:5]))


def check_markdown(c: Check, md_path: Path, report: dict,
                   events_dir: Path | None = None):
    """MD 路线的核心门禁：八章齐全、栏目合法、A/A+ 四节、唯一主卡、空栏目。"""
    if not md_path.exists():
        c.add("md", "Markdown 文件存在", False, str(md_path))
        return
    text = md_path.read_text(encoding="utf-8", errors="ignore")
    c.add("md", "文件 size > 0", len(text) > 0, f"{len(text)} bytes")

    # frontmatter 必须有 title（渲染器强依赖）
    fm = _md_frontmatter(text)
    c.add("md", "frontmatter 含 title", bool(fm.get("title")),
          str(fm.get("title", ""))[:60])
    c.add("md", "frontmatter 含 date", bool(fm.get("date")),
          str(fm.get("date", ""))[:20])

    secs = _md_sections(text)

    # 八章：MD 章标题不带数字前缀（如「本轮结论与技术趋势」），按顺序
    # 匹配——第 N 个 ## 就是第 N 章。顺序错位（缺章或多章）会被发现。
    chapter_count = len(TAXONOMY.chapters())
    h2_titles = [title for level, title, _ in secs if level == 2]
    found_chapters = list(range(1, min(len(h2_titles), chapter_count) + 1))
    expected = set(range(1, chapter_count + 1))
    missing_ch = sorted(expected - set(found_chapters))
    c.add("md", "八章齐全（按 ## 顺序匹配）",
          not missing_ch, f"missing={missing_ch}（共 {len(h2_titles)} 个 ##）")

    # 8.1/8.2/8.3 子节存在（按标题文本）
    flat = " ".join(t for _, t, _ in secs)
    c.add("md", "8.1/8.2/8.3 子节存在",
          all(x in flat for x in ("8.1", "8.2", "8.3")), "")

    # 来源链接 ≥ 10（markdown 链接 + 裸 URL）
    md_links = re.findall(r'\[[^\]]*\]\((https?://[^)]+)\)', text)
    bare = re.findall(r'(?<![\(\"])(https?://[^\s\)\"]+)', text)
    uniq = set(md_links) | set(bare)
    c.add("md", "原始来源链接 >= 10", len(uniq) >= 10,
          f"{len(uniq)} unique links")

    # 窗口日期一致
    ws = report.get("target_window", {}).get("start", "")
    we = report.get("target_window", {}).get("end", "")
    if ws:
        ws_date = ws[:10]
        c.add("md", "正文含窗口起始日期", ws_date in text, f"expect {ws_date}")
        c.add("md", "文件名日期 = WINDOW_START_DATE",
              ws_date in md_path.name, f"expect {ws_date} in {md_path.name}")
    else:
        c.warn("md", "报告缺 target_window", "跳过窗口一致性检查")

    # 窗口截断披露：partial 源必须在正文里被点名
    partial = [r for r in report.get("sources", [])
               if r.get("covered_quality") == "partial"]
    if partial:
        markers = ("覆盖不完整", "窗口截断", "partial", "前半段", "未回溯")
        has_marker = any(k in text for k in markers)
        missing = [r["id"] for r in partial
                   if r["id"] not in text and (r.get("entity") or "") not in text]
        c.add("md", "披露了窗口截断源",
              has_marker and not missing,
              ("缺截断措辞" if not has_marker else "")
              + (" 未列源: " + ", ".join(missing[:6]) if missing else ""))

    # A/A+ 主卡四维深拆：义务由事件 JSON 决定；五级标题是深拆节
    events = _load_events(events_dir)
    ws = _iso(report.get("target_window", {}).get("start", "")) if report else None
    lay = _md_layout(text)
    main_cards = [cd for cards in lay["columns"].values() for cd in cards] + \
                 [cd for cd in lay["focus"] if cd["decl"]]
    duty = [cd for cd in main_cards if _deep_dive_required(cd, events, ws)]
    missing_sec = []
    for cd in duty:
        h5_text = " ".join(t for (lv, t, _) in _md_sections(cd["body"]) if lv == 5)
        for req in _REQUIRED_DEEP_SECTIONS:
            if req not in h5_text:
                missing_sec.append(f"{cd['eid']}: 缺「{req}」")
    c.add("md", "A/A+ 主卡含四维深拆（挑战/机制/效果/对比）",
          not missing_sec,
          "; ".join(missing_sec[:4]) if missing_sec else f"{len(duty)} 张 A/A+ 主卡")

    # 卡片标记里的评级必须等于事件 JSON：否则写个 B 就能躲掉深拆
    if events:
        wrong = []
        for lv, title, off in _md_sections(text):
            if lv != 4:
                continue
            body = _md_section_body(text, off)
            marker = _md_card_marker(body)
            ids = set(EV_ID_RE.findall(marker))
            if len(ids) != 1:
                continue
            eid = ids.pop()
            want = (events.get(eid) or {}).get("rating")
            got = _marker_rating(marker)
            if want and got != want:
                wrong.append(f"{eid}: 卡片写 {got or '无评级'}，JSON 为 {want}")
        c.add("md", "卡片评级与事件 JSON 一致", not wrong, "; ".join(wrong[:4]))

    # 图片必须是本地文件：渲染时内嵌成 data URI，页面才自包含
    remote = re.findall(r'!\[[^\]]*\]\((https?://[^)\s]+)', text)
    c.add("md", "图片均为本地文件（渲染时内嵌）", not remote,
          "远程图片: " + ", ".join(remote[:3]))

    _check_md_columns(c, text, events_dir)


_URL_SHAPES = [
    # (名称, URL 形态, 从 URL 取可校验的数值/日期, 校验函数说明)
    ("HN item", re.compile(r'news\.ycombinator\.com/item\?id=(\d+)', re.I), "hn_id"),
    ("arXiv abs", re.compile(r'arxiv\.org/(?:abs|pdf|html)/(\d{2})(\d{2})\.\d{4,5}', re.I),
     "arxiv_ym"),
    ("GitHub release", re.compile(
        r'github\.com/[^/\s]+/[^/\s]+/releases/tag/([^/?#\s]+)', re.I), "gh_tag"),
]


def _hn_id_range(events: dict) -> tuple[int, int]:
    """本轮候选里出现过的 HN item id 区间。HN 的 id 单调递增，
    区间外的 id 一定不是本窗口的条目。"""
    ids = []
    for ev in events.values():
        for u in _event_urls(ev):
            m = _URL_SHAPES[0][1].search(u)
            if m:
                ids.append(int(m.group(1)))
    return (min(ids), max(ids)) if ids else (0, 0)


def _event_urls(ev: dict) -> list:
    out = [str(ev.get("source") or ""), str(ev.get("canonical_source") or "")]
    for c in ev.get("claims") or []:
        if isinstance(c, dict) and c.get("url"):
            out.append(str(c["url"]))
    return [u for u in out if u.startswith("http")]


_NUM = re.compile(r'(\d+)')


def check_must_review(c: Check, mr_path: Path | None, trace_path: Path | None,
                     events_dir: Path | None):
    """必审清单内每一条都要有处置留痕。

    候选池 2000+ 条无法逐条台账，但"分层必审"的那一层必须逐条可查，否则漏检
    就查不出来：2026-10-30 回测里三份报告各自漏掉不同事件（Glance、Masked
    Erosion、Claude Code 2.1.314），都不是判断分歧，而是根本没进视野。
    """
    if not (mr_path and mr_path.exists()):
        c.add("collection", "必审清单已生成", False,
              "缺少 must_review.json，先跑 must_review.py")
        return
    try:
        mr = json.loads(mr_path.read_text(encoding="utf-8"))
    except Exception as e:
        c.add("collection", "必审清单已生成", False, f"解析失败 {e}")
        return
    items = mr.get("items") or []
    c.add("collection", "必审清单已生成", bool(items),
          f"{len(items)} 条 / {mr.get('by_tier')}")

    if not (trace_path and trace_path.exists()):
        c.add("collection", "必审清单逐条留痕", False,
              f"缺少 {trace_path.name if trace_path else 'must_review_trace.json'}，"
              f"用 must_review.py --trace-out 生成后逐条填写")
        return
    try:
        tr = json.loads(trace_path.read_text(encoding="utf-8"))
    except Exception as e:
        c.add("collection", "必审清单逐条留痕", False, f"台账解析失败 {e}")
        return
    disp = tr.get("dispositions") or {}

    try:
        import must_review as mrmod
        legal_disp = set(mrmod.DISPOSITIONS)
        legal_reason = set(mrmod.DISCARD_REASONS)
    except Exception:
        legal_disp = {"selected", "merged", "chapter5", "discarded"}
        legal_reason = set()

    ev_ids, ev_urls = set(), {}
    if events_dir and events_dir.exists():
        for f in sorted(events_dir.glob("EV-*.json")):
            try:
                ev = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            ev_ids.add(f.stem)
            for u in _event_urls(ev):
                ev_urls[u] = f.stem

    missing, illegal, bad_ev, bad_reason, misfiled = [], [], [], [], []
    for it in items:
        uid = it.get("uid") or ""
        e = disp.get(uid)
        label = (it.get("title") or uid)[:40]
        if not e or not (e.get("disposition") or "").strip():
            missing.append(label)
            continue
        d = e["disposition"].strip()
        if d not in legal_disp:
            illegal.append(f"{label}={d}")
            continue
        if d in ("selected", "merged"):
            if not EV_ID_RE.fullmatch(str(e.get("ev") or "")) or \
                    (ev_ids and e["ev"] not in ev_ids):
                bad_ev.append(f"{label}→{e.get('ev')!r}")
        elif d == "discarded":
            if legal_reason and (e.get("reason") or "").strip() not in legal_reason:
                bad_reason.append(f"{label}={e.get('reason')!r}")
        elif d == "chapter5" and not (e.get("reason") or "").strip():
            bad_reason.append(f"{label}=第5章未写归属")

        # 反向核对：清单条目的链接已出现在某个事件里，处置却不是入选/并入，
        # 说明台账填错了（事件确实写了，台账说丢弃）。
        hit = ev_urls.get(it.get("url") or "")
        if hit and d not in ("selected", "merged"):
            misfiled.append(f"{label}已写入 {hit} 但台账记 {d}")

    c.add("collection", "必审清单逐条留痕", not missing,
          f"{len(missing)} 条未填: " + "; ".join(missing[:4]) if missing else
          f"{len(items)} 条全部留痕")
    c.add("collection", "处置取值合法", not illegal, "; ".join(illegal[:4]))
    c.add("collection", "入选/并入指向存在的 EV", not bad_ev, "; ".join(bad_ev[:4]))
    c.add("collection", "丢弃理由取自封闭集合", not bad_reason,
          "; ".join(bad_reason[:4]))
    c.add("collection", "台账与事件产物不矛盾", not misfiled, "; ".join(misfiled[:3]))


def _script_commit() -> str:
    """记录跑门禁时的脚本版本，便于回溯一份报告是用哪一版校验的。"""
    try:
        import subprocess
        return subprocess.run(["git", "-C", str(Path(__file__).parent),
                               "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=5).stdout.strip() or "?"
    except Exception:
        return "?"


def check_stats_recomputable(c: Check, md_path: Path | None, report: dict,
                             events_dir: Path | None):
    """Dashboard 与 8.2 的数字必须能由事件目录复算。

    手写统计一定会漂移：2026-10-31 的一次运行自报 15 个事件、索引只有 14 行，
    自报 A+/A 为 1/5、实际 1/6。这里用 report_stats 复算一遍逐项比对。
    """
    if not (md_path and md_path.exists() and events_dir and events_dir.exists()):
        return
    try:
        import report_stats
        st = report_stats.compute(report_stats.load_events(events_dir), report)
    except Exception as e:
        c.warn("md", "统计可复算", f"复算失败 {e}")
        return

    text = md_path.read_text(encoding="utf-8", errors="ignore")
    bad = []

    # 事件总数：Dashboard 里「事件总数 | N」
    m = re.search(r'事件总数[^|\n]*\|\s*(\d+)', text)
    if m and int(m.group(1)) != st["events_total"]:
        bad.append(f"事件总数 正文 {m.group(1)} ≠ 事实源 {st['events_total']}")

    # A+/A 计数
    m = re.search(r'A\+\s*/\s*A[^|\n]*\|\s*(\d+)\s*/\s*(\d+)', text)
    if m:
        want = (st["by_rating"]["A+"], st["by_rating"]["A"])
        got = (int(m.group(1)), int(m.group(2)))
        if got != want:
            bad.append(f"A+/A 正文 {got[0]}/{got[1]} ≠ 事实源 {want[0]}/{want[1]}")

    # 8.2 的 EV 行数
    m82 = re.search(r'^(#{2,4})\s*8\.2\b[^\n]*$', text, re.M)
    if m82:
        seg = text[m82.end():]
        nxt = re.search(rf'^#{{1,{len(m82.group(1))}}}\s+', seg, re.M)
        seg = seg[:nxt.start()] if nxt else seg
        n_rows = len({m.group(0) for ln in seg.splitlines()
                      if ln.strip().startswith("|")
                      for m in [EV_ID_RE.search(ln)] if m})
        if n_rows != st["events_total"]:
            bad.append(f"8.2 索引 {n_rows} 行 ≠ 事件数 {st['events_total']}")

    c.add("md", "统计可由事件目录复算", not bad, "; ".join(bad[:4]))


def check_window_consistency(c: Check, report: dict, report_path: Path | None):
    """窗口只能冻结一次：采集报告里的窗口必须与 window.json 完全一致。

    各脚本各自再算一遍会产生秒级漂移（实测 22 秒），让产物之间的口径对不上。
    同时核对 SCAN_WINDOW 确实比归属窗口早，证明缓冲区真的生效了
    —— 旧实现把 scan_start 算出来写进报告，却从未传给采集逻辑。
    """
    tw = report.get("target_window") or {}
    ws, we = tw.get("start", ""), tw.get("end", "")
    sw = report.get("scan_window") or {}
    ss = sw.get("start", "") or report.get("scan_start", "")

    wj = (report_path.parent / "window.json") if report_path else None
    if wj and wj.exists():
        try:
            win = json.loads(wj.read_text(encoding="utf-8"))
            same = (win.get("window_start") == ws and win.get("window_end") == we
                    and win.get("scan_start") == ss)
            c.add("collection", "采集窗口与 window.json 一致", same,
                  f"window.json={win.get('window_start')}→{win.get('window_end')} "
                  f"报告={ws}→{we}")
        except Exception as e:
            c.add("collection", "采集窗口与 window.json 一致", False, f"读取失败 {e}")

    a_, b_ = _iso(ss), _iso(ws)
    if a_ and b_:
        hours = (b_ - a_).total_seconds() / 3600
        c.add("collection", "扫描窗口早于归属窗口（缓冲区生效）", hours >= 1,
              f"SCAN_START 比 WINDOW_START 早 {hours:.1f} 小时")


def check_link_identity(c: Check, report: dict, events_dir: Path | None,
                        pool_path: Path | None = None):
    """链接身份：URL 指向的对象必须确实属于本窗口。

    只看域名是不够的。2026-10-31 实测，一份报告引用了四个形如
    news.ycombinator.com/item?id=4213xxxx 的链接，域名、路径都对，
    但那是 2024 年量级的 id —— 本窗口真实区间从 50291424 起。
    对三类结构化 URL 做区间/日期校验，能把这类编造直接拦下。
    """
    if not events_dir or not events_dir.exists():
        return
    events = {}
    for f in sorted(events_dir.glob("EV-*.json")):
        try:
            events[f.stem] = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
    if not events:
        return

    ws = _iso((report.get("target_window") or {}).get("start", ""))
    we = _iso((report.get("target_window") or {}).get("end", ""))

    # HN id 区间以候选池为准；没有候选池时退回事件自身，只能做弱校验
    lo = hi = 0
    if pool_path and pool_path.exists():
        try:
            pool = json.loads(pool_path.read_text(encoding="utf-8"))
            rows = pool.get("items", pool) if isinstance(pool, dict) else pool
            ids = [int(m.group(1)) for r in rows
                   for m in [_URL_SHAPES[0][1].search(str(r.get("url", "")))] if m]
            if ids:
                lo, hi = min(ids), max(ids)
        except Exception:
            pass
    if not lo:
        lo, hi = _hn_id_range(events)

    bad = []
    for eid, ev in sorted(events.items()):
        for u in _event_urls(ev):
            m = _URL_SHAPES[0][1].search(u)
            if m and lo:
                v = int(m.group(1))
                # 放宽一个数量级的余量，只拦明显不同年代的 id
                if v < lo * 0.9 or v > hi * 1.1:
                    bad.append(f"{eid}: HN id {v} 在本轮区间 [{lo},{hi}] 之外")
                continue
            m = _URL_SHAPES[1][1].search(u)
            if m and ws:
                yy, mm = int(m.group(1)), int(m.group(2))
                if not (1 <= mm <= 12):
                    bad.append(f"{eid}: arXiv id 月份非法 {m.group(0)}")
                elif abs((2000 + yy) * 12 + mm - (ws.year * 12 + ws.month)) > 2:
                    bad.append(f"{eid}: arXiv id {m.group(0)} 的年月距窗口超过 2 个月")
                continue
    c.add("trace", "来源链接的对象编号落在本轮区间内", not bad, "; ".join(bad[:4]))


def check_md_event_index(c: Check, md_path: Path, report: dict,
                         events_dir: Path | None = None):
    """8.2 Event Index 校验：解析 MD 表格行，与 EV JSON 逐条对账。"""
    if not md_path.exists():
        return
    text = md_path.read_text(encoding="utf-8", errors="ignore")

    ws = _iso(report.get("target_window", {}).get("start", ""))
    we = _iso(report.get("target_window", {}).get("end", ""))
    if not (ws and we):
        c.warn("md", "缺窗口信息，跳过 Event Index 检查", "")
        return

    # 定位 8.2 段：从 "### 8.2" 或 "## 8.2" 到下一个同级或更高级标题
    m82 = re.search(r'^(#{2,4})\s*8\.2\b[^\n]*$', text, re.M)
    if not m82:
        c.warn("md", "未定位 8.2 段", "需人工核对 Event Index")
        return
    level = len(m82.group(1))
    seg_start = m82.end()
    nxt = re.search(rf'^#{{1,{level}}}\s+', text[seg_start:], re.M)
    seg = text[seg_start: seg_start + nxt.start()] if nxt else text[seg_start:]

    # MD 表格行：| ... | 形式
    rows = [ln for ln in seg.splitlines() if ln.strip().startswith("|")
            and "---" not in ln]
    idx_rows: dict[str, dict] = {}
    all_dates: list[datetime] = []
    for row in rows:
        dates = []
        for d in re.findall(r"(20\d{2}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?)", row):
            dt = _iso(d.replace(" ", "T"))
            if dt:
                dates.append(dt)
        all_dates.extend(dates)
        eid = EV_ID_RE.search(row)
        if eid:
            idx_rows[eid.group(0)] = {"text": row, "dates": dates}

    if not all_dates:
        c.warn("md", "8.2 中未找到结构化时刻", "需人工核对 Event Index")
    else:
        end_str = we.strftime("%Y-%m-%dT%H:%M")
        dates = [d for d in all_dates if d.strftime("%Y-%m-%dT%H:%M") != end_str]
        late = [d for d in dates if d > we]
        c.add("md", "无晚于 WINDOW_END 的新事件",
              not late, ", ".join(d.isoformat() for d in late[:3]))

        bad_rows = []
        for eid, info in idx_rows.items():
            early = [d for d in info["dates"] if d < ws
                     and d.strftime("%Y-%m-%dT%H:%M") != end_str]
            if not early:
                continue
            if not any(k in info["text"] for k in
                       ("Active Event", "Historical", "历史", "不计入本轮")):
                bad_rows.append(f"{eid} ({early[0].strftime('%m-%d %H:%M')})")
        before = [d for d in dates if d < ws]
        if before:
            c.add("md", "早于 WINDOW_START 的事件标为 Active/Historical",
                  not bad_rows,
                  "未标注的行: " + ", ".join(bad_rows[:6]) if bad_rows
                  else f"{len(before)} 个早于窗口，已标注")

    # 与 EV JSON 交叉校验
    if not events_dir or not events_dir.exists():
        if idx_rows:
            c.warn("md", "8.2 声明了事件但未提供 events 目录",
                   f"{len(idx_rows)} 行事件无法回溯到事实源")
        return

    ev_files: dict[str, dict] = {}
    for f in sorted(events_dir.glob("EV-*.json")):
        try:
            ev_files[f.stem] = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            c.add("trace", f"{f.name} 可解析", False, "JSON 解析失败")

    no_json = sorted(set(idx_rows) - set(ev_files))
    c.add("trace", "8.2 每个事件都有 EV JSON", not no_json,
          "缺事实源: " + ", ".join(no_json[:8]))
    not_in_md = sorted(set(ev_files) - set(idx_rows))
    c.add("trace", "每个 EV JSON 都在 8.2 出现", not not_in_md,
          "未在 Event Index 引用: " + ", ".join(not_in_md[:8]))

    outside, id_mismatch, time_mismatch = [], [], []
    for eid, ev in ev_files.items():
        if ev.get("date_precision") == "none":
            if not ev.get("date_precision_note"):
                outside.append(f"{eid} (date_precision=none 但无说明)")
            continue
        fp = _iso(ev.get("first_publish_shanghai", ""))
        if fp is None:
            outside.append(f"{eid} (缺 first_publish_shanghai)")
        if fp is not None and not (ws <= fp <= we):
            row = idx_rows.get(eid)
            if row and any(k in row["text"] for k in
                           ("Active Event", "Historical", "历史", "不计入本轮")):
                continue
            outside.append(f"{eid} {fp.strftime('%m-%d %H:%M')}")

        row = idx_rows.get(eid)
        if row:
            ev_tokens = _tokens((ev.get("event_title") or "") + " "
                                + (ev.get("statement") or ""))
            if ev_tokens and not (ev_tokens & _tokens(row["text"])):
                id_mismatch.append(
                    f"{eid}: MD「{row['text'][:40]}」↔ JSON「"
                    f"{(ev.get('event_title') or '')[:40]}」")
            if ev.get("rating"):
                cells = [x.strip() for x in row["text"].strip().strip("|").split("|")]
                tokens = {t for cell in cells for t in re.split(r'[\s·/,，]+', cell) if t}
                if ev["rating"] not in tokens:
                    id_mismatch.append(
                        f"{eid}: 评级不一致 8.2 中无独立的「{ev['rating']}」 ↔ JSON={ev['rating']}")
            if fp is not None and row["dates"]:
                md_times = {d.strftime("%Y-%m-%dT%H:%M") for d in row["dates"]}
                if fp.strftime("%Y-%m-%dT%H:%M") not in md_times:
                    time_mismatch.append(
                        f"{eid}: MD {sorted(md_times)[0]} ↔ JSON "
                        f"{fp.strftime('%Y-%m-%d %H:%M')}")

    c.add("trace", "EV JSON 首发时刻落在 TARGET_WINDOW",
          not outside, "窗口外: " + ", ".join(outside[:6]))
    c.add("trace", "EV 编号与事件内容一致",
          not id_mismatch, "; ".join(id_mismatch[:3]))
    c.add("trace", "8.2 时刻与 EV JSON 一致（同一时区）",
          not time_mismatch, "; ".join(time_mismatch[:4]))


def check_unclassified(c: Check, events_dir: Path | None):
    """
    「未归类」必须有出口：三条条件缺一不可，否则它就变成兜底类。

    设计文档 §4.6：有证据 / 无归属 / 写了理由。机器只能判后两条的
    形式（无归属 = 确实没给 primary_path 但声明了 unclassified；
    写了理由 = 理由非空且不是套话），"有证据"仍靠人工。
    """
    events = _load_events(events_dir)
    if not events:
        return

    vague = {"无", "暂无", "待定", "见正文", "跨层", "不确定", "新范式", "边界模糊"}
    no_reason, vague_reason, also_classified = [], [], []
    for eid, ev in events.items():
        if not ev.get("unclassified"):
            continue
        reason = (ev.get("unclassified_reason") or "").strip()
        if not reason:
            no_reason.append(eid)
        elif reason in vague or len(reason) < 10:
            vague_reason.append(f"{eid}={reason[:16]}")
        if ev.get("primary_path"):
            also_classified.append(eid)

    if no_reason or vague_reason or also_classified:
        c.add("taxonomy", "未归类事件满足三条件", False,
              "; ".join(filter(None, [
                  f"缺理由: {', '.join(no_reason[:5])}" if no_reason else "",
                  f"理由过泛: {', '.join(vague_reason[:4])}" if vague_reason else "",
                  f"同时给了 primary_path: {', '.join(also_classified[:4])}" if also_classified else "",
              ])))
    else:
        n = sum(1 for ev in events.values() if ev.get("unclassified"))
        c.add("taxonomy", "未归类事件满足三条件", True,
              f"{n} 条已归类之外的事件" if n else "无未归类事件")


def check_publish_precision(c: Check, events_dir: Path | None):
    """
    日粒度事件被引用时必须标注精度。

    日期只到日的条目，其真实时刻在 50 小时区间内不确定（见 extract.window_match）。
    把它们当成精确时刻写进正文，等于把时区猜测伪装成事实 —— 而这类事件
    恰好集中在窗口边界，正是最需要读者自己判断的那批。
    """
    events = _load_events(events_dir)
    if not events:
        return

    bad_first, bad_prec = [], []
    for eid, ev in events.items():
        prec = (ev.get("date_precision") or "").strip()
        fp = (ev.get("first_publish_shanghai") or "").strip()
        if not prec:
            bad_prec.append(eid)
        if prec == "day" and fp:
            # 日粒度必须在正文里显式标出，且时刻写成日期（不含时分秒）
            if re.search(r"T\d{2}:\d{2}", fp) and not ev.get("date_precision_note"):
                bad_first.append(f"{eid}={fp}")
    c.add("trace", "事件声明了 date_precision", not bad_prec,
          "缺: " + ", ".join(bad_prec[:6]))
    c.add("trace", "日粒度事件标注了精度来源", not bad_first,
          "; ".join(bad_first[:4]) + "（day 精度却写成精确时刻且无 note）" if bad_first else "")


def _tokens(s: str) -> set[str]:
    """取有区分度的词，用于 HTML 行标题与 EV JSON 的事件标题做弱匹配。"""
    stop = {"when", "into", "your", "main", "loop", "building", "with", "from",
            "that", "this", "release", "update", "and", "the", "for", "new",
            "agent", "agents", "api", "model", "models", "platform", "官方",
            "发布", "参考", "架构"}
    raw = re.findall(r"[A-Za-z][A-Za-z0-9.\-]{2,}|[\u4e00-\u9fa5]{2,}", s)
    return {t.lower() for t in raw if t.lower() not in stop}


# ---------- 追溯层 ----------
def check_traceability(c: Check, events_dir: Path | None):
    """P2 留痕：事件已经过 events.py normalize（有 event_key），A/A+ 有 claim inventory。"""
    events = _load_events(events_dir)
    if not events:
        c.warn("trace", "未提供 events 目录", "跳过事件留痕检查")
        return
    no_key = [e for e, ev in events.items() if not ev.get("event_key")]
    c.add("trace", "事件已规范化（有 event_key）", not no_key,
          "缺: " + ", ".join(no_key[:6]) + "（先跑 events.py normalize）" if no_key else "")
    no_claims = [e for e, ev in events.items()
                 if ev.get("rating") in ("A", "A+") and not ev.get("claims")]
    c.add("trace", "A/A+ 事件有 claim inventory", not no_claims,
          "缺失: " + ", ".join(no_claims[:6]))


def _open_registry(state_dir: Path | None):
    from thesis_registry import Registry, RegistryError
    path = (state_dir or Path("state")) / "thesis_registry.json"
    if not path.exists():
        return None, f"{path} 不存在"
    try:
        return Registry(path.parent), ""
    except RegistryError as e:
        return None, str(e)


def check_registry(c: Check, events_dir: Path | None, state_dir: Path | None, run_date: str):
    """P3/P4 留痕：召回由工具生成、A/A+ 有裁决、本轮已整批入库且与事件目录一致。"""
    events = _load_events(events_dir)
    if not events:
        return
    reg, err = _open_registry(state_dir)
    c.add("registry", "registry 可读", reg is not None, err)
    if reg is None:
        return
    missing_days = reg.gaps(run_date)
    if missing_days:
        c.warn("registry", "存在漏跑的窗口",
               f"{missing_days[:6]}：按完整流程补跑，ingest 用 --backfill（SKILL 步骤 1）")
    run = next((r for r in reg.runs if r["run_date"] == run_date), None)
    c.add("registry", f"本轮 {run_date} 已入库", run is not None,
          "先跑 thesis_registry.py ingest" if run is None else "")
    if run is None:
        return

    keys = {ev.get("event_key") for ev in events.values() if ev.get("event_key")}
    extra, missing = sorted(set(run["event_keys"]) - keys), sorted(keys - set(run["event_keys"]))
    c.add("registry", "入库事件与 events 目录一致", not extra and not missing,
          (f"目录里没有: {extra[:3]} " if extra else "") + (f"未入库: {missing[:3]}" if missing else ""))

    drift, undecided, unlinked = [], [], []
    linked = {l["event_key"] for l in reg.data["links"]}
    for eid, ev in sorted(events.items()):
        strong = ev.get("rating") in ("A", "A+")
        if strong:
            got = ev.get("thesis_candidates")
            want = [x["id"] for x in reg.candidates(ev, run_date)]
            if got is None or [x.get("id") for x in got] != want:
                drift.append(f"{eid}: 写的是 {[x.get('id') for x in got or []]}，应为 {want}")
            if (ev.get("thesis_decision") or {}).get("action") not in ("attach", "new"):
                undecided.append(eid)
        action = (ev.get("thesis_decision") or {}).get("action")
        if action in ("attach", "new") and ev.get("event_key") not in linked:
            unlinked.append(eid)
    c.add("registry", "A/A+ 候选由 registry candidates 生成", not drift, "; ".join(drift[:3]))
    c.add("registry", "A/A+ 事件有 attach/new 裁决", not undecided, ", ".join(undecided[:6]))
    c.add("registry", "裁决已写入 registry", not unlinked,
          ", ".join(unlinked[:6]) + "（改过裁决后需重跑 ingest）" if unlinked else "")


_TH_RE = re.compile(r"TH-\d{4}")


def check_md_theses(c: Check, md_path: Path | None, state_dir: Path | None, run_date: str):
    """第 7 章与 registry 报告对齐：
      - 每条判断（列表项）都写 TH 编号；整章没有编号时必须写明"本轮无核心技术判断"；
      - registry 报告里 core_judgment 为真的命题全部出现（不能挑着写）；
      - 引用的命题存在、为 active / contested 且非 Low，置信度文字与 registry 一致，
        contested 必须写出反证。"""
    if not md_path or not md_path.exists():
        return
    text = md_path.read_text(encoding="utf-8", errors="ignore")
    h2 = [(t, off) for lv, t, off in _md_sections(text) if lv == 2]
    if len(h2) < 7:
        return                 # 八章缺失由 check_markdown 报
    ch7 = _md_section_body(text, h2[6][1])
    lines = [ln.strip() for ln in ch7.splitlines() if ln.strip()]
    items = [ln for ln in lines if re.match(r'^([-*+]|\d+[.)、])\s+', ln)]
    unmarked = [ln[:30] for ln in items if not _TH_RE.search(ln)]
    c.add("registry", "第 7 章每条判断都标了 TH 编号", not unmarked,
          "未标编号: " + " / ".join(unmarked[:3]))
    cited = [(m.group(0), ln) for ln in lines for m in _TH_RE.finditer(ln)]

    reg, err = _open_registry(state_dir)
    if reg is None:
        c.add("registry", "第 7 章引用可核对", False, err)
        return
    try:
        core = [r["id"] for r in reg.report(run_date)["theses"] if r["core_judgment"]]
    except Exception as e:           # 本轮未入库已由 check_registry 报
        core = []
        c.warn("registry", "无法生成本轮 registry 报告", str(e))
    if not cited:
        c.add("registry", "第 7 章为空时写明本轮无核心判断",
              "本轮无核心技术判断" in ch7 and not core,
              f"registry 有核心判断 {core[:4]} 未写" if core else "需写明「本轮无核心技术判断」")
        return
    cited_ids = {t for t, _ in cited}
    missing = [t for t in core if t not in cited_ids]
    c.add("registry", "第 7 章覆盖全部核心判断", not missing, "未写: " + ", ".join(missing[:6]))

    unknown, not_core, wrong_conf, no_counter = [], [], [], []
    for tid, line in cited:
        if tid not in reg.data["theses"]:
            unknown.append(tid)
            continue
        v = reg.view(tid, run_date)
        if v["state"] not in ("active", "contested") or v["confidence"] == "Low":
            not_core.append(f"{tid}（{v['state']} / {v['confidence']}）")
        if v["confidence"] not in line:
            wrong_conf.append(f"{tid} 应写 {v['confidence']}")
        if v["state"] == "contested" and "反证" not in line:
            no_counter.append(tid)
    c.add("registry", "第 7 章引用的命题存在", not unknown, ", ".join(unknown[:6]))
    c.add("registry", "第 7 章只引用 active/contested 且非 Low 的命题", not not_core,
          "; ".join(not_core[:4]))
    c.add("registry", "第 7 章置信度与 registry 一致", not wrong_conf, "; ".join(wrong_conf[:4]))
    c.add("registry", "contested 命题写出了反证", not no_counter, ", ".join(no_counter[:6]))


def main():
    ap = argparse.ArgumentParser(description="Gate 校验器")
    ap.add_argument("--report", default="", help="collect_report.json")
    ap.add_argument("--md", default="", help="简报 Markdown 源路径（reports/<slug>-<date>.md）")
    ap.add_argument("--events", default="", help="events_run_<date>/ 目录")
    ap.add_argument("--gap-tasks", default="", help="gap_tasks.json")
    ap.add_argument("--raw-dir", default="", help="raw_<date>/ 目录（自动推导其它参数）")
    ap.add_argument("--state", default="", help="registry 状态目录（默认 $TECH_BRIEFING_STATE 或 ./state）")
    ap.add_argument("--snapshot-roots", nargs="*", default=[],
                    help="快照根目录（claim 级证据比对用，如 raw_<date> src）")
    ap.add_argument("--must-review", default="", help="must_review.json")
    ap.add_argument("--must-review-trace", default="",
                    help="must_review_trace.json（逐条处置台账）")
    ap.add_argument("--json-out", default="", help="结果写成 JSON")
    args = ap.parse_args()

    report_path = Path(args.report) if args.report else None
    md_path = Path(args.md) if args.md else None
    events_dir = Path(args.events) if args.events else None
    gap_path = Path(args.gap_tasks) if args.gap_tasks else None
    state_dir = Path(args.state or os.environ.get("TECH_BRIEFING_STATE") or "state")
    run_date = events_dir.name[len("events_run_"):] if events_dir and \
        events_dir.name.startswith("events_run_") else ""

    mr_path = Path(args.must_review) if args.must_review else None
    trace_path = Path(args.must_review_trace) if args.must_review_trace else None

    if args.raw_dir:
        rd = Path(args.raw_dir)
        report_path = report_path or rd / "collect_report.json"
        gap_path = gap_path or rd / "gap_tasks.json"
        mr_path = mr_path or rd / "must_review.json"
        trace_path = trace_path or rd / "must_review_trace.json"
        if not args.snapshot_roots:
            # raw_<date>/ 本身就是快照目录；src/ 是补检时手工抓的页面
            args.snapshot_roots = [str(rd)] + \
                ([str(rd.parent / "src")] if (rd.parent / "src").exists() else [])

    c = Check()
    check_taxonomy_definition(c)
    check_root_tech_list(c)
    check_event_paths(c, events_dir)
    check_event_annotations(c, events_dir)
    check_unclassified(c, events_dir)
    check_publish_precision(c, events_dir)
    check_scoring(c, events_dir,
                  (events_dir / "pairwise.json") if events_dir else None)
    check_claim_evidence(c, events_dir, args.snapshot_roots)

    if report_path and report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        run_date = (report.get("target_window", {}).get("start") or "")[:10] or run_date
        check_source_coverage_definition(c, report)
        check_collection(c, report, gap_path)
        pool_path = (Path(report_path).parent / "candidate_pool.json"
                     if report_path else None)
        check_pool_retains_undated(c, report, pool_path)
        check_link_identity(c, report, events_dir, pool_path)
        check_window_consistency(c, report, report_path)
        check_must_review(c, mr_path, trace_path, events_dir)
        if md_path:
            # MD 路线：HTML 是机械渲染副本，门禁校验 MD 源；HTML 只做轻量断言
            check_markdown(c, md_path, report, events_dir)
            check_md_event_index(c, md_path, report, events_dir)
            check_stats_recomputable(c, md_path, report, events_dir)
            check_ch1_mainlines(c, md_path, events_dir)
            html_sibling = md_path.with_suffix(".html")
            if html_sibling.exists():
                check_html_lightweight(c, html_sibling, report)
        else:
            # 未给 --md 时不能静默跳过文档层，否则门禁对简报正文恒绿
            c.add("md", "提供了 --md 简报源", False,
                  "文档层未校验：用 --md reports/<slug>-<WINDOW_START_DATE>.md")
    else:
        c.add("collection", "采集报告存在", False, str(report_path))

    check_traceability(c, events_dir)
    if run_date:
        check_registry(c, events_dir, state_dir, run_date)
        check_md_theses(c, md_path, state_dir, run_date)
    elif events_dir:
        c.add("registry", "能确定本轮 run_date", False, "用 --report 或 events_run_<date>/ 目录名")

    c.print()

    # 门禁摘要写到 .md 旁边：渲染器据此拒绝渲染未过门禁的稿子，
    # 让「没跑门禁的报告」无法产出 final 状态的 HTML。
    if md_path:
        summary = {
            "passed": sum(1 for r in c.results if r["status"] == "PASS"),
            "warned": sum(1 for r in c.results if r["status"] == "WARN"),
            "failed": [r["name"] for r in c.results if r["status"] == "FAIL"],
            "checked_at": datetime.now(SH_TZ).isoformat(timespec="seconds"),
            "script_commit": _script_commit(),
            "md": md_path.name,
        }
        (md_path.parent / ".gate_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps({"results": c.results,
                        "failed": len(c.failed)},
                       ensure_ascii=False, indent=2), encoding="utf-8")

    return 1 if c.failed else 0


if __name__ == "__main__":
    sys.exit(main())
