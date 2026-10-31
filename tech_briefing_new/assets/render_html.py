#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用 visual-explainer 的 kit 渲染简报页面。

为什么不让 LLM 手写完整 HTML：kit 提供字体、token、figure 样式与一个会**测量**页面的
渲染器（标签最小字号、标签是否被边框穿过、是否横向溢出、图是否缺 caption）。这些错误
靠人眼看 HTML 源码查不出来，靠 LLM 读一遍自证也查不出来 —— 必须真的排版一次再量。

用法：
  python render_html.py --src 多源技术热点简报_2026-10-26.src.html
  python render_html.py --src ... --out 多源技术热点简报_2026-10-26.html
  python render_html.py --check            # 只打印找到的 kit 路径

定位顺序：
  1) --kit 参数
  2) 环境变量 VISUAL_EXPLAINER_KIT
  3) 与本 skill 同级的 visual-explainer（**首选，与客户端无关**）
     本文件在 $SKILL_DIR/assets/，故 skill 根目录 = Path(__file__).parent.parent，
     skills 根目录 = 其上一级。visual-explainer 通常与 tech-briefing-* 并列安装：
       <skills-root>/visual-explainer/plugins/visual-explainer/kit
       <skills-root>/visual-explainer/kit
  4) 常见客户端 skills 根目录（~/.cac、~/.claude、~/.dsh、~/.codex、~/.config 等），
     以及项目内 .<client>/skills —— 仅作兜底，不假设只存在某一种客户端
  5) PATH 中 `visual-explainer` 包（node_modules）

退出码：0 渲染通过；1 渲染器报 ✗（页面已写出，仍需修）；2 环境不可用
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

KIT_REL = Path("visual-explainer") / "plugins" / "visual-explainer" / "kit"
KIT_REL_FLAT = Path("visual-explainer") / "kit"

# 只用来兜底列举可能的客户端 skills 根目录名；不存在的直接跳过，绝不创建。
CLIENT_ROOTS = (".cac", ".claude", ".dsh", ".codex", ".agent", ".config")


def _kit_if_valid(p: Path) -> Path | None:
    p = p.expanduser()
    return p if (p / "render.mjs").exists() else None


def sibling_kit_candidates() -> list[Path]:
    """从本脚本自身位置推导，与客户端目录名无关。"""
    skill_dir = Path(__file__).resolve().parent.parent   # $SKILL_DIR
    out = []
    for base in (skill_dir.parent, skill_dir.parent.parent):
        out.append(base / KIT_REL)
        out.append(base / KIT_REL_FLAT)
    return out


def client_skill_roots() -> list[Path]:
    """兜底：常见客户端的 skills 根目录 + 当前工作目录内的同名目录。"""
    roots = []
    home = Path.home()
    bases = [home, Path.cwd()]
    for base in bases:
        for name in CLIENT_ROOTS:
            roots.append(base / name / "skills")
    return roots


def find_kit(explicit: str = "") -> Path | None:
    if explicit:
        return _kit_if_valid(Path(explicit))
    env = os.environ.get("VISUAL_EXPLAINER_KIT", "")
    if env:
        p = _kit_if_valid(Path(env))
        if p:
            return p
    for p in sibling_kit_candidates():
        hit = _kit_if_valid(p)
        if hit:
            return hit
    for root in client_skill_roots():
        for rel in (KIT_REL, KIT_REL_FLAT):
            hit = _kit_if_valid(root / rel)
            if hit:
                return hit
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="用 visual-explainer kit 渲染简报")
    ap.add_argument("--src", default="", help="页面源文件（.src.html）")
    ap.add_argument("--out", default="", help="输出文件；默认把 .src.html 换成 .html")
    ap.add_argument("--kit", default="", help="kit 目录（含 render.mjs）")
    ap.add_argument("--check", action="store_true", help="只报告 kit 是否可用")
    ap.add_argument("--no-check", action="store_true", help="跳过浏览器视觉检查（不推荐）")
    args = ap.parse_args()

    # 先把上一轮的产物删掉：无论后面是"找不到 kit"还是"渲染报错"，
    # 都不允许目录里留着一个看起来像本轮结果的旧 .html。
    # 这一步必须在任何可能失败的分支之前执行。
    if args.src:
        src = Path(args.src)
        out = Path(args.out) if args.out else src.with_name(
            src.name[:-len(".src.html")] + ".html" if src.name.endswith(".src.html")
            else src.stem + ".html")
        if out.resolve() != src.resolve() and out.exists():
            out.unlink()

    kit = find_kit(args.kit)
    if kit is None:
        print("找不到 visual-explainer kit。安装：agentcenter skill 安装 visual-explainer，"
              "或用 --kit / VISUAL_EXPLAINER_KIT 指定包含 render.mjs 的目录。",
              file=sys.stderr)
        return 2
    node = shutil.which("node")
    if not node:
        print("找不到 node（visual-explainer 的渲染器需要 Node 18+）", file=sys.stderr)
        return 2
    if args.check:
        print(f"kit  : {kit}")
        print(f"node : {node}")
        return 0
    if not args.src:
        print("缺少 --src", file=sys.stderr)
        return 2

    if not src.exists():
        print(f"源文件不存在: {src}", file=sys.stderr)
        return 2
    if out.suffix != ".html":
        print(f"输出必须是 .html: {out}", file=sys.stderr)
        return 2

    cmd = [node, str(kit / "render.mjs"), str(src), "-o", str(out)]
    if args.no_check:
        cmd.append("--no-check")
    print("渲染:", " ".join(cmd))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print("渲染器报错或视觉检查未通过；修 .src.html 后重跑，不要手改 .html",
              file=sys.stderr)
        return 1
    if not out.exists():
        print(f"渲染器退出码为 0 但没有产出文件: {out}", file=sys.stderr)
        return 2
    print(f"OK  {out}  ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
