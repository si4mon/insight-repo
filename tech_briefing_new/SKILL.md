---
name: tech-briefing-new
description: 生成 Asia/Shanghai 时区下从昨日 00:00 到执行时刻的多源技术热点简报，采集、分析、成稿并输出自包含 HTML。用户说"生成技术简报""今日技术简报""跑一下技术简报"或要求重新生成时触发。
allowed-tools:
  - Bash(python:*)
  - Bash(python3:*)
  - Bash(curl:*)
  - Bash(ls:*)
  - Bash(rm:raw_*/*)
  - Bash(rm:reports/*)
  - Bash(rm:events_run_*/*)
  - Bash(mkdir:*)
  - Bash(date:*)
  - Bash(powershell:*)
  - Bash(node:*)
  - WebSearch
  - WebFetch
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

生成 Asia/Shanghai 时区下，从"昨日 00:00"至"任务实际执行时刻"的多源技术热点简报，交付完整、
可独立打开的高信息密度 HTML。

**分工**：`assets/tech_report_task_def.md`（下文简称 task_def）是规则源，写"做什么、按什么标准判断"；
本文件只写步骤、命令、路径与产物契约，规则以"task_def §N"引用，不重复。冲突时内容判断以 task_def
为准，结构契约、文件路径与门禁以本文件和脚本为准。命令中的 `python` 指 Python 3（Linux/macOS 上
用 `python3`）。

## 目录结构

本 skill 自包含全部引擎与骨架，不依赖项目目录；根目录按运行时的真实安装位置解析（见 `$SKILL_DIR`）。
```
$SKILL_DIR/
├── SKILL.md                 本文件：步骤、命令、路径、产物契约
├── assets/
│   ├── tech_report_task_def.md   规则源：做什么与判断标准
│   ├── thesis_ontology.json      骨架：变化类型、评级、置信度模型、taxonomy（人工维护）
│   ├── sources.py / extract.py / coverage.py / collect_sources.py   采集与覆盖对账
│   ├── build_pool.py / gap_tasks.py   候选池与补检任务
│   ├── events.py / thesis_registry.py / taxonomy.py   事件规范化、命题库、分类
│   ├── verify_gates.py           门禁（校验 .md 工作源）
│   ├── render_report.py + report_engine/   MD → 自包含 HTML（纯 Node）
│   └── test_*.py                 单测
├── references/              按需读取：changelog / gate-checks / gap-playbook / pool-triage /
│                            event-writing / date-precision / design-constraints / design-rationale /
│                            registry-v2-design / chapter-structure-design
└── data/                    只读资料（四层技术地图、分类规则说明）
```

**工作目录**（`$WORKDIR`，执行 skill 时的当前目录）存放运行时产物：

| 路径 | 内容 | 日期含义 |
|---|---|---|
| `raw_<date>/` | 原始字节、`items_<source>.json`、`collect_report.json`、`gap_tasks.json`、`candidate_pool.json` | 脚本运行的**今天** |
| `events_run_<date>/` | `EV-xx.json`、`thesis_report.json`（第 7 章输入） | **WINDOW_START_DATE** |
| `reports/` | `<标题 slug>-<date>.md`（唯一手写产物）、同名 `.html`、`figures/`、报告库 `index.json` / `index.html` | **WINDOW_START_DATE** |
| `snapshots/` | 跨 run 的官方面快照，用于差分 | — |
| `state/` | registry 状态 `thesis_registry.json` 与审计日志；可用 `TECH_BRIEFING_STATE` 指向共享目录 | — |

**路径变量**：`$SKILL_DIR` = 本 `SKILL.md` 所在目录（由客户端决定，可能是 `~/.cac/skills/<name>`、
`~/.claude/skills/<name>` 等，**不要写死**；不确定时用 Glob 找同目录有 `assets/tech_report_task_def.md`
的 `SKILL.md`）；`$ASSETS` = `$SKILL_DIR/assets`；`$DATA` = `$SKILL_DIR/data`。

