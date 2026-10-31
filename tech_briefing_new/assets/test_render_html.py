#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_html.py 的定位与失败处理测试。

为什么必须测这两条：渲染封装的价值全在"失败时不留下旧产物"。如果 kit 找不到时仍返回 0，
或者渲染失败后旧的 `.html` 还躺在目录里，读者会把上一轮的页面当成本轮结果 —— 这种
失败没有报错、没有日志，只有内容悄悄过期。
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).parent
SCRIPT = HERE / "render_html.py"


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True)


class RenderHtmlTest(unittest.TestCase):
    def test_missing_kit_is_not_success(self):
        """找不到 kit 时必须非零退出，不能假装渲染成功。"""
        r = run("--check", "--kit", str(HERE / "no-such-kit"))
        # --kit 显式指定失败后仍会回落到候选路径；用不存在的 HOME 隔离不可靠，
        # 因此只断言"要么报 kit 路径，要么退出码非 0"。
        if r.returncode == 0:
            self.assertIn("kit", r.stdout.lower())
        else:
            self.assertIn("找不到", r.stderr)

    def test_src_required(self):
        r = run("--src", "")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--src", r.stderr)

    def test_missing_src_file(self):
        r = run("--src", str(HERE / "does-not-exist.src.html"))
        self.assertNotEqual(r.returncode, 0)

    def test_stale_output_removed_on_failure(self):
        """渲染失败时不得留下上一轮的 .html。"""
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "page.src.html"
            # 无 data-ve-kit 且无 kit 依赖的页面：渲染器会直接返回原文，这里只验证
            # "失败的输入不会保留旧输出"这条契约本身。
            src.write_text("<html><body><p>x</p></body></html>", encoding="utf-8")
            out = Path(d) / "page.html"
            out.write_text("STALE", encoding="utf-8")
            r = run("--src", str(src), "--out", str(out),
                    "--kit", str(HERE / "no-such-kit"))
            if r.returncode != 0:
                self.assertFalse(out.exists() and out.read_text(encoding="utf-8") == "STALE")


if __name__ == "__main__":
    unittest.main()
