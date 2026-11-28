"""Tkinter masaüstü arayüzü."""
from __future__ import annotations

import json
import os
import sys
import time
import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk

from . import __version__
from .engine import PASS_PERCENT, QuizSession, build_session
from . import i18n
from .exams import EXAMS
from .store import QuestionBank, Settings, Stats, ValidationError, load_import_file, localized

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
MODES = ("pratik", "sinav")
FOCUS = ("karisik", "zayif", "yeni")
SOURCES = (("src_all", None), ("src_builtin", ["builtin"]), ("src_user", ["ice-aktarim"]))
QLANGS = ("tr", "en", "bi")


class Choice:
    """Görünen etiketi dile göre değişen, iç değeri sabit kalan açılır liste."""

    def __init__(self, parent, pairs, value=None, **kw):
        self.pairs = list(pairs)  # [(değer, etiket)]
        self.var = tk.StringVar()
        self.cb = ttk.Combobox(parent, textvariable=self.var, state="readonly",
                               values=[lbl for _, lbl in self.pairs], **kw)
        self.set(value)

    def get(self):
        lbl = self.var.get()
        return next((v for v, l in self.pairs if l == lbl), self.pairs[0][0])

    def set(self, value):
        self.var.set(next((l for v, l in self.pairs if v == value), self.pairs[0][1]))

    def set_pairs(self, pairs):
        cur = self.get()
        self.pairs = list(pairs)
        self.cb["values"] = [lbl for _, lbl in self.pairs]
        self.set(cur)


def primary_lang(setting: str) -> str:
    """Ayardaki dil için soruların ana gösterim dili."""
    return "tr" if setting == "tr" else "en"


def insert_question(txt: tk.Text, q: dict, setting: str, ui: str = "tr", order=None, correct=None,
                    sel=frozenset()):
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
            mark = i18n.t("your_answer", ui) if i in sel else ""
            txt.insert("end", f"{chr(65 + i)}. {loc['options'][orig]}{mark}\n", tag)
        txt.insert("end", "\nAçıklama\n" if lang == "tr" else "\nExplanation\n", "h")
        txt.insert("end", (loc["explanation"] or i18n.t("no_expl", ui)) + "\n")
    if q.get("source_url"):
        txt.insert("end", "\n" + i18n.t("source_line", ui, url=q["source_url"]))


