"""Arayüz metinleri (Türkçe / English).

Soru içerikleri ayrıca soru dosyasında iki dillidir; bu modül yalnızca menü,
düğme ve mesaj metinlerini içerir.
"""
from __future__ import annotations

import re

UI_LANGS = ("tr", "en")

# anahtar: (Türkçe, English)
STRINGS: dict[str, tuple[str, str]] = {
    "app_title": ("GCP ACE Exam Trainer — Associate Cloud Engineer Sınav Pratiği",
                  "GCP ACE Exam Trainer — Associate Cloud Engineer Exam Practice"),
    "subtitle": ("Associate Cloud Engineer sınav pratiği • v{v}", "Associate Cloud Engineer exam practice • v{v}"),
    "all": ("Tümü", "All"),
    "btn_reset": ("İlerlemeyi sıfırla", "Reset progress"),
    "btn_import": ("JSON içe aktar", "Import JSON"),
    "btn_bank": ("Soru bankası", "Question bank"),
    "new_session": ("Yeni oturum", "New session"),
    "lbl_exam": ("Sınav", "Exam"),
    "lbl_qlang": ("Soru dili", "Question language"),
    "lbl_mode": ("Mod", "Mode"),
    "lbl_count": ("Soru sayısı", "Questions"),
    "lbl_domain": ("Alan (domain)", "Domain"),
    "lbl_topic": ("Konu", "Topic"),
    "lbl_focus": ("Odak", "Focus"),
    "lbl_source": ("Kaynak", "Source"),
    "timed_practice": ("Pratikte de süre tut", "Timed practice"),
    "btn_start": ("▶  Başla", "▶  Start"),
    "tip": ("İpucu: 1-5 tuşlarıyla seçenek seçip Enter ile kontrol edebilir, ← → ile sorular arasında "
            "gezebilir, T ile o sorunun dilini Türkçe ⇄ English değiştirebilirsiniz. Gerçek sınav "
            "İngilizce olacağı için sınava yaklaştıkça English modunda çalışmanız önerilir.",
            "Tip: press 1-5 to pick an option and Enter to check, use ← → to move between questions, "
            "and T to switch the current question between English ⇄ Turkish. The real exam is in "
            "English, so practise in English mode as the exam gets closer."),
    "progress": ("İlerlemeniz", "Your progress"),
    "by_domain": ("Alan bazında başarı", "Score by domain"),
    "recent": ("Son oturumlar", "Recent sessions"),
    "col_date": ("Tarih", "Date"),
    "col_mode": ("Mod", "Mode"),
    "col_score": ("Puan", "Score"),
    "bank_warn_title": ("Soru bankası", "Question bank"),
    "bank_warn": ("Bazı sorular yüklenemedi:", "Some questions could not be loaded:"),
    "bank_info": ("Bankada {total} soru var ({builtin} hazır, {user} eklenen). Gördüğünüz: {seen} • "
                  "Tekrar etmeniz gereken: {weak}. Gerçek sınav: ~{qc} soru / {mins} dk.",
                  "{total} questions in the bank ({builtin} built-in, {user} imported). Seen: {seen} • "
                  "To review: {weak}. Real exam: ~{qc} questions / {mins} min."),
    "bank_empty": ("{code} için henüz soru yok. 'JSON içe aktar' ile soru ekleyebilirsiniz.",
                   "No questions for {code} yet. Use 'Import JSON' to add some."),
    "overall": ("{n} cevap • Başarı {acc}", "{n} answers • Score {acc}"),
    "no_questions": ("Soru yok", "No questions"),
    "reset_title": ("Sıfırla", "Reset"),
    "reset_ask": ("Tüm ilerleme ve oturum geçmişi silinsin mi?", "Delete all progress and session history?"),
    "pick_file": ("Soru dosyası seç", "Choose a question file"),
    "import_title": ("İçe aktarma", "Import"),
    "import_added": ("{n} soru eklendi.", "{n} questions added."),
    "import_skipped": ("{n} soru atlandı:", "{n} questions skipped:"),
    # modlar, odak, kaynak, dil
    "mode_pratik": ("Pratik (anında geri bildirim)", "Practice (instant feedback)"),
    "mode_sinav": ("Sınav simülasyonu (süreli)", "Exam simulation (timed)"),
    "mode_short_pratik": ("Pratik", "Practice"),
    "mode_short_sinav": ("Sınav", "Exam"),
    "focus_karisik": ("Akıllı karışık (zayıflara öncelik)", "Smart mix (weak questions first)"),
    "focus_zayif": ("Yalnızca yanlış yaptıklarım", "Only ones I got wrong"),
    "focus_yeni": ("Yalnızca hiç görmediklerim", "Only unseen ones"),
    "src_all": ("Tüm sorular", "All questions"),
    "src_builtin": ("Hazır sorular", "Built-in questions"),
    "src_user": ("İçe aktarılanlar", "Imported"),
    "srclabel_builtin": ("Hazır", "Built-in"),
    "srclabel_ice-aktarim": ("İçe aktarım", "Imported"),
    "qlang_tr": ("Türkçe", "Turkish"),
    "qlang_en": ("English", "English"),
    "qlang_bi": ("İki dilli (İngilizce + Türkçe)", "Bilingual (English + Turkish)"),
    # soru ekranı
    "q_pos": ("Soru {i} / {n}", "Question {i} / {n}"),
    "meta_domain": ("Alan {k}: {name}", "Domain {k}: {name}"),
    "meta_topic": ("Konu: {t}", "Topic: {t}"),
    "meta_diff": ("Zorluk: {d}", "Difficulty: {d}"),
    "meta_source": ("Kaynak: {s}", "Source: {s}"),
    "meta_flagged": ("⚑ işaretli", "⚑ flagged"),
    "score_practice": ("Doğru: {ok} / {n}", "Correct: {ok} / {n}"),
    "score_exam": ("Cevaplanan: {a} / {n} • İşaretli: {f}", "Answered: {a} / {n} • Flagged: {f}"),
    "btn_prev": ("⟵ Önceki", "⟵ Previous"),
    "btn_flag": ("⚑ İşaretle", "⚑ Flag"),
    "btn_unflag": ("⚑ İşareti kaldır", "⚑ Unflag"),
    "btn_nav": ("☰ Soru listesi", "☰ Question list"),
    "btn_finish": ("Bitir", "Finish"),
    "btn_next": ("Sonraki ⟶", "Next ⟶"),
    "btn_check": ("Kontrol et ✓", "Check ✓"),
    "btn_finish_last": ("Bitir ⏹", "Finish ⏹"),
    "answer_title": ("Cevap", "Answer"),
    "answer_pick": ("Lütfen bir seçenek seçin.", "Please choose an option."),
    "answer_count": ("Bu soru {need} seçenek istiyor; siz {got} seçtiniz. Yine de kontrol edilsin mi?",
                     "This question needs {need} options; you chose {got}. Check anyway?"),
    "fb_right": ("✓ Doğru!", "✓ Correct!"),
    "fb_wrong": ("✗ Yanlış. Doğru cevap: {ans}", "✗ Wrong. Correct answer: {ans}"),
    "no_expl": ("(Açıklama yok)", "(No explanation)"),
    "source_line": ("Kaynak: {url}", "Source: {url}"),
    "nav_title": ("Soru listesi", "Question list"),
    "nav_hint": ("Bir soruya gitmek için tıklayın.  ● cevaplandı  ⚑ işaretli",
                 "Click a question to jump to it.  ● answered  ⚑ flagged"),
    "time_up_title": ("Süre doldu", "Time is up"),
    "time_up": ("Süre doldu! Sonuçlar gösteriliyor.", "Time is up! Showing your results."),
    "finish_ask": ("Oturumu bitirmek istiyor musunuz?", "Do you want to finish the session?"),
    "finish_unanswered": ("{n} soru cevaplanmadı. Yine de bitirilsin mi?",
                          "{n} questions are unanswered. Finish anyway?"),
    # sonuç ekranı
    "results": ("Sonuçlar", "Results"),
    "passed": ("GEÇTİNİZ 🎉", "PASSED 🎉"),
    "below": ("Hedefin altında", "Below target"),
    "result_line": ("{c} / {t} doğru • Süre {time} • Hedef: %{p} (Google resmi geçme notunu açıklamaz; "
                    "%70+ güvenli kabul edilir)",
                    "{c} / {t} correct • Time {time} • Target: {p}% (Google does not publish the passing "
                    "score; 70%+ is considered safe)"),
    "res_domains": ("Alan bazında", "By domain"),
    "res_list": ("Sorular (incelemek için çift tıklayın)", "Questions (double-click to review)"),
    "col_result": ("Sonuç", "Result"),
    "col_question": ("Soru", "Question"),
    "blank": ("— boş", "— blank"),
    "btn_home": ("⌂ Ana sayfa", "⌂ Home"),
    "btn_retry": ("↻ Yanlış/boş soruları tekrar çöz ({n})", "↻ Retry wrong/blank questions ({n})"),
    "your_answer": ("  ← sizin cevabınız", "  ← your answer"),
    "review_title": ("Soru {i} — inceleme", "Question {i} — review"),
    "btn_close": ("Kapat", "Close"),
    "view_meta": ("{code} • Alan {k}: {name} • {topic} • {diff}", "{code} • Domain {k}: {name} • {topic} • {diff}"),
    # soru bankası
    "lbl_search": ("Ara", "Search"),
    "btn_export": ("JSON olarak dışa aktar", "Export as JSON"),
    "col_id": ("ID", "ID"),
    "col_domain": ("Alan", "Domain"),
    "col_topic": ("Konu", "Topic"),
    "col_diff": ("Zorluk", "Difficulty"),
    "col_source": ("Kaynak", "Source"),
    "col_success": ("Başarı", "Score"),
    "bank_hint": ("Çift tıklayarak soruyu görüntüleyin. Yalnızca içe aktarılan sorular silinebilir.",
                  "Double-click to view a question. Only imported questions can be deleted."),
    "btn_delete": ("Seçileni sil", "Delete selected"),
    "n_questions": ("{n} soru", "{n} questions"),
    "delete_title": ("Sil", "Delete"),
    "delete_builtin": ("Hazır sorular silinemez.", "Built-in questions cannot be deleted."),
    "delete_ask": ("Bu soru kalıcı olarak silinsin mi?", "Delete this question permanently?"),
    "export_title": ("Dışa aktar", "Export"),
    "export_done": ("{n} soru kaydedildi.", "{n} questions saved."),
    "export_file": ("{code}_sorular.json", "{code}_questions.json"),
}

