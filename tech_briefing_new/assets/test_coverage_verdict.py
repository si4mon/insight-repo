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
from pathlib import Path

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
        self.gt.tag_details = lambda *a, **k: {}
        r = self.gt.collect("x/y")
        self.assertEqual(r["status"], "parse_failed")
        self.assertEqual([i["date_precision"] for i in r["items"]], ["none", "none"])

    def test_items_carry_second_precision_when_timed(self):
        self.gt.list_tags = lambda *a, **k: (["v1"], "")
        self.gt.tag_details = lambda *a, **k: {
            "v1": {"time": "2026-11-01T20:51:31+00:00",
                   "notes": "* **api:** add a model option",
                   "notes_source": "CHANGELOG.md diff v0..v1"}}
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


class GitReleaseNotesTest(unittest.TestCase):
    """git 通道必须带回"改了什么"的可引证原文。

    原先只有 tag 名与提交时刻：git_tags 的文档说第 3 步"由采集器按
    git_fallback.changelog 顺带落盘"，但采集器里从来没有这段实现。于是该通道
    产出的事件连续三轮卡在 B 级——A / A+ 要求每条 claim 绑定到快照里的原文
    片段（task_def 15.1），而原文从未落盘。openai-python / openai-node 同分钟
    配对发布跨两个窗口出现，只能描述成"节奏"，就是这个缺口的直接后果。
    """

    def setUp(self):
        import git_tags
        self.gt = git_tags
        self.gt.list_tags = lambda *a, **k: (["v2", "v1"], "")
        self.gt.tag_details = lambda *a, **k: {
            "v2": {"time": "2026-11-05T17:58:18+00:00",
                   "notes": "* **api:** add a model option for Responses",
                   "notes_source": "CHANGELOG.md diff v1..v2"},
            "v1": {"time": "2026-11-04T02:16:58+00:00",
                   "notes": "", "notes_source": ""}}

    def test_items_carry_release_notes(self):
        it = self.gt.collect("openai/openai-python")["items"][0]
        self.assertIn("add a model option", it["release_notes"])
        self.assertEqual(it["release_notes_source"], "CHANGELOG.md diff v1..v2")

    def test_notes_reach_the_snippet_not_only_the_snapshot(self):
        """打分与选题读 snippet；原文只进快照等于不给下游看。"""
        it = self.gt.collect("openai/openai-python")["items"][0]
        self.assertIn("add a model option", it["snippet"])

    def test_snapshot_contains_quotable_text_and_provenance(self):
        res = self.gt.collect("openai/openai-python")
        snap = res["notes_snapshot"]
        self.assertIn("* **api:** add a model option for Responses", snap)
        self.assertIn("CHANGELOG.md diff v1..v2", snap)
        self.assertEqual(res["notes_count"], 1)

    def test_tag_without_notes_is_marked_not_faked(self):
        snap = self.gt.collect("openai/openai-python")["notes_snapshot"]
        self.assertIn("（未取到发布说明）", snap)

    def test_snapshot_present_even_when_times_missing(self):
        """取不到时刻仍判 parse_failed，但已拿到的发布说明不该一起丢掉。"""
        self.gt.tag_details = lambda *a, **k: {}
        res = self.gt.collect("openai/openai-python")
        self.assertEqual(res["status"], "parse_failed")
        self.assertIn("notes_snapshot", res)

    def test_collector_writes_the_snapshot_file(self):
        """回归：缺的那一步是采集器里的写文件，所以必须走真实的 collect_one。

        让 atom / API 两条通道全部传输失败（线上是 403），逼出 git 回退，
        然后断言快照文件真的落在 raw 目录里、内容可引用、记录里指得到它。
        """
        import tempfile
        import collect_sources as cs
        orig_fetch = cs.fetch
        cs.fetch = lambda *a, **k: ("http_error", b"", "HTTP 403")
        self.addCleanup(lambda: setattr(cs, "fetch", orig_fetch))

        out = Path(tempfile.mkdtemp())
        src = {"id": "gh_openai_openai-python", "entity": "OpenAI",
               "surface": "code", "layer": "sdk-release", "channel": "G_official_surface",
               "mode": "atom", "critical": False,
               "urls": [("https://github.com/openai/openai-python/releases.atom",
                         "gh_openai_openai-python.atom")],
               "git_fallback": {"repo": "openai/openai-python",
                                "file": "gh_openai_openai-python_tags.json"}}
        rec = cs.collect_one(None, src, out, "2026-11-05T00:00:00+08:00",
                             "2026-11-06T12:00:00+08:00")

        snap = out / "gh_openai_openai-python_tags_changelog.md"
        self.assertTrue(snap.exists(), f"快照未落盘；目录内容 {sorted(p.name for p in out.iterdir())}")
        self.assertIn("add a model option", snap.read_text(encoding="utf-8"))
        self.assertEqual(rec["changelog_file"], snap.name)
        self.assertIn("发布说明已落盘", rec["note"])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class GzipSniffTest(unittest.TestCase):
    """响应是 gzip 但头没了，也要能解开。

    deepmind.google/blog/rss.xml 返回 gzip 字节，而 content-encoding 头在出网
    代理那里被改掉了。我们把 gzip 字节当文本存下来，classify 看到二进制就判
    PARSE_FAILED「内容形态与声明模式不符」。压不压由代理当时的协商决定，所以
    它表现得像偶发故障（11-01 失败、11-02 正常、11-04 又失败），前两次都被记成
    传输层偶发。失败的那几轮 Google DeepMind 的 blog 面实际是失明的。
    """

    def test_gzip_body_is_decompressed(self):
        import gzip
        import collect_sources
        raw = b'<?xml version="1.0"?><rss version="2.0"><channel/></rss>'
        self.assertEqual(collect_sources._maybe_decompress(gzip.compress(raw)), raw)

    def test_plain_body_untouched(self):
        import collect_sources
        raw = b'<?xml version="1.0"?><rss/>'
        self.assertEqual(collect_sources._maybe_decompress(raw), raw)

    def test_bad_gzip_magic_returns_input(self):
        import collect_sources
        raw = b"\x1f\x8b not actually gzip"
        self.assertEqual(collect_sources._maybe_decompress(raw), raw)


