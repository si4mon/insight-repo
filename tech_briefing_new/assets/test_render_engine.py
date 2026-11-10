#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""渲染引擎单测：五级标题、首字下沉只用于拉丁字母、本地图片内嵌、缺图失败、输出与 .md 同名，
以及包装器的门禁闸门（无摘要 / 有失败项 / 门禁后改稿 一律拒绝；--allow-gate-fail 走降级交付）。

需要 node；没有 node 时整组跳过。
  python -m unittest test_render_engine -v
"""
import re
import shutil
import json
import os
import time
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).parent
RENDER_JS = HERE / "report_engine" / "render.mjs"
NODE = shutil.which("node")

SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4 4"><rect width="4" height="4"/></svg>'


def _md(body: str, title: str = "测试") -> str:
    return f"---\ntitle: {title}\ndate: 2026-10-30\nstatus: draft\n---\n\n{body}\n"


@unittest.skipIf(NODE is None, "node 不可用")
class RenderEngineTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name) / "reports"
        (self.dir / "figures").mkdir(parents=True)
        (self.dir / "figures" / "a.svg").write_text(SVG, encoding="utf-8")
        self.addCleanup(self._tmp.cleanup)

    def render(self, body: str, name: str = "r-2026-10-30.md"):
        src = self.dir / name
        src.write_text(_md(body), encoding="utf-8")
        out = src.with_suffix(".html")
        r = subprocess.run([NODE, str(RENDER_JS), str(src), str(out), "--no-open"],
                           capture_output=True, text=True)
        html = out.read_text(encoding="utf-8") if out.exists() else ""
        return r, html

    def test_level5_heading_renders_without_id(self):
        r, html = self.render("## 章\n\n### 3.2 栏目\n\n#### 卡片\n\n**A · EV-01**\n\n##### 挑战与问题\n\n正文。\n\n"
                              "#### 卡片二\n\n**A · EV-02**\n\n##### 挑战与问题\n\n正文。")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotRegex(html, r'<p[^>]*>#####', "五级标题不能以文本出现")
        self.assertEqual(len(re.findall(r'<h5[^>]*>挑战与问题</h5>', html)), 2)
        self.assertNotRegex(html, r'<h[45][^>]*\sid="', "h4/h5 不生成 id，避免重复")

    def test_dropcap_only_for_latin(self):
        _, cjk = self.render("## 结论\n\n窗口统计：本轮 12 个事件。")
        self.assertNotIn('class="dropcap"', cjk)
        _, latin = self.render("## Summary\n\nWindow stats: 12 events.", name="l-2026-10-30.md")
        self.assertIn('class="dropcap"', latin)

    def test_dropcap_only_on_first_paragraph_after_chapter(self):
        """章内后面的拉丁段落不该被选中。

        lastHeadingLevel 以前不会被段落重置，所以「Early Signal（…）」
        「Model–Harness 边界：…」这类段落只要出现在章里就会拿到首字下沉，
        连续四轮都要把中文挪到段首来规避。
        """
        _, html = self.render(
            "## 值得关注\n\n本章收的是证据不足的条目。\n\n"
            "Early Signal（本轮窗口内）：三条。",
            name="d-2026-10-30.md")
        self.assertNotIn('class="dropcap"', html)

    def test_dropcap_skips_cjk_first_paragraph_without_falling_through(self):
        _, html = self.render(
            "## 第一章\n\n中文首段。\n\nLatin second paragraph here.\n\n"
            "## Second chapter\n\nLatin first paragraph here.",
            name="e-2026-10-30.md")
        caps = re.findall(r'<p class="dropcap"[^>]*>([^<]{0,20})', html)
        self.assertEqual(len(caps), 1, caps)
        self.assertTrue(caps[0].startswith("Latin first"), caps)

    def test_local_image_inlined(self):
        r, html = self.render("## 章\n\n![结论](figures/a.svg)\n\n行内 ![x](figures/a.svg) 图。")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(html.count('src="data:image/svg+xml;base64,'), 2)
        self.assertNotIn('src="figures/a.svg"', html)

    def test_missing_image_fails_and_writes_nothing(self):
        r, html = self.render("## 章\n\n![缺](figures/none.svg)")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("image not found", r.stderr)
        self.assertEqual(html, "")

    def test_remote_image_left_as_link(self):
        r, html = self.render("## 章\n\n![远程](https://example.com/a.png)")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('src="https://example.com/a.png"', html)

    def _draft(self, name="any-name-2026-10-30.md"):
        src = self.dir / name
        src.write_text(_md("## 章\n\n正文。", title="完全不同的标题"), encoding="utf-8")
        return src

    def _gate_ok(self, src, failed=()):
        (src.parent / ".gate_summary.json").write_text(
            json.dumps({"md": src.name, "passed": 1, "failed": list(failed)}),
            encoding="utf-8")

    def _wrap(self, src, *extra):
        return subprocess.run(
            [sys.executable, str(HERE / "render_report.py"), "--md", str(src), *extra],
            capture_output=True, text=True, cwd=self.dir.parent)

    def test_wrapper_output_matches_md_name(self):
        # 渲染器默认按"标题 slug + 日期"命名；wrapper 必须显式指定与 .md 同名的输出
        src = self._draft()
        self._gate_ok(src)
        r = self._wrap(src)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(src.with_suffix(".html").exists())

    def test_refuses_without_gate_summary(self):
        """没过门禁的稿子不许渲染：HTML 是被阅读转发的那一份，它一出现就没人再追门禁。"""
        src = self._draft()
        r = self._wrap(src)
        self.assertEqual(r.returncode, 2)
        self.assertIn("没有门禁摘要", r.stderr)
        self.assertFalse(src.with_suffix(".html").exists())

    def test_refuses_when_gates_failed(self):
        src = self._draft()
        self._gate_ok(src, failed=["统计可由事件目录复算"])
        r = self._wrap(src)
        self.assertEqual(r.returncode, 2)
        self.assertIn("门禁未通过", r.stderr)
        self.assertFalse(src.with_suffix(".html").exists())

    def test_refuses_when_md_changed_after_gates(self):
        src = self._draft()
        self._gate_ok(src)
        os.utime(src, (time.time() + 60, time.time() + 60))
        r = self._wrap(src)
        self.assertEqual(r.returncode, 2)
        self.assertIn("门禁之后被改过", r.stderr)

    def test_refuses_summary_for_another_md(self):
        src = self._draft()
        (src.parent / ".gate_summary.json").write_text(
            json.dumps({"md": "other.md", "failed": []}), encoding="utf-8")
        r = self._wrap(src)
        self.assertEqual(r.returncode, 2)
        self.assertIn("不是", r.stderr)

    def test_degraded_delivery_requires_the_degraded_header(self):
        """--allow-gate-fail 不是「忽略失败」：稿子必须自己带降级节，
        否则产出的 HTML 看不出是降级的，比不交付更糟。"""
        src = self._draft()
        self._gate_ok(src, failed=["统计可由事件目录复算"])
        r = self._wrap(src, "--allow-gate-fail")
        self.assertEqual(r.returncode, 2)
        self.assertIn("降级节", r.stderr)
        self.assertFalse(src.with_suffix(".html").exists())

    def test_degraded_delivery_renders_with_the_header(self):
        src = self._draft()
        src.write_text(src.read_text(encoding="utf-8").replace(
            "## 章", "<!-- gate-degraded -->\n\n> [WARNING]\n> 本稿未通过门禁。\n\n## 章"),
            encoding="utf-8")
        self._gate_ok(src, failed=["统计可由事件目录复算"])
        r = self._wrap(src, "--allow-gate-fail")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        html = src.with_suffix(".html").read_text(encoding="utf-8")
        self.assertIn("本稿未通过门禁", html)

    def test_attempt_cap_is_named_in_the_refusal(self):
        """到达上限时的提示要指向降级交付，而不是只说「修完重跑」——
        无人值守时没人能把「一直修」执行下去。"""
        src = self._draft()
        (src.parent / ".gate_summary.json").write_text(
            json.dumps({"md": src.name, "passed": 1, "failed": ["某项"],
                        "attempt": 3, "max_attempts": 3}), encoding="utf-8")
        r = self._wrap(src)
        self.assertEqual(r.returncode, 2)
        self.assertIn("第 3/3 轮", r.stderr)
        self.assertIn("--allow-gate-fail", r.stderr)

    def test_passing_gate_still_rejects_allow_flag_noise(self):
        """门禁通过时加不加 --allow-gate-fail 都照常渲染，不要求降级节。"""
        src = self._draft()
        self._gate_ok(src)
        r = self._wrap(src, "--allow-gate-fail")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_skip_gate_check_is_an_explicit_escape_hatch(self):
        src = self._draft()
        r = self._wrap(src, "--skip-gate-check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)


@unittest.skipIf(NODE is None, "node 不可用")
class EventCardTest(unittest.TestCase):
    """事件卡的视觉隔离与双层标题。

    2026-11-10 补入。11-09 那稿的反馈是「不同技术事件之间隔离不清晰，容易迷失，
    不知道已经到下一个技术事件了」——h4 与正文字号差不足以构成边界，所以每张卡
    包进 article.event-card，靠方框和左侧强调条成立。
    """

    def _render(self, md: str) -> str:
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "t.md"
            out = Path(d) / "t.html"
            src.write_text("---\ntitle: T\ndate: 2026-11-10\nstatus: draft\n"
                           "summary: s\n---\n\n" + md, encoding="utf-8")
            r = subprocess.run([NODE, str(RENDER_JS), str(src), str(out), "--no-open"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            return out.read_text(encoding="utf-8")

    def test_each_card_is_wrapped_and_closed(self):
        html = self._render(
            "## 2 今日必看\n\n"
            "#### A 模型｜第一条\n\n**A · EV-01**\n\n正文一。\n\n"
            "##### 机制与架构\n\n小节仍属第一张卡。\n\n"
            "#### B 模型｜第二条\n\n**A · EV-02**\n\n正文二。\n")
        # 标签上会带 data-layer / data-rating，所以匹配到类名为止
        self.assertEqual(html.count('<article class="event-card"'), 2)
        # 第一张卡必须在第二张卡开始前闭合，否则两条事件会套在一起
        first = html.index('<article class="event-card"')
        second = html.index('<article class="event-card"', first + 1)
        self.assertIn("</article>", html[first:second])

    def test_higher_heading_closes_the_card(self):
        """下一个 ### / ## 必须结束上一张卡，否则卡会吃掉整节。"""
        html = self._render(
            "## 3 模型\n\n### 3.3 多模态\n\n"
            "#### A｜一条\n\n**B · EV-01**\n\n正文。\n\n"
            "### 3.4 其他\n\n普通段落，不该在卡里。\n")
        card = html.index('<article class="event-card"')
        close = html.index("</article>", card)
        self.assertNotIn("普通段落", html[card:close])

    def test_two_layer_title_split(self):
        html = self._render("#### ERNIE Evolve｜双循环接成生产闭环\n\n**A · EV-01**\n\n正文。\n")
        self.assertIn('<span class="event-card__kw">ERNIE Evolve</span>', html)
        self.assertIn('双循环接成生产闭环</span>', html)
        self.assertIn('event-card__sum', html)

    def test_title_without_bar_still_renders(self):
        """老稿子没有竖线，必须退化成单层而不是报错或吞掉标题。"""
        html = self._render("#### 没有竖线的标题\n\n**B · EV-01**\n\n正文。\n")
        self.assertIn("没有竖线的标题", html)
        self.assertIn('<article class="event-card"', html)

    def test_section_nesting_stays_valid(self):
        """article 嵌在 section 内，关卡必须早于关 section。"""
        html = self._render(
            "## 2 今日必看\n\n#### A｜一条\n\n**A · EV-01**\n\n正文。\n\n"
            "## 3 模型技术热点\n\n另一节。\n")
        import html.parser as hp

        class P(hp.HTMLParser):
            def __init__(self):
                super().__init__()
                self.stack, self.bad = [], []

            def handle_starttag(self, tag, attrs):
                if tag in ("section", "article"):
                    self.stack.append(tag)

            def handle_endtag(self, tag):
                if tag in ("section", "article"):
                    if not self.stack or self.stack[-1] != tag:
                        self.bad.append(tag)
                    else:
                        self.stack.pop()

        p = P()
        p.feed(html)
        self.assertEqual(p.bad, [], "section/article 交叉嵌套")
        self.assertEqual(p.stack, [], "有未闭合的 section/article")


