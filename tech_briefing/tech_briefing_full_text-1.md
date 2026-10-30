assets/gap_tasks.py
----------------------------------------
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

assets/html_render_guide.md
----------------------------------------
# HTML 渲染指南 · 借用 visual-explainer 的 kit

本文件是 `SKILL.md` 步骤 5 的执行细则，属于 **tech-briefing 自己的**约束。

visual-explainer 是一个成熟的第三方 skill（MIT，v0.14.0）。**本文件不修改它、不评价它**，
只记录一件事：把"日报的八章内容"塞进它的渲染器时需要遵守什么。

分三类写，不要混：

- **§2 我们的门禁要求** —— `verify_gates.py` 是本地脚本，它的切分规则决定了 HTML 必须长什么样
- **§3 kit 的既定用法** —— kit 已经声明好的行为，照着用即可；违反它会报 `✗`，那是我写错，不是它有问题
- **§4 我踩过的坑** —— 我写错过的地方与正确写法

## 0. 设计约束（零依赖，先于 kit 生效）

以下清单不依赖任何外部 skill、渲染器或 npm 包，**写 `.src.html` 之前先过一遍**。
来源：`educlopez/ui-craft`（typeset / ui-craft-editorial）、`ConardLi/garden-skills`
（web-design-engineer 的 failure-patterns）、`nexu-io/html-anything` 的模板硬约束、
`anthropics/skills` 的 frontend-design。全部 MIT/Apache-2.0，此处只摘条款，不引入代码。

### 0.1 字号与字阶

| 规则 | 判据 |
|---|---|
| 用模数字阶，不用逐处手调的零散值 | 锚定 1.125 / 1.2 / 1.25 之一，取值落在 `12/14/16/20/24/32/48/64` |
| 禁止 13px / 15px / 17px 这类一次性尺寸 | 除非光学补偿，否则一律回到字阶 |
| 正文 ≥ 14px，标签 ≥ 12px | 与 kit 的 12px 门禁同源；`look.mjs` 会实测 SVG 标签 |
| 中文正文行高 1.7–1.8 | 西文 1.5–1.65 偏紧，中文需要更大行距 |

### 0.2 tracking / leading / 字重

| 场景 | 规则 |
|---|---|
| ≥ 24px 标题 | `letter-spacing: -0.02em` 或更紧；40px+ 可到 `-0.035em` |
| 14–20px 正文 | 默认 tracking，不额外加 |
| 11–13px 标签 | `+0.06em` 且允许大写（**唯一**允许 all-caps 的地方） |
| 标题 / 导航 / 按钮 / 表格头 | **禁止全大写** |
| 标题 leading | 1.05–1.15 |
| 正文 leading | 1.5–1.65；中文 1.7–1.8 |
| UI 元素 leading | 1.2–1.3 |
| 字重 | 最多 2–3 档（400 正文 / 500 UI / 600–700 标题），不要为了"保险"加载 9 档 |

### 0.3 字体选择

- **Inter / Roboto / Arial / system-ui / Instrument Serif 不得作为"品牌性"的展示字体**。
  它们作为回退链是合理的，作为唯一字体是 AI 生成页面的头号破绽。
- 一个正文字体 + 可选一个展示字体，**绝不超过两个**。
- 中文字体栈必须显式写 `'Noto Sans SC'` / `'Source Han Sans SC'`，不能只靠系统默认。
- 中文**禁用首字下沉（drop cap）**：放大一个汉字会把相邻汉字挤成孤行（本轮 A/B 实测，
  「窗口统计」被拆成「窗」+「口统计」）。西文用 drop cap 才有意义。

### 0.4 间距与网格

- 8px 基线网格：所有 spacing / line-height / font-size 取 8 的倍数。
- **标题上方空间是下方空间的 2–3 倍**（`margin-top ≈ 2–3 × margin-bottom`）。
- 主内容区有宽度上限（本 skill 用 `max-width: 1080px`），不贴边。
- 禁止"每段都套圆角卡片"（cardification）：容器只在**分组、可选中、需要层次**时才用。

### 0.5 可读性与无障碍

- 正文字对比度 **≥ 4.5:1**；每个可交互元素有真实 `:focus` 态。
- 尊重 `prefers-reduced-motion`：超过简单状态反馈的动效必须可关。
- 所有 `<svg>` 带 `aria-label`，纯装饰写 `aria-hidden="true"`。

### 0.6 反 AI-slop（这些是识别度最高的破绽）

| 破绽 | 为什么是破绽 | 正确做法 |
|---|---|---|
| 每个标题上方一行全大写小标签 | 形成机械化模板节奏 | 只在真正需要分类时用；否则用导语句 / 数字 / 引言变化层级 |
| 每段都进圆角卡片 | 视觉重量均质化，没有主次 | 用留白、对齐、分隔线、排版区分 |
| 居中大标题 + 渐变 + 两个 CTA | 统计意义上的默认值，不是设计决策 | 按内容层级重新构图 |
| 01 / 02 / 03 编号 | 内容不是序列却强行编号 | 删掉，或换成真实序号 |
| 编造的数据 / 评价 / logo 墙 | 假可信度比诚实的空缺更糟 | 标"未披露"或留占位 |
| 装饰性版本号 / 假坐标 / 状态点 | 不帮助理解的信息 | 删除，或连接到真实状态 |

### 0.7 数据图表的诚实性

- **数字必须有对比语境**：基线、上期、目标或同类组，缺一即无意义。
- **data-ink ratio**：删掉网格线、3D、阴影、渐变；比较类图从 0 起、按值排序。
- **一图一主张**：`<figcaption>` 写结论，不写"如图所示"。
- **不要让装饰遮蔽比较**：发光、阴影、动画若削弱比例判断，一律去掉。
- 图表容器必须有显式高度（`<div style="position:relative;height:240px">`）；
  只给 `<canvas height=>` 当布局会让响应式图表陷入 ResizeObserver 死循环。

### 0.8 简报特有的密度取舍

本 skill 的内容形态是「分析型 + 重比较」，对应 Information Density **7–8 档**，
不是营销页的 4–6 档。因此：

- 允许高密度表格、逐条论点、并列对比表；**不要**为了"呼吸感"把比较拆散。
- 但高密度 ≠ 均质重量：主卡 / 摘要卡 / 折叠深拆必须三层区分（见 §9、§10.5）。
- 「呼吸感」靠留白与折叠获得，**不靠删内容**。

## 1. 职责边界

| 谁 | 负责 |
|---|---|
| tech-briefing | 内容：八章结构、事件卡字段、8.1/8.2/8.3 审计、窗口一致性、门禁可判的锚点与表格 |
| visual-explainer | 形式：register、figure 设计、KPI、表格样式、字体配色、响应式与可读性检查 |
| `verify_gates.py` | 只校验事实与结构，**不校验美观**；两者互不替代 |

页面只有三样自写内容：本页少量布局类、figure 里的 SVG、`data-column` 之类的门禁标记。
其余样式全部来自 kit。

## 2. 我们的门禁要求（`verify_gates.py` 决定，不是 kit 决定）

这些约束来自本地脚本如何解析 HTML，与 visual-explainer 无关。

