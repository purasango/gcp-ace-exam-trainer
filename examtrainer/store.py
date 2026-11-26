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


# İçe aktarma ve kayıtlı veri için üst sınırlar (kötü niyetli/bozuk dosyaya karşı).
MAX_IMPORT_BYTES = 5 * 1024 * 1024
MAX_IMPORT_QUESTIONS = 2000
_MAX_LEN = {"question": 4000, "option": 1000, "explanation": 8000, "topic": 200,
            "source_url": 2000, "check": 300, "short": 100}


def _read_json(path: Path, default):
    """JSON dosyasını okur. Dosya yoksa, bozuksa veya beklenen türde (default'un türü) değilse
    default döner; bozuk dosya kaybolmasın diye yedeklenir."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return default
    except (ValueError, OSError, RecursionError):  # JSONDecodeError/UnicodeDecodeError ValueError'dur
        data = None
    if isinstance(data, type(default)):
        return data
    try:
        path.rename(path.with_suffix(path.suffix + f".bozuk-{time.time_ns()}"))
    except OSError:
        pass
    return default


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class ValidationError(ValueError):
    pass


def _text(value, field: str, limit: str, default: str | None = None) -> str:
    """Metin alanını doğrular: str (veya bool olmayan sayı) olmalı ve uzunluk sınırını aşmamalı."""
    if value is None and default is not None:
        return default
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValidationError(f"'{field}' metin olmalı")
    value = str(value).strip()
    if len(value) > _MAX_LEN[limit]:
        raise ValidationError(f"'{field}' çok uzun")
    return value


def _options(raw, field: str) -> list[str]:
    if not isinstance(raw, list) or not 2 <= len(raw) <= 8:
        raise ValidationError(f"'{field}' 2-8 arası seçenek olmalı")
    opts = [_text(o, field, "option") for o in raw]
    if any(not o for o in opts) or len(set(opts)) != len(opts):
        raise ValidationError("Seçenekler boş veya tekrarlı olamaz")
    return opts


def _english(en, n_options: int):
    """İsteğe bağlı İngilizce karşılık; eksik veya hatalıysa None (soru Türkçe gösterilir)."""
    if not isinstance(en, dict):
        return None
    try:
        question = _text(en.get("question"), "en.question", "question", "")
        options = _options(en.get("options"), "en.options")
        explanation = _text(en.get("explanation"), "en.explanation", "explanation", "")
    except ValidationError:
        return None
    if not question or len(options) != n_options:
        return None
    return {"question": question, "options": options, "explanation": explanation}


def validate_question(q: dict, exam_code: str | None = None) -> dict:
    """Bir soruyu doğrular ve normalize edilmiş kopyasını döndürür.
    Hatalı her girdi için yalnızca ValidationError fırlatır."""
    if not isinstance(q, dict):
        raise ValidationError("Soru bir nesne olmalı")
    text = _text(q.get("question"), "question", "question", "")
    if not text:
        raise ValidationError("Soru metni boş")
    options = _options(q.get("options"), "options")
    correct = q.get("correct")
    if isinstance(correct, int) and not isinstance(correct, bool):
        correct = [correct]
    if (not isinstance(correct, list) or not correct
            or not all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c < len(options) for c in correct)
            or len(set(correct)) != len(correct) or len(correct) >= len(options)):
        raise ValidationError("Doğru cevap indeksleri geçersiz")
    exam = q.get("exam") or exam_code or ""
    if not isinstance(exam, str):
        raise ValidationError("'exam' metin olmalı")
    exam = exam.upper()
    if exam not in EXAMS:
        raise ValidationError(f"Bilinmeyen sınav: {exam[:20]!r}")
    domain = q.get("domain", 1)
    if isinstance(domain, bool) or not isinstance(domain, (int, str)):
        domain = 1
    try:
        domain = int(domain)
    except ValueError:
        domain = 1
    if domain not in EXAMS[exam].domains:
        domain = min(EXAMS[exam].domains)
    diff = q.get("difficulty", "orta")
    diff = diff.lower() if isinstance(diff, str) else "orta"
    if diff not in DIFFICULTIES:
        diff = "orta"
    checks = q.get("check")
    checks = [_text(c, "check", "check") for c in checks[:20]] if isinstance(checks, list) else []
    return {
        "id": _text(q.get("id"), "id", "short", ""),
        "exam": exam,
        "domain": domain,
        "difficulty": diff,
        "topic": _text(q.get("topic"), "topic", "topic", ""),
        "question": text,
        "options": options,
        "correct": sorted(correct),
        "explanation": _text(q.get("explanation"), "explanation", "explanation", ""),
        "source": _text(q.get("source"), "source", "short", "builtin") or "builtin",
        "source_url": _text(q.get("source_url"), "source_url", "source_url", ""),
        "objective": _text(q.get("objective"), "objective", "short", ""),
        "check": checks,
        "created": _text(q.get("created"), "created", "short", ""),
        "en": _english(q.get("en"), len(options)),
    }


def load_import_file(path) -> list:
    """Kullanıcının seçtiği soru dosyasını güvenli sınırlarla okur; sorun varsa ValidationError."""
    try:
        size = os.path.getsize(path)
    except OSError as e:
        raise ValidationError(f"Dosya okunamadı: {e}") from e
    if size > MAX_IMPORT_BYTES:
        raise ValidationError(f"Dosya çok büyük ({size // 1024} KB); en fazla {MAX_IMPORT_BYTES // (1024 * 1024)} MB olabilir.")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except OSError as e:
        raise ValidationError(f"Dosya okunamadı: {e}") from e
    except RecursionError as e:
        raise ValidationError("Dosya çok derin iç içe yapı içeriyor.") from e
    except ValueError as e:  # JSONDecodeError ve UnicodeDecodeError
        raise ValidationError(f"Geçerli bir UTF-8 JSON dosyası değil: {e}") from e
    if isinstance(data, dict):
        data = data.get("questions", [])
    if not isinstance(data, list):
        raise ValidationError("Dosya bir soru listesi içermeli.")
    if len(data) > MAX_IMPORT_QUESTIONS:
        raise ValidationError(f"Tek seferde en fazla {MAX_IMPORT_QUESTIONS} soru içe aktarılabilir.")
    return data


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
            qid = raw.get("id", "?") if isinstance(raw, dict) else "?"
            self.load_errors.append(f"{str(qid)[:40]}: {e}")
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
        qs = data.get("questions")
        self.questions: dict = {k: v for k, v in qs.items() if self._valid_entry(v)} if isinstance(qs, dict) else {}
        ss = data.get("sessions")
        self.sessions: list = [x for x in ss if self._valid_session(x)] if isinstance(ss, list) else []

    @staticmethod
    def _valid_entry(v) -> bool:
        return (isinstance(v, dict)
                and all(isinstance(v.get(k), int) and not isinstance(v.get(k), bool)
                        for k in ("seen", "correct", "streak", "last")))

    @staticmethod
    def _valid_session(x) -> bool:
        return (isinstance(x, dict) and isinstance(x.get("exam"), str) and isinstance(x.get("date"), str)
                and isinstance(x.get("mode"), str) and isinstance(x.get("passed"), bool)
                and all(isinstance(x.get(k), int) and not isinstance(x.get(k), bool)
                        for k in ("percent", "correct", "total")))

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
        stored = _read_json(self.path, {})
        # Yalnızca bilinen ve metin türündeki ayarlar alınır.
        self.data = {**self.DEFAULTS, **{k: v for k, v in stored.items()
                                         if k in self.DEFAULTS and isinstance(v, str)}}

    def __getitem__(self, k):
        return self.data[k]

    def __setitem__(self, k, v):
        self.data[k] = v

    def save(self) -> None:
        _write_json(self.path, self.data)
