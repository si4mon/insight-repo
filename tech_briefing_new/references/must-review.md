# 必审清单（分层留痕）

> 对应对比报告第 8 节第 10 条。脚本 `assets/must_review.py`，词表 `data/review_terms.json`，
> 门禁 `verify_gates.py::check_must_review`。

## 1 要解决的问题

2026-10-30 同一窗口三份报告的漏检互不重叠：

| 事件 | A 报告 | B 报告 | C 报告 |
|---|---|---|---|
| Glance（生成骨干兼任重排器） | 漏 | 漏 | 入选 A |
| Masked Erosion（验收门侵蚀防护冗余） | 漏 | 入选 A | 漏 |
| Claude Code 2.1.314 目录边界 | 漏 | 漏 | 入选 A |
| VeriCUA / Prefix Executability | 漏 | 漏 | 入选 A |

这些不是价值判断分歧——三份报告都没在丢弃日志里提到它们，说明根本没进视野。
只要"看哪些条目"由模型自行决定，同一把尺子也量不出同样的结果。

候选池一轮 2000+ 条，逐条台账不可执行。折中是分层：

- **清单内**：强制逐条留痕，必须有处置与理由；
- **清单外**：按池筛规则统计留痕，不要求逐条。

清单只决定"要不要留痕"，**不决定评级**，也不做价值判断。清单外的条目仍可评 A。

## 2 分层规则

| 层 | 范围 | 理由 |
|---|---|---|
| T1_official | `A_entity` + `G_official_surface` 的窗口内条目 | 官方首发面，量小，漏一条就是硬漏检 |
| T2_hf_papers | `hf_daily_papers` 全部 | 人工策划的当日论文榜，信噪比最高 |
| T3_hn | HN 条目，`points ≥ 50` 且命中论域词 | 分数是社区注意力的现成代理 |
| T4_techmeme | Techmeme 条目命中论域词 | 聚合源，条数可控 |
| T5_cn_media | `F_cn_media` 命中论域词 | 中文首发常不进英文源 |
| T6_arxiv | arXiv 按打分前 K（默认 40） | 日公告千篇级，只能取头部 |

趋势榜单源（`hf_trending_models`、`gh_trending`）不入清单：同一批条目连日在场，
进清单只会每天重复一遍同样的处置。

无日期条目只在 `freshness == new_since_last_run` 时入清单。

## 3 arXiv 打分

`high` 词 2 分，`med` 词 1 分，`announce_type == "new"` 再 1 分，取前 K。
分值只用于排序，不进评级。

**词表是被维护的那一份。** 回测里 Masked Erosion 只得 4 分、落在 K 外，原因是
词表里缺防护机制的词汇（`safeguard`/`guardrail`/`redundan`/`acceptance gate`/
`erosion`…），而简报第 4.6 章整章讲防护机制。补词表后它得 12 分、进前 40。

所以：**有价值的论文落在 K 外时，补词表，不抬 K。** 抬 K 只是让人多读无关论文，
而漏掉的那一类仍然漏掉。每次补词要在第 6 节记一行。

## 4 逐条留痕

清单上百条不适合全塞进 8.3——那一节是给人读的摘录，范围仍按 task_def 保持
"Tier-1 来源条目与共振命中条目"。完整台账落在 `must_review_trace.json`：

```jsonc
{"dispositions": {
  "<uid>": {"disposition": "selected", "ev": "EV-03", "reason": ""},
  "<uid>": {"disposition": "discarded", "ev": "", "reason": "技术命题未发生变化"}
}}
```

`disposition` 封闭集合：

| 取值 | 含义 | 必填 |
|---|---|---|
| `selected` | 入选为独立事件 | `ev` |
| `merged` | 并入其他事件 | `ev` |
| `chapter5` | 写入第 5 章（Active Event / Early Signal / 线索） | `reason` 写明归属 |
| `discarded` | 丢弃 | `reason` 取 task_def 8.3 的十项封闭集合 |

## 5 门禁

| 检查 | 失败条件 |
|---|---|
| 必审清单已生成 | 没有 `must_review.json` |
| 必审清单逐条留痕 | 清单内任一 uid 在台账里没填 |
| 处置取值合法 | `disposition` 不在封闭集合内 |
| 入选/并入指向存在的 EV | `ev` 不是 `EV-\d+`，或该 EV JSON 不存在 |
| 丢弃理由取自封闭集合 | `reason` 自造；或 `chapter5` 未写归属 |
| 台账与事件产物不矛盾 | 条目链接已出现在某个 EV 里，台账却记丢弃 |

最后一条是反向核对：它抓的是"事件确实写了，台账说丢弃"这种填错，而不是漏检。

