# HTML 渲染指南 · 借用 visual-explainer 的 kit

本文件是 `SKILL.md` 步骤 5 的执行细则，属于 **tech-briefing 自己的**约束。

visual-explainer 是一个成熟的第三方 skill（MIT，v0.14.0）。**本文件不修改它、不评价它**，
只记录一件事：把"日报的八章内容"塞进它的渲染器时需要遵守什么。

分三类写，不要混：

- **§2 我们的门禁要求** —— `verify_gates.py` 是本地脚本，它的切分规则决定了 HTML 必须长什么样
- **§3 kit 的既定用法** —— kit 已经声明好的行为，照着用即可；违反它会报 `✗`，那是我写错，不是它有问题
- **§4 我踩过的坑** —— 我写错过的地方与正确写法

## 0. 设计约束（零依赖，先于 kit 生效）

以下清单不依赖任何外部 skill、渲染器或 npm 包，**写 `.src.html` 之前先过一遍**。
来源：`educlopez/ui-craft`（typeset / ui-craft-editorial）、`ConardLi/garden-skills`
（web-design-engineer 的 failure-patterns）、`nexu-io/html-anything` 的模板硬约束、
`anthropics/skills` 的 frontend-design。全部 MIT/Apache-2.0，此处只摘条款，不引入代码。

### 0.1 字号与字阶

| 规则 | 判据 |
|---|---|
| 用模数字阶，不用逐处手调的零散值 | 锚定 1.125 / 1.2 / 1.25 之一，取值落在 `12/14/16/20/24/32/48/64` |
| 禁止 13px / 15px / 17px 这类一次性尺寸 | 除非光学补偿，否则一律回到字阶 |
| 正文 ≥ 14px，标签 ≥ 12px | 与 kit 的 12px 门禁同源；`look.mjs` 会实测 SVG 标签 |
| 中文正文行高 1.7–1.8 | 西文 1.5–1.65 偏紧，中文需要更大行距 |

### 0.2 tracking / leading / 字重

| 场景 | 规则 |
|---|---|
| ≥ 24px 标题 | `letter-spacing: -0.02em` 或更紧；40px+ 可到 `-0.035em` |
| 14–20px 正文 | 默认 tracking，不额外加 |
| 11–13px 标签 | `+0.06em` 且允许大写（**唯一**允许 all-caps 的地方） |
| 标题 / 导航 / 按钮 / 表格头 | **禁止全大写** |
| 标题 leading | 1.05–1.15 |
| 正文 leading | 1.5–1.65；中文 1.7–1.8 |
| UI 元素 leading | 1.2–1.3 |
| 字重 | 最多 2–3 档（400 正文 / 500 UI / 600–700 标题），不要为了"保险"加载 9 档 |

### 0.3 字体选择

- **Inter / Roboto / Arial / system-ui / Instrument Serif 不得作为"品牌性"的展示字体**。
  它们作为回退链是合理的，作为唯一字体是 AI 生成页面的头号破绽。
- 一个正文字体 + 可选一个展示字体，**绝不超过两个**。
- 中文字体栈必须显式写 `'Noto Sans SC'` / `'Source Han Sans SC'`，不能只靠系统默认。
- 中文**禁用首字下沉（drop cap）**：放大一个汉字会把相邻汉字挤成孤行（本轮 A/B 实测，
  「窗口统计」被拆成「窗」+「口统计」）。西文用 drop cap 才有意义。

### 0.4 间距与网格

- 8px 基线网格：所有 spacing / line-height / font-size 取 8 的倍数。
- **标题上方空间是下方空间的 2–3 倍**（`margin-top ≈ 2–3 × margin-bottom`）。
- 主内容区有宽度上限（本 skill 用 `max-width: 1080px`），不贴边。
- 禁止"每段都套圆角卡片"（cardification）：容器只在**分组、可选中、需要层次**时才用。

### 0.5 可读性与无障碍

- 正文字对比度 **≥ 4.5:1**；每个可交互元素有真实 `:focus` 态。
- 尊重 `prefers-reduced-motion`：超过简单状态反馈的动效必须可关。
- 所有 `<svg>` 带 `aria-label`，纯装饰写 `aria-hidden="true"`。

### 0.6 反 AI-slop（这些是识别度最高的破绽）

