"""Tkinter masaüstü arayüzü."""
from __future__ import annotations

import json
import sys
import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk

from . import __version__
from .engine import PASS_PERCENT, QuizSession, build_session
from .exams import EXAMS
from .store import QuestionBank, Settings, Stats, localized

APP_TITLE = "GCP ACE Exam Trainer — Associate Cloud Engineer Sınav Pratiği"
ALL = "Tümü"
MODES = {"Pratik (anında geri bildirim)": "pratik", "Sınav simülasyonu (süreli)": "sinav"}
FOCUS = {"Akıllı karışık (zayıflara öncelik)": "karisik",
         "Yalnızca yanlış yaptıklarım": "zayif",
         "Yalnızca hiç görmediklerim": "yeni"}
SOURCES = {"Tüm sorular": None, "Hazır sorular": ["builtin"], "İçe aktarılanlar": ["ice-aktarim"]}
SOURCE_LABEL = {"builtin": "Hazır", "ice-aktarim": "İçe aktarım"}
LANGS = {"Türkçe": "tr", "English": "en", "İki dilli (İngilizce + Türkçe)": "bi"}


def primary_lang(setting: str) -> str:
    """Ayardaki dil için soruların ana gösterim dili."""
    return "tr" if setting == "tr" else "en"


def insert_question(txt: tk.Text, q: dict, setting: str, order=None, correct=None, sel=frozenset()):
    """Bir soruyu (gerekirse iki dilde) Text widget'ına yazar."""
    langs = ["tr"] if setting == "tr" else (["en"] if setting == "en" else ["en", "tr"])
    if not q.get("en"):
        langs = ["tr"]
    order = order if order is not None else list(range(len(q["options"])))
    correct = correct if correct is not None else set(q["correct"])
    for n, lang in enumerate(langs):
        loc = localized(q, lang)
        if len(langs) > 1:
            txt.insert("end", ("\n" if n else "") + ("English" if lang == "en" else "Türkçe") + "\n", "lang")
        txt.insert("end", loc["question"] + "\n", "q")
        for i, orig in enumerate(order):
            tag = "ok" if i in correct else ("bad" if i in sel else "")
            mark = "  ← sizin cevabınız" if i in sel else ""
            txt.insert("end", f"{chr(65 + i)}. {loc['options'][orig]}{mark}\n", tag)
        txt.insert("end", "\nAçıklama\n" if lang == "tr" else "\nExplanation\n", "h")
        txt.insert("end", (loc["explanation"] or "(Açıklama yok)") + "\n")
    if q.get("source_url"):
        txt.insert("end", f"\nKaynak: {q['source_url']}")


def make_text(win, app) -> tk.Text:
    txt = tk.Text(win, wrap="word", font=app.f_opt, padx=14, pady=12, relief="flat")
    txt.pack(fill="both", expand=True)
    txt.tag_configure("q", font=app.f_q, spacing3=10)
    txt.tag_configure("ok", foreground=GREEN, background=GREEN_BG)
    txt.tag_configure("bad", foreground=RED, background=RED_BG)
    txt.tag_configure("h", font=app.f_h2, spacing1=12)
    txt.tag_configure("lang", font=app.f_h2, foreground="#1a73e8", spacing1=6, spacing3=4)
    return txt

GREEN, RED, AMBER = "#1e8e3e", "#d93025", "#f9ab00"
GREEN_BG, RED_BG = "#e6f4ea", "#fce8e6"


