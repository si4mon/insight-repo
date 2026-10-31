生成 Asia/Shanghai 时区下，从“昨日 00:00”开始至“任务实际执行时刻”为止的“多源技术热点简报”，默认交付完整、可独立打开的高信息密度 HTML 文件。

本文件定义"做什么、按什么标准判断"；执行步骤、命令、文件路径与产物格式见 SKILL.md，本文件不重复。二者冲突时：内容判断以本文件为准，结构契约、文件路径与门禁以 SKILL.md 和脚本为准。

【0｜TARGET_WINDOW Gate｜最高优先级】
任务开始后，必须先获取真实当前运行时刻 NOW_UTC，并转换到 IANA 时区 Asia/Shanghai：NOW_SHANGHAI = convert_timezone(NOW_UTC, "Asia/Shanghai")。WINDOW_START_DATE = date(NOW_SHANGHAI) - 1 calendar day；WINDOW_START = WINDOW_START_DATE 00:00:00 Asia/Shanghai；WINDOW_END = NOW_SHANGHAI；TARGET_WINDOW = [WINDOW_START, WINDOW_END]。本任务中的 TARGET_DATE / TARGET_RANGE 语义统一解释为 TARGET_WINDOW，不再限定为单一自然日。禁止使用用户时区、浏览器时区、系统默认时区、上一轮日期、历史文件名、历史正文或已有状态文件推导 TARGET_WINDOW。冻结 TARGET_WINDOW 后，本轮的采集、检索、筛选、事件归属、标题、正文、文件名、8.2 Event Index 都必须使用同一窗口：WINDOW_START ≤ event_first_publish_time_in_Asia_Shanghai ≤ WINDOW_END。昨日全天事件允许进入正文；今日从 00:00 至任务执行时刻的事件允许进入正文；昨日 00:00 之前首次发布的事件，不得作为本轮“新事件”进入正文，只能按 Active Event / Historical Context 规则作为背景引用；无法确认首发时刻的高价值候选，必须明确标注“首发时间未完全核实”，不得伪造日期归属。生成前必须执行 Window Audit：H1 中的时间范围必须等于 TARGET_WINDOW；正文首页必须显示 WINDOW_START / WINDOW_END；8.2 Event Index 中所有“本轮新事件”的首发时刻都必须位于 TARGET_WINDOW；若文件生成过程中 NOW_SHANGHAI 已变化，不重新扩展 WINDOW_END；WINDOW_END 在任务开始时冻结；任一位置时间窗口不一致，废弃草稿并重新生成。文件名日期一律用 WINDOW_START_DATE（路径与命名见 SKILL.md）。

【0.1｜扫描窗口与事件归属分离】
事件归属窗口为 TARGET_WINDOW。为减少跨时区漏检，实际采集扫描窗口扩大为：SCAN_WINDOW_START = WINDOW_START - 6 hours；SCAN_WINDOW_END = WINDOW_END；SCAN_WINDOW = [SCAN_WINDOW_START, SCAN_WINDOW_END]。扫描窗口用于“发现候选”，TARGET_WINDOW 用于“决定正文新事件归属”。每个事件仍按“首次公开发布时刻”换算 Asia/Shanghai 判定是否属于 TARGET_WINDOW；SCAN_WINDOW_START 至 WINDOW_START 之间出现的事件只用于跨时区边界校验、Active Event、背景关系与漏检回溯；WINDOW_END 之后的信息不得以本次正文新事件身份出现；如果搜索结果页面日期与原始首发时间不一致，必须优先使用官方原始发布时间；美国当地日期、UTC 日期、媒体转载日期不得直接作为归属日期；聚合源命中后必须回溯原始来源确认首发时刻。跨日状态（源注册表 assets/sources.py、known_vocabulary、thesis registry 及其事件库、官方面快照、漏检档案）仅用于去重、差分和回溯，禁止用于推导 TARGET_WINDOW。若状态文件不可用，按“首次运行”执行，并在 8.1 中记录。

【1｜执行强度】
必须按高强度 Research / Reasoning 执行：多源检索、交叉验证、日期/版本审计、事件聚合、近 3 日 Active Event、Expert Thesis Watch、Frontier / Convergence / Confidence Gate、Zero-result Audit 后再成稿。禁止低强度摘要。执行顺序必须显式分阶段：P1 宽召回 → P2 抽象提升 → P3 聚类收敛 → P4 价值门控与排序 → P5 成稿交付 → P6 漏检回溯。P1 阶段禁止做价值判断和主题过滤。

