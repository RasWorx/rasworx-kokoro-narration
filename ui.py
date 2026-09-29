"""Desktop window for turning a script (picked file or pasted text) into an MP3 with Kokoro-82M.

Launch with ui.bat (runs .venv\\Scripts\\pythonw.exe ui.py, no console window).
Reuses generate.py for text cleaning, synthesis and MP3 export, so the output matches the CLI.
Styled after the RasWorx brand guide (dark palette, primary blue #046FCC, Montserrat).
"""

import json
import logging
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import traceback
import unicodedata
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ui_theme import (
    BLUE, BLUE_TEXT, BORDER, CHARCOAL, FIELD, FIELD_OFF, SLATE, TEXT_STRONG, WARNING, WARNING_BG,
    apply_theme, dark_title_bar,
)
from generate import (
    DEFAULT_VOICE, INPUT_DIR, OUTPUT_DIR, ROOT, SAMPLE_RATE,
    accent_of, load_text, paragraphs_of, resolve_voice, synthesize, write_mp3,
)

LOG_FILE = ROOT / "ui.log"
ASSETS = ROOT / "assets"
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
SETTINGS_FILE = ROOT / "settings.json"
_LINTER_REL = Path("tts-output/scripts/check_tts_script.py")
LINTER = next((p for p in (ROOT / ".agents/skills" / _LINTER_REL,
                           Path(os.environ.get("USERPROFILE", "~")).expanduser() / ".claude/skills" / _LINTER_REL)
               if p.exists()), ROOT / ".agents/skills" / _LINTER_REL)
VOICES = ["af_kore", "af_heart", "af_bella", "af_nicole", "af_aoede", "af_sarah", "am_michael", "am_fenrir", "am_puck"]
# name, voice (None keeps the current one), speed, pause. From the tts-output mood table (midpoints).
MOODS = [
    ("Custom", DEFAULT_VOICE, 1.00, 0.40),
    ("Calm, documentary", "af_kore", 0.95, 0.45),
    ("Warm, reassuring", "af_heart", 0.92, 0.55),
    ("Serious, reflective", "af_heart", 0.88, 0.80),
    ("Excited, upbeat", "af_heart", 1.08, 0.30),
    ("Urgent, tense", None, 1.05, 0.30),
    ("Meditation, sleep", "af_heart", 0.82, 2.00),
]
LINT_IDLE = "Pick a file or click Convert"
SPEED_RANGE = (0.70, 1.30)
PAUSE_RANGE = (0.0, 3.0)
NAME_OK = re.compile(r"^[A-Za-z0-9_-]+$")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

log = logging.getLogger("ui")


class Cancelled(Exception):
    pass


class Engine:
    """Holds the loaded Kokoro pipelines (one per accent) and renders text to a file. No UI code."""

    def __init__(self):
        self.device = None
        self._pipelines = {}

    def load(self, lang="a"):
        import torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.pipeline(lang)

    def pipeline(self, lang):
        if lang not in self._pipelines:
            from kokoro import KPipeline
            self._pipelines[lang] = KPipeline(lang_code=lang, repo_id="hexgrad/Kokoro-82M", device=self.device)
        return self._pipelines[lang]

    def render(self, text, voice, speed, pause, out, progress=None, stop=None):
        """Synthesize text into out (.mp3, or .wav if MP3 export fails). Returns (path, audio seconds)."""
        if not paragraphs_of(text):
            raise ValueError("There is no text to speak.")
        audio = synthesize(self.pipeline(accent_of(voice)), text, resolve_voice(voice), speed, pause, progress, stop)
        if audio is None:
            raise Cancelled
        out.parent.mkdir(parents=True, exist_ok=True)
        return write_mp3(audio, out), len(audio) / SAMPLE_RATE


def slugify(text):
    """File-name slug from the first Markdown heading, or else the first five words."""
    heading = re.search(r"^[ \t]{0,3}#{1,6}[ \t]+(.+)$", text, flags=re.M)
    words = heading.group(1) if heading else " ".join(text.split()[:5])
    words = unicodedata.normalize("NFKD", words).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9_-]+", "-", words).strip("-_")[:60].strip("-_")


