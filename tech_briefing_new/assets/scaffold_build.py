#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为一轮简报生成 build.py 骨架，并把已知事实预填进每个事件桩位。

为什么需要：build.py 每轮手写 516–723 行，是单轮最大的人工开销。其中绝大多数
行是判断内容（标题、key_data、机制叙述、四维评分的证据串），生成不了，也不该
生成。但有四类纯机械劳动每轮重复，而且都出过错：

  1. 样板头尾约 70 行（import、SHA 表、E/S/RT 辅助、SIG 表、规范化落盘）；
  2. 事实转抄：source / entity / first_publish_shanghai / 标题要从候选池抄进桩位。
     2026-11-02 那份简报把 qwen-code v0.26.6 的 11-03 01:51 写成 09:51、nightly
     的 06:04 写成 14:04，就是转抄时又按 +08 换了一次——两处事实错误发出去了；
  3. SIG 表：切换信号原文手抄，而 root_tech 会逐字校验 signal_quote；
  4. rejected 列表：新建命题必须逐个说明为何不归入召回到的候选，每轮都要手工
     把 thesis_candidates 与已写的 rejected 做差再补齐。

本工具只做这四类。判断字段留 TODO，并在旁边列出封闭集合的全部取值——写错
取值的那类缺陷（change_object="Benchmark" 被静默丢弃、evidence_form="research"）
在桩位上就看得见。

  # 第一步：选完题后生成骨架
  python scaffold_build.py --raw-dir raw_2026-11-06 --picks picks.txt --out build.py
  # 第二步：build.py 跑过且 registry candidates 标注过之后，补 rejected
  python scaffold_build.py rejected --events-dir events_run_2026-11-05
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from datetime import datetime, timedelta, timezone

import build_pool
import events as ev_mod
import report_stats
import root_tech as rt
import scoring

HERE = Path(__file__).resolve().parent
SNAP_DIR_WARN = 12          # 目录下超过这么多文件就提醒点名，别整目录声明
SH_TZ = timezone(timedelta(hours=8))


def _to_shanghai(iso: str) -> tuple[str, str]:
    """把候选池的时刻换成 Asia/Shanghai，并说明换算前是什么。

    这是脚手架存在的主要理由之一。候选池里的时刻带的是来源自己的时区
    （arXiv 回来是 -05:00，HN 是 +00:00，git tag 归一成 UTC），而字段名叫
    first_publish_shanghai。2026-11-02 那份简报把 qwen-code v0.26.6 的
    11-03 01:51 写成 09:51、nightly 的 06:04 写成 14:04，就是人在转抄时
    对一个已经是 +08:00 的值又按 +08 换了一次。这里一次换到位，并把原值
    留在注释里，人只需要核对，不需要再算。
    """
    raw = (iso or "").strip()
    if not raw:
        return "", "TODO 候选池里没有时刻，需人工确认（Asia/Shanghai）"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return "", f"TODO 候选池时刻无法解析，需人工确认: {raw}"
    if dt.tzinfo is None:
        return "", f"TODO 候选池时刻没有时区，需人工确认: {raw}"
    return (dt.astimezone(SH_TZ).isoformat(),
            f"已换算到 Asia/Shanghai（候选池原值 {raw}），核对即可")


def _window(raw_dir: Path) -> dict:
    """window.json 可能在 raw_<date>/ 里（采集器写的），也可能在运行根目录
    （freeze_window.py 单独跑时）。两处都找，否则骨架会因为找不到窗口而罢工。"""
    for f in (raw_dir / "window.json", raw_dir.parent / "window.json"):
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
    raise SystemExit(f"找不到 window.json（已找 {raw_dir} 与 {raw_dir.parent}）；"
                     f"先跑 freeze_window.py")


def _pool_index(raw_dir: Path) -> tuple[dict, dict]:
    """(canonical_source → 条目, uid → 条目)。窗口内与窗口外都索引：
    Active Event 的本体常常在窗口外，桩位也要能预填它的事实。"""
    in_pool, out_pool = build_pool.build(raw_dir)
    by_cs, by_uid = {}, {}
    for row in list(in_pool) + list(out_pool):
        u = (row.get("url") or "").strip()
        if u:
            by_cs.setdefault(ev_mod.canonical_source(u), row)
        if row.get("uid"):
            by_uid.setdefault(row["uid"], row)
    return by_cs, by_uid


