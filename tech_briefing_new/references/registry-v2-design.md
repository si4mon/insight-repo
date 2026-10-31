# Thesis Registry v2 设计方案

> 适用范围：`tech_briefing_new` skill 的 P3 聚类收敛、P4 入库、P6 生命周期，以及第 7 章"本轮技术判断"。
> 前提：**不迁移历史**。v2 从空库起步；v1 的 `thesis_registry.py` 与 `data/thesis_registry.json` 不再读取，可以删除或归档。

## 0. 摘要

v1 registry 的定位是"技术命题库"，但实际运行中退化成了一份事件日志：51 个 thesis 里有 37 个只有 1 条证据，跨时间收敛查询对 v2 事件恒返回空，置信度只升不降，相邻窗口的重叠还会把同一事件计两次。

v2 只回答三个问题：

1. **这条事件是不是在给某个已知命题加证据？**（归属）
2. **这个命题现在有多可信？**（置信度）
3. **本轮哪些命题变强、变弱、被挑战、或沉寂了？**（第 7 章的输入）

为此做了五个关键决策：

| 决策 | v1 | v2 |
|---|---|---|
| 事件与命题 | 一个事件新建一个 thesis | 事件（证据）与命题（thesis）分开存储，用 link 连接；一个命题积累多条证据 |
| 归属判断 | 机械交集 + LLM 临场写脚本覆写 | **机器召回候选 → LLM 写裁决 → registry 校验后入库**，三步各有留痕 |
| 状态与置信度 | 逐次累加、只升不降 | **由证据派生**：每次读取时从 links 重新计算，反证会降低置信度 |
| 幂等 | 无；重跑或窗口重叠都会重复计数 | 事件按 `event_key` 去重，入库以 run 为单位整批替换 |
| 状态存放 | skill 安装目录下的 `data/` | 工作目录下的 `state/`，与代码分离 |

---

## 1. 目标与非目标

**目标**

- 同一命题的证据跨天累积，"跨时间收敛"成为可计算的事实，而不是 LLM 的印象。
- 置信度可以复算、可以下降，第 7 章的置信度和变化方向直接来自 registry 的输出。
- 同一窗口重跑、相邻窗口重叠、gate 失败后修改重跑，都不会污染 registry。
- 归属判断的每一步都可以被门禁检查：查过什么、选了什么、为什么不选其他候选。

**非目标**

- 不迁移 v1 的 51 个 thesis，也不回填历史简报。
- 不做语义向量检索。召回只依赖分类结构，语义判断由 LLM 完成（理由见 §5）。
- 不改变事件级的规则：评级、claims、窗口归属、一个事件承载一个命题，这些保持现有定义。

---

## 2. v1 的问题清单（设计输入）

| # | 问题 | 证据 | v2 中对应的位置 |
|---|---|---|---|
| 1 | 收敛维度与 v2 分类体系脱节 | 查询要求 track 或 section 有交集，而 v2 事件不写这两个字段，CLI 恒返回 `[]` | §5 用叶子路径召回 |
| 2 | 旧 section ID 语义冲突 | `s3-x` 在 v1 表示 Harness，在 v2 表示模型章；TH-048"世界模型"和 AgentOS 类命题落进同一个桶 | §4 只用叶子 ID，不再使用 section |
| 3 | 一个事件一个 thesis | 37/51 只有 1 条证据；SKILL 写着"每个事件都会分配新 TH 编号，这是预期行为" | §4 事件与命题分离、§5 裁决 |
| 4 | 置信度只升不降 | `_max_confidence` 只取较大值，反证只是追加一条记录 | §6 派生置信度 |
| 5 | 重叠窗口重复计数 | 窗口为"昨日 00:00 到执行时刻"，相邻两轮重叠约 9 小时，有日期的事件会被 ingest 两次 | §8 幂等 |
| 6 | merged 的 thesis 仍会被召回 | 召回只排除 `retired` | §5 召回只取有效状态 |
| 7 | 生命周期按天数近似 run 数 | `runs_since = days_since` | §7 按实际 run 计数 |
| 8 | 关键步骤靠临场脚本 | `make_events.py`、`fix_events.py` 由 LLM 每轮现写 | §9 固化为工具 |
| 9 | 没有测试 | registry 是 bug 最多的模块，却是唯一没有单测的核心模块 | §12 |