**硬约束**：只读本 skill 目录；不在 `$WORKDIR` 之外创建目录（尤其不要 `mkdir ~/.cac/...` 之类的客户端
根目录）；`$ASSETS` 或 `$DATA` 不存在说明 `$SKILL_DIR` 解析错了，重新定位，**不要建空目录顶替**。

## 前置依赖

- **task_def**：规则源，步骤 1 中读完全文。
- **渲染引擎**：`$ASSETS/render_report.py` + `$ASSETS/report_engine/`（纯 Node，不依赖外部 skill）。
- **taxonomy**：分类查询一律走 `$ASSETS/taxonomy.py`，不在提示词里另抄映射：
  `leaves`（54 叶子）、`columns`（11 栏目）、`chapter 3|4`、`resolve <路径>`（→ 栏目，4.6 叶子另给
  `annotation`）、`validate`。
- **registry**：`$ASSETS/events.py`（事件规范化）与 `$ASSETS/thesis_registry.py`（召回 / 入库 / 报告 /
  决策 / 漏跑检测），状态在 `state/`，设计见 `references/registry-v2-design.md`。
- **检索**：Technology Watch、Expert Watch 与补检任务需要 WebSearch / WebFetch。

## Goal

在 `$WORKDIR/reports/` 下生成 `<标题 slug>-<WINDOW_START_DATE>.md` 及其渲染出的自包含 `.html`，满足：
1. TARGET_WINDOW 正确冻结（task_def §0）
2. 八章结构完整（task_def §16）
3. `verify_gates.py` 退出码 0，人工复核表逐项有结论
4. 先运行采集脚本，采集报告落盘到 `raw_<date>/collect_report.json`
5. registry 完整走过 normalize → candidates → 裁决 → ingest → report，第 7 章取自 report
6. 漏跑的窗口已识别并补跑或登记

## Steps

### 1. 冻结 TARGET_WINDOW 并读取任务定义

取真实当前时刻并换算到 Asia/Shanghai：
`powershell -Command "[TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, 'China Standard Time').ToString('yyyy-MM-dd HH:mm:ss')"`
（非 Windows 用 `TZ=Asia/Shanghai date '+%F %T'`）。计算：

- `WINDOW_START_DATE = date(NOW_SHANGHAI) - 1 天`；`WINDOW_START = WINDOW_START_DATE 00:00:00`；
  `WINDOW_END = NOW_SHANGHAI`（开始时冻结，之后不再扩展）
- `SCAN_WINDOW = WINDOW_START - 6 小时 → WINDOW_END`

读取 task_def 全文。

<HARD-GATE>
读完 task_def 全文前，禁止进入步骤 2。窗口规则（禁止的推导来源、事件归属、Window Audit、扫描窗口
与归属窗口分离）见 task_def §0 / §0.1；推导错窗口会让采集、事件归属、文件名全部失配，门禁到步骤 6
才暴露，已无法回溯。
</HARD-GATE>

**漏跑检查**：窗口固定为"昨日 00:00 → 执行时刻"，漏跑一天，就有一段时间不在任何窗口里。
```bash
python "$ASSETS/thesis_registry.py" gaps --until <WINDOW_START_DATE>
```
`missing` 非空时，对每个漏掉的日期 D 按完整流程补跑一份简报：`collect_sources.py --date <D+1>`
（`--date` 是那一轮的"今天"）→ `events_run_<D>/` → 正常裁决 → `ingest --backfill --run-date D` →
`reports/<slug>-<D>.md`。源只保留近期条目，越晚补漏得越多，超出保留期的部分由补检检索覆盖并在 8.3
记根因"源面未覆盖"。来不及补跑的日期在本轮 8.1 登记。

**渲染引擎自检**：`python "$ASSETS/render_report.py" --check`，等到步骤 5 才发现缺 node 等于白写。

**Rules**：
- `collect_sources.py` 只在补跑时传 `--date`。它把 `--date` 当"今天"再减一天得到 WINDOW_START：
  日常运行传了 `--date 2026-10-26` 会得到 WINDOW_START = 10-25，整轮作废。
- `raw_<date>` 用运行当天日期，`events_run_<date>` 与报告文件名用 WINDOW_START_DATE，两者不可互推
  （例：10-27 运行 → `raw_2026-10-27/`、`events_run_2026-10-26/`、`reports/<slug>-2026-10-26.md`）。

