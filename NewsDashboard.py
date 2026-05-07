#!/usr/bin/env python3
"""
News Dashboard, single file, Tkinter only, cross-platform.

What is new in this build
- Reader title no longer wraps to single characters; wrap length tracks the pane width.
- Stronger and smarter fetcher:
  * Rotates several realistic User-Agent headers.
  * Retries with backoff.
  * Normalizes and auto-fixes several common feeds, for example old Reuters endpoints.
  * HTTP to HTTPS upgrade when safe.
- Larger, richer default source lists per section.
- Per-section headline cap raised to 100.
- Export to .txt kept; button lives in the reader pane.

Standard library only.
"""

from __future__ import annotations

import json
import queue
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, colorchooser, filedialog, font as tkfont


# ----------------------------- Defaults and data models -----------------------------

APP_NAME = "News Dashboard"
SETTINGS_FILE = str(Path.home() / ".news_dashboard_settings.json")

# Known good RSS endpoints, grouped by section. You can edit these later in Options.
DEFAULT_SECTIONS: Dict[str, List[str]] = {
    "Top": [
        "https://feeds.bbci.co.uk/news/rss.xml",
        "http://rss.cnn.com/rss/cnn_topstories.rss",
        "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
        "https://feeds.reuters.com/reuters/topNews",
        "https://www.theguardian.com/world/rss",
        "https://apnews.com/hub/apf-topnews?utm_source=ap_rss&utm_medium=rss&utm_campaign=ap_rss",
        "https://www.npr.org/rss/rss.php?id=1001",
        "https://www.aljazeera.com/xml/rss/all.xml",
    ],
    "US": [
        "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/US.xml",
        "http://feeds.foxnews.com/foxnews/latest",
        "https://www.npr.org/rss/rss.php?id=1003",
        "https://apnews.com/hub/us-news?utm_source=ap_rss&utm_medium=rss&utm_campaign=ap_rss",
        "https://www.pbs.org/newshour/feeds/rss/headlines",
    ],
    "World": [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "https://feeds.reuters.com/reuters/worldNews",
        "https://www.theguardian.com/world/rss",
        "https://www.dw.com/en/top-stories/s-9097?maca=en-rss-en-all-1573-rdf",
        "https://www.aljazeera.com/xml/rss/all.xml",
        "https://apnews.com/hub/world-news?utm_source=ap_rss&utm_medium=rss&utm_campaign=ap_rss",
    ],
    "Business": [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",  # WSJ markets
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "https://www.marketwatch.com/feeds/topstories",
        "https://www.ft.com/?format=rss",
        "https://apnews.com/hub/business?utm_source=ap_rss&utm_medium=rss&utm_campaign=ap_rss",
    ],
    "Tech": [
        "https://www.theverge.com/rss/index.xml",
        "http://feeds.arstechnica.com/arstechnica/index",
        "https://www.wired.com/feed/rss",
        "https://www.engadget.com/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
        "https://feeds.reuters.com/reuters/technologyNews",
        "https://apnews.com/hub/technology?utm_source=ap_rss&utm_medium=rss&utm_campaign=ap_rss",
    ],
    "Science": [
        "https://rss.nytimes.com/services/xml/rss/nyt/Science.xml",
        "https://www.nasa.gov/rss/dyn/breaking_news.rss",
        "https://www.sciencedaily.com/rss/top/science.xml",
        "https://feeds.nature.com/nature/rss/current",
        "https://apnews.com/hub/science?utm_source=ap_rss&utm_medium=rss&utm_campaign=ap_rss",
        "https://www.newscientist.com/section/news/feed/",
        "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=science",
    ],
    "Sports": [
        "https://www.espn.com/espn/rss/news",
        "https://www.cbssports.com/rss/headlines/",
        "https://sports.yahoo.com/rss/",
        "https://feeds.reuters.com/reuters/sportsNews",
        "https://apnews.com/hub/sports?utm_source=ap_rss&utm_medium=rss&utm_campaign=ap_rss",
        "https://www.skysports.com/rss/12040",
    ],
    "Arts": [
        "https://rss.nytimes.com/services/xml/rss/nyt/Arts.xml",
        "https://www.theguardian.com/culture/rss",
        "https://apnews.com/hub/entertainment?utm_source=ap_rss&utm_medium=rss&utm_campaign=ap_rss",
        "https://www.rollingstone.com/music/music-news/feed/",
        "https://www.vanityfair.com/feed/rss",
    ],
    "Favorites": [],  # virtual section; program fills this when you save items
}

def _default_palette() -> Dict[str, str]:
    return {
        "bg": "#0b1321",
        "panel": "#121c2d",
        "text": "#e7edf7",
        "muted": "#a9b3c7",
        "accent": "#4f8cff",
        "accent2": "#ff3b30",
        "list_alt": "#0f1a2b",
        "link": "#a0c4ff",
    }

@dataclass
class Settings:
    sections: Dict[str, List[str]] = field(default_factory=lambda: json.loads(json.dumps(DEFAULT_SECTIONS)))
    refresh_seconds: int = 300
    max_per_section: int = 100
    font_family: str = "Segoe UI"
    font_size: int = 12
    reader_font_size: int = 14
    bold_headlines: bool = False
    palette: Dict[str, str] = field(default_factory=_default_palette)
    include_source_name: bool = True
    open_links_in_browser_by_default: bool = False
    autosave_path: str = SETTINGS_FILE

    def clamp(self) -> None:
        self.refresh_seconds = max(60, min(3600, int(self.refresh_seconds)))
        self.max_per_section = max(10, min(500, int(self.max_per_section)))
        self.font_size = max(10, min(18, int(self.font_size)))
        self.reader_font_size = max(12, min(28, int(self.reader_font_size)))
        # Clean up feeds
        clean: Dict[str, List[str]] = {}
        for name, urls in self.sections.items():
            uniq, seen = [], set()
            for u in urls:
                u2 = u.strip()
                if u2 and u2 not in seen:
                    seen.add(u2)
                    uniq.append(u2)
            clean[name] = uniq
        self.sections = clean

