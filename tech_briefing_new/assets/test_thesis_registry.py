#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Thesis Registry v2 单测（references/registry-v2-design.md §12）。

  python -m unittest test_thesis_registry -v
"""
import json
import tempfile
import unittest
from pathlib import Path

from events import event_key
from thesis_registry import LockTimeout, Registry, RegistryError, ValidationError

R1, R2, R3 = "2026-10-28", "2026-10-29", "2026-10-30"


def ev(eid, src, rating="A", path="B1.1", entity="OpenAI", fp="2026-10-28T10:00:00+08:00",
       form="product", cts=("CT-01",), decision=None, related=()):
    e = {"event_id": eid, "event_title": f"事件 {eid}", "source": src, "entity": entity,
         "first_publish_shanghai": fp, "rating": rating, "primary_path": path,
         "change_types": list(cts), "evidence_form": form, "related_domains": list(related)}
    e["event_key"] = event_key(e)
    if decision is not None:
        e["thesis_decision"] = decision
    return e


def new(alias="", leaves=("B1.1",), obj="判断能力", rejected=()):
    nt = {"name": f"命题 {alias or obj}", "statement": "判断从生成后解析移到专用模型，因此接口契约成为新约束",
          "object": obj, "consequence": "接口契约成为新约束",
          "scope_leaves": list(leaves), "change_types": ["CT-01"]}
    if alias:
        nt["alias"] = alias
    return {"action": "new", "relation": "supports", "rationale": "新命题", "new_thesis": nt,
            "rejected": [{"id": t, "reason": "方向不同"} for t in rejected]}


def attach(tid, relation="supports", override=""):
    d = {"action": "attach", "thesis_id": tid, "relation": relation, "rationale": "同一命题"}
    if override:
        d["override_reason"] = override
    return d


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state = Path(self._tmp.name) / "state"
        self.addCleanup(self._tmp.cleanup)

    def ingest(self, run_date, events):
        with Registry(self.state) as reg:
            return reg.ingest_run(run_date, events)

    def reg(self):
        return Registry(self.state)

    def empty_runs(self, dates):
        for d in dates:
            self.ingest(d, [])


def _days(start_day: int, n: int) -> list[str]:
    from datetime import date, timedelta
    base = date(2026, 11, 1)
    return [(base + timedelta(days=start_day + i)).isoformat() for i in range(n)]


class IdempotencyTest(Base):
    def test_rerun_same_run_is_identical(self):
        batch = [ev("EV-01", "https://openai.com/a", decision=new())]
        self.ingest(R1, batch)
        first = json.loads((self.state / "thesis_registry.json").read_text(encoding="utf-8"))
        self.ingest(R1, batch)
        second = json.loads((self.state / "thesis_registry.json").read_text(encoding="utf-8"))
        for d in (first, second):
            for r in d["runs"]:
                r.pop("ingested_at")
        self.assertEqual(first, second)

    def test_rerun_with_changed_decision_replaces_batch(self):
        self.ingest(R1, [ev("EV-01", "https://openai.com/a", decision=new("x")),
                         ev("EV-02", "https://google.com/b", entity="Google", decision=new("y", obj="别的"))])
        self.assertEqual(len(self.reg().data["theses"]), 2)
        # 改判：EV-02 归入 EV-01 新建的命题
        self.ingest(R1, [ev("EV-01", "https://openai.com/a", decision=new("x")),
                         ev("EV-02", "https://google.com/b", entity="Google", decision=attach("NEW:x"))])
        reg = self.reg()
        self.assertEqual(len(reg.data["theses"]), 1)
        self.assertEqual(len(reg.data["links"]), 2)

    def test_overlapping_window_does_not_double_count(self):
        self.ingest(R1, [ev("EV-01", "https://openai.com/a", rating="B", decision=new())])
        # 次日窗口重叠，同一事件再次出现，裁决相同
        res = self.ingest(R2, [ev("EV-03", "https://openai.com/a?utm=x", rating="B",
                                  decision=attach("TH-0001"))])
        self.assertEqual(res["seen_before"], {"EV-03": R1})
        reg = self.reg()
        self.assertEqual(len(reg.data["links"]), 1)
        v = reg.view("TH-0001")
        self.assertEqual(len(v["support"]), 1)
        self.assertEqual(v["state"], "proposed", "同一事件重复出现不能把 proposed 升为 active")
        # 证据仍记在首次裁决的 run 上：否则本轮报告会谎称"新增支持 / 跨时间收敛"，沉寂计时也被重置
        self.assertEqual(reg.data["links"][0]["decided_in"], R1)
        self.assertEqual(reg.report(R2)["theses"], [])

    def test_older_run_cannot_be_ingested(self):
        self.ingest(R2, [])
        with self.assertRaises(RegistryError):
            self.ingest(R1, [])


class StateAndConfidenceTest(Base):
    def test_single_b_proposed_then_active_with_distinct_second_event(self):
        self.ingest(R1, [ev("EV-01", "https://a.com/1", rating="B", decision=new())])
        self.assertEqual(self.reg().view("TH-0001")["state"], "proposed")
        self.ingest(R2, [ev("EV-01", "https://b.com/2", rating="B", entity="Google",
                            fp="2026-10-29T10:00:00+08:00", decision=attach("TH-0001"))])
        self.assertEqual(self.reg().view("TH-0001")["state"], "active")

    def test_single_a_plus_is_medium_single_a_is_low(self):
        self.ingest(R1, [ev("EV-01", "https://a.com/1", rating="A+", decision=new("p")),
                         ev("EV-02", "https://a.com/2", rating="A", path="C1.2",
                            decision=new("q", leaves=("C1.2",), obj="执行状态"))])
        reg = self.reg()
        self.assertEqual(reg.view("TH-0001")["confidence"], "Medium")
        self.assertEqual(reg.view("TH-0002")["confidence"], "Low")

    def test_breadth_and_persistence_reach_high(self):
        # A+ (3) + 3 实体 (2) + 跨 2 周 (1) = 6 → High
        self.ingest(R1, [ev("EV-01", "https://a.com/1", rating="A+", fp="2026-10-20T10:00:00+08:00",
                            decision=new("p"))])
        self.ingest(R2, [ev("EV-01", "https://b.com/1", rating="B", entity="Google",
                            fp="2026-10-28T10:00:00+08:00", decision=attach("TH-0001")),
                         ev("EV-02", "https://c.com/1", rating="B", entity="Anthropic",
                            fp="2026-10-28T11:00:00+08:00", decision=attach("TH-0001"))])
        v = self.reg().view("TH-0001")
        self.assertEqual(v["score"], 6, v["breakdown"])
        self.assertEqual(v["confidence"], "High")
        self.assertEqual(v["type"], "Convergence Thesis")

    def test_counter_evidence_lowers_confidence_and_contests(self):
        self.ingest(R1, [ev("EV-01", "https://a.com/1", rating="A+", decision=new())])
        self.assertEqual(self.reg().view("TH-0001")["confidence"], "Medium")
        self.ingest(R2, [ev("EV-01", "https://b.com/9", rating="A+", entity="Google",
                            fp="2026-10-29T10:00:00+08:00",
                            decision=attach("TH-0001", relation="contradicts"))])
        v = self.reg().view("TH-0001")
        self.assertEqual(v["confidence"], "Low", v["breakdown"])
        self.assertEqual(v["state"], "contested")

    def test_dormant_after_14_runs_then_revived(self):
        self.ingest(R1, [ev("EV-01", "https://a.com/1", rating="A", decision=new())])
        runs = _days(0, 14)
        self.empty_runs(runs)
        self.assertEqual(self.reg().view("TH-0001")["state"], "dormant")
        nxt = _days(14, 1)[0]
        self.ingest(nxt, [ev("EV-01", "https://b.com/1", rating="B", entity="Google",
                             fp=f"{nxt}T10:00:00+08:00", decision=attach("TH-0001"))])
        self.assertEqual(self.reg().view("TH-0001")["state"], "active")

    def test_proposed_expires_after_ttl(self):
        self.ingest(R1, [ev("EV-01", "https://a.com/1", rating="B", decision=new())])
        self.empty_runs(_days(0, 10))
        v = self.reg().view("TH-0001")
        self.assertEqual((v["state"], v["state_reason"]), ("retired", "未获二次证据"))

    def test_b_event_attaching_adds_breadth(self):
        self.ingest(R1, [ev("EV-01", "https://a.com/1", rating="A", decision=new())])
        before = self.reg().view("TH-0001")["score"]
        self.ingest(R2, [ev("EV-01", "https://b.com/1", rating="B", entity="Google",
                            form="paper", decision=attach("TH-0001"))])
        after = self.reg().view("TH-0001")
        self.assertEqual(after["score"], before + 2, after["breakdown"])   # 跨实体 +1、跨形态 +1


class ValidationTest(Base):
    def _file(self):
        p = self.state / "thesis_registry.json"
        return p.read_bytes() if p.exists() else b""

    def test_attach_outside_candidates_needs_override(self):
        self.ingest(R1, [ev("EV-01", "https://a.com/1", rating="A", decision=new())])
        snapshot = self._file()
        far = ev("EV-01", "https://b.com/1", rating="A", path="E3.1", cts=("CT-05",),
                 decision=attach("TH-0001"))
        with self.assertRaises(ValidationError) as cm:
            self.ingest(R2, [far])
        self.assertTrue(any("override_reason" in e for e in cm.exception.errors))
        self.assertEqual(self._file(), snapshot, "校验失败时 registry 文件不能有任何改动")
        far["thesis_decision"]["override_reason"] = "跨域：交互层事件验证了判断模型命题"
        self.ingest(R2, [far])

    def test_new_must_reject_every_candidate(self):
        self.ingest(R1, [ev("EV-01", "https://a.com/1", rating="A", decision=new())])
        with self.assertRaises(ValidationError) as cm:
            self.ingest(R2, [ev("EV-01", "https://b.com/1", rating="A", decision=new(obj="另一个"))])
        self.assertTrue(any("TH-0001" in e for e in cm.exception.errors))
        self.ingest(R2, [ev("EV-01", "https://b.com/1", rating="A",
                            decision=new(obj="另一个", rejected=("TH-0001",)))])

    def test_scope_must_be_leaves(self):
        with self.assertRaises(ValidationError) as cm:
            self.ingest(R1, [ev("EV-01", "https://a.com/1", decision=new(leaves=("B1",)))])
        self.assertTrue(any("叶子" in e for e in cm.exception.errors))

    def test_strong_event_cannot_be_none(self):
        with self.assertRaises(ValidationError):
            self.ingest(R1, [ev("EV-01", "https://a.com/1", rating="A+", decision={"action": "none"})])
        self.ingest(R1, [ev("EV-01", "https://a.com/1", rating="B", decision={"action": "none"})])

    def test_new_thesis_cannot_be_contradicts(self):
        d = new()
        d["relation"] = "contradicts"
        with self.assertRaises(ValidationError):
            self.ingest(R1, [ev("EV-01", "https://a.com/1", decision=d)])

    def test_stale_event_key_rejected(self):
        e = ev("EV-01", "https://a.com/1", decision=new())
        e["source"] = "https://a.com/changed"
        with self.assertRaises(ValidationError) as cm:
            self.ingest(R1, [e])
        self.assertTrue(any("event_key" in x for x in cm.exception.errors))

    def test_unknown_alias_rejected(self):
        with self.assertRaises(ValidationError):
            self.ingest(R1, [ev("EV-01", "https://a.com/1", decision=attach("NEW:nope"))])

    def test_failed_ingest_keeps_in_memory_state(self):
        # 同一个对象在 ingest 失败后继续使用（如接着做 merge），内存不能停在回滚了一半的状态
        self.ingest(R1, [ev("EV-01", "https://a.com/1", decision=new())])
        with Registry(self.state) as reg:
            with self.assertRaises(ValidationError):
                reg.ingest_run(R1, [ev("EV-01", "https://a.com/1", decision=attach("NEW:nope"))])
            self.assertIn("TH-0001", reg.data["theses"])
            self.assertEqual(len(reg.data["links"]), 1)
            reg.retire("TH-0001", "测试：失败后继续写决策")
        self.assertIn("TH-0001", self.reg().data["theses"])

    def test_lock_busy_leaves_file_untouched(self):
        self.ingest(R1, [])
        snapshot = self._file()
        holder = Registry(self.state).lock()
        try:
            with self.assertRaises(LockTimeout):
                Registry(self.state).lock(timeout=0.3)
        finally:
            holder.unlock()
        self.assertEqual(self._file(), snapshot)


class RecallAndDecisionTest(Base):
    def test_same_leaf_ranks_above_same_level2(self):
        self.ingest(R1, [ev("EV-01", "https://a.com/1", path="B1.2", decision=new("a", leaves=("B1.2",), obj="规划")),
                         ev("EV-02", "https://a.com/2", path="B1.1", decision=new("b", obj="判断"))])
        cands = self.reg().candidates(ev("EV-09", "https://z.com/9", path="B1.1"), R2)
        self.assertEqual([c["id"] for c in cands], ["TH-0002", "TH-0001"])

    def test_merged_and_retired_not_recalled(self):
        self.ingest(R1, [ev("EV-01", "https://a.com/1", decision=new("a")),
                         ev("EV-02", "https://a.com/2", entity="Google", decision=new("b", obj="判断2"))])
        with Registry(self.state) as reg:
            reg.merge("TH-0002", "TH-0001", "同一命题")
        reg = self.reg()
        self.assertEqual(reg.view("TH-0002")["state"], "merged")
        target = reg.view("TH-0001")
        self.assertEqual(len(target["support"]), 2)
        self.assertEqual(target["entities"], ["Google", "OpenAI"])
        self.empty_runs([R2])
        ids = [c["id"] for c in self.reg().candidates(ev("EV-09", "https://z.com/9"), R3)]
        self.assertEqual(ids, ["TH-0001"])
        with Registry(self.state) as reg:
            reg.retire("TH-0001", "被否证")
        self.empty_runs([R3])
        self.assertEqual(self.reg().candidates(ev("EV-09", "https://z.com/9"), "2026-10-31"), [])

    def test_rerun_drops_decisions_on_removed_theses(self):
        self.ingest(R1, [ev("EV-01", "https://a.com/1", decision=new("a")),
                         ev("EV-02", "https://a.com/2", entity="Google", decision=new("b", obj="判断2"))])
        with Registry(self.state) as reg:
            reg.merge("TH-0002", "TH-0001", "同一命题")
        res = self.ingest(R1, [ev("EV-01", "https://a.com/1", decision=new("a"))])
        self.assertEqual(self.reg().data["decisions"], [])
        self.assertTrue(any("撤销" in w for w in res["warnings"]))


class BackfillTest(Base):
    def test_gaps_lists_missing_days(self):
        self.ingest(R1, [])
        self.ingest(R3, [])
        self.assertEqual(self.reg().gaps("2026-10-31"), [R2])
        self.assertEqual(self.reg().gaps(R2), [])

    def test_plain_ingest_of_older_run_points_to_backfill(self):
        self.ingest(R3, [])
        with self.assertRaises(RegistryError) as cm:
            self.ingest(R2, [])
        self.assertIn("--backfill", str(cm.exception))

    def test_backfill_inserts_missing_run(self):
        self.ingest(R1, [ev("EV-01", "https://a.com/1", rating="B", decision=new())])
        self.ingest(R3, [])
        with Registry(self.state) as reg:
            reg.ingest_run(R2, [ev("EV-01", "https://g.com/1", rating="B", entity="Google",
                                   fp="2026-10-29T10:00:00+08:00", decision=attach("TH-0001"))],
                           backfill=True)
        reg = self.reg()
        self.assertEqual(reg.run_dates(), [R1, R2, R3])
        self.assertEqual(reg.view("TH-0001")["state"], "active")
        self.assertEqual(reg.gaps("2026-10-31"), [])

    def test_backfill_refuses_existing_or_newest_run(self):
        self.ingest(R1, [])
        self.ingest(R3, [])
        for day in (R1, R3, "2026-10-31"):
            with Registry(self.state) as reg:
                with self.assertRaises(RegistryError):
                    reg.ingest_run(day, [], backfill=True)

    def test_backfill_cannot_attach_to_later_thesis(self):
        self.ingest(R1, [])
        self.ingest(R3, [ev("EV-01", "https://a.com/1", decision=new())])
        with Registry(self.state) as reg:
            with self.assertRaises(ValidationError):
                reg.ingest_run(R2, [ev("EV-01", "https://b.com/1", decision=attach("TH-0001"))],
                               backfill=True)

    def test_backfill_keeps_later_decision_on_overlap(self):
        self.ingest(R1, [ev("EV-01", "https://a.com/0", decision=new())])
        self.ingest(R3, [ev("EV-01", "https://a.com/1", decision=attach("TH-0001"))])
        with Registry(self.state) as reg:
            res = reg.ingest_run(R2, [ev("EV-01", "https://a.com/1",
                                         decision=attach("TH-0001", relation="contradicts"))],
                                 backfill=True)
        self.assertTrue(any("不改写后续裁决" in w for w in res["warnings"]))
        link = next(l for l in self.reg().data["links"] if l["decided_in"] == R3)
        self.assertEqual(link["relation"], "supports")


class ReportTest(Base):
    def test_in_run_convergence(self):
        self.ingest(R1, [ev("EV-01", "https://a.com/1", rating="A+", decision=new("x")),
                         ev("EV-02", "https://g.com/1", rating="A", entity="Google",
                            decision=attach("NEW:x"))])
        row = self.reg().report(R1)["theses"][0]
        self.assertIn("本轮收敛", row["convergence"])
        self.assertIsNone(row["state_before"])
        self.assertTrue(row["core_judgment"])

    def test_cross_time_convergence_and_delta(self):
        self.ingest(R1, [ev("EV-01", "https://a.com/1", rating="A", decision=new())])
        self.ingest(R2, [ev("EV-01", "https://g.com/1", rating="A", entity="Google",
                            fp="2026-10-29T10:00:00+08:00", decision=attach("TH-0001"))])
        row = self.reg().report(R2)["theses"][0]
        self.assertIn("跨时间收敛", row["convergence"])
        self.assertEqual((row["confidence_before"], row["confidence"]), ("Low", "Medium"))

    def test_low_confidence_is_not_core_judgment(self):
        self.ingest(R1, [ev("EV-01", "https://a.com/1", rating="A", decision=new())])
        self.assertFalse(self.reg().report(R1)["theses"][0]["core_judgment"])

    def test_untouched_unchanged_theses_not_reported(self):
        self.ingest(R1, [ev("EV-01", "https://a.com/1", rating="A+", decision=new())])
        self.empty_runs([R2])
        self.assertEqual(self.reg().report(R2)["theses"], [])



class EntityIndependenceTest(Base):
    """跨实体收敛的实体必须是独立组织。

    2026-10-30 的 TH-0002 由两篇不同团队的论文撑起 Medium —— 两篇论文不是两个
    实体，这里把那条路堵掉。
    """

    def test_two_papers_count_as_one_entity_slot(self):
        from thesis_registry import independent_entities
        sup = [({}, {"entity": "清华大学", "evidence_form": "paper"}),
               ({}, {"entity": "斯坦福", "evidence_form": "preprint"})]
        self.assertEqual(independent_entities(sup), ["学术证据"])

    def test_paper_plus_deployment_are_two_entities(self):
        from thesis_registry import independent_entities
        sup = [({}, {"entity": "清华大学", "evidence_form": "paper"}),
               ({}, {"entity": "Anthropic", "evidence_form": "deployment"})]
        self.assertEqual(independent_entities(sup), ["Anthropic", "学术证据"])

    def test_same_org_paper_and_deployment_is_one_entity(self):
        from thesis_registry import independent_entities
        sup = [({}, {"entity": "Anthropic", "evidence_form": "paper"}),
               ({}, {"entity": "Anthropic", "evidence_form": "deployment"})]
        self.assertEqual(independent_entities(sup), ["Anthropic"])

    def test_placeholder_entity_is_not_an_organization(self):
        from thesis_registry import independent_entities
        self.assertEqual(
            independent_entities([({}, {"entity": "arXiv", "evidence_form": "paper"}),
                                  ({}, {"entity": "未披露", "evidence_form": "product"})]),
            [])

    def test_two_papers_do_not_reach_convergence_or_medium(self):
        d = _days(0, 1)
        self.ingest(d[0], [
            ev("EV-01", rating="A", entity="清华大学", form="paper",
               src="https://arxiv.org/abs/2610.00001", decision=new("t")),
            ev("EV-02", rating="A", entity="斯坦福", form="paper",
               src="https://arxiv.org/abs/2610.00002",
               decision=attach("NEW:t")),
        ])
        v = self.reg().view("TH-0001", d[0])
        self.assertEqual(v["entities_counted"], ["学术证据"])
        self.assertEqual(v["breakdown"]["entities"], 0,
                         "两篇论文拿不到跨实体加分")
        self.assertEqual(v["type"], "Frontier Thesis")
        self.assertEqual(v["confidence"], "Low")

    def test_paper_plus_independent_deployment_does_converge(self):
        d = _days(0, 1)
        self.ingest(d[0], [
            ev("EV-01", rating="A", entity="清华大学", form="paper",
               src="https://arxiv.org/abs/2610.00001", decision=new("t")),
            ev("EV-02", rating="A", entity="Anthropic", form="deployment",
               src="https://anthropic.com/x", decision=attach("NEW:t")),
        ])
        v = self.reg().view("TH-0001", d[0])
        self.assertEqual(v["type"], "Convergence Thesis")
        self.assertGreaterEqual(v["breakdown"]["entities"], 1)


class ViaClaimTest(Base):
    """关系要可复核：裁决必须指到承载该关系的那条 claim。"""

    def _ev_with_claims(self, decision):
        e = ev("EV-01", "https://ex.com/a", decision=decision)
        e["claims"] = [{"claim": "第一条", "disposition": "absorbed:EV-01"},
                       {"claim": "第二条", "disposition": "absorbed:EV-01"}]
        return e

    def _errs(self, decision):
        d = _days(0, 1)
        with Registry(self.state) as reg:
            errs, _ = reg.validate_batch(d[0], [self._ev_with_claims(decision)])
        return " ".join(errs)

    def test_missing_via_claim_rejected(self):
        self.assertIn("缺 via_claim", self._errs(new("t")))

    def test_index_within_range_accepted(self):
        self.assertNotIn("via_claim", self._errs({**new("t"), "via_claim": 1}))

    def test_out_of_range_index_rejected(self):
        self.assertIn("越界", self._errs({**new("t"), "via_claim": 5}))

    def test_quoted_claim_text_accepted(self):
        self.assertNotIn("via_claim", self._errs({**new("t"), "via_claim": "第二条"}))

    def test_claim_text_not_in_event_rejected(self):
        self.assertIn("与任何 claim 都不一致",
                      self._errs({**new("t"), "via_claim": "我编的一条"}))

    def test_event_without_claims_is_exempt(self):
        """聚合卡没有 claim 列表，不要求 via_claim。"""
        d = _days(0, 1)
        with Registry(self.state) as reg:
            errs, _ = reg.validate_batch(d[0], [ev("EV-01", "https://ex.com/a", decision=new("t"))])
        self.assertNotIn("via_claim", " ".join(errs))

    def test_via_claim_is_persisted_on_the_link(self):
        d = _days(0, 1)
        self.ingest(d[0], [self._ev_with_claims({**new("t"), "via_claim": 1})])
        links = self.reg().data["links"]
        self.assertEqual([l["via_claim"] for l in links], [1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