| 破绽 | 为什么是破绽 | 正确做法 |
|---|---|---|
| 每个标题上方一行全大写小标签 | 形成机械化模板节奏 | 只在真正需要分类时用；否则用导语句 / 数字 / 引言变化层级 |
| 每段都进圆角卡片 | 视觉重量均质化，没有主次 | 用留白、对齐、分隔线、排版区分 |
| 居中大标题 + 渐变 + 两个 CTA | 统计意义上的默认值，不是设计决策 | 按内容层级重新构图 |
| 01 / 02 / 03 编号 | 内容不是序列却强行编号 | 删掉，或换成真实序号 |
| 编造的数据 / 评价 / logo 墙 | 假可信度比诚实的空缺更糟 | 标"未披露"或留占位 |
| 装饰性版本号 / 假坐标 / 状态点 | 不帮助理解的信息 | 删除，或连接到真实状态 |

### 0.7 数据图表的诚实性

- **数字必须有对比语境**：基线、上期、目标或同类组，缺一即无意义。
- **data-ink ratio**：删掉网格线、3D、阴影、渐变；比较类图从 0 起、按值排序。
- **一图一主张**：`<figcaption>` 写结论，不写"如图所示"。
- **不要让装饰遮蔽比较**：发光、阴影、动画若削弱比例判断，一律去掉。
- 图表容器必须有显式高度（`<div style="position:relative;height:240px">`）；
  只给 `<canvas height=>` 当布局会让响应式图表陷入 ResizeObserver 死循环。

### 0.8 简报特有的密度取舍

本 skill 的内容形态是「分析型 + 重比较」，对应 Information Density **7–8 档**，
不是营销页的 4–6 档。因此：

- 允许高密度表格、逐条论点、并列对比表；**不要**为了"呼吸感"把比较拆散。
- 但高密度 ≠ 均质重量：主卡 / 摘要卡 / 折叠深拆必须三层区分（见 §9、§10.5）。
- 「呼吸感」靠留白与折叠获得，**不靠删内容**。

## 1. 职责边界

| 谁 | 负责 |
|---|---|
| tech-briefing | 内容：八章结构、事件卡字段、8.1/8.2/8.3 审计、窗口一致性、门禁可判的锚点与表格 |
| visual-explainer | 形式：register、figure 设计、KPI、表格样式、字体配色、响应式与可读性检查 |
| `verify_gates.py` | 只校验事实与结构，**不校验美观**；两者互不替代 |

页面只有三样自写内容：本页少量布局类、figure 里的 SVG、`data-column` 之类的门禁标记。
其余样式全部来自 kit。

## 2. 我们的门禁要求（`verify_gates.py` 决定，不是 kit 决定）

这些约束来自本地脚本如何解析 HTML，与 visual-explainer 无关。

| 要求 | 门禁怎么切 | 正确写法 |
|---|---|---|
| 卡片边界 | 用正则 `<div class="card[^"]*">` 切卡，**`class` 只要以 `card` 开头就算一张卡** | 卡片外层只用 `class="card"`；头部元素必须换名（本轮用 `class="chead"`，写成 `card-head` 会被当成第二张空卡，触发"主卡归位""4.6 标注"误报） |
| 栏目锚点 | 按 `<h3-6 id="s(\d)-(\d)">` 切段，值必须是 `s<章>-<栏目号>` | 栏目用 `h3`/`h4`，如 `<h3 id="s4-6">` |
| 章节锚点 | 八章按 `<section id="s1..s8">` 认 | 章必须用 `<section>`，不是 `<div>` |
| 8.2 时刻 | 按 `id="s8-2"` 切段后抓 `YYYY-MM-DDTHH:MM` | `<td class="mono">2026-10-27T06:01</td>`，与 EV JSON 分钟级一致 |
| 折叠卡 | 看 `data-column` 声明的栏目是否有独立片段 | 单条栏目折进相邻栏目时，卡片加 `data-column="3.4"`，且该栏目**不渲染标题** |
| 4.6 标注 | 在 4.6 片段内逐卡找标签词 | 卡片正文写具体技术域（评测环境/结果核验/…），与 `primary_path` 叶子一致 |
| 8.1 截断披露 | 在 `id="s8-1"` 片段内找关键词 | 正文明确出现"覆盖不完整""窗口截断""前半段"之一，只列源名不算披露 |
| 来源链接 | 全文数唯一 `http(s)` | ≥10 个；每张卡保留原始链接，8.3 也带链接 |

