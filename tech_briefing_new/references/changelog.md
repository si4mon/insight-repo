# 变更记录（ADJUSTMENT_PLAN）

> 历史踩坑沉淀为永久约束。修改本 skill 的脚本或规则前先读；新增条目格式：`日期 + 问题 + 根因 + 约束`。

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

### 2026-10-31 起：task_def 与 SKILL.md 分工

- **问题**：两份文件各写一遍窗口规则、评级定义、Top N 规则、八章清单、8.3 字段，且互相矛盾：
  五路召回的 A–E 两边含义不同，又与代码里的源通道 `channel`（A_entity…G_official_surface）撞字母；
  8.3 根因在 SKILL 是"封闭集合"，在 task_def 是另一份清单；task_def 仍写旧文件名、旧章号、
  已不存在的 `thesis_map` / `source_registry`，§18 仍是 LLM 读 HTML 自证的旧验收。
- **约束**：task_def 只写"做什么、按什么标准判断"，SKILL.md 只写步骤、命令、路径、产物契约，
  同一规则只在一处，另一处以"task_def §N"引用。冲突时内容判断以 task_def 为准，结构契约、
  路径与门禁以 SKILL.md 和脚本为准。召回"机制"与源"通道"分开命名。

### 2026-10-31 起：补跑、渲染与门禁义务收口

- **问题**：registry 只接受最新 run，补采的历史窗口无法入库，漏跑的时段不在任何窗口里也无人发现；
  指令要求 mermaid 与图片可视化，但渲染器不支持 mermaid、也不内嵌本地图片，页面换位置图就断；
  渲染器按标题 slug 命名输出，`.md` 文件名稍有出入就"没有产出文件"；门禁按卡片自报的文字判断深拆
  义务（写 Convergence 或 B 就能豁免），8.2 评级用子串比对；第 7 章不写 TH 编号即可绕过、可以只挑
  部分核心判断；UNCOVERABLE 登记一次就永久豁免，10 个 Tier-1 实体长期失明无人补。
- **约束**：`ingest --backfill` 补跑、`gaps` 检测漏跑（门禁警告）；本地图片内嵌为 data URI、缺图渲染
  失败、远程图片门禁拒绝，渲染输出固定为与 `.md` 同名；深拆义务与卡片评级以事件 JSON 为准，8.2 评级
  精确匹配；第 7 章每条判断带 TH 编号且覆盖全部核心判断；UNCOVERABLE 必须写补偿方式、检索词与复探
  期限，过期 FAIL，整实体失明每天生成 `entity_blind` 补检任务。SKILL.md 只留步骤与契约，运行手册与
  变更记录移到 references/。


### 2026-11-01 起：跨模型方差收口（P0 / P1）

同一窗口（2026-10-30）用三个模型跑同一份 skill，产出差异远超预期：事件重叠只有 4 个，
一份报告把 OpenAI 融资缩水、Intel 暴跌、S&P 下调 Meta 评成 A/B，一份把 HN 上指向同一篇
分析的三个帖子当成多源共振，一份引用了 2024 年的 HN item id。对比分析见
`tech-briefing-多模型执行对比分析-2026-10-30.md`。按根因分成两组：

**P0（事实层会出错的）**

- **问题**：窗口在流水线里被反复重算，六小时扫描缓冲区算出来了却从未传给采集；三类时刻
  （提交 / 公告 / 刷新）混用，arXiv 论文按提交时刻归窗；HN 分页在 `pages_fetched` 上抛
  KeyError，1638 条被记成 TRANSPORT_FAIL，采集器自身的 bug 与源不可达混成一类；缺口任务
  只有"完成/未完成"两态，三个零结果结论是伪造的也能标完成；GitHub release 只走网页抓取，
  页面改版即失明；链接里的对象编号（HN item id、arXiv 编号）无人校验；统计手写，自报 15
  个事件而索引只有 14 行；没过门禁的 `.md` 一样能渲染出看起来成稿的 HTML。
- **约束**：窗口冻结进 `window.json`，一次冻结全程传参（`freeze_window.py`，门禁核对
  一致性且断言缓冲区生效）；三类时刻全部入库，归窗口径由 `FIRST_PUBLISH_RULE` 一张表决定；
  分页修复并引入 `INTERNAL_ERROR` 判定（带 `error_site`，要修代码不是换通道）；缺口四态
  （`confirmed_zero` / `found_items` / `still_blind` / `unknown`）+ 证据校验，零结果必须给出
  检索区间与最新条目时刻；GitHub 走 API 通道、arXiv 增加归档回退；新增链接身份校验；统计
  全部由 `report_stats.py` 派生并由门禁复算；门禁摘要落盘，渲染器拒绝渲染未过门禁的稿子。

**P1（判断层会发散的）**

- **问题**：候选池 2000+ 条，看哪些条目由模型自行决定，三份报告各自漏掉不同事件（Glance、
  Masked Erosion、Claude Code 2.1.314），且都没在丢弃日志里提过——不是判断分歧，是没进视野；
  评级由模型直接给，各自拿一把不同的尺子，非技术事件被影响面抬进 A；证据独立性按 URL 计，
  同一篇原文的多个转帖算成多源共振；跨实体收敛里两篇不同团队的论文算成两个实体
  （TH-0002 由此拿到 Medium）；战略相关度没有可证伪的依据；A 级 claim 只要求快照存在，
  抓了原文仍可凭印象写机制；第 1 章主线可以不引用任何事件。
- **约束**：分层必审清单（`must_review.py` + `review_terms.json`，清单内逐条留痕，清单外
  统计留痕；有价值论文落在前 K 外时补词表不抬 K）；五维评分 0–2 并附证据，评级由
  `scoring.py` 派生，非技术类事件硬上限 C/B，锚例固定在 `rating-anchors.md`，Top N 次序由
  成对比较决定；独立首发源按域归并（聚合源不计、HF Papers 折叠到 arXiv）；跨实体收敛要求
  独立组织，论文类集体证据只占一个实体位；战略相关度只按根技术清单的切换信号计分
  （`root_tech.json` + `root-tech-scoring.md`，否证与支持同分）；A/A+ 的每条 claim 绑定
  `{snapshot, snapshot_sha256, quote}` 并逐条比对；第 1 章每条主线至少引用 2 个评级不低于
  B 的 EV。
- **一处与建议不同**：对比报告建议给 `forms_bonus` 加同类型半权折减。实现时发现 `forms`
  本就按去重后的 `evidence_form` 计，第二条同类型证据的贡献已经是 0，比半权更严。所以折减
  落在实体独立性上，没有另加系数——照建议改反而会放宽。
