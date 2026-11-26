"""Soru bankası, istatistikler ve ayarların diskte saklanması."""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

from .exams import EXAMS

APP_DIR = Path(__file__).resolve().parent.parent
BUILTIN_DIR = APP_DIR / "questions"
DATA_DIR = Path(os.environ.get("GCP_TRAINER_DATA", APP_DIR / "data"))

DIFFICULTIES = ("kolay", "orta", "zor")


def _read_json(path: Path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except (json.JSONDecodeError, OSError):
        # Bozuk dosyayı kaybetmemek için yedekle, varsayılanla devam et.
        try:
            path.rename(path.with_suffix(path.suffix + f".bozuk-{int(time.time())}"))
        except OSError:
            pass
        return default


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


class ValidationError(ValueError):
    pass


def validate_question(q: dict, exam_code: str | None = None) -> dict:
    """Bir soruyu doğrular ve normalize edilmiş kopyasını döndürür."""
    if not isinstance(q, dict):
        raise ValidationError("Soru bir nesne olmalı")
    text = str(q.get("question", "")).strip()
    options = q.get("options")
    correct = q.get("correct")
    if not text:
        raise ValidationError("Soru metni boş")
    if not isinstance(options, list) or not 2 <= len(options) <= 8:
        raise ValidationError("2-8 arası seçenek olmalı")
    options = [str(o).strip() for o in options]
    if any(not o for o in options) or len(set(options)) != len(options):
        raise ValidationError("Seçenekler boş veya tekrarlı olamaz")
    if isinstance(correct, int):
        correct = [correct]
    if (not isinstance(correct, list) or not correct
            or not all(isinstance(c, int) and 0 <= c < len(options) for c in correct)
            or len(set(correct)) != len(correct) or len(correct) >= len(options)):
        raise ValidationError("Doğru cevap indeksleri geçersiz")
    exam = (q.get("exam") or exam_code or "").upper()
    if exam not in EXAMS:
        raise ValidationError(f"Bilinmeyen sınav: {exam!r}")
    domain = q.get("domain", 1)
    try:
        domain = int(domain)
    except (TypeError, ValueError):
        domain = 1
    if domain not in EXAMS[exam].domains:
        domain = min(EXAMS[exam].domains)
    en = q.get("en")
    if not (isinstance(en, dict) and str(en.get("question", "")).strip()
            and isinstance(en.get("options"), list) and len(en["options"]) == len(options)):
        en = None
    else:
        en = {"question": str(en["question"]).strip(),
              "options": [str(o).strip() for o in en["options"]],
              "explanation": str(en.get("explanation", "")).strip()}
    diff = str(q.get("difficulty", "orta")).lower()
    if diff not in DIFFICULTIES:
        diff = "orta"
    return {
        "id": str(q.get("id") or ""),
        "exam": exam,
        "domain": domain,
        "difficulty": diff,
        "topic": str(q.get("topic", "") or "").strip(),
        "question": text,
        "options": options,
        "correct": sorted(correct),
        "explanation": str(q.get("explanation", "")).strip(),
        "source": str(q.get("source", "builtin")),
        "source_url": str(q.get("source_url", "") or ""),
        "objective": str(q.get("objective", "") or ""),
        "check": [str(c) for c in q["check"]] if isinstance(q.get("check"), list) else [],
        "created": q.get("created") or "",
        "en": en,
    }


def localized(q: dict, lang: str) -> dict:
    """Sorunun istenen dildeki metnini döndürür ('en' yoksa Türkçeye düşer)."""
    if lang == "en" and q.get("en"):
        return {"question": q["en"]["question"], "options": q["en"]["options"],
                "explanation": q["en"]["explanation"] or q["explanation"], "lang": "en"}
    return {"question": q["question"], "options": q["options"],
            "explanation": q["explanation"], "lang": "tr"}


class QuestionBank:
    """Hazır sorular (questions/*.json) + kullanıcının eklediği/ürettiği sorular."""

    def __init__(self, builtin_dir: Path = BUILTIN_DIR, data_dir: Path = DATA_DIR):
        self.builtin_dir = Path(builtin_dir)
        self.user_file = Path(data_dir) / "user_questions.json"
        self.questions: dict[str, dict] = {}
        self.load_errors: list[str] = []
        self.reload()

    def reload(self) -> None:
        self.questions.clear()
        self.load_errors.clear()
        for exam in EXAMS.values():
            if exam.bank_file:
                for q in _read_json(self.builtin_dir / exam.bank_file, []):
                    self._add(q, exam.code, "builtin")
        for q in _read_json(self.user_file, []):
            added = self._add(q, None, None)
            if added and added["source"] == "builtin":
                # Kullanıcı dosyasındaki soru hazır sayılmaz; aksi halde silinemez.
                added["source"] = "ice-aktarim"

    def _add(self, raw: dict, exam_code, source) -> dict | None:
        try:
            q = validate_question(raw, exam_code)
        except ValidationError as e:
            self.load_errors.append(f"{raw.get('id', '?')}: {e}")
            return None
        if source:
            q["source"] = source
        if not q["id"]:
            q["id"] = f"{q['exam'].lower()}-u{int(time.time()*1000)}-{len(self.questions)}"
        self.questions[q["id"]] = q
        return q

    def for_exam(self, exam_code: str, domains=None, sources=None, topics=None) -> list[dict]:
        return [q for q in self.questions.values()
                if q["exam"] == exam_code
                and (not domains or q["domain"] in domains)
                and (not topics or q["topic"] in topics)
                and (not sources or q["source"] in sources)]

    def count(self, exam_code: str) -> dict:
        qs = self.for_exam(exam_code)
        return {"toplam": len(qs),
                "hazir": sum(q["source"] == "builtin" for q in qs),
                "eklenen": sum(q["source"] != "builtin" for q in qs)}

    def is_duplicate(self, q: dict) -> bool:
        norm = " ".join(q["question"].lower().split())
        return any(" ".join(x["question"].lower().split()) == norm
                   for x in self.questions.values() if x["exam"] == q["exam"])

    def add_user_questions(self, raws: list[dict], exam_code: str | None = None,
                           source: str = "ice-aktarim") -> tuple[int, list[str]]:
        """Soruları doğrulayıp kullanıcı dosyasına ekler. (eklenen, hatalar) döner."""
        stored = _read_json(self.user_file, [])
        added, errors = 0, []
        stamp = time.strftime("%Y-%m-%d")
        for i, raw in enumerate(raws):
            try:
                q = validate_question(raw, exam_code)
            except ValidationError as e:
                errors.append(f"#{i + 1}: {e}")
                continue
            if self.is_duplicate(q):
                errors.append(f"#{i + 1}: zaten bankada var")
                continue
            raw_source = raw.get("source")
            q["source"] = raw_source if raw_source and raw_source != "builtin" else source
            q["created"] = q["created"] or stamp
            q["id"] = f"{q['exam'].lower()}-u{int(time.time()*1000)}-{len(stored)}"
            stored.append(q)
            self.questions[q["id"]] = q
            added += 1
        if added:
            _write_json(self.user_file, stored)
        return added, errors

    def delete_user_question(self, qid: str) -> bool:
        stored = _read_json(self.user_file, [])
        kept = [q for q in stored if q.get("id") != qid]
        if len(kept) == len(stored):
            return False
        _write_json(self.user_file, kept)
        self.questions.pop(qid, None)
        return True


class Stats:
    """Soru bazında deneme geçmişi ve oturum geçmişi."""

    def __init__(self, data_dir: Path = DATA_DIR):
        self.path = Path(data_dir) / "stats.json"
        data = _read_json(self.path, {})
        self.questions: dict = data.get("questions", {})
        self.sessions: list = data.get("sessions", [])

    def save(self) -> None:
        _write_json(self.path, {"questions": self.questions, "sessions": self.sessions[-500:]})

    def record_answer(self, qid: str, correct: bool) -> None:
        s = self.questions.setdefault(qid, {"seen": 0, "correct": 0, "streak": 0, "last": 0})
        s["seen"] += 1
        s["last"] = int(time.time())
        s["correct"] += int(correct)
        s["streak"] = s["streak"] + 1 if correct else 0
        s["wrong_last"] = not correct

    def record_session(self, summary: dict) -> None:
        self.sessions.append(summary)
        self.save()

    def get(self, qid: str) -> dict:
        return self.questions.get(qid, {"seen": 0, "correct": 0, "streak": 0, "last": 0})

    def weak_ids(self, qids) -> list[str]:
        """Son denemede yanlış yapılan veya başarı oranı < %60 olan sorular."""
        out = []
        for qid in qids:
            s = self.questions.get(qid)
            if s and s["seen"] and (s.get("wrong_last") or s["correct"] / s["seen"] < 0.6):
                out.append(qid)
        return out

    def reset(self) -> None:
        self.questions, self.sessions = {}, []
        self.save()


class Settings:
    DEFAULTS = {"last_exam": "ACE", "language": "tr"}  # language: tr | en | bi

    def __init__(self, data_dir: Path = DATA_DIR):
        self.path = Path(data_dir) / "settings.json"
        self.data = {**self.DEFAULTS, **_read_json(self.path, {})}

    def __getitem__(self, k):
        return self.data[k]

    def __setitem__(self, k, v):
        self.data[k] = v

    def save(self) -> None:
        _write_json(self.path, self.data)
