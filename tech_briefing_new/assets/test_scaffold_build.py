#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build.py 骨架生成的单测。

骨架只做四类机械劳动（样板、事实转抄、SIG 表、rejected 补齐），判断字段留 TODO。
这里重点守两条：
  - 时刻必须换算到 Asia/Shanghai。字段名叫 first_publish_shanghai，而候选池里
    带的是来源自己的时区；2026-11-02 那份简报的两处时间错误就出在人工转抄。
  - 生成的文件必须是合法 Python，并且带着 TODO 跑会明确失败而不是静默写出残缺事件。
"""
import ast
import json
import tempfile
import unittest
from pathlib import Path

import scaffold_build as sb

_WINDOW = {"window_start": "2026-11-05T00:00:00+08:00",
           "window_end": "2026-11-06T09:44:48+08:00",
           "run_date": "2026-11-05", "tz": "Asia/Shanghai"}


class ToShanghaiTest(unittest.TestCase):
    def test_utc_converted(self):
        iso, note = sb._to_shanghai("2026-11-05T07:44:30+00:00")
        self.assertEqual(iso, "2026-11-05T15:44:30+08:00")
        self.assertIn("候选池原值", note)

    def test_negative_offset_converted(self):
        iso, _ = sb._to_shanghai("2026-11-05T00:00:00-05:00")
        self.assertEqual(iso, "2026-11-05T13:00:00+08:00")

    def test_already_shanghai_is_not_shifted_again(self):
        """回归：对一个已经是 +08:00 的值再按 +08 换一次，正是那两处事实错误的成因。"""
        iso, _ = sb._to_shanghai("2026-11-03T01:51:00+08:00")
        self.assertEqual(iso, "2026-11-03T01:51:00+08:00")

    def test_z_suffix_accepted(self):
        iso, _ = sb._to_shanghai("2026-11-05T07:44:30Z")
        self.assertEqual(iso, "2026-11-05T15:44:30+08:00")

    def test_naive_timestamp_left_as_todo(self):
        iso, note = sb._to_shanghai("2026-11-05T07:44:30")
        self.assertEqual(iso, "")
        self.assertIn("TODO", note)

    def test_unparseable_left_as_todo(self):
        iso, note = sb._to_shanghai("昨天下午")
        self.assertEqual(iso, "")
        self.assertIn("TODO", note)

    def test_missing_left_as_todo(self):
        self.assertEqual(sb._to_shanghai("")[0], "")
        self.assertIn("TODO", sb._to_shanghai("")[1])


class PicksTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.f = Path(self._tmp.name) / "picks.txt"

    def test_comments_and_blanks_ignored(self):
        self.f.write_text("# 注释\n\nEV-01 https://a.example/x   # 行内注释\n",
                          encoding="utf-8")
        self.assertEqual(sb.read_picks(self.f), [("EV-01", "https://a.example/x")])

    def test_duplicate_ev_id_rejected(self):
        self.f.write_text("EV-01 https://a/x\nEV-01 https://a/y\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            sb.read_picks(self.f)

    def test_single_column_rejected(self):
        self.f.write_text("EV-01\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            sb.read_picks(self.f)

    def test_empty_file_rejected(self):
        self.f.write_text("# 全是注释\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            sb.read_picks(self.f)


class ScaffoldTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.raw = self.root / "raw_2026-11-06"
        self.raw.mkdir()
        (self.raw / "window.json").write_text(json.dumps(_WINDOW), encoding="utf-8")
        self._pool = [{"uid": "u1", "url": "https://arxiv.org/abs/2611.05866",
                       "title": "Auditable Unlearning", "channel": "B_arxiv",
                       "src": "arxiv_cs_AI", "published": "2026-11-05T00:00:00-05:00"}]
        sb.build_pool.build = lambda d: (list(self._pool), [])
        self.addCleanup(lambda: None)

    def _gen(self, picks, state=None):
        return sb.build_scaffold(self.raw, picks, [], state)

    def test_output_is_valid_python(self):
        ast.parse(self._gen([("EV-01", "u1")]))

    def test_window_json_found_in_parent_dir(self):
        """window.json 可能在运行根目录而不是 raw_<date>/ 下。"""
        (self.raw / "window.json").unlink()
        (self.root / "window.json").write_text(json.dumps(_WINDOW), encoding="utf-8")
        self.assertIn("2026-11-05", self._gen([("EV-01", "u1")]))

    def test_facts_are_prefilled_and_converted(self):
        out = self._gen([("EV-01", "u1")])
        self.assertIn('source="https://arxiv.org/abs/2611.05866"', out)
        self.assertIn('first_publish_shanghai="2026-11-05T13:00:00+08:00"', out)
        self.assertIn('evidence_form="paper"', out)

    def test_pick_by_url_as_well_as_uid(self):
        out = self._gen([("EV-01", "https://arxiv.org/abs/2611.05866v2")])
        self.assertIn('first_publish_shanghai="2026-11-05T13:00:00+08:00"', out)

    def test_unknown_pick_still_produces_a_stub(self):
        out = self._gen([("EV-09", "https://nowhere.example/x")])
        self.assertIn('EV["EV-09"]', out)
        self.assertIn('source="https://nowhere.example/x"', out)

    def test_judgment_fields_are_todo_not_guessed(self):
        out = self._gen([("EV-01", "u1")])
        for field in ("primary_path", "change_object", "signal"):
            self.assertIn(f'{field}="TODO"' if field != "primary_path"
                          else 'primary_path="TODO 叶子编号"', out)

    def test_closed_sets_listed_in_header(self):
        out = self._gen([("EV-01", "u1")])
        self.assertIn("交互·应用", out)
        self.assertIn("CT-07 信任/权限模型变化", out)

    def test_sig_table_is_generated_not_transcribed(self):
        import root_tech as rt
        root = next(r for r in rt.load()["roots"] if r.get("switch_signal"))
        self.assertIn(json.dumps(root["switch_signal"], ensure_ascii=False),
                      self._gen([("EV-01", "u1")]))

    def test_seen_source_gets_increment_hint(self):
        class FakeReg:
            def seen(self, urls):
                return {"u1": {"kind": "event", "event_key": "abc123",
                               "first_seen": "2026-11-03", "runs": ["2026-11-03"],
                               "labels": {"2026-11-03": "EV-08"}, "title": "旧事件"}}
        # 用真实路径但把 Registry 换掉
        orig = sb.build_scaffold
        import thesis_registry
        real = thesis_registry.Registry
        thesis_registry.Registry = lambda state: FakeReg()
        self.addCleanup(lambda: setattr(thesis_registry, "Registry", real))
        out = orig(self.raw, [("EV-01", "u1")], [], self.root)
        self.assertIn("这个来源以前见过", out)
        self.assertIn('"event_key": "abc123"', out)
        self.assertIn("increment_of", out)

    def test_snapshot_declarations_are_named_after_the_file(self):
        """常量名按文件名生成。`SNAP_1`、`SNAP_7` 这种序号名在写 claim 时没法读，
        而 E(SNAP_x, "原文") 正是人要逐条对着快照核的地方。"""
        f = self.root / "itnews_dont_ask_again.txt"
        f.write_text("x", encoding="utf-8")
        out = sb.build_scaffold(self.raw, [("EV-01", "u1")], [str(f)], None)
        self.assertIn("SNAP_ITNEWS_DONT_ASK_AGAIN_TXT = ", out)
        self.assertNotIn("SNAP_1 = ", out)
        self.assertIn("ce.sha256_file", out)

    def test_duplicate_basenames_get_distinct_names(self):
        a = self.root / "a"; b = self.root / "b"
        a.mkdir(); b.mkdir()
        (a / "snap.html").write_text("x", encoding="utf-8")
        (b / "snap.html").write_text("y", encoding="utf-8")
        out = sb.build_scaffold(self.raw, [("EV-01", "u1")],
                                [str(a / "snap.html"), str(b / "snap.html")], None)
        self.assertIn("SNAP_SNAP_HTML = ", out)
        self.assertIn("SNAP_SNAP_HTML_2 = ", out)

    def test_no_snapshots_gives_empty_sha_map(self):
        self.assertIn("SHA = {}", self._gen([("EV-01", "u1")]))


class RejectedBlocksTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ev = Path(self._tmp.name) / "events_run_2026-11-05"
        self.ev.mkdir()

    def _write(self, eid, action="new", cands=(), rejected=()):
        d = {"thesis_decision": {"action": action,
                                 "rejected": [{"id": t, "reason": "已说明"} for t in rejected]},
             "thesis_candidates": [{"id": t} for t in cands]}
        (self.ev / f"{eid}.json").write_text(json.dumps(d, ensure_ascii=False),
                                             encoding="utf-8")

    def test_lists_only_the_missing_ones(self):
        self._write("EV-01", cands=("TH-0001", "TH-0002"), rejected=("TH-0001",))
        out = sb.rejected_blocks(self.ev, None)
        self.assertIn("TH-0002", out)
        self.assertNotIn('"id": "TH-0001"', out)

    def test_output_is_valid_python_when_pasted(self):
        self._write("EV-01", cands=("TH-0001",))
        body = sb.rejected_blocks(self.ev, None)
        ast.parse('EV = {"EV-01": {"thesis_decision": {"rejected": []}}}\n' + body)

    def test_attach_decisions_need_no_rejected(self):
        self._write("EV-01", action="attach", cands=("TH-0001",))
        self.assertIn("没有缺失", sb.rejected_blocks(self.ev, None))

    def test_blank_reason_counts_as_missing(self):
        d = {"thesis_decision": {"action": "new",
                                 "rejected": [{"id": "TH-0001", "reason": "   "}]},
             "thesis_candidates": [{"id": "TH-0001"}]}
        (self.ev / "EV-01.json").write_text(json.dumps(d), encoding="utf-8")
        self.assertIn("TH-0001", sb.rejected_blocks(self.ev, None))


if __name__ == "__main__":
    unittest.main(verbosity=2)