**表格闭合**也要对齐：`<div class="ve-table"><table>…</tbody></table></div>`。
写成 `</div></table>` 时浏览器会自愈，但门禁按 `id="sN-M"` 切段会切错位置。
提交前用 `grep -c "<table"` 与 `grep -c "</table>"` 数一遍。

## 3. kit 的既定用法（照着做就好）

| kit 的规则 | 出处 | 我该怎么写 |
|---|---|---|
| `.ve-svg` 的字号以 **14 单位**为基准保证 ≥12px | `kit/kit.css:128` 注释 "keeps 14-unit labels >= 12px as rendered" | SVG 内文字 ≤14 单位时，viewBox 宽 ≤816 才安全；`ve-label` 是 `--t-label`（.75rem = 12 单位），**放在 SVG 里就会触发小字告警** —— 需要小标题时用 14 单位，或干脆不放进图里 |
| 边先画、节点后画、标签最后 | `references/kit.md` 的 Node/Edge 顺序 | `<path class="ve-e">` 全部写在前，`<g class="ve-n">` 其后 |
| `ve-el` 的 `--bg` 光晕只能压**先画**的线 | `look.mjs` 的 halo 判定（`later(t, sh.e)`） | 标签写在它所标注的边之后；不要让标签压在后画的线上 |
| `.ve-n text` 是 `text-anchor: middle`，居中在 `x` | `kit/kit.css:133` | 节点内的文字必须落在节点框内；跨行说明文字要放进独立节点，不能挂在别的形状旁边 |
| 异形节点（`path.sh` + `ellipse.sh.lid`）只放自己的名字 | `references/diagrams.md` | 说明性文字换成矩形节点承载，罐体只留标题 |
| viewBox 宽 >816 时 kit 自动加 `--ve-min` | `kit/render.mjs:112` | 不用手写 `min-width`；窄屏由 `.frame` 横向滚动 |
| 每张 `<svg>` 都要 `aria-label` | `render.mjs` 校验 | 纯装饰写 `aria-hidden="true"` |
| `history.replaceState` 在 `file://` 下会抛错 | kit 已用 `try/catch` | 自写导航脚本也要 `try/catch` |

**结论**：`✗` 里凡是几何类报错（标签穿框、标签过小、文字越界），先假设是我违反了上面某条，
而不是 kit 有缺陷。

## 4. 我踩过的坑与正确写法

| 我写错的 | 现象 | 正确写法 |
|---|---|---|
| 在 SVG 顶部加 `<text class="ve-label">` | 390px 下报"label renders at 10.94px" | 该行标题放进 `figcaption` 或 `h2`；图内小标题用 14 单位 |
| 把说明文字写在罐体右侧（`x` 在罐体外） | 报"label crossed by a border" | 罐体只放自己的名字；说明文字另起一个 `<g class="ve-n"><rect class="sh">` |
| 标签写在边之前 | 报"label crossed by a line" | 边 → 节点 → 标签，顺序不能倒 |
| `</div></table>` | 浏览器自愈，门禁切段错位 | 逐块数结束标签 |
| `class="card-head"` | 门禁多切出一张空卡 | 头部用 `chead` 等非 `card` 前缀 |
| `class="card-grid"`（网格 wrapper） | 门禁 `_card_bodies` 正则把网格 div 当卡 → `?@4.6` 误报 | 网格 wrapper 用 `grid-cards` 等不以 `card` 开头的名字（见 §10.5） |

## 5. 图表配额（我们的内容要求）

| 位置 | 图 | 规则 |
|---|---|---|
| 首屏 | 1 张"本轮结构性变化"合成图 | 3 个输入 → 1 个落点 → 2 个后果 |
| 章 2 Top 1 | 至少 1 张机制图 | 画机制不画名字：箭头带动词、跨度带尺寸线、关键节点 `.is-key` |
| 章 8.1 | 1 个数据图 | `<ve-bars>` / `<ve-waffle>` / `<ve-stack>` |
| 每张图 | `<figcaption>` | 一句话说出结论，不是"如图所示" |

