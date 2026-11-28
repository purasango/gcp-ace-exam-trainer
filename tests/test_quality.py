"""Soru bankası kalite kapıları: sınav tekniğiyle (ipucu avcılığıyla) çözülebilen soruları engeller.

Yeni soru eklerken bu testlerin geçmesi, soruların gerçek sınav gibi bilgiyle çözülmesini sağlar.
"""
import itertools
import json
import re
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QS = json.loads((ROOT / "questions" / "ace.json").read_text(encoding="utf-8"))

ABSOLUTE = re.compile(r"\b(always|never|only|automatically|all|any|every|cannot|can't|no longer|exactly)\b", re.I)
STOP = set("which what should your with that this from have they their there would about into when does "
           "used using want need only more than other google cloud project projects choose".split())


def _words(text):
    return set(re.findall(r"[a-z][a-z0-9\-\.]{3,}", text.lower())) - STOP


class QualityGates(unittest.TestCase):
    def test_multi_select_share_and_format(self):
        multi = [q for q in QS if len(q["correct"]) > 1]
        self.assertGreaterEqual(len(multi) / len(QS), 0.08, "çok seçimli soru oranı %8'in altında")
        for q in multi:
            self.assertEqual(len(q["correct"]), 2, q["id"])
            self.assertEqual(len(q["options"]), 5, q["id"])
            self.assertIn("(Choose two.)", q["en"]["question"], q["id"])
            self.assertIn("(İki seçenek seçin.)", q["question"], q["id"])

    def test_absolute_words_are_not_a_giveaway(self):
        # "always/never/only" gibi kesin ifadeler yanlış şıklarda belirgin şekilde daha sık olmamalı.
        def ratio(want_correct):
            hits = total = 0
            for q in QS:
                for i, o in enumerate(q["en"]["options"]):
                    if (i in q["correct"]) == want_correct:
                        total += 1
                        hits += bool(ABSOLUTE.search(o))
            return hits / total
        self.assertLess(ratio(False) - ratio(True), 0.05)

    def test_longest_option_is_rarely_correct(self):
        for lang in ("tr", "en"):
            longest = 0
            for q in QS:
                lens = [len(o) for o in (q["options"] if lang == "tr" else q["en"]["options"])]
                longest += any(lens[c] == max(lens) for c in q["correct"]) and lens.count(max(lens)) == 1
            self.assertLess(longest / len(QS), 0.30, lang)

    def test_correct_position_is_balanced(self):
        single = [q["correct"][0] for q in QS if len(q["correct"]) == 1]
        for pos, n in Counter(single).items():
            self.assertLess(n / len(single), 0.35, f"doğru cevap {pos}. konumda yığılmış")

    def test_no_near_duplicate_questions(self):
        keys = [(q["id"], _words(q["en"]["question"] + " " +
                                 " ".join(q["en"]["options"][i] for i in q["correct"]))) for q in QS]
        for (a, ka), (b, kb) in itertools.combinations(keys, 2):
            sim = len(ka & kb) / max(1, len(ka | kb))
            self.assertLess(sim, 0.5, f"{a} ve {b} neredeyse aynı soru")


if __name__ == "__main__":
    unittest.main()
