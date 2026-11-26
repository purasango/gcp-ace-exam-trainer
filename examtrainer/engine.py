"""Sınav oturumu: soru seçimi, karıştırma, puanlama."""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from .exams import EXAMS
from .store import QuestionBank, Stats, localized

PASS_PERCENT = 70  # Google geçme notunu açıklamaz; %70 yaygın kabul edilen hedeftir.


@dataclass
class Item:
    q: dict
    order: list[int]  # ekrandaki sıra -> orijinal seçenek indeksi

    @property
    def options(self) -> list[str]:
        return self.options_in("tr")

    def options_in(self, lang: str) -> list[str]:
        opts = localized(self.q, lang)["options"]
        return [opts[i] for i in self.order]

    @property
    def correct(self) -> set[int]:
        """Doğru cevapların ekrandaki indeksleri."""
        return {d for d, orig in enumerate(self.order) if orig in self.q["correct"]}

    @property
    def multi(self) -> bool:
        return len(self.q["correct"]) > 1


@dataclass
class QuizSession:
    exam_code: str
    mode: str  # "pratik" | "sinav"
    items: list[Item]
    time_limit: int | None = None  # saniye
    answers: dict[int, set[int]] = field(default_factory=dict)
    flagged: set[int] = field(default_factory=set)
    started: float = field(default_factory=time.time)
    finished: float | None = None
    recorded: set[int] = field(default_factory=set)  # istatistiğe yazılmış cevaplar

    def is_correct(self, idx: int) -> bool:
        return self.answers.get(idx, set()) == self.items[idx].correct

    def answer(self, idx: int, selection) -> bool:
        self.answers[idx] = set(selection)
        return self.is_correct(idx)

    def record(self, idx: int, stats: Stats) -> None:
        """Cevabı istatistiğe bir kez yazıp diske kaydeder (pratikte kontrol anında);
        oturum yarıda kapansa da ilerleme kaybolmaz."""
        if idx in self.recorded or idx not in self.answers:
            return
        self.recorded.add(idx)
        stats.record_answer(self.items[idx].q["id"], self.is_correct(idx))
        stats.save()

    def remaining(self) -> int | None:
        if self.time_limit is None:
            return None
        return max(0, int(self.time_limit - (time.time() - self.started)))

    def finish(self, stats: Stats | None = None) -> dict:
        if self.finished is None:
            self.finished = time.time()
            if stats is not None:
                for i, it in enumerate(self.items):
                    if i in self.answers and i not in self.recorded:
                        self.recorded.add(i)
                        stats.record_answer(it.q["id"], self.is_correct(i))
        exam = EXAMS[self.exam_code]
        per_domain: dict[int, list[int]] = {}
        for i, it in enumerate(self.items):
            d = per_domain.setdefault(it.q["domain"], [0, 0])
            d[1] += 1
            d[0] += int(self.is_correct(i))
        correct = sum(self.is_correct(i) for i in range(len(self.items)))
        total = len(self.items)
        pct = round(100 * correct / total) if total else 0
        summary = {
            "exam": self.exam_code,
            "mode": self.mode,
            "date": time.strftime("%Y-%m-%d %H:%M", time.localtime(self.started)),
            "total": total,
            "answered": len(self.answers),
            "correct": correct,
            "percent": pct,
            "passed": pct >= PASS_PERCENT,
            "seconds": int(self.finished - self.started),
            "domains": {exam.domain_name(k): v for k, v in sorted(per_domain.items())},
        }
        if stats is not None:
            stats.record_session(summary)
        return summary


def _pick_weighted(pool: list[dict], n: int, stats: Stats, rng: random.Random) -> list[dict]:
    """Görülmemiş ve zayıf sorulara öncelik veren ağırlıklı seçim (tekrarsız)."""
    def weight(q):
        s = stats.get(q["id"])
        if s["seen"] == 0:
            return 3.0
        acc = s["correct"] / s["seen"]
        w = 1.0 + 3.0 * (1 - acc) + (2.0 if s.get("wrong_last") else 0)
        return w / (1 + s["streak"])
    # Efraimidis-Spirakis ağırlıklı örnekleme
    keyed = sorted(pool, key=lambda q: rng.random() ** (1.0 / weight(q)), reverse=True)
    return keyed[:n]


def build_session(bank: QuestionBank, stats: Stats, exam_code: str, n: int,
                  mode: str = "pratik", domains=None, focus: str = "karisik",
                  sources=None, timed: bool | None = None, seed=None,
                  topics=None) -> QuizSession:
    """focus: 'karisik' (akıllı karışık), 'zayif' (yanlış yapılanlar), 'yeni' (hiç görülmemiş)."""
    rng = random.Random(seed)
    exam = EXAMS[exam_code]
    pool = bank.for_exam(exam_code, domains, sources, topics)
    if focus == "zayif":
        weak = set(stats.weak_ids(q["id"] for q in pool))
        pool = [q for q in pool if q["id"] in weak]
    elif focus == "yeni":
        pool = [q for q in pool if stats.get(q["id"])["seen"] == 0]
    if not pool:
        raise ValueError("Bu filtrelerle uygun soru bulunamadı.")
    n = min(n, len(pool))

    if mode == "sinav" and not domains and not topics:
        # Alan ağırlıklarına göre dağıt
        by_dom: dict[int, list[dict]] = {}
        for q in pool:
            by_dom.setdefault(q["domain"], []).append(q)
        total_w = sum(exam.domains[d][1] for d in by_dom)
        chosen = []
        for d, qs in by_dom.items():
            k = min(len(qs), round(n * exam.domains[d][1] / total_w))
            chosen += _pick_weighted(qs, k, stats, rng)
        rest = [q for q in pool if q not in chosen]
        chosen = chosen[:n] + _pick_weighted(rest, max(0, n - len(chosen)), stats, rng)
    else:
        chosen = _pick_weighted(pool, n, stats, rng)
    rng.shuffle(chosen)

    items = []
    for q in chosen:
        order = list(range(len(q["options"])))
        rng.shuffle(order)
        items.append(Item(q, order))

    if timed is None:
        timed = mode == "sinav"
    limit = None
    if timed:
        # Gerçek sınavın soru başına süresiyle orantılı
        limit = int(exam.minutes * 60 * len(items) / exam.question_count)
    return QuizSession(exam_code, mode, items, limit)