### 2. 采集 + 提取 + 对账 + 生成补检任务

```bash
cd "$WORKDIR" && python "$ASSETS/collect_sources.py"
cd "$WORKDIR" && python "$ASSETS/gap_tasks.py" --report raw_<date>/collect_report.json --out raw_<date>/gap_tasks.json
```

采集不是"抓字节"，是"证明每个面被看到了"。每个源有三级状态，任何一级失败都不会被下一级掩盖：

| 层级 | 取值 |
|---|---|
| transport | ok / http_error / timeout / url_error |
| extract | ok / empty / parse_failed / blocked（代理拦截页）/ skipped |
| window | OK_IN_WINDOW / OK_OUT_OF_WINDOW / OK_EMPTY / OK_NO_DATES / OK_NEW_VIA_DIFF |

第四级是窗口覆盖度 `covered_quality`：单页 API 可能只覆盖窗口后半段，未触底标 `partial`。

**四种"空"必须分开**：没读到（transport/extract 失败）→ 补检；读到但窗口内无新增（OK_OUT_OF_WINDOW）
与源正常但当天 0 条（OK_EMPTY，如 arXiv 周末）→ 正常结论，**不是失明**；只覆盖窗口一段（partial）→
回溯该时段。把后两种当失明，补检会永远打在查过的地方；把 partial 当成功，漏检就藏进盲区。

源注册表 `sources.py` 按"实体 × 面 × 提取模式"登记，新增/下线源只改这个文件。官方面确实不可达的
登记在 `UNCOVERABLE`，必须写明补偿方式、检索词与复探期限，过期门禁 FAIL。

**Rules**：必须运行采集脚本，不得用历史数据；代理拦截页（HIS Proxy / Huawei Proxy / mwg-internal /
"访问外部AI大模型"）判为 `blocked`，不计成功；成功证据是 `items_count` 与 `items_in_window`，
不是 HTTP 200 或文件大小；失败的源不中断流程，但必须进入 `gap_tasks.json`。

**Success criteria**：`collect_report.json` 含每个源的 transport / extract / verdict / items_total /
items_in_window / covered_quality；`gap_tasks.json` 已生成；`items_<source>.json` 存在。

### 2.5 Gap-driven 补检（缺口必须清零）

逐条执行 `gap_tasks.json` 中 open 的任务。**执行前读 `references/gap-playbook.md`**（按缺口类型
换通道：Techmeme 逐小时归档、arXiv pastweek、GitHub API、原文元数据等）。检索范围与首发判定按
task_def §0.1 / §13（覆盖整个 SCAN_WINDOW、回溯官方原文）。完成后：
`python "$ASSETS/gap_tasks.py" --report ... --out ... --mark-done GAP-xx --note "结论"`。

| 任务类型 | 来源 | 严重度 | 验收 |
|---|---|---|---|
| `critical_blind` / `surface_blind` | 整面失明（拦截、解析失败、空响应） | 阻断交付 | 该面在 SCAN_WINDOW 内有 N 条或确认 0 条 |
| `window_partial` | 面读到了，但窗口前半段未检索 | 必须关闭 | 该时段有 N 条或确认 0 条（翻页/归档证据） |
| `entity_blind` | Tier-1 实体的官方面全部不可达 | 必须关闭 | 按任务里的检索词覆盖 SCAN_WINDOW：有 N 条（回溯到官方原文）或确认 0 条 |

不要用"再搜一次"关任务；代理拦截类（`fallback_channel` 非空）必须换通道。关闭的 note 必须可复核：
用了哪个通道、覆盖哪段时间、去重后几条、其中几条落在 TARGET_WINDOW。只写"已核查"等于没关。

**Success criteria**：`tasks_blocking_open == 0` 且 `tasks_action_open == 0`；每条关闭任务有"有 N 条
（附 URL）"或"确认 0 条（附证据）"的结论；补检发现的事件已加入候选池。

### 3. P1 宽召回：构建候选池

