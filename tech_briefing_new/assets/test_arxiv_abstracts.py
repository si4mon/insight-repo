#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""arXiv 摘要补抓的单测：解析、回填、快照复用、失败降级。

为什么要测：补抓是为了让 arxiv_score 的打分文本可比。如果解析静默失败，
清单会退回"按标题打分"而没人知道——这正是这条缺陷原本的形态。
"""
import json
import tempfile
import unittest
from pathlib import Path

import arxiv_abstracts as aa
import build_pool

_FEED = b"""<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2611.02153v1</id>
    <title>Multi-Agent Collusion</title>
    <summary>  We study collusion in
multi-agent systems and oversight probes.  </summary>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2611.05372v2</id>
    <title>PolicyIK</title>
    <summary>Inverse kinematics with RL.</summary>
  </entry>
</feed>"""


class ParseFeedTest(unittest.TestCase):
    def test_extracts_id_and_summary(self):
        got = aa.parse_feed(_FEED)
        self.assertEqual(sorted(got), ["2611.02153", "2611.05372"])

    def test_collapses_whitespace(self):
        got = aa.parse_feed(_FEED)
        self.assertEqual(got["2611.02153"],
                         "We study collusion in multi-agent systems and oversight probes.")

    def test_entry_without_summary_is_skipped(self):
        body = b"<feed><entry><id>http://arxiv.org/abs/2611.00001</id></entry></feed>"
        self.assertEqual(aa.parse_feed(body), {})

    def test_garbage_body_returns_empty_not_raises(self):
        self.assertEqual(aa.parse_feed(b"\x00\x01not xml"), {})


class ArxivIdTest(unittest.TestCase):
    def test_versioned_abs_url(self):
        self.assertEqual(build_pool.arxiv_id({"url": "https://arxiv.org/abs/2611.05372v2"}),
                         "2611.05372")

    def test_non_arxiv_url(self):
        self.assertEqual(build_pool.arxiv_id({"url": "https://openai.com/index/x"}), "")


class ApplyCacheTest(unittest.TestCase):
    """回填只动没有摘要的 arXiv 条目，并保留原来的批次标记。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.raw = Path(self._tmp.name)

    def _cache(self, mapping):
        (self.raw / build_pool.ABSTRACT_CACHE).write_text(
            json.dumps({"abstracts": mapping}, ensure_ascii=False), encoding="utf-8")

    def _pool(self):
        long = "x" * 200
        return [
            {"channel": "B_arxiv", "url": "https://arxiv.org/abs/2611.02153",
             "snippet": "arXiv 公告批次 2026-11-04"},                       # 待回填
            {"channel": "B_arxiv", "url": "https://arxiv.org/abs/2611.09999",
             "snippet": long},                                              # 已有摘要
            {"channel": "A_entity", "url": "https://arxiv.org/abs/2611.02153",
             "snippet": "短"},                                              # 非 arXiv 通道
        ]

    def test_backfills_only_missing_arxiv_rows(self):
        self._cache({"2611.02153": "y" * 300, "2611.09999": "z" * 300})
        pool = self._pool()
        n = build_pool.apply_abstract_cache(pool, self.raw)
        self.assertEqual(n, 1)
        self.assertTrue(pool[0]["abstract_backfilled"])
        self.assertEqual(pool[0]["snippet_origin"], "arXiv 公告批次 2026-11-04")
        self.assertNotIn("abstract_backfilled", pool[1])
        self.assertNotIn("abstract_backfilled", pool[2])

    def test_missing_cache_file_is_a_noop(self):
        pool = self._pool()
        self.assertEqual(build_pool.apply_abstract_cache(pool, self.raw), 0)
        self.assertFalse(build_pool.has_abstract(pool[0]))

    def test_corrupt_cache_degrades_to_noop(self):
        (self.raw / build_pool.ABSTRACT_CACHE).write_text("{not json", encoding="utf-8")
        self.assertEqual(build_pool.apply_abstract_cache(self._pool(), self.raw), 0)

    def test_idempotent(self):
        self._cache({"2611.02153": "y" * 300})
        pool = self._pool()
        build_pool.apply_abstract_cache(pool, self.raw)
        self.assertEqual(build_pool.apply_abstract_cache(pool, self.raw), 0)
        self.assertEqual(pool[0]["snippet_origin"], "arXiv 公告批次 2026-11-04")


class MissingIdsTest(unittest.TestCase):
    def test_only_in_window_arxiv_without_abstract(self):
        pool = [
            {"channel": "B_arxiv", "in_window": True, "snippet": "短",
             "url": "https://arxiv.org/abs/2611.00001"},
            {"channel": "B_arxiv", "in_window": False, "snippet": "短",
             "url": "https://arxiv.org/abs/2611.00002"},     # 窗口外
            {"channel": "B_arxiv", "in_window": True, "snippet": "x" * 200,
             "url": "https://arxiv.org/abs/2611.00003"},     # 已有摘要
            {"channel": "F_cn_media", "in_window": True, "snippet": "短",
             "url": "https://arxiv.org/abs/2611.00004"},     # 非 arXiv 通道
            {"channel": "B_arxiv", "window_match": "no_date", "snippet": "短",
             "url": "https://arxiv.org/abs/2611.00001"},     # 与第一条同编号
        ]
        self.assertEqual(aa.missing_ids(pool), ["2611.00001"])


class ScoringTextReportTest(unittest.TestCase):
    """清单必须报出"还有多少条没有摘要"，不能让偏低的分数静默影响排序。"""

    def test_reports_no_abstract_remainder(self):
        import must_review as m
        terms = {"ai_relevance": {"en": [], "zh": []},
                 "arxiv_score": {"high": ["agent"], "med": []}}
        pool = [{"channel": "B_arxiv", "in_window": True, "uid": f"u{i}",
                 "src": "arxiv_cs_AI", "title": "agent paper",
                 "url": f"https://arxiv.org/abs/2611.0000{i}",
                 "snippet": ("x" * 200) if i % 2 else "短"} for i in range(4)]
        out = m.build(pool, terms)
        st = out["thresholds"]["arxiv_scoring_text"]
        self.assertEqual(st["arxiv_candidates"], 4)
        self.assertEqual(st["no_abstract"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