def read_picks(path: Path) -> list[tuple[str, str]]:
    """picks 文件：每行 `EV-01 <url 或 uid>`，# 起头是注释。"""
    out = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        s = line.split("#", 1)[0].strip()
        if not s:
            continue
        parts = s.split()
        if len(parts) < 2:
            raise SystemExit(f"{path}:{n} 需要两列（EV 编号 + url/uid）: {line!r}")
        out.append((parts[0], parts[1]))
    if not out:
        raise SystemExit(f"{path} 里没有有效的 picks")
    dup = {e for e, _ in out if [x for x, _ in out].count(e) > 1}
    if dup:
        raise SystemExit(f"EV 编号重复: {sorted(dup)}")
    return out


def _py(s) -> str:
    return json.dumps(s, ensure_ascii=False)


def _sig_table() -> str:
    """SIG 表由 root_tech 生成，不再手抄——signal_quote 会被逐字校验。"""
    roots = rt.load()["roots"]
    lines = ["# 切换信号原文由 root_tech 生成（root_tech 会逐字校验 signal_quote，",
             "# 手抄一个字都不能错）。只保留本轮用到的几条即可，多留无害。",
             "SIG = {"]
    for r in roots:
        sig = (r.get("switch_signal") or "").strip()
        if sig:
            lines.append(f"    {_py(r['id'])}: {_py(sig)},")
    lines.append("}")
    return "\n".join(lines)


def _snap_name(path: str, taken: set[str]) -> str:
    """按文件名生成常量名。`SNAP_7` 这种序号名在写 claim 时没法读，
    而 claim 的 E(SNAP_x, "原文") 是人要逐条对着快照核的地方。"""
    stem = re.sub(r"[^0-9A-Za-z]+", "_", Path(path).name).strip("_").upper()
    base = f"SNAP_{stem}" or "SNAP"
    name, n = base, 2
    while name in taken:
        name, n = f"{base}_{n}", n + 1
    taken.add(name)
    return name


def header(window: dict, snapshots: list[str]) -> str:
    taken: set[str] = set()
    names = [_snap_name(p, taken) for p in snapshots]
    decls = "\n".join(f"{n} = {_py(p)}" for n, p in zip(names, snapshots))
    sha = ("SHA = {f: ce.sha256_file(Path(f)) for f in (\n    "
           + ",\n    ".join(names) + ",\n)}" if names else "SHA = {}")
    ct = "  ".join(f"{c['id']} {c['name']}" for c in ev_mod.ONTOLOGY["change_types"])
    return f'''"""{window["run_date"]} 窗口的事件构建（scaffold_build.py 生成骨架）。

评级一律由 scoring.derive_rating 派生，不手写。
TARGET_WINDOW: {window["window_start"]} → {window["window_end"]}
"""
import json
import sys
from pathlib import Path

A = {_py(str(HERE))}
sys.path.insert(0, A)
import claim_evidence as ce          # noqa: E402
import events as ev_mod              # noqa: E402

# ---------------- 快照 ----------------
# A / A+ 的每条 claim 必须绑定到快照原文（task_def 15.1）。
# 重新采集会重写同名快照，绑过的 claim 要重新核对。
{decls or "# 还没有快照：用 --snapshots 指定目录，或在此手工声明"}
{sha}


def E(s, q):
    """claim 证据：快照 + sha256 + 原文片段。"""
    return {{"snapshot": s, "snapshot_sha256": SHA[s], "quote": q}}


def S(sc, **e):
    """四维评分。顺序: {", ".join(scoring.DIMENSIONS)}"""
    a, m, n, q, j = sc
    return {{"source_authority": {{"score": a, "evidence": e["sa"]}},
            "magnitude": {{"score": m, "evidence": e["mag"]}},
            "mechanism_novelty": {{"score": n, "evidence": e["nov"]}},
            "quantitative_evidence": {{"score": q, "evidence": e["quant"]}},
            "strategic_adjacency": {{"score": j, "evidence": e["adj"]}}}}


def RT(rid, rel, why, d=None, sig=None):
    """根技术命中。rel=switch_evidence 时必须给 direction 与 signal_quote。"""
    h = {{"id": rid, "relation": rel, "why": why}}
    if rel == "switch_evidence":
        h["direction"], h["signal_quote"] = d, sig
    return h


{_sig_table()}

# ---------------- 封闭集合（写错取值会被静默丢弃或门禁打红） ----------------
# change_object : {"  ".join(report_stats.CHANGE_OBJECTS)}
# evidence_form : {"  ".join(ev_mod.EVIDENCE_FORMS)}
# change_types  : {ct}

EV = {{}}
'''


