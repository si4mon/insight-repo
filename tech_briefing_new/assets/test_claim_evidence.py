#!/usr/bin/env python3
"""claim 级证据绑定的测试。"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import claim_evidence as ce
import verify_gates as vg

PAGE = (
    "<html><head><style>body{color:red}</style></head><body>\n"
    "<h1>Security advisory</h1>\n"
    "<p>The malicious code is <b>prepended</b> to extension.js and runs\n"
    "   on Node load, before &amp; independent of activate().</p>\n"
    "<script>var x = 'not prose';</script>\n"
    "<p>受影响版本为 2.1.312 与 2.1.313，分发约 11 小时。</p>\n"
    "</body></html>\n"
)


class NormalizeTest(unittest.TestCase):
    def test_tags_entities_and_whitespace_folded(self):
        t = ce.normalize_text(PAGE)
        self.assertIn("prepended to extension.js and runs on Node load", t)
        self.assertIn("before & independent of activate()", t)

    def test_script_and_style_bodies_dropped(self):
        t = ce.normalize_text(PAGE)
        self.assertNotIn("not prose", t)
        self.assertNotIn("color:red", t)

    def test_typographic_variants_match(self):
        t = ce.normalize_text("他说“这是机制”，不是推测。")
        self.assertIn(ce.normalize_quote('他说"这是机制",不是推测。'), t)


class VerifyTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.snap = self.d / "advisory.html"
        self.snap.write_text(PAGE, encoding="utf-8")
        self.sha = ce.sha256_file(self.snap)

    def ev(self, rating="A", **over):
        c = {"claim": "载荷前置于 extension.js",
             "evidence": {"snapshot": "advisory.html", "snapshot_sha256": self.sha,
                          "quote": "prepended to extension.js"}}
        c.update(over.pop("claim0", {}))
        e = {"event_id": "EV-01", "rating": rating, "claims": [c]}
        e.update(over)
        return e

    def run_(self, ev):
        return " ".join(ce.verify(ev, [self.d]))

    def test_matching_quote_passes(self):
        self.assertEqual(self.run_(self.ev()), "")

    def test_b_rating_not_required(self):
        e = self.ev(rating="B", claim0={"evidence": None})
        self.assertEqual(self.run_(e), "")

    def test_missing_evidence_block_reported(self):
        self.assertIn("缺 evidence", self.run_(self.ev(claim0={"evidence": None})))

    def test_each_missing_field_reported(self):
        for field, msg in (("snapshot", "缺 snapshot"),
                           ("snapshot_sha256", "缺 snapshot_sha256"),
                           ("quote", "缺 quote")):
            e = self.ev()
            e["claims"][0]["evidence"][field] = ""
            self.assertIn(msg, self.run_(e), field)

    def test_invented_quote_reported(self):
        """快照在，但这句话不是从原文来的——这正是凭印象写机制的样子。"""
        e = self.ev()
        e["claims"][0]["evidence"]["quote"] = "载荷在用户点击后才执行"
        self.assertIn("不是从原文来的", self.run_(e))

    def test_snapshot_swapped_after_the_fact_reported(self):
        self.snap.write_text(PAGE.replace("prepended", "appended"), encoding="utf-8")
        self.assertIn("在事后被换过", self.run_(self.ev()))

    def test_missing_snapshot_file_reported(self):
        e = self.ev()
        e["claims"][0]["evidence"]["snapshot"] = "nope.html"
        self.assertIn("找不到快照", self.run_(e))

    def test_snapshot_found_by_name_in_subdirectory(self):
        sub = self.d / "nested"; sub.mkdir()
        moved = sub / "advisory.html"
        moved.write_text(PAGE, encoding="utf-8")
        self.snap.unlink()
        self.assertEqual(self.run_(self.ev()), "")

    def test_dropped_claim_is_exempt(self):
        e = self.ev()
        e["claims"][0] = {"claim": "x", "disposition": "dropped:低影响"}
        self.assertEqual(self.run_(e), "")

    def test_cjk_quote_matches(self):
        e = self.ev()
        e["claims"][0]["evidence"]["quote"] = "受影响版本为 2.1.312 与 2.1.313"
        self.assertEqual(self.run_(e), "")

    def test_verify_dir_counts_only_required_events(self):
        for eid, rating in (("EV-01", "A"), ("EV-02", "B")):
            e = self.ev(rating=rating)
            e["event_id"] = eid
            (self.d / f"{eid}.json").write_text(json.dumps(e, ensure_ascii=False),
                                                encoding="utf-8")
        n, errs = ce.verify_dir(self.d, [self.d])
        self.assertEqual((n, errs), (1, []))


class GateTest(VerifyTest):
    def gate(self, **evs):
        evdir = self.d / "events_run_2026-10-30"
        evdir.mkdir(exist_ok=True)
        for eid, ev in evs.items():
            ev["event_id"] = eid
            (evdir / f"{eid}.json").write_text(json.dumps(ev, ensure_ascii=False),
                                               encoding="utf-8")
        c = vg.Check()
        vg.check_claim_evidence(c, evdir, [str(self.d)])
        return {r["name"]: (r["status"], r["detail"]) for r in c.results}

    def test_gate_passes_on_bound_claims(self):
        r = self.gate(**{"EV-01": self.ev()})
        self.assertEqual(r["A/A+ 的 claim 绑定到快照原文片段"][0], "PASS")

    def test_gate_fails_on_invented_quote(self):
        e = self.ev()
        e["claims"][0]["evidence"]["quote"] = "我编的机制"
        st, detail = self.gate(**{"EV-01": e})["A/A+ 的 claim 绑定到快照原文片段"]
        self.assertEqual(st, "FAIL")
        self.assertIn("不是从原文来的", detail)

    def test_gate_warns_without_snapshot_roots(self):
        evdir = self.d / "events_run_2026-10-30"
        evdir.mkdir(exist_ok=True)
        (evdir / "EV-01.json").write_text(json.dumps(self.ev(), ensure_ascii=False),
                                          encoding="utf-8")
        c = vg.Check()
        vg.check_claim_evidence(c, evdir, [])
        self.assertEqual([r["status"] for r in c.results], ["WARN"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