```bash
cd "$WORKDIR" && python "$ASSETS/build_pool.py" --raw-dir raw_<date>
```
合并 `items_<source>.json`、按（源, uid）去重、归窗，产出 `candidate_pool.json` 与 `pool_out_of_window.json`。
不要手工拼候选池。

| 条目 | `window_match` | 处置 |
|---|---|---|
| 有准确时刻且在窗口内 | `exact` | 确定事件 |
| 仅日粒度、区间与窗口相交 | `fuzzy` | 可能事件，引用时标精度 |
| 无日期字段（HF / GitHub Trending 等） | `no_date` | **保留**，按 `freshness` 处置 |
| 无标题（sitemap 纯 URL） | 移到 `pool_out_of_window.json` | 只用于 surface diff |

`no_date` 条目的 `freshness`：`new_since_last_run` 可作本轮新事件；`carried_over`（上轮已在场）只能进
第 5 章持续信号；`baseline_unknown`（首次运行）不得声称"本轮新增"。快照基线只在跨日时前进，同日
重跑不覆盖基线。

**每次运行交付 TARGET_WINDOW 的全量简报，不是增量**：同一窗口跑两遍，两遍同样完整；`carried_over`
只用于无日期源去重；首发早于 WINDOW_START 的事件仍是窗口外。窗口外条目留在
`pool_out_of_window.json`，供 8.3 丢弃日志引证。`collect_report.json` 的 `diff.new_uids` 是官方面
"本轮新增了什么"的直接证据。

**五路召回机制（task_def §2）与执行方式**。机制是"怎么召回"，源通道是代码里每个源的 `channel`，
两套名字不要混用。8.3 的"召回通道"列：来自候选池的条目填源通道，来自检索的填"Technology Watch
补检"或对应的 `GAP-xx`。

| 召回机制 | 执行方式 | 对应源通道 |
|---|---|---|
| Entity Watch | `collect_sources.py` 读 Tier-1 官方面 | `A_entity`、`F_cn_media`（国内厂商） |
| Technology Watch Matrix | 按 task_def §4 / §5 / §6 的技术面检索 | —（检索补检） |
| Source Full-Read | `build_pool.py` 合并全部源窗口内条目，不按主题预过滤 | 全部源通道 |
| Cross-Source Resonance | 候选池内跨源计数 + HN / GitHub / HF Trending 热度 | `D_social`、`C_aggregator`、`E_expert` |
| Official Surface Diff | 快照差分（`diff.new_uids`） | `G_official_surface` |

另按 task_def §8 做 GitHub Org Diff、按 §12 做 Expert Thesis Watch。候选池字段要求见 task_def §2；
`build_pool.py` 已给出来源、首发时刻、`window_match`、`freshness`，LLM 补召回机制与"本轮新事件 /
Active Event / Historical Context"判定。**候选池常有 2000+ 条，筛选顺序见 `references/pool-triage.md`。**

**Success criteria**：全部源已解析；每个候选有首发时刻、来源、召回通道；区分本轮新事件与
Active Event / Historical Context。

### 4. P2-P4 抽象提升、聚类收敛、价值门控排序

**事件集只从本窗口候选池生成**：重跑时重新生成，覆盖面不应少于上次；不要读已有 `events_run_<date>/`
决定"哪些还在"。编号 EV-01..EV-NN 在本轮内连续即可。

**P2 事件 JSON**：每个入选事件写 `events_run_<WINDOW_START_DATE>/EV-xx.json`。**写之前读
`references/event-writing.md`**（A/A+ 必须逐条抽取 claims；同一实体不同系统层的变化不得合并；
主卡结构与四节深拆；抓原文与"媒体摘要"标注）。

