#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_gates 分类层单测：确认新增的 4 条校验既会在该红时红，也会在该绿时绿。

为什么要测：门禁最危险的失效方式是"永远绿"——规则写了，但判定逻辑
因为锚点没匹配上、片段切错、字段读错而从不触发。这里用合成 fixture
直接调用 check_*，不依赖真实产物。

  python test_verify_gates.py
"""
import json
import re
import tempfile
import unittest
from pathlib import Path

from taxonomy import TAXONOMY
import testlib
import verify_gates
from verify_gates import (_degraded_header, check_ch1_mainlines, Check, check_ct_labels,
                          check_scoring,
                          check_event_annotations, check_event_body_presence,
                          check_event_paths,
                          check_markdown, check_md_event_index, check_md_theses,
                          check_publish_precision, check_source_coverage_definition,
                          check_registry, check_taxonomy_definition, check_traceability,
                          check_unclassified)


def _card(ev: str, extra: str = "", decl: str = "", rating: str = "B") -> str:
    """一张 MD 事件卡：EV 编号只写在标记行里（门禁按标记区识别，不靠标题）。"""
    tag = f" · 归属 {decl}" if decl else ""
    return f"#### 事件标题\n\n**{rating} · {ev}{tag}**\n\n{extra}\n\n"


def _column(col: str, cards: str) -> str:
    return f"### {col} 栏目标题\n\n{cards}"


def _md(*columns: str, focus: str = "") -> str:
    """最小简报：章 1 结论、章 2 今日必看（focus）、章 3 放所有分类栏目。"""
    return ("---\ntitle: t\ndate: 2026-10-30\n---\n\n"
            "## 本轮结论与技术趋势\n\n结论。\n\n"
            f"## 今日必看\n\n{focus}"
            "## 分类\n\n" + "".join(columns))


def _events(tmp: Path, **evs) -> Path:
    d = tmp / "events"
    d.mkdir()
    for eid, payload in evs.items():
        (d / f"{eid}.json").write_text(json.dumps(payload, ensure_ascii=False),
                                       encoding="utf-8")
    return d


def _status(c: Check, name: str) -> str:
    for r in c.results:
        if r["name"] == name:
            return r["status"]
    raise AssertionError(f"未找到检查项: {name}")


class TaxonomyGateTest(unittest.TestCase):
    def test_definition_passes_on_real_ontology(self):
        c = Check()
        check_taxonomy_definition(c)
        self.assertEqual(c.failed, [])


class EventPathGateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _run(self, **evs) -> Check:
        d = _events(self.tmp, **evs)
        c = Check()
        check_event_paths(c, d)
        return c

    def test_valid_event_passes(self):
        c = self._run(**{"EV-01": {"primary_path": "B1.1", "change_object": "Model"}})
        self.assertEqual(c.failed, [], c.results)

    def test_missing_primary_path_fails(self):
        c = self._run(**{"EV-01": {"change_object": "Model"}})
        self.assertEqual(_status(c, "每个事件都有 primary_path"), "FAIL")

    def test_ambiguous_level2_fails(self):
        # B1 跨 3.2/4.1，停在二级必须被判红
        c = self._run(**{"EV-01": {"primary_path": "B1", "change_object": "Model"}})
        self.assertEqual(_status(c, "跨栏目的二级域已下钻到三级"), "FAIL")

    def test_unknown_path_fails(self):
        c = self._run(**{"EV-01": {"primary_path": "Z9.9", "change_object": "Model"}})
        self.assertEqual(_status(c, "primary_path / related_domains 可解析"), "FAIL")

    def test_unknown_related_domain_fails(self):
        c = self._run(**{"EV-01": {"primary_path": "B1.1", "change_object": "Model",
                                   "related_domains": ["Q1.1"]}})
        self.assertEqual(_status(c, "primary_path / related_domains 可解析"), "FAIL")

    def test_three_related_domains_fails(self):
        c = self._run(**{"EV-01": {"primary_path": "B1.1", "change_object": "Model",
                                   "related_domains": ["A1.1", "B2.1", "C1.1"]}})
        self.assertEqual(_status(c, "关联技术域 <= 2"), "FAIL")

    def test_two_related_domains_pass(self):
        c = self._run(**{"EV-01": {"primary_path": "B1.1", "change_object": "Model",
                                   "related_domains": ["A1.1", "B2.1"]}})
        self.assertEqual(c.failed, [], c.results)

    def test_bad_change_object_fails(self):
        c = self._run(**{"EV-01": {"primary_path": "B1.1", "change_object": "Harness?"}})
        self.assertEqual(_status(c, "change_object 取值合法"), "FAIL")


class AnnotationMapGateTest(unittest.TestCase):
    """4.6 的标注必须能从 primary_path 推出，不能自选宽标签。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _run(self, **evs) -> Check:
        c = Check()
        check_event_annotations(c, _events(self.tmp, **evs))
        return c

    def test_every_leaf_has_exactly_one_label(self):
        amap = TAXONOMY.annotation_map("4.6")
        self.assertEqual(sorted(amap.values()), sorted(TAXONOMY.leaves_of("4.6")))
        self.assertEqual(len(set(amap)), 10, "标签必须一一对应，不能合并叶子")

    def test_d13_has_its_own_label(self):
        # 上一版 7 个标签缺 D1.3，这条事件无处可标
        self.assertEqual(TAXONOMY.annotation_label_for("D1.3"), "可靠性归因")

    def test_matching_annotation_passes(self):
        c = self._run(**{"EV-01": {"primary_path": "D1.3", "annotation": "可靠性归因"}})
        self.assertEqual(_status(c, "4.6 标注与 primary_path 一致"), "PASS")

    def test_wrong_annotation_fails(self):
        c = self._run(**{"EV-01": {"primary_path": "D1.3", "annotation": "结果核验"}})
        self.assertEqual(_status(c, "4.6 标注与 primary_path 一致"), "FAIL")

    def test_missing_annotation_fails(self):
        c = self._run(**{"EV-01": {"primary_path": "D3.2"}})
        self.assertEqual(_status(c, "4.6 标注与 primary_path 一致"), "FAIL")

    def test_non_aggregate_column_not_checked(self):
        c = self._run(**{"EV-01": {"primary_path": "C1.1"}})
        self.assertEqual(_status(c, "4.6 标注与 primary_path 一致"), "PASS")


class UnclassifiedGateTest(unittest.TestCase):
    """未归类必须有出口：缺理由、理由过泛、同时给了主路径，都判红。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _run(self, **evs) -> Check:
        c = Check()
        check_unclassified(c, _events(self.tmp, **evs))
        return c

    def test_no_unclassified_passes(self):
        c = self._run(**{"EV-01": {"primary_path": "B1.1"}})
        self.assertEqual(_status(c, "未归类事件满足三条件"), "PASS")

    def test_unclassified_with_reason_passes(self):
        c = self._run(**{"EV-01": {
            "unclassified": True,
            "unclassified_reason": "该机制描述的是模型与运行时之间的职责重新划分，54 个叶子均不覆盖"}})
        self.assertEqual(_status(c, "未归类事件满足三条件"), "PASS")

    def test_unclassified_without_reason_fails(self):
        c = self._run(**{"EV-01": {"unclassified": True}})
        self.assertEqual(_status(c, "未归类事件满足三条件"), "FAIL")

    def test_vague_reason_fails(self):
        # 旧结构 2.4 变兜底类的原因：一句"跨层"就能装进去
        c = self._run(**{"EV-01": {"unclassified": True, "unclassified_reason": "跨层"}})
        self.assertEqual(_status(c, "未归类事件满足三条件"), "FAIL")

    def test_unclassified_but_also_classified_fails(self):
        c = self._run(**{"EV-01": {
            "unclassified": True, "primary_path": "B1.1",
            "unclassified_reason": "说不清具体落在哪个技术域，暂放这里观察"}})
        self.assertEqual(_status(c, "未归类事件满足三条件"), "FAIL")


class PublishPrecisionGateTest(unittest.TestCase):
    """日粒度事件不得把日期伪装成精确时刻。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _run(self, **evs) -> Check:
        c = Check()
        check_publish_precision(c, _events(self.tmp, **evs))
        return c

    def test_second_precision_passes(self):
        c = self._run(**{"EV-01": {"date_precision": "second",
                                   "first_publish_shanghai": "2026-10-22T13:05:00+08:00"}})
        self.assertEqual(c.failed, [], c.results)

    def test_day_with_note_passes(self):
        c = self._run(**{"EV-01": {"date_precision": "day",
                                   "first_publish_shanghai": "2026-10-22T00:00:00+08:00",
                                   "date_precision_note": "源站只给日期字段，无时刻"}})
        self.assertEqual(c.failed, [], c.results)

    def test_day_without_note_fails(self):
        c = self._run(**{"EV-01": {"date_precision": "day",
                                   "first_publish_shanghai": "2026-10-22T00:00:00+08:00"}})
        self.assertEqual(_status(c, "日粒度事件标注了精度来源"), "FAIL")

    def test_missing_precision_fails(self):
        c = self._run(**{"EV-01": {"first_publish_shanghai": "2026-10-22T00:00:00+08:00"}})
        self.assertEqual(_status(c, "事件声明了 date_precision"), "FAIL")

    def test_batch_precision_not_treated_as_day(self):
        c = self._run(**{"EV-01": {"date_precision": "batch",
                                   "first_publish_shanghai": "2026-10-23T12:00:00+08:00"}})
        self.assertEqual(c.failed, [], c.results)