## 6 阈值与词表变更记录

| 日期 | 变更 | 原因 |
|---|---|---|
| 2026-10-31 | 建表：`HN_MIN_POINTS=50`、`ARXIV_TOP_K=40` | 2026-10-31 实测池 2323 条 → 清单 121 条，人工可执行 |
| 2026-10-31 | `arxiv_score.high` 补防护机制词 17 个 | Masked Erosion 落在 K 外，缺的是词表不是 K |
| 2026-11-02 | `ai_relevance.zh` 补 8 个词（开源、开放、基准测试、推理模型、决策模型、世界模型、形式化、注入攻击），并去掉重复的「智能体」 | 量子位「Jev新成果，再次引爆开源」未命中词表——表里只有「开源权重」没有「开源」，而该条目最终入选为事件 |

## 2026-11-09 词表按业务优先级重排

### 为什么改

五轮产出复盘发现 high 层（权重 2）的主题配比与业务优先级倒挂：

| | 改前 high 层 | 业务优先级目标 |
|---|---|---|
| tier-1 模型 / harness+RSI+工具治理 / 个性化记忆 | 其中记忆仅 1 词（`memory`） | ~54% |
| tier-2 agent infra | 4 词（kv cache / kv-cache / speculative / sandbox） | ~33% |
| tier-3 AgentOS / agent 安全 | **39 词** | ~13% |

直接后果：个性化记忆的六条根技术（U1–U6：个人数据语义层、记忆形成与巩固、记忆形态与放置、
多模态情景记忆、记忆调用策略、记忆治理）五轮一共只被命中 1 次；agent infra 类（I1–I4）0.14 倍覆盖。
召回面上没有这两条线，评分再公平也评不出来。

### 改了什么

- 补 tier-1 个性化记忆 20 词：episodic memory、memory consolidat、consolidat、personaliz、
  user model、user profil、preference learning、preference model、forgetting、
  catastrophic forget、retention、memory governance、memory retrieval、semantic layer、
  long-term memory、lifelong、continual learning、knowledge editing、model editing、
  machine unlearning。另把原先归在安全词里的 `unlearn` 认定为记忆治理（U6「删除可验证」）。
- 补 tier-1 harness / RSI / 工具治理 19 词：harness、task state、context compression、
  context management、delegation、skill selection、skill librar、tool schema、tool selection、
  mcp、checkpoint、recovery、replay、trajectory、scaffold、self-refine、curriculum、
  meta-learning、agent workflow。
- 补 tier-2 infra 17 词：disaggregat、prefill、decode、serving、scheduling、scheduler、
  batching、offload、cache hit、paged attention、tensor parallel、expert parallel、async rl、
  asynchronous rl、inference system、edge-cloud、端云。
- 把 19 个通用安全泛词从 high 降到 med：verif、fact-check、audit、monitor、safeguard、
  guardrail、defense、defence、robustness、degrad、erosion、redundan、acceptance gate、
  mitigation、refusal、attack surface、containment、oversight、poison。
  **保留**具体的攻击与失配机制词在 high：prompt injection、jailbreak、backdoor、data poison、
  reward hack、sandbag、collusion、steganograph、subliminal、membership inference。
  依据是命中面宽窄，不是立场——`monitor` 几乎任何论文都能命中，`sandbag` 只命中一类工作。

high 75 → 112 词，med 41 → 60 词。

### 回测（五轮历史候选池，旧词表 vs 新词表）

| 窗口 | 截断分 旧→新 | 记忆类入选 旧→新 | infra 类入选 旧→新 |
|---|---|---|---|
| 11-01 | 6 → 6 | 7 → 10 | 0 → 2 |
| 11-02 | 6 → 6 | 7 → 10 | 0 → 2 |
| 11-03 | 15 → 17 | 3 → 8 | 4 → 8 |
| 11-05 | 7 → 8 | 7 → 12 | 4 → 5 |

已入选事件的回归：1 处，且确认是并列档边界而非被挤出——`2610.37657`（EV-05，B 级，
prompt injection 防御）得 6 分、截断正好 6 分，`cut_inside_tie` 已自动报警；
`--arxiv-top-k 48` 取整档后回到清单内。

### 中途踩的坑：子串连锁升降

第一版把 `benchmark` / `evaluation` / `eval` 一起从 high 降到 med，回测立刻挤出三个已入选事件
（含两个 A 级）。原因有两层：一是 `eval` 是 `evaluation` 的子串，三词会连锁命中，整组降级
一次损失 3 分；二是分类错了——评测属于 M6「学习信号」与 D1，是 tier-1，不是通用安全泛词。
已全部恢复到 high。

