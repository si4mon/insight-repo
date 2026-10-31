#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_pool 单测：归窗、无日期条目的 freshness、无标题条目移出、同源去重。

  python -m unittest test_build_pool -v
"""
import json
import tempfile
import unittest
from pathlib import Path

from build_pool import build

WINDOW = {"start": "2026-10-30T00:00:00+08:00", "end": "2026-10-31T09:00:00+08:00"}


def _raw(tmp: Path, items: dict, sources: list, diff: dict | None = None) -> Path:
    raw = tmp / "raw_2026-10-31"
    raw.mkdir()
    (raw / "collect_report.json").write_text(json.dumps(
        {"target_window": WINDOW, "sources": sources, "diff": diff or {}}), encoding="utf-8")
    for sid, rows in items.items():
        (raw / f"items_{sid}.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return raw


def _src(sid, mode="rss", channel="A_entity"):
    return {"id": sid, "entity": "OpenAI", "surface": "company", "channel": channel, "mode": mode}


def _item(uid, published=None, title="标题", precision="second"):
    it = {"uid": uid, "title": title, "url": f"https://ex.com/{uid}"}
    if published:
        it["published"] = published
        it["date_precision"] = precision
    return it


class BuildPoolTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_in_window_exact_and_out_of_window_kept_as_evidence(self):
        raw = _raw(self.tmp, {"blog": [_item("a", "2026-10-30T10:00:00+08:00"),
                                       _item("b", "2026-10-20T10:00:00+08:00")]}, [_src("blog")])
        pool, out = build(raw)
        self.assertEqual([(x["uid"], x["window_match"]) for x in pool], [("a", "exact")])
        self.assertEqual([x["uid"] for x in out], ["b"], "窗口外条目必须留在池外文件，供 8.3 引证")
        self.assertEqual(pool[0]["channel"], "A_entity")

    def test_day_precision_is_fuzzy_not_exact(self):
        raw = _raw(self.tmp, {"blog": [_item("a", "2026-10-30T00:00:00+08:00", precision="day")]},
                   [_src("blog")])
        pool, _ = build(raw)
        self.assertEqual(pool[0]["window_match"], "fuzzy")

    def test_undated_items_kept_with_freshness(self):
        diff = {"trend": {"new_uids": ["new"], "is_first_run": False}}
        raw = _raw(self.tmp, {"trend": [_item("new"), _item("old")]}, [_src("trend")], diff)
        pool, _ = build(raw)
        fresh = {x["uid"]: x["freshness"] for x in pool}
        self.assertEqual(fresh, {"new": "new_since_last_run", "old": "carried_over"})
        self.assertTrue(all(x["window_match"] == "no_date" for x in pool))

    def test_first_run_has_no_baseline(self):
        diff = {"trend": {"new_uids": [], "is_first_run": True}}
        raw = _raw(self.tmp, {"trend": [_item("x")]}, [_src("trend")], diff)
        pool, _ = build(raw)
        self.assertEqual(pool[0]["freshness"], "baseline_unknown")

    def test_untitled_and_sitemap_moved_out(self):
        raw = _raw(self.tmp, {"blog": [_item("a", "2026-10-30T10:00:00+08:00", title=" ")],
                              "map": [_item("m", "2026-10-30T10:00:00+08:00")]},
                   [_src("blog"), _src("map", mode="sitemap")])
        pool, out = build(raw)
        self.assertEqual(pool, [])
        self.assertEqual(sorted(x["uid"] for x in out), ["a", "m"])
        self.assertTrue(all(x["window_match"] == "no_title" for x in out))

    def test_dedup_within_source_not_across_sources(self):
        it = _item("same", "2026-10-30T10:00:00+08:00")
        raw = _raw(self.tmp, {"a": [it, it], "b": [it]}, [_src("a"), _src("b")])
        pool, _ = build(raw)
        self.assertEqual(sorted(x["src"] for x in pool), ["a", "b"],
                         "同源去重；跨源合并是 P2 的语义工作")


if __name__ == "__main__":
    unittest.main(verbosity=2)