---

## 3. 设计原则

1. **证据和结论分开存。** 事件是不可变的证据，thesis 是可以被证据支持或削弱的命题。结论（状态、置信度、类型）不存储，每次都从证据推导出来。
2. **只存决策，不存累加值。** registry 持久化的只有四类东西：命题定义、事件、link（哪条事件以什么关系挂在哪个命题上）、显式决策（合并、否证、修订）。`evidence_count`、`confidence`、`state` 都是派生值。这样重跑、修正、撤销都只需要替换决策，派生值自动正确。
3. **机器负责召回和校验，LLM 负责语义裁决。** 机器擅长"不漏"和"一致"，LLM 擅长"是不是同一个命题"。每一方只做自己擅长的部分，而且每一方的输出都有留痕。
4. **幂等优先。** 同一份输入执行两次，结果与执行一次相同。
5. **状态不跟代码走。** skill 目录可能是只读的，也可能被多个工作目录共享，运行状态属于工作目录。

---

## 4. 数据模型

一个 JSON 文件：`$STATE/thesis_registry.json`。默认 `$STATE = $WORKDIR/state`，可以用 `--state` 参数或环境变量 `TECH_BRIEFING_STATE` 覆盖。

```jsonc
{
  "schema_version": 2,
  "runs":      [ /* Run */ ],
  "events":    { "<event_key>": /* Event */ },
  "theses":    { "TH-0001": /* Thesis */ },
  "links":     [ /* Link */ ],
  "decisions": [ /* Decision：合并、否证、修订 */ ]
}
```

### 4.1 Run

```jsonc
{ "run_date": "2026-10-30",                  // = WINDOW_START_DATE，是 run 的身份
  "window": ["2026-10-30T00:00:00+08:00", "2026-10-31T09:12:00+08:00"],
  "ingested_at": "2026-10-31T10:05:00+08:00",
  "event_keys": ["..."] }                    // 本轮入库的事件
```

同一个 `run_date` 再次 ingest 时，**整批替换**该 run 的 links，不会追加（见 §8）。

### 4.2 Event（证据，不可变）

```jsonc
{ "event_key": "a3f9c2e1b7d0",              // 由工具计算，见 §8.1
  "title": "...", "entity": "OpenAI",
  "source": "https://...", "first_publish": "2026-10-30T02:00:00+08:00",
  "primary_path": "B1.1", "related_domains": ["C3.1"],
  "change_types": ["CT-01", "CT-04"],
  "rating": "A+", "signal": "Frontier",
  "evidence_form": "product",                // 新增字段：paper | product | api | code | benchmark | deployment | expert
  "seen_in_runs": ["2026-10-30", "2026-10-31"] }
```

`evidence_form` 用于计算 Cross-Form 维度（ontology 中的 convergence 维度之一）。v1 没有这个字段，所以这个维度一直无法计算。

### 4.3 Thesis（命题定义）

```jsonc
{ "id": "TH-0007",
  "name": "判断从生成后解析转向专用决策模型",
  "statement": "判断/决策能力从通用 LLM 的生成后解析移到专用类型化决策模型，因此决策接口契约成为新约束",
  "object": "判断/决策能力",                 // 什么在变
  "consequence": "决策接口契约成为新约束",   // 所以呢
  "scope_leaves": ["B1.1"],                  // 1–3 个叶子，召回依据
  "change_types": ["CT-01", "CT-06"],
  "created_in": "2026-10-30",
  "revisions": [] }                          // statement 修订记录，见 §4.6
```

**不存储的字段**：`state`、`confidence`、`evidence_count`、`thesis_type`（Frontier/Convergence）、`entities`、`last_seen`。这些都在读取时由 links 推导（§6、§7）。

### 4.4 Link（事件与命题的关系）

