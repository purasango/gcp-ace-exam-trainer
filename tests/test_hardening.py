"""Güvenlik incelemesindeki bulgular için regresyon testleri (ağ gerektirmez)."""
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

from examtrainer import store
from examtrainer.store import (QuestionBank, Settings, Stats, ValidationError, load_import_file,
                               validate_question)

ROOT = Path(__file__).resolve().parent.parent
GOOD = {"question": "S?", "options": ["a", "b", "c", "d"], "correct": [1]}


class ValidationTypes(unittest.TestCase):
    def test_non_string_exam_is_validation_error(self):  # F3
        for bad in (7, True, ["ACE"], {"x": 1}, 1.5):
            with self.subTest(exam=bad), self.assertRaises(ValidationError):
                validate_question({**GOOD, "exam": bad}, "ACE")

    def test_bool_correct_rejected(self):
        with self.assertRaises(ValidationError):
            validate_question({**GOOD, "correct": [True]}, "ACE")
        with self.assertRaises(ValidationError):
            validate_question({**GOOD, "correct": True}, "ACE")

    def test_wrong_field_types_only_raise_validation_error(self):
        cases = [("question", ["x"]), ("question", {"a": 1}), ("options", "abcd"), ("options", [["a"], "b"]),
                 ("explanation", ["x"]), ("topic", {"a": 1}), ("source_url", ["u"]),
                 ("difficulty", ["zor"]), ("domain", ["1"]), ("check", "abc"), ("en", ["x"]), ("id", ["x"])]
        for field, val in cases:
            with self.subTest(field=field):
                try:
                    q = validate_question({**GOOD, field: val}, "ACE")
                except ValidationError:
                    continue
                # Kabul edildiyse normalize edilmiş türler doğru olmalı
                self.assertIsInstance(q["question"], str)
                self.assertTrue(all(isinstance(o, str) for o in q["options"]))
                self.assertIsInstance(q["domain"], int)

    def test_length_limits(self):
        with self.assertRaises(ValidationError):
            validate_question({**GOOD, "question": "x" * 5000}, "ACE")
        with self.assertRaises(ValidationError):
            validate_question({**GOOD, "options": ["a" * 2000, "b"]}, "ACE")


class ImportAndStartup(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_import_with_bad_exam_reports_error(self):  # F3
        bank = QuestionBank(ROOT / "questions", self.tmp)
        added, errors = bank.add_user_questions([{**GOOD, "exam": 7}, {**GOOD, "question": "Yeni?"}], "ACE")
        self.assertEqual(added, 1)
        self.assertEqual(len(errors), 1)

    def test_startup_survives_malformed_user_records(self):  # F3
        (self.tmp / "user_questions.json").write_text(json.dumps(
            [{**GOOD, "exam": 7}, "metin", 42, {**GOOD, "question": "Sağlam?", "exam": "ACE", "id": "u1"}]),
            encoding="utf-8")
        bank = QuestionBank(ROOT / "questions", self.tmp)
        self.assertIn("u1", bank.questions)
        self.assertEqual(len(bank.load_errors), 3)

    def test_wrong_top_level_shapes_fall_back_to_defaults(self):
        (self.tmp / "user_questions.json").write_text('{"a": 1}', encoding="utf-8")
        (self.tmp / "stats.json").write_text("[1, 2]", encoding="utf-8")
        (self.tmp / "settings.json").write_text('{"language": ["x"], "last_exam": 5}', encoding="utf-8")
        QuestionBank(ROOT / "questions", self.tmp)
        st = Stats(self.tmp)
        self.assertEqual((st.questions, st.sessions), ({}, []))
        self.assertEqual(Settings(self.tmp).data, Settings.DEFAULTS)
        # Bozuk dosyalar silinmez, yedeklenir
        self.assertTrue(any(p.name.startswith("stats.json.bozuk-") for p in self.tmp.iterdir()))

    def test_malformed_stats_entries_are_dropped(self):
        (self.tmp / "stats.json").write_text(json.dumps({
            "questions": {"ace-001": {"seen": 1, "correct": 1, "streak": 1, "last": 0}, "ace-002": "x",
                          "ace-003": {"seen": "1"}},
            "sessions": [{"exam": "ACE"}, 5]}), encoding="utf-8")
        st = Stats(self.tmp)
        self.assertEqual(list(st.questions), ["ace-001"])
        self.assertEqual(st.sessions, [])

    def test_import_file_limits(self):  # F2
        big = self.tmp / "big.json"
        big.write_bytes(b"[" + b" " * (store.MAX_IMPORT_BYTES + 1) + b"]")
        with self.assertRaises(ValidationError):
            load_import_file(big)
        deep = self.tmp / "deep.json"
        deep.write_text("[" * 100000 + "]" * 100000, encoding="utf-8")
        with self.assertRaises(ValidationError):
            load_import_file(deep)
        many = self.tmp / "many.json"
        many.write_text(json.dumps([GOOD] * (store.MAX_IMPORT_QUESTIONS + 1)), encoding="utf-8")
        with self.assertRaises(ValidationError):
            load_import_file(many)
        bad = self.tmp / "bad.json"
        bad.write_bytes(b"\xff\xfe nope")
        with self.assertRaises(ValidationError):
            load_import_file(bad)
        ok = self.tmp / "ok.json"
        ok.write_text(json.dumps({"questions": [GOOD]}), encoding="utf-8")
        self.assertEqual(load_import_file(ok), [GOOD])

    def test_write_json_cleans_temp_file_on_failure(self):
        with self.assertRaises(TypeError):
            store._write_json(self.tmp / "x.json", {"bad": object()})
        self.assertEqual([p.name for p in self.tmp.iterdir()], [])


class SourceChecker(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import check_sources
        self.cs = check_sources

    def test_redirect_outside_allowlist_is_refused(self):
        import urllib.request
        h = self.cs._AllowlistRedirects()
        req = urllib.request.Request("https://cloud.google.com/x")
        with self.assertRaises(urllib.error.URLError):
            h.redirect_request(req, None, 302, "Found", {}, "http://evil.example/")
        self.assertIsNotNone(h.redirect_request(req, None, 301, "Moved", {},
                                                "https://docs.cloud.google.com/x"))

    def test_non_allowlisted_urls_never_fetched(self):
        for u in ("file:///etc/passwd", "ftp://cloud.google.com/", "http://cloud.google.com/", 5, None):
            self.assertFalse(self.cs.is_allowed(u))
        with self.assertRaises(ValueError):
            self.cs.page_text("file:///etc/passwd", {})


if __name__ == "__main__":
    unittest.main()
