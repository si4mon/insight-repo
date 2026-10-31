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


if __name__ == "__main__":
    unittest.main(verbosity=2)
