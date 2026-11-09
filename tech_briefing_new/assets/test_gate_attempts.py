#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""门禁轮次与降级交付的单测。"""
import json, subprocess, sys, tempfile, unittest
from pathlib import Path
HERE=Path(__file__).parent

class GateAttemptTest(unittest.TestCase):
    """门禁轮次必须是事实而不是回忆：每次运行追加一行，不依赖谁记得跑了几轮。
    插入降级头之后那次重跑是交付前复核，不算新的修复尝试——否则轮次会比
    降级头里写的数字多 1，两处自相矛盾。"""

    def setUp(self):
        self._t=tempfile.TemporaryDirectory(); self.addCleanup(self._t.cleanup)
        self.d=Path(self._t.name)/'reports'; self.d.mkdir()
        self.md=self.d/'r-2026-11-08.md'
        self.md.write_text("---\ntitle: t\ndate: 2026-11-08\n---\n\n正文。\n",encoding='utf-8')

    def _run(self):
        return subprocess.run([sys.executable,str(HERE/'verify_gates.py'),'--md',str(self.md)],
                              capture_output=True,text=True)

    def _summary(self):
        return json.loads((self.d/'.gate_summary.json').read_text(encoding='utf-8'))

    def test_attempt_increments(self):
        for n in (1,2,3):
            self._run()
            self.assertEqual(self._summary()['attempt'], n)

    def test_attempts_log_is_appended(self):
        self._run(); self._run()
        lines=[l for l in (self.d/'.gate_attempts.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
        self.assertEqual(len(lines),2)
        self.assertEqual([json.loads(l)['attempt'] for l in lines],[1,2])

    def test_redeliver_check_does_not_increment(self):
        self._run(); self._run(); self._run()
        self.assertEqual(self._summary()['attempt'],3)
        s=self.md.read_text(encoding='utf-8')
        self.md.write_text(s.replace('正文。','<!-- gate-degraded -->\n\n> [WARNING]\n> 降级。\n\n正文。'),encoding='utf-8')
        r=self._run()
        self.assertEqual(self._summary()['attempt'],3, '复核不该把轮次推到 4')
        self.assertTrue(self._summary()['redeliver_check'])
        self.assertIn('交付前复核', r.stdout)

    def test_cap_message_points_to_degraded_delivery(self):
        self._run(); self._run(); r=self._run()
        self.assertIn('已达重试上限', r.stdout)
        self.assertIn('--allow-gate-fail', r.stdout)

    def test_md_sha256_recorded(self):
        self._run()
        import hashlib
        self.assertEqual(self._summary()['md_sha256'],
                         hashlib.sha256(self.md.read_bytes()).hexdigest())

if __name__=='__main__':
    unittest.main(verbosity=2)
