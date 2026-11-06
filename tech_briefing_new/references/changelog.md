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

### 2026-11-02 起：连续运行暴露的六处缺陷

2026-10-31 与 2026-11-01 两个窗口各跑了一轮完整简报，第三轮（2026-11-01 窗口）同时作为稳定性观测。三轮下来，人工介入点里属于代码缺陷的有六处，全部修掉：

- **GitHub 发布面连续两轮全部失明。** `releases.atom` 与 `api.github.com` 在有出网网关的环境里被一并 403，10 个代码面源全部 TRANSPORT_FAIL，而它们覆盖的正是每天发版的面（Claude Code、OpenAI SDK、qwen-code）。两轮都靠手工用 `git ls-remote` 补。**约束**：匿名 git 作为第三通道收进采集器（`git_tags.py` + 源侧 `git_fallback` + 判定 `OK_FROM_GIT_TAGS`，与正常采集区分，因为时刻是 tag 提交时刻而非 release 发布时刻）。效果：TRANSPORT_FAIL 10 → 0，阻断缺口 4 → 0，并补回三条此前完全不可见的窗口内发布。
- **`qwen_code` 指向模型仓。** 原登记 `QwenLM/Qwen3` 没有 release tag，三条通道都只能回答「没有」——这个面长期是个假的零结果。**约束**：改指 `QwenLM/qwen-code`；新增源时要确认该仓库确实发 release。
- **git 回退返回「仓库没有 tag」被判成传输失败。** 会造出假的阻断缺口。**约束**：`empty` 结果记 `structure_ok=True`，按结构正常 0 条处理。
- **同一篇 arXiv 论文有两个身份。** RSS 路径哈希 URL、归档页路径用裸 id，于是跨分类的论文在必审清单里各出现两次，台账要为同一篇填两次处置；更糟的是前 40 名被重复项占掉名额，实际只有 33 篇。**约束**：`make_uid` 对 arXiv URL 按 `arxiv:<id>` 规范化（去版本号）；必审清单先去重再取前 K。
- **所有以 HN 为来源的事件会撞成同一个 `event_key`。** `canonical_source` 丢掉 query，而 HN 的条目身份全在 `item?id=N` 里，两个无关事件被入库校验判成同一事件。**约束**：加 `hn:<id>` 规范化。
- **补检任务 ID 是位置号。** 缺口集合一变，编号全体平移，而 `--mark-done` 按 ID 结案——实测 11 条结案记录落到了错误的任务上。**约束**：ID 改为 `GAP-<类型首字母><type+实体+面的短哈希>`，跨 run 稳定；原序号保留在 `seq` 字段里供阅读。

另有两处不是缺陷但记下来：`report_stats.py` 的「Early Signal Signal」重复后缀已修；论域词表缺「开源」导致一条最终入选的事件没进必审清单，已补 8 个中文词（规则是补词表不抬阈值，见 `must-review.md`）。

**仍未解决的设计缺口**：registry 没有「向已有事件追加增量」的通道。同一事件的机制在后续窗口被披露时（如 Anthropic 用途边界：第一轮是用户报告、第二轮是系统提示机制），两者来源 URL 不同，于是被记成两条独立事件，入库只给「疑似同一事件」警告。

## 2026-11-03（第四轮运行发现的六处缺陷）

本轮运行 2026-11-02 窗口时发现并修掉六处缺陷，全部带回归测试（测试总数 311 → 317）。

1. **`verify_gates.check_publish_precision`：arXiv 的 `replace` / `replace-cross` 不当作窗口内首发。**
   重新公告的时刻确实落在窗口里，所以旧门禁的 `first_publish ∈ [WS, WE]` 查不出来。现在
   `announce_type ∈ {replace, replace-cross}` 的事件必须在 `date_semantics` /
   `date_precision_note` / `signal` 里标成 Active Event / 历史 / 增量 / 不计入本轮，否则门禁不过。
   回测：2026-11-01 的报告有两条（Heads of Security、EvoMemBench）本该被拦。

2. **`events.normalize`：`change_object` 按封闭集合校验。**
   此前不校验，而 `report_stats` 只按 `("Model", "Harness", "运行平台", "交互·应用", "尚未披露")`
   计数——写别的值不报错，只会从 dashboard 统计里静默消失（门禁用同一脚本复算，也查不出来）。
   `events.CHANGE_OBJECTS` 与 `report_stats.CHANGE_OBJECTS` 由测试断言保持一致。

