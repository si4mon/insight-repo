#!/usr/bin/env python3
"""GitHub 发布面的第三通道：匿名 git。

为什么需要第三条：GitHub 的两条机器可读通道（`releases.atom` 与
`api.github.com/repos/.../releases`）在有出网网关的环境里会被一并拦掉。
2026-11-01 与 2026-11-02 两轮实测，10 个代码面源全部 HTTP 403，而这 10 个源
覆盖的正是 Claude Code、OpenAI SDK 这类每天都发版的面——连续两轮手工补，
说明它该进采集器而不是留给人。

匿名 `git` 读走的是另一条路（git 协议 / git 代理），本环境可用：
  1. `git ls-remote --tags` 一次往返拿到 tag 列表（回答"有没有新发布"）；
  2. 对最近的几个 tag 浅取，拿到提交时刻（回答"是不是在窗口内"）；
  3. `raw.githubusercontent.com` 取 CHANGELOG（回答"改了什么"，并作为 claim 快照）。

本模块只做 1 与 2，第 3 步由采集器按 `git_fallback.changelog` 顺带落盘。
拿不到就老实返回空，由判定层记成失明——不编造条目。
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

# 这些 ref 不是发布：构建中间 tag、nightly 以外的噪声
_SKIP_RE = re.compile(r"(^|/)(latest|stable|edge|nightly-latest)$", re.I)
_DEREF = "^{}"


def _run(args: list[str], timeout: int) -> tuple[bool, str]:
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.returncode == 0, (p.stdout if p.returncode == 0 else p.stderr)
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, str(e)


def list_tags(repo: str, limit: int = 8, timeout: int = 90) -> tuple[list[str], str]:
    """返回 (按版本倒序的 tag 名, 错误说明)。"""
    if not shutil.which("git"):
        return [], "没有 git 可执行文件"
    ok, out = _run(["git", "ls-remote", "--tags", "--sort=-v:refname",
                    f"https://github.com/{repo}"], timeout)
    if not ok:
        return [], out.strip()[:200]
    tags = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) != 2 or not parts[1].startswith("refs/tags/"):
            continue
        name = parts[1][len("refs/tags/"):]
        if name.endswith(_DEREF) or _SKIP_RE.search(name):
            continue
        if name not in tags:
            tags.append(name)
        if len(tags) >= limit:
            break
    return tags, ""


def tag_times(repo: str, tags: list[str], timeout: int = 150) -> dict[str, str]:
    """浅取每个 tag，返回 {tag: 提交时刻 ISO}。取不到的 tag 不出现在结果里。"""
    if not tags:
        return {}
    out: dict[str, str] = {}
    with tempfile.TemporaryDirectory() as d:
        if not _run(["git", "init", "-q", d], 30)[0]:
            return {}
        if not _run(["git", "-C", d, "remote", "add", "origin",
                     f"https://github.com/{repo}"], 30)[0]:
            return {}
        for t in tags:
            if not _run(["git", "-C", d, "fetch", "-q", "--depth", "1",
                         "origin", "tag", t], timeout)[0]:
                continue
            ok, iso = _run(["git", "-C", d, "log", "-1", "--format=%cI", t], 30)
            if ok and iso.strip():
                out[t] = iso.strip()
    return out


def collect(repo: str, limit: int = 8, timeout: int = 90) -> dict:
    """产出与 extract 同形状的条目列表，可直接进候选池。"""
    tags, err = list_tags(repo, limit, timeout)
    if err:
        return {"status": "transport_failed", "error": err, "items": []}
    if not tags:
        return {"status": "empty", "error": "", "items": []}
    times = tag_times(repo, tags)
    items = []
    for t in tags:
        iso = times.get(t)
        url = f"https://github.com/{repo}/releases/tag/{t}"
        items.append({
            "uid": hashlib.sha1(f"{repo}@{t}".encode()).hexdigest()[:16],
            "title": f"{repo} {t}",
            "url": url,
            "published": iso or "",
            "date_precision": "second" if iso else "none",
            "snippet": ("tag 提交时刻（git），非 release 发布时刻"
                        if iso else "未取到 tag 时刻"),
        })
    # 一个 tag 都没取到时刻 → 不能回答"是不是窗口内"，按解析失败处理
    if not times:
        return {"status": "parse_failed",
                "error": f"{len(tags)} 个 tag 均未取到提交时刻", "items": items}
    return {"status": "ok", "error": "", "items": items}


if __name__ == "__main__":
    import sys
    for r in sys.argv[1:]:
        res = collect(r)
        print(f"{r}: {res['status']} {res['error']}")
        for it in res["items"][:4]:
            print(f"   {it['published'][:19] or '?':20} {it['title']}")