class MdTaxonomyGateTest(unittest.TestCase):
    """分类呈现规则在 Markdown 源上校验（设计文档 §5）。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _run(self, md: str, **evs) -> Check:
        p = self.tmp / "r-2026-10-30.md"
        p.write_text(md, encoding="utf-8")
        d = _events(self.tmp, **evs) if evs else None
        c = Check()
        check_markdown(c, p, {}, d)
        return c

    def test_conformant_md_passes(self):
        md = _md(_column("3.2", _card("EV-01")), _column("4.1", _card("EV-02")))
        c = self._run(md, **{"EV-01": {"primary_path": "B1.1"},
                             "EV-02": {"primary_path": "C1.1"}})
        failed = [r for r in c.failed if r["gate"] == "taxonomy"]
        self.assertEqual(failed, [], c.results)

    def test_duplicate_main_card_fails(self):
        # 同一事件在两个栏目各写一张完整卡片 → Dashboard 会重复计数
        md = _md(_column("3.2", _card("EV-01")), _column("4.1", _card("EV-01")))
        c = self._run(md, **{"EV-01": {"primary_path": "B1.1"}})
        self.assertEqual(_status(c, "唯一主卡：事件不在多个栏目重复写全卡"), "FAIL")

    def test_card_in_wrong_column_fails(self):
        # primary_path=B1.2 应落 4.1，却写进了 3.2
        md = _md(_column("3.2", _card("EV-01")))
        c = self._run(md, **{"EV-01": {"primary_path": "B1.2"}})
        self.assertEqual(_status(c, "主卡落在 primary_path 对应的栏目"), "FAIL")

    def test_aa_event_without_main_card_fails(self):
        md = _md(_column("3.2", _card("EV-01")))
        c = self._run(md, **{"EV-01": {"primary_path": "B1.1"},
                             "EV-02": {"primary_path": "C1.1", "rating": "A"}})
        self.assertEqual(_status(c, "主卡落在 primary_path 对应的栏目"), "FAIL")

    def test_b_event_without_main_card_passes(self):
        # B 级可只出现在章 5，不强制主卡
        md = _md(_column("3.2", _card("EV-01")))
        c = self._run(md, **{"EV-01": {"primary_path": "B1.1"},
                             "EV-02": {"primary_path": "C1.1", "rating": "B"}})
        self.assertEqual(_status(c, "主卡落在 primary_path 对应的栏目"), "PASS")

    def test_empty_column_rendered_fails(self):
        # 旧实现只登记"有卡的栏目"，空栏目永远查不到（空集恒真）
        md = _md(_column("3.2", _card("EV-01")), _column("3.4", ""))
        c = self._run(md, **{"EV-01": {"primary_path": "B1.1"}})
        self.assertEqual(_status(c, "空栏目不出现在正文"), "FAIL")

    def test_old_structure_column_ids_fail(self):
        md = _md(_column("2.1", _card("EV-01")))
        c = self._run(md, **{"EV-01": {"primary_path": "A1.1"}})
        self.assertEqual(_status(c, "栏目编号均属 11 个栏目"), "FAIL")

    def test_audit_subsections_not_treated_as_columns(self):
        md = _md(_column("3.2", _card("EV-01")), _column("8.1", ""),
                 _column("8.2", ""), _column("8.3", ""))
        c = self._run(md, **{"EV-01": {"primary_path": "B1.1"}})
        self.assertEqual(_status(c, "栏目编号均属 11 个栏目"), "PASS")
        self.assertEqual(_status(c, "空栏目不出现在正文"), "PASS")

    def test_marker_only_event_ids_are_read_in_every_column(self):
        # EV 只写在标记行；第二个栏目的卡片此前按片段内偏移切全文而读丢
        md = _md(_column("3.2", _card("EV-01")), _column("4.7", _card("EV-02")))
        c = self._run(md, **{"EV-01": {"primary_path": "B1.1"},
                             "EV-02": {"primary_path": "E1.1", "rating": "A"}})
        self.assertEqual(_status(c, "主卡落在 primary_path 对应的栏目"), "PASS")

    def test_focus_card_can_hold_main_card(self):
        # 章 2 的 Top 卡声明归属 → 它就是主卡，分类章不再写全卡
        md = _md(_column("4.1", _card("EV-02")),
                 focus=_card("EV-01", decl="3.2", rating="A+"))
        c = self._run(md, **{"EV-01": {"primary_path": "B1.1", "rating": "A+"},
                             "EV-02": {"primary_path": "C1.1"}})
        self.assertEqual(_status(c, "主卡落在 primary_path 对应的栏目"), "PASS")
        self.assertEqual(_status(c, "唯一主卡：事件不在多个栏目重复写全卡"), "PASS")

    def test_column_holding_only_a_cross_reference_is_not_empty(self):
        # 主卡在章 2，分类章 3.2 只留一句交叉引用 —— 规定写法，不是空栏目
        md = _md(_column("3.2", "（主卡见章 2。）\n\n"), _column("4.1", _card("EV-02")),
                 focus=_card("EV-01", decl="3.2", rating="A+"))
        c = self._run(md, **{"EV-01": {"primary_path": "B1.1", "rating": "A+"},
                             "EV-02": {"primary_path": "C1.1"}})
        self.assertEqual(_status(c, "空栏目不出现在正文"), "PASS")

    def test_focus_card_plus_column_card_is_duplicate(self):
        md = _md(_column("3.2", _card("EV-01")),
                 _column("4.1", _card("EV-02")),
                 focus=_card("EV-02", decl="3.2", rating="A+"))
        c = self._run(md, **{"EV-01": {"primary_path": "B1.1"},
                             "EV-02": {"primary_path": "C1.1"}})
        self.assertEqual(_status(c, "唯一主卡：事件不在多个栏目重复写全卡"), "FAIL")

    def test_focus_summary_card_is_not_a_main_card(self):
        # 未声明归属的章 2 卡片是摘要卡，不参与唯一主卡计数
        md = _md(_column("3.2", _card("EV-01")), focus=_card("EV-01", rating="A"))
        c = self._run(md, **{"EV-01": {"primary_path": "B1.1"}})
        self.assertEqual(_status(c, "唯一主卡：事件不在多个栏目重复写全卡"), "PASS")

    def test_annotation_required_in_aggregate_column(self):
        md = _md(_column("4.6", _card("EV-01", "只是可信治理")))
        c = self._run(md, **{"EV-01": {"primary_path": "D3.2"}})
        self.assertEqual(_status(c, "聚合栏目卡片标注了具体技术域"), "FAIL")

    def test_annotation_satisfied_by_specific_domain(self):
        md = _md(_column("4.6", _card("EV-01", "具体属于执行隔离：Sandbox")))
        c = self._run(md, **{"EV-01": {"primary_path": "D3.2"}})
        self.assertEqual(_status(c, "聚合栏目卡片标注了具体技术域"), "PASS")

    def test_annotation_not_required_elsewhere(self):
        md = _md(_column("4.1", _card("EV-01", "无细分标注")))
        c = self._run(md, **{"EV-01": {"primary_path": "C1.1"}})
        self.assertEqual(_status(c, "聚合栏目卡片标注了具体技术域"), "PASS")

    def test_folded_card_declares_real_column(self):
        # 4.5 只有 1 条 → 按设计折进相邻栏目 4.4，并在标记行声明「归属 4.5」
        md = _md(_column("4.4", _card("EV-01", decl="4.5")),
                 _column("4.1", _card("EV-02")))
        c = self._run(md, **{"EV-01": {"primary_path": "B4.1"},
                             "EV-02": {"primary_path": "C1.1"}})
        self.assertEqual(_status(c, "主卡落在 primary_path 对应的栏目"), "PASS")
        self.assertEqual(_status(c, "归属声明是合法栏目"), "PASS")

    def test_folded_card_without_declaration_fails(self):
        md = _md(_column("4.4", _card("EV-01")),
                 _column("4.1", _card("EV-02")))
        c = self._run(md, **{"EV-01": {"primary_path": "B4.1"},
                             "EV-02": {"primary_path": "C1.1"}})
        self.assertEqual(_status(c, "主卡落在 primary_path 对应的栏目"), "FAIL")

    def test_folded_card_with_bogus_column_fails(self):
        md = _md(_column("4.4", _card("EV-01", decl="9.9")),
                 _column("4.1", _card("EV-02")))
        c = self._run(md, **{"EV-01": {"primary_path": "B4.1"},
                             "EV-02": {"primary_path": "C1.1"}})
        self.assertEqual(_status(c, "归属声明是合法栏目"), "FAIL")

    def test_two_cards_folded_into_one_column_fails(self):
        md = _md(_column("4.4", _card("EV-01", decl="4.5") + _card("EV-02", decl="4.5")))
        c = self._run(md, **{"EV-01": {"primary_path": "B4.1"},
                             "EV-02": {"primary_path": "B4.2"}})
        self.assertEqual(_status(c, "折叠栏目只折 1 条"), "FAIL")

    def test_declaring_an_expanded_column_does_not_fold(self):
        # 4.1 有自己的小节，卡片却写在 3.2 并声明归属 4.1 → 位置写错，不算折叠
        md = _md(_column("3.2", _card("EV-01", decl="4.1")),
                 _column("4.1", _card("EV-02")))
        c = self._run(md, **{"EV-01": {"primary_path": "C1.1"},
                             "EV-02": {"primary_path": "C1.2"}})
        self.assertEqual(_status(c, "主卡落在 primary_path 对应的栏目"), "FAIL")


class RegistryGateTest(unittest.TestCase):
    """registry 层门禁：召回由工具生成、本轮已入库、第 7 章引用与派生值一致。"""

    RUN = "2026-10-30"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.state = self.tmp / "state"
        self.evdir = self.tmp / f"events_run_{self.RUN}"
        self.evdir.mkdir()

    def _write(self, eid, **kw):
        from events import normalize_event
        ev = {"event_title": f"事件 {eid}", "source": f"https://ex.com/{eid}", "entity": "OpenAI",
              "first_publish_shanghai": "2026-10-30T10:00:00+08:00", "rating": "A+",
              "primary_path": "B1.1", "change_types": ["CT-01"], "evidence_form": "product",
              "claims": [{"claim": "c", "disposition": f"absorbed:{eid}"}], **kw}
        testlib.decorate(ev)
        ev, errs = normalize_event(ev, eid)
        assert not errs, errs
        (self.evdir / f"{eid}.json").write_text(json.dumps(ev, ensure_ascii=False), encoding="utf-8")
        return ev

    def _ingest(self):
        from thesis_registry import Registry, load_events_dir
        reg = Registry(self.state)
        for f in sorted(self.evdir.glob("EV-*.json")):
            ev = json.loads(f.read_text(encoding="utf-8"))
            ev["thesis_candidates"] = reg.candidates(ev, self.RUN)
            f.write_text(json.dumps(ev, ensure_ascii=False), encoding="utf-8")
        with Registry(self.state) as reg:
            reg.ingest_run(self.RUN, load_events_dir(self.evdir))

    def _new(self, conf_entity=""):
        return {"action": "new", "relation": "supports", "rationale": "r",
                "via_claim": 0,
                "new_thesis": {"name": "n", "statement": "s", "object": "o", "consequence": "c",
                               "scope_leaves": ["B1.1"], "change_types": ["CT-01"]}}

    def _registry(self):
        c = Check()
        check_registry(c, self.evdir, self.state, self.RUN)
        return c

    def test_ingested_run_passes(self):
        self._write("EV-01", thesis_decision=self._new())
        self._ingest()
        c = self._registry()
        self.assertEqual(c.failed, [], c.results)

    def test_missing_run_fails(self):
        self._write("EV-01", thesis_decision=self._new())
        self._ingest()
        c = Check()
        check_registry(c, self.evdir, self.state, "2026-10-31")
        self.assertEqual(_status(c, "本轮 2026-10-31 已入库"), "FAIL")

    def test_event_added_after_ingest_fails(self):
        self._write("EV-01", thesis_decision=self._new())
        self._ingest()
        self._write("EV-02", rating="B")
        self.assertEqual(_status(self._registry(), "入库事件与 events 目录一致"), "FAIL")

    def test_hand_written_candidates_fail(self):
        self._write("EV-01", thesis_decision=self._new())
        self._ingest()
        f = self.evdir / "EV-01.json"
        ev = json.loads(f.read_text(encoding="utf-8"))
        ev["thesis_candidates"] = [{"id": "TH-0099"}]
        f.write_text(json.dumps(ev, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(_status(self._registry(), "A/A+ 候选由 registry candidates 生成"), "FAIL")

    def test_decision_changed_after_ingest_fails(self):
        self._write("EV-01", rating="B", thesis_decision={"action": "none"})
        self._ingest()
        f = self.evdir / "EV-01.json"
        ev = json.loads(f.read_text(encoding="utf-8"))
        ev["thesis_decision"] = self._new()
        f.write_text(json.dumps(ev, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(_status(self._registry(), "裁决已写入 registry"), "FAIL")

    def test_unnormalized_event_fails_trace(self):
        (self.evdir / "EV-09.json").write_text(json.dumps({"rating": "B"}), encoding="utf-8")
        c = Check()
        check_traceability(c, self.evdir)
        self.assertEqual(_status(c, "事件已规范化（有 event_key）"), "FAIL")

    # ---- 第 7 章 ----
    def _md_with_ch7(self, line):
        chapters = "".join(f"## 第{i}章\n\n正文。\n\n" for i in range(1, 7))
        p = self.tmp / f"r-{self.RUN}.md"
        p.write_text(f"---\ntitle: t\n---\n\n{chapters}## 本轮技术判断\n\n{line}\n\n## 信息源\n\n", encoding="utf-8")
        return p

    def _ch7(self, line):
        c = Check()
        check_md_theses(c, self._md_with_ch7(line), self.state, self.RUN)
        return c

    def test_ch7_matching_confidence_passes(self):
        self._write("EV-01", thesis_decision=self._new())          # 单条 A+ → Medium
        self._ingest()
        c = self._ch7("- TH-0001 判断转向专用模型（Frontier，置信度 Medium）")
        self.assertEqual(c.failed, [], c.results)

    def test_ch7_wrong_confidence_fails(self):
        self._write("EV-01", thesis_decision=self._new())
        self._ingest()
        self.assertEqual(_status(self._ch7("- TH-0001（置信度 High）"), "第 7 章置信度与 registry 一致"), "FAIL")

    def test_ch7_low_thesis_fails(self):
        self._write("EV-01", rating="A", thesis_decision=self._new())   # 单条 A → Low
        self._ingest()
        c = self._ch7("- TH-0001（置信度 Low）")
        self.assertEqual(_status(c, "第 7 章只引用 active/contested 且非 Low 的命题"), "FAIL")

    def test_ch7_contested_needs_counter_evidence(self):
        from events import normalize_event
        from thesis_registry import Registry
        self._write("EV-01", thesis_decision=self._new())
        self._ingest()
        run2 = "2026-10-31"
        con, _ = normalize_event({
            "event_title": "反证", "source": "https://ex.com/counter", "entity": "Google",
            "first_publish_shanghai": "2026-10-31T10:00:00+08:00", "rating": "A+",
            "primary_path": "B1.1", "change_types": ["CT-01"], "evidence_form": "paper",
            "thesis_decision": {"action": "attach", "thesis_id": "TH-0001",
                                "relation": "contradicts", "rationale": "r",
                                "via_claim": 0}}, "EV-01")
        with Registry(self.state) as reg:
            reg.ingest_run(run2, [con])
        md = self._md_with_ch7("- TH-0001（置信度 Low）")
        c = Check()
        check_md_theses(c, md, self.state, run2)
        self.assertEqual(_status(c, "contested 命题写出了反证"), "FAIL")
        md = self._md_with_ch7("- TH-0001（置信度 Low，Google 论文给出反证）")
        c = Check()
        check_md_theses(c, md, self.state, run2)
        self.assertEqual(_status(c, "contested 命题写出了反证"), "PASS")

    def test_ch7_unmarked_judgment_fails(self):
        self._write("EV-01", thesis_decision=self._new())
        self._ingest()
        c = self._ch7("- TH-0001（置信度 Medium）\n- 推理成本还会继续下降")
        self.assertEqual(_status(c, "第 7 章每条判断都标了 TH 编号"), "FAIL")

    def test_ch7_must_cover_all_core_judgments(self):
        self._write("EV-01", thesis_decision=self._new())          # TH-0001 为核心判断
        self._ingest()
        c = self._ch7("本轮无核心技术判断。")
        self.assertEqual(_status(c, "第 7 章为空时写明本轮无核心判断"), "FAIL")

    def test_ch7_empty_statement_ok_when_no_core(self):
        self._write("EV-01", rating="B", thesis_decision=self._new())   # 单条 B → proposed
        self._ingest()
        c = self._ch7("本轮无核心技术判断。")
        self.assertEqual(_status(c, "第 7 章为空时写明本轮无核心判断"), "PASS")

    def test_ch7_unknown_thesis_fails(self):
        self._write("EV-01", thesis_decision=self._new())
        self._ingest()
        self.assertEqual(_status(self._ch7("- TH-0042（Medium）"), "第 7 章引用的命题存在"), "FAIL")


class JsonDrivenDutyTest(unittest.TestCase):
    """深拆义务与卡片评级以事件 JSON 为准，不看卡片自报的文字。"""

    WIN = {"target_window": {"start": "2026-10-30T00:00:00+08:00", "end": "2026-10-31T09:00:00+08:00"}}
    DEEP = "##### 挑战与问题\n\n正文。\n\n##### 机制与架构\n\n正文。\n\n##### 效果与定量\n\n正文。\n\n##### 对比其他方案的价值\n\n正文。\n\n"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _run(self, md, **evs):
        d = Path(tempfile.mkdtemp(dir=self.tmp))
        p = d / "r-2026-10-30.md"
        p.write_text(md, encoding="utf-8")
        c = Check()
        check_markdown(c, p, self.WIN, _events(d, **evs))
        return c

    def _ev(self, rating, fp="2026-10-30T10:00:00+08:00"):
        return {"primary_path": "B1.1", "rating": rating, "first_publish_shanghai": fp}

    def test_card_claiming_b_cannot_escape_deep_dive(self):
        c = self._run(_md(_column("3.2", _card("EV-01", rating="B"))), **{"EV-01": self._ev("A")})
        self.assertEqual(_status(c, "A/A+ 主卡含四维深拆（挑战/机制/效果/对比）"), "FAIL")
        self.assertEqual(_status(c, "卡片评级与事件 JSON 一致"), "FAIL")

    def test_convergence_label_does_not_exempt(self):
        c = self._run(_md(_column("3.2", _card("EV-01", rating="A+ · Convergence"))),
                      **{"EV-01": self._ev("A+")})
        self.assertEqual(_status(c, "A/A+ 主卡含四维深拆（挑战/机制/效果/对比）"), "FAIL")

    def test_deep_dive_present_passes(self):
        c = self._run(_md(_column("3.2", _card("EV-01", self.DEEP, rating="A"))), **{"EV-01": self._ev("A")})
        self.assertEqual(_status(c, "A/A+ 主卡含四维深拆（挑战/机制/效果/对比）"), "PASS")
        self.assertEqual(_status(c, "卡片评级与事件 JSON 一致"), "PASS")

    def test_active_event_is_exempt(self):
        c = self._run(_md(_column("3.2", _card("EV-01", rating="A"))),
                      **{"EV-01": self._ev("A", fp="2026-10-28T10:00:00+08:00")})
        self.assertEqual(_status(c, "A/A+ 主卡含四维深拆（挑战/机制/效果/对比）"), "PASS")

    def test_summary_card_in_focus_is_not_a_main_card(self):
        md = _md(_column("3.2", _card("EV-01", self.DEEP, rating="A")), focus=_card("EV-01", rating="A"))
        c = self._run(md, **{"EV-01": self._ev("A")})
        self.assertEqual(_status(c, "A/A+ 主卡含四维深拆（挑战/机制/效果/对比）"), "PASS")

    def test_remote_image_rejected(self):
        c = self._run(_md(_column("3.2", _card("EV-01", "![图](https://ex.com/a.png)"))),
                      **{"EV-01": self._ev("B")})
        self.assertEqual(_status(c, "图片均为本地文件（渲染时内嵌）"), "FAIL")
        c = self._run(_md(_column("3.2", _card("EV-01", "![图](figures/a.svg)"))),
                      **{"EV-01": self._ev("B")})
        self.assertEqual(_status(c, "图片均为本地文件（渲染时内嵌）"), "PASS")

    def test_event_index_rating_is_exact(self):
        md = ("---\ntitle: t\n---\n\n### 8.2 事件索引\n\n| EV | 事件 | 首发 |\n|---|---|---|\n"
              "| EV-01 | Decisions 接口 Active 迁移 API | 2026-10-30 10:00 |\n")
        p = self.tmp / "r-2026-10-30.md"
        p.write_text(md, encoding="utf-8")
        d = _events(self.tmp, **{"EV-01": {"event_title": "Decisions 接口", "rating": "A",
                                           "first_publish_shanghai": "2026-10-30T10:00:00+08:00"}})
        c = Check()
        check_md_event_index(c, p, self.WIN, d)
        self.assertEqual(_status(c, "EV 编号与事件内容一致"), "FAIL",
                         "「Active」「API」里的字母 A 不能算作评级 A")
        p.write_text(md.replace("| Decisions 接口 Active", "| A | Decisions 接口 Active"), encoding="utf-8")
        c = Check()
        check_md_event_index(c, p, self.WIN, d)
        self.assertEqual(_status(c, "EV 编号与事件内容一致"), "PASS")


class UncoverableExpiryTest(unittest.TestCase):
    def test_expired_registration_fails(self):
        c = Check()
        check_source_coverage_definition(c, {"target_window": {"start": "2026-12-15T00:00:00+08:00"}})
        self.assertEqual(_status(c, "不可达登记未过复探期限"), "FAIL")

    def test_current_registration_passes(self):
        c = Check()
        check_source_coverage_definition(c, {"target_window": {"start": "2026-10-30T00:00:00+08:00"}})
        self.assertEqual(_status(c, "不可达登记未过复探期限"), "PASS")
        self.assertEqual(_status(c, "不可达登记写明了补偿方式与复探期限"), "PASS")


class TaxonomyCoverageTest(unittest.TestCase):
    """确认 11 个栏目都能被 MD 切分器识别，没有编号形式上的盲区。"""

    def test_all_columns_reachable(self):
        cols = TAXONOMY.column_ids()
        md = _md(*[_column(col, _card(f"EV-{i:02d}")) for i, col in enumerate(cols, 1)])
        p = Path(tempfile.mkdtemp()) / "r-2026-10-30.md"
        p.write_text(md, encoding="utf-8")
        c = Check()
        check_markdown(c, p, {})
        self.assertEqual(_status(c, "栏目编号均属 11 个栏目"), "PASS")
        self.assertEqual(_status(c, "空栏目不出现在正文"), "PASS")



class Ch1MainlineTest(unittest.TestCase):
    """第 1 章主线必须由技术事件支撑：一个事件撑不起「主线」这个词。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _run(self, ch1_body, ratings=None):
        md = self.tmp / "r.md"
        md.write_text(f"## 本轮结论与技术趋势\n\n{ch1_body}\n\n## 今日必看\n\n正文。\n",
                      encoding="utf-8")
        evdir = self.tmp / "events_run_2026-10-30"
        evdir.mkdir(exist_ok=True)
        for eid, r in (ratings or {}).items():
            (evdir / f"{eid}.json").write_text(
                json.dumps({"event_id": eid, "rating": r}), encoding="utf-8")
        c = Check()
        check_ch1_mainlines(c, md, evdir)
        return {x["name"]: (x["status"], x["detail"]) for x in c.results}

    TWO = ("1. **主线甲。** 证据见 EV-01 与 EV-02。\n"
           "2. **主线乙。** 证据见 EV-03 与 EV-04。")
    RT = {"EV-01": "A", "EV-02": "A", "EV-03": "B", "EV-04": "A+"}

    def test_two_citations_each_passes(self):
        r = self._run(self.TWO, self.RT)
        self.assertEqual({v[0] for v in r.values()}, {"PASS"})

    def test_single_citation_fails(self):
        r = self._run("1. **主线甲。** 只有 EV-01。", self.RT)
        self.assertEqual(r["第 1 章主线各引用 ≥2 个 EV"][0], "FAIL")

    def test_repeated_same_id_is_still_one(self):
        r = self._run("1. **主线甲。** EV-01 与 EV-01。", self.RT)
        self.assertEqual(r["第 1 章主线各引用 ≥2 个 EV"][0], "FAIL")

    def test_dangling_ev_fails(self):
        r = self._run("1. **主线甲。** EV-01 与 EV-77。", self.RT)
        self.assertEqual(r["第 1 章引用的 EV 都存在"][0], "FAIL")

    def test_c_rated_evidence_fails(self):
        r = self._run("1. **主线甲。** EV-01 与 EV-05。",
                      {**self.RT, "EV-05": "C"})
        self.assertEqual(r["第 1 章引用的 EV 评级不低于 B"][0], "FAIL")

    def test_chapter_without_mainlines_fails(self):
        r = self._run("本轮没什么可说的。", self.RT)
        self.assertEqual(r["第 1 章有主线"][0], "FAIL")

    def test_bullet_mainlines_also_counted(self):
        r = self._run("- **主线甲。** EV-01 与 EV-02。\n- **主线乙。** EV-03 与 EV-04。",
                      self.RT)
        self.assertEqual(r["第 1 章主线各引用 ≥2 个 EV"][0], "PASS")

    def test_later_chapters_are_not_scanned(self):
        """第 2 章的卡片不是主线，不应被当成主线来查引用数。"""
        md = self.tmp / "r.md"
        md.write_text("## 本轮结论与技术趋势\n\n1. **主线甲。** EV-01 与 EV-02。\n\n"
                      "## 今日必看\n\n1. **某张卡。** 只提 EV-03。\n", encoding="utf-8")
        evdir = self.tmp / "events_run_2026-10-30"
        evdir.mkdir(exist_ok=True)
        for eid, r in self.RT.items():
            (evdir / f"{eid}.json").write_text(
                json.dumps({"event_id": eid, "rating": r}), encoding="utf-8")
        c = Check()
        check_ch1_mainlines(c, md, evdir)
        self.assertEqual({x["status"] for x in c.results}, {"PASS"})