3. **`verify_gates.check_ct_labels`：正文里 CT 编号后的中文标签必须等于词表里的名字。**
   `normalize` 只校验 CT 的 ID，标签是正文手写的。2026-11-01 的报告把 CT-02 写成「机制变化」、
   CT-03 写成「核验方式变化」、CT-05 写成「效率/成本结构变化」、CT-06 写成「评测与度量变化」，
   那是另一套早期词表；当轮 92 项门禁全过，错标签照样发了出去。连词（与/和/及…）与单字片段
   不当标签看。

4. **`thesis_registry._is_placeholder_entity`：占位实体不触发「疑似同一事件」。**
   两篇不同作者团队的 arXiv 论文都写 `entity="学术界"`，同叶子、同一个公告批次就会互相告警。
   11-02 与 11-03 两轮各出现两条假阳性，每条都要人工排除。占位判定允许带括号后缀
   （「学术界（OLMo-Twin，代码已公开）」）。真实组织不受影响。

5. **`gap_tasks`：window_partial 的验收区间归一到 Asia/Shanghai。**
   `covered_from` 带源自己的时区，旧实现直接截前 16 字符，于是 arXiv 的
   `2026-11-02T00:00:00-05:00`（= 上海 13:00）被写成「窗口起点 至 2026-11-02T00:00」——
   而窗口起点正是 2026-11-02 00:00 (+08:00)，13 小时的盲区读起来像空区间。

6. **`gap_tasks.validate_resolution`：window_partial 的 `confirmed_zero` 按未覆盖时段判。**
   旧校验要求 `latest_item_time < WINDOW_START`。arXiv 整个窗口当然有条目（每工作日美东
   00:00 一批），但未覆盖的那段里不可能有，于是这类缺口永远结不了案，只能天天挂一条
   `partial_compensated`。现在 `window_partial` 需要新的 `range_end` 证据字段
   （CLI `--range-end`，一般取该源的 `covered_from`），并按它判定。
   entity_blind / surface_blind 的规则不变。

7. **`report_engine/render.mjs`：首字下沉只给章标题后紧挨着的那一段。**
   `lastHeadingLevel` 不被段落重置，所以章内任意一段只要以拉丁字母开头就会被选中
   （「Early Signal（…）」「Model–Harness 边界：…」在简报里很常见）。**连续四轮手工
   规避同一处**：前三轮都是把中文挪到段首。

## 2026-11-04（第五轮运行发现的五处缺陷）

本轮跑 2026-11-03 窗口时挖出五处缺陷，其中四处会导致漏采或误判，且都不是本轮新引入的——
触发点是一个没有被当成偶发放过的 PARSE_FAILED。全部带回归测试（测试总数 317 → 335）。

1. **`collect_sources._maybe_decompress`：按首字节魔数判断 gzip，不信 `content-encoding` 头。**
   `deepmind.google/blog/rss.xml` 的响应体是 gzip，而该头在到达采集器前被出网代理改掉了，
   于是 gzip 字节被当文本落盘，`extract.classify` 判「内容形态与声明模式不符」。压不压由代理
   当时的协商决定，所以它表现得像偶发故障：11-01 判 PARSE_FAILED、11-02 正常、11-04 又失败，
   前两次都被记成传输层偶发。失败的那几轮 Google DeepMind 的 blog 面实际是失明的。

2. **`git_tags._to_utc`：把 `%cI` 归一到 UTC 再写入原始文件。**
   git 的 `%cI` 带的是**提交者本地**时区偏移，同一次采集里会同时出现 `+00:00` / `+08:00` / `-07:00`。
   原始文件混着多种偏移，读的人很容易再按 +08 换一次——2026-11-02 那份简报就把
   qwen-code v0.26.6 的 11-03 01:51 写成 09:51，同仓 nightly 的 06:04 写成 14:04。

3. **`collect_sources._truncated_before_window`：归档回退的第二个触发条件。**
   旧条件只在主通道 0 条时读归档页，而 arXiv 的 RSS 只带最近一个公告批次。窗口跨两个公告日时，
   较早那一整批一条都不会进池子（2026-11-03 窗口漏掉 1,294 篇）。`window_partial` 缺口报了出来，
   但补偿从未发生。新条件：主通道最早一条比 WINDOW_START 晚 `on_truncation_hours`（默认 12）小时以上
   也触发，阈值的意思是「够装下一整个发布批次」。

