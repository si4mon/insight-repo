---
name: tech-briefing
description: 生成 Asia/Shanghai 时区下从昨日 00:00 到执行时刻的多源技术热点简报，按 tech_report_task_def.md 规则采集、分析、成稿，输出完整 HTML 文件
allowed-tools:
  - Bash(python:*)
  - Bash(curl:*)
  - Bash(ls:*)
  - Bash(rm:*)
  - Bash(mkdir:*)
  - Bash(date:*)
  - Bash(powershell:*)
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
  Use when the user wants to generate the daily multi-source tech briefing.
  Triggers on phrases like: "生成技术简报", "重新生成技术简报", "今日技术简报", "跑一下技术简报".
  Also use when the user references the tech briefing workflow or asks to regenerate today's briefing.
  The skill handles the full pipeline: time window freezing, multi-source data collection,
  candidate pool construction, abstraction/clustering/rating, HTML generation, and acceptance verification.
---

# 多源技术热点简报生成

生成 Asia/Shanghai 时区下，从"昨日 00:00"开始至"任务实际执行时刻"为止的"多源技术热点简报"，
默认交付完整、可独立打开的高信息密度 HTML 文件。

## 目录结构

本 skill 自包含全部引擎与骨架，不依赖任何项目目录：

```
~/.cac/skills/tech-briefing/
├── SKILL.md                          # 本文件（skill 定义）
├── assets/                           # 只读引擎 + 稳定骨架
│   ├── tech_report_task_def.md       # 24KB 完整任务定义（规则源）
│   ├── collect_sources.py            # 多源数据采集脚本
│   ├── thesis_registry.py            # Thesis registry API
│   └── thesis_ontology.json          # Upper Ontology 骨架
└── data/                             # 可写全局状态
    └── thesis_registry.json          # Thesis 实例库（跨 run 累积）
```

**工作目录**（用户执行 skill 时所在的目录）存放运行时产物：
- `raw_<date>/` — 采集的原始数据
- `events_run_<date>/` — 本轮事件 JSON 文件
- `collect_report.json` — 采集报告
- `多源技术热点简报_YYYY-MM-DD.html` — 输出简报

**路径变量**（下文统一使用）：
- `$SKILL_DIR` = `~/.cac/skills/tech-briefing`
- `$ASSETS` = `$SKILL_DIR/assets`
- `$DATA` = `$SKILL_DIR/data`
- `$WORKDIR` = 当前工作目录（用户执行 skill 时所在的目录）

## 前置依赖

- **任务定义**：`$ASSETS/tech_report_task_def.md`
  — 24KB 的完整任务定义，包含 TARGET_WINDOW Gate、五路召回、变化类型分类、
  技术命题映射、A/A+ 评级标准、八章结构规范、18 条验收清单等全部规则。
  **必须在步骤 1 之前读取此文件，并严格遵守其中的全部规则。**
- **采集脚本**：`$ASSETS/collect_sources.py`
  — 多源数据采集脚本，已针对华为 MWG 代理网关优化（UA 分流、HF 镜像、重试、fallback）。
- **Thesis Registry 三件套**：
  - `$ASSETS/thesis_ontology.json` — Upper Ontology 骨架（9 种变化类型、双 Track、评级标准、评估链）。**稳定骨架，由人工维护，不由 LLM 动态改写。**
  - `$DATA/thesis_registry.json` — Thesis 实例库（跨 run 累积的 thesis 历史）。
  - `$ASSETS/thesis_registry.py` — query / ingest / update / merge API。
- **样式参考**：工作目录下已有的 `多源技术热点简报_*.html` 文件可作为 HTML 样式参考。

## Goal

生成一个完整的 `$WORKDIR/多源技术热点简报_YYYY-MM-DD.html` 文件，满足：
1. TARGET_WINDOW 正确冻结（昨日 00:00 → 今日执行时刻 Asia/Shanghai）
2. 包含完整八章结构
3. 通过 18 条验收清单
4. 采集报告 collect_report.json 落盘到 `$WORKDIR`
5. 必须先运行 collect_sources.py 采集数据，不能跳过采集步骤
6. Thesis registry 正确读写（convergence 查询 + ingest + 生命周期更新）

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

读取 `$ASSETS/tech_report_task_def.md` 全文，理解全部规则后再进入步骤 2。

**Success criteria**:
- 已获取 NOW_SHANGHAI 真实时刻（非系统默认时区、非历史文件名推导）
- TARGET_WINDOW 已冻结，WINDOW_START / WINDOW_END 明确
- tech_report_task_def.md 已读取并理解

