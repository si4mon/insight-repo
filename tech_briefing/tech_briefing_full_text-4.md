assets/sources.py
----------------------------------------
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
源注册表（Source Surface Registry）

修的是机制缺陷 M2：源写死在流程里、没有 surface 维度，
导致无法回答"OpenAI 的 developer/API 面今天查过没有"。

每个源必须声明（对应 tech_report_task_def §3 的七层面）：
  entity    一级实体（OpenAI / Anthropic / NVIDIA / ...），非厂商源填 channel 名
  surface   公司面 company | 产品面 product | 帮助面 support | 开发者面 developer
            | 模型面 model | 代码面 code | 社媒面 social | 聚合面 aggregator
            | 研究面 research | 社区面 community
  layer     配 surface 的更细粒度标记，用于覆盖率对账
            （例如 anthropic/developer 下的 claude.com/blog 与 platform docs 是不同 layer）
  channel   A_entity / B_arxiv / C_aggregator / D_social / E_expert / F_cn_media / G_official_surface
  mode      提取模式（rss / atom / json_api / markdown_dated / html_cards / sitemap）
  urls      [(url, filename), ...] 顺序 fallback

关键约束（来自实测）：
  - 站点优先用机器可读形态（.md / .atom / .rss / .json），HTML 首页放最后
  - 被 HIS 代理拦截的域名（anthropic.com / docs.claude.com / deepmind.google /
    minimax.io / x.ai / ai.meta.com）不写主 URL，改用可达的替代面
  - 302 自环的源（ai.google.dev changelog）不写

