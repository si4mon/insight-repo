#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Taxonomy · 技术分类映射 API

单一事实源：54 个三级叶子（data/四层技术地图.txt） → 11 个阅读栏目 → 8 章。
定义在 thesis_ontology.json 的 "taxonomy" 段，本模块只做查询与校验，
不改写数据。成稿提示词、gate 校验、thesis_registry 共用同一套映射。

**为什么要有这一层**：此前栏目写死在 SKILL.md 和 verify_gates.py 里，
叶子和栏目之间没有机器可读的对应关系，改分类必然漏改一处。

三种查询：
  leaf      — 叶子 → 栏目（事件归档身份）
  column    — 栏目 → 叶子（当天正文分节）
  resolve   — 主技术路径（可能停在二级）→ 栏目，按"可停二级"规则判定

用法：
  # CLI
  python taxonomy.py leaves
  python taxonomy.py columns
  python taxonomy.py chapter 4
  python taxonomy.py leaf A1.1
  python taxonomy.py resolve A1
  python taxonomy.py validate

  # 作为模块
  from taxonomy import TAXONOMY
  TAXONOMY.column_of("B1.1")        # "3.2"
  TAXONOMY.leaves_of("4.6")         # ["D1.1", ...]
  TAXONOMY.resolve("A1")            # 抛 AmbiguousPath：A1 跨 3.1/3.3/3.4
  TAXONOMY.anchor("3.2")            # "s3-2"

