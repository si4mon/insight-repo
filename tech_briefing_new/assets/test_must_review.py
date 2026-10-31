#!/usr/bin/env python3
"""必审清单与其门禁的测试。"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import must_review as mr
import verify_gates as vg

TERMS = {
    "ai_relevance": {"en": ["agent", "llm"], "zh": ["大模型"]},
    "arxiv_score": {"high": ["verif", "agent"], "med": ["reasoning"]},
}


def row(**kw):
    base = {"uid": kw.get("uid", "u"), "title": "", "url": "", "snippet": "",
            "published": "2026-10-30T10:00:00+08:00", "in_window": True,
            "src": "x", "channel": "A_entity"}
    base.update(kw)
    return base


class TierTest(unittest.TestCase):
    def test_official_and_papers_are_full_coverage(self):
        pool = [row(uid="a", src="openai_news_rss", channel="A_entity", title="X"),
                row(uid="b", src="openai_api_changelog",
                    channel="G_official_surface", title="Y"),
                row(uid="c", src="hf_daily_papers", channel="A_entity", title="Z")]
        out = mr.build(pool, TERMS)
        self.assertEqual(out["by_tier"]["T1_official"], 2)
        self.assertEqual(out["by_tier"]["T2_hf_papers"], 1)

    def test_ranking_sources_excluded(self):
        """趋势榜单连日在场，入清单只会每天重复同一条处置。"""
        pool = [row(uid="a", src="hf_trending_models", channel="A_entity", title="M"),
                row(uid="b", src="gh_trending", channel="D_social", title="R")]
        self.assertEqual(mr.build(pool, TERMS)["total"], 0)

    def test_hn_needs_both_points_and_relevance(self):
        pool = [
            row(uid="a", src="hn_front", channel="D_social",
                title="New agent framework", snippet="points=120 comments=3"),
            row(uid="b", src="hn_front", channel="D_social",
                title="New agent framework", snippet="points=10 comments=1"),
            row(uid="c", src="hn_front", channel="D_social",
                title="My sourdough starter", snippet="points=900 comments=9"),
        ]
        got = {r["uid"] for r in mr.build(pool, TERMS)["items"]}
        self.assertEqual(got, {"a"}, "分数不够或与论域无关的都不入清单")

    def test_carried_over_undated_item_excluded(self):
        pool = [row(uid="a", src="openai_news_rss", title="X", in_window=None,
                    window_match="no_date", freshness="carried_over"),
                row(uid="b", src="openai_news_rss", title="Y", in_window=None,
                    window_match="no_date", freshness="new_since_last_run")]
        got = {r["uid"] for r in mr.build(pool, TERMS)["items"]}
        self.assertEqual(got, {"b"})

    def test_arxiv_takes_top_k_by_score(self):
        pool = [row(uid=f"p{i}", src="arxiv_cs_AI", channel="B_arxiv",
                    title=t) for i, t in enumerate([
                        "Verification of agent plans",   # 4
                        "Agent reasoning survey",        # 3
                        "A note on typography",          # 0
                    ])]
        out = mr.build(pool, TERMS, arxiv_top_k=2)
        got = [r["uid"] for r in out["items"]]
        self.assertEqual(got, ["p0", "p1"])
        self.assertEqual(out["thresholds"]["arxiv_score_cutoff"], 3)
        self.assertEqual(out["arxiv_candidates"], 3)

    def test_same_item_from_two_sources_counted_once(self):
        """HN front 与 newest 是同一 uid；台账按 uid 记，清单必须同样去重。"""
        pool = [row(uid="dup", src="hn_front", channel="D_social",
                    title="agent", snippet="points=100"),
                row(uid="dup", src="hn_newest", channel="D_social",
                    title="agent", snippet="points=100")]
        out = mr.build(pool, TERMS)
        self.assertEqual(out["total"], 1)
        self.assertEqual(out["items"][0]["also_srcs"], ["hn_newest"])

    def test_trace_template_covers_every_item(self):
        pool = [row(uid="a", src="openai_news_rss", title="X"),
                row(uid="b", src="openai_news_rss", title="Y")]
        out = mr.build(pool, TERMS)
        tpl = mr.trace_template(out)
        self.assertEqual(set(tpl["dispositions"]), {"a", "b"})
        self.assertEqual(tpl["must_review_total"], len(tpl["dispositions"]))


class GateTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.mr = self.d / "must_review.json"
        self.tr = self.d / "must_review_trace.json"
        self.ev = self.d / "events_run_2026-10-30"
        self.ev.mkdir()
        (self.ev / "EV-01.json").write_text(
            json.dumps({"source": "https://x.test/a"}), encoding="utf-8")
        self.mr.write_text(json.dumps({
            "total": 2, "by_tier": {},
            "items": [{"uid": "u1", "title": "A", "url": "https://x.test/a",
                       "tier": "T1_official"},
                      {"uid": "u2", "title": "B", "url": "https://x.test/b",
                       "tier": "T1_official"}]}, ensure_ascii=False),
            encoding="utf-8")

    def fails(self, disp) -> set:
        self.tr.write_text(json.dumps({"dispositions": disp}, ensure_ascii=False),
                           encoding="utf-8")
        c = vg.Check()
        vg.check_must_review(c, self.mr, self.tr, self.ev)
        return {r["name"] for r in c.results if r["status"] == "FAIL"}

    OK = {"u1": {"disposition": "selected", "ev": "EV-01"},
          "u2": {"disposition": "discarded", "reason": "低影响"}}

    def test_complete_ledger_passes(self):
        self.assertEqual(self.fails(dict(self.OK)), set())

    def test_unfilled_entry_fails(self):
        d = dict(self.OK); d["u2"] = {"disposition": "", "ev": "", "reason": ""}
        self.assertIn("必审清单逐条留痕", self.fails(d))

    def test_missing_entry_fails(self):
        d = dict(self.OK); d.pop("u2")
        self.assertIn("必审清单逐条留痕", self.fails(d))

    def test_invented_disposition_fails(self):
        d = dict(self.OK); d["u2"] = {"disposition": "ignored"}
        self.assertIn("处置取值合法", self.fails(d))

    def test_dangling_ev_fails(self):
        d = dict(self.OK); d["u1"] = {"disposition": "selected", "ev": "EV-99"}
        self.assertIn("入选/并入指向存在的 EV", self.fails(d))

    def test_invented_discard_reason_fails(self):
        d = dict(self.OK); d["u2"] = {"disposition": "discarded", "reason": "不重要"}
        self.assertIn("丢弃理由取自封闭集合", self.fails(d))

    def test_chapter5_without_placement_fails(self):
        d = dict(self.OK); d["u2"] = {"disposition": "chapter5", "reason": ""}
        self.assertIn("丢弃理由取自封闭集合", self.fails(d))

    def test_ledger_contradicting_events_fails(self):
        """事件里确实写了这条链接，台账却记丢弃——台账填错了。"""
        d = dict(self.OK)
        d["u1"] = {"disposition": "discarded", "reason": "低影响"}
        self.assertIn("台账与事件产物不矛盾", self.fails(d))

    def test_missing_list_fails(self):
        c = vg.Check()
        vg.check_must_review(c, self.d / "nope.json", self.tr, self.ev)
        self.assertIn("必审清单已生成",
                      {r["name"] for r in c.results if r["status"] == "FAIL"})

    def test_missing_ledger_fails(self):
        c = vg.Check()
        vg.check_must_review(c, self.mr, self.d / "nope.json", self.ev)
        self.assertIn("必审清单逐条留痕",
                      {r["name"] for r in c.results if r["status"] == "FAIL"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