```jsonc
{ "event_key": "a3f9c2e1b7d0", "thesis_id": "TH-0007",
  "relation": "supports",                    // supports | contradicts | refines
  "decided_in": "2026-10-30",                // 由哪个 run 的裁决产生
  "rationale": "一句话理由" }
```

- 一个事件只有一条 link，延续"一个事件承载一个命题"的规则。如果一个事件对另一个命题也有意义，按现有 claims 规则拆成单独的事件。
- `refines`：事件支持该命题，但同时收窄或修正了它的边界。计为支持，并提示考虑用 `revise` 修订 statement（§4.5）。
- 唯一约束是 `(event_key)` 唯一，从结构上杜绝重复计数。

### 4.5 Decision（显式决策）

只记录不能从证据推导出来的人为决定：

| type | 字段 | 作用 |
|---|---|---|
| `merge` | `source`、`target`、`reason` | source 的 links 在推导时视为属于 target；source 状态为 `merged` |
| `retire` | `thesis_id`、`reason` | 被否证或确认失效，状态为 `retired` |
| `revise` | `thesis_id`、`new_statement`、`reason` | 修订 statement，旧版保留在 `revisions` 里 |
| `supersede` | `old`、`new`、`reason` | 命题方向发生实质变化，新建命题取代旧命题 |

### 4.6 命题粒度准则

这是 v1 实际失效的根源，所以写进 SKILL，并由 ingest 做形式校验：

- **命题是方向性判断，不是事件标题。** 它要能被后续证据支持或推翻。"某公司发布了某产品"不是命题。
- **范围限定在 1–3 个叶子内。** 超过 3 个叶子，说明它是第 1 章的跨栏目主线，不是单个命题。
- **预期寿命以周到月计。** 只在一天内成立的判断不应进入 registry。
- **必须写出 consequence。** 也就是 task_def 句式"X 从 A 移到 B，**因此 C 成为新约束**"中的 C。写不出 C，说明还不构成技术命题。

用 v1 已有条目举例：

| v1 条目 | 判断 | 原因 |
|---|---|---|
| TH-003 System One 专用模型谱系扩张 | 合格 | 方向明确、可证伪，后续有多实体证据 |
| TH-049 订阅制 API 额度从开发者工具变为套餐权益 | 不应成为命题 | 商业套餐变化，不对应技术约束；作为事件进 8.3 即可 |
| TH-047 芯片管制催生灰色供应链 | 不应成为命题 | 非技术命题，且被错归入 4.6（评测与治理） |

---

## 5. 归属流程：召回 → 裁决 → 校验

### 5.1 机器召回（`registry candidates`）

对每个事件，在**有效命题**（排除 `retired`、`merged`）中打分：

| 特征 | 分值 |
|---|---|
| `primary_path` 属于命题的 `scope_leaves` | +4 |
| 与某个 scope 叶子同属一个二级域（如 B1.1 与 B1.2） | +2 |
| `related_domains` 与 scope 叶子或其二级域相交 | +1 |
| `change_types` 有交集 | 每项 +1，最多 +2 |
| 命题已有证据来自同一实体 | +1 |

总分 ≥ 3 进入候选，按分数取前 8 个。结果写回事件 JSON：

```jsonc
"thesis_candidates": [
  { "id": "TH-0007", "score": 7, "state": "active", "confidence": "Medium",
    "reasons": ["同叶子 B1.1", "CT-01"] }
]
```

**为什么不用语义检索。** 结构化召回可以复现、可以解释，门禁也能校验"候选集是否真的由工具生成"。语义上的跨域关联交给 LLM：如果它认为某个不在候选集里的命题才是正确归属，可以通过 override 指定，但必须写理由（§5.2）。另外提供 `registry search <关键词>` 作为人工兜底查询。

### 5.2 LLM 裁决（写在事件 JSON 里）

