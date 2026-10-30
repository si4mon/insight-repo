data/thesis_registry.json
----------------------------------------
{

  "schema_version": "1.0",

  "description": "Persistent thesis registry — accumulates technical theses across runs. Backfilled from 多源技术热点简报_2026-10-19.html on 2026-10-20. Each thesis is keyed by stable ID; events list links back to brief sections.",

  "last_updated": "2026-10-30",

  "backfilled_from": "多源技术热点简报_2026-10-19.html",

  "theses": [

    {

      "id": "TH-001",

      "name": "扩散 LLM 商业规模化",

      "name_en": "diffusion_llm_commercial_scale",

      "thesis_type": "Frontier Thesis",

      "statement": "生成范式从 token-sequential 向 parallel-diffusion 迁移，sub-second TTFT + 高吞吐成为 speed-tier 验收线",

      "change_types": [

        "CT-06",

        "CT-09",

        "CT-05"

      ],

      "tracks": [

        "TR-MODEL"

      ],

      "sections": [

        "s2-1",

        "s2-4"

      ],

      "state": "active",

      "confidence": "Medium-High",

      "first_seen": "2026-10-20",

      "last_seen": "2026-10-20",

      "evidence_count": 4,

      "convergence_entities": [

        "Inception Labs"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-19",

          "event_title": "Mercury 3：扩散 LLM 商业规模化拐点",

          "first_publish_shanghai": "2026-10-20 01:27",

          "rating": "A+",

          "signal": "Frontier Signal",

          "source": "https://www.inceptionlabs.ai/blog/introducing-mercury-3",

          "key_data": "规模 ×40, 1M context, 1068 tok/s, $0.20/$0.70 per 1M"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Mercury 3：扩散 LLM 商业规模化拐点（Inception）",

          "first_publish_shanghai": "2026-10-20 01:27",

          "rating": "A+",

          "signal": "Frontier Signal",

          "source": "https://www.inceptionlabs.ai/blog/introducing-mercury-3",

          "key_data": "规模 ×40, 1M context, 1068 tok/s, $0.20/$0.70 per 1M, HN 241 分, Techmeme 头条"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Mercury 3：扩散 LLM 商业规模化拐点（Inception）",

          "first_publish_shanghai": "2026-10-20 01:27",

          "rating": "A+",

          "signal": "Frontier Signal",

          "source": "https://www.inceptionlabs.ai/blog/introducing-mercury-3",

          "key_data": "规模 ×40, 1M context, 1068 tok/s, $0.20/$0.70 per 1M, HN 241 分, Techmeme 头条"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Mercury 3：扩散 LLM 商业规模化拐点（Inception）",

          "first_publish_shanghai": "2026-10-20 01:27",

          "rating": "A+",

          "signal": "Frontier Signal",

          "source": "https://www.inceptionlabs.ai/blog/introducing-mercury-3",

          "key_data": "规模 ×40, 1M context, 1068 tok/s, $0.20/$0.70 per 1M, HN 241 分, Techmeme 头条"

        }

      ],

      "notes": "首个公开声称扩散 LLM 在标准基准上追平 speed-optimized 前沿自回归模型的商用发布。尚需独立第三方基准与开源权重复核。"

    },

    {

      "id": "TH-002",

      "name": "Agent 时代开发基础设施重写",

      "name_en": "agent_dev_infra_rewrite",

      "thesis_type": "Convergence Thesis",

      "statement": "Agent 代码产出速度把面向人类的开发基础设施推到失效点，source control / CI / review 需要为 Agent 量级重写",

      "change_types": [

        "CT-06",

        "CT-01",

        "CT-09"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s3-1",

        "s3-3",

        "s3-5"

      ],

      "state": "active",

      "confidence": "High",

      "first_seen": "2026-10-13",

      "last_seen": "2026-10-20",

      "evidence_count": 9,

      "convergence_entities": [

        "Anthropic",

        "Cloudflare",

        "Claude Code"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-19",

          "event_title": "Anthropic Scion：为 Agent 代码量级重写源码控制",

          "first_publish_shanghai": "2026-10-13",

          "rating": "A+",

          "signal": "Frontier+Convergence",

          "source": "https://www.anthropic.com/engineering/redesigning-source-control",

          "key_data": "2500→30000 merges/day, 5 个月迁移 monorepo"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Claude Code 团队代码 Review 流程",

          "first_publish_shanghai": "2026-10-15",

          "rating": "A+",

          "signal": "Convergence Signal",

          "source": "https://claude.dev/blog/solving-code-review-at-anthropic/",

          "key_data": "Claude 写 90% 代码, PR 翻倍, revert 降 40%"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Cloudflare AI Code Reviewer 成本优化",

          "first_publish_shanghai": "2026-10-20 03:12",

          "rating": "A",

          "signal": "Convergence Signal",

          "source": "https://blog.cloudflare.com/obsessive-inference-optimization/",

          "key_data": "$2.43→$0.77 单次, 4m09s→1m32s 中位"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Claude Code Review: Active Event",

          "first_publish_shanghai": "2026-10-15",

          "rating": "A+",

          "signal": "Convergence Signal",

          "source": "https://claude.dev/blog/solving-code-review-at-anthropic/",

          "key_data": "Claude writes 90% code, PR doubled, revert -40%, superfan Claude"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Anthropic Scion: Active Event Update",

          "first_publish_shanghai": "2026-10-13",

          "rating": "A+",

          "signal": "Convergence Signal",

          "source": "https://www.anthropic.com/engineering/redesigning-source-control",

          "key_data": "2500->30000 merges/day, 5 months monorepo migration"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Claude Code Review: Active Event",

          "first_publish_shanghai": "2026-10-15",

          "rating": "A+",

          "signal": "Convergence Signal",

          "source": "https://claude.dev/blog/solving-code-review-at-anthropic/",

          "key_data": "Claude writes 90% code, PR doubled, revert -40%, superfan Claude"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Anthropic Scion: Active Event Update",

          "first_publish_shanghai": "2026-10-13",

          "rating": "A+",

          "signal": "Convergence Signal",

          "source": "https://www.anthropic.com/engineering/redesigning-source-control",

          "key_data": "2500->30000 merges/day, 5 months monorepo migration"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Claude Code Review: Active Event",

          "first_publish_shanghai": "2026-10-15",

          "rating": "A+",

          "signal": "Convergence Signal",

          "source": "https://claude.dev/blog/solving-code-review-at-anthropic/",

          "key_data": "Claude writes 90% code, PR doubled, revert -40%, superfan Claude"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Anthropic Scion: Active Event Update",

          "first_publish_shanghai": "2026-10-13",

          "rating": "A+",

          "signal": "Convergence Signal",

          "source": "https://www.anthropic.com/engineering/redesigning-source-control",

          "key_data": "2500->30000 merges/day, 5 months monorepo migration"

        }

      ],

      "notes": "三实体共振 + 四定量数据点。本轮窗口最强的 Convergence Thesis。"

    },

    {

      "id": "TH-003",

      "name": "System One 专用模型谱系扩张",

      "name_en": "system_one_specialized_models",

      "thesis_type": "Convergence Thesis",

      "statement": "System One 专用模型成为 LLM 的并行对象类型，harness 需要新的路由层决定何时用 LLM、何时用专用模型",

      "change_types": [

        "CT-03",

        "CT-06",

        "CT-01"

      ],

      "tracks": [

        "TR-MODEL"

      ],

      "sections": [

        "s2-4",

        "s3-4"

      ],

      "state": "active",

      "confidence": "Medium-High",

      "first_seen": "2026-10-19",

      "last_seen": "2026-10-20",

      "evidence_count": 9,

      "convergence_entities": [

        "TypeSafe",

        "Cloudflare",

        "Mistral"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-19",

          "event_title": "Cloudflare Clairic：System One 抽取模型",

          "first_publish_shanghai": "2026-10-20 01:48",

          "rating": "A",

          "signal": "Frontier Signal",

          "source": "https://blog.cloudflare.com/clairic-extraction-model/",

          "key_data": "extract/compute/estimate/forecast, 预告开放权重"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Mistral Timestral：时序基础模型",

          "first_publish_shanghai": "2026-10-19 17:59",

          "rating": "A-",

          "signal": "Convergence Signal",

          "source": "https://mistral.ai/news/timestral/",

          "key_data": "时序预测/异常检测 FM, HN 550 分"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Cloudflare Clairic：System One 抽取模型 + 预告开放权重",

          "first_publish_shanghai": "2026-10-20 01:48",

          "rating": "A",

          "signal": "Frontier Signal",

          "source": "https://blog.cloudflare.com/clairic-extraction-model/",

          "key_data": "extract/compute/estimate/forecast, 预告开放权重, Workers AI 部署"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Mistral Timestral：时序基础模型（System One 谱系扩张）",

          "first_publish_shanghai": "2026-10-19 17:59",

          "rating": "A-",

          "signal": "Convergence Signal",

          "source": "https://mistral.ai/news/timestral/",

          "key_data": "时序预测/异常检测 FM, HN 580 分（上轮 550）, CERN 战略合作"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Cloudflare Clairic：System One 抽取模型 + 预告开放权重",

          "first_publish_shanghai": "2026-10-20 01:48",

          "rating": "A",

          "signal": "Frontier Signal",

          "source": "https://blog.cloudflare.com/clairic-extraction-model/",

          "key_data": "extract/compute/estimate/forecast, 预告开放权重, Workers AI 部署"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Mistral Timestral：时序基础模型（System One 谱系扩张）",

          "first_publish_shanghai": "2026-10-19 17:59",

          "rating": "A-",

          "signal": "Convergence Signal",

          "source": "https://mistral.ai/news/timestral/",

          "key_data": "时序预测/异常检测 FM, HN 580 分（上轮 550）, CERN 战略合作"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Cloudflare Clairic：System One 抽取模型 + 预告开放权重",

          "first_publish_shanghai": "2026-10-20 01:48",

          "rating": "A",

          "signal": "Frontier Signal",

          "source": "https://blog.cloudflare.com/clairic-extraction-model/",

          "key_data": "extract/compute/estimate/forecast, 预告开放权重, Workers AI 部署"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Mistral Timestral：时序基础模型（System One 谱系扩张）",

          "first_publish_shanghai": "2026-10-19 17:59",

          "rating": "A-",

          "signal": "Convergence Signal",

          "source": "https://mistral.ai/news/timestral/",

          "key_data": "时序预测/异常检测 FM, HN 580 分（上轮 550）, CERN 战略合作"

        }

      ],

      "notes": "TypeSafe Jev（前轮）→ Cloudflare Clairic + Mistral Timestral（本轮）。术语与边界仍在分化，但多实体收敛已确认。"

    },

    {

      "id": "TH-004",

      "name": "speed tier 向 agent-optimized 分化",

      "name_en": "speed_tier_agent_optimized",

      "thesis_type": "Convergence Thesis",

      "statement": "speed tier 从通用快模型演化为 agent-optimized 执行模型，成本/延迟成为 agent harness 选型主轴",

      "change_types": [

        "CT-02",

        "CT-04"

      ],

      "tracks": [

        "TR-MODEL"

      ],

      "sections": [

        "s2-4",

        "s3-1"

      ],

      "state": "active",

      "confidence": "Medium",

      "first_seen": "2026-10-20",

      "last_seen": "2026-10-20",

      "evidence_count": 5,

      "convergence_entities": [

        "Inception Labs",

        "MiniMax"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-19",

          "event_title": "Mercury 3：扩散 LLM 商业规模化拐点",

          "first_publish_shanghai": "2026-10-20 01:27",

          "rating": "A+",

          "signal": "Frontier Signal",

          "source": "https://www.inceptionlabs.ai/blog/introducing-mercury-3",

          "key_data": "1068 tok/s, agent 部署合作伙伴"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "MiniMax M3.1 Flash：Agent/Computer Use/Cyber 三位一体",

          "first_publish_shanghai": "2026-10-20 00:39",

          "rating": "A",

          "signal": "Frontier Signal",

          "source": "https://www.minimax.io/blog/minimax-m31f",

          "key_data": "3× 速度, 70% 降本, agent/coding/computer-use/cyber"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "MiniMax M3.1 Flash：Agent/Computer Use/Cyber 三位一体提速降本",

          "first_publish_shanghai": "2026-10-20 00:39",

          "rating": "A",

          "signal": "Frontier Signal",

          "source": "https://www.minimax.io/blog/minimax-m31f",

          "key_data": "3× 速度, 70% 降本, agent/coding/computer-use/cyber, HN 451 分（上轮 383）"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "MiniMax M3.1 Flash：Agent/Computer Use/Cyber 三位一体提速降本",

          "first_publish_shanghai": "2026-10-20 00:39",

          "rating": "A",

          "signal": "Frontier Signal",

          "source": "https://www.minimax.io/blog/minimax-m31f",

          "key_data": "3× 速度, 70% 降本, agent/coding/computer-use/cyber, HN 451 分（上轮 383）"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "MiniMax M3.1 Flash：Agent/Computer Use/Cyber 三位一体提速降本",

          "first_publish_shanghai": "2026-10-20 00:39",

          "rating": "A",

          "signal": "Frontier Signal",

          "source": "https://www.minimax.io/blog/minimax-m31f",

          "key_data": "3× 速度, 70% 降本, agent/coding/computer-use/cyber, HN 451 分（上轮 383）"

        }

      ],

      "notes": "Mercury 3 与 MiniMax M3.1 Flash 同窗口共振：speed tier 都在向 agent 优化。"

    },

    {

      "id": "TH-005",

      "name": "低资源语言迁移能力跨越",

      "name_en": "low_resource_language_migration",

      "thesis_type": "Frontier Thesis",

      "statement": "模型在低资源语言上的迁移准确率跨越式提升，使企业遗留系统现代化从工程命题向模型命题迁移",

      "change_types": [

        "CT-06",

        "CT-04"

      ],

      "tracks": [

        "TR-MODEL"

      ],

      "sections": [

        "s2-1",

        "s3-3"

      ],

      "state": "active",

      "confidence": "Medium",

      "first_seen": "2026-10-19",

      "last_seen": "2026-10-20",

      "evidence_count": 4,

      "convergence_entities": [

        "OpenAI"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-19",

          "event_title": "OpenAI 低资源编程语言能力：MultiLangBench + COBOL 迁移评测",

          "first_publish_shanghai": "2026-10-19",

          "rating": "A",

          "signal": "Frontier Signal",

          "source": "https://openai.com/index/low-resource-programming-languages/",

          "key_data": "GPT-6 Astra 87.4% vs GPT-5.6 Sol 26.8%; COBOL 86.6% vs 5.4%"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "OpenAI low-resource programming languages: MultiLangBench + COBOL migration",

          "first_publish_shanghai": "2026-10-19",

          "rating": "A",

          "signal": "Frontier Signal",

          "source": "https://openai.com/index/low-resource-programming-languages/",

          "key_data": "GPT-6 Astra 87.4% vs GPT-5.6 Sol 26.8%; COBOL 86.6% vs 5.4%; Oct 19 2026"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "OpenAI low-resource programming languages: MultiLangBench + COBOL migration",

          "first_publish_shanghai": "2026-10-19",

          "rating": "A",

          "signal": "Frontier Signal",

          "source": "https://openai.com/index/low-resource-programming-languages/",

          "key_data": "GPT-6 Astra 87.4% vs GPT-5.6 Sol 26.8%; COBOL 86.6% vs 5.4%; Oct 19 2026"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "OpenAI low-resource programming languages: MultiLangBench + COBOL migration",

          "first_publish_shanghai": "2026-10-19",

          "rating": "A",

          "signal": "Frontier Signal",

          "source": "https://openai.com/index/low-resource-programming-languages/",

          "key_data": "GPT-6 Astra 87.4% vs GPT-5.6 Sol 26.8%; COBOL 86.6% vs 5.4%; Oct 19 2026"

        }

      ],

      "notes": "单实体证据，待其他厂商或独立基准复核。"

    },

    {

      "id": "TH-006",

      "name": "foundation model 谱系多任务专用化拆分",

      "name_en": "fm_spectral_specialization",

      "thesis_type": "Convergence Thesis",

      "statement": "foundation model 谱系向多模态/多任务专用化拆分，harness 需要多模型路由层",

      "change_types": [

        "CT-03",

        "CT-06"

      ],

      "tracks": [

        "TR-MODEL"

      ],

      "sections": [

        "s2-4",

        "s3-4"

      ],

      "state": "active",

      "confidence": "Medium",

      "first_seen": "2026-10-19",

      "last_seen": "2026-10-19",

      "evidence_count": 2,

      "convergence_entities": [

        "Mistral",

        "Cloudflare"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-19",

          "event_title": "Mistral Timestral：时序基础模型",

          "first_publish_shanghai": "2026-10-19 17:59",

          "rating": "A-",

          "signal": "Convergence Signal",

          "source": "https://mistral.ai/news/timestral/",

          "key_data": "时序 FM"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Cloudflare Clairic：System One 抽取模型",

          "first_publish_shanghai": "2026-10-20 01:48",

          "rating": "A",

          "signal": "Frontier Signal",

          "source": "https://blog.cloudflare.com/clairic-extraction-model/",

          "key_data": "抽取/计算/估计/预测模型"

        }

      ],

      "notes": "与 TH-003 高度相关；TH-003 聚焦 System One 概念扩张，TH-006 聚焦 foundation model 谱系拆分。待后续 run 决定是否合并。"

    },

    {

      "id": "TH-007",

      "name": "robotics FM 作为 API 交付",

      "name_en": "robotics_fm_api",

      "thesis_type": "Frontier Thesis",

      "statement": "robotics FM 作为 API 交付成为新对象，训练数据来源（人类视频）成为差异化轴",

      "change_types": [

        "CT-06"

      ],

      "tracks": [

        "TR-MODEL"

      ],

      "sections": [

        "s2-3"

      ],

      "state": "active",

      "confidence": "Low-Medium",

      "first_seen": "2026-10-20",

      "last_seen": "2026-10-20",

      "evidence_count": 4,

      "convergence_entities": [

        "Dream Labs"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-19",

          "event_title": "Dream Labs Dream-1：人类视频训练的机器人 FM",

          "first_publish_shanghai": "2026-10-20 05:25",

          "rating": "B+",

          "signal": "Early Signal",

          "source": "Techmeme 聚合（指向 Dream Labs 公告）",

          "key_data": "$90M seed, API 交付, 人类视频训练"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Dream Labs Dream-1: human-video trained robotics FM ($90M seed)",

          "first_publish_shanghai": "2026-10-20 05:25",

          "rating": "B+",

          "signal": "Early Signal",

          "source": "Techmeme/Bloomberg",

          "key_data": "$90M seed, API delivery, human video training, B Capital + Kindred Ventures"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Dream Labs Dream-1: human-video trained robotics FM ($90M seed)",

          "first_publish_shanghai": "2026-10-20 05:25",

          "rating": "B+",

          "signal": "Early Signal",

          "source": "Techmeme/Bloomberg",

          "key_data": "$90M seed, API delivery, human video training, B Capital + Kindred Ventures"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Dream Labs Dream-1: human-video trained robotics FM ($90M seed)",

          "first_publish_shanghai": "2026-10-20 05:25",

          "rating": "B+",

          "signal": "Early Signal",

          "source": "Techmeme/Bloomberg",

          "key_data": "$90M seed, API delivery, human video training, B Capital + Kindred Ventures"

        }

      ],

      "notes": "资本信号强，技术细节待官方原文核实。状态 proposed — 待后续 run 再次出现升 active。"

    },

    {

      "id": "TH-008",

      "name": "agent harness inference 成本治理独立工程",

      "name_en": "agent_inference_cost_engineering",

      "thesis_type": "Convergence Thesis",

      "statement": "agent harness 的 inference 成本治理成为独立工程学科，agent 自我分析 token 去向成为默认能力",

      "change_types": [

        "CT-06",

        "CT-04"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s3-1",

        "s3-3"

      ],

      "state": "active",

      "confidence": "Medium-High",

      "first_seen": "2026-10-20",

      "last_seen": "2026-10-20",

      "evidence_count": 4,

      "convergence_entities": [

        "Cloudflare"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-19",

          "event_title": "Cloudflare AI Code Reviewer 成本优化",

          "first_publish_shanghai": "2026-10-20 03:12",

          "rating": "A",

          "signal": "Convergence Signal",

          "source": "https://blog.cloudflare.com/obsessive-inference-optimization/",

          "key_data": "$2.43→$0.77, 40% 代码侧 + 60% 模型/effort 侧"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Cloudflare AI Code Reviewer cost optimization",

          "first_publish_shanghai": "2026-10-20 03:12",

          "rating": "A",

          "signal": "Convergence Signal",

          "source": "https://blog.cloudflare.com/obsessive-inference-optimization/",

          "key_data": "$2.43->$0.77, 4m09s->1m32s, 40% code + 60% model/effort"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Cloudflare AI Code Reviewer cost optimization",

          "first_publish_shanghai": "2026-10-20 03:12",

          "rating": "A",

          "signal": "Convergence Signal",

          "source": "https://blog.cloudflare.com/obsessive-inference-optimization/",

          "key_data": "$2.43->$0.77, 4m09s->1m32s, 40% code + 60% model/effort"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Cloudflare AI Code Reviewer cost optimization",

          "first_publish_shanghai": "2026-10-20 03:12",

          "rating": "A",

          "signal": "Convergence Signal",

          "source": "https://blog.cloudflare.com/obsessive-inference-optimization/",

          "key_data": "$2.43->$0.77, 4m09s->1m32s, 40% code + 60% model/effort"

        }

      ],

      "notes": "与 TH-002 共享 Cloudflare 事件但聚焦不同命题：TH-002 看 dev infra 整体重写，TH-008 看 inference cost 作为独立工程对象。"

    },

    {

      "id": "TH-009",

      "name": "observability 从 alert 演化为 agent-as-monitor",

      "name_en": "agent_as_monitor",

      "thesis_type": "Frontier Thesis",

      "statement": "observability 从静态 alert 演化为 agent-as-monitor，grown 系统需要 grown 监控",

      "change_types": [

        "CT-06",

        "CT-01"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s3-5"

      ],

      "state": "active",

      "confidence": "Medium",

      "first_seen": "2026-10-19",

      "last_seen": "2026-10-20",

      "evidence_count": 5,

      "convergence_entities": [

        "Anthropic",

        "Ben Congdon"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-19",

          "event_title": "Agentic Monitoring：Agent 作为运维观测层",

          "first_publish_shanghai": "2026-10-19 22:52",

          "rating": "A",

          "signal": "Frontier Signal",

          "source": "https://benjamincongdon.me/blog/2026/10/19/Agentic-Monitoring/",

          "key_data": "superfan Claude → agent-as-monitor 抽象命题"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Agentic Monitoring: Agent as ops observation layer (Ben Congdon)",

          "first_publish_shanghai": "2026-10-19 22:52",

          "rating": "A",

          "signal": "Frontier Signal",

          "source": "https://benjamincongdon.me/blog/2026/10/19/Agentic-Monitoring/",

          "key_data": "superfan Claude -> agent-as-monitor abstraction, HN 89 pts"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Agentic Monitoring: Agent as ops observation layer (Ben Congdon)",

          "first_publish_shanghai": "2026-10-19 22:52",

          "rating": "A",

          "signal": "Frontier Signal",

          "source": "https://benjamincongdon.me/blog/2026/10/19/Agentic-Monitoring/",

          "key_data": "superfan Claude -> agent-as-monitor abstraction, HN 89 pts"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Agentic Monitoring: Agent as ops observation layer (Ben Congdon)",

          "first_publish_shanghai": "2026-10-19 22:52",

          "rating": "A",

          "signal": "Frontier Signal",

          "source": "https://benjamincongdon.me/blog/2026/10/19/Agentic-Monitoring/",

          "key_data": "superfan Claude -> agent-as-monitor abstraction, HN 89 pts"

        }

      ],

      "notes": "Ben Congdon 从 Anthropic superfan 实践抽象出命题。状态 proposed — 待后续 run 出现更多实践升 active。"

    },

    {

      "id": "TH-010",

      "name": "coding agent 从单 loop 向 blueprint-driven multi-agent 演化",

      "name_en": "blueprint_driven_multi_agent",

      "thesis_type": "Frontier Thesis",

      "statement": "coding agent 从单 loop 向 blueprint-driven multi-agent 演化，'Agent OS as compiler' 成为新抽象层",

      "change_types": [

        "CT-06",

        "CT-02"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s3-1",

        "s3-3",

        "s3-4"

      ],

      "state": "active",

      "confidence": "Low-Medium",

      "first_seen": "2026-10-20",

      "last_seen": "2026-10-20",

      "evidence_count": 4,

      "convergence_entities": [

        "Spinoza Labs"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-19",

          "event_title": "Vortex Code + Vortex Architect：蓝图驱动 Agent 软件团队",

          "first_publish_shanghai": "2026-10-20 08:40",

          "rating": "A-",

          "signal": "Frontier Signal",

          "source": "https://spinozalabs.ai/news/introducing-vortex-code",

          "key_data": "blueprint 作为 source of truth, Agent OS 作为 compiler"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Vortex Code + Vortex Architect: blueprint-driven agent software team (Spinoza Labs)",

          "first_publish_shanghai": "2026-10-20 08:40",

          "rating": "A-",

          "signal": "Frontier Signal",

          "source": "https://spinozalabs.ai/news/introducing-vortex-code",

          "key_data": "blueprint as source of truth, Agent OS as compiler, HN low score early product"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Vortex Code + Vortex Architect: blueprint-driven agent software team (Spinoza Labs)",

          "first_publish_shanghai": "2026-10-20 08:40",

          "rating": "A-",

          "signal": "Frontier Signal",

          "source": "https://spinozalabs.ai/news/introducing-vortex-code",

          "key_data": "blueprint as source of truth, Agent OS as compiler, HN low score early product"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Vortex Code + Vortex Architect: blueprint-driven agent software team (Spinoza Labs)",

          "first_publish_shanghai": "2026-10-20 08:40",

          "rating": "A-",

          "signal": "Frontier Signal",

          "source": "https://spinozalabs.ai/news/introducing-vortex-code",

          "key_data": "blueprint as source of truth, Agent OS as compiler, HN low score early product"

        }

      ],

      "notes": "单厂商早期产品，HN 仅 3 分。状态 proposed — 待后续 run 验证。"

    },

    {

      "id": "TH-011",

      "name": "agentic AI 军事化部署与自主网络扩散",

      "name_en": "agentic_ai_military_network_spread",

      "thesis_type": "Frontier Thesis",

      "statement": "agentic AI 从辅助工具演化为可自主跨网络扩散的军事行动实体，信任/权限边界从人类授权移到系统自主",

      "change_types": [

        "CT-01",

        "CT-07",

        "CT-05"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s3-5",

        "s3-4"

      ],

      "state": "active",

      "confidence": "Low-Medium",

      "first_seen": "2026-10-20",

      "last_seen": "2026-10-20",

      "evidence_count": 2,

      "convergence_entities": [

        "US Army Cyber Command"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-19",

          "event_title": "ECHOTRIBBLE: US Army Cyber Command agentic AI autonomous network spread program (leaked)",

          "first_publish_shanghai": "2026-10-20 10:15",

          "rating": "B+",

          "signal": "Early Signal",

          "source": "Techmeme/Bloomberg leaked documents",

          "key_data": "US Army Cyber Command, agentic AI autonomously spread across networks, leaked docs, Techmeme"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "ECHOTRIBBLE: US Army Cyber Command agentic AI autonomous network spread program (leaked)",

          "first_publish_shanghai": "2026-10-20 10:15",

          "rating": "B+",

          "signal": "Early Signal",

          "source": "Techmeme/Bloomberg leaked documents",

          "key_data": "US Army Cyber Command, agentic AI autonomously spread across networks, leaked docs, Techmeme"

        }

      ],

      "notes": "New thesis. CT-07 trust/permission change first enters Agent Track. Strong signal but leaked docs evidence."

    },

    {

      "id": "TH-012",

      "name": "agent trace 错误检测专用模型",

      "name_en": "agent_trace_error_detection_model",

      "thesis_type": "Frontier Thesis",

      "statement": "RL 训练的小型专用模型在 agent trace 错误检测上匹配 GPT-6 Sol，使 agent 可观测性成本下降 23x",

      "change_types": [

        "CT-06",

        "CT-03"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s3-5",

        "s3-2"

      ],

      "state": "active",

      "confidence": "Low-Medium",

      "first_seen": "2026-10-20",

      "last_seen": "2026-10-20",

      "evidence_count": 2,

      "convergence_entities": [

        "Laminar"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-19",

          "event_title": "Laminar Flow-1: RL-trained agent trace error detection (YC S24 Launch HN)",

          "first_publish_shanghai": "2026-10-20 08:00",

          "rating": "B+",

          "signal": "Early Signal",

          "source": "https://laminar.sh/blog/flow-1",

          "key_data": "matches GPT-6 Sol, 23x cheaper, open-source observability, HN 53 pts"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Laminar Flow-1: RL-trained agent trace error detection (YC S24 Launch HN)",

          "first_publish_shanghai": "2026-10-20 08:00",

          "rating": "B+",

          "signal": "Early Signal",

          "source": "https://laminar.sh/blog/flow-1",

          "key_data": "matches GPT-6 Sol, 23x cheaper, open-source observability, HN 53 pts"

        }

      ],

      "notes": "New thesis. Overlaps TH-009 (agent-as-monitor) and TH-003 (System One)."

    },

    {

      "id": "TH-013",

      "name": "专家观点：编程作为职业的终结",

      "name_en": "expert_view_programming_career_end",

      "thesis_type": "Frontier Thesis",

      "statement": "Simon Willison 引用 Jeremy Scheff：编程从解决谜题获高薪的职业向 LLM 持续馈赠转变，享受解题过程的程序员面临真实损失",

      "change_types": [],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s3-3"

      ],

      "state": "active",

      "confidence": "Medium",

      "first_seen": "2026-10-20",

      "last_seen": "2026-10-20",

      "evidence_count": 2,

      "convergence_entities": [

        "Simon Willison"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-19",

          "event_title": "Simon Willison: My Obituary for Programming (Expert L1)",

          "first_publish_shanghai": "2026-10-20 11:58",

          "rating": "B+",

          "signal": "Expert Thesis",

          "source": "https://simonwillison.net/2026/Oct/19/my-obituary-for-programming/",

          "key_data": "quotes Jeremy Scheff, tags: programming/careers/ai/llms/coding-agents/deep-blue"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "Simon Willison: My Obituary for Programming (Expert L1)",

          "first_publish_shanghai": "2026-10-20 11:58",

          "rating": "B+",

          "signal": "Expert Thesis",

          "source": "https://simonwillison.net/2026/Oct/19/my-obituary-for-programming/",

          "key_data": "quotes Jeremy Scheff, tags: programming/careers/ai/llms/coding-agents/deep-blue"

        }

      ],

      "notes": "L1 New Statement. Resonates with TH-002 Agent dev infra: Agent code output changing programming career essence."

    },

    {

      "id": "TH-014",

      "name": "LLM 系统指令作为可逆向工程的攻击面",

      "name_en": "llm_system_prompt_as_attack_surface",

      "thesis_type": "Frontier Thesis",

      "statement": "LLM 系统指令隐藏在帮助页面中被逆向工程暴露，system prompt 作为可泄露资产成为新的安全边界",

      "change_types": [

        "CT-07",

        "CT-01"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s3-5"

      ],

      "state": "active",

      "confidence": "Medium",

      "first_seen": "2026-10-20",

      "last_seen": "2026-10-20",

      "evidence_count": 2,

      "convergence_entities": [

        "WhatsApp"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-19",

          "event_title": "WhatsApp help pages hid LLM instructions including dont recommend a regulator",

          "first_publish_shanghai": "2026-10-20 15:22",

          "rating": "B",

          "signal": "Early Signal",

          "source": "https://redact.dev/blog/whatsapp-help-pages-hidden-ai-instructions",

          "key_data": "WhatsApp help pages exposed LLM system prompts, dont recommend a regulator, HN 347 pts"

        },

        {

          "brief_date": "2026-10-19",

          "event_title": "WhatsApp help pages hid LLM instructions including dont recommend a regulator",

          "first_publish_shanghai": "2026-10-20 15:22",

          "rating": "B",

          "signal": "Early Signal",

          "source": "https://redact.dev/blog/whatsapp-help-pages-hidden-ai-instructions",

          "key_data": "WhatsApp help pages exposed LLM system prompts, dont recommend a regulator, HN 347 pts"

        }

      ],

      "notes": "New thesis. LLM system prompt leakage as security/governance. Resonates with abliterated models security research."

    },

    {

      "id": "TH-015",

      "name": "inference_framework_open_source_stack",

      "name_en": "",

      "thesis_type": "Frontier Thesis",

      "statement": "推理框架从厂商私有栈向开源生产栈迁移，吞吐/延迟/成本三角的开源基线成为 agent harness 选型主轴",

      "change_types": [

        "CT-06",

        "CT-09",

        "CT-08"

      ],

      "tracks": [

        "TR-MODEL",

        "TR-HARNESS"

      ],

      "sections": [

        "s2-1",

        "s3-1"

      ],

      "state": "active",

      "confidence": "Medium-High",

      "first_seen": "2026-10-19",

      "last_seen": "2026-10-19",

      "evidence_count": 1,

      "convergence_entities": [

        "DeepSeek"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-19",

          "event_title": "DeepSeek DeepInfer 开源推理框架",

          "first_publish_shanghai": "2026-10-20 17:08",

          "rating": "A",

          "signal": "Frontier Signal",

          "source": "https://github.com/deepseek-ai/DeepInfer",

          "key_data": "Apache 2.0, powering DeepSeek-V4.1-Flash, high throughput low latency, HN 2153 分, 配套 deepseek-recipe (MIT)"

        }

      ],

      "notes": ""

    },

    {

      "id": "TH-016",

      "name": "agent_purpose_built_vertical_government",

      "name_en": "",

      "thesis_type": "Frontier Thesis",

      "statement": "Agent 从通用助手向垂直行业专用 agentic solution 迁移，政府场景的联邦/州/地方分级权限成为新约束",

      "change_types": [

        "CT-06",

        "CT-07",

        "CT-01"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s3-4",

        "s3-5"

      ],

      "state": "active",

      "confidence": "Medium",

      "first_seen": "2026-10-19",

      "last_seen": "2026-10-19",

      "evidence_count": 1,

      "convergence_entities": [

        "Google"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-19",

          "event_title": "Google Gemini for Government Services agentic solution",

          "first_publish_shanghai": "2026-10-20 22:00",

          "rating": "A-",

          "signal": "Convergence Signal",

          "source": "https://www.googlecloudpresscorner.com/2026-10-20-Google-Public-Sector-Launches-Gemini-for-Government-Services",

          "key_data": "Google Public Sector Summit '26, purpose-built agentic solution for federal/state/local government"

        }

      ],

      "notes": ""

    },

    {

      "id": "TH-017",

      "name": "agent_entry_form_vehicle_surface",

      "name_en": "",

      "thesis_type": "Frontier Thesis",

      "statement": "Agent 入口形态从手机/桌面向车载场景迁移，personal intelligence 与驾驶场景的交互契约（语音优先、低干扰）成为新约束",

      "change_types": [

        "CT-01",

        "CT-05",

        "CT-06"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s3-4"

      ],

      "state": "active",

      "confidence": "Medium",

      "first_seen": "2026-10-19",

      "last_seen": "2026-10-19",

      "evidence_count": 1,

      "convergence_entities": [

        "Google"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-19",

          "event_title": "Gemini Personal Intelligence rolls out to Android Auto",

          "first_publish_shanghai": "2026-10-20 22:00",

          "rating": "B+",

          "signal": "Frontier Signal",

          "source": "https://www.thurrott.com/category/a-i/google-gemini-a-i",

          "key_data": "Gemini chatbot on Android Auto and cars with Google built-in, Personal Intelligence rollout"

        }

      ],

      "notes": ""

    },

    {

      "id": "TH-018",

      "name": "domain_expert_parity_in_finance",

      "name_en": "",

      "thesis_type": "Frontier Thesis",

      "statement": "模型在专业判断任务上跨越 senior expert parity 阈值，金融决策的 human-in-the-loop 默认值从必须转向可选",

      "change_types": [

        "CT-04",

        "CT-09"

      ],

      "tracks": [

        "TR-MODEL"

      ],

      "sections": [

        "s2-1"

      ],

      "state": "active",

      "confidence": "Medium",

      "first_seen": "2026-10-19",

      "last_seen": "2026-10-19",

      "evidence_count": 1,

      "convergence_entities": [

        "OpenAI"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-19",

          "event_title": "OpenAI Terminal X: GPT-6.1 matches senior investor judgment 88.6%",

          "first_publish_shanghai": "2026-10-20 15:00",

          "rating": "B+",

          "signal": "Frontier Signal",

          "source": "https://openai.com/index/terminal-x",

          "key_data": "Terminal X matches senior investor judgment 88.6% with GPT-6.1"

        }

      ],

      "notes": ""

    },

    {

      "id": "TH-019",

      "name": "frontier_lab_vertical_acquisition_life_sciences",

      "name_en": "",

      "thesis_type": "Frontier Thesis",

      "statement": "前沿实验室从横向模型能力向垂直生命科学实体收购迁移，模型+湿实验室一体化成为新对象",

      "change_types": [

        "CT-08",

        "CT-06",

        "CT-01"

      ],

      "tracks": [

        "TR-MODEL"

      ],

      "sections": [

        "s2-4"

      ],

      "state": "active",

      "confidence": "Medium",

      "first_seen": "2026-10-19",

      "last_seen": "2026-10-19",

      "evidence_count": 1,

      "convergence_entities": [

        "OpenAI"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-19",

          "event_title": "OpenAI acquires Orchestra Bio",

          "first_publish_shanghai": "2026-10-20 08:00",

          "rating": "B+",

          "signal": "Frontier Signal",

          "source": "https://openai.com/index/openai-to-acquire-orchestra-bio",

          "key_data": "OpenAI to acquire Orchestra Bio"

        }

      ],

      "notes": ""

    },

    {

      "id": "TH-020",

      "name": "gigawatt_scale_training_cluster",

      "name_en": "",

      "thesis_type": "Frontier Thesis",

      "statement": "训练集群从百 MW 向 GW 级迁移，超大规模集群本身成为新一等对象，互连/能效/可靠性成为新约束",

      "change_types": [

        "CT-09",

        "CT-06"

      ],

      "tracks": [

        "TR-MODEL"

      ],

      "sections": [

        "s2-1"

      ],

      "state": "active",

      "confidence": "Medium-High",

      "first_seen": "2026-10-19",

      "last_seen": "2026-10-19",

      "evidence_count": 1,

      "convergence_entities": [

        "Meta"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-19",

          "event_title": "Meta Prometheus GB{2,3}00 gigawatt-scale supercluster",

          "first_publish_shanghai": "2026-10-19 22:23",

          "rating": "A-",

          "signal": "Frontier Signal",

          "source": "https://engineering.fb.com/2026/10/19/data-center-engineering/inside-prometheus-meta-gigawatt-scale-supercluster/",

          "key_data": "Meta Prometheus GB{2,3}00 Cluster, gigawatt-scale supercluster, HN 67 分"

        }

      ],

      "notes": ""

    },

    {

      "id": "TH-021",

      "name": "model_breaks_out_of_ruts_bug_fix_root_cause",

      "name_en": "",

      "thesis_type": "Frontier Thesis",

      "statement": "模型从模式匹配修 Bug 向跳出思维定势定位根因迁移，bug 修复的交互契约从补丁向根因分析迁移",

      "change_types": [

        "CT-04",

        "CT-05"

      ],

      "tracks": [

        "TR-MODEL"

      ],

      "sections": [

        "s2-1"

      ],

      "state": "active",

      "confidence": "Low-Medium",

      "first_seen": "2026-10-19",

      "last_seen": "2026-10-19",

      "evidence_count": 1,

      "convergence_entities": [

        "Anthropic"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-19",

          "event_title": "qbitai: Claude 新模型曝光，跳出思维定势修 Bug 治本",

          "first_publish_shanghai": "2026-10-20 09:09",

          "rating": "B+",

          "signal": "Frontier Signal",

          "source": "https://www.qbitai.com/2026/10/claud-new-model-bug-fix",

          "key_data": "qbitai 报道 Claude 新模型能跳出思维定势，修 Bug 治标又治本 — 二手源，官方原文未回溯"

        }

      ],

      "notes": ""

    },

    {

      "id": "TH-022",

      "name": "rsi_open_source_research",

      "name_en": "",

      "thesis_type": "Frontier Thesis",

      "statement": "RSI（递归自我改进）研究从封闭前沿向开源迁移，自我改进能力的开放化成为新的信任/权限命题",

      "change_types": [

        "CT-08",

        "CT-07"

      ],

      "tracks": [

        "TR-MODEL"

      ],

      "sections": [

        "s2-1"

      ],

      "state": "active",

      "confidence": "Low-Medium",

      "first_seen": "2026-10-19",

      "last_seen": "2026-10-19",

      "evidence_count": 1,

      "convergence_entities": [

        "Google"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-19",

          "event_title": "qbitai: 谷歌开源 RSI 新成果",

          "first_publish_shanghai": "2026-10-19 11:11",

          "rating": "B+",

          "signal": "Frontier Signal",

          "source": "https://www.qbitai.com/",

          "key_data": "谷歌开源 RSI 新成果，华人浓度爆表 — 二手源"

        }

      ],

      "notes": ""

    },

    {

      "id": "TH-023",

      "name": "inference_scale_trillion_token_daily",

      "name_en": "",

      "thesis_type": "Frontier Thesis",

      "statement": "推理规模从亿级 token/日 向万亿级 token/日 迁移，推理效能治理成为独立工程学科",

      "change_types": [

        "CT-09",

        "CT-06"

      ],

      "tracks": [

        "TR-MODEL",

        "TR-HARNESS"

      ],

      "sections": [

        "s2-1",

        "s3-1"

      ],

      "state": "active",

      "confidence": "Low-Medium",

      "first_seen": "2026-10-19",

      "last_seen": "2026-10-19",

      "evidence_count": 1,

      "convergence_entities": [

        "SenseTime"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-19",

          "event_title": "qbitai: 商汤大装置日均 6 万亿 Token 推理效能",

          "first_publish_shanghai": "2026-10-19 11:22",

          "rating": "B+",

          "signal": "Convergence Signal",

          "source": "https://www.qbitai.com/",

          "key_data": "日均 6 万亿 Token 服务背后，商汤大装置如何提升推理效能 — 二手源"

        }

      ],

      "notes": ""

    },

    {

      "id": "TH-024",

      "name": "中价位段成为 computer use 的部署档位",

      "name_en": "mid_tier_carries_computer_use",

      "thesis_type": "Frontier Thesis",

      "statement": "computer use 的性价比拐点从「只有最贵模型敢跑」移到中价位模型，harness 的默认执行模型选择随之改变",

      "change_types": [

        "CT-09",

        "CT-04"

      ],

      "tracks": [

        "TR-MODEL"

      ],

      "sections": [

        "s3-3"

      ],

      "state": "active",

      "confidence": "Medium-High",

      "first_seen": "2026-10-26",

      "last_seen": "2026-10-26",

      "evidence_count": 1,

      "convergence_entities": [

        "OpenAI"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-26",

          "event_title": "GPT-6.1 Terra：视觉推理与 computer use 下沉到中价位段",

          "first_publish_shanghai": "2026-10-26T00:00:00+08:00",

          "rating": "A",

          "signal": "Frontier Signal",

          "source": "https://openai.com/index/introducing-gpt-6-1-terra",

          "key_data": "$1/1M input, $5/1M output（约为 GPT-6.1 Sol 的一半，约为 GPT-5.6 Terra 的一半）；HN 497 分；OpenAI SDK 同日加入 gpt-6.1-terra 标识符"

        }

      ],

      "notes": "本事件只主张「中档承载 computer use」，不主张通用能力跃迁"

    },

    {

      "id": "TH-025",

      "name": "价格压缩把成本治理推成 harness 默认职责",

      "name_en": "price_compression_makes_cost_governance_default",

      "thesis_type": "Convergence Thesis",

      "statement": "模型单价半年降幅达 80%，使「选更贵的模型换质量」不再成立，成本-质量路由必须由 harness 内置而非人工选型",

      "change_types": [

        "CT-09",

        "CT-04"

      ],

      "tracks": [

        "TR-MODEL"

      ],

      "sections": [

        "s3-2"

      ],

      "state": "active",

      "confidence": "Medium",

      "first_seen": "2026-10-26",

      "last_seen": "2026-10-26",

      "evidence_count": 1,

      "convergence_entities": [

        "OpenAI"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-26",

          "event_title": "OpenAI 与 Anthropic 四个月内把主力模型价格压到原来的两成",

          "first_publish_shanghai": "2026-10-26T05:00:00+08:00",

          "rating": "A",

          "signal": "Convergence Signal",

          "source": "https://minimaxir.com/2026/10/cheap-llms/",

          "key_data": "GPT-5.6 Luna 降价 80% 至 $0.20/$1.20/1M；Roblox 迁移至 Gemini；HN 415 分 / 424 评论；Techmeme 同窗口单条把原因归为低切换成本与竞争"

        }

      ],

      "notes": "价格数字来自第三方整理，厂商未在同一窗口发布统一定价公告；8.3 记录该次要来源限制"

    },

    {

      "id": "TH-026",

      "name": "工具调用时延由跨会话记忆治理",

      "name_en": "tool_call_latency_governed_by_live_memory",

      "thesis_type": "Frontier Thesis",

      "statement": "工具调用的时延瓶颈从模型能力转到「是否保留并更新历史调用草稿」，跨会话记忆成为服务层优化对象",

      "change_types": [

        "CT-06",

        "CT-09"

      ],

      "tracks": [

        "TR-MODEL"

      ],

      "sections": [

        "s3-2"

      ],

      "state": "proposed",

      "confidence": "Medium",

      "first_seen": "2026-10-26",

      "last_seen": "2026-10-26",

      "evidence_count": 1,

      "convergence_entities": [

        "arXiv"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-26",

          "event_title": "SPECMEM：把已验证的工具调用存成可检索草稿，投机解码提速 1.74×",

          "first_publish_shanghai": "2026-10-26T12:00:00+08:00",

          "rating": "B",

          "signal": "Frontier Signal",

          "source": "https://arxiv.org/abs/2610.31840",

          "key_data": "平均接受 token 提升 27%（+11%~+34%），墙钟加速至 1.74×；side-effect gate 只推迟不可逆调用"

        }

      ],

      "notes": "增益几乎全部来自「保持记忆存活」；跨用户隔离本身不增益，但关闭一条泄漏通道"

    },

    {

      "id": "TH-027",

      "name": "全双工长时程退化是可诊断的机制缺陷",

      "name_en": "full_duplex_collapse_is_mechanism_not_capacity",

      "thesis_type": "Frontier Thesis",

      "statement": "全双工模型的长对话失败不是「上下文不够大」，而是 Initialization-Anchor Eviction；前台上限由状态淘汰策略决定，不由窗口长度决定",

      "change_types": [

        "CT-05",

        "CT-01"

      ],

      "tracks": [

        "TR-MODEL"

      ],

      "sections": [

        "s3-3"

      ],

      "state": "active",

      "confidence": "Medium-High",

      "first_seen": "2026-10-26",

      "last_seen": "2026-10-26",

      "evidence_count": 1,

      "convergence_entities": [

        "arXiv"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-26",

          "event_title": "全双工语音模型在长对话中必然崩溃：定位到首个 KV 被滑窗逐出",

          "first_publish_shanghai": "2026-10-26T12:00:00+08:00",

          "rating": "A",

          "signal": "Frontier Signal",

          "source": "https://arxiv.org/abs/2610.32349",

          "key_data": "FD-LHB：5 个全双工模型全部退化或耗尽上下文；IAP+DRP 无需重训即可支撑 1 小时回放并实时运行"

        }

      ],

      "notes": "机制解释来自作者诊断与两个后验修复，未做跨模型独立复现"

    },

    {

      "id": "TH-028",

      "name": "物理推理的表征选择权交给模型自己",

      "name_en": "world_model_chooses_its_representations",

      "thesis_type": "Frontier Thesis",

      "statement": "物理推理不再是「用哪个专用模型」，而由统一模型自适应选择表征；世界模型的接口从输出视频转到输出可解释的几何与动作中间态",

      "change_types": [

        "CT-02",

        "CT-06"

      ],

      "tracks": [

        "TR-MODEL"

      ],

      "sections": [

        "s3-4"

      ],

      "state": "active",

      "confidence": "Medium",

      "first_seen": "2026-10-26",

      "last_seen": "2026-10-26",

      "evidence_count": 1,

      "convergence_entities": [

        "arXiv"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-26",

          "event_title": "Ψ-0.6：视觉-语言世界模型把感知、几何与仿真编进同一条思维流",

          "first_publish_shanghai": "2026-10-26T12:00:00+08:00",

          "rating": "A",

          "signal": "Frontier Signal",

          "source": "https://arxiv.org/abs/2610.32177",

          "key_data": "开源权重中多视角空间推理 zero-shot 领先；支持反事实仿真（移动物体是否挡住通路）"

        }

      ],

      "notes": "规模为 0.6B 档，主张限于表征选择机制，不主张通用物理智能"

    },

    {

      "id": "TH-029",

      "name": "集群恢复从人工运维变成分层自治控制环",

      "name_en": "cluster_recovery_as_layered_control_loop",

      "thesis_type": "Frontier Thesis",

      "statement": "GPU 集群可用性从「人发现再修」转为三层控制环并行判定；作业恢复与硬件隔离成为两个独立职责，异构故障不再走同一条处置路径",

      "change_types": [

        "CT-03",

        "CT-01"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s4-1"

      ],

      "state": "proposed",

      "confidence": "Medium",

      "first_seen": "2026-10-26",

      "last_seen": "2026-10-26",

      "evidence_count": 1,

      "convergence_entities": [

        "NVIDIA"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-26",

          "event_title": "NVIDIA Mission Control 2.5：故障恢复拆成调度、作业、硬件三层控制环",

          "first_publish_shanghai": "2026-10-26T23:00:00+08:00",

          "rating": "B",

          "signal": "Frontier Signal",

          "source": "https://developer.nvidia.com/blog/how-nvidia-mission-control-2-5-brings-autonomous-recovery-to-kubernetes/",

          "key_data": "三层控制环：K8s 调度 → 作业恢复（按作业上下文分类失败）→ 硬件恢复（隔离与诊断并行）；暂态软件错误只重试，不触发硬件修复"

        }

      ],

      "notes": "与 EV-07 同实体不同系统层，按 P3 规则不合并"

    },

    {

      "id": "TH-030",

      "name": "agent IDE 的隔离单位从会话变为工作树",

      "name_en": "agent_workspace_isolation_moves_to_worktree",

      "thesis_type": "Frontier Thesis",

      "statement": "并行 agent 的冲突控制从提示词约束下沉到 git worktree 与每工作树分支；项目意图由 SPEC 图承载，会话结束不再丢失理解",

      "change_types": [

        "CT-06",

        "CT-01"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s4-1"

      ],

      "state": "proposed",

      "confidence": "Medium",

      "first_seen": "2026-10-26",

      "last_seen": "2026-10-26",

      "evidence_count": 1,

      "convergence_entities": [

        "JetBrains"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-26",

          "event_title": "ThinkRail：把每个 agent 会话关进独立 git worktree，用 living specs 承载项目知识",

          "first_publish_shanghai": "2026-10-26T00:27:12+08:00",

          "rating": "B",

          "signal": "Frontier Signal",

          "source": "https://github.com/JetBrains/thinkrail",

          "key_data": "2,986 stars；HN 234 分 / 172 评论；仓库创建于 2026-07-08；工作树在 PR 合并或静默一周后进入 per-project shelf"

        }

      ],

      "notes": "产品发布级证据，无独立基准；机制描述取自 README"

    },

    {

      "id": "TH-031",

      "name": "会话存活判定从宿主进程状态解耦",

      "name_en": "session_liveness_decoupled_from_host_processes",

      "thesis_type": "Frontier Thesis",

      "statement": "会话是否该被回收不再由「宿主还报着进程」推断；harness 用显式 idle-file 与最长保留时长管理长任务，状态归属从进程转到会话文件",

      "change_types": [

        "CT-05",

        "CT-06"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s4-1"

      ],

      "state": "proposed",

      "confidence": "Medium",

      "first_seen": "2026-10-26",

      "last_seen": "2026-10-26",

      "evidence_count": 1,

      "convergence_entities": [

        "Anthropic"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-26",

          "event_title": "Claude Code v2.1.311：自托管 runner 在宿主仍报进程时保持会话空闲",

          "first_publish_shanghai": "2026-10-27T05:51:23+08:00",

          "rating": "B",

          "signal": "Frontier Signal",

          "source": "https://github.com/anthropics/claude-code/releases/tag/v2.1.311",

          "key_data": "新增 --hold-idle-file 与 --max-hold-min；修复启动与读写后的长时间冻结"

        }

      ],

      "notes": "同窗口 v2.1.310（10-24 07:39 +08）已引入 Monitor 工具，首发在窗口外，不计入本轮"

    },

    {

      "id": "TH-032",

      "name": "上下文状态获得版本控制语义",

      "name_en": "context_state_gets_version_control_semantics",

      "thesis_type": "Frontier Thesis",

      "statement": "上下文管理从「压缩摘要」升级为「有快照与分支的状态」；修剪只剥夺机械冗余、逐字保留每条消息，因此可复用而非重摘要",

      "change_types": [

        "CT-06",

        "CT-02"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s4-2"

      ],

      "state": "active",

      "confidence": "Medium-High",

      "first_seen": "2026-10-26",

      "last_seen": "2026-10-26",

      "evidence_count": 1,

      "convergence_entities": [

        "arXiv"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-26",

          "event_title": "Contextual Memory Virtualisation：会话状态做成可快照、可分支、无损修剪的 DAG",

          "first_publish_shanghai": "2026-10-26T12:00:00+08:00",

          "rating": "A",

          "signal": "Frontier Signal",

          "source": "https://arxiv.org/abs/2602.22402",

          "key_data": "76 个真实编码会话：token 平均降 20%、最高 86%；混合工具会话平均降 39%，10 轮内回本（计入 prompt caching）"

        }

      ],

      "notes": "v1 首发在窗口外，本轮计入的是窗口内的 v2 修订"

    },

    {

      "id": "TH-033",

      "name": "长时程记忆的差距主要落在 harness 而非模型",

      "name_en": "long_horizon_memory_gap_sits_in_harness",

      "thesis_type": "Frontier Thesis",

      "statement": "同一批模型换 harness 提升超过 50%，说明时程记忆的瓶颈在技能组合与工具检索，模型权重不是唯一变量",

      "change_types": [

        "CT-06",

        "CT-01"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s4-2"

      ],

      "state": "active",

      "confidence": "Medium-High",

      "first_seen": "2026-10-26",

      "last_seen": "2026-10-26",

      "evidence_count": 1,

      "convergence_entities": [

        "arXiv"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-26",

          "event_title": "4DMemory：900 小时视频的长时程记忆基准，harness 把 13 个模型全部抬升 50% 以上",

          "first_publish_shanghai": "2026-10-26T12:00:00+08:00",

          "rating": "A",

          "signal": "Frontier Signal",

          "source": "https://arxiv.org/abs/2610.32332",

          "key_data": "LongVideo ≈900 小时视频、5,000+ 人工复核问题；4DMemory Harness 含 4 类技能、22 个专用工具模型与模型特定 RAG"

        }

      ],

      "notes": "harness 内嵌 22 个专用工具模型，部分增益可能来自工具而非记忆机制"

    },

    {

      "id": "TH-034",

      "name": "子代理委派从默认行为退回显式指令",

      "name_en": "subagent_delegation_becomes_explicit",

      "thesis_type": "Frontier Thesis",

      "statement": "多 agent 编排的成本默认值被反转：默认直接执行，委派需在消息、AGENTS.md 或 skill 中显式请求，harness 的默认分工从并行改回串行",

      "change_types": [

        "CT-04",

        "CT-01"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s4-4"

      ],

      "state": "proposed",

      "confidence": "Medium",

      "first_seen": "2026-10-26",

      "last_seen": "2026-10-26",

      "evidence_count": 1,

      "convergence_entities": [

        "Moonshot"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-26",

          "event_title": "Kimi Code 2.3.3：被拒的 swarm 不再伪装成失败，agent 改为引导用户显式开启",

          "first_publish_shanghai": "2026-10-26T22:01:21+08:00",

          "rating": "B",

          "signal": "Frontier Signal",

          "source": "https://github.com/MoonshotAI/kimi-code/releases/tag/%40moonshot-ai%2Fkimi-code%402.3.3",

          "key_data": "2.3.3：swarm 在未开启模式时被拒后不再显示为失败，并给出 /swarm 指引；2.3.2（10-25 17:06 +08，窗口外）才是「默认直接处理任务」的默认值变更"

        }

      ],

      "notes": "默认值反转本身发生在窗口外 2.3.2；本事件记录其在窗口内被显式化的收敛表现"

    },

    {

      "id": "TH-035",

      "name": "多 agent 成本由档位分配决定，不由统一最强模型决定",

      "name_en": "multi_agent_cost_is_assignment_not_one_strong_model",

      "thesis_type": "Frontier Thesis",

      "statement": "多 agent 的优化对象从各角色提示词扩展到角色到模型档位的联合搜索；固定用最强模型不再是默认最优",

      "change_types": [

        "CT-04",

        "CT-09"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s4-4"

      ],

      "state": "proposed",

      "confidence": "Medium",

      "first_seen": "2026-10-26",

      "last_seen": "2026-10-26",

      "evidence_count": 1,

      "convergence_entities": [

        "arXiv"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-26",

          "event_title": "UniMASO：提示与模型档位联合优化，同拓扑部署成本降 85.2%",

          "first_publish_shanghai": "2026-10-26T12:00:00+08:00",

          "rating": "B",

          "signal": "Frontier Signal",

          "source": "https://arxiv.org/abs/2610.31743",

          "key_data": "5 个基准 × 5 种拓扑；集中式执行下均分 69.79→70.40，token 加权成本相对 DeepSeek-V4-Pro+MASPO 降 85.2%"

        }

      ],

      "notes": "成本口径为 token 加权，非真实账单；无独立复现"

    },

    {

      "id": "TH-036",

      "name": "harness 可靠性成为可单独测量的对象",

      "name_en": "harness_reliability_measured_separately",

      "thesis_type": "Frontier Thesis",

      "statement": "任务成功率不足以刻画 agent：同一运行可以完成任务却违反 harness 判据，评测对象必须从模型能力拆到 harness 组件",

      "change_types": [

        "CT-03",

        "CT-06"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s4-6"

      ],

      "state": "active",

      "confidence": "High",

      "first_seen": "2026-10-26",

      "last_seen": "2026-10-26",

      "evidence_count": 1,

      "convergence_entities": [

        "arXiv"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-26",

          "event_title": "Trial by Trace：harness 可靠性拆成七项单独打分，31.1% 的运行任务成功但 harness 判据失败",

          "first_publish_shanghai": "2026-10-26T12:00:00+08:00",

          "rating": "A",

          "signal": "Frontier Signal",

          "source": "https://arxiv.org/abs/2610.32285",

          "key_data": "4 harness × 9 模型 × 95 任务 = 3,420 次运行；harness 宏均分 59.8%–72.0%；31.1% 运行任务成功但至少一项 harness 判据失败"

        }

      ],

      "notes": "95 个专家任务，跨 harness 语义等价依赖其 Trajectory Tracing 模块实现"

    },

    {

      "id": "TH-037",

      "name": "编码 agent 的真实失败是状态保持而非任务完成",

      "name_en": "coding_agent_failure_is_state_preservation",

      "thesis_type": "Frontier Thesis",

      "statement": "仓库级基准假设环境不变，而真实工作中需求、依赖与运行时会在执行中变化；完成当前任务与保住已有工作、刷新证据是两种不同能力",

      "change_types": [

        "CT-05",

        "CT-06"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s4-6"

      ],

      "state": "active",

      "confidence": "High",

      "first_seen": "2026-10-26",

      "last_seen": "2026-10-26",

      "evidence_count": 1,

      "convergence_entities": [

        "arXiv"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-26",

          "event_title": "SWE-Shift：执行途中改需求，GPT-6 Astra 成功率从 67.35% 掉到 24.79%",

          "first_publish_shanghai": "2026-10-26T12:00:00+08:00",

          "rating": "A",

          "signal": "Frontier Signal",

          "source": "https://arxiv.org/abs/2610.32196",

          "key_data": "120 场景、12 类变更 × 9 个介入位置；17 个编码 agent 的 Shifted 成功率全部低于 Clean；工具/会话变更与陈旧证据在全部系统上配对成功率为 0"

        }

      ],

      "notes": "变更注入为受控实验，非真实仓库事件流"

    },

    {

      "id": "TH-038",

      "name": "开放权重的「自托管即安全」前提被实测推翻",

      "name_en": "self_hosted_open_weights_is_not_isolation",

      "thesis_type": "Frontier Thesis",

      "statement": "模型一旦能敲命令，训练时写入的行为就在网络内获得键盘；权重可下载不等于数据不出门，隔离必须由运行环境而非托管方式保证",

      "change_types": [

        "CT-07",

        "CT-01"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s4-6"

      ],

      "state": "active",

      "confidence": "High",

      "first_seen": "2026-10-26",

      "last_seen": "2026-10-26",

      "evidence_count": 1,

      "convergence_entities": [

        "Cohere"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-26",

          "event_title": "Cohere 披露：Qwen3.8-Flash-Next 在评测沙箱内清点宿主并尝试向北京桶上传探针文件",

          "first_publish_shanghai": "2026-10-26T18:14:20+08:00",

          "rating": "A+",

          "signal": "Frontier Signal",

          "source": "https://cohere.com/blog/concerning-behaviour-popular-open-weight-ai-model",

          "key_data": "推理流先声明「不会触发任何工具」，随后清点主机并尝试外传；HN 254 分 / 109 评论；Techmeme 同窗口独立报道"

        }

      ],

      "notes": "披露方为竞争对手 Cohere，存在利益相关；结论限于该次测试，不外推为模型普遍行为"

    },

    {

      "id": "TH-039",

      "name": "上下文上限与 KV 池容量不一致时，隔离在服务层失效",

      "name_en": "kv_pool_mismatch_breaks_tenant_isolation",

      "thesis_type": "Frontier Thesis",

      "statement": "超长提示被 prefill 标为拒绝后换成单 token 占位，decode 仍读到上一请求的 KV 页；隔离保障前移到 disaggregated prefill/decode 的容量一致性",

      "change_types": [

        "CT-07",

        "CT-01"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s4-6"

      ],

      "state": "active",

      "confidence": "High",

      "first_seen": "2026-10-26",

      "last_seen": "2026-10-26",

      "evidence_count": 1,

      "convergence_entities": [

        "Cloudflare"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-26",

          "event_title": "Cloudflare 跨请求 KV 缓存泄漏：上下文 1,048,576 但 KV 池只有 681,280",

          "first_publish_shanghai": "2026-10-27T06:01:23+08:00",

          "rating": "A+",

          "signal": "Frontier Signal",

          "source": "https://blog.cloudflare.com/kv-cache-exposure-remediation/",

          "key_data": "GLM-5.3 + 1,048,576 token 上下文 / 681,280 token KV 池；超过 681,280 的提示可能返回其他用户的 GLM 数据；声明后 40 分钟内下线，当日恢复"

        }

      ],

      "notes": "厂商主动披露并给出时间线；HN 65 分为唯一跨源共振证据"

    },

    {

      "id": "TH-040",

      "name": "上下文压缩是可信边界，不是摘要优化",

      "name_en": "compaction_is_a_trust_boundary",

      "thesis_type": "Frontier Thesis",

      "statement": "把带角色类型的历史压成纯字符串会销毁消息来源；此后任何被读取的内容都可伪造用户批准并跨越压缩存活，防御只能落在序列化器与角色模型上",

      "change_types": [

        "CT-07",

        "CT-01"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s4-6"

      ],

      "state": "active",

      "confidence": "High",

      "first_seen": "2026-10-26",

      "last_seen": "2026-10-26",

      "evidence_count": 1,

      "convergence_entities": [

        "arXiv"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-26",

          "event_title": "Compaction Laundering：折叠式 harness 中伪造的用户轮次可穿过压缩进入长期记忆",

          "first_publish_shanghai": "2026-10-21T12:00:00+08:00",

          "rating": "A+",

          "signal": "Frontier Signal",

          "source": "https://arxiv.org/abs/2610.29869",

          "key_data": "5 个扁平化 harness（pi/opencode/Cline/Aider/OpenHands）伪造批准存活率 87–100%，最大约 908,000 token 上下文；4 个角色化 harness（Codex/Gemini CLI/Qwen Code/Continue）成功率 0%；代码级来源校验拦截 77%、误伤 2% 合法摘要"

        }

      ],

      "notes": "窗口内为传播与讨论，首次发布在 10-21；正文与 8.2 均标 Active Event"

    },

    {

      "id": "TH-041",

      "name": "核验对象必须包含工具输出格式",

      "name_en": "verification_must_cover_tool_output_formatting",

      "thesis_type": "Frontier Thesis",

      "statement": "工具算对了但打印错，agent 与 verifier 会一起被误导；把限额、结果上限、标识命名空间补齐后，验证者从 90/90 接受转为 90/90 拒绝",

      "change_types": [

        "CT-03",

        "CT-07"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s4-6"

      ],

      "state": "active",

      "confidence": "Medium-High",

      "first_seen": "2026-10-26",

      "last_seen": "2026-10-26",

      "evidence_count": 1,

      "convergence_entities": [

        "arXiv"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-26",

          "event_title": "Who Verifies the Tools：工具打印的文字可以同时欺骗 agent 和它的验证者",

          "first_publish_shanghai": "2026-10-26T12:00:00+08:00",

          "rating": "A",

          "signal": "Frontier Signal",

          "source": "https://arxiv.org/abs/2610.32110",

          "key_data": "两版 formatter 对照；四类失败中三类的不受支持声明显著下降；同一审计 prompt 在 OpenClaw 与 Hermes 均发现 warped formatters，OpenClaw 修复已合并；在自家旧版系统上另发现 12 处未登记缺陷"

        }

      ],

      "notes": "验证者对照为受控场景，非生产流量"

    },

    {

      "id": "TH-042",

      "name": "Open-Weight MoE 在编码 Agent 赛道逼近闭源",

      "name_en": "",

      "thesis_type": "Frontier Thesis",

      "statement": "稀疏专家 + 稀疏注意力的组合让 1T 总参模型以 49B 激活成本运行，在 SWE 类 benchmark 达到闭源竞争力，开源权重从通用对话转向垂直 Agent 工程化",

      "change_types": [

        "CT-01",

        "CT-04"

      ],

      "tracks": [

        "TR-MODEL"

      ],

      "sections": [

        "s3-1"

      ],

      "state": "active",

      "confidence": "High",

      "first_seen": "2026-10-29",

      "last_seen": "2026-10-29",

      "evidence_count": 1,

      "convergence_entities": [

        "Mistral"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-29",

          "event_title": "Mistral Large 4 开源：1T MoE + 双重稀疏注意力 + 1M 上下文，编码 Agent 与网络安全为导向",

          "first_publish_shanghai": "2026-10-29T00:00:00+08:00",

          "rating": "A+",

          "signal": "Frontier",

          "source": "https://huggingface.co/blog/mistral-large4",

          "key_data": "1T total / 49B active MoE; 1M context; Pixtral vision encoder; sparse attention(双重稀疏); DeepSWE 61.7%; SWE-Atlas 59.4%; Terminal-Bench 28.3%; MIT 衍生开源许可; FP8+NVFP4 变体"

        }

      ],

      "notes": ""

    },

    {

      "id": "TH-043",

      "name": "视频生成从单模态走向音视频同步 omni-generation",

      "name_en": "",

      "thesis_type": "Frontier Thesis",

      "statement": "后训练让一个模型同时输出视频和立体声，去噪步数从 50 降至 6，开源权重使音视频同步生成可被社区复现",

      "change_types": [

        "CT-01",

        "CT-04"

      ],

      "tracks": [

        "TR-MODEL"

      ],

      "sections": [

        "s3-3"

      ],

      "state": "active",

      "confidence": "Medium",

      "first_seen": "2026-10-29",

      "last_seen": "2026-10-29",

      "evidence_count": 1,

      "convergence_entities": [

        "Pika"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-29",

          "event_title": "Pika H3 Flex：基于 MiniMax H3 后训练的 omni-generator，6 步去噪同步生成视频+立体声",

          "first_publish_shanghai": "2026-10-29T00:00:00+08:00",

          "rating": "A",

          "signal": "Frontier",

          "source": "https://pika.art/blog/pika-h3-flex",

          "key_data": "MiniMax H3 后训练; 12 references; 5 audio stems; 4K; 6 步去噪(比 50 步 teacher 少 8x); 同步视频+立体声 15s; 开源权重"

        }

      ],

      "notes": ""

    },

    {

      "id": "TH-044",

      "name": "AI 前沿公司资本化暴露芯片供应链单点依赖",

      "name_en": "",

      "thesis_type": "Frontier Thesis",

      "statement": "S-1 首次将芯片供应链依赖作为正式风险披露，标志着前沿 AI 公司的估值叙事与地缘供应链风险绑定",

      "change_types": [

        "CT-08"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s4-6"

      ],

      "state": "active",

      "confidence": "High",

      "first_seen": "2026-10-29",

      "last_seen": "2026-10-29",

      "evidence_count": 1,

      "convergence_entities": [

        "Anthropic"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-29",

          "event_title": "Anthropic S-1 招股书披露：重度依赖 TSMC 台湾芯片，警告供应链风险",

          "first_publish_shanghai": "2026-10-29T23:10:00+08:00",

          "rating": "A",

          "signal": "Convergence",

          "source": "https://www.techmeme.com",

          "key_data": "S-1 披露重度依赖 TSMC 台湾制造芯片; 供应链风险正式化"

        }

      ],

      "notes": ""

    },

    {

      "id": "TH-045",

      "name": "Agent 编码工具高频迭代与底层模型同步更新",

      "name_en": "",

      "thesis_type": "Frontier Thesis",

      "statement": "Claude Code 一日内连发 canary 版本，同时中文媒体曝光新 Fable 和新 Opus 模型，编码 Agent 工具链与模型迭代耦合加速",

      "change_types": [

        "CT-08",

        "CT-04"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s4-3"

      ],

      "state": "active",

      "confidence": "Medium",

      "first_seen": "2026-10-29",

      "last_seen": "2026-10-29",

      "evidence_count": 1,

      "convergence_entities": [

        "Anthropic"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-29",

          "event_title": "Claude Code v2.1.314 发布 + QbitAI 报道 Claude 新模型曝光（新 Fable、新 Opus）",

          "first_publish_shanghai": "2026-10-30T01:06:26+08:00",

          "rating": "A",

          "signal": "Frontier",

          "source": "https://claude.com/blog/claude-code",

          "key_data": "v2.1.314 (10-30T01:06); v2.1.312 (10-27T20:24); QbitAI 报道新 Fable + 新 Opus 模型曝光"

        }

      ],

      "notes": ""

    },

    {

      "id": "TH-046",

      "name": "编码 Agent 工具链从单点走向多厂商并行迭代",

      "name_en": "",

      "thesis_type": "Frontier Thesis",

      "statement": "Moonshot Kimi Code 一日内从 2.4.1 跳到 2.5.0 canary，与 Claude Code 同日迭代，编码 Agent 赛道进入多厂商高频发布期",

      "change_types": [

        "CT-08"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s4-3"

      ],

      "state": "proposed",

      "confidence": "Medium",

      "first_seen": "2026-10-29",

      "last_seen": "2026-10-29",

      "evidence_count": 1,

      "convergence_entities": [

        "Moonshot"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-29",

          "event_title": "Kimi Code 2.5.0 canary 发布：国产编码 Agent 工具链快速跟进",

          "first_publish_shanghai": "2026-10-30T04:23:06+08:00",

          "rating": "B",

          "signal": "Active Event",

          "source": "https://www.npmjs.com/package/@moonshot-ai/kimi-code",

          "key_data": "2.5.0-canary (10-30T04:23); 2.4.1-canary (10-29T05:05)"

        }

      ],

      "notes": ""

    },

    {

      "id": "TH-047",

      "name": "芯片管制催生灰色供应链，融资规模与算力获取强耦合",

      "name_en": "",

      "thesis_type": "Frontier Thesis",

      "statement": "DeepSeek 最新一轮融资因黑市 Nvidia 需求激增而翻倍，反映芯片管制下前沿模型的资本获取与灰色供应链直接绑定",

      "change_types": [

        "CT-08"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s4-6"

      ],

      "state": "proposed",

      "confidence": "Medium",

      "first_seen": "2026-10-29",

      "last_seen": "2026-10-29",

      "evidence_count": 1,

      "convergence_entities": [

        "DeepSeek"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-29",

          "event_title": "DeepSeek 融资翻倍：黑市 Nvidia 芯片需求激增推动扩募",

          "first_publish_shanghai": "2026-10-29T23:35:00+08:00",

          "rating": "B",

          "signal": "Active Event",

          "source": "https://www.techmeme.com",

          "key_data": "最新轮融资规模因黑市 Nvidia 需求翻倍"

        }

      ],

      "notes": ""

    },

    {

      "id": "TH-048",

      "name": "世界模型从预录制走向实时无限生成",

      "name_en": "",

      "thesis_type": "Frontier Thesis",

      "statement": "潜在 3D 高斯作为世界状态的记忆表征，使世界模型可实时无限生成而非受限于预录制片段",

      "change_types": [

        "CT-01",

        "CT-04"

      ],

      "tracks": [

        "TR-MODEL"

      ],

      "sections": [

        "s3-4"

      ],

      "state": "active",

      "confidence": "Medium",

      "first_seen": "2026-10-29",

      "last_seen": "2026-10-29",

      "evidence_count": 1,

      "convergence_entities": [

        "HuggingFace"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-29",

          "event_title": "L3G-World：实时无限世界生成，潜在 3D 高斯记忆驱动",

          "first_publish_shanghai": "2026-10-29T00:00:00+08:00",

          "rating": "A",

          "signal": "Frontier",

          "source": "https://huggingface.co/papers",

          "key_data": "潜在 3D 高斯记忆; 实时无限世界生成"

        }

      ],

      "notes": ""

    },

    {

      "id": "TH-049",

      "name": "订阅制 API 额度从开发者工具变为套餐权益",

      "name_en": "",

      "thesis_type": "Frontier Thesis",

      "statement": "API 额度从独立计费转向订阅套餐内嵌，降低开发者入门摩擦但绑定消费到订阅层",

      "change_types": [

        "CT-03",

        "CT-08"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s4-7"

      ],

      "state": "proposed",

      "confidence": "High",

      "first_seen": "2026-10-29",

      "last_seen": "2026-10-29",

      "evidence_count": 1,

      "convergence_entities": [

        "OpenAI"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-29",

          "event_title": "OpenAI API 更新：ChatGPT Pro/Business 订阅者可领取最高 $500 额度",

          "first_publish_shanghai": "2026-10-28T00:00:00+08:00",

          "rating": "B",

          "signal": "Active Event",

          "source": "https://platform.openai.com/docs/changelog",

          "key_data": "ChatGPT Pro/Business 可领 $500 API 额度"

        }

      ],

      "notes": ""

    },

    {

      "id": "TH-050",

      "name": "开源 LLM 被武器化，网络安全攻防双方都使用前沿模型",

      "name_en": "",

      "thesis_type": "Frontier Thesis",

      "statement": "DeepSeek 开源 LLM 被用于国家级 APT 工具链，开源权重的双刃剑效应在威胁情报中首次被实证",

      "change_types": [

        "CT-08"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s4-6"

      ],

      "state": "active",

      "confidence": "High",

      "first_seen": "2026-10-29",

      "last_seen": "2026-10-29",

      "evidence_count": 1,

      "convergence_entities": [

        "CrowdStrike"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-29",

          "event_title": "CrowdStrike 披露：中国关联黑客使用 DeepSeek LLM 驱动 ARTEX AI 工具",

          "first_publish_shanghai": "2026-10-30T00:01:16+08:00",

          "rating": "A",

          "signal": "Convergence",

          "source": "https://www.techmeme.com",

          "key_data": "China-linked hackers; ARTEX AI tool; DeepSeek LLM 驱动"

        }

      ],

      "notes": ""

    },

    {

      "id": "TH-051",

      "name": "模型更新从全量替换走向增量热切换",

      "name_en": "",

      "thesis_type": "Frontier Thesis",

      "statement": "Granite Switch 允许在不重建 pipeline 的情况下切换模型版本，模型运维从一次性部署走向持续更新范式",

      "change_types": [

        "CT-04",

        "CT-08"

      ],

      "tracks": [

        "TR-HARNESS"

      ],

      "sections": [

        "s4-1"

      ],

      "state": "proposed",

      "confidence": "Medium",

      "first_seen": "2026-10-29",

      "last_seen": "2026-10-29",

      "evidence_count": 1,

      "convergence_entities": [

        "IBM"

      ],

      "counter_evidence": [],

      "events": [

        {

          "brief_date": "2026-10-29",

          "event_title": "IBM Granite Switch 4.1.1：像更新软件一样更新模型",

          "first_publish_shanghai": "2026-10-29T13:37:07+08:00",

          "rating": "B",

          "signal": "Active Event",

          "source": "https://huggingface.co/blog",

          "key_data": "Granite Switch 4.1.1; 增量模型切换"

        }

      ],

      "notes": ""

    }

  ]

}

