---
name: tech-briefing-new
description: 生成 Asia/Shanghai 时区下从昨日 00:00 到执行时刻的多源技术热点简报，采集、分析、成稿并输出自包含 HTML。用户说"生成技术简报""今日技术简报""跑一下技术简报"或要求重新生成时触发。
allowed-tools:
  - Bash(python:*)
  - Bash(curl:*)
  - Bash(ls:*)
  - Bash(rm:raw_*/*)
  - Bash(rm:reports/*)
  - Bash(rm:events_run_*/*)
  - Bash(mkdir:*)
  - Bash(date:*)
  - Bash(powershell:*)
  - Bash(node:*)
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - TaskCreate
  - TaskUpdate
  - TaskList
  - TaskGet
when_to_use: |
  Use when the user references the tech briefing workflow or asks to regenerate today's briefing.
  The skill handles the full pipeline: time window freezing, multi-source data collection,
  candidate pool construction, abstraction/clustering/rating, HTML generation, and acceptance verification.
---

# 多源技术热点简报生成

生成 Asia/Shanghai 时区下，从"昨日 00:00"开始至"任务实际执行时刻"为止的"多源技术热点简报"，
默认交付完整、可独立打开的高信息密度 HTML 文件。

## 目录结构

本 skill 自包含全部引擎与骨架，不依赖任何项目目录。**根目录按运行时的真实安装位置解析，
```
$SKILL_DIR/                           # 本 skill 的安装目录（SKILL.md 所在目录）
├── SKILL.md                          # 本文件（skill 定义）
├── assets/                           # 只读引擎 + 稳定骨架
│   ├── tech_report_task_def.md       # 24KB 完整任务定义（规则源）
│   ├── sources.py                    # 源注册表（实体 × 面 × 提取模式）
│   ├── extract.py                    # 条目提取层（rss/atom/json/md/html/sitemap）
│   ├── coverage.py                   # 三级状态对账 + 窗口覆盖度 + 快照差分
│   ├── collect_sources.py            # 采集主流程
│   ├── build_pool.py                 # P1 候选池构建（归窗 + 无日期条目差分）
│   ├── gap_tasks.py                  # 覆盖缺口 → 可执行补检任务
│   ├── verify_gates.py               # Gate 校验器（机器可判，校验 .md 工作源）
│   ├── render_report.py              # MD 路线渲染包装层（调 report_engine 把 .md → .html）
│   ├── report_engine/                # 内置 MD→HTML 渲染引擎（纯 Node 零依赖）
│   │   ├── render.mjs                #   渲染器主入口（含 slug/unstash/Windows 路径修复）
│   │   ├── template.html             #   自包含 HTML 模板（TOC/脚注/评注/导出）
│   │   ├── build-index.mjs           #   报告库索引生成（index.json + index.html）
│   │   └── ...                       #   comments/review/extract 等配套脚本
│   ├── events.py                     # 事件 JSON 规范化（event_key / 枚举 / schema）
│   ├── thesis_registry.py            # Thesis registry v2（召回 / 事务入库 / 派生状态 / 报告）
│   ├── taxonomy.py                   # 分类映射 API（54 叶子 ↔ 11 栏目 ↔ 8 章）
│   ├── test_*.py                     # 单测（taxonomy / gates / extract / coverage / registry / events）
│   └── thesis_ontology.json          # Upper Ontology 骨架 + taxonomy 定义
├── references/                       # 按需读取的参考
│   ├── design-constraints.md         # P5 设计约束（写作侧 + 排版侧）
│   ├── design-rationale.md           # 设计决策记录
│   └── registry-v2-design.md         # Thesis registry v2 设计
└── data/                             # 只读参考资料（四层技术地图等）
```

**工作目录**（用户执行 skill 时所在的目录）存放运行时产物：
- `raw_<date>/` — 原始字节 + `items_<source>.json` 提取条目 + `collect_report.json` + `gap_tasks.json`
- `snapshots/surface_snapshot.json` — 跨 run 的条目 uid 快照，用于官方面差分
- `events_run_<date>/` — 本轮事件 JSON 文件 + `thesis_report.json`（第 7 章输入）
- `state/` — registry 状态（`thesis_registry.json` + `registry_log.jsonl`），跨 run 累积；
  可用 `TECH_BRIEFING_STATE` 指向共享目录
- `reports/` — **简报交付目录（方案 1：所有简报统一落此）**
  - `<标题 slug>-<YYYY-MM-DD>.md` — LLM 手写的工作源（唯一手写产物）
  - `<标题 slug>-<YYYY-MM-DD>.html` — 交付用的自包含页面（机械渲染，勿手改）
  - `index.json` / `index.html` — 报告库索引（render 末尾自动生成，Ctrl-O / Reports 按钮依赖它）

**路径变量**（下文统一使用）：
- `$SKILL_DIR` = 本 skill 的安装目录（即当前 `SKILL.md` 所在目录，由客户端决定，
  可能是 `~/.cac/skills/<name>`、`~/.claude/skills/<name>`、`~/.dsh/skills/<name>`、
  项目内 `.cac/skills/<name>` 等任意位置）。**不要写死客户端目录名。**
  若不确定具体位置，用 `Glob` 找本 skill 的 `SKILL.md`（同目录必须有
  `assets/tech_report_task_def.md`），其父目录就是 `$SKILL_DIR`。
- `$ASSETS` = `$SKILL_DIR/assets`
- `$DATA` = `$SKILL_DIR/data`
- `$WORKDIR` = 当前工作目录（用户执行 skill 时所在的目录）

**硬约束：只读本 skill 现有目录，不新建客户端目录。**
- 不要在 `$WORKDIR` 之外创建任何目录，尤其不要为了"补齐路径"而 `mkdir ~/.cac/...`、
  `~/.claude/...` 之类的客户端根目录。
- `$ASSETS` 或 `$DATA` 不存在，说明 `$SKILL_DIR` 解析错了：回到上一条重新定位，
  **不要创建空目录顶替**。
- registry 状态写在 `$WORKDIR/state/`（或 `TECH_BRIEFING_STATE`），首次 ingest 时自动创建；
  不写进 skill 目录。

## 前置依赖

- **渲染引擎（默认 MD 路线必需）**：`$ASSETS/render_report.py` + `$ASSETS/report_engine/`。
  步骤 1 之前跑一次 `python "$ASSETS/render_report.py" --check` 确认引擎与 node 可用。
  引擎是 vendored 的纯 Node 零依赖实现，不依赖任何外部 skill。
- **任务定义**：`$ASSETS/tech_report_task_def.md`
  — 24KB 的完整任务定义，包含 TARGET_WINDOW Gate、五路召回、变化类型分类、
  技术命题映射、A/A+ 评级标准、八章结构规范等全部规则。
  **必须在步骤 1 之前读取此文件，并严格遵守其中的全部规则。**
- **采集脚本**：`$ASSETS/collect_sources.py`
  — 多源数据采集脚本，已针对华为 MWG 代理网关优化（UA 分流、HF 镜像、重试、fallback）。
- **Thesis Registry 三件套**：
  - `$ASSETS/thesis_ontology.json` — Upper Ontology 骨架（9 种变化类型、评级标准、评估链、`taxonomy` 分类定义）。**稳定骨架，由人工维护，不由 LLM 动态改写。**
  - `$ASSETS/taxonomy.py` — 分类映射 API：叶子 → 栏目、栏目 → 叶子、主技术路径解析、54/11 完整性校验。**分类查询一律走这里，不要在提示词里硬编码栏目与叶子的对应关系。**
    ```
    python $ASSETS/taxonomy.py leaves            # 54 叶子全表
    python $ASSETS/taxonomy.py columns           # 11 栏目
    python $ASSETS/taxonomy.py chapter 4         # 某章及其栏目
    python $ASSETS/taxonomy.py resolve B1.1      # 主技术路径 → 栏目 + 锚点
    python $ASSETS/taxonomy.py validate          # 完整性校验
    ```
  - `$ASSETS/events.py` — 事件规范化；`$ASSETS/thesis_registry.py` — registry v2
    （candidates / ingest / report / show / search / merge / retire / revise / supersede），
    状态在 `$WORKDIR/state/`，设计见 `references/registry-v2-design.md`。

