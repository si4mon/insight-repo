#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用内置 report_engine 把简报 Markdown 渲染成自包含 HTML。

为什么让 LLM 只写 Markdown：手写完整 HTML 时，每张卡片的 DOM 结构、类名、
内联样式都要 LLM 逐字产出，token 花在"套模板"而不是"讲清楚技术判断"上。
Markdown 只承载内容，样式与交互（目录、脚注、评注、导出）由渲染器机械生成。

交付约定（方案 1）：
  所有简报统一落在 $WORKDIR/reports/ 下，该目录同时是报告库根目录 ——
  render 末尾会扫这个目录生成 index.json / index.html，并把索引快照回写进
  每份 HTML，使 Ctrl-O 切换器在 file:// 下可用。

    $WORKDIR/reports/<标题 slug>-<YYYY-MM-DD>.md     ← LLM 写的工作源
    $WORKDIR/reports/<标题 slug>-<YYYY-MM-DD>.html   ← 交付物
    $WORKDIR/reports/index.json / index.html         ← 报告库索引（自动生成）

.md 不是第二份交付物：HTML 内嵌了完整 Markdown，页面里「Save as MD」即可导出。
因此不需要另外维护一份 .md 副本。

用法：
  python render_report.py --md reports/xxx-2026-10-27.md
  python render_report.py --md ... --open          # 顺带起本地评注服务
  python render_report.py --check                  # 只打印引擎与 node 路径

退出码：0 渲染成功；1 渲染器报错；2 环境或参数不可用
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ENGINE_SUBDIR = "report_engine"
INDEX_FILES = ("index.json", "index.html")


def engine_dir() -> Path:
    """引擎随 skill 分发，位置由本文件自推，与客户端目录名无关。"""
    return Path(__file__).resolve().parent / ENGINE_SUBDIR


def reports_dir() -> Path:
    """报告库根目录 = 当前工作目录下的 reports/。"""
    return (Path.cwd() / "reports").resolve()


def same_path(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return False


def gate_blocker(src: Path) -> str:
    """没过门禁的稿子不许渲染。

    否则「手写统计、没跑过门禁」的 Markdown 也能产出一份看起来成稿的 HTML，
    而 HTML 是实际被阅读和转发的那一份——它一旦存在，就没人再去追门禁。
    返回空串表示放行，否则返回给人看的阻断原因。
    """
    gs = src.parent / ".gate_summary.json"
    hint = (f"  先跑: python3 verify_gates.py --md {src.name} ...\n"
            f"  只排查渲染器本身时可加 --skip-gate-check，产物不得当成稿。")
    if not gs.exists():
        return f"没有门禁摘要 {gs.name}，拒绝渲染。\n{hint}"
    try:
        data = json.loads(gs.read_text(encoding="utf-8"))
    except Exception as e:
        return f"门禁摘要无法解析（{e}），拒绝渲染。\n{hint}"

    if data.get("md") != src.name:
        return (f"门禁摘要对应的是 {data.get('md')!r}，不是 {src.name!r}，拒绝渲染。\n{hint}")
    failed = data.get("failed") or []
    if failed:
        return ("门禁未通过，拒绝渲染。失败项：\n  - "
                + "\n  - ".join(str(x) for x in failed[:8])
                + f"\n修完重跑门禁。")
    # 门禁跑在旧稿上同样不算过：.md 改过就要重跑
    try:
        if src.stat().st_mtime > gs.stat().st_mtime + 1:
            return (f"{src.name} 在门禁之后被改过，门禁结果已失效，拒绝渲染。\n{hint}")
    except OSError:
        pass
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description="把简报 Markdown 渲染成自包含 HTML")
    ap.add_argument("--md", default="", help="简报 Markdown 源文件（应位于 reports/ 下）")
    ap.add_argument("--open", action="store_true", help="渲染后起本地评注服务并打开浏览器")
    ap.add_argument("--check", action="store_true", help="只报告引擎与 node 是否可用")
    ap.add_argument("--allow-outside", action="store_true",
                    help="允许源文件不在 reports/ 下（破坏报告库索引一致性，仅用于排查）")
    ap.add_argument("--skip-gate-check", action="store_true",
                    help="跳过门禁摘要校验（只用于排查渲染器自身问题，产物不得当成稿）")
    args = ap.parse_args()

    eng = engine_dir()
    node = shutil.which("node")
    render_js = eng / "render.mjs"

    if not render_js.exists():
        print(f"找不到渲染引擎: {render_js}\n"
              f"引擎应随 skill 一起分发在 {eng}，缺失说明 skill 安装不完整。",
              file=sys.stderr)
        return 2
    if not node:
        print("找不到 node（渲染器需要 Node 18+）", file=sys.stderr)
        return 2
    if args.check:
        print(f"engine : {eng}")
        print(f"node   : {node}")
        print(f"reports: {reports_dir()}")
        return 0
    if not args.md:
        print("缺少 --md", file=sys.stderr)
        return 2

    src = Path(args.md)
    if not src.exists():
        print(f"源文件不存在: {src}", file=sys.stderr)
        return 2
    if src.suffix != ".md":
        print(f"源文件必须是 .md: {src}", file=sys.stderr)
        return 2

    rdir = reports_dir()
    if not args.allow_outside and not same_path(src.parent, rdir):
        print(f"源文件必须写在 reports/ 下，否则它不会进入报告库索引。\n"
              f"  期望目录: {rdir}\n"
              f"  实际位置: {src.resolve()}\n"
              f"把 .md 移到 reports/ 后重跑；确需在别处渲染加 --allow-outside。",
              file=sys.stderr)
        return 2

    gate_err = "" if args.skip_gate_check else gate_blocker(src)
    if gate_err:
        print(gate_err, file=sys.stderr)
        return 2

    out = src.with_suffix(".html")
    # 显式指定输出路径：渲染器默认按"标题 slug + 日期"命名，与 .md 文件名稍有出入
    # 就会产出另一个文件，门禁与报告库都找不到它。
    cmd = [node, str(render_js), str(src), str(out)]
    if not args.open:
        cmd.append("--no-open")

    print("渲染:", " ".join(cmd))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print("渲染器报错；修 Markdown 后重跑，不要手改生成的 HTML",
              file=sys.stderr)
        return 1

    if not out.exists():
        print(f"渲染器退出码为 0 但没有产出文件: {out}", file=sys.stderr)
        return 2

    # 报告库索引是本路线的核心交付能力之一：渲染完必须确认索引真的更新了，
    # 否则 Ctrl-O / Reports 按钮会静默地看不到这份报告。
    missing = [n for n in INDEX_FILES if not (src.parent / n).exists()]
    if missing:
        print(f"警告: 报告库索引缺失 {missing} —— Ctrl-O 与 Reports 按钮将不可用。",
              file=sys.stderr)

    print(f"OK  {out}  ({out.stat().st_size} bytes)")
    idx = src.parent / "index.json"
    if idx.exists():
        try:
            data = json.loads(idx.read_text(encoding="utf-8"))
            print(f"    报告库: {data.get('report_count', 0)} 份  ({src.parent / 'index.html'})")
        except (OSError, json.JSONDecodeError):
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