class ReplaceAnnounceTest(unittest.TestCase):
    """arXiv 的 replace / replace-cross 不是窗口内首发。

    回测动机：2026-11-02 与 2026-11-03 两轮都有 replace 公告被当成新事件写进
    主事件（Heads of Security、EvoMemBench、AgentCollab）。门禁此前只比对
    first_publish 是否落在窗口里，而 replace 的公告日确实在窗口里，所以查不出来。
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.evdir = Path(self._tmp.name) / "events"
        self.evdir.mkdir()
        self.addCleanup(self._tmp.cleanup)

    def _write(self, eid: str, **kw):
        ev = {"rating": "B", "date_precision": "batch",
              "first_publish_shanghai": "2026-11-02T13:00:00+08:00"}
        ev.update(kw)
        (self.evdir / f"{eid}.json").write_text(
            json.dumps(ev, ensure_ascii=False), encoding="utf-8")

    def _status(self):
        c = Check()
        check_publish_precision(c, self.evdir)
        return _status(c, "arXiv replace 不当作窗口内首发")

    def test_new_announcement_passes(self):
        self._write("EV-01", announce_type="new")
        self.assertEqual(self._status(), "PASS")

    def test_cross_v1_passes(self):
        self._write("EV-01", announce_type="cross")
        self.assertEqual(self._status(), "PASS")

    def test_replace_without_marker_fails(self):
        self._write("EV-01", announce_type="replace",
                    date_semantics="arXiv 公告日（replace）")
        self.assertEqual(self._status(), "FAIL")

    def test_replace_cross_without_marker_fails(self):
        self._write("EV-01", announce_type="replace-cross")
        self.assertEqual(self._status(), "FAIL")

    def test_replace_marked_as_active_event_passes(self):
        self._write("EV-01", announce_type="replace",
                    date_semantics="机制披露日；本体首发于历史窗口，按 Active Event 增量记")
        self.assertEqual(self._status(), "PASS")


class CtLabelTest(unittest.TestCase):
    """正文里 CT 编号后面的中文标签必须等于词表里的名字。

    2026-11-01 的报告把 CT-02 写成「机制变化」、CT-05 写成「效率/成本结构变化」
    （那是另一套早期词表），而 ontology 里 CT-02 是「抽象合并」、CT-05 是
    「交互契约变化」。ID 合法，所以当轮 92 项门禁全过，错标签照样发了出去。
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.md = Path(self._tmp.name) / "r-2026-11-02.md"

    def _status(self, body: str) -> str:
        self.md.write_text(body, encoding="utf-8")
        c = Check()
        check_ct_labels(c, self.md)
        return _status(c, "变化类型的中文标签与词表一致")

    def test_correct_label_passes(self):
        self.assertEqual(self._status("| 变化类型 | CT-01 边界迁移 · CT-06 新一等对象 |"),
                         "PASS")

    def test_prefix_of_label_passes(self):
        self.assertEqual(self._status("变化类型：CT-01 边界迁移"), "PASS")

    def test_old_vocabulary_fails(self):
        self.assertEqual(self._status("| 变化类型 | CT-02 机制变化 · CT-05 效率/成本结构变化 |"),
                         "FAIL")

    def test_bare_id_passes(self):
        self.assertEqual(self._status("回扣 CT-03 与 CT-09。"), "PASS")