## Goal

在 `$WORKDIR/reports/` 下生成 `<标题 slug>-YYYY-MM-DD.md` 工作源及其渲染出的自包含 `.html`，满足：
1. TARGET_WINDOW 正确冻结（昨日 00:00 → 今日执行时刻 Asia/Shanghai）
2. 包含完整八章结构
3. 通过 `verify_gates.py` 机器校验 + 人工复核表
4. 采集报告 collect_report.json 落盘到 `$WORKDIR`
5. 必须先运行 collect_sources.py 采集数据，不能跳过采集步骤
6. Thesis registry 正确读写（normalize + candidates + 裁决 + ingest + report），第 7 章取自 report

## Steps

### 1. 冻结 TARGET_WINDOW 并读取任务定义

获取真实当前运行时刻 NOW_UTC，转换到 Asia/Shanghai 时区：
`NOW_SHANGHAI = convert_timezone(NOW_UTC, "Asia/Shanghai")`。
用 PowerShell 确认：`powershell -Command "[TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, 'China Standard Time').ToString('yyyy-MM-dd HH:mm:ss')"`。

计算：
- `WINDOW_START_DATE = date(NOW_SHANGHAI) - 1 calendar day`
- `WINDOW_START = WINDOW_START_DATE 00:00:00 Asia/Shanghai`
- `WINDOW_END = NOW_SHANGHAI`
- `TARGET_WINDOW = [WINDOW_START, WINDOW_END]`
- `SCAN_WINDOW = WINDOW_START - 6 hours → WINDOW_END`（缓解跨时区漏检）

冻结后，本轮采集、检索、筛选、事件归属、标题、正文、文件名、8.2 Event Index 都必须使用同一窗口。

读取 `$ASSETS/tech_report_task_def.md` 全文。

<HARD-GATE>
读完 `tech_report_task_def.md` 全文前，禁止进入步骤 2。
未读规则就开干，会导致窗口冻结、评级、八章结构全部偏移，整轮作废。
</HARD-GATE>

**Success criteria**:
- 已获取 NOW_SHANGHAI 真实时刻（非系统默认时区、非历史文件名推导）
- TARGET_WINDOW 已冻结，WINDOW_START / WINDOW_END 明确
- tech_report_task_def.md 已读取并理解

**Rules**:
- <HARD-GATE>
  禁止使用用户时区、浏览器时区、系统默认时区、上一轮日期、历史文件名、历史正文推导 TARGET_WINDOW。
  违反则窗口边界错位，采集/事件归属/文件名全部失配，门禁在步骤 6 才暴露但已无法回溯。
  </HARD-GATE>
- 昨日 00:00 之前首次发布的事件不得作为本轮"新事件"进入正文
- 无法确认首发时刻的高价值候选必须标注"首发时间未完全核实"
- **`collect_sources.py` 不要传 `--date`**。它把 `--date` 当"今天"，再减一天算 WINDOW_START：
  传 `--date 2026-10-26` 会得到 WINDOW_START = **10-25**，整轮采集作废重跑。
  正确做法是不传，让脚本用真实今天；只在**补采历史某天**时才传，且传的是"那一天"。
- **两处日期不是同一个**，不要互相推导：
  - `raw_<date>/` 的 date = 脚本运行的**今天**（`target_date`）
  - `reports/<标题 slug>-<date>.md` / `.html` 的 date = **WINDOW_START_DATE**（昨天）
  - `events_run_<date>/` 的 date = **WINDOW_START_DATE**，与输出文件名一致
  例：10-27 运行 → `raw_2026-10-27/`、`events_run_2026-10-26/`、`reports/<标题 slug>-2026-10-26.md`。
  门禁按 `collect_report.json` 的 `target_window.start` 校验文件名，推错会在步骤 6 才暴露。
- 步骤 1 结束前跑一次 `python "$ASSETS/render_report.py" --check`，确认引擎与 node 可用；
  等到步骤 5 才发现缺 node，等于把内容白写一遍。

### 2. 采集 + 提取 + 对账 + 生成补检任务

在工作目录下依次执行：
```bash
cd "$WORKDIR" && python "$ASSETS/collect_sources.py"
cd "$WORKDIR" && python "$ASSETS/gap_tasks.py" --report raw_<date>/collect_report.json --out raw_<date>/gap_tasks.json
```

**采集不是"抓字节"，是"证明每个面被看到了"。** 脚本产出三级状态，
任何一级失败都不会被下一级掩盖：

| 层级 | 取值 | 含义 |
|---|---|---|
| transport | ok / http_error / timeout / url_error | 网络层 |
| extract | ok / empty / parse_failed / blocked / skipped | 解析层（blocked=代理拦截页） |
| window | OK_IN_WINDOW / OK_OUT_OF_WINDOW / OK_EMPTY / OK_NO_DATES / OK_NEW_VIA_DIFF | 归窗层 |

**`OK_EMPTY` 与 `EMPTY` 必须分开**：前者是源结构正常、当天确实没有内容
（arXiv 周末、发布稀疏的厂商 blog），**不是失明，不产生补检**；
后者是空响应或结构被换掉，是真失明。把前者当失明会造出假缺口。

**第四级：窗口覆盖度**（`covered_quality`）。源"有 100 条窗口内条目"不等于
"窗口被覆盖"——单页 API 可能只覆盖 4 小时而窗口是 30 小时。采集端对分页源
做时间切片，逐片取回到窗口起点；未触底则标 `partial` 并进入补检。

**源注册表** `sources.py` 按 `实体 × 面（company/developer/product/code/
research/model/support/aggregator/community）× 提取模式` 登记。
新增/下线源只改这个文件，不改流程代码。

**必须区分的四种"空"**：
1. **没读到**（transport/extract 失败）→ 补检任务，必须换通道或申请权限
2. **读到了但窗口内无新增**（OK_OUT_OF_WINDOW）→ 正常结论，**不是失明，不产生补检**
3. **读到了但源结构正常、当天 0 条**（OK_EMPTY）→ 同样**不是失明**
4. **读到了但只覆盖窗口一段**（covered_quality=partial）→ 回溯该时段

把 2/3 当成 1 会让补检永远打在已经查过的地方；把 4 当成成功会让漏检藏进盲区。

**Success criteria**:
- `raw_<date>/collect_report.json` 已生成，含每条源的 `transport` /
  `extract` / `verdict` / `items_total` / `items_in_window` / `covered_quality`
- `raw_<date>/gap_tasks.json` 已生成，`tasks_open` 已知
- `raw_<date>/items_<source>.json` 存在（说明条目真的被提取出来了）

**Rules**:
- 必须运行采集脚本，不能跳过直接用历史数据
- 代理拦截页（HIS Proxy / Huawei Proxy / mwg-internal / 访问外部AI大模型）
  必须判为 `blocked`，**不得计为采集成功**
- **禁止用"HTTP 200"或"文件大小"作为采集成功的证据**；成功证据是 `items_count`
  与 `items_in_window`
- 采集失败的源不中断流程，但必须进入 `gap_tasks.json`
- 存在 `blocking` 缺口时不得直接成稿，先执行步骤 2.5

### 2.5 Gap-driven 补检（阻断性缺口必须清零）

读取 `raw_<date>/gap_tasks.json`，**逐条执行 open 状态的任务**。

每条任务给出：目标实体/面、失败源、检索式、换通道建议、验收条件。

**执行规则**：
- 检索式必须覆盖整个 SCAN_WINDOW，不得只搜 today
- 检索结果必须回溯官方原文确认首发时刻，不得用媒体转载日期
- 代理拦截类缺口（`fallback_channel` 非空）检索无效，必须换通道
- 完成任务后用 `python "$ASSETS/gap_tasks.py" --report ... --out ... \
  --mark-done GAP-xx --note "结论"` 标记
- **`tasks_blocking_open > 0` 或 `tasks_action_open > 0` 时都不得进入步骤 5 成稿**