【2｜采集机制：五路召回 + 双驱动补检】
禁止只按厂商/产品名扫描，也禁止只按关键词表扫描。关键词表与实体表决定“补检深度”，不决定“召回边界”。每天必须并行执行以下五路召回机制，全部完成后才能进入 Zero-result Gate。注意：这里的五路是“召回机制”，不同于源注册表里的源通道字段 channel（A_entity / B_arxiv / C_aggregator / D_social / E_expert / F_cn_media / G_official_surface）；二者的对应关系与执行方式见 SKILL.md 步骤 3，8.3 的“召回通道”列按 SKILL.md 填写。
1. Entity Watch：按厂商、项目、仓库、产品线检查正式发布与实质更新。
2. Technology Watch Matrix：按关键技术命题独立搜索，即使没有命中既有型号/产品名，也必须进入候选池。
3. Source Full-Read：对源注册表中每个源读取 SCAN_WINDOW 内全部条目，至少获取标题、链接、发布时间、来源，不得预先按主题过滤，包括注意力聚合源。
4. Cross-Source Resonance：任一实体/事件在 24h 内被 ≥3 个独立来源报道，或在 Hacker News 首页、GitHub Trending、Hugging Face Trending、专家 X / 博客圈、主流 AI 技术媒体出现明显热度突增，无论主题是否在 Watch Matrix 中，都强制进入候选池。
5. Official Surface Diff：对 Tier-1 厂商文档站导航/sitemap、changelog、release notes、model catalog、定价/套餐页、Help Center 更新列表、产品入口、开发者控制台公开页面与上一快照执行 diff。新增页面、新增对象名、新增/合并/下线的产品、模型、模式、API 生命周期变化，一律进入候选池。
预算约束：Source Full-Read、Cross-Source Resonance、Official Surface Diff 中非 Watchlist 命中的开放召回，不少于总检索/抓取调用的 30%。P1 输出候选池字段至少包括：标题、URL、首发时刻、Asia/Shanghai 首发时刻、来源、召回通道、原文要点、是否位于 TARGET_WINDOW、是否属于 Active Event / Historical Context。

【2.5｜抽象提升：把产品语言翻译成技术命题】
候选池中每个条目，尤其是产品公告、UI/形态变更、套餐与定价调整、帮助中心说明、新造名词，都必须先完成抽象提升，再判定去留。
变化类型可多选：边界迁移（能力/职责在 用户↔系统、Harness↔Model、端↔云、App↔OS、人工↔自动 之间移动）；抽象合并/拆分（产品、模式、入口、API、角色合一或分化）；默认值变化（从可选变默认、从手动变自动、从显式选择变系统路由）；交互契约变化（同步↔异步、阻塞↔后台、设备绑定↔设备脱离、单轮↔持续）；新一等对象（新名词成为可创建、可共享、可计费、可调度、可恢复或可审计的对象，例如 skill、routine、artifact、session、task）；信任/权限模型变化；生命周期变化（Beta、GA、弃用、价格、可用性）；规模或成本拐点。
技术命题必须使用类似“X 从 A 移到 B，因此 C 成为新约束”的句式改写至少一条，并按 primary_path 映射到第 3 章或第 4 章的栏目。
抽取原文中不在 known_vocabulary 中的新名词、缩写、产品名；若出现在 Tier-1 官方源或 ≥2 个独立来源，必须单独检索解释并进入候选评估；评估后更新 known_vocabulary。
对于“Claude chat 与 Cowork 合并为一个 Claude，无需选择模式，合上电脑任务继续执行”之类事件，不能只写“产品整合”，应识别为抽象合并 + 边界迁移 + 默认值变化 + 交互契约变化，并形成技术命题：模式选择从用户侧移到系统侧，任务路由开始内化；会话生命周期与客户端连接解耦，任务状态更多归属服务端/云端；context / skills / connectors 从产品面绑定转向账号级共享层。按具体机制拆到叶子：任务状态与路由内化 → C1.1/C1.3（4.1）；入口合并与交互契约 → E2.2/E1.2（4.7）；context/skills 共享层 → B2.4/B3.2。跨层影响用 related_domains 表达；只有存在内化、外置或职责调整的证据时，才附加 Model–Agent Boundary 关系标签，它不再是栏目。禁止以“属于产品/UI 更新”“不是模型发布”“不是 Runtime”“不在 Watch Matrix 中”为由直接丢弃，必须先完成抽象提升，再进入价值判断。

