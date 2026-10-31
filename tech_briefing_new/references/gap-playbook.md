# 补检换通道手册

> SKILL.md 步骤 2.5 的操作参考。表中的日期、字节数是实测时的示例，不是规则。

不要用"再搜一次"去关缺口——同一通道重搜命中率不会变。按下表换形态：

| 缺口 | 通道 | 做法 | 判定依据 |
|---|---|---|---|
| `window_partial` · Techmeme | **站点逐小时归档** | `https://www.techmeme.com/<YYMMDD>/h<HHMM>`，如 `/261025/h1200`（ET 时区）。取 4 小时间隔的几个快照即可覆盖窗口前半段；标题在 `<STRONG CLASS="L4"><A CLASS="ourh" HREF="…">` 里 | 页头 `<TITLE>Techmeme @ 12:00 PM ET, October 25, 2026` 给出快照时刻；去重后数条目 |
| `window_partial` · arXiv | **`pastweek` 归档 + 周历** | `https://arxiv.org/list/<cat>/pastweek?show=2000`，页内 `<h3>` 逐个给出 `Mon, 26 Oct 2026 (showing 189 of 189 entries)` | **周末无批次**：10-24/10-25 是周六周日，故 `window_start→周一 12:00` 段确认 0 条。这是合法空，不是失明 |
| `surface_blind` · Anthropic `company` | **产品 blog + sitemap + 聚合源** | `anthropic.com/news` 恒为 HIS 代理拦截页（4202B）；读 `claude.com/blog`、`claude.com/resources/articles/*`、`anthropic_sitemap.xml` | 命中条目要能打开原文；sitemap 的 4080 条 URL **无 `lastmod`**，不能用于时间差分 |
| `surface_blind` · 任意厂商 `code` 面 | **GitHub API** | `https://api.github.com/repos/<org>/<repo>` 取 `created_at` / `pushed_at` / `stargazers_count`；`releases.atom` 取发布时间 | release 的 `published` 是秒级，可直接归窗；仓库创建时间用来区分"新项目"与"老项目新热度" |
| 首发时刻存疑（媒体转载） | **原文元数据** | HTML 里找 `"datePublished"`、`article:published_time`、`<time datetime>`、页面可见日期行 | 三者矛盾时取官方页面可见日期，并在事件里写 `date_precision_note` |
| 代理拦截的整面 | **换形态** | HTML 首页 → `.md` / `.atom` / RSS / JSON API；仍不可达则登记 `UNCOVERABLE` | 拦截页识别：HIS Proxy / 华为代理 / `mwg-internal` / "访问外部AI大模型" 提示，正文不含目标内容 |

**关闭任务时的 note 必须可复核**：写清用了哪个通道、覆盖了哪段时间、去重后几条、
其中哪些落在 TARGET_WINDOW 内。只写"已核查无问题"等于没关。