任务分两档，严重度不同，**但都必须清零**：

| 任务类型 | 来源缺口 | 严重度 | 验收 |
|---|---|---|---|
| `surface_blind` / `critical_blind` | 整面失明（代理拦截、解析失败、空响应） | 阻断交付 | 该面在 SCAN_WINDOW 内有 N 条或确认 0 条 |
| `window_partial` | 面读到了，但窗口前半段从未被检索 | 必须处理 | 该时段有 N 条或确认 0 条（翻页/归档证据） |

`window_partial` 的源本身健康，只是单页 API / 每日批量发布覆盖不到窗口起点。
它**必须**产生任务并关闭——只留在 `collect_report.json` 的 `note` 里，
正文和 8.3 都会看不到它，静默截断就藏在这里。

关闭方式：给出"该时段有 N 条"或"确认 0 条"的结论并 `--mark-done`。
若缺口时段已由其他通道独立覆盖（如 Techmeme 缺时段由 HN 覆盖），
在 `--note` 里写清覆盖来源与条数即可。

**换通道手册（实测可用，按缺口类型查表）**

不要用"再搜一次"去关缺口——同一通道重搜命中率不会变。按下表换形态：

| 缺口 | 通道 | 做法 | 判定依据 |
|---|---|---|---|
| `window_partial` · Techmeme | **站点逐小时归档** | `https://www.techmeme.com/<YYMMDD>/h<HHMM>`，如 `/261025/h1200`（ET 时区）。取 4 小时间隔的几个快照即可覆盖窗口前半段；标题在 `<STRONG CLASS="L4"><A CLASS="ourh" HREF="…">` 里 | 页头 `<TITLE>Techmeme @ 12:00 PM ET, October 25, 2026` 给出快照时刻；去重后数条目 |
| `window_partial` · arXiv | **`pastweek` 归档 + 周历** | `https://arxiv.org/list/<cat>/pastweek?show=2000`，页内 `<h3>` 逐个给出 `Mon, 26 Oct 2026 (showing 189 of 189 entries)` | **周末无批次**：10-24/10-25 是周六周日，故 `window_start→周一 12:00` 段确认 0 条。这是合法空，不是失明 |
| `surface_blind` · Anthropic `company` | **产品 blog + sitemap + 聚合源** | `anthropic.com/news` 恒为 HIS 代理拦截页（4202B）；读 `claude.com/blog`、`claude.com/resources/articles/*`、`anthropic_sitemap.xml` | 命中条目要能打开原文；sitemap 的 4080 条 URL **无 `lastmod`**，不能用于时间差分 |
| `surface_blind` · 任意厂商 `code` 面 | **GitHub API** | `https://api.github.com/repos/<org>/<repo>` 取 `created_at` / `pushed_at` / `stargazers_count`；`releases.atom` 取发布时间 | release 的 `published` 是秒级，可直接归窗；仓库创建时间用来区分"新项目"与"老项目新热度" |
| 首发时刻存疑（媒体转载） | **原文元数据** | HTML 里找 `"datePublished"`、`article:published_time`、`<time datetime>`、页面可见日期行 | 三者矛盾时取官方页面可见日期，并在事件里写 `date_precision_note` |
| 代理拦截的整面 | **换形态** | HTML 首页 → `.md` / `.atom` / RSS / JSON API；仍不可达则登记 `UNCOVERABLE` | 拦截页识别：HIS Proxy / 华为代理 / `mwg-internal` / "访问外部AI大模型" 提示，正文不含目标内容 |

**关闭任务时的 note 必须可复核**：写清用了哪个通道、覆盖了哪段时间、去重后几条、
其中哪些落在 TARGET_WINDOW 内。只写"已核查无问题"等于没关。

**Success criteria**:
- `gap_tasks.json` 中 `tasks_blocking_open == 0` 且 `tasks_action_open == 0`
- 每条已关闭任务都有明确结论（"有 N 条更新（附 URL）"或"确认 0 条（附检查证据）"）
- 补检发现的新事件已加入候选池

### 3. P1 宽召回：构建候选池

**不要手工拼候选池**，用脚本：
```bash
cd "$WORKDIR" && python "$ASSETS/build_pool.py" --raw-dir raw_<date>
```
它合并 `items_<source>.json`、按 (源, uid) 去重、归窗，产出
`raw_<date>/candidate_pool.json` 与 `pool_out_of_window.json`。

**三类条目必须保留，不得因为"没法归窗"就扔掉：**

| 类型 | 处理 | 理由 |
|---|---|---|
| 有准确时刻且在窗口内 | `window_match=exact` | 确定事件 |
| 仅日粒度、区间与窗口相交 | `window_match=fuzzy` | 可能事件，引用时标精度 |
| **无日期字段** | `window_match=no_date`，**保留** | HF Trending / GitHub Trending / Google Dev Blog 属此类。它们是"模型热度、新仓库、官方新工具"的主要载体；按日期过滤会整源丢失 |
| 无标题（sitemap 的纯 URL） | 移到 `pool_out_of_window.json` | 无标题无法判断语义，只用于 surface diff |

`no_date` 条目不能直接当"本轮新事件"。`build_pool.py` 会给每条打
`freshness`：

| freshness | 含义 | 处置 |
|---|---|---|
| `new_since_last_run` | 相对上一快照新增 | 可作本轮新事件 |
| `carried_over` | 上轮就已在场 | **只能进第 5 章持续信号**，不得当新事件 |
| `baseline_unknown` | 首次运行、无基线 | 不得声称"本轮新增" |

**这是定时任务的核心纪律**：Trending 榜单（HF / GitHub）的条目会连续多天在场。
不区分"新上榜"与"仍在上轮名单"，同一批模型/仓库每天都会被当成新事件重复入选。

**快照基线只在跨日时前进**（`coverage.update_snapshots`）。同一自然日重跑
（失败重试、手工补跑）不覆盖基线，否则第二次运行的差分变成"与几分钟前的自己比"，
真正的新增会被静默抹掉。

**每次运行必须交付 TARGET_WINDOW 的全量简报，不是增量。** 这是硬约束：

| 概念 | 基准 | 用在哪 |
|---|---|---|
| **相对上一份简报**（跨日，如 10-26 对 10-25） | 上一份已交付简报 | `freshness=carried_over` 的判定，只用于**无日期源**（Trending 榜）避免重复计费 |
| **同一窗口内上一次执行**（同日不同时刻重跑） | **不作为任何去重基准** | 不适用 |

- 窗口内出现的每个事件都要进正文，无论它在上一次执行里是否已经写过。
  同一窗口跑两遍，两遍都应是**同样完整**的报告，不是"第二遍只写新增"。
- 上一轮窗口外的事件（首发早于 WINDOW_START）在本轮仍是窗口外，不因"上轮写过"而收录；
  这是窗口判定，不是增量判定。

窗口外条目保留在 `pool_out_of_window.json`，供 8.3 丢弃日志引证——
"为什么没进正文"必须有据可查，不能靠回忆。

对候选池的补充信号：
- `collect_report.json` 的 `diff`：相对上一快照的新增条目（`new_uids`）。
  这是官方 changelog 类源"本轮新增了什么"的直接证据，无需人工比对。
- `covered_quality` / `pagination`：判断某源的候选池是否完整可信。

候选池之外，仍需按 tech_report_task_def §2 的 Technology Watch Matrix 与
Expert Thesis Watch 做**语义补检**（机制/专家维度，无法靠源覆盖证明）。

五路召回通道：
- A. Entity Watch — Tier-1 厂商官方 blog（Anthropic/OpenAI/Google/Cloudflare/Mistral/MiniMax 等）
- B. arXiv source-native feeds — cs.AI/CL/LG/MA/RO
- C. Aggregator — Techmeme feed
- D. Social Signal — Hacker News top stories + GitHub Trending
- E. Expert Thesis Watch — Simon Willison / Latent Space / 专家博客圈

对每个候选项标注：
- 首发时刻（Asia/Shanghai）
- 来源 URL
- 召回通道
- 是否在 TARGET_WINDOW 内（本轮新事件 / Active Event / Historical Context）