【3｜Tier-1 厂商 Source Surface Gate】
一级实体至少包括：OpenAI、Anthropic、Google / DeepMind、xAI、Meta、Microsoft、NVIDIA、DeepSeek、Qwen / Alibaba、ByteDance / Seed / Doubao、Moonshot / Kimi、Tencent / Hunyuan、Baidu、Zhipu、MiniMax、World Labs、Runway、Pika、Luma、Black Forest Labs、Stability AI。
至少检查：1) 官方公司/研究 Blog；2) 官方产品 Blog；3) Help Center / 用户 release notes / App 更新说明；4) Developer / API docs；5) Model catalog / model page / model card；6) Release notes / changelog / deprecations / availability / pricing；7) 官方 GitHub / releases / significant commits；8) 官方 X / 社媒作为补充。检查面必须落到源注册表 assets/sources.py 中的具体 URL，而不是抽象类别；某面确无可达源时登记在 UNCOVERABLE 并写明理由。
Anthropic 必含 anthropic.com/news、claude.com/blog、support.claude.com release notes、docs.claude.com、Claude Code / Cowork release notes 与 GitHub。OpenAI 必含 openai.com/index、help.openai.com release notes、platform / developers docs 与 changelog、Realtime / Audio / Agents / Codex surfaces。Google / DeepMind 必含 blog.google、deepmind.google、developers.googleblog、Gemini app updates / drops、Gemini API model catalog、Live API / Audio docs、release notes、model cards。ByteDance 必含 SeedRealtime / Seed / 豆包模型与产品技术页、火山引擎文档与更新日志、豆包 App 更新说明。其余一级实体按公司面 / 产品面 / 用户帮助面 / 开发者面 / 模型面 / 代码面 / 社媒面七层登记。若未完成对应子产品 / developer / 用户帮助面检查，不允许写“该厂商无高价值新增”。

【4｜Technology Watch Matrix｜模型侧必扫】
> 本节标题中的 "Track" 仅指**扫描范围**，不是输出栏目。事件的输出归属一律按 `primary_path` 落到 54 个叶子，不写 `tracks` 字段。

每天至少覆盖：
1. Foundation / Reasoning：LLM、MoE、pretraining、post-training、RL、test-time compute、recurrent depth、latent / concept reasoning、long context、KV / cache、speculative decoding、quantization、distillation、open weights、benchmark。
2. Realtime / Audio / Full-Duplex：native speech-to-speech、full-duplex、thinker-talker、fast / slow system、background reasoning、configurable thinking、async / non-blocking tool calling、barge-in / interrupt、proactive audio、streaming transcript、multiparty turn-taking、speaker grounding、real-time agent state。
3. Multimodal / Vision / Video：native multimodal、vision-language、understanding-generation unification、agentic video、video-tool-action loop、GUI / computer-use perception-action。
4. World Model / Spatial / Embodied：world state、spatial intelligence、video / world model、robot world model、VLA、physical reasoning、action generation、simulation / evaluator。
5. Model Internals / Interpretability：representation analysis、causal intervention、activation steering、model editing、training-data attribution、internal state observability。
6. Model–Harness 职责边界（**关系标签，不是栏目**）：重点检查 planning、skill routing、tool use、memory、verification、subagent decomposition、orchestration，判断这些能力究竟从 Harness 向模型内化，还是从模型外置到 state / control plane。事件仍按具体技术变化归入正常叶子；只有存在内化、外置或职责调整的证据时，才在卡片上附加该标签，**不得因“跨层”归入任何特殊栏目**。任何技术命题若出现一级厂商正式能力跃迁，即使不属于传统“新 foundation model 发布”，也必须进入 P0/P1 候选池。Live / Audio 模型、API lifecycle 改变、configurable thinking、background reasoning + async tools 等不得被“非通用大模型”过滤。本矩阵用于补检，不是召回边界。