```jsonc
"thesis_decision": {
  "action": "attach",                        // attach | new | none
  "thesis_id": "TH-0007",                    // attach 时必填；同批新建的命题写 "NEW:<alias>"
  "relation": "supports",                    // supports | contradicts | refines
  "rationale": "一句话：为什么是同一命题",
  "override_reason": "",                     // attach 的目标不在候选集时必填
  "new_thesis": null,                        // new 时必填：name/statement/object/consequence/scope_leaves/change_types，可选 alias
  "rejected": []                             // new 且候选非空时必填：[{id, reason}]
}
```

规则：

- A/A+ 事件的 `action` 只能是 `attach` 或 `new`。B 级及以下可以是 `none`，即只作为事件记录，不挂到任何命题上。
- **选择 `new` 时，必须逐个说明为什么不归入现有候选。** 这是防止命题无限增殖的关键约束，v1 正是在这里失守的。
- `contradicts` 只能用于 `attach`。不存在"新建一个被反驳的命题"这种操作。
- **同批次内引用新命题**：本轮两个实体在同一个新命题上对齐（本轮收敛）时，第二个事件在召回里
  看不到这个尚未入库的命题。做法是第一个事件 `new` 并给 `new_thesis.alias`，其余事件
  `attach` 到 `NEW:<alias>`；ingest 先建全部新命题，再解析这些引用。
- **已入库事件再次出现**时，`none` 表示保留原裁决，不会删除已有 link。

### 5.3 registry 校验（`registry ingest`）

ingest 是一个事务：整批事件全部通过校验才写入，任何一条失败则整批不写。

| 校验 | 失败时 |
|---|---|
| 事件 schema 合法，`event_key` 已计算 | 拒绝 |
| `attach` 的目标存在且有效；不在候选集时 `override_reason` 非空 | 拒绝 |
| `new` 的 `scope_leaves` 为 1–3 个合法叶子，`consequence` 非空，候选非空时 `rejected` 覆盖全部候选 | 拒绝 |
| A/A+ 事件的 `action` 不是 `none` | 拒绝 |
| 同实体、同叶子、首发时间相差 24 小时以内，但 `event_key` 不同 | 警告"疑似重复事件"，不拒绝 |
| 新命题与现有命题的 `scope_leaves` 和 `object` 都相同 | 警告"疑似重复命题"，提示考虑 attach 或 merge |

---

## 6. 置信度：由证据派生

置信度是 links 的纯函数，每次读取时计算。参数放在 `thesis_ontology.json` 的 `confidence_model` 里，可以调整，不写死在代码中。

**只计入有效证据**：relation 为 `supports` 或 `refines`。

| 维度（对应 ontology） | 计算 | 分值 |
|---|---|---|
| 证据强度 | 支持证据中的最高评级 | A+ = 3，A = 2，B = 1 |
| Cross-Entity | 支持证据的不同实体数 | 2 个 +1，≥3 个 +2 |
| Cross-Form | 支持证据的不同 `evidence_form` 数 | ≥2 种 +1 |
| Temporal Persistence | 支持证据首发时间覆盖的不同 ISO 周数 | 2 周 +1，≥4 周 +2 |
| Adoption | 存在 `evidence_form = deployment` 的支持证据 | +1 |
| Counter-Evidence | 近 60 天的反证 | 每条 A/A+ 反证 −2，每条 B 反证 −1 |
| 时效 | 近 30 天没有任何支持证据 | −1 |

分档：**≥ 6 为 High，3–5 为 Medium，≤ 2 为 Low。** 现有规则"Low 不进入核心技术判断"保持不变。

按这个模型推算：

- 单条 A+ 证据得 3 分，为 Medium，可以作为 Frontier Thesis 进入第 7 章。
- 单条 A 证据得 2 分，为 Low，需要第二条独立证据才能进入第 7 章。这和评级定义"A = 量化显著但缺乏独立基准"一致。
- 要到 High，需要类似"A+ + 3 个实体 + 跨 2 周"这样的组合（3 + 2 + 1 = 6）。
- 一条 A+ 反证可以把 Medium 拉回 Low，这正是 v1 做不到的。

Frontier 和 Convergence 也是派生值：支持证据来自 ≥ 2 个实体为 **Convergence Thesis**，否则为 **Frontier Thesis**。

