"""A small Markdown renderer for a read-only tk.Text, used for the paste box preview.

No dependencies. It covers what narration scripts use: headings, bold, italic, inline code,
block quotes, lists, horizontal rules, links (shown as their text), fenced code and plain
paragraphs. Tables, images and nested lists deeper than three levels show as plain text.
It mirrors how generate.markdown_to_speech reads the same Markdown (a heading needs no space
after the #, a `---` line is a rule, single line breaks join into one paragraph), so the
preview looks like what will be spoken. Only the display changes; the raw text is never touched.
"""

import re
from tkinter import font as tkfont

from ui_theme import BLUE, BLUE_TEXT, BORDER, FIELD_OFF, SCROLL, TEXT, TEXT_MUTED, TEXT_STRONG

_DETECT = re.compile(
    r"^ {0,3}#{1,6}[ \t]+\S"  # heading
    r"|^[ \t]*>[ \t]?\S"  # block quote
    r"|^[ \t]*(?:[-*+]|\d+[.)])[ \t]+\S"  # list item
    r"|^[ \t]*(?:[-*_][ \t]*){3,}$"  # horizontal rule
    r"|^```"  # code fence
    r"|\*\*\S(?:.*?\S)?\*\*|__\S(?:.*?\S)?__"  # bold
    r"|\[[^\]\n]+\]\([^)\n]*\)",  # link
    re.M,
)
_FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
_RULE = re.compile(r"^[ \t]*(?:[-*_][ \t]*){3,}$")
_HEADING = re.compile(r"^[ \t]{0,3}(#{1,6})[ \t]*(.+?)[ \t]*#*[ \t]*$")
_LIST = re.compile(r"^([ \t]*)([-*+]|\d+[.)])[ \t]+(.*)$")
_QUOTE = re.compile(r"^[ \t]*>[ \t]?(.*)$")
_INLINE = re.compile(
    r"\*\*\*(?P<bi>.+?)\*\*\*"
    r"|\*\*(?P<b>.+?)\*\*|__(?P<b2>.+?)__"
    r"|(?<![\w*])\*(?!\s)(?P<i>.+?)(?<!\s)\*(?![\w*])|(?<!\w)_(?!\s)(?P<i2>.+?)(?<!\s)_(?!\w)"
    r"|~~(?P<s>.+?)~~"
    r"|`(?P<c>[^`]+)`"
    r"|!\[[^\]]*\]\([^)]*\)"
    r"|\[\[(?:[^\]|]+\|)?(?P<w>[^\]]+)\]\]"
    r"|\[(?P<lt>[^\]]+)\]\((?P<lu>[^)]*)\)"
)
_KOKORO_MARKUP = re.compile(r"/[^/)]+/|[-+]?\d+(?:\.\d+)?|#[^)]*#")  # [word](/ipa/), [word](+2), [123](#a#)
_COMMENT = re.compile(r"<!--.*?-->", re.S)


def looks_like_markdown(text):
    """True when the text uses Markdown syntax (so a rendered view makes sense)."""
    return bool(_DETECT.search(text))


def configure_tags(widget, base_font):
    """Create the tags render() uses. Call once, after the widget exists."""
    fonts = {}

    def make(name, **options):
        font = base_font.copy()
        font.configure(**options)
        fonts[name] = font
        return font

    widget._md_fonts = fonts  # keep references: tk drops a font when its object is collected
    heading_sizes = {1: 18, 2: 15, 3: 13, 4: 11, 5: 11, 6: 10}
    for level, size in heading_sizes.items():
        widget.tag_configure(f"h{level}", font=make(f"h{level}", size=size, weight="bold"),
                             foreground=TEXT_STRONG if level < 4 else TEXT, spacing1=10 if level < 3 else 6,
                             spacing3=8)
    widget.tag_configure("p", spacing3=12)
    widget.tag_configure("bold", font=make("bold", weight="bold"), foreground=TEXT_STRONG)
    widget.tag_configure("italic", font=make("italic", slant="italic"))
    widget.tag_configure("bolditalic", font=make("bolditalic", weight="bold", slant="italic"),
                         foreground=TEXT_STRONG)
    widget.tag_configure("strike", overstrike=True, foreground=TEXT_MUTED)
    widget.tag_configure("code", font=make("code", family="Consolas", size=9), background=FIELD_OFF,
                         foreground=BLUE_TEXT)
    widget.tag_configure("codeblock", font=fonts["code"], background=FIELD_OFF, foreground=TEXT_MUTED,
                         lmargin1=10, lmargin2=10, spacing3=12)
    widget.tag_configure("link", foreground=BLUE_TEXT, underline=True)
    widget.tag_configure("quote", foreground=TEXT_MUTED, lmargin1=26, lmargin2=26, spacing3=12)
    widget.tag_configure("bar", foreground=BLUE, lmargin1=8)
    widget.tag_configure("rule", foreground=SCROLL, spacing1=4, spacing3=14)
    widget.tag_configure("bullet", foreground=BLUE_TEXT)
    widget.tag_configure("table", font=fonts["code"], foreground=TEXT_MUTED, spacing3=2)
    for depth in range(4):
        widget.tag_configure(f"li{depth}", lmargin1=14 + depth * 20, lmargin2=32 + depth * 20, spacing3=4)
    widget.tag_raise("sel")