| 要求 | 门禁怎么切 | 正确写法 |
|---|---|---|
| 卡片边界 | 用正则 `<div class="card[^"]*">` 切卡，**`class` 只要以 `card` 开头就算一张卡** | 卡片外层只用 `class="card"`；头部元素必须换名（本轮用 `class="chead"`，写成 `card-head` 会被当成第二张空卡，触发"主卡归位""4.6 标注"误报） |
| 栏目锚点 | 按 `<h3-6 id="s(\d)-(\d)">` 切段，值必须是 `s<章>-<栏目号>` | 栏目用 `h3`/`h4`，如 `<h3 id="s4-6">` |
| 章节锚点 | 八章按 `<section id="s1..s8">` 认 | 章必须用 `<section>`，不是 `<div>` |
| 8.2 时刻 | 按 `id="s8-2"` 切段后抓 `YYYY-MM-DDTHH:MM` | `<td class="mono">2026-10-27T06:01</td>`，与 EV JSON 分钟级一致 |
| 折叠卡 | 看 `data-column` 声明的栏目是否有独立片段 | 单条栏目折进相邻栏目时，卡片加 `data-column="3.4"`，且该栏目**不渲染标题** |
| 4.6 标注 | 在 4.6 片段内逐卡找标签词 | 卡片正文写具体技术域（评测环境/结果核验/…），与 `primary_path` 叶子一致 |
| 8.1 截断披露 | 在 `id="s8-1"` 片段内找关键词 | 正文明确出现"覆盖不完整""窗口截断""前半段"之一，只列源名不算披露 |
| 来源链接 | 全文数唯一 `http(s)` | ≥10 个；每张卡保留原始链接，8.3 也带链接 |

**表格闭合**也要对齐：`<div class="ve-table"><table>…</tbody></table></div>`。
写成 `</div></table>` 时浏览器会自愈，但门禁按 `id="sN-M"` 切段会切错位置。
提交前用 `grep -c "<table"` 与 `grep -c "</table>"` 数一遍。

## 3. kit 的既定用法（照着做就好）

| kit 的规则 | 出处 | 我该怎么写 |
|---|---|---|
| `.ve-svg` 的字号以 **14 单位**为基准保证 ≥12px | `kit/kit.css:128` 注释 "keeps 14-unit labels >= 12px as rendered" | SVG 内文字 ≤14 单位时，viewBox 宽 ≤816 才安全；`ve-label` 是 `--t-label`（.75rem = 12 单位），**放在 SVG 里就会触发小字告警** —— 需要小标题时用 14 单位，或干脆不放进图里 |
| 边先画、节点后画、标签最后 | `references/kit.md` 的 Node/Edge 顺序 | `<path class="ve-e">` 全部写在前，`<g class="ve-n">` 其后 |
| `ve-el` 的 `--bg` 光晕只能压**先画**的线 | `look.mjs` 的 halo 判定（`later(t, sh.e)`） | 标签写在它所标注的边之后；不要让标签压在后画的线上 |
| `.ve-n text` 是 `text-anchor: middle`，居中在 `x` | `kit/kit.css:133` | 节点内的文字必须落在节点框内；跨行说明文字要放进独立节点，不能挂在别的形状旁边 |
| 异形节点（`path.sh` + `ellipse.sh.lid`）只放自己的名字 | `references/diagrams.md` | 说明性文字换成矩形节点承载，罐体只留标题 |
| viewBox 宽 >816 时 kit 自动加 `--ve-min` | `kit/render.mjs:112` | 不用手写 `min-width`；窄屏由 `.frame` 横向滚动 |
| 每张 `<svg>` 都要 `aria-label` | `render.mjs` 校验 | 纯装饰写 `aria-hidden="true"` |
| `history.replaceState` 在 `file://` 下会抛错 | kit 已用 `try/catch` | 自写导航脚本也要 `try/catch` |

**结论**：`✗` 里凡是几何类报错（标签穿框、标签过小、文字越界），先假设是我违反了上面某条，
而不是 kit 有缺陷。

## 4. 我踩过的坑与正确写法

| 我写错的 | 现象 | 正确写法 |
|---|---|---|
| 在 SVG 顶部加 `<text class="ve-label">` | 390px 下报"label renders at 10.94px" | 该行标题放进 `figcaption` 或 `h2`；图内小标题用 14 单位 |
| 把说明文字写在罐体右侧（`x` 在罐体外） | 报"label crossed by a border" | 罐体只放自己的名字；说明文字另起一个 `<g class="ve-n"><rect class="sh">` |
| 标签写在边之前 | 报"label crossed by a line" | 边 → 节点 → 标签，顺序不能倒 |
| `</div></table>` | 浏览器自愈，门禁切段错位 | 逐块数结束标签 |
| `class="card-head"` | 门禁多切出一张空卡 | 头部用 `chead` 等非 `card` 前缀 |
| `class="card-grid"`（网格 wrapper） | 门禁 `_card_bodies` 正则把网格 div 当卡 → `?@4.6` 误报 | 网格 wrapper 用 `grid-cards` 等不以 `card` 开头的名字（见 §10.5） |

## 5. 图表配额（我们的内容要求）

| 位置 | 图 | 规则 |
|---|---|---|
| 首屏 | 1 张"本轮结构性变化"合成图 | 3 个输入 → 1 个落点 → 2 个后果 |
| 章 2 Top 1 | 至少 1 张机制图 | 画机制不画名字：箭头带动词、跨度带尺寸线、关键节点 `.is-key` |
| 章 8.1 | 1 个数据图 | `<ve-bars>` / `<ve-waffle>` / `<ve-stack>` |
| 每张图 | `<figcaption>` | 一句话说出结论，不是"如图所示" |

数字成图：跨度用尺寸线，占比用 `<ve-stack>`/`<ve-waffle>`，比较用 `<ve-bars>`（从零起、按值排序）。

## 6. register 选择

| 内容 | register |
|---|---|
| 默认（日报形态） | `instrument` |
| 架构/流程图为主的一期 | `blueprint` |
| 长阅读专题 | `paper` |

`data-register` 写在 `<html>` 上。不自造配色；需要切主题时按 visual-explainer 的
`references/themes.md` 实现，而不是手写两套 CSS。

## 7. 渲染节奏（实测 2~3 轮收敛）

| 轮次 | 做什么 | 典型 `✗` |
|---|---|---|
| 1 | 写完 `.src.html` 直接渲染 | 结构类：标签错位、figure 缺 caption、SVG 缺 `aria-label`、`ve-bar` 数值非法 |
| 2 | 修结构，再看几何 | 几何类：标签穿框、标签 < 12px、文字越界 |
| 3 | 微调节点位置 | 通常剩 1~2 条，改完即 `✓` |

- 几何错误一次只修一处，改多会引入新的穿过。
- 报"标签 < 12px"时先想"这句能不能不放进图"，删掉比缩 viewBox 快。
- `sheet-*.png` 用来判断**图是否表达清楚**；格式错误 `✗` 已经说完了。
- 不要为消 `✗` 删图——图是内容的一部分。

## 8. 两道关的关系

| 关卡 | 命令 | 查什么 | 全绿不代表 |
|---|---|---|---|
| 视觉 | `render_html.py` | 标签字号、遮挡、横向溢出、figure 完整性 | 内容正确（数字可能是错的） |
| 内容 | `verify_gates.py` | 字段对得上事实源、窗口一致、归类归位 | 页面可读（可能 10px 字） |

## 9. 视觉呼吸感硬约束（避免压抑拥挤）

简报内容密度高（18 事件 + 10 张 A/A+ 深拆），默认 instrument register 的紧凑表格风会让
页面压抑拥挤。在 `<style>` 里必须落实以下三层呼吸感，缺一会让"信息密度"变成"视觉压迫"：

**层 1 · 主区与章节留白**

```css
main{max-width:1080px;margin:0 auto;overflow-x:hidden}
section{margin-top:var(--s-8);padding-top:var(--s-6);border-top:1px solid var(--border)}
section:first-of-type{border-top:none;margin-top:var(--s-6)}
header{padding-bottom:var(--s-6);border-bottom:1px solid var(--border);margin-bottom:var(--s-2)}
```

