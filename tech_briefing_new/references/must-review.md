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