数字成图：跨度用尺寸线，占比用 `<ve-stack>`/`<ve-waffle>`，比较用 `<ve-bars>`（从零起、按值排序）。

## 6. register 选择

| 内容 | register |
|---|---|
| 默认（日报形态） | `instrument` |
| 架构/流程图为主的一期 | `blueprint` |
| 长阅读专题 | `paper` |

`data-register` 写在 `<html>` 上。不自造配色；需要切主题时按 visual-explainer 的
`references/themes.md` 实现，而不是手写两套 CSS。

## 7. 渲染节奏（实测 2~3 轮收敛）

| 轮次 | 做什么 | 典型 `✗` |
|---|---|---|
| 1 | 写完 `.src.html` 直接渲染 | 结构类：标签错位、figure 缺 caption、SVG 缺 `aria-label`、`ve-bar` 数值非法 |
| 2 | 修结构，再看几何 | 几何类：标签穿框、标签 < 12px、文字越界 |
| 3 | 微调节点位置 | 通常剩 1~2 条，改完即 `✓` |

- 几何错误一次只修一处，改多会引入新的穿过。
- 报"标签 < 12px"时先想"这句能不能不放进图"，删掉比缩 viewBox 快。
- `sheet-*.png` 用来判断**图是否表达清楚**；格式错误 `✗` 已经说完了。
- 不要为消 `✗` 删图——图是内容的一部分。

## 8. 两道关的关系

| 关卡 | 命令 | 查什么 | 全绿不代表 |
|---|---|---|---|
| 视觉 | `render_html.py` | 标签字号、遮挡、横向溢出、figure 完整性 | 内容正确（数字可能是错的） |
| 内容 | `verify_gates.py` | 字段对得上事实源、窗口一致、归类归位 | 页面可读（可能 10px 字） |

## 9. 视觉呼吸感硬约束（避免压抑拥挤）

简报内容密度高（18 事件 + 10 张 A/A+ 深拆），默认 instrument register 的紧凑表格风会让
页面压抑拥挤。在 `<style>` 里必须落实以下三层呼吸感，缺一会让"信息密度"变成"视觉压迫"：

**层 1 · 主区与章节留白**

```css
main{max-width:1080px;margin:0 auto;overflow-x:hidden}
section{margin-top:var(--s-8);padding-top:var(--s-6);border-top:1px solid var(--border)}
section:first-of-type{border-top:none;margin-top:var(--s-6)}
header{padding-bottom:var(--s-6);border-bottom:1px solid var(--border);margin-bottom:var(--s-2)}
```

- 主区不贴边、居中、有上限宽度；章节之间用 hairline + `--s-8` 大间距分隔，而非紧凑堆叠。
- `section:first-of-type` 去掉首章顶部的 border，避免首屏出现双线（header 底线 + 章顶线）。

**层 2 · card 减重**

```css
.card{padding:var(--s-5);margin-bottom:var(--s-6);border:1px solid var(--border);
      border-radius:var(--r-2);background:var(--bg)}
h3{margin-top:var(--s-6);margin-bottom:var(--s-3)}
.summary-card{padding:var(--s-3) var(--s-4);margin-bottom:var(--s-3);
              border-left:2px solid var(--accent);background:transparent}
```

- card 内距从 `--s-4` 抬到 `--s-5`，card 间距从 `--s-5` 抬到 `--s-6`——块与块之间有呼吸。
- summary-card（章 2 折叠卡）用 2px 左边线 + 透明背景，视觉重量远低于主卡，避免一排卡片
  看起来像等重方块墙。
- h3 栏目标题前 `--s-6` 后 `--s-3`，符合 style-guide「space above a heading is 2–3× the space below it」。

**层 3 · 深拆四节折叠进 `<details>`**

```css
.deep-dive{margin-top:var(--s-4);border-top:1px solid var(--border);padding-top:var(--s-3)}
.deep-dive > summary{cursor:pointer;list-style:none;font-size:var(--t-small);
  color:var(--text-dim);display:flex;align-items:center;gap:var(--s-2);padding:var(--s-2) 0}
.deep-dive > summary::-webkit-details-marker{display:none}
.deep-dive > summary::before{content:"▸";transition:transform var(--fast) var(--ease);color:var(--accent)}
.deep-dive[open] > summary::before{transform:rotate(90deg)}
.deep-dive > summary .dd-label{font-weight:600;color:var(--text)}
```

