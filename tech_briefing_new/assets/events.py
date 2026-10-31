#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
事件 JSON 规范化：补 event_key、统一枚举写法、按 schema 校验。

替代此前每轮由 LLM 现写的 make_events.py / fix_events.py：LLM 仍按自己的方式写
EV-xx.json，写完后必须跑一次 normalize，字段拼写漂移（同一个 date_precision 写成
三种拼法）在这里统一消掉，registry 入库前拿到的是确定的结构。

event_key 是事件的身份：同一事件在相邻窗口里重复出现、或同一窗口重跑，都按它去重
（references/registry-v2-design.md §8.1）。

用法：
  python events.py normalize --events-dir events_run_2026-10-30
  python events.py key "https://arxiv.org/abs/2610.01234v2"     # 查看规范化结果
退出码：0 全部通过；1 有错误（错误逐条打印，文件不会被部分改写）
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).parent))
import scoring  # noqa: E402
from taxonomy import TAXONOMY, TaxonomyError  # noqa: E402

ONTOLOGY = json.loads((Path(__file__).parent / "thesis_ontology.json").read_text(encoding="utf-8"))
EVIDENCE_FORMS = tuple(ONTOLOGY["evidence_forms"])
CHANGE_TYPES = tuple(ct["id"] for ct in ONTOLOGY["change_types"])
RATINGS = ("A+", "A", "B", "C")
DATE_PRECISIONS = ("second", "day", "batch", "none")

# rating 不在必填里：它由 scoring 派生（见 scoring.py）。必填的是评分块本身。
REQUIRED = ("event_title", "source", "entity", "first_publish_shanghai",
            "scoring", "primary_path", "change_types", "evidence_form")

_ARXIV = re.compile(r'arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5})(?:v\d+)?', re.I)
_GH_RELEASE = re.compile(r'github\.com/([^/\s]+)/([^/\s]+)/releases/tag/([^/?#\s]+)', re.I)


def canonical_source(url: str) -> str:
    """把首发来源规范成稳定字符串：arXiv 去版本号，GitHub release 取 org/repo@tag，
    其余 URL 去 scheme、www、query、fragment 与末尾斜杠。"""
    u = (url or "").strip()
    m = _ARXIV.search(u)
    if m:
        return f"arxiv:{m.group(1)}"
    m = _GH_RELEASE.search(u)
    if m:
        return f"gh:{m.group(1).lower()}/{m.group(2).lower()}@{m.group(3)}"
    parts = urlsplit(u if "://" in u else f"https://{u}")
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parts.path.rstrip("/")
    return f"{host}{path}"


def event_key(ev: dict) -> str:
    """事件身份。同一事件换了来源 URL 时，用 canonical_source 字段指定原始来源。"""
    basis = canonical_source(ev.get("canonical_source") or ev.get("source") or "")
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]


def _norm_rating(v) -> str:
    return str(v or "").strip().upper().replace("＋", "+")


def normalize_event(ev: dict, event_id: str) -> tuple[dict, list[str]]:
    """返回 (规范化后的事件, 错误列表)。不修改入参。"""
    out = dict(ev)
    errors = []
    out["event_id"] = event_id

    for f in REQUIRED:
        if out.get(f) in (None, "", []):
            errors.append(f"{event_id}: 缺必填字段 {f}")

    out["rating"] = _norm_rating(out.get("rating"))
    if out["rating"] and out["rating"] not in RATINGS:
        errors.append(f"{event_id}: rating={out['rating']} 不在 {RATINGS}")

    cts = out.get("change_types") or []
    out["change_types"] = sorted({str(x).strip().upper() for x in cts})
    bad_ct = [x for x in out["change_types"] if x not in CHANGE_TYPES]
    if bad_ct:
        errors.append(f"{event_id}: 未知 change_types {bad_ct}")

    form = str(out.get("evidence_form") or "").strip().lower()
    out["evidence_form"] = form
    if form and form not in EVIDENCE_FORMS:
        errors.append(f"{event_id}: evidence_form={form} 不在 {EVIDENCE_FORMS}")

    if "date_precision" in out:
        prec = str(out["date_precision"] or "").strip().lower()
        out["date_precision"] = prec
        if prec not in DATE_PRECISIONS:
            errors.append(f"{event_id}: date_precision={prec} 不在 {DATE_PRECISIONS}")

    path = out.get("primary_path")
    if path:
        try:
            TAXONOMY.resolve(path)
        except TaxonomyError as e:
            errors.append(f"{event_id}: primary_path={path} 无法解析（{e}）")

    fp = out.get("first_publish_shanghai")
    if fp:
        try:
            datetime.fromisoformat(str(fp))
        except ValueError:
            errors.append(f"{event_id}: first_publish_shanghai={fp} 不是 ISO 时间")

    errors += _normalize_timestamps(out, event_id)

    # 评分块：有 scoring 就必须自洽（含评级可派生）；没有 scoring 且已写 rating，
    # 说明评级是手给的——这正是跨模型方差的来源，所以直接报错。
    if out.get("scoring"):
        out.setdefault("independent_sources", scoring.independent_sources(
            [str(out.get("source") or ""), str(out.get("canonical_source") or "")]
            + [str(c.get("url")) for c in (out.get("claims") or [])
               if isinstance(c, dict) and c.get("url")]
            + [str(u) for u in (out.get("corroborating_urls") or [])]))
        errors += scoring.validate(out)
        if not out.get("rating"):
            r, why = scoring.derive_rating(
                out["scoring"], out.get("event_class") or "technical",
                bool(str(out.get("product_to_thesis") or "").strip()))
            out["rating"], out["rating_basis"] = r, why
    elif out.get("rating"):
        errors.append(f"{event_id}: 写了 rating 却没有 scoring 块；"
                      f"评级必须由五维评分派生，见 references/rating-anchors.md")

    if out.get("source"):
        out["event_key"] = event_key(out)
    return out, errors