**候选池筛选的实操顺序**（本轮实测有效，直接复用）

候选池动辄 2000+ 条，逐条读会淹没。按下面的顺序收敛：

```bash
# 1) 先排除"量大但重复度高"的两类：HN 与 arXiv 单独处理
# 2) 其余源按时间排序全量过一遍（通常 40~70 条，可读完）
python - <<'PY'
import json
pool=json.load(open('raw_2026-10-27/candidate_pool.json',encoding='utf-8'))
sel=[x for x in pool if x['src'] not in ('hn_newest','hn_front') and not x['src'].startswith('arxiv')]
for x in sorted(sel,key=lambda x:(x.get('published') or '')):
    print(f"{(x.get('published') or 'NONE')[:19]:19s} {x['window_match']:6s} {x['src'][:26]:26s} {x['title'][:100]}")
PY

# 3) HN 按 points 排序 + 技术关键词过滤（points 在 snippet 里：points=NNN comments=NN）
# 4) arXiv 按 title 关键词打分，再按公告类型筛
```

三条分工纪律：

| 源 | 排序/过滤 | 注意 |
|---|---|---|
| HN（`hn_newest` / `hn_front`） | 按 `points` 降序，再用技术词过滤；不按时间 | 低分条目（points ≤ 10）里仍有真信号（如 `Init` 9 分、`Compaction Laundering` 9 分），**不能只取高分**；但也不得因低分直接判 A 级 |
| arXiv | 按 title 关键词打分，**再按 `Announce Type` 分档** | `new` 才是本轮新投稿；`cross` 是跨分类转载；`replace` / `replace-cross` 是修订版。**修订版不能当新论文**，若 v2 在窗口内、v1 在窗口外，进正文时必须标"v2 修订" |
| 无日期源（`no_date`） | 不进本章正文，只作背景 | `carried_over` 的条目全部只能进第 5 章"持续热度" |

**摘要只有 300 字时不要猜机制**：arXiv RSS 的 `snippet` 常截断到 300 字符。
候选池只是召回证据，写事件卡前必须 `fetch` 原文（`arxiv.org/abs/<id>` 的
`<blockquote class="abstract">`、厂商 blog 的 `datePublished` + 正文）。

**省级素材（原文抓不到时）**：Techmeme 等聚合源的条目摘要若信息充分，足以支撑事件卡，
但必须在卡片上标"媒体摘要，未回溯原文"，并在 8.3 记为"官方原文未回溯"。

**Success criteria**:
- 全部源数据已解析
- 候选池构建完成，每个候选有首发时刻、来源、召回通道标注
- 明确区分"本轮新事件"与"Active Event / Historical Context"

### 4. P2-P4 抽象提升、聚类收敛、价值门控排序

按 tech_report_task_def.md 中的规则。本步同时与 **thesis registry** 交互，
保证跨 run 一致性（避免 thesis 命名漂移、支持跨时间收敛判断）。

**事件集的来源只有一个：本窗口的候选池。** 不从"上一次执行写了几个"出发：

```
候选池（本窗口全部条目）→ 抽象提升 → 评级 → 全部入选事件落盘 → 成稿
```

- 同一窗口重跑时，事件集**重新从候选池生成**，结果应与上一次执行的覆盖面一致
  （窗口更长则更多，不应更少）。
- 不要读 `events_run_<date>/` 里已有的 JSON 来决定"哪些还在"——那是上一次执行的产物，
  不是事实源。事实源是 `raw_<date>/candidate_pool.json`。
- 编号 EV-01..EV-NN 在本轮内连续自洽即可，不要求与上一次执行的编号对齐
  （8.2 与 `EV-*.json` 一一对应见下方"编号一致性"硬约束）。

**Registry v2**（设计见 `references/registry-v2-design.md`）：
- 参数（只读）：`$ASSETS/thesis_ontology.json` 的 `confidence_model` / `thesis_lifecycle` / `thesis_rules`
- 状态（可写）：`$STATE/thesis_registry.json`，`$STATE` 默认 `$WORKDIR/state`，可用 `--state` 或
  环境变量 `TECH_BRIEFING_STATE` 指向共享目录；同时追加审计日志 `registry_log.jsonl`
- 工具：`$ASSETS/events.py`（事件规范化）、`$ASSETS/thesis_registry.py`（召回 / 入库 / 报告 / 决策）

registry 只存证据（事件）、命题定义、两者的 link 与显式决策；命题的**状态、置信度、
Frontier/Convergence 类型都由证据派生**，不由 LLM 填写。

**P2 抽象提升**：对每个候选识别变化类型（CT-01..CT-09，见 ontology），映射到技术命题。
对每个候选事件构造 event 记录，保存为 `$WORKDIR/events_run_<date>/EV-xx.json`。

**必填字段**：

| 字段 | 说明 |
|---|---|
| `event_title` | 一句话说清技术变化，不是产品口号 |
| `evidence_form` | `paper` / `product` / `api` / `code` / `benchmark` / `deployment` / `expert`（置信度的跨形态维度靠它） |
| `thesis_decision` | 归属裁决，见 P3（A/A+ 必填） |
| `change_types` | `CT-01..CT-09` |
| `primary_path` | 主技术路径，通常到三级叶子；`A1`/`B1`/`C3` 必须下钻 |
| `related_domains` | 关联技术域，≤2 项 |
| `change_object` | `Model` / `Harness` / `运行平台` / `交互·应用` / `尚未披露` |
| `annotation` | 仅当 `primary_path` 落在 `4.6` 时必填：取 `python $ASSETS/taxonomy.py resolve <primary_path>` 输出的 `annotation`，不得自选 |
| `rating` / `signal` | 评级与信号（命题置信度由 registry 派生，事件里不写） |
| `first_publish_shanghai` | 换算后的 +08 时刻，配合 `date_precision` |
| `date_precision` | `second` / `day` / `batch` / `none`；为 `day` 时必须写 `date_precision_note` |
| `source` / `entity` / `key_data` | 来源、实体、关键定量 |
| `claims` | 逐条论点处置（见下） |

`tracks` 与 `sections` 已废弃：不要在事件里写，归属一律由 `primary_path`
经 `taxonomy.resolve()` 推出。写旧字段不会报错，但会让门禁与正文各算各的。

**写入方式**：可以用一次性脚本批量落盘（字段集合天然一致），也可以逐个写；
**写完必须规范化**，不要手填 `event_key`：

```bash
python "$ASSETS/events.py" normalize --events-dir events_run_<WINDOW_START_DATE>
```

它补 `event_key`（事件身份：arXiv 去版本号、GitHub release 取 org/repo@tag、URL 去 query），
统一枚举拼写，校验必填字段；有任何错误时一个文件都不改写。同一事件换了来源 URL 时，
在事件里写 `canonical_source` 指向原始来源。

`absorbed:<EV-xx>` 指向**本事件**（一个事件承载一个命题）；`separated:EV-xx` 才是
"拆成另一个事件"。

**编号一致性（硬约束）**：`EV-01.json` 的内容必须就是正文 8.2 里编号 `EV-01` 的那一行。
8.2 中出现的每个 EV 编号都必须有同名 JSON，**不允许"正文 14 条、落盘 3 条"**。
`first_publish_shanghai` 的时区与精度要求见 P6 验收"时区约束"段；
早于 WINDOW_START 的背景引用事件，JSON 保留真实时刻，8.2 那一行显式标
`Active Event`/`Historical`。

**P2 硬约束：claim inventory（逐条论点抽取）**

一份原文常含多个独立论点。**禁止对整篇只抽一条技术命题** —— 这会让同一个
事件只保留一个叙事角度，其余论点静默消失。

每个 A / A+ 事件必须在 event JSON 中写 `claims` 数组，每项：
```json
{"claim": "一句话原文论点", "change_types": ["CT-01"], "primary_path": "C2.1",
 "disposition": "absorbed:EV-03 | separated:EV-07 | discarded:重复",
 "reason": "处置理由（discarded 必填）"}
```
- `absorbed` — 由本事件承载（写本事件编号），本事件再经 `thesis_decision` 归属命题
- `separated` — 独立成一个事件（跨层/跨命题时必须分离）
- `discarded` — 丢弃，必须写理由