**Rules**:
- 禁止使用用户时区、浏览器时区、系统默认时区、上一轮日期、历史文件名、历史正文推导 TARGET_WINDOW
- 昨日 00:00 之前首次发布的事件不得作为本轮"新事件"进入正文
- 无法确认首发时刻的高价值候选必须标注"首发时间未完全核实"

### 2. 运行 collect_sources.py 采集多源数据

在工作目录下执行采集脚本：
```bash
cd "$WORKDIR" && python "$ASSETS/collect_sources.py"
```

脚本会自动：
- 采集 arXiv（cs.AI/CL/LG/MA/RO）、HuggingFace（走 hf-mirror.com 镜像）、Hacker News、
  Techmeme、GitHub Trending、专家博客（Simon Willison / Latent Space）、
  中文媒体（机器之心 / 新智元 / 量子位）、Tier-1 厂商官方 blog（Anthropic / OpenAI /
  DeepMind / Google / Cloudflare / MiniMax / Mistral / Inception）
- 每个 UA 分流（curl/8.0 默认，浏览器 UA 用于 Tier-1 官方站）
- 失败重试 3 次，大页面 timeout 45s
- 输出到 `$WORKDIR/raw_<date>/` 目录
- 生成 `collect_report.json` 采集报告（在 raw_<date>/ 目录内）

**Success criteria**:
- collect_sources.py 执行完毕
- `$WORKDIR/raw_<date>/` 目录存在且包含采集到的文件
- `collect_report.json` 已生成，记录每个源的采集结果

**Rules**:
- 必须运行采集脚本，不能跳过直接用历史数据
- 采集失败的源不中断流程，在步骤 6 的 8.1 Source Audit 中标注 Zero-result
- 如果成功率低于 50%，暂停并告知用户

### 3. P1 宽召回：解析源数据，构建候选池

解析 `$WORKDIR/raw_<date>/` 下的全部源数据，提取标题/链接/发布时间/要点，
过滤 SCAN_WINDOW 范围内的条目，构建候选池。

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

**Success criteria**:
- 全部源数据已解析
- 候选池构建完成，每个候选有首发时刻、来源、召回通道标注
- 明确区分"本轮新事件"与"Active Event / Historical Context"

### 4. P2-P4 抽象提升、聚类收敛、价值门控排序

按 tech_report_task_def.md 中的规则。本步同时与 **thesis registry** 交互，
保证跨 run 一致性（避免 thesis 命名漂移、支持跨时间收敛判断）。

**Registry 三件套位置**：
- Ontology（只读骨架）：`$ASSETS/thesis_ontology.json`
- Registry 实例库（可写全局状态）：`$DATA/thesis_registry.json`
- API 脚本：`$ASSETS/thesis_registry.py`

**P2 抽象提升**：对每个候选识别变化类型（CT-01..CT-09，见 ontology），映射到技术命题（一句话）。
对每个候选事件构造 event 记录（含 thesis_name / statement / change_types /
tracks / sections / rating / signal / first_publish_shanghai / source /
event_title / key_data / entity / confidence），保存为 JSON 文件到
`$WORKDIR/events_run_<date>/`。

**P3 聚类收敛（含跨时间收敛）**：
1. 先用 `python "$ASSETS/thesis_registry.py" convergence --event-file <event.json>`
   对每个事件查询历史 thesis 的 change_types / tracks / sections 交集，
   识别"本轮事件 ↔ 历史 thesis"的跨时间收敛。
2. 再做本轮窗口内的聚类：同一技术命题的候选聚到一起，识别
   Convergence Signal（多实体收敛）和 Frontier Signal（单实体拐点）。
3. 跨时间收敛 + 本轮收敛共同决定 thesis 的 state 迁移：
   proposed → active（再次出现）、active → dormant（长期无新证据）。

**P4 价值门控排序**：按 Technical Value / Evidence Confidence / Trend Maturity 评级。
A+ = 机制新颖 + 定量充分 + 多源共振；A = 量化显著但缺乏独立基准；
B = 信号明确但证据不足。

选取 Top 3（跨 Track），Top 1 需深拆（架构可视化 + 落地场景 + 与历史路线关系）。
对比 registry 中同名/相关 thesis 的历史置信度，更新本轮置信度。

**P4 后写入 registry**：对每个入选事件执行
`python "$ASSETS/thesis_registry.py" ingest --event-file <event.json> --run-date <YYYY-MM-DD>`。
- 映射到已有 thesis：追加 event 记录，更新 last_seen / evidence_count，
  proposed → active；若新实体出现则加入 convergence_entities。
- 新建 thesis：分配新 ID（TH-xxx），rating B/C 默认 state=proposed，
  A/A+ 默认 state=active。
- 若发现两个 thesis 语义重合：`python "$ASSETS/thesis_registry.py" merge --source TH-xxx --target TH-yyy`。

