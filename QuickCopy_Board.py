from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
import tkinter as tk
import webbrowser
from dataclasses import dataclass
from tkinter import colorchooser, filedialog, messagebox, ttk


APP_NAME = "QuickCopy Boards"
APP_VERSION = "1.2"
DATA_FILENAME = ".quickcopy_boards.json"


# ----------------------------
# Utilities
# ----------------------------
def user_data_path() -> str:
    home = os.path.expanduser("~")
    return os.path.join(home, DATA_FILENAME)


def now_ts() -> float:
    return time.time()


def safe_int(value: str, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def clamp(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, n))


def center_window(win: tk.Toplevel | tk.Tk, width: int, height: int) -> None:
    win.update_idletasks()
    x = (win.winfo_screenwidth() - width) // 2
    y = (win.winfo_screenheight() - height) // 2
    win.geometry(f"{width}x{height}+{x}+{y}")


def _expand_path(path: str) -> str:
    expanded = os.path.expanduser(path)
    expanded = os.path.expandvars(expanded)
    return expanded


def open_in_file_explorer(path: str) -> None:
    """
    Open a folder, or reveal a file in its folder.
    Windows: uses explorer, selects file when possible.
    macOS: uses open (or open -R for files).
    Linux: uses xdg-open on the folder.
    """
    if not path:
        return

    expanded = _expand_path(path.strip())

    if not os.path.exists(expanded):
        messagebox.showwarning(APP_NAME, f"Path does not exist:\n{expanded}")
        return

    system = platform.system().lower()
    try:
        if "windows" in system:
            if os.path.isfile(expanded):
                subprocess.Popen(["explorer", "/select,", expanded])
            else:
                subprocess.Popen(["explorer", expanded])
        elif "darwin" in system:
            if os.path.isfile(expanded):
                subprocess.Popen(["open", "-R", expanded])
            else:
                subprocess.Popen(["open", expanded])
        else:
            folder = expanded
            if os.path.isfile(expanded):
                folder = os.path.dirname(expanded) or expanded
            subprocess.Popen(["xdg-open", folder])
    except Exception as exc:
        messagebox.showerror(APP_NAME, f"Could not open path.\n\n{exc}")


def normalize_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    # If the user typed a bare domain, add https://
    if "://" not in u and not u.lower().startswith(("mailto:", "file:")):
        u = "https://" + u
    return u


def open_url(url: str, prefer_chrome: bool = False) -> None:
    """
    Open a URL. If prefer_chrome is True, attempt Chrome first, otherwise fall back to default browser.
    """
    u = normalize_url(url)
    if not u:
        return

    try:
        if prefer_chrome:
            # Try common controller names
            for name in ("chrome", "google-chrome", "chrome-browser", "chromium", "chromium-browser"):
                try:
                    b = webbrowser.get(name)
                    b.open_new_tab(u)
                    return
                except Exception:
                    pass
        webbrowser.open_new_tab(u)
    except Exception as exc:
        messagebox.showerror(APP_NAME, f"Could not open URL.\n\n{exc}")


# ----------------------------
# Defaults
# ----------------------------
def default_button(i: int) -> dict:
    return {
        "id": f"btn_{i}_{int(now_ts() * 1000)}",
        "name": f"Button {i + 1}",
        "content": "",
        "tags": "",
        "path": "",
        "url": "",                     # NEW
        "prefer_chrome": True,         # NEW
        "empty_action": "path",        # NEW: 'path' | 'url' | 'none'
        "color": "#4C78A8",
        "icon": "📌",
        "bg_image": "",
        "bg_mode": "Fit",              # Stretch | Fit | Fill | Tile | Center
    }


def default_board(name: str = "Board 1", rows: int = 3, cols: int = 3) -> dict:
    count = rows * cols
    return {
        "id": f"board_{int(now_ts() * 1000)}",
        "name": name,
        "columns": cols,
        "buttons": [default_button(i) for i in range(count)],
    }


def default_data() -> dict:
    return {
        "meta": {"app": APP_NAME, "version": APP_VERSION},
        "ui": {
            "theme_mode": "auto",
            "always_on_top": False,
            "window_geometry": "980x640",
            "compact_geometry": "520x420",
            "compact_mode": False,
            "padding": 10,
        },
        "shortcuts": {
            "copy_focused": "<Return>",
            "copy_focused_alt": "<space>",
            "find": "<Control-f>",
            "new_button": "<Control-n>",
            "save": "<Control-s>",
            "toggle_edit_mode": "<Control-e>",
            "toggle_compact": "<Control-p>",
            "open_shortcut_manager": "<Control-k>",
        },
        "boards": [default_board("Board 1", 3, 3)],
        "active_board_index": 0,
    }


def migrate_data(data: dict) -> dict:
    """
    Ensure older saved JSON gains new keys without breaking existing data.
    """
    base = default_data()
    base.update(data)
    base["ui"].update(data.get("ui", {}))
    base["shortcuts"].update(data.get("shortcuts", {}))

    if not base.get("boards"):
        base["boards"] = [default_board("Board 1", 3, 3)]
        base["active_board_index"] = 0

    for board in base["boards"]:
        board.setdefault("columns", 3)
        board.setdefault("buttons", [])
        for i, btn in enumerate(board["buttons"]):
            btn.setdefault("id", f"btn_{i}_{int(now_ts() * 1000)}")
            btn.setdefault("name", f"Button {i + 1}")
            btn.setdefault("content", "")
            btn.setdefault("tags", "")
            btn.setdefault("path", "")
            btn.setdefault("url", "")
            btn.setdefault("prefer_chrome", True)
            btn.setdefault("empty_action", "path")
            btn.setdefault("color", "#4C78A8")
            btn.setdefault("icon", "📌")
            btn.setdefault("bg_image", "")
            btn.setdefault("bg_mode", "Fit")

    return base


# ----------------------------
# Icon Picker
# ----------------------------
ICON_SETS = {
    "General": [
        "📌", "⭐", "✅", "🧠", "🧩", "🧰", "🗂️", "📁", "📝", "📎", "🔗", "🔍", "🧾", "📦", "🧷",
        "⚙️", "🛠️", "🔧", "🔒", "🔑", "⏱️", "📅", "📍", "🧭", "🧯", "📣", "📊", "📈", "🧮",
    ],
    "Work": [
        "🏭", "🧪", "📋", "🧫", "🧬", "🧴", "📦", "🧾", "🗃️", "🗄️", "🧹", "🧼", "🧻", "🧰",
        "👷", "🦺", "🧯", "🚧", "🔍", "✅", "⚠️", "⛔", "🧷", "🧾",
    ],
    "Places": [
        "🏠", "🏢", "🏬", "🏥", "🏫", "🏦", "🏨", "🏟️", "🏞️", "🏕️", "🗺️", "📍", "🚗", "✈️",
    ],
    "Files": [
        "📁", "🗂️", "🗃️", "🗄️", "📄", "📃", "🧾", "📑", "📊", "📈", "📉", "🧮", "🧷", "📎",
    ],
    "Fun": [
        "🔥", "🎯", "🎵", "🎧", "🎮", "🎲", "🍕", "☕", "🌲", "❄️", "🌙", "🌟", "🧊", "⚡",
    ],
}


class IconPickerDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk, initial: str = "📌"):
        super().__init__(parent)
        self.title("Pick an icon")
        self.transient(parent)
        self.grab_set()

        self.result: str | None = None
        self._initial = initial

        root = ttk.Frame(self, padding=(12, 12))
        root.pack(fill="both", expand=True)

        top = ttk.Frame(root)
        top.pack(fill="x")

        ttk.Label(top, text="Search:").pack(side="left")
        self.search_var = tk.StringVar(value="")
        search = ttk.Entry(top, textvariable=self.search_var, width=28)
        search.pack(side="left", padx=(6, 10))
        search.bind("<KeyRelease>", lambda _e: self._render_grid())

        ttk.Label(top, text="Category:").pack(side="left")
        self.cat_var = tk.StringVar(value="General")
        cats = ttk.Combobox(top, textvariable=self.cat_var, values=list(ICON_SETS.keys()), width=14, state="readonly")
        cats.pack(side="left", padx=(6, 0))
        cats.bind("<<ComboboxSelected>>", lambda _e: self._render_grid())

        self.canvas = tk.Canvas(root, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, pady=(12, 0))

        self.scroll = ttk.Scrollbar(root, orient="vertical", command=self.canvas.yview)
        self.scroll.place(relx=1.0, rely=0.18, relheight=0.78, anchor="ne")
        self.canvas.configure(yscrollcommand=self.scroll.set)

        self.inner = ttk.Frame(self.canvas, padding=(6, 6))
        self.inner_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        btns = ttk.Frame(root)
        btns.pack(fill="x", pady=(10, 0))
        ttk.Button(btns, text="Cancel", command=self._cancel).pack(side="right")
        ttk.Button(btns, text="Use default", command=self._use_default).pack(side="right", padx=(0, 8))

        self.bind("<Escape>", lambda _e: self._cancel())

        center_window(self, 520, 520)
        search.focus_set()
        self._render_grid()
        self.wait_window(self)

    def _on_inner_configure(self, _e: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, _e: tk.Event) -> None:
        self.canvas.itemconfigure(self.inner_id, width=self.canvas.winfo_width())

    def _use_default(self) -> None:
        self.result = self._initial
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()

    def _render_grid(self) -> None:
        for child in self.inner.winfo_children():
            child.destroy()

        query = self.search_var.get().strip()
        cat = self.cat_var.get()
        icons = ICON_SETS.get(cat, [])

        if query:
            icons = [ic for ic in icons if query in ic]

        if query:
            all_icons = []
            for _cat, items in ICON_SETS.items():
                all_icons.extend(items)
            icons = [ic for ic in all_icons if query in ic]
            icons = list(dict.fromkeys(icons))

        cols = 10
        for c in range(cols):
            self.inner.columnconfigure(c, weight=1)

        def pick(ic: str) -> None:
            self.result = ic
            self.destroy()

        for i, ic in enumerate(icons):
            r = i // cols
            c = i % cols
            b = ttk.Button(self.inner, text=ic, width=3, command=lambda x=ic: pick(x))
            b.grid(row=r, column=c, padx=4, pady=4, sticky="nsew")

        if not icons:
            ttk.Label(self.inner, text="No icons match your search.").grid(row=0, column=0, sticky="w")


# ----------------------------
# Image rendering helpers
# ----------------------------
@dataclass
class RenderedImage:
    photo: tk.PhotoImage
    width: int
    height: int


class ImageCache:
    """
    Caches loaded originals and scaled versions per button tile size.
    """
    def __init__(self) -> None:
        self._originals: dict[str, tk.PhotoImage] = {}
        self._scaled: dict[tuple[str, int, int, str], tk.PhotoImage] = {}

    def get_original(self, path: str) -> tk.PhotoImage | None:
        path = path.strip()
        if not path:
            return None
        expanded = _expand_path(path)
        if not os.path.exists(expanded):
            return None
        key = expanded
        if key in self._originals:
            return self._originals[key]
        try:
            img = tk.PhotoImage(file=expanded)
            self._originals[key] = img
            return img
        except Exception:
            return None

    def get_scaled(self, path: str, target_w: int, target_h: int, mode: str) -> tk.PhotoImage | None:
        orig = self.get_original(path)
        if orig is None:
            return None

        mode_norm = (mode or "Fit").strip()
        if mode_norm == "Stretch":
            mode_norm = "Fill"

        if mode_norm in {"Tile", "Center"}:
            return orig

        key = (_expand_path(path), target_w, target_h, mode_norm)
        if key in self._scaled:
            return self._scaled[key]

        ow, oh = orig.width(), orig.height()
        if ow <= 0 or oh <= 0 or target_w <= 0 or target_h <= 0:
            return orig

        sx = target_w / ow
        sy = target_h / oh

        if mode_norm == "Fit":
            s = min(sx, sy)
        else:
            s = max(sx, sy)

        if s <= 0:
            return orig

        if s < 1.0:
            n = int(round(1.0 / s))
            n = clamp(n, 1, 20)
            scaled = orig.subsample(n, n)
        else:
            n = int(round(s))
            n = clamp(n, 1, 10)
            scaled = orig.zoom(n, n)

        self._scaled[key] = scaled
        return scaled


