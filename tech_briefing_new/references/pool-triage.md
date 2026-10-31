# 候选池筛选实操

> SKILL.md 步骤 3 的操作参考：候选池动辄 2000+ 条时的收敛顺序与各源的排序纪律。

候选池动辄 2000+ 条，逐条读会淹没。按下面的顺序收敛：

```bash
# 1) 先排除"量大但重复度高"的两类：HN 与 arXiv 单独处理
# 2) 其余源按时间排序全量过一遍（通常 40~70 条，可读完）
python - <<'PY'
import json
pool=json.load(open('raw_2026-10-27/candidate_pool.json',encoding='utf-8'))
sel=[x for x in pool if x['src'] not in ('hn_newest','hn_front') and not x['src'].startswith('arxiv')]
for x in sorted(sel,key=lambda x:(x.get('published') or '')):
    print(f"{(x.get('published') or 'NONE')[:19]:19s} {x['window_match']:6s} {x['src'][:26]:26s} {x['title'][:100]}")
PY

# 3) HN 按 points 排序 + 技术关键词过滤（points 在 snippet 里：points=NNN comments=NN）
# 4) arXiv 按 title 关键词打分，再按公告类型筛
```

三条分工纪律：

| 源 | 排序/过滤 | 注意 |
|---|---|---|
| HN（`hn_newest` / `hn_front`） | 按 `points` 降序，再用技术词过滤；不按时间 | 低分条目（points ≤ 10）里仍有真信号（如 `Init` 9 分、`Compaction Laundering` 9 分），**不能只取高分**；但也不得因低分直接判 A 级 |
| arXiv | 按 title 关键词打分，**再按 `Announce Type` 分档** | `new` 才是本轮新投稿；`cross` 是跨分类转载；`replace` / `replace-cross` 是修订版，按 task_def §9 不能当新论文，若 v2 在窗口内、v1 在窗口外，进正文时标"v2 修订" |
| 无日期源（`no_date`） | 不进本章正文，只作背景 | `carried_over` 的条目全部只能进第 5 章"持续热度" |