# 每类源用哪个时刻作为「首次公开」。改这张表就能改归窗口径，
# 不需要回去重写事件 —— 三类时刻都已入库。
FIRST_PUBLISH_RULE = {
    "arxiv":     "announced",   # 论文公告前不可见，提交时刻不是首次公开
    "github":    "announced",   # release 的 published_at
    "default":   "announced",
}
TS_KINDS = ("submitted", "announced", "refreshed")


def _tz_offset_hours(iso: str):
    try:
        dt = datetime.fromisoformat(str(iso))
    except (ValueError, TypeError):
        return None
    return None if dt.tzinfo is None else dt.utcoffset().total_seconds() / 3600


def _normalize_timestamps(out: dict, event_id: str) -> list[str]:
    """三类时刻分开保存，first_publish_shanghai 由规则派生。

    提交 / 公告 / 修订三个时刻各有用处，入库时只留一个就把信息丢了：
    arXiv 的「提交时刻还是公告批次」之争、GitHub 的 tag 名日期与 published_at
    之差、媒体转载日与原文首发日，都需要在事后还能重新判定。
    存全了之后，归窗口径变成 FIRST_PUBLISH_RULE 里可切换的一行，
    而不是写事件时的有损选择。
    """
    ts = out.get("timestamps")
    if not isinstance(ts, dict):
        return []
    errs = []
    for k in list(ts):
        if k in ("source_tz", "note"):
            continue
        if k not in TS_KINDS:
            errs.append(f"{event_id}: timestamps.{k} 不在 {TS_KINDS}")
            continue
        if ts[k] and _tz_offset_hours(ts[k]) is None:
            errs.append(f"{event_id}: timestamps.{k}={ts[k]} 必须是带时区的 ISO 时间")
    kind = FIRST_PUBLISH_RULE.get(out.get("source_kind", ""), FIRST_PUBLISH_RULE["default"])
    want = ts.get(kind) or ts.get("announced") or ts.get("submitted")
    fp = out.get("first_publish_shanghai")
    if want and fp:
        a, b = _tz_offset_hours(want), _tz_offset_hours(fp)
        if a is not None and b is not None:
            if b != 8.0:
                errs.append(f"{event_id}: first_publish_shanghai 必须是 +08:00，实为 UTC{b:+g}")
            elif abs((datetime.fromisoformat(str(want))
                      - datetime.fromisoformat(str(fp))).total_seconds()) > 60:
                errs.append(
                    f"{event_id}: first_publish_shanghai={fp} 与 timestamps.{kind}={want} "
                    f"换算后不一致（按 {kind} 口径派生）")
    return errs


def normalize_dir(events_dir: Path) -> tuple[int, list[str]]:
    """规范化目录下全部 EV-*.json。有任何错误时一个文件都不写（避免半成品状态）。"""
    files = sorted(events_dir.glob("EV-*.json"))
    staged, errors = [], []
    for f in files:
        try:
            ev = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            errors.append(f"{f.name}: JSON 解析失败（{e}）")
            continue
        out, errs = normalize_event(ev, f.stem)
        errors += errs
        staged.append((f, out))

    keys: dict[str, str] = {}
    for f, out in staged:
        k = out.get("event_key")
        if k and k in keys:
            errors.append(f"{f.stem}: 与 {keys[k]} 的 event_key 相同（同一来源被拆成两个事件？"
                          f"若确是不同论点，按 claims 规则拆分后给其中一个写 canonical_source）")
        elif k:
            keys[k] = f.stem

    if not errors:
        for f, out in staged:
            f.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return len(files), errors


def main() -> int:
    ap = argparse.ArgumentParser(description="事件 JSON 规范化")
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("normalize", help="补 event_key、统一枚举、校验 schema")
    n.add_argument("--events-dir", required=True)
    k = sub.add_parser("key", help="打印某来源的规范形式与 event_key")
    k.add_argument("source")
    args = ap.parse_args()

    if args.cmd == "key":
        print(canonical_source(args.source), event_key({"source": args.source}))
        return 0

    count, errors = normalize_dir(Path(args.events_dir))
    if errors:
        for e in errors:
            print(f"  x {e}")
        print(f"normalize FAIL — {len(errors)} 个错误，{count} 个文件均未改写")
        return 1
    print(f"normalize OK — {count} 个事件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