4. **`extract._extract_arxiv_listing`：`url` / `title` 在 make_uid 之前求值。**
   两者原先只在 dict 字面量里算出来，而 `make_uid` 在同一字面量里就引用了它们：第一条即 NameError，
   整个函数 parse_failed。**归档回退自 2026-11-02 引入 make_uid 起从未产出过一条**，而当轮的 8.1
   还写了「自动改读归档页补回批次」——那句话当时就是错的。教训：报告里写某个机制起了作用时，
   要引用它产出的条数，不要引用它被调用了。

5. **`collect_sources`：归档回退与主通道合并，不顶掉。**
   归档页不带摘要，主通道的 RSS 带。第 3 条修好后当天那一批论文的摘要全部消失，而
   `must_review.arxiv_score` 打的是标题加摘要，于是 T6 排序被标题关键词密度主导。改为归档条目在前、
   主通道条目按 uid 覆盖。

### 同轮的词表与口径调整（非缺陷）

- `data/review_terms.json` 的 `arxiv_score` 补了 19 个 high 与 13 个 med 词
  （interpretab / collusion / membership inference / state tracking / linear attention /
  weight-space / subliminal / recurrent / provenance / unlearn 等）。回测动机见该文件的 `_doc`。
- T6 的截断改为「不在并列分数档内部切刀」：68 篇得分 ≥6 时取前 40，等于在 6 分档内随机取舍。
  本轮用 `--arxiv-top-k 68` 取整档，清单 155 → 183 条。

### 本轮新记录的两处待办

- **`arxiv_score` 对没有摘要的条目系统性低估**：归档页来源的条目没有摘要，而打分用标题加摘要。
  要么为归档条目补抓摘要，要么把打分按「有无摘要」分层。
- **门禁不检查「栏目章里每个非 Active 的 EV 都有一张卡」**：`check_md_event_index` 只核 8.2 索引与
  EV JSON 的对应，2026-11-03 一轮漏写了一张 C 级卡而门禁没发现。

## 2026-11-06（批次覆盖的"今天还没公告"误报）

- **`coverage._batch_coverage`：公告时刻未到的那一天不计为缺批次。**
  旧实现要求窗口内每个工作日都有该源的一个批次，而 arXiv 每个工作日在固定时刻公告一批
  （归一到上海约 12:00）。2026-11-05 窗口于上海 09:44 执行，11-06 这个工作日的批次还没发，
  于是五个 arXiv 源全部被判 `covered_quality: partial`，凭空生出五条无事可做的补检任务
  （`action_gaps` 16 → 应有 11）。现在按该源已有批次条目的时钟推算公告时刻，晚于窗口终点就跳过；
  取不到时钟按 12:00 兜底，周末照旧不要求。修完 `window_partial_sources` 从 6 降到 1。
  回归测试 4 个（`BatchNotYetDueTest`）。

### 本轮记录的流程教训（非代码）

- **重跑采集会重写快照，已绑定的 claim 必须重新校验。** 2026-11-05 一轮里，EV-04 的两条引文建卡时
  指向 `arxiv_cs_CL.xml`，修完覆盖缺陷后重跑采集，该文件的 RSS 已滚到新批次，引文校验报
  「这句话不是从原文来的」。实际原因是快照被重写而非引文造假（该摘要在 `arxiv_cs_AI.xml` 里）。
  claim_evidence 的 sha256 校验在这里起了作用——它准确地说出"快照变了"，但报错措辞会让人误以为是引文问题。
- **`openai.com` 不可达不代表 OpenAI 的文档不可达。** 连续四轮 openai.com 返回 403，而本轮第一次
  分主机试过：`developers.openai.com` 与 `platform.openai.com` 都可达，GPT-6 Cyber 的规格、价格与
  Daybreak 访问机制全部从这两个主机的 `.md` 文档取到。下次遇到某个域不可达，先按主机拆开试。
- **`thesis_registry gaps` 只在下一轮启动时报漏跑。** 2026-11-04 整个窗口没跑过，这件事直到
  11-06 启动时才被报出来，而当天的官方发布与社区讨论已经滚出各源的 feed、不可追回
  （arXiv 侧因为归档页还能补）。

## 2026-11-06（四轮复盘后批准的六项：P0-2/3/4、P1-5/6/8）

复盘文档列了 14 个问题，这一批只动其中六项。另议的两项（窗口首尾相接、第 5 章上限等）
按"每天自动跑 + 失败后用 `freeze_window.py --date` 手工补指定日期"处理，不改代码。

### P0-4 门禁不检查「事件在正文里有没有落点」

- **问题**：2026-11-03 一轮，一个 C 级事件在 8.2 索引里有行、有 EV JSON、两边编号对得上、
  门禁 94 项全过，正文里一个字都没有。