【5｜Technology Watch Matrix｜Agent 系统侧必扫】
> 同上：这是扫描范围，不是栏目。输出归属按 `primary_path` 决定。

至少覆盖：Agent Runtime；Loop / Harness / Scaffold；Session / Task State；Long-running / Persistent Agent；Memory / Knowledge / Context Engineering；Skill / Routine / Automation；Tool Use；MCP / A2A；Computer Use；Multi-Agent / Swarm / Subagent；Agent Teams；AgentOS / Kernel；Sandbox；Trusted Agent；Policy / Permission / Verify / Governance；Evaluator / Observer / Commit Gate；Registry / Discovery；Agent Gateway；Recovery / Checkpoint / Audit / Observability；Artifact / Evidence / Trajectory；端云协同；多模型 / 多 Agent 编排；Harness / Skill / Routine Evolution；Agent 入口形态与产品形态；对话 / 代理 / 工作区合并或拆分；任务路由；设备脱离执行；跨端接续。
Open-ended Frontier Discovery 必须通过机制执行：以 Source Full-Read / Cross-Source Resonance / Official Surface Diff 的非 Watchlist 召回为输入；以【2.5】变化类型识别 new architecture、new abstraction、new engineering layer、new paradigm、new problem decomposition；以 known_vocabulary 差集识别新名词。不得因为名称不在关键词表中而漏掉。

【6｜Full-Duplex / Realtime Agent 专项 Watch】
每天必须单独检查 Google Gemini Live、OpenAI Realtime / GPT-Live、ByteDance SeedRealtime / 豆包、xAI / Grok voice、Anthropic voice、其他头部 native audio 模型及相关论文。重点判断：S2S / unified realtime model；speech、reasoning、tool execution 是否并行；blocking vs async tool semantics；client/runtime state 是否发生变化；turn completion 与 task completion 是否仍是同一语义；后台 reasoning / tool 是否可在前台语音继续时运行。若这些能力改变“实时 Agent 前台 + 后台推理 / 工具”的技术判断，应至少评为 A / A+ 候选，并在卡片上附加 Model–Harness 边界标签（标签不是栏目，主归属仍按具体叶子）。

【7｜固定来源 + 注意力聚合源】
固定来源：arXiv source-native feed / new / recent；Hugging Face Daily Papers / Blog / Models / Datasets / Spaces / Trending；GitHub 当日 repo / release / docs / commit / Trending；官方 Blog / Docs / Model Catalog / Release Notes / Help Center / RSS / X；Hacker News。中文优先源：机器之心、新智元、量子位、AI科技评论、智东西、DeepTech深科技、AI科技大本营、极客公园、硅星人Pro。专家原始博客 / X / 访谈 / 演讲。注意力聚合源：Techmeme、Hacker News 首页、Simon Willison、The Decoder、Latent Space、AlphaSignal、TechCrunch AI、The Verge AI、上述中文媒体头条。按 Source Full-Read 读取 SCAN_WINDOW 内全部条目。聚合源条目若指向一级实体官方公告，必须回溯官方原文确认首发时刻。所有来源登记在 assets/sources.py 中，支持动态增删，不得写死在流程里。模型侧（第 3 章）与 Agent 系统侧（第 4 章）必须各自独立完成 arXiv / HF / open-web discovery，不能用一侧的结果替代另一侧。

【8｜GitHub Org Diff】
对一级 Agent / Harness 项目执行 TARGET_WINDOW + 过去 48 小时 commit / release diff，至少覆盖：OpenClaw、DeepSeek Harness、Hermes、Microsoft Agent Framework、LangChain / LangGraph、LlamaIndex、CrewAI、Browser Use、Manus、OpenAI Codex / Agent、Claude Code / Cowork、Google ADK、AWS AgentCore、NVIDIA NemoClaw / OpenShell、Kimi。所有 commit 时间必须换算 Asia/Shanghai 后归档。正文中的“本轮新增”必须满足 TARGET_WINDOW。TARGET_WINDOW 之前、但位于过去 48 小时内的 commit，只能用于 Active Event、diff baseline、路线背景、连续演化判断。0 结果必须用 open web + official docs / X 复核。同时检查 GitHub Trending 中 SCAN_WINDOW 内 star 增速异常的 Agent / Model 新仓库，按 Cross-Source Resonance 进入候选池。