新增/下线源只改本文件，不改流程代码。
"""
import json
import re
from pathlib import Path

BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")
DEFAULT_UA = "curl/8.0"

# surface 枚举（与 task_def §3 "七层登记" 对齐）
SURFACES = [
    "company", "product", "support", "developer",
    "model", "code", "social", "pricing",
    "research", "community", "aggregator",
]

# 覆盖率对账要求的"实体 × 必查面"。
# 对照 tech_report_task_def §3：一级实体必须落到公司面/产品面/帮助面/开发者面/
# 模型面/代码面/社媒面中的可查面；某面确无公开源时，必须在 UNCOVERABLE 中登记理由，
# 否则 coverage.py 判该实体该面"未覆盖"。
#
# 关键不变式：本表的实体集合必须与 thesis_ontology.json 的 tier1_entities
# **完全一致**（去掉 "default"）。否则某实体既没登记源、也不在本表里时，
# coverage.build_gaps 的两条循环都不会访问它 —— 它既不失明也不缺源，
# 永远不产生缺口，也就永远不会被发现。Kimi K3.1 Pro 漏检正是这条路径。
#
# 关键不变式：`set(REQUIRED_SURFACES) - {"default"} == set(TIER1_CANONICAL.values())`。
# 否则某实体既没登记源、也不在本表里时，coverage.build_gaps 的两条循环
# 都不会访问它 —— 它既不失明、也不缺源，永远不产生缺口，也就永远不会被发现。
# Kimi K3.1 Pro 漏检正是这条路径：它在 tier1_entities 里，但既无源也无必查面登记。
#
# 本表用**源侧短名**（与 sources 的 entity 字段一致），TIER1_CANONICAL 负责
# 与 thesis_ontology.json 的显示名对齐。
REQUIRED_SURFACES = {
    "default": ["company", "developer", "code"],
    "OpenAI": ["company", "developer", "code"],
    "Anthropic": ["company", "product", "developer", "code"],
    "Google": ["company", "developer", "research"],
    "NVIDIA": ["company", "developer"],
    "DeepSeek": ["company", "developer"],
    "Qwen": ["company", "code"],
    "MiniMax": ["company"],
    # Mistral 不在 ontology 的 tier1_entities 里，故不出现在本表；
    # 它的源保留（mistral_news），只是不作为必查面参与缺口计算。
    "Meta": ["company"],
    "Microsoft": ["company", "developer"],
    "Moonshot": ["company", "code"],
    "xAI": ["company"],
    "ByteDance": ["company"],
    "Tencent": ["company"],
    "Baidu": ["company"],
    "Zhipu": ["company"],
    "World Labs": ["company"],
    "Runway": ["company"],
    "Pika": ["company"],
    "Luma": ["company"],
    "Black Forest Labs": ["company"],
    "Stability AI": ["company"],
}

# ontology 里的显示名 → 源侧短名。用于校验两侧实体集合一致。
TIER1_CANONICAL = {
    "OpenAI": "OpenAI",
    "Anthropic": "Anthropic",
    "Google / DeepMind": "Google",
    "xAI": "xAI",
    "Meta": "Meta",
    "Microsoft": "Microsoft",
    "NVIDIA": "NVIDIA",
    "DeepSeek": "DeepSeek",
    "Qwen / Alibaba": "Qwen",
    "ByteDance / Seed / Doubao": "ByteDance",
    "Moonshot / Kimi": "Moonshot",
    "Tencent / Hunyuan": "Tencent",
    "Baidu": "Baidu",
    "Zhipu": "Zhipu",
    "MiniMax": "MiniMax",
    "World Labs": "World Labs",
    "Runway": "Runway",
    "Pika": "Pika",
    "Luma": "Luma",
    "Black Forest Labs": "Black Forest Labs",
    "Stability AI": "Stability AI",
}

# 已知无法覆盖的 实体×面，必须写明原因，否则审计时不通过。
# reason 会原样写进 8.1，供人工判断是否需要申请权限。
UNCOVERABLE = [
    {
        "entity": "Anthropic", "surface": "developer",
        "layer": "docs.claude.com",
        "reason": "docs.claude.com 返回 HIS Proxy 拦截页（4200B），无可达替代源；"
                  "已用 platform.claude.com/docs 与 claude.com/blog 部分替代",
    },
    {
        "entity": "Anthropic", "surface": "support",
        "layer": "support.claude.com",
        "reason": "support.claude.com 可达但为 JS 渲染列表页，HTML 中无日期文本，"
                  "html_cards 提取 0 条；已在 8.1 标注需人工补检",
    },
    {
        "entity": "Google", "surface": "developer",
        "layer": "gemini-api-changelog",
        "reason": "ai.google.dev/gemini-api/docs/changelog 302 自环重定向（Location 指向自身），"
                  "HTTP 层无法获取；已用 developers.googleblog.com 与 blog.google/technology/ai 替代",
    },
    {
        "entity": "Meta", "surface": "company",
        "layer": "ai.meta.com",
        "reason": "ai.meta.com/blog 返回 400，RSS 亦 400；无可达官方源",
    },
    {
        "entity": "xAI", "surface": "company",
        "layer": "x.ai",
        "reason": "x.ai/news 返回 403；无可达官方源",
    },
    {
        "entity": "DeepSeek", "surface": "company",
        "layer": "deepseek-com",
        "reason": "deepseek.com 首页为图片墙结构，无标题/日期文本，html_cards 提取 0 条；"
                  "公司面新闻经 Techmeme/HN 聚合源回溯，代码面用 GitHub release 替代",
    },
    {
        "entity": "NVIDIA", "surface": "company",
        "layer": "nvidianews",
        "reason": "NVIDIA 官方新闻室无稳定 RSS；developer.nvidia.com/blog/feed 覆盖技术面，"
                  "公司面新闻需经聚合源（Techmeme/HN）回溯",
    },
    {
        "entity": "Moonshot", "surface": "company",
        "layer": "kimi.com / moonshot.ai",
        "reason": "kimi.com/blog 与 moonshot.ai/blog 均返回 HIS Proxy 拦截页（4200B/3557B）；"
                  "平台文档页同样被拦截。公司面改由 code 面（GitHub release）与"
                  "Techmeme/HN 回溯，模型发布信息需人工补检",
    },
    {
        "entity": "ByteDance", "surface": "company",
        "layer": "seed.bytedance.com",
        "reason": "seed.bytedance.com/en/blog 可达（11KB）但为 JS 渲染，HTML 无标题/日期文本，"
                  "html_cards 与 rss 均提取 0 条",
    },
    {
        "entity": "Tencent", "surface": "company",
        "layer": "hunyuan.tencent.com",
        "reason": "hunyuan.tencent.com 返回 HIS Proxy 拦截页（4201B）",
    },
    {
        "entity": "Baidu", "surface": "company",
        "layer": "ernie.baidu.com",
        "reason": "ernie.baidu.com 可达（28KB）但首页无文章列表与日期，html_cards 提取 0 条",
    },
    {
        "entity": "Zhipu", "surface": "company",
        "layer": "zhipuai.cn",
        "reason": "zhipuai.cn/en/news 返回 HIS Proxy 拦截页（3557B）",
    },
    {
        "entity": "Runway", "surface": "company",
        "layer": "runwayml.com/news",
        "reason": "runwayml.com/news 可达（725KB）但为客户端渲染，html_cards 提取 0 条；"
                  "RSS 返回 http_error",
    },
    {
        "entity": "Luma", "surface": "company",
        "layer": "lumalabs.ai/blog",
        "reason": "lumalabs.ai/blog 返回 HIS Proxy 拦截页（4202B）",
    },
    {
        "entity": "Black Forest Labs", "surface": "company",
        "layer": "bfl.ai/blog",
        "reason": "bfl.ai/blog 返回 HIS Proxy 拦截页（3556B）",
    },
    {
        "entity": "Stability AI", "surface": "company",
        "layer": "stability.ai/news",
        "reason": "stability.ai/news 可达（894KB）并提取 20 条，但条目均无日期字段，"
                  "无法归窗；仅在快照差分模式下可见",
    },
    {
        "entity": "Microsoft", "surface": "company",
        "layer": "blogs.microsoft.com / news.microsoft.com",
        "reason": "blogs.microsoft.com/feed、blogs.microsoft.com/ai/feed、"
                  "news.microsoft.com/feed 三个入口均 url_error；"
                  "公司面改由 developer 面（devblogs RSS）与聚合源回溯",
    },
]


def _classes(*names):
    return " ".join(names)


def build_sources() -> list[dict]:
    """构建全部源定义。返回 list，每项是一个采集任务。"""
    S = []

    def add(**kw):
        kw.setdefault("ua", DEFAULT_UA)
        kw.setdefault("timeout", 20)
        kw.setdefault("critical", False)   # critical=该源零覆盖直接导致 gate 失败
        kw.setdefault("required", True)    # required=False 表示尽力而为
        S.append(kw)

    # ==========================================================
    # OpenAI
    # ==========================================================
    # 实测：openai.com/index 与 openai.com/news 走代理仍 403；
    # platform.openai.com/docs/changelog.md 是 200 + 77KB 纯 Markdown，含完整日期条目。
    # 这是"API lifecycle 变化"唯一稳定来源，因此设为 critical。
    add(id="openai_api_changelog", entity="OpenAI", surface="developer",
        layer="platform-changelog", channel="G_official_surface",
        mode="markdown_dated", critical=True,
        urls=[("https://platform.openai.com/docs/changelog.md", "openai_changelog.md")])

    add(id="openai_api_deprecations", entity="OpenAI", surface="developer",
        layer="platform-deprecations", channel="G_official_surface",
        mode="markdown_dated",
        urls=[("https://platform.openai.com/docs/deprecations.md", "openai_deprecations.md")])

    # SDK release atom = API 变更的代理信号（changelog 之外的独立交叉验证）
    for sdk in ("openai-python", "openai-node", "openai-agents-python"):
        add(id=f"openai_sdk_{sdk.replace('-', '_')}", entity="OpenAI",
            surface="code", layer="sdk-release", channel="G_official_surface",
            mode="atom",
            urls=[(f"https://github.com/openai/{sdk}/releases.atom",
                   f"gh_openai_{sdk}.atom")])

    add(id="openai_platform_docs", entity="OpenAI", surface="developer",
        layer="platform-docs-index", channel="G_official_surface",
        mode="markdown", required=False,
        urls=[("https://platform.openai.com/docs/llms.txt", "openai_llms.txt")])

    # 公司面：openai.com/index 与 /news 的 HTML 均 403，但 RSS 可用（1316 条）。
    # 这解释了历史上"OpenAI 只采到 366KB HTML"——采到了反爬页而非内容。
    add(id="openai_news_rss", entity="OpenAI", surface="company",
        layer="openai-news-rss", channel="A_entity", mode="rss",
        urls=[("https://openai.com/news/rss.xml", "openai_news.xml")])

    # ==========================================================
    # Anthropic
    # ==========================================================
    # 实测：anthropic.com/* 与 docs.claude.com 全是 HIS Proxy 拦截页（4200B）。
    # claude.com/blog 是 574KB 完整 HTML，带 12 张 ResourceCard（标题+日期），可解析。
    # task_def §3 明确要求 claude.com/blog，此前采集器完全缺失。
    add(id="anthropic_blog", entity="Anthropic", surface="product",
        layer="claude-com-blog", channel="A_entity", mode="html_cards",
        critical=True,
        urls=[("https://claude.com/blog", "anthropic_blog.html")])

    add(id="anthropic_blog_engineering", entity="Anthropic", surface="product",
        layer="claude-com-blog-engineering", channel="A_entity", mode="html_cards",
        urls=[("https://claude.com/blog?category=engineering",
               "anthropic_blog_engineering.html")])

    # sitemap 用于 surface diff：新增文章即使当天不在首页卡片上也能被 diff 发现
    add(id="anthropic_sitemap", entity="Anthropic", surface="product",
        layer="claude-com-sitemap", channel="G_official_surface", mode="sitemap",
        urls=[("https://claude.com/sitemap.xml", "anthropic_sitemap.xml")])

    add(id="anthropic_platform_docs", entity="Anthropic", surface="developer",
        layer="platform-docs", channel="A_entity", mode="markdown", required=False,
        urls=[("https://platform.claude.com/docs/en/overview.md",
               "anthropic_platform_docs.md")])

    for sdk in ("claude-code", "anthropic-sdk-python"):
        add(id=f"anthropic_{sdk.replace('-', '_')}", entity="Anthropic",
            surface="code", layer="sdk-release", channel="G_official_surface",
            mode="atom",
            urls=[(f"https://github.com/anthropics/{sdk}/releases.atom",
                   f"gh_anthropic_{sdk}.atom")])

    # anthropic.com 保留为"探测性源"：不设 critical，且拦截页会被显式标记，
    # 这样 8.1 能持续显示"该面仍被拦截"，而不是静默成功。
    add(id="anthropic_news_probe", entity="Anthropic", surface="company",
        layer="anthropic-com-news", channel="A_entity", mode="html_cards",
        required=False,
        urls=[("https://www.anthropic.com/news", "anthropic_news_probe.html")])

    # ==========================================================
    # Google / DeepMind
    # ==========================================================
    # 实测：deepmind.google 与 ai.google.dev/changelog 不可用；
    # 但 blog.google / research.google / developers.googleblog 的 RSS 均可用。
    add(id="google_ai_blog", entity="Google", surface="company",
        layer="blog-google-ai", channel="A_entity", mode="rss",
        urls=[("https://blog.google/technology/ai/rss/", "google_ai_blog.xml")])

    add(id="google_research_blog", entity="Google", surface="research",
        layer="research-google", channel="A_entity", mode="rss",
        urls=[("https://research.google/blog/rss/", "google_research.xml")])

    add(id="google_developers_blog", entity="Google", surface="developer",
        layer="developers-googleblog", channel="A_entity", mode="rss",
        urls=[("https://developers.googleblog.com/feeds/posts/default",
               "google_devblog.atom")])

    add(id="deepmind_probe", entity="Google", surface="company",
        layer="deepmind-blog", channel="A_entity", mode="rss", required=False,
        urls=[("https://deepmind.google/blog/rss.xml", "deepmind.xml")])

    add(id="google_genai_sdk", entity="Google", surface="code",
        layer="sdk-release", channel="G_official_surface", mode="atom",
        urls=[("https://github.com/googleapis/python-genai/releases.atom",
               "gh_python_genai.atom")])

    # ==========================================================
    # NVIDIA —— 此前完全缺失，遗漏 3 的直接原因
    # ==========================================================
    add(id="nvidia_dev_blog", entity="NVIDIA", surface="developer",
        layer="nvidia-technical-blog", channel="A_entity", mode="atom",
        critical=True,
        urls=[("https://developer.nvidia.com/blog/feed/", "nvidia_blog.atom")])

    # 关键词搜索页：覆盖 feed 只保留最近 100 条导致的漏检
    # （Cosmos 等较早期条目会滚出 feed，但搜索页仍可命中）
    for kw, fn in (("Minerva", "nvidia_search_minerva.html"),
                   ("agent", "nvidia_search_agent.html")):
        add(id=f"nvidia_search_{kw.lower()}", entity="NVIDIA", surface="developer",
            layer=f"nvidia-blog-search-{kw.lower()}", channel="A_entity",
            mode="html_cards", required=False,
            urls=[(f"https://developer.nvidia.com/blog/?s={kw}", fn)])

    # ==========================================================
    # 其他一级实体
    # ==========================================================
    add(id="deepseek_updates", entity="DeepSeek", surface="developer",
        layer="api-docs-updates", channel="A_entity", mode="html_cards",
        urls=[("https://api-docs.deepseek.com/updates", "deepseek_updates.html")])

    add(id="qwen_blog", entity="Qwen", surface="company",
        layer="qwen-blog", channel="A_entity", mode="rss",
        urls=[("https://qwenlm.github.io/blog/index.xml", "qwen_blog.xml")])

    add(id="qwen_code", entity="Qwen", surface="code",
        layer="qwen-github-release", channel="G_official_surface", mode="atom",
        required=False,
        urls=[("https://github.com/QwenLM/Qwen3/releases.atom", "gh_qwen3.atom")])

    # DeepSeek 公司面：deepseek.com 首页无日期结构，用 GitHub release 作代码面兜底
    add(id="deepseek_code", entity="DeepSeek", surface="code",
        layer="deepseek-github-release", channel="G_official_surface", mode="atom",
        required=False,
        urls=[("https://github.com/deepseek-ai/DeepSeek-V3/releases.atom",
               "gh_deepseek.atom")])

    add(id="mistral_news", entity="Mistral", surface="company",
        layer="mistral-news", channel="A_entity", mode="rss",
        urls=[("https://mistral.ai/rss.xml", "mistral_news.xml")])

    add(id="minimax_probe", entity="MiniMax", surface="company",
        layer="minimax-blog", channel="A_entity", mode="html_cards", required=False,
        urls=[("https://www.minimax.io/blog", "minimax_blog.html")])

    add(id="hf_blog", entity="HuggingFace", surface="company",
        layer="hf-blog", channel="A_entity", mode="rss",
        urls=[("https://huggingface.co/blog/feed.xml", "hf_blog.xml")])

    # ==========================================================
    # A2. 其余 Tier-1 实体
    # ==========================================================
    # 这些实体在 tier1_entities 里，此前既无源也无必查面登记，
    # 因此既不报失明也不产生缺口 —— Kimi K3.1 Pro 就是这样漏掉的。
    # 官网多数被 HIS 代理拦截，优先用可达的 GitHub release 通道。

    # Moonshot / Kimi：kimi.com 与 moonshot.ai 均返回拦截页；
    # Kimi 自家 harness/工具的 release 是目前唯一可达的官方变更面。
    add(id="moonshot_kimi_code", entity="Moonshot", surface="code",
        layer="kimi-code-release", channel="G_official_surface", mode="atom",
        urls=[("https://github.com/MoonshotAI/kimi-code/releases.atom",
               "gh_moonshot_kimi_code.atom")])
    add(id="moonshot_checkpoint_engine", entity="Moonshot", surface="code",
        layer="checkpoint-engine-release", channel="G_official_surface", mode="atom",
        required=False,
        urls=[("https://github.com/MoonshotAI/checkpoint-engine/releases.atom",
               "gh_moonshot_checkpoint.atom")])

    # Microsoft：devblogs RSS 可达（116KB/10 条），是 Agent 相关一手内容的主要来源
    add(id="msft_devblogs", entity="Microsoft", surface="developer",
        layer="devblogs-feed", channel="A_entity", mode="rss",
        urls=[("https://devblogs.microsoft.com/feed/", "msft_devblogs.xml")])

    # World Labs / Pika：官网 blog 可解析
    add(id="worldlabs_blog", entity="World Labs", surface="company",
        layer="worldlabs-blog", channel="A_entity", mode="html_cards",
        urls=[("https://www.worldlabs.ai/blog", "worldlabs_blog.html")])
    add(id="pika_blog", entity="Pika", surface="company",
        layer="pika-blog", channel="A_entity", mode="html_cards",
        urls=[("https://pika.art/blog", "pika_blog.html")])

    # ==========================================================
    # B. arXiv source-native
    # ==========================================================
    for cat in ("cs.AI", "cs.CL", "cs.LG", "cs.MA", "cs.RO"):
        add(id=f"arxiv_{cat.replace('.', '_')}", entity="arXiv",
            surface="research", layer="arxiv-rss", channel="B_arxiv",
            mode="rss",
            timeout=45 if cat in ("cs.CL", "cs.LG") else 20,
            # arXiv 每天整批发布一次、周末不发。用"连续时间覆盖"判定会
            # 把正常情况误报成窗口截断（周末没有批次，最早条目必然晚于窗口起点）。
            daily_batch=True,
            skip_weekends=True,
            urls=[(f"https://export.arxiv.org/rss/{cat}",
                   f"arxiv_{cat.replace('.', '_')}.xml")])

    # ==========================================================
    # C. 聚合源
    # ==========================================================
    add(id="techmeme", entity="Techmeme", surface="aggregator",
        layer="techmeme-feed", channel="C_aggregator", mode="rss",
        urls=[("https://www.techmeme.com/feed.xml", "techmeme.xml")])

    # 注意：HN 必须用"按时间"而不是"按分数"的入口。
    # 原实现只取 topstories 前 40 条，points 低的真实事件（如 Minerva，points=2）
    # 天然被丢弃 —— 这是比"聚类过度合并"更靠前的漏检机制。
    # 必须"时间切片 + 逐片翻页"两条都用，单靠任一条都会静默截断：
    #   - 只取单页：100 条按时间倒序仅覆盖约 4 小时（窗口约 30 小时）
    #   - 只翻页：Algolia 对单查询有 1000 条上限，30 小时窗口内实有 2000+ 条
    # 结果是 points 低但真实的条目（如 NVIDIA Minerva，points=2）永远翻不到，
    # 而源仍显示 OK_IN_WINDOW —— 静默截断，比失明更危险。
    add(id="hn_newest", entity="HackerNews", surface="aggregator",
        layer="hn-newest", channel="D_social", mode="json_api",
        json_mode="hn_algolia", critical=True,
        paginate={
            "url_template": ("https://hn.algolia.com/api/v1/search_by_date"
                             "?tags=story&hitsPerPage={per_page}&page={page}"
                             "&numericFilters=created_at_i>={start_ts},"
                             "created_at_i<{end_ts}"),
            "per_page": 1000,
            "max_pages": 1,              # 切片足够小，单片通常 1 页内取完
            "slice_hours": 2,            # 每片 2 小时，实测每片约 150 条
            "filename_template": "hn_newest_{start_ts}_{page}.json",
        },
        urls=[("https://hn.algolia.com/api/v1/search_by_date?tags=story&hitsPerPage=100",
               "hn_newest.json")])

    add(id="hn_front", entity="HackerNews", surface="aggregator",
        layer="hn-frontpage", channel="D_social", mode="json_api",
        json_mode="hn_algolia",
        urls=[("https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=60",
               "hn_front.json")])

    add(id="gh_trending", entity="GitHub", surface="code",
        layer="gh-trending-rss", channel="D_social", mode="rss",
        urls=[("https://mshibanami.github.io/GitHubTrendingRSS/daily/all.xml",
               "gh_trending.xml")])

    # ==========================================================
    # E. 专家博客
    # ==========================================================
    # 实测：atom/everything 133KB / 30 条，原 HTML 首页不可解析。
    add(id="simonwillison", entity="SimonWillison", surface="community",
        layer="simonwillison-atom", channel="E_expert", mode="atom", critical=True,
        urls=[("https://simonwillison.net/atom/everything/", "simonwillison.atom")])

    add(id="latentspace", entity="LatentSpace", surface="community",
        layer="latentspace-feed", channel="E_expert", mode="rss",
        urls=[("https://www.latent.space/feed", "latentspace.xml")])

    # ==========================================================
    # F. 中文媒体
    # ==========================================================
    add(id="qbitai", entity="QbitAI", surface="community",
        layer="qbitai-feed", channel="F_cn_media", mode="rss",
        urls=[("https://www.qbitai.com/feed", "qbitai.xml")])

    add(id="jiqizhixin", entity="Jiqizhixin", surface="community",
        layer="jiqizhixin-index", channel="F_cn_media", mode="html_cards",
        required=False,
        urls=[("https://www.jiqizhixin.com/", "jiqizhixin.html")])

    # ==========================================================
    # 模型面 / 数据集面
    # ==========================================================
    add(id="hf_daily_papers", entity="HuggingFace", surface="model",
        layer="hf-daily-papers", channel="A_entity", mode="json_api",
        json_mode="hf_daily_papers",
        urls=[("https://hf-mirror.com/api/daily_papers", "hf_daily_papers.json"),
              ("https://huggingface.co/api/daily_papers", "hf_daily_papers_orig.json")])

    add(id="hf_trending_models", entity="HuggingFace", surface="model",
        layer="hf-trending-models", channel="A_entity", mode="json_api",
        json_mode="hf_trending",
        urls=[("https://hf-mirror.com/api/trending?model", "hf_trending_models.json"),
              ("https://huggingface.co/api/trending?model", "hf_trending_models_orig.json")])

    return S


def surface_matrix(sources: list[dict]) -> dict:
    """
    输出 实体 → surface → [source_id] 的矩阵，用于覆盖率对账。
    这是 M2 的修复核心：把"源集合"变成"可对账的覆盖矩阵"。
    """
    m = {}
    for s in sources:
        m.setdefault(s["entity"], {}).setdefault(s["surface"], []).append(s["id"])
    return m


def coverage_gaps(sources: list[dict]) -> list[dict]:
    """
    对每个必须覆盖的实体×面，检查是否有源登记。
    返回缺口列表：[{entity, surface, status, reason}]
    status: missing（未登记任何源）| uncoverable（已登记不可达原因）
    """
    m = surface_matrix(sources)
    uncoverable = {(u["entity"], u["surface"]) for u in UNCOVERABLE}
    gaps = []
    for entity, required in REQUIRED_SURFACES.items():
        if entity == "default":
            continue
        for surf in required:
            if entity in m and surf in m[entity]:
                continue
            if (entity, surf) in uncoverable:
                gaps.append({"entity": entity, "surface": surf,
                             "status": "uncoverable",
                             "reason": next(u["reason"] for u in UNCOVERABLE
                                            if u["entity"] == entity and u["surface"] == surf)})
            else:
                gaps.append({"entity": entity, "surface": surf,
                             "status": "missing", "reason": ""})
    return gaps


if __name__ == "__main__":
    srcs = build_sources()
    print(f"sources: {len(srcs)}")
    m = surface_matrix(srcs)
    for ent, surf in m.items():
        print(f"  {ent:14} " + " ".join(f"{k}({len(v)})" for k, v in surf.items()))
    print("\ncoverage gaps:")
    for g in coverage_gaps(srcs):
        print(f"  [{g['status']:11}] {g['entity']} / {g['surface']}: {g['reason'][:70]}")

assets/taxonomy.py
----------------------------------------
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Taxonomy · 技术分类映射 API

单一事实源：54 个三级叶子（data/四层技术地图.txt） → 11 个阅读栏目 → 8 章。
定义在 thesis_ontology.json 的 "taxonomy" 段，本模块只做查询与校验，
不改写数据。成稿提示词、gate 校验、thesis_registry 共用同一套映射。

**为什么要有这一层**：此前栏目写死在 SKILL.md 和 verify_gates.py 里，
叶子和栏目之间没有机器可读的对应关系，改分类必然漏改一处。

三种查询：
  leaf      — 叶子 → 栏目（事件归档身份）
  column    — 栏目 → 叶子（当天正文分节）
  resolve   — 主技术路径（可能停在二级）→ 栏目，按"可停二级"规则判定

用法：
  # CLI
  python taxonomy.py leaves
  python taxonomy.py columns
  python taxonomy.py chapter 4
  python taxonomy.py leaf A1.1
  python taxonomy.py resolve A1
  python taxonomy.py validate

  # 作为模块
  from taxonomy import TAXONOMY
  TAXONOMY.column_of("B1.1")        # "3.2"
  TAXONOMY.leaves_of("4.6")         # ["D1.1", ...]
  TAXONOMY.resolve("A1")            # 抛 AmbiguousPath：A1 跨 3.1/3.3/3.4
  TAXONOMY.anchor("3.2")            # "s3-2"

退出码：0 正常；1 validate 有 FAIL
"""
import argparse
import json
import sys
from pathlib import Path