def fmt_time(sec: int) -> str:
    h, rem = divmod(max(0, int(sec)), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1100x760")
        self.minsize(880, 600)
        self.settings = Settings()
        self.bank = QuestionBank()
        self.stats = Stats()
        self._setup_style()
        self.container = ttk.Frame(self)
        self.container.pack(fill="both", expand=True)
        self.screen = None
        self.show_home()

    def _setup_style(self):
        style = ttk.Style(self)
        if sys.platform not in ("win32", "darwin"):
            style.theme_use("clam")
        base = tkfont.nametofont("TkDefaultFont")
        base.configure(size=11)
        tkfont.nametofont("TkTextFont").configure(size=11)
        fam = base.actual("family")
        self.f_title = (fam, 18, "bold")
        self.f_h2 = (fam, 13, "bold")
        self.f_q = (fam, 13)
        self.f_opt = (fam, 12)
        self.f_small = (fam, 10)
        style.configure("Title.TLabel", font=self.f_title)
        style.configure("H2.TLabel", font=self.f_h2)
        style.configure("Muted.TLabel", foreground="#5f6368")
        style.configure("Big.TButton", font=(fam, 12, "bold"), padding=(14, 8))
        style.configure("Treeview", rowheight=26)

    def switch(self, frame_cls, *args):
        if self.screen is not None:
            self.screen.destroy()
        self.screen = frame_cls(self.container, self, *args)
        self.screen.pack(fill="both", expand=True)

    def show_home(self):
        self.switch(HomeScreen)

    def start_session(self, session: QuizSession):
        self.switch(QuizScreen, session)

    def show_results(self, session: QuizSession, summary: dict):
        self.switch(ResultScreen, session, summary)


# ----------------------------------------------------------------------------- Ana ekran
class HomeScreen(ttk.Frame):
    def __init__(self, parent, app: App):
        super().__init__(parent, padding=20)
        self.app = app
        exam_code = app.settings["last_exam"] if app.settings["last_exam"] in EXAMS else "ACE"

        head = ttk.Frame(self)
        head.pack(fill="x")
        titles = ttk.Frame(head)
        titles.pack(side="left")
        ttk.Label(titles, text="GCP ACE Exam Trainer", style="Title.TLabel").pack(anchor="w")
        ttk.Label(titles, text=f"Associate Cloud Engineer sınav pratiği • v{__version__}",
                  style="Muted.TLabel").pack(anchor="w")
        for txt, cmd in (("İlerlemeyi sıfırla", self.reset_stats), ("JSON içe aktar", self.import_json),
                         ("Soru bankası", self.open_bank)):
            ttk.Button(head, text=txt, command=cmd).pack(side="right", padx=4)

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, pady=(16, 0))
        body.columnconfigure(0, weight=3, uniform="c")
        body.columnconfigure(1, weight=2, uniform="c")
        body.rowconfigure(0, weight=1)

        # --- Sol: oturum kurulumu
        left = ttk.LabelFrame(body, text="Yeni oturum", padding=14)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.columnconfigure(1, weight=1)

        self.v_exam = tk.StringVar(value=self._exam_label(exam_code))
        self.v_mode = tk.StringVar(value=list(MODES)[0])
        self.v_count = tk.IntVar(value=20)
        self.v_domain = tk.StringVar(value=ALL)
        self.v_topic = tk.StringVar(value=ALL)
        self.v_focus = tk.StringVar(value=list(FOCUS)[0])
        self.v_source = tk.StringVar(value=list(SOURCES)[0])
        self.v_timed = tk.BooleanVar(value=False)
        inv = {v: k for k, v in LANGS.items()}
        self.v_lang = tk.StringVar(value=inv.get(app.settings["language"], "Türkçe"))

        r = 0

        def row(label, widget):
            nonlocal r
            ttk.Label(left, text=label).grid(row=r, column=0, sticky="w", pady=5, padx=(0, 10))
            widget.grid(row=r, column=1, sticky="ew", pady=5)
            r += 1

        self.cb_exam = ttk.Combobox(left, textvariable=self.v_exam, state="readonly",
                                    values=[self._exam_label(c) for c in EXAMS])
        self.cb_exam.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        row("Sınav", self.cb_exam)
        cb_lang = ttk.Combobox(left, textvariable=self.v_lang, state="readonly", values=list(LANGS))
        cb_lang.bind("<<ComboboxSelected>>", lambda e: self._save_lang())
        row("Soru dili", cb_lang)
        row("Mod", ttk.Combobox(left, textvariable=self.v_mode, state="readonly", values=list(MODES)))
        cnt = ttk.Frame(left)
        ttk.Spinbox(cnt, from_=5, to=200, increment=5, textvariable=self.v_count, width=6).pack(side="left")
        for n in (10, 20, 50):
            ttk.Button(cnt, text=str(n), width=4, command=lambda n=n: self.v_count.set(n)).pack(side="left", padx=2)
        ttk.Checkbutton(cnt, text="Pratikte de süre tut", variable=self.v_timed).pack(side="left", padx=10)
        row("Soru sayısı", cnt)
        self.cb_domain = ttk.Combobox(left, textvariable=self.v_domain, state="readonly")
        row("Alan (domain)", self.cb_domain)
        self.cb_topic = ttk.Combobox(left, textvariable=self.v_topic, state="readonly")
        row("Konu", self.cb_topic)
        row("Odak", ttk.Combobox(left, textvariable=self.v_focus, state="readonly", values=list(FOCUS)))
        row("Kaynak", ttk.Combobox(left, textvariable=self.v_source, state="readonly", values=list(SOURCES)))

        self.lbl_bank = ttk.Label(left, style="Muted.TLabel", wraplength=520, justify="left")
        self.lbl_bank.grid(row=r, column=0, columnspan=2, sticky="w", pady=(10, 4))
        r += 1
        btns = ttk.Frame(left)
        btns.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Button(btns, text="▶  Başla", style="Big.TButton", command=self.start).pack(side="left")
        r += 1
        tip = ("İpucu: 1-5 tuşlarıyla seçenek seçip Enter ile kontrol edebilir, ← → ile sorular "
               "arasında gezebilir, T ile o sorunun dilini Türkçe ⇄ English değiştirebilirsiniz. "
               "Gerçek sınav İngilizce olacağı için sınava yaklaştıkça English modunda çalışmanız önerilir.")
        ttk.Label(left, text=tip, style="Muted.TLabel", wraplength=520, justify="left").grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(16, 0))

        # --- Sağ: ilerleme
        right = ttk.LabelFrame(body, text="İlerlemeniz", padding=14)
        right.grid(row=0, column=1, sticky="nsew")
        self.lbl_overall = ttk.Label(right, font=self.app.f_h2, justify="left")
        self.lbl_overall.pack(anchor="w")
        ttk.Label(right, text="Alan bazında başarı", style="Muted.TLabel").pack(anchor="w", pady=(12, 2))
        self.dom_frame = ttk.Frame(right)
        self.dom_frame.pack(fill="x")
        ttk.Label(right, text="Son oturumlar", style="Muted.TLabel").pack(anchor="w", pady=(14, 2))
        self.tv_hist = ttk.Treeview(right, columns=("t", "m", "s"), show="headings", height=8)
        for c, t, w in (("t", "Tarih", 130), ("m", "Mod", 70), ("s", "Puan", 90)):
            self.tv_hist.heading(c, text=t)
            self.tv_hist.column(c, width=w, anchor="w")
        self.tv_hist.pack(fill="both", expand=True)

        if app.bank.load_errors:
            messagebox.showwarning("Soru bankası", "Bazı sorular yüklenemedi:\n" +
                                   "\n".join(app.bank.load_errors[:10]))
        self.refresh()

    # yardımcılar
    @staticmethod
    def _exam_label(code):
        e = EXAMS[code]
        return f"{e.code} — {e.name}"

    def _save_lang(self):
        self.app.settings["language"] = LANGS[self.v_lang.get()]
        self.app.settings.save()

    def exam_code(self):
        return self.v_exam.get().split(" — ")[0]

    def refresh(self):
        code = self.exam_code()
        exam = EXAMS[code]
        self.app.settings["last_exam"] = code
        self.app.settings.save()
        self.cb_domain["values"] = [ALL] + [f"{k}. {v[0]}" for k, v in exam.domains.items()]
        if self.v_domain.get() not in self.cb_domain["values"]:
            self.v_domain.set(ALL)
        topics = sorted({q["topic"] for q in self.app.bank.for_exam(code) if q["topic"]})
        self.cb_topic["values"] = [ALL] + topics
        if self.v_topic.get() not in self.cb_topic["values"]:
            self.v_topic.set(ALL)
        c = self.app.bank.count(code)
        qs = self.app.bank.for_exam(code)
        seen = sum(1 for q in qs if self.app.stats.get(q["id"])["seen"])
        weak = len(self.app.stats.weak_ids(q["id"] for q in qs))
        if c["toplam"]:
            txt = (f"Bankada {c['toplam']} soru var ({c['hazir']} hazır, {c['eklenen']} eklenen). "
                   f"Gördüğünüz: {seen} • Tekrar etmeniz gereken: {weak}. "
                   f"Gerçek sınav: ~{exam.question_count} soru / {exam.minutes} dk.")
        else:
            txt = f"{exam.code} için henüz soru yok. 'JSON içe aktar' ile soru ekleyebilirsiniz."
        self.lbl_bank["text"] = txt

        # ilerleme paneli
        tot = sum(self.app.stats.get(q["id"])["seen"] for q in qs)
        cor = sum(self.app.stats.get(q["id"])["correct"] for q in qs)
        acc = f"%{round(100 * cor / tot)}" if tot else "—"
        self.lbl_overall["text"] = f"{tot} cevap • Başarı {acc}"
        for w in self.dom_frame.winfo_children():
            w.destroy()
        for k, (name, _w) in exam.domains.items():
            dq = [q for q in qs if q["domain"] == k]
            t = sum(self.app.stats.get(q["id"])["seen"] for q in dq)
            cc = sum(self.app.stats.get(q["id"])["correct"] for q in dq)
            pct = round(100 * cc / t) if t else 0
            fr = ttk.Frame(self.dom_frame)
            fr.pack(fill="x", pady=2)
            ttk.Label(fr, text=f"{k}. {name}", wraplength=260, justify="left").pack(anchor="w")
            bar = ttk.Frame(fr)
            bar.pack(fill="x")
            pb = ttk.Progressbar(bar, maximum=100, value=pct)
            pb.pack(side="left", fill="x", expand=True)
            ttk.Label(bar, text=f"%{pct} ({t})" if t else "—", width=10).pack(side="left", padx=4)
        self.tv_hist.delete(*self.tv_hist.get_children())
        for s in reversed([s for s in self.app.stats.sessions if s["exam"] == code][-30:]):
            mark = "✓" if s["passed"] else "✗"
            self.tv_hist.insert("", "end", values=(s["date"], s["mode"],
                                                   f"{mark} %{s['percent']} ({s['correct']}/{s['total']})"))

    def start(self):
        self._save_lang()
        code = self.exam_code()
        dom = self.v_domain.get()
        domains = None if dom == ALL else [int(dom.split(".")[0])]
        topics = None if self.v_topic.get() == ALL else [self.v_topic.get()]
        mode = MODES[self.v_mode.get()]
        try:
            n = max(1, int(self.v_count.get()))
        except (tk.TclError, ValueError):
            n = 20
        try:
            sess = build_session(self.app.bank, self.app.stats, code, n, mode, domains,
                                 FOCUS[self.v_focus.get()], SOURCES[self.v_source.get()],
                                 timed=True if self.v_timed.get() or mode == "sinav" else False,
                                 topics=topics)
        except ValueError as e:
            messagebox.showinfo("Soru yok", str(e))
            return
        self.app.start_session(sess)

    def open_bank(self):
        BankWindow(self.app, self.exam_code(), on_close=self.refresh)

    def reset_stats(self):
        if messagebox.askyesno("Sıfırla", "Tüm ilerleme ve oturum geçmişi silinsin mi?"):
            self.app.stats.reset()
            self.refresh()

    def import_json(self):
        path = filedialog.askopenfilename(title="Soru dosyası seç", filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            messagebox.showerror("İçe aktarma", f"Dosya okunamadı:\n{e}")
            return
        if isinstance(data, dict):
            data = data.get("questions", [])
        if not isinstance(data, list):
            messagebox.showerror("İçe aktarma", "Dosya bir soru listesi içermeli.")
            return
        added, errors = self.app.bank.add_user_questions(data, self.exam_code())
        msg = f"{added} soru eklendi."
        if errors:
            msg += f"\n{len(errors)} soru atlandı:\n" + "\n".join(errors[:12])
        messagebox.showinfo("İçe aktarma", msg)
        self.refresh()


# ----------------------------------------------------------------------------- Soru ekranı
class QuizScreen(ttk.Frame):
    def __init__(self, parent, app: App, session: QuizSession):
        super().__init__(parent, padding=(20, 14))
        self.app, self.s = app, session
        self.idx = 0
        self.checked: set[int] = set()  # pratik modunda kontrol edilen sorular
        self.exam = EXAMS[session.exam_code]

        top = ttk.Frame(self)
        top.pack(fill="x")
        self.lbl_pos = ttk.Label(top, style="H2.TLabel")
        self.lbl_pos.pack(side="left")
        self.lbl_timer = ttk.Label(top, style="H2.TLabel")
        self.lbl_timer.pack(side="right")
        self.lbl_score = ttk.Label(top, style="Muted.TLabel")
        self.lbl_score.pack(side="right", padx=16)
        self.progress = ttk.Progressbar(self, maximum=len(session.items))
        self.progress.pack(fill="x", pady=(6, 4))
        self.lbl_meta = ttk.Label(self, style="Muted.TLabel")
        self.lbl_meta.pack(anchor="w")

        # kaydırılabilir içerik
        mid = ttk.Frame(self)
        mid.pack(fill="both", expand=True, pady=(8, 8))
        self.canvas = tk.Canvas(mid, highlightthickness=0, bg=self._bg())
        sb = ttk.Scrollbar(mid, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=self._bg())
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.canvas.bind("<Configure>", self._on_resize)
        self.bind_all("<MouseWheel>", self._on_wheel)
        self.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-2, "units"))
        self.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(2, "units"))

        self.lang_setting = app.settings["language"]
        self.flip = False  # T tuşuyla o sorunun dilini geçici olarak değiştir
        self.lbl_q = tk.Label(self.inner, font=app.f_q, justify="left", anchor="w", bg=self._bg())
        self.lbl_q.pack(fill="x", pady=(0, 4))
        self.lbl_q2 = tk.Label(self.inner, font=app.f_opt, justify="left", anchor="w", bg=self._bg(),
                               fg="#5f6368")
        self.q_gap = tk.Frame(self.inner, height=10, bg=self._bg())
        self.q_gap.pack(fill="x")
        self.opt_frame = tk.Frame(self.inner, bg=self._bg())
        self.opt_frame.pack(fill="x")
        self.feedback = tk.Label(self.inner, font=app.f_opt, justify="left", anchor="w",
                                 bg=self._bg(), padx=12, pady=10)

        # alt düğmeler
        bot = ttk.Frame(self)
        bot.pack(fill="x")
        ttk.Button(bot, text="⟵ Önceki", command=lambda: self.go(-1)).pack(side="left")
        self.btn_flag = ttk.Button(bot, text="⚑ İşaretle", command=self.toggle_flag)
        self.btn_flag.pack(side="left", padx=6)
        self.btn_nav = ttk.Button(bot, text="☰ Soru listesi", command=self.open_navigator)
        self.btn_nav.pack(side="left")
        self.btn_lang = ttk.Button(bot, text="🌐 Dil (T)", command=self.toggle_lang)
        self.btn_lang.pack(side="left", padx=6)
        ttk.Button(bot, text="Bitir", command=self.finish).pack(side="right")
        self.btn_next = ttk.Button(bot, text="Sonraki ⟶", style="Big.TButton", command=self.primary)
        self.btn_next.pack(side="right", padx=6)

        self.vars: list = []
        self.radio_var = tk.IntVar(value=-1)
        self.opt_widgets: list[tk.Widget] = []

        for k in range(1, 9):
            self.app.bind(str(k), lambda e, k=k: self.key_select(k - 1))
        self.app.bind("<Return>", lambda e: self.primary())
        self.app.bind("<Right>", lambda e: self.go(1))
        self.app.bind("<Left>", lambda e: self.go(-1))
        self.app.bind("t", lambda e: self.toggle_lang())
        self.app.bind("T", lambda e: self.toggle_lang())
        self.render()
        self.tick()

    def destroy(self):
        for k in list(range(1, 9)):
            self.app.unbind(str(k))
        for seq in ("<Return>", "<Right>", "<Left>", "t", "T"):
            self.app.unbind(seq)
        self.unbind_all("<MouseWheel>")
        self.unbind_all("<Button-4>")
        self.unbind_all("<Button-5>")
        super().destroy()

    def _bg(self):
        return ttk.Style(self).lookup("TFrame", "background") or "#f0f0f0"

    def _on_resize(self, e):
        self.canvas.itemconfigure(self.win, width=e.width)
        wrap = max(300, e.width - 60)
        self.lbl_q.configure(wraplength=wrap)
        self.lbl_q2.configure(wraplength=wrap)
        self.feedback.configure(wraplength=wrap - 30)
        for w in self.opt_widgets:
            w.configure(wraplength=wrap - 40)

    def _on_wheel(self, e):
        self.canvas.yview_scroll(int(-e.delta / 120) if sys.platform != "darwin" else -e.delta, "units")

    # ---- çizim
    @property
    def practice(self):
        return self.s.mode == "pratik"

    @property
    def lang(self) -> str:
        base = primary_lang(self.lang_setting)
        if self.flip:
            return "tr" if base == "en" else "en"
        return base

    def toggle_lang(self):
        if not self.s.items[self.idx].q.get("en"):
            return  # bu sorunun İngilizcesi yok
        self.flip = not self.flip
        self.render(keep_scroll=True)

    def render(self, keep_scroll=False):
        it = self.s.items[self.idx]
        q = it.q
        n = len(self.s.items)
        self.lbl_pos["text"] = f"Soru {self.idx + 1} / {n}"
        self.progress["value"] = len(self.s.answers)
        meta = f"Alan {q['domain']}: {self.exam.domain_name(q['domain'])}"
        if q.get("topic"):
            meta += f"  •  Konu: {q['topic']}"
        meta += f"  •  Zorluk: {q['difficulty']}  •  Kaynak: {SOURCE_LABEL.get(q['source'], q['source'])}"
        if self.idx in self.s.flagged:
            meta += "  •  ⚑ işaretli"
        self.lbl_meta["text"] = meta
        if self.practice:
            done = [i for i in self.checked]
            ok = sum(self.s.is_correct(i) for i in done)
            self.lbl_score["text"] = f"Doğru: {ok} / {len(done)}"
        else:
            self.lbl_score["text"] = f"Cevaplanan: {len(self.s.answers)} / {n} • İşaretli: {len(self.s.flagged)}"

        lang = self.lang
        loc = localized(q, lang)
        text = loc["question"]
        low = text.lower()
        if it.multi and "seçin" not in low and "choose" not in low and "select" not in low:
            text += (f"\n\n(Choose {len(q['correct'])}.)" if loc["lang"] == "en"
                     else f"\n\n({len(q['correct'])} seçenek seçin)")
        self.lbl_q["text"] = text
        # İki dilli modda Türkçe soru metni İngilizcenin altında gösterilir
        if self.lang_setting == "bi" and loc["lang"] == "en":
            self.lbl_q2.configure(text="TR — " + q["question"])
            self.lbl_q2.pack(fill="x", pady=(4, 0), before=self.q_gap)
        else:
            self.lbl_q2.pack_forget()
        has_en = bool(q.get("en"))
        self.btn_lang["text"] = ("🌐 Türkçe (T)" if loc["lang"] == "en" else "🌐 English (T)") if has_en else "🌐 —"
        if has_en:
            self.btn_lang.state(["!disabled"])
        else:
            self.btn_lang.state(["disabled"])

        for w in self.opt_frame.winfo_children():
            w.destroy()
        self.opt_widgets = []
        prev = self.s.answers.get(self.idx, set())
        wrap = max(300, self.canvas.winfo_width() - 100)
        locked = self.practice and self.idx in self.checked
        if it.multi:
            self.vars = [tk.BooleanVar(value=(i in prev)) for i in range(len(it.options))]
        else:
            self.radio_var = tk.IntVar(value=next(iter(prev)) if prev else -1)
        for i, opt in enumerate(it.options_in(lang)):
            label = f"{chr(65 + i)}.  {opt}"
            common = dict(text=label, font=self.app.f_opt, justify="left", anchor="w",
                          wraplength=wrap, padx=8, pady=8, bg=self._bg(), activebackground=self._bg(),
                          highlightthickness=0, bd=0, command=self.on_select)
            if it.multi:
                w = tk.Checkbutton(self.opt_frame, variable=self.vars[i], **common)
            else:
                w = tk.Radiobutton(self.opt_frame, variable=self.radio_var, value=i, **common)
            if locked:
                w.configure(state="disabled", disabledforeground="#202124")
            w.pack(fill="x", anchor="w", pady=2)
            self.opt_widgets.append(w)

        self.feedback.pack_forget()
        if locked:
            self.show_feedback()
        self.btn_flag["text"] = "⚑ İşareti kaldır" if self.idx in self.s.flagged else "⚑ İşaretle"
        self._update_primary()
        if not keep_scroll:
            self.canvas.yview_moveto(0)

    def _update_primary(self):
        last = self.idx == len(self.s.items) - 1
        if self.practice and self.idx not in self.checked:
            self.btn_next["text"] = "Kontrol et ✓"
        elif last:
            self.btn_next["text"] = "Bitir ⏹"
        else:
            self.btn_next["text"] = "Sonraki ⟶"

    def selection(self) -> set[int]:
        it = self.s.items[self.idx]
        if it.multi:
            return {i for i, v in enumerate(self.vars) if v.get()}
        v = self.radio_var.get()
        return {v} if v >= 0 else set()

    def on_select(self):
        if self.practice and self.idx in self.checked:
            return
        sel = self.selection()
        if sel:
            self.s.answers[self.idx] = sel
        else:
            self.s.answers.pop(self.idx, None)
        self.progress["value"] = len(self.s.answers)
        if not self.practice:
            n = len(self.s.items)
            self.lbl_score["text"] = f"Cevaplanan: {len(self.s.answers)} / {n} • İşaretli: {len(self.s.flagged)}"

    def key_select(self, i):
        it = self.s.items[self.idx]
        if i >= len(it.options) or (self.practice and self.idx in self.checked):
            return
        if it.multi:
            self.vars[i].set(not self.vars[i].get())
        else:
            self.radio_var.set(i)
        self.on_select()

    def primary(self):
        if self.practice and self.idx not in self.checked:
            self.check()
        elif self.idx == len(self.s.items) - 1:
            self.finish()
        else:
            self.go(1)

    def check(self):
        sel = self.selection()
        it = self.s.items[self.idx]
        if not sel:
            messagebox.showinfo("Cevap", "Lütfen bir seçenek seçin.")
            return
        if it.multi and len(sel) != len(it.correct):
            if not messagebox.askyesno("Cevap", f"Bu soru {len(it.correct)} seçenek istiyor; "
                                                f"siz {len(sel)} seçtiniz. Yine de kontrol edilsin mi?"):
                return
        self.s.answer(self.idx, sel)
        self.s.record(self.idx, self.app.stats)
        self.checked.add(self.idx)
        self.render()

    def show_feedback(self):
        it = self.s.items[self.idx]
        sel = self.s.answers.get(self.idx, set())
        for i, w in enumerate(self.opt_widgets):
            if i in it.correct:
                w.configure(bg=GREEN_BG, disabledforeground=GREEN)
            elif i in sel:
                w.configure(bg=RED_BG, disabledforeground=RED)
        ok = self.s.is_correct(self.idx)
        right = ", ".join(chr(65 + i) for i in sorted(it.correct))
        head = "✓ Doğru!" if ok else f"✗ Yanlış. Doğru cevap: {right}"
        loc = localized(it.q, self.lang)
        body = loc["explanation"] or "(Açıklama yok)"
        if self.lang_setting == "bi" and loc["lang"] == "en" and it.q["explanation"]:
            body += "\n\nTR — " + it.q["explanation"]
        if it.q.get("source_url"):
            body += f"\n\nKaynak: {it.q['source_url']}"
        self.feedback.configure(text=f"{head}\n\n{body}", bg=GREEN_BG if ok else RED_BG,
                                fg="#202124")
        self.feedback.pack(fill="x", pady=(14, 10))

    def go(self, d):
        new = self.idx + d
        if 0 <= new < len(self.s.items):
            self.idx = new
            self.flip = False
            self.render()

    def toggle_flag(self):
        self.s.flagged.symmetric_difference_update({self.idx})
        self.render()

    def open_navigator(self):
        win = tk.Toplevel(self)
        win.title("Soru listesi")
        win.transient(self.app)
        ttk.Label(win, text="Bir soruya gitmek için tıklayın.  ● cevaplandı  ⚑ işaretli",
                  padding=8).pack()
        grid = ttk.Frame(win, padding=8)
        grid.pack()
        for i in range(len(self.s.items)):
            mark = ""
            if self.practice and i in self.checked:
                mark = "✓" if self.s.is_correct(i) else "✗"
            elif i in self.s.answers:
                mark = "●"
            if i in self.s.flagged:
                mark += "⚑"
            b = ttk.Button(grid, text=f"{i + 1} {mark}", width=6,
                           command=lambda i=i: (setattr(self, "idx", i), self.render(), win.destroy()))
            b.grid(row=i // 10, column=i % 10, padx=2, pady=2)

    def tick(self):
        if not self.winfo_exists():
            return
        rem = self.s.remaining()
        if rem is None:
            self.lbl_timer["text"] = "⏱ " + fmt_time(int(__import__("time").time() - self.s.started))
        else:
            self.lbl_timer["text"] = "⏳ " + fmt_time(rem)
            self.lbl_timer.configure(foreground=RED if rem < 300 else "")
            if rem == 0:
                messagebox.showinfo("Süre doldu", "Süre doldu! Sonuçlar gösteriliyor.")
                self.finish(force=True)
                return
        self.after(1000, self.tick)

    def finish(self, force=False):
        if not force:
            unanswered = len(self.s.items) - len(self.s.answers)
            if self.practice:
                unanswered = len(self.s.items) - len(self.checked)
            msg = "Oturumu bitirmek istiyor musunuz?"
            if unanswered:
                msg = f"{unanswered} soru cevaplanmadı. Yine de bitirilsin mi?"
            if not messagebox.askyesno("Bitir", msg):
                return
        if self.practice:
            # pratikte yalnızca kontrol edilen cevaplar sayılır
            for i in list(self.s.answers):
                if i not in self.checked:
                    self.s.answers.pop(i)
        summary = self.s.finish(self.app.stats)
        self.app.show_results(self.s, summary)

# ----------------------------------------------------------------------------- Sonuç ekranı
class ResultScreen(ttk.Frame):
    def __init__(self, parent, app: App, session: QuizSession, summary: dict):
        super().__init__(parent, padding=20)
        self.app, self.s, self.sum = app, session, summary
        ok = summary["passed"]
        ttk.Label(self, text="Sonuçlar", style="Title.TLabel").pack(anchor="w")
        color = GREEN if ok else RED
        verdict = "GEÇTİNİZ 🎉" if ok else "Hedefin altında"
        tk.Label(self, text=f"%{summary['percent']}  —  {verdict}", font=(app.f_title[0], 26, "bold"),
                 fg=color, bg=ttk.Style(self).lookup("TFrame", "background")).pack(anchor="w", pady=(6, 0))
        ttk.Label(self, text=(f"{summary['correct']} / {summary['total']} doğru • "
                              f"Süre {fmt_time(summary['seconds'])} • Hedef: %{PASS_PERCENT} "
                              "(Google resmi geçme notunu açıklamaz; %70+ güvenli kabul edilir)"),
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 12))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=2, uniform="r")
        body.columnconfigure(1, weight=3, uniform="r")
        body.rowconfigure(0, weight=1)

        dom = ttk.LabelFrame(body, text="Alan bazında", padding=10)
        dom.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        for name, (c, t) in summary["domains"].items():
            pct = round(100 * c / t) if t else 0
            ttk.Label(dom, text=name, wraplength=320, justify="left").pack(anchor="w", pady=(6, 0))
            fr = ttk.Frame(dom)
            fr.pack(fill="x")
            ttk.Progressbar(fr, maximum=100, value=pct).pack(side="left", fill="x", expand=True)
            ttk.Label(fr, text=f"{c}/{t}  %{pct}", width=11).pack(side="left", padx=4)

        lst = ttk.LabelFrame(body, text="Sorular (incelemek için çift tıklayın)", padding=10)
        lst.grid(row=0, column=1, sticky="nsew")
        self.tv = ttk.Treeview(lst, columns=("n", "r", "q"), show="headings")
        for c, t, w, st in (("n", "#", 40, False), ("r", "Sonuç", 70, False), ("q", "Soru", 500, True)):
            self.tv.heading(c, text=t)
            self.tv.column(c, width=w, stretch=st, anchor="w")
        sb = ttk.Scrollbar(lst, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        self.tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tv.tag_configure("ok", foreground=GREEN)
        self.tv.tag_configure("bad", foreground=RED)
        self.tv.tag_configure("skip", foreground="#80868b")
        for i, it in enumerate(session.items):
            if i not in session.answers:
                r, tag = "— boş", "skip"
            elif session.is_correct(i):
                r, tag = "✓", "ok"
            else:
                r, tag = "✗", "bad"
            qtext = localized(it.q, primary_lang(app.settings["language"]))["question"]
            self.tv.insert("", "end", iid=str(i), values=(i + 1, r, qtext[:140]), tags=(tag,))
        self.tv.bind("<Double-1>", self.review)

        bot = ttk.Frame(self)
        bot.pack(fill="x", pady=(12, 0))
        ttk.Button(bot, text="⌂ Ana sayfa", style="Big.TButton", command=app.show_home).pack(side="left")
        wrong = [i for i in range(len(session.items)) if not session.is_correct(i)]
        b = ttk.Button(bot, text=f"↻ Yanlış/boş soruları tekrar çöz ({len(wrong)})", style="Big.TButton",
                       command=lambda: self.retry(wrong))
        b.pack(side="left", padx=10)
        if not wrong:
            b.state(["disabled"])

    def review(self, _e=None):
        sel = self.tv.selection()
        if sel:
            ReviewWindow(self.app, self.s, int(sel[0]))

    def retry(self, idxs):
        import random
        from .engine import Item
        items = []
        for i in idxs:
            q = self.s.items[i].q
            order = list(range(len(q["options"])))
            random.shuffle(order)
            items.append(Item(q, order))
        random.shuffle(items)
        self.app.start_session(QuizSession(self.s.exam_code, "pratik", items))


class ReviewWindow(tk.Toplevel):
    def __init__(self, app: App, session: QuizSession, idx: int):
        super().__init__(app)
        self.app = app
        self.title(f"Soru {idx + 1} — inceleme")
        self.geometry("820x620")
        it = session.items[idx]
        sel = session.answers.get(idx, set())
        txt = make_text(self, app)
        insert_question(txt, it.q, app.settings["language"], it.order, it.correct, sel)
        txt.configure(state="disabled")
        bar = ttk.Frame(self, padding=8)
        bar.pack(fill="x")
        ttk.Button(bar, text="Kapat", command=self.destroy).pack(side="right")


class QuestionView(tk.Toplevel):
    def __init__(self, parent, app: App, q: dict):
        super().__init__(parent)
        self.title(q.get("id") or "Soru")
        self.geometry("780x560")
        txt = make_text(self, app)
        exam = EXAMS[q["exam"]]
        txt.insert("end", f"{exam.code} • Alan {q['domain']}: {exam.domain_name(q['domain'])} • "
                          f"{q.get('topic', '')} • {q['difficulty']}\n\n")
        insert_question(txt, q, app.settings["language"])
        txt.configure(state="disabled")


# ----------------------------------------------------------------------------- Soru bankası
class BankWindow(tk.Toplevel):
    def __init__(self, app: App, exam_code: str, on_close=None):
        super().__init__(app)
        self.app, self.on_close = app, on_close
        self.title("Soru bankası")
        self.geometry("1000x620")
        self.protocol("WM_DELETE_WINDOW", self.close)
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        self.v_exam = tk.StringVar(value=exam_code)
        self.v_search = tk.StringVar()
        ttk.Label(top, text="Sınav").pack(side="left")
        cb = ttk.Combobox(top, textvariable=self.v_exam, values=list(EXAMS), state="readonly", width=8)
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self.fill())
        ttk.Label(top, text="Ara").pack(side="left", padx=(12, 0))
        ent = ttk.Entry(top, textvariable=self.v_search, width=40)
        ent.pack(side="left", padx=6)
        self.v_search.trace_add("write", lambda *a: self.fill())
        self.lbl = ttk.Label(top, style="Muted.TLabel")
        self.lbl.pack(side="left", padx=10)
        ttk.Button(top, text="JSON olarak dışa aktar", command=self.export).pack(side="right")

        frm = ttk.Frame(self, padding=(10, 0))
        frm.pack(fill="both", expand=True)
        cols = (("id", "ID", 120, False), ("d", "Alan", 45, False), ("t", "Konu", 190, False),
                ("z", "Zorluk", 60, False), ("s", "Kaynak", 80, False), ("b", "Başarı", 80, False),
                ("q", "Soru", 400, True))
        self.tv = ttk.Treeview(frm, columns=[c[0] for c in cols], show="headings")
        for c, t, w, st in cols:
            self.tv.heading(c, text=t)
            self.tv.column(c, width=w, stretch=st, anchor="w")
        sb = ttk.Scrollbar(frm, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        self.tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tv.bind("<Double-1>", self.view)
        bot = ttk.Frame(self, padding=10)
        bot.pack(fill="x")
        ttk.Label(bot, text="Çift tıklayarak soruyu görüntüleyin. Yalnızca içe aktarılan sorular silinebilir.",
                  style="Muted.TLabel").pack(side="left")
        ttk.Button(bot, text="Seçileni sil", command=self.delete).pack(side="right")
        self.fill()

    def rows(self):
        term = self.v_search.get().lower().strip()
        qs = self.app.bank.for_exam(self.v_exam.get())
        if term:
            def hay(q):
                parts = [q["question"], q.get("topic", ""), *q["options"]]
                if q.get("en"):
                    parts += [q["en"]["question"], *q["en"]["options"]]
                return " ".join(parts).lower()
            qs = [q for q in qs if term in hay(q)]
        return sorted(qs, key=lambda q: (q["domain"], q["id"]))

    def fill(self):
        self.tv.delete(*self.tv.get_children())
        qs = self.rows()
        for q in qs:
            s = self.app.stats.get(q["id"])
            b = f"{s['correct']}/{s['seen']}" if s["seen"] else "—"
            self.tv.insert("", "end", iid=q["id"], values=(q["id"], q["domain"], q.get("topic", ""),
                                                          q["difficulty"], SOURCE_LABEL.get(q["source"], q["source"]),
                                                          b, localized(q, primary_lang(
                                                              self.app.settings["language"]))["question"][:150]))
        self.lbl["text"] = f"{len(qs)} soru"

    def view(self, _e=None):
        sel = self.tv.selection()
        if sel:
            QuestionView(self, self.app, self.app.bank.questions[sel[0]])

    def delete(self):
        sel = self.tv.selection()
        if not sel:
            return
        q = self.app.bank.questions[sel[0]]
        if q["source"] == "builtin":
            messagebox.showinfo("Sil", "Hazır sorular silinemez.", parent=self)
            return
        if messagebox.askyesno("Sil", "Bu soru kalıcı olarak silinsin mi?", parent=self):
            self.app.bank.delete_user_question(q["id"])
            self.fill()

    def export(self):
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".json",
                                            initialfile=f"{self.v_exam.get().lower()}_sorular.json",
                                            filetypes=[("JSON", "*.json")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.rows(), f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Dışa aktar", f"{len(self.rows())} soru kaydedildi.", parent=self)

    def close(self):
        self.destroy()
        if self.on_close:
            self.on_close()


def main():
    app = App()
    app.mainloop()