---

## 7. 生命周期：按 run 计数的派生状态机

状态也在读取时计算，计数单位是 `runs` 列表里的**实际运行次数**，不是自然日。

| 状态 | 判定（按优先级从上到下） |
|---|---|
| `merged` | 存在以它为 source 的 merge 决策 |
| `retired` | 存在 retire 决策；或 dormant 后累计 30 个 run 仍无支持证据；或停留在 proposed 超过 10 个 run 仍无第二条证据（原因记为"未获二次证据"） |
| `contested` | 近 60 天内有 A/A+ 反证 |
| `dormant` | 距离最近一条支持证据已有 ≥ 14 个 run |
| `active` | 至少有 1 条 A/A+ 支持证据，或至少有 2 条不同事件的支持证据 |
| `proposed` | 其他情况（典型情况：只有一条 B 级支持证据） |

由上表可以推出以下转移（不需要单独存储，状态随证据和 run 数自然变化）：

| 从 | 到 | 触发 |
|---|---|---|
| proposed | active | 出现第二条不同事件的支持证据，或出现一条 A/A+ 支持证据 |
| proposed | retired | 10 个 run 内没有第二条证据 |
| active | contested | 出现 A/A+ 反证 |
| contested | active | 该反证已超过 60 天 |
| active | dormant | 14 个 run 没有新的支持证据 |
| dormant | active | 出现新的支持证据 |
| dormant | retired | 再过 30 个 run 仍无支持证据 |
| 任意 | retired / merged | 显式的 retire / merge 决策 |

与现有规则的对应关系：

- `proposed` 不进第 7 章核心判断，只能作为第 5 章的 Early Signal（沿用现有规则）。
- `contested` 可以进第 7 章，但必须同时写出反证。这正好对应现有的人工复核项"有反证时是否下调置信度"。
- `dormant` 的命题仍会出现在召回里，所以新证据可以把它唤醒，"重新出现"因此成为可计算的事件。

---

## 8. 幂等与窗口重叠

### 8.1 event_key

`event_key` 等于规范化后的首发来源的 sha1 前 12 位。规范化规则如下：

| 来源 | 规范形式 |
|---|---|
| arXiv | `arxiv:<id>`，去掉版本号。v1 与 v2 视为同一事件；修订版按现有规则在事件里标注"v2 修订" |
| GitHub release | `gh:<org>/<repo>@<tag>` |
| 其他 URL | 小写 host，去掉 `www.`、query、fragment 和末尾斜杠 |

### 8.2 三种重复场景

| 场景 | 行为 |
|---|---|
| **同一窗口重跑**（失败重试、gate 修正后重跑） | 同一个 `run_date`：先删除该 run 之前产生的全部 links，再写入本次的裁决。派生值自动正确 |
| **相邻窗口重叠**（今天 00:00 到 09:00 的事件在明天的窗口里再次出现） | `event_key` 已存在：只在 `seen_in_runs` 里追加本轮。如果本轮裁决与已有 link 相同，不做任何操作；如果不同，更新 link 并记录 `decided_in`。证据按 event_key 计数，所以不会重复 |
| **同一事件换了来源 URL** | 由 §5.3 的"疑似重复事件"警告兜底，LLM 确认后复用已有的 event_key |

ingest 的输出会标出 `seen_before: <run_date>`。第 8.2 节可以据此标注"上期已报"：事件仍然出现在正文里，满足"每轮交付全量简报"的硬约束，但不计入新增。

---

## 9. 工具与接口

### 9.1 `events.py`：替代 `make_events.py` 和 `fix_events.py`

| 命令 | 作用 |
|---|---|
| `events.py normalize --events-dir D` | 补全 `event_key`，统一枚举值写法（`date_precision`、`evidence_form` 等），按 schema 校验（只用标准库，不引入 jsonschema 依赖） |

LLM 仍然按自己的方式写 `EV-xx.json`，但写完之后必须经过 normalize，字段拼写不一致的问题就此消失。

### 9.2 `thesis_registry.py`（v2 重写）