- 主区不贴边、居中、有上限宽度；章节之间用 hairline + `--s-8` 大间距分隔，而非紧凑堆叠。
- `section:first-of-type` 去掉首章顶部的 border，避免首屏出现双线（header 底线 + 章顶线）。

**层 2 · card 减重**

```css
.card{padding:var(--s-5);margin-bottom:var(--s-6);border:1px solid var(--border);
      border-radius:var(--r-2);background:var(--bg)}
h3{margin-top:var(--s-6);margin-bottom:var(--s-3)}
.summary-card{padding:var(--s-3) var(--s-4);margin-bottom:var(--s-3);
              border-left:2px solid var(--accent);background:transparent}
```

- card 内距从 `--s-4` 抬到 `--s-5`，card 间距从 `--s-5` 抬到 `--s-6`——块与块之间有呼吸。
- summary-card（章 2 折叠卡）用 2px 左边线 + 透明背景，视觉重量远低于主卡，避免一排卡片
  看起来像等重方块墙。
- h3 栏目标题前 `--s-6` 后 `--s-3`，符合 style-guide「space above a heading is 2–3× the space below it」。

**层 3 · 深拆四节折叠进 `<details>`**

```css
.deep-dive{margin-top:var(--s-4);border-top:1px solid var(--border);padding-top:var(--s-3)}
.deep-dive > summary{cursor:pointer;list-style:none;font-size:var(--t-small);
  color:var(--text-dim);display:flex;align-items:center;gap:var(--s-2);padding:var(--s-2) 0}
.deep-dive > summary::-webkit-details-marker{display:none}
.deep-dive > summary::before{content:"▸";transition:transform var(--fast) var(--ease);color:var(--accent)}
.deep-dive[open] > summary::before{transform:rotate(90deg)}
.deep-dive > summary .dd-label{font-weight:600;color:var(--text)}
```

- A/A+ 卡的「挑战/机制/效果/对比」四节用 `<details class="deep-dive">` 包裹，默认折叠。
  主卡只露：标题 + meta-line + kv 表 + 一段摘要。这是 style-guide §3
  「Overview, then detail. Raw material goes in `<details>`」的直接应用。
- 平铺四节会让每张 A/A+ 卡变成 800+ 字的密集长方块，10 张连排阅读沉重；折叠后主卡
  视觉重量大降，读者按需展开深拆。
- 自定义 `▸` 箭头随 `[open]` 旋转，给折叠状态一个轻量视觉提示，不依赖默认的三角标记
  （默认标记在各浏览器表现不一致）。
- 门禁读 HTML 文本，details 折叠不影响四节检测——`<h4>挑战与问题</h4>` 仍在 DOM 里。

**反例**：不做这三层时，18 事件 + 10 张深拆四节全平铺，页面变成一面密密麻麻的灰底方块墙，
首屏没有任何视觉锚点，读者从顶部滑到底部找不到呼吸的间隙。信息密度本身没问题，问题是
**所有内容都被赋予了相同的视觉重量**——没有主次、没有折叠、没有留白。


先跑视觉（步骤 5 末尾）再跑内容（步骤 6a）：改 `.src.html` 比改事件 JSON 便宜。

## 10. 暖色调 editorial 报头 + 全章节 panel 化（借鉴宽屏样例）

§9 解决"压抑"，本节解决"平淡"——把技术文档升级为 editorial 简报视觉风格。
在 `<style>` 里落实以下结构，配合 §9 三层呼吸感使用。

### 10.1 intro 区深层推理框（事实层 + 推理层）

intro 区不只是列举事件，必须分两层。**缺推理层不成稿**：

```html
<section class="intro" aria-labelledby="report-title">
  <p class="eyebrow">TODAY'S TECHNICAL INSIGHT</p>
  <h1 id="report-title">模型档位分化、世界模型工程化与 agent 架构解耦</h1>
  <p class="dek">今日关注三条技术主线：...（事实列举 + 统计数据）。</p>
  <p class="reasoning"><span class="r-label">深层推理</span>三条主线并非孤立事件，
    它们共同指向 <b>agent 技术栈的全栈解耦</b>：...（跨层推理 + 叠加效应）。
    但四层解耦的因果链尚未由单一来源证实，应视为本轮窗口内的分析假设而非已确立结论。</p>
</section>
```

```css
.intro .dek{font-size:15px;line-height:1.8;color:#51585d;max-width:1120px;margin:15px 0 0}
.intro .reasoning{font-size:14px;line-height:1.8;color:#51585d;max-width:1120px;
  margin:14px 0 0;padding:14px 18px;background:var(--accent-soft);
  border-left:3px solid var(--accent);border-radius:0 8px 8px 0}
.intro .reasoning .r-label{font-size:10px;letter-spacing:.12em;text-transform:uppercase;
  color:var(--accent);font-weight:700;margin-right:7px}
```

写作纪律：
- **不强行汇总到单一技术方案**：h1 仍是多命题并列；reasoning 框是"潜在价值"而非"已证实结论"。
- **必须标证据边界**：跨事件推理的因果链未经单一来源证实时，结尾写明"应视为本轮窗口内的分析假设而非已确立结论"。
- **可空但不可假**：若本轮事件间无明确跨层关系，写"本轮事件以独立信号为主，未发现跨层收敛"，不得编造因果。

### 10.2 masthead 报头 + h1 内容标题 + window-line

h1 是**内容标题**（如"模型档位分化、世界模型工程化与 agent 架构解耦"），不是时间戳。
时间窗口降为 `window-line` 小字。

```html
<header class="masthead">
  <div class="brand">
    <div class="brand-mark" aria-hidden="true"></div>
    <div>
      <div class="brand-title">多源技术热点简报</div>
      <div class="brand-sub">TECHNOLOGY INSIGHT BRIEF</div>
    </div>
  </div>
  <div class="mast-meta">DAILY EDITION&nbsp; / &nbsp;2026.10.28</div>
</header>
<div class="window-line">采集时间范围：2026-10-27 00:00 — 2026-10-28 09:46（Asia/Shanghai，UTC+08:00） · 跨度 33.8 h</div>
```

```css
.masthead{display:flex;align-items:center;justify-content:space-between;gap:20px;
  padding:24px 0 18px;border-bottom:1px solid var(--border-bright)}
.brand{display:flex;align-items:center;gap:12px;min-width:0}
.brand-mark{width:4px;height:34px;border-radius:4px;background:var(--accent);flex:0 0 auto}
.brand-title{font-size:16px;font-weight:700;letter-spacing:.02em;color:var(--text)}
.brand-sub{font-size:10px;letter-spacing:.16em;color:var(--text-dim);margin-top:1px}
.mast-meta{font-size:11px;color:var(--text-dim);text-align:right;white-space:nowrap}
.window-line{font-size:11px;color:var(--text-dim);margin:15px 0 24px;letter-spacing:.01em}
.intro{padding:0 0 30px}
.intro .eyebrow{font-size:11px;letter-spacing:.12em;text-transform:uppercase;
  color:var(--accent);font-weight:700;margin:0 0 9px}
.intro h1{font-size:clamp(26px,3vw,40px);line-height:1.2;letter-spacing:-.035em;
  margin:0;max-width:1180px;font-weight:760}
```

### 10.3 暖色调配色 + 强制浅色主题