**同类风险的词组**（升降必须整组评估，不能逐个拍）：`eval`/`evaluation`、
`defense`/`defence`、`red team`/`red-team`、`poison`/`data poison`、`supply chain`/`supply-chain`、
`tool use`/`tool-use`、`computer use`/`computer-use`、`kv cache`/`kv-cache`、
`weight space`/`weight-space`。

### 没动的部分

评级公式未改。业务优先级不进评分维度——否则一个 9 分 / 机制新颖度 2 / 战略相关度 2 的
安全类事件会被制度性压到 A，而这正是要避免的。优先级只进召回与排序。

### 2026-11-09 补记：business_tier 标签已确认落盘

82 条根技术逐条打上 `business_tier`（1/2/3），落在 `data/root_tech.json`。
分布：tier-1 43 条（52.4%）、tier-2 27 条（32.9%）、tier-3 12 条（14.6%）。

5 处交叉项由用户逐条裁定，带 `tier_note` 记下理由，**不要按组重算**：

| 条目 | 组 | tier | 裁定 |
|---|---|---|---|
| S2.2 智能体供应链语义安全 | S2 智能体生态信任 | 3 | 供应链语义安全属安全议题，治理对象是上游发布方 |
| S2.3 端侧第三方智能体操作治理 | S2 智能体生态信任 | 1 | 治理在自家设备上运行的第三方智能体，属 harness engineering |
| S2.4 可追责执行记录 | S2 智能体生态信任 | 2 | 落在 D2.1/D3.4，更像 infra 的可观测底账 |
| S4.4 自演化机制进入产品 | S4 可观测与可控 | 1 | RSI 的切换信号本体 |
| S4.5 可解释性定位指导训练修复 | S4 可观测与可控 | 1 | 偏模型内部理解 |

**S2 组横跨三个 tier 是裁定结果，不是漏改。** 关键区分：「工具治理」指治理在本机运行的
第三方智能体（S2.3，tier-1），不是审计上游供应链（S2.2，tier-3）。
`test_root_tech_tier.py` 守这五条，以及「每条都有合法 tier」与「tier 不参与评分」的注记。

本次只打标签，没有任何代码读取 `business_tier`，行为零变化（已 grep 确认）。

### 词表重排后，按确认 tier 重算的差距

| | 清单占比 | 五轮实际命中 | 倾斜 |
|---|---|---|---|
| tier-1 | 52.4% | 54.5% | 1.04×（达标） |
| tier-2 agent infra | 32.9% | 16.9% | **0.51×** |
| tier-3 | 14.6% | 28.6% | **1.95×** |

按事件计：tier-1 38 个、tier-2 7 个、tier-3 16 个、无根技术命中 14 个。
tier-2 仍是半饥饿状态——词表已补 22 个 infra 词，但词表只管召回面，
名额仍由单一 top-K 分配，tier-2 的候选会和 tier-1 抢同一批名额。
这是「must_review 加 tier 配额」要解决的问题，待批准。

### 2026-11-09 再修正：召回端只做加法，19 个安全词恢复 high

用户明确：tier 只影响 Top N 的呈现次序，不是要降低技术事件的价值；高价值的 infra 与
安全类技术点依然需要优先呈现。

据此回测第一版的副作用，结果支持这个要求：把 19 个通用安全泛词从 high 降到 med 后，
**安全类条目的入选数四轮合计从 34 掉到 24（-29%），其中 11-03 一轮从 11 腰斩到 5**。
召回不到就无从优先呈现，所以全部恢复到 high。

恢复后的回测（旧词表 → 现词表）：

| 窗口 | 截断分 | 安全类 | 记忆类 | infra 类 |
|---|---|---|---|---|
| 11-01 | 6 → 7 | 9 → 9 | 6 → 9 | 0 → 2 |
| 11-02 | 6 → 7 | 9 → 9 | 6 → 9 | 0 → 2 |
| 11-03 | 15 → 18 | 11 → 9 | 3 → 5 | 4 → 8 |
| 11-05 | 7 → 8 | 5 → 4 | 6 → 9 | 4 → 5 |
| **合计** | | **34 → 31** | **21 → 32** | **8 → 17** |

已入选事件回归：**0 处**（第一版那 1 处边界回归也随之消失）。
安全类剩下的 -9% 是名额被挤占的结果（清单仍是 top-40），不是权重下调。

**定下来的原则：词表只做加法。** 词表管的是「能不能被看见」，看不见就无从呈现；
主题配比不平衡要靠补齐缺失的线来纠，不靠压低已有的线。high 131 词 / med 41 词。

---

## 2026-11-10 补主动性线（proactivity）

### 为什么改