# Resmi sınav rehberindeki İngilizce bölüm adları
DOMAIN_EN = {
    "ACE": {
        1: "Setting up a cloud solution environment",
        2: "Planning and implementing a cloud solution",
        3: "Ensuring the successful operation of a cloud solution",
        4: "Configuring access and security",
    },
}

TOPIC_EN = {
    "Kaynak hiyerarşisi ve faturalandırma": "Resource hierarchy and billing",
    "gcloud ve Cloud Shell": "gcloud and Cloud Shell",
    "IAM ve servis hesapları": "IAM and service accounts",
    "Compute Engine": "Compute Engine",
    "Instance group ve yük dengeleme": "Instance groups and load balancing",
    "GKE (Kubernetes)": "GKE (Kubernetes)",
    "Serverless (Cloud Run, Functions, App Engine)": "Serverless (Cloud Run, Functions, App Engine)",
    "Cloud Storage": "Cloud Storage",
    "Veritabanları": "Databases",
    "VPC ve ağ": "VPC and networking",
    "Logging ve Monitoring": "Logging and Monitoring",
    "Veri ve analitik": "Data and analytics",
    "IaC ve DevOps": "IaC and DevOps",
    "Gemini ve yapay zekâ araçları": "Gemini and AI tools",
}

DIFF_EN = {"kolay": "easy", "orta": "medium", "zor": "hard"}