```css
:root{color-scheme:light}
html:root{
  --bg:#f3f2ee; --surface:#ffffff; --border:#e1ded7; --border-bright:#d3cfc5;
  --text:#252b30; --text-dim:#6e7478; --accent:#9b7842; --accent-soft:#f4ecdf;
  --accent-dim:rgba(155,120,66,.12); --teal:#4c7771; --violet:#786a91;
  --shadow:0 8px 26px rgba(40,42,40,.035);
}
@media (prefers-color-scheme: dark){
  html:root{ /* 重复浅色值，覆盖 instrument register 的深色默认 */
    --bg:#f3f2ee; --surface:#ffffff; --border:#e1ded7; --border-bright:#d3cfc5;
    --text:#252b30; --text-dim:#6e7478; --accent:#9b7842; --accent-soft:#f4ecdf;
    --accent-dim:rgba(155,120,66,.12); --teal:#4c7771; --violet:#786a91;
    --shadow:0 8px 26px rgba(40,42,40,.035);
  }
}
```

### 10.4 全章节 panel 化

**sec-head**（章标题加 hairline + kicker）：
```css
.sec-head{display:flex;align-items:baseline;justify-content:space-between;gap:18px;
  margin:0 0 18px;padding-bottom:12px;border-bottom:1px solid var(--border-bright)}
.sec-head h2{font-size:19px;line-height:1.35;margin:0;font-weight:730;letter-spacing:-.02em}
.sec-head .ve-label{font-size:10px;color:var(--text-dim);letter-spacing:.12em;
  text-transform:uppercase;white-space:nowrap}
```

**stats-panel**（KPI 深底大字，替代扁平 kpi）：
```css
.stats-panel{background:#e9e6df;border:1px solid #dedad1;border-radius:13px;
  padding:22px 25px;margin:24px 0}
.kpis{margin:0;display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:18px}
.kpi{padding:0;border-right:1px solid #d4d0c7;padding-right:15px;
  background:transparent;border-radius:0;display:flex;flex-direction:column;gap:5px}
.kpi:last-child{border-right:0}
.kpi .val{font-size:30px;line-height:1.2;font-weight:750;letter-spacing:-.04em;
  font-variant-numeric:tabular-nums;color:var(--text)}
.kpi .ve-label{font-size:11px;color:#77766f}
```

**ve-table**（圆角 + 表头浅底 + 行间 hairline）：
```css
.ve-table{border:1px solid var(--border);border-radius:10px;overflow:hidden;
  background:var(--surface);box-shadow:var(--shadow)}
.ve-table th{background:#f5f3ee;font-size:11px;letter-spacing:.04em;color:#6f6a5d;
  text-transform:uppercase;font-weight:650;padding:11px 14px;text-align:left;
  border-bottom:1px solid var(--border-bright)}
.ve-table td{padding:11px 14px;border-bottom:1px solid #efede8;font-size:13px;color:var(--text)}
.ve-table tr:last-child td{border-bottom:0}
.ve-table a{color:var(--accent);text-decoration:none}
```

**figure-panel**（图独立面板）+ **thesis-grid**（章7 左边线分级）+ **sources-panel**（chip 化）：
```css
.figure-panel{background:var(--surface);border:1px solid var(--border);
  border-radius:13px;padding:23px 25px 18px;box-shadow:var(--shadow);margin:18px 0}
.thesis-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:12px 0 18px}
.thesis-grid > .card{margin-bottom:0;padding:18px 20px;border-left:3px solid var(--accent)}
.thesis-grid > .card.conv{border-left-color:var(--teal)}
.sources-panel{background:#e9e6df;border:1px solid #dedad1;border-radius:13px;padding:20px 25px;margin-top:24px}
.sources-panel .src-chips{display:flex;flex-wrap:wrap;gap:7px}
.sources-panel .src-chips a{display:inline-flex;align-items:center;gap:5px;
  padding:5px 10px;background:rgba(255,255,255,.66);border:1px solid #ddd8ce;
  border-radius:5px;font-size:11px;color:#565b5d;text-decoration:none}
```

### 10.5 事件卡分级 + 多列网格

A+ 单列深拆，A/B 级用 `grid-cards`（**不能用 `card-grid`**）包 2 列。
chead 改 chead-top（eyebrow 带 dot + event-num 右上角）+ h3 双行结构。

```css
.chead{display:flex;flex-direction:column;gap:10px;margin-bottom:14px}
.chead-top{display:flex;align-items:center;justify-content:space-between;gap:12px}
.chead .eyebrow{margin:0;font-size:11px;letter-spacing:.04em;
  display:inline-flex;align-items:center;gap:7px;padding:5px 9px;border-radius:5px;font-weight:650}
.card{padding:23px 23px 20px;margin-bottom:18px;border:1px solid var(--border);
  border-radius:13px;background:var(--surface);box-shadow:var(--shadow);
  display:flex;flex-direction:column;min-width:0}
.card[data-grade="ap"]{border-left:4px solid var(--accent)}
.card[data-grade="ap"] .eyebrow{color:#62533d;background:#f5f0e7;border:1px solid #eee4d4}
.card[data-grade="ap"] .eyebrow::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--accent)}
.card[data-grade="a"] .eyebrow{color:#3e6c65;background:#edf4f2;border:1px solid #e0ece8}
.card[data-grade="a"] .eyebrow::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--teal)}
.card[data-grade="b"] .eyebrow{color:#665783;background:#f1eef6;border:1px solid #e7e1f0}
.card[data-grade="b"] .eyebrow::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--violet)}
.event-num{font-size:11px;color:#aaa59a;letter-spacing:.12em}
.grid-cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin-bottom:24px}
.grid-cards > .card{margin-bottom:0}
@media (max-width:900px){.grid-cards{grid-template-columns:1fr}}
```

## 11. 我踩过的坑（暖色调 panel 化批次）

| 我写错的 | 现象 | 正确写法 |
|---|---|---|
| `class="card-grid"` | 门禁 `_card_bodies` 正则 `<div class="card[^"]*"` 把网格 div 当卡 → `?@4.6` 误报 | 改名 `grid-cards`（不以 `card` 开头） |
| ve-bars 在 390px 窄屏 | 标签缩到 11.97px（< 12px 门禁），SVG 缩放致标签变小 | 加 `@media (max-width:480px){.ve-bars{font-size:14px}}` 补偿 |
| sources-head 的 h2 与 span 用 flex 同行 | 渲染器报"heading sits 0 px from the span below it" | eyebrow span 在 h2 上方（block + margin-bottom），不要同行 |
| 批量包 grid-cards 用简单 `</div>` 匹配 | card 内含 `</details></div>`（一行两个 close）让深度归零提前，网格只包 1 张卡 | 用深度感知脚本（`opens-closes` 累计），遇 `</section>`/`<h3`/`<section` 关闭网格 |
| `:root` 覆盖深色主题不生效 | instrument register 深色默认优先级高 | 用 `html:root` + `@media (prefers-color-scheme: dark)` 内重复浅色值 |

assets/render_html.py
----------------------------------------
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用 visual-explainer 的 kit 渲染简报页面。

为什么不让 LLM 手写完整 HTML：kit 提供字体、token、figure 样式与一个会**测量**页面的
渲染器（标签最小字号、标签是否被边框穿过、是否横向溢出、图是否缺 caption）。这些错误
靠人眼看 HTML 源码查不出来，靠 LLM 读一遍自证也查不出来 —— 必须真的排版一次再量。

用法：
  python render_html.py --src 多源技术热点简报_2026-10-26.src.html
  python render_html.py --src ... --out 多源技术热点简报_2026-10-26.html
  python render_html.py --check            # 只打印找到的 kit 路径

定位顺序：
  1) --kit 参数
  2) 环境变量 VISUAL_EXPLAINER_KIT
  3) 与本 skill 同级的 visual-explainer（**首选，与客户端无关**）
     本文件在 $SKILL_DIR/assets/，故 skill 根目录 = Path(__file__).parent.parent，
     skills 根目录 = 其上一级。visual-explainer 通常与 tech-briefing-* 并列安装：
       <skills-root>/visual-explainer/plugins/visual-explainer/kit
       <skills-root>/visual-explainer/kit
  4) 常见客户端 skills 根目录（~/.cac、~/.claude、~/.dsh、~/.codex、~/.config 等），
     以及项目内 .<client>/skills —— 仅作兜底，不假设只存在某一种客户端
  5) PATH 中 `visual-explainer` 包（node_modules）

