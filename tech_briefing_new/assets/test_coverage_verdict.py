#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
coverage.source_verdict / build_gaps 的单测。

守住的规则：
  1. 0 条目要分两种："源结构正常但没内容"（OK_EMPTY，非失明）与
     "内容不对劲"（EMPTY，失明）。混为一谈会给健康源造出假缺口。
  2. 缺口的分母是"声明的必查面"，不是"报告里有哪些源"——
     一个既无源又未登记不可达的实体必须被判出来。
"""
import unittest

import coverage
from coverage import BLIND_VERDICTS, source_verdict
import sources as src_reg


def rec(**kw):
    base = {"transport": "ok", "extract": "ok", "items_in_window": 0,
            "items_with_date": 0}
    base.update(kw)
    return base


class EmptyStateTest(unittest.TestCase):
    def test_well_formed_empty_feed_is_not_blind(self):
        v = source_verdict(rec(extract="empty", structure_ok=True))
        self.assertEqual(v, "OK_EMPTY")
        self.assertNotIn(v, BLIND_VERDICTS)

    def test_malformed_empty_is_blind(self):
        v = source_verdict(rec(extract="empty", structure_ok=False))
        self.assertEqual(v, "EMPTY")
        self.assertIn(v, BLIND_VERDICTS)

    def test_missing_structure_flag_defaults_to_blind(self):
        # 旧报告没有该字段：必须按失明处理，不能用"缺字段 = 通过"
        v = source_verdict(rec(extract="empty"))
        self.assertEqual(v, "EMPTY")
        self.assertIn(v, BLIND_VERDICTS)

    def test_blocked_and_parse_failed_stay_blind(self):
        self.assertIn(source_verdict(rec(extract="blocked")), BLIND_VERDICTS)
        self.assertIn(source_verdict(rec(extract="parse_failed")), BLIND_VERDICTS)

    def test_read_but_out_of_window_is_not_blind(self):
        v = source_verdict(rec(items_with_date=10))
        self.assertEqual(v, "OK_OUT_OF_WINDOW")
        self.assertNotIn(v, BLIND_VERDICTS)

    def test_in_window_wins(self):
        v = source_verdict(rec(items_in_window=3, structure_ok=True))
        self.assertEqual(v, "OK_IN_WINDOW")


class Tier1InvariantTest(unittest.TestCase):
    """REQUIRED_SURFACES 必须与 tier1 实体集合一致，否则实体蒸发。"""

    def test_every_tier1_has_canonical_name(self):
        import json
        from pathlib import Path
        onto = json.loads((Path(__file__).parent / "thesis_ontology.json")
                          .read_text(encoding="utf-8"))
        missing = [t for t in onto["tier1_entities"] if t not in src_reg.TIER1_CANONICAL]
        self.assertEqual(missing, [], f"tier1 实体缺映射: {missing}")

    def test_required_surfaces_match_tier1(self):
        import json
        from pathlib import Path
        onto = json.loads((Path(__file__).parent / "thesis_ontology.json")
                          .read_text(encoding="utf-8"))
        names = {src_reg.TIER1_CANONICAL[t] for t in onto["tier1_entities"]}
        required = set(src_reg.REQUIRED_SURFACES) - {"default"}
        self.assertEqual(names, required,
                         f"仅 tier1 有: {names - required}；仅必查表有: {required - names}")

    def test_no_silent_entity_surface(self):
        built = src_reg.build_sources()
        have = {(s["entity"], s["surface"]) for s in built}
        registered = {(u["entity"], u["surface"]) for u in src_reg.UNCOVERABLE}
        silent = []
        for ent, surfs in src_reg.REQUIRED_SURFACES.items():
            if ent == "default":
                continue
            for surf in surfs:
                if (ent, surf) not in have and (ent, surf) not in registered:
                    silent.append(f"{ent}/{surf}")
        self.assertEqual(silent, [], f"既无源也未登记不可达: {silent}")



class GitTagsFallbackTest(unittest.TestCase):
    """第三通道（匿名 git）的判定要与正常采集区分开。"""

    def rec(self, **kw):
        base = {"transport": "ok", "extract": "ok", "items_total": 4,
                "items_with_date": 4, "items_in_window": 2}
        base.update(kw)
        return base

    def test_git_tags_has_its_own_verdict(self):
        self.assertEqual(coverage.source_verdict(self.rec(from_git_tags=True)),
                         "OK_FROM_GIT_TAGS")

    def test_plain_success_is_not_relabelled(self):
        self.assertEqual(coverage.source_verdict(self.rec()), "OK_IN_WINDOW")

    def test_git_tags_wins_over_archive_label(self):
        """两条回退都标了时，git 通道更具体，标签取它。"""
        self.assertEqual(
            coverage.source_verdict(self.rec(from_git_tags=True, from_archive=True)),
            "OK_FROM_GIT_TAGS")

    def test_verdict_is_healthy_and_labelled(self):
        self.assertIn("OK_FROM_GIT_TAGS", coverage.VERDICT_LABEL)
        self.assertNotIn("OK_FROM_GIT_TAGS", coverage.BLIND_VERDICTS)


class GitTagsCollectTest(unittest.TestCase):
    """git_tags.collect 的状态语义：取不到时刻就不能回答归窗问题。"""

    def setUp(self):
        import git_tags
        self.gt = git_tags

    def test_transport_failure_reported(self):
        self.gt.list_tags = lambda *a, **k: ([], "fatal: could not read")
        r = self.gt.collect("x/y")
        self.assertEqual(r["status"], "transport_failed")
        self.assertEqual(r["items"], [])

    def test_no_tags_is_empty_not_failure(self):
        self.gt.list_tags = lambda *a, **k: ([], "")
        self.assertEqual(self.gt.collect("x/y")["status"], "empty")

    def test_tags_without_times_cannot_answer_window(self):
        self.gt.list_tags = lambda *a, **k: (["v1", "v2"], "")
        self.gt.tag_times = lambda *a, **k: {}
        r = self.gt.collect("x/y")
        self.assertEqual(r["status"], "parse_failed")
        self.assertEqual([i["date_precision"] for i in r["items"]], ["none", "none"])

    def test_items_carry_second_precision_when_timed(self):
        self.gt.list_tags = lambda *a, **k: (["v1"], "")
        self.gt.tag_times = lambda *a, **k: {"v1": "2026-11-01T20:51:31+00:00"}
        r = self.gt.collect("x/y")
        self.assertEqual(r["status"], "ok")
        it = r["items"][0]
        self.assertEqual(it["date_precision"], "second")
        self.assertEqual(it["url"], "https://github.com/x/y/releases/tag/v1")
        self.assertIn("tag 提交时刻", it["snippet"])

    def test_deref_and_moving_tags_skipped(self):
        """^{} 解引用行与 latest / stable 这类移动 tag 不是发布。"""
        import subprocess
        out = ("aaa\trefs/tags/v2\n"
               "bbb\trefs/tags/v2^{}\n"
               "ccc\trefs/tags/latest\n"
               "ddd\trefs/tags/v1\n")
        self.gt._run = lambda args, timeout: (True, out)
        tags, err = self.gt.list_tags("x/y")
        self.assertEqual((tags, err), (["v2", "v1"], ""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
