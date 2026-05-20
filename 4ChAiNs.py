import json
import threading
import time
import html
import webbrowser
from pathlib import Path
from urllib import request, error, parse

import tkinter as tk
from tkinter import ttk, messagebox

from typing import Optional


APP_NAME = "Chan & Reddit Clean Reader"
PREFS_FILENAME = ".chan_reddit_reader_prefs.json"
TOP_SUBREDDITS = [
    "all","announcements","AskReddit","funny","gaming","aww","worldnews","todayilearned",
    "movies","pics","science","news","IAmA","Showerthoughts","mildlyinteresting","videos",
    "Music","Jokes","LifeProTips","explainlikeimfive","OldSchoolCool","space","sports","nottheonion",
    "EarthPorn","food","DIY","Art","books","history",
]

COLOR_CHOICES = [
    "black","white","gray10","gray20","gray30","gray40","gray50","gray60","gray70","gray80",
    "red","tomato","orange","gold","yellow","green","lime","teal","cyan","skyblue",
    "blue","navy","steelblue","purple","magenta","pink","brown","sienna",
]


def get_prefs_path() -> Path:
    """
    Return the path to the preferences file in the user's home directory.
    """
    home = Path.home()
    return home / PREFS_FILENAME


def load_preferences() -> dict:
    """
    Load preferences from disk, or return defaults if not present.
    """
    defaults = {
        "sfw_mode": "hide",  # hide, blur, show
        "site": "4chan",  # 4chan or Reddit
        "current_board": "g",
        "current_subreddit": "all",
        "auto_refresh_enabled": False,
        "auto_refresh_interval": 60,
        "keyword_filter": [],
        "poster_filter_4chan": [],
        "author_filter_reddit": [],
        "bookmarks": [],
        "recent": [],
        "proxy": "",
        "font_size": 11,
        "theme_name": "Dark",
        "custom_theme": {},
    }
    path = get_prefs_path()
    if not path.exists():
        return defaults
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return defaults
        defaults.update({k: v for k, v in data.items() if k in defaults})
        return defaults
    except Exception:
        return defaults


def save_preferences(prefs: dict) -> None:
    """
    Save preferences to disk.
    """
    try:
        path = get_prefs_path()
        with path.open("w", encoding="utf-8") as f:
            json.dump(prefs, f, indent=2)
    except Exception:
        # Non fatal
        pass


def build_opener(proxy_url: Optional[str]) -> request.OpenerDirector:
    """
    Build a urllib opener with optional proxy and a custom User Agent.
    """
    handlers = []
    if proxy_url:
        handlers.append(request.ProxyHandler({"http": proxy_url, "https": proxy_url}))
    opener = request.build_opener(*handlers)
    opener.addheaders = [
        ("User-Agent", f"{APP_NAME}/1.0 (https://example.com)")
    ]
    return opener


def fetch_json(
    url: str, proxy_url: Optional[str] = None, timeout: int = 15
) -> Optional[object]:
    """
    Fetch JSON from a URL and return the parsed object.
    Returns None on error.
    """
    opener = build_opener(proxy_url)
    try:
        with opener.open(url, timeout=timeout) as resp:
            data = resp.read()
        return json.loads(data.decode("utf-8", errors="replace"))
    except error.URLError as e:
        print(f"Network error: {e}")
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
    except Exception as e:
        print(f"Unexpected error fetching {url}: {e}")
    return None


def strip_html(text: str) -> str:
    """
    Very simple HTML tag stripper for 4chan comments.
    """
    result = []
    in_tag = False
    for ch in text:
        if ch == "<":
            in_tag = True
            continue
        if ch == ">":
            in_tag = False
            continue
        if not in_tag:
            result.append(ch)
    cleaned = "".join(result)
    cleaned = cleaned.replace("<br>", "\n").replace("&gt;", ">")
    cleaned = html.unescape(cleaned)
    return cleaned


class Tooltip:
    """
    Simple tooltip for Tkinter widgets.
    """

    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, _event=None):
        if self.tip_window is not None or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=self.text,
            justify=tk.LEFT,
            relief=tk.SOLID,
            borderwidth=1,
            padx=4,
            pady=2,
            background="#ffffe0",
        )
        label.pack()

    def hide_tip(self, _event=None):
        if self.tip_window is not None:
            self.tip_window.destroy()
            self.tip_window = None