**Success criteria**:
- 每个入选事件有变化类型（CT-xx）+ 技术命题 + 评级
- Top 3 已选取，Top 1 深拆完成
- Convergence / Frontier Signal 已识别，并标注"本轮收敛"或"跨时间收敛"
- thesis_registry.json 已更新：新 thesis 入库或已有 thesis 追加 event
- 没有重复 thesis（已通过 merge 合并）

**Rules**:
- P3 必须调用 registry 的 convergence 查询，不能只做本轮窗口内聚类
- thesis 的 statement 一经写入尽量保持稳定；若本轮发现 statement 需要修订，
  在 notes 中追加修订原因，不直接改写 statement（保留可追溯性）
- proposed 状态的 thesis 不进入第 7 章"本轮技术判断"核心技术判断，
  只在第 5 章"值得关注"中作为 Early Signal 出现

### 5. P5 成稿：生成完整 HTML 简报

按固定八章结构生成 HTML 文件 `$WORKDIR/多源技术热点简报_YYYY-MM-DD.html`（YYYY-MM-DD = WINDOW_START_DATE）：

1. 技术总结与趋势
2. 模型技术热点（2.1 Language/Reasoning/Training、2.2 Multimodal/Speech、
   2.3 World Model/Embodied、2.4 Model-Agent Boundary）
3. Agent/Harness 技术热点（3.1 Runtime/Session、3.2 Memory/Knowledge、
   3.3 Harness/Loop/Skill、3.4 Multi-agent/AgentOS、3.5 Trusted Agent/Sandbox）
4. 今日必看（跨 Track Top 3，Top 1 深拆）
5. 值得关注（Early Signal / Active Event / Counter-signal / 时间边界候选）
6. 业界专家观点与趋势信号（L1 New Statement / L2 Reactivated / L3 Validation）
7. 本轮技术判断（Frontier Thesis / Convergence Thesis + 置信度）
8. 信息源采集统计（8.1 Source/Zero-result Audit、8.2 Event Index、8.3 漏检回溯）

HTML 样式参考工作目录下已有简报文件（sidebar + main 布局，hero 区显示 TARGET_WINDOW，
card 组件含 meta tags / facts / analysis grid / sources）。

**Success criteria**:
- HTML 文件已写入工作目录根
- 八章结构完整
- H1 时间范围 = TARGET_WINDOW
- 8.2 Event Index 中所有"本轮新事件"首发时刻在 TARGET_WINDOW 内
- 8.3 漏检回溯表已填写

**Rules**:
- 文件名中的日期 = WINDOW_START_DATE（昨日日期）
- 正文首页必须显示 WINDOW_START / WINDOW_END
- H1 中的时间范围必须等于 TARGET_WINDOW

### 6. P6 验收 + 漏检回溯 + Registry 生命周期更新

**6a. 验收**（18 条清单，见下）

**6b. 漏检回溯表**（8.3）

**6c. Registry 生命周期更新**：HTML 验收通过后执行
`python "$ASSETS/thesis_registry.py" update --run-date <YYYY-MM-DD>`，
触发 thesis 的 state 迁移（active → dormant / dormant → retired）。
若 8.3 漏检回溯发现"抽象提升失败 / 价值误判"导致漏检，
应向对应 thesis 追加 counter_evidence：
`python "$ASSETS/thesis_registry.py"` 模块调用 `reg.add_counter_evidence(thesis_id, evidence, run_date)`。

执行 18 条验收清单：
1. HTML 文件 size > 0
2. `<title>` 存在且含时间范围
3. `<h1>` 存在且含时间范围
4. 八个 section（s1-s8）id 齐全
5. 8.1 / 8.2 / 8.3 三个子节存在
6. 原始来源链接 ≥ 10
7. TARGET_WINDOW 在 hero 区显示
8. title / H1 / Dashboard 时间一致
9. 8.2 所有本轮新事件首发时刻在 TARGET_WINDOW 内
10. 8.2 早于 WINDOW_START 的事件标为 Active Event
11. 无晚于 WINDOW_END 的新事件
12. 无残留 TARGET_DATE 单一天逻辑
13-18. 其他一致性检查

生成漏检回溯表（8.3），记录：
- 可能漏检项（未覆盖的源面）
- 根因分类（代理拦截 / 源面未覆盖 / 官方原文未回溯）
- 处置方式（下一轮补采 / 申请权限 / 用二次源确认）

**Success criteria**:
- 18 条验收清单全部通过
- 漏检回溯表已填写
- 失败源已在 8.1 标注 Zero-result

**Rules**:
- 验收不通过时必须修正后重新验收，不能跳过