@unittest.skipIf(NODE is None, "node 不可用")
class HtmlCommentTest(unittest.TestCase):
    """独占一行的 HTML 注释必须渲染成真注释，不能漏成可见文本。

    2026-11-10 发现：渲染器只认 @report-comment，其余 HTML 注释掉进段落分支被转义，
    于是门禁的降级哨兵 `<!-- gate-degraded -->` 直接印在了页面上（11-09 那稿可见）。
    哨兵要留在 HTML 里供机器识别，但不该让读者看到。
    """

    def _render(self, md: str) -> str:
        with tempfile.TemporaryDirectory() as d:
            src, out = Path(d) / "t.md", Path(d) / "t.html"
            src.write_text("---\ntitle: T\ndate: 2026-11-10\nstatus: draft\n"
                           "summary: s\n---\n\n" + md, encoding="utf-8")
            r = subprocess.run([NODE, str(RENDER_JS), str(src), str(out), "--no-open"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            return out.read_text(encoding="utf-8")

    def test_sentinel_is_a_real_comment_not_visible_text(self):
        html = self._render("<!-- gate-degraded -->\n\n## 门禁未通过项与影响\n\n正文。\n")
        self.assertNotIn("&lt;!--", html, "注释被转义成了可见文本")
        self.assertIn("<!-- gate-degraded -->", html, "哨兵必须留在 HTML 里供机器识别")

    def test_report_comment_markers_still_work(self):
        """通用注释处理不能吃掉 @report-comment 这条既有通路。"""
        html = self._render("正文一段。\n")
        self.assertIn("article", html)


@unittest.skipIf(NODE is None, "node 不可用")
class CardFacetTest(unittest.TestCase):
    """卡片按 change_object 上色、按 rating 定轻重（2026-11-10）。

    只让一个维度管色相：两个维度都上色，读者一个都认不出来。
    「尚未披露」走中性灰——信息缺失不该被画成一个类别。
    """

    LAYERS = [("Model", "model"), ("Harness", "harness"), ("运行平台", "platform"),
              ("交互·应用", "interaction"), ("尚未披露", "undisclosed")]

    def _render(self, md: str) -> str:
        with tempfile.TemporaryDirectory() as d:
            src, out = Path(d) / "t.md", Path(d) / "t.html"
            src.write_text("---\ntitle: T\ndate: 2026-11-10\nstatus: draft\n"
                           "summary: s\n---\n\n" + md, encoding="utf-8")
            r = subprocess.run([NODE, str(RENDER_JS), str(src), str(out), "--no-open"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            return out.read_text(encoding="utf-8")

    def test_each_layer_becomes_a_data_attribute(self):
        for zh, slug in self.LAYERS:
            html = self._render(f"#### X｜一条\n\n**A · Frontier · EV-01 · {zh}**\n\n正文。\n")
            self.assertIn(f'data-layer="{slug}"', html, f"{zh} 没映射成 {slug}")

    def test_rating_becomes_a_data_attribute(self):
        for r in ("A+", "A", "B", "C"):
            html = self._render(f"#### X｜一条\n\n**{r} · Early Signal · EV-01 · Model**\n\n正文。\n")
            self.assertIn(f'data-rating="{r}"', html, f"评级 {r} 没取到")

    def test_card_without_layer_stays_neutral(self):
        """老稿子没有层字段，退回中性样式而不是报错。"""
        html = self._render("#### X｜一条\n\n**B · Early Signal · EV-01**\n\n正文。\n")
        # data-layer 在样式表里本来就有，所以只看 article 标签本身
        tag = re.search(r'<article class="event-card"[^>]*>', html)
        self.assertIsNotNone(tag)
        self.assertNotIn("data-layer=", tag.group(0))

    def test_every_layer_has_a_hue_defined(self):
        """渲染出的页面里必须有每一层的色相定义，否则属性白设。"""
        html = self._render("#### X｜一条\n\n**A · Frontier · EV-01 · Model**\n\n正文。\n")
        for _, slug in self.LAYERS:
            self.assertIn(f'[data-layer="{slug}"]', html, f"{slug} 没有色相定义")

    def test_undisclosed_stays_achromatic(self):
        """「尚未披露」是信息缺失，给它色相等于把缺失说成了分类。

        它仍然要有自己的底色（否则会变成唯一一张看不出边界的卡），
        但彩度必须接近 0——判定的是彩度，不是用不用 oklch。
        """
        html = self._render("#### X｜一条\n\n**C · Early · EV-01 · 尚未披露**\n\n正文。\n")
        m = re.search(r'\.event-card\[data-layer="undisclosed"\]\s*\{([^}]*)\}', html)
        self.assertIsNotNone(m, "找不到 undisclosed 的定义")
        chromas = [float(c) for _, c in
                   re.findall(r"oklch\(\s*([0-9.]+)\s+([0-9.]+)", m.group(1))]
        self.assertTrue(chromas, "没解析到 oklch 值")
        self.assertLess(max(chromas), 0.010,
                        f"彩度 {max(chromas)} 太高，会被读成一个颜色类别")

    def test_colored_layers_actually_carry_chroma(self):
        """反过来：四个真实层的彩度必须明显高于中性档，否则等于没上色。"""
        html = self._render("#### X｜一条\n\n**A · Frontier · EV-01 · Model**\n\n正文。\n")
        for slug in ("model", "harness", "platform", "interaction"):
            m = re.search(rf'\.event-card\[data-layer="{slug}"\]\s*\{{([^}}]*)\}}', html)
            self.assertIsNotNone(m, f"找不到 {slug}")
            chromas = [float(c) for _, c in
                       re.findall(r"oklch\(\s*([0-9.]+)\s+([0-9.]+)", m.group(1))]
            self.assertGreater(max(chromas), 0.05, f"{slug} 彩度不足，等于没上色")


class CardContrastTest(unittest.TestCase):
    """卡片底色与页面底色的明度差（2026-11-10）。

    反馈「卡片颜色和背景太接近」。第一版把 B/C 卡的底色设成 var(--bg)——
    与页面完全同色，只剩 1px 边框；而历史事件里 B+C 占 51/75，等于大多数卡片没有底。
    第二版改成带色相的浅底后实测浅色模式弱档 ΔL 仍只有 0.019，还在可辨阈值以下。

    这里直接校验 template.html 里声明的 oklch 明度（CSS 的 oklch L 就是 OKLab L），
    不渲染不截图：阈值是契约，跑一次 0.01 秒，能挡住以后被悄悄调回去。
    """

    THRESHOLD = 0.030   # ΔL≈0.02 勉强可辨，≥0.03 明确可辨

    @classmethod
    def setUpClass(cls):
        cls.css = (HERE / "report_engine" / "template.html").read_text(encoding="utf-8")

    def _page_L(self, dark: bool) -> float:
        """取 :root 或 [data-theme="dark"] 里 --bg 的明度。"""
        block = self.css.split('[data-theme="dark"]')[1 if dark else 0]
        m = re.search(r"--bg:\s*oklch\(\s*([0-9.]+)", block)
        self.assertIsNotNone(m, f"找不到 {'暗' if dark else '亮'}色 --bg")
        return float(m.group(1))

    def test_every_card_fill_is_distinguishable_from_the_page(self):
        page_light, page_dark = self._page_L(False), self._page_L(True)
        fills = re.findall(r"--card-fill(?:-quiet)?:\s*oklch\(\s*([0-9.]+)", self.css)
        self.assertGreaterEqual(len(fills), 12, "底色声明数量不对，可能有漏改")
        weak = []
        for L in (float(x) for x in fills):
            # 亮色档靠近 1、暗色档靠近 0，按哪个页面底色更近来归属
            page = page_light if abs(L - page_light) < abs(L - page_dark) else page_dark
            if abs(L - page) < self.THRESHOLD:
                weak.append((L, page, round(abs(L - page), 3)))
        self.assertEqual(weak, [],
                         f"这些底色与页面明度差不足 {self.THRESHOLD}: {weak}")

    def test_no_card_fill_equals_the_page_background(self):
        """第一版的具体病因：底色直接写 var(--bg)。"""
        block = re.search(r"\.event-card\[data-rating=\"B\"\][\s\S]{0,200}?\}", self.css)
        self.assertIsNotNone(block)
        self.assertNotIn("background: var(--bg);", block.group(0),
                         "B/C 卡又用回了页面底色")

    def test_rating_bar_width_targets_the_pseudo_element(self):
        """选择器列表里漏掉 ::before 会把 width 加在卡片本身上，把整张卡压成一条。"""
        for m in re.finditer(r"([^{}]*)\{\s*width:\s*\d+px[^}]*\}", self.css):
            sel = m.group(1)
            if "event-card" in sel and "data-rating" in sel:
                for part in sel.split(","):
                    if "data-rating" in part:
                        self.assertIn("::before", part,
                                      f"这个选择器会把宽度加在卡片上: {part.strip()}")
