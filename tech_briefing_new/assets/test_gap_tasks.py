#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gap_tasks / coverage 缺口单测：任务分档、window_partial 合并、整实体失明任务、
UNCOVERABLE 的补偿登记。

  python -m unittest test_gap_tasks -v
"""
import unittest

import coverage
import sources
import gap_tasks
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
        # ID 由内容派生而不是位置号（见 gap_tasks 里的注释）：阻断缺口仍排在最前，
        # 但编号不随缺口集合平移——否则 --mark-done 会结错任务。
        self.assertTrue(b["tasks"][0]["id"].startswith("GAP-C"), b["tasks"][0]["id"])
        self.assertEqual(b["tasks"][0]["seq"], 1)
        self.assertEqual(b["tasks"][0]["id"],
                         build_tasks(rep, "2026-10-31")["tasks"][0]["id"],
                         "同一缺口两次构建必须得到同一个 ID")
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
        # 验收区间一律按 Asia/Shanghai 写出
        self.assertIn("2026-10-30 12:00 +08:00", t["acceptance"])

    def test_mark_done_updates_counters(self):
        rep = _report([{"type": "entity_blind", "blocking": False, "action_required": True,
                        "entity": "Baidu", "surface": "company", "source": "", "verdict": "ENTITY_BLIND",
                        "search_terms": ["文心"]}])
        built = build_tasks(rep, "2026-10-31")
        b = mark_done(built, built["tasks"][0]["id"], "确认 0 条")
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


class AcceptanceTimezoneTest(unittest.TestCase):
    """window_partial 的验收区间要归一到 Asia/Shanghai。

    covered_from 带源自己的时区。arXiv 的 RSS 是 -05:00，所以
    2026-11-02T00:00:00-05:00 其实是上海 11-02 13:00，离窗口起点 13 小时；
    旧实现直接截字符串，写出来是"窗口起点 至 2026-11-02T00:00"，
    读起来像个空区间，于是这条盲区会被当成不存在而草草结案。
    """

    def test_arxiv_offset_is_normalized(self):
        report = {
            "run_date": "2026-11-03",
            "target_window": {"start": "2026-11-02T00:00:00+08:00",
                              "end": "2026-11-03T09:41:00+08:00"},
            "sources": [{"id": "arxiv_cs_CL", "covered_from": "2026-11-02T00:00:00-05:00"}],
            "gaps": [{"type": "window_partial", "entity": "arXiv", "surface": "research",
                      "source": "arxiv_cs_CL", "action_required": True,
                      "covered_from": "2026-11-02T00:00:00-05:00"}],
        }
        task = gap_tasks.build_tasks(report, "2026-11-03")["tasks"][0]
        self.assertIn("2026-11-02 13:00 +08:00", task["acceptance"])
        self.assertNotIn("2026-11-02T00:00", task["acceptance"])


class WindowPartialConfirmedZeroTest(unittest.TestCase):
    """window_partial 的 confirmed_zero 按未覆盖时段判，而不是按整个窗口。

    arXiv 每个工作日只在美东 00:00 公告一批（上海 13:00）。窗口起点到 13:00
    这一段不可能有公告，但整个窗口当然有条目；按窗口起点比，这条缺口永远
    结不了案，只能天天挂一条 partial_compensated。
    """

    WS = "2026-11-02T00:00:00+08:00"

    def test_window_partial_needs_range_end(self):
        ev = {"channel": "arxiv rss", "range_checked": "起点→13:00",
              "latest_item_time": "2026-11-02T13:00:00+08:00"}
        probs = gap_tasks.validate_resolution("confirmed_zero", ev, self.WS,
                                              "window_partial")
        self.assertTrue(any("range_end" in x for x in probs), probs)

    def test_window_partial_closes_within_uncovered_range(self):
        ev = {"channel": "arxiv rss", "range_checked": "起点→13:00",
              "latest_item_time": "2026-11-02T13:00:00+08:00",
              "range_end": "2026-11-02T13:00:00+08:00"}
        self.assertEqual(
            gap_tasks.validate_resolution("confirmed_zero", ev, self.WS,
                                          "window_partial"), [])

    def test_item_after_uncovered_range_still_fails(self):
        ev = {"channel": "arxiv rss", "range_checked": "起点→13:00",
              "latest_item_time": "2026-11-02T18:00:00+08:00",
              "range_end": "2026-11-02T13:00:00+08:00"}
        probs = gap_tasks.validate_resolution("confirmed_zero", ev, self.WS,
                                              "window_partial")
        self.assertTrue(any("未覆盖时段终点" in x for x in probs), probs)

    def test_entity_blind_rule_unchanged(self):
        ev = {"channel": "blog", "range_checked": "SCAN_WINDOW",
              "latest_item_time": "2026-11-02T09:00:00+08:00"}
        probs = gap_tasks.validate_resolution("confirmed_zero", ev, self.WS,
                                              "entity_blind")
        self.assertTrue(any("窗口起点" in x for x in probs), probs)