_STUB = '''
# ---------------------------------------------------------------- {eid}
# 候选池原始标题: {ctitle}
# 召回通道: {channel}  来源源: {src}{seen_note}
EV["{eid}"] = dict(
 event_title={title},      # TODO 改写成技术命题式标题
 source={source},
 entity={entity}, first_party_source={fps},
 key_data="TODO 定量与机制的事实陈述",
 first_publish_shanghai={fp},   # {fpnote}
 date_precision={dp},            # second / day / batch / none
 date_semantics="TODO 这个时刻是什么日（发布日 / 公告日 / 更新日）",
 primary_path="TODO 叶子编号",
 related_domains=[],
 change_object="TODO",           # 见文件头封闭集合
 change_types=["TODO"],
 evidence_form={ef},
 signal="TODO",                  # Frontier Signal / Convergence Signal / Early Signal
 scoring=S((0, 0, 0, 0, 0),
           sa="TODO", mag="TODO", nov="TODO", quant="TODO", adj="TODO"),
 root_tech=[],                   # RT("RT:S4.2", "switch_evidence", "…", "supports", SIG["S4.2"])
 claims=[],                      # A / A+ 必须逐条绑定 E(SNAP_n, "原文片段")
 thesis_decision={{"action": "none"}},
){inc}
'''

_FOOTER = '''

# ---------------- 规范化落盘 ----------------
OUT = Path("events_run_{run_date}")
OUT.mkdir(exist_ok=True)
errs = []
for eid in sorted(EV):
    out, e = ev_mod.normalize_event(EV[eid], eid)
    if e:
        errs += e
        continue
    (OUT / f"{{eid}}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
if errs:
    print("规范化失败：")
    for x in errs:
        print("  x", x)
    sys.exit(1)
print(f"写出 {{len(EV)}} 个事件 → {{OUT}}")
for eid in sorted(EV):
    d = json.loads((OUT / f"{{eid}}.json").read_text(encoding="utf-8"))
    print(f"  {{eid}} {{d['rating']:3s}} {{d['signal']:14s}} {{d['primary_path']:6s}} "
          f"{{d['event_title'][:46]}}")
'''


def _evidence_form_guess(row: dict) -> str:
    ch = (row.get("channel") or "")
    src = (row.get("src") or "")
    if ch == "B_arxiv" or "arxiv" in src:
        return '"paper"'
    if "release" in (row.get("url") or "") or src.startswith("gh_"):
        return '"code"'
    if ch in ("A_entity", "G_official_surface"):
        return '"product"'
    return '"TODO"'


def _date_precision(row: dict) -> str:
    if (row.get("snippet") or "").startswith("arXiv 公告批次"):
        return '"batch"'
    return '"second"' if row.get("published") else '"none"'


def build_scaffold(raw_dir: Path, picks: list[tuple[str, str]],
                   snapshots: list[str], state: Path | None) -> str:
    win = _window(raw_dir)
    by_cs, by_uid = _pool_index(raw_dir)

    seen: dict[str, dict] = {}
    if state is not None:
        try:
            from thesis_registry import Registry
            seen = Registry(state).seen([k for _e, k in picks])
        except Exception as e:                        # registry 不可用不该挡住出骨架
            print(f"! 读不到 registry（{e}），跳过跨轮判重预填", file=sys.stderr)

    parts = [header(win, snapshots)]
    unresolved = []
    for eid, key in picks:
        row = by_uid.get(key) or by_cs.get(ev_mod.canonical_source(key)) or {}
        if not row:
            unresolved.append((eid, key))
        url = (row.get("url") or key).strip()
        fp, fpnote = _to_shanghai(row.get("published") or "")
        hit = seen.get(key)
        seen_note, inc = "", ""
        if hit:
            label = "/".join(f"{k}:{v}" for k, v in sorted((hit.get("labels") or {}).items()))
            seen_note = (f"\n# ! 这个来源以前见过：首见 {hit['first_seen']}"
                         f"（{label or hit.get('note', '')}）"
                         f"\n#   同一桩事情的后续动作请用 increment_of 挂在原事件下，"
                         f"不要新建事件")
            if hit.get("event_key"):
                inc = (f'\nEV["{eid}"]["increment_of"] = '
                       f'{{"event_key": {_py(hit["event_key"])},\n'
                       f'                              '
                       f'"delta": "TODO 这次又发生了什么"}}'
                       f'   # 不是增量就删掉这两行')
        parts.append(_STUB.format(
            eid=eid,
            ctitle=(row.get("title") or "（候选池里没有这条，核对 picks）")[:96],
            channel=row.get("channel") or "?", src=row.get("src") or "?",
            seen_note=seen_note,
            title=_py(row.get("title") or ""),
            source=_py(url),
            entity=_py(row.get("entity") or ""),
            fps="True" if (row.get("channel") or "") in
                ("A_entity", "G_official_surface") else "False",
            fp=_py(fp), fpnote=fpnote,
            dp=_date_precision(row),
            ef=_evidence_form_guess(row),
            inc=inc))
    parts.append(_FOOTER.format(run_date=win["run_date"]))
    if unresolved:
        print("! 以下 picks 在候选池里找不到，桩位只留了 EV 编号与来源："
              + ", ".join(f"{e}→{k}" for e, k in unresolved), file=sys.stderr)
    return "".join(parts)