- A/A+ 卡的「挑战/机制/效果/对比」四节用 `<details class="deep-dive">` 包裹，默认折叠。
  主卡只露：标题 + meta-line + kv 表 + 一段摘要。这是 style-guide §3
  「Overview, then detail. Raw material goes in `<details>`」的直接应用。
- 平铺四节会让每张 A/A+ 卡变成 800+ 字的密集长方块，10 张连排阅读沉重；折叠后主卡
  视觉重量大降，读者按需展开深拆。
- 自定义 `▸` 箭头随 `[open]` 旋转，给折叠状态一个轻量视觉提示，不依赖默认的三角标记
  （默认标记在各浏览器表现不一致）。
- 门禁读 HTML 文本，details 折叠不影响四节检测——`<h4>挑战与问题</h4>` 仍在 DOM 里。

**反例**：不做这三层时，18 事件 + 10 张深拆四节全平铺，页面变成一面密密麻麻的灰底方块墙，
首屏没有任何视觉锚点，读者从顶部滑到底部找不到呼吸的间隙。信息密度本身没问题，问题是
**所有内容都被赋予了相同的视觉重量**——没有主次、没有折叠、没有留白。


先跑视觉（步骤 5 末尾）再跑内容（步骤 6a）：改 `.src.html` 比改事件 JSON 便宜。

## 10. 暖色调 editorial 报头 + 全章节 panel 化（借鉴宽屏样例）

§9 解决"压抑"，本节解决"平淡"——把技术文档升级为 editorial 简报视觉风格。
在 `<style>` 里落实以下结构，配合 §9 三层呼吸感使用。

### 10.1 intro 区深层推理框（事实层 + 推理层）

intro 区不只是列举事件，必须分两层。**缺推理层不成稿**：

```html
<section class="intro" aria-labelledby="report-title">
  <p class="eyebrow">TODAY'S TECHNICAL INSIGHT</p>
  <h1 id="report-title">模型档位分化、世界模型工程化与 agent 架构解耦</h1>
  <p class="dek">今日关注三条技术主线：...（事实列举 + 统计数据）。</p>
  <p class="reasoning"><span class="r-label">深层推理</span>三条主线并非孤立事件，
    它们共同指向 <b>agent 技术栈的全栈解耦</b>：...（跨层推理 + 叠加效应）。
    但四层解耦的因果链尚未由单一来源证实，应视为本轮窗口内的分析假设而非已确立结论。</p>
</section>
```

```css
.intro .dek{font-size:15px;line-height:1.8;color:#51585d;max-width:1120px;margin:15px 0 0}
.intro .reasoning{font-size:14px;line-height:1.8;color:#51585d;max-width:1120px;
  margin:14px 0 0;padding:14px 18px;background:var(--accent-soft);
  border-left:3px solid var(--accent);border-radius:0 8px 8px 0}
.intro .reasoning .r-label{font-size:10px;letter-spacing:.12em;text-transform:uppercase;
  color:var(--accent);font-weight:700;margin-right:7px}
```

写作纪律：
- **不强行汇总到单一技术方案**：h1 仍是多命题并列；reasoning 框是"潜在价值"而非"已证实结论"。
- **必须标证据边界**：跨事件推理的因果链未经单一来源证实时，结尾写明"应视为本轮窗口内的分析假设而非已确立结论"。
- **可空但不可假**：若本轮事件间无明确跨层关系，写"本轮事件以独立信号为主，未发现跨层收敛"，不得编造因果。

### 10.2 masthead 报头 + h1 内容标题 + window-line

h1 是**内容标题**（如"模型档位分化、世界模型工程化与 agent 架构解耦"），不是时间戳。
时间窗口降为 `window-line` 小字。

```html
<header class="masthead">
  <div class="brand">
    <div class="brand-mark" aria-hidden="true"></div>
    <div>
      <div class="brand-title">多源技术热点简报</div>
      <div class="brand-sub">TECHNOLOGY INSIGHT BRIEF</div>
    </div>
  </div>
  <div class="mast-meta">DAILY EDITION&nbsp; / &nbsp;2026.10.28</div>
</header>
<div class="window-line">采集时间范围：2026-10-27 00:00 — 2026-10-28 09:46（Asia/Shanghai，UTC+08:00） · 跨度 33.8 h</div>
```