ASSETS_DIR = Path(__file__).parent
ONTOLOGY_PATH = ASSETS_DIR / "thesis_ontology.json"

# 可以停在二级的域：当且仅当该二级域的全部叶子落在同一栏目。
# A1（3.1/3.3/3.4）、C3（4.3/4.4）跨栏目，必须下钻到三级。
# 名单以 ontology 的 taxonomy.rules.must_drill_level2 为准，此处只做默认值。


class TaxonomyError(Exception):
    """叶子/栏目/章节不存在。"""


class AmbiguousPath(TaxonomyError):
    """停在二级，但该二级域跨多个栏目，必须下钻。"""


class Taxonomy:
    def __init__(self, ontology_path: Path = ONTOLOGY_PATH):
        self.ontology_path = ontology_path
        raw = json.loads(ontology_path.read_text(encoding="utf-8"))
        data = raw.get("taxonomy")
        if not data:
            raise TaxonomyError(f"{ontology_path} 缺少 taxonomy 段")
        self.data = data
        self._must_drill = tuple(data.get("rules", {}).get("must_drill_level2", []))
        self._leaves = {x["id"]: x for x in data["leaves"]}
        self._columns = {x["id"]: x for x in data["columns"]}
        self._chapters = {x["chapter"]: x for x in data["chapters"]}
        self._level2 = {}
        for dom in data["domains"]:
            for l2 in dom["level2"]:
                self._level2[l2["id"]] = {"level1": dom["id"], **l2}

    # ---------- leaf ----------
    def leaf(self, leaf_id: str) -> dict:
        try:
            return self._leaves[leaf_id]
        except KeyError:
            raise TaxonomyError(f"未知叶子: {leaf_id}")

    def leaf_ids(self) -> list[str]:
        return list(self._leaves)

    def column_of(self, leaf_id: str) -> str:
        return self.leaf(leaf_id)["column"]

    # ---------- column ----------
    def column(self, column_id: str) -> dict:
        try:
            return self._columns[column_id]
        except KeyError:
            raise TaxonomyError(f"未知栏目: {column_id}")

    def column_ids(self) -> list[str]:
        return list(self._columns)

    def leaves_of(self, column_id: str) -> list[str]:
        return list(self.column(column_id)["leaves"])

    def columns_of_chapter(self, chapter: int) -> list[dict]:
        return [c for c in self.data["columns"] if c["chapter"] == chapter]

    def column_ids_of_chapter(self, chapter: int) -> list[str]:
        return [c["id"] for c in self.columns_of_chapter(chapter)]

    def annotation_labels(self, column_id: str) -> list[str]:
        """聚合栏目要求卡片标注的细分技术域；普通栏目返回空列表。"""
        return list(self.column(column_id).get("annotation_labels", []))

    def annotation_map(self, column_id: str) -> dict[str, str]:
        """标注标签 → 叶子。用于校验标签覆盖了栏目的全部叶子。"""
        return dict(self.column(column_id).get("annotation_map", {}))

    def annotation_label_for(self, leaf_id: str) -> str:
        """
        叶子 → 该叶子唯一允许的标注标签（普通栏目返回空串）。

        方向与 annotation_map 相反。必须提供这个方向：卡片校验拿到的是
        叶子，若在 map 上直接取叶子会恒为 None，校验会静默通过。
        """
        column = self.column_of(leaf_id)
        for label, leaf in self.annotation_map(column).items():
            if leaf == leaf_id:
                return label
        return ""

    # ---------- chapter ----------
    def chapter(self, n: int) -> dict:
        try:
            return self._chapters[n]
        except KeyError:
            raise TaxonomyError(f"未知章节: {n}")

    def chapters(self) -> list[dict]:
        return sorted(self.data["chapters"], key=lambda x: x["chapter"])

    def section_id(self, n: int) -> str:
        """章号 → HTML section id（s1..s8）。"""
        return self.chapter(n)["section_id"]

    def anchor(self, column_id: str) -> str:
        """栏目号 → HTML 锚点 id（3.2 → s3-2，4.6 → s4-6）。"""
        chapter, num = self.column(column_id)["id"].split(".")
        return f"s{chapter}-{num}"

    # ---------- resolve ----------
    def resolve(self, path: str) -> str:
        """
        主技术路径 → 栏目。path 可以是三级叶子，也可以是二级域。

        规则（设计文档 §4.2）：
          - 三级叶子直接映射；
          - 二级域只在"全部叶子落在同一栏目"时可停；
          - A1 / C3 必须下钻到三级。
        """
        if path in self._leaves:
            return self._leaves[path]["column"]
        if path in self._level2:
            if path in self._must_drill:
                raise AmbiguousPath(f"{path} 跨多个栏目，必须下钻到三级叶子")
            cols = {self._leaves[x]["column"] for x in self._leaves_by_level2(path)}
            if len(cols) == 1:
                return cols.pop()
            raise AmbiguousPath(f"{path} 跨多个栏目 {sorted(cols)}，必须下钻到三级叶子")
        raise TaxonomyError(f"未知技术路径: {path}")

    def _leaves_by_level2(self, level2: str) -> list[str]:
        return [lid for lid, x in self._leaves.items() if x["level2"] == level2]

    # ---------- misc ----------
    def change_objects(self) -> list[str]:
        return list(self.data["change_objects"])

    def rules(self) -> dict:
        return dict(self.data["rules"])

    # ---------- validate ----------
    def validate(self) -> list[dict]:
        """返回 [{name, ok, detail}]，供 gate 与单测直接消费。"""
        out = []

        def add(name, ok, detail=""):
            out.append({"name": name, "ok": bool(ok), "detail": detail})

        leaves, columns, chapters = self.data["leaves"], self.data["columns"], self.data["chapters"]

        ids = [x["id"] for x in leaves]
        dup = sorted({i for i in ids if ids.count(i) > 1})
        add("叶子数 = 54", len(leaves) == 54, f"actual={len(leaves)}")
        add("叶子 id 无重复", not dup, f"dup={dup}")

        cids = [x["id"] for x in columns]
        cdup = sorted({i for i in cids if cids.count(i) > 1})
        add("栏目数 = 11", len(columns) == 11, f"actual={len(columns)}")
        add("栏目 id 无重复", not cdup, f"dup={cdup}")

        unknown = [x["id"] for x in leaves if x.get("column") not in self._columns]
        add("每个叶子指向存在的栏目", not unknown, f"bad={unknown}")

        # 双向一致：栏目列出的叶子 == 叶子自己声明的栏目
        mismatched = []
        for c in columns:
            for lid in c["leaves"]:
                if lid not in self._leaves:
                    mismatched.append(f"{c['id']}→未知叶子 {lid}")
                elif self._leaves[lid]["column"] != c["id"]:
                    mismatched.append(f"{c['id']} 列了 {lid}，但叶子声明 {self._leaves[lid]['column']}")
        for l in leaves:
            if l["id"] not in self._columns.get(l["column"], {}).get("leaves", []):
                mismatched.append(f"叶子 {l['id']} 未出现在栏目 {l['column']} 的列表里")
        add("叶子↔栏目双向一致", not mismatched, f"{len(mismatched)} 处: {mismatched[:5]}")

        multi = [lid for lid in ids if sum(1 for c in columns if lid in c["leaves"]) > 1]
        add("每个叶子只属一个栏目", not multi, f"multi={multi}")

        add("章 3 栏目数 = 4", len(self.columns_of_chapter(3)) == 4,
            f"actual={len(self.columns_of_chapter(3))}")
        add("章 4 栏目数 = 7", len(self.columns_of_chapter(4)) == 7,
            f"actual={len(self.columns_of_chapter(4))}")
        cap = [c["id"] for c in columns if c["chapter"] not in (3, 4)]
        add("栏目只挂章 3/章 4", not cap, f"bad={cap}")

        ch_nums = sorted(x["chapter"] for x in chapters)
        add("章号 1–8 连续", ch_nums == list(range(1, 9)), f"actual={ch_nums}")
        sec_ids = [x["section_id"] for x in chapters]
        add("section id = s1..s8", sec_ids == [f"s{i}" for i in range(1, 9)], f"actual={sec_ids}")

        bad_l1 = [x["id"] for x in leaves if x["level1"] not in {d["id"] for d in self.data["domains"]}]
        add("叶子 level1 均存在", not bad_l1, f"bad={bad_l1}")
        bad_l2 = [x["id"] for x in leaves if x["level2"] not in self._level2]
        add("叶子 level2 均存在", not bad_l2, f"bad={bad_l2}")
        unused_l2 = [k for k in self._level2 if not self._leaves_by_level2(k)]
        add("每个二级域至少有一个叶子", not unused_l2, f"unused={unused_l2}")

        # 可停二级规则：跨栏目的二级域必须拒绝解析，单栏目的必须解析成功
        wrong = []
        for l2 in self._level2:
            spans = {self._leaves[x]["column"] for x in self._leaves_by_level2(l2)}
            try:
                got = self.resolve(l2)
            except AmbiguousPath:
                if len(spans) == 1:
                    wrong.append(f"{l2} 单栏目 {spans} 却拒绝解析")
            else:
                if len(spans) > 1:
                    wrong.append(f"{l2} 跨栏目 {sorted(spans)} 却停在了二级")
        add("可停二级规则一致", not wrong, f"{wrong}")

        # must_drill 是冗余声明，必须与"叶子实际跨栏目"推导出的集合一致，
        # 否则漏配会被 resolve() 的跨栏目兜底掩盖，规则声明与实际行为脱节。
        cross = sorted(l2 for l2 in self._level2
                       if len({self._leaves[x]["column"] for x in self._leaves_by_level2(l2)}) > 1)
        add("must_drill_level2 与跨栏目集合一致",
            sorted(self._must_drill) == cross,
            f"declared={sorted(self._must_drill)} derived={cross}")

        add("变更对象非空", bool(self.data.get("change_objects")), "")
        add("每个叶子有名称", all(x.get("name") for x in leaves), "")

        # 聚合栏目的标注标签必须恰好覆盖其全部叶子：
        # 少一个 → 那个叶子的事件无法合规标注（D1.3 曾因此无法归位）；
        # 多一个 → 标签指向不存在的叶子。
        for c in columns:
            labels = c.get("annotation_labels")
            if not labels:
                continue
            amap = c.get("annotation_map", {})
            covered = set(amap.values())
            want = set(c["leaves"])
            add(f"{c['id']} 标注标签覆盖全部叶子", covered == want,
                f"未覆盖={sorted(want - covered)} 多出={sorted(covered - want)}")
            bad = [k for k in amap if k not in labels]
            add(f"{c['id']} annotation_map 的键都在标签表内", not bad, f"bad={bad}")

        return out