| 命令 | 作用 | 用在哪一步 |
|---|---|---|
| `candidates --events-dir D` | 为每个事件写入 `thesis_candidates` | P3 |
| `ingest --events-dir D --run-date R` | 校验裁决并以事务方式入库；同一 R 整批替换。只能入库最新 run 或重跑最近一次 run，早于最近一次的 R 会被拒绝 | P4 |
| `report --run-date R [--out events_run_R/thesis_report.json]` | 本轮触及的命题：状态和置信度的前后对比、Frontier/Convergence、本轮收敛或跨时间收敛、得分明细 | P5 写第 7 章 |
| `show TH-xxxx` / `search <kw>` / `stats` | 查询 | 任意时候 |
| `merge` / `retire` / `revise` / `supersede` | 写入显式决策 | 人工维护 |

`report` 中的"收敛类型"是派生值：

- **本轮收敛**：本轮新增的支持证据来自 ≥ 2 个实体。
- **跨时间收敛**：本轮新增了支持证据，并且该命题在更早的 run 里已有支持证据。

前后对比的计算方法是：分别只用 `decided_in < R` 的 links 和全部 links 计算一次，二者的差就是本轮带来的变化。

`run_lifecycle` 不再需要作为单独命令：状态是派生值，ingest 时记录了 run，状态就自然推进了。

### 9.3 Python API

```python
reg = Registry.open(state_dir)                 # 加锁读取
reg.candidates(event) -> list[Candidate]
reg.ingest_run(run_date, window, events) -> IngestResult  # 事务；失败时抛 ValidationError 并附全部错误
reg.view(thesis_id, as_of=None) -> ThesisView  # 派生出 state/confidence/type/entities
reg.report(run_date) -> RunReport
reg.save()                                     # 原子写入
```

---

## 10. 与 SKILL、门禁、第 7 章的集成

### 10.1 事件 JSON 字段变化

| v1 字段 | v2 字段 |
|---|---|
| `convergence_checked` / `convergence_hits` | `thesis_candidates`（由工具写入） |
| `convergence_semantic` | `thesis_decision`（LLM 写入） |
| `thesis_name` / `statement` / `proposed_thesis_id` | 移入 `thesis_decision.new_thesis` 或 `thesis_id` |
| `tracks` / `sections` | 删除（v2 已经废弃） |
| — | 新增 `evidence_form` |
| claims 的 `absorbed:<EV-xx>` | 不变，仍指向本事件，本事件再通过 decision 指向命题 |

### 10.2 SKILL 中步骤 4 的新顺序

```
写 EV-*.json → events.py normalize → registry candidates
  → LLM 逐条写 thesis_decision → registry ingest（失败就修正裁决再跑，可安全重跑）
  → registry report → 按 thesis_report.json 写第 7 章
```

删除 SKILL 中 `fix_events.py` 的代码块、"批量 ingest 要自己补 track/section"一段，以及 P6 中的 `update` 步骤。

### 10.3 门禁（`verify_gates.py` 追溯层）

| 检查项 | 规则 |
|---|---|
| 候选已生成 | 每个 A/A+ 事件都有 `thesis_candidates`（允许为空列表），并且与 `registry candidates` 重新计算的结果一致 |
| 裁决完整 | 每个 A/A+ 事件都有 `thesis_decision`，`action` 不是 `none` |
| 新命题有对照 | `action = new` 且候选非空时，`rejected` 覆盖全部候选 |
| 已入库 | registry 中存在本轮的 run，其 `event_keys` 与 8.2 声明的事件一致 |
| 第 7 章引用合法 | 第 7 章引用的 `TH-` 编号都存在于 `thesis_report.json` 中；状态为 active 或 contested；置信度文字与 report 一致；contested 的命题必须写出反证 |

---

## 11. 存储与并发