@dataclass
class Headline:
    title: str
    link: str
    source: str
    pubtime: str = ""
    section: str = ""

@dataclass
class Article:
    title: str
    link: str
    source: str
    text: str


# ----------------------------- Utility helpers -----------------------------

def load_settings(path: str) -> Settings:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        s = Settings(**data)
        s.clamp()
        return s
    except Exception:
        s = Settings()
        s.clamp()
        return s

def save_settings(s: Settings) -> None:
    try:
        with open(s.autosave_path, "w", encoding="utf-8") as f:
            json.dump(asdict(s), f, indent=2)
    except Exception as e:
        print(f"[WARN] settings save failed: {e}")

def html_unescape(s: str) -> str:
    return (
        s.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&apos;", "'")
    )


# ----------------------------- Robust fetchers -----------------------------

UA_POOL = [
    # Rotate a few realistic user agents; some feeds block very old defaults
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/118.0",
]

def normalize_feed_url(url: str) -> str:
    """Rewrite a few legacy or brittle endpoints to stable ones."""
    u = url.strip()
    # Reuters legacy paths -> feeds.reuters.com
    m = re.match(r"^https?://www\.reuters\.com/rssFeed/([A-Za-z0-9]+)$", u)
    if m:
        return f"https://feeds.reuters.com/reuters/{m.group(1)}"
    # Nature subject old path -> current
    if "nature.com/subjects/science.rss" in u:
        return "https://feeds.nature.com/nature/rss/current"
    # Prefer https where possible
    if u.startswith("http://rss.cnn.com/"):
        return u  # CNN top is http only at this endpoint
    if u.startswith("http://"):
        return "https://" + u.split("://", 1)[1]
    return u