TAXONOMY = Taxonomy()


# ---------- CLI ----------
def _dump(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser(description="Technology taxonomy lookup")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("leaves", help="列出全部叶子")
    sub.add_parser("columns", help="列出全部栏目")

    c = sub.add_parser("chapter", help="列出某章及其栏目")
    c.add_argument("n", type=int)

    lf = sub.add_parser("leaf", help="查一个叶子")
    lf.add_argument("path")

    r = sub.add_parser("resolve", help="主技术路径 → 栏目")
    r.add_argument("path")

    sub.add_parser("validate", help="校验 54 叶子 / 11 栏目完整性")

    args = p.parse_args()

    try:
        if args.cmd == "leaves":
            _dump(TAXONOMY.data["leaves"])
        elif args.cmd == "columns":
            _dump(TAXONOMY.data["columns"])
        elif args.cmd == "chapter":
            ch = TAXONOMY.chapter(args.n)
            _dump({**ch, "columns": TAXONOMY.columns_of_chapter(args.n)})
        elif args.cmd == "leaf":
            _dump({**TAXONOMY.leaf(args.path),
                   "column_name": TAXONOMY.column(TAXONOMY.column_of(args.path))["name"]})
        elif args.cmd == "resolve":
            col = TAXONOMY.resolve(args.path)
            _dump({"path": args.path, "column": col,
                   "column_name": TAXONOMY.column(col)["name"],
                   "anchor": TAXONOMY.anchor(col)})
        elif args.cmd == "validate":
            results = TAXONOMY.validate()
            for x in results:
                print(f"{'PASS' if x['ok'] else 'FAIL'}  {x['name']}"
                      + (f"  — {x['detail']}" if x["detail"] and not x["ok"] else ""))
            nf = sum(1 for x in results if not x["ok"])
            print(f"\n{len(results) - nf} pass / {nf} fail")
            return 1 if nf else 0
    except TaxonomyError as e:
        print(f"[taxonomy] {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

assets/tech_report_task_def.md
----------------------------------------
生成 Asia/Shanghai 时区下，从“昨日 00:00”开始至“任务实际执行时刻”为止的“多源技术热点简报”，默认交付完整、可独立打开的高信息密度 HTML 文件。



【0｜TARGET_WINDOW Gate｜最高优先级】

任务开始后，必须先获取真实当前运行时刻 NOW_UTC，并转换到 IANA 时区 Asia/Shanghai：NOW_SHANGHAI = convert_timezone(NOW_UTC, "Asia/Shanghai")。WINDOW_START_DATE = date(NOW_SHANGHAI) - 1 calendar day；WINDOW_START = WINDOW_START_DATE 00:00:00 Asia/Shanghai；WINDOW_END = NOW_SHANGHAI；TARGET_WINDOW = [WINDOW_START, WINDOW_END]。本任务中的 TARGET_DATE / TARGET_RANGE 语义统一解释为 TARGET_WINDOW，不再限定为单一自然日。禁止使用用户时区、浏览器时区、系统默认时区、上一轮日期、历史文件名、历史正文或已有状态文件推导 TARGET_WINDOW。冻结 TARGET_WINDOW 后，本轮的采集、检索、筛选、事件归属、标题、正文、文件名、8.2 Event Index 都必须使用同一窗口：WINDOW_START ≤ event_first_publish_time_in_Asia_Shanghai ≤ WINDOW_END。昨日全天事件允许进入正文；今日从 00:00 至任务执行时刻的事件允许进入正文；昨日 00:00 之前首次发布的事件，不得作为本轮“新事件”进入正文，只能按 Active Event / Historical Context 规则作为背景引用；无法确认首发时刻的高价值候选，必须明确标注“首发时间未完全核实”，不得伪造日期归属。生成前必须执行 Window Audit：H1 中的时间范围必须等于 TARGET_WINDOW；正文首页必须显示 WINDOW_START / WINDOW_END；8.2 Event Index 中所有“本轮新事件”的首发时刻都必须位于 TARGET_WINDOW；若文件生成过程中 NOW_SHANGHAI 已变化，不重新扩展 WINDOW_END；WINDOW_END 在任务开始时冻结；任一位置时间窗口不一致，废弃草稿并重新生成。建议文件名：多源技术热点简报_{WINDOW_START_DATE}.html。



【0.1｜扫描窗口与事件归属分离】

事件归属窗口为 TARGET_WINDOW。为减少跨时区漏检，实际采集扫描窗口扩大为：SCAN_WINDOW_START = WINDOW_START - 6 hours；SCAN_WINDOW_END = WINDOW_END；SCAN_WINDOW = [SCAN_WINDOW_START, SCAN_WINDOW_END]。扫描窗口用于“发现候选”，TARGET_WINDOW 用于“决定正文新事件归属”。每个事件仍按“首次公开发布时刻”换算 Asia/Shanghai 判定是否属于 TARGET_WINDOW；SCAN_WINDOW_START 至 WINDOW_START 之间出现的事件只用于跨时区边界校验、Active Event、背景关系与漏检回溯；WINDOW_END 之后的信息不得以本次正文新事件身份出现；如果搜索结果页面日期与原始首发时间不一致，必须优先使用官方原始发布时间；美国当地日期、UTC 日期、媒体转载日期不得直接作为归属日期；聚合源命中后必须回溯原始来源确认首发时刻。跨日状态文件 source_registry、known_vocabulary、thesis_map、event_index、官方面快照、漏检档案，仅用于去重、差分和回溯，禁止用于推导 TARGET_WINDOW。若状态文件不可用，按“首次运行”执行，并在 8.1 中记录。



【1｜执行强度】

必须按高强度 Research / Reasoning 执行：多源检索、交叉验证、日期/版本审计、事件聚合、近 3 日 Active Event、Expert Thesis Watch、Frontier / Convergence / Confidence Gate、Zero-result Audit 后再成稿。禁止低强度摘要。执行顺序必须显式分阶段：P1 宽召回 → P2 抽象提升 → P3 聚类收敛 → P4 价值门控与排序 → P5 成稿交付 → P6 漏检回溯。P1 阶段禁止做价值判断和主题过滤。



【2｜采集机制：三路召回 + 双驱动补检】

禁止只按厂商/产品名扫描，也禁止只按关键词表扫描。关键词表与实体表决定“补检深度”，不决定“召回边界”。每天必须并行执行以下五路，全部完成后才能进入 Zero-result Gate：

A. Entity Watch：按厂商、项目、仓库、产品线检查正式发布与实质更新。

B. Technology Watch Matrix：按关键技术命题独立搜索，即使没有命中既有型号/产品名，也必须进入候选池。

C. Source Full-Read：对 source_registry 中每个源读取 SCAN_WINDOW 内全部条目，至少获取标题、链接、发布时间、来源，不得预先按主题过滤，包括注意力聚合源。

D. Cross-Source Resonance：任一实体/事件在 24h 内被 ≥3 个独立来源报道，或在 Hacker News 首页、GitHub Trending、Hugging Face Trending、专家 X / 博客圈、主流 AI 技术媒体出现明显热度突增，无论主题是否在 Watch Matrix 中，都强制进入候选池。

E. Official Surface Diff：对 Tier-1 厂商文档站导航/sitemap、changelog、release notes、model catalog、定价/套餐页、Help Center 更新列表、产品入口、开发者控制台公开页面与上一快照执行 diff。新增页面、新增对象名、新增/合并/下线的产品、模型、模式、API 生命周期变化，一律进入候选池。

预算约束：C + D + E 中非 Watchlist 命中的开放召回，不少于总检索/抓取调用的 30%。P1 输出候选池字段至少包括：标题、URL、首发时刻、Asia/Shanghai 首发时刻、来源、召回通道、原文要点、是否位于 TARGET_WINDOW、是否属于 Active Event / Historical Context。



【2.5｜抽象提升：把产品语言翻译成技术命题】

候选池中每个条目，尤其是产品公告、UI/形态变更、套餐与定价调整、帮助中心说明、新造名词，都必须先完成抽象提升，再判定去留。

变化类型可多选：边界迁移（能力/职责在 用户↔系统、Harness↔Model、端↔云、App↔OS、人工↔自动 之间移动）；抽象合并/拆分（产品、模式、入口、API、角色合一或分化）；默认值变化（从可选变默认、从手动变自动、从显式选择变系统路由）；交互契约变化（同步↔异步、阻塞↔后台、设备绑定↔设备脱离、单轮↔持续）；新一等对象（新名词成为可创建、可共享、可计费、可调度、可恢复或可审计的对象，例如 skill、routine、artifact、session、task）；信任/权限模型变化；生命周期变化（Beta、GA、弃用、价格、可用性）；规模或成本拐点。

技术命题必须使用类似“X 从 A 移到 B，因此 C 成为新约束”的句式改写至少一条，并映射到第 2 章或第 3 章对应小节。

抽取原文中不在 known_vocabulary 中的新名词、缩写、产品名；若出现在 Tier-1 官方源或 ≥2 个独立来源，必须单独检索解释并进入候选评估；评估后更新 known_vocabulary。

对于“Claude chat 与 Cowork 合并为一个 Claude，无需选择模式，合上电脑任务继续执行”之类事件，不能只写“产品整合”，应识别为抽象合并 + 边界迁移 + 默认值变化 + 交互契约变化，并形成技术命题：模式选择从用户侧移到系统侧，任务路由开始内化；会话生命周期与客户端连接解耦，任务状态更多归属服务端/云端；context / skills / connectors 从产品面绑定转向账号级共享层。按具体机制拆到叶子：任务状态与路由内化 → C1.1/C1.3（4.1）；入口合并与交互契约 → E2.2/E1.2（4.7）；context/skills 共享层 → B2.4/B3.2。跨层影响用 related_domains 表达；只有存在内化、外置或职责调整的证据时，才附加 Model–Agent Boundary 关系标签，它不再是栏目。禁止以“属于产品/UI 更新”“不是模型发布”“不是 Runtime”“不在 Watch Matrix 中”为由直接丢弃，必须先完成抽象提升，再进入价值判断。



【3｜Tier-1 厂商 Source Surface Gate】

一级实体至少包括：OpenAI、Anthropic、Google / DeepMind、xAI、Meta、Microsoft、NVIDIA、DeepSeek、Qwen / Alibaba、ByteDance / Seed / Doubao、Moonshot / Kimi、Tencent / Hunyuan、Baidu、Zhipu、MiniMax、World Labs、Runway、Pika、Luma、Black Forest Labs、Stability AI。

至少检查：1) 官方公司/研究 Blog；2) 官方产品 Blog；3) Help Center / 用户 release notes / App 更新说明；4) Developer / API docs；5) Model catalog / model page / model card；6) Release notes / changelog / deprecations / availability / pricing；7) 官方 GitHub / releases / significant commits；8) 官方 X / 社媒作为补充。检查面必须落到 source_registry 中的具体 URL，而不是抽象类别。

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