def _eight_chapters(ch1_7: str, audit: str = "") -> str:
    """固定八章骨架。第 8 章标题写的是「信息源采集统计」而不是以 8 开头——
    第一版 _md_body_before_audit 按标题文字找 "8"，没命中就退回全文，
    于是 8.2 索引表自己把检查喂成了恒绿。这里按真实标题写，守住那个回归。"""
    heads = ["本轮结论与技术趋势", "今日必看", "模型技术热点", "Agent 系统技术热点",
             "值得关注", "业界专家观点与趋势信号", "本轮技术判断"]
    out = []
    for i, h in enumerate(heads):
        out.append(f"## {h}\n\n" + (ch1_7 if i == 2 else "正文。\n") + "\n")
    out.append("## 信息源采集统计\n\n### 8.2 事件索引\n\n" + audit + "\n")
    return "".join(out)


class EventBodyPresenceTest(unittest.TestCase):
    """每个事件都要在第 1–7 章有落点；正文卡片都要有事实源。

    第五轮 EV-09（C 级）在 8.2 索引里有行、有 EV JSON、两边编号对得上、
    门禁 94 项全过，正文里却一个字都没有——"主卡归位"只对 A / A+ 强制，
    B 级及以下允许只出现在章 5，而"是否真的出现在章 5"没有任何检查项。
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.md = self.root / "r-2026-11-03.md"
        self.ev = self.root / "events_run_2026-11-03"
        self.ev.mkdir()

    def _event(self, eid: str, rating: str = "C", path: str = "A2.2"):
        ev = {"rating": rating, "primary_path": path,
              "event_title": f"事件 {eid}",
              "first_publish_shanghai": "2026-11-03T10:00:00+08:00"}
        (self.ev / f"{eid}.json").write_text(
            json.dumps(ev, ensure_ascii=False), encoding="utf-8")

    def _run(self, body: str, audit: str = "", name: str = "每个事件在第 1–7 章有落点"):
        self.md.write_text(_eight_chapters(body, audit), encoding="utf-8")
        c = Check()
        check_event_body_presence(c, self.md, self.ev)
        return _status(c, name)

    def test_card_in_body_passes(self):
        self._event("EV-09")
        self.assertEqual(self._run("### 3.1 模型架构、训练与适应\n\n"
                                   + _card("EV-09", decl="3.1")), "PASS")

    def test_mentioned_only_in_chapter5_passes(self):
        """B / C 级只在章 5 露面是规定写法，不该被这条检查打红。"""
        self._event("EV-09")
        self.md.write_text(_eight_chapters("正文。\n").replace(
            "## 值得关注\n\n正文。", "## 值得关注\n\n- **EV-09** 持续信号。"),
            encoding="utf-8")
        c = Check()
        check_event_body_presence(c, self.md, self.ev)
        self.assertEqual(_status(c, "每个事件在第 1–7 章有落点"), "PASS")

    def test_only_in_audit_index_fails(self):
        self._event("EV-09")
        self.assertEqual(self._run("正文。\n", audit="| EV-09 | C | 标题 |"), "FAIL")

    def test_audit_chapter_title_is_not_numbered(self):
        """回归：审计章必须被切掉。切不掉的话上一条会误判为 PASS。"""
        self._event("EV-09")
        md = _eight_chapters("正文。\n", audit="| EV-09 | C | 标题 |")
        self.assertFalse([h for h in re.findall(r'^## +(.*)$', md, re.M)
                          if h.startswith("8")])     # 二级章标题确实不以 8 开头
        self.md.write_text(md, encoding="utf-8")
        c = Check()
        check_event_body_presence(c, self.md, self.ev)
        self.assertEqual(_status(c, "每个事件在第 1–7 章有落点"), "FAIL")

    def test_card_without_event_json_fails(self):
        self._event("EV-01")
        self.assertEqual(
            self._run("### 3.1 模型架构、训练与适应\n\n"
                      + _card("EV-01", decl="3.1") + _card("EV-77", decl="3.1"),
                      audit="| EV-01 | C |"),
            "PASS")
        self.md.write_text(_eight_chapters(
            "### 3.1 模型架构、训练与适应\n\n"
            + _card("EV-01", decl="3.1") + _card("EV-77", decl="3.1")), encoding="utf-8")
        c = Check()
        check_event_body_presence(c, self.md, self.ev)
        self.assertEqual(_status(c, "正文卡片都有对应的 EV JSON"), "FAIL")

    def test_missing_chapter_eight_does_not_go_vacuous(self):
        """定位不到第 8 章时必须打红，不能退回全文把检查喂成恒绿。"""
        self._event("EV-09")
        self.md.write_text("## 只有一章\n\n| EV-09 | C |\n", encoding="utf-8")
        c = Check()
        check_event_body_presence(c, self.md, self.ev)
        self.assertEqual(_status(c, "能切出第 1–7 章正文"), "FAIL")


class DegradedHeaderTest(unittest.TestCase):
    """门禁失败时生成的降级交付节（2026-11-10 起附在正文末尾，不再插在开头）。

    定时跑的兜底：重试到上限仍不过，与其静默不交付，不如把本轮产出交出去——
    但读者必须一眼看出是降级的。所以这段说明由门禁结果派生而不是手写：
    手写的「已知问题」会漏项，也会随稿子变动而失真。
    """

    def _summary(self, **kw):
        base = {"attempt": 3, "max_attempts": 3, "passed": 89, "warned": 1,
                "checked_at": "2026-11-09T10:45:58+08:00", "script_commit": "abc1234",
                "failed_detail": [{"name": "第 1 章主线各引用 ≥2 个 EV",
                                   "detail": "「主线一」只引用 1 个 EV"}]}
        base.update(kw)
        return base

    def test_carries_the_sentinel_for_the_renderer(self):
        """包装器靠这个哨兵确认稿子真带了降级节，才放行 --allow-gate-fail。"""
        self.assertIn("<!-- gate-degraded -->", _degraded_header(self._summary()))

    def test_uses_the_renderer_callout_syntax(self):
        """渲染器认的是 > [WARNING]，不是 GitHub 的 > [!WARNING]；
        写错了只会渲染成一段普通引用，警告就不显眼了。"""
        out = _degraded_header(self._summary())
        self.assertIn("> [WARNING]", out)
        self.assertNotIn("[!WARNING]", out)

    def test_lists_every_failure_with_detail(self):
        out = _degraded_header(self._summary(failed_detail=[
            {"name": "A", "detail": "细节甲"}, {"name": "B", "detail": "细节乙"}]))
        for x in ("A", "细节甲", "B", "细节乙"):
            self.assertIn(x, out)

    def test_states_attempt_and_counts(self):
        out = _degraded_header(self._summary())
        self.assertIn("第 3 轮", out)
        self.assertIn("上限 3 轮", out)
        self.assertIn("abc1234", out)
        self.assertIn("89", out)

    def test_failure_without_detail_still_listed(self):
        out = _degraded_header(self._summary(failed_detail=[{"name": "某项", "detail": ""}]))
        self.assertIn("某项", out)

    def test_detail_newlines_collapsed(self):
        out = _degraded_header(self._summary(failed_detail=[
            {"name": "X", "detail": "第一行\n第二行"}]))
        self.assertNotIn("\n第二行", out)      # 多行 detail 会破坏引用块
        self.assertIn("第一行 第二行", out)


class PairwiseValueGuardTest(unittest.TestCase):
    """成对裁定不能把低价值事件排到高价值之前。

    业务优先级（business_tier）只影响 Top N 的呈现次序，不影响评级与召回。但"次序"
    与"价值"在实现上只隔一步：裁定的 why 是自由文本，没有约束时一句「tier-1 优先」
    就能把 A 级安全事件排到 B 级模型事件之后，优先级于是悄悄变成了降权。
    这条检查的对象是裁定本身，防的是规则被 why 字段绕过。
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ev = Path(self._tmp.name) / "events_run_2026-11-08"
        self.ev.mkdir()
        self.pw = self.ev / "pairwise.json"

    def _write(self, eid, rating, scores):
        # 2026-11-11 起只有四维（权威已移除），元组按 影响/机制/量化/战略
        dims = ("magnitude", "mechanism_novelty",
                "quantitative_evidence", "strategic_adjacency")
        ev = {"rating": rating, "primary_path": "D3.1", "event_title": eid,
              "first_publish_shanghai": "2026-11-08T10:00:00+08:00",
              "scoring": {d: {"score": v, "evidence": "x"} for d, v in zip(dims, scores)}}
        (self.ev / f"{eid}.json").write_text(json.dumps(ev, ensure_ascii=False),
                                             encoding="utf-8")

    def _decide(self, pair, winner, why="tier-1 优先"):
        self.pw.write_text(json.dumps(
            {"decisions": [{"pair": list(pair), "winner": winner, "why": why}]},
            ensure_ascii=False), encoding="utf-8")

    def _run(self):
        c = Check()
        check_scoring(c, self.ev, self.pw)
        return _status(c, "成对裁定未把低价值事件排到高价值之前")

    def test_tier_may_break_a_one_point_tie(self):
        """分差 1 分之内算噪声，用业务优先级裁决是允许的。"""
        self._write("EV-01", "B", (1, 1, 1, 1))   # 4
        self._write("EV-02", "B", (2, 1, 1, 1))   # 5
        self._decide(("EV-01", "EV-02"), "EV-01")
        self.assertEqual(self._run(), "PASS")

    def test_equal_scores_may_be_broken_by_tier(self):
        self._write("EV-01", "B", (1, 1, 1, 1))   # 4
        self._write("EV-02", "B", (1, 1, 1, 1))   # 4
        self._decide(("EV-01", "EV-02"), "EV-01")
        self.assertEqual(self._run(), "PASS")

    def test_cannot_win_across_rating_bands(self):
        """A 级安全事件被 B 级模型事件压到后面 —— 正是要防的那一步。"""
        self._write("EV-01", "B", (2, 1, 1, 1))   # 5
        self._write("EV-02", "A", (2, 2, 1, 2))   # 7
        self._decide(("EV-01", "EV-02"), "EV-01")
        self.assertEqual(self._run(), "FAIL")

    def test_cannot_win_with_two_point_deficit(self):
        self._write("EV-01", "B", (1, 1, 1, 0))   # 3
        self._write("EV-02", "B", (2, 2, 1, 0))   # 5
        self._decide(("EV-01", "EV-02"), "EV-01")
        self.assertEqual(self._run(), "FAIL")

    def test_higher_value_winner_always_fine(self):
        self._write("EV-01", "A", (2, 2, 1, 2))   # 7
        self._write("EV-02", "C", (0, 0, 0, 0))   # 0
        self._decide(("EV-01", "EV-02"), "EV-01")
        self.assertEqual(self._run(), "PASS")

    def test_malformed_decision_is_skipped_not_crashed(self):
        self._write("EV-01", "B", (1, 1, 1, 1))
        self._write("EV-02", "B", (1, 1, 1, 1))
        self.pw.write_text(json.dumps({"decisions": [
            {"pair": ["EV-01"], "winner": "EV-01", "why": "x"},
            {"pair": ["EV-01", "EV-99"], "winner": "EV-01", "why": "x"}]}),
            encoding="utf-8")
        self.assertEqual(self._run(), "PASS")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class DegradedSectionPlacementTest(unittest.TestCase):
    """降级说明改为末尾节（2026-11-10）。

    反馈是「放在最上面没有什么价值，除非有办法解决」——降级项绝大多数是采集与
    覆盖缺口，读者当场无法处置，只影响他怎么引用正文。所以位置挪到末尾，
    同时每项必须说清对本稿的影响，否则读者拿到的只是一串检查项名字。
    """

    def _summary(self, failed):
        return {"attempt": 3, "max_attempts": 3, "failed_detail": failed,
                "passed": 88, "warned": 0, "checked_at": "2026-11-10T03:11:00+08:00",
                "script_commit": "abc1234"}

    def test_section_has_a_heading_so_it_reads_as_the_last_section(self):
        out = verify_gates._degraded_section(self._summary(
            [{"gate": "collection", "name": "critical 源全部可用", "detail": "hn_newest"}]))
        self.assertIn("## 门禁未通过项与影响", out)
        self.assertTrue(out.startswith(verify_gates.GATE_DEGRADED_MARK),
                        "哨兵必须在节首，渲染包装器靠它放行 --allow-gate-fail")

    def test_every_row_states_an_impact(self):
        """只列检查项名字等于没说——每行必须给出对本稿的影响。"""
        failed = [{"gate": g, "name": f"检查{g}", "detail": "d"}
                  for g in ("collection", "coverage", "md", "taxonomy",
                            "trace", "registry", "html")]
        out = verify_gates._degraded_section(self._summary(failed))
        for g in ("collection", "coverage", "md", "taxonomy", "trace", "registry", "html"):
            self.assertIn(verify_gates._DEGRADED_IMPACT[g], out, f"{g} 缺影响说明")

    def test_unknown_gate_falls_back_rather_than_crashing(self):
        out = verify_gates._degraded_section(self._summary(
            [{"gate": "something_new", "name": "N", "detail": "d"}]))
        self.assertIn(verify_gates._DEGRADED_IMPACT_DEFAULT, out)

    def test_impact_differs_by_gate(self):
        """采集缺口和渲染未达标对读者的意义完全不同，不能共用一句话。"""
        self.assertNotEqual(verify_gates._DEGRADED_IMPACT["collection"],
                            verify_gates._DEGRADED_IMPACT["html"])


