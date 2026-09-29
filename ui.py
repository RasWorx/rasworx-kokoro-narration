"""Desktop window for turning a script (picked file or pasted text) into an MP3 with Kokoro-82M.

Launch with ui.bat (runs .venv\\Scripts\\pythonw.exe ui.py, no console window).
Reuses generate.py for text cleaning, synthesis and MP3 export, so the output matches the CLI.
Styled after the RasWorx brand guide (dark palette, primary blue #046FCC, Montserrat).
"""

import io
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
import winsound
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

import soundfile as sf

import generate
from generate import (
    DEFAULT_VOICE, EXTENSIONS, INPUT_DIR, OUTPUT_DIR, ROOT, SAMPLE_RATE,
    accent_of, load_text, paragraphs_of, parse_pronunciations, prepare_text, render_audio, resolve_voice, write_mp3,
)
from ui_theme import (
    BLUE, BORDER, CHARCOAL, ERROR, FIELD, FIELD_OFF, SUCCESS, TEXT_MUTED, TEXT_STRONG, WARNING, WARNING_BG,
    apply_theme, dark_title_bar,
)
from version import __version__

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
LOADING = "Loading the Kokoro model... the first start can take about a minute."
SPEED_RANGE = (0.70, 1.30)
PAUSE_RANGE = (0.0, 3.0)
PREVIEW_CHARS = 300  # about 15-20 s of speech
FILE_PREVIEW_CHARS = 50_000
NAME_OK = re.compile(r"^[A-Za-z0-9_-]+$")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
PRON_HELP = ("One entry per line: word = how to say it. Use a respelling (Nkosi = en-KO-see) or exact sounds "
             "between slashes (Kokoro = /kˈOkəɹO/). Whole words only, any capitals. Lines starting with # are notes. "
             "The dictionary applies to every conversion and preview.")
PRON_TEMPLATE = "# Pronunciation dictionary. One entry per line:  word = respelling   or   word = /IPA/\n# Kokoro = ko-ko-ro\n"

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

    def render(self, text, voice, speed, pause, out, progress=None, stop=None, normalize=True):
        """Synthesize text into out (.mp3, or .wav if MP3 export fails). Returns (path, audio seconds)."""
        audio = render_audio(self.pipeline(accent_of(voice)), text, resolve_voice(voice), speed, pause, normalize,
                             progress, stop)
        if audio is None:
            raise Cancelled
        out.parent.mkdir(parents=True, exist_ok=True)
        return write_mp3(audio, out), len(audio) / SAMPLE_RATE

    def preview(self, text, voice, speed, normalize=True):
        """Render the opening of the text. Returns (WAV bytes, seconds); nothing is written to disk."""
        audio = render_audio(self.pipeline(accent_of(voice)), preview_excerpt(text), resolve_voice(voice), speed, 0.0,
                             normalize, progress=lambda i, n: None)
        buffer = io.BytesIO()
        sf.write(buffer, audio, SAMPLE_RATE, format="WAV", subtype="PCM_16")
        return buffer.getvalue(), len(audio) / SAMPLE_RATE


class Tooltip:
    """Small hover hint at the pointer. `text` is a string or a callable returning one (empty = no tip)."""

    def __init__(self, widget, text, font):
        self.widget, self.text, self.font = widget, text, font
        self.tip = self.job = None
        widget.bind("<Enter>", self.schedule, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def schedule(self, _event=None):
        self.hide()
        self.job = self.widget.after(500, self.show)

    def show(self):
        self.job = None
        text = self.text() if callable(self.text) else self.text
        if not text or self.tip is not None:
            return
        self.tip = tip = tk.Toplevel(self.widget)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{self.widget.winfo_pointerx() + 12}+{self.widget.winfo_pointery() + 18}")
        tk.Label(tip, text=text, background=FIELD, foreground=TEXT_STRONG, font=self.font, padx=8, pady=4,
                 highlightbackground=BORDER, highlightthickness=1, borderwidth=0).pack()

    def hide(self, _event=None):
        if self.job is not None:
            self.widget.after_cancel(self.job)
            self.job = None
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None


def slugify(text):
    """File-name slug from the first Markdown heading, or else the first five words."""
    heading = re.search(r"^[ \t]{0,3}#{1,6}[ \t]+(.+)$", text, flags=re.M)
    words = heading.group(1) if heading else " ".join(text.split()[:5])
    words = unicodedata.normalize("NFKD", words).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9_-]+", "-", words).strip("-_")[:60].strip("-_")


def preview_excerpt(text, limit=PREVIEW_CHARS):
    """The opening of the spoken text, cut at a sentence end, at most `limit` characters."""
    out, size = [], 0
    for para in paragraphs_of(text):
        room = limit - size
        if len(para) > room:
            cut = para[:room]
            ends = [m.end() for m in re.finditer(r"[.!?][\"')]*(?:\s|$)", cut)]
            para = cut[:ends[-1]].strip() if ends else (cut.rsplit(" ", 1)[0] if " " in cut else cut).rstrip(",;:") + "."
            out.append(para)
            break
        out.append(para)
        size += len(para)
        if size >= limit * 2 // 3:
            break
    return "\n\n".join(out)


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
    """Saved settings; anything missing, invalid or out of range keeps its default."""
    out = {"mood": "Custom", "voice": DEFAULT_VOICE, "speed": 1.00, "pause": 0.40, "normalize": True}
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
    if isinstance(data.get("normalize"), bool):
        out["normalize"] = data["normalize"]
    return out