Open-ended Frontier Discovery 必须通过机制执行：以 C / D / E 的非 Watchlist 召回为输入；以【2.5】变化类型识别 new architecture、new abstraction、new engineering layer、new paradigm、new problem decomposition；以 known_vocabulary 差集识别新名词。不得因为名称不在关键词表中而漏掉。



【6｜Full-Duplex / Realtime Agent 专项 Watch】

每天必须单独检查 Google Gemini Live、OpenAI Realtime / GPT-Live、ByteDance SeedRealtime / 豆包、xAI / Grok voice、Anthropic voice、其他头部 native audio 模型及相关论文。重点判断：S2S / unified realtime model；speech、reasoning、tool execution 是否并行；blocking vs async tool semantics；client/runtime state 是否发生变化；turn completion 与 task completion 是否仍是同一语义；后台 reasoning / tool 是否可在前台语音继续时运行。若这些能力改变“实时 Agent 前台 + 后台推理 / 工具”的技术判断，应至少评为 A / A+ 候选，并在卡片上附加 Model–Harness 边界标签（标签不是栏目，主归属仍按具体叶子）。



【7｜固定来源 + 注意力聚合源】

固定来源：arXiv source-native feed / new / recent；Hugging Face Daily Papers / Blog / Models / Datasets / Spaces / Trending；GitHub 当日 repo / release / docs / commit / Trending；官方 Blog / Docs / Model Catalog / Release Notes / Help Center / RSS / X；Hacker News。中文优先源：机器之心、新智元、量子位、AI科技评论、智东西、DeepTech深科技、AI科技大本营、极客公园、硅星人Pro。专家原始博客 / X / 访谈 / 演讲。注意力聚合源：Techmeme、Hacker News 首页、Simon Willison、The Decoder、Latent Space、AlphaSignal、TechCrunch AI、The Verge AI、上述中文媒体头条。按 Source Full-Read 读取 SCAN_WINDOW 内全部条目。聚合源条目若指向一级实体官方公告，必须回溯官方原文确认首发时刻。所有来源登记在 source_registry 中，支持动态增删，不得写死在流程里。Model Track 与 Harness Track 必须独立完成 arXiv / HF / open-web discovery，不能用一条主线结果替代另一条。



