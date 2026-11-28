"""Arayüz dili (TR/EN) testleri."""
import json
import re
import string
import tempfile
import unittest
from pathlib import Path

from examtrainer import i18n
from examtrainer.engine import build_session
from examtrainer.exams import EXAMS
from examtrainer.store import QuestionBank, Settings, Stats, ValidationError, load_import_file, validate_question

ROOT = Path(__file__).resolve().parent.parent
TURKISH = re.compile("[çğıöşüÇĞİÖŞÜ]")


def fields(s):
    return {f for _, f, _, _ in string.Formatter().parse(s) if f}


class TestStrings(unittest.TestCase):
    def test_every_key_has_both_languages_with_same_placeholders(self):
        for key, (tr, en) in i18n.STRINGS.items():
            self.assertTrue(tr and en, key)
            self.assertEqual(fields(tr), fields(en), key)

    def test_english_strings_have_no_turkish(self):
        # "Türkçe" düğme etiketi dışında İngilizce metinlerde Türkçe karakter olmamalı
        for key, (_, en) in i18n.STRINGS.items():
            self.assertIsNone(TURKISH.search(en), key)

    def test_gui_uses_only_known_keys(self):
        src = (ROOT / "examtrainer" / "gui.py").read_text(encoding="utf-8")
        used = set(re.findall(r'\bt\(\s*"([a-z_]+)"', src))
        used |= set(re.findall(r'i18n\.t\(\s*"([a-z_]+)"', src))
        self.assertGreater(len(used), 50)
        self.assertEqual(used - set(i18n.STRINGS), set())
        for prefix, keys in (("mode_", ("pratik", "sinav")), ("mode_short_", ("pratik", "sinav")),
                             ("focus_", ("karisik", "zayif", "yeni")), ("qlang_", ("tr", "en", "bi")),
                             ("srclabel_", ("builtin", "ice-aktarim"))):
            for k in keys:
                self.assertIn(prefix + k, i18n.STRINGS)

    def test_unknown_language_falls_back_to_turkish(self):
        self.assertEqual(i18n.norm_lang("de"), "tr")
        self.assertEqual(i18n.norm_lang(None), "tr")
        self.assertEqual(i18n.t("btn_start", "xx"), i18n.STRINGS["btn_start"][0])


class TestContentLabels(unittest.TestCase):
    def test_all_topics_and_domains_translated(self):
        data = json.loads((ROOT / "questions" / "ace.json").read_text(encoding="utf-8"))
        qs = data["questions"] if isinstance(data, dict) else data
        for topic in {q["topic"] for q in qs} | set(EXAMS["ACE"].topics):
            self.assertIn(topic, i18n.TOPIC_EN)
            self.assertIsNone(TURKISH.search(i18n.TOPIC_EN[topic]), topic)
        exam = EXAMS["ACE"]
        for k in exam.domains:
            self.assertNotEqual(i18n.domain_name(exam, k, "en"), exam.domain_name(k))
            self.assertEqual(i18n.domain_name(exam, k, "tr"), exam.domain_name(k))
        self.assertEqual(i18n.topic_name("Kendi konum", "en"), "Kendi konum")
        self.assertEqual(i18n.difficulty("zor", "en"), "hard")


class TestErrorTranslation(unittest.TestCase):
    def messages(self):
        bad = [
            "x", {"question": ""}, {"question": "q", "options": ["a"]},
            {"question": "q", "options": ["a", "a"], "correct": 0},
            {"question": "q", "options": ["a", "b"], "correct": [5]},
            {"question": "q", "options": ["a", "b"], "correct": 0, "exam": 3},
            {"question": "q", "options": ["a", "b"], "correct": 0, "exam": "PCA"},
            {"question": ["q"], "options": ["a", "b"], "correct": 0},
            {"question": "q" * 5000, "options": ["a", "b"], "correct": 0},
        ]
        out = []
        for raw in bad:
            with self.assertRaises(ValidationError) as cm:
                validate_question(raw, "ACE")
            out.append(str(cm.exception))
        with tempfile.TemporaryDirectory() as d:
            for name, body in (("a.json", b"{bad"), ("b.json", b"42"), ("c.json", b"[" * 100000)):
                p = Path(d) / name
                p.write_bytes(body)
                with self.assertRaises(ValidationError) as cm:
                    load_import_file(p)
                out.append(str(cm.exception))
            big = Path(d) / "big.json"
            big.write_text(json.dumps([{}] * 2001))
            with self.assertRaises(ValidationError) as cm:
                load_import_file(big)
            out.append(str(cm.exception))
            bank = QuestionBank(Path(d), Path(d))
            q = {"question": "Yeni soru?", "options": ["a", "b"], "correct": 0}
            bank.add_user_questions([q], "ACE")
            _, errs = bank.add_user_questions([q], "ACE")
            out += errs
            with self.assertRaises(ValueError) as cm:
                build_session(bank, Stats(Path(d)), "ACE", 5, topics=["yok"])
            out.append(str(cm.exception))
        return out

    def test_core_messages_translate_to_english(self):
        msgs = self.messages()
        self.assertGreaterEqual(len(msgs), 14)
        for m in msgs:
            en = i18n.error(m, "en")
            self.assertIsNone(TURKISH.search(en), f"{m!r} -> {en!r}")
            self.assertEqual(i18n.error(m, "tr"), m)


class TestSettings(unittest.TestCase):
    def test_ui_lang_default_and_persist(self):
        with tempfile.TemporaryDirectory() as d:
            s = Settings(Path(d))
            self.assertEqual(s["ui_lang"], "tr")
            s["ui_lang"] = "en"
            s.save()
            self.assertEqual(Settings(Path(d))["ui_lang"], "en")


class TestIcon(unittest.TestCase):
    def test_icon_files_exist(self):
        assets = ROOT / "examtrainer" / "assets"
        for n in (16, 32, 48, 256):
            self.assertTrue((assets / f"icon-{n}.png").read_bytes().startswith(b"\x89PNG"))
        self.assertTrue((assets / "icon.ico").read_bytes().startswith(b"\x00\x00\x01\x00"))


if __name__ == "__main__":
    unittest.main()