def rejected_blocks(events_dir: Path, state: Path | None) -> str:
    """把每个新建命题的 rejected 列表写成可粘贴的代码。

    新建命题必须逐个说明为何不归入召回到的候选（registry.validate_batch）。
    此前每轮都要手工把 thesis_candidates 与已写的 rejected 做差——而且手工补的
    理由往往是泛泛一句。这里把候选的名字与陈述一并打出来，理由是对着真实内容写的。
    """
    reg = None
    if state is not None:
        try:
            from thesis_registry import Registry
            reg = Registry(state)
        except Exception as e:
            print(f"! 读不到 registry（{e}），只能列出编号", file=sys.stderr)
    out = []
    for f in sorted(Path(events_dir).glob("EV-*.json")):
        ev = json.loads(f.read_text(encoding="utf-8"))
        dec = ev.get("thesis_decision") or {}
        if dec.get("action") != "new":
            continue
        cands = [c["id"] for c in (ev.get("thesis_candidates") or [])]
        have = {r.get("id") for r in (dec.get("rejected") or [])
                if (r.get("reason") or "").strip()}
        missing = [c for c in cands if c not in have]
        if not missing:
            continue
        out.append(f'# ---- {f.stem}: 还缺 {len(missing)} 条 rejected 说明')
        out.append(f'EV["{f.stem}"]["thesis_decision"]["rejected"] += [')
        for tid in missing:
            name = statement = ""
            if reg is not None:
                try:
                    v = reg.view(tid)
                    name, statement = v["name"], v["statement"]
                except Exception:
                    pass
            if name:
                out.append(f'    # {tid} {name}')
                out.append(f'    #   {statement[:90]}')
            out.append(f'    {{"id": {_py(tid)}, "reason": "TODO 为什么不归入这一条"}},')
        out.append(']')
        out.append('')
    if not out:
        return "# 没有缺失的 rejected 说明\n"
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    ap.add_argument("--raw-dir", default="", help="raw_<date>/ 目录")
    ap.add_argument("--picks", default="", help="每行 `EV-01 <url 或 uid>`")
    ap.add_argument("--snapshots", default="",
                    help="快照目录；其中的文件会写进 SHA 表（逗号分隔多个目录）")
    ap.add_argument("--state", default="", help="registry 状态目录，用于跨轮判重预填")
    ap.add_argument("--out", default="", help="输出路径（默认打到标准输出）")
    r = sub.add_parser("rejected", help="补齐新建命题的 rejected 说明")
    r.add_argument("--events-dir", required=True)
    r.add_argument("--state", default="")
    r.add_argument("--out", default="")
    args = ap.parse_args()

    if args.cmd == "rejected":
        text = rejected_blocks(Path(args.events_dir),
                               Path(args.state) if args.state else None)
    else:
        if not (args.raw_dir and args.picks):
            ap.error("需要 --raw-dir 与 --picks")
        snaps: list[str] = []
        for d in [x for x in args.snapshots.split(",") if x.strip()]:
            p = Path(d.strip())
            if not p.is_dir():
                snaps.append(str(p))
                continue
            found = sorted(str(f) for f in p.iterdir() if f.is_file())
            if len(found) > SNAP_DIR_WARN:
                print(f"! {p} 下有 {len(found)} 个文件，全部声明会让 SHA 表无法阅读、"
                      f"每次构建都要重算哈希；只点名要引用的那几个文件更合适",
                      file=sys.stderr)
            snaps += found
        snaps = list(dict.fromkeys(snaps))
        text = build_scaffold(Path(args.raw_dir), read_picks(Path(args.picks)),
                              snaps, Path(args.state) if args.state else None)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"→ {args.out}（{len(text.splitlines())} 行）")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
