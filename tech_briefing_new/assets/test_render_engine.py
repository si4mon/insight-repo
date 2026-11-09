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
        """--allow-gate-fail 不是「忽略失败」：稿子必须自己带降级头，
        否则产出的 HTML 看不出是降级的，比不交付更糟。"""
        src = self._draft()
        self._gate_ok(src, failed=["统计可由事件目录复算"])
        r = self._wrap(src, "--allow-gate-fail")
        self.assertEqual(r.returncode, 2)
        self.assertIn("降级头", r.stderr)
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
        """门禁通过时加不加 --allow-gate-fail 都照常渲染，不要求降级头。"""
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