补之前的词表（high 131 / med 41）里主动性相关词是 **0**。拿六篇核心文献的真实摘要
（export.arxiv.org 返回，不是复述）回测，旧词表给的分是：

| 文献 | 旧分 | 新分 | 新增命中 |
|---|---|---|---|
| 立场论文 2605.06717（autonomy vs proactivity） | 7 | 15 | proactiv, interrupt, insight policy, unsolicited |
| ProAgentBench 2602.04482（28,528 真实事件） | 14 | 20 | proactiv, anticipat, intervention, assistance |
| PARE Bench 2604.00842（Proposal Rate） | 8 | 15 | proactiv, intervention timing, anticipat |
| Proactive Agent 2410.12361 | **6** | 11 | proactiv, anticipat, assistance |
| UniClawBench 2607.08768 | 16 | 18 | proactiv |
| KnowU-Bench 2604.08455 | 21 | 28 | proactiv, when to intervene, intervention, silent |

各轮实际截断线是 7 / 7 / 8 / 18。2410.12361 原本 6 分，**连最低的 7 分线都到不了**，
整条看不见；其余几篇全靠 agent、eval、benchmark 这些通用词擦边过线，等于主动性这个
维度对打分器完全不存在。

遗留的限制要说清楚：立场论文补词后 15 分，仍过不了重日的 18 分线。它是观点类文献、
没有定量结果，光靠词表救不回来——这条要靠 `evidence_form: expert` 那条通路，不是打分。

### 改了什么

纯加法，不动任何已有词的层级。high 131 → 155，med 41 → 52。

- **high（24 个）**：proactiv、interrupt、missed opportunity、alert fatigue、notif、
  attention budget、when to assist、when to intervene、intervention timing、opportune、
  opportunity detection、silence、insight policy、situational、situation-aware、
  proposal rate、unsolicited、ambient agent、personal agent、personal assistant、
  information overload、triage、anticipat、timeliness。
  定层依据：在 4600 条 arXiv 语料上实测命中率 0.00%–0.67%，与现有 high 层的中位数
  0.24% 同量级（现有 high 里本就有 10 个词命中率为 0.00%）。`proactiv` 只命中 9 条。
- **med（11 个）**：intervention（2.70%，多为因果推断/医学干预）、salien（多为
  saliency map）、assistance、assistive、silent（会命中 silent failure）、
  follow-up、digest、ambient、dismiss、inbox、reminder。
- **ai_relevance**：en +9、zh +11（个人助理、主动提醒、主动服务、主动性、信息过滤、
  事务管理、待办、通知、个人智能体、记忆 等）。这张表的口径是「宁宽勿窄」，中文
  personal agent 类产品报道（蚂蚁灵光一类）此前在这里完全没有钩子。

子串连锁按 11-09 那次的教训逐条去重：只留 `interrupt`（覆盖 interruption /
interruption cost）、只留 `notif`（覆盖 notification(s)）、`silence` 不配 `silent`。
`test_review_terms_proactivity.py` 里有一条测试专门锁这个。

### 踩的坑：固定名额让「只做加法」在选择层失效

词表只做加法，但清单是 `ARXIV_TOP_K` 固定名额，所以新词必然挤掉同等数量的原有条目。
五轮回测：

| 轮次 | 池 | 截断线 | K=40 丢失 | K=44 丢失 | K=48 丢失 |
|---|---|---|---|---|---|
| 11-02 | 1874 | 7 | 2 | 0 | 0 |
| 11-03 | 2186 | 7 | 2 | 0 | 0 |
| test | 4398 | 18 | 6 | 4 | 0 |
| 11-06 | 2856 | 8 | 1 | 0 | 0 |
| 合计 | | | **11** | 4 | **0** |

被挤掉的 11 条里有 **两条是已发布事件**：11-02 简报的 Sparse Text Diffusion、
11-05 简报的 ScamWorld。这是真回归，不是无害置换。所以 `ARXIV_TOP_K` 由 40 提到 **48**
（让五轮归零的最小值），代价是必审清单涨 5~8%（472 → 504 条）。

顺带的收益：上一节记的「安全类 -9% 是名额被挤占的结果（清单仍是 top-40）」也随之缓解，
同词表下安全类条目 24 → 27。

**补充到原则里**：召回端只做加法，而且**加词必须连带复核 K**——词表是加法，名额不是。

### 新词在历史池里的实际收获

四轮池里命中主动性词的条目只有 5 条，K=40 和 K=48 都是 5 条。这不是改动无效，而是
这个方向在日更量里本就稀薄（4600 条里 `proactiv` 仅 9 条）。改动的价值在六篇已知文献
的分数上（见上表），以及以后此类条目不再因为 0 命中而沉底，不在历史池的条目数上。