class GitTagTimezoneTest(unittest.TestCase):
    """git 的 %cI 带提交者本地时区，原始文件必须统一成 UTC。

    同一次采集里 anthropic 的 tag 回来是 +00:00、QwenLM 的回来是 +08:00。
    原始文件混着两种偏移，读的人很容易再按 +08 换一次——2026-11-02 那份简报
    就把 qwen-code v0.26.6 的 11-03 01:51 写成了 09:51，nightly 那条同样差 8 小时。
    """

    def test_local_offset_normalized(self):
        import git_tags
        self.assertEqual(git_tags._to_utc("2026-11-03T01:51:25+08:00"),
                         "2026-11-02T17:51:25+00:00")

    def test_utc_unchanged(self):
        import git_tags
        self.assertEqual(git_tags._to_utc("2026-11-03T01:25:28+00:00"),
                         "2026-11-03T01:25:28+00:00")

    def test_garbage_passes_through(self):
        import git_tags
        self.assertEqual(git_tags._to_utc("garbage"), "garbage")

    def test_all_offsets_identical_after_normalizing(self):
        import git_tags
        raw = ["2026-11-03T01:51:25+08:00", "2026-11-03T01:25:28+00:00",
               "2026-11-02T19:02:13-05:00"]
        offs = {git_tags._to_utc(x)[-6:] for x in raw}
        self.assertEqual(offs, {"+00:00"})


class ArchiveFallbackOnTruncationTest(unittest.TestCase):
    """窗口跨了两个公告批次时，归档回退也要触发。

    arXiv 的 RSS 只带最近一个公告批次。2026-11-04 一轮的窗口跨了 11-03 13:00
    与 11-04 13:00 两批，11-03 那一整批（数百篇）一条都没进池子：window_partial
    缺口把它报了出来，但旧条件只在"主通道 0 条"时读归档页，所以补偿从未发生。
    阈值用「够装下一整个批次」，避免 feed 只回溯几小时这种常态截断反复多抓。
    """

    WS = "2026-11-03T00:00:00+08:00"

    def _res(self, *iso):
        return {"status": "ok", "items": [{"published": t} for t in iso]}

    def test_missing_whole_batch_triggers(self):
        import collect_sources
        self.assertTrue(collect_sources._truncated_before_window(
            self._res("2026-11-04T05:00:00+00:00"), self.WS))

    def test_few_hours_late_does_not_trigger(self):
        import collect_sources
        self.assertFalse(collect_sources._truncated_before_window(
            self._res("2026-11-02T20:00:00+00:00"), self.WS))

    def test_source_spanning_window_does_not_trigger(self):
        import collect_sources
        self.assertFalse(collect_sources._truncated_before_window(
            self._res("2026-11-02T17:00:00+00:00", "2026-11-04T05:00:00+00:00"), self.WS))

    def test_undated_items_do_not_trigger(self):
        import collect_sources
        self.assertFalse(collect_sources._truncated_before_window(
            {"status": "ok", "items": [{}, {"published": ""}]}, self.WS))

    def test_non_ok_status_does_not_trigger(self):
        import collect_sources
        self.assertFalse(collect_sources._truncated_before_window(
            {"status": "empty", "items": []}, self.WS))

    def test_custom_threshold_respected(self):
        import collect_sources
        res = self._res("2026-11-03T06:00:00+08:00")      # 窗口起点后 6 小时
        self.assertFalse(collect_sources._truncated_before_window(res, self.WS, 12.0))
        self.assertTrue(collect_sources._truncated_before_window(res, self.WS, 3.0))