退出码：0 渲染通过；1 渲染器报 ✗（页面已写出，仍需修）；2 环境不可用
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

KIT_REL = Path("visual-explainer") / "plugins" / "visual-explainer" / "kit"
KIT_REL_FLAT = Path("visual-explainer") / "kit"

# 只用来兜底列举可能的客户端 skills 根目录名；不存在的直接跳过，绝不创建。
CLIENT_ROOTS = (".cac", ".claude", ".dsh", ".codex", ".agent", ".config")


def _kit_if_valid(p: Path) -> Path | None:
    p = p.expanduser()
    return p if (p / "render.mjs").exists() else None


def sibling_kit_candidates() -> list[Path]:
    """从本脚本自身位置推导，与客户端目录名无关。"""
    skill_dir = Path(__file__).resolve().parent.parent   # $SKILL_DIR
    out = []
    for base in (skill_dir.parent, skill_dir.parent.parent):
        out.append(base / KIT_REL)
        out.append(base / KIT_REL_FLAT)
    return out


def client_skill_roots() -> list[Path]:
    """兜底：常见客户端的 skills 根目录 + 当前工作目录内的同名目录。"""
    roots = []
    home = Path.home()
    bases = [home, Path.cwd()]
    for base in bases:
        for name in CLIENT_ROOTS:
            roots.append(base / name / "skills")
    return roots