【8｜GitHub Org Diff】

对一级 Agent / Harness 项目执行 TARGET_WINDOW + 过去 48 小时 commit / release diff，至少覆盖：OpenClaw、DeepSeek Harness、Hermes、Microsoft Agent Framework、LangChain / LangGraph、LlamaIndex、CrewAI、Browser Use、Manus、OpenAI Codex / Agent、Claude Code / Cowork、Google ADK、AWS AgentCore、NVIDIA NemoClaw / OpenShell、Kimi。所有 commit 时间必须换算 Asia/Shanghai 后归档。正文中的“本轮新增”必须满足 TARGET_WINDOW。TARGET_WINDOW 之前、但位于过去 48 小时内的 commit，只能用于 Active Event、diff baseline、路线背景、连续演化判断。0 结果必须用 open web + official docs / X 复核。同时检查 GitHub Trending 中 SCAN_WINDOW 内 star 增速异常的 Agent / Model 新仓库，按 Cross-Source Resonance 进入候选池。



【9｜Active Event / 日期语义】

持续跟踪过去 3 天 A / A+：预告、Beta、论文、仓库、产品预热、模型灰度发布、API rollout、benchmark 更新。如果 TARGET_WINDOW 内出现实质新增，可作为事件更新。必须严格区分：首发日、论文 v1、revision、HF 榜单日、GitHub release、GitHub commit、媒体传播日、价格生效日、GA 生效日、rollout 开始日、文档更新日。禁止把传播日伪装成首发日。对于 TARGET_WINDOW 之前首次发布、但在本轮窗口内出现显著新增的事件，可以作为 Active Event Update 收录，但必须同时标 Original First Publish 与 Current Window Update，不能改写首发日期。