def lint(path):
    """Run the tts-output linter. Returns (summary, [warning lines]); raises on failure."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    python = VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable)
    proc = subprocess.run([str(python), str(LINTER), str(path), "--quiet"], capture_output=True,
                          env=env, creationflags=NO_WINDOW, timeout=60)
    lines = proc.stdout.decode("utf-8", "replace").splitlines()
    m = re.search(r"(\d+) words, ~([\d.]+) min", lines[0] if lines else "")
    if proc.returncode not in (0, 1) or not m:  # 1 only means "has warnings"
        raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip() or "unexpected linter output")
    warnings = [line.strip() for line in lines if line.lstrip().startswith("WARN")]
    count = len(warnings)
    summary = f"{int(m.group(1)):,} words, ~{m.group(2)} min, {count} warning{'' if count == 1 else 's'}"
    return summary, warnings


def load_settings():
    """Saved (mood, voice, speed, pause); anything missing, invalid or out of range keeps its default."""
    out = {"mood": "Custom", "voice": DEFAULT_VOICE, "speed": 1.00, "pause": 0.40}
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("not an object")
    except (OSError, ValueError):
        return out
    if data.get("mood") in [m[0] for m in MOODS]:
        out["mood"] = data["mood"]
    if isinstance(data.get("voice"), str) and data["voice"].strip():
        out["voice"] = data["voice"].strip()
    for key, (low, high) in (("speed", SPEED_RANGE), ("pause", PAUSE_RANGE)):
        value = data.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and low <= value <= high:
            out[key] = float(value)
    return out


def save_settings(data):
    try:
        SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        log.exception("could not save settings")


def audio_length(path):
    """Length of an audio file in seconds, or None if it cannot be read."""
    try:
        import soundfile
        return soundfile.info(str(path)).duration
    except Exception:
        return None


def run_in_thread(fn, *args):
    threading.Thread(target=fn, args=args, daemon=True).start()




class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Kokoro narration")
        self.minsize(1080, 620)
        try:
            self.iconbitmap(default=str(ASSETS / "app.ico"))
        except tk.TclError:
            pass
        self.fonts = apply_theme(self)
        self.engine = Engine()
        self.events = queue.Queue()  # (kind, *data) from worker threads, handled on the Tk thread
        self.stop_event = threading.Event()
        self.ready = False
        self.busy = False
        self.last_out = None
        self.lint_seq = 0
        self.warnings = []
        self.popup = None
        self.lengths = {}  # (path, mtime) -> seconds, so the file list does not re-read every MP3
        self.applying_mood = False
        self.name_touched = False  # paste mode: stop auto-naming once the user edits the name

        self.mode = tk.StringVar(value="file")
        self.file_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.paste_name = ""
        self.out_var = tk.StringVar()
        saved = load_settings()
        self.mood_var = tk.StringVar(value=saved["mood"])
        self.voice_var = tk.StringVar(value=saved["voice"])
        self.speed_var = tk.StringVar(value=f"{saved['speed']:.2f}")
        self.pause_var = tk.StringVar(value=f"{saved['pause']:.2f}")
        self.lint_var = tk.StringVar(value=LINT_IDLE)
        self.progress_var = tk.StringVar()
        self.status_var = tk.StringVar()

        self._build()
        self.name_var.trace_add("write", lambda *_: self._update_out_label())
        for var in (self.voice_var, self.speed_var, self.pause_var):
            var.trace_add("write", self._on_setting_edit)
        self._on_mode()
        self._refresh_files()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        dark_title_bar(self)
        self.state("zoomed")  # start maximized
        self.after(100, self._poll)
        self._start_model_load()

    # ---------- layout ----------

    def _build(self):
        page = ttk.Frame(self, style="Page.TFrame", padding=(18, 14, 18, 14))
        page.pack(fill="both", expand=True)
        page.columnconfigure(0, weight=1)
        page.columnconfigure(1, weight=0, minsize=420)
        page.rowconfigure(1, weight=1)

        header = ttk.Frame(page, style="Page.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        header.columnconfigure(1, weight=1)
        hi_dpi = self.winfo_fpixels("1i") >= 120
        logo = ASSETS / ("rasworx-logo-dark@2x.png" if hi_dpi else "rasworx-logo-dark.png")
        if logo.exists():
            self.logo = tk.PhotoImage(file=str(logo))
            ttk.Label(header, image=self.logo, style="Page.TLabel").grid(row=0, column=0, rowspan=2, sticky="w")
        ttk.Label(header, text="Kokoro narration", style="Title.TLabel").grid(row=0, column=1, sticky="se")
        ttk.Label(header, text="Text or Markdown to MP3, offline", style="Page.TLabel").grid(
            row=1, column=1, sticky="ne")
        self.clear_btn = ttk.Button(header, text="Clear", style="Page.TButton", command=self._clear)
        self.clear_btn.grid(row=0, column=2, rowspan=2, padx=(14, 0))
        tk.Frame(page, background=BLUE, height=2).grid(row=0, column=0, columnspan=2, sticky="sew")

        f = ttk.Frame(page, padding=16)  # the card
        f.grid(row=1, column=0, sticky="nsew")
        f.columnconfigure(1, weight=1)
        f.rowconfigure(2, weight=1)
        pad = {"padx": 4, "pady": 4}

        def key(text, row):
            ttk.Label(f, text=text.upper(), style="Key.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 12))

        key("Input", 0)
        row = ttk.Frame(f)
        row.grid(row=0, column=1, sticky="ew", **pad)
        row.columnconfigure(1, weight=1)
        ttk.Radiobutton(row, text="File", value="file", variable=self.mode, command=self._on_mode).grid(
            row=0, column=0, padx=(0, 8))
        ttk.Entry(row, textvariable=self.file_var, state="readonly").grid(row=0, column=1, sticky="ew", padx=4)
        self.browse_btn = ttk.Button(row, text="Browse", command=self._browse)
        self.browse_btn.grid(row=0, column=2)
        ttk.Radiobutton(f, text="Paste", value="paste", variable=self.mode, command=self._on_mode).grid(
            row=1, column=1, sticky="w", **pad)

        box = tk.Frame(f, background=BORDER, padx=1, pady=1)  # 1 px border around the text box
        box.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(2, 10))
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)
        self.text = tk.Text(box, height=8, wrap="word", undo=True, font=self.fonts["body"], relief="flat",
                            borderwidth=0, padx=10, pady=8, foreground=TEXT_STRONG, insertbackground=TEXT_STRONG,
                            selectbackground=BLUE, selectforeground="#FFFFFF", highlightthickness=0)
        self.text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(box, command=self.text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=scroll.set)
        self.text.bind("<<Modified>>", self._on_text_change)
        self.text.bind("<Control-a>", lambda e: (self.text.tag_add("sel", "1.0", "end-1c"), "break")[1])

        key("Name", 3)
        row = ttk.Frame(f)
        row.grid(row=3, column=1, sticky="ew", **pad)
        self.name_entry = ttk.Entry(row, textvariable=self.name_var, width=30)
        self.name_entry.grid(row=0, column=0)
        self.name_entry.bind("<Key>", lambda e: self.after_idle(self._on_name_key))
        ttk.Label(row, textvariable=self.out_var, style="Muted.TLabel").grid(row=0, column=1, padx=10)

        key("Mood", 4)
        mood = ttk.Combobox(f, textvariable=self.mood_var, values=[m[0] for m in MOODS], state="readonly", width=22)
        mood.grid(row=4, column=1, sticky="w", **pad)
        mood.bind("<<ComboboxSelected>>", self._on_mood)

        key("Voice", 5)
        row = ttk.Frame(f)
        row.grid(row=5, column=1, sticky="w", **pad)
        ttk.Combobox(row, textvariable=self.voice_var, values=VOICES, width=22).grid(row=0, column=0)
        ttk.Label(row, text="SPEED", style="Key.TLabel").grid(row=0, column=1, padx=(18, 6))
        ttk.Spinbox(row, textvariable=self.speed_var, from_=SPEED_RANGE[0], to=SPEED_RANGE[1], increment=0.05,
                    format="%.2f", width=6).grid(row=0, column=2)
        ttk.Label(row, text="PAUSE", style="Key.TLabel").grid(row=0, column=3, padx=(18, 6))
        ttk.Spinbox(row, textvariable=self.pause_var, from_=PAUSE_RANGE[0], to=PAUSE_RANGE[1], increment=0.1,
                    format="%.2f", width=6).grid(row=0, column=4)
        ttk.Label(row, text="s", style="Muted.TLabel").grid(row=0, column=5, padx=4)

        # Script check row (hidden when the tts-output linter is not installed)
        self.lint_row = ttk.Frame(f)
        self.lint_row.columnconfigure(1, weight=1)
        ttk.Label(self.lint_row, text="SCRIPT CHECK", style="Key.TLabel").grid(row=0, column=0, padx=(0, 12))
        self.lint_label = ttk.Label(self.lint_row, textvariable=self.lint_var)
        self.lint_label.grid(row=0, column=1, sticky="w")
        self.lint_label.bind("<Button-1>", lambda e: self._show_warning_popup())
        self.lint_view = ttk.Button(self.lint_row, text="View ▸", style="Link.TButton",
                                    command=self._show_warning_popup)
        if LINTER.exists():
            self.lint_row.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        row = ttk.Frame(page, style="Page.TFrame")
        row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(14, 4))
        row.columnconfigure(2, weight=1)
        self.convert_btn = ttk.Button(row, text="CONVERT", style="Primary.TButton", command=self._convert,
                                      state="disabled")
        self.convert_btn.grid(row=0, column=0)
        self.cancel_btn = ttk.Button(row, text="Cancel", style="Page.TButton", command=self._cancel,
                                     state="disabled")
        self.cancel_btn.grid(row=0, column=1, padx=8)
        self.progress = ttk.Progressbar(row, mode="determinate", style="Brand.Horizontal.TProgressbar")
        self.progress.grid(row=0, column=2, sticky="ew", padx=4)
        ttk.Label(row, textvariable=self.progress_var, style="Page.TLabel", width=12).grid(row=0, column=3)

        self.status = ttk.Label(page, textvariable=self.status_var, style="Status.TLabel", wraplength=600)
        self.status.grid(row=3, column=0, columnspan=2, sticky="w", pady=4)
        page.bind("<Configure>", lambda e: self.status.configure(wraplength=max(300, e.width - 40)))

        row = ttk.Frame(page, style="Page.TFrame")
        row.grid(row=4, column=0, columnspan=2, sticky="w")
        self.play_btn = ttk.Button(row, text="Play", style="Page.TButton", command=self._play, state="disabled")
        self.play_btn.grid(row=0, column=0)
        ttk.Button(row, text="Open Input Folder", style="Page.TButton",
                   command=lambda: self._open_folder(INPUT_DIR)).grid(row=0, column=1, padx=8)
        ttk.Button(row, text="Open Output Folder", style="Page.TButton",
                   command=lambda: self._open_folder(OUTPUT_DIR)).grid(row=0, column=2)

        self._build_files(page)

    def _build_files(self, page):
        panel = ttk.Frame(page, padding=16)
        panel.grid(row=1, column=1, sticky="nsew", padx=(14, 0))
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)
        ttk.Label(panel, text="OUTPUT FILES", style="Key.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        box = tk.Frame(panel, background=BORDER, padx=1, pady=1)
        box.grid(row=1, column=0, sticky="nsew")
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)
        self.files = ttk.Treeview(box, columns=("length", "date"), selectmode="extended", style="Brand.Treeview")
        self.files.heading("#0", text="Name", anchor="w")
        self.files.heading("length", text="Length", anchor="e")
        self.files.heading("date", text="Date", anchor="w")
        self.files.column("#0", width=160, minwidth=100, stretch=True)
        self.files.column("length", width=60, minwidth=50, anchor="e", stretch=False)
        self.files.column("date", width=125, minwidth=110, stretch=False)
        self.files.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(box, command=self.files.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.files.configure(yscrollcommand=scroll.set)
        self.files.bind("<Double-1>", lambda e: self._play_selected())
        self.files.bind("<<TreeviewSelect>>", lambda e: self._update_file_buttons())
        self.files.bind("<Delete>", lambda e: self._delete_selected())
        row = ttk.Frame(panel)
        row.grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.file_play_btn = ttk.Button(row, text="Play selected", command=self._play_selected, state="disabled")
        self.file_play_btn.grid(row=0, column=0)
        self.file_delete_btn = ttk.Button(row, text="Delete selected", command=self._delete_selected,
                                          state="disabled")
        self.file_delete_btn.grid(row=0, column=1, padx=6)
        ttk.Button(row, text="Refresh", style="Link.TButton", command=self._refresh_files).grid(row=0, column=2)

    def _set_status(self, message, kind="Status"):
        self.status_var.set(message)
        self.status.configure(style=f"{kind}.TLabel")

    # ---------- input and settings ----------

    def _on_mode(self):
        paste = self.mode.get() == "paste"
        self.text.configure(state="normal" if paste else "disabled", background=FIELD if paste else FIELD_OFF)
        self.browse_btn.configure(state="disabled" if paste else "normal")
        if paste:
            self.name_entry.configure(state="normal")
            self.name_var.set(self.paste_name)
            self.text.focus_set()
        else:
            self.paste_name = self.name_var.get()
            self.name_entry.configure(state="readonly")
            self.name_var.set(Path(self.file_var.get()).stem if self.file_var.get() else "")

    def _browse(self):
        path = filedialog.askopenfilename(
            parent=self, initialdir=INPUT_DIR, title="Pick a script",
            filetypes=[("Scripts", "*.txt *.md *.markdown"), ("All files", "*.*")])
        if path:
            self.file_var.set(str(Path(path)))
            self.name_var.set(Path(path).stem)
            self._start_lint(Path(path))

    def _on_text_change(self, _event):
        self.text.edit_modified(False)
        if self.mode.get() == "paste" and not self.name_touched:
            self.name_var.set(slugify(self.text.get("1.0", "end-1c")))

    def _on_name_key(self):
        if self.mode.get() == "paste":
            self.name_touched = bool(self.name_var.get())

    def _update_out_label(self):
        name = self.name_var.get()
        self.out_var.set(f"→  output\\{name}.mp3" if name else "")

    def _on_mood(self, _event=None):
        _, voice, speed, pause = next(m for m in MOODS if m[0] == self.mood_var.get())
        self.applying_mood = True
        try:
            if voice:
                self.voice_var.set(voice)
            self.speed_var.set(f"{speed:.2f}")
            self.pause_var.set(f"{pause:.2f}")
        finally:
            self.applying_mood = False

    def _on_setting_edit(self, *_):
        if not self.applying_mood:
            self.mood_var.set("Custom")

    @staticmethod
    def _number(var, bounds):
        try:
            value = float(var.get())
        except ValueError:
            return None
        return value if bounds[0] <= value <= bounds[1] else None

    def _settings(self):
        """Validated (voice, speed, pause); shows an error and returns None when something is wrong."""
        voice = self.voice_var.get().strip().replace(" ", "")
        try:
            speed, pause = float(self.speed_var.get()), float(self.pause_var.get())
        except ValueError:
            return self._error("Speed and Pause must be numbers.")
        if not SPEED_RANGE[0] <= speed <= SPEED_RANGE[1]:
            return self._error(f"Speed must be between {SPEED_RANGE[0]:.2f} and {SPEED_RANGE[1]:.2f}.")
        if not PAUSE_RANGE[0] <= pause <= PAUSE_RANGE[1]:
            return self._error(f"Pause must be between {PAUSE_RANGE[0]:.1f} and {PAUSE_RANGE[1]:.1f} seconds.")
        if not voice:
            return self._error("Pick a voice.")
        try:
            resolve_voice(voice)
        except SystemExit as exc:  # missing .pt file
            return self._error(str(exc))
        return voice, speed, pause

    # ---------- script check ----------

    def _start_lint(self, path, temp=False):
        if not LINTER.exists():
            return
        self.lint_seq += 1
        self.lint_var.set("checking...")
        self._show_warnings([])
        run_in_thread(self._lint_worker, self.lint_seq, path, temp)

    def _lint_worker(self, seq, path, temp):
        try:
            self.events.put(("lint", seq, *lint(path)))
        except Exception as exc:
            log.exception("script check failed")
            self.events.put(("lint", seq, f"failed ({exc})", []))
        finally:
            if temp:
                path.unlink(missing_ok=True)

    def _show_warnings(self, warnings):
        self.warnings = list(warnings)
        if warnings:
            self.lint_view.grid(row=0, column=2)
            self.lint_label.configure(cursor="hand2")
        else:
            self.lint_view.grid_remove()
            self.lint_label.configure(cursor="")
            if self.popup is not None and self.popup.winfo_exists():
                self.popup.destroy()

    def _show_warning_popup(self):
        if not self.warnings:
            return
        if self.popup is not None and self.popup.winfo_exists():
            self.popup.destroy()
        win = self.popup = tk.Toplevel(self, background=CHARCOAL)
        win.title("Script check warnings")
        win.geometry("640x360")
        win.minsize(420, 200)
        win.transient(self)
        try:
            win.iconbitmap(str(ASSETS / "app.ico"))
        except tk.TclError:
            pass
        ttk.Label(win, text=self.lint_var.get(), style="Page.TLabel").pack(anchor="w", padx=16, pady=(14, 8))
        box = tk.Frame(win, background=BORDER, padx=1, pady=1)
        box.pack(fill="both", expand=True, padx=16)
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)
        text = tk.Text(box, wrap="word", font=self.fonts["body"], relief="flat", background=WARNING_BG,
                       foreground=WARNING, padx=12, pady=10, highlightthickness=0, spacing3=4)
        text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(box, command=text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        text.configure(yscrollcommand=scroll.set)
        text.insert("1.0", "\n".join(self.warnings))
        text.configure(state="disabled")
        ttk.Button(win, text="Close", style="Page.TButton", command=win.destroy).pack(anchor="e", padx=16, pady=12)
        win.bind("<Escape>", lambda e: win.destroy())
        dark_title_bar(win)
        win.focus_set()

    # ---------- model and conversion ----------

    def _start_model_load(self):
        self._set_status("Loading model...", "Busy")
        run_in_thread(self._load_worker)

    def _load_worker(self):
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self.events.put(("status", f"Loading model on {device}..."))
            self.engine.load("a")
            self.events.put(("ready", self.engine.device))
        except Exception as exc:
            log.exception("model load failed")
            self.events.put(("fatal", f"Could not load the Kokoro model: {exc}"))

    def _convert(self):
        settings = self._settings()
        if not settings:
            return
        name = self.name_var.get().strip()
        if self.mode.get() == "file":
            source = Path(self.file_var.get()) if self.file_var.get() else None
            if not source or not source.is_file():
                return self._error("Pick a script file first (Browse).")
            name = source.stem
        else:
            pasted = self.text.get("1.0", "end-1c")
            if not pasted.strip():
                return self._error("Paste some text first.")
            if not NAME_OK.match(name):
                return self._error("Name may only use letters, digits, - and _.")
            source = INPUT_DIR / f"{name}.md"
            if source.exists() and not self._confirm(f"input\\{source.name} already exists. Overwrite it?"):
                return

        out = OUTPUT_DIR / f"{name}.mp3"
        if out.exists() and not self._confirm(f"output\\{out.name} already exists. Overwrite it?"):
            return

        if self.mode.get() == "paste":
            try:
                INPUT_DIR.mkdir(exist_ok=True)
                source.write_text(pasted, encoding="utf-8")
            except OSError as exc:
                return self._error(f"Could not save {source}: {exc}")
            fd, tmp = tempfile.mkstemp(suffix=".md", prefix="kokoro-check-")
            os.close(fd)
            Path(tmp).write_text(pasted, encoding="utf-8")
            self._start_lint(Path(tmp), temp=True)
        else:
            self._start_lint(source)

        self.busy = True
        self.stop_event.clear()
        self._update_buttons()
        self.progress.configure(value=0, maximum=1)
        self.progress_var.set("")
        self._set_status(f"Converting {source.name}...", "Busy")
        run_in_thread(self._convert_worker, source, out, *settings)

    def _convert_worker(self, source, out, voice, speed, pause):
        start = time.perf_counter()
        try:
            text = load_text(source)
            path, seconds = self.engine.render(
                text, voice, speed, pause, out,
                progress=lambda i, n: self.events.put(("progress", i, n)),
                stop=self.stop_event.is_set)
            self.events.put(("done", path, seconds, time.perf_counter() - start))
        except Cancelled:
            self.events.put(("cancelled",))
        except Exception as exc:
            log.exception("conversion failed")
            self.events.put(("error", f"Conversion failed: {exc}"))

    def _cancel(self):
        self.stop_event.set()
        self.cancel_btn.configure(state="disabled")
        self._set_status("Cancelling after this paragraph...", "Busy")

    def _poll(self):
        try:
            while True:
                kind, *data = self.events.get_nowait()
                self._handle(kind, data)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _handle(self, kind, data):
        if kind == "status":
            self._set_status(data[0], "Busy")
        elif kind == "ready":
            self.ready = True
            self._set_status(f"Ready (model on {data[0]})", "Success")
        elif kind == "fatal":
            self._error(data[0])
        elif kind == "lint":
            seq, summary, warnings = data
            if seq == self.lint_seq:
                self.lint_var.set(summary)
                self._show_warnings(warnings)
        elif kind == "progress":
            i, n = data
            self.progress.configure(maximum=n, value=i - 1)
            self.progress_var.set(f"para {i}/{n}")
        elif kind == "done":
            path, seconds, took = data
            self.busy = False
            self.last_out = path
            self.progress.configure(value=self.progress["maximum"])
            where = f"{path.parent.name}\\{path.name}"
            if path.suffix.lower() == ".wav":
                self._set_status(f"MP3 export failed, saved WAV instead: {where} "
                                 f"({seconds / 60:.1f} min in {took:.0f} s). See ui.log.", "Error")
            else:
                self._set_status(f"Saved {where} ({seconds / 60:.1f} min in {took:.0f} s)", "Success")
            log.info("saved %s (%.1f min in %.0f s)", path, seconds / 60, took)
            self._refresh_files()
        elif kind == "cancelled":
            self.busy = False
            self.progress.configure(value=0)
            self.progress_var.set("")
            self._set_status("Cancelled. No MP3 was written.")
        elif kind == "error":
            self.busy = False
            self._error(data[0])
        self._update_buttons()

    def _update_buttons(self):
        self.convert_btn.configure(state="normal" if self.ready and not self.busy else "disabled")
        self.cancel_btn.configure(state="normal" if self.busy and not self.stop_event.is_set() else "disabled")
        have_out = self.last_out is not None and self.last_out.exists() and not self.busy
        self.play_btn.configure(state="normal" if have_out else "disabled")
        self.clear_btn.configure(state="disabled" if self.busy else "normal")

    # ---------- after conversion ----------

    def _play(self):
        try:
            os.startfile(self.last_out)
        except OSError as exc:
            self._error(f"Could not play {self.last_out}: {exc}")

    def _open_folder(self, folder):
        try:
            folder.mkdir(exist_ok=True)
            os.startfile(folder)
        except OSError as exc:
            self._error(f"Could not open {folder}: {exc}")

    def _clear(self):
        """Back to the just-opened state. Keeps the loaded model and the Mood / Voice / Speed / Pause settings."""
        if self.busy:
            return
        self.mode.set("file")
        self.file_var.set("")
        self.paste_name = ""
        self.name_touched = False
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.edit_reset()
        self._on_mode()
        self.name_var.set("")
        self.lint_seq += 1  # drop any check still running
        self.lint_var.set(LINT_IDLE)
        self._show_warnings([])
        self.progress.configure(value=0, maximum=1)
        self.progress_var.set("")
        self.last_out = None
        if self.ready:
            self._set_status(f"Ready (model on {self.engine.device})", "Success")
        else:
            self._set_status("Loading model...", "Busy")
        self._update_buttons()

    # ---------- output file list ----------

    def _output_files(self):
        try:
            files = [p for p in OUTPUT_DIR.iterdir() if p.is_file() and p.suffix.lower() in (".mp3", ".wav")]
        except OSError:
            return []
        return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)

    def _refresh_files(self):
        selected = set(self.files.selection())
        self.files.delete(*self.files.get_children())
        for path in self._output_files():
            stat = path.stat()
            key = (str(path), stat.st_mtime)
            if key not in self.lengths:
                self.lengths[key] = audio_length(path)
            seconds = self.lengths[key]
            length = "?" if seconds is None else f"{int(seconds // 60)}:{int(seconds % 60):02d}"
            date = time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime))
            self.files.insert("", "end", iid=str(path), text=path.name, values=(length, date))
            if str(path) in selected:
                self.files.selection_add(str(path))
        self._update_file_buttons()

    def _update_file_buttons(self):
        state = "normal" if self.files.selection() else "disabled"
        self.file_play_btn.configure(state=state)
        self.file_delete_btn.configure(state=state)

    def _play_selected(self):
        selection = self.files.selection()
        if selection:
            try:
                os.startfile(selection[0])
            except OSError as exc:
                self._error(f"Could not play {selection[0]}: {exc}")

    def _delete_selected(self):
        paths = [Path(p) for p in self.files.selection()]
        if not paths:
            return
        names = "\n".join(f"  {p.name}" for p in paths[:15])
        if len(paths) > 15:
            names += f"\n  ...and {len(paths) - 15} more"
        count = f"{len(paths)} file{'' if len(paths) == 1 else 's'}"
        if not messagebox.askyesno("Delete files?", f"Permanently delete {count} from output\\?\n\n{names}",
                                   icon="warning", default="no", parent=self):
            return
        failed = []
        for path in paths:
            try:
                path.unlink()
                log.info("deleted %s", path)
            except OSError as exc:
                log.exception("could not delete %s", path)
                failed.append(f"{path.name}: {exc}")
        if self.last_out is not None and not self.last_out.exists():
            self.last_out = None
        self._refresh_files()
        self._update_buttons()
        if failed:
            self._error("Could not delete: " + "; ".join(failed))
        else:
            self._set_status(f"Deleted {count}.")

    # ---------- helpers ----------

    def _confirm(self, message):
        return messagebox.askyesno("Overwrite?", message, icon="warning", default="no", parent=self)

    def _error(self, message):
        log.error(message)
        self._set_status(message, "Error")
        messagebox.showerror("Kokoro narration", message, parent=self)
        return None

    def report_callback_exception(self, exc, val, tb):
        log.error("UI error:\n%s", "".join(traceback.format_exception(exc, val, tb)))
        self._error(f"Unexpected error: {val}")

    def _on_close(self):
        speed, pause = self._number(self.speed_var, SPEED_RANGE), self._number(self.pause_var, PAUSE_RANGE)
        voice = self.voice_var.get().strip().replace(" ", "")
        defaults = load_settings()
        save_settings({"mood": self.mood_var.get(), "voice": voice or defaults["voice"],
                       "speed": defaults["speed"] if speed is None else speed,
                       "pause": defaults["pause"] if pause is None else pause})
        self.stop_event.set()
        self.destroy()


def setup_logging():
    """pythonw.exe has no console: send print(), warnings and errors to ui.log instead."""
    stream = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = stream
    logging.basicConfig(stream=stream, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.captureWarnings(True)
    log.info("---- ui started ----")


def main():
    setup_logging()
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # sharp text on scaled displays
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("RasWorx.KokoroNarration")  # own taskbar icon
    except Exception:
        pass
    App().mainloop()


if __name__ == "__main__":
    main()