【9｜Active Event / 日期语义】
持续跟踪过去 3 天 A / A+：预告、Beta、论文、仓库、产品预热、模型灰度发布、API rollout、benchmark 更新。如果 TARGET_WINDOW 内出现实质新增，可作为事件更新。必须严格区分：首发日、论文 v1、revision、HF 榜单日、GitHub release、GitHub commit、媒体传播日、价格生效日、GA 生效日、rollout 开始日、文档更新日。禁止把传播日伪装成首发日。对于 TARGET_WINDOW 之前首次发布、但在本轮窗口内出现显著新增的事件，可以作为 Active Event Update 收录，但必须同时标 Original First Publish 与 Current Window Update，不能改写首发日期。

【10｜Frontier Value Gate】
每个候选独立评估 Technical Value、Evidence Confidence、Trend Maturity。Technical Value 高不等于成熟度高。Source Authority、Magnitude、Mechanism Novelty、Quantitative Evidence、Strategic Adjacency 五维各计 0–2 分并附证据，写进事件 JSON 的 scoring 块；评级由 scoring.py 按固定规则派生（A+：总分 ≥9 且机制新颖度与战略相关度均为 2；A：总分 ≥8 且两者均 ≥1；B：总分 ≥4；其余 C），不由人工给出。不同意派生结果时改某一维的分并写证据，不得直接改 rating。事件还要声明 event_class（technical / funding / market / regulatory / opinion）：后四类评级上限为 C，写出技术命题且机制新颖度 ≥1 时放宽到 B——融资、股价、评级、立法、观点类事件的影响面与量化证据都可能拿满分，没有这条上限会被抬进 A。Source Authority 按归并后的独立首发源计数：聚合源与社交平台本身不是首发源，指向同一篇原文的多个帖子合并计为 1，HF Papers 折叠到 arXiv。Strategic Adjacency 只按根技术清单计分（命中切换信号 2 分，当前代进展 1 分，无关 0 分），否证与支持同分；判据与清单见 references/root-tech-scoring.md，维度判据与正反例锚定见 references/rating-anchors.md。Top N 的次序对总分相差 ≤1 的相邻候选做两两比较后确定，裁定写进 events_run_<date>/pairwise.json。New Abstraction / Paradigm 即使部署早期，也必须单独评估 Abstraction Novelty、Architectural Leverage、Strategic Adjacency，不得因“像 framework / survey / position paper”自动降权。Technical Value 与 Strategic Adjacency 必须以【2.5】产出的技术命题为评估对象，并对照 thesis registry 中的已有命题（召回由 thesis_registry.py candidates 给出），例如 Model–Harness 能力边界、System Agent 入口与交互形态、端云任务状态归属、Agent 可信执行与权限、Realtime 前台 / 后台并行、Agent persistent state、Agent recovery / observability。判断该事件是否改变某一技术命题，而不是按原始公告产物类型判断。

【11｜Convergence / Confidence Gate】
趋势按 Event → Signal → Pattern → Thesis 评估：Cross-Entity、Cross-Form、Temporal Persistence、Adoption / Deployment、Mechanism Consistency、Counter-Evidence。趋势置信度输出 High / Medium / Low。Low 不进入核心技术判断。技术判断区分 Frontier Thesis 与 Convergence Thesis。置信度与 Frontier / Convergence 类型不由人工判定，而由 thesis registry 按 thesis_ontology.json 的 confidence_model 从证据派生：Cross-Entity、Cross-Form、Temporal Persistence、Adoption、Counter-Evidence 已量化计分；Mechanism Consistency 体现在 attach / new 与 supports / contradicts 的裁决中。跨实体收敛判断以【2.5】变化类型与技术命题对齐，不要求厂商使用相同名词。跨实体收敛里的"实体"必须是独立组织：占位性取值（arXiv、学术界、未披露等）不构成组织；论文 / 预印本 / 评测这类集体形态的支持证据整体只占一个实体位——两个不同作者团队的 arXiv 论文不构成两个实体。supports / contradicts / refines 的裁决必须可复核：除 rationale 外还要写 via_claim，指出事件的哪一条 claim 承载这个关系。

