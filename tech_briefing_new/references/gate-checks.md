# 门禁检查项（verify_gates.py）

> SKILL.md 步骤 6 的参考：门禁逐层检查什么、以什么为分母。门禁只校验事实与结构，不校验排版。

| 层 | 检查项 |
|---|---|
| collection | 源读取成功、窗口内有条目、无阻断缺口、critical 源可用、补检任务清零（含 `window_partial` 与 `entity_blind`）、无 critical 源窗口覆盖不完整 |
| coverage | Tier-1 实体都有源侧映射；每个必查实体×面有源或已登记不可达；不可达登记写明补偿方式、检索词与复探期限，且未过期（过期即 FAIL，强制重新探测）；Tier-1 实体本轮均被尝试采集 |
| taxonomy | 分类定义完整：54 叶子 / 11 栏目 / 8 章，叶子↔栏目双向一致、无重复收录 |
| taxonomy | 每个事件有 `primary_path` 且可解析；`A1`/`B1`/`C3` 已下钻到三级；`related_domains` ≤2；`change_object` 合法；4.6 事件的 `annotation` 与 `primary_path` 一致 |
| taxonomy | MD 栏目编号（`### N.M`）均属 11 个栏目；唯一主卡（含章 2 声明归属的主卡）；主卡落在 `primary_path` 对应栏目，A/A+ 必须有主卡；出现 `###` 的栏目不得无卡；`归属 N.M` 合法且每栏最多折 1 条；4.6 卡片写具体技术域 |
| md | 文件非空、frontmatter title/date、八章 `##` 按顺序齐全、8.1/8.2/8.3 存在、来源链接 ≥10、正文与文件名含 WINDOW_START_DATE、窗口截断源已披露 |
| md | A/A+ 主卡四节深拆：**义务由事件 JSON 决定**（A/A+ 的主卡必须写；聚合卡与首发早于窗口的 Active Event 豁免），不看卡片自报的文字；卡片标记里的评级必须等于事件 JSON；图片必须是本地文件（渲染时内嵌） |
| md | 8.2 无晚于 WINDOW_END 的新事件；早于 WINDOW_START 的那一行标为 Active/Historical |
| trace | 每个事件已规范化（有 `event_key`）；A/A+ 有 `claims` |
| trace | 8.2 每个 EV 编号都有 `EV-xx.json`，每个 JSON 都在 8.2 出现；JSON 首发落在窗口内；8.2 行的评级是独立的评级记号（精确匹配，不是子串）；8.2 时刻等于 JSON 的 `first_publish_shanghai`（分钟粒度） |
| registry | 本轮已入库，入库事件与 events 目录一致；A/A+ 的 `thesis_candidates` 等于工具重算结果；A/A+ 有 attach/new 裁决且已写入 registry；存在漏跑窗口时给出警告 |
| registry | 第 7 章：每条判断（列表项）都写 TH 编号，整章无编号时必须写明"本轮无核心技术判断"；覆盖 registry 报告中全部核心判断；引用的命题存在、为 active/contested 且非 Low、置信度与 registry 一致、contested 写出反证 |

**trace 层以 8.2 声明的编号为分母**：缺 JSON 直接 FAIL。8.2 的时刻必须能被 `EV-*.json` 证实——
门禁校验事实源，不是表格里手填的日期；两者不一致时以 JSON 为准。`check_md_event_index`
直接解析 `### 8.2` 下的 Markdown 表格行。
