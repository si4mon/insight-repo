assets/thesis_ontology.json
----------------------------------------
{
  "schema_version": "1.0",
  "source": "demo/tech_report_task_def/tech_report_task_def.md",
  "description": "Upper ontology extracted from tech_report_task_def — stable backbone used by thesis_registry to ensure cross-run consistency. New categories emerge bottom-up via LLM proposal; this file only fixes the stable top-level axis.",
  "change_types": [
    {
      "id": "CT-01",
      "name": "边界迁移",
      "name_en": "boundary_migration",
      "definition": "能力/职责在 用户↔系统、Harness↔Model、端↔云、App↔OS、人工↔自动 之间移动",
      "task_def_ref": "line 23"
    },
    {
      "id": "CT-02",
      "name": "抽象合并",
      "name_en": "abstraction_merge",
      "definition": "产品、模式、入口、API、角色合一",
      "task_def_ref": "line 23"
    },
    {
      "id": "CT-03",
      "name": "抽象拆分",
      "name_en": "abstraction_split",
      "definition": "产品、模式、入口、API、角色分化",
      "task_def_ref": "line 23"
    },
    {
      "id": "CT-04",
      "name": "默认值变化",
      "name_en": "default_shift",
      "definition": "从可选变默认、从手动变自动、从显式选择变系统路由",
      "task_def_ref": "line 23"
    },
    {
      "id": "CT-05",
      "name": "交互契约变化",
      "name_en": "interaction_contract_change",
      "definition": "同步↔异步、阻塞↔后台、设备绑定↔设备脱离、单轮↔持续",
      "task_def_ref": "line 23"
    },
    {
      "id": "CT-06",
      "name": "新一等对象",
      "name_en": "new_first_class_object",
      "definition": "新名词成为可创建、可共享、可计费、可调度、可恢复或可审计的对象（skill/routine/artifact/session/task）",
      "task_def_ref": "line 23"
    },
    {
      "id": "CT-07",
      "name": "信任/权限模型变化",
      "name_en": "trust_permission_change",
      "definition": "信任边界、权限模型、治理结构发生变化",
      "task_def_ref": "line 23"
    },
    {
      "id": "CT-08",
      "name": "生命周期变化",
      "name_en": "lifecycle_change",
      "definition": "Beta、GA、弃用、价格、可用性等生命周期阶段变化",
      "task_def_ref": "line 23"
    },
    {
      "id": "CT-09",
      "name": "规模或成本拐点",
      "name_en": "scale_cost_inflection",
      "definition": "规模放大或成本下降达到拐点（如 40× 规模、70% 降本、1000+ tok/s）",
      "task_def_ref": "line 23"
    }
  ],
  "taxonomy": {
    "schema_version": "2.0",
    "description": "54 个三级技术叶子 → 11 个阅读栏目 → 8 章。叶子是事件的归档身份（跨天稳定），栏目是当天正文的阅读聚合（随热点显隐），章是固定骨架。映射固定，不逐日调整。",
    "sources": [
      "data/四层技术地图.txt",
      "data/技术简报分类和规则说明.txt"
    ],
    "chapters": [
      {"chapter": 1, "section_id": "s1", "name": "本轮结论与技术趋势", "part": "I 焦点", "role": "跨栏目主线，最多 3 条"},
      {"chapter": 2, "section_id": "s2", "name": "今日必看", "part": "I 焦点", "role": "按技术价值取 Top N，不设固定数量，不按栏目配额；Top1 深拆，N>5 时其余压缩为摘要卡"},
      {"chapter": 3, "section_id": "s3", "name": "模型技术热点", "part": "II 分类", "role": "3.1–3.4 动态栏目"},
      {"chapter": 4, "section_id": "s4", "name": "Agent 系统技术热点", "part": "II 分类", "role": "4.1–4.7 动态栏目"},
      {"chapter": 5, "section_id": "s5", "name": "值得关注", "part": "III 信号与判断", "role": "Early Signal / Counter-signal / Active Event / 未归类"},
      {"chapter": 6, "section_id": "s6", "name": "业界专家观点与趋势信号", "part": "III 信号与判断", "role": "人与其判断"},
      {"chapter": 7, "section_id": "s7", "name": "本轮技术判断", "part": "III 信号与判断", "role": "Frontier Thesis / Convergence Thesis"},
      {"chapter": 8, "section_id": "s8", "name": "信息源采集统计", "part": "IV 证据", "role": "8.1 源与覆盖审计 / 8.2 事件索引 / 8.3 丢弃与漏检回溯"}
    ],
    "domains": [
      {
        "id": "A",
        "name": "模型与学习技术",
        "question": "Agent 的模型能力如何形成，如何高效运行",
        "level2": [
          {"id": "A1", "name": "模型架构与表征"},
          {"id": "A2", "name": "训练与适应"},
          {"id": "A3", "name": "推理与部署效率"}
        ]
      },
      {
        "id": "B",
        "name": "认知、记忆与行动机制",
        "question": "Agent 如何理解任务、选择行动、积累经验",
        "level2": [
          {"id": "B1", "name": "推理、决策与规划"},
          {"id": "B2", "name": "记忆、知识与上下文"},
          {"id": "B3", "name": "工具、技能与环境行动"},
          {"id": "B4", "name": "学习与自进化"}
        ]
      },
      {
        "id": "C",
        "name": "运行、协同与基础设施",
        "question": "Agent 如何持续执行，多个执行主体如何协作",
        "level2": [
          {"id": "C1", "name": "Runtime 与持久执行"},
          {"id": "C2", "name": "多 Agent 协同"},
          {"id": "C3", "name": "协议与互操作"},
          {"id": "C4", "name": "运行平台与资源管理"}
        ]
      },
      {
        "id": "D",
        "name": "可靠性、评测与治理",
        "question": "怎样知道任务做对了，以及怎样约束执行",
        "level2": [
          {"id": "D1", "name": "评测与结果验证"},
          {"id": "D2", "name": "可观测与运维"},
          {"id": "D3", "name": "安全、身份与治理"}
        ]
      },
      {
        "id": "E",
        "name": "人机交互与持续委托",
        "question": "用户如何表达目标、控制代理，并在持续服务中理解其行为",
        "level2": [
          {"id": "E1", "name": "意图理解与用户委托"},
          {"id": "E2", "name": "多模态与生成式交互"},
          {"id": "E3", "name": "主动服务与连续体验"}
        ]
      }
    ],
    "columns": [
      {
        "id": "3.1",
        "chapter": 3,
        "name": "模型架构、训练与适应",
        "coverage": "架构、数据、后训练、蒸馏、持续适应",
        "leaves": ["A1.1", "A1.4", "A2.1", "A2.2", "A2.3"]
      },
      {
        "id": "3.2",
        "chapter": 3,
        "name": "推理、决策与效率",
        "coverage": "推理预算、判断模型、解码、缓存、模型服务效率",
        "leaves": ["A3.1", "A3.2", "A3.3", "B1.1"]
      },
      {
        "id": "3.3",
        "chapter": 3,
        "name": "多模态、语音与实时模型",
        "coverage": "视觉/视频/音频、原生多模态、实时模型",
        "leaves": ["A1.2"]
      },
      {
        "id": "3.4",
        "chapter": 3,
        "name": "世界、空间与动作模型",
        "coverage": "世界状态、空间推理、具身模型、动作生成",
        "leaves": ["A1.3"]
      },
      {
        "id": "4.1",
        "chapter": 4,
        "name": "任务控制、运行与基础设施",
        "coverage": "规划执行、Loop、任务状态、调度、恢复、运行平台",
        "leaves": ["B1.2", "B1.3", "C1.1", "C1.2", "C1.3", "C4.1", "C4.2", "C4.3"]
      },
      {
        "id": "4.2",
        "chapter": 4,
        "name": "记忆、知识与上下文",
        "coverage": "记忆生命周期、知识组织、检索、上下文与缓存",
        "leaves": ["B2.1", "B2.2", "B2.3", "B2.4"]
      },
      {
        "id": "4.3",
        "chapter": 4,
        "name": "外部环境中的行动与工具使用",
        "coverage": "工具使用、Skill、GUI/Computer Use、代码行动",
        "leaves": ["B3.1", "B3.2", "B3.3", "C3.1"]
      },
      {
        "id": "4.4",
        "chapter": 4,
        "name": "多 Agent 协同与互操作",
        "coverage": "团队组织、通信、共享状态、发现与委托协议",
        "leaves": ["C2.1", "C2.2", "C2.3", "C3.2", "C3.3"]
      },
      {
        "id": "4.5",
        "chapter": 4,
        "name": "学习与系统自进化",
        "coverage": "Prompt/Skill/Tool/Workflow/团队结构的反馈改进",
        "leaves": ["B4.1", "B4.2", "B4.3"]
      },
      {
        "id": "4.6",
        "chapter": 4,
        "name": "评测、验证与可信治理",
        "coverage": "Benchmark、Verify、Observability、隔离、权限与审计",
        "leaves": ["D1.1", "D1.2", "D1.3", "D2.1", "D2.2", "D2.3", "D3.1", "D3.2", "D3.3", "D3.4"],
        "annotation_required": true,
        "annotation_labels": ["评测环境", "结果核验", "可靠性归因", "运行证据", "调试回放", "生产质量", "身份授权", "执行隔离", "内容防护", "审计治理"],
        "annotation_map": {
          "评测环境": "D1.1",
          "结果核验": "D1.2",
          "可靠性归因": "D1.3",
          "运行证据": "D2.1",
          "调试回放": "D2.2",
          "生产质量": "D2.3",
          "身份授权": "D3.1",
          "执行隔离": "D3.2",
          "内容防护": "D3.3",
          "审计治理": "D3.4"
        }
      },
      {
        "id": "4.7",
        "chapter": 4,
        "name": "交互、主动服务与持续委托",
        "coverage": "动态界面、用户委托、主动性、连续体验",
        "leaves": ["E1.1", "E1.2", "E1.3", "E2.1", "E2.2", "E2.3", "E3.1", "E3.2", "E3.3"]
      }
    ],
    "leaves": [
      {"id": "A1.1", "name": "语言与推理模型结构", "level1": "A", "level2": "A1", "column": "3.1", "examples": "稠密/MoE、循环深度、潜在表征"},
      {"id": "A1.2", "name": "多模态与实时模型", "level1": "A", "level2": "A1", "column": "3.3", "examples": "跨模态融合、原生 S2S、thinker–talker"},
      {"id": "A1.3", "name": "世界、空间与动作模型", "level1": "A", "level2": "A1", "column": "3.4", "examples": "状态预测、空间表征、VLA/动作生成"},
      {"id": "A1.4", "name": "模型内部理解与干预", "level1": "A", "level2": "A1", "column": "3.1", "examples": "表征分析、因果干预、激活引导"},
      {"id": "A2.1", "name": "数据与训练环境", "level1": "A", "level2": "A2", "column": "3.1", "examples": "轨迹合成、课程构造、模拟环境"},
      {"id": "A2.2", "name": "Agent 能力后训练", "level1": "A", "level2": "A2", "column": "3.1", "examples": "工具使用 SFT、长程任务 RL、过程奖励"},
      {"id": "A2.3", "name": "专业化与持续适应", "level1": "A", "level2": "A2", "column": "3.1", "examples": "蒸馏、LoRA/适配器、持续学习与遗忘控制"},
      {"id": "A3.1", "name": "推理时计算控制", "level1": "A", "level2": "A3", "column": "3.2", "examples": "自适应预算、动态深度、早停"},
      {"id": "A3.2", "name": "推理解码与压缩", "level1": "A", "level2": "A3", "column": "3.2", "examples": "投机解码、量化、KV 优化"},
      {"id": "A3.3", "name": "模型服务与资源利用", "level1": "A", "level2": "A3", "column": "3.2", "examples": "批处理、分布式推理、多模型服务调度"},

      {"id": "B1.1", "name": "判断与动作选择", "level1": "B", "level2": "B1", "column": "3.2", "examples": "typed decision、置信校准、弃权与升级判断"},
      {"id": "B1.2", "name": "任务规划与搜索", "level1": "B", "level2": "B1", "column": "4.1", "examples": "任务分解、层级规划、约束/搜索规划"},
      {"id": "B1.3", "name": "执行反馈与重规划", "level1": "B", "level2": "B1", "column": "4.1", "examples": "进展判断、失败诊断、反思与计划修订"},
      {"id": "B2.1", "name": "记忆表示与载体", "level1": "B", "level2": "B2", "column": "4.2", "examples": "显式记录、参数化记忆、潜在状态记忆"},
      {"id": "B2.2", "name": "记忆生命周期", "level1": "B", "level2": "B2", "column": "4.2", "examples": "写入筛选、冲突更新、遗忘/有效期/版本"},
      {"id": "B2.3", "name": "知识组织", "level1": "B", "level2": "B2", "column": "4.2", "examples": "知识图谱、Wiki、程序性知识图"},
      {"id": "B2.4", "name": "检索与上下文构造", "level1": "B", "level2": "B2", "column": "4.2", "examples": "检索重排、上下文选择/压缩、缓存复用"},
      {"id": "B3.1", "name": "工具使用", "level1": "B", "level2": "B3", "column": "4.3", "examples": "工具选择、参数生成、组合调用与错误修复"},
      {"id": "B3.2", "name": "程序性技能", "level1": "B", "level2": "B3", "column": "4.3", "examples": "Skill 表示、检索组合、适用条件与执行"},
      {"id": "B3.3", "name": "环境感知与行动落地", "level1": "B", "level2": "B3", "column": "4.3", "examples": "GUI grounding、Code as Action、机器人动作控制"},
      {"id": "B4.1", "name": "可演进对象", "level1": "B", "level2": "B4", "column": "4.5", "examples": "Prompt、Skill/Tool、Loop/Workflow/团队结构"},
      {"id": "B4.2", "name": "改进算法与反馈", "level1": "B", "level2": "B4", "column": "4.5", "examples": "文本反馈优化、奖励驱动搜索、种群演化"},
      {"id": "B4.3", "name": "改进的保留与推广", "level1": "B", "level2": "B4", "column": "4.5", "examples": "跨任务经验迁移、模型与系统协同演进、回归验证"},

      {"id": "C1.1", "name": "执行循环与任务状态", "level1": "C", "level2": "C1", "column": "4.1", "examples": "状态机、任务 DAG、终止与完成条件"},
      {"id": "C1.2", "name": "持久化与故障恢复", "level1": "C", "level2": "C1", "column": "4.1", "examples": "Checkpoint、事件日志、重放与语义恢复"},
      {"id": "C1.3", "name": "调度与并发控制", "level1": "C", "level2": "C1", "column": "4.1", "examples": "异步工具、后台任务、取消/中断/超时"},
      {"id": "C2.1", "name": "组织与分工", "level1": "C", "level2": "C2", "column": "4.4", "examples": "Supervisor–Worker、层级团队、动态角色分配"},
      {"id": "C2.2", "name": "通信与共享状态", "level1": "C", "level2": "C2", "column": "4.4", "examples": "消息/潜在通信、共享工作区、状态一致性"},
      {"id": "C2.3", "name": "集体决策与协调", "level1": "C", "level2": "C2", "column": "4.4", "examples": "协商、辩论/投票、协作学习与信用分配"},
      {"id": "C3.1", "name": "工具和数据连接", "level1": "C", "level2": "C3", "column": "4.3", "examples": "能力描述、工具发现、调用与通知契约"},
      {"id": "C3.2", "name": "Agent 发现与委托", "level1": "C", "level2": "C3", "column": "4.4", "examples": "Agent Card、远程任务生命周期、产物交换"},
      {"id": "C3.3", "name": "工作接续与语义互通", "level1": "C", "level2": "C3", "column": "4.4", "examples": "语义检查点、未完成任务交接、证据与产物血缘"},
      {"id": "C4.1", "name": "执行环境与资源", "level1": "C", "level2": "C4", "column": "4.1", "examples": "容器/VM、浏览器/代码环境、资源配额"},
      {"id": "C4.2", "name": "能力与服务生命周期", "level1": "C", "level2": "C4", "column": "4.1", "examples": "Registry、版本/依赖管理、发布与退役"},
      {"id": "C4.3", "name": "端云与异构协同", "level1": "C", "level2": "C4", "column": "4.1", "examples": "执行位置选择、状态迁移、算力与能耗协同"},

      {"id": "D1.1", "name": "任务与环境评测", "level1": "D", "level2": "D1", "column": "4.6", "examples": "长程任务集、交互式 benchmark、真实环境测试"},
      {"id": "D1.2", "name": "过程和结果核验", "level1": "D", "level2": "D1", "column": "4.6", "examples": "可执行检查、形式验证、证据核验与 Judge"},
      {"id": "D1.3", "name": "可靠性与归因", "level1": "D", "level2": "D1", "column": "4.6", "examples": "重复试验、故障注入、模型/系统/环境归因"},
      {"id": "D2.1", "name": "运行证据采集", "level1": "D", "level2": "D2", "column": "4.6", "examples": "Trace、动作/状态日志、证据与产物关联"},
      {"id": "D2.2", "name": "调试与回放", "level1": "D", "level2": "D2", "column": "4.6", "examples": "轨迹重放、分支比较、回归定位"},
      {"id": "D2.3", "name": "生产质量与效率", "level1": "D", "level2": "D2", "column": "4.6", "examples": "成功率、延迟/成本、SLO 与异常诊断"},
      {"id": "D3.1", "name": "身份与委托授权", "level1": "D", "level2": "D3", "column": "4.6", "examples": "用户/Agent 身份、最小权限、凭据隔离"},
      {"id": "D3.2", "name": "执行隔离与动作控制", "level1": "D", "level2": "D3", "column": "4.6", "examples": "Sandbox、网络外发控制、审批/提交门槛"},
      {"id": "D3.3", "name": "内容和供应链防护", "level1": "D", "level2": "D3", "column": "4.6", "examples": "Prompt injection、记忆污染、恶意工具/Skill"},
      {"id": "D3.4", "name": "审计与生命周期治理", "level1": "D", "level2": "D3", "column": "4.6", "examples": "行为审计、策略管理、数据保留/删除与撤权"},

      {"id": "E1.1", "name": "目标与偏好对齐", "level1": "E", "level2": "E1", "column": "4.7", "examples": "目标澄清、偏好推断、冲突目标处理"},
      {"id": "E1.2", "name": "委托范围表达", "level1": "E", "level2": "E1", "column": "4.7", "examples": "时间/资源/动作边界、完成条件、可撤销委托"},
      {"id": "E1.3", "name": "人与 Agent 协作", "level1": "E", "level2": "E1", "column": "4.7", "examples": "人工接管、协同编辑、反馈与纠偏"},
      {"id": "E2.1", "name": "实时对话协同", "level1": "E", "level2": "E2", "column": "4.7", "examples": "打断、轮次管理、前台对话与后台任务同步"},
      {"id": "E2.2", "name": "动态界面", "level1": "E", "level2": "E2", "column": "4.7", "examples": "声明式组件、数据绑定、交互动作回传"},
      {"id": "E2.3", "name": "任务与结果呈现", "level1": "E", "level2": "E2", "column": "4.7", "examples": "进度可视化、可编辑产物、证据及验收界面"},
      {"id": "E3.1", "name": "主动机会识别", "level1": "E", "level2": "E3", "column": "4.7", "examples": "需求预测、相关性判断、打扰预算"},
      {"id": "E3.2", "name": "持续目标服务", "level1": "E", "level2": "E3", "column": "4.7", "examples": "周期/事件触发、目标常驻、完成条件更新"},
      {"id": "E3.3", "name": "跨端与跨会话连续性", "level1": "E", "level2": "E3", "column": "4.7", "examples": "交互状态接续、设备切换、用户上下文连续"}
    ],
    "change_objects": ["Model", "Harness", "运行平台", "交互·应用", "尚未披露"],
    "rules": {
      "primary_path_unique": true,
      "must_drill_level2": ["A1", "B1", "C3"],
      "max_related_domains": 2,
      "unclassified_chapter": 5,
      "boundary_label": "Model–Agent Boundary",
      "column_display": {
        "0": "不出现",
        "1": "折叠为卡片标签",
        "gte2": "展开为独立小节"
      },
      "empty_states": ["已扫描无入选", "扫描不完整", "未扫描"],
      "meanings": {
        "已扫描无入选": "覆盖完成，当日本领域无实质技术变化",
        "扫描不完整": "采集存在缺口，需补检",
        "未扫描": "未覆盖该领域，需登记原因"
      },
      "sections_field": "deprecated（保留但不再写入；新事件只写 primary_path）",
      "tracks_field": "deprecated（由 taxonomy.change_objects 取代）"
    }
  },
  "tracks": [
    {
      "id": "TR-MODEL",
      "name": "Model Track",
      "sections": [
        {"id": "s2-1", "name": "Language / Reasoning / Training & Inference"},
        {"id": "s2-2", "name": "Multimodal / Speech / Full-duplex / Vision"},
        {"id": "s2-3", "name": "World Model / Spatial / Embodied"},
        {"id": "s2-4", "name": "Model–Agent Boundary"}
      ],
      "watch_matrix": [
        "Foundation / Reasoning",
        "Realtime / Audio / Full-Duplex",
        "Multimodal / Vision / Video",
        "World Model / Spatial / Embodied",
        "Model Internals / Interpretability",
        "Model–Harness Boundary"
      ],
      "task_def_ref": "line 33-40, 82"
    },
    {
      "id": "TR-HARNESS",
      "name": "Harness Track",
      "sections": [
        {"id": "s3-1", "name": "Runtime / Session / Task State / Long-running"},
        {"id": "s3-2", "name": "Memory / Knowledge / Context"},
        {"id": "s3-3", "name": "Harness / Loop / Skill / Routine / Automation / Evolution"},
        {"id": "s3-4", "name": "Multi-agent / AgentOS / Tool / MCP / A2A / Computer Use"},
        {"id": "s3-5", "name": "Trusted Agent / Sandbox / Verify / Governance"}
      ],
      "watch_matrix": [
        "Agent Runtime", "Loop / Harness / Scaffold", "Session / Task State",
        "Long-running / Persistent Agent", "Memory / Knowledge / Context Engineering",
        "Skill / Routine / Automation", "Tool Use", "MCP / A2A", "Computer Use",
        "Multi-Agent / Swarm / Subagent", "Agent Teams", "AgentOS / Kernel",
        "Sandbox", "Trusted Agent", "Policy / Permission / Verify / Governance",
        "Evaluator / Observer / Commit Gate", "Registry / Discovery", "Agent Gateway",
        "Recovery / Checkpoint / Audit / Observability", "Artifact / Evidence / Trajectory",
        "端云协同", "多模型 / 多 Agent 编排", "Harness / Skill / Routine Evolution",
        "Agent 入口形态与产品形态", "对话 / 代理 / 工作区合并或拆分", "任务路由",
        "设备脱离执行", "跨端接续"
      ],
      "task_def_ref": "line 42-44, 83"
    }
  ],
  "rating": {
    "levels": [
      {
        "id": "R-A-PLUS",
        "name": "A+",
        "criteria": "机制新颖 + 定量充分 + 多源共振（Source Authority / Magnitude of Change / Mechanism Novelty / Quantitative Evidence / Strategic Adjacency 多数满足）",
        "enters_top_watch": true,
        "task_def_ref": "line 58-59, 77"
      },
      {
        "id": "R-A",
        "name": "A",
        "criteria": "量化显著但缺乏独立基准；改变某一技术命题，证据强度稍逊 A+",
        "enters_top_watch": true,
        "task_def_ref": "line 59, 71-72"
      },
      {
        "id": "R-B",
        "name": "B",
        "criteria": "信号明确但证据不足；进入值得关注但不进入今日必看",
        "enters_top_watch": false,
        "task_def_ref": "line 72-73"
      },
      {
        "id": "R-C",
        "name": "C",
        "criteria": "旁证 / issue / discussion 级，仅作佐证",
        "enters_top_watch": false,
        "task_def_ref": "line 74"
      },
      {
        "id": "R-D",
        "name": "D",
        "criteria": "丢弃或并入其他事件",
        "enters_top_watch": false,
        "task_def_ref": "line 92"
      }
    ],
    "evaluation_dimensions": {
      "technical_value": ["Source Authority", "Magnitude of Change", "Mechanism Novelty", "Quantitative Evidence", "Strategic Adjacency"],
      "abstraction_specific": ["Abstraction Novelty", "Architectural Leverage", "Strategic Adjacency"],
      "task_def_ref": "line 59"
    }
  },
  "signal_types": [
    {
      "id": "SIG-FRONTIER",
      "name": "Frontier Signal",
      "definition": "单实体拐点 — 某一 Tier-1 实体出现机制新颖/规模/能力的实质跃迁，即使部署早期也单独评估",
      "task_def_ref": "line 59, 61"
    },
    {
      "id": "SIG-CONVERGENCE",
      "name": "Convergence Signal",
      "definition": "多实体收敛 — 跨实体在同一技术命题上对齐（不要求使用相同名词）",
      "task_def_ref": "line 61-62"
    }
  ],
  "evaluation_chain": {
    "stages": ["Event", "Signal", "Pattern", "Thesis"],
    "convergence_dimensions": [
      "Cross-Entity", "Cross-Form", "Temporal Persistence",
      "Adoption / Deployment", "Mechanism Consistency", "Counter-Evidence"
    ],
    "confidence_levels": ["High", "Medium", "Low"],
    "low_confidence_rule": "Low 不进入核心技术判断",
    "thesis_types": ["Frontier Thesis", "Convergence Thesis"],
    "task_def_ref": "line 61-62"
  },
  "value_ranking": {
    "P0": "Frontier Lab / 头部厂商模型；Audio / Live；Agent；Runtime；协议；架构正式发布；重要 open weights；重大能力 / API lifecycle 变化；系统级 benchmark；核心专家范式判断；头部厂商 Agent 产品形态 / 入口合并、拆分或默认行为变化",
    "P1": "高质量论文 / 报告的新架构、机制、benchmark、定量证据；重大 Runtime / Framework Release；Memory / Harness / AgentInfra / MCP / A2A；New Abstraction；New Paradigm；New Engineering Layer；达到跨源共振阈值",
    "P2": "近 3 日 Active Event 实质增量；企业部署 / 生态落地；高价值 Thesis Validation",
    "P3": "issue / discussion / bug 默认仅作旁证",
    "main_event_count": "8–14 个，高价值明显多于 14 可扩到 16–18，禁止为数量降低证据门槛",
    "task_def_ref": "line 70-75"
  },
  "expert_watch": {
    "experts": [
      "Andrej Karpathy", "Dario Amodei", "Sam Altman", "Demis Hassabis",
      "Yann LeCun", "Ilya Sutskever", "Geoffrey Hinton", "Jensen Huang",
      "Satya Nadella", "Mustafa Suleyman", "Jeff Dean", "Noam Brown",
      "Aidan Gomez", "Thomas Wolf", "Yoshua Bengio", "Fei-Fei Li",
      "Lilian Weng", "Liang Wenfeng"
    ],
    "categories": {
      "L1": "New Statement — TARGET_WINDOW 内首次公开表达的新观点",
      "L2": "Reactivated Thesis — 原始观点早于窗口，本轮重新传播",
      "L3": "Thesis Validation — 事件/数据验证了专家既有论点"
    },
    "task_def_ref": "line 64-65"
  },
  "tier1_entities": [
    "OpenAI", "Anthropic", "Google / DeepMind", "xAI", "Meta",
    "Microsoft", "NVIDIA", "DeepSeek", "Qwen / Alibaba",
    "ByteDance / Seed / Doubao", "Moonshot / Kimi", "Tencent / Hunyuan",
    "Baidu", "Zhipu", "MiniMax", "World Labs", "Runway", "Pika",
    "Luma", "Black Forest Labs", "Stability AI"
  ],
  "thesis_lifecycle": {
    "states": ["proposed", "active", "dormant", "retired"],
    "transitions": {
      "proposed->active": "再次在后续 run 中出现且证据增强",
      "active->dormant": "连续 N run 未出现新证据（N 默认 14）",
      "dormant->active": "重新出现新证据",
      "dormant->retired": "被 counter-evidence 否证或被新 thesis 合并",
      "any->merged": "与另一 thesis 合并"
    },
    "note": "lifecycle 由 thesis_registry.py 维护，不由 ontology 直接约束"
  }
}