【12｜Expert Thesis Watch】
至少覆盖 Andrej Karpathy、Dario Amodei、Sam Altman、Demis Hassabis、Yann LeCun、Ilya Sutskever、Geoffrey Hinton、Jensen Huang、Satya Nadella、Mustafa Suleyman、Jeff Dean、Noam Brown、Aidan Gomez、Thomas Wolf、Yoshua Bengio、Fei-Fei Li、Lilian Weng、Liang Wenfeng。分类：L1 New Statement、L2 Reactivated Thesis、L3 Thesis Validation。只有专家在 TARGET_WINDOW 内首次公开表达的新观点，才属于 L1；如果原始观点早于 TARGET_WINDOW，只是在本轮重新传播，不得伪造为 L1；L1 = 0 时必须明确写 0；禁止用二手媒体转述制造“专家新观点”。

【12.5｜必审清单｜分层留痕】
候选池一轮 2000+ 条，逐条台账不可执行；全凭取舍则同一窗口不同执行各自漏掉不同事件。必须由 must_review.py 生成分层必审清单：官方首发面（A_entity + G_official_surface）窗口内条目全量、HF Daily Papers 全量、HN 上命中论域词且分数达阈值的条目、Techmeme 命中论域词的条目、中文媒体命中论域词的条目、arXiv 按词表打分前 K 篇。趋势榜单源不入清单。清单内每一条都必须在 must_review_trace.json 里给出处置：selected / merged（给出 EV 编号）、chapter5（写明第 5 章归属）、discarded（理由取【16.1】的封闭集合）；清单外的条目按池筛规则统计留痕，不要求逐条。清单只决定要不要留痕，不决定评级：清单外的条目仍可评 A。有价值的 arXiv 论文落在前 K 之外时，补词表而不是抬 K。分层规则、阈值与词表变更记录见 references/must-review.md。

【13｜Zero-result Gate｜强约束】
任何“无新模型”“无高价值新增”“0 命中”“某厂商今日无更新”结论都必须附采集证据。必须确认：Entity Watch 已完成；Technology Watch Matrix 对应技术面已完成；Tier-1 厂商公司面 + 产品面 + 用户帮助面 + developer/API + model catalog + release notes/model card 已完成；Source Full-Read 已完成；Cross-Source Resonance 已完成；Official Surface Diff 已完成，或记录快照不可用原因；arXiv / HF source-native open-ended scan 已完成；对相关 GitHub / 官方社媒做了补检；搜索时间范围覆盖整个 SCAN_WINDOW，而不是只搜“today”。任一面未执行，不得给 Zero-result 结论。8.1 中必须记录具体检查面、时间范围、查询方式、0 结果、无法访问的页面、快照不可用原因（8.1 的完整格式见 SKILL.md 6c）。

【14｜Value Ranking】
P0：Frontier Lab / 头部厂商模型；Audio / Live；Agent；Runtime；协议；架构正式发布；重要 open weights；重大能力 / API lifecycle 变化；系统级 benchmark；核心专家范式判断；头部厂商 Agent 产品形态 / 入口合并、拆分或默认行为变化。前提是经【2.5】确认改变技术命题。
P1：高质量论文 / 报告的新架构、机制、benchmark、定量证据；重大 Runtime / Framework Release；Memory / Harness / AgentInfra / MCP / A2A；New Abstraction；New Paradigm；New Engineering Layer；达到跨源共振阈值且经抽象提升确认有技术含义的事件。
P2：近 3 日 Active Event 实质增量；企业部署 / 生态落地；高价值 Thesis Validation。
P3：issue / discussion / bug 默认仅作为旁证。
主事件建议 8–14 个，宁滥毋缺。双日窗口内高价值事件明显多于 14 个，可扩大至 16–18 个，但禁止为追求数量降低证据门槛。第 3 章（模型）与第 4 章（Agent 系统）都必须保留真正改变技术判断的事件，但不按栏目配额。