- **根因**：`check_md_event_index` 核的是索引与 JSON 的双向对应，`_check_md_columns` 的
  主卡归位只对 A / A+ 强制（B 级及以下允许只出现在第 5 章，这是规定写法）。而"是否
  真的出现在第 5 章"没有任何检查项以它为对象。索引对账只能证明"编号两边都有"，
  证明不了"这个事件被写过"。
- **约束**：新增 `check_event_body_presence`。正向要求每个 EV 的编号在第 1–7 章出现过，
  反向要求正文卡片都有对应的 EV JSON。
- **第一版自己踩了"永远绿"**：按章标题文字找 "8" 来切审计章，而第 8 章标题写的是
  「信息源采集统计」，没命中就退回全文，8.2 索引表把检查喂成了恒绿——在真实报告上
  "通过"了。改为按固定八章位置取第 8 个二级标题，`8.x` 下级标题兜底，两条都落空就打红。
  剔除法回测确认：把 2026-11-03 报告里承载 EV-09 的小节删掉，门禁精确报出
  「EV-09（C 级）只在审计章出现」；另三份历史稿不误报。

### P1-6 git 通道的 CHANGELOG 从未落盘

- **问题**：git 第三通道产出的事件连续三轮卡在 B 级。openai-python / openai-node 同分钟
  配对发布跨两个窗口出现，只能描述成"节奏"。
- **根因**：`git_tags.py` 的文档写着第 3 步"由采集器按 `git_fallback.changelog` 顺带落盘"，
  但采集器里从来没有这段实现——`git_fallback` 在 `collect_sources.py` 里只用于写 tag 条目。
  拿得到"发了哪个版本、什么时刻"，拿不到"改了什么"的可引证原文，而 A / A+ 要求 claim
  绑定到快照原文（task_def 15.1）。
- **约束**：不走 `raw.githubusercontent.com`（和 atom / API 一样会被拦），而是利用 tag 浅取
  之后本地已有的树：`git diff <prev> <tag> -- CHANGELOG.md` 的新增行就是这次发布的内容，
  退到发布提交正文（release-bot 仓库写在那里），再退到 CHANGELOG 开头 60 行。
  `tag_details` 一次浅取同时拿时刻与发布说明（`tag_times` 保留为薄封装）；采集器把
  `notes_snapshot` 写成 `<条目文件名>_changelog.md`，记录里带 `changelog_file`。
  发布说明同时进 `snippet`——只进快照等于不给打分与选题看。
- **实测**：openai/openai-python 四个 tag 全部命中 CHANGELOG diff，拿到
  「**api:** add a model option for Responses」这类可引用原文。回归测试走真实
  `collect_one`（让两条通道都返回 403 逼出 git 回退），断言快照真的落盘——缺的那一步
  正是写文件，复刻落盘逻辑的测试会绕开缺陷。

### P1-5 registry 没有「为已有事件追加增量」的通道

- **问题**：registry 只有"新事件"与"同一事件再次出现"两种状态，后者只往 `seen_in_runs`
  加一个日期，记不下"这次又发生了什么"。同一桩配对发版的事情在 11-01 / 11-03 / 11-05
  三轮各建了一个 B 级事件。
- **约束**：`events[].increments[]` + `append_increment()` + CLI `append-increment`；
  事件 JSON 可声明 `increment_of = {"event_key", "delta"}`，入库时自动挂上并由
  `validate_batch` 校验（指向不存在的事件、缺 delta、指向自己都打红）。增量自带
  source 与 first_publish，所以后续动作即使来自另一个仓库也挂在同一事件下。
  同一 (run_date, source) 只记一次。`report()` 单独列出本轮增量，供第 5 章与第 7 章书写。
  规则写进 task_def 15.3。

### P0-3 跨轮判重靠人工

- **问题**：registry 存着每个事件的来源，也有 `seen_before`，但 `seen_before` 只在 ingest
  时命中——那已经是卡片写完之后。每轮十几条「重复」处置都是手工 grep 上一份报告填的。
  第 5 章线索与被并入的条目根本不进 `events`，完全没有跨轮记忆。
- **约束**：`Registry.seen(urls)` + CLI `seen`，判重口径与 `event_key` 完全一致（都走
  `events.canonical_source`），所以不会出现"选题说新、入库说旧"；索引同时覆盖事件来源、
  增量来源与 `mentions`。`record_mentions()` + CLI `record-mentions` 从必审台账里把
  `chapter5` / `merged` 的条目登记进 registry，只存判重所需的最小信息，不参与命题图谱。