def save_settings(data):
    try:
        SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        log.exception("could not save settings")


def audio_length(path):
    """Length of an audio file in seconds, or None if it cannot be read."""
    try:
        return sf.info(str(path)).duration
    except Exception:
        return None


def run_in_thread(fn, *args):
    threading.Thread(target=fn, args=args, daemon=True).start()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Kokoro narration {__version__}")
        self.minsize(1200, 700)
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
        self.preview_state = "idle"  # idle | rendering | playing
        self.preview_seq = 0
        self.preview_files = []  # temp WAVs of previews, removed when they finish
        self.lint_seq = 0
        self.warnings = []
        self.popup = None
        self.pron_win = None
        self.lengths = {}  # (path, mtime) -> seconds, so the file list does not re-read every MP3
        self.applying_mood = False
        self.name_touched = False  # paste mode: stop auto-naming once the user edits the name
        self.box_mode = None  # what the big text box currently holds: "paste" or "file" (a read-only preview)
        self.paste_text = ""
        self.paste_name = ""
        self._named_from = ""
        self.hover_row = ""
        self.dnd = self._init_dnd()

        self.mode = tk.StringVar(value="file")
        self.file_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.out_var = tk.StringVar()
        saved = load_settings()
        self.mood_var = tk.StringVar(value=saved["mood"])
        self.voice_var = tk.StringVar(value=saved["voice"])
        self.speed_var = tk.StringVar(value=f"{saved['speed']:.2f}")
        self.pause_var = tk.StringVar(value=f"{saved['pause']:.2f}")
        self.normalize_var = tk.BooleanVar(value=saved["normalize"])
        self.lint_var = tk.StringVar(value=LINT_IDLE)
        self.progress_var = tk.StringVar()
        self.status_var = tk.StringVar()

        self._build()
        self.name_var.trace_add("write", lambda *_: self._update_out_label())
        for var in (self.voice_var, self.speed_var, self.pause_var):
            var.trace_add("write", self._on_setting_edit)
        self._on_mode()
        self._bind_keys()
        self._refresh_files()
        self._update_buttons()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        dark_title_bar(self)
        self.state("zoomed")  # start maximized
        self.after(100, self._poll)
        self._start_model_load()

    def _init_dnd(self):
        """Load drag-and-drop support (tkinterdnd2). Without it the window still works, just without drops."""
        try:
            from tkinterdnd2 import TkinterDnD
            TkinterDnD._require(self)
            return True
        except Exception:
            log.warning("drag and drop is unavailable", exc_info=True)
            return False

    # ---------- layout ----------

    def _card(self, parent, **grid):
        """A slate panel with a 1 px border; returns the inner frame."""
        edge = tk.Frame(parent, background=BORDER, padx=1, pady=1)
        edge.grid(**grid)
        edge.columnconfigure(0, weight=1)
        edge.rowconfigure(0, weight=1)
        card = ttk.Frame(edge, padding=16)
        card.grid(sticky="nsew")
        return card

    def _build(self):
        small = self.fonts["small"]
        page = ttk.Frame(self, style="Page.TFrame", padding=(20, 14, 20, 16))
        page.pack(fill="both", expand=True)
        page.columnconfigure(0, weight=1, minsize=660, uniform="cols")
        page.columnconfigure(1, weight=1, minsize=460, uniform="cols")
        page.rowconfigure(1, weight=1)

        header = ttk.Frame(page, style="Page.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        header.columnconfigure(1, weight=1)
        hi_dpi = self.winfo_fpixels("1i") >= 120
        logo = ASSETS / ("rasworx-logo-dark@2x.png" if hi_dpi else "rasworx-logo-dark.png")
        if logo.exists():
            self.logo = tk.PhotoImage(file=str(logo))
            ttk.Label(header, image=self.logo, style="Page.TLabel").grid(row=0, column=0, rowspan=2, sticky="w")
        ttk.Label(header, text="Kokoro narration", style="Title.TLabel").grid(row=0, column=1, sticky="se")
        ttk.Label(header, text=f"v{__version__}   ·   Text or Markdown to MP3, offline", style="Page.TLabel").grid(
            row=1, column=1, sticky="ne")
        self.clear_btn = ttk.Button(header, text="Clear", style="Page.TButton", command=self._clear)
        self.clear_btn.grid(row=0, column=2, rowspan=2, padx=(14, 0))
        Tooltip(self.clear_btn, "Start over  (Ctrl+L)", small)
        tk.Frame(page, background=BLUE, height=2).grid(row=0, column=0, columnspan=2, sticky="sew")

        f = self._card(page, row=1, column=0, sticky="nsew")
        f.columnconfigure(1, weight=1)
        f.rowconfigure(1, weight=1)
        pad = {"padx": 4, "pady": 5}

        def key(text, row):
            ttk.Label(f, text=text.upper(), style="Key.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 14))

        # Input: File | Paste segmented control, path, Browse
        key("Input", 0)
        row = ttk.Frame(f)
        row.grid(row=0, column=1, sticky="ew", **pad)
        row.columnconfigure(1, weight=1)
        seg = ttk.Frame(row)
        seg.grid(row=0, column=0)
        for column, (label, value) in enumerate((("File", "file"), ("Paste", "paste"))):
            ttk.Radiobutton(seg, text=label, value=value, variable=self.mode, command=self._on_mode,
                            style="Seg.Toolbutton").grid(row=0, column=column)
        ttk.Entry(row, textvariable=self.file_var, state="readonly").grid(row=0, column=1, sticky="ew", padx=10)
        self.browse_btn = ttk.Button(row, text="Browse", command=self._browse)
        self.browse_btn.grid(row=0, column=2)
        Tooltip(self.browse_btn, "Pick a script  (Ctrl+O)", small)

        # Text box: pasted text, or a read-only preview of the picked file. Also the drop zone.
        self.drop_edge = tk.Frame(f, background=BORDER, padx=1, pady=1)
        self.drop_edge.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(4, 12))
        self.drop_edge.columnconfigure(0, weight=1)
        self.drop_edge.rowconfigure(0, weight=1)
        self.text = tk.Text(self.drop_edge, width=10, height=8, wrap="word", undo=True, font=self.fonts["body"],
                            relief="flat", borderwidth=0, padx=10, pady=8, foreground=TEXT_STRONG,
                            insertbackground=TEXT_STRONG, selectbackground=BLUE, selectforeground="#FFFFFF",
                            highlightthickness=0)
        self.text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(self.drop_edge, command=self.text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=scroll.set)
        self.text.bind("<<Modified>>", self._on_text_change)
        self.text.bind("<Control-a>", lambda e: (self.text.tag_add("sel", "1.0", "end-1c"), "break")[1])
        for sequence, step in (("<Tab>", "tk_focusNext"), ("<Shift-Tab>", "tk_focusPrev")):  # Tab leaves the box
            self.text.bind(sequence, lambda e, step=step: (getattr(e.widget, step)().focus(), "break")[1])
        self.hint = tk.Label(self.text, font=self.fonts["body"], foreground=TEXT_MUTED, justify="center", cursor="hand2")
        self.hint.bind("<Button-1>", self._on_hint_click)
        if self.dnd:
            self._enable_drop()

        key("Name", 2)
        row = ttk.Frame(f)
        row.grid(row=2, column=1, sticky="ew", **pad)
        self.name_entry = ttk.Entry(row, textvariable=self.name_var, width=30)
        self.name_entry.grid(row=0, column=0)
        self.name_entry.bind("<Key>", lambda e: self.after_idle(self._on_name_key))
        ttk.Label(row, textvariable=self.out_var, style="Muted.TLabel").grid(row=0, column=1, padx=10)

        key("Mood", 3)
        mood = ttk.Combobox(f, textvariable=self.mood_var, values=[m[0] for m in MOODS], state="readonly", width=22)
        mood.grid(row=3, column=1, sticky="w", **pad)
        mood.bind("<<ComboboxSelected>>", self._on_mood)

        key("Voice", 4)
        row = ttk.Frame(f)
        row.grid(row=4, column=1, sticky="w", **pad)
        ttk.Combobox(row, textvariable=self.voice_var, values=VOICES, width=22).grid(row=0, column=0)
        ttk.Label(row, text="SPEED", style="Key.TLabel").grid(row=0, column=1, padx=(18, 6))
        ttk.Spinbox(row, textvariable=self.speed_var, from_=SPEED_RANGE[0], to=SPEED_RANGE[1], increment=0.05,
                    format="%.2f", width=6).grid(row=0, column=2)
        ttk.Label(row, text="PAUSE", style="Key.TLabel").grid(row=0, column=3, padx=(18, 6))
        ttk.Spinbox(row, textvariable=self.pause_var, from_=PAUSE_RANGE[0], to=PAUSE_RANGE[1], increment=0.1,
                    format="%.2f", width=6).grid(row=0, column=4)
        ttk.Label(row, text="s", style="Muted.TLabel").grid(row=0, column=5, padx=4)

        key("Audio", 5)
        row = ttk.Frame(f)
        row.grid(row=5, column=1, sticky="ew", **pad)
        row.columnconfigure(1, weight=1)
        normalize = ttk.Checkbutton(row, text="Normalize loudness", variable=self.normalize_var)
        normalize.grid(row=0, column=0)
        self.preview_btn = ttk.Button(row, text="Preview", command=self._preview, state="disabled")
        self.preview_btn.grid(row=0, column=2)
        Tooltip(self.preview_btn, self._preview_tip, small)
        Tooltip(normalize, "Raise the volume to about podcast level. Kokoro's own output is quiet.", small)

        # Script check row (hidden when the tts-output linter is not installed) plus the pronunciation dictionary
        self.lint_row = ttk.Frame(f)
        self.lint_row.columnconfigure(3, weight=1)
        ttk.Label(self.lint_row, text="SCRIPT CHECK", style="Key.TLabel").grid(row=0, column=0, padx=(0, 14))
        self.lint_chip = ttk.Label(self.lint_row, textvariable=self.lint_var, style="Chip.TLabel")
        self.lint_chip.grid(row=0, column=1, sticky="w")
        self.lint_chip.bind("<Button-1>", lambda e: self._show_warning_popup())
        self.lint_view = ttk.Button(self.lint_row, text="View ▸", style="Link.TButton",
                                    command=self._show_warning_popup)
        if LINTER.exists():
            self.lint_row.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        pron = ttk.Button(f, text="Pronunciations ▸", style="Link.TButton", command=self._open_pronunciations)
        pron.grid(row=6, column=1, sticky="e", pady=(8, 0))
        Tooltip(pron, "Words Kokoro says wrongly: fix them once for every script", small)

        tk.Frame(f, background=BORDER, height=1).grid(row=7, column=0, columnspan=2, sticky="ew", pady=(14, 14))

        row = ttk.Frame(f)
        row.grid(row=8, column=0, columnspan=2, sticky="ew")
        row.columnconfigure(2, weight=1)
        self.convert_btn = ttk.Button(row, text="LOADING MODEL...", style="Primary.TButton", command=self._convert,
                                      state="disabled", width=18)
        self.convert_btn.grid(row=0, column=0)
        Tooltip(self.convert_btn, self._convert_tip, small)
        self.cancel_btn = ttk.Button(row, text="Cancel", command=self._cancel, state="disabled")
        self.cancel_btn.grid(row=0, column=1, padx=8)
        Tooltip(self.cancel_btn, "Stop after this paragraph  (Esc)", small)
        self.progress = ttk.Progressbar(row, mode="determinate", style="Brand.Horizontal.TProgressbar")
        self.progress.grid(row=0, column=2, sticky="ew", padx=4)
        ttk.Label(row, textvariable=self.progress_var, style="Muted.TLabel", width=12).grid(row=0, column=3)

        self.status = ttk.Label(f, textvariable=self.status_var, style="Status.TLabel", wraplength=560)
        self.status.grid(row=9, column=0, columnspan=2, sticky="w", pady=(10, 0))
        f.bind("<Configure>", lambda e: self.status.configure(wraplength=max(300, e.width - 60)))
        self._set_status(LOADING, "Busy")

        self._build_files(page)

    def _build_files(self, page):
        small = self.fonts["small"]
        panel = self._card(page, row=1, column=1, sticky="nsew", padx=(14, 0))
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)
        head = ttk.Frame(panel)
        head.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        head.columnconfigure(0, weight=1)
        ttk.Label(head, text="OUTPUT FILES", style="Key.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(head, text="Input folder ▸", style="Link.TButton",
                   command=lambda: self._open_folder(INPUT_DIR)).grid(row=0, column=1)
        ttk.Button(head, text="Output folder ▸", style="Link.TButton",
                   command=lambda: self._open_folder(OUTPUT_DIR)).grid(row=0, column=2)

        box = tk.Frame(panel, background=BORDER, padx=1, pady=1)
        box.grid(row=1, column=0, sticky="nsew")
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)
        self.files = ttk.Treeview(box, columns=("length", "date"), selectmode="extended", style="Brand.Treeview")
        self.files.heading("#0", text="Name", anchor="w")
        self.files.heading("length", text="Length", anchor="e")
        self.files.heading("date", text="Date", anchor="w")
        self.files.column("#0", width=200, minwidth=120, stretch=True)
        self.files.column("length", width=70, minwidth=60, anchor="e", stretch=False)
        self.files.column("date", width=110, minwidth=100, stretch=False)
        self.files.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(box, command=self.files.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.files.configure(yscrollcommand=scroll.set)
        self.files.bind("<Double-1>", lambda e: self._play_selected())
        self.files.bind("<<TreeviewSelect>>", lambda e: self._update_file_buttons())
        self.files.bind("<Delete>", lambda e: self._delete_selected())
        self.files.bind("<Motion>", self._on_tree_hover)
        self.files_tip = Tooltip(self.files, lambda: self.hover_row, small)
        self.files_hint = tk.Label(self.files, text="No MP3s yet.\nConvert a script and it appears here.",
                                   font=self.fonts["body"], background=FIELD, foreground=TEXT_MUTED, justify="center")

        row = ttk.Frame(panel)
        row.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        self.file_play_btn = ttk.Button(row, text="Play selected", command=self._play_selected, state="disabled")
        self.file_play_btn.grid(row=0, column=0)
        self.file_delete_btn = ttk.Button(row, text="Delete selected", command=self._delete_selected,
                                          state="disabled")
        self.file_delete_btn.grid(row=0, column=1, padx=8)
        refresh = ttk.Button(row, text="Refresh", style="Link.TButton", command=self._refresh_files)
        refresh.grid(row=0, column=2)
        Tooltip(refresh, "Reload the list  (F5)", small)

    def _set_status(self, message, kind="Status"):
        self.status_var.set(f"●   {message}" if message else "")
        self.status.configure(style=f"{kind}.TLabel")

    def _ready_status(self):
        self._set_status(f"Ready (model on {self.engine.device})", "Success")

    def _convert_tip(self):
        return "Convert  (Ctrl+Enter)" if self.ready else "The Kokoro model is still loading. The first start takes about a minute."

    def _preview_tip(self):
        if self.preview_state == "playing":
            return "Stop the preview  (Ctrl+P)"
        return "Hear the opening of the script with these settings, without saving  (Ctrl+P)"

    # ---------- keyboard ----------

    def _bind_keys(self):
        keys = {"<Control-Return>": self._key_convert, "<Control-o>": self._key_browse,
                "<Control-l>": self._clear, "<Control-p>": self._preview}
        for sequence, action in keys.items():
            handler = lambda e, action=action: (action(), "break")[1]  # "break": the text box must not also act
            self.bind(sequence, handler)
            self.text.bind(sequence, handler)  # it would otherwise insert a line or move the cursor
        self.bind("<Escape>", lambda e: self._cancel() if self.busy and not self.stop_event.is_set() else None)
        self.bind("<F5>", lambda e: self._refresh_files())

    def _key_convert(self):
        if self.ready and not self.busy and self.preview_state != "rendering":
            self._convert()

    def _key_browse(self):
        if not self.busy:
            self._browse()

    # ---------- input and settings ----------

    def _on_mode(self):
        paste = self.mode.get() == "paste"
        if paste:
            if self.box_mode != "paste":
                self._set_box(self.paste_text, True)
            self.box_mode = "paste"
            self.name_entry.configure(state="normal")
            self.name_var.set(self.paste_name)
            self.text.focus_set()
        else:
            if self.box_mode == "paste":
                self.paste_text = self.text.get("1.0", "end-1c")
                self.paste_name = self.name_var.get()
            self.box_mode = "file"
            path = Path(self.file_var.get()) if self.file_var.get() else None
            self._set_box(self._file_preview(path), False)
            self.name_entry.configure(state="readonly")
            self.name_var.set(path.stem if path else "")
        self.browse_btn.configure(state="disabled" if paste else "normal")

    @staticmethod
    def _file_preview(path):
        if path is None:
            return ""
        try:
            with path.open(encoding="utf-8-sig") as handle:
                text = handle.read(FILE_PREVIEW_CHARS + 1)
        except (OSError, UnicodeDecodeError):
            log.exception("could not preview %s", path)
            return ""
        return text[:FILE_PREVIEW_CHARS] + "\n\n... (preview shortened)" if len(text) > FILE_PREVIEW_CHARS else text

    def _set_box(self, content, editable):
        """Fill the big text box. `editable` False makes it a greyed-out, read-only preview."""
        self._named_from = content
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)
        self.text.edit_reset()
        self.text.edit_modified(False)
        self.text.configure(state="normal" if editable else "disabled", background=FIELD if editable else FIELD_OFF)
        self._update_hint()

    def _update_hint(self):
        """The centred empty-state message over the text box."""
        if self.text.get("1.0", "end-1c").strip():
            self.hint.place_forget()
            return
        if self.mode.get() == "paste":
            message = "Paste your script here"
        elif self.file_var.get():
            message = "This file has no readable text"
        elif self.dnd:
            message = "Drop a .txt or .md script here,\nor click Browse"
        else:
            message = "Click Browse to pick a .txt or .md script"
        self.hint.configure(text=message, background=self.text.cget("background"))
        self.hint.place(relx=0.5, rely=0.5, anchor="center")

    def _on_hint_click(self, _event):
        if self.mode.get() == "paste":
            self.text.focus_set()
        elif not self.busy:
            self._browse()

    def _enable_drop(self):
        from tkinterdnd2 import DND_FILES
        for widget in (self.text, self.hint):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<DropEnter>>", self._on_drop_enter)
            widget.dnd_bind("<<DropLeave>>", self._on_drop_leave)
            widget.dnd_bind("<<Drop>>", self._on_drop)

    def _on_drop_enter(self, event):
        self.drop_edge.configure(background=BLUE)
        return event.action

    def _on_drop_leave(self, event):
        self.drop_edge.configure(background=BORDER)
        return event.action

    def _on_drop(self, event):
        self.drop_edge.configure(background=BORDER)
        paths = self.tk.splitlist(event.data)
        if paths:
            # Handled after the drop returns, so an error dialog cannot block the drag source (Explorer)
            self.after(50, self._load_dropped, Path(paths[0]), len(paths))
        return event.action

    def _load_dropped(self, path, count):
        if self.busy:
            self._set_status("Wait for the current conversion to finish, then drop the file again.", "Error")
            return
        self._load_file(path)
        if count > 1:
            self._set_status(f"Loaded {path.name}. Drop one script at a time; the others were ignored.")

    def _browse(self):
        path = filedialog.askopenfilename(
            parent=self, initialdir=INPUT_DIR, title="Pick a script",
            filetypes=[("Scripts", "*.txt *.md *.markdown"), ("All files", "*.*")])
        if path:
            self._load_file(Path(path))

    def _load_file(self, path):
        """Use a script file as the input (picked or dropped)."""
        if path.suffix.lower() not in EXTENSIONS:
            return self._error(f"{path.name} is not a script. Use a .txt, .md or .markdown file.")
        if not path.is_file():
            return self._error(f"{path} is not a file.")
        self.mode.set("file")
        self.file_var.set(str(path))
        self._on_mode()
        self._start_lint(path)

    def _on_text_change(self, _event):
        self.text.edit_modified(False)
        self._update_hint()
        if self.mode.get() == "paste" and not self.name_touched and self.text.cget("state") == "normal":
            content = self.text.get("1.0", "end-1c")
            if content != self._named_from:
                self._named_from = content
                self.name_var.set(slugify(content))

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
        self._set_lint("checking...")
        run_in_thread(self._lint_worker, self.lint_seq, path, temp)

    def _lint_worker(self, seq, path, temp):
        try:
            summary, warnings = lint(path)
            self.events.put(("lint", seq, summary, warnings, "ChipWarn" if warnings else "ChipOk"))
        except Exception as exc:
            log.exception("script check failed")
            self.events.put(("lint", seq, f"failed ({exc})", [], "ChipBad"))
        finally:
            if temp:
                path.unlink(missing_ok=True)

    def _set_lint(self, summary, warnings=(), state="Chip"):
        """Show the script-check result. `state` is the chip style: Chip (idle), ChipOk, ChipWarn or ChipBad."""
        self.lint_var.set(summary)
        self.warnings = list(warnings)
        self.lint_chip.configure(style=f"{state}.TLabel", cursor="hand2" if self.warnings else "")
        if self.warnings:
            self.lint_view.grid(row=0, column=2, padx=(6, 0))
        else:
            self.lint_view.grid_remove()
            if self.popup is not None and self.popup.winfo_exists():
                self.popup.destroy()

    def _show_warning_popup(self):
        if not self.warnings:
            return
        if self.popup is not None and self.popup.winfo_exists():
            self.popup.destroy()
        win = self.popup = self._dialog("Script check warnings", "640x360", (420, 200))
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
        win.focus_set()

    def _dialog(self, title, size, minsize):
        """A dark, brand-styled child window."""
        win = tk.Toplevel(self, background=CHARCOAL)
        win.title(title)
        width, height = (int(n) for n in size.split("x"))
        x = max(0, self.winfo_rootx() + (self.winfo_width() - width) // 2)
        y = max(0, self.winfo_rooty() + (self.winfo_height() - height) // 3)
        win.geometry(f"{size}+{x}+{y}")
        win.minsize(*minsize)
        win.transient(self)
        try:
            win.iconbitmap(str(ASSETS / "app.ico"))
        except tk.TclError:
            pass
        dark_title_bar(win)
        return win

    # ---------- pronunciation dictionary ----------

    def _open_pronunciations(self):
        if self.pron_win is not None and self.pron_win.winfo_exists():
            self.pron_win.lift()
            self.pron_win.focus_set()
            return
        try:
            content = generate.PRONUNCIATIONS_FILE.read_text(encoding="utf-8-sig")
        except OSError:
            content = PRON_TEMPLATE
        win = self.pron_win = self._dialog("Pronunciations", "680x480", (480, 320))
        win.columnconfigure(0, weight=1)
        win.rowconfigure(1, weight=1)
        ttk.Label(win, text=PRON_HELP, style="Page.TLabel", wraplength=640, justify="left").grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 10))
        box = tk.Frame(win, background=BORDER, padx=1, pady=1)
        box.grid(row=1, column=0, sticky="nsew", padx=16)
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)
        editor = tk.Text(box, wrap="none", undo=True, font=tkfont.Font(family="Consolas", size=10), relief="flat",
                         background=FIELD, foreground=TEXT_STRONG, insertbackground=TEXT_STRONG,
                         selectbackground=BLUE, selectforeground="#FFFFFF", padx=10, pady=8, highlightthickness=0)
        editor.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(box, command=editor.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        editor.configure(yscrollcommand=scroll.set)
        editor.insert("1.0", content)
        editor.edit_reset()
        editor.edit_modified(False)
        editor.focus_set()

        footer = ttk.Frame(win, style="Page.TFrame")
        footer.grid(row=2, column=0, sticky="ew", padx=16, pady=12)
        footer.columnconfigure(0, weight=1)
        note = ttk.Label(footer, text="", style="Page.TLabel", wraplength=420, justify="left")
        note.grid(row=0, column=0, sticky="w")

        def save(_event=None):
            entries, errors = parse_pronunciations(editor.get("1.0", "end-1c"))
            if errors:
                shown = "; ".join(f"line {n}: {msg}" for n, msg in errors[:2])
                note.configure(text=f"Not saved. {shown}", foreground=ERROR)
                return "break"
            try:
                generate.PRONUNCIATIONS_FILE.write_text(editor.get("1.0", "end-1c").rstrip() + "\n", encoding="utf-8")
            except OSError as exc:
                note.configure(text=f"Could not save: {exc}", foreground=ERROR)
                return "break"
            editor.edit_modified(False)
            note.configure(text=f"Saved {len(entries)} word{'' if len(entries) == 1 else 's'}. "
                                "Used by the next conversion and preview.", foreground=SUCCESS)
            return "break"

        def close(_event=None):
            if editor.edit_modified() and not messagebox.askyesno(
                    "Pronunciations", "Close without saving your changes?", icon="warning", default="no", parent=win):
                return
            win.destroy()

        ttk.Button(footer, text="Save", style="Primary.TButton", command=save).grid(row=0, column=1, padx=8)
        ttk.Button(footer, text="Close", style="Page.TButton", command=close).grid(row=0, column=2)
        win.bind("<Control-s>", save)
        editor.bind("<Control-s>", save)
        win.bind("<Escape>", close)
        win.protocol("WM_DELETE_WINDOW", close)

    # ---------- model and conversion ----------

    def _start_model_load(self):
        self._set_status(LOADING, "Busy")
        run_in_thread(self._load_worker)

    def _load_worker(self):
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self.events.put(("status", LOADING.replace("model...", f"model on {device}...")))
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
                return self._error("Pick a script file first (Browse, or drop one on the window).")
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

        self._stop_sound()
        self.busy = True
        self.stop_event.clear()
        self._update_buttons()
        self.progress.configure(value=0, maximum=1)
        self.progress_var.set("")
        self._set_status(f"Converting {source.name}...", "Busy")
        run_in_thread(self._convert_worker, source, out, *settings, self.normalize_var.get())

    def _convert_worker(self, source, out, voice, speed, pause, normalize):
        start = time.perf_counter()
        try:
            text = load_text(source)
            path, seconds = self.engine.render(
                text, voice, speed, pause, out,
                progress=lambda i, n: self.events.put(("progress", i, n)),
                stop=self.stop_event.is_set, normalize=normalize)
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

    # ---------- preview ----------

    def _preview(self):
        """Render and play the opening of the script with the current settings. A second click stops it."""
        if self.preview_state == "playing":
            return self._stop_sound()
        if not self.ready or self.busy or self.preview_state != "idle":
            return
        settings = self._settings()
        if not settings:
            return
        source, pasted = None, self.text.get("1.0", "end-1c")
        if self.mode.get() == "file":
            source = Path(self.file_var.get()) if self.file_var.get() else None
            if not source or not source.is_file():
                return self._error("Pick a script file or paste some text to preview.")
        elif not pasted.strip():
            return self._error("Paste some text to preview.")
        self.preview_state = "rendering"
        self._update_buttons()
        self._set_status("Rendering a preview...", "Busy")
        run_in_thread(self._preview_worker, source, pasted, settings[0], settings[1], self.normalize_var.get())

    def _preview_worker(self, source, pasted, voice, speed, normalize):
        try:
            text = load_text(source) if source else prepare_text(pasted, markdown=True)  # off the UI thread: may be long
            self.events.put(("preview_ready", *self.engine.preview(text, voice, speed, normalize)))
        except Exception as exc:
            log.exception("preview failed")
            self.events.put(("preview_error", f"Preview failed: {exc}"))

    def _play_preview(self, wav, seconds):
        """Play WAV bytes through a temp file. (winsound cannot stop a sound that is playing from memory.)"""
        self._drop_preview_files()
        self.preview_seq += 1
        path = Path(tempfile.gettempdir()) / f"kokoro-preview-{os.getpid()}-{self.preview_seq}.wav"
        self.preview_files.append(path)
        try:
            path.write_bytes(wav)
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
        except (OSError, RuntimeError) as exc:
            self.preview_state = "idle"
            return self._error(f"Could not play the preview: {exc}")
        self.preview_state = "playing"
        self._set_status("Playing the preview... click Stop or press Ctrl+P to end it.", "Busy")
        self.after(int(seconds * 1000) + 400, self._preview_finished, self.preview_seq)

    def _preview_finished(self, seq):
        if seq != self.preview_seq or self.preview_state != "playing":
            return
        self.preview_state = "idle"
        self._drop_preview_files()
        if not self.busy:
            self._ready_status()
        self._update_buttons()

    def _drop_preview_files(self):
        self.preview_files = [p for p in self.preview_files if not self._try_unlink(p)]

    @staticmethod
    def _try_unlink(path):
        try:
            path.unlink(missing_ok=True)
            return True
        except OSError:
            return False  # still locked by the player; tried again next time

    def _stop_sound(self):
        if self.preview_state == "playing":
            winsound.PlaySound(None, winsound.SND_PURGE)
            self._preview_finished(self.preview_seq)

    # ---------- events ----------

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
            if not self.ready:
                self._set_status(data[0], "Busy")
        elif kind == "ready":
            self.ready = True
            self._ready_status()
        elif kind == "fatal":
            self._error(data[0])
        elif kind == "lint":
            seq, *result = data
            if seq == self.lint_seq:
                self._set_lint(*result)
        elif kind == "progress":
            i, n = data
            self.progress.configure(maximum=n, value=i - 1)
            self.progress_var.set(f"para {i}/{n}")
        elif kind == "done":
            path, seconds, took = data
            self.busy = False
            self.progress.configure(value=self.progress["maximum"])
            where = f"{path.parent.name}\\{path.name}"
            if path.suffix.lower() == ".wav":
                self._set_status(f"MP3 export failed, saved WAV instead: {where} "
                                 f"({seconds / 60:.1f} min in {took:.0f} s). See ui.log.", "Error")
            else:
                self._set_status(f"Saved {where} ({seconds / 60:.1f} min in {took:.0f} s)", "Success")
            log.info("saved %s (%.1f min in %.0f s)", path, seconds / 60, took)
            self._refresh_files(select=str(path))
        elif kind == "cancelled":
            self.busy = False
            self.progress.configure(value=0)
            self.progress_var.set("")
            self._set_status("Cancelled. No MP3 was written.")
        elif kind == "error":
            self.busy = False
            self._error(data[0])
        elif kind == "preview_ready":
            self._play_preview(*data)
        elif kind == "preview_error":
            self.preview_state = "idle"
            self._error(data[0])
        self._update_buttons()

    def _update_buttons(self):
        rendering = self.preview_state == "rendering"
        self.convert_btn.configure(text="CONVERT" if self.ready else "LOADING MODEL...",
                                   state="normal" if self.ready and not self.busy and not rendering else "disabled")
        self.cancel_btn.configure(state="normal" if self.busy and not self.stop_event.is_set() else "disabled")
        self.preview_btn.configure(
            text={"idle": "Preview", "rendering": "Rendering...", "playing": "Stop"}[self.preview_state],
            state="normal" if self.ready and not self.busy and not rendering else "disabled")
        self.clear_btn.configure(state="disabled" if self.busy else "normal")

    # ---------- after conversion ----------

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
        self.paste_text = ""
        self.paste_name = ""
        self.name_touched = False
        self.box_mode = None
        self._on_mode()
        self.lint_seq += 1  # drop any check still running
        self._set_lint(LINT_IDLE)
        self.progress.configure(value=0, maximum=1)
        self.progress_var.set("")
        if self.ready:
            self._ready_status()
        else:
            self._set_status(LOADING, "Busy")
        self._update_buttons()

    # ---------- output file list ----------

    def _output_files(self):
        try:
            files = [p for p in OUTPUT_DIR.iterdir() if p.is_file() and p.suffix.lower() in (".mp3", ".wav")]
        except OSError:
            return []
        return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)

    def _refresh_files(self, select=None):
        """Reload the list. `select` (a path string) becomes the selection, e.g. the file just made."""
        selected = {select} if select else set(self.files.selection())
        self.files.delete(*self.files.get_children())
        year = time.localtime().tm_year
        for path in self._output_files():
            stat = path.stat()
            key = (str(path), stat.st_mtime)
            if key not in self.lengths:
                self.lengths[key] = audio_length(path)
            seconds = self.lengths[key]
            length = "?" if seconds is None else f"{int(seconds // 60)}:{int(seconds % 60):02d}"
            when = time.localtime(stat.st_mtime)
            date = time.strftime("%d %b %H:%M" if when.tm_year == year else "%d %b %Y", when)
            self.files.insert("", "end", iid=str(path), text=path.name, values=(length, date))
            if str(path) in selected:
                self.files.selection_add(str(path))
                self.files.see(str(path))
        if self.files.get_children():
            self.files_hint.place_forget()
        else:
            self.files_hint.place(relx=0.5, rely=0.4, anchor="center")
        self._update_file_buttons()

    def _on_tree_hover(self, event):
        row = self.files.identify_row(event.y)
        text = self.files.item(row, "text") if row else ""
        if text != self.hover_row:
            self.hover_row = text
            self.files_tip.schedule()

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
                       "pause": defaults["pause"] if pause is None else pause,
                       "normalize": bool(self.normalize_var.get())})
        self.stop_event.set()
        self._stop_sound()
        self._drop_preview_files()
        self.destroy()


def setup_logging():
    """pythonw.exe has no console: send print(), warnings and errors to ui.log instead."""
    stream = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = stream
    logging.basicConfig(stream=stream, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.captureWarnings(True)
    log.info("---- ui %s started ----", __version__)


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