- **原子写**：先写临时文件，再用 `os.replace` 替换，在 Windows 上同样适用。
- **单写者锁**：`state/.registry.lock`，用 `O_CREAT | O_EXCL` 创建；超时后报错，不会强行覆盖。
- **审计日志**：`state/registry_log.jsonl` 只追加，每次 ingest 或决策写一行（run、操作、变更摘要），用于事后追溯"某个置信度是怎么来的"。
- **容量估算**：每天 10–18 个事件，一年约 5,000 条事件，JSON 约 5–10 MB，单文件足够。如果日后出现多个工作目录共享一份状态、或者需要按年份查询的需求，再迁移到 SQLite；派生式设计使这次迁移只涉及存储层。

---

## 12. 测试计划

| 测试 | 预期 |
|---|---|
| 同一 run 连续 ingest 两次 | 状态完全一致，没有重复的 link |
| 修改一条裁决后重跑同一 run | 旧 link 被替换，置信度随之变化 |
| 相邻窗口出现同一 event_key | 证据数不变，`seen_in_runs` 追加，`seen_before` 被标出 |
| 一条 B 级证据 | 状态为 proposed；同一事件重复 ingest 后仍是 proposed；一条**不同**事件的支持证据进来后变为 active |
| 单条 A+ / 单条 A | 分别为 Medium / Low |
| 加入一条 A+ 反证 | 置信度下降，状态变为 contested |
| 14 个 run 无支持证据 | dormant；新证据进来后恢复 active |
| proposed 停留 10 个 run | retired，原因为"未获二次证据" |
| merge 之后 | source 不再出现在候选里，target 的派生证据包含 source 的全部证据且不重复 |
| attach 到候选集外的命题、且没写 override_reason | 整批 ingest 被拒绝，registry 文件不变 |
| new 时 rejected 没有覆盖全部候选 | 拒绝 |
| 召回打分 | 同叶子排在同二级域之前；merged/retired 不出现 |
| arXiv v1/v2、URL 带 query | 得到相同的 event_key |
| 写入时锁已被占用 | 超时报错，文件不变 |

和这次门禁迁移一样，每条规则都要做"故意破坏规则，测试应当变红"的变异检验。

---

## 13. 实施步骤

| 步骤 | 内容 | 产出 |
|---|---|---|
| 1 | registry v2 核心：数据模型、派生计算、召回、事务 ingest、report、存储与锁 | `thesis_registry.py`（重写）+ 单测 |
| 2 | `events.py normalize` 和 event schema | 替代两个临时脚本 |
| 3 | ontology 增加 `confidence_model`、v2 生命周期、`evidence_form` 枚举、命题粒度规则 | `thesis_ontology.json` |
| 4 | 门禁追溯层改造；SKILL 第 4、6 步和第 7 章写法更新；删除 v1 的 registry 文件 | `verify_gates.py`、SKILL.md |
| 5 | 用合成的 3 个 run（含窗口重叠、一条反证、一次合并）做端到端演练 | 演练记录 |

---

## 14. 已确认的决策

以下 5 项已于 2026-10-31 确认，均按建议执行。

| # | 问题 | 决策 |
|---|---|---|
| 1 | 单条 A 级证据的命题能否进入第 7 章？ | **不能。** 按 §6 模型执行：A 的强度分为 2，单条 A 证据的命题为 Low，需要第二条独立证据才能进入第 7 章；单条 A+ 为 Medium，可以当天进入 |
| 2 | B 级事件能否作为支持证据挂到已有命题上？ | **可以。** 强度只计 1 分，但计入跨实体、跨形态和持续性维度，作为"长期信号"的来源 |
| 3 | 命题范围能否停在二级域（如 B1）？ | **不能。** `scope_leaves` 必须是 1–3 个叶子，由 ingest 校验（§5.3） |
| 4 | 状态目录的默认位置 | **`$WORKDIR/state/`**。多个定时任务或多台机器共用一份 registry 时，用 `--state` 或环境变量 `TECH_BRIEFING_STATE` 指向同一个共享目录 |
| 5 | 置信度参数是否需要先校准 | **先按 §6 的数值上线。** 运行 2–3 周后根据第 7 章的实际表现调整；参数放在 ontology 的 `confidence_model` 里，调整不需要改代码 |
