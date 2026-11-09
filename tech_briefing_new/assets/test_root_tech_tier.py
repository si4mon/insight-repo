import json, unittest
from pathlib import Path
ROOT = Path(__file__).parent.parent / 'data' / 'root_tech.json'

class BusinessTierTest(unittest.TestCase):
    """根技术的 business_tier 标签完整性。

    tier 用于召回配额、排序与留观门槛，不参与评分——业务优先级若进评分公式，
    一个 9 分且机制新颖度与战略相关度均为 2 的安全类事件会被制度性压到 A。
    这里只守标签本身：每条都要有、取值合法、交叉项不被按组重算覆盖。
    """

    @classmethod
    def setUpClass(cls):
        cls.d = json.loads(ROOT.read_text(encoding='utf-8'))
        cls.roots = cls.d['roots']

    def test_every_root_has_a_tier(self):
        missing = [r['id'] for r in self.roots if 'business_tier' not in r]
        self.assertEqual(missing, [], f'缺 business_tier: {missing}')

    def test_tier_values_are_valid(self):
        bad = [(r['id'], r.get('business_tier')) for r in self.roots
               if r.get('business_tier') not in (1, 2, 3)]
        self.assertEqual(bad, [])

    def test_cross_cutting_entries_keep_their_adjudicated_tier(self):
        """这 5 条是业务优先级与根技术组边界交叉之处，2026-11-09 逐条裁定过。
        按组重算会把它们改错——S2.2 与 S2.3 同组却分属 tier-3 与 tier-1。"""
        want = {'S2.2': 3, 'S2.3': 1, 'S2.4': 2, 'S4.4': 1, 'S4.5': 1}
        got = {r['id'].replace('RT:', ''): r['business_tier'] for r in self.roots
               if r['id'].replace('RT:', '') in want}
        self.assertEqual(got, want)

    def test_cross_cutting_entries_carry_a_reason(self):
        for r in self.roots:
            if r['id'].replace('RT:', '') in ('S2.2', 'S2.3', 'S2.4', 'S4.4', 'S4.5'):
                self.assertTrue((r.get('tier_note') or '').strip(),
                                f"{r['id']} 缺 tier_note")

    def test_same_group_may_split_across_tiers(self):
        """回归：不要「同组同 tier」地去规整它——S2 组横跨三个 tier 是裁定结果。"""
        s2 = {r['business_tier'] for r in self.roots
              if r.get('group', '').startswith('S2 ')}
        self.assertEqual(s2, {1, 2, 3})

    def test_note_explains_tier_is_not_a_scoring_dimension(self):
        note = self.d.get('business_tier_note', '')
        self.assertIn('不参与评分维度', note)

if __name__ == '__main__':
    unittest.main(verbosity=2)
