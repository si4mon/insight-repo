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
import tempfile
import unittest
from pathlib import Path

from taxonomy import TAXONOMY
from verify_gates import (Check, check_event_annotations, check_event_paths,
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
                                "relation": "contradicts", "rationale": "r"}}, "EV-01")
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