典型反例：Anthropic 关于"何时把 subagent 折叠进主 loop"的文章，若只被抽象成
"Agent Skills 标准化（→ AAIF）"，就丢掉了"并行/隔离/核验场景仍需 Subagent"
这个独立的架构边界命题。这两个 claim 必须分别处置。

**P3 硬约束：同实体不同系统层不得合并**

同一 Tier-1 实体在本窗口出现 ≥2 条候选时，**先按系统层分解**，每层独立评级、
独立技术命题，**只有同层同命题才允许合并**：

| 系统层 | 典型内容 |
|---|---|
| Model | 模型能力、权重、benchmark |
| Runtime / Sandbox | agent 执行环境、沙箱、权限 |
| Platform API | API 契约、SDK、生命周期 |
| Ops / Governance | 监控、故障关联、运维 Agent |
| Hardware / Infra | 芯片、多机推理、集群 |
| Docs / DevRel | 文档、教程、发布说明 |

反例：把 OpenShell（Runtime/Sandbox）、Minerva（Ops）、Cosmos（训练/模拟）、
DGX Spark（Hardware）合并成"NVIDIA Agent 基础设施"，会让四个不同技术命题
互相吞没。它们分属四层，本就不该合并。

**P3 聚类收敛：召回 → 裁决**（机器负责不漏，LLM 负责是不是同一命题）：

1. **召回**（工具写入，不要手改）：
   ```bash
   python "$ASSETS/thesis_registry.py" candidates --events-dir events_run_<WINDOW_START_DATE>
   ```
   按叶子路径、二级域、关联域、变化类型、实体给历史命题打分，把 ≤8 个候选写进每个
   事件的 `thesis_candidates`（含得分与理由）。门禁会重算并比对。
2. **裁决**：逐个事件写 `thesis_decision`：
   ```jsonc
   {"action": "attach",               // attach | new | none（A/A+ 不能 none）
    "thesis_id": "TH-0007",           // attach；同批新建的命题写 "NEW:<alias>"
    "relation": "supports",           // supports | contradicts | refines
    "rationale": "一句话：为什么是同一命题",
    "override_reason": "",            // attach 目标不在候选里时必填
    "new_thesis": {                   // new 时必填
      "alias": "decision-model",      // 同批其他事件要挂上来时用
      "name": "...", "statement": "X 从 A 移到 B，因此 C 成为新约束",
      "object": "X", "consequence": "C 成为新约束",
      "scope_leaves": ["B1.1"],       // 1–3 个叶子，不能停在二级域
      "change_types": ["CT-01"]},
    "rejected": [{"id": "TH-0003", "reason": "同叶子但方向相反"}]}  // new 且有候选时，必须覆盖全部候选
   ```
   - **新建命题必须逐个说明为何不归入候选**——这是防止"一个事件一个命题"的关键约束。
   - 本轮两个实体在同一新命题上对齐：第一个 `new` 并给 `alias`，其余 `attach` 到 `NEW:<alias>`。
   - 命题粒度：方向性、可证伪的判断，不是事件标题；范围 1–3 个叶子；预期寿命以周到月计；
     写不出 consequence 的不是技术命题。商业套餐、融资、管制类变化不建命题。
   - B 级事件可以 `attach` 到已有命题作支持证据（贡献跨实体与持续性），也可以 `none`。
3. 再做本轮窗口内聚类：同一技术命题的候选聚到一起，识别 Convergence Signal（多实体）
   与 Frontier Signal（单实体拐点）。

**P4 价值门控排序**：按 Technical Value / Evidence Confidence / Trend Maturity 评级。
A+ = 机制新颖 + 定量充分 + 多源共振；A = 量化显著但缺乏独立基准；
B = 信号明确但证据不足。

**章 2 取 Top N，不设固定数量**：按技术价值排序，达标几条列几条——2 条就列 2 条，7 条就列 7 条。
- **不得为凑数降低门槛**，也不得为凑数把 B 级抬进焦点层；
- **不得按栏目做配额**（"每个栏目都要有人上榜"、"单条栏目优先提上来"都是错的），技术讨论只讲价值；
- 全卡超过 5 条时，Top 1 保留深拆，其余压缩为摘要卡（标题 + 评级 + 一句话命题 + 锚点指向分类章主卡），不重复正文。

Top 1 需深拆（架构可视化 + 落地场景 + 与历史路线关系）。评级相同时，优先"改变技术判断"而非"刷新数字"的那条。
命题的置信度与升降不由 LLM 判断，以 `registry report` 的输出为准（见下方"P4 后写入 registry"）。

**A/A+ 事件卡四维深拆硬约束**：每张 A/A+ 主卡（不只是 Top 1）必须含四个 `#####` 五级小节
（结构契约见 P5），缺一不成稿：

| 章节 | 内容 | 数据来源 |
|---|---|---|
| **挑战与问题** | 现有方案的三道坎（精度/速度/隔离/成本等具体痛点，不是泛泛而谈） | 原文背景段 + 技术常识 |
| **机制与架构** | 新方案如何回应这三道坎，引用原文关键设计词（如 natively multimodal / event-driven / commit-order prediction） | **必须 fetch 官方原文** |
| **效果与定量** | 原文披露的关键数字（benchmark/参数/定价/速度），抓不到就显式标"blog 未在首发时披露"，不得编造 | **必须 fetch 官方原文** |
| **对比其他方案的价值** | 横向对比 2-3 个竞品（同栏目优先），点出本方案差异化价值，回扣 TH 命题 | 原文 + 候选池同栏目事件 |

- **写卡前必须 fetch 原文**（候选池 snippet 截断到 300 字，见 P3）。抓原文遇企业网络拦截用
  华为代理 `proxyca.huawei.com:8080` + `urllib.request.ProxyHandler` 绕过；URL 从
  `candidate_pool.json` 按 title 关键词提取，不要手编 slug。
- **B 级卡片不强制四节**，但 A/A+ 必须四节齐全；持续信号卡（章 5）、聚合栏目摘要卡不适用。
- **无官方原文可抓的事件**（仅媒体转载）标"媒体摘要，未回溯原文"，并在 8.3 记为"官方原文未回溯"。
- 四节总长 200-350 字/卡；横向对比至少 2 个竞品（1 同栏目 + 1 跨栏目）。

**P4 后写入 registry**（整批事务，`--run-date` 用 **WINDOW_START_DATE**）：

```bash
python "$ASSETS/thesis_registry.py" ingest --events-dir events_run_<WINDOW_START_DATE> \
    --run-date <WINDOW_START_DATE> --report raw_<date>/collect_report.json
python "$ASSETS/thesis_registry.py" report --run-date <WINDOW_START_DATE> \
    --out events_run_<WINDOW_START_DATE>/thesis_report.json
```

- 校验失败时整批不写、逐条报错，修正裁决后重跑即可。**同一 run 重跑会整批替换**，
  不会重复计数；相邻窗口重叠出现的事件按 `event_key` 去重，输出里的 `seen_before`
  给出首次入库的 run，8.2 可据此标"上期已报"。
- 只能入库最新 run 或重跑最近一次 run。
- 输出中的 `warnings`（疑似重复事件 / 疑似重复命题）要逐条看：确属同一命题就改为 `attach`，
  或事后 `merge --source TH-a --target TH-b --reason ...`。
- `report` 是第 7 章的唯一输入：本轮触及的命题、状态与置信度的前后对比、得分明细、
  `本轮收敛` / `跨时间收敛`、`core_judgment`（active/contested 且非 Low 才为 true）。
- 其他决策：命题被否证 `retire --id TH-x --reason ...`；表述需收窄 `revise`；方向实质变化
  新建命题后 `supersede --old --new`。statement 不直接改写。

