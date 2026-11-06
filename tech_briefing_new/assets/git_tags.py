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

三步都在本模块完成。第 3 步原先写的是"由采集器按 `git_fallback.changelog` 顺带
落盘"，但采集器里从来没有这段实现——于是 git 通道产出的事件三轮都卡在 B 级：
拿得到"发了哪个版本、什么时刻"，拿不到"改了什么"的可引证原文，而 A / A+ 要求
claim 绑定到快照里的原文片段（task_def 15.1）。openai-python / openai-node 同分钟
配对发布连续两个窗口出现，只能描述成"节奏"，就是因为这个。

第 3 步不走 raw.githubusercontent.com（和 atom / API 一样会被拦），而是利用
tag 浅取之后本地已有的树：版本间 `git diff <prev> <tag> -- CHANGELOG.md` 的新增行
就是这次发布的内容；取不到就退到发布提交正文（release-bot 仓库写在那里），
再退到 CHANGELOG 开头若干行。拿不到就老实返回空，由判定层记成失明——不编造条目。
"""
from __future__ import annotations

import datetime
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


def _to_utc(iso: str) -> str:
    """把 %cI 归一到 UTC。

    git 的 %cI 带的是**提交者本地**的时区偏移，不是 UTC：同一次采集里
    anthropic 的 tag 回来是 +00:00，而 QwenLM 的回来是 +08:00。原始文件里
    混着两种偏移，读的人很容易再按 +08 换一次——2026-11-02 那份简报就把
    qwen-code v0.26.6 的 11-03 01:51 写成了 09:51（nightly 那条同样差 8 小时）。
    统一成 UTC 之后，原始文件里只剩一种偏移，没有可以再换一次的空间。
    """
    try:
        return datetime.datetime.fromisoformat(iso).astimezone(
            datetime.timezone.utc).isoformat()
    except (TypeError, ValueError):
        return iso


def tag_times(repo: str, tags: list[str], timeout: int = 150) -> dict[str, str]:
    """{tag: 提交时刻 ISO}。薄封装，细节在 tag_details。"""
    return {t: d["time"] for t, d in tag_details(repo, tags, timeout).items()}



_CHANGELOG_RE = re.compile(r"^CHANGELOG(\.(md|rst|txt))?$", re.I)
NOTES_MAX_CHARS = 4000      # 单个 tag 的发布说明上限，超出截断并标注


def _changelog_path(d: str, tag: str) -> str:
    """tag 的树里 CHANGELOG 文件的路径名，没有就返回空。"""
    ok, out = _run(["git", "-C", d, "ls-tree", "--name-only", tag], 30)
    if not ok:
        return ""
    for name in out.splitlines():
        if _CHANGELOG_RE.match(name.strip()):
            return name.strip()
    return ""


def _release_notes(d: str, tag: str, prev: str | None) -> tuple[str, str]:
    """返回 (发布说明, 来源标记)。三级回退，拿不到返回空。"""
    path = _changelog_path(d, tag)
    if path and prev:
        ok, out = _run(["git", "-C", d, "diff", prev, tag, "--", path], 60)
        if ok:
            added = [ln[1:] for ln in out.splitlines()
                     if ln.startswith("+") and not ln.startswith("+++")]
            text = "\n".join(added).strip()
            if text:
                return text[:NOTES_MAX_CHARS], f"{path} diff {prev}..{tag}"
    ok, body = _run(["git", "-C", d, "log", "-1", "--format=%B", tag], 30)
    if ok and body.strip():
        return body.strip()[:NOTES_MAX_CHARS], f"发布提交正文 {tag}"
    if path:
        ok, out = _run(["git", "-C", d, "show", f"{tag}:{path}"], 60)
        if ok and out.strip():
            head = "\n".join(out.splitlines()[:60]).strip()
            return head[:NOTES_MAX_CHARS], f"{path} 开头 60 行 @{tag}"
    return "", ""


def tag_details(repo: str, tags: list[str], timeout: int = 150) -> dict[str, dict]:
    """浅取每个 tag，一次拿到提交时刻与发布说明。

    {tag: {"time": ISO(UTC), "notes": 原文, "notes_source": 出处}}。
    取不到时刻的 tag 不出现在结果里（与 tag_times 的语义一致）。
    先把所有 tag 都取下来再算 diff —— 版本间 diff 需要两个 tag 都在本地，
    边取边算会让最老的那个 tag 永远没有对照。
    """
    if not tags:
        return {}
    out: dict[str, dict] = {}
    with tempfile.TemporaryDirectory() as d:
        if not _run(["git", "init", "-q", d], 30)[0]:
            return {}
        if not _run(["git", "-C", d, "remote", "add", "origin",
                     f"https://github.com/{repo}"], 30)[0]:
            return {}
        fetched = []
        for t in tags:
            if _run(["git", "-C", d, "fetch", "-q", "--depth", "1",
                     "origin", "tag", t], timeout)[0]:
                fetched.append(t)
        for i, t in enumerate(fetched):
            ok, iso = _run(["git", "-C", d, "log", "-1", "--format=%cI", t], 30)
            if not (ok and iso.strip()):
                continue
            # tags 按版本倒序，下一个就是上一版；它也必须在本地才能 diff
            prev = fetched[i + 1] if i + 1 < len(fetched) else None
            notes, src = _release_notes(d, t, prev)
            out[t] = {"time": _to_utc(iso.strip()), "notes": notes,
                      "notes_source": src}
    return out


def notes_snapshot(repo: str, tags: list[str], details: dict[str, dict]) -> str:
    """把发布说明拼成一份快照原文，供 claim 绑定（task_def 15.1）。"""
    lines = [f"# {repo} 发布说明快照", "",
             "由 git_tags.py 从匿名 git 的 tag 树取得（atom 与 API 通道被拦）。",
             "每节的「出处」说明这段文字是 CHANGELOG 版本间 diff、发布提交正文，"
             "还是 CHANGELOG 开头——引用时按出处判断它的证据强度。", ""]
    for t in tags:
        d = details.get(t) or {}
        lines += [f"## tag {t}", "",
                  f"- 提交时刻（UTC）: {d.get('time') or '未取到'}",
                  f"- 出处: {d.get('notes_source') or '未取到'}", ""]
        notes = (d.get("notes") or "").strip()
        # 发布说明自带 Markdown 标题，围栏起来才不会和节标题混在一起；
        # claim 的引文比对是子串匹配，围栏不影响。
        lines += (["```", notes, "```", ""] if notes
                  else ["（未取到发布说明）", ""])
    return "\n".join(lines)


def collect(repo: str, limit: int = 8, timeout: int = 90) -> dict:
    """产出与 extract 同形状的条目列表，可直接进候选池。

    除条目外还带 notes_snapshot：发布说明的快照原文，由采集器落盘，
    让 git 通道的事件也能满足 A / A+ 的 claim 级证据要求。
    """
    tags, err = list_tags(repo, limit, timeout)
    if err:
        return {"status": "transport_failed", "error": err, "items": []}
    if not tags:
        return {"status": "empty", "error": "", "items": []}
    details = tag_details(repo, tags)
    items = []
    for t in tags:
        d = details.get(t) or {}
        iso = d.get("time")
        notes = (d.get("notes") or "").strip()
        url = f"https://github.com/{repo}/releases/tag/{t}"
        # snippet 带上发布说明：打分与选题读的是 snippet，只写"tag 提交时刻"
        # 等于把"改了什么"藏在快照里不给下游看。
        base = ("tag 提交时刻（git），非 release 发布时刻"
                if iso else "未取到 tag 时刻")
        items.append({
            "uid": hashlib.sha1(f"{repo}@{t}".encode()).hexdigest()[:16],
            "title": f"{repo} {t}",
            "url": url,
            "published": iso or "",
            "date_precision": "second" if iso else "none",
            "snippet": f"{base}。发布说明（{d.get('notes_source') or '未取到'}）："
                       f"{notes[:600]}" if notes else base,
            "release_notes": notes,
            "release_notes_source": d.get("notes_source") or "",
        })
    times = {t: d["time"] for t, d in details.items() if d.get("time")}
    snap = notes_snapshot(repo, tags, details)
    # 一个 tag 都没取到时刻 → 不能回答"是不是窗口内"，按解析失败处理
    if not times:
        return {"status": "parse_failed",
                "error": f"{len(tags)} 个 tag 均未取到提交时刻", "items": items,
                "notes_snapshot": snap}
    got = sum(1 for d in details.values() if (d.get("notes") or "").strip())
    return {"status": "ok", "error": "", "items": items,
            "notes_snapshot": snap, "notes_count": got}


if __name__ == "__main__":
    import sys
    for r in sys.argv[1:]:
        res = collect(r)
        print(f"{r}: {res['status']} {res['error']}")
        for it in res["items"][:4]:
            print(f"   {it['published'][:19] or '?':20} {it['title']}")
            if it.get("release_notes"):
                first = it["release_notes"].splitlines()
                first = next((l for l in first if l.strip()), "")
                print(f"   {'':20} ↳ {it['release_notes_source']}: {first[:90]}")