class Tier1GuardTest(unittest.TestCase):
    """tier-1 命中项不得以「未验证」结案（task_def 16.2）。

    2026-11-09 那轮的真实漏判：76 条必审里约 50 条共用「未验证」，
    Flex-RSI、BOXBOX、Knowing When to Intervene 三条就此消失，
    而同一轮 ERNIE Evolve（同属 RSI）被评 A 并立了 TH-0001。
    """

    REAL_MISSES = [
        "Flex-RSI: Benchmarking Recursive Self-Improvement of Frontier Agents",
        "BOXBOX: Recursive Harness Self-Improvement for Long-Running Performance Optimization",
        "Knowing When to Intervene: Causal Evaluation of AI Agents",
    ]

    def test_catches_the_three_known_misses(self):
        for t in self.REAL_MISSES:
            self.assertTrue(verify_gates._tier1_guard_hit(t), f"漏掉 {t[:40]}")

    def test_lets_unrelated_items_through(self):
        """守卫过宽就会被绕开，所以与 tier-1 无关的条目必须放行。"""
        for t in ["MorphSched: Workload-Aware Adaptive Scheduler Generation for Linux",
                  "Fold Epic Paper Airplanes",
                  "AdaAlloc: Adaptive Visual Token Allocation for Long-Video Question Answering"]:
            self.assertEqual(verify_gates._tier1_guard_hit(t), "", f"误拦 {t[:40]}")

    def test_bare_broad_words_are_not_in_the_list(self):
        """memory / reasoning / tool use 这类裸词会把拦截面推到 37%，不能收。"""
        words = verify_gates._tier1_guard_words()
        for w in ("memory", "reasoning", "tool use", "agent", "benchmark", "eval"):
            self.assertNotIn(w, words, f"{w!r} 过宽，会让门禁被绕开")

    def test_gate_fails_when_a_tier1_hit_is_discarded_as_unverified(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            mr = {"items": [{"uid": "u1", "title": self.REAL_MISSES[0],
                             "url": "https://arxiv.org/abs/2611.08946"}]}
            (root / "must_review.json").write_text(json.dumps(mr, ensure_ascii=False),
                                                   encoding="utf-8")
            trace = {"dispositions": {"u1": {"disposition": "discarded",
                                             "reason": "未验证"}}}
            (root / "must_review_trace.json").write_text(
                json.dumps(trace, ensure_ascii=False), encoding="utf-8")
            c = Check()
            verify_gates.check_must_review(c, root / "must_review.json",
                                           root / "must_review_trace.json", None)
            named = [r for r in c.results
                     if r["name"] == "tier-1 命中项未被「未验证」静默丢弃"]
            self.assertTrue(named, "门禁项没跑起来")
            self.assertEqual(named[0]["status"], "FAIL")

    def test_gate_passes_when_demoted_to_chapter5(self):
        """降到第 5 章留线索位就是合规出口。"""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            mr = {"items": [{"uid": "u1", "title": self.REAL_MISSES[2], "url": "https://x/1"}]}
            (root / "must_review.json").write_text(json.dumps(mr, ensure_ascii=False),
                                                   encoding="utf-8")
            trace = {"dispositions": {"u1": {"disposition": "chapter5",
                                             "reason": "主动介入，对应根技术 P5，留线索位"}}}
            (root / "must_review_trace.json").write_text(
                json.dumps(trace, ensure_ascii=False), encoding="utf-8")
            c = Check()
            verify_gates.check_must_review(c, root / "must_review.json",
                                           root / "must_review_trace.json", None)
            named = [r for r in c.results
                     if r["name"] == "tier-1 命中项未被「未验证」静默丢弃"]
            self.assertEqual(named[0]["status"], "PASS")

    def test_other_discard_reasons_are_still_allowed(self):
        """给出真正说明情况的理由（如首发早于窗口）仍可丢弃。"""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            mr = {"items": [{"uid": "u1", "title": self.REAL_MISSES[1], "url": "https://x/1"}]}
            (root / "must_review.json").write_text(json.dumps(mr, ensure_ascii=False),
                                                   encoding="utf-8")
            trace = {"dispositions": {"u1": {"disposition": "discarded",
                                             "reason": "首发早于 WINDOW_START"}}}
            (root / "must_review_trace.json").write_text(
                json.dumps(trace, ensure_ascii=False), encoding="utf-8")
            c = Check()
            verify_gates.check_must_review(c, root / "must_review.json",
                                           root / "must_review_trace.json", None)
            named = [r for r in c.results
                     if r["name"] == "tier-1 命中项未被「未验证」静默丢弃"]
            self.assertEqual(named[0]["status"], "PASS")


class CardLayerTest(unittest.TestCase):
    """卡片标记行的 change_object 与渲染配色（2026-11-10）。

    渲染器按 change_object 给卡片上色。标记行与事件 JSON 不一致时颜色会说谎——
    读者按颜色判断「这个变化发生在哪一层」，而那个判断来自没人核对过的字段。
    """

    def _card(self, decl: str) -> str:
        # 卡片要落在第 2 章才会被 _md_layout 收进 focus，所以前面补一个 ## 占位
        return (f"## 1 本轮结论\n\n略。\n\n## 2 今日必看\n\n"
                f"#### A｜一条\n\n**{decl}**\n\n正文。\n")

    def test_extracts_each_layer(self):
        for v in verify_gates.CARD_LAYERS:
            got = verify_gates._md_card_layer(f"**A · Frontier · EV-01 · {v} · 归属 4.5**")
            self.assertEqual(got, v)

    def test_interaction_layer_survives_the_separator(self):
        """「交互·应用」里的点与标记行分隔符同形，按分隔符切会把它切成两半。"""
        self.assertEqual(
            verify_gates._md_card_layer("**B · Early Signal · EV-04 · 交互·应用**"),
            "交互·应用")

    def test_ignores_marker_without_ev(self):
        """只认带 EV 编号的那一行，正文里出现层名不算声明。"""
        self.assertEqual(verify_gates._md_card_layer("**这不是标记行 Model**"), "")

    def _run(self, decl, change_object):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            md = root / "r.md"
            md.write_text("---\ntitle: T\ndate: 2026-11-10\n---\n\n" + self._card(decl),
                          encoding="utf-8")
            ev = root / "events"
            ev.mkdir()
            (ev / "EV-01.json").write_text(
                json.dumps({"event_id": "EV-01", "rating": "A",
                            "change_object": change_object}, ensure_ascii=False),
                encoding="utf-8")
            c = Check()
            verify_gates.check_card_layers(c, md, ev)
            return {r["name"]: r["status"] for r in c.results}

    def test_mismatch_with_event_json_fails(self):
        r = self._run("A · Frontier · EV-01 · Model", "Harness")
        self.assertEqual(r["卡片层标注与事件 JSON 一致"], "FAIL")

    def test_match_passes(self):
        r = self._run("A · Frontier · EV-01 · Harness", "Harness")
        self.assertEqual(r["卡片层标注与事件 JSON 一致"], "PASS")
        self.assertEqual(r["卡片标记行写明 change_object"], "PASS")

    def test_missing_layer_fails(self):
        r = self._run("A · Frontier · EV-01", "Model")
        self.assertEqual(r["卡片标记行写明 change_object"], "FAIL")


class ScoringDiscriminationTest(unittest.TestCase):
    """这一轮的打分有没有在区分事件（2026-11-11）。

    起因：11-10 那轮 21 个事件的 source_authority 全是 2，12 个事件卡在同一合计上，
    A 率 62%（历史 31%~42%）。单看每张卡都自洽、单看规则也没违反，但整轮打分
    没有在区分任何东西。这条检查不管分打得对不对，只管分有没有在分。
    """

    def _run(self, rows):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        for i, vals in enumerate(rows, 1):
            (d / f"EV-{i:02d}.json").write_text(json.dumps(
                {"event_id": f"EV-{i:02d}",
                 "scoring": {k: {"score": x, "evidence": "e"}
                             for k, x in zip(verify_gates.SCORING_DIMENSIONS, vals)}},
                ensure_ascii=False), encoding="utf-8")
        c = Check()
        verify_gates.check_scoring_discrimination(c, d)
        return {r["name"]: r["status"] for r in c.results}

    def test_constant_dimension_fails(self):
        """某个维度全轮同值 = 这个维度这一轮没在区分任何事件。"""
        rows = [[2, m, q, a] for m in (1, 2) for q in (0, 1, 2) for a in (1, 2)]
        r = self._run(rows)
        self.assertEqual(r["没有在本轮失去区分度的打分维度"], "FAIL")

    def test_varied_dimensions_pass(self):
        rows = [[m, n, q, a] for m in (1, 2) for n in (0, 1, 2) for q in (1, 2) for a in (1, 2)]
        r = self._run(rows)
        self.assertEqual(r["没有在本轮失去区分度的打分维度"], "PASS")

    def test_piling_on_one_total_fails(self):
        """11-10 的真实形态：12/21 压在同一个合计，而那个合计正好贴着门槛。"""
        rows = [[2, 1, 2, 1]] * 12 + [[1, 2, 2, 1], [2, 2, 1, 1], [1, 1, 2, 1],
                                      [2, 1, 1, 1], [1, 2, 1, 1], [2, 2, 2, 1],
                                      [1, 1, 1, 1], [2, 1, 2, 2], [1, 2, 2, 2]]
        r = self._run(rows)
        self.assertEqual(r["打分未在单一合计上堆积"], "FAIL")

    def test_historical_spread_passes(self):
        """历史六轮同分占比最高 42%，上限取 50%，不能误伤。"""
        rows = ([[1, 1, 1, 1]] * 5 + [[2, 1, 1, 1]] * 3 + [[2, 2, 1, 1]] * 2
                + [[1, 0, 2, 1], [2, 2, 2, 2]])
        r = self._run(rows)
        self.assertEqual(r["打分未在单一合计上堆积"], "PASS")

    def test_small_round_is_not_judged(self):
        """事件太少时分布本来就可能集中，不判。"""
        r = self._run([[2, 1, 1, 1]] * 5)
        self.assertEqual(r, {}, "样本不足时不该给出结论")

    def test_dimensions_track_scoring_module(self):
        """维度表从 scoring.py 取，不能两处各写一份。"""
        import scoring
        self.assertEqual(tuple(verify_gates.SCORING_DIMENSIONS),
                         tuple(scoring.DIMENSIONS))
        self.assertNotIn("source_authority", verify_gates.SCORING_DIMENSIONS)