class ReaderApp(tk.Tk):
    """
    Main application window and controller.
    A clean reader for 4chan and Reddit that shows username and message only.
    """

    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1100x650")
        self.minsize(900, 550)

        self.prefs = load_preferences()
        self.log_entries: list[str] = []

        self.current_site = self.prefs.get("site", "4chan")
        self.current_board = self.prefs.get("current_board", "g")
        self.current_subreddit = self.prefs.get("current_subreddit", "all")
        self.current_thread_descriptor: Optional[dict] = None

        # board name -> {title, meta}
        self.boards_info: dict[str, dict] = {}

        self._auto_refresh_job: Optional[str] = None
        self.theme_tokens = {}
        self._style_theme = ttk.Style(self)

        self._build_style()
        self._build_menu()
        self._build_widgets()
        self._bind_shortcuts()

        # Load initial data
        self.after(100, self.load_initial_data)

    def log(self, message: str) -> None:
        """
        Append a line to the internal log and update the status view.
        """
        timestamp = time.strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}"
        print(line)
        self.log_entries.append(line)
        if len(self.log_entries) > 500:
            self.log_entries = self.log_entries[-500:]
        self.status_var.set(message)
        self._refresh_status_text()

    def _refresh_status_text(self) -> None:
        """
        Update the status tab content.
        """
        if not hasattr(self, "status_text"):
            return
        self.status_text.configure(state="normal")
        self.status_text.delete("1.0", tk.END)
        self.status_text.insert(tk.END, "\n".join(self.log_entries))
        self.status_text.configure(state="disabled")
        self.status_text.see(tk.END)

    def _build_style(self) -> None:
        """
        Configure a simple dark theme using ttk.
        """
        try:
            self._style_theme.theme_use("clam")
        except tk.TclError:
            pass
        self._style_theme.configure("Header.TLabel", font=("Segoe UI", 11, "bold"))
        self._style_theme.configure("TButton", padding=(6, 3))
        self._style_theme.configure("Treeview", rowheight=22)
        self._style_theme.map(
            "TButton",
            relief=[("pressed", "sunken"), ("active", "raised")],
        )
        self._init_themes()
        self.apply_theme(self.prefs.get("theme_name", "Dark"))

    def _init_themes(self) -> None:
        """
        Initialize built-in themes and an optional saved custom theme.
        """
        self.themes = {
            "Dark": {"bg":"#1e1f22","panel":"#2a2c31","fg":"#f0f0f0","muted":"#c1c1c1","accent":"#8ab4f8","text_bg":"#121212","status_bg":"#101010","search_bg":"#555555"},
            "Light Professional": {"bg":"#f3f5f7","panel":"#ffffff","fg":"#1f2937","muted":"#475569","accent":"#1d4ed8","text_bg":"#ffffff","status_bg":"#f8fafc","search_bg":"#dbeafe"},
            "Blue/Steel": {"bg":"#1b2635","panel":"#27384c","fg":"#e8eef5","muted":"#c5d1dd","accent":"#63b3ed","text_bg":"#0f1b2a","status_bg":"#132235","search_bg":"#355c7d"},
            "High Contrast": {"bg":"#000000","panel":"#111111","fg":"#ffffff","muted":"#ffffff","accent":"#00ffff","text_bg":"#000000","status_bg":"#000000","search_bg":"#ffff00"},
        }
        custom = self.prefs.get("custom_theme", {})
        if custom:
            self.themes["Custom"] = custom
        else:
            # Keep Custom available in menus even before first save.
            self.themes["Custom"] = dict(self.themes["Dark"])

    def _build_menu(self) -> None:
        """
        Build the top application menu.
        """
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Refresh", command=self.refresh_current, accelerator="Ctrl+R")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.destroy, accelerator="Ctrl+Q")
        menubar.add_cascade(label="File", menu=file_menu)
        view = tk.Menu(menubar, tearoff=0)
        theme_menu = tk.Menu(view, tearoff=0)
        for name in ["Dark","Light Professional","Blue/Steel","High Contrast","Custom"]:
            theme_menu.add_command(label=name, command=lambda n=name: self.apply_theme(n))
        theme_menu.add_separator()
        theme_menu.add_command(label="Custom Theme Maker", command=self.open_custom_theme_maker)
        view.add_cascade(label="Theme", menu=theme_menu)
        menubar.add_cascade(label="View", menu=view)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Keyboard Shortcuts", command=self.show_shortcuts)
        help_menu.add_command(label="Tips and Tricks", command=self.show_tips)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.config(menu=menubar)

    def _build_widgets(self) -> None:
        """
        Build all UI widgets and layout.
        """
        # Top level layout: horizontal paned window
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(paned, padding=8)
        right = ttk.Frame(paned, padding=8)
        paned.add(left, weight=1)
        paned.add(right, weight=3)

        # Left side controls
        site_row = ttk.Frame(left)
        site_row.pack(fill=tk.X, pady=(0, 4))

        ttk.Label(site_row, text="Site:", style="Header.TLabel").pack(side=tk.LEFT)
        self.site_var = tk.StringVar(value=self.current_site)
        self.site_combo = ttk.Combobox(
            site_row,
            textvariable=self.site_var,
            values=["4chan", "Reddit"],
            state="readonly",
            width=10,
        )
        self.site_combo.pack(side=tk.LEFT, padx=(6, 0))
        self.site_combo.bind("<<ComboboxSelected>>", self.on_site_changed)
        Tooltip(self.site_combo, "Switch between 4chan and Reddit")

        # 4chan controls frame
        self.chan_frame = ttk.LabelFrame(left, text="4chan", padding=6)
        self.chan_frame.pack(fill=tk.X, pady=(4, 4))

        chan_board_row = ttk.Frame(self.chan_frame)
        chan_board_row.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(chan_board_row, text="Board:").pack(side=tk.LEFT)
        self.board_var = tk.StringVar(value=self.current_board)
        self.board_combo = ttk.Combobox(
            chan_board_row, textvariable=self.board_var, width=8, state="readonly"
        )
        self.board_combo.pack(side=tk.LEFT, padx=(4, 4))
        # Update guide when selection is changed or when arrow keys move through boards
        self.board_combo.bind("<<ComboboxSelected>>", self.on_board_changed)
        self.board_combo.bind("<Up>", self.on_board_arrow)
        self.board_combo.bind("<Down>", self.on_board_arrow)
        self.board_combo.bind("<Return>", self.on_board_enter)
        self.board_combo.bind("<Tab>", self.on_board_tab)

        self.load_board_btn = ttk.Button(
            chan_board_row, text="Load", command=self.load_board_catalog
        )
        self.load_board_btn.pack(side=tk.LEFT)
        Tooltip(self.load_board_btn, "Load catalog for selected board")

        # Board guide label under the combobox
        self.board_info_label = ttk.Label(
            self.chan_frame,
            text="",
            wraplength=260,
            justify=tk.LEFT,
        )
        self.board_info_label.pack(fill=tk.X, pady=(2, 0))

        # 4chan search helper using Google site search
        chan_search_row = ttk.Frame(self.chan_frame)
        chan_search_row.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(chan_search_row, text="Google search:").pack(side=tk.LEFT)
        self.chan_search_var = tk.StringVar()
        chan_search_entry = ttk.Entry(
            chan_search_row, textvariable=self.chan_search_var
        )
        chan_search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4))
        chan_search_btn = ttk.Button(
            chan_search_row, text="Open", command=self.open_4chan_google_search
        )
        chan_search_btn.pack(side=tk.LEFT)
        Tooltip(
            chan_search_btn,
            'Open browser search using pattern: site:4chan.org "your terms"',
        )

        # Reddit controls frame
        self.reddit_frame = ttk.LabelFrame(left, text="Reddit", padding=6)
        self.reddit_frame.pack(fill=tk.X, pady=(4, 4))

        reddit_row1 = ttk.Frame(self.reddit_frame)
        reddit_row1.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(reddit_row1, text="Subreddit:").pack(side=tk.LEFT)
        self.subreddit_var = tk.StringVar(value=self.current_subreddit)
        self.subreddit_entry = ttk.Entry(
            reddit_row1, textvariable=self.subreddit_var, width=16
        )
        self.subreddit_entry.pack(side=tk.LEFT, padx=(4, 4))
        self.top_sub_var = tk.StringVar(value="Top subreddits")
        self.top_sub_combo = ttk.Combobox(reddit_row1, textvariable=self.top_sub_var, values=TOP_SUBREDDITS, state="readonly", width=18)
        self.top_sub_combo.pack(side=tk.LEFT, padx=(0,4))
        self.top_sub_combo.bind("<<ComboboxSelected>>", self.on_top_subreddit_selected)
        self.subreddit_sort_var = tk.StringVar(value="hot")
        sort_combo = ttk.Combobox(
            reddit_row1,
            textvariable=self.subreddit_sort_var,
            values=["hot", "new", "top"],
            width=6,
            state="readonly",
        )
        sort_combo.pack(side=tk.LEFT, padx=(4, 4))
        self.load_subreddit_btn = ttk.Button(
            reddit_row1, text="Load", command=self.load_subreddit_posts
        )
        self.load_subreddit_btn.pack(side=tk.LEFT)
        Tooltip(self.load_subreddit_btn, "Load posts from subreddit")

        # Thread list
        threads_label = ttk.Label(left, text="Threads", style="Header.TLabel")
        threads_label.pack(anchor="w", pady=(8, 2))

        thread_frame = ttk.Frame(left)
        thread_frame.pack(fill=tk.BOTH, expand=True)

        self.thread_list = tk.Listbox(
            thread_frame,
            activestyle="dotbox",
            exportselection=False,
        )
        thread_scroll = ttk.Scrollbar(
            thread_frame, orient=tk.VERTICAL, command=self.thread_list.yview
        )
        self.thread_list.configure(yscrollcommand=thread_scroll.set)
        self.thread_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        thread_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.thread_list.bind("<<ListboxSelect>>", self.on_thread_selected)
        # Ensure keyboard Up or Down also triggers open after selection moves
        self.thread_list.bind("<KeyRelease-Up>", lambda e: self.on_thread_selected())
        self.thread_list.bind("<KeyRelease-Down>", lambda e: self.on_thread_selected())
        self.thread_list.bind("<Return>", self.on_thread_enter)
        self.thread_list.bind("<Tab>", self.on_threads_tab)
        Tooltip(self.thread_list, "Select a thread to view in the reader")

        # Bookmarks
        bookmarks_label = ttk.Label(left, text="Bookmarks", style="Header.TLabel")
        bookmarks_label.pack(anchor="w", pady=(8, 2))
        bookmarks_frame = ttk.Frame(left)
        bookmarks_frame.pack(fill=tk.BOTH, expand=False)

        self.bookmarks_list = tk.Listbox(
            bookmarks_frame,
            height=6,
            activestyle="dotbox",
            exportselection=False,
        )
        bm_scroll = ttk.Scrollbar(
            bookmarks_frame, orient=tk.VERTICAL, command=self.bookmarks_list.yview
        )
        self.bookmarks_list.configure(yscrollcommand=bm_scroll.set)
        self.bookmarks_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        bm_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.bookmarks_list.bind("<Double-Button-1>", self.on_bookmark_activated)
        Tooltip(self.bookmarks_list, "Double click a bookmark to open it")

        # Bookmark buttons
        bm_btn_row = ttk.Frame(left)
        bm_btn_row.pack(fill=tk.X, pady=(2, 0))
        add_bm_btn = ttk.Button(
            bm_btn_row, text="Add current", command=self.add_current_bookmark
        )
        add_bm_btn.pack(side=tk.LEFT)
        del_bm_btn = ttk.Button(
            bm_btn_row, text="Delete", command=self.delete_selected_bookmark
        )
        del_bm_btn.pack(side=tk.LEFT, padx=(4, 0))
        Tooltip(add_bm_btn, "Bookmark the currently open thread")
        Tooltip(del_bm_btn, "Remove the selected bookmark")

        # Right side: notebook with reader and status
        notebook = ttk.Notebook(right)
        notebook.pack(fill=tk.BOTH, expand=True)

        reader_tab = ttk.Frame(notebook, padding=4)
        status_tab = ttk.Frame(notebook, padding=4)
        notebook.add(reader_tab, text="Reader")
        notebook.add(status_tab, text="Status")

        # Reader controls
        reader_controls = ttk.Frame(reader_tab)
        reader_controls.pack(fill=tk.X, pady=(0, 4))

        self.sfw_var = tk.StringVar(value=self.prefs.get("sfw_mode", "hide"))
        sfw_menu = ttk.OptionMenu(
            reader_controls,
            self.sfw_var,
            self.sfw_var.get(),
            "hide",
            "blur",
            "show",
            command=self.on_sfw_mode_changed,
        )
        ttk.Label(reader_controls, text="Images:").pack(side=tk.LEFT)
        sfw_menu.pack(side=tk.LEFT, padx=(4, 8))
        Tooltip(
            sfw_menu,
            "Choose how images are handled: hide, blur placeholder, or show thumbnails",
        )

        self.auto_refresh_var = tk.BooleanVar(
            value=self.prefs.get("auto_refresh_enabled", False)
        )
        auto_refresh_cb = ttk.Checkbutton(
            reader_controls,
            text="Auto refresh",
            variable=self.auto_refresh_var,
            command=self.on_auto_refresh_changed,
        )
        auto_refresh_cb.pack(side=tk.LEFT)
        Tooltip(auto_refresh_cb, "Periodically refresh the current list or thread")

        ttk.Label(reader_controls, text="Every").pack(side=tk.LEFT, padx=(4, 0))
        self.refresh_interval_var = tk.IntVar(
            value=int(self.prefs.get("auto_refresh_interval", 60))
        )
        interval_spin = ttk.Spinbox(
            reader_controls,
            from_=15,
            to=600,
            textvariable=self.refresh_interval_var,
            width=5,
            command=self.on_refresh_interval_changed,
        )
        interval_spin.pack(side=tk.LEFT)
        ttk.Label(reader_controls, text="sec").pack(side=tk.LEFT)
        Tooltip(interval_spin, "Auto refresh interval in seconds")

        # Search in thread
        ttk.Label(reader_controls, text="Find:").pack(side=tk.LEFT, padx=(12, 0))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(
            reader_controls, textvariable=self.search_var, width=18
        )
        self.search_entry.pack(side=tk.LEFT, padx=(4, 0))
        search_btn = ttk.Button(
            reader_controls, text="Go", command=self.search_in_thread
        )
        search_btn.pack(side=tk.LEFT, padx=(2, 0))
        Tooltip(search_btn, "Search within the current thread text")

        # Reader text widget
        self.reader_text = tk.Text(
            reader_tab,
            wrap=tk.WORD,
            state="disabled",
            background="#121212",
            foreground="#f0f0f0",
            insertbackground="#ffffff",
            padx=8,
            pady=8,
        )
        self.reader_text.pack(fill=tk.BOTH, expand=True)
        reader_font_size = int(self.prefs.get("font_size", 11))
        self._set_reader_font_size(reader_font_size)

        # Status tab widgets
        status_label = ttk.Label(status_tab, text="Network and activity log")
        status_label.pack(anchor="w")
        self.status_text = tk.Text(
            status_tab,
            wrap=tk.NONE,
            height=10,
            state="disabled",
            background="#101010",
            foreground="#e0e0e0",
        )
        self.status_text.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        # Bottom status bar
        status_bar = ttk.Frame(self)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_var = tk.StringVar(value="Ready")
        status_label_bar = ttk.Label(
            status_bar, textvariable=self.status_var, anchor="w"
        )
        status_label_bar.pack(fill=tk.X, padx=6, pady=2)

        self._update_site_frames()
        self._refresh_bookmarks_view()

    def _set_reader_font_size(self, size: int) -> None:
        """
        Set the font size for the reader text widget.
        """
        try:
            self.reader_text.configure(font=("Segoe UI", size))
        except tk.TclError:
            self.reader_text.configure(font=("TkDefaultFont", size))

    def _bind_shortcuts(self) -> None:
        """
        Set up keyboard shortcuts.
        """
        self.bind("<Control-f>", lambda e: self._focus_search())
        self.bind("<Control-F>", lambda e: self._focus_search())
        self.bind("<Control-l>", lambda e: self._focus_site_switch())
        self.bind("<Control-L>", lambda e: self._focus_site_switch())
        self.bind("<Control-b>", lambda e: self.add_current_bookmark())
        self.bind("<Control-B>", lambda e: self.add_current_bookmark())
        self.bind("<Control-s>", lambda e: self.cycle_sfw_mode())
        self.bind("<Control-S>", lambda e: self.cycle_sfw_mode())
        self.bind("<Control-r>", lambda e: self.refresh_current())
        self.bind("<Control-R>", lambda e: self.refresh_current())
        self.bind("<Control-plus>", lambda e: self.adjust_font_size(1))
        self.bind("<Control-minus>", lambda e: self.adjust_font_size(-1))
        self.bind("<Control-=>", lambda e: self.adjust_font_size(1))
        self.bind("<Control-q>", lambda e: self.destroy())

    def _focus_search(self) -> None:
        """
        Focus the inline search box.
        """
        if hasattr(self, "search_entry"):
            self.search_entry.focus_set()

    def _focus_site_switch(self) -> None:
        """
        Focus the site selection combobox.
        """
        self.focus()
        if hasattr(self, "site_combo"):
            self.site_combo.focus_set()

    def on_top_subreddit_selected(self, _event=None) -> None:
        chosen = self.top_sub_var.get().strip()
        if chosen:
            self.subreddit_var.set(chosen)
            self.load_subreddit_posts()

    def apply_theme(self, name: str) -> None:
        """
        Apply a theme immediately to styled and Tk widgets.
        """
        if name not in self.themes:
            return
        t = self.themes[name]
        self.theme_tokens = t
        s = self._style_theme
        s.configure("TFrame", background=t["bg"])
        s.configure("TLabel", background=t["bg"], foreground=t["fg"])
        s.configure("TLabelframe", background=t["panel"], foreground=t["fg"])
        s.configure("TLabelframe.Label", background=t["panel"], foreground=t["fg"])
        s.configure("TCheckbutton", background=t["bg"], foreground=t["fg"])
        s.configure("TMenubutton", background=t["panel"], foreground=t["fg"])
        self.configure(background=t["bg"])
        if hasattr(self, "reader_text"):
            self.reader_text.configure(background=t["text_bg"], foreground=t["fg"], insertbackground=t["fg"])
            self.status_text.configure(background=t["status_bg"], foreground=t["muted"], insertbackground=t["fg"])
            self.reader_text.tag_config("search_hit", background=t["search_bg"], foreground=t["fg"])
            self.reader_text.tag_config("username", foreground=t["accent"])
            self.reader_text.tag_config("thread_title", foreground=t["fg"])
        self.prefs["theme_name"] = name
        save_preferences(self.prefs)

    def open_custom_theme_maker(self) -> None:
        """
        Open a simple custom theme editor with live preview.
        """
        win = tk.Toplevel(self)
        win.title("Custom Theme Maker")
        win.geometry("540x360")
        win.resizable(False, False)
        areas = [("bg","Window Background"),("panel","Panels"),("fg","Main Text"),("muted","Secondary Text"),("accent","Accent/Usernames"),("text_bg","Reader Background"),("status_bg","Status Background"),("search_bg","Search Highlight")]
        current = dict(self.themes.get(self.prefs.get("theme_name","Dark"), self.themes["Dark"]))
        vars_map = {}
        preview_frame = ttk.LabelFrame(win, text="Preview", padding=8)
        preview_frame.grid(row=0, column=2, rowspan=len(areas)+1, padx=(10, 8), pady=8, sticky="ns")
        preview_label = tk.Label(preview_frame, text="Aa Preview Text", width=18)
        preview_label.pack(pady=(4, 6))
        preview_muted = tk.Label(preview_frame, text="Muted text", width=18)
        preview_muted.pack(pady=(0, 6))
        preview_box = tk.Label(preview_frame, text="Reader area", width=18, height=4)
        preview_box.pack()

        for i,(k,label) in enumerate(areas):
            ttk.Label(win, text=label).grid(row=i,column=0,sticky="w",padx=8,pady=4)
            v = tk.StringVar(value=current.get(k, "white"))
            vars_map[k] = v
            combo = ttk.Combobox(win, textvariable=v, values=[f"{c} ■" for c in COLOR_CHOICES], width=20, state="readonly")
            combo.grid(row=i,column=1,sticky="w")
            combo.bind(
                "<<ComboboxSelected>>",
                lambda e: self._preview_custom(vars_map, preview_label, preview_muted, preview_box),
            )
        self._preview_custom(vars_map, preview_label, preview_muted, preview_box)
        ttk.Button(win, text="Save & Apply", command=lambda: self._save_custom_theme(vars_map, win)).grid(row=len(areas),column=1,sticky="e",pady=10)

    def _preview_custom(self, vars_map: dict, preview_label=None, preview_muted=None, preview_box=None) -> None:
        """
        Live preview custom theme in app and optional sample widgets.
        """
        theme = {k: v.get().split()[0] for k, v in vars_map.items()}
        self.themes["Custom"] = theme
        self.apply_theme("Custom")
        if preview_label:
            preview_label.configure(bg=theme["panel"], fg=theme["fg"])
            preview_muted.configure(bg=theme["panel"], fg=theme["muted"])
            preview_box.configure(bg=theme["text_bg"], fg=theme["accent"])

    def _save_custom_theme(self, vars_map: dict, window) -> None:
        theme = {k: v.get().split()[0] for k, v in vars_map.items()}
        self.themes["Custom"] = theme
        self.prefs["custom_theme"] = theme
        save_preferences(self.prefs)
        self.apply_theme("Custom")
        window.destroy()

    def show_shortcuts(self) -> None:
        messagebox.showinfo(
            "Keyboard Shortcuts",
            "Ctrl+F: Find in thread\n"
            "Ctrl+L: Focus site selector\n"
            "Ctrl+R: Refresh current view\n"
            "Ctrl+B: Bookmark current thread\n"
            "Ctrl+S: Cycle image mode\n"
            "Ctrl++ / Ctrl+-: Font size\n"
            "Ctrl+Q: Quit\n"
            "Enter: Open selected thread\n"
            "Tab: Move focus between selectors/list",
        )
    def show_tips(self) -> None:
        messagebox.showinfo("Tips and Tricks", "Use the subreddit dropdown for quick navigation.\nUse bookmarks to save favorites.\nEnable auto-refresh for live discussions.\nUse theme menu to match lighting/accessibility.")
    def show_about(self) -> None:
        messagebox.showinfo("About", f"{APP_NAME}\nA clean 4chan + Reddit reader built with Python stdlib + Tkinter.")

    def adjust_font_size(self, delta: int) -> None:
        """
        Increase or decrease reader font size.
        """
        size = int(self.prefs.get("font_size", 11))
        size = max(8, min(24, size + delta))
        self.prefs["font_size"] = size
        save_preferences(self.prefs)
        self._set_reader_font_size(size)
        self.log(f"Font size set to {size}")

    def cycle_sfw_mode(self) -> None:
        """
        Cycle image mode: hide -> blur -> show -> hide.
        """
        modes = ["hide", "blur", "show"]
        current = self.sfw_var.get()
        try:
            idx = modes.index(current)
        except ValueError:
            idx = 0
        new_mode = modes[(idx + 1) % len(modes)]
        self.sfw_var.set(new_mode)
        self.on_sfw_mode_changed(new_mode)

    def on_sfw_mode_changed(self, value: str) -> None:
        """
        Store new SFW mode and refresh current thread.
        """
        self.prefs["sfw_mode"] = value
        save_preferences(self.prefs)
        self.log(f"Image mode changed to {value}")
        if self.current_thread_descriptor:
            self.open_thread_from_descriptor(self.current_thread_descriptor)

    def on_auto_refresh_changed(self) -> None:
        """
        Handle toggling of auto refresh.
        """
        enabled = self.auto_refresh_var.get()
        self.prefs["auto_refresh_enabled"] = bool(enabled)
        save_preferences(self.prefs)
        self.log(f"Auto refresh {'enabled' if enabled else 'disabled'}")
        if enabled:
            self.schedule_auto_refresh()
        else:
            if self._auto_refresh_job is not None:
                try:
                    self.after_cancel(self._auto_refresh_job)
                except Exception:
                    pass
                self._auto_refresh_job = None

    def on_refresh_interval_changed(self) -> None:
        """
        Update refresh interval preference.
        """
        interval = int(self.refresh_interval_var.get())
        self.prefs["auto_refresh_interval"] = interval
        save_preferences(self.prefs)
        self.log(f"Auto refresh interval set to {interval} seconds")

    def schedule_auto_refresh(self) -> None:
        """
        Schedule the next auto refresh tick.
        """
        if not self.auto_refresh_var.get():
            return
        interval = int(self.refresh_interval_var.get())
        if interval < 15:
            interval = 15
        if self._auto_refresh_job is not None:
            try:
                self.after_cancel(self._auto_refresh_job)
            except Exception:
                pass
        self._auto_refresh_job = self.after(interval * 1000, self._auto_refresh_tick)

    def _auto_refresh_tick(self) -> None:
        """
        Auto refresh callback.
        """
        self.refresh_current()
        self.schedule_auto_refresh()

    def on_site_changed(self, _event=None) -> None:
        """
        Handle switching between 4chan and Reddit.
        """
        self.current_site = self.site_var.get()
        self.prefs["site"] = self.current_site
        save_preferences(self.prefs)
        self.log(f"Site changed to {self.current_site}")
        self._update_site_frames()
        self.refresh_current()

    def _update_site_frames(self) -> None:
        """
        Hook reserved for future visual hints.
        """
        pass

    def load_initial_data(self) -> None:
        """
        Load boards and initial content.
        """
        self.load_4chan_boards()
        if self.current_site == "4chan":
            self.load_board_catalog()
        else:
            self.load_subreddit_posts()
        if self.prefs.get("auto_refresh_enabled", False):
            self.schedule_auto_refresh()

    # 4chan related methods

    def load_4chan_boards(self) -> None:
        """
        Fetch list of 4chan boards using the public JSON API,
        then build a board guide mapping.
        """

        def worker():
            self.log("Loading 4chan boards list...")
            url = "https://a.4cdn.org/boards.json"
            proxy = self.prefs.get("proxy") or None
            data = fetch_json(url, proxy_url=proxy)
            if data is None:
                self.log("Failed to load 4chan boards")
                return
            boards_raw = data.get("boards", [])
            boards = sorted([b["board"] for b in boards_raw if "board" in b])
            info_map: dict[str, dict] = {}
            for b in boards_raw:
                key = b.get("board")
                if not key:
                    continue
                info_map[key] = {
                    "title": html.unescape(b.get("title", "")),
                    "meta": html.unescape(b.get("meta_description", "")),
                }
            self.after(0, self._populate_4chan_boards, boards, info_map)

        threading.Thread(target=worker, daemon=True).start()

    def _populate_4chan_boards(
        self, boards: list[str], info_map: dict[str, dict]
    ) -> None:
        """
        Fill the board combobox and store the guide info.
        """
        self.boards_info = info_map or {}
        self.board_combo["values"] = boards
        if self.current_board in boards:
            self.board_var.set(self.current_board)
        elif boards:
            self.board_var.set(boards[0])
        self.update_board_info()

    def update_board_info(self) -> None:
        """
        Update the board guide text under the combobox.
        """
        board = self.board_var.get().strip()
        info = self.boards_info.get(board, {})
        title = info.get("title") or ""
        meta = info.get("meta") or ""
        if not board:
            text = ""
        else:
            header = f"/{board}/"
            if title:
                header += f"  {title}"
            text = header
            if meta:
                text += f"\n{meta}"
        self.board_info_label.config(text=text)

    def on_board_changed(self, _event=None) -> None:
        """
        When the selected board changes, update the guide text.
        """
        self.update_board_info()

    def on_board_arrow(self, event) -> str:
        """
        Handle Up and Down keys on the board combobox so that
        pressing the arrows cycles through boards and updates the guide.
        """
        values = list(self.board_combo["values"])
        if not values:
            return "break"
        current = self.board_var.get()
        try:
            idx = values.index(current)
        except ValueError:
            idx = 0
        if event.keysym == "Up":
            idx = (idx - 1) % len(values)
        elif event.keysym == "Down":
            idx = (idx + 1) % len(values)
        self.board_var.set(values[idx])
        self.update_board_info()
        # prevent default handling so we stay in control of cycling
        return "break"

    def on_board_enter(self, _event=None) -> str:
        """
        Pressing Enter on the board selector loads the selected board.
        """
        self.load_board_catalog()
        return "break"

    def on_board_tab(self, _event=None) -> str:
        """
        Pressing Tab on the board selector moves focus to the thread list.
        """
        if self.thread_list.size() > 0:
            # Ensure something is selected when we jump over
            if not self.thread_list.curselection():
                self.thread_list.selection_set(0)
                self.thread_list.activate(0)
                self.on_thread_selected()
        self.thread_list.focus_set()
        return "break"

    def load_board_catalog(self) -> None:
        """
        Load the catalog for the current board and populate the thread list.
        """
        board = self.board_var.get().strip()
        if not board:
            return
        self.current_board = board
        self.prefs["current_board"] = board
        save_preferences(self.prefs)

        def worker():
            self.log(f"Loading catalog for /{board}/...")
            url = f"https://a.4cdn.org/{board}/catalog.json"
            proxy = self.prefs.get("proxy") or None
            data = fetch_json(url, proxy_url=proxy)
            if data is None:
                self.log("Failed to load board catalog")
                return
            threads = []
            for page in data:
                for th in page.get("threads", []):
                    threads.append(th)
            self.after(0, self._populate_thread_list_4chan, threads)

        threading.Thread(target=worker, daemon=True).start()

    def _populate_thread_list_4chan(self, threads: list[dict]) -> None:
        """
        Show 4chan threads in the listbox.
        """
        self.thread_list.delete(0, tk.END)
        self.thread_index: list[dict] = []
        for th in threads:
            no = th.get("no")
            sub = th.get("sub") or ""
            com = th.get("com") or ""
            subject = sub if sub else strip_html(com).split("\n", 1)[0][:80]
            replies = th.get("replies", 0)
            display = f"[{replies:3d}r] {subject}"
            self.thread_list.insert(tk.END, display)
            descriptor = {
                "site": "4chan",
                "board": self.current_board,
                "thread_no": no,
                "title": subject,
            }
            self.thread_index.append(descriptor)
        # Select the first thread by default
        if self.thread_index:
            self.thread_list.selection_clear(0, tk.END)
            self.thread_list.selection_set(0)
            self.thread_list.activate(0)
            self.on_thread_selected()
        self.log(f"Loaded {len(threads)} threads for /{self.current_board}/")

    def on_thread_selected(self, _event=None) -> None:
        """
        Open the thread corresponding to the selected listbox item.
        """
        selection = self.thread_list.curselection()
        if not selection:
            return
        idx = selection[0]
        if not hasattr(self, "thread_index"):
            return
        if idx >= len(self.thread_index):
            return
        descriptor = self.thread_index[idx]
        self.open_thread_from_descriptor(descriptor)

    def on_thread_enter(self, _event=None) -> str:
        """
        Pressing Enter on the thread list loads the selected thread.
        """
        self.on_thread_selected()
        return "break"

    def on_threads_tab(self, _event=None) -> str:
        """
        Pressing Tab on the thread list moves focus back to the board selector.
        """
        self.board_combo.focus_set()
        return "break"

    def open_thread_from_descriptor(self, descriptor: dict) -> None:
        """
        Open a thread from a descriptor dict, supporting both sites.
        """
        self.current_thread_descriptor = descriptor
        site = descriptor.get("site")
        if site == "4chan":
            self._open_4chan_thread(descriptor)
        elif site == "Reddit" or site == "reddit":
            self._open_reddit_thread(descriptor)

        # Update recent list
        self._add_to_recent(descriptor)

    def _open_4chan_thread(self, descriptor: dict) -> None:
        """
        Fetch and display a 4chan thread.
        """
        board = descriptor.get("board")
        thread_no = descriptor.get("thread_no")
        if not board or not thread_no:
            return

        def worker():
            self.log(f"Loading thread {thread_no} on /{board}/...")
            url = f"https://a.4cdn.org/{board}/thread/{thread_no}.json"
            proxy = self.prefs.get("proxy") or None
            data = fetch_json(url, proxy_url=proxy)
            if data is None:
                self.log("Failed to load thread")
                return
            posts = data.get("posts", [])
            self.after(0, self._display_4chan_thread, posts)

        threading.Thread(target=worker, daemon=True).start()

    def _display_4chan_thread(self, posts: list[dict]) -> None:
        """
        Display a 4chan thread in clean reader format: username and message only.
        """
        self.reader_text.configure(state="normal")
        self.reader_text.delete("1.0", tk.END)

        keyword_filter = [w.lower() for w in self.prefs.get("keyword_filter", [])]
        id_filter = [s.strip() for s in self.prefs.get("poster_filter_4chan", [])]

        for post in posts:
            name = post.get("name") or "Anonymous"
            pid = post.get("id") or ""
            com = post.get("com") or ""
            text = strip_html(com)

            ltext = text.lower()
            if keyword_filter and any(k in ltext for k in keyword_filter):
                continue
            if id_filter and pid and pid in id_filter:
                continue

            # Username and message only
            header = f"{name}"
            if pid:
                header += f" (ID: {pid})"
            header_line = header + "\n"
            body = text.strip() + "\n\n"

            self.reader_text.insert(tk.END, header_line, ("username",))
            self.reader_text.insert(tk.END, body)

            # Images are represented as placeholders or links depending on mode
            if "filename" in post or "tim" in post:
                mode = self.sfw_var.get()
                if mode == "hide":
                    pass
                elif mode == "blur":
                    self.reader_text.insert(
                        tk.END, "[image blurred]\n\n", ("image_placeholder",)
                    )
                else:
                    # Show a clickable link to open image in browser
                    board = self.current_board
                    tim = post.get("tim")
                    ext = post.get("ext", "")
                    if tim and ext:
                        url = f"https://i.4cdn.org/{board}/{tim}{ext}"
                        start = self.reader_text.index(tk.END)
                        self.reader_text.insert(
                            tk.END, "[open image]\n\n", ("image_link",)
                        )
                        end = self.reader_text.index(tk.END)
                        self.reader_text.tag_add(url, start, end)
                        self.reader_text.tag_bind(
                            url,
                            "<Button-1>",
                            lambda e, link=url: webbrowser.open(link),
                        )

        self.reader_text.tag_config(
            "username",
            foreground="#8ab4f8",
            font=("Segoe UI", int(self.prefs.get("font_size", 11)), "bold"),
        )
        self.reader_text.tag_config("image_placeholder", foreground="#aaaaaa")
        self.reader_text.tag_config("image_link", underline=True)
        self.reader_text.configure(state="disabled")
        self.reader_text.see("1.0")

    # Reddit methods

    def load_subreddit_posts(self) -> None:
        """
        Load posts from the selected subreddit.
        """
        sub = self.subreddit_var.get().strip()
        if not sub:
            return
        self.current_subreddit = sub
        self.prefs["current_subreddit"] = sub
        save_preferences(self.prefs)
        sort = self.subreddit_sort_var.get()

        def worker():
            self.log(f"Loading r/{sub} ({sort})...")
            url = f"https://www.reddit.com/r/{parse.quote(sub)}/{sort}.json?limit=50"
            proxy = self.prefs.get("proxy") or None
            data = fetch_json(url, proxy_url=proxy)
            if data is None:
                self.log("Failed to load subreddit posts")
                return
            try:
                children = data["data"]["children"]
            except Exception:
                self.log("Unexpected Reddit response structure")
                return
            posts = [c["data"] for c in children if "data" in c]
            self.after(0, self._populate_thread_list_reddit, posts)

        threading.Thread(target=worker, daemon=True).start()

    def _populate_thread_list_reddit(self, posts: list[dict]) -> None:
        """
        Show subreddit posts in the thread listbox.
        """
        self.thread_list.delete(0, tk.END)
        self.thread_index: list[dict] = []
        for p in posts:
            title = p.get("title") or ""
            author = p.get("author") or "unknown"
            num_comments = p.get("num_comments", 0)
            post_id = p.get("id")
            display = f"[{num_comments:3d}c] {title} (u/{author})"
            self.thread_list.insert(tk.END, display)
            descriptor = {
                "site": "Reddit",
                "subreddit": self.current_subreddit,
                "id": post_id,
                "title": title,
            }
            self.thread_index.append(descriptor)
        if self.thread_index:
            self.thread_list.selection_clear(0, tk.END)
            self.thread_list.selection_set(0)
            self.thread_list.activate(0)
            self.on_thread_selected()
        self.log(f"Loaded {len(posts)} posts for r/{self.current_subreddit}")

    def _open_reddit_thread(self, descriptor: dict) -> None:
        """
        Fetch and display a Reddit thread.
        """
        sub = descriptor.get("subreddit")
        post_id = descriptor.get("id")
        if not sub or not post_id:
            return

        def worker():
            self.log(f"Loading Reddit thread {post_id} in r/{sub}...")
            url = f"https://www.reddit.com/r/{parse.quote(sub)}/comments/{post_id}.json?limit=100&depth=1&sort=top"
            proxy = self.prefs.get("proxy") or None
            data = fetch_json(url, proxy_url=proxy)
            if not data or not isinstance(data, list):
                self.log("Failed to load Reddit comments")
                return
            try:
                post_data = data[0]["data"]["children"][0]["data"]
                comments = data[1]["data"]["children"]
            except Exception:
                self.log("Unexpected Reddit comments structure")
                return

            flat_comments = []
            for c in comments:
                kind = c.get("kind")
                cdata = c.get("data", {})
                if kind != "t1":
                    continue
                body = cdata.get("body")
                author = cdata.get("author") or "unknown"
                if body:
                    flat_comments.append({"author": author, "body": body})
            self.after(0, self._display_reddit_thread, post_data, flat_comments)

        threading.Thread(target=worker, daemon=True).start()

    def _display_reddit_thread(self, post_data: dict, comments: list[dict]) -> None:
        """
        Display Reddit submission and top level comments in clean reader format.
        """
        self.reader_text.configure(state="normal")
        self.reader_text.delete("1.0", tk.END)

        keyword_filter = [w.lower() for w in self.prefs.get("keyword_filter", [])]
        author_filter = [s.strip() for s in self.prefs.get("author_filter_reddit", [])]

        title = post_data.get("title") or ""
        author = post_data.get("author") or "unknown"
        self.reader_text.insert(tk.END, f"{title}\n", ("thread_title",))
        self.reader_text.insert(tk.END, f"by u/{author}\n\n", ("username",))

        self.reader_text.tag_config(
            "thread_title",
            foreground="#ffffff",
            font=("Segoe UI", int(self.prefs.get("font_size", 11)) + 2, "bold"),
        )

        for c in comments:
            body = c.get("body", "")
            author = c.get("author", "unknown")
            lbody = body.lower()
            if keyword_filter and any(k in lbody for k in keyword_filter):
                continue
            if author_filter and author in author_filter:
                continue
            header = f"u/{author}\n"
            self.reader_text.insert(tk.END, header, ("username",))
            self.reader_text.insert(tk.END, body.strip() + "\n\n")

        self.reader_text.tag_config(
            "username",
            foreground="#8ab4f8",
            font=("Segoe UI", int(self.prefs.get("font_size", 11)), "bold"),
        )
        self.reader_text.configure(state="disabled")
        self.reader_text.see("1.0")

    # Bookmarks and recent

    def _add_to_recent(self, descriptor: dict) -> None:
        """
        Maintain a simple recent threads list in prefs.
        """
        recent = self.prefs.get("recent", [])
        key = self._descriptor_key(descriptor)
        recent = [d for d in recent if self._descriptor_key(d) != key]
        recent.insert(0, descriptor)
        recent = recent[:50]
        self.prefs["recent"] = recent
        save_preferences(self.prefs)

    def add_current_bookmark(self) -> None:
        """
        Bookmark the currently open thread.
        """
        if not self.current_thread_descriptor:
            self.log("No thread open to bookmark")
            return
        bookmarks = self.prefs.get("bookmarks", [])
        key = self._descriptor_key(self.current_thread_descriptor)
        if any(self._descriptor_key(bm) == key for bm in bookmarks):
            self.log("Thread already bookmarked")
            return
        bookmarks.append(self.current_thread_descriptor)
        self.prefs["bookmarks"] = bookmarks
        save_preferences(self.prefs)
        self._refresh_bookmarks_view()
        self.log("Bookmark added")

    def delete_selected_bookmark(self) -> None:
        """
        Delete the currently selected bookmark.
        """
        selection = self.bookmarks_list.curselection()
        if not selection:
            return
        idx = selection[0]
        bookmarks = self.prefs.get("bookmarks", [])
        if idx >= len(bookmarks):
            return
        bm = bookmarks.pop(idx)
        self.prefs["bookmarks"] = bookmarks
        save_preferences(self.prefs)
        self._refresh_bookmarks_view()
        self.log(f"Deleted bookmark: {bm.get('title', '')}")

    def _descriptor_key(self, d: dict) -> str:
        """
        Generate a unique key for a thread descriptor.
        """
        site = d.get("site")
        if site == "4chan":
            return f"4chan:{d.get('board')}:{d.get('thread_no')}"
        if site == "Reddit":
            return f"Reddit:{d.get('subreddit')}:{d.get('id')}"
        return repr(d)

    def _refresh_bookmarks_view(self) -> None:
        """
        Refresh the bookmarks listbox from prefs.
        """
        self.bookmarks_list.delete(0, tk.END)
        bookmarks = self.prefs.get("bookmarks", [])
        for bm in bookmarks:
            site = bm.get("site")
            if site == "4chan":
                label = f"/{bm.get('board')}/ - {bm.get('title', '')}"
            else:
                label = f"r/{bm.get('subreddit')}/ - {bm.get('title', '')}"
            self.bookmarks_list.insert(tk.END, label)

    def on_bookmark_activated(self, _event=None) -> None:
        """
        Open a bookmark on double click.
        """
        selection = self.bookmarks_list.curselection()
        if not selection:
            return
        idx = selection[0]
        bookmarks = self.prefs.get("bookmarks", [])
        if idx >= len(bookmarks):
            return
        descriptor = bookmarks[idx]
        self.open_thread_from_descriptor(descriptor)

    # Search within thread

    def search_in_thread(self) -> None:
        """
        Highlight all matches for the search term in the current thread.
        """
        term = self.search_var.get().strip()
        if not term:
            return
        self.reader_text.tag_remove("search_hit", "1.0", tk.END)
        if self.reader_text.compare("end-1c", "==", "1.0"):
            return
        idx = "1.0"
        first_hit = None
        while True:
            idx = self.reader_text.search(term, idx, nocase=1, stopindex=tk.END)
            if not idx:
                break
            end = f"{idx}+{len(term)}c"
            self.reader_text.tag_add("search_hit", idx, end)
            if first_hit is None:
                first_hit = idx
            idx = end
        if first_hit:
            self.reader_text.see(first_hit)
            self.reader_text.tag_config("search_hit", background="#555555")
            self.log(f"Search completed for '{term}'")
        else:
            self.log(f"No matches found for '{term}'")

    # 4chan Google search helper

    def open_4chan_google_search(self) -> None:
        """
        Open a Google search restricted to 4chan in the default browser.
        """
        query = self.chan_search_var.get().strip()
        if not query:
            return
        q = f"site:4chan.org {query}"
        url = "https://www.google.com/search?q=" + parse.quote_plus(q)
        webbrowser.open(url)
        self.log(f"Opened browser search for: {q}")

    def refresh_current(self) -> None:
        """
        Refresh the current context (list or thread) for the chosen site.
        """
        if self.current_site == "4chan":
            if (
                self.current_thread_descriptor
                and self.current_thread_descriptor.get("site") == "4chan"
            ):
                self._open_4chan_thread(self.current_thread_descriptor)
            else:
                self.load_board_catalog()
        else:
            if (
                self.current_thread_descriptor
                and self.current_thread_descriptor.get("site") == "Reddit"
            ):
                self._open_reddit_thread(self.current_thread_descriptor)
            else:
                self.load_subreddit_posts()

    def run(self) -> None:
        """
        Start the Tkinter main loop.
        """
        self.log("Application started")
        self.mainloop()


def main() -> None:
    app = ReaderApp()
    app.run()


if __name__ == "__main__":
    main()
