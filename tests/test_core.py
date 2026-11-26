import json
import tempfile
import unittest
from pathlib import Path

from examtrainer.engine import build_session
from examtrainer.exams import EXAMS
from examtrainer.store import QuestionBank, Stats, ValidationError, localized, validate_question

ROOT = Path(__file__).resolve().parent.parent


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.bank = QuestionBank(ROOT / "questions", self.tmp)
        self.stats = Stats(self.tmp)

    def test_builtin_bank_valid(self):
        self.assertEqual(self.bank.load_errors, [])
        qs = self.bank.for_exam("ACE")
        self.assertGreaterEqual(len(qs), 140)
        self.assertEqual({q["domain"] for q in qs}, set(EXAMS["ACE"].domains))
        for q in qs:
            self.assertIn(q["topic"], EXAMS["ACE"].topics, q["id"])
        ids = [q["id"] for q in qs]
        self.assertEqual(len(ids), len(set(ids)))
        raw = json.loads((ROOT / "questions" / "ace.json").read_text(encoding="utf-8"))
        for q in raw:
            self.assertTrue(q["source_url"].startswith(("https://docs.cloud.google.com/", "https://cloud.google.com/")), q["id"])
            self.assertTrue(q["check"], q["id"])
        texts = [" ".join(q["question"].lower().split()) for q in qs]
        self.assertEqual(len(texts), len(set(texts)), "tekrarlanan soru metni")

    def test_shuffle_keeps_correct_answer(self):
        s = build_session(self.bank, self.stats, "ACE", 30, seed=1)
        for i, it in enumerate(s.items):
            correct_texts = {it.q["options"][c] for c in it.q["correct"]}
            self.assertEqual({it.options[d] for d in it.correct}, correct_texts)
            self.assertTrue(s.answer(i, it.correct))
        summary = s.finish(self.stats)
        self.assertEqual(summary["percent"], 100)
        self.assertTrue(summary["passed"])
        self.assertTrue((self.tmp / "stats.json").exists())

    def test_exam_mode_distribution_and_timer(self):
        s = build_session(self.bank, self.stats, "ACE", 50, mode="sinav", seed=2)
        self.assertEqual(len(s.items), 50)
        self.assertEqual(len({it.q["id"] for it in s.items}), 50)
        self.assertEqual(s.time_limit, 120 * 60)
        doms = [it.q["domain"] for it in s.items]
        self.assertGreater(doms.count(2), doms.count(1))

    def test_weak_focus(self):
        s = build_session(self.bank, self.stats, "ACE", 5, seed=3)
        s.answer(0, {99})  # yanlış
        s.finish(self.stats)
        weak = build_session(self.bank, self.stats, "ACE", 10, focus="zayif")
        self.assertEqual([it.q["id"] for it in weak.items], [s.items[0].q["id"]])

    def test_topic_filter(self):
        s = build_session(self.bank, self.stats, "ACE", 100, topics=["GKE (Kubernetes)"])
        self.assertTrue(all(it.q["topic"] == "GKE (Kubernetes)" for it in s.items))

    def test_validation_and_import(self):
        with self.assertRaises(ValidationError):
            validate_question({"question": "x", "options": ["a", "b"], "correct": [5]}, "ACE")
        good = {"question": "Yeni soru?", "options": ["a", "b", "c", "d"], "correct": [2],
                "domain": 2, "explanation": "çünkü"}
        added, errors = self.bank.add_user_questions([good, good], "ACE")
        self.assertEqual((added, len(errors)), (1, 1))
        stored = json.loads((self.tmp / "user_questions.json").read_text(encoding="utf-8"))
        self.assertEqual(len(stored), 1)
        again = QuestionBank(ROOT / "questions", self.tmp)
        self.assertEqual(again.count("ACE")["eklenen"], 1)
        self.assertTrue(again.delete_user_question(stored[0]["id"]))

    def test_english_translations(self):
        for q in self.bank.for_exam("ACE", sources=["builtin"]):
            self.assertIsNotNone(q["en"], q["id"])
            self.assertEqual(len(q["en"]["options"]), len(q["options"]), q["id"])
            self.assertTrue(q["en"]["explanation"], q["id"])
            self.assertEqual(localized(q, "en")["lang"], "en")

    def test_shuffle_same_order_in_both_languages(self):
        s = build_session(self.bank, self.stats, "ACE", 20, seed=5)
        for it in s.items:
            tr, en = it.options_in("tr"), it.options_in("en")
            self.assertEqual([it.q["options"].index(o) for o in tr],
                             [it.q["en"]["options"].index(o) for o in en])

    def test_missing_or_bad_english_falls_back(self):
        q = validate_question({"question": "S?", "options": ["a", "b"], "correct": [0],
                               "en": {"question": "Q?", "options": ["x"]}}, "ACE")
        self.assertIsNone(q["en"])
        self.assertEqual(localized(q, "en")["question"], "S?")

    def test_answer_length_is_not_a_giveaway(self):
        # "En uzun (veya en kısa) şıkkı seç" taktiği rastgele tahminden (~%25) belirgin iyi olmamalı.
        qs = self.bank.for_exam("ACE", sources=["builtin"])
        for lang in ("tr", "en"):
            longest = shortest = 0
            for q in qs:
                lens = [len(o) for o in localized(q, lang)["options"]]
                longest += any(lens[c] == max(lens) for c in q["correct"])
                shortest += any(lens[c] == min(lens) for c in q["correct"])
            self.assertLess(longest / len(qs), 0.40, f"{lang}: doğru cevap çoğunlukla en uzun şık")
            self.assertLess(shortest / len(qs), 0.40, f"{lang}: doğru cevap çoğunlukla en kısa şık")

    def test_practice_answer_saved_immediately(self):
        s = build_session(self.bank, self.stats, "ACE", 5, seed=4)
        qid = s.items[0].q["id"]
        s.answer(0, s.items[0].correct)
        s.record(0, self.stats)
        self.assertEqual(Stats(self.tmp).get(qid)["seen"], 1)  # oturum bitmeden diske yazıldı
        s.finish(self.stats)
        self.assertEqual(self.stats.get(qid)["seen"], 1)  # bitişte iki kez sayılmadı

    def test_imported_builtin_source_stays_deletable(self):
        raw = {"question": "Kaynağı builtin yazılmış soru?", "options": ["a", "b"], "correct": [0],
               "source": "builtin"}
        self.bank.add_user_questions([raw], "ACE")
        stored = json.loads((self.tmp / "user_questions.json").read_text(encoding="utf-8"))
        self.assertEqual(stored[0]["source"], "ice-aktarim")
        # Bu düzeltmeden önce kaydedilmiş, kaynağı "builtin" kalmış kullanıcı sorusu:
        (self.tmp / "user_questions.json").write_text(json.dumps(
            [{**raw, "question": "Eski dosyadaki soru?", "id": "ace-u1", "exam": "ACE"}]), encoding="utf-8")
        again = QuestionBank(ROOT / "questions", self.tmp)
        self.assertEqual(again.questions["ace-u1"]["source"], "ice-aktarim")
        self.assertTrue(again.delete_user_question("ace-u1"))

    def test_objective_and_check_kept(self):
        q = self.bank.questions["ace-001"]
        self.assertEqual(q["objective"], "4.1")
        self.assertTrue(q["check"])


if __name__ == "__main__":
    unittest.main()