# store/engine hata mesajlarının İngilizce karşılıkları (desen, yerine)
_ERRORS_EN = [
    (r"'([^']*)' metin olmalı", r"'\1' must be text"),
    (r"'([^']*)' çok uzun", r"'\1' is too long"),
    (r"'([^']*)' 2-8 arası seçenek olmalı", r"'\1' must have 2-8 options"),
    (r"Seçenekler boş veya tekrarlı olamaz", "Options cannot be empty or duplicated"),
    (r"Soru bir nesne olmalı", "Each question must be an object"),
    (r"Soru metni boş", "Question text is empty"),
    (r"Doğru cevap indeksleri geçersiz", "Invalid correct-answer indexes"),
    (r"Bilinmeyen sınav: ", "Unknown exam: "),
    (r"Dosya okunamadı: ", "Could not read file: "),
    (r"Dosya çok büyük \((\d+) KB\); en fazla (\d+) MB olabilir\.", r"File is too large (\1 KB); the limit is \2 MB."),
    (r"Dosya çok derin iç içe yapı içeriyor\.", "The file is nested too deeply."),
    (r"Geçerli bir UTF-8 JSON dosyası değil: ", "Not a valid UTF-8 JSON file: "),
    (r"Dosya bir soru listesi içermeli\.", "The file must contain a list of questions."),
    (r"Tek seferde en fazla (\d+) soru içe aktarılabilir\.", r"At most \1 questions can be imported at once."),
    (r"zaten bankada var", "already in the bank"),
    (r"Bu filtrelerle uygun soru bulunamadı\.", "No questions match these filters."),
]


def norm_lang(lang) -> str:
    return lang if lang in UI_LANGS else "tr"


def t(key: str, lang: str, **kw) -> str:
    text = STRINGS[key][1 if lang == "en" else 0]
    return text.format(**kw) if kw else text


def domain_name(exam, k: int, lang: str) -> str:
    if lang == "en":
        name = DOMAIN_EN.get(exam.code, {}).get(k)
        if name:
            return name
    return exam.domain_name(k)


def topic_name(topic: str, lang: str) -> str:
    return TOPIC_EN.get(topic, topic) if lang == "en" else topic


def difficulty(d: str, lang: str) -> str:
    return DIFF_EN.get(d, d) if lang == "en" else d


def error(msg: str, lang: str) -> str:
    """Çekirdek modüllerden gelen (Türkçe) hata mesajını arayüz diline çevirir."""
    if lang != "en":
        return msg
    for pat, rep in _ERRORS_EN:
        msg = re.sub(pat, rep, msg)
    return msg
