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
from verify_gates import (Check, check_event_paths, check_html_taxonomy,
                          check_publish_precision, check_taxonomy_definition,
                          check_unclassified)


def _card(ev: str, extra: str = "", cls: str = "", column: str = "") -> str:
    attr = f' data-column="{column}"' if column else ""
    return (f'<div class="card{cls}"{attr}><div class="chd"><span class="rank">{ev}</span>'
            f'<h5>t</h5></div>{extra}</div>')


def _column(col: str, cards: str) -> str:
    return f'<h4 id="s{col.replace(".", "-")}">{col} 标题</h4>{cards}'


def _html(*columns: str) -> str:
    body = "".join(columns)
    return f'<html><head><title>t</title></head><body><h1>h</h1>{body}</body></html>'


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
        p = self.tmp / "r.html"
        p.write_text(_html(_column("4.6", "")), encoding="utf-8")
        c = Check()
        check_html_taxonomy(c, p, _events(self.tmp, **evs))
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


class HtmlTaxonomyGateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _run(self, html: str, **evs) -> Check:
        p = self.tmp / "r.html"
        p.write_text(html, encoding="utf-8")
        d = _events(self.tmp, **evs) if evs else None
        c = Check()
        check_html_taxonomy(c, p, d)
        return c

    def test_conformant_html_passes(self):
        html = _html(_column("3.2", _card("EV-01")), _column("4.1", _card("EV-02")))
        c = self._run(html,
                      **{"EV-01": {"primary_path": "B1.1"},
                         "EV-02": {"primary_path": "C1.1"}})
        self.assertEqual(c.failed, [], c.results)

    def test_duplicate_main_card_fails(self):
        # 同一事件在两个栏目各写一张完整卡片 → Dashboard 会重复计数
        html = _html(_column("3.2", _card("EV-01")), _column("4.1", _card("EV-01")))
        c = self._run(html, **{"EV-01": {"primary_path": "B1.1"}})
        self.assertEqual(_status(c, "唯一主卡：事件不在多个栏目重复写全卡"), "FAIL")

    def test_card_in_wrong_column_fails(self):
        # primary_path=B1.2 应落 4.1，却写进了 3.2
        html = _html(_column("3.2", _card("EV-01")))
        c = self._run(html, **{"EV-01": {"primary_path": "B1.2"}})
        self.assertEqual(_status(c, "主卡落在 primary_path 对应的栏目"), "FAIL")

    def test_empty_column_rendered_fails(self):
        html = _html(_column("3.2", _card("EV-01")), _column("3.4", ""))
        c = self._run(html, **{"EV-01": {"primary_path": "B1.1"}})
        self.assertEqual(_status(c, "空栏目不出现在正文"), "FAIL")

    def test_old_structure_column_ids_fail(self):
        html = _html(_column("2.1", _card("EV-01")))
        c = self._run(html, **{"EV-01": {"primary_path": "A1.1"}})
        self.assertEqual(_status(c, "HTML 栏目编号均属 11 个栏目"), "FAIL")

    def test_audit_subsections_not_treated_as_columns(self):
        html = _html(_column("3.2", _card("EV-01")), _column("8.1", ""),
                     _column("8.2", ""), _column("8.3", ""))
        c = self._run(html, **{"EV-01": {"primary_path": "B1.1"}})
        self.assertEqual(_status(c, "HTML 栏目编号均属 11 个栏目"), "PASS")

    def test_last_column_card_is_counted(self):
        # 最后一段没有 </section> 结尾，旧正则会把它的卡片整个漏掉
        html = _html(_column("3.2", _card("EV-01")), _column("4.7", _card("EV-02")))
        c = self._run(html, **{"EV-01": {"primary_path": "B1.1"},
                               "EV-02": {"primary_path": "E1.1"}})
        self.assertEqual(_status(c, "主卡落在 primary_path 对应的栏目"), "PASS")

    def test_annotation_required_in_aggregate_column(self):
        html = _html(_column("4.6", _card("EV-01", "<p>只是可信治理</p>")))
        c = self._run(html, **{"EV-01": {"primary_path": "D3.2"}})
        self.assertEqual(_status(c, "聚合栏目卡片标注了具体技术域"), "FAIL")

    def test_annotation_satisfied_by_specific_domain(self):
        html = _html(_column("4.6", _card("EV-01", "<p>具体属于执行隔离：Sandbox</p>")))
        c = self._run(html, **{"EV-01": {"primary_path": "D3.2"}})
        self.assertEqual(_status(c, "聚合栏目卡片标注了具体技术域"), "PASS")

    def test_folded_card_declares_real_column(self):
        # 4.5 只有 1 条 → 按设计折进相邻栏目 4.4，但必须用 data-column 声明归属
        html = _html(_column("4.4", _card("EV-01", column="4.5")),
                     _column("4.1", _card("EV-02")))
        c = self._run(html, **{"EV-01": {"primary_path": "B4.1"},
                               "EV-02": {"primary_path": "C1.1"}})
        self.assertEqual(_status(c, "主卡落在 primary_path 对应的栏目"), "PASS")
        self.assertEqual(_status(c, "折叠卡的 data-column 是合法栏目"), "PASS")

    def test_folded_card_without_declaration_fails(self):
        html = _html(_column("4.4", _card("EV-01")),
                     _column("4.1", _card("EV-02")))
        c = self._run(html, **{"EV-01": {"primary_path": "B4.1"},
                               "EV-02": {"primary_path": "C1.1"}})
        self.assertEqual(_status(c, "主卡落在 primary_path 对应的栏目"), "FAIL")

    def test_folded_card_with_bogus_column_fails(self):
        html = _html(_column("4.4", _card("EV-01", column="9.9")),
                     _column("4.1", _card("EV-02")))
        c = self._run(html, **{"EV-01": {"primary_path": "B4.1"},
                               "EV-02": {"primary_path": "C1.1"}})
        self.assertEqual(_status(c, "折叠卡的 data-column 是合法栏目"), "FAIL")

    def test_two_cards_folded_into_one_column_fails(self):
        html = _html(_column("4.4", _card("EV-01", column="4.5") + _card("EV-02", column="4.5")))
        c = self._run(html, **{"EV-01": {"primary_path": "B4.1"},
                               "EV-02": {"primary_path": "B4.2"}})
        self.assertEqual(_status(c, "折叠栏目只折 1 条"), "FAIL")

    def test_annotation_not_required_elsewhere(self):
        html = _html(_column("4.1", _card("EV-01", "<p>无细分标注</p>")))
        c = self._run(html, **{"EV-01": {"primary_path": "C1.1"}})
        self.assertEqual(_status(c, "聚合栏目卡片标注了具体技术域"), "PASS")


class TaxonomyCoverageTest(unittest.TestCase):
    """确认 11 个栏目都能被 HTML 切分器识别，没有编号形式上的盲区。"""

    def test_all_columns_reachable(self):
        cols = TAXONOMY.column_ids()
        html = _html(*[_column(c, "") for c in cols])
        p = Path(tempfile.mkdtemp()) / "r.html"
        p.write_text(html, encoding="utf-8")
        c = Check()
        # 只跑"未知栏目"这一项，空栏目报 FAIL 是预期的
        check_html_taxonomy(c, p, None)
        self.assertEqual(_status(c, "HTML 栏目编号均属 11 个栏目"), "PASS")


if __name__ == "__main__":
    unittest.main(verbosity=2)
