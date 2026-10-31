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


# 每条 UNCOVERABLE 都必须写明补偿方式与复探期限 —— 登记一次就永久豁免，盲区就会被遗忘。
#   compensate    该面看不到时，靠什么补（已登记的替代源 / 聚合源回溯 / 每日检索任务）
#   search_terms  该实体的检索词（中英文名、主力产品名），gap_tasks 用它生成补检任务
#   recheck_by    复探期限：到期后必须重新探测该面，可达就改为登记源，仍不可达就续期并更新 reason
# 没有任何可读官方面的 Tier-1 实体，gap_tasks 每天生成一条 entity_blind 补检任务（必须关闭）。
UNCOVERABLE_RECHECK_BY = "2026-11-30"
_COMPENSATION = {
    ("Anthropic", "developer"): ("已登记 platform.claude.com/docs 与 claude.com/blog", ["Claude API", "Anthropic API"]),
    ("Anthropic", "support"): ("claude.com/blog 与聚合源回溯；8.1 标注需人工补检", ["Claude release notes"]),
    ("Google", "developer"): ("已登记 developers.googleblog.com 与 blog.google/technology/ai", ["Gemini API"]),
    ("Meta", "company"): ("聚合源（Techmeme / HN）与中文媒体回溯 + 每日检索任务", ["Meta AI", "Llama"]),
    ("xAI", "company"): ("聚合源回溯 + 每日检索任务", ["xAI", "Grok"]),
    ("DeepSeek", "company"): ("已登记 GitHub release（code 面）+ 聚合源回溯", ["DeepSeek"]),
    ("NVIDIA", "company"): ("已登记 developer.nvidia.com/blog + 聚合源回溯", ["NVIDIA AI"]),
    ("Moonshot", "company"): ("已登记 code 面（GitHub release）+ 中文媒体回溯", ["Kimi", "月之暗面"]),
    ("ByteDance", "company"): ("中文媒体（机器之心 / 量子位）回溯 + 每日检索任务", ["豆包", "字节跳动 Seed", "火山引擎 大模型"]),
    ("Tencent", "company"): ("中文媒体回溯 + 每日检索任务", ["腾讯混元", "Hunyuan"]),
    ("Baidu", "company"): ("中文媒体回溯 + 每日检索任务", ["文心", "ERNIE"]),
    ("Zhipu", "company"): ("中文媒体回溯 + 每日检索任务", ["智谱", "GLM"]),
    ("Runway", "company"): ("聚合源回溯 + 每日检索任务", ["Runway Gen", "Runway AI"]),
    ("Luma", "company"): ("聚合源回溯 + 每日检索任务", ["Luma AI", "Dream Machine"]),
    ("Black Forest Labs", "company"): ("聚合源回溯 + 每日检索任务", ["Black Forest Labs", "FLUX"]),
    ("Stability AI", "company"): ("快照差分（条目无日期）+ 聚合源回溯", ["Stability AI", "Stable Diffusion"]),
    ("Microsoft", "company"): ("已登记 devblogs（developer 面）+ 聚合源回溯", ["Microsoft AI", "Copilot"]),
}
for _u in UNCOVERABLE:
    _comp, _terms = _COMPENSATION[(_u["entity"], _u["surface"])]
    _u.setdefault("compensate", _comp)
    _u.setdefault("search_terms", _terms)
    _u.setdefault("recheck_by", UNCOVERABLE_RECHECK_BY)


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