def _inline(widget, text, tags):
    """Insert `text` at the end, applying bold / italic / code / link styling on top of `tags`."""
    position = 0
    for match in _INLINE.finditer(text):
        if match.start() > position:
            widget.insert("end", text[position:match.start()], tags)
        position = match.end()
        kind = match.lastgroup
        if kind in ("bi", "b", "b2", "i", "i2", "s"):
            style = {"bi": "bolditalic", "b": "bold", "b2": "bold", "i": "italic", "i2": "italic", "s": "strike"}[kind]
            _inline(widget, match.group(kind), tags + (style,))
        elif kind == "c":
            widget.insert("end", match.group("c"), tags + ("code",))
        elif kind == "w":
            widget.insert("end", match.group("w"), tags)
        elif kind == "lu":  # a link: its text, underlined, unless it is Kokoro pronunciation markup
            styled = tags if _KOKORO_MARKUP.fullmatch(match.group("lu")) else tags + ("link",)
            _inline(widget, match.group("lt"), styled)
        # images (no group matched) are dropped, as generate.py does
    if position < len(text):
        widget.insert("end", text[position:], tags)


def render(widget, text):
    """Replace the content of `widget` (a tk.Text set up by configure_tags) with the rendered Markdown."""
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    text = _COMMENT.sub("", _FRONT_MATTER.sub("", text.replace("\r\n", "\n")))
    paragraph, kind = [], "p"  # pending paragraph lines and their kind ("p" or "quote")
    lines = iter(text.split("\n"))

    def flush():
        if paragraph:
            joined = " ".join(part.strip() for part in paragraph)
            if kind == "quote":
                widget.insert("end", "▎  ", ("quote", "bar"))
                _inline(widget, joined, ("quote",))
            else:
                _inline(widget, joined, ("p",))
            widget.insert("end", "\n", ("quote",) if kind == "quote" else ("p",))
            paragraph.clear()

    for line in lines:
        if line.lstrip().startswith("```"):  # fenced code: shown as written until the closing fence
            flush()
            block = []
            for inner in lines:
                if inner.lstrip().startswith("```"):
                    break
                block.append(inner)
            widget.insert("end", "\n".join(block) + "\n", ("codeblock",))
            continue
        quote = _QUOTE.match(line)
        heading = None if quote else _HEADING.match(line)
        item = None if quote or heading else _LIST.match(line)
        if not line.strip() or (quote and not quote.group(1).strip()):
            flush()
        elif _RULE.match(line):  # like generate.py, "- - -" is a rule, not a list item
            flush()
            widget.insert("end", "─" * 36 + "\n", ("rule",))
        elif heading:
            flush()
            tag = f"h{len(heading.group(1))}"
            _inline(widget, heading.group(2), (tag,))
            widget.insert("end", "\n", (tag,))
        elif item:
            flush()
            depth = min(len(item.group(1).replace("\t", "    ")) // 2, 3)
            marker = "•" if item.group(2) in "-*+" else item.group(2)
            widget.insert("end", marker + "  ", (f"li{depth}", "bullet"))
            _inline(widget, item.group(3).strip(), (f"li{depth}",))
            widget.insert("end", "\n", (f"li{depth}",))
        elif line.lstrip().startswith("|"):
            flush()
            widget.insert("end", line.strip() + "\n", ("table",))
        else:
            wanted = "quote" if quote else "p"
            if paragraph and kind != wanted:
                flush()
            kind = wanted
            paragraph.append(quote.group(1) if quote else line)
    flush()
    widget.configure(state="disabled")