assets/thesis_registry.py
----------------------------------------
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Thesis Registry · query / ingest / update API

跨 run 持久化技术命题（thesis）的轻量状态机。
- Upper ontology 从 thesis_ontology.json 读取（稳定骨架）
- Thesis 实例持久化在 thesis_registry.json（跨 run 累积）
- Per-run instances 由 LLM 动态生成，通过 ingest_event 写入

三种核心操作：
  query  — 反向查询历史 thesis，供 P3 聚类收敛判断跨时间收敛
  ingest — 把本轮事件映射/创建 thesis，供 P2 抽象提升后持久化
  update — 运行生命周期迁移（proposed→active / active→dormant / 合并 / 退役）

用法：
  # CLI
  python thesis_registry.py query --track TR-MODEL
  python thesis_registry.py query --search "扩散"
  python thesis_registry.py query --id TH-001
  python thesis_registry.py ingest --event-file /path/to/event.json
  python thesis_registry.py update --run-date 2026-10-20
  python thesis_registry.py stats

  # 作为模块
  from thesis_registry import Registry
  reg = Registry()
  hits = reg.query_by_track("TR-MODEL")
  reg.ingest_event(event_dict, run_date="2026-10-20")
  reg.save()
"""
import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import Optional


ASSETS_DIR = Path(__file__).parent                  # assets/ — 只读引擎 + 骨架
SKILL_DIR = ASSETS_DIR.parent                       # tech-briefing/
DATA_DIR = SKILL_DIR / "data"                        # data/ — 可写全局状态
ONTOLOGY_PATH = ASSETS_DIR / "thesis_ontology.json"  # 骨架在 assets/
REGISTRY_PATH = DATA_DIR / "thesis_registry.json"    # 实例库在 data/
DATA_DIR.mkdir(parents=True, exist_ok=True)          # 首次运行时确保 data/ 存在

# 默认生命周期参数
DORMANT_AFTER_RUNS = 14  # 连续 N run 无新证据 → dormant
RETIRE_AFTER_RUNS = 30  # dormant 后再 N run 仍无证据 → retired


def shanghai_today() -> str:
    tz = datetime.timezone(datetime.timedelta(hours=8))
    return datetime.datetime.now(tz).strftime("%Y-%m-%d")


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


class Registry:
    """Thesis registry — 封装 ontology + thesis 实例的查询与写入。"""

    def __init__(self,
                 ontology_path: Path = ONTOLOGY_PATH,
                 registry_path: Path = REGISTRY_PATH):
        self.ontology_path = ontology_path
        self.registry_path = registry_path
        self.ontology = load_json(ontology_path)
        self.registry = load_json(registry_path)
        if "theses" not in self.registry:
            self.registry["theses"] = []

    # ---------- query ----------
    def all_theses(self) -> list[dict]:
        return self.registry.get("theses", [])

    def get_by_id(self, thesis_id: str) -> Optional[dict]:
        for t in self.all_theses():
            if t["id"] == thesis_id:
                return t
        return None

    def query_by_track(self, track_id: str) -> list[dict]:
        return [t for t in self.all_theses() if track_id in t.get("tracks", [])]

    def query_by_section(self, section_id: str) -> list[dict]:
        return [t for t in self.all_theses() if section_id in t.get("sections", [])]

    def query_by_state(self, state: str) -> list[dict]:
        return [t for t in self.all_theses() if t.get("state") == state]

    def query_by_change_type(self, ct_id: str) -> list[dict]:
        return [t for t in self.all_theses() if ct_id in t.get("change_types", [])]

    def query_by_entity(self, entity: str) -> list[dict]:
        hits = []
        for t in self.all_theses():
            if entity in t.get("convergence_entities", []):
                hits.append(t)
            for ev in t.get("events", []):
                if entity.lower() in ev.get("source", "").lower():
                    hits.append(t)
                    break
        return hits

    def search(self, keyword: str) -> list[dict]:
        kw = keyword.lower()
        hits = []
        for t in self.all_theses():
            blob = (t.get("name", "") + " " + t.get("name_en", "") +
                    " " + t.get("statement", "")).lower()
            if kw in blob:
                hits.append(t)
        return hits

    def query_for_convergence(self, event: dict) -> list[dict]:
        """
        P3 聚类收敛时调用：根据事件的 change_types / tracks / sections
        找出可能产生跨时间收敛的历史 thesis。
        返回 active / dormant 的 thesis（排除 retired）。
        """
        ct = event.get("change_types", [])
        tracks = event.get("tracks", [])
        sections = event.get("sections", [])
        hits = []
        for t in self.all_theses():
            if t.get("state") == "retired":
                continue
            overlap_ct = set(ct) & set(t.get("change_types", []))
            overlap_tr = set(tracks) & set(t.get("tracks", []))
            overlap_sec = set(sections) & set(t.get("sections", []))
            if overlap_ct and (overlap_tr or overlap_sec):
                hits.append(t)
        return hits

    # ---------- ingest ----------
    def ingest_event(self, event: dict, run_date: Optional[str] = None) -> dict:
        """
        把一个 P2 抽象提升后的事件写入 registry。

        event 字段：
          thesis_name, thesis_name_en (可选), statement,
          thesis_type (Frontier/Convergence), change_types (CT-xx),
          tracks (TR-xxx), sections (s2-x / s3-x),
          rating (A+/A/B...), signal (Frontier/Convergence/Early),
          first_publish_shanghai, source, event_title, key_data,
          confidence (可选), proposed_thesis_id (可选, 若映射到已有 thesis)

        返回写入的 thesis 字典。
        """
        run_date = run_date or shanghai_today()
        thesis_id = event.get("proposed_thesis_id")
        existing = self.get_by_id(thesis_id) if thesis_id else None

        # 若没有 proposed_thesis_id，尝试用 thesis_name_en 精确匹配已有 thesis
        if not existing and event.get("thesis_name_en"):
            name_en = event["thesis_name_en"]
            for t in self.registry.get("theses", []):
                if t.get("name_en") == name_en and t.get("state") != "merged":
                    existing = t
                    break

        event_record = {
            "brief_date": event.get("brief_date", run_date),
            "event_title": event.get("event_title", ""),
            "first_publish_shanghai": event.get("first_publish_shanghai", ""),
            "rating": event.get("rating", ""),
            "signal": event.get("signal", ""),
            "source": event.get("source", ""),
            "key_data": event.get("key_data", ""),
        }

        if existing:
            # 映射到已有 thesis — 追加事件，更新 last_seen / evidence_count / state
            existing["events"].append(event_record)
            existing["last_seen"] = run_date
            existing["evidence_count"] = existing.get("evidence_count", 0) + 1
            # proposed → active：再次出现即升级
            if existing.get("state") == "proposed":
                existing["state"] = "active"
            # 追加新实体（去重）
            ent = event.get("entity", "")
            if ent and ent not in existing.get("convergence_entities", []):
                existing["convergence_entities"].append(ent)
            # 更新置信度（取更高）
            new_conf = event.get("confidence")
            if new_conf:
                existing["confidence"] = _max_confidence(
                    existing.get("confidence", "Low"), new_conf)
            return existing

        # 创建新 thesis
        new_id = self._next_thesis_id()
        new_thesis = {
            "id": new_id,
            "name": event.get("thesis_name", ""),
            "name_en": event.get("thesis_name_en", ""),
            "thesis_type": event.get("thesis_type", "Frontier Thesis"),
            "statement": event.get("statement", ""),
            "change_types": event.get("change_types", []),
            "tracks": event.get("tracks", []),
            "sections": event.get("sections", []),
            "state": "proposed" if event.get("rating", "B") in ("B", "C") else "active",
            "confidence": event.get("confidence", "Medium"),
            "first_seen": run_date,
            "last_seen": run_date,
            "evidence_count": 1,
            "convergence_entities": [event.get("entity", "")] if event.get("entity") else [],
            "counter_evidence": [],
            "events": [event_record],
            "notes": event.get("notes", ""),
        }
        self.registry["theses"].append(new_thesis)
        return new_thesis

    def _next_thesis_id(self) -> str:
        existing_ids = [t["id"] for t in self.all_theses() if t["id"].startswith("TH-")]
        max_n = 0
        for tid in existing_ids:
            try:
                n = int(tid.split("-")[1])
                if n > max_n:
                    max_n = n
            except (ValueError, IndexError):
                continue
        return f"TH-{max_n + 1:03d}"

    # ---------- update / lifecycle ----------
    def run_lifecycle(self, run_date: Optional[str] = None) -> dict:
        """
        每次 run 结束后调用：根据 last_seen 与 run_date 的差值
        执行状态迁移。

        返回迁移摘要 {state_changes: [...], merges: [...]}。
        """
        run_date = run_date or shanghai_today()
        changes = []
        for t in self.all_theses():
            old_state = t.get("state", "active")
            days_since = _days_between(t.get("last_seen", run_date), run_date)
            # 粗略按"每轮 run 间隔 1 天"估算 run 数
            runs_since = max(0, days_since)

            if old_state == "active" and runs_since >= DORMANT_AFTER_RUNS:
                t["state"] = "dormant"
                changes.append({"id": t["id"], "from": old_state, "to": "dormant"})
            elif old_state == "dormant" and runs_since >= DORMANT_AFTER_RUNS + RETIRE_AFTER_RUNS:
                t["state"] = "retired"
                changes.append({"id": t["id"], "from": old_state, "to": "retired"})

        self.registry["last_updated"] = run_date
        return {"state_changes": changes}

    def merge_theses(self, source_id: str, target_id: str, run_date: Optional[str] = None) -> dict:
        """把 source thesis 合并到 target，source 标记为 merged。"""
        run_date = run_date or shanghai_today()
        source = self.get_by_id(source_id)
        target = self.get_by_id(target_id)
        if not source or not target:
            raise ValueError(f"merge: thesis not found ({source_id} / {target_id})")
        target["events"].extend(source.get("events", []))
        target["evidence_count"] = target.get("evidence_count", 0) + source.get("evidence_count", 0)
        for ent in source.get("convergence_entities", []):
            if ent not in target.get("convergence_entities", []):
                target["convergence_entities"].append(ent)
        target["last_seen"] = max(target.get("last_seen", run_date),
                                  source.get("last_seen", run_date))
        source["state"] = "merged"
        source["merged_into"] = target_id
        return {"merged": source_id, "into": target_id}

    def add_counter_evidence(self, thesis_id: str, evidence: str, run_date: Optional[str] = None) -> dict:
        run_date = run_date or shanghai_today()
        t = self.get_by_id(thesis_id)
        if not t:
            raise ValueError(f"counter-evidence: thesis {thesis_id} not found")
        t.setdefault("counter_evidence", []).append({
            "date": run_date,
            "evidence": evidence,
        })
        return t

    # ---------- stats ----------
    def stats(self) -> dict:
        theses = self.all_theses()
        by_state = {}
        by_track = {}
        by_type = {}
        for t in theses:
            by_state[t.get("state", "unknown")] = by_state.get(t.get("state", "unknown"), 0) + 1
            for tr in t.get("tracks", []):
                by_track[tr] = by_track.get(tr, 0) + 1
            tt = t.get("thesis_type", "unknown")
            by_type[tt] = by_type.get(tt, 0) + 1
        return {
            "total": len(theses),
            "by_state": by_state,
            "by_track": by_track,
            "by_type": by_type,
            "last_updated": self.registry.get("last_updated", ""),
        }

    # ---------- persistence ----------
    def save(self):
        self.registry["last_updated"] = shanghai_today()
        self.registry_path.write_text(
            json.dumps(self.registry, ensure_ascii=False, indent=2),
            encoding="utf-8")


def _max_confidence(a: str, b: str) -> str:
    order = ["Low", "Low-Medium", "Medium", "Medium-High", "High"]
    ia = order.index(a) if a in order else 1
    ib = order.index(b) if b in order else 1
    return order[max(ia, ib)]


def _days_between(d1: str, d2: str) -> int:
    try:
        date1 = datetime.datetime.strptime(d1, "%Y-%m-%d").date()
        date2 = datetime.datetime.strptime(d2, "%Y-%m-%d").date()
        return abs((date2 - date1).days)
    except ValueError:
        return 0


# ---------- CLI ----------
def cmd_query(args, reg: Registry):
    if args.id:
        result = reg.get_by_id(args.id)
        results = [result] if result else []
    elif args.track:
        results = reg.query_by_track(args.track)
    elif args.section:
        results = reg.query_by_section(args.section)
    elif args.state:
        results = reg.query_by_state(args.state)
    elif args.change_type:
        results = reg.query_by_change_type(args.change_type)
    elif args.entity:
        results = reg.query_by_entity(args.entity)
    elif args.search:
        results = reg.search(args.search)
    else:
        results = reg.all_theses()

    print(json.dumps(results, ensure_ascii=False, indent=2))


def cmd_ingest(args, reg: Registry):
    event = load_json(Path(args.event_file))
    t = reg.ingest_event(event, run_date=args.run_date)
    reg.save()
    print(f"[ingest] thesis {t['id']} ({t.get('state')}) — {t['name']}")


def cmd_update(args, reg: Registry):
    result = reg.run_lifecycle(run_date=args.run_date)
    reg.save()
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_merge(args, reg: Registry):
    result = reg.merge_theses(args.source, args.target, run_date=args.run_date)
    reg.save()
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_stats(args, reg: Registry):
    print(json.dumps(reg.stats(), ensure_ascii=False, indent=2))


def cmd_convergence(args, reg: Registry):
    """读一个 event JSON，输出可能与之跨时间收敛的历史 thesis。"""
    event = load_json(Path(args.event_file))
    hits = reg.query_for_convergence(event)
    print(json.dumps(hits, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Thesis Registry · query / ingest / update")
    sub = parser.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("query", help="查询 thesis")
    q.add_argument("--id")
    q.add_argument("--track")
    q.add_argument("--section")
    q.add_argument("--state")
    q.add_argument("--change-type")
    q.add_argument("--entity")
    q.add_argument("--search")

    ing = sub.add_parser("ingest", help="写入一个事件（创建或更新 thesis）")
    ing.add_argument("--event-file", required=True, help="event JSON 路径")
    ing.add_argument("--run-date", default=shanghai_today())

    upd = sub.add_parser("update", help="运行生命周期迁移")
    upd.add_argument("--run-date", default=shanghai_today())

    mrg = sub.add_parser("merge", help="合并 thesis")
    mrg.add_argument("--source", required=True)
    mrg.add_argument("--target", required=True)
    mrg.add_argument("--run-date", default=shanghai_today())

    sub.add_parser("stats", help="registry 统计")

    cvg = sub.add_parser("convergence", help="查询与某事件可能收敛的历史 thesis")
    cvg.add_argument("--event-file", required=True)

    args = parser.parse_args()
    reg = Registry()

    if args.cmd == "query":
        cmd_query(args, reg)
    elif args.cmd == "ingest":
        cmd_ingest(args, reg)
    elif args.cmd == "update":
        cmd_update(args, reg)
    elif args.cmd == "merge":
        cmd_merge(args, reg)
    elif args.cmd == "stats":
        cmd_stats(args, reg)
    elif args.cmd == "convergence":
        cmd_convergence(args, reg)


if __name__ == "__main__":
    main()