【15｜每个 A / A+ 的分析门槛】
至少写清：核心变化；机制 / 架构；为什么重要；Technical Value；Evidence Confidence；Trend Maturity / Frontier Signal；与近 3 日 / 历史路线关系；原始 / 补充来源；日期语义；Asia/Shanghai 首发时间；召回通道。必须额外写出变化类型与技术命题。若原文是产品语言，必须提供“产品表述 → 技术命题”对应。若属于 Model–Harness Boundary，必须明确哪些能力正在从 Harness → Model 内化；哪些 state / policy / authority 继续外置；是否改变 client ↔ server / model ↔ runtime 的职责边界。若属于 Realtime / Audio，必须明确 speech / reasoning / tool 的并行关系；blocking vs async；client/runtime state；turn completion 与 task completion；前台语音和后台任务是否解耦。这些要求在主卡中的落位：评级、信号、Technical Value / Evidence Confidence / Trend Maturity、首发时间、日期语义、召回通道、变化类型、技术命题（TH 编号）写在卡片元信息里；核心变化与为什么重要写进「挑战与问题」；机制 / 架构以及 Model–Harness、Realtime 的必答项写进「机制与架构」；定量写进「效果与定量」；与近 3 日 / 历史路线的关系写进「对比其他方案的价值」（Markdown 结构见 SKILL.md 步骤 4、5）。

【15.1｜A / A+ 的 claim 级证据】
A / A+ 事件的每条未丢弃 claim 必须绑定到快照里的原文片段：claims[].evidence = {snapshot, snapshot_sha256, quote}。snapshot_sha256 对不上说明快照在事后被换过；quote 在快照里匹配不到说明那句话不是从原文来的。只要求"快照文件存在"是不够的——抓了原文却凭印象写机制时，快照仍然在，对不上的是正文。比对由 claim_evidence.py 完成，门禁逐条校验。

【15.2｜统计与主线】
事件总数、A+/A 计数、Dashboard 各项、8.2 索引表、第 2 章 Top N 必须由同一份 events_run_<date>/ 派生（report_stats.py），不得手写；门禁用同一脚本复算比对。第 1 章每条主线至少引用 2 个 8.2 中的 EV 编号，且引用的 EV 评级不低于 B——一个事件撑不起"主线"，那是单个事件，写在卡片里就够了。门禁通过后把摘要（通过数、失败项、脚本 commit）写在 .md 旁边，渲染器拒绝渲染没有门禁摘要、摘要有失败项、或 .md 在门禁之后被改过的稿子。

【16｜固定八章】
1 本轮结论与技术趋势：≤3 条跨栏目主线，描述本轮结构性变化的交汇，不重复栏目内的事件论证；分事实层与推理层书写（写法见 references/event-writing.md），并给出 Dashboard（见【17】）。
2 今日必看：“今日必看”指本 TARGET_WINDOW 最值得看的事件，不再局限于单一自然日。按技术价值输出 Top N，不设固定数量、不按栏目配额；达标几条列几条，不为凑数降低门槛，也不为凑数把 B 级抬进焦点层。评级相同时，优先改变技术判断的事件，而非只刷新数字的事件。Top 1 深拆（架构/流程可视化 + 落地场景 + 与历史路线关系），可在此承载该事件的唯一主卡；全卡超过 5 条时，Top 1 保留深拆，其余压缩为摘要卡（标题 + 评级 + 一句话命题 + 指向分类章主卡的链接），不重复正文。
3 模型技术热点：3.1 模型架构、训练与适应；3.2 推理、决策与效率；3.3 多模态、语音与实时模型；3.4 世界、空间与动作模型。只展开当天有入选事件的栏目（0 条不出现，1 条折叠进相邻栏目）；每个事件只在唯一主栏目写全卡。
4 Agent 系统技术热点：4.1 任务控制、运行与基础设施；4.2 记忆、知识与上下文；4.3 外部环境中的行动与工具使用；4.4 多 Agent 协同与互操作；4.5 学习与系统自进化；4.6 评测、验证与可信治理；4.7 交互、主动服务与持续委托。
5 值得关注：Early Signal、Active Event、Counter-signal、时间边界候选、未归类高信号。时间边界候选指首发时刻接近 WINDOW_START、时间信息存在时区歧义或仍需进一步核实的候选。未归类事件必须写明"为什么现有 54 个叶子都不覆盖"。
6 业界专家观点与趋势信号。
7 本轮技术判断：Frontier Thesis、Convergence Thesis。只写 thesis registry 本轮报告中 core_judgment 为真的命题（状态 active / contested 且置信度非 Low），每条写 TH 编号、类型、置信度（与 registry 一致）、本轮收敛 / 跨时间收敛与前后变化；contested 的命题必须写出反证；proposed 或 Low 的命题只能作为第 5 章 Early Signal。
8 信息源采集统计：8.1 源与覆盖审计；8.2 事件索引；8.3 候选池丢弃日志与漏检回溯。