| 字段 | 说明 |
|---|---|
| `event_title` | 一句话技术变化，不是产品口号 |
| `source` / `entity` / `key_data` | 原始来源、实体、关键定量；同一事件换了 URL 时加 `canonical_source` |
| `first_publish_shanghai` / `date_precision` | +08 时刻；`second`/`day`/`batch`/`none`，`day` 必须写 `date_precision_note`（见 `references/date-precision.md`） |
| `rating` / `signal` | 评级（task_def §10）与信号；命题置信度由 registry 派生，事件里不写 |
| `change_types` | `CT-01..CT-09` |
| `primary_path` / `related_domains` | 主技术路径（通常到叶子，`A1`/`B1`/`C3` 必须下钻）；关联域 ≤2 |
| `change_object` | `Model` / `Harness` / `运行平台` / `交互·应用` / `尚未披露` |
| `annotation` | 仅 4.6 事件：取 `taxonomy.py resolve <primary_path>` 输出的 `annotation` |
| `evidence_form` | `paper` / `product` / `api` / `code` / `benchmark` / `deployment` / `expert` |
| `claims` | 逐条论点处置：`absorbed:<本事件 EV>` / `separated:<EV>` / `discarded:<理由>` |
| `thesis_decision` | 归属裁决（P3），A/A+ 必填 |

不写已废弃的 `tracks` / `sections`。写完必须规范化（补 `event_key`、统一枚举、校验必填；有错时一个
文件都不改写）：
```bash
python "$ASSETS/events.py" normalize --events-dir events_run_<WINDOW_START_DATE>
```
**编号一致性**：`EV-01.json` 就是 8.2 里 `EV-01` 那一行，8.2 的每个编号都有同名 JSON；早于
WINDOW_START 的背景事件 JSON 保留真实时刻，8.2 那一行标 `Active Event` / `Historical`。

**P3 聚类收敛：召回 → 裁决**（机器负责不漏，LLM 负责是不是同一命题）：

1. 召回（工具写入，不要手改，门禁会重算比对）：
   ```bash
   python "$ASSETS/thesis_registry.py" candidates --events-dir events_run_<WINDOW_START_DATE>
   ```
2. 逐个事件写 `thesis_decision`：
   ```jsonc
   {"action": "attach",               // attach | new | none（A/A+ 不能 none）
    "thesis_id": "TH-0007",           // attach；同批新建的命题写 "NEW:<alias>"
    "relation": "supports",           // supports | contradicts | refines
    "rationale": "一句话：为什么是同一命题",
    "override_reason": "",            // attach 目标不在候选里时必填
    "new_thesis": {                   // new 时必填
      "alias": "decision-model",
      "name": "...", "statement": "X 从 A 移到 B，因此 C 成为新约束",
      "object": "X", "consequence": "C 成为新约束",
      "scope_leaves": ["B1.1"],       // 1–3 个叶子，不能停在二级域
      "change_types": ["CT-01"]},
    "rejected": [{"id": "TH-0003", "reason": "同叶子但方向相反"}]}  // new 且有候选时覆盖全部候选
   ```
   - **新建命题必须逐个说明为何不归入候选**，这是防止"一个事件一个命题"的关键约束。
   - 本轮两个实体在同一新命题上对齐：第一个 `new` 并给 `alias`，其余 `attach` 到 `NEW:<alias>`。
   - 命题是方向性、可证伪的判断，不是事件标题；范围 1–3 个叶子；预期寿命以周到月计；写不出
     consequence 的不是技术命题；商业套餐、融资、管制类变化不建命题。
   - B 级事件可以 `attach` 作支持证据，也可以 `none`；反驳已有命题用 `attach` + `contradicts`。
3. 本轮窗口内聚类：识别 Convergence Signal（多实体）与 Frontier Signal（单实体拐点）。

**P4 价值门控排序**：评级标准见 task_def §10，优先级见 §14，章 2 Top N 规则见 §16。A/A+ 主卡必须含
四节深拆，内容落位见 task_def §15 与 `references/event-writing.md`。

**P4 后写入 registry**（整批事务，`--run-date` 用 WINDOW_START_DATE；补跑加 `--backfill`）：
```bash
python "$ASSETS/thesis_registry.py" ingest --events-dir events_run_<WINDOW_START_DATE> \
    --run-date <WINDOW_START_DATE> --report raw_<date>/collect_report.json
python "$ASSETS/thesis_registry.py" report --run-date <WINDOW_START_DATE> \
    --out events_run_<WINDOW_START_DATE>/thesis_report.json
```
- 校验失败整批不写、逐条报错；修正后重跑即可，同一 run 整批替换，不会重复计数。
- 输出的 `seen_before` 是相邻窗口重叠出现的事件，8.2 可标"上期已报"；`warnings`（疑似重复事件 /
  命题）逐条处理：改为 `attach`，或事后 `merge --source TH-a --target TH-b --reason ...`。