- **实测**：用第五轮的 183 条必审清单问当前 registry，命中 15 条早在 11-02 / 11-03
  已入库——正是每轮手工填的那 13–19 条。

### P0-2 build.py 每轮手写 500–700 行

- **问题**：单轮最大人工开销（516 / 723 / 683 行）。
- **诚实的边界**：680 行里绝大多数是判断内容（标题、key_data、机制叙述、五维评分的
  证据串），生成不了也不该生成。能自动化的是四类纯机械劳动，而且每类都出过错：
  样板头尾约 70 行；事实转抄；SIG 表手抄（`root_tech` 会逐字校验 `signal_quote`）；
  rejected 列表手工做差。
- **约束**：新增 `scaffold_build.py`。按 `picks.txt`（每行 `EV-01 <url 或 uid>`）生成骨架，
  预填 source / entity / 标题 / `evidence_form` 猜测，**时刻换算到 Asia/Shanghai 并把原值
  留在注释里**——2026-11-02 那份简报把 qwen-code v0.26.6 的 01:51 写成 09:51、nightly 的
  06:04 写成 14:04，就是人对一个已经是 +08:00 的值又按 +08 换了一次，这类错误从此不再
  经过人手。文件头列出 `change_object` / `evidence_form` / `change_types` 的全部合法取值，
  写错取值在桩位上就看得见。判断字段留 TODO，带着 TODO 跑会明确失败并列出缺什么。
  来源被 `seen` 命中时写出 `increment_of` 桩位。
  子命令 `rejected` 把缺失的说明连同每个候选的名字与陈述一并打出来——理由要对着真实
  内容写，不是对着一个编号写（此前手工补的理由往往泛泛一句）。

### P1-8 arxiv_score 对无摘要条目低估：前提被证伪，只保留补抓

- **先试的方案错了**：按"有无摘要"分车道配名额，有实测反例。第五轮那篇 A 级论文
  （J-Space 串谋）得 8 分且**有**摘要，按池内占比分配会把有摘要车道压到 8 个名额、
  截断线抬到 9 分，它反而被挤出清单——把一种偏差换成了另一种。已撤掉。
- **改为全量补抓摘要**：`arxiv_abstracts.py` 走 arXiv 官方批量接口，一次 100 篇、
  调用间隔 3 秒、落盘快照重跑不重抓。第五轮实测 1599 篇 16 次请求全部命中，约 1 分钟。
  摘要判定与回填归 `build_pool`（池层属性），`must_review.has_abstract` 保留为别名；
  清单的 `thresholds.arxiv_scoring_text` 报出补抓后仍无摘要的残量与"截断是否切在并列
  分数档内部"。
- **但补抓没有解决原问题**：补完之后截断线从 7 分跳到 15 分，那篇 A 级论文同样掉出
  top-40——`arxiv_score` 是无上限的词频累加，摘要越长命中越多，它排的是啰嗦程度。
  拿四轮 19 个 arXiv 来源事件当标注数据测了四种变体（现行 / 去重上限 / 标题加权 /
  长度归一），第五轮那 5 个正例在所有变体下都排 140–709 名，top-40 一个都捞不到；
  而当轮这 5 个事件**确实都不在必审清单里**，是靠临场读 arXiv 列表找出来的。
  进一步查：1102 / 1103 两轮召回看起来 9/9、3/3，是因为那两轮的 arXiv 池子只有 545 条
  （列表解析那时还是坏的），修好后是 1840 条、覆盖两个公告批次。真实量级是每公告日
  约 900 篇，K=40 等于 2–4% 覆盖。
- **结论**：arXiv 这条通道的正式召回机制目前是装饰性的，真正的选题来自临场阅读——
  这也解释了同一份 skill 换模型执行结果差异大。这是机制问题不是公式问题（可能要把
  每个批次的标题清单固化进运行记录，让重跑读到同一批），留待单独议。补抓本身保留：
  它是对的、便宜，是任何更好打分的前提，并且会在仍有残量时报警。

### 同轮顺手修掉的两处

- `test_verify_gates.py` 的 `if __name__ == "__main__"` 卡在文件中间，它后面定义的类
  （第四轮加的 `ReplaceAnnounceTest`、`CtLabelTest`）在直接运行该文件时压根不会被收集，
  只有 `unittest discover` 能跑到。已挪到文件末尾。
- `scaffold_build` 兼容 `window.json` 在 `raw_<date>/` 与运行根目录两处（采集器写前者，
  `freeze_window.py` 单独跑时在后者）。

测试 339 → 411 条，全绿。