【10｜Frontier Value Gate】

每个候选独立评估 Technical Value、Evidence Confidence、Trend Maturity。Technical Value 高不等于成熟度高。若 Source Authority、Magnitude of Change、Mechanism Novelty、Quantitative Evidence、Strategic Adjacency 多数满足，可进入 A / A+ / 今日必看，并标 Frontier Signal。New Abstraction / Paradigm 即使部署早期，也必须单独评估 Abstraction Novelty、Architectural Leverage、Strategic Adjacency，不得因“像 framework / survey / position paper”自动降权。Technical Value 与 Strategic Adjacency 必须以【2.5】产出的技术命题为评估对象，并对照 thesis_map，例如 Model–Harness 能力边界、System Agent 入口与交互形态、端云任务状态归属、Agent 可信执行与权限、Realtime 前台 / 后台并行、Agent persistent state、Agent recovery / observability。判断该事件是否改变某一技术命题，而不是按原始公告产物类型判断。



【11｜Convergence / Confidence Gate】

趋势按 Event → Signal → Pattern → Thesis 评估：Cross-Entity、Cross-Form、Temporal Persistence、Adoption / Deployment、Mechanism Consistency、Counter-Evidence。趋势置信度输出 High / Medium / Low。Low 不进入核心技术判断。技术判断区分 Frontier Thesis 与 Convergence Thesis。跨实体收敛判断以【2.5】变化类型与技术命题对齐，不要求厂商使用相同名词。



【12｜Expert Thesis Watch】

至少覆盖 Andrej Karpathy、Dario Amodei、Sam Altman、Demis Hassabis、Yann LeCun、Ilya Sutskever、Geoffrey Hinton、Jensen Huang、Satya Nadella、Mustafa Suleyman、Jeff Dean、Noam Brown、Aidan Gomez、Thomas Wolf、Yoshua Bengio、Fei-Fei Li、Lilian Weng、Liang Wenfeng。分类：L1 New Statement、L2 Reactivated Thesis、L3 Thesis Validation。只有专家在 TARGET_WINDOW 内首次公开表达的新观点，才属于 L1；如果原始观点早于 TARGET_WINDOW，只是在本轮重新传播，不得伪造为 L1；L1 = 0 时必须明确写 0；禁止用二手媒体转述制造“专家新观点”。



【13｜Zero-result Gate｜强约束】

