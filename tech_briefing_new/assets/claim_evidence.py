#!/usr/bin/env python3
"""claim 级证据绑定：引用的片段必须能在快照里精确匹配到。

只要求"快照文件存在"是不够的：模型可以确实抓到了原文，却凭印象写机制。
2026-10-30 回测里有一份报告把扩展投毒的加载顺序写成了另一种机制，原文并没有
那句话——快照是在的，对不上的是正文。

把每条 claim 绑到 `{snapshot, snapshot_sha256, quote}` 之后：
  - `snapshot_sha256` 对不上 → 快照在事后被换过；
  - `quote` 在快照里找不到 → 这句话不是从原文来的。
两种情况都在门禁阶段暴露，而不是等人读出来。

用法:
    python3 claim_evidence.py --events events_run_2026-10-30 --roots raw_2026-10-31 src
    python3 claim_evidence.py --hash raw_2026-10-31/anthropic_blog.html   # 取 sha256
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from pathlib import Path

# 需要 claim 级证据的评级。B/C 事件不要求——它们不承载机制论断。
REQUIRED_RATINGS = ("A", "A+")

_TAG = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.I | re.S)
_ANY_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
# 引文里的排版差异不应该算"对不上"：中英文引号、短横线、不换行空格
_FOLD = str.maketrans({
    "“": '"', "”": '"', "‘": "'", "’": "'",
    "—": "-", "–": "-", "−": "-", " ": " ",
    "（": "(", "）": ")", "：": ":", "，": ",",
})


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_text(raw: str) -> str:
    """把快照正文压成可比对的一行：去标签、解实体、折叠空白与排版差异。"""
    t = _TAG.sub(" ", raw)
    t = _ANY_TAG.sub(" ", t)
    t = html.unescape(t)
    t = t.translate(_FOLD)
    return _WS.sub(" ", t).strip()


def normalize_quote(q: str) -> str:
    return _WS.sub(" ", html.unescape(str(q)).translate(_FOLD)).strip()


def _find(path: Path, roots: list[Path]) -> Path | None:
    if path.is_absolute() and path.exists():
        return path
    for r in roots:
        p = r / path
        if p.exists():
            return p
    # 允许只写文件名：在 roots 下递归找同名文件
    for r in roots:
        hit = next((x for x in r.rglob(path.name) if x.is_file()), None)
        if hit:
            return hit
    return None


def required_for(ev: dict) -> bool:
    return str(ev.get("rating") or "") in REQUIRED_RATINGS


def verify(ev: dict, roots: list[Path]) -> list[str]:
    """校验一个事件的 claim 级证据。返回错误列表。"""
    eid = ev.get("event_id") or "?"
    claims = [c for c in (ev.get("claims") or []) if isinstance(c, dict)]
    if not required_for(ev) or not claims:
        return []

    errs: list[str] = []
    cache: dict[Path, str] = {}
    for i, c in enumerate(claims):
        tag = f"{eid} claim[{i}]"
        if str(c.get("disposition") or "").startswith("dropped"):
            continue
        evd = c.get("evidence")
        if not isinstance(evd, dict):
            errs.append(f"{tag}: 缺 evidence {{snapshot, snapshot_sha256, quote}}")
            continue
        snap = str(evd.get("snapshot") or "").strip()
        want_sha = str(evd.get("snapshot_sha256") or "").strip().lower()
        quote = str(evd.get("quote") or "").strip()
        if not snap:
            errs.append(f"{tag}: evidence 缺 snapshot（快照文件路径）")
        if not want_sha:
            errs.append(f"{tag}: evidence 缺 snapshot_sha256")
        if not quote:
            errs.append(f"{tag}: evidence 缺 quote（原文片段）")
        if not (snap and want_sha and quote):
            continue

        path = _find(Path(snap), roots)
        if path is None:
            errs.append(f"{tag}: 找不到快照 {snap}（查过 "
                        f"{[str(r) for r in roots]}）")
            continue
        got_sha = sha256_file(path)
        if got_sha != want_sha:
            errs.append(f"{tag}: 快照 {path.name} 的 sha256 是 {got_sha[:12]}…，"
                        f"声明的是 {want_sha[:12]}…；快照在事后被换过")
            continue
        if path not in cache:
            try:
                cache[path] = normalize_text(
                    path.read_text(encoding="utf-8", errors="replace"))
            except OSError as e:
                errs.append(f"{tag}: 快照不可读 {e}")
                continue
        if normalize_quote(quote) not in cache[path]:
            errs.append(f"{tag}: quote 在快照里找不到——这句话不是从原文来的。"
                        f"引的是「{quote[:40]}…」")
    return errs


def verify_dir(events_dir: Path, roots: list[Path]) -> tuple[int, list[str]]:
    errs, n = [], 0
    for f in sorted(events_dir.glob("EV-*.json")):
        try:
            ev = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            errs.append(f"{f.name}: 解析失败 {e}")
            continue
        ev.setdefault("event_id", f.stem)
        if required_for(ev):
            n += 1
        errs += verify(ev, roots)
    return n, errs


def main() -> int:
    ap = argparse.ArgumentParser(description="校验 claim 级证据绑定")
    ap.add_argument("--events", default="")
    ap.add_argument("--roots", nargs="*", default=[],
                    help="快照根目录（可多个，如 raw_<date> src）")
    ap.add_argument("--hash", default="", help="只打印某个文件的 sha256")
    args = ap.parse_args()

    if args.hash:
        p = Path(args.hash)
        if not p.exists():
            print(f"文件不存在: {p}", file=sys.stderr)
            return 2
        print(sha256_file(p))
        return 0

    if not args.events:
        print("缺 --events", file=sys.stderr)
        return 2
    roots = [Path(r) for r in args.roots] or [Path(".")]
    n, errs = verify_dir(Path(args.events), roots)
    print(f"需要 claim 级证据的事件 {n} 个")
    for e in errs:
        print("  x", e)
    print("OK" if not errs else f"{len(errs)} 处不合格")
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
