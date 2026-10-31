#!/usr/bin/env python3
"""五维评分、评级派生、证据独立性的测试。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import scoring as sc
from events import normalize_event
from testlib import leaf0, rt_hits


def mk(**over) -> dict:
    s = {d: {"score": 1, "evidence": "e"} for d in sc.DIMENSIONS}
    s["strategic_adjacency"]["root_tech"] = ["RT:S2.2"]
    for k, v in over.items():
        s[k] = {**s[k], **({"score": v} if isinstance(v, int) else v)}
    return s


class IndependenceTest(unittest.TestCase):
    def test_three_hn_threads_on_one_article_count_as_one(self):
        """一份报告用 HN 的 876/655/399 三帖论证多源共振，三帖指向同一篇分析。"""
        urls = ["https://news.ycombinator.com/item?id=1",
                "https://news.ycombinator.com/item?id=2",
                "https://news.ycombinator.com/item?id=3",
                "https://phorion.io/blog/x"]
        self.assertEqual(sc.independent_sources(urls), ["phorion.io"])

    def test_subdomains_fold_to_one_source(self):
        self.assertEqual(
            sc.independent_sources(["https://blog.openai.com/a",
                                    "https://openai.com/b"]), ["openai.com"])

    def test_hf_papers_folds_to_arxiv_but_hf_blog_does_not(self):
        got = sc.independent_sources(["https://huggingface.co/papers/2610.1",
                                      "https://arxiv.org/abs/2610.1",
                                      "https://huggingface.co/blog/foo"])
        self.assertEqual(got, ["arxiv.org", "huggingface.co"])

    def test_two_letter_cctld_keeps_second_level(self):
        self.assertEqual(sc.registrable("https://www.ithome.com.cn/x"), "ithome.com.cn")

    def test_authority_needs_two_sources_or_first_party(self):
        self.assertEqual(sc.source_authority(["a.com"], False), 1)
        self.assertEqual(sc.source_authority(["a.com"], True), 2)
        self.assertEqual(sc.source_authority(["a.com", "b.com"], False), 2)
        self.assertEqual(sc.source_authority([], True), 0)


class DeriveTest(unittest.TestCase):
    def test_aplus_needs_novelty_and_adjacency_both_two(self):
        self.assertEqual(sc.derive_rating(mk(**{d: 2 for d in sc.DIMENSIONS}))[0], "A+")
        # 总分够 9 但机制新颖度只有 1 → 不是 A+
        s = mk(**{d: 2 for d in sc.DIMENSIONS}); s["mechanism_novelty"]["score"] = 1
        self.assertEqual(sc.derive_rating(s)[0], "A")

    def test_a_needs_both_at_least_one(self):
        s = mk(source_authority=2, magnitude=2, mechanism_novelty=2,
               quantitative_evidence=2, strategic_adjacency=0)
        self.assertEqual(sc.total(s), 8)
        self.assertEqual(sc.derive_rating(s)[0], "B",
                         "战略相关度为 0 时，高总分也不进 A")

    def test_seven_is_below_the_a_band(self):
        """一份大厂模型技术报告（权威+量化满分、机制与相关度各 1）总分 7，是 B 不是 A。"""
        s = mk(source_authority=2, magnitude=1, mechanism_novelty=1,
               quantitative_evidence=2, strategic_adjacency=1)
        self.assertEqual(sc.total(s), 7)
        self.assertEqual(sc.derive_rating(s)[0], "B")
        s["magnitude"]["score"] = 2
        self.assertEqual(sc.derive_rating(s)[0], "A")

    def test_bands(self):
        self.assertEqual(sc.derive_rating(mk())[0], "B")       # 5
        self.assertEqual(sc.derive_rating(mk(**{d: 0 for d in sc.DIMENSIONS}))[0], "C")

    def test_market_event_capped_at_c_without_thesis(self):
        """Intel 暴跌的影响面与量化证据都能拿满分，但它没有技术机制。"""
        s = mk(**{d: 2 for d in sc.DIMENSIONS})
        self.assertEqual(sc.derive_rating(s, "market", has_thesis=False)[0], "C")

    def test_market_event_capped_at_b_with_mechanism_and_thesis(self):
        s = mk(**{d: 2 for d in sc.DIMENSIONS})
        r, why = sc.derive_rating(s, "funding", has_thesis=True)
        self.assertEqual(r, "B")
        self.assertIn("硬上限", why)

    def test_cap_never_raises_a_rating(self):
        s = mk(**{d: 0 for d in sc.DIMENSIONS})
        self.assertEqual(sc.derive_rating(s, "market", has_thesis=True)[0], "C")


class ValidateTest(unittest.TestCase):
    def base(self, **over) -> dict:
        ev = {"event_id": "EV-01", "source": "https://phorion.io/x",
              "scoring": mk(), "event_class": "technical",
              "primary_path": leaf0(), "product_to_thesis": "p → t"}
        ev.update(over)
        ev.setdefault("root_tech",
                      rt_hits(ev["scoring"]["strategic_adjacency"]["score"]))
        return ev

    def test_clean_event_passes(self):
        ev = self.base()
        ev["rating"] = sc.derive_rating(ev["scoring"], "technical", True)[0]
        self.assertEqual(sc.validate(ev), [])

    def test_missing_scoring_block_reported(self):
        self.assertTrue(sc.validate({"event_id": "EV-01"}))

    def test_score_out_of_range_reported(self):
        ev = self.base(); ev["scoring"]["magnitude"]["score"] = 3
        self.assertIn("不在 0–2", " ".join(sc.validate(ev)))

    def test_nonzero_score_without_evidence_reported(self):
        ev = self.base(); ev["scoring"]["magnitude"] = {"score": 2, "evidence": ""}
        self.assertIn("没写证据", " ".join(sc.validate(ev)))

    def test_overclaimed_independent_sources_reported(self):
        ev = self.base(independent_sources=["phorion.io", "cursor.com"])
        self.assertIn("多报", " ".join(sc.validate(ev)))

    def test_authority_two_on_single_secondary_source_reported(self):
        ev = self.base()
        ev["scoring"]["source_authority"]["score"] = 2
        self.assertIn("≥2 个独立首发源", " ".join(sc.validate(ev)))

    def test_authority_two_allowed_for_first_party(self):
        ev = self.base(first_party_source=True)
        ev["scoring"]["source_authority"]["score"] = 2
        self.assertNotIn("独立首发源", " ".join(sc.validate(ev)))

    def test_adjacency_without_root_tech_reported(self):
        ev = self.base(root_tech=[])
        ev["scoring"]["strategic_adjacency"] = {"score": 2, "evidence": "e"}
        self.assertIn("未写命中的根技术编号", " ".join(sc.validate(ev)))


    def test_hand_written_rating_conflict_reported(self):
        ev = self.base(rating="A+")
        joined = " ".join(sc.validate(ev))
        self.assertIn("与派生值", joined)
        self.assertIn("不要直接改 rating", joined)

    def test_invalid_event_class_reported(self):
        ev = self.base(event_class="rumor")
        self.assertIn("不在封闭集合", " ".join(sc.validate(ev)))


class NormalizeIntegrationTest(unittest.TestCase):
    def test_rating_is_filled_from_scores(self):
        ev = {"event_title": "t", "source": "https://phorion.io/x", "entity": "A",
              "first_publish_shanghai": "2026-10-30T10:00:00+08:00",
              "primary_path": leaf0(), "change_types": ["CT-01"],
              "evidence_form": "product", "date_precision": "second",
              "scoring": mk(**{d: 2 for d in sc.DIMENSIONS}),
              "first_party_source": True, "root_tech": rt_hits(2),
              "product_to_thesis": "p → t"}
        out, errs = normalize_event(ev, "EV-01")
        self.assertEqual(errs, [])
        self.assertEqual(out["rating"], "A+")
        self.assertIn("总分 10", out["rating_basis"])
        self.assertEqual(out["independent_sources"], ["phorion.io"])

    def test_rating_without_scoring_is_an_error(self):
        ev = {"event_title": "t", "source": "https://phorion.io/x", "entity": "A",
              "first_publish_shanghai": "2026-10-30T10:00:00+08:00",
              "primary_path": "B1.1", "change_types": ["CT-01"],
              "evidence_form": "product", "date_precision": "second",
              "rating": "A", "scoring": None}
        _, errs = normalize_event(ev, "EV-02")
        self.assertIn("评级必须由五维评分派生", " ".join(errs))


class PairwiseTest(unittest.TestCase):
    def evs(self, totals):
        out = []
        for i, t in enumerate(totals):
            s = {d: {"score": 0, "evidence": "e"} for d in sc.DIMENSIONS}
            left = t
            for d in sc.DIMENSIONS:
                take = min(2, left); s[d]["score"] = take; left -= take
            out.append({"event_id": f"EV-{i+1:02}", "scoring": s})
        return out

    def test_only_close_pairs_are_compared(self):
        pairs = sc.pair_candidates(self.evs([10, 9, 5]))
        self.assertEqual(pairs, [("EV-01", "EV-02")],
                         "分差大于 band 的对不进成对比较")

    def test_pairwise_decision_swaps_adjacent(self):
        order = ["EV-01", "EV-02", "EV-03"]
        got = sc.apply_pairwise(order, [{"pair": ["EV-01", "EV-02"],
                                         "winner": "EV-02", "why": "更改变判断"}])
        self.assertEqual(got, ["EV-02", "EV-01", "EV-03"])

    def test_decision_confirming_order_changes_nothing(self):
        order = ["EV-01", "EV-02"]
        got = sc.apply_pairwise(order, [{"pair": ["EV-01", "EV-02"],
                                         "winner": "EV-01"}])
        self.assertEqual(got, order)

    def test_malformed_decision_ignored(self):
        order = ["EV-01", "EV-02"]
        self.assertEqual(sc.apply_pairwise(order, [{"pair": ["EV-01"], "winner": "EV-01"},
                                                   {"pair": ["EV-01", "EV-09"],
                                                    "winner": "EV-09"}]), order)



class RootTechAdjacencyTest(unittest.TestCase):
    """Strategic Adjacency 由根技术命中派生，不由模型自报。"""

    def setUp(self):
        import root_tech as rt
        self.rt = rt
        self.data = rt.load()
        # 取一条真实根技术，避免测试写死一个不存在的编号
        self.root = self.data["roots"][0]
        self.rid = "RT:" + self.root["id"]
        self.signal = self.root["switch_signal"]
        self.leaf = (self.root.get("leaves_core") or ["B1.1"])[0]

    def hit(self, **over):
        h = {"id": self.rid, "relation": "switch_evidence",
             "direction": "supports", "signal_quote": self.signal,
             "why": "事件给出该信号的直接读数"}
        h.update(over)
        return h

    def ev(self, adj, hits, **over):
        e = {"event_id": "EV-01", "source": "https://phorion.io/x",
             "primary_path": self.leaf, "event_class": "technical",
             "product_to_thesis": "p → t", "root_tech": hits,
             "scoring": mk(strategic_adjacency={"score": adj, "evidence": "e"})}
        e.update(over)
        return e

    def test_switch_evidence_scores_two(self):
        self.assertEqual(self.rt.derive_adjacency([self.hit()]), 2)
        self.assertEqual(sc.validate(self.ev(2, [self.hit()])), [])

    def test_current_gen_scores_one(self):
        h = self.hit(relation="current_gen", direction=None, signal_quote="")
        self.assertEqual(self.rt.derive_adjacency([h]), 1)
        self.assertEqual(sc.validate(self.ev(1, [h])), [])

    def test_contradicting_evidence_scores_the_same(self):
        """否证当前代假设与支持证据同分，否则清单会把简报变成确认偏误放大器。"""
        self.assertEqual(
            self.rt.derive_adjacency([self.hit(direction="contradicts")]), 2)

    def test_selfreported_score_must_match_derivation(self):
        joined = " ".join(sc.validate(self.ev(1, [self.hit()])))
        self.assertIn("与根技术命中派生值", joined)

    def test_missing_rt_prefix_rejected(self):
        joined = " ".join(sc.validate(self.ev(2, [self.hit(id=self.root["id"])])))
        self.assertIn("缺 RT: 前缀", joined)

    def test_unknown_root_rejected(self):
        joined = " ".join(sc.validate(self.ev(2, [self.hit(id="RT:ZZ9.9")])))
        self.assertIn("不在根技术清单里", joined)

    def test_signal_quote_must_match_the_list(self):
        joined = " ".join(sc.validate(self.ev(2, [self.hit(signal_quote="我改写的信号")])))
        self.assertIn("与清单原文不一致", joined)

    def test_switch_evidence_needs_direction(self):
        joined = " ".join(sc.validate(self.ev(2, [self.hit(direction="maybe")])))
        self.assertIn("必须声明 direction", joined)

    def test_why_is_required(self):
        joined = " ".join(sc.validate(self.ev(2, [self.hit(why="")])))
        self.assertIn("缺 why", joined)

    def test_offpath_leaf_must_be_explained(self):
        e = self.ev(2, [self.hit()], primary_path="E3.3")
        joined = " ".join(sc.validate(e))
        self.assertIn("落点为何不一致", joined)
        e2 = self.ev(2, [self.hit(why="落点不一致：该根技术的叶子未覆盖本事件形态")],
                     primary_path="E3.3")
        self.assertNotIn("落点为何不一致", " ".join(sc.validate(e2)))

    def test_candidate_hits_are_listed_separately(self):
        """候选根只记录不计分：命中要能被取出来写进第 5 章的「候选根升格信号」。"""
        cid = next(iter(self.data["candidate_index"]), None)
        if not cid:
            self.skipTest("清单里没有候选根")
        hits = [self.hit(), self.hit(id="RT:" + cid)]
        self.assertEqual(self.rt.candidate_hits(hits), [cid])
        self.assertEqual(self.rt.candidate_hits([self.hit()]), [])

    def test_candidate_root_is_not_scored(self):
        cid = next(iter(self.data["candidate_index"]), None)
        if not cid:
            self.skipTest("清单里没有候选根")
        joined = " ".join(sc.validate(self.ev(2, [self.hit(id="RT:" + cid)])))
        self.assertIn("候选根", joined)



class RootTechListGateTest(unittest.TestCase):
    """清单自身的定义检查：战略相关度整维挂在它上面，清单坏了整维就失效。"""

    def _run(self, patch=None):
        import verify_gates as vg
        import root_tech as rt
        data = {k: v for k, v in rt.load().items()}
        if patch:
            data = patch({**data, "roots": [dict(r) for r in data["roots"]]})
            data["index"] = {r["id"]: r for r in data["roots"]}
        orig = rt.load
        rt.load = lambda path=None: data
        try:
            c = vg.Check()
            vg.check_root_tech_list(c)
            return {r["name"]: r["status"] for r in c.results}
        finally:
            rt.load = orig

    def test_real_list_passes(self):
        self.assertNotIn("FAIL", set(self._run().values()))

    def test_duplicate_id_fails(self):
        def patch(d):
            d["roots"].append(dict(d["roots"][0]))
            return d
        self.assertEqual(self._run(patch)["根技术编号唯一"], "FAIL")

    def test_missing_switch_signal_fails(self):
        def patch(d):
            d["roots"][0] = {**d["roots"][0], "switch_signal": ""}
            return d
        self.assertEqual(self._run(patch)["每项根技术都有切换信号"], "FAIL")

    def test_leaf_outside_taxonomy_fails(self):
        def patch(d):
            d["roots"][0] = {**d["roots"][0], "leaves_core": ["ZZ9.9"]}
            return d
        self.assertEqual(self._run(patch)["根技术叶子落点在分类表内"], "FAIL")

    def test_empty_list_fails(self):
        self.assertEqual(self._run(lambda d: {**d, "roots": []})["根技术清单可加载"],
                         "FAIL")


if __name__ == "__main__":
    unittest.main(verbosity=2)