**Success criteria**:
- 每个入选事件有变化类型（CT-xx）+ 技术命题 + 评级
- Top N 已按技术价值选取（数量由达标事件数决定，无配额），Top 1 深拆完成
- Convergence / Frontier Signal 已识别，"本轮收敛 / 跨时间收敛"取自 `thesis_report.json`
- `events.py normalize`、`thesis_registry.py candidates`、`ingest`、`report` 均已执行且退出码为 0
- ingest 的 warnings 已逐条处理（attach 或 merge）

**Rules**:
- 候选只能由 `thesis_registry.py candidates` 生成，不能手写或删改
- statement 不直接改写，修订走 `revise` / `supersede` 决策（保留可追溯性）
- 第 7 章只写 `core_judgment = true` 的命题；proposed 与 Low 的命题只能作为第 5 章 Early Signal，
  contested 的命题进第 7 章时必须写出反证

### 5. P5 成稿：写 Markdown，用内置引擎渲染成 HTML 简报

**先读 `references/design-constraints.md`**，写 `.md` **之前**过一遍其中的写作侧条款
（§6 反 AI-slop、§7 数据图表的诚实性、§8 密度取舍）；排版侧条款由 `report_engine/template.html` 承担。

**为什么让 LLM 只写 Markdown**：见 `references/design-rationale.md` §1。
核心收益：同等信息量下 LLM 输出量降 41%，无信息损失。

**交付约定（方案 1）**：所有简报统一落在 `$WORKDIR/reports/` 下（理由见
`references/design-rationale.md` §4-5）。该目录同时是报告库根目录——
render 末尾扫它生成 `index.json` / `index.html`，使 Ctrl-O 与 Reports 按钮在
`file://` 下可用。`.md` 是工作源，HTML 内嵌完整 MD 可导出，不需另维护副本。

成稿分三步，不可合并：

```bash
# 1) 写工作源：八章内容 + YAML frontmatter
#    $WORKDIR/reports/<标题 slug>-<WINDOW_START_DATE>.md
#    frontmatter 必须含 title / date / status / summary；
#    可选 tags / eyebrow / generated_by / sources / version

# 2) 渲染（自包含 HTML + 报告库索引）
python "$ASSETS/render_report.py" \
  --md "$WORKDIR/reports/<标题 slug>-<WINDOW_START_DATE>.md"

# 3) 在浏览器里打开渲染出的 .html，肉眼复核阅读体验；改 .md，重跑第 2 步
```

- <HARD-GATE>
  只改 `.md`，**永远不手改 `.html`**。`.html` 是渲染产物，改它会被下次渲染覆盖，
  且门禁 `--md` 通道只校验 `.md` 源——手改 HTML 等于绕过门禁制造虚假通过。
  </HARD-GATE>
- `render_report.py` 会校验源文件在 `reports/` 下（否则它不会进报告库索引）；
  确需在别处渲染加 `--allow-outside`（仅用于排查）。
- 渲染前先跑一次 `python "$ASSETS/render_report.py" --check` 确认引擎与 node 可用。

八章结构（内容侧，必须是这些锚点）：

1. 本轮结论与技术趋势（≤3 条跨栏目主线）
2. 今日必看（技术价值 Top N，不设固定数量；Top 1 深拆）
3. 模型技术热点（3.1 模型架构、训练与适应；3.2 推理、决策与效率；
   3.3 多模态、语音与实时模型；3.4 世界、空间与动作模型）
4. Agent 系统技术热点（4.1 任务控制、运行与基础设施；4.2 记忆、知识与上下文；
   4.3 外部环境中的行动与工具使用；4.4 多 Agent 协同与互操作；
   4.5 学习与系统自进化；4.6 评测、验证与可信治理；4.7 交互、主动服务与持续委托）
5. 值得关注（Early Signal / Active Event / Counter-signal / 时间边界候选 / 未归类高信号）
6. 业界专家观点与趋势信号（L1 New Statement / L2 Reactivated / L3 Validation）
7. 本轮技术判断（Frontier Thesis / Convergence Thesis + 置信度）：只写 `thesis_report.json` 中
   `core_judgment = true` 的命题，每条写 `TH-xxxx`、类型、置信度（与 report 一致）、本轮收敛 /
   跨时间收敛与前后变化；contested 的命题同一行写出反证
8. 信息源采集统计（8.1 源与覆盖审计、8.2 事件索引、8.3 丢弃与漏检回溯）

栏目的叶子归属一律查 `$ASSETS/taxonomy.py`，不要在提示词里另抄一份映射表。

**Markdown 结构契约**（门禁 `verify_gates.py --md` 按此切分，违反会判 FAIL）：

| 层级 | 语法 | 承载 |
|---|---|---|
| `## <章标题>` | 二级标题 | 八章之一（按顺序匹配，第 N 个 `##` = 第 N 章） |
| `### <N.M> <栏目标题>` | 三级标题，编号开头 | 11 个栏目之一（3.1–3.4 / 4.1–4.7）；8.1/8.2/8.3 是审计子节 |
| `#### <事件卡标题>` | 四级标题 | 一张事件卡；A/A+ 卡必须含四节深拆 |
| `##### 挑战与问题` / `机制与架构` / `效果与定量` / `对比其他方案的价值` | 五级标题 | A/A+ 卡的四维深拆，缺一节判 FAIL |

卡片正文第一行写评级标记：`**A+ · Frontier · EV-02**` 或 `**A · Frontier · EV-09**`。
门禁靠这一行判定是否承担四节义务（Top N / Active Event / Convergence / 非 Frontier 豁免）。
EV 编号写在这行 `**...**` 标记里，门禁只扫卡片前 200 字符的标记区找 EV，不扫深拆段落
（深拆里的 EV 编号是交叉引用，扫到会让「唯一主卡」误报重复）。
卡片不在自己的主栏目下时（折叠卡、章 2 承载主卡的 Top 卡），在同一标记里追加 `· 归属 N.M`，
如 `**A · Frontier · EV-07 · 归属 4.5**`；门禁只认标记区里的这一写法。

**分类章的三条渲染规则**（门禁会逐条校验）：

| 规则 | 做法 |
|---|---|
| **唯一主卡** | 每个事件只在一个栏目写完整卡片。章 2 的 Top 1 可承载该事件的唯一主卡（标记写 `归属 N.M`），分类章只留交叉引用；章 2 未写归属的卡视为摘要卡 |
| **主卡归位** | 全卡必须落在 `primary_path` 经 `taxonomy.resolve()` 算出的栏目；A/A+ 事件必须有主卡，B 级及以下可只出现在章 5 |
| **空栏目不渲染** | 0 条事件的栏目不出现 `###` 标题；只有 1 条的栏目折叠进相邻展开栏目，卡片标记写 `归属 N.M`；每个栏目最多折叠 1 条 |
| **聚合栏目标注** | `4.6` 的卡片必须写具体技术域（评测环境/结果核验/可靠性归因/运行证据/调试回放/生产质量/身份授权/执行隔离/内容防护/审计治理），且与事件 JSON 的 `annotation` 一致（后者由 `primary_path` 唯一确定） |

章 2 的其余条目用摘要卡（标题 + 评级 + 一句话命题 + 锚点指向分类章主卡），不重复正文。

**视觉侧的三条硬约束**（写 MD 时就要落实，门禁不查但必须遵守）：

| 约束 | 做法 | 违反后果 |
|---|---|---|
| 首屏即结论 | 第 1 章第一段是结论 + 一句话，不是装饰 hero | 读者 10 秒内读不到本轮判断 |
| 一图一主张 | 图用 `![结论文字](图源)`，alt 文本写结论不写"如图所示" | 图退化成装饰 |
| 数字成图 | 跨度/占比/比较用表格或 mermaid，不要用纯文字罗列数字 | 数字无法比较 |

**Success criteria**:
- `reports/<标题 slug>-<DATE>.md` 与渲染后的 `.html` 都在 `reports/` 下
- `render_report.py` 输出 `OK` 且 `报告库: N 份`
- 八章结构完整（`##` 数量 = 8）
- frontmatter `title` / `date` / `status` / `summary` 齐全
- H1 时间范围 = TARGET_WINDOW
- 8.2 Event Index 中所有"本轮新事件"首发时刻在 TARGET_WINDOW 内
- 8.3 漏检回溯表已填写