def fetch_bytes(url: str, timeout: int = 20) -> Optional[bytes]:
    url = normalize_feed_url(url)
    # Try up to three attempts with different UAs
    for attempt in range(3):
        headers = {
            "User-Agent": UA_POOL[attempt % len(UA_POOL)],
            "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
            "Accept-Language": "en-US,en;q=0.8",
            "Connection": "close",
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            # If forbidden or not found, try one more normalized pass, then give up
            if attempt == 0 and e.code in (401, 403, 404):
                url = normalize_feed_url(url)  # may already be normalized
                time.sleep(0.2)
                continue
            print(f"[WARN] fetch failed {url}: HTTP {e.code} {e.reason}")
        except urllib.error.URLError as e:
            print(f"[WARN] fetch failed {url}: {e}")
        time.sleep(0.35 * (attempt + 1))
    return None


# ----------------------------- RSS parsing -----------------------------

def parse_rss(xml_data: bytes, default_source: str) -> List[Headline]:
    items: List[Headline] = []
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return items

    ns = {"atom": "http://www.w3.org/2005/Atom"}

    # RSS 2.0
    channel = root.find("channel")
    if channel is not None:
        src = channel.findtext("title") or default_source
        for it in channel.findall("item"):
            title = html_unescape((it.findtext("title") or "").strip())
            link = (it.findtext("link") or "").strip()
            pub = (it.findtext("pubDate") or "").strip()
            if title and link:
                items.append(Headline(title=title, link=link, source=src, pubtime=pub))
        return items

    # Atom
    feed_title = root.findtext("title") or default_source
    for entry in root.findall("atom:entry", ns) or root.findall("entry"):
        title = html_unescape(
            (entry.findtext("atom:title", default="", namespaces=ns) or entry.findtext("title") or "").strip()
        )
        link_el = entry.find("atom:link", ns) or entry.find("link")
        href = link_el.get("href") if link_el is not None else ""
        if title and href:
            updated = entry.findtext("updated") or entry.findtext("published") or ""
            items.append(Headline(title=title, link=href, source=feed_title, pubtime=updated))
    return items

def dedupe_headlines(items: List[Headline]) -> List[Headline]:
    seen = set()
    out = []
    for h in items:
        key = (h.title.strip().lower(), h.link.strip())
        if key not in seen:
            seen.add(key)
            out.append(h)
    return out


# ----------------------------- Simple HTML article extractor -----------------------------

class SimpleHTMLExtractor:
    """
    Lightweight readability-style extractor.

    Strategy
    - Ignore scripts, styles, nav, header, footer, aside.
    - Prefer <article>, else collect dense clusters of <p>/<h1>/<h2>.
    - Collapse whitespace to paragraphs.
    """
    SKIP = {"script", "style", "noscript", "nav", "header", "footer", "aside", "form"}

    def __init__(self):
        from html.parser import HTMLParser

        class P(HTMLParser):
            def __init__(self, outer):
                super().__init__(convert_charrefs=True)
                self.outer = outer
                self.stack: List[str] = []
                self.in_skip = 0
                self.in_article = 0
                self.buf_article: List[str] = []
                self.paras: List[str] = []
                self._cur: List[str] = []
                self.title_bits: List[str] = []

            def handle_starttag(self, tag, attrs):
                tag = tag.lower()
                self.stack.append(tag)
                if tag in SimpleHTMLExtractor.SKIP:
                    self.in_skip += 1
                if tag == "article":
                    self.in_article += 1
                if tag in ("p", "h1", "h2"):
                    self._cur = []
                if tag == "meta":
                    d = {k.lower(): v for k, v in attrs}
                    if d.get("property", "").lower() == "og:title" and d.get("content"):
                        self.title_bits.append(d["content"])

            def handle_endtag(self, tag):
                tag = tag.lower()
                if tag in SimpleHTMLExtractor.SKIP and self.in_skip > 0:
                    self.in_skip -= 1
                if tag == "article" and self.in_article > 0:
                    self.in_article -= 1
                if tag in ("p", "h1", "h2") and self._cur:
                    txt = " ".join(self._cur).strip()
                    self._cur = []
                    if txt:
                        self.paras.append(txt)
                if self.stack and self.stack[-1] == tag:
                    self.stack.pop()

            def handle_data(self, data):
                if self.in_skip:
                    return
                t = data.strip()
                if not t:
                    return
                if self.in_article:
                    self.buf_article.append(t)
                if self.stack and self.stack[-1] in ("p", "h1", "h2"):
                    self._cur.append(t)

        self._parser_cls = P

    def extract(self, html: bytes) -> Tuple[str, str]:
        parser = self._parser_cls(self)
        try:
            parser.feed(html.decode("utf-8", errors="ignore"))
        except Exception:
            pass

        title = " ".join(parser.title_bits).strip()
        article_text = " ".join(parser.buf_article).strip()

        if not article_text:
            # choose a dense block of paragraphs
            best = self._best_block(parser.paras)
            article_text = best

        article_text = self._cleanup(article_text)
        return title, article_text

    def _best_block(self, paras: List[str]) -> str:
        if not paras:
            return ""
        win = 6
        best_score = 0
        best_i = 0
        for i in range(len(paras)):
            block = paras[i:i+win]
            score = sum(len(p) for p in block)
            if score > best_score:
                best_score = score
                best_i = i
        block = paras[best_i:best_i+12]
        return "\n\n".join(block)

    def _cleanup(self, text: str) -> str:
        if not text:
            return ""
        text = html_unescape(text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


# ----------------------------- Background workers -----------------------------

class Fetcher(threading.Thread):
    """Polls RSS feeds by section; sends results to the UI via a queue."""
    def __init__(self, settings: Settings, outq: "queue.Queue[Tuple[str, object]]", stop: threading.Event):
        super().__init__(daemon=True)
        self.s = settings
        self.q = outq
        self.stop = stop

    def run(self) -> None:
        next_time = 0.0
        while not self.stop.is_set():
            now = time.time()
            if now >= next_time:
                self.q.put(("STATUS", "Refreshing feeds..."))
                data = self._refresh_all()
                self.q.put(("HEADLINES_ALL", data))
                next_time = now + self.s.refresh_seconds
            self.stop.wait(0.5)

    def _refresh_all(self) -> Dict[str, List[Headline]]:
        out: Dict[str, List[Headline]] = {}
        for section, feeds in self.s.sections.items():
            if section in ("Favorites", "Favorites_links"):
                continue
            bucket: List[Headline] = []
            for url in feeds:
                b = fetch_bytes(url)
                if not b:
                    continue
                parsed = parse_rss(b, default_source=url)
                for h in parsed:
                    h.section = section
                bucket.extend(parsed)
            bucket = dedupe_headlines(bucket)
            out[section] = bucket[: self.s.max_per_section]
        # Build a virtual Breaking section as union of top areas
        if out:
            combined = []
            for k in ("Top", "US", "World", "Business", "Tech"):
                combined.extend(out.get(k, []))
            out["Breaking"] = dedupe_headlines(combined)[: self.s.max_per_section]
        return out


# ----------------------------- UI: main application -----------------------------

class NewsDashboard(tk.Tk):
    def __init__(self, settings: Settings):
        super().__init__()
        self.s = settings
        self.title(APP_NAME)
        self.geometry("1280x720")
        self.minsize(900, 560)

        # Tk theme
        self.style = ttk.Style(self)
        try:
            if "clam" in self.style.theme_names():
                self.style.theme_use("clam")
        except Exception:
            pass

        self.palette = dict(self.s.palette)
        self._apply_styles()

        # shared state
        self.outq: "queue.Queue[Tuple[str, object]]" = queue.Queue()
        self.stop = threading.Event()
        self.fetcher = Fetcher(self.s, self.outq, self.stop)
        self.fetcher.start()
        self.extractor = SimpleHTMLExtractor()
        self.all_headlines: Dict[str, List[Headline]] = {}
        self.favorites: List[Headline] = []
        self._load_favorites_from_settings()

        # fonts
        self.font_list = tkfont.Font(family=self.s.font_family, size=self.s.font_size,
                                     weight="bold" if self.s.bold_headlines else "normal")
        self.font_reader = tkfont.Font(family=self.s.font_family, size=self.s.reader_font_size)

        # menu and toolbar
        self._build_menu()
        self._build_toolbar()

        # main panes
        self.root_pane = ttk.Panedwindow(self, orient="horizontal")
        self.root_pane.pack(fill="both", expand=True)

        # left: sections
        self.left_frame = ttk.Frame(self.root_pane)
        self._build_sections_list(self.left_frame)
        self.root_pane.add(self.left_frame, weight=1)

        # center: headlines
        self.mid_frame = ttk.Frame(self.root_pane)
        self._build_headlines_list(self.mid_frame)
        self.root_pane.add(self.mid_frame, weight=3)

        # right: reader
        self.right_frame = ttk.Frame(self.root_pane)
        self._build_reader(self.right_frame)
        self.root_pane.add(self.right_frame, weight=4)

        # status bar
        self.status = tk.StringVar(value="Welcome")
        self.status_lbl = tk.Label(self, textvariable=self.status, anchor="w",
                                   bg=self.palette["panel"], fg=self.palette["muted"], padx=8)
        self.status_lbl.pack(fill="x")

        # bindings
        self.bind("<Key-r>", lambda e: self.refresh_now())
        self.bind("<Key-s>", lambda e: self.save_all())
        self.bind("<Control-f>", lambda e: self._focus_search())
        self.bind("<Control-plus>", lambda e: self._bump_reader_font(+1))
        self.bind("<Control-minus>", lambda e: self._bump_reader_font(-1))
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # polling loop
        self.after(100, self._pump_messages)

        # initial selection
        self._rebuild_sections()
        self._select_section("Breaking")

    # --------------------- build UI ---------------------

    def _apply_styles(self) -> None:
        p = self.palette
        self.configure(bg=p["bg"])
        self.style.configure("TFrame", background=p["panel"])
        self.style.configure("TLabel", background=p["panel"], foreground=p["text"])
        self.style.configure("TButton", padding=6)
        self.style.map("TButton", foreground=[("active", p["text"])])
        self.style.configure("List.Treeview", background=p["panel"], fieldbackground=p["panel"], foreground=p["text"])
        self.style.map("Treeview", background=[("selected", p["accent"])], foreground=[("selected", "#ffffff")])

    def _build_menu(self) -> None:
        m = tk.Menu(self)
        filem = tk.Menu(m, tearoff=False)
        filem.add_command(label="Options", command=self.open_options)
        filem.add_separator()
        filem.add_command(label="Save settings", command=self.save_all, accelerator="S")
        filem.add_separator()
        filem.add_command(label="Quit", command=self._on_close)
        m.add_cascade(label="File", menu=filem)

        viewm = tk.Menu(m, tearoff=False)
        viewm.add_command(label="Refresh now", command=self.refresh_now, accelerator="R")
        viewm.add_command(label="Increase reader text", command=lambda: self._bump_reader_font(+1),
                          accelerator="Ctrl+plus")
        viewm.add_command(label="Decrease reader text", command=lambda: self._bump_reader_font(-1),
                          accelerator="Ctrl+minus")
        m.add_cascade(label="View", menu=viewm)

        helpm = tk.Menu(m, tearoff=False)
        helpm.add_command(label="About", command=lambda: messagebox.showinfo("About", f"{APP_NAME}\nStandard library only"))
        m.add_cascade(label="Help", menu=helpm)
        self.config(menu=m)

    def _build_toolbar(self) -> None:
        p = self.palette
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        ttk.Button(bar, text="Refresh", command=self.refresh_now).pack(side="left", padx=6, pady=6)
        ttk.Button(bar, text="Options", command=self.open_options).pack(side="left", padx=6, pady=6)
        tk.Label(bar, text=" Search:", bg=p["panel"], fg=p["text"]).pack(side="left", padx=(14, 4))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(bar, textvariable=self.search_var, width=36)
        self.search_entry.pack(side="left", padx=4)
        self.search_entry.bind("<Return>", lambda e: self._apply_search())
        ttk.Button(bar, text="Go", command=self._apply_search).pack(side="left", padx=4)

    def _build_sections_list(self, parent: ttk.Frame) -> None:
        p = self.palette
        tk.Label(parent, text="Sections", anchor="w", bg=p["panel"], fg=p["muted"], padx=8, pady=4).pack(fill="x")
        self.sections_list = tk.Listbox(parent, activestyle="dotbox", bg=p["panel"], fg=p["text"],
                                        selectbackground=self.palette["accent"], highlightthickness=0)
        self.sections_list.pack(fill="both", expand=True, padx=6, pady=6)
        self.sections_list.bind("<<ListboxSelect>>", lambda e: self._on_section_select())
        btns = ttk.Frame(parent)
        btns.pack(fill="x", padx=6, pady=6)
        ttk.Button(btns, text="Add section", command=self._add_section).pack(side="left", padx=2)
        ttk.Button(btns, text="Remove", command=self._remove_section).pack(side="left", padx=2)
        ttk.Button(btns, text="Rename", command=self._rename_section).pack(side="left", padx=2)

    def _build_headlines_list(self, parent: ttk.Frame) -> None:
        p = self.palette
        tk.Label(parent, text="Headlines", anchor="w", bg=p["panel"], fg=p["muted"], padx=8, pady=4).pack(fill="x")
        cols = ("title", "source")
        self.tree = ttk.Treeview(parent, columns=cols, show="headings", style="List.Treeview")
        self.tree.heading("title", text="Title")
        self.tree.heading("source", text="Source")
        self.tree.column("title", width=720, anchor="w")
        self.tree.column("source", width=160, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.tree.bind("<Double-1>", lambda e: self._open_selected())
        self.tree.bind("<Return>", lambda e: self._open_selected())
        # Auto-open in reader when a headline is selected with a single click
        self.tree.bind("<<TreeviewSelect>>", self._auto_open_on_select)

        btns = ttk.Frame(parent)
        btns.pack(fill="x", padx=6, pady=6)
        ttk.Button(btns, text="Open", command=self._open_selected).pack(side="left", padx=2)
        ttk.Button(btns, text="Open in browser", command=self._browser_selected).pack(side="left", padx=2)
        ttk.Button(btns, text="Save to favorites", command=self._fav_selected).pack(side="left", padx=2)
        ttk.Button(btns, text="Remove from favorites", command=self._unfav_selected).pack(side="left", padx=2)

    def _build_reader(self, parent: ttk.Frame) -> None:
        p = self.palette
        tk.Label(parent, text="Reader", anchor="w", bg=p["panel"], fg=p["muted"], padx=8, pady=4).pack(fill="x")
        # Title label with dynamic wrap length, fixes the single-character column issue
        self.reader_title = tk.StringVar(value="Select a headline to read")
        self.lbl_title = tk.Label(parent, textvariable=self.reader_title, bg=p["panel"], fg=p["text"],
                                  anchor="w", justify="left", wraplength=800)
        self.lbl_title.pack(fill="x", padx=10, pady=(4, 0))
        parent.bind(
            "<Configure>",
            lambda e: self.lbl_title.config(wraplength=max(300, e.width - 40))
        )
        # Scrolled text
        self.reader_txt = tk.Text(parent, wrap="word", bg=p["bg"], fg=p["text"],
                                  insertbackground=p["text"], relief="flat")
        self.reader_txt.configure(font=self.font_reader)
        yscroll = ttk.Scrollbar(parent, orient="vertical", command=self.reader_txt.yview)
        self.reader_txt["yscrollcommand"] = yscroll.set
        self.reader_txt.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=6)
        yscroll.pack(side="left", fill="y", padx=(0, 10), pady=6)
        # Actions
        btns = ttk.Frame(parent)
        btns.pack(fill="x", padx=10, pady=4)
        ttk.Button(btns, text="Export .txt", command=self._export_reader).pack(side="left", padx=2)
        ttk.Button(btns, text="Open in browser", command=self._open_current_in_browser).pack(side="left", padx=2)
        ttk.Button(btns, text="A+", command=lambda: self._bump_reader_font(+1), width=4).pack(side="left", padx=(12, 2))
        ttk.Button(btns, text="A-", command=lambda: self._bump_reader_font(-1), width=4).pack(side="left", padx=2)

    # --------------------- events and helpers ---------------------

    def _pump_messages(self) -> None:
        try:
            while True:
                kind, payload = self.outq.get_nowait()
                if kind == "STATUS":
                    self._status(str(payload))
                elif kind == "HEADLINES_ALL":
                    self.all_headlines = payload  # type: ignore
                    self._status("Feeds updated")
                    self._refill_headlines()
                self.outq.task_done()
        except queue.Empty:
            pass
        self.after(150, self._pump_messages)

    def _status(self, msg: str) -> None:
        self.status.set(msg)
        self.title(f"{APP_NAME} | {msg}")

    def refresh_now(self) -> None:
        self.outq.put(("STATUS", "Manual refresh requested"))

    def save_all(self) -> None:
        if self.favorites:
            urls = [h.link for h in self.favorites]
            self.s.sections["Favorites_links"] = urls
        save_settings(self.s)
        self._status("Settings saved")

    def _focus_search(self) -> None:
        self.search_entry.focus_set()
        self.search_entry.select_range(0, "end")

    def _apply_search(self) -> None:
        term = self.search_var.get().strip().lower()
        self._refill_headlines(term=term)

    def _rebuild_sections(self) -> None:
        self.sections_list.delete(0, "end")
        names = [n for n in self.s.sections.keys() if n != "Favorites_links"]
        for extra in ("Breaking", "Favorites"):
            if extra not in names:
                names.insert(0, extra)
        seen = set()
        for n in names:
            if n not in seen:
                self.sections_list.insert("end", n)
                seen.add(n)

    def _on_section_select(self) -> None:
        idx = self._sel_index(self.sections_list)
        if idx is None:
            return
        name = self.sections_list.get(idx)
        self._select_section(name)

    def _select_section(self, name: str) -> None:
        for i in range(self.sections_list.size()):
            if self.sections_list.get(i) == name:
                self.sections_list.selection_clear(0, "end")
                self.sections_list.selection_set(i)
                self.sections_list.activate(i)
                break
        self._refill_headlines()

    def _sel_index(self, listbox: tk.Listbox) -> Optional[int]:
        sel = listbox.curselection()
        return int(sel[0]) if sel else None

    def _iter_current_section_headlines(self) -> List[Headline]:
        idx = self._sel_index(self.sections_list)
        section = self.sections_list.get(idx) if idx is not None else "Breaking"
        if section == "Favorites":
            return list(self.favorites)
        if section == "Breaking":
            return self.all_headlines.get("Breaking", [])
        return self.all_headlines.get(section, [])

    def _refill_headlines(self, term: str = "") -> None:
        items = self._iter_current_section_headlines()
        self.tree.delete(*self.tree.get_children())
        for h in items:
            if term and term not in h.title.lower() and term not in h.source.lower():
                continue
            self.tree.insert("", "end", values=(h.title, h.source))
        self._status(f"Showing {len(self.tree.get_children())} headlines")

    def _current_tree_headline(self) -> Optional[Headline]:
        sel = self.tree.selection()
        if not sel:
            return None
        vals = self.tree.item(sel[0])["values"]
        if not vals:
            return None
        title = vals[0]
        source = vals[1] if len(vals) > 1 else ""
        for h in self._iter_current_section_headlines():
            if h.title == title and h.source == source:
                return h
        return None

    def _open_selected(self) -> None:
        h = self._current_tree_headline()
        if not h:
            return
        self._load_article(h)
    def _auto_open_on_select(self, event=None) -> None:
        """Auto-load the currently selected headline into the reader."""
        # Use a short delay to allow the selection to settle, avoids edge cases on fast clicks
        self.after(5, self._open_selected)


    def _browser_selected(self) -> None:
        h = self._current_tree_headline()
        if not h:
            return
        webbrowser.open(h.link)

    def _fav_selected(self) -> None:
        h = self._current_tree_headline()
        if not h:
            return
        if not any(f.link == h.link for f in self.favorites):
            self.favorites.append(h)
            if self.sections_list.get(self._sel_index(self.sections_list) or 0) == "Favorites":
                self._refill_headlines()
            self._status("Saved to favorites")

    def _unfav_selected(self) -> None:
        h = self._current_tree_headline()
        if not h:
            return
        self.favorites = [f for f in self.favorites if f.link != h.link]
        if self.sections_list.get(self._sel_index(self.sections_list) or 0) == "Favorites":
            self._refill_headlines()
        self._status("Removed from favorites")

    def _load_article(self, h: Headline) -> None:
        self.reader_title.set(f"{h.title}\n{h.source}")
        self.reader_txt.delete("1.0", "end")
        self.reader_txt.insert("1.0", "Loading article...")
        def worker():
            # Fetch article HTML and try to extract readable text
            html = fetch_bytes(h.link)
            if not html:
                self._reader_show_text("Could not fetch this article; opening in your browser.")
                webbrowser.open(h.link)
                return
            title, text = self.extractor.extract(html)
            if not text or len(text) < 300:
                self._reader_show_text("Reader could not extract this page; opening in your browser.")
                webbrowser.open(h.link)
                return
            shown_title = title or h.title
            self._reader_show_text(f"{shown_title}\n\n{text}")
        threading.Thread(target=worker, daemon=True).start()

    def _reader_show_text(self, text: str) -> None:
        def apply():
            self.reader_txt.delete("1.0", "end")
            self.reader_txt.insert("1.0", text)
        self.after(0, apply)

    def _bump_reader_font(self, delta: int) -> None:
        self.s.reader_font_size = max(12, min(28, self.s.reader_font_size + delta))
        self.font_reader.configure(size=self.s.reader_font_size)

    def _open_current_in_browser(self) -> None:
        h = self._current_tree_headline()
        if not h:
            return
        webbrowser.open(h.link)

    def _export_reader(self) -> None:
        text = self.reader_txt.get("1.0", "end").strip()
        if not text:
            messagebox.showinfo("Export", "Nothing to export.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            title="Save article as .txt",
        )
        if not path:
            return
        try:
            # keep paragraphs only, strip extra blank lines
            paras = [p.strip() for p in text.split("\n") if p.strip()]
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n\n".join(paras))
            self._status(f"Saved {Path(path).name}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    def _add_section(self) -> None:
        name = simpledialog.askstring("Add section", "Section name:")
        if not name:
            return
        name = name.strip()
        if not name:
            return
        if name in self.s.sections:
            messagebox.showinfo("Exists", "A section with that name already exists.")
            return
        self.s.sections[name] = []
        self._rebuild_sections()

    def _remove_section(self) -> None:
        idx = self._sel_index(self.sections_list)
        if idx is None:
            return
        name = self.sections_list.get(idx)
        if name in ("Breaking", "Favorites"):
            messagebox.showinfo("Blocked", "This section cannot be removed.")
            return
        if messagebox.askyesno("Remove", f"Remove section '{name}' and its feed list?"):
            self.s.sections.pop(name, None)
            self._rebuild_sections()
            self._select_section("Breaking")

    def _rename_section(self) -> None:
        idx = self._sel_index(self.sections_list)
        if idx is None:
            return
        old = self.sections_list.get(idx)
        if old in ("Breaking", "Favorites"):
            messagebox.showinfo("Blocked", "This section cannot be renamed.")
            return
        new = simpledialog.askstring("Rename section", "New name:", initialvalue=old)
        if not new:
            return
        new = new.strip()
        if not new or new in self.s.sections:
            return
        self.s.sections[new] = self.s.sections.pop(old, [])
        self._rebuild_sections()
        self._select_section(new)

    def open_options(self) -> None:
        OptionsWindow(self)

    def _on_close(self) -> None:
        self.save_all()
        self.stop.set()
        self.destroy()

    def _load_favorites_from_settings(self) -> None:
        links = self.s.sections.get("Favorites_links", [])
        if links:
            stubbed = [Headline(title=l, link=l, source="Favorite") for l in links]
            self.favorites = stubbed


# ----------------------------- Options window -----------------------------

class OptionsWindow(tk.Toplevel):
    def __init__(self, app: NewsDashboard):
        super().__init__(app)
        self.app = app
        self.s = app.s
        self.title("Options")
        self.resizable(True, True)
        self.transient(app)
        self.grab_set()

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_general = ttk.Frame(nb)
        self.tab_style = ttk.Frame(nb)
        self.tab_sections = ttk.Frame(nb)

        nb.add(self.tab_general, text="General")
        nb.add(self.tab_style, text="Style")
        nb.add(self.tab_sections, text="Sections & Feeds")

        self._build_general()
        self._build_style()
        self._build_sections()

        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=10, pady=10)
        ttk.Button(bar, text="Save", command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Close", command=self._close).pack(side="right", padx=4)

    def _build_general(self) -> None:
        s = self.s
        p = ttk.Frame(self.tab_general)
        p.pack(fill="both", expand=True, padx=8, pady=8)

        self.refresh_var = tk.IntVar(value=s.refresh_seconds)
        self.max_var = tk.IntVar(value=s.max_per_section)
        self.inc_src = tk.BooleanVar(value=s.include_source_name)
        self.browser_default = tk.BooleanVar(value=s.open_links_in_browser_by_default)

        make_labeled_spin(p, "Refresh seconds", self.refresh_var, 60, 3600).pack(anchor="w", pady=4)
        make_labeled_spin(p, "Max per section", self.max_var, 10, 500).pack(anchor="w", pady=4)
        ttk.Checkbutton(p, text="Prefix headlines with source name", variable=self.inc_src).pack(anchor="w", pady=4)
        ttk.Checkbutton(p, text="Open links in browser by default", variable=self.browser_default).pack(anchor="w", pady=4)

    def _build_style(self) -> None:
        s = self.s
        p = ttk.Frame(self.tab_style)
        p.pack(fill="both", expand=True, padx=8, pady=8)

        families = sorted(set(tkfont.families()))
        self.font_var = tk.StringVar(value=s.font_family if s.font_family in families else families[0])
        self.size_var = tk.IntVar(value=s.font_size)
        self.reader_size_var = tk.IntVar(value=s.reader_font_size)
        self.bold_var = tk.BooleanVar(value=s.bold_headlines)

        make_labeled_combo(p, "UI font", self.font_var, families, width=26).pack(anchor="w", pady=4)
        make_labeled_spin(p, "Headline font size", self.size_var, 10, 18).pack(anchor="w", pady=4)
        make_labeled_spin(p, "Reader font size", self.reader_size_var, 12, 28).pack(anchor="w", pady=4)
        ttk.Checkbutton(p, text="Bold headlines", variable=self.bold_var).pack(anchor="w", pady=8)

        # colors
        tk.Label(p, text="Colors", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(12, 4))
        self.colors: Dict[str, tk.StringVar] = {}
        for key in ("bg", "panel", "text", "muted", "accent", "accent2", "list_alt", "link"):
            v = tk.StringVar(value=s.palette.get(key, _default_palette()[key]))
            self.colors[key] = v
            make_color_picker(p, key, v).pack(anchor="w", pady=2)

    def _build_sections(self) -> None:
        s = self.s
        root = ttk.Frame(self.tab_sections)
        root.pack(fill="both", expand=True, padx=8, pady=8)

        left = ttk.Frame(root)
        left.pack(side="left", fill="both", expand=False)

        tk.Label(left, text="Sections").pack(anchor="w")
        self.section_list = tk.Listbox(left, height=12)
        self.section_list.pack(fill="y", expand=False)
        for name in s.sections.keys():
            if name != "Favorites_links":
                self.section_list.insert("end", name)

        btns = ttk.Frame(left)
        btns.pack(fill="x", pady=6)
        ttk.Button(btns, text="Add", command=self._add_section).pack(side="left", padx=2)
        ttk.Button(btns, text="Rename", command=self._rename_section).pack(side="left", padx=2)
        ttk.Button(btns, text="Remove", command=self._remove_section).pack(side="left", padx=2)

        # feeds editor
        right = ttk.Frame(root)
        right.pack(side="left", fill="both", expand=True, padx=(10, 0))
        tk.Label(right, text="Feeds for selected section").pack(anchor="w")
        self.feed_list = tk.Listbox(right, height=12)
        self.feed_list.pack(fill="both", expand=True)

        btns2 = ttk.Frame(right)
        btns2.pack(fill="x", pady=6)
        ttk.Button(btns2, text="Add feed", command=self._add_feed).pack(side="left", padx=2)
        ttk.Button(btns2, text="Edit", command=self._edit_feed).pack(side="left", padx=2)
        ttk.Button(btns2, text="Remove", command=self._remove_feed).pack(side="left", padx=2)
        ttk.Button(btns2, text="Move up", command=lambda: self._move_feed(-1)).pack(side="left", padx=2)
        ttk.Button(btns2, text="Move down", command=lambda: self._move_feed(+1)).pack(side="left", padx=2)
        ttk.Button(btns2, text="Restore defaults", command=self._restore_defaults).pack(side="left", padx=(14, 2))

        self.section_list.bind("<<ListboxSelect>>", lambda e: self._load_feeds_for_selected())
        if self.section_list.size():
            self.section_list.selection_set(0)
            self._load_feeds_for_selected()

    # ---- options events ----

    def _add_section(self) -> None:
        name = simpledialog.askstring("Add section", "Section name:", parent=self)
        if not name:
            return
        name = name.strip()
        if not name or name in self.s.sections or name in ("Breaking", "Favorites", "Favorites_links"):
            return
        self.s.sections[name] = []
        self.section_list.insert("end", name)

    def _rename_section(self) -> None:
        idx = self._sel_index(self.section_list)
        if idx is None:
            return
        old = self.section_list.get(idx)
        if old in ("Breaking", "Favorites", "Favorites_links"):
            return
        new = simpledialog.askstring("Rename section", "New name:", initialvalue=old, parent=self)
        if not new:
            return
        new = new.strip()
        if not new or new in self.s.sections:
            return
        self.s.sections[new] = self.s.sections.pop(old, [])
        self.section_list.delete(idx)
        self.section_list.insert(idx, new)
        self.section_list.selection_set(idx)

    def _remove_section(self) -> None:
        idx = self._sel_index(self.section_list)
        if idx is None:
            return
        name = self.section_list.get(idx)
        if name in ("Breaking", "Favorites", "Favorites_links"):
            return
        if messagebox.askyesno("Remove", f"Remove section '{name}'?"):
            self.s.sections.pop(name, None)
            self.section_list.delete(idx)
            self.feed_list.delete(0, "end")

    def _load_feeds_for_selected(self) -> None:
        idx = self._sel_index(self.section_list)
        if idx is None:
            return
        name = self.section_list.get(idx)
        self.feed_list.delete(0, "end")
        for u in self.s.sections.get(name, []):
            self.feed_list.insert("end", u)

    def _add_feed(self) -> None:
        idx = self._sel_index(self.section_list)
        if idx is None:
            return
        name = self.section_list.get(idx)
        url = simpledialog.askstring("Add feed", "Enter RSS or Atom feed URL:", parent=self)
        if not url:
            return
        url = url.strip()
        if not url:
            return
        self.s.sections.setdefault(name, []).append(url)
        self.feed_list.insert("end", url)

    def _edit_feed(self) -> None:
        sidx = self._sel_index(self.section_list)
        fidx = self._sel_index(self.feed_list)
        if sidx is None or fidx is None:
            return
        name = self.section_list.get(sidx)
        cur = self.feed_list.get(fidx)
        url = simpledialog.askstring("Edit feed", "Feed URL:", initialvalue=cur, parent=self)
        if not url:
            return
        url = url.strip()
        if not url:
            return
        self.s.sections[name][fidx] = url
        self.feed_list.delete(fidx)
        self.feed_list.insert(fidx, url)
        self.feed_list.selection_set(fidx)

    def _remove_feed(self) -> None:
        sidx = self._sel_index(self.section_list)
        fidx = self._sel_index(self.feed_list)
        if sidx is None or fidx is None:
            return
        name = self.section_list.get(sidx)
        del self.s.sections[name][fidx]
        self.feed_list.delete(fidx)

    def _move_feed(self, direction: int) -> None:
        sidx = self._sel_index(self.section_list)
        fidx = self._sel_index(self.feed_list)
        if sidx is None or fidx is None:
            return
        name = self.section_list.get(sidx)
        new = fidx + direction
        if new < 0 or new >= self.feed_list.size():
            return
        feeds = self.s.sections[name]
        feeds[fidx], feeds[new] = feeds[new], feeds[fidx]
        self._load_feeds_for_selected()
        self.feed_list.selection_set(new)

    def _restore_defaults(self) -> None:
        if not messagebox.askyesno(
            "Restore defaults",
            "Replace section feeds with defaults for this name, if available?"
        ):
            return
        sidx = self._sel_index(self.section_list)
        if sidx is None:
            return
        name = self.section_list.get(sidx)
        if name in DEFAULT_SECTIONS:
            self.s.sections[name] = list(DEFAULT_SECTIONS[name])
            self._load_feeds_for_selected()
        else:
            messagebox.showinfo("No defaults", "No defaults for this section name.")

    def _save(self) -> None:
        self.s.refresh_seconds = int(self.refresh_var.get())
        self.s.max_per_section = int(self.max_var.get())
        self.s.include_source_name = bool(self.inc_src.get())
        self.s.open_links_in_browser_by_default = bool(self.browser_default.get())
        self.s.font_family = self.font_var.get()
        self.s.font_size = int(self.size_var.get())
        self.s.reader_font_size = int(self.reader_size_var.get())
        self.s.bold_headlines = bool(self.bold_var.get())
        for k, var in self.colors.items():
            self.s.palette[k] = var.get()
        self.s.clamp()
        # reapply styles and fonts in the main app
        self.app.palette = dict(self.s.palette)
        self.app._apply_styles()
        self.app.font_list.configure(
            family=self.s.font_family,
            size=self.s.font_size,
            weight="bold" if self.s.bold_headlines else "normal",
        )
        self.app.font_reader.configure(
            family=self.s.font_family,
            size=self.s.reader_font_size,
        )
        self.app.save_all()
        self.app._rebuild_sections()
        self.app._refill_headlines()
        messagebox.showinfo("Saved", "Options saved.")
        self._close()

    def _close(self) -> None:
        self.destroy()

    def _sel_index(self, lb: tk.Listbox) -> Optional[int]:
        sel = lb.curselection()
        return int(sel[0]) if sel else None


# ----------------------------- small UI helpers -----------------------------

def make_labeled_spin(parent, label: str, var: tk.IntVar, mn: int, mx: int) -> ttk.Frame:
    f = ttk.Frame(parent)
    ttk.Label(f, text=label).pack(side="left", padx=(0, 8))
    sp = ttk.Spinbox(f, from_=mn, to=mx, textvariable=var, width=6)
    sp.pack(side="left")
    return f

def make_labeled_combo(parent, label: str, var: tk.StringVar, values: List[str], width: int = 20) -> ttk.Frame:
    f = ttk.Frame(parent)
    ttk.Label(f, text=label).pack(side="left", padx=(0, 8))
    cb = ttk.Combobox(f, textvariable=var, values=values, width=width, state="readonly")
    cb.pack(side="left")
    return f

def make_color_picker(parent, label: str, var: tk.StringVar) -> ttk.Frame:
    f = ttk.Frame(parent)
    ttk.Label(f, text=label).pack(side="left", padx=(0, 8))
    btn = ttk.Button(f, textvariable=var, command=lambda: _pick_color(var))
    btn.pack(side="left")
    return f

def _pick_color(var: tk.StringVar) -> None:
    initial = var.get()
    color, _ = colorchooser.askcolor(initialcolor=initial)
    if color:
        r, g, b = [int(c) for c in color]
        var.set(f"#{r:02x}{g:02x}{b:02x}")


# ----------------------------- app entry -----------------------------

def main() -> None:
    s = load_settings(SETTINGS_FILE)
    app = NewsDashboard(s)
    app.mainloop()

if __name__ == "__main__":
    main()