class ArchiveMergeTest(unittest.TestCase):
    """归档回退要与主通道合并，不能顶掉。

    归档页不带摘要，主通道的 RSS 带。直接替换会让当天那一批论文失去摘要，
    必审清单打分只剩标题可用——2026-11-04 一轮归档补回 1528 篇，同时把 684 篇
    当天论文的摘要弄丢了，T6 层的排序因此被标题关键词密度主导。
    """

    def test_merge_prefers_main_channel_copy(self):
        archive = {"status": "ok", "items": [
            {"uid": "a", "title": "A", "snippet": "arXiv 公告批次 2026-11-03"},
            {"uid": "b", "title": "B", "snippet": "arXiv 公告批次 2026-11-04"}]}
        main = {"status": "ok", "items": [
            {"uid": "b", "title": "B", "snippet": "Abstract: the real abstract"}]}
        by_uid = {it["uid"]: it for it in archive["items"]}
        by_uid.update({it["uid"]: it for it in main["items"]})
        merged = list(by_uid.values())
        self.assertEqual(len(merged), 2)
        got = {it["uid"]: it["snippet"] for it in merged}
        self.assertIn("real abstract", got["b"])
        self.assertIn("公告批次", got["a"])


class BatchNotYetDueTest(unittest.TestCase):
    """当天批次还没公告，不算缺。

    arXiv 每个工作日在固定时刻公告一批（归一到上海约 12:00），而窗口终点是任务
    开始时刻。2026-11-05 窗口于上海 09:44 执行，五个 arXiv 源都被报成 partial，
    凭空生出五条无事可做的补检任务——缺的那天正是执行当天，批次还没发。
    """

    def _rec(self, dates):
        return {"daily_batch": True, "batch_dates": list(dates)}

    def _q(self, dates, earliest, start, end):
        from datetime import datetime
        import coverage
        return coverage._batch_coverage(
            self._rec(dates), datetime.fromisoformat(start),
            datetime.fromisoformat(end), earliest)

    def test_today_batch_not_yet_announced_is_full(self):
        q = self._q(["2026-11-05", "2026-11-04"], "2026-11-04T12:00:00+08:00",
                    "2026-11-05T00:00:00+08:00", "2026-11-06T09:44:00+08:00")
        self.assertEqual(q["covered_quality"], "full", q)

    def test_today_batch_overdue_is_partial(self):
        q = self._q(["2026-11-05", "2026-11-04"], "2026-11-04T12:00:00+08:00",
                    "2026-11-05T00:00:00+08:00", "2026-11-06T18:00:00+08:00")
        self.assertEqual(q["covered_quality"], "partial", q)
        self.assertEqual(q["missing_batch_days"], ["2026-11-06"])

    def test_missing_earlier_weekday_still_partial(self):
        q = self._q(["2026-11-05"], "2026-11-05T12:00:00+08:00",
                    "2026-11-04T00:00:00+08:00", "2026-11-06T09:44:00+08:00")
        self.assertEqual(q["covered_quality"], "partial", q)
        self.assertEqual(q["missing_batch_days"], ["2026-11-04"])

    def test_weekend_never_required(self):
        q = self._q(["2026-11-06"], "2026-11-06T12:00:00+08:00",
                    "2026-11-07T00:00:00+08:00", "2026-11-08T20:00:00+08:00")
        self.assertEqual(q["covered_quality"], "full", q)