**Rules**:
- 文件名中的日期 = WINDOW_START_DATE（昨日日期）
- 正文首页必须显示 WINDOW_START / WINDOW_END
- H1 中的时间范围必须等于 TARGET_WINDOW
- 视觉复核没过就不允许进入步骤 6 —— 门禁查的是事实与结构，查不出排版缺陷

**intro 区深层推理硬约束**：

intro 区（第 1 章）不只是列举事件，必须分两层写，缺第二层不成稿：

| 层 | 元素 | 内容 |
|---|---|---|
| 事实层 | 普通段落 | 列举 2-3 条主线各自做了什么（一句话/条）+ 统计数据（源/条目/事件/评级分布） |
| 推理层 | `> [INSIGHT] ...` callout | 把多条主线合在一起指向什么——跨层解耦/叠加效应/工程经济学改变等**潜在价值**，不是简单复述 |

推理层写作要求：
- **不强行汇总到单一技术方案**：h1 仍是多命题并列；INSIGHT 框是"潜在价值"而非"已证实结论"。
- **必须标证据边界**：跨事件推理的因果链若未经单一来源证实，结尾写明"应视为本轮窗口内的分析假设而非已确立结论"。
- **可空但不可假**：若本轮事件间无明确跨层关系，推理层可写"本轮事件以独立信号为主，未发现跨层收敛"，
  不得强行编造因果。

### 6. P6 验收 + 漏检回溯 + Registry 生命周期更新

**6a. 验收**：**先跑机器校验，再人工复核**。两道关卡都要过，缺一不可：

```bash
# 关卡 1：内容与结构（事实、窗口、追溯、归类）—— 直接校验 LLM 手写的 .md 源
python "$ASSETS/verify_gates.py" \
  --raw-dir raw_<date> \
  --md "reports/<标题 slug>-<WINDOW_START_DATE>.md" \
  --events events_run_<WINDOW_START_DATE>/ \
  --state state/ \
  --json-out verify_result.json

# 关卡 2：视觉（排版、可读性、figure 完整性）—— 重渲染即可复验
python "$ASSETS/render_report.py" \
  --md "reports/<标题 slug>-<WINDOW_START_DATE>.md"
```

为什么门禁校验 `.md` 而不是 `.html`：见 `references/design-rationale.md` §2。

任一退出码非 0 都存在 FAIL，必须修正后重跑。**`verify_gates.py` 全绿不代表页面可读**：
它查的是字段是否对得上事实源，不查 10px 的标签或穿框的文本——视觉问题交给重渲染复核。

`verify_gates.py` 机器校验覆盖：

| 层 | 检查项 |
|---|---|
| collection | 源读取成功、窗口内有条目、无阻断缺口、critical 源可用、补检任务清零、无 critical 源窗口覆盖不完整 |
| collection | 非 critical 源的窗口截断也必须转成补检任务（`window_partial` → `tasks_action_open=0`） |
| taxonomy | 分类定义完整：54 叶子 / 11 栏目 / 8 章，叶子↔栏目双向一致、无重复收录 |
| taxonomy | 每个事件有 `primary_path` 且可解析；跨栏目的二级域（`A1`/`B1`/`C3`）已下钻到三级 |
| taxonomy | `related_domains` ≤2 且可解析；`change_object` 取值合法 |
| taxonomy | MD 栏目编号（`### N.M`）均属 11 个栏目（旧结构 `2.x`/`3.x` 直接 FAIL） |
| taxonomy | **唯一主卡**：同一事件不在多个栏目重复写全卡（含章 2 声明归属的主卡）；主卡落在 `primary_path` 对应栏目，A/A+ 必须有主卡；出现 `###` 的栏目不得无卡 |
| taxonomy | 折叠：`归属 N.M` 是合法栏目、每个栏目最多折 1 条；`4.6` 卡片正文写具体技术域，事件 JSON 的 `annotation` 与 `primary_path` 一致 |
| md | 文件非空、frontmatter title 存在、八章 `##` 按顺序齐全、8.1/8.2/8.3 存在、来源链接 ≥10、文件名与 H1 的窗口日期一致 |
| md | 8.2 无晚于 WINDOW_END 的新事件、早于 WINDOW_START 的**那一行**标为 Active/Historical |
| trace | 每个事件已规范化（有 `event_key`）；A/A+ 事件有 `claims` 数组 |
| registry | 本轮已入库且入库事件与 events 目录一致；A/A+ 的 `thesis_candidates` 等于工具重算结果；A/A+ 有 attach/new 裁决且已写入 registry |
| registry | 第 7 章引用的 `TH-xxxx` 存在、为 active/contested 且非 Low、置信度文字与 registry 一致、contested 写出反证 |
| trace | 8.2 每个 EV 编号都有对应 `EV-xx.json`；JSON 的 `first_publish_shanghai` 落在窗口内；编号与事件内容/评级一致 |
| trace | **8.2 表格里的时刻必须等于 EV JSON 的 `first_publish_shanghai`**（分钟粒度，同一时区） |

**trace 层以 8.2 Event Index 表格声明的编号为分母**：缺 JSON 直接 FAIL。
**8.2 的时刻必须能被 `events_run_<date>/EV-*.json` 证实** ——
门禁校验事实源，不是表格里手填的日期；两者不一致时以 JSON 为准。
MD 通道下，`check_md_event_index` 直接解析 `### 8.2` 栏目下的 Markdown 表格行，
与 HTML DOM 结构解耦。

**时区必须在两处同时约束**：
1. `first_publish_shanghai` 写换算后的 +08 时刻（不是源站钟面时间）；
2. 8.2 的"首发（Asia/Shanghai）"列必须与 JSON 完全一致。

arXiv 按 00:00-04:00 整批发布，换算后为 12:00。

**日粒度源用模糊精度归窗，不得把日期钉成零点时刻。**
日期只到"日"时，源站时区不可知（全球 UTC-12 ~ UTC+14），真实时刻落在
`[D-1 10:00Z, D+1 12:00Z)` 这个 50 小时区间内。因此：

| 判定 | 含义 | 处置 |
|---|---|---|
| `exact` | 精确到秒，且落在窗口内 | 可作为确定事件引用 |
| `fuzzy` | 仅日粒度，50 小时区间与窗口相交 | **保留**，但引用时必须标 `date_precision: day`，不得当作确定窗口内事件 |
| 不入窗 | 区间与窗口不相交 | 丢弃，归 8.3 |
| `time_unknown` | 无日期 | 按快照差分判断，不按时间归窗 |

**零点时刻一律按 day 精度处理。** RSS 的 `pubDate` 语法上精确到秒，但大量源实际只填到日，
表现为 `00:00:00`。`extract._precision_of()` 统一降级为 `day`——
把只有"日"的信息当秒精度，等于凭空加 50 小时确定性，窗口边界会成批误判。
代价是真正的 UTC 零点发布被低估精度，这是可接受的方向：**宁可标模糊，不可漏扫描**。

`extract.window_match()` 返回 `exact` / `fuzzy` / `None`，`in_window()` 把两档都算入窗。
事件 JSON 若 `date_precision: day`，必须同时写 `date_precision_note` 说明精度来源
（如"源站只给日期字段"），否则 gate 判 FAIL。
候选池与 `collect_report.json` 分别记 `items_in_window_exact` 与
`items_in_window_fuzzy`，8.1 必须同时披露这两个数字——只报一个总数，
读者无法知道其中有多少条需要人工核时间。

精度必须在第一次解析时确定并贯穿到底，不要"先转 ISO 串再交给下游解析"：
ISO 串带 `T`，二次解析会把日粒度升级成秒级。

**格式与覆盖类问题一律以脚本结果为准**，不要再由 LLM 读一遍 HTML 自证"已通过"。

**6b. 人工复核**（机器判不了的部分）

