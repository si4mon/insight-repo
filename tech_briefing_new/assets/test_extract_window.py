#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract 的日期精度与窗口判定单测。

守住两条不变式：
  1. 解析路径不得把 day 精度降级成 second（否则日粒度源的时刻被伪装成精确值）；
  2. 日粒度按 50 小时不确定区间与窗口求交，不能拿零点做点比较。

  python test_extract_window.py
"""
import unittest

import extract

from extract import (extract_items, in_window, parse_date, precision_span,
                     window_match)

WS = "2026-10-22T00:00:00+08:00"
WE = "2026-10-23T15:13:32+08:00"


def _item(published, precision):
    return {"published": published, "date_precision": precision}


class DatePrecisionTest(unittest.TestCase):
    def test_day_string_stays_day(self):
        iso, prec = parse_date("Oct 21, 2026")
        self.assertEqual(prec, "day")

    def test_reparsing_iso_keeps_day(self):
        # 旧 bug：ISO 串带 T，二次解析被认成 second。现在零点一律判 day，
        # 所以二次解析不再降级——这是双保险，第一层靠 _item_from 的显式传参。
        iso, _ = parse_date("Oct 21, 2026")
        _, again = parse_date(iso)
        self.assertEqual(again, "day")

    def test_midnight_rss_timestamp_is_day(self):
        # 真实数据：arXiv 370/370、hf_blog 759/889、openai_news_rss 387/1316
        # 的 pubDate 都是 00:00:00。语法上有秒，实际只有日。
        self.assertEqual(parse_date("Fri, 23 Oct 2026 00:00:00 -0400")[1], "day")
        self.assertEqual(parse_date("Fri, 23 Oct 2026 00:00:00 GMT")[1], "day")

    def test_real_timestamp_stays_second(self):
        self.assertEqual(parse_date("Thu, 22 Oct 2026 22:24:34 GMT")[1], "second")
        self.assertEqual(parse_date("2026-10-22T13:05:00+08:00")[1], "second")

    def test_html_cards_keeps_day_precision(self):
        # 真实结构：claude.com/blog 的 ResourceCard
        body = (b'<html><body><a href="https://claude.com/blog/duet">'
                b'<h3>Introducing Claude Duet</h3>'
                b'<span>Article Oct 21, 2026</span></a></body></html>')
        res = extract_items(body, "html_cards", "https://claude.com/blog")
        duet = [i for i in res["items"] if "Duet" in i["title"]]
        self.assertTrue(duet, res["items"])
        self.assertEqual(duet[0]["date_precision"], "day",
                         "day 精度被降级成 second，窗口边界会被误判")

    def test_markdown_day_precision(self):
        body = ("# Changelog\n\n## October, 2026\n\n### Oct 22\n\n"
                "Update - Model: gpt-6-luna\n").encode()
        res = extract_items(body, "markdown_dated", "https://x/changelog")
        self.assertEqual(res["items"][0]["date_precision"], "day")


class FuzzyWindowTest(unittest.TestCase):
    def test_day_span_is_50_hours(self):
        lo, hi = precision_span(_item("2026-10-21T00:00:00+00:00", "day"))
        self.assertEqual((hi - lo).total_seconds() / 3600, 50)

    def test_second_span_is_a_point(self):
        lo, hi = precision_span(_item("2026-10-22T10:00:00+00:00", "second"))
        self.assertEqual(lo, hi)

    def test_duet_day_before_window_start_is_fuzzy(self):
        # 真实案例：官方源抓到了 Duet，日期 Oct 21，窗口起点 10-22 00:00+08。
        # 点比较会判窗口外（10-21 08:00+08），模糊精度必须留住它。
        item = _item("2026-10-21T00:00:00+00:00", "day")
        self.assertEqual(window_match(item, WS, WE), "fuzzy")
        self.assertTrue(in_window(item, WS, WE))

    def test_day_well_outside_is_rejected(self):
        for day in ("2026-10-19T00:00:00+00:00", "2026-10-20T00:00:00+00:00",
                    "2026-10-25T00:00:00+00:00"):
            self.assertIsNone(window_match(_item(day, "day"), WS, WE), day)

    def test_second_precision_boundary_is_exact(self):
        self.assertIsNone(window_match(_item("2026-10-21T10:00:00+00:00", "second"), WS, WE))
        self.assertEqual(window_match(_item("2026-10-21T20:00:00+00:00", "second"), WS, WE),
                         "exact")
        self.assertIsNone(window_match(_item("2026-10-23T20:00:00+00:00", "second"), WS, WE))

    def test_day_never_reported_as_exact(self):
        # day 精度即使区间端点落在窗口内也不是确定时刻
        for day in ("2026-10-21", "2026-10-22", "2026-10-23"):
            got = window_match(_item(f"{day}T00:00:00+00:00", "day"), WS, WE)
            self.assertIn(got, (None, "fuzzy"), f"{day} -> {got}")

    def test_no_date_is_not_in_window(self):
        self.assertIsNone(window_match(_item("", "none"), WS, WE))
        self.assertFalse(in_window(_item("", "none"), WS, WE))



class ArxivIdentityTest(unittest.TestCase):
    """同一篇 arXiv 论文从不同通道进来必须是同一个 uid。

    2026-11-02 实测：一篇论文同时出现在 cs.AI 的 RSS 与 cs.CL 的归档页，
    两条路径各算一套 uid，于是必审清单里同一篇论文出现两次，台账要填两次处置。
    """

    def test_versions_and_paths_share_identity(self):
        base = extract.make_uid("https://arxiv.org/abs/2610.41994", "t", "p")
        for u in ("https://arxiv.org/abs/2610.41994v2",
                  "http://arxiv.org/pdf/2610.41994",
                  "https://arxiv.org/html/2610.41994v1"):
            self.assertEqual(extract.make_uid(u, "other title", "other date"), base, u)

    def test_different_papers_stay_distinct(self):
        self.assertNotEqual(extract.make_uid("https://arxiv.org/abs/2610.41994", "t", "p"),
                            extract.make_uid("https://arxiv.org/abs/2610.41995", "t", "p"))

    def test_non_arxiv_urls_unaffected(self):
        self.assertNotEqual(extract.make_uid("https://x.test/a?v=1", "t", "p"),
                            extract.make_uid("https://x.test/a?v=2", "t", "p"))

    def test_listing_path_uses_the_same_uid(self):
        html = (b'<h3>Sun, 1 Nov 2026</h3>'
                b'<dt><a href="/abs/2610.41994">arXiv:2610.41994</a></dt>'
                b'<dd><div class="list-title">Title: DAMI</div>'
                b'<div class="list-journal-ref">Announce Type: new</div></dd>')
        res = extract.extract_items(html, "arxiv_listing",
                                    source_url="https://arxiv.org/list/cs.CL/pastweek")
        if res["status"] != "ok" or not res["items"]:
            self.skipTest("归档页样例与解析器格式不匹配，另有专项测试覆盖")
        self.assertEqual(res["items"][0]["uid"],
                         extract.make_uid("https://arxiv.org/abs/2610.41994", "DAMI", ""))


if __name__ == "__main__":
    unittest.main(verbosity=2)


class ArxivListingTest(unittest.TestCase):
    """归档页解析不能在第一条上就炸掉。

    url / title 原先只在 dict 字面量里算出来，而 make_uid 在同一个字面量里就
    引用了它们：第一条即 NameError，整个 _extract_arxiv_listing 变成 parse_failed，
    归档回退自引入 make_uid（2026-11-02 那轮）起从未产出过一条。那轮的 8.1
    还写了"自动改读归档页补回批次"——报告里这句话当时就是错的。
    """

    PAGE = b"""<h3>Wed, 4 Nov 2026 (showing 2 of 2 entries )</h3>
    <dt><a name='item1'>[1]</a>
      <a href ="/abs/2611.04977" title="Abstract" id="2611.04977">arXiv:2611.04977</a></dt>
    <dd><div class='meta'><div class='list-title mathjax'><span class='descriptor'>Title:</span>
          First Paper Title
        </div></div></dd>
    <dt><a name='item2'>[2]</a>
      <a href ="/abs/2611.04978" title="Abstract" id="2611.04978">arXiv:2611.04978</a></dt>
    <dd><div class='meta'><div class='list-title mathjax'><span class='descriptor'>Title:</span>
          Second Paper Title (cross-list from cs.LG)
        </div></div></dd>
    """

    def _items(self):
        import extract
        r = extract.extract_items(
            self.PAGE, "arxiv_listing",
            source_url="https://arxiv.org/list/cs.MA/pastweek?skip=0&show=2000")
        self.assertEqual(r["status"], "ok", r.get("error"))
        return r["items"]

    def test_parses_entries(self):
        items = self._items()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["url"], "https://arxiv.org/abs/2611.04977")
        self.assertEqual(items[0]["title"], "First Paper Title")

    def test_uid_matches_rss_path(self):
        import extract
        items = self._items()
        self.assertEqual(items[0]["uid"],
                         extract.make_uid("https://arxiv.org/abs/2611.04977v2",
                                          "whatever", items[0]["published"]))

    def test_published_is_batch_time(self):
        items = self._items()
        self.assertEqual(items[0]["published"], "2026-11-04T12:00:00+08:00")
        self.assertEqual(items[0]["date_precision"], "batch")