任何“无新模型”“无高价值新增”“0 命中”“某厂商今日无更新”结论都必须附采集证据。必须确认：Entity Watch 已完成；Technology Watch Matrix 对应技术面已完成；Tier-1 厂商公司面 + 产品面 + 用户帮助面 + developer/API + model catalog + release notes/model card 已完成；Source Full-Read 已完成；Cross-Source Resonance 已完成；Official Surface Diff 已完成，或记录快照不可用原因；arXiv / HF source-native open-ended scan 已完成；对相关 GitHub / 官方社媒做了补检；搜索时间范围覆盖整个 SCAN_WINDOW，而不是只搜“today”。任一面未执行，不得给 Zero-result 结论。8.1 中必须记录具体检查面、时间范围、查询方式、0 结果、无法访问的页面、快照不可用原因。



【14｜Value Ranking】

P0：Frontier Lab / 头部厂商模型；Audio / Live；Agent；Runtime；协议；架构正式发布；重要 open weights；重大能力 / API lifecycle 变化；系统级 benchmark；核心专家范式判断；头部厂商 Agent 产品形态 / 入口合并、拆分或默认行为变化。前提是经【2.5】确认改变技术命题。

P1：高质量论文 / 报告的新架构、机制、benchmark、定量证据；重大 Runtime / Framework Release；Memory / Harness / AgentInfra / MCP / A2A；New Abstraction；New Paradigm；New Engineering Layer；达到跨源共振阈值且经抽象提升确认有技术含义的事件。

P2：近 3 日 Active Event 实质增量；企业部署 / 生态落地；高价值 Thesis Validation。

P3：issue / discussion / bug 默认仅作为旁证。

主事件建议 8–14 个，宁滥毋缺。双日窗口内高价值事件明显多于 14 个，可扩大至 16–18 个，但禁止为追求数量降低证据门槛。Model / Harness 两条主线都必须保留真正改变技术判断的事件。



【15｜每个 A / A+ 的分析门槛】

至少写清：核心变化；机制 / 架构；为什么重要；Technical Value；Evidence Confidence；Trend Maturity / Frontier Signal；与近 3 日 / 历史路线关系；原始 / 补充来源；日期语义；Asia/Shanghai 首发时间；召回通道。必须额外写出变化类型与技术命题。若原文是产品语言，必须提供“产品表述 → 技术命题”对应。若属于 Model–Harness Boundary，必须明确哪些能力正在从 Harness → Model 内化；哪些 state / policy / authority 继续外置；是否改变 client ↔ server / model ↔ runtime 的职责边界。若属于 Realtime / Audio，必须明确 speech / reasoning / tool 的并行关系；blocking vs async；client/runtime state；turn completion 与 task completion；前台语音和后台任务是否解耦。



【16｜固定八章】

1 本轮结论与技术趋势：≤3 条跨栏目主线，描述本轮结构性变化的交汇，不重复栏目内的事件论证。

2 今日必看：“今日必看”指本 TARGET_WINDOW 最值得看的事件，不再局限于单一自然日。按技术价值输出 Top N，不设固定数量、不按栏目配额；达标几条列几条，不为凑数降低门槛。Top 1 深拆（架构/流程可视化）；全卡超过 5 条时，Top 1 保留深拆，其余压缩为摘要卡并指向分类章主卡。

3 模型技术热点：3.1 模型架构、训练与适应；3.2 推理、决策与效率；3.3 多模态、语音与实时模型；3.4 世界、空间与动作模型。栏目下只展开当天有入选事件的叶子；每个事件只在唯一主栏目写全卡。

4 Agent 系统技术热点：4.1 任务控制、运行与基础设施；4.2 记忆、知识与上下文；4.3 外部环境中的行动与工具使用；4.4 多 Agent 协同与互操作；4.5 学习与系统自进化；4.6 评测、验证与可信治理；4.7 交互、主动服务与持续委托。

5 值得关注：Early Signal、Active Event、Counter-signal、时间边界候选、未归类高信号。时间边界候选指首发时刻接近 WINDOW_START、时间信息存在时区歧义或仍需进一步核实的候选。未归类事件必须写明"为什么现有 54 个叶子都不覆盖"。

6 业界专家观点与趋势信号。

7 本轮技术判断：Frontier Thesis、Convergence Thesis。

8 信息源采集统计：8.1 源与覆盖审计；8.2 事件索引；8.3 候选池丢弃日志与漏检回溯。



栏目与叶子的映射以 assets/taxonomy.py 为唯一事实源，本文档不重复维护映射表。

第二、三章结构与分析深度必须对称。



【16.1｜候选池丢弃日志与漏检回溯】

候选池中被丢弃的 Tier-1 来源条目及共振命中条目，逐条记录：条目、来源、召回通道、首发时刻、是否位于 TARGET_WINDOW、处置、理由。理由必须属于明确类别，例如：未验证、重复、低影响、首发早于 WINDOW_START、首发晚于 WINDOW_END、Active Event 非新事件、错误年份、媒体转载误判、已并入其他事件、技术命题未发生变化。不得无理由丢弃。

漏检回溯 P6：每次运行对照前一次扫描窗口的注意力聚合源头条、专家讨论、当前网络热点、上一份简报，识别可能漏检项。漏检根因分类：源面未覆盖、召回通道未命中、抽象提升失败、价值误判、日期边界、时区换算错误、官方原文未回溯、搜索结果年份污染、动态页面未读取。并据此更新 source_registry、known_vocabulary、thesis_map、变化类型体系。8.3 必须使用表格呈现。



【17｜HTML】

默认交付响应式、高信息密度、专业克制的完整 HTML。**排版与图形一律由 visual-explainer skill 承担**：写 `多源技术热点简报_<DATE>.src.html`（`<html data-register="…">` + `<link rel="stylesheet" href="kit.css" data-ve-kit>`），再用 `python assets/render_html.py --src …src.html --out …html` 渲染成自包含页面；渲染器的视觉检查必须无 ✗。禁止自写主题、禁止手改渲染后的 `.html`、禁止以截图或读源码代替渲染器实测。Dashboard 必须同时显示 TARGET_WINDOW、事件总数、A / A+ 数、Frontier Signal 数、Convergence Signal 数、Active Event 数，并按 `change_object` 给出分布（Model / Harness / 运行平台 / 交互·应用 / 尚未披露）—— 不再使用旧的 Model Track / Harness Track 双轨计数。Top N 使用独立重点卡（数量按技术价值，不设固定值）。Top 1 必须给架构或流程可视化（手绘 SVG，画机制不画名字；箭头带动词，跨度带尺寸线）。每个事件必须包含：可点击原始源、Asia/Shanghai 首发时刻、日期语义、Technical Value、Evidence Confidence、Trend Maturity、变化类型、技术命题。8.1 / 8.2 / 8.3 使用表格。



【18｜附件交付 Gate】

HTML 生成后必须重新读取验收。检查：1) 文件存在且 size > 0；2) title 存在；3) H1 存在；4) 固定八章全部存在；5) 8.1 / 8.2 / 8.3 全部存在；6) 原始来源链接完整；7) TARGET_WINDOW 显示正确；8) title / H1 / Dashboard / 正文窗口 / 文件名时间范围一致；9) 8.2 中所有“本轮新事件”的 Asia/Shanghai 首发时刻必须位于 TARGET_WINDOW；10) 8.2 中早于 WINDOW_START 的事件只能标记为 Active / Historical；11) 不允许出现晚于 WINDOW_END 的正文新事件；12) 不允许残留旧版“TARGET_DATE = 单一天”的文字或审计逻辑。优先发布 conversation file 并核对真实文件对象。若未出现，再按可用机制发布持久文件并反查 file_id、filename、size_bytes > 0。只有获得真实可见文件对象才允许标 SUCCESS。



【19｜最终回复】

最终回复必须简要给出：1) TARGET_WINDOW：WINDOW_START → WINDOW_END，均为 Asia/Shanghai；2) 本轮采纳了哪些栏目（按栏目列出主卡数量）；3) 章 2 的 Top N 名单（N 由价值决定）；4) 最重要的 Model ↔ Harness 技术判断；5) 与上一轮相比最重要的新增 / 修正，如有；6) 已通过可见性验收的真实 HTML 文件入口。最终回复不得把 TARGET_WINDOW 简写成单一 TARGET_DATE。若正文同时覆盖昨天和今天，必须明确写出两个自然日及精确截止时间。