- 只能入库最新 run、重跑最近一次 run，或用 `--backfill` 补一个尚未入库的较早日期。
- `report` 是第 7 章的唯一输入：命题前后的状态与置信度、得分明细、本轮收敛 / 跨时间收敛、
  `core_judgment`（active/contested 且非 Low）。
- 其他决策：被否证 `retire`；表述收窄 `revise`；方向实质变化先新建再 `supersede`。statement 不直接改。

**Success criteria**：每个事件有变化类型、命题裁决与评级；`normalize`、`candidates`、`ingest`、`report`
退出码均为 0；ingest 的 warnings 已逐条处理。

**Rules**：候选只能由 `candidates` 生成，不能手写或删改。

### 5. P5 成稿：写 Markdown，渲染成 HTML

写之前读 `references/design-constraints.md` 的写作侧条款（§6–§8）与 `references/event-writing.md` 的
"第 1 章写法""视觉约束"。八章与各章内容要求见 task_def §16；栏目编号与名称查
`taxonomy.py chapter 3|4`。所有简报落在 `reports/`（报告库根目录，理由见 `references/design-rationale.md`）。

```bash
# 1) 写 reports/<标题 slug>-<WINDOW_START_DATE>.md；frontmatter 必须含 title / date / status / summary
# 2) 渲染：输出同名 .html 并更新报告库索引
python "$ASSETS/render_report.py" --md "reports/<标题 slug>-<WINDOW_START_DATE>.md"
# 3) 浏览器打开 .html 肉眼复核；有问题改 .md，重跑第 2 步
```

<HARD-GATE>
只改 `.md`，永远不手改 `.html`：它是渲染产物，会被覆盖，且门禁只校验 `.md`，手改等于绕过门禁。
</HARD-GATE>

**Markdown 结构契约**（门禁按此切分）：

| 层级 | 承载 |
|---|---|
| `## <章标题>` | 八章之一，按顺序匹配（第 N 个 `##` = 第 N 章） |
| `### <N.M> <栏目标题>` | 11 个栏目之一（3.1–3.4 / 4.1–4.7）；8.1 / 8.2 / 8.3 是审计子节 |
| `#### <事件卡标题>` | 一张事件卡 |
| `##### 挑战与问题` / `机制与架构` / `效果与定量` / `对比其他方案的价值` | A/A+ 主卡的四节深拆 |

**卡片标记行**：卡片正文第一行写 `**<评级> · <信号> · EV-xx**`，如 `**A+ · Frontier · EV-02**`。
评级必须与事件 JSON 一致；四节深拆的义务由事件 JSON 决定（A/A+ 的主卡必须写，聚合卡与首发早于窗口
的 Active Event 豁免），不看标记里写了什么。EV 编号只写在标记里（门禁扫卡片前 200 字符），深拆里的
EV 编号视为交叉引用。卡片不在自己的主栏目下时（折叠卡、章 2 承载主卡的 Top 卡），在标记里追加
`· 归属 N.M`。

| 分类呈现规则 | 做法 |
|---|---|
| 唯一主卡 | 每个事件只写一张全卡；章 2 的 Top 卡写了 `归属 N.M` 就是主卡，分类章只留"亦见"引用；章 2 未写归属的卡是摘要卡 |
| 主卡归位 | 全卡落在 `primary_path` 解析出的栏目；A/A+ 必须有主卡，B 级可只在章 5 出现 |
| 空栏目 | 0 条不出现 `###`；1 条折叠进相邻栏目并写 `归属 N.M`，每栏最多折 1 条；主卡在章 2、只留引用的栏目不算空 |
| 4.6 标注 | 卡片写具体技术域（评测环境 / 结果核验 / 可靠性归因 / 运行证据 / 调试回放 / 生产质量 / 身份授权 / 执行隔离 / 内容防护 / 审计治理），与事件 JSON 的 `annotation` 一致 |