def find_kit(explicit: str = "") -> Path | None:
    if explicit:
        return _kit_if_valid(Path(explicit))
    env = os.environ.get("VISUAL_EXPLAINER_KIT", "")
    if env:
        p = _kit_if_valid(Path(env))
        if p:
            return p
    for p in sibling_kit_candidates():
        hit = _kit_if_valid(p)
        if hit:
            return hit
    for root in client_skill_roots():
        for rel in (KIT_REL, KIT_REL_FLAT):
            hit = _kit_if_valid(root / rel)
            if hit:
                return hit
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="用 visual-explainer kit 渲染简报")
    ap.add_argument("--src", default="", help="页面源文件（.src.html）")
    ap.add_argument("--out", default="", help="输出文件；默认把 .src.html 换成 .html")
    ap.add_argument("--kit", default="", help="kit 目录（含 render.mjs）")
    ap.add_argument("--check", action="store_true", help="只报告 kit 是否可用")
    ap.add_argument("--no-check", action="store_true", help="跳过浏览器视觉检查（不推荐）")
    args = ap.parse_args()

    # 先把上一轮的产物删掉：无论后面是"找不到 kit"还是"渲染报错"，
    # 都不允许目录里留着一个看起来像本轮结果的旧 .html。
    # 这一步必须在任何可能失败的分支之前执行。
    if args.src:
        src = Path(args.src)
        out = Path(args.out) if args.out else src.with_name(
            src.name[:-len(".src.html")] + ".html" if src.name.endswith(".src.html")
            else src.stem + ".html")
        if out.resolve() != src.resolve() and out.exists():
            out.unlink()

    kit = find_kit(args.kit)
    if kit is None:
        print("找不到 visual-explainer kit。安装：agentcenter skill 安装 visual-explainer，"
              "或用 --kit / VISUAL_EXPLAINER_KIT 指定包含 render.mjs 的目录。",
              file=sys.stderr)
        return 2
    node = shutil.which("node")
    if not node:
        print("找不到 node（visual-explainer 的渲染器需要 Node 18+）", file=sys.stderr)
        return 2
    if args.check:
        print(f"kit  : {kit}")
        print(f"node : {node}")
        return 0
    if not args.src:
        print("缺少 --src", file=sys.stderr)
        return 2

    if not src.exists():
        print(f"源文件不存在: {src}", file=sys.stderr)
        return 2
    if out.suffix != ".html":
        print(f"输出必须是 .html: {out}", file=sys.stderr)
        return 2

    cmd = [node, str(kit / "render.mjs"), str(src), "-o", str(out)]
    if args.no_check:
        cmd.append("--no-check")
    print("渲染:", " ".join(cmd))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print("渲染器报错或视觉检查未通过；修 .src.html 后重跑，不要手改 .html",
              file=sys.stderr)
        return 1
    if not out.exists():
        print(f"渲染器退出码为 0 但没有产出文件: {out}", file=sys.stderr)
        return 2
    print(f"OK  {out}  ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

assets/render_report.py
----------------------------------------
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用内置 report_engine 把简报 Markdown 渲染成自包含 HTML。

为什么让 LLM 只写 Markdown：手写完整 HTML 时，每张卡片的 DOM 结构、类名、
内联样式都要 LLM 逐字产出，token 花在"套模板"而不是"讲清楚技术判断"上。
Markdown 只承载内容，样式与交互（目录、脚注、评注、导出）由渲染器机械生成。

交付约定（方案 1）：
  所有简报统一落在 $WORKDIR/reports/ 下，该目录同时是报告库根目录 ——
  render 末尾会扫这个目录生成 index.json / index.html，并把索引快照回写进
  每份 HTML，使 Ctrl-O 切换器在 file:// 下可用。

    $WORKDIR/reports/<标题 slug>-<YYYY-MM-DD>.md     ← LLM 写的工作源
    $WORKDIR/reports/<标题 slug>-<YYYY-MM-DD>.html   ← 交付物
    $WORKDIR/reports/index.json / index.html         ← 报告库索引（自动生成）

.md 不是第二份交付物：HTML 内嵌了完整 Markdown，页面里「Save as MD」即可导出。
因此不需要另外维护一份 .md 副本。

用法：
  python render_report.py --md reports/xxx-2026-10-27.md
  python render_report.py --md ... --open          # 顺带起本地评注服务
  python render_report.py --check                  # 只打印引擎与 node 路径

退出码：0 渲染成功；1 渲染器报错；2 环境或参数不可用
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ENGINE_SUBDIR = "report_engine"
INDEX_FILES = ("index.json", "index.html")


def engine_dir() -> Path:
    """引擎随 skill 分发，位置由本文件自推，与客户端目录名无关。"""
    return Path(__file__).resolve().parent / ENGINE_SUBDIR


def reports_dir() -> Path:
    """报告库根目录 = 当前工作目录下的 reports/。"""
    return (Path.cwd() / "reports").resolve()


def same_path(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description="把简报 Markdown 渲染成自包含 HTML")
    ap.add_argument("--md", default="", help="简报 Markdown 源文件（应位于 reports/ 下）")
    ap.add_argument("--open", action="store_true", help="渲染后起本地评注服务并打开浏览器")
    ap.add_argument("--check", action="store_true", help="只报告引擎与 node 是否可用")
    ap.add_argument("--allow-outside", action="store_true",
                    help="允许源文件不在 reports/ 下（破坏报告库索引一致性，仅用于排查）")
    args = ap.parse_args()

    eng = engine_dir()
    node = shutil.which("node")
    render_js = eng / "render.mjs"

    if not render_js.exists():
        print(f"找不到渲染引擎: {render_js}\n"
              f"引擎应随 skill 一起分发在 {eng}，缺失说明 skill 安装不完整。",
              file=sys.stderr)
        return 2
    if not node:
        print("找不到 node（渲染器需要 Node 18+）", file=sys.stderr)
        return 2
    if args.check:
        print(f"engine : {eng}")
        print(f"node   : {node}")
        print(f"reports: {reports_dir()}")
        return 0
    if not args.md:
        print("缺少 --md", file=sys.stderr)
        return 2

    src = Path(args.md)
    if not src.exists():
        print(f"源文件不存在: {src}", file=sys.stderr)
        return 2
    if src.suffix != ".md":
        print(f"源文件必须是 .md: {src}", file=sys.stderr)
        return 2

    rdir = reports_dir()
    if not args.allow_outside and not same_path(src.parent, rdir):
        print(f"源文件必须写在 reports/ 下，否则它不会进入报告库索引。\n"
              f"  期望目录: {rdir}\n"
              f"  实际位置: {src.resolve()}\n"
              f"把 .md 移到 reports/ 后重跑；确需在别处渲染加 --allow-outside。",
              file=sys.stderr)
        return 2

    cmd = [node, str(render_js), str(src)]
    if not args.open:
        cmd.append("--no-open")

    print("渲染:", " ".join(cmd))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print("渲染器报错；修 Markdown 后重跑，不要手改生成的 HTML",
              file=sys.stderr)
        return 1

    out = src.with_suffix(".html")
    if not out.exists():
        print(f"渲染器退出码为 0 但没有产出文件: {out}", file=sys.stderr)
        return 2

    # 报告库索引是本路线的核心交付能力之一：渲染完必须确认索引真的更新了，
    # 否则 Ctrl-O / Reports 按钮会静默地看不到这份报告。
    missing = [n for n in INDEX_FILES if not (src.parent / n).exists()]
    if missing:
        print(f"警告: 报告库索引缺失 {missing} —— Ctrl-O 与 Reports 按钮将不可用。",
              file=sys.stderr)

    print(f"OK  {out}  ({out.stat().st_size} bytes)")
    idx = src.parent / "index.json"
    if idx.exists():
        try:
            data = json.loads(idx.read_text(encoding="utf-8"))
            print(f"    报告库: {data.get('report_count', 0)} 份  ({src.parent / 'index.html'})")
        except (OSError, json.JSONDecodeError):
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

assets/report_engine/build-index.mjs
----------------------------------------
/*
 * build-index.mjs — scan a reports/ directory, build index.json + index.html,
 * and sweep the inline <script id="report-index"> block in every report.
 *
 * Used by render.mjs at end-of-render. Pure Node, no dependencies.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// Windows: new URL(...).pathname gives "/D:/...", and path.join turns that into "D:\D:\...".
// fileURLToPath handles drive letters and percent-decoding.
const INDEX_TEMPLATE_PATH = path.join(path.dirname(fileURLToPath(import.meta.url)), 'index-template.html');

// ---------- frontmatter extraction ----------

const SOURCE_MD_RE = /<script id="source-md"[^>]*>([\s\S]*?)<\/script>/;
const FRONTMATTER_RE = /^---\r?\n([\s\S]*?)\r?\n---/;

export function extractFrontmatterFromHtml(html) {
  const scriptMatch = SOURCE_MD_RE.exec(html);
  if (!scriptMatch) return null;
  const mdBody = scriptMatch[1].trim();
  const fmMatch = FRONTMATTER_RE.exec(mdBody);
  if (!fmMatch) return null;
  const meta = {};
  for (const line of fmMatch[1].split(/\r?\n/)) {
    const mm = line.match(/^([\w_-]+):\s*(.*)$/);
    if (!mm) continue;
    let [, key, val] = mm;
    val = val.trim();
    if (val.startsWith('[') && val.endsWith(']')) {
      val = val.slice(1, -1).split(',').map(s => s.trim().replace(/^["']|["']$/g, '')).filter(Boolean);
    } else if (/^["'].*["']$/.test(val)) {
      val = val.slice(1, -1);
    }
    meta[key] = val;
  }
  return meta;
}

// ---------- entry projection ----------

const OPTIONAL_KEYS = ['tags', 'version', 'eyebrow', 'generated_by', 'sources'];

function deriveSlug(filename) {
  return filename
    .replace(/\.html$/, '')
    .replace(/-\d{4}-\d{2}-\d{2}$/, '');
}

function countWords(html) {
  const stripped = html
    .replace(/<script[\s\S]*?<\/script>/g, '')
    .replace(/<style[\s\S]*?<\/style>/g, '')
    .replace(/<[^>]+>/g, ' ');
  const tokens = stripped.split(/\s+/).filter(Boolean);
  return tokens.length;
}

function projectEntry(filename, html, stat, fm) {
  const slug = deriveSlug(filename);
  const wordCount = countWords(html);
  const readingTime = Math.max(1, Math.round(wordCount / 220));
  const entry = {
    slug,
    href: filename,
    title: fm.title || '(untitled)',
    summary: fm.summary || '',
    date: fm.date || '1970-01-01',
    status: fm.status || 'draft',
    reading_time_min: readingTime,
    word_count: wordCount,
    last_modified: stat.mtime.toISOString(),
  };
  for (const key of OPTIONAL_KEYS) {
    if (fm[key] !== undefined && fm[key] !== '' && !(Array.isArray(fm[key]) && fm[key].length === 0)) {
      entry[key] = fm[key];
    }
  }
  return entry;
}

// ---------- buildIndex ----------

export function buildIndex(reportsDir) {
  const entries = [];
  if (!fs.existsSync(reportsDir)) {
    return { generated_at: new Date().toISOString(), report_count: 0, reports: [] };
  }
  for (const name of fs.readdirSync(reportsDir)) {
    if (!name.endsWith('.html')) continue;
    if (name === 'index.html') continue;
    const full = path.join(reportsDir, name);
    const stat = fs.statSync(full);
    if (!stat.isFile()) continue;
    const html = fs.readFileSync(full, 'utf8');
    const fm = extractFrontmatterFromHtml(html);
    if (!fm) {
      process.stderr.write(`skipped: ${name} — no embedded source\n`);
      continue;
    }
    entries.push(projectEntry(name, html, stat, fm));
  }
  entries.sort((a, b) => {
    if (a.date !== b.date) return a.date < b.date ? 1 : -1;
    if (a.last_modified !== b.last_modified) return a.last_modified < b.last_modified ? 1 : -1;
    return a.slug < b.slug ? -1 : (a.slug > b.slug ? 1 : 0);
  });
  return {
    generated_at: new Date().toISOString(),
    report_count: entries.length,
    reports: entries,
  };
}

// ---------- JSON-in-script-tag safety ----------

export function safeJsonForScript(obj) {
  // JSON.stringify does not escape "<", which means an attacker-controlled or
  // accidentally-included "</script>" inside any string field would close the
  // surrounding <script> tag and break the page. Escape the slash inside any
  // closing-tag-like sequence so the JSON parses identically but the HTML
  // tokenizer cannot exit the script element early.
  return JSON.stringify(obj, null, 2).replace(/<\/(script)/gi, '<\\/$1');
}

// ---------- write index.json and (Task 8) index.html ----------

export function writeIndexArtifacts(reportsDir, index) {
  const jsonPath = path.join(reportsDir, 'index.json');
  const tmpJsonPath = jsonPath + '.tmp';
  fs.writeFileSync(tmpJsonPath, JSON.stringify(index, null, 2) + '\n', 'utf8');
  fs.renameSync(tmpJsonPath, jsonPath);

  const htmlPath = path.join(reportsDir, 'index.html');
  const tmpHtmlPath = htmlPath + '.tmp';
  fs.writeFileSync(tmpHtmlPath, renderIndexHtml(index), 'utf8');
  fs.renameSync(tmpHtmlPath, htmlPath);
}

const STATUS_LABEL = { 'draft': 'Draft', 'in-review': 'In review', 'reviewed': 'Reviewed', 'final': 'Final' };

function escAttr(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]));
}
function escText(s) {
  return String(s == null ? '' : s).replace(/[&<>]/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;' }[c]));
}

function renderRow(r) {
  const tags = Array.isArray(r.tags) ? r.tags.join(' · ') : '';
  const status = r.status || 'draft';
  const label = STATUS_LABEL[status] || status;
  return `<tr tabindex="0" data-href="${escAttr(r.href)}">` +
    `<td class="col-date">${escText(r.date)}</td>` +
    `<td class="col-title"><a href="${escAttr(r.href)}">${escText(r.title)}</a></td>` +
    `<td class="col-tags">${escText(tags)}</td>` +
    `<td class="col-read">${escText(r.reading_time_min + 'm')}</td>` +
    `<td class="col-status"><span class="status-dot status-dot--${escAttr(status)}"></span>${escText(label)}</td>` +
  `</tr>`;
}

export function renderIndexHtml(index) {
  const template = fs.readFileSync(INDEX_TEMPLATE_PATH, 'utf8');
  const countLabel = index.report_count === 1
    ? '1 report'
    : `${index.report_count} reports`;
  const tbodyHtml = (index.reports || []).map(renderRow).join('\n');
  return template
    .replace('{{REPORT_COUNT_LABEL}}', countLabel)
    .replace('{{REPORTS_TBODY}}', tbodyHtml)
    .replace('{{REPORTS_JSON}}', safeJsonForScript(index));
}

// ---------- sweep inline snapshots ----------

const REPORT_INDEX_RE = /<script id="report-index" type="application\/json">[\s\S]*?<\/script>/;

export function sweepInlineIndex(reportsDir, index) {
  if (!fs.existsSync(reportsDir)) return;
  for (const name of fs.readdirSync(reportsDir)) {
    if (!name.endsWith('.html')) continue;
    if (name === 'index.html') continue;
    const full = path.join(reportsDir, name);
    try {
      const stat = fs.statSync(full);
      if (!stat.isFile()) continue;
      const html = fs.readFileSync(full, 'utf8');
      if (!REPORT_INDEX_RE.test(html)) continue;
      const slug = deriveSlug(name);
      const snapshot = { ...index, current_slug: slug };
      const block = `<script id="report-index" type="application/json">\n${safeJsonForScript(snapshot)}\n</script>`;
      const next = html.replace(REPORT_INDEX_RE, block);
      if (next !== html) {
        fs.writeFileSync(full, next, 'utf8');
      }
    } catch (err) {
      process.stderr.write(`sweep: ${name} — ${err.message}\n`);
    }
  }
}


assets/report_engine/clean-comments.mjs
----------------------------------------
#!/usr/bin/env node
/*
 * clean-comments.mjs — remove @report-comment markers from a rendered report.
 *
 * Usage:
 *   node clean-comments.mjs <input.html>
 *
 * The script extracts the embedded Markdown, strips all review comment markers,
 * and re-renders the same HTML path so visible review annotations disappear too.
 */

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { cleanReportComments, extractEmbeddedMarkdown } from './comments.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function usage() {
  console.error('Usage: node clean-comments.mjs <input.html>');
}