退出码：0 正常；1 validate 有 FAIL
"""
import argparse
import json
import sys
from pathlib import Path

ASSETS_DIR = Path(__file__).parent
ONTOLOGY_PATH = ASSETS_DIR / "thesis_ontology.json"

# 可以停在二级的域：当且仅当该二级域的全部叶子落在同一栏目。
# A1（3.1/3.3/3.4）、C3（4.3/4.4）跨栏目，必须下钻到三级。
# 名单以 ontology 的 taxonomy.rules.must_drill_level2 为准，此处只做默认值。


class TaxonomyError(Exception):
    """叶子/栏目/章节不存在。"""


class AmbiguousPath(TaxonomyError):
    """停在二级，但该二级域跨多个栏目，必须下钻。"""


class Taxonomy:
    def __init__(self, ontology_path: Path = ONTOLOGY_PATH):
        self.ontology_path = ontology_path
        raw = json.loads(ontology_path.read_text(encoding="utf-8"))
        data = raw.get("taxonomy")
        if not data:
            raise TaxonomyError(f"{ontology_path} 缺少 taxonomy 段")
        self.data = data
        self._must_drill = tuple(data.get("rules", {}).get("must_drill_level2", []))
        self._leaves = {x["id"]: x for x in data["leaves"]}
        self._columns = {x["id"]: x for x in data["columns"]}
        self._chapters = {x["chapter"]: x for x in data["chapters"]}
        self._level2 = {}
        for dom in data["domains"]:
            for l2 in dom["level2"]:
                self._level2[l2["id"]] = {"level1": dom["id"], **l2}

    # ---------- leaf ----------
    def leaf(self, leaf_id: str) -> dict:
        try:
            return self._leaves[leaf_id]
        except KeyError:
            raise TaxonomyError(f"未知叶子: {leaf_id}")

    def leaf_ids(self) -> list[str]:
        return list(self._leaves)

    def column_of(self, leaf_id: str) -> str:
        return self.leaf(leaf_id)["column"]

    # ---------- column ----------
    def column(self, column_id: str) -> dict:
        try:
            return self._columns[column_id]
        except KeyError:
            raise TaxonomyError(f"未知栏目: {column_id}")

    def column_ids(self) -> list[str]:
        return list(self._columns)

    def leaves_of(self, column_id: str) -> list[str]:
        return list(self.column(column_id)["leaves"])

    def columns_of_chapter(self, chapter: int) -> list[dict]:
        return [c for c in self.data["columns"] if c["chapter"] == chapter]

    def column_ids_of_chapter(self, chapter: int) -> list[str]:
        return [c["id"] for c in self.columns_of_chapter(chapter)]

    def annotation_labels(self, column_id: str) -> list[str]:
        """聚合栏目要求卡片标注的细分技术域；普通栏目返回空列表。"""
        return list(self.column(column_id).get("annotation_labels", []))

    def annotation_map(self, column_id: str) -> dict[str, str]:
        """标注标签 → 叶子。用于校验标签覆盖了栏目的全部叶子。"""
        return dict(self.column(column_id).get("annotation_map", {}))

    def annotation_label_for(self, leaf_id: str) -> str:
        """
        叶子 → 该叶子唯一允许的标注标签（普通栏目返回空串）。

        方向与 annotation_map 相反。必须提供这个方向：卡片校验拿到的是
        叶子，若在 map 上直接取叶子会恒为 None，校验会静默通过。
        """
        column = self.column_of(leaf_id)
        for label, leaf in self.annotation_map(column).items():
            if leaf == leaf_id:
                return label
        return ""

    # ---------- chapter ----------
    def chapter(self, n: int) -> dict:
        try:
            return self._chapters[n]
        except KeyError:
            raise TaxonomyError(f"未知章节: {n}")

    def chapters(self) -> list[dict]:
        return sorted(self.data["chapters"], key=lambda x: x["chapter"])

    def section_id(self, n: int) -> str:
        """章号 → HTML section id（s1..s8）。"""
        return self.chapter(n)["section_id"]

    def anchor(self, column_id: str) -> str:
        """栏目号 → HTML 锚点 id（3.2 → s3-2，4.6 → s4-6）。"""
        chapter, num = self.column(column_id)["id"].split(".")
        return f"s{chapter}-{num}"

    # ---------- resolve ----------
    def resolve(self, path: str) -> str:
        """
        主技术路径 → 栏目。path 可以是三级叶子，也可以是二级域。

        规则（设计文档 §4.2）：
          - 三级叶子直接映射；
          - 二级域只在"全部叶子落在同一栏目"时可停；
          - A1 / C3 必须下钻到三级。
        """
        if path in self._leaves:
            return self._leaves[path]["column"]
        if path in self._level2:
            if path in self._must_drill:
                raise AmbiguousPath(f"{path} 跨多个栏目，必须下钻到三级叶子")
            cols = {self._leaves[x]["column"] for x in self._leaves_by_level2(path)}
            if len(cols) == 1:
                return cols.pop()
            raise AmbiguousPath(f"{path} 跨多个栏目 {sorted(cols)}，必须下钻到三级叶子")
        raise TaxonomyError(f"未知技术路径: {path}")

    def _leaves_by_level2(self, level2: str) -> list[str]:
        return [lid for lid, x in self._leaves.items() if x["level2"] == level2]

    # ---------- misc ----------
    def change_objects(self) -> list[str]:
        return list(self.data["change_objects"])

    def rules(self) -> dict:
        return dict(self.data["rules"])

    # ---------- validate ----------
    def validate(self) -> list[dict]:
        """返回 [{name, ok, detail}]，供 gate 与单测直接消费。"""
        out = []

        def add(name, ok, detail=""):
            out.append({"name": name, "ok": bool(ok), "detail": detail})

        leaves, columns, chapters = self.data["leaves"], self.data["columns"], self.data["chapters"]

        ids = [x["id"] for x in leaves]
        dup = sorted({i for i in ids if ids.count(i) > 1})
        add("叶子数 = 54", len(leaves) == 54, f"actual={len(leaves)}")
        add("叶子 id 无重复", not dup, f"dup={dup}")

        cids = [x["id"] for x in columns]
        cdup = sorted({i for i in cids if cids.count(i) > 1})
        add("栏目数 = 11", len(columns) == 11, f"actual={len(columns)}")
        add("栏目 id 无重复", not cdup, f"dup={cdup}")

        unknown = [x["id"] for x in leaves if x.get("column") not in self._columns]
        add("每个叶子指向存在的栏目", not unknown, f"bad={unknown}")

        # 双向一致：栏目列出的叶子 == 叶子自己声明的栏目
        mismatched = []
        for c in columns:
            for lid in c["leaves"]:
                if lid not in self._leaves:
                    mismatched.append(f"{c['id']}→未知叶子 {lid}")
                elif self._leaves[lid]["column"] != c["id"]:
                    mismatched.append(f"{c['id']} 列了 {lid}，但叶子声明 {self._leaves[lid]['column']}")
        for l in leaves:
            if l["id"] not in self._columns.get(l["column"], {}).get("leaves", []):
                mismatched.append(f"叶子 {l['id']} 未出现在栏目 {l['column']} 的列表里")
        add("叶子↔栏目双向一致", not mismatched, f"{len(mismatched)} 处: {mismatched[:5]}")

        multi = [lid for lid in ids if sum(1 for c in columns if lid in c["leaves"]) > 1]
        add("每个叶子只属一个栏目", not multi, f"multi={multi}")

        add("章 3 栏目数 = 4", len(self.columns_of_chapter(3)) == 4,
            f"actual={len(self.columns_of_chapter(3))}")
        add("章 4 栏目数 = 7", len(self.columns_of_chapter(4)) == 7,
            f"actual={len(self.columns_of_chapter(4))}")
        cap = [c["id"] for c in columns if c["chapter"] not in (3, 4)]
        add("栏目只挂章 3/章 4", not cap, f"bad={cap}")

        ch_nums = sorted(x["chapter"] for x in chapters)
        add("章号 1–8 连续", ch_nums == list(range(1, 9)), f"actual={ch_nums}")
        sec_ids = [x["section_id"] for x in chapters]
        add("section id = s1..s8", sec_ids == [f"s{i}" for i in range(1, 9)], f"actual={sec_ids}")

        bad_l1 = [x["id"] for x in leaves if x["level1"] not in {d["id"] for d in self.data["domains"]}]
        add("叶子 level1 均存在", not bad_l1, f"bad={bad_l1}")
        bad_l2 = [x["id"] for x in leaves if x["level2"] not in self._level2]
        add("叶子 level2 均存在", not bad_l2, f"bad={bad_l2}")
        unused_l2 = [k for k in self._level2 if not self._leaves_by_level2(k)]
        add("每个二级域至少有一个叶子", not unused_l2, f"unused={unused_l2}")

        # 可停二级规则：跨栏目的二级域必须拒绝解析，单栏目的必须解析成功
        wrong = []
        for l2 in self._level2:
            spans = {self._leaves[x]["column"] for x in self._leaves_by_level2(l2)}
            try:
                got = self.resolve(l2)
            except AmbiguousPath:
                if len(spans) == 1:
                    wrong.append(f"{l2} 单栏目 {spans} 却拒绝解析")
            else:
                if len(spans) > 1:
                    wrong.append(f"{l2} 跨栏目 {sorted(spans)} 却停在了二级")
        add("可停二级规则一致", not wrong, f"{wrong}")

        # must_drill 是冗余声明，必须与"叶子实际跨栏目"推导出的集合一致，
        # 否则漏配会被 resolve() 的跨栏目兜底掩盖，规则声明与实际行为脱节。
        cross = sorted(l2 for l2 in self._level2
                       if len({self._leaves[x]["column"] for x in self._leaves_by_level2(l2)}) > 1)
        add("must_drill_level2 与跨栏目集合一致",
            sorted(self._must_drill) == cross,
            f"declared={sorted(self._must_drill)} derived={cross}")

        add("变更对象非空", bool(self.data.get("change_objects")), "")
        add("每个叶子有名称", all(x.get("name") for x in leaves), "")

        # 聚合栏目的标注标签必须恰好覆盖其全部叶子：
        # 少一个 → 那个叶子的事件无法合规标注（D1.3 曾因此无法归位）；
        # 多一个 → 标签指向不存在的叶子。
        for c in columns:
            labels = c.get("annotation_labels")
            if not labels:
                continue
            amap = c.get("annotation_map", {})
            covered = set(amap.values())
            want = set(c["leaves"])
            add(f"{c['id']} 标注标签覆盖全部叶子", covered == want,
                f"未覆盖={sorted(want - covered)} 多出={sorted(covered - want)}")
            bad = [k for k in amap if k not in labels]
            add(f"{c['id']} annotation_map 的键都在标签表内", not bad, f"bad={bad}")

        return out


TAXONOMY = Taxonomy()


# ---------- CLI ----------
def _dump(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser(description="Technology taxonomy lookup")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("leaves", help="列出全部叶子")
    sub.add_parser("columns", help="列出全部栏目")

    c = sub.add_parser("chapter", help="列出某章及其栏目")
    c.add_argument("n", type=int)

    lf = sub.add_parser("leaf", help="查一个叶子")
    lf.add_argument("path")

    r = sub.add_parser("resolve", help="主技术路径 → 栏目")
    r.add_argument("path")

    sub.add_parser("validate", help="校验 54 叶子 / 11 栏目完整性")

    args = p.parse_args()

    try:
        if args.cmd == "leaves":
            _dump(TAXONOMY.data["leaves"])
        elif args.cmd == "columns":
            _dump(TAXONOMY.data["columns"])
        elif args.cmd == "chapter":
            ch = TAXONOMY.chapter(args.n)
            _dump({**ch, "columns": TAXONOMY.columns_of_chapter(args.n)})
        elif args.cmd == "leaf":
            _dump({**TAXONOMY.leaf(args.path),
                   "column_name": TAXONOMY.column(TAXONOMY.column_of(args.path))["name"]})
        elif args.cmd == "resolve":
            col = TAXONOMY.resolve(args.path)
            _dump({"path": args.path, "column": col,
                   "column_name": TAXONOMY.column(col)["name"],
                   "anchor": TAXONOMY.anchor(col)})
        elif args.cmd == "validate":
            results = TAXONOMY.validate()
            for x in results:
                print(f"{'PASS' if x['ok'] else 'FAIL'}  {x['name']}"
                      + (f"  — {x['detail']}" if x["detail"] and not x["ok"] else ""))
            nf = sum(1 for x in results if not x["ok"])
            print(f"\n{len(results) - nf} pass / {nf} fail")
            return 1 if nf else 0
    except TaxonomyError as e:
        print(f"[taxonomy] {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
