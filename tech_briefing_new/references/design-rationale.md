# 设计决策记录（Design Rationale）

本文件承载 tech-briefing-new 的"为什么"，供需要理解决策背景时查阅。SKILL.md 正文
只保留执行指令，设计 rationale 集中在此处避免稀释指令 token。

## 1. 为什么 LLM 只写 Markdown，不手写完整 HTML

手写完整 HTML 时，每张卡片的 DOM 结构、类名、内联样式都要 LLM 逐字产出，token 花在
"套模板"而不是"讲清楚技术判断"上。

**A/B 实测数据**（2026-10-27，同等信息量下）：
- LLM 输出量：MD 路线 51,390 bytes vs 旧 `.src.html` 路线 86,748 bytes → **降 41%**
- 纯文本信息量：MD 路线 28,451 字符 vs 旧路线 27,872 字符 → **102%（无信息损失）**
- HTML 总体积：因 JS runtime 内嵌，MD 路线略增，属可接受代价

结论：Markdown 只承载内容，样式与交互（目录、脚注、评注、导出、报告库索引）由
`$ASSETS/report_engine/` 机械生成。这是纯结构收益，无信息损失。

## 2. 为什么门禁校验 `.md` 而不是 `.html`

HTML 是渲染器机械生成的副本，DOM 结构随引擎版本变化；`.md` 是 LLM 唯一手写产物，
结构稳定、切分可靠。校验副本等于让渲染器结构变更静默绕过门禁——曾实测旧 HTML
门禁对新 MD 路线 HTML 全部"假绿 PASS"（0 张卡 → 唯一主卡/空栏目断言在空集上恒真）。

`--md` 通道在校验 MD 之外对 HTML 做轻量存在性断言（`check_html_lightweight`），
不重复跑旧 DOM 契约检查（`id="sN"`/`<p class="eyebrow">` 等）。

## 3. 为什么旧路线（visual-explainer + .src.html）保留作 A/B 基线

保留旧路线是为了对比验证新路线的信息完整性。新旧路线共用同一套采集/分类/评级管道，
只在渲染层分叉。禁止用旧路线产物覆盖 `reports/` 下的新路线产物——两者产物目录隔离：
- 新路线：`reports/<slug>-<date>.md` → `.html`
- 旧路线：`$WORKDIR/<title>.src.html` → `.html`

## 4. 为什么交付约定用"方案 1"（所有简报统一落 reports/）

报告库索引（`index.json` / `index.html`）依赖扁平扫描 `reports/` 目录。若简报散落
在工作目录根或其他子目录，索引找不到它们，Ctrl-O 切换器与 Reports 按钮会静默失效。
统一落 `reports/` 让交付目录与报告库根目录合一，避免维护两套路径。

## 5. 为什么 .md 不需要维护第二份副本

HTML 内嵌了完整 Markdown（`<script id="source-md">`），页面里「Save as MD」即可导出。
因此 `.md` 是工作源而非第二份交付物，不需要另外维护一份 `.md` 副本。