const args = process.argv.slice(2);
if (args.length !== 1) {
  usage();
  process.exit(1);
}

const htmlPath = path.resolve(args[0]);
if (!fs.existsSync(htmlPath)) {
  console.error(`error: input not found: ${htmlPath}`);
  process.exit(1);
}

const html = fs.readFileSync(htmlPath, 'utf8');
let markdown;
try {
  markdown = extractEmbeddedMarkdown(html);
} catch (error) {
  console.error(`error: ${error.message}`);
  process.exit(2);
}

const cleaned = cleanReportComments(markdown).trim() + '\n';
const tempPath = path.join(os.tmpdir(), `report-clean-${process.pid}-${Date.now()}.md`);

try {
  fs.writeFileSync(tempPath, cleaned, 'utf8');
  execFileSync('node', [path.join(__dirname, 'render.mjs'), tempPath, htmlPath], { stdio: 'pipe' });
  console.log(`✓ cleaned report comments: ${htmlPath}`);
} finally {
  try {
    fs.unlinkSync(tempPath);
  } catch {
    // Best effort cleanup only.
  }
}


assets/report_engine/comments.mjs
----------------------------------------
const MARKER_RE = /<!--\s*@report-comment\s+([^\n\r]*)\r?\n([\s\S]*?)-->/g;

function escapeAttr(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function unescapeAttr(value) {
  return String(value ?? '')
    .replace(/&quot;/g, '"')
    .replace(/&gt;/g, '>')
    .replace(/&lt;/g, '<')
    .replace(/&amp;/g, '&');
}

function parseAttrs(source) {
  const attrs = {};
  const re = /([a-zA-Z_:-]+)="([^"]*)"/g;
  let match;
  while ((match = re.exec(source))) {
    attrs[match[1]] = unescapeAttr(match[2]);
  }
  return attrs;
}

function splitResolvedNote(text) {
  const normalized = String(text ?? '').trim();
  const match = normalized.match(/(?:^|\n{2,})Resolved:\s*([\s\S]*?)\s*$/);
  if (!match) return { body: normalized, resolvedNote: '' };
  return {
    body: normalized.slice(0, match.index).trim(),
    resolvedNote: match[1].trim(),
  };
}

export function parseReportComments(markdown) {
  const comments = [];
  let match;
  MARKER_RE.lastIndex = 0;
  while ((match = MARKER_RE.exec(markdown))) {
    const attrs = parseAttrs(match[1]);
    const { body, resolvedNote } = splitResolvedNote(match[2]);
    comments.push({
      id: attrs.id || '',
      status: attrs.status === 'resolved' ? 'resolved' : 'open',
      target: attrs.target || '',
      body,
      resolvedNote,
      raw: match[0],
      start: match.index,
      end: match.index + match[0].length,
    });
  }
  return comments;
}

export function filterReportComments(comments, status = 'all') {
  if (status === 'open' || status === 'resolved') {
    return comments.filter(comment => comment.status === status);
  }
  return comments;
}

export function formatReviewSummary(comments, title = 'Report') {
  const open = comments.filter(comment => comment.status !== 'resolved');
  const resolved = comments.filter(comment => comment.status === 'resolved');
  const sections = comments.map(comment => {
    const resolvedText = comment.resolvedNote
      ? `\n\nResolved: ${comment.resolvedNote}`
      : '';
    return `## ${comment.id} — ${comment.status || 'open'} — ${comment.target}\n\n${comment.body || ''}${resolvedText}\n`;
  });

  return [
    `# Review Comments: ${title}`,
    '',
    `Open comments: ${open.length}`,
    `Resolved comments: ${resolved.length}`,
    `Total comments: ${comments.length}`,
    '',
    ...sections,
  ].join('\n').replace(/\n{3,}/g, '\n\n').trim() + '\n';
}

export function serializeReportComment(comment) {
  const id = comment.id || createCommentId();
  const status = comment.status === 'resolved' ? 'resolved' : 'open';
  const target = comment.target || '';
  const body = String(comment.body ?? '').trim();
  const resolvedNote = String(comment.resolvedNote ?? '').trim();
  const resolvedText = status === 'resolved' && resolvedNote
    ? `\n\nResolved: ${resolvedNote}`
    : '';

  return `<!-- @report-comment id="${escapeAttr(id)}" status="${status}" target="${escapeAttr(target)}"\n${body}${resolvedText}\n-->`;
}

export function cleanReportComments(markdown) {
  return String(markdown).replace(MARKER_RE, '').replace(/\n{3,}/g, '\n\n');
}

export function deleteReportComment(markdown, id) {
  const comment = parseReportComments(markdown).find(c => c.id === id);
  if (!comment) return markdown;
  return markdown.slice(0, comment.start) + markdown.slice(comment.end);
}

