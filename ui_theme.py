"""RasWorx brand theme for the Kokoro window: palette, ttk styles and the dark title bar."""

from tkinter import font as tkfont
from tkinter import ttk

# RasWorx brand palette, dark variant (same tokens as the ofx-conv GUI)
BLUE = "#046FCC"
BLUE_HOVER = "#1F86E3"
BLUE_SOFT = "#1C3552"
BLUE_TEXT = "#6FB4F5"
CHARCOAL = "#0D0F14"
SLATE = "#1A1F27"
TEXT = "#E6EAF0"
TEXT_STRONG = "#F7F9FB"
TEXT_MUTED = "#A7B1BC"
DISABLED = "#98A3AE"
BORDER = "#2C3442"
FIELD = "#232935"
FIELD_OFF = "#1C212B"
TROUGH = "#151920"
SCROLL = "#3A4454"
SUCCESS = "#5DD39B"
WARNING = "#F5C063"
WARNING_BG = "#3A2A08"
ERROR = "#FF9A8F"


def apply_theme(root):
    """ttk styles for the RasWorx dark palette. Returns the fonts dict."""
    families = set(tkfont.families(root))
    family = "Montserrat" if "Montserrat" in families else "Segoe UI"
    semibold = "Montserrat SemiBold" if "Montserrat SemiBold" in families else family
    medium = "Montserrat Medium" if "Montserrat Medium" in families else family
    heavy = "normal" if semibold != family else "bold"
    fonts = {
        "title": tkfont.Font(root, family=semibold, size=15, weight=heavy),
        "body": tkfont.Font(root, family=family, size=10),
        "small": tkfont.Font(root, family=family, size=9),
        "key": tkfont.Font(root, family=medium, size=8, weight="normal" if medium != family else "bold"),
        "button": tkfont.Font(root, family=medium, size=10, weight="normal" if medium != family else "bold"),
    }
    root.configure(background=CHARCOAL)
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", background=SLATE, foreground=TEXT, font=fonts["body"], borderwidth=0)
    s.configure("TFrame", background=SLATE)
    s.configure("Page.TFrame", background=CHARCOAL)
    s.configure("TLabel", background=SLATE, foreground=TEXT)
    s.configure("Page.TLabel", background=CHARCOAL, foreground=TEXT_MUTED, font=fonts["small"])
    s.configure("Title.TLabel", background=CHARCOAL, foreground=TEXT_STRONG, font=fonts["title"])
    s.configure("Key.TLabel", foreground=TEXT_MUTED, font=fonts["key"])
    s.configure("Muted.TLabel", foreground=TEXT_MUTED, font=fonts["small"])
    for name, colour in (("Status", TEXT), ("Success", SUCCESS), ("Error", ERROR), ("Busy", BLUE_TEXT)):
        s.configure(f"{name}.TLabel", background=CHARCOAL, foreground=colour)

    s.configure("TButton", background=SLATE, foreground=BLUE_TEXT, font=fonts["button"], padding=(14, 6),
                borderwidth=1, bordercolor=BLUE_TEXT, lightcolor=SLATE, darkcolor=SLATE, focuscolor=BLUE)
    s.map("TButton", background=[("disabled", FIELD_OFF), ("pressed", BLUE_SOFT), ("active", BLUE_SOFT)],
          foreground=[("disabled", DISABLED)], bordercolor=[("disabled", BORDER)])
    s.configure("Page.TButton", background=CHARCOAL, lightcolor=CHARCOAL, darkcolor=CHARCOAL)
    s.map("Page.TButton", background=[("disabled", CHARCOAL), ("pressed", BLUE_SOFT), ("active", BLUE_SOFT)])
    s.configure("Primary.TButton", background=BLUE, foreground="#FFFFFF", padding=(22, 7), borderwidth=0,
                bordercolor=BLUE, lightcolor=BLUE, darkcolor=BLUE, focuscolor=BLUE_HOVER)
    s.map("Primary.TButton", background=[("disabled", "#3A4454"), ("pressed", BLUE_HOVER), ("active", BLUE_HOVER)],
          foreground=[("disabled", DISABLED)], bordercolor=[("disabled", "#3A4454")])
    s.configure("Link.TButton", background=SLATE, foreground=BLUE_TEXT, borderwidth=0, padding=(6, 2),
                font=fonts["small"])
    s.map("Link.TButton", background=[("active", BLUE_SOFT)])

    field = dict(fieldbackground=FIELD, background=FIELD, foreground=TEXT_STRONG, bordercolor=BORDER,
                 lightcolor=BORDER, darkcolor=BORDER, insertcolor=TEXT_STRONG, padding=(8, 5),
                 selectbackground=BLUE, selectforeground="#FFFFFF", arrowcolor=BLUE_TEXT)
    field_map = dict(fieldbackground=[("readonly", FIELD_OFF), ("disabled", FIELD_OFF)],
                     foreground=[("disabled", DISABLED)], bordercolor=[("focus", BLUE)],
                     lightcolor=[("focus", BLUE)], darkcolor=[("focus", BLUE)], arrowcolor=[("disabled", DISABLED)])
    for widget in ("TEntry", "TCombobox", "TSpinbox"):
        s.configure(widget, **field)
        s.map(widget, **field_map)
    s.map("TCombobox", fieldbackground=[("readonly", FIELD)], selectbackground=[("readonly", FIELD)],
          selectforeground=[("readonly", TEXT_STRONG)], bordercolor=[("focus", BLUE)])
    root.option_add("*TCombobox*Listbox.font", fonts["body"])
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT_STRONG)
    root.option_add("*TCombobox*Listbox.selectBackground", BLUE)
    root.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")

    s.configure("TRadiobutton", background=SLATE, foreground=TEXT, indicatorbackground=FIELD,
                indicatorforeground=BLUE, indicatormargin=(0, 0, 8, 0), focuscolor=SLATE)
    s.map("TRadiobutton", background=[("active", SLATE)],
          indicatorbackground=[("selected", BLUE)], indicatorforeground=[("selected", "#FFFFFF")])
    s.configure("Brand.Horizontal.TProgressbar", background=BLUE, troughcolor=TROUGH, bordercolor=TROUGH,
                lightcolor=BLUE, darkcolor=BLUE, thickness=8)
    s.configure("Vertical.TScrollbar", background=SCROLL, troughcolor=TROUGH, bordercolor=TROUGH,
                lightcolor=SCROLL, darkcolor=SCROLL, arrowcolor=TEXT_MUTED, gripcount=0)
    s.map("Vertical.TScrollbar", background=[("active", BLUE_TEXT)])
    s.configure("Brand.Treeview", background=FIELD, fieldbackground=FIELD, foreground=TEXT_STRONG, borderwidth=0,
                rowheight=26, font=fonts["body"])
    s.map("Brand.Treeview", background=[("selected", BLUE)], foreground=[("selected", "#FFFFFF")])
    s.configure("Brand.Treeview.Heading", background=SLATE, foreground=TEXT_MUTED, font=fonts["key"],
                borderwidth=0, padding=(8, 6))
    s.map("Brand.Treeview.Heading", background=[("active", BLUE_SOFT)])
    return fonts


def dark_title_bar(window):
    """Ask Windows 10/11 for a dark title bar so it matches the page."""
    try:
        import ctypes
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:
        pass
