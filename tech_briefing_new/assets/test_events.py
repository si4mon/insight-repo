#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""events.py 单测：event_key 的规范化与 normalize 的全有或全无语义。"""
import json
import tempfile
import unittest
from pathlib import Path

from events import canonical_source, event_key, normalize_dir, normalize_event

GOOD = {"event_title": "t", "source": "https://www.example.com/post/", "entity": "OpenAI",
        "first_publish_shanghai": "2026-10-30T10:00:00+08:00", "rating": "a+",
        "primary_path": "B1.1", "change_types": ["ct-01"], "evidence_form": "Product",
        "date_precision": "Second"}


class CanonicalTest(unittest.TestCase):
    def test_arxiv_versions_share_identity(self):
        self.assertEqual(canonical_source("https://arxiv.org/abs/2610.01234v1"),
                         canonical_source("https://arxiv.org/pdf/2610.01234v3"))
        self.assertEqual(canonical_source("arxiv.org/abs/2610.01234"), "arxiv:2610.01234")

    def test_github_release(self):
        self.assertEqual(canonical_source("https://github.com/OpenAI/Codex/releases/tag/v1.2.0"),
                         "gh:openai/codex@v1.2.0")

    def test_url_noise_ignored(self):
        a = event_key({"source": "https://www.Example.com/post/?utm_source=x#top"})
        b = event_key({"source": "http://example.com/post"})
        self.assertEqual(a, b)

    def test_canonical_source_overrides(self):
        a = event_key({"source": "https://media.com/repost", "canonical_source": "https://openai.com/x"})
        self.assertEqual(a, event_key({"source": "https://openai.com/x"}))


class NormalizeTest(unittest.TestCase):
    def test_enums_are_normalized(self):
        out, errors = normalize_event(GOOD, "EV-01")
        self.assertEqual(errors, [])
        self.assertEqual((out["rating"], out["change_types"], out["evidence_form"], out["date_precision"]),
                         ("A+", ["CT-01"], "product", "second"))
        self.assertEqual(out["event_id"], "EV-01")
        self.assertEqual(len(out["event_key"]), 12)

    def test_bad_values_are_reported(self):
        bad = {**GOOD, "rating": "S", "evidence_form": "blog", "primary_path": "Z9.9",
               "first_publish_shanghai": "昨天"}
        _, errors = normalize_event(bad, "EV-02")
        joined = " ".join(errors)
        for frag in ("rating", "evidence_form", "primary_path", "ISO"):
            self.assertIn(frag, joined)

    def test_missing_required_field(self):
        _, errors = normalize_event({k: v for k, v in GOOD.items() if k != "evidence_form"}, "EV-03")
        self.assertTrue(any("evidence_form" in e for e in errors))

    def test_dir_is_all_or_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "EV-01.json").write_text(json.dumps(GOOD), encoding="utf-8")
            (d / "EV-02.json").write_text(json.dumps({**GOOD, "source": "https://b.com", "rating": "S"}),
                                          encoding="utf-8")
            before = (d / "EV-01.json").read_text(encoding="utf-8")
            _, errors = normalize_dir(d)
            self.assertTrue(errors)
            self.assertEqual((d / "EV-01.json").read_text(encoding="utf-8"), before,
                             "有错误时一个文件都不能改写")

    def test_duplicate_event_key_in_dir(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            for i in (1, 2):
                (d / f"EV-0{i}.json").write_text(json.dumps(GOOD), encoding="utf-8")
            _, errors = normalize_dir(d)
            self.assertTrue(any("event_key 相同" in e for e in errors))

    def test_dir_ok_writes_keys(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "EV-01.json").write_text(json.dumps(GOOD), encoding="utf-8")
            n, errors = normalize_dir(d)
            self.assertEqual((n, errors), (1, []))
            self.assertIn("event_key", json.loads((d / "EV-01.json").read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
