#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gap_tasks / coverage 缺口单测：任务分档、window_partial 合并、整实体失明任务、
UNCOVERABLE 的补偿登记。

  python -m unittest test_gap_tasks -v
"""
import unittest

import coverage
import sources
from gap_tasks import build_tasks, mark_done


def _report(gaps, sources_=None):
    return {"target_window": {"start": "2026-10-30T00:00:00+08:00"}, "gaps": gaps,
            "sources": sources_ or []}


class BuildTasksTest(unittest.TestCase):
    def test_blocking_and_action_counts(self):
        rep = _report([
            {"type": "critical_blind", "blocking": True, "entity": "OpenAI", "surface": "developer",
             "source": "openai_changelog", "verdict": "PROXY_BLOCKED"},
            {"type": "entity_blind", "blocking": False, "action_required": True, "entity": "Zhipu",
             "surface": "company", "source": "", "verdict": "ENTITY_BLIND", "search_terms": ["智谱", "GLM"]},
            {"type": "source_blind", "blocking": False, "entity": "X", "surface": "community",
             "source": "x", "verdict": "PARSE_FAILED"},
        ])
        b = build_tasks(rep, "2026-10-31")
        self.assertEqual((b["tasks_total"], b["tasks_blocking_open"], b["tasks_action_open"]), (2, 1, 1),
                         "非阻断且无 action_required 的 source_blind 不产生任务")
        self.assertEqual(b["tasks"][0]["id"], "GAP-01")
        self.assertTrue(b["tasks"][0]["blocking"], "阻断任务先编号")

    def test_entity_blind_queries_come_from_search_terms(self):
        rep = _report([{"type": "entity_blind", "blocking": False, "action_required": True,
                        "entity": "ByteDance", "surface": "company", "source": "",
                        "verdict": "ENTITY_BLIND", "search_terms": ["豆包", "字节跳动 Seed"]}])
        t = build_tasks(rep, "2026-10-31")["tasks"][0]
        self.assertEqual(len(t["queries"]), 2)
        self.assertIn('"豆包"', t["queries"][0])
        self.assertIn("SCAN_WINDOW", t["acceptance"])

    def test_window_partial_merged_per_entity_surface_with_widest_gap(self):
        rep = _report([
            {"type": "window_partial", "blocking": False, "action_required": True, "entity": "arXiv",
             "surface": "research", "source": "arxiv_cs_AI", "covered_from": "2026-10-30T12:00:00+08:00"},
            {"type": "window_partial", "blocking": False, "action_required": True, "entity": "arXiv",
             "surface": "research", "source": "arxiv_cs_CL", "covered_from": "2026-10-30T02:00:00-04:00"},
        ])
        b = build_tasks(rep, "2026-10-31")
        self.assertEqual(b["tasks_total"], 1)
        t = b["tasks"][0]
        self.assertEqual(sorted(t["failing_sources"]), ["arxiv_cs_AI", "arxiv_cs_CL"])
        # 02:00-04:00 = 14:00+08:00，比 12:00+08:00 晚；最宽缺口取最早的 12:00
        self.assertIn("2026-10-30T12:00", t["acceptance"])

    def test_mark_done_updates_counters(self):
        rep = _report([{"type": "entity_blind", "blocking": False, "action_required": True,
                        "entity": "Baidu", "surface": "company", "source": "", "verdict": "ENTITY_BLIND",
                        "search_terms": ["文心"]}])
        b = mark_done(build_tasks(rep, "2026-10-31"), "GAP-01", "确认 0 条")
        self.assertEqual((b["tasks_open"], b["tasks_action_open"]), (0, 0))


class CoverageGapsTest(unittest.TestCase):
    def _records(self, ok_entities=None):
        srcs = sources.build_sources()
        return [{"entity": s["entity"], "surface": s["surface"], "id": s["id"],
                 "verdict": "OK_OUT_OF_WINDOW", "critical": s.get("critical")} for s in srcs]

    def test_fully_blind_tier1_entities_get_daily_task(self):
        recs = self._records()
        gaps = coverage.build_gaps(recs, sources.REQUIRED_SURFACES, sources.UNCOVERABLE,
                                   coverage.surface_coverage(recs))
        blind = {g["entity"] for g in gaps if g["type"] == "entity_blind"}
        self.assertIn("ByteDance", blind)
        self.assertIn("Zhipu", blind)
        self.assertNotIn("Anthropic", blind, "有其他面读到内容的实体不算整实体失明")
        self.assertTrue(all(g.get("action_required") and not g.get("blocking")
                            for g in gaps if g["type"] == "entity_blind"))

    def test_entity_with_a_readable_surface_is_not_blind(self):
        recs = self._records() + [{"entity": "ByteDance", "surface": "code", "id": "bd_gh",
                                   "verdict": "OK_OUT_OF_WINDOW"}]
        gaps = coverage.build_gaps(recs, sources.REQUIRED_SURFACES, sources.UNCOVERABLE,
                                   coverage.surface_coverage(recs))
        self.assertNotIn("ByteDance", {g["entity"] for g in gaps if g["type"] == "entity_blind"})

    def test_every_uncoverable_entry_declares_compensation(self):
        for u in sources.UNCOVERABLE:
            self.assertTrue(u.get("compensate") and u.get("search_terms") and u.get("recheck_by"),
                            f"{u['entity']}/{u['surface']} 缺补偿登记")


if __name__ == "__main__":
    unittest.main(verbosity=2)