```css
.masthead{display:flex;align-items:center;justify-content:space-between;gap:20px;
  padding:24px 0 18px;border-bottom:1px solid var(--border-bright)}
.brand{display:flex;align-items:center;gap:12px;min-width:0}
.brand-mark{width:4px;height:34px;border-radius:4px;background:var(--accent);flex:0 0 auto}
.brand-title{font-size:16px;font-weight:700;letter-spacing:.02em;color:var(--text)}
.brand-sub{font-size:10px;letter-spacing:.16em;color:var(--text-dim);margin-top:1px}
.mast-meta{font-size:11px;color:var(--text-dim);text-align:right;white-space:nowrap}
.window-line{font-size:11px;color:var(--text-dim);margin:15px 0 24px;letter-spacing:.01em}
.intro{padding:0 0 30px}
.intro .eyebrow{font-size:11px;letter-spacing:.12em;text-transform:uppercase;
  color:var(--accent);font-weight:700;margin:0 0 9px}
.intro h1{font-size:clamp(26px,3vw,40px);line-height:1.2;letter-spacing:-.035em;
  margin:0;max-width:1180px;font-weight:760}
```

### 10.3 暖色调配色 + 强制浅色主题

```css
:root{color-scheme:light}
html:root{
  --bg:#f3f2ee; --surface:#ffffff; --border:#e1ded7; --border-bright:#d3cfc5;
  --text:#252b30; --text-dim:#6e7478; --accent:#9b7842; --accent-soft:#f4ecdf;
  --accent-dim:rgba(155,120,66,.12); --teal:#4c7771; --violet:#786a91;
  --shadow:0 8px 26px rgba(40,42,40,.035);
}
@media (prefers-color-scheme: dark){
  html:root{ /* 重复浅色值，覆盖 instrument register 的深色默认 */
    --bg:#f3f2ee; --surface:#ffffff; --border:#e1ded7; --border-bright:#d3cfc5;
    --text:#252b30; --text-dim:#6e7478; --accent:#9b7842; --accent-soft:#f4ecdf;
    --accent-dim:rgba(155,120,66,.12); --teal:#4c7771; --violet:#786a91;
    --shadow:0 8px 26px rgba(40,42,40,.035);
  }
}
```

### 10.4 全章节 panel 化

**sec-head**（章标题加 hairline + kicker）：
```css
.sec-head{display:flex;align-items:baseline;justify-content:space-between;gap:18px;
  margin:0 0 18px;padding-bottom:12px;border-bottom:1px solid var(--border-bright)}
.sec-head h2{font-size:19px;line-height:1.35;margin:0;font-weight:730;letter-spacing:-.02em}
.sec-head .ve-label{font-size:10px;color:var(--text-dim);letter-spacing:.12em;
  text-transform:uppercase;white-space:nowrap}
```

**stats-panel**（KPI 深底大字，替代扁平 kpi）：
```css
.stats-panel{background:#e9e6df;border:1px solid #dedad1;border-radius:13px;
  padding:22px 25px;margin:24px 0}
.kpis{margin:0;display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:18px}
.kpi{padding:0;border-right:1px solid #d4d0c7;padding-right:15px;
  background:transparent;border-radius:0;display:flex;flex-direction:column;gap:5px}
.kpi:last-child{border-right:0}
.kpi .val{font-size:30px;line-height:1.2;font-weight:750;letter-spacing:-.04em;
  font-variant-numeric:tabular-nums;color:var(--text)}
.kpi .ve-label{font-size:11px;color:#77766f}
```

**ve-table**（圆角 + 表头浅底 + 行间 hairline）：
```css
.ve-table{border:1px solid var(--border);border-radius:10px;overflow:hidden;
  background:var(--surface);box-shadow:var(--shadow)}
.ve-table th{background:#f5f3ee;font-size:11px;letter-spacing:.04em;color:#6f6a5d;
  text-transform:uppercase;font-weight:650;padding:11px 14px;text-align:left;
  border-bottom:1px solid var(--border-bright)}
.ve-table td{padding:11px 14px;border-bottom:1px solid #efede8;font-size:13px;color:var(--text)}
.ve-table tr:last-child td{border-bottom:0}
.ve-table a{color:var(--accent);text-decoration:none}
```