# ----------------------------
# Main app
# ----------------------------
class QuickCopyApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.minsize(720, 480)

        self.data_path = user_data_path()
        self.data = self.load_data()
        self.edit_mode = tk.BooleanVar(value=False)
        self.search_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Ready")
        self._last_save_ts = 0.0

        self.image_cache = ImageCache()

        self.geometry(self.data["ui"].get("window_geometry", "980x640"))
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.style = ttk.Style(self)
        self._configure_style()

        self.apply_topmost()
        if self.data["ui"].get("compact_mode", False):
            self.after(50, self.enable_compact_mode)

        self._build_menu()
        self._build_toolbar()
        self._build_notebook()
        self._build_statusbar()

        self.refresh_tabs()
        self.apply_shortcuts()

        self.after(1000, self._tick)

    # ----------------------------
    # Persistence
    # ----------------------------
    def load_data(self) -> dict:
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                return migrate_data(raw)
            except Exception as exc:
                messagebox.showwarning(
                    APP_NAME,
                    f"Could not load settings file.\nA new one will be created.\n\n{exc}",
                )
                return default_data()
        return default_data()

    def save_data(self) -> None:
        if self.data["ui"].get("compact_mode", False):
            self.data["ui"]["compact_geometry"] = self.geometry()
        else:
            self.data["ui"]["window_geometry"] = self.geometry()

        try:
            with open(self.data_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            self._last_save_ts = now_ts()
            self.set_status("Saved")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not save settings.\n\n{exc}")

    def autosave(self) -> None:
        self.save_data()

    # ----------------------------
    # UI construction
    # ----------------------------
    def _configure_style(self) -> None:
        available = self.style.theme_names()
        theme_mode = self.data["ui"].get("theme_mode", "auto")

        if theme_mode == "dark":
            if "clam" in available:
                self.style.theme_use("clam")
        elif theme_mode == "light":
            if sys.platform.startswith("win") and "vista" in available:
                self.style.theme_use("vista")
            elif "clam" in available:
                self.style.theme_use("clam")
        else:
            if sys.platform.startswith("win") and "vista" in available:
                self.style.theme_use("vista")
            elif "clam" in available:
                self.style.theme_use("clam")

        default_font = ("Segoe UI", 10) if sys.platform.startswith("win") else ("TkDefaultFont", 10)
        self.option_add("*Font", default_font)

        self.style.configure("TButton", padding=(10, 8))
        self.style.configure("Toolbutton.TButton", padding=(8, 6))
        self.style.configure("TEntry", padding=(8, 6))
        self.style.configure("TNotebook.Tab", padding=(12, 8))

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="New board", command=self.new_board)
        file_menu.add_command(label="Rename active board", command=self.rename_active_board)
        file_menu.add_command(label="Delete active board", command=self.delete_active_board)
        file_menu.add_separator()
        file_menu.add_command(label="Import boards from JSON", command=self.import_json)
        file_menu.add_command(label="Export boards to JSON", command=self.export_json)
        file_menu.add_separator()
        file_menu.add_command(label="Save now\tCtrl+S", command=self.save_data)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)

        view_menu = tk.Menu(menubar, tearoff=False)
        view_menu.add_command(label="Toggle always on top", command=self.toggle_always_on_top)
        view_menu.add_command(label="Toggle compact palette\tCtrl+P", command=self.toggle_compact_mode)

        theme_menu = tk.Menu(view_menu, tearoff=False)
        theme_menu.add_command(label="Auto", command=lambda: self.set_theme_mode("auto"))
        theme_menu.add_command(label="Light", command=lambda: self.set_theme_mode("light"))
        theme_menu.add_command(label="Dark", command=lambda: self.set_theme_mode("dark"))
        view_menu.add_cascade(label="Theme", menu=theme_menu)

        tools_menu = tk.Menu(menubar, tearoff=False)
        tools_menu.add_command(label="Shortcut manager\tCtrl+K", command=self.open_shortcut_manager)
        tools_menu.add_command(label="About", command=self.show_about)

        menubar.add_cascade(label="File", menu=file_menu)
        menubar.add_cascade(label="View", menu=view_menu)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        self.config(menu=menubar)

    def _build_toolbar(self) -> None:
        pad = self.data["ui"].get("padding", 10)
        bar = ttk.Frame(self, padding=(pad, pad, pad, 6))
        bar.pack(fill="x")

        left = ttk.Frame(bar)
        left.pack(side="left", fill="x", expand=True)

        right = ttk.Frame(bar)
        right.pack(side="right")

        self.search_entry = ttk.Entry(left, textvariable=self.search_var, width=36)
        self.search_entry.pack(side="left")
        self.search_entry.bind("<KeyRelease>", lambda _e: self.refresh_active_board())

        ttk.Button(left, text="Clear", style="Toolbutton.TButton", command=self.clear_search).pack(
            side="left", padx=(8, 0)
        )

        ttk.Separator(left, orient="vertical").pack(side="left", fill="y", padx=10)

        ttk.Button(left, text="+ New button\tCtrl+N", command=self.new_button_dialog).pack(side="left")

        ttk.Checkbutton(
            left,
            text="Edit mode\tCtrl+E",
            variable=self.edit_mode,
            command=self._on_edit_mode_changed,
        ).pack(side="left", padx=(10, 0))

        ttk.Button(right, text="New board", style="Toolbutton.TButton", command=self.new_board).pack(side="left")
        ttk.Button(right, text="Rename board", style="Toolbutton.TButton", command=self.rename_active_board).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(right, text="Save", style="Toolbutton.TButton", command=self.save_data).pack(side="left", padx=(8, 0))

    def _build_notebook(self) -> None:
        pad = self.data["ui"].get("padding", 10)
        container = ttk.Frame(self, padding=(pad, 0, pad, pad))
        container.pack(fill="both", expand=True)

        self.notebook = ttk.Notebook(container)
        self.notebook.pack(fill="both", expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", lambda _e: self.on_tab_changed())

    def _build_statusbar(self) -> None:
        bar = ttk.Frame(self, padding=(10, 6))
        bar.pack(fill="x", side="bottom")
        ttk.Label(bar, textvariable=self.status_var).pack(side="left")
        ttk.Label(bar, text="  |  Left click runs button, right click edits, middle click runs and closes").pack(
            side="right"
        )

    # ----------------------------
    # Tabs and board rendering
    # ----------------------------
    def refresh_tabs(self) -> None:
        for tab_id in self.notebook.tabs():
            self.notebook.forget(tab_id)

        self.board_frames: list[ttk.Frame] = []
        for idx, board in enumerate(self.data["boards"]):
            frame = ttk.Frame(self.notebook)
            self.board_frames.append(frame)
            self.notebook.add(frame, text=board.get("name", f"Board {idx + 1}"))

        active = clamp(self.data.get("active_board_index", 0), 0, len(self.data["boards"]) - 1)
        self.notebook.select(active)
        self.refresh_active_board()

    def on_tab_changed(self) -> None:
        self.data["active_board_index"] = self.notebook.index(self.notebook.select())
        self.refresh_active_board()
        self.autosave()

    def active_board(self) -> dict:
        idx = clamp(self.data.get("active_board_index", 0), 0, len(self.data["boards"]) - 1)
        return self.data["boards"][idx]

    def active_frame(self) -> ttk.Frame:
        idx = clamp(self.data.get("active_board_index", 0), 0, len(self.board_frames) - 1)
        return self.board_frames[idx]

    def refresh_active_board(self) -> None:
        frame = self.active_frame()
        board = self.active_board()

        for child in frame.winfo_children():
            child.destroy()

        top = ttk.Frame(frame, padding=(10, 10, 10, 8))
        top.pack(fill="x")

        ttk.Label(top, text="Columns:").pack(side="left")
        cols_var = tk.StringVar(value=str(board.get("columns", 3)))
        cols_entry = ttk.Entry(top, textvariable=cols_var, width=6)
        cols_entry.pack(side="left", padx=(6, 0))

        def apply_cols() -> None:
            cols = clamp(safe_int(cols_var.get(), board.get("columns", 3)), 1, 12)
            board["columns"] = cols
            self.autosave()
            self.refresh_active_board()

        ttk.Button(top, text="Apply", style="Toolbutton.TButton", command=apply_cols).pack(side="left", padx=(8, 0))

        ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=12)

        ttk.Button(top, text="Add button", style="Toolbutton.TButton", command=self.new_button_dialog).pack(side="left")
        ttk.Button(top, text="Manage board", style="Toolbutton.TButton", command=self.manage_board_dialog).pack(
            side="left", padx=(8, 0)
        )

        grid = ttk.Frame(frame, padding=(10, 0, 10, 10))
        grid.pack(fill="both", expand=True)

        cols = clamp(int(board.get("columns", 3)), 1, 12)
        buttons = list(board.get("buttons", []))

        query = self.search_var.get().strip().lower()
        if query:
            def match(btn: dict) -> bool:
                name = (btn.get("name") or "").lower()
                tags = (btn.get("tags") or "").lower()
                content = (btn.get("content") or "").lower()
                path = (btn.get("path") or "").lower()
                url = (btn.get("url") or "").lower()
                return query in name or query in tags or query in content or query in path or query in url

            buttons = [b for b in buttons if match(b)]

        for c in range(cols):
            grid.columnconfigure(c, weight=1, uniform="col")
        rows = max(1, (len(buttons) + cols - 1) // cols)
        for r in range(rows):
            grid.rowconfigure(r, weight=1, uniform="row")

        for i, btn in enumerate(buttons):
            r = i // cols
            c = i % cols
            tile = ButtonTile(master=grid, app=self, btn_data=btn)
            tile.grid(row=r, column=c, sticky="nsew", padx=6, pady=6)

        if not buttons:
            msg = "No matches. Try clearing search." if query else "No buttons yet. Add one with Ctrl+N."
            ttk.Label(grid, text=msg).place(relx=0.5, rely=0.5, anchor="center")

    # ----------------------------
    # Clipboard and status
    # ----------------------------
    def copy_to_clipboard(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update_idletasks()

    def set_status(self, text: str) -> None:
        self.status_var.set(text)

    # ----------------------------
    # Board ops
    # ----------------------------
    def new_board(self) -> None:
        name = simple_text_prompt(self, "New board", "Board name:", "New Board")
        if not name:
            return
        self.data["boards"].append(default_board(name, 3, 3))
        self.data["active_board_index"] = len(self.data["boards"]) - 1
        self.autosave()
        self.refresh_tabs()
        self.set_status(f"Created board: {name}")

    def rename_active_board(self) -> None:
        board = self.active_board()
        current = board.get("name", "Board")
        name = simple_text_prompt(self, "Rename board", "Board name:", current)
        if not name:
            return
        board["name"] = name
        self.autosave()
        self.refresh_tabs()
        self.set_status(f"Renamed board to: {name}")

    def delete_active_board(self) -> None:
        if len(self.data["boards"]) <= 1:
            messagebox.showinfo(APP_NAME, "You must keep at least one board.")
            return
        board = self.active_board()
        if not messagebox.askyesno(APP_NAME, f"Delete board '{board.get('name', '')}'?\nThis cannot be undone."):
            return
        idx = self.data.get("active_board_index", 0)
        self.data["boards"].pop(idx)
        self.data["active_board_index"] = clamp(idx, 0, len(self.data["boards"]) - 1)
        self.autosave()
        self.refresh_tabs()
        self.set_status("Board deleted")

    # ----------------------------
    # Button ops
    # ----------------------------
    def new_button_dialog(self) -> None:
        board = self.active_board()
        dlg = ButtonEditorDialog(self, title="New button", initial=None, allow_delete=False)
        if not dlg.result:
            return
        board["buttons"].append(dlg.result)
        self.autosave()
        self.refresh_active_board()
        self.set_status("Added button")

    def edit_button(self, btn_data: dict) -> None:
        dlg = ButtonEditorDialog(self, title="Edit button", initial=btn_data, allow_delete=True)
        if dlg.deleted:
            self.delete_button(btn_data)
            return
        if dlg.result:
            btn_data.update(dlg.result)
            self.autosave()
            self.refresh_active_board()
            self.set_status("Updated button")

    def delete_button(self, btn_data: dict) -> None:
        board = self.active_board()
        if not messagebox.askyesno(APP_NAME, f"Delete '{btn_data.get('name', '')}'?"):
            return
        board["buttons"] = [b for b in board["buttons"] if b.get("id") != btn_data.get("id")]
        self.autosave()
        self.refresh_active_board()
        self.set_status("Deleted button")

    def manage_board_dialog(self) -> None:
        board = self.active_board()
        current = len(board.get("buttons", []))
        desired_str = simple_text_prompt(self, "Manage board", "Total buttons (will add or remove):", str(current))
        if desired_str is None:
            return
        desired = clamp(safe_int(desired_str, current), 1, 400)

        if desired == current:
            return

        if desired < current:
            if not messagebox.askyesno(APP_NAME, f"Remove {current - desired} button(s) from the end?"):
                return
            board["buttons"] = board["buttons"][:desired]
        else:
            for i in range(current, desired):
                board["buttons"].append(default_button(i))

        self.autosave()
        self.refresh_active_board()
        self.set_status(f"Board now has {desired} button(s)")

    # ----------------------------
    # Search
    # ----------------------------
    def clear_search(self) -> None:
        self.search_var.set("")
        self.search_entry.focus_set()
        self.refresh_active_board()

    # ----------------------------
    # Theme and view
    # ----------------------------
    def set_theme_mode(self, mode: str) -> None:
        self.data["ui"]["theme_mode"] = mode
        self._configure_style()
        self.autosave()
        self.refresh_active_board()
        self.set_status(f"Theme set to: {mode}")

    def apply_topmost(self) -> None:
        self.attributes("-topmost", bool(self.data["ui"].get("always_on_top", False)))

    def toggle_always_on_top(self) -> None:
        self.data["ui"]["always_on_top"] = not bool(self.data["ui"].get("always_on_top", False))
        self.apply_topmost()
        self.autosave()
        self.set_status("Always on top enabled" if self.data["ui"]["always_on_top"] else "Always on top disabled")

    def enable_compact_mode(self) -> None:
        self.data["ui"]["compact_mode"] = True
        self.apply_topmost()
        self.geometry(self.data["ui"].get("compact_geometry", "520x420"))
        self.set_status("Compact palette mode on")
        self.autosave()

    def disable_compact_mode(self) -> None:
        self.data["ui"]["compact_mode"] = False
        self.apply_topmost()
        self.geometry(self.data["ui"].get("window_geometry", "980x640"))
        self.set_status("Compact palette mode off")
        self.autosave()

    def toggle_compact_mode(self) -> None:
        if self.data["ui"].get("compact_mode", False):
            self.disable_compact_mode()
        else:
            self.enable_compact_mode()

    # ----------------------------
    # Shortcuts
    # ----------------------------
    def apply_shortcuts(self) -> None:
        sc = self.data.get("shortcuts", {})

        self.bind_all(sc.get("copy_focused", "<Return>"), lambda _e: self.copy_focused_button())
        self.bind_all(sc.get("copy_focused_alt", "<space>"), lambda _e: self.copy_focused_button())
        self.bind_all(sc.get("find", "<Control-f>"), lambda _e: self.focus_search())
        self.bind_all(sc.get("new_button", "<Control-n>"), lambda _e: self.new_button_dialog())
        self.bind_all(sc.get("save", "<Control-s>"), lambda _e: self.save_data())
        self.bind_all(sc.get("toggle_edit_mode", "<Control-e>"), lambda _e: self.toggle_edit_mode())
        self.bind_all(sc.get("toggle_compact", "<Control-p>"), lambda _e: self.toggle_compact_mode())
        self.bind_all(sc.get("open_shortcut_manager", "<Control-k>"), lambda _e: self.open_shortcut_manager())

        for i in range(1, 11):
            key = f"<Control-Key-{i % 10}>"
            self.bind_all(key, lambda _e, idx=i - 1: self.jump_to_board(idx))

    def jump_to_board(self, idx: int) -> None:
        if idx < len(self.data["boards"]):
            self.data["active_board_index"] = idx
            self.notebook.select(idx)
            self.autosave()

    def focus_search(self) -> None:
        self.search_entry.focus_set()
        self.search_entry.selection_range(0, tk.END)

    def toggle_edit_mode(self) -> None:
        self.edit_mode.set(not self.edit_mode.get())
        self._on_edit_mode_changed()

    def _on_edit_mode_changed(self) -> None:
        self.set_status("Edit mode on" if self.edit_mode.get() else "Edit mode off")

    def open_shortcut_manager(self) -> None:
        ShortcutManagerDialog(self)

    def copy_focused_button(self) -> None:
        widget = self.focus_get()
        if hasattr(widget, "_quickcopy_activate"):
            try:
                widget._quickcopy_activate()  # type: ignore[attr-defined]
            except Exception:
                pass

    # ----------------------------
    # Import / Export
    # ----------------------------
    def export_json(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export boards to JSON",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        payload = {
            "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "app": APP_NAME,
            "version": APP_VERSION,
            "boards": self.data.get("boards", []),
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            self.set_status(f"Exported to: {path}")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Export failed.\n\n{exc}")

    def import_json(self) -> None:
        path = filedialog.askopenfilename(
            title="Import boards from JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            boards = payload.get("boards")
            if not isinstance(boards, list) or not boards:
                raise ValueError("No boards found in JSON.")

            if not messagebox.askyesno(APP_NAME, f"Import {len(boards)} board(s)?\nThis will add to your existing boards."):
                return

            for b in boards:
                migrated = migrate_data({"boards": [b]}).get("boards", [b])[0]
                self.data["boards"].append(migrated)

            self.data["active_board_index"] = len(self.data["boards"]) - len(boards)
            self.autosave()
            self.refresh_tabs()
            self.set_status(f"Imported {len(boards)} board(s)")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Import failed.\n\n{exc}")

    # ----------------------------
    # About / close
    # ----------------------------
    def show_about(self) -> None:
        messagebox.showinfo(
            APP_NAME,
            f"{APP_NAME}\nVersion {APP_VERSION}\n\n"
            "How a button runs:\n"
            "1) If Content is not empty: it copies Content to your clipboard.\n"
            "2) If Content is empty: it opens a folder/file path or a web URL, based on the button settings.\n\n"
            "Mouse:\n"
            "Left click runs, right click edits, Shift + right click opens menu, middle click runs and closes\n\n"
            "Data stored at:\n" + self.data_path,
        )

    def on_close(self) -> None:
        self.save_data()
        self.destroy()

    def _tick(self) -> None:
        if self._last_save_ts and (now_ts() - self._last_save_ts) > 2.0:
            if self.status_var.get() == "Saved":
                self.status_var.set("Ready")
        self.after(1000, self._tick)


# ----------------------------
# Button tile widget (Canvas-based to support images)
# ----------------------------
class ButtonTile(ttk.Frame):
    def __init__(self, master: ttk.Frame, app: QuickCopyApp, btn_data: dict):
        super().__init__(master)
        self.app = app
        self.btn_data = btn_data

        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        self._menu = tk.Menu(self, tearoff=False)
        self._menu.add_command(label="Run (copy or open)", command=self.run)
        self._menu.add_command(label="Edit", command=self.edit)
        self._menu.add_separator()
        self._menu.add_command(label="Open path", command=self.open_path)
        self._menu.add_command(label="Open URL", command=self.open_url)
        self._menu.add_separator()
        self._menu.add_command(label="Delete", command=self.delete)

        # Bindings
        self.canvas.bind("<Button-1>", self.on_left_click)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Button-2>", self.on_middle_click)
        self.canvas.bind("<Enter>", self._on_hover_in)
        self.canvas.bind("<Leave>", self._on_hover_out)
        self.canvas.bind("<Configure>", lambda _e: self.redraw())

        # Make focusable for keyboard
        self.canvas.configure(takefocus=True)
        self.canvas.bind("<Return>", lambda _e: self.on_left_click())
        self.canvas.bind("<space>", lambda _e: self.on_left_click())

        # Hook for "copy focused"
        self.canvas._quickcopy_activate = self.on_left_click  # type: ignore[attr-defined]

        self._hover = False
        self._bg_photo: tk.PhotoImage | None = None
        self.redraw()

    def label_text(self) -> str:
        icon = (self.btn_data.get("icon") or "").strip()
        name = (self.btn_data.get("name") or "").strip()
        if icon and name:
            return f"{icon}  {name}"
        return name or "(Unnamed)"

    def readable_text_color(self, bg_hex: str) -> str:
        try:
            r = int(bg_hex[1:3], 16)
            g = int(bg_hex[3:5], 16)
            b = int(bg_hex[5:7], 16)
            lum = (0.2126 * r + 0.7152 * g + 0.0722 * b)
            return "#111111" if lum > 150 else "#FFFFFF"
        except Exception:
            return "#FFFFFF"

    def redraw(self) -> None:
        self.canvas.delete("all")
        w = max(1, self.canvas.winfo_width())
        h = max(1, self.canvas.winfo_height())

        color = (self.btn_data.get("color") or "#4C78A8").strip()
        bg_image = (self.btn_data.get("bg_image") or "").strip()
        mode = (self.btn_data.get("bg_mode") or "Fit").strip()

        # Background
        if bg_image:
            orig = self.app.image_cache.get_original(bg_image)
            if orig is None:
                self.canvas.create_rectangle(0, 0, w, h, fill=color, outline="")
                self._bg_photo = None
            else:
                if mode == "Tile":
                    self._bg_photo = orig
                    iw, ih = orig.width(), orig.height()
                    if iw > 0 and ih > 0:
                        x = 0
                        while x < w:
                            y = 0
                            while y < h:
                                self.canvas.create_image(x, y, image=orig, anchor="nw")
                                y += ih
                            x += iw
                    else:
                        self.canvas.create_rectangle(0, 0, w, h, fill=color, outline="")
                elif mode == "Center":
                    self._bg_photo = orig
                    self.canvas.create_rectangle(0, 0, w, h, fill=color, outline="")
                    self.canvas.create_image(w // 2, h // 2, image=orig, anchor="center")
                else:
                    scaled = self.app.image_cache.get_scaled(bg_image, w, h, mode)
                    if scaled is None:
                        self.canvas.create_rectangle(0, 0, w, h, fill=color, outline="")
                        self._bg_photo = None
                    else:
                        self._bg_photo = scaled
                        self.canvas.create_image(w // 2, h // 2, image=scaled, anchor="center")
        else:
            self.canvas.create_rectangle(0, 0, w, h, fill=color, outline="")
            self._bg_photo = None

        # Overlay label bar
        bar_h = max(32, int(h * 0.22))
        self.canvas.create_rectangle(0, 0, w, bar_h, fill="#000000", outline="")
        try:
            self.canvas.create_rectangle(0, 0, w, bar_h, fill="#000000", outline="", stipple="gray50")
        except Exception:
            pass

# Title bar is black, so always use white text for the label
        label = self.label_text()
        fg = "#FFFFFF"

        self.canvas.create_text(
            10,
            bar_h // 2,
            text=label,
            fill=fg,
            anchor="w",
            font=("Segoe UI", 11, "bold") if sys.platform.startswith("win") else ("TkDefaultFont", 11, "bold"),
        )

        tags = (self.btn_data.get("tags") or "").strip()
        if tags:
            self.canvas.create_text(
                10,
                bar_h - 6,
                text=tags,
                fill=fg,
                anchor="sw",
                font=("Segoe UI", 9) if sys.platform.startswith("win") else ("TkDefaultFont", 9),
            )

        # Small "mode" hint in the corner, helps confirm what it will do when Content is empty
        content = (self.btn_data.get("content") or "").strip()
        empty_action = (self.btn_data.get("empty_action") or "path").strip()
        if not content:
            hint = "Empty: open path" if empty_action == "path" else ("Empty: open URL" if empty_action == "url" else "Empty: nothing")
            self.canvas.create_text(
                w - 10,
                bar_h - 6,
                text=hint,
                fill=fg,
                anchor="se",
                font=("Segoe UI", 8) if sys.platform.startswith("win") else ("TkDefaultFont", 8),
            )

        if self._hover:
            self.canvas.create_rectangle(2, 2, w - 2, h - 2, outline="#111111", width=2)

    # Actions
    def run(self) -> None:
        """
        Clear, predictable behavior:
        - If Content has text: copy it to clipboard.
        - If Content is empty: open Path or URL based on 'empty_action' selection.
        """
        content = (self.btn_data.get("content") or "").strip()
        if content:
            self.app.copy_to_clipboard(content)
            self.app.set_status(f"Copied: {self.btn_data.get('name', '')}")
            return

        empty_action = (self.btn_data.get("empty_action") or "path").strip()
        if empty_action == "path":
            path = (self.btn_data.get("path") or "").strip()
            if not path:
                self.app.set_status("Nothing to do (no path set)")
                return
            open_in_file_explorer(path)
            self.app.set_status("Opened path")
            return

        if empty_action == "url":
            url = (self.btn_data.get("url") or "").strip()
            if not url:
                self.app.set_status("Nothing to do (no URL set)")
                return
            prefer_chrome = bool(self.btn_data.get("prefer_chrome", True))
            open_url(url, prefer_chrome=prefer_chrome)
            self.app.set_status("Opened URL")
            return

        self.app.set_status("Nothing to do")

    def edit(self) -> None:
        self.app.edit_button(self.btn_data)

    def delete(self) -> None:
        self.app.delete_button(self.btn_data)

    def open_path(self) -> None:
        path = (self.btn_data.get("path") or "").strip()
        if not path:
            messagebox.showinfo(APP_NAME, "No path set for this button.")
            return
        open_in_file_explorer(path)

    def open_url(self) -> None:
        url = (self.btn_data.get("url") or "").strip()
        if not url:
            messagebox.showinfo(APP_NAME, "No URL set for this button.")
            return
        prefer_chrome = bool(self.btn_data.get("prefer_chrome", True))
        open_url(url, prefer_chrome=prefer_chrome)

    # Click handlers
    def on_left_click(self, _event: tk.Event | None = None) -> None:
        if self.app.edit_mode.get():
            self.edit()
        else:
            self.run()

    def on_right_click(self, event: tk.Event) -> None:
        if event.state & 0x0001:
            try:
                self._menu.tk_popup(event.x_root, event.y_root)
            finally:
                self._menu.grab_release()
        else:
            self.edit()

    def on_middle_click(self, _event: tk.Event) -> None:
        self.run()
        self.app.on_close()

    def _on_hover_in(self, _e: tk.Event) -> None:
        self._hover = True
        self.redraw()

    def _on_hover_out(self, _e: tk.Event) -> None:
        self._hover = False
        self.redraw()


# ----------------------------
# Dialog helpers
# ----------------------------
def simple_text_prompt(parent: tk.Tk, title: str, label: str, initial: str) -> str | None:
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.transient(parent)
    dlg.grab_set()

    body = ttk.Frame(dlg, padding=(12, 12))
    body.pack(fill="both", expand=True)

    ttk.Label(body, text=label).pack(anchor="w")
    var = tk.StringVar(value=initial)
    entry = ttk.Entry(body, textvariable=var, width=40)
    entry.pack(fill="x", pady=(6, 10))
    entry.focus_set()
    entry.selection_range(0, tk.END)

    result: dict[str, str | None] = {"value": None}

    btns = ttk.Frame(body)
    btns.pack(fill="x")
    ttk.Button(btns, text="Cancel", command=lambda: (result.__setitem__("value", None), dlg.destroy())).pack(side="right")
    ttk.Button(btns, text="OK", command=lambda: (result.__setitem__("value", var.get().strip()), dlg.destroy())).pack(
        side="right", padx=(0, 8)
    )

    dlg.bind("<Escape>", lambda _e: (result.__setitem__("value", None), dlg.destroy()))
    dlg.bind("<Return>", lambda _e: (result.__setitem__("value", var.get().strip()), dlg.destroy()))

    center_window(dlg, 420, 160)
    parent.wait_window(dlg)
    return result["value"]


# ----------------------------
# Button Editor Dialog
# ----------------------------
class ButtonEditorDialog(tk.Toplevel):
    BG_MODES = ["Stretch", "Fit", "Fill", "Tile", "Center"]
    EMPTY_ACTIONS = [("path", "Open Windows path"), ("url", "Open web URL"), ("none", "Do nothing")]

    def __init__(self, parent: QuickCopyApp, title: str, initial: dict | None, allow_delete: bool):
        super().__init__(parent)
        self.parent = parent
        self.title(title)
        self.transient(parent)
        self.grab_set()

        self.result: dict | None = None
        self.deleted = False
        self.allow_delete = allow_delete

        pad = 12
        root = ttk.Frame(self, padding=(pad, pad, pad, pad))
        root.pack(fill="both", expand=True)

        # Fields
        self.var_name = tk.StringVar(value=(initial.get("name") if initial else "New button"))
        self.var_icon = tk.StringVar(value=(initial.get("icon") if initial else "📌"))
        self.var_color = tk.StringVar(value=(initial.get("color") if initial else "#4C78A8"))
        self.var_tags = tk.StringVar(value=(initial.get("tags") if initial else ""))

        self.var_path = tk.StringVar(value=(initial.get("path") if initial else ""))
        self.var_url = tk.StringVar(value=(initial.get("url") if initial else ""))
        self.var_prefer_chrome = tk.BooleanVar(value=bool(initial.get("prefer_chrome", True)) if initial else True)
        self.var_empty_action = tk.StringVar(value=(initial.get("empty_action") if initial else "path"))

        self.var_bg_image = tk.StringVar(value=(initial.get("bg_image") if initial else ""))
        self.var_bg_mode = tk.StringVar(value=(initial.get("bg_mode") if initial else "Fit"))

        ttk.Label(root, text="Name").grid(row=0, column=0, sticky="w")
        ttk.Entry(root, textvariable=self.var_name).grid(row=1, column=0, sticky="ew", padx=(0, 8))

        ttk.Label(root, text="Icon").grid(row=0, column=1, sticky="w")
        icon_row = ttk.Frame(root)
        icon_row.grid(row=1, column=1, sticky="ew")
        ttk.Entry(icon_row, textvariable=self.var_icon, width=8).pack(side="left")
        ttk.Button(icon_row, text="Pick", style="Toolbutton.TButton", command=self.pick_icon).pack(side="left", padx=(8, 0))

        ttk.Label(root, text="Color").grid(row=2, column=0, sticky="w", pady=(10, 0))
        color_row = ttk.Frame(root)
        color_row.grid(row=3, column=0, sticky="ew", padx=(0, 8))
        ttk.Entry(color_row, textvariable=self.var_color).pack(side="left", fill="x", expand=True)
        ttk.Button(color_row, text="Pick", style="Toolbutton.TButton", command=self.pick_color).pack(side="left", padx=(8, 0))

        ttk.Label(root, text="Tags (comma or space separated)").grid(row=2, column=1, sticky="w", pady=(10, 0))
        ttk.Entry(root, textvariable=self.var_tags).grid(row=3, column=1, sticky="ew")

        # ---- Path + URL section ----
        ttk.Label(root, text="When Content is empty, the button will open one of these:").grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(12, 4)
        )

        choice_box = ttk.LabelFrame(root, text="Empty-content action", padding=(10, 8))
        choice_box.grid(row=5, column=0, columnspan=2, sticky="ew")

        for i, (val, label) in enumerate(self.EMPTY_ACTIONS):
            ttk.Radiobutton(
                choice_box,
                text=label,
                value=val,
                variable=self.var_empty_action,
                command=self._on_empty_action_changed,
            ).grid(row=0, column=i, sticky="w", padx=(0, 16))

        # Path row
        ttk.Label(root, text="Windows path (folder or file)").grid(row=6, column=0, sticky="w", pady=(10, 0))
        path_row = ttk.Frame(root)
        path_row.grid(row=7, column=0, columnspan=2, sticky="ew")
        ttk.Entry(path_row, textvariable=self.var_path).pack(side="left", fill="x", expand=True)
        ttk.Button(path_row, text="Browse", style="Toolbutton.TButton", command=self.browse_path).pack(side="left", padx=(8, 0))
        ttk.Button(path_row, text="Open", style="Toolbutton.TButton", command=self.open_path_now).pack(side="left", padx=(8, 0))

        # URL row
        ttk.Label(root, text="Web address (URL)").grid(row=8, column=0, sticky="w", pady=(10, 0))
        url_row = ttk.Frame(root)
        url_row.grid(row=9, column=0, columnspan=2, sticky="ew")
        ttk.Entry(url_row, textvariable=self.var_url).pack(side="left", fill="x", expand=True)
        ttk.Button(url_row, text="Open", style="Toolbutton.TButton", command=self.open_url_now).pack(side="left", padx=(8, 0))

        ttk.Checkbutton(
            root,
            text="Prefer Chrome (if available) when opening URL",
            variable=self.var_prefer_chrome,
        ).grid(row=10, column=0, columnspan=2, sticky="w", pady=(6, 0))

        # ---- Background image controls ----
        ttk.Label(root, text="Background image (optional)").grid(row=11, column=0, sticky="w", pady=(12, 0))
        img_row = ttk.Frame(root)
        img_row.grid(row=12, column=0, columnspan=2, sticky="ew")

        ttk.Entry(img_row, textvariable=self.var_bg_image).pack(side="left", fill="x", expand=True)
        ttk.Button(img_row, text="Load image", style="Toolbutton.TButton", command=self.browse_image).pack(side="left", padx=(8, 0))
        ttk.Button(img_row, text="Clear", style="Toolbutton.TButton", command=self.clear_image).pack(side="left", padx=(8, 0))

        mode_row = ttk.Frame(root)
        mode_row.grid(row=13, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Label(mode_row, text="Display mode:").pack(side="left")
        mode = ttk.Combobox(mode_row, textvariable=self.var_bg_mode, values=self.BG_MODES, state="readonly", width=10)
        mode.pack(side="left", padx=(6, 0))
        mode.bind("<<ComboboxSelected>>", lambda _e: self.refresh_preview())

        ttk.Label(mode_row, text="Tip: PNG/GIF/PPM work. JPG needs external libraries.").pack(side="left", padx=(12, 0))

        ttk.Label(root, text="Preview").grid(row=14, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.preview = tk.Canvas(root, height=140, highlightthickness=1, highlightbackground="#888888")
        self.preview.grid(row=15, column=0, columnspan=2, sticky="nsew", pady=(6, 0))
        self._preview_photo: tk.PhotoImage | None = None
        self.preview.bind("<Configure>", lambda _e: self.refresh_preview())

        # ---- Content ----
        ttk.Label(root, text="Content (copied to clipboard when not empty)").grid(
            row=16, column=0, columnspan=2, sticky="w", pady=(12, 0)
        )
        self.txt = tk.Text(root, height=10, wrap="word", undo=True)
        self.txt.grid(row=17, column=0, columnspan=2, sticky="nsew", pady=(6, 0))
        self.txt.insert("1.0", initial.get("content", "") if initial else "")

        clip_row = ttk.Frame(root)
        clip_row.grid(row=18, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(clip_row, text="Paste clipboard into content", command=self.paste_clipboard).pack(side="left")

        # Buttons
        btns = ttk.Frame(root)
        btns.grid(row=19, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        btns.columnconfigure(0, weight=1)

        if self.allow_delete:
            ttk.Button(btns, text="Delete", command=self.do_delete).pack(side="left")

        ttk.Button(btns, text="Cancel", command=self.close).pack(side="right")
        ttk.Button(btns, text="Save", command=self.do_save).pack(side="right", padx=(0, 8))

        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=0)
        root.rowconfigure(17, weight=1)

        self._id = initial.get("id") if initial else f"btn_{int(now_ts() * 1000)}"

        self.bind("<Escape>", lambda _e: self.close())

        center_window(self, 820, 900)
        self._on_empty_action_changed()
        self.refresh_preview()
        self.wait_window(self)

    def _on_empty_action_changed(self) -> None:
        # Visual cue only, no disabling so you can fill both fields if you want.
        self.refresh_preview()

    def pick_icon(self) -> None:
        dlg = IconPickerDialog(self, initial=self.var_icon.get().strip() or "📌")
        if dlg.result:
            self.var_icon.set(dlg.result)
            self.refresh_preview()

    def pick_color(self) -> None:
        color = colorchooser.askcolor(title="Pick a color")
        if color and color[1]:
            self.var_color.set(color[1])
            self.refresh_preview()

    def browse_path(self) -> None:
        path = filedialog.askdirectory(title="Choose folder")
        if path:
            self.var_path.set(path)

    def open_path_now(self) -> None:
        p = self.var_path.get().strip()
        if not p:
            messagebox.showinfo(APP_NAME, "No path entered.")
            return
        open_in_file_explorer(p)

    def open_url_now(self) -> None:
        u = self.var_url.get().strip()
        if not u:
            messagebox.showinfo(APP_NAME, "No URL entered.")
            return
        open_url(u, prefer_chrome=self.var_prefer_chrome.get())

    def browse_image(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose background image",
            filetypes=[
                ("Supported images (PNG, GIF, PPM/PGM)", "*.png *.gif *.ppm *.pgm"),
                ("PNG", "*.png"),
                ("GIF", "*.gif"),
                ("PPM/PGM", "*.ppm *.pgm"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.var_bg_image.set(path)
            self.refresh_preview()

    def clear_image(self) -> None:
        self.var_bg_image.set("")
        self.refresh_preview()

    def paste_clipboard(self) -> None:
        try:
            text = self.parent.clipboard_get()
        except Exception:
            text = ""
        if text:
            self.txt.delete("1.0", tk.END)
            self.txt.insert("1.0", text)

    def refresh_preview(self) -> None:
        self.preview.delete("all")
        w = max(1, self.preview.winfo_width())
        h = max(1, self.preview.winfo_height())

        color = (self.var_color.get().strip() or "#4C78A8")
        bg_image = (self.var_bg_image.get().strip() or "")
        mode = (self.var_bg_mode.get().strip() or "Fit")

        if bg_image:
            orig = self.parent.image_cache.get_original(bg_image)
            if orig is None:
                self.preview.create_rectangle(0, 0, w, h, fill=color, outline="")
                self._preview_photo = None
                self.preview.create_text(w // 2, h // 2, text="Image not found or unsupported format", fill="#FFFFFF")
            else:
                if mode == "Tile":
                    self._preview_photo = orig
                    iw, ih = orig.width(), orig.height()
                    if iw > 0 and ih > 0:
                        x = 0
                        while x < w:
                            y = 0
                            while y < h:
                                self.preview.create_image(x, y, image=orig, anchor="nw")
                                y += ih
                            x += iw
                elif mode == "Center":
                    self._preview_photo = orig
                    self.preview.create_rectangle(0, 0, w, h, fill=color, outline="")
                    self.preview.create_image(w // 2, h // 2, image=orig, anchor="center")
                else:
                    scaled = self.parent.image_cache.get_scaled(bg_image, w, h, mode)
                    if scaled is None:
                        self.preview.create_rectangle(0, 0, w, h, fill=color, outline="")
                        self._preview_photo = None
                    else:
                        self._preview_photo = scaled
                        self.preview.create_image(w // 2, h // 2, image=scaled, anchor="center")
        else:
            self.preview.create_rectangle(0, 0, w, h, fill=color, outline="")
            self._preview_photo = None

        label = self.var_icon.get().strip()
        name = self.var_name.get().strip()
        text = f"{label}  {name}".strip()
        bar_h = max(30, int(h * 0.24))
        self.preview.create_rectangle(0, 0, w, bar_h, fill="#000000", outline="")
        try:
            self.preview.create_rectangle(0, 0, w, bar_h, fill="#000000", outline="", stipple="gray50")
        except Exception:
            pass
        self.preview.create_text(10, bar_h // 2, text=text or "(Unnamed)", fill="#FFFFFF", anchor="w")

        # Show the rule, so it is always clear
        empty_action = self.var_empty_action.get().strip()
        rule = "If Content has text: copy it. If Content is empty: open path."
        if empty_action == "url":
            rule = "If Content has text: copy it. If Content is empty: open URL."
        elif empty_action == "none":
            rule = "If Content has text: copy it. If Content is empty: do nothing."
        self.preview.create_text(
            w - 10,
            bar_h // 2,
            text=rule,
            fill="#FFFFFF",
            anchor="e",
            font=("Segoe UI", 8) if sys.platform.startswith("win") else ("TkDefaultFont", 8),
        )

        if mode == "Stretch":
            self.preview.create_text(
                w - 10,
                bar_h - 6,
                text="Stretch uses Fill",
                fill="#FFFFFF",
                anchor="se",
                font=("Segoe UI", 8) if sys.platform.startswith("win") else ("TkDefaultFont", 8),
            )

    def do_save(self) -> None:
        name = self.var_name.get().strip() or "Unnamed"
        icon = self.var_icon.get().strip()
        color = self.var_color.get().strip() or "#4C78A8"
        tags = self.var_tags.get().strip()

        path = self.var_path.get().strip()
        url = self.var_url.get().strip()
        prefer_chrome = bool(self.var_prefer_chrome.get())
        empty_action = self.var_empty_action.get().strip() or "path"

        content = self.txt.get("1.0", tk.END).rstrip("\n")

        bg_image = self.var_bg_image.get().strip()
        bg_mode = self.var_bg_mode.get().strip() or "Fit"

        self.result = {
            "id": self._id,
            "name": name,
            "icon": icon,
            "color": color,
            "tags": tags,
            "path": path,
            "url": url,
            "prefer_chrome": prefer_chrome,
            "empty_action": empty_action,
            "content": content,
            "bg_image": bg_image,
            "bg_mode": bg_mode,
        }
        self.destroy()

    def do_delete(self) -> None:
        if messagebox.askyesno(APP_NAME, "Delete this button?"):
            self.deleted = True
            self.destroy()

    def close(self) -> None:
        self.result = None
        self.destroy()


# ----------------------------
# Shortcut Manager
# ----------------------------
class ShortcutManagerDialog(tk.Toplevel):
    ACTIONS = [
        ("copy_focused", "Run focused button", "Example: <Return>"),
        ("copy_focused_alt", "Run focused button (alt)", "Example: <space>"),
        ("find", "Focus search", "Example: <Control-f>"),
        ("new_button", "New button", "Example: <Control-n>"),
        ("save", "Save", "Example: <Control-s>"),
        ("toggle_edit_mode", "Toggle edit mode", "Example: <Control-e>"),
        ("toggle_compact", "Toggle compact palette", "Example: <Control-p>"),
        ("open_shortcut_manager", "Open shortcut manager", "Example: <Control-k>"),
    ]

    def __init__(self, parent: QuickCopyApp):
        super().__init__(parent)
        self.parent = parent
        self.title("Shortcut manager")
        self.transient(parent)
        self.grab_set()

        root = ttk.Frame(self, padding=(12, 12))
        root.pack(fill="both", expand=True)

        ttk.Label(root, text="Edit keyboard shortcuts (Tk binding syntax). Changes apply immediately.").pack(anchor="w")

        table = ttk.Frame(root)
        table.pack(fill="both", expand=True, pady=(10, 0))

        self.vars: dict[str, tk.StringVar] = {}

        for r, (key, label, hint) in enumerate(self.ACTIONS):
            ttk.Label(table, text=label).grid(row=r, column=0, sticky="w", padx=(0, 10), pady=6)
            var = tk.StringVar(value=self.parent.data["shortcuts"].get(key, ""))
            self.vars[key] = var
            ttk.Entry(table, textvariable=var, width=24).grid(row=r, column=1, sticky="w", pady=6)
            ttk.Label(table, text=hint).grid(row=r, column=2, sticky="w", padx=(10, 0), pady=6)

        table.columnconfigure(0, weight=1)

        btns = ttk.Frame(root)
        btns.pack(fill="x", pady=(12, 0))

        ttk.Button(btns, text="Reset defaults", command=self.reset_defaults).pack(side="left")
        ttk.Button(btns, text="Close", command=self.apply_and_close).pack(side="right")
        ttk.Button(btns, text="Apply", command=self.apply).pack(side="right", padx=(0, 8))

        center_window(self, 720, 360)
        self.wait_window(self)

    def reset_defaults(self) -> None:
        defaults = default_data()["shortcuts"]
        for k, var in self.vars.items():
            var.set(defaults.get(k, ""))

    def apply(self) -> None:
        try:
            for k, var in self.vars.items():
                binding = var.get().strip()
                if not binding:
                    raise ValueError(f"Shortcut for '{k}' cannot be empty.")
                self.parent.bind_all(binding, lambda _e: None)
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Invalid shortcut binding.\n\n{exc}")
            return

        for k, var in self.vars.items():
            self.parent.data["shortcuts"][k] = var.get().strip()

        self.parent.apply_shortcuts()
        self.parent.autosave()
        self.parent.set_status("Shortcuts updated")

    def apply_and_close(self) -> None:
        self.apply()
        self.destroy()


# ----------------------------
# Entry point
# ----------------------------
def main() -> None:
    app = QuickCopyApp()
    app.mainloop()


if __name__ == "__main__":
    main()