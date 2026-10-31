#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""渲染引擎单测：五级标题、首字下沉只用于拉丁字母、本地图片内嵌、缺图失败、输出与 .md 同名。

需要 node；没有 node 时整组跳过。
  python -m unittest test_render_engine -v
"""
import re
import shutil
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

    def test_wrapper_output_matches_md_name(self):
        # 渲染器默认按"标题 slug + 日期"命名；wrapper 必须显式指定与 .md 同名的输出
        src = self.dir / "any-name-2026-10-30.md"
        src.write_text(_md("## 章\n\n正文。", title="完全不同的标题"), encoding="utf-8")
        r = subprocess.run([sys.executable, str(HERE / "render_report.py"), "--md", str(src)],
                           capture_output=True, text=True, cwd=self.dir.parent)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(src.with_suffix(".html").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
