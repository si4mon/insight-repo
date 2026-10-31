#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
taxonomy 单测：守住 54 叶子 / 11 栏目映射的结构不变式。

用标准库 unittest，不引入额外依赖：
  python test_taxonomy.py
  python -m unittest test_taxonomy -v
"""
import unittest
from pathlib import Path

from taxonomy import AmbiguousPath, Taxonomy, TaxonomyError, TAXONOMY


REPO_MAP = Path(__file__).resolve().parents[1] / "data" / "四层技术地图.txt"


def _map_leaves() -> dict[str, str]:
    """从源地图直接解析叶子 id → 名称，作为独立第二来源。"""
    raw = REPO_MAP.read_bytes().decode("gb18030")
    leaves = {}
    for line in raw.splitlines():
        cols = line.split("\t")
        if len(cols) >= 2 and cols[1].strip().startswith(("A", "B", "C", "D", "E")):
            head = cols[1].strip().split()
            if head and "." in head[0]:
                leaves[head[0]] = " ".join(head[1:])
    return leaves


class TaxonomyStructureTest(unittest.TestCase):
    def test_validation_passes(self):
        results = TAXONOMY.validate()
        failed = [x for x in results if not x["ok"]]
        self.assertEqual(failed, [], f"validate 失败: {failed}")

    def test_54_leaves_cover_source_map(self):
        source = _map_leaves()
        self.assertEqual(len(source), 54, "源地图叶子数应为 54")
        self.assertEqual(set(source), set(TAXONOMY.leaf_ids()),
                         "ontology 叶子必须与四层技术地图完全一致")

    def test_leaf_names_match_source_map(self):
        source = _map_leaves()
        mismatched = {
            lid: (source[lid], TAXONOMY.leaf(lid)["name"])
            for lid in source if source[lid] != TAXONOMY.leaf(lid)["name"]
        }
        self.assertEqual(mismatched, {}, f"叶子名称与源地图不一致: {mismatched}")

    def test_every_leaf_has_exactly_one_column(self):
        seen = {}
        for cid in TAXONOMY.column_ids():
            for lid in TAXONOMY.leaves_of(cid):
                self.assertNotIn(lid, seen, f"{lid} 同时出现在 {seen.get(lid)} 和 {cid}")
                seen[lid] = cid
        self.assertEqual(set(seen), set(TAXONOMY.leaf_ids()), "有叶子未被任何栏目覆盖")
        for lid in TAXONOMY.leaf_ids():
            self.assertEqual(TAXONOMY.column_of(lid), seen[lid])

    def test_column_counts(self):
        self.assertEqual(TAXONOMY.column_ids_of_chapter(3),
                         ["3.1", "3.2", "3.3", "3.4"])
        self.assertEqual(TAXONOMY.column_ids_of_chapter(4),
                         ["4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7"])
        total = sum(len(TAXONOMY.leaves_of(c)) for c in TAXONOMY.column_ids())
        self.assertEqual(total, 54)

    def test_chapters_and_anchors(self):
        self.assertEqual([TAXONOMY.section_id(n) for n in range(1, 9)],
                         [f"s{n}" for n in range(1, 9)])
        self.assertEqual(TAXONOMY.anchor("3.2"), "s3-2")
        self.assertEqual(TAXONOMY.anchor("4.7"), "s4-7")


class TaxonomyResolveTest(unittest.TestCase):
    def test_leaf_resolve(self):
        self.assertEqual(TAXONOMY.resolve("B1.1"), "3.2")
        self.assertEqual(TAXONOMY.resolve("B1.2"), "4.1")
        self.assertEqual(TAXONOMY.resolve("B1.3"), "4.1")
        self.assertEqual(TAXONOMY.resolve("A1.4"), "3.1")
        self.assertEqual(TAXONOMY.resolve("C3.1"), "4.3")
        self.assertEqual(TAXONOMY.resolve("C3.2"), "4.4")

    def test_single_column_level2_allowed(self):
        for lid in ("A2", "A3", "B2", "B3", "B4", "C1", "C2", "C4",
                    "D1", "D2", "D3", "E1", "E2", "E3"):
            self.assertIn(TAXONOMY.resolve(lid), TAXONOMY.column_ids(), lid)

    def test_cross_column_level2_rejected(self):
        for lid in ("A1", "B1", "C3"):
            with self.assertRaises(AmbiguousPath, msg=f"{lid} 应要求下钻"):
                TAXONOMY.resolve(lid)

    def test_unknown_path(self):
        with self.assertRaises(TaxonomyError):
            TAXONOMY.resolve("Z9.9")

    def test_annotation_required_on_4_6(self):
        # 每个叶子一个标签：标签数必须等于叶子数，否则被合并的叶子无法区分
        labels = TAXONOMY.annotation_labels("4.6")
        leaves = TAXONOMY.leaves_of("4.6")
        self.assertEqual(len(labels), len(leaves))
        self.assertEqual(sorted(TAXONOMY.annotation_map("4.6").values()), sorted(leaves))
        self.assertEqual(TAXONOMY.annotation_labels("4.1"), [])

    def test_annotation_label_for_is_inverse_of_map(self):
        amap = TAXONOMY.annotation_map("4.6")
        for label, leaf in amap.items():
            self.assertEqual(TAXONOMY.annotation_label_for(leaf), label)
        self.assertEqual(TAXONOMY.annotation_label_for("A1.1"), "")

    def test_custom_ontology_path(self):
        self.assertEqual(Taxonomy(TAXONOMY.ontology_path).column_of("A1.1"), "3.1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