def source_label(src: str, ui: str) -> str:
    key = f"srclabel_{src}"
    return i18n.t(key, ui) if key in i18n.STRINGS else src


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
        if sys.platform == "win32":
            # Görev çubuğunda Python logosu yerine uygulamanın kendi simgesi görünsün
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("GCPACEExamTrainer")
            except Exception:
                pass
        super().__init__()
        self.settings = Settings()
        self.home_state: dict = {}
        self.title(self.t("app_title"))
        self._set_icon()
        self.geometry("1100x760")
        self.minsize(880, 600)
        self.bank = QuestionBank()
        self.stats = Stats()
        self._setup_style()
        self.container = ttk.Frame(self)
        self.container.pack(fill="both", expand=True)
        self.screen = None
        self.show_home()

    @property
    def ui(self) -> str:
        return i18n.norm_lang(self.settings["ui_lang"])

    def t(self, key: str, **kw) -> str:
        return i18n.t(key, self.ui, **kw)

    def set_ui_lang(self, lang: str):
        self.settings["ui_lang"] = i18n.norm_lang(lang)
        self.settings.save()
        self.title(self.t("app_title"))
        self.show_home()

    def _set_icon(self):
        try:
            imgs = [tk.PhotoImage(file=os.path.join(ASSETS, f"icon-{n}.png")) for n in (256, 48, 32, 16)]
            self.iconphoto(True, *imgs)
            self._icons = imgs  # çöp toplayıcı silmesin
        except (tk.TclError, OSError):
            pass

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
        style.configure("Lang.Toolbutton", font=(fam, 10, "bold"), padding=(8, 4), anchor="center")
        style.map("Lang.Toolbutton", background=[("selected", "#1a73e8"), ("active", "#d2e3fc")],
                  foreground=[("selected", "#ffffff")])

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
        t, ui = app.t, app.ui
        st = app.home_state
        exam_code = app.settings["last_exam"] if app.settings["last_exam"] in EXAMS else "ACE"

        head = ttk.Frame(self)
        head.pack(fill="x")
        titles = ttk.Frame(head)
        titles.pack(side="left")
        ttk.Label(titles, text="GCP ACE Exam Trainer", style="Title.TLabel").pack(anchor="w")
        ttk.Label(titles, text=t("subtitle", v=__version__), style="Muted.TLabel").pack(anchor="w")
        # arayüz dili: TR | EN
        sw = ttk.Frame(head)
        sw.pack(side="right", padx=(12, 0))
        self.v_ui = tk.StringVar(value=ui)
        for code, lbl in (("tr", "TR"), ("en", "EN")):
            ttk.Radiobutton(sw, text=lbl, value=code, variable=self.v_ui, style="Lang.Toolbutton", width=3,
                            command=self._switch_ui).pack(side="left")
        for key, cmd in (("btn_reset", self.reset_stats), ("btn_import", self.import_json),
                         ("btn_bank", self.open_bank)):
            ttk.Button(head, text=t(key), command=cmd).pack(side="right", padx=4)

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, pady=(16, 0))
        body.columnconfigure(0, weight=3, uniform="c")
        body.columnconfigure(1, weight=2, uniform="c")
        body.rowconfigure(0, weight=1)

        # --- Sol: oturum kurulumu
        left = ttk.LabelFrame(body, text=t("new_session"), padding=14)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.columnconfigure(1, weight=1)

        self.v_count = tk.IntVar(value=st.get("count", 20))
        self.v_timed = tk.BooleanVar(value=st.get("timed", False))

        r = 0

        def row(label, widget):
            nonlocal r
            ttk.Label(left, text=label).grid(row=r, column=0, sticky="w", pady=5, padx=(0, 10))
            widget.grid(row=r, column=1, sticky="ew", pady=5)
            r += 1

        self.c_exam = Choice(left, [(c, f"{c} — {e.name}") for c, e in EXAMS.items()], exam_code)
        self.c_exam.cb.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        row(t("lbl_exam"), self.c_exam.cb)
        self.c_lang = Choice(left, [(k, t(f"qlang_{k}")) for k in QLANGS], app.settings["language"])
        self.c_lang.cb.bind("<<ComboboxSelected>>", lambda e: self._save_lang())
        row(t("lbl_qlang"), self.c_lang.cb)
        self.c_mode = Choice(left, [(k, t(f"mode_{k}")) for k in MODES], st.get("mode"))
        row(t("lbl_mode"), self.c_mode.cb)
        cnt = ttk.Frame(left)
        ttk.Spinbox(cnt, from_=5, to=200, increment=5, textvariable=self.v_count, width=6).pack(side="left")
        for n in (10, 20, 50):
            ttk.Button(cnt, text=str(n), width=4, command=lambda n=n: self.v_count.set(n)).pack(side="left", padx=2)
        ttk.Checkbutton(cnt, text=t("timed_practice"), variable=self.v_timed).pack(side="left", padx=10)
        row(t("lbl_count"), cnt)
        self.c_domain = Choice(left, [(None, t("all"))])
        row(t("lbl_domain"), self.c_domain.cb)
        self.c_topic = Choice(left, [(None, t("all"))])
        row(t("lbl_topic"), self.c_topic.cb)
        self.c_focus = Choice(left, [(k, t(f"focus_{k}")) for k in FOCUS], st.get("focus"))
        row(t("lbl_focus"), self.c_focus.cb)
        self.c_source = Choice(left, [(k, t(k)) for k, _ in SOURCES], st.get("source"))
        row(t("lbl_source"), self.c_source.cb)

        self.lbl_bank = ttk.Label(left, style="Muted.TLabel", wraplength=520, justify="left")
        self.lbl_bank.grid(row=r, column=0, columnspan=2, sticky="w", pady=(10, 4))
        r += 1
        btns = ttk.Frame(left)
        btns.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Button(btns, text=t("btn_start"), style="Big.TButton", command=self.start).pack(side="left")
        r += 1
        ttk.Label(left, text=t("tip"), style="Muted.TLabel", wraplength=520, justify="left").grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(16, 0))

        # --- Sağ: ilerleme
        right = ttk.LabelFrame(body, text=t("progress"), padding=14)
        right.grid(row=0, column=1, sticky="nsew")
        self.lbl_overall = ttk.Label(right, font=self.app.f_h2, justify="left")
        self.lbl_overall.pack(anchor="w")
        ttk.Label(right, text=t("by_domain"), style="Muted.TLabel").pack(anchor="w", pady=(12, 2))
        self.dom_frame = ttk.Frame(right)
        self.dom_frame.pack(fill="x")
        ttk.Label(right, text=t("recent"), style="Muted.TLabel").pack(anchor="w", pady=(14, 2))
        self.tv_hist = ttk.Treeview(right, columns=("t", "m", "s"), show="headings", height=8)
        for c, key, w in (("t", "col_date", 130), ("m", "col_mode", 70), ("s", "col_score", 90)):
            self.tv_hist.heading(c, text=t(key))
            self.tv_hist.column(c, width=w, anchor="w")
        self.tv_hist.pack(fill="both", expand=True)

        self.refresh(domain=st.get("domain"), topic=st.get("topic"))
        if app.bank.load_errors and not st.get("warned"):
            st["warned"] = True
            messagebox.showwarning(t("bank_warn_title"), t("bank_warn") + "\n" + "\n".join(
                i18n.error(e, ui) for e in app.bank.load_errors[:10]))

    # yardımcılar
    def _remember(self):
        """Dil değişince ekran yeniden kurulurken seçimler kaybolmasın."""
        try:
            count = int(self.v_count.get())
        except (tk.TclError, ValueError):
            count = 20
        self.app.home_state.update(mode=self.c_mode.get(), count=count, timed=self.v_timed.get(),
                                   domain=self.c_domain.get(), topic=self.c_topic.get(),
                                   focus=self.c_focus.get(), source=self.c_source.get())

    def _switch_ui(self):
        if self.v_ui.get() != self.app.ui:
            self._remember()
            self._save_lang()
            self.app.set_ui_lang(self.v_ui.get())

    def _save_lang(self):
        self.app.settings["language"] = self.c_lang.get()
        self.app.settings.save()

    def exam_code(self):
        return self.c_exam.get()

    def refresh(self, domain=None, topic=None):
        t, ui = self.app.t, self.app.ui
        code = self.exam_code()
        exam = EXAMS[code]
        self.app.settings["last_exam"] = code
        self.app.settings.save()
        self.c_domain.set_pairs([(None, t("all"))] + [(k, f"{k}. {i18n.domain_name(exam, k, ui)}")
                                                      for k in exam.domains])
        topics = sorted({q["topic"] for q in self.app.bank.for_exam(code) if q["topic"]},
                        key=lambda x: i18n.topic_name(x, ui).lower())
        self.c_topic.set_pairs([(None, t("all"))] + [(x, i18n.topic_name(x, ui)) for x in topics])
        if domain is not None:
            self.c_domain.set(domain)
        if topic is not None:
            self.c_topic.set(topic)
        c = self.app.bank.count(code)
        qs = self.app.bank.for_exam(code)
        seen = sum(1 for q in qs if self.app.stats.get(q["id"])["seen"])
        weak = len(self.app.stats.weak_ids(q["id"] for q in qs))
        if c["toplam"]:
            txt = t("bank_info", total=c["toplam"], builtin=c["hazir"], user=c["eklenen"], seen=seen,
                    weak=weak, qc=exam.question_count, mins=exam.minutes)
        else:
            txt = t("bank_empty", code=exam.code)
        self.lbl_bank["text"] = txt

        # ilerleme paneli
        def pct_text(p):
            return f"{p}%" if ui == "en" else f"%{p}"

        tot = sum(self.app.stats.get(q["id"])["seen"] for q in qs)
        cor = sum(self.app.stats.get(q["id"])["correct"] for q in qs)
        acc = pct_text(round(100 * cor / tot)) if tot else "—"
        self.lbl_overall["text"] = t("overall", n=tot, acc=acc)
        for w in self.dom_frame.winfo_children():
            w.destroy()
        for k in exam.domains:
            dq = [q for q in qs if q["domain"] == k]
            n = sum(self.app.stats.get(q["id"])["seen"] for q in dq)
            cc = sum(self.app.stats.get(q["id"])["correct"] for q in dq)
            pct = round(100 * cc / n) if n else 0
            fr = ttk.Frame(self.dom_frame)
            fr.pack(fill="x", pady=2)
            ttk.Label(fr, text=f"{k}. {i18n.domain_name(exam, k, ui)}", wraplength=260,
                      justify="left").pack(anchor="w")
            bar = ttk.Frame(fr)
            bar.pack(fill="x")
            pb = ttk.Progressbar(bar, maximum=100, value=pct)
            pb.pack(side="left", fill="x", expand=True)
            ttk.Label(bar, text=f"{pct_text(pct)} ({n})" if n else "—", width=10).pack(side="left", padx=4)
        self.tv_hist.delete(*self.tv_hist.get_children())
        for s in reversed([s for s in self.app.stats.sessions if s["exam"] == code][-30:]):
            mark = "✓" if s["passed"] else "✗"
            mode = t(f"mode_short_{s['mode']}") if s["mode"] in MODES else s["mode"]
            self.tv_hist.insert("", "end", values=(s["date"], mode,
                                                   f"{mark} {pct_text(s['percent'])} ({s['correct']}/{s['total']})"))

    def start(self):
        self._save_lang()
        self._remember()
        code = self.exam_code()
        dom = self.c_domain.get()
        domains = None if dom is None else [dom]
        topic = self.c_topic.get()
        topics = None if topic is None else [topic]
        mode = self.c_mode.get()
        try:
            n = max(1, int(self.v_count.get()))
        except (tk.TclError, ValueError):
            n = 20
        try:
            sess = build_session(self.app.bank, self.app.stats, code, n, mode, domains,
                                 self.c_focus.get(), dict(SOURCES)[self.c_source.get()],
                                 timed=True if self.v_timed.get() or mode == "sinav" else False,
                                 topics=topics)
        except ValueError as e:
            messagebox.showinfo(self.app.t("no_questions"), i18n.error(str(e), self.app.ui))
            return
        self.app.start_session(sess)

    def open_bank(self):
        BankWindow(self.app, self.exam_code(), on_close=self.refresh)

    def reset_stats(self):
        if messagebox.askyesno(self.app.t("reset_title"), self.app.t("reset_ask")):
            self.app.stats.reset()
            self.refresh()

    def import_json(self):
        t, ui = self.app.t, self.app.ui
        path = filedialog.askopenfilename(title=t("pick_file"), filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            data = load_import_file(path)
        except ValidationError as e:
            messagebox.showerror(t("import_title"), i18n.error(str(e), ui))
            return
        added, errors = self.app.bank.add_user_questions(data, self.exam_code())
        msg = t("import_added", n=added)
        if errors:
            msg += "\n" + t("import_skipped", n=len(errors)) + "\n" + "\n".join(
                i18n.error(e, ui) for e in errors[:12])
        messagebox.showinfo(t("import_title"), msg)
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
        t = app.t
        ttk.Button(bot, text=t("btn_prev"), command=lambda: self.go(-1)).pack(side="left")
        self.btn_flag = ttk.Button(bot, text=t("btn_flag"), command=self.toggle_flag)
        self.btn_flag.pack(side="left", padx=6)
        self.btn_nav = ttk.Button(bot, text=t("btn_nav"), command=self.open_navigator)
        self.btn_nav.pack(side="left")
        self.btn_lang = ttk.Button(bot, text="🌐 Dil (T)", command=self.toggle_lang)
        self.btn_lang.pack(side="left", padx=6)
        ttk.Button(bot, text=t("btn_finish"), command=self.finish).pack(side="right")
        self.btn_next = ttk.Button(bot, text=t("btn_next"), style="Big.TButton", command=self.primary)
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
        t, ui = self.app.t, self.app.ui
        self.lbl_pos["text"] = t("q_pos", i=self.idx + 1, n=n)
        self.progress["value"] = len(self.s.answers)
        parts = [t("meta_domain", k=q["domain"], name=i18n.domain_name(self.exam, q["domain"], ui))]
        if q.get("topic"):
            parts.append(t("meta_topic", t=i18n.topic_name(q["topic"], ui)))
        parts.append(t("meta_diff", d=i18n.difficulty(q["difficulty"], ui)))
        parts.append(t("meta_source", s=source_label(q["source"], ui)))
        if self.idx in self.s.flagged:
            parts.append(t("meta_flagged"))
        self.lbl_meta["text"] = "  •  ".join(parts)
        if self.practice:
            done = [i for i in self.checked]
            ok = sum(self.s.is_correct(i) for i in done)
            self.lbl_score["text"] = t("score_practice", ok=ok, n=len(done))
        else:
            self.lbl_score["text"] = t("score_exam", a=len(self.s.answers), n=n, f=len(self.s.flagged))

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
        self.btn_flag["text"] = t("btn_unflag") if self.idx in self.s.flagged else t("btn_flag")
        self._update_primary()
        if not keep_scroll:
            self.canvas.yview_moveto(0)

    def _update_primary(self):
        last = self.idx == len(self.s.items) - 1
        if self.practice and self.idx not in self.checked:
            self.btn_next["text"] = self.app.t("btn_check")
        elif last:
            self.btn_next["text"] = self.app.t("btn_finish_last")
        else:
            self.btn_next["text"] = self.app.t("btn_next")

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
            self.lbl_score["text"] = self.app.t("score_exam", a=len(self.s.answers), n=len(self.s.items),
                                                f=len(self.s.flagged))

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
        t = self.app.t
        if not sel:
            messagebox.showinfo(t("answer_title"), t("answer_pick"))
            return
        if it.multi and len(sel) != len(it.correct):
            if not messagebox.askyesno(t("answer_title"), t("answer_count", need=len(it.correct), got=len(sel))):
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
        t = self.app.t
        head = t("fb_right") if ok else t("fb_wrong", ans=right)
        loc = localized(it.q, self.lang)
        body = loc["explanation"] or t("no_expl")
        if self.lang_setting == "bi" and loc["lang"] == "en" and it.q["explanation"]:
            body += "\n\nTR — " + it.q["explanation"]
        if it.q.get("source_url"):
            body += "\n\n" + t("source_line", url=it.q["source_url"])
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
        win.title(self.app.t("nav_title"))
        win.transient(self.app)
        ttk.Label(win, text=self.app.t("nav_hint"), padding=8).pack()
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
            self.lbl_timer["text"] = "⏱ " + fmt_time(int(time.time() - self.s.started))
        else:
            self.lbl_timer["text"] = "⏳ " + fmt_time(rem)
            self.lbl_timer.configure(foreground=RED if rem < 300 else "")
            if rem == 0:
                messagebox.showinfo(self.app.t("time_up_title"), self.app.t("time_up"))
                self.finish(force=True)
                return
        self.after(1000, self.tick)

    def finish(self, force=False):
        if not force:
            unanswered = len(self.s.items) - len(self.s.answers)
            if self.practice:
                unanswered = len(self.s.items) - len(self.checked)
            t = self.app.t
            msg = t("finish_unanswered", n=unanswered) if unanswered else t("finish_ask")
            if not messagebox.askyesno(t("btn_finish"), msg):
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
        t, ui = app.t, app.ui
        exam = EXAMS[session.exam_code]
        ok = summary["passed"]
        ttk.Label(self, text=t("results"), style="Title.TLabel").pack(anchor="w")
        color = GREEN if ok else RED
        verdict = t("passed") if ok else t("below")
        pct = f"{summary['percent']}%" if ui == "en" else f"%{summary['percent']}"
        tk.Label(self, text=f"{pct}  —  {verdict}", font=(app.f_title[0], 26, "bold"),
                 fg=color, bg=ttk.Style(self).lookup("TFrame", "background")).pack(anchor="w", pady=(6, 0))
        ttk.Label(self, text=t("result_line", c=summary["correct"], t=summary["total"],
                               time=fmt_time(summary["seconds"]), p=PASS_PERCENT),
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 12))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=2, uniform="r")
        body.columnconfigure(1, weight=3, uniform="r")
        body.rowconfigure(0, weight=1)

        dom = ttk.LabelFrame(body, text=t("res_domains"), padding=10)
        dom.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        by_name = {v[0]: k for k, v in exam.domains.items()}
        for name, (c, tot) in summary["domains"].items():
            pct = round(100 * c / tot) if tot else 0
            k = by_name.get(name)
            label = f"{k}. {i18n.domain_name(exam, k, ui)}" if k else name
            ttk.Label(dom, text=label, wraplength=320, justify="left").pack(anchor="w", pady=(6, 0))
            fr = ttk.Frame(dom)
            fr.pack(fill="x")
            ttk.Progressbar(fr, maximum=100, value=pct).pack(side="left", fill="x", expand=True)
            ttk.Label(fr, text=f"{c}/{tot}  " + (f"{pct}%" if ui == "en" else f"%{pct}"),
                      width=11).pack(side="left", padx=4)

        lst = ttk.LabelFrame(body, text=t("res_list"), padding=10)
        lst.grid(row=0, column=1, sticky="nsew")
        self.tv = ttk.Treeview(lst, columns=("n", "r", "q"), show="headings")
        for c, head, w, st in (("n", "#", 40, False), ("r", t("col_result"), 70, False),
                               ("q", t("col_question"), 500, True)):
            self.tv.heading(c, text=head)
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
                r, tag = t("blank"), "skip"
            elif session.is_correct(i):
                r, tag = "✓", "ok"
            else:
                r, tag = "✗", "bad"
            qtext = localized(it.q, primary_lang(app.settings["language"]))["question"]
            self.tv.insert("", "end", iid=str(i), values=(i + 1, r, qtext[:140]), tags=(tag,))
        self.tv.bind("<Double-1>", self.review)

        bot = ttk.Frame(self)
        bot.pack(fill="x", pady=(12, 0))
        ttk.Button(bot, text=t("btn_home"), style="Big.TButton", command=app.show_home).pack(side="left")
        wrong = [i for i in range(len(session.items)) if not session.is_correct(i)]
        b = ttk.Button(bot, text=t("btn_retry", n=len(wrong)), style="Big.TButton",
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
        self.title(app.t("review_title", i=idx + 1))
        self.geometry("820x620")
        it = session.items[idx]
        sel = session.answers.get(idx, set())
        txt = make_text(self, app)
        insert_question(txt, it.q, app.settings["language"], app.ui, it.order, it.correct, sel)
        txt.configure(state="disabled")
        bar = ttk.Frame(self, padding=8)
        bar.pack(fill="x")
        ttk.Button(bar, text=app.t("btn_close"), command=self.destroy).pack(side="right")


class QuestionView(tk.Toplevel):
    def __init__(self, parent, app: App, q: dict):
        super().__init__(parent)
        ui = app.ui
        self.title(q.get("id") or app.t("col_question"))
        self.geometry("780x560")
        txt = make_text(self, app)
        exam = EXAMS[q["exam"]]
        txt.insert("end", app.t("view_meta", code=exam.code, k=q["domain"],
                                name=i18n.domain_name(exam, q["domain"], ui),
                                topic=i18n.topic_name(q.get("topic", ""), ui),
                                diff=i18n.difficulty(q["difficulty"], ui)) + "\n\n")
        insert_question(txt, q, app.settings["language"], ui)
        txt.configure(state="disabled")


# ----------------------------------------------------------------------------- Soru bankası
class BankWindow(tk.Toplevel):
    def __init__(self, app: App, exam_code: str, on_close=None):
        super().__init__(app)
        self.app, self.on_close = app, on_close
        t = app.t
        self.title(t("btn_bank"))
        self.geometry("1000x620")
        self.protocol("WM_DELETE_WINDOW", self.close)
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        self.v_exam = tk.StringVar(value=exam_code)
        self.v_search = tk.StringVar()
        ttk.Label(top, text=t("lbl_exam")).pack(side="left")
        cb = ttk.Combobox(top, textvariable=self.v_exam, values=list(EXAMS), state="readonly", width=8)
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self.fill())
        ttk.Label(top, text=t("lbl_search")).pack(side="left", padx=(12, 0))
        ent = ttk.Entry(top, textvariable=self.v_search, width=40)
        ent.pack(side="left", padx=6)
        self.v_search.trace_add("write", lambda *a: self.fill())
        self.lbl = ttk.Label(top, style="Muted.TLabel")
        self.lbl.pack(side="left", padx=10)
        ttk.Button(top, text=t("btn_export"), command=self.export).pack(side="right")

        frm = ttk.Frame(self, padding=(10, 0))
        frm.pack(fill="both", expand=True)
        cols = (("id", t("col_id"), 120, False), ("d", t("col_domain"), 70, False),
                ("t", t("col_topic"), 190, False), ("z", t("col_diff"), 85, False),
                ("s", t("col_source"), 80, False), ("b", t("col_success"), 70, False),
                ("q", t("col_question"), 400, True))
        self.tv = ttk.Treeview(frm, columns=[c[0] for c in cols], show="headings")
        for c, head, w, st in cols:
            self.tv.heading(c, text=head)
            self.tv.column(c, width=w, stretch=st, anchor="w")
        sb = ttk.Scrollbar(frm, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        self.tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tv.bind("<Double-1>", self.view)
        bot = ttk.Frame(self, padding=10)
        bot.pack(fill="x")
        ttk.Label(bot, text=t("bank_hint"), style="Muted.TLabel").pack(side="left")
        ttk.Button(bot, text=t("btn_delete"), command=self.delete).pack(side="right")
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
        ui = self.app.ui
        qlang = primary_lang(self.app.settings["language"])
        for q in qs:
            s = self.app.stats.get(q["id"])
            b = f"{s['correct']}/{s['seen']}" if s["seen"] else "—"
            self.tv.insert("", "end", iid=q["id"], values=(
                q["id"], q["domain"], i18n.topic_name(q.get("topic", ""), ui), i18n.difficulty(q["difficulty"], ui),
                source_label(q["source"], ui), b, localized(q, qlang)["question"][:150]))
        self.lbl["text"] = self.app.t("n_questions", n=len(qs))

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
            messagebox.showinfo(self.app.t("delete_title"), self.app.t("delete_builtin"), parent=self)
            return
        if messagebox.askyesno(self.app.t("delete_title"), self.app.t("delete_ask"), parent=self):
            self.app.bank.delete_user_question(q["id"])
            self.fill()

    def export(self):
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".json",
                                            initialfile=self.app.t("export_file", code=self.v_exam.get().lower()),
                                            filetypes=[("JSON", "*.json")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.rows(), f, ensure_ascii=False, indent=2)
            messagebox.showinfo(self.app.t("export_title"), self.app.t("export_done", n=len(self.rows())),
                                parent=self)

    def close(self):
        self.destroy()
        if self.on_close:
            self.on_close()


def main():
    app = App()
    app.mainloop()