**figure-panel**（图独立面板）+ **thesis-grid**（章7 左边线分级）+ **sources-panel**（chip 化）：
```css
.figure-panel{background:var(--surface);border:1px solid var(--border);
  border-radius:13px;padding:23px 25px 18px;box-shadow:var(--shadow);margin:18px 0}
.thesis-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:12px 0 18px}
.thesis-grid > .card{margin-bottom:0;padding:18px 20px;border-left:3px solid var(--accent)}
.thesis-grid > .card.conv{border-left-color:var(--teal)}
.sources-panel{background:#e9e6df;border:1px solid #dedad1;border-radius:13px;padding:20px 25px;margin-top:24px}
.sources-panel .src-chips{display:flex;flex-wrap:wrap;gap:7px}
.sources-panel .src-chips a{display:inline-flex;align-items:center;gap:5px;
  padding:5px 10px;background:rgba(255,255,255,.66);border:1px solid #ddd8ce;
  border-radius:5px;font-size:11px;color:#565b5d;text-decoration:none}
```

### 10.5 事件卡分级 + 多列网格

A+ 单列深拆，A/B 级用 `grid-cards`（**不能用 `card-grid`**）包 2 列。
chead 改 chead-top（eyebrow 带 dot + event-num 右上角）+ h3 双行结构。

```css
.chead{display:flex;flex-direction:column;gap:10px;margin-bottom:14px}
.chead-top{display:flex;align-items:center;justify-content:space-between;gap:12px}
.chead .eyebrow{margin:0;font-size:11px;letter-spacing:.04em;
  display:inline-flex;align-items:center;gap:7px;padding:5px 9px;border-radius:5px;font-weight:650}
.card{padding:23px 23px 20px;margin-bottom:18px;border:1px solid var(--border);
  border-radius:13px;background:var(--surface);box-shadow:var(--shadow);
  display:flex;flex-direction:column;min-width:0}
.card[data-grade="ap"]{border-left:4px solid var(--accent)}
.card[data-grade="ap"] .eyebrow{color:#62533d;background:#f5f0e7;border:1px solid #eee4d4}
.card[data-grade="ap"] .eyebrow::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--accent)}
.card[data-grade="a"] .eyebrow{color:#3e6c65;background:#edf4f2;border:1px solid #e0ece8}
.card[data-grade="a"] .eyebrow::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--teal)}
.card[data-grade="b"] .eyebrow{color:#665783;background:#f1eef6;border:1px solid #e7e1f0}
.card[data-grade="b"] .eyebrow::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--violet)}
.event-num{font-size:11px;color:#aaa59a;letter-spacing:.12em}
.grid-cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin-bottom:24px}
.grid-cards > .card{margin-bottom:0}
@media (max-width:900px){.grid-cards{grid-template-columns:1fr}}
```

## 11. 我踩过的坑（暖色调 panel 化批次）

| 我写错的 | 现象 | 正确写法 |
|---|---|---|
| `class="card-grid"` | 门禁 `_card_bodies` 正则 `<div class="card[^"]*"` 把网格 div 当卡 → `?@4.6` 误报 | 改名 `grid-cards`（不以 `card` 开头） |
| ve-bars 在 390px 窄屏 | 标签缩到 11.97px（< 12px 门禁），SVG 缩放致标签变小 | 加 `@media (max-width:480px){.ve-bars{font-size:14px}}` 补偿 |
| sources-head 的 h2 与 span 用 flex 同行 | 渲染器报"heading sits 0 px from the span below it" | eyebrow span 在 h2 上方（block + margin-bottom），不要同行 |
| 批量包 grid-cards 用简单 `</div>` 匹配 | card 内含 `</details></div>`（一行两个 close）让深度归零提前，网格只包 1 张卡 | 用深度感知脚本（`opens-closes` 累计），遇 `</section>`/`<h3`/`<section` 关闭网格 |
| `:root` 覆盖深色主题不生效 | instrument register 深色默认优先级高 | 用 `html:root` + `@media (prefers-color-scheme: dark)` 内重复浅色值 |