**第 7 章**：只写 `thesis_report.json` 中 `core_judgment = true` 的命题，**一个不漏**；每条一个列表项，
写 `TH-xxxx`、类型、置信度（与 report 一致）、本轮收敛 / 跨时间收敛与前后变化；contested 的命题同一行
写出反证。没有核心判断时写明"本轮无核心技术判断"。

**图片**：只用本地图片（SVG / PNG / JPG），放 `reports/figures/`，按相对路径引用，如
`![Agent 状态从客户端移到服务端](figures/<slug>-<date>-arch.svg)`。渲染时内嵌为 data URI，页面才自包含；
本地图片缺失会让渲染失败，远程图片会被门禁拒绝。渲染器不支持 mermaid，比较类数字用表格。

**Success criteria**：`.md` 与 `.html` 都在 `reports/`；`render_report.py` 输出 `OK` 与报告库计数；
frontmatter 齐全；窗口在标题、首页、文件名上一致（task_def §0）；视觉复核通过后才进入步骤 6。

### 6. P6 验收 + 漏检回溯 + Registry

**6a. 机器校验**（以退出码为准，不由 LLM 读 HTML 自证）：
```bash
python "$ASSETS/verify_gates.py" --raw-dir raw_<date> \
  --md "reports/<标题 slug>-<WINDOW_START_DATE>.md" \
  --events events_run_<WINDOW_START_DATE>/ --state state/ --json-out verify_result.json
python "$ASSETS/render_report.py" --md "reports/<标题 slug>-<WINDOW_START_DATE>.md"
```
任一退出码非 0 都要修正后重跑。门禁逐层检查项见 `references/gate-checks.md`；它只查事实与结构，
不查排版。

**6b. 人工复核**（机器判不了的部分）：

| 复核项 | 判据 |
|---|---|
| 机制新颖性 | 是否真的改变了技术命题，而非只刷新数字 |
| 归类与裁决 | `primary_path` 与机制对得上；attach / new 是否真是同一 / 不同命题；反驳性证据是否如实裁决为 `contradicts`（置信度由裁决派生，裁决错了它就错） |
| 证据 | 来源数量、独立性、定量数据 |
| 章 1 主线 | 是否真的跨栏目 |
| 窗口文字 | title / H1 / Dashboard / 正文 / 文件名的时间范围一致；无残留"TARGET_DATE = 单一天"（task_def §18） |

**6c. 8.1 与 8.3**（数据直接来自 `candidate_pool.json`、`pool_out_of_window.json`、`gap_tasks.json`、
`collect_report.json`，不凭印象）：

- **8.3 丢弃日志与漏检回溯**：两张表；字段、"丢弃理由"与"漏检根因"两个封闭集合见 task_def §16.1；
  处置方式取 下一轮补采 / 申请权限 / 换通道 / 用二次源确认 / 已并入 TH-xxxx。
- **8.1 源与覆盖审计**（task_def §13 的 Zero-result 证据也记在这里）：判定分布；`items_in_window_exact`
  与 `items_in_window_fuzzy` 分别报；每个失明源的原因；实体×面覆盖情况；不可达面的登记理由与补偿方式；
  `entity_blind` 任务的结论；每个"0 命中 / 无新增"结论的检查面、时间范围、查询方式、无法访问的页面、
  快照不可用原因；漏跑窗口及补跑情况。

**6d. Registry**：命题状态（proposed / active / contested / dormant / retired）由证据与 run 计数派生，
没有单独的生命周期命令。8.3 发现命题被证伪用 `retire`，两个命题实为同一个用 `merge`。

**Success criteria**：`verify_gates.py` 与 `render_report.py` 退出码为 0；人工复核表逐项有结论；
8.1 / 8.3 已按上面填写。验收不通过必须修正后重新验收，不能跳过。

## 变更记录

历史踩坑与由此形成的约束见 `references/changelog.md`。**修改本 skill 的脚本或规则前先读它**；
新增条目按"日期 + 问题 + 根因 + 约束"追加在那里。
