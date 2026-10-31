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
  - 追溯层：thesis convergence 是否被记录、丢弃日志是否完整

用法：
  python verify_gates.py --report raw_2026-10-23/collect_report.json
  python verify_gates.py --raw-dir raw_2026-10-23 \\
      --md reports/<标题 slug>-2026-10-22.md --events events_run_2026-10-22/
退出码：0 全部通过；1 有 FAIL；2 参数错误
"""
import argparse
import json
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


def _md_is_aa_card(body: str) -> bool:
    """判定一张卡是否承担四节深拆义务。规则与旧 HTML eyebrow 豁免一致：
    Top N / Active Event / Convergence / 非 Frontier 都豁免。

    MD 卡片把评级标记写在正文第一行（如 **A+ · Frontier · EV-02**），
    需先去掉 markdown 强调标记再判首词，否则 **A 会被当成首词。
    """
    head = body[:600]
    # 去 markdown 强调标记，让 "A+" / "A" 能被首词匹配
    flat = re.sub(r'[*_`]', '', head).strip()
    if "Top " in flat:
        return False
    if "Active Event" in flat:
        return False
    if "Convergence" in flat:
        return False
    if "Frontier" not in flat:
        return False
    if not re.search(r'\bA\+?\b', flat):
        return False
    first = flat.split()[0].rstrip("·").strip() if flat else ""
    return first in ("A+", "A")


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

    # A/A+ 主卡四维深拆：四级标题是卡，五级标题是深拆节
    aa_cards = []
    for i, (level, title, off) in enumerate(secs):
        if level != 4:
            continue
        body = _md_section_body(text, off)
        eid = _md_card_event(title, body)
        if not eid:
            continue
        if _md_is_aa_card(body):
            aa_cards.append((title, eid, body))

    missing_sec = []
    for title, eid, body in aa_cards:
        # 五级标题里找四节
        h5s = [t for (lv, t, _) in _md_sections(body) if lv == 5]
        h5_text = " ".join(h5s)
        for req in _REQUIRED_DEEP_SECTIONS:
            if req not in h5_text:
                missing_sec.append(f"{eid} {title[:24]}: 缺「{req}」")
    c.add("md", "A/A+ 主卡含四维深拆（挑战/机制/效果/对比）",
          not missing_sec,
          "; ".join(missing_sec[:4]) if missing_sec
          else f"{len(aa_cards)} 张 A/A+ 主卡")

    _check_md_columns(c, text, events_dir)


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
            if ev.get("rating") and ev["rating"] not in row["text"]:
                id_mismatch.append(
                    f"{eid}: 评级不一致 MD 无 {ev['rating']} ↔ JSON={ev['rating']}")
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
    """检查 P2/P3 的留痕：convergence 查询是否执行、丢弃日志是否完整。"""
    if not events_dir or not events_dir.exists():
        c.warn("trace", "未提供 events 目录", "跳过 convergence / 丢弃日志检查")
        return

    files = sorted(events_dir.glob("*.json"))
    c.add("trace", "存在 event 文件", bool(files), f"{len(files)} files")
    if not files:
        return

    # 覆盖率检查必须建立在"8.2 声明了什么"之上，而不是"目录里有什么文件"。
    # 旧实现只遍历已存在的 EV 文件，于是缺 11 个事件文件的 run 也能全绿。
    missing_conv = []
    missing_discard = []
    for f in files:
        try:
            ev = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            c.add("trace", f"{f.name} 可解析", False, "JSON 解析失败")
            continue

        # A/A+ 事件必须记录 convergence 查询结果
        if ev.get("rating") in ("A", "A+"):
            hits = ev.get("convergence_hits")
            if hits is None:
                missing_conv.append(f.name)
            elif hits == [] and ev.get("convergence_checked") is not True:
                missing_conv.append(f.name)

        # 每个 A/A+ 事件必须有 claim inventory（逐条论点处置）
        if ev.get("rating") in ("A", "A+"):
            claims = ev.get("claims")
            if not claims:
                missing_discard.append(f.name)

    c.add("trace", "A/A+ 事件已执行 convergence 查询并留痕",
          not missing_conv,
          "未留痕: " + ", ".join(missing_conv[:6]))
    c.add("trace", "A/A+ 事件有 claim inventory",
          not missing_discard,
          "缺失: " + ", ".join(missing_discard[:6]))


def main():
    ap = argparse.ArgumentParser(description="Gate 校验器")
    ap.add_argument("--report", default="", help="collect_report.json")
    ap.add_argument("--md", default="", help="简报 Markdown 源路径（reports/<slug>-<date>.md）")
    ap.add_argument("--events", default="", help="events_run_<date>/ 目录")
    ap.add_argument("--gap-tasks", default="", help="gap_tasks.json")
    ap.add_argument("--raw-dir", default="", help="raw_<date>/ 目录（自动推导其它参数）")
    ap.add_argument("--json-out", default="", help="结果写成 JSON")
    args = ap.parse_args()

    report_path = Path(args.report) if args.report else None
    md_path = Path(args.md) if args.md else None
    events_dir = Path(args.events) if args.events else None
    gap_path = Path(args.gap_tasks) if args.gap_tasks else None

    if args.raw_dir:
        rd = Path(args.raw_dir)
        report_path = report_path or rd / "collect_report.json"
        gap_path = gap_path or rd / "gap_tasks.json"

    c = Check()
    check_taxonomy_definition(c)
    check_event_paths(c, events_dir)
    check_event_annotations(c, events_dir)
    check_unclassified(c, events_dir)
    check_publish_precision(c, events_dir)

    if report_path and report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        check_source_coverage_definition(c, report)
        check_collection(c, report, gap_path)
        pool_path = (Path(report_path).parent / "candidate_pool.json"
                     if report_path else None)
        check_pool_retains_undated(c, report, pool_path)
        if md_path:
            # MD 路线：HTML 是机械渲染副本，门禁校验 MD 源；HTML 只做轻量断言
            check_markdown(c, md_path, report, events_dir)
            check_md_event_index(c, md_path, report, events_dir)
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

    c.print()

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps({"results": c.results,
                        "failed": len(c.failed)},
                       ensure_ascii=False, indent=2), encoding="utf-8")

    return 1 if c.failed else 0


if __name__ == "__main__":
    sys.exit(main())
