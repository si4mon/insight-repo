"""主动性词表的回归测试。

2026-11-10 补入。背景：补词前 131 个 high + 41 个 med 里主动性相关词为 0，
实测六篇核心文献里有一篇（2410.12361）连最低的截断线 7 分都到不了，等于完全失明。
这些测试锁住三件事：词在表里、子串连锁没有重新引入、top-K 名额够用。
"""
import json
import unittest
from pathlib import Path

import must_review

TERMS = json.loads((Path(__file__).resolve().parents[1] / "data" / "review_terms.json")
                   .read_text(encoding="utf-8"))


class ProactivityTermsTest(unittest.TestCase):
    def test_core_terms_present(self):
        """核心词必须在 high 层：这些是主动性方向唯一的识别钩子。"""
        high = TERMS["arxiv_score"]["high"]
        for w in ("proactiv", "interrupt", "insight policy", "unsolicited",
                  "when to assist", "when to intervene", "intervention timing",
                  "proposal rate", "missed opportunity", "alert fatigue",
                  "attention budget", "silence", "anticipat", "personal agent"):
            self.assertIn(w, high, f"high 层缺 {w!r}")

    def test_drift_prone_terms_stay_in_med(self):
        """语义漂移词留在 med：intervention 多为因果/医学干预，salien 多为 saliency map。"""
        high = TERMS["arxiv_score"]["high"]
        med = TERMS["arxiv_score"]["med"]
        for w in ("intervention", "salien", "assistance", "silent", "ambient"):
            self.assertIn(w, med, f"med 层缺 {w!r}")
            self.assertNotIn(w, high, f"{w!r} 命中面过宽，不该进 high")

    def test_no_substring_chain_within_concept(self):
        """同一概念不得同时留下包含关系的词，否则一篇文献会被重复计分。

        这是 eval ⊂ evaluation 那次教训的推广：interrupt / interruption /
        interruption cost 只能留最短的一个。
        """
        all_terms = TERMS["arxiv_score"]["high"] + TERMS["arxiv_score"]["med"]
        chains = [("interrupt", "interruption"), ("interrupt", "interruption cost"),
                  ("notif", "notification"), ("notif", "notification fatigue"),
                  ("proactiv", "proactive"), ("anticipat", "anticipatory"),
                  ("situational", "situational awareness")]
        for short, long in chains:
            if short in all_terms:
                self.assertNotIn(long, all_terms,
                                 f"{short!r} 已覆盖 {long!r}，同时保留会重复计分")

    def test_ai_relevance_covers_personal_agent(self):
        """ai_relevance 的口径是宁宽勿窄，中文 personal agent 报道要靠它留痕。"""
        self.assertIn("个人助理", TERMS["ai_relevance"]["zh"])
        self.assertIn("主动提醒", TERMS["ai_relevance"]["zh"])
        self.assertIn("personal agent", TERMS["ai_relevance"]["en"])

    def test_position_paper_clears_low_cutoff(self):
        """2605.06717 的真实摘要在补词后必须明显高于常见截断线 7/8。

        摘要片段取自 export.arxiv.org 的实际返回，不是复述，避免循环论证。
        """
        abstract = (
            "Coding agents are rapidly changing the landscape of software development. "
            "We argue that agentic coding needs proactivity, not just autonomy: an agent "
            "must decide whether and when to interrupt the developer. We audit deployed "
            "agents and find no model of interruption cost, and unsolicited suggestions "
            "evaluated only by precision. We propose an insight policy."
        )
        score, _ = must_review.arxiv_score({"title": abstract, "snippet": ""}, TERMS)
        self.assertGreaterEqual(score, 9, "立场论文仍过不了常见截断线")

    def test_top_k_absorbs_the_additions(self):
        """K 是固定名额，加词会挤掉原有条目，所以 K 必须跟着抬。

        五轮回测里 K=40 挤掉 11 条（含两条已发布事件），K=48 归零。
        以后再加词必须连带复核这个值。
        """
        self.assertGreaterEqual(must_review.ARXIV_TOP_K, 48)


if __name__ == "__main__":
    unittest.main()