| 复核项 | 判据 |
|---|---|
| 机制新颖性 | 变化是否真的改变了技术命题，而非只是数字刷新 |
| 命题归属是否合理 | `primary_path` 与事件机制是否对得上（门禁只校验形式） |
| 证据是否充分 | 来源数量、独立性、定量数据 |
| 章 1 主线是否成立 | 是否真的跨栏目，而不是把某一栏目的事件换个说法 |
| 章 7 判断是否被证据支撑 | 有反证时是否下调置信度，而不是硬凑命题 |

**6c. 漏检回溯表**（8.3）

生成漏检回溯表，**数据直接来自 `gap_tasks.json` 与 `collect_report.json`**，
不要凭印象填写。每行记录：
- 条目 / 来源 / 召回通道 / 首发时刻 / 是否位于 TARGET_WINDOW / 处置 / 理由
- 根因分类（用下面的封闭集合，不得自创）：
  `代理拦截` / `源面未覆盖` / `解析失败` / `窗口覆盖不完整` / `窗口外`
  / `重复` / `低影响` / `抽象提升失败` / `价值误判` / `日期边界`
- 处置方式（下一轮补采 / 申请权限 / 换通道 / 用二次源确认 / 已并入 TH-xxx）

**8.1 必须包含三级状态统计**，而不是只写"采集成功 N 个源"：
- 判定分布（OK_IN_WINDOW / OK_OUT_OF_WINDOW / OK_EMPTY / PARSE_FAILED / PROXY_BLOCKED 等）
- 结论数（`items_in_window_exact` / `items_in_window_fuzzy` 分别报）
- 每个失明源的具体原因
- 每个实体×面的覆盖情况（哪些面读过、哪些面失明）
- 不可达面的登记理由（来自 `sources.py` 的 `UNCOVERABLE`）

**6d. Registry**：状态迁移（proposed / active / contested / dormant / retired）由证据与 run 计数
派生，ingest 记录了本轮 run 即自动推进，**没有单独的生命周期命令**。
若 8.3 回溯发现某命题被证伪，用 `retire --id TH-x --reason ...`；若发现两个命题实为同一命题，
用 `merge`。反驳某命题的新事件走正常裁决（`attach` + `relation: contradicts`）。

**Success criteria**:
- `verify_gates.py --md` 退出码为 0（GATE PASS）
- `render_report.py` 退出码为 0，`reports/index.json` 计数已更新
- 人工复核表中每一项都有明确结论
- 漏检回溯表已填写
- 失败源已在 8.1 标注 Zero-result

**Rules**:
- 验收不通过时必须修正后重新验收，不能跳过

## ADJUSTMENT_PLAN

本区沉淀历史踩坑为永久约束，防止重蹈。新增条目格式：`日期 + 问题 + 根因 + 约束`。

### 2026-10-27 起：门禁只校验 MD，不校验 HTML 副本

- **问题**：旧 HTML 门禁（`check_html` 的 `id="sN"`/`<p class="eyebrow">` DOM 契约）
  对 MD 路线渲染的 HTML 全部"假绿 PASS"——0 张卡匹配，唯一主卡/空栏目断言在空集上恒真。
- **根因**：门禁靠生成器 DOM 结构定位对象；换渲染路线后 0 匹配，缺失性断言在空集恒真。
- **约束**：文档层只走 `check_markdown` + `check_md_event_index` + `check_html_lightweight`；
  HTML 只做轻量存在性断言。更换渲染器时，结构契约仍在 `.md` 上校验，不要回到 DOM 契约。

### 2026-10-27 起：`_iso()` 必须补 SH_TZ

- **问题**：`collect_report.json` 的窗口串不带时区（naive），`_row_dates` 给的带 SH_TZ
  （aware），两者比较抛 `TypeError: can't compare offset-naive and offset-aware datetimes`。
- **根因**：`_iso()` 返回 naive datetime，未补时区。
- **约束**：`_iso()` 返回时若 `dt.tzinfo is None` 补 `SH_TZ`。新增任何 datetime 比较
  前先确认两端 tzinfo 一致。

### 2026-10-27 起：slug 必须保留中文字符

- **问题**：渲染器 slug 用 `[a-z0-9]` 白名单，中文标题生成的 id 全为空字符串，
  锚点全部指向 `#`，但渲染器退出码仍 0——静默丢失中文锚点。
- **根因**：ASCII 白名单 slug 把 `\p{L}` 范围外的字符全部清空。
- **约束**：slug 正则用 `\p{L}\p{N}` 保留 Unicode 字母数字。接入新渲染器前先跑中文
  标题冒烟断言（`## 中文标题` → id 非空）。

### 2026-10-27 起：文件名日期 = WINDOW_START_DATE

- **问题**：文件名用运行日期（10-27），但窗口起始是 10-26，门禁报
  `文件名日期 = WINDOW_START_DATE: expect 2026-10-26`。
- **根因**：混淆了 `raw_<date>` 的 date（运行今天）与简报文件名的 date（WINDOW_START_DATE）。
- **约束**：`reports/<slug>-<WINDOW_START_DATE>.md`；`raw_<date>/` 用运行日期；
  `events_run_<date>/` 用 WINDOW_START_DATE。两处日期不可互相推导。

### 2026-10-27 起：Ctrl-O 空列表是设计行为非 bug

- **现象**：报告库只有 1 份报告时，Ctrl-O 切换器列表为 0。
- **归因**：`filterReports()` 有意排除当前报告（`r.slug !== data.current_slug`），
  库只有 1 份时过滤后自然为 0。
- **约束**：排查 Ctrl-O 问题时先确认报告库 ≥2 份；只有 1 份应点 Reports 按钮看
  `index.html`，不要当成 bug 去改 filter 逻辑。

### 2026-10-31 起：移除 visual-explainer 旧路线

- **问题**：旧路线（visual-explainer kit + 手写 `.src.html` + `render_html.py` + 门禁 `--html` 通道）
  作为 A/B 基线保留，但 MD 路线已经验证无信息损失，旧路线只剩维护负担，且其指令
  （`<h4>`/`<details>` 写法、`html_render_guide.md` §10 CSS）与 MD 结构契约冲突。
- **处置**：删除 `render_html.py`、`test_render_html.py`、`html_render_guide.md`，门禁去掉 `--html`
  通道；设计约束保留为 `references/design-constraints.md`。
- **约束**：渲染只走 `render_report.py` + `report_engine/`；`verify_gates.py` 未给 `--md` 时
  文档层直接 FAIL，不再存在"只查 HTML"的分支。

### 2026-10-31 起：分类呈现规则在 MD 通道落地

- **问题**：主卡归位、折叠声明、4.6 标注三条规则只在旧 HTML 门禁里实现，MD 通道从未检查；
  MD 的空栏目检查只登记"有卡的栏目"，在空集上恒真；栏目内卡片按片段内偏移去全文切片，
  只写在标记行的 EV 编号会读丢。另外渲染器只识别 1–4 级标题，`#####` 深拆小节原样显示为文本，
  中文首段被加首字下沉。
- **约束**：分类规则一律由 `_check_md_columns` 在 `.md` 上校验，折叠与章 2 主卡用标记里的
  `归属 N.M` 声明；渲染器支持到六级标题（h4 卡片标题、h5/h6 小标签，均不生成 id），
  首字下沉只用于拉丁字母开头的段落。新增门禁规则时同时写"该红时红"的测试。

### 2026-10-31 起：Thesis registry v2

- **问题**：v1 registry 一个事件新建一个 thesis（51 个里 37 个只有 1 条证据），收敛查询依赖已废弃的
  track/section、对 v2 事件恒返回空，置信度只升不降，相邻窗口重叠会重复计数，
  每轮靠 LLM 现写 `make_events.py` / `fix_events.py` 适配。
- **处置**：重写为 v2（`references/registry-v2-design.md`）：事件与命题分离、状态与置信度由证据派生、
  召回 → 裁决 → 事务入库三步留痕、按 `event_key` 幂等、状态移到 `$WORKDIR/state/`。v1 数据不迁移。
- **约束**：候选只能由 `candidates` 生成；新建命题必须逐个拒绝候选；第 7 章只取 `report` 的
  `core_judgment` 命题。改裁决后重跑 ingest 即可，同一 run 整批替换。