export function updateReportComment(markdown, id, patch = {}) {
  const comment = parseReportComments(markdown).find(c => c.id === id);
  if (!comment) return markdown;
  const next = serializeReportComment({ ...comment, ...patch, id });
  return markdown.slice(0, comment.start) + next + markdown.slice(comment.end);
}

// Replace the prose body of `currentMarkdown` with `newBody`, preserving any
// existing @report-comment markers re-anchored to their original target
// blocks. Used by the review server's PUT /api/source so an in-browser edit
// does not wipe comments that live alongside the source.
export function replaceBodyKeepingComments(currentMarkdown, newBody) {
  const comments = parseReportComments(currentMarkdown);
  const incoming = cleanReportComments(newBody);
  if (!comments.length) return incoming;
  let result = incoming;
  for (const c of comments) {
    result = insertReportComment(result, {
      id: c.id,
      status: c.status,
      target: c.target,
      body: c.body,
      resolvedNote: c.resolvedNote,
    }, blockIndexFromTarget(c.target));
  }
  return result;
}

export function insertReportComment(markdown, comment, blockIndex = 0) {
  const starts = findMarkdownBlockStarts(markdown);
  const index = Math.max(0, Math.min(Number(blockIndex) || 0, starts.length));
  const offset = starts[index] ?? markdown.length;
  const marker = serializeReportComment(comment);
  const before = markdown.slice(0, offset).replace(/[ \t]+$/u, '');
  const after = markdown.slice(offset).replace(/^\n*/u, '');
  const separatorBefore = before.endsWith('\n\n') || before.length === 0 ? '' : '\n\n';
  const separatorAfter = after.length ? '\n\n' : '\n';
  return `${before}${separatorBefore}${marker}${separatorAfter}${after}`;
}

export function extractEmbeddedMarkdown(html) {
  const match = String(html).match(/<script id="source-md"[^>]*>([\s\S]*?)<\/script>/);
  if (!match) {
    throw new Error('No <script id="source-md"> block found.');
  }
  return match[1].replace(/^\r?\n/, '');
}

export function replaceEmbeddedMarkdown(html, markdown) {
  const source = String(html);
  const match = source.match(/(<script id="source-md"[^>]*>)([\s\S]*?)(<\/script>)/);
  if (!match) {
    throw new Error('No <script id="source-md"> block found.');
  }
  const normalized = String(markdown).replace(/\s*$/u, '\n');
  return source.slice(0, match.index)
    + `${match[1]}\n${normalized}${match[3]}`
    + source.slice(match.index + match[0].length);
}

export function createCommentId(existingIds = []) {
  const used = new Set(existingIds);
  for (let i = 1; i < 100000; i++) {
    const id = `c${i}`;
    if (!used.has(id)) return id;
  }
  return `c${Date.now().toString(36)}`;
}

export function blockIndexFromTarget(target) {
  const match = String(target || '').match(/^block:b(\d+)$/);
  if (!match) return 0;
  return Math.max(0, Number(match[1]) - 1);
}

export function findMarkdownBlockStarts(markdown) {
  const text = String(markdown);
  const lineMatches = [...text.matchAll(/^.*(?:\n|$)/gm)].filter(m => m[0].length > 0);
  const lines = lineMatches.map(match => ({
    text: match[0].replace(/\n$/u, ''),
    start: match.index,
  }));
  const starts = [];
  let i = 0;

  if (lines[0]?.text.trim() === '---') {
    i = 1;
    while (i < lines.length && lines[i].text.trim() !== '---') i++;
    if (i < lines.length) i++;
  }

  while (i < lines.length) {
    const line = lines[i].text;

    if (/^\s*$/.test(line)) {
      i++;
      continue;
    }

    if (/^\s*<!--\s*@report-comment\b/.test(line)) {
      i++;
      while (i < lines.length && !/-->\s*$/.test(lines[i - 1].text)) i++;
      continue;
    }

    starts.push(lines[i].start);

    if (/^```\s*/.test(line)) {
      i++;
      while (i < lines.length && !/^```\s*$/.test(lines[i].text)) i++;
      if (i < lines.length) i++;
      continue;
    }

    if (/^[-*]\s+/.test(line) || /^\d+\.\s+/.test(line)) {
      i++;
      while (i < lines.length && /^\s{2,}\S/.test(lines[i].text)) i++;
      continue;
    }

    if (/^>\s?/.test(line)) {
      i++;
      while (i < lines.length && /^>\s?/.test(lines[i].text)) i++;
      continue;
    }

    if (line.includes('|') && i + 1 < lines.length && /^[\s|:\-]+$/.test(lines[i + 1].text) && lines[i + 1].text.includes('-')) {
      i += 2;
      while (i < lines.length && lines[i].text.includes('|') && !/^\s*$/.test(lines[i].text)) {
        starts.push(lines[i].start);
        i++;
      }
      continue;
    }

    if (i + 1 < lines.length && /^:\s+/.test(lines[i + 1].text)) {
      i += 2;
      while (i < lines.length && /^\s{2,}\S/.test(lines[i].text)) i++;
      continue;
    }

    i++;
    while (
      i < lines.length
      && !/^\s*$/.test(lines[i].text)
      && !/^(#{1,4})\s+/.test(lines[i].text)
      && !/^[-*]\s+/.test(lines[i].text)
      && !/^\d+\.\s+/.test(lines[i].text)
      && !/^>\s?/.test(lines[i].text)
      && !/^!\[.*\]\(.*\)\s*$/.test(lines[i].text)
      && !/^```/.test(lines[i].text)
    ) {
      i++;
    }
  }

  return starts;
}


assets/report_engine/extract.mjs
----------------------------------------
#!/usr/bin/env node
/*
 * extract.mjs — pull the embedded source Markdown out of a rendered HTML report.
 *
 * Every report rendered by render.mjs embeds its original Markdown source inside
 *   <script id="source-md" type="text/markdown"> ... </script>
 *
 * This script reads that block and writes it to a .md file, so the report can
 * be edited and re-rendered.
 *
 * Usage:
 *   node extract.mjs <input.html> [output.md]
 *
 * If [output.md] is omitted, writes to a sibling file with the same basename
 * but .md extension (e.g. report.html → report.md).
 *
 * Refuses to overwrite an existing .md unless --force is passed.
 */

import fs from 'node:fs';
import path from 'node:path';

const args = process.argv.slice(2);
const force = args.includes('--force');
const positional = args.filter(a => !a.startsWith('--'));

if (positional.length < 1) {
  console.error('Usage: node extract.mjs <input.html> [output.md] [--force]');
  process.exit(1);
}

const inputPath = path.resolve(positional[0]);
if (!fs.existsSync(inputPath)) {
  console.error(`error: input not found: ${inputPath}`);
  process.exit(1);
}

const html = fs.readFileSync(inputPath, 'utf8');
const m = html.match(/<script id="source-md"[^>]*>\s*([\s\S]*?)\s*<\/script>/);
if (!m) {
  console.error('error: no <script id="source-md"> block found in input HTML.');
  console.error('hint: this report may have been rendered without an embedded source, or hand-edited.');
  process.exit(2);
}

const md = m[1].trim() + '\n';

const outputPath = positional[1]
  ? path.resolve(positional[1])
  : path.join(path.dirname(inputPath), path.basename(inputPath, path.extname(inputPath)) + '.md');

if (fs.existsSync(outputPath) && !force) {
  console.error(`error: output already exists: ${outputPath}`);
  console.error('hint: pass --force to overwrite, or specify a different output path.');
  process.exit(3);
}

fs.writeFileSync(outputPath, md, 'utf8');
console.log(`✓ extracted: ${outputPath}`);