栏目与叶子的映射以 assets/taxonomy.py 为唯一事实源，本文档不重复维护映射表。
第 3、4 章结构与分析深度必须对称。

【16.1｜候选池丢弃日志与漏检回溯】
候选池中被丢弃的 Tier-1 来源条目及共振命中条目，逐条记录：条目、来源、召回通道、首发时刻、是否位于 TARGET_WINDOW、处置、理由。丢弃理由为封闭集合，只能取：未验证、重复、低影响、首发早于 WINDOW_START、首发晚于 WINDOW_END、Active Event 非新事件、错误年份、媒体转载误判、已并入其他事件、技术命题未发生变化。不得无理由丢弃。
漏检回溯 P6：每次运行对照前一次扫描窗口的注意力聚合源头条、专家讨论、当前网络热点、上一份简报，识别可能漏检项。漏检根因为封闭集合，只能取：源面未覆盖、召回通道未命中、代理拦截、解析失败、窗口覆盖不完整、抽象提升失败、价值误判、日期边界、时区换算错误、官方原文未回溯、搜索结果年份污染、动态页面未读取。并据此更新 assets/sources.py、known_vocabulary、thesis registry（retire / merge / revise 决策）；变化类型体系属于 thesis_ontology.json，由人工维护。8.3 必须使用表格呈现。

【17｜HTML】
默认交付响应式、高信息密度、专业克制的完整 HTML。**只写 Markdown 工作源**，由内置渲染引擎生成自包含页面（命令、路径与 Markdown 结构契约见 SKILL.md 步骤 5）；排版与主题由引擎模板承担，设计约束见 references/design-constraints.md。禁止手改渲染后的 .html，修改一律回到 .md 重新渲染。Dashboard（第 1 章事实层中的统计表）必须同时显示 TARGET_WINDOW、事件总数、A / A+ 数、Frontier Signal 数、Convergence Signal 数、Active Event 数，并按 `change_object` 给出分布（Model / Harness / 运行平台 / 交互·应用 / 尚未披露）—— 不再使用旧的 Model Track / Harness Track 双轨计数。Top N 使用独立重点卡（数量按技术价值，不设固定值）。Top 1 必须给架构或流程可视化（本地 SVG/PNG 图片或表格，画机制不画名字；箭头带动词，跨度带尺寸线；图片要求见 SKILL.md 步骤 5）。每张主卡必须包含：可点击原始源、Asia/Shanghai 首发时刻、日期语义、Technical Value、Evidence Confidence、Trend Maturity、变化类型、技术命题（TH 编号）；摘要卡与第 5 章持续信号卡只需评级、一句话命题与指向主卡的链接。8.1 / 8.2 / 8.3 使用表格。

【18｜附件交付 Gate】
验收以脚本退出码为准，不由 LLM 读一遍 HTML 自证通过：结构、时间窗口、8.2 首发时刻归窗、Active / Historical 标注、来源链接、追溯与 registry 由 verify_gates.py 校验，渲染由 render_report.py 校验（检查项见 SKILL.md 步骤 6）。脚本覆盖不到的两项列入人工复核：title / H1 / Dashboard / 正文窗口 / 文件名的时间范围一致；不残留旧版“TARGET_DATE = 单一天”的文字或审计逻辑。交付前确认 reports/ 下渲染出的 .html 真实存在且 size > 0；客户端支持文件附件时，附上该文件并核对文件对象（文件名、大小），只有拿到真实可见的文件对象才允许标 SUCCESS。

【19｜最终回复】
最终回复必须简要给出：1) TARGET_WINDOW：WINDOW_START → WINDOW_END，均为 Asia/Shanghai；2) 本轮采纳了哪些栏目（按栏目列出主卡数量）；3) 章 2 的 Top N 名单（N 由价值决定）；4) 最重要的 Model ↔ Harness 技术判断；5) 与上一轮相比最重要的新增 / 修正，如有；6) 已通过可见性验收的真实 HTML 文件入口。最终回复不得把 TARGET_WINDOW 简写成单一 TARGET_DATE。若正文同时覆盖昨天和今天，必须明确写出两个自然日及精确截止时间。
