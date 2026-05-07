import os, re, csv, json, sqlite3, sys
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import tkinter.font as tkfont

APP_NAME = "Prompt Vault"
DB_FILENAME = "prompt_vault.db"
CONFIG_FILENAME = "prompt_vault_config.json"


def get_app_dir():
    base = Path.home() / ".prompt_vault"
    base.mkdir(exist_ok=True)
    return base


APP_DIR = get_app_dir()
DB_PATH = APP_DIR / DB_FILENAME
CONFIG_PATH = APP_DIR / CONFIG_FILENAME


# Minimize the Windows console at startup, safe no-op elsewhere

def minimize_console_window():
    if os.name != "nt":
        return
    try:
        import ctypes

        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
    except Exception:
        pass


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    category TEXT DEFAULT '',
    favorite INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_prompts_title ON prompts(title);
CREATE INDEX IF NOT EXISTS idx_prompts_category ON prompts(category);
CREATE INDEX IF NOT EXISTS idx_prompts_fav ON prompts(favorite);

-- New table that stores the Text.dump payload for formatting
CREATE TABLE IF NOT EXISTS prompt_formats (
    prompt_id INTEGER PRIMARY KEY,
    payload TEXT NOT NULL,
    FOREIGN KEY(prompt_id) REFERENCES prompts(id) ON DELETE CASCADE
);
"""

# Optional spellcheck
try:
    import enchant

    _ENCHANT_OK = True
except Exception:
    _ENCHANT_OK = False


class PromptVaultDB:
    def __init__(self, path):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        # Ensure foreign keys work for prompt_formats
        try:
            self.conn.execute("PRAGMA foreign_keys = ON")
        except Exception:
            pass
        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.executescript(SCHEMA_SQL)

    def list_categories(self):
        cur = self.conn.cursor()
        cur.execute("SELECT DISTINCT category FROM prompts ORDER BY category")
        return [r[0] for r in cur.fetchall() if r[0]]

    def search_prompts(self, text="", category=None, favorites_only=False):
        sql = "SELECT id, title, category, favorite, updated_at FROM prompts WHERE 1=1"
        params = []
        if text:
            sql += " AND (title LIKE ? OR content LIKE ? OR category LIKE ?)"
            q = f"%{text}%"
            params += [q, q, q]
        if category and category.strip():
            sql += " AND category = ?"
            params.append(category.strip())
        if favorites_only:
            sql += " AND favorite = 1"
        sql += " ORDER BY favorite DESC, updated_at DESC"
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()

    def get_prompt(self, pid):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM prompts WHERE id = ?", (pid,))
        return cur.fetchone()

    def create_prompt(self, title, content, category="", favorite=False):
        now = datetime.now().isoformat(timespec="seconds")
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO prompts(title, content, category, favorite, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (title, content, category, 1 if favorite else 0, now, now),
            )
            return cur.lastrowid

    def update_prompt(self, pid, title, content, category="", favorite=False):
        now = datetime.now().isoformat(timespec="seconds")
        with self.conn:
            self.conn.execute(
                "UPDATE prompts SET title = ?, content = ?, category = ?, favorite = ?, updated_at = ? WHERE id = ?",
                (title, content, category, 1 if favorite else 0, now, pid),
            )

    def delete_prompt(self, pid):
        with self.conn:
            self.conn.execute("DELETE FROM prompts WHERE id = ?", (pid,))

    def export_csv(self, filepath):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT id, title, content, category, favorite, created_at, updated_at FROM prompts ORDER BY id"
        )
        rows = cur.fetchall()
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["id", "title", "content", "category", "favorite", "created_at", "updated_at"]
            )
            for r in rows:
                writer.writerow(
                    [
                        r["id"],
                        r["title"],
                        r["content"],
                        r["category"],
                        r["favorite"],
                        r["created_at"],
                        r["updated_at"],
                    ]
                )

    def import_csv(self, filepath):
        count = 0
        with open(filepath, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                title = row.get("title", "").strip()
                content = row.get("content", "")
                category = row.get("category", "").strip()
                favorite = int(row.get("favorite", 0)) == 1
                if title and content:
                    self.create_prompt(title, content, category, favorite)
                    count += 1
        return count

    # Formatting payload helpers
    def get_format_payload(self, pid: int):
        cur = self.conn.cursor()
        cur.execute("SELECT payload FROM prompt_formats WHERE prompt_id = ?", (pid,))
        r = cur.fetchone()
        return r["payload"] if r else None

    def upsert_format_payload(self, pid: int, payload: str):
        with self.conn:
            self.conn.execute(
                "INSERT INTO prompt_formats(prompt_id, payload) VALUES (?, ?) "
                "ON CONFLICT(prompt_id) DO UPDATE SET payload = excluded.payload",
                (pid, payload),
            )


class App(ttk.Frame):
    DEFAULT_KEYMAP = {
        "new": "<Control-n>",
        "save": "<Control-s>",
        "duplicate": "<Control-d>",
        "delete": "",
        "find": "<Control-f>",
        "bold": "<Control-b>",
        "italic": "<Control-i>",
        "underline": "<Control-u>",
        "strike": "<Alt-Shift-5>",
        "clearfmt": "<Control-0>",
        "bullets": "<Control-period>",
        "numbers": "<Control-slash>",
        "case_upper": "<Control-Shift-u>",
        "case_lower": "<Control-Shift-l>",
        "case_title": "<Control-Shift-t>",
        "case_sentence": "<Control-Shift-s>",
        "clear_msel": "<Escape>",
    }

    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.db = PromptVaultDB(DB_PATH)
        self.current_id = None
        self.dirty = False
        self._load_config()
        self.user_dict = set(self.config.get("user_dictionary", []))
        self.ignored_words = set()
        self._build_ui()
        self._bind_shortcuts()
        self._refresh_list()
        self._maybe_seed()

    def _load_config(self):
        self.config = {
            "geometry": "1100x700",
            "paned": 350,
            "favorites_only": False,
            "content_font_family": None,
            "content_font_size": None,
            "keymap": {},
        }
        if CONFIG_PATH.exists():
            try:
                self.config.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
            except Exception:
                pass

    def _save_config(self):
        try:
            self.config["geometry"] = self.master.winfo_geometry()
            self.config["paned"] = self.paned.sashpos(0)
            self.config["user_dictionary"] = sorted(self.user_dict)
            CONFIG_PATH.write_text(json.dumps(self.config, indent=2), encoding="utf-8")
        except Exception:
            pass

    # ---------- Fonts and tags ----------
    def _init_content_font(self):
        base = tkfont.nametofont("TkDefaultFont")
        fam = self.config.get("content_font_family") or base.cget("family")
        try:
            size = int(self.config.get("content_font_size") or base.cget("size"))
        except Exception:
            size = 10
        self.content_font = tkfont.Font(family=fam, size=size)

    def _compose_fonts(self):
        fam = self.content_font.cget("family")
        size = int(self.content_font.cget("size"))
        self._font_norm = tkfont.Font(family=fam, size=size)
        self._font_b = tkfont.Font(family=fam, size=size, weight="bold")
        self._font_i = tkfont.Font(family=fam, size=size, slant="italic")
        self._font_bi = tkfont.Font(family=fam, size=size, weight="bold", slant="italic")

    def _apply_content_font(self):
        rh = int(max(int(self.content_font.cget("size")) * 1.6, 22))
        self.style.configure("Treeview", font=self.content_font, rowheight=rh)
        if hasattr(self, "text"):
            self.text.configure(font=self.content_font)
            self._compose_fonts()
            self.text.tag_configure("font_b", font=self._font_b)
            self.text.tag_configure("font_i", font=self._font_i)
            self.text.tag_configure("font_bi", font=self._font_bi)
            self.text.tag_configure("underline", underline=1)
            self.text.tag_configure("strike", overstrike=1)
            self.text.tag_configure("misspell", underline=1, foreground="#c00000")
            self.text.tag_configure("msel", background="#e6f2ff")

    # ---------- UI ----------
    def _build_ui(self):
        self.master.title(APP_NAME)
        self.master.geometry(self.config.get("geometry", "1100x700"))
        self.master.minsize(950, 560)

        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass
        self.style.configure("TButton", padding=6)
        self.style.configure("Accent.TButton", padding=8)
        self.style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"))
        self.style.configure("Small.TLabel", font=("Segoe UI", 9))

        menubar = tk.Menu(self.master)
        self.master.config(menu=menubar)

        # Edit menu
        self.edit_menu = tk.Menu(menubar, tearoff=0)
        self._edit_add_cmd("Bold", self._toggle_bold, "bold")
        self._edit_add_cmd("Italic", self._toggle_italic, "italic")
        self._edit_add_cmd("Underline", self._toggle_underline, "underline")
        self._edit_add_cmd("Strikethrough", self._toggle_strike, "strike")
        self.edit_menu.add_separator()
        self._edit_add_cmd("Clear formatting", self._clear_all_formatting, "clearfmt")
        self.edit_menu.add_separator()
        self._edit_add_cmd("Bulleted list toggle", self._toggle_bullets, "bullets")
        self._edit_add_cmd("Numbered list toggle", self._toggle_numbers, "numbers")
        self.edit_menu.add_separator()
        self._edit_add_cmd("UPPERCASE", lambda: self._convert_case("upper"), "case_upper")
        self._edit_add_cmd("lowercase", lambda: self._convert_case("lower"), "case_lower")
        self._edit_add_cmd("Title Case", lambda: self._convert_case("title"), "case_title")
        self._edit_add_cmd("Sentence case", lambda: self._convert_case("sentence"), "case_sentence")
        self.edit_menu.add_separator()
        self.edit_menu.add_command(label="Keyboard Shortcuts...", command=self._open_shortcuts_dialog)
        menubar.add_cascade(label="Edit", menu=self.edit_menu)

        # View menu
        view = tk.Menu(menubar, tearoff=0)
        view.add_command(label="Increase content font", command=self._content_font_increase)
        view.add_command(label="Decrease content font", command=self._content_font_decrease)
        view.add_command(label="Reset content font", command=self._content_font_reset)
        view.add_separator()
        view.add_command(label="Choose content font family...", command=self._content_font_choose_family)
        view.add_command(label="Use Aptos for content", command=self._content_use_aptos)
        menubar.add_cascade(label="View", menu=view)

        self._init_content_font()

        self.paned = ttk.Panedwindow(self.master, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True)

        # Left
        left = ttk.Frame(self.paned, padding=8)
        self.paned.add(left, weight=1)
        ttk.Label(left, text="Library", style="Header.TLabel").pack(anchor="w")
        topbar = ttk.Frame(left)
        topbar.pack(fill=tk.X, pady=(6, 8))
        self.search_var = tk.StringVar()
        search = ttk.Entry(topbar, textvariable=self.search_var)
        search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        search.insert(0, "Search title, content, or category")
        search.bind("<FocusIn>", lambda e: self._clear_placeholder(search))
        self.category_var = tk.StringVar(value="All categories")
        self.category_combo = ttk.Combobox(
            topbar, textvariable=self.category_var, state="readonly", width=20
        )
        self.category_combo.pack(side=tk.LEFT, padx=6)
        self.category_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_list())
        self.fav_only = tk.BooleanVar(value=self.config.get("favorites_only", False))
        ttk.Checkbutton(topbar, text="Favorites", variable=self.fav_only, command=self._refresh_list).pack(
            side=tk.LEFT
        )

        columns = ("title", "category", "updated")
        self.tree = ttk.Treeview(left, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("title", text="Title")
        self.tree.heading("category", text="Category")
        self.tree.heading("updated", text="Updated")
        self.tree.column("title", width=260, anchor="w")
        self.tree.column("category", width=140, anchor="w")
        self.tree.column("updated", width=120, anchor="center")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._on_select())
        self.tree.bind("<Double-1>", lambda e: self._on_copy())

        # Right
        right = ttk.Frame(self.paned, padding=8)
        self.paned.add(right, weight=3)
        try:
            self.paned.sashpos(0, int(self.config.get("paned", 350)))
        except Exception:
            pass

        ttk.Label(right, text="Editor", style="Header.TLabel").pack(anchor="w")
        form = ttk.Frame(right)
        form.pack(fill=tk.X, pady=(6, 4))
        ttk.Label(form, text="Title").grid(row=0, column=0, sticky="w")
        self.title_var = tk.StringVar()
        self.title_entry = ttk.Entry(form, textvariable=self.title_var)
        self.title_entry.grid(row=1, column=0, sticky="we", padx=(0, 8))
        ttk.Label(form, text="Category").grid(row=0, column=1, sticky="w")
        self.category_edit_var = tk.StringVar()
        self.category_entry = ttk.Entry(form, textvariable=self.category_edit_var, width=24)
        self.category_entry.grid(row=1, column=1, sticky="we", padx=(0, 8))
        self.category_picker = ttk.Combobox(form, state="readonly", width=18)
        self.category_picker.grid(row=1, column=3, sticky="we", padx=(0, 8))
        self.category_picker.bind(
            "<<ComboboxSelected>>", lambda e: self.category_edit_var.set(self.category_picker.get())
        )
        self.fav_var = tk.BooleanVar()
        ttk.Checkbutton(form, text="Favorite", variable=self.fav_var).grid(row=1, column=2, sticky="w")
        form.columnconfigure(0, weight=3)
        form.columnconfigure(1, weight=2)
        form.columnconfigure(3, weight=1)

        # Formatting toolbar
        fmtbar = ttk.Frame(right)
        fmtbar.pack(fill=tk.X, pady=(2, 2))
        self._mk_btn(fmtbar, "Bold", "bold")
        self._mk_btn(fmtbar, "Italic", "italic")
        self._mk_btn(fmtbar, "Underline", "underline")
        self._mk_btn(fmtbar, "Strikethrough", "strike")
        ttk.Separator(fmtbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)
        self._mk_btn(fmtbar, "Bullets", "bullets")
        self._mk_btn(fmtbar, "Numbers", "numbers")
        ttk.Separator(fmtbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)
        self._mk_btn(fmtbar, "UPPER", "case_upper")
        self._mk_btn(fmtbar, "lower", "case_lower")
        self._mk_btn(fmtbar, "Title", "case_title")
        self._mk_btn(fmtbar, "Sentence", "case_sentence")
        ttk.Separator(fmtbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)
        ttk.Button(fmtbar, text="Clear select", command=self._clear_multi_select).pack(side=tk.LEFT)

        # Text
        self.text = tk.Text(right, wrap="word", height=20, undo=True)
        self.text.pack(fill=tk.BOTH, expand=True, pady=(6, 6))
        self.text.bind("<<Modified>>", self._on_modified)

        # Compose fonts and tags
        self._apply_content_font()

        # Actions
        actions = ttk.Frame(right)
        actions.pack(fill=tk.X)
        ttk.Button(actions, text="New", command=self._on_new).pack(side=tk.LEFT)
        ttk.Button(actions, text="Save", style="Accent.TButton", command=self._on_save).pack(
            side=tk.LEFT, padx=6
        )
        ttk.Button(actions, text="Duplicate", command=self._on_duplicate).pack(side=tk.LEFT)
        ttk.Button(actions, text="Delete", command=self._on_delete).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Separator(actions, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Button(actions, text="Copy", command=self._on_copy).pack(side=tk.LEFT)
        ttk.Button(actions, text="Copy with variables", command=self._on_copy_with_vars).pack(
            side=tk.LEFT, padx=6
        )
        ttk.Button(actions, text="Copy as Markdown code block", command=self._on_copy_md).pack(side=tk.LEFT)
        ttk.Separator(actions, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Button(actions, text="Export CSV", command=self._on_export).pack(side=tk.LEFT)
        ttk.Button(actions, text="Import CSV", command=self._on_import).pack(side=tk.LEFT, padx=6)

        # Status
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.master, textvariable=self.status_var, anchor="w", style="Small.TLabel").pack(
            fill=tk.X, side=tk.BOTTOM
        )

        # Context menus
        self.menu = tk.Menu(self.master, tearoff=0)
        self.menu.add_command(label="Copy", command=self._on_copy)
        self.menu.add_command(label="Duplicate", command=self._on_duplicate)
        self.menu.add_separator()
        self.menu.add_command(label="Delete", command=self._on_delete)
        self.tree.bind("<Button-3>", self._on_right_click)

        self.editor_menu = tk.Menu(self.master, tearoff=0)
        self.editor_menu.add_command(label="Cut", command=lambda: self.master.focus_get().event_generate("<<Cut>>"))
        self.editor_menu.add_command(
            label="Copy", command=lambda: self.master.focus_get().event_generate("<<Copy>>")
        )
        self.editor_menu.add_command(
            label="Paste", command=lambda: self.master.focus_get().event_generate("<<Paste>>")
        )
        self.editor_menu.add_separator()
        self.editor_menu.add_command(label="Add to dictionary", command=self._spell_add_to_dict)
        self.editor_menu.add_command(label="Ignore word", command=self._spell_ignore_word)
        self.text.bind("<Button-3>", self._on_text_right_click)

        # Spellcheck bindings
        if _ENCHANT_OK:
            self.spell_dict = enchant.Dict("en_US")
            for ch in (
                "space",
                "Return",
                "period",
                "comma",
                "exclam",
                "question",
                "colon",
                "semicolon",
                "slash",
            ):
                self.text.bind(f"<KeyRelease-{ch}>", self._spell_check_last_word)
        else:
            self.spell_dict = None
            self.status_var.set("Spellcheck disabled, install pyenchant to enable")

        # Multi-select bindings
        self._msel_anchor = None
        self.text.bind("<Control-Button-1>", self._msel_start)
        self.text.bind("<Control-B1-Motion>", self._msel_drag)
        self.text.bind("<Button-1>", self._click_normal)  # clear msel on normal click

    def _mk_btn(self, parent, label, action_key):
        ttk.Button(
            parent, text=f"{label} {self._label_hotkey(action_key)}", command=lambda k=action_key: self._invoke_action(k)
        ).pack(side=tk.LEFT, padx=(0, 4))

    def _label_hotkey(self, key):
        km = self._get_keymap()
        seq = km.get(key, "")
        if not seq:
            return ""
        pretty = seq.strip("<>").replace("Control", "Ctrl").replace("-", "+")
        return f"({pretty})"

    def _edit_add_cmd(self, text, cmd, key):
        self.edit_menu.add_command(label=f"{text}", command=cmd, accelerator=self._accel_text(key))

    def _accel_text(self, key):
        km = self._get_keymap()
        seq = km.get(key, "")
        return seq.strip("<>").replace("Control", "Ctrl").replace("-", "+")

    # ---------- Shortcuts ----------
    def _get_keymap(self):
        km = dict(self.DEFAULT_KEYMAP)
        km.update(self.config.get("keymap", {}))
        return km

    def _bind_shortcuts(self):
        km = self._get_keymap()
        for seq in getattr(self, "_bound_seqs", []):
            try:
                self.master.unbind(seq)
            except Exception:
                pass
        self._bound_seqs = []

        def bind(seq, func):
            if not seq:
                return
            self.master.bind(seq, lambda e: func() or "break")
            self._bound_seqs.append(seq)

        bind(km["new"], self._on_new)
        bind(km["save"], self._on_save)
        bind(km["duplicate"], self._on_duplicate)
        bind(km["delete"], self._on_delete)
        bind(km["find"], self._focus_search)
        bind(km["bold"], self._toggle_bold)
        bind(km["italic"], self._toggle_italic)
        bind(km["underline"], self._toggle_underline)
        bind(km["strike"], self._toggle_strike)
        bind(km["clearfmt"], self._clear_all_formatting)
        bind(km["bullets"], self._toggle_bullets)
        bind(km["numbers"], self._toggle_numbers)
        bind(km["case_upper"], lambda: self._convert_case("upper"))
        bind(km["case_lower"], lambda: self._convert_case("lower"))
        bind(km["case_title"], lambda: self._convert_case("title"))
        bind(km["case_sentence"], lambda: self._convert_case("sentence"))
        bind(km["clear_msel"], self._clear_multi_select)
        self.master.protocol("WM_DELETE_WINDOW", self._on_close)

    def _open_shortcuts_dialog(self):
        km = self._get_keymap()
        dlg = tk.Toplevel(self.master)
        dlg.title("Keyboard Shortcuts")
        dlg.geometry("520x420")
        dlg.transient(self.master)
        cols = ("Action", "Shortcut")
        tv = ttk.Treeview(dlg, columns=cols, show="headings", selectmode="browse")
        tv.heading("Action", text="Action")
        tv.heading("Shortcut", text="Shortcut")
        tv.column("Action", width=260)
        tv.column("Shortcut", width=180, anchor="center")
        tv.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        actions = [
            ("New", "new"),
            ("Save", "save"),
            ("Duplicate", "duplicate"),
            ("Delete", "delete"),
            ("Find", "find"),
            ("Bold", "bold"),
            ("Italic", "italic"),
            ("Underline", "underline"),
            ("Strikethrough", "strike"),
            ("Clear formatting", "clearfmt"),
            ("Bulleted list toggle", "bullets"),
            ("Numbered list toggle", "numbers"),
            ("UPPERCASE", "case_upper"),
            ("lowercase", "case_lower"),
            ("Title Case", "case_title"),
            ("Sentence case", "case_sentence"),
            ("Clear multi-select", "clear_msel"),
        ]

        def refresh():
            for i in tv.get_children():
                tv.delete(i)
            for name, key in actions:
                seq = km.get(key, "")
                tv.insert(
                    "",
                    "end",
                    iid=key,
                    values=(name, seq.strip("<>").replace("Control", "Ctrl").replace("-", "+")),
                )

        def on_change():
            sel = tv.selection()
            if not sel:
                return
            key = sel[0]
            current = km.get(key, "")
            prompt = "Enter new shortcut, example: Ctrl+Shift+S, Alt+/, Ctrl+."
            val = simpledialog.askstring("Change Shortcut", f"{prompt}\nCurrent: {current}", parent=dlg)
            if not val:
                return
            seq = self._parse_user_shortcut(val)
            if not seq:
                messagebox.showerror("Shortcut", "Could not parse shortcut, try format like: Ctrl+Shift+B")
                return
            userkm = self.config.get("keymap", {})
            userkm[key] = seq
            self.config["keymap"] = userkm
            self._bind_shortcuts()
            self._rebuild_edit_menu_labels()
            refresh()

        def on_reset():
            self.config["keymap"] = {}
            self._bind_shortcuts()
            self._rebuild_edit_menu_labels()
            refresh()

        btns = ttk.Frame(dlg)
        btns.pack(fill=tk.X, padx=8, pady=(0, 8))
        ttk.Button(btns, text="Change...", command=on_change).pack(side=tk.LEFT)
        ttk.Button(btns, text="Reset to defaults", command=on_reset).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="Close", command=dlg.destroy).pack(side=tk.RIGHT)
        refresh()

    def _rebuild_edit_menu_labels(self):
        self.master.config(menu="")
        menubar = tk.Menu(self.master)
        self.master.config(menu=menubar)
        self.edit_menu = tk.Menu(menubar, tearoff=0)
        self._edit_add_cmd("Bold", self._toggle_bold, "bold")
        self._edit_add_cmd("Italic", self._toggle_italic, "italic")
        self._edit_add_cmd("Underline", self._toggle_underline, "underline")
        self._edit_add_cmd("Strikethrough", self._toggle_strike, "strike")
        self.edit_menu.add_separator()
        self._edit_add_cmd("Clear formatting", self._clear_all_formatting, "clearfmt")
        self.edit_menu.add_separator()
        self._edit_add_cmd("Bulleted list toggle", self._toggle_bullets, "bullets")
        self._edit_add_cmd("Numbered list toggle", self._toggle_numbers, "numbers")
        self.edit_menu.add_separator()
        self._edit_add_cmd("UPPERCASE", lambda: self._convert_case("upper"), "case_upper")
        self._edit_add_cmd("lowercase", lambda: self._convert_case("lower"), "case_lower")
        self._edit_add_cmd("Title Case", lambda: self._convert_case("title"), "case_title")
        self._edit_add_cmd("Sentence case", lambda: self._convert_case("sentence"), "case_sentence")
        self.edit_menu.add_separator()
        self.edit_menu.add_command(label="Keyboard Shortcuts...", command=self._open_shortcuts_dialog)
        menubar.add_cascade(label="Edit", menu=self.edit_menu)
        view = tk.Menu(menubar, tearoff=0)
        view.add_command(label="Increase content font", command=self._content_font_increase)
        view.add_command(label="Decrease content font", command=self._content_font_decrease)
        view.add_command(label="Reset content font", command=self._content_font_reset)
        view.add_separator()
        view.add_command(label="Choose content font family...", command=self._content_font_choose_family)
        view.add_command(label="Use Aptos for content", command=self._content_use_aptos)
        menubar.add_cascade(label="View", menu=view)

    def _parse_user_shortcut(self, s):
        s = s.strip().lower().replace("ctrl", "control").replace("win", "super")
        s = s.replace("plus", "+").replace(" ", "")
        parts = [p for p in s.split("+") if p]
        if not parts:
            return None
        mods = []
        key = parts[-1]
        for p in parts[:-1]:
            if p in ("control", "shift", "alt", "super"):
                mods.append(p)
            else:
                return None
        glyph_map = {
            ".": "period",
            "/": "slash",
            "\\": "backslash",
            ";": "semicolon",
            "'": "apostrophe",
            ",": "comma",
            "[": "bracketleft",
            "]": "bracketright",
            "`": "grave",
        }
        key = glyph_map.get(key, key)
        seq = "<" + "-".join([m.capitalize() if m != "super" else "Super" for m in mods] + [key]) + ">"
        return seq

    # ---------- Selection helpers ----------
    def _get_target_ranges(self):
        m = self.text.tag_ranges("msel")
        if m:
            return list(zip(m[0::2], m[1::2]))
        try:
            start = self.text.index("sel.first")
            end = self.text.index("sel.last")
            return [(start, end)]
        except tk.TclError:
            return []

    def _clear_multi_select(self):
        self.text.tag_remove("msel", "1.0", "end")
        self._msel_anchor = None
        self.status_var.set("Multi-select cleared")

    # Multi-select handlers
    def _msel_start(self, event):
        self._msel_anchor = self.text.index(f"@{event.x},{event.y}")
        return "break"

    def _msel_drag(self, event):
        if not self._msel_anchor:
            return "break"
        cur = self.text.index(f"@{event.x},{event.y}")
        self.text.tag_remove("msel", self._msel_anchor, cur)
        self.text.tag_add("msel", self._msel_anchor, cur)
        return "break"

    def _click_normal(self, event):
        self._clear_multi_select()

    # ---------- Formatting ----------
    def _toggle_bold(self):
        self._toggle_font_combo(apply_bold=True)

    def _toggle_italic(self):
        self._toggle_font_combo(apply_italic=True)

    def _toggle_underline(self):
        for s, e in self._get_target_ranges():
            if self.text.tag_nextrange("underline", s, e):
                self.text.tag_remove("underline", s, e)
            else:
                self.text.tag_add("underline", s, e)

    def _toggle_strike(self):
        for s, e in self._get_target_ranges():
            if self.text.tag_nextrange("strike", s, e):
                self.text.tag_remove("strike", s, e)
            else:
                self.text.tag_add("strike", s, e)

    def _toggle_font_combo(self, apply_bold=False, apply_italic=False):
        ranges = self._get_target_ranges()
        if not ranges:
            self.status_var.set("Select text, or use Ctrl-select for multiple ranges")
            return
        for s, e in ranges:
            has_b = bool(self.text.tag_nextrange("font_b", s, e) or self.text.tag_nextrange("font_bi", s, e))
            has_i = bool(self.text.tag_nextrange("font_i", s, e) or self.text.tag_nextrange("font_bi", s, e))
            if apply_bold:
                has_b = not has_b
            if apply_italic:
                has_i = not has_i
            self.text.tag_remove("font_b", s, e)
            self.text.tag_remove("font_i", s, e)
            self.text.tag_remove("font_bi", s, e)
            if has_b and has_i:
                self.text.tag_add("font_bi", s, e)
            elif has_b:
                self.text.tag_add("font_b", s, e)
            elif has_i:
                self.text.tag_add("font_i", s, e)
        self.status_var.set("Formatting applied")

    def _clear_all_formatting(self):
        for s, e in self._get_target_ranges():
            for tag in ("font_b", "font_i", "font_bi", "underline", "strike", "misspell"):
                self.text.tag_remove(tag, s, e)

    # ---------- Lists ----------
    def _iter_selected_lines(self):
        ranges = self._get_target_ranges()
        if not ranges:
            return []
        lines = set()
        for s, e in ranges:
            ls = int(float(self.text.index(s).split(".")[0]))
            le = int(float(self.text.index(e).split(".")[0]))
            for ln in range(ls, le + 1):
                lines.add(ln)
        return sorted(lines)

    def _toggle_bullets(self):
        lines = self._iter_selected_lines()
        if not lines:
            return
        bullet = "• "
        first = self.text.get(f"{lines[0]}.0", f"{lines[0]}.0 lineend")
        add = not first.lstrip().startswith(bullet)
        for ln in lines[::-1]:
            start = f"{ln}.0"
            line = self.text.get(start, f"{ln}.0 lineend")
            if add:
                self.text.insert(start, bullet)
            else:
                if line.lstrip().startswith(bullet):
                    i = line.find(bullet)
                    self.text.delete(f"{ln}.{i}", f"{ln}.{i+len(bullet)}")

    def _toggle_numbers(self):
        lines = self._iter_selected_lines()
        if not lines:
            return
        first = self.text.get(f"{lines[0]}.0", f"{lines[0]}.0 lineend")
        m = re.match(r"\s*\d+\.\s", first)
        add = not bool(m)
        if add:
            for idx, ln in enumerate(lines, start=1):
                self.text.insert(f"{ln}.0", f"{idx}. ")
        else:
            for ln in lines[::-1]:
                line = self.text.get(f"{ln}.0", f"{ln}.0 lineend")
                m = re.match(r"\s*\d+\.\s", line)
                if m:
                    i = m.start()
                    j = m.end()
                    self.text.delete(f"{ln}.{i}", f"{ln}.{j}")

    # ---------- Case conversion ----------
    def _convert_case(self, mode):
        ranges = self._get_target_ranges()
        if not ranges:
            return
        for s, e in ranges:
            txt = self.text.get(s, e)
            if mode == "upper":
                nt = txt.upper()
            elif mode == "lower":
                nt = txt.lower()
            elif mode == "title":
                nt = txt.title()
            else:
                def sent(s_):
                    out = []
                    cap_next = True
                    for ch in s_:
                        if cap_next and ch.isalpha():
                            out.append(ch.upper())
                            cap_next = False
                        else:
                            out.append(ch.lower())
                        if ch in ".!?":
                            cap_next = True
                    return "".join(out)

                nt = sent(txt)
            try:
                self.text.replace(s, e, nt)
            except Exception:
                self.text.delete(s, e)
                self.text.insert(s, nt)

    # ---------- Spellcheck ----------
    def _word_bounds_at(self, index):
        try:
            ws = self.text.index(f"{index} wordstart")
            we = self.text.index(f"{index} wordend")
            return ws, we
        except Exception:
            return None, None

    def _spell_check_last_word(self, event=None):
        if not self.spell_dict:
            return
        ws, we = self._word_bounds_at("insert-1c")
        if not ws:
            return
        word = self.text.get(ws, we)
        clean = re.sub(r"^[^A-Za-z']+|[^A-Za-z']+$", "", word)
        self.text.tag_remove("misspell", ws, we)
        if not clean or clean.lower() in self.ignored_words or clean.lower() in self.user_dict:
            return
        try:
            ok = self.spell_dict.check(clean)
        except Exception:
            ok = True
        if not ok:
            self.text.tag_add("misspell", ws, we)

    def _current_word_bounds(self):
        try:
            idx = self.text.index(
                "@%d,%d"
                % (
                    self.text.winfo_pointerx() - self.text.winfo_rootx(),
                    self.text.winfo_pointery() - self.text.winfo_rooty(),
                )
            )
            return self._word_bounds_at(idx)
        except Exception:
            return None, None

    def _spell_add_to_dict(self):
        ws, we = self._current_word_bounds()
        if not ws:
            return
        w = self.text.get(ws, we).strip().lower()
        self.user_dict.add(w)
        self.text.tag_remove("misspell", ws, we)
        self.status_var.set(f"Added to dictionary: {w}")

    def _spell_ignore_word(self):
        ws, we = self._current_word_bounds()
        if not ws:
            return
        w = self.text.get(ws, we).strip().lower()
        self.ignored_words.add(w)
        self.text.tag_remove("misspell", ws, we)
        self.status_var.set(f"Ignored: {w}")

    # ---------- Rich formatting persistence ----------
    def _serialize_rich_content(self) -> str:
        """Capture text plus tag on or off events as a JSON list from Text.dump."""
        ops = self.text.dump("1.0", "end-1c", tag=True, text=True, mark=False, image=False)
        filtered = []
        skip_tags = {"sel", "misspell", "msel"}  # do not persist transient tags
        for item in ops:
            kind, value, index = item
            if kind in ("tagon", "tagoff") and value in skip_tags:
                continue
            filtered.append(item)
        return json.dumps(filtered)

    def _restore_rich_content(self, payload: str):
        """Rebuild the content and tags from a JSON dump created by _serialize_rich_content."""
        try:
            ops = json.loads(payload)
        except Exception:
            return
        self.text.delete("1.0", "end")
        open_tags = set()
        for kind, value, index in ops:
            if kind == "tagon":
                open_tags.add(value)
            elif kind == "tagoff":
                open_tags.discard(value)
            elif kind == "text":
                if open_tags:
                    self.text.insert("end", value, tuple(open_tags))
                else:
                    self.text.insert("end", value)
        self.text.edit_modified(False)

    # ---------- Misc UI helpers ----------
    def _clear_placeholder(self, entry):
        if entry.get().strip().lower().startswith("search "):
            entry.delete(0, "end")

    def _on_text_right_click(self, event):
        self.editor_menu.tk_popup(event.x_root, event.y_root)

    def _on_right_click(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            self.menu.tk_popup(event.x_root, event.y_root)

    # ---------- Font controls ----------
    def _content_font_increase(self):
        s = int(self.content_font.cget("size")) + 1
        self.content_font.configure(size=s)
        self.config["content_font_size"] = s
        self._apply_content_font()

    def _content_font_decrease(self):
        s = max(8, int(self.content_font.cget("size")) - 1)
        self.content_font.configure(size=s)
        self.config["content_font_size"] = s
        self._apply_content_font()

    def _content_font_reset(self):
        base = tkfont.nametofont("TkDefaultFont")
        fam = base.cget("family")
        size = int(base.cget("size"))
        self.content_font.configure(family=fam, size=size)
        self.config["content_font_family"] = fam
        self.config["content_font_size"] = size
        self._apply_content_font()

    def _content_font_choose_family(self):
        fam_input = simpledialog.askstring(
            "Content font family",
            "Enter a font family for the prompt list and editor. Examples: Segoe UI, Aptos, Calibri, Arial, Helvetica, Verdana, Courier New.\nLeave blank to cancel.",
            parent=self.master,
        )
        if not fam_input:
            return
        fams = {f.lower(): f for f in tkfont.families()}
        choice = fams.get(fam_input.lower())
        if not choice:
            messagebox.showerror("Font family", f"'{fam_input}' not found on this system.")
            return
        self.content_font.configure(family=choice)
        self.config["content_font_family"] = choice
        self._apply_content_font()

    def _content_use_aptos(self):
        fams = {f.lower(): f for f in tkfont.families()}
        choice = fams.get("aptos")
        if not choice:
            messagebox.showerror("Aptos font", "Aptos does not appear to be installed on this system.")
            return
        self.content_font.configure(family=choice)
        self.config["content_font_family"] = choice
        self._apply_content_font()

    # ---------- Core app behaviors ----------
    def _focus_search(self):
        self.search_var.set("")
        self.category_combo.configure(values=["All categories"] + self.db.list_categories())
        self.category_combo.set(self.category_var.get() or "All categories")
        for child in self.master.winfo_children():
            for g in child.winfo_children():
                if isinstance(g, ttk.Entry):
                    try:
                        if "Search" in g.get():
                            g.focus_set()
                            return
                    except Exception:
                        pass

    def _refresh_categories(self):
        cats = ["All categories"] + self.db.list_categories()
        try:
            self.category_combo.configure(values=cats)
            if self.category_var.get() not in cats:
                self.category_combo.set("All categories")
        except Exception:
            pass
        try:
            self.category_picker.configure(values=self.db.list_categories())
        except Exception:
            pass

    def _refresh_list(self):
        search = self.search_var.get().strip()
        category = None if self.category_var.get() == "All categories" else self.category_var.get()
        rows = self.db.search_prompts(
            text=search if not search.lower().startswith("search ") else "",
            category=category,
            favorites_only=self.fav_only.get(),
        )
        self._refresh_categories()
        for i in self.tree.get_children():
            self.tree.delete(i)
        for r in rows:
            updated = r["updated_at"].split("T")[0] if r["updated_at"] else ""
            title = ("★ " if r["favorite"] else "") + r["title"]
            self.tree.insert("", "end", iid=str(r["id"]), values=(title, r["category"], updated))
        self.status_var.set(f"Loaded {len(rows)} item(s)")

    def _load_into_editor(self, pid):
        row = self.db.get_prompt(pid)
        if not row:
            return
        self.current_id = row["id"]
        self.title_var.set(row["title"])
        self.category_edit_var.set(row["category"] or "")
        self.fav_var.set(bool(row["favorite"]))
        # Attempt to restore full formatting if present
        payload = self.db.get_format_payload(row["id"])
        if payload:
            # Ensure tags exist
            self._apply_content_font()
            self._restore_rich_content(payload)
        else:
            # Fallback to plain text
            self.text.delete("1.0", "end")
            self.text.insert("1.0", row["content"])
        self.text.edit_modified(False)
        self.dirty = False
        self.text.tag_remove("msel", "1.0", "end")
        self.status_var.set(f"Loaded: {row['title']}")
        if self.spell_dict:
            self.text.tag_remove("misspell", "1.0", "end")

    def _on_select(self, *args):
        sel = self.tree.selection()
        if not sel:
            return
        pid = int(sel[0])
        if self.dirty:
            if not messagebox.askyesno("Unsaved changes", "Discard unsaved changes and load the selected item?"):
                return
        self._load_into_editor(pid)

    def _on_new(self):
        if self.dirty and not messagebox.askyesno("Unsaved changes", "Discard unsaved changes and create new?"):
            return
        self.current_id = None
        self.title_var.set("New prompt")
        self.category_edit_var.set("")
        self.fav_var.set(False)
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "")
        self.text.edit_modified(False)
        self.dirty = False
        self.status_var.set("New item ready")

    def _on_save(self):
        title = self.title_var.get().strip()
        # Always keep content column in sync with what is visible
        content = self.text.get("1.0", "end-1c")
        category = self.category_edit_var.get().strip()
        favorite = self.fav_var.get()
        if not title:
            messagebox.showerror("Validation", "Title is required")
            return
        if not content.strip():
            if not messagebox.askyesno("Empty content", "Content is empty, continue?"):
                return
        if self.current_id is None:
            self.current_id = self.db.create_prompt(title, content, category, favorite)
            self.status_var.set("Saved new item")
        else:
            self.db.update_prompt(self.current_id, title, content, category, favorite)
            self.status_var.set("Saved changes")
        # Persist rich formatting after the prompt record exists
        fmt_payload = self._serialize_rich_content()
        self.db.upsert_format_payload(self.current_id, fmt_payload)
        self.text.edit_modified(False)
        self.dirty = False
        self._refresh_list()
        if self.current_id:
            try:
                self.tree.selection_set(str(self.current_id))
                self.tree.see(str(self.current_id))
            except Exception:
                pass

    def _on_duplicate(self):
        if self.current_id is None:
            messagebox.showinfo("Duplicate", "Load or create an item first")
            return
        title = self.title_var.get().strip() + " (copy)"
        content = self.text.get("1.0", "end-1c")
        category = self.category_edit_var.get().strip()
        favorite = self.fav_var.get()
        new_id = self.db.create_prompt(title, content, category, favorite)
        # Duplicate formatting from current editor state
        fmt_payload = self._serialize_rich_content()
        self.db.upsert_format_payload(new_id, fmt_payload)
        self._refresh_list()
        self._refresh_categories()
        self.tree.selection_set(str(new_id))
        self.tree.see(str(new_id))
        self._load_into_editor(new_id)
        self.status_var.set("Duplicated")

    def _on_delete(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Delete", "Select an item to delete")
            return
        pid = int(sel[0])
        row = self.db.get_prompt(pid)
        if not row:
            return
        if messagebox.askyesno("Delete", f"Delete '{row['title']}'?"):
            self.db.delete_prompt(pid)
            if self.current_id == pid:
                self.current_id = None
                self._on_new()
            self._refresh_list()
            self._refresh_categories()
            self.status_var.set("Deleted")

    def _on_copy(self):
        content = self.text.get("1.0", "end-1c")
        self.master.clipboard_clear()
        self.master.clipboard_append(content)
        self.status_var.set("Copied to clipboard")

    def _on_copy_md(self):
        content = self.text.get("1.0", "end-1c")
        block = "```\n" + content + "\n```"
        self.master.clipboard_clear()
        self.master.clipboard_append(block)
        self.status_var.set("Copied as Markdown code block")

    def _on_copy_with_vars(self):
        content = self.text.get("1.0", "end-1c")
        vars_found = sorted(set(re.findall(r"\{{(.*?)\}}", content))) or sorted(
            set(re.findall(r"\{(.*?)\}", content))
        )
        values = {}
        for v in vars_found:
            val = simpledialog.askstring("Variable", f"Value for '{v}':", parent=self.master)
            if val is None:
                return
            values[v] = val

        def repl(m):
            return values.get(m.group(1), m.group(0))

        if vars_found:
            content = re.sub(r"\{{(.*?)\}}", repl, content)
            content = re.sub(r"\{(.*?)\}", repl, content)
        self.master.clipboard_clear()
        self.master.clipboard_append(content)
        self.status_var.set("Copied with variables applied")

    def _on_import(self):
        path = filedialog.askopenfilename(title="Import CSV", filetypes=[("CSV files", "*.csv")])
        if not path:
            return
        try:
            count = self.db.import_csv(path)
            self._refresh_list()
            self._refresh_categories()
            messagebox.showinfo("Import", f"Imported {count} item(s)")
        except Exception as e:
            messagebox.showerror("Import error", str(e))

    def _on_export(self):
        path = filedialog.asksaveasfilename(
            title="Export CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile="prompts_export.csv",
        )
        if not path:
            return
        try:
            self.db.export_csv(path)
            messagebox.showinfo("Export", "Exported successfully")
        except Exception as e:
            messagebox.showerror("Export error", str(e))

    def _on_modified(self, event=None):
        if self.text.edit_modified():
            self.dirty = True
            self.text.edit_modified(False)

    def _maybe_seed(self):
        cur = self.db.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM prompts")
        n = cur.fetchone()[0]
        if n == 0:
            self.db.create_prompt(
                "Bug report template",
                "Title: {{title}}\nSteps to reproduce:\n1)\n2)\nExpected:\nActual:\nNotes:\n",
                category="Templates",
                favorite=True,
            )
            self.db.create_prompt(
                "Polished rewrite prompt",
                "Rewrite the following email for clarity, professional tone, and concise structure:\n\n---\n{{email_text}}\n---\nConstraints: keep all facts, fix grammar, use short paragraphs.",
                category="AI",
                favorite=False,
            )
            self._refresh_list()

    # ---------- Unsaved on close ----------
    def _on_close(self):
        if self.dirty:
            self._prompt_unsaved_close()
            return
        self._save_config()
        self.master.destroy()

    def _prompt_unsaved_close(self):
        dlg = tk.Toplevel(self.master)
        dlg.title("Unsaved changes")
        dlg.transient(self.master)
        dlg.grab_set()
        ttk.Label(dlg, text="You have unsaved changes.", padding=12).pack(anchor="w")
        btns = ttk.Frame(dlg)
        btns.pack(fill=tk.X, padx=12, pady=(0, 12))

        def save_now():
            self._on_save()
            dlg.destroy()  # keep app open after saving

        def close_without():
            dlg.destroy()
            self._save_config()
            self.master.destroy()

        ttk.Button(btns, text="Save Now", command=save_now).pack(side=tk.LEFT)
        ttk.Button(btns, text="Close Without Saving", command=close_without).pack(side=tk.RIGHT)
        # Center dialog over parent
        dlg.update_idletasks()
        x = self.master.winfo_rootx() + (self.master.winfo_width() - dlg.winfo_width()) // 2
        y = self.master.winfo_rooty() + (self.master.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{x}+{y}")

    def _invoke_action(self, key):
        mapping = {
            "bold": self._toggle_bold,
            "italic": self._toggle_italic,
            "underline": self._toggle_underline,
            "strike": self._toggle_strike,
            "bullets": self._toggle_bullets,
            "numbers": self._toggle_numbers,
            "case_upper": lambda: self._convert_case("upper"),
            "case_lower": lambda: self._convert_case("lower"),
            "case_title": lambda: self._convert_case("title"),
            "case_sentence": lambda: self._convert_case("sentence"),
        }
        fn = mapping.get(key)
        if fn:
            fn()


def main():
    minimize_console_window()
    root = tk.Tk()
    try:
        root.iconbitmap(default="")
    except Exception:
        pass
    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    try:
        root.after(
            150,
            lambda: (
                root.lift(),
                root.attributes("-topmost", True),
                root.after(150, lambda: root.attributes("-topmost", False)),
            ),
        )
    except Exception:
        pass
    app = App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
