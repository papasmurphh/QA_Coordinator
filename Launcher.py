import base64
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
import webbrowser
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

APP_NAME = "QuickLaunch Profiles"
CONFIG_FILE = Path.home() / ".quicklaunch_profiles.json"

# -------------------------
# Embedded base64 icons
# -------------------------
run_icon_b64 = (
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAA21BMVEUAAAB"
    "wcHB0dHR3d3eAgICMjIyTk5OUlJSTk5OTk5OTk5Obm5uYmJiQkJCUlJSVlZWTk5OTk5OTk5OTk5OampqSkpKVlZWXl5eTk5OTk5OTk5OcnJyXl5eYmJiTk5OTk5OTk5OampqTk5O"
    "Tk5OTk5OUlJSUlJSTk5OTk5OTk5OTk5OTk5OcnJyTk5OTk5OTk5OTk5OTk5OTk5OTk5OTk5OTk5OAAAAAADd4r3bAAAAJHRSTlMAAQMIBQwQFhkaISQxQFJmcIGQp7C3wMTH2uXy"
    "9f7////x8U3u8xwAAABiSURBVBjTY2AgD2BkYGBgYGRgYICJgYGBkYFBAQhYAAy0AUVQwMBQGqg2EwMBQZ2BLgSBbBB2g8JrAwCFYJWA2gQySgYQmCkqOQ0QyqC4gkEoYh0YgJCi"
    "ZC4nQKAA0r0Y8Y8J9dAAAAAElFTkSuQmCC"
)
gear_icon_b64 = (
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAA21BMVEUA"
    "AABwcHB0dHR3d3eAgICMjIyTk5OUlJSTk5OTk5OTk5Obm5uYmJiQkJCUlJSVlZWTk5OTk5OTk5OTk5OampqSkpKVlZWXl5eTk5OTk5OTk5OcnJyXl5eYmJiTk5OTk5OTk5Oampq"
    "Tk5OTk5OTk5OUlJSUlJSTk5OTk5OTk5OTk5OTk5OcnJyTk5OTk5OTk5OTk5OTk5OTk5OTk5OTk5OTk5OAAAAAADd4r3bAAAAJHRSTlMAAQMIBQwQFhkaISQxQFJmcIGQp7C3wMTH"
    "2uXy9f7////x8U3u8xwAAABfSURBVBjTY2AgD2BkYGBgYGRgYICJgYGBkYFBAQhYAAy0AUXRwcHBgapwGg4ODoYgG2g8JrAwCFYJWA2gQySgYQmCkqOQ0QyqC4gkEoYh0YgJCiZ"
    "C4nQKAA2eYYk7o0mQAAAAASUVORK5CYII="
)

def load_icon(b64: str) -> tk.PhotoImage:
    return tk.PhotoImage(data=base64.b64decode(b64))

# -------------------------
# Data Model
# -------------------------
@dataclass
class Step:
    kind: str                  # "program", "folder", "url"
    path_or_url: str
    args: str = ""
    screen_index: int = 0
    anchor: str = "top-right"  # "top-left", "top-right", "bottom-left", "bottom-right", "center"
    width_ratio: float = 0.5
    height_ratio: float = 0.5
    delay_before_move_ms: int = 400
    try_place: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Step":
        return Step(**d)

@dataclass
class Profile:
    name: str
    steps: List[Step] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "steps": [s.to_dict() for s in self.steps]}

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Profile":
        return Profile(name=d["name"], steps=[Step.from_dict(x) for x in d.get("steps", [])])

# -------------------------
# Persistence
# -------------------------
def load_profiles() -> List[Profile]:
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return [Profile.from_dict(p) for p in data.get("profiles", [])]
        except Exception:
            messagebox.showwarning(APP_NAME, "Could not read the profiles file, starting with a fresh list.")
    return []

def save_profiles(profiles: List[Profile]) -> None:
    CONFIG_FILE.write_text(json.dumps({"profiles": [p.to_dict() for p in profiles]}, indent=2), encoding="utf-8")

# -------------------------
# Platform helpers
# -------------------------
def is_windows() -> bool:
    return platform.system().lower() == "windows"

def is_macos() -> bool:
    return platform.system().lower() == "darwin"

def is_linux() -> bool:
    return platform.system().lower() == "linux"

def which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)

# -------------------------
# Launchers
# -------------------------
def launch_step(step: Step) -> Tuple[Optional[int], Optional[str]]:
    try:
        if step.kind == "program":
            if is_windows():
                proc = subprocess.Popen([step.path_or_url, *step.args.split()] if step.args.strip() else [step.path_or_url], shell=False)
                return proc.pid, Path(step.path_or_url).stem
            elif is_macos():
                if step.path_or_url.endswith(".app"):
                    cmd = ["open", "-a", step.path_or_url]
                    if step.args.strip():
                        cmd += ["--args", *step.args.split()]
                    subprocess.Popen(cmd)
                    return None, Path(step.path_or_url).stem
                proc = subprocess.Popen([step.path_or_url, *step.args.split()] if step.args.strip() else [step.path_or_url])
                return proc.pid, Path(step.path_or_url).stem
            else:
                proc = subprocess.Popen([step.path_or_url, *step.args.split()] if step.args.strip() else [step.path_or_url])
                return proc.pid, Path(step.path_or_url).stem

        if step.kind == "folder":
            target = step.path_or_url
            if is_windows():
                os.startfile(target)  # type: ignore[attr-defined]
                return None, "Explorer"
            if is_macos():
                subprocess.Popen(["open", target])
                return None, "Finder"
            if which("xdg-open"):
                subprocess.Popen(["xdg-open", target])
            else:
                webbrowser.open(f"file://{Path(target).resolve()}")
            return None, None

        if step.kind == "url":
            webbrowser.open(step.path_or_url)
            return None, None
    except Exception as e:
        messagebox.showerror(APP_NAME, f"Failed to launch:\n{step.path_or_url}\n\n{e}")
    return None, None

# -------------------------
# Window placement
# -------------------------
def get_screens_geometry(root: tk.Tk) -> List[Tuple[int, int, int, int]]:
    if is_windows():
        try:
            import ctypes
            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
            class MONITORINFOEX(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECT), ("rcWork", RECT), ("dwFlags", ctypes.c_ulong), ("szDevice", ctypes.c_wchar * 32)]
            monitors: List[Tuple[int, int, int, int]] = []
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            MonitorEnumProc = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(RECT), ctypes.c_double)
            def _cb(hMon, hdc, rect_ptr, data):
                mi = MONITORINFOEX()
                mi.cbSize = ctypes.sizeof(MONITORINFOEX)
                user32.GetMonitorInfoW(hMon, ctypes.byref(mi))
                x, y = mi.rcWork.left, mi.rcWork.top
                w = mi.rcWork.right - mi.rcWork.left
                h = mi.rcWork.bottom - mi.rcWork.top
                monitors.append((x, y, w, h))
                return 1
            user32.EnumDisplayMonitors(0, 0, MonitorEnumProc(_cb), 0)
            if monitors:
                return monitors
        except Exception:
            pass
    return [(0, 0, root.winfo_screenwidth(), root.winfo_screenheight())]

def compute_anchor_rect(screen_rect: Tuple[int, int, int, int], anchor: str, width_ratio: float, height_ratio: float) -> Tuple[int, int, int, int]:
    sx, sy, sw, sh = screen_rect
    w = max(200, int(sw * max(0.2, min(1.0, width_ratio))))
    h = max(160, int(sh * max(0.2, min(1.0, height_ratio))))
    if anchor == "top-left":
        x, y = sx, sy
    elif anchor == "top-right":
        x, y = sx + sw - w, sy
    elif anchor == "bottom-left":
        x, y = sx, sy + sh - h
    elif anchor == "bottom-right":
        x, y = sx + sw - w, sy + sh - h
    else:
        x = sx + (sw - w) // 2
        y = sy + (sh - h) // 2
    return x, y, w, h

def place_window(step: Step, screens: List[Tuple[int, int, int, int]], app_hint: Optional[str], pid: Optional[int]) -> None:
    if not step.try_place:
        return
    if step.screen_index < 0 or step.screen_index >= len(screens):
        return
    time.sleep(max(0, step.delay_before_move_ms) / 1000.0)
    target_rect = compute_anchor_rect(screens[step.screen_index], step.anchor, step.width_ratio, step.height_ratio)
    if is_windows():
        _place_window_windows(pid, target_rect)
    elif is_macos():
        _place_window_macos(app_hint, target_rect)
    elif is_linux():
        _place_window_linux(pid, target_rect)

def _place_window_windows(pid: Optional[int], rect: Tuple[int, int, int, int]) -> None:
    if pid is None:
        return
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        EnumWindows = user32.EnumWindows
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        IsWindowVisible = user32.IsWindowVisible
        GetWindowThreadProcessId = user32.GetWindowThreadProcessId
        MoveWindow = user32.MoveWindow
        hwnds = []
        def cb(hwnd, lParam):
            if IsWindowVisible(hwnd):
                _pid = ctypes.c_ulong()
                GetWindowThreadProcessId(hwnd, ctypes.byref(_pid))
                if _pid.value == pid:
                    hwnds.append(hwnd)
            return True
        EnumWindows(EnumWindowsProc(cb), 0)
        if not hwnds:
            return
        x, y, w, h = rect
        MoveWindow(hwnds[0], x, y, w, h, True)
    except Exception:
        pass

def _place_window_macos(app_hint: Optional[str], rect: Tuple[int, int, int, int]) -> None:
    try:
        x, y, w, h = rect
        appname = app_hint or ""
        if appname.lower() == "explorer":
            appname = "Finder"
        if appname:
            script = f'''
            tell application "{appname}" to activate
            tell application "System Events"
                tell process "{appname}"
                    try
                        set position of window 1 to {{{x}, {y}}}
                        set size of window 1 to {{{w}, {h}}}
                    end try
                end tell
            end tell
            '''
        else:
            script = f'''
            tell application "System Events"
                tell (first application process whose frontmost is true)
                    try
                        set position of window 1 to {{{x}, {y}}}
                        set size of window 1 to {{{w}, {h}}}
                    end try
                end tell
            end tell
            '''
        subprocess.run(["osascript", "-e", script], check=False)
    except Exception:
        pass

def _place_window_linux(pid: Optional[int], rect: Tuple[int, int, int, int]) -> None:
    if not which("wmctrl") or pid is None:
        return
    try:
        x, y, w, h = rect
        out = subprocess.check_output(["wmctrl", "-lp"]).decode("utf-8", "ignore").splitlines()
        win_ids = []
        for line in out:
            parts = line.split()
            if len(parts) >= 3:
                try:
                    if int(parts[2]) == pid:
                        win_ids.append(parts[0])
                except ValueError:
                    pass
        if not win_ids:
            return
        subprocess.call(["wmctrl", "-ir", win_ids[0], "-e", f"0,{x},{y},{w},{h}"])
    except Exception:
        pass

# -------------------------
# UI utilities
# -------------------------
class ToolTip:
    def __init__(self, widget: tk.Widget, text: str, delay_ms: int = 500):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._id = None
        self.tip = None
        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self._unschedule)

    def _schedule(self, _):
        self._id = self.widget.after(self.delay_ms, self._show)

    def _unschedule(self, _):
        if self._id:
            self.widget.after_cancel(self._id)
            self._id = None
        if self.tip:
            self.tip.destroy()
            self.tip = None

    def _show(self):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        ttk.Label(tw, text=self.text, padding=(8, 4)).pack()

def ask_yes_no(title: str, message: str) -> bool:
    return messagebox.askyesno(title, message, icon="question")

# -------------------------
# Dialogs
# -------------------------
class StepDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk, step: Optional[Step] = None):
        super().__init__(parent)
        self.title("Edit Step")
        self.resizable(False, False)
        self.result: Optional[Step] = None

        self.kind_var = tk.StringVar(value=(step.kind if step else "program"))
        self.path_var = tk.StringVar(value=(step.path_or_url if step else ""))
        self.args_var = tk.StringVar(value=(step.args if step else ""))
        self.screen_var = tk.IntVar(value=(step.screen_index if step else 0))
        self.anchor_var = tk.StringVar(value=(step.anchor if step else "top-right"))
        self.wratio_var = tk.DoubleVar(value=(step.width_ratio if step else 0.5))
        self.hratio_var = tk.DoubleVar(value=(step.height_ratio if step else 0.5))
        self.delay_var = tk.IntVar(value=(step.delay_before_move_ms if step else 400))
        self.place_var = tk.BooleanVar(value=(step.try_place if step else True))

        frm = ttk.Frame(self, padding=12)
        frm.grid(row=0, column=0, sticky="nsew")

        row = 0
        ttk.Label(frm, text="Type").grid(row=row, column=0, sticky="w")
        ttk.Combobox(frm, textvariable=self.kind_var, values=["program", "folder", "url"], state="readonly", width=12).grid(row=row, column=1, sticky="ew", padx=6, pady=4)
        row += 1

        ttk.Label(frm, text="Program or path or URL").grid(row=row, column=0, sticky="w")
        ent_path = ttk.Entry(frm, textvariable=self.path_var, width=48)
        ent_path.grid(row=row, column=1, columnspan=2, sticky="ew", padx=6, pady=4)
        ttk.Button(frm, text="Browse", command=self._browse).grid(row=row, column=3, sticky="ew")
        row += 1

        ttk.Label(frm, text="Arguments").grid(row=row, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.args_var).grid(row=row, column=1, columnspan=3, sticky="ew", padx=6, pady=4)
        row += 1

        ttk.Separator(frm).grid(row=row, column=0, columnspan=4, sticky="ew", pady=(6, 6))
        row += 1

        ttk.Checkbutton(frm, text="Try to place window after launch", variable=self.place_var).grid(row=row, column=0, columnspan=4, sticky="w")
        row += 1

        ttk.Label(frm, text="Screen index").grid(row=row, column=0, sticky="w")
        ttk.Spinbox(frm, from_=0, to=8, textvariable=self.screen_var, width=6).grid(row=row, column=1, sticky="w", padx=6, pady=4)
        row += 1

        ttk.Label(frm, text="Anchor").grid(row=row, column=0, sticky="w")
        ttk.Combobox(frm, textvariable=self.anchor_var, values=["top-left", "top-right", "bottom-left", "bottom-right", "center"], state="readonly", width=14).grid(row=row, column=1, sticky="w", padx=6, pady=4)
        row += 1

        ttk.Label(frm, text="Width ratio").grid(row=row, column=0, sticky="w")
        ttk.Scale(frm, from_=0.2, to=1.0, orient="horizontal", variable=self.wratio_var).grid(row=row, column=1, sticky="ew", padx=6)
        ttk.Label(frm, textvariable=self.wratio_var, width=6).grid(row=row, column=2, sticky="w")
        row += 1

        ttk.Label(frm, text="Height ratio").grid(row=row, column=0, sticky="w")
        ttk.Scale(frm, from_=0.2, to=1.0, orient="horizontal", variable=self.hratio_var).grid(row=row, column=1, sticky="ew", padx=6)
        ttk.Label(frm, textvariable=self.hratio_var, width=6).grid(row=row, column=2, sticky="w")
        row += 1

        ttk.Label(frm, text="Delay before move, ms").grid(row=row, column=0, sticky="w")
        ttk.Spinbox(frm, from_=0, to=5000, increment=100, textvariable=self.delay_var, width=8).grid(row=row, column=1, sticky="w", padx=6, pady=4)
        row += 1

        btns = ttk.Frame(frm)
        btns.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        ttk.Button(btns, text="OK", command=self._ok).pack(side="left")
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="left", padx=6)

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self.transient(parent)
        self.grab_set()
        self.wait_visibility()
        self.focus_set()

    def _browse(self):
        k = self.kind_var.get()
        if k == "program":
            if is_windows():
                p = filedialog.askopenfilename(title="Select program", filetypes=[("Executables", "*.exe;*.bat;*.cmd;*.com"), ("All files", "*.*")])
            elif is_macos():
                p = filedialog.askopenfilename(title="Select app or executable", filetypes=[("Applications", "*.app"), ("All files", "*.*")])
            else:
                p = filedialog.askopenfilename(title="Select executable", filetypes=[("All files", "*.*")])
            if p:
                self.path_var.set(p)
        elif k == "folder":
            d = filedialog.askdirectory(title="Select folder")
            if d:
                self.path_var.set(d)

    def _ok(self):
        target = self.path_var.get().strip()
        if not target:
            messagebox.showerror(APP_NAME, "Path or URL is required.")
            return
        self.result = Step(
            kind=self.kind_var.get(),
            path_or_url=target,
            args=self.args_var.get().strip(),
            screen_index=max(0, self.screen_var.get()),
            anchor=self.anchor_var.get(),
            width_ratio=float(self.wratio_var.get()),
            height_ratio=float(self.hratio_var.get()),
            delay_before_move_ms=int(self.delay_var.get()),
            try_place=bool(self.place_var.get()),
        )
        self.destroy()

class ProfileDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk, profile: Optional[Profile] = None):
        super().__init__(parent)
        self.title("Edit Profile")
        self.resizable(True, True)
        self.result: Optional[Profile] = None
        self.steps: List[Step] = list(profile.steps) if profile else []
        name_val = profile.name if profile else "New Profile"
        self.name_var = tk.StringVar(value=name_val)

        frm = ttk.Frame(self, padding=12)
        frm.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        ttk.Label(frm, text="Profile name").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.name_var, width=40).grid(row=0, column=1, columnspan=3, sticky="ew", padx=6, pady=(0, 6))

        self.tree = ttk.Treeview(frm, columns=("type", "target", "args", "place"), show="headings", height=10)
        for col, txt, w in [("type", "Type", 80), ("target", "Target", 360), ("args", "Args", 140), ("place", "Placement", 220)]:
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=w, anchor="w", stretch=(col != "type"))
        self.tree.grid(row=1, column=0, columnspan=4, sticky="nsew")
        frm.rowconfigure(1, weight=1)
        frm.columnconfigure(3, weight=1)

        sb = ttk.Scrollbar(frm, orient="vertical", command=self.tree.yview)
        sb.grid(row=1, column=4, sticky="ns")
        self.tree.configure(yscroll=sb.set)

        btns = ttk.Frame(frm)
        btns.grid(row=2, column=0, columnspan=4, sticky="w", pady=8)
        b_add = ttk.Button(btns, text="Add Step", command=self._add_step)
        b_edit = ttk.Button(btns, text="Edit Step", command=self._edit_step)
        b_del = ttk.Button(btns, text="Remove Step", command=self._del_step)
        b_up = ttk.Button(btns, text="Move Up", command=lambda: self._move(-1))
        b_dn = ttk.Button(btns, text="Move Down", command=lambda: self._move(1))
        for w in (b_add, b_edit, b_del, b_up, b_dn):
            w.pack(side="left", padx=(0, 6))

        row3 = ttk.Frame(frm)
        row3.grid(row=3, column=0, columnspan=4, sticky="ew")
        ttk.Button(row3, text="OK", command=self._ok).pack(side="left")
        ttk.Button(row3, text="Cancel", command=self.destroy).pack(side="left", padx=6)

        self._refresh_tree()

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self.transient(parent)
        self.grab_set()
        self.wait_visibility()
        self.focus_set()

    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for idx, s in enumerate(self.steps):
            place = f"{'yes' if s.try_place else 'no'} @ screen {s.screen_index}, {s.anchor}, {s.width_ratio:.2f}×{s.height_ratio:.2f}, delay {s.delay_before_move_ms} ms"
            self.tree.insert("", "end", iid=str(idx), values=(s.kind, s.path_or_url, s.args, place))

    def _add_step(self):
        d = StepDialog(self)
        self.wait_window(d)  # important: block until dialog closes
        if d.result:
            self.steps.append(d.result)
            self._refresh_tree()

    def _edit_step(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        d = StepDialog(self, self.steps[idx])
        self.wait_window(d)  # important: block until dialog closes
        if d.result:
            self.steps[idx] = d.result
            self._refresh_tree()

    def _del_step(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if ask_yes_no(APP_NAME, "Remove the selected step?"):
            self.steps.pop(idx)
            self._refresh_tree()

    def _move(self, delta: int):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        new = idx + delta
        if 0 <= new < len(self.steps):
            self.steps[idx], self.steps[new] = self.steps[new], self.steps[idx]
            self._refresh_tree()
            self.tree.selection_set(str(new))

    def _ok(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror(APP_NAME, "Profile name is required.")
            return
        self.result = Profile(name=name, steps=list(self.steps))
        self.destroy()

# -------------------------
# Main App
# -------------------------
class QuickLaunchApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.minsize(780, 460)

        # Icons
        try:
            self._icon_run = load_icon(run_icon_b64)
            self._icon_gear = load_icon(gear_icon_b64)
            self.iconphoto(True, self._icon_run)
        except Exception:
            self._icon_run = None
            self._icon_gear = None

        self._style_setup()

        # State
        self.profiles: List[Profile] = load_profiles()
        if not self.profiles:
            self.profiles.append(Profile("Example: Files and Browser", [Step(kind="folder", path_or_url=str(Path.home())), Step(kind="url", path_or_url="https://www.python.org", try_place=False)]))
            save_profiles(self.profiles)

        # Layout
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root)
        header.pack(fill="x")
        ttk.Label(header, text=APP_NAME, style="Title.TLabel").pack(side="left")

        top_btns = ttk.Frame(header)
        top_btns.pack(side="right")
        b_new = ttk.Button(top_btns, text="New Profile", command=self._new_profile)
        b_dup = ttk.Button(top_btns, text="Duplicate", command=self._duplicate_profile)
        b_del = ttk.Button(top_btns, text="Delete", command=self._delete_profile)
        b_cfg = ttk.Button(top_btns, text="Edit", command=self._manage_profiles)
        for w in (b_new, b_dup, b_del, b_cfg):
            w.pack(side="left", padx=(6, 0))

        mid = ttk.Frame(root)
        mid.pack(fill="both", expand=True, pady=(8, 8))

        left = ttk.Frame(mid)
        left.pack(side="left", fill="y", padx=(0, 8))

        ttk.Label(left, text="Profiles").pack(anchor="w")
        self.listbox = tk.Listbox(left, activestyle="none", height=12, exportselection=False)
        self.listbox.pack(fill="y", expand=False)
        for p in self.profiles:
            self.listbox.insert("end", p.name)
        if self.profiles:
            self.listbox.selection_set(0)

        btns = ttk.Frame(left)
        btns.pack(fill="x", pady=(8, 0))
        b_run = ttk.Button(btns, text="Run Profile", command=self._run_selected)
        if self._icon_run:
            b_run.configure(image=self._icon_run, compound="left")
        b_run.pack(fill="x")

        right = ttk.Frame(mid)
        right.pack(side="left", fill="both", expand=True)

        ttk.Label(right, text="Selected Profile Steps").pack(anchor="w")
        self.steps_tree = ttk.Treeview(right, columns=("type", "target", "args", "place"), show="headings")
        for col, txt, w in [("type", "Type", 80), ("target", "Target", 380), ("args", "Args", 160), ("place", "Placement", 240)]:
            self.steps_tree.heading(col, text=txt)
            self.steps_tree.column(col, width=w, anchor="w", stretch=(col != "type"))
        self.steps_tree.pack(fill="both", expand=True)

        # Status bar
        self.status = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status, anchor="w", padding=(8, 4), style="Status.TLabel").pack(fill="x", side="bottom")

        # Events
        self.listbox.bind("<<ListboxSelect>>", lambda e: self._refresh_steps_view())
        self.bind_all("<Control-r>", lambda e: self._run_selected())
        self.bind_all("<Control-e>", lambda e: self._manage_profiles())
        self._refresh_steps_view()

    def _style_setup(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        base_font = ("Segoe UI", 10) if is_windows() else ("SF Pro Text", 12) if is_macos() else ("DejaVu Sans", 10)
        style.configure(".", font=base_font)
        style.configure("Title.TLabel", font=(base_font[0], base_font[1] + 4, "bold"))
        style.configure("Status.TLabel", relief="groove")

    # Helpers
    def _selected_index(self) -> Optional[int]:
        sel = self.listbox.curselection()
        return sel[0] if sel else (0 if self.profiles else None)

    def _refresh_steps_view(self):
        self.steps_tree.delete(*self.steps_tree.get_children())
        idx = self._selected_index()
        if idx is None:
            self.status.set("No profiles yet. Click New Profile.")
            return
        p = self.profiles[idx]
        for s in p.steps:
            place = f"{'yes' if s.try_place else 'no'} @ screen {s.screen_index}, {s.anchor}, {s.width_ratio:.2f}×{s.height_ratio:.2f}, delay {s.delay_before_move_ms} ms"
            self.steps_tree.insert("", "end", values=(s.kind, s.path_or_url, s.args, place))
        self.status.set(f"Selected: {p.name}")

    # Main actions
    def _manage_profiles(self):
        idx = self._selected_index()
        if idx is None:
            return self._new_profile()
        current = self.profiles[idx]
        d = ProfileDialog(self, current)
        self.wait_window(d)
        if d.result:
            self.profiles[idx] = d.result
            save_profiles(self.profiles)
            self._reload_listbox(select_name=d.result.name)
            self.status.set(f"Saved profile: {d.result.name}")

    def _new_profile(self):
        d = ProfileDialog(self, Profile("New Profile", []))
        self.wait_window(d)
        if d.result:
            self.profiles.append(d.result)
            save_profiles(self.profiles)
            self._reload_listbox(select_name=d.result.name)
            self.status.set(f"Created profile: {d.result.name}")

    def _duplicate_profile(self):
        idx = self._selected_index()
        if idx is None:
            return
        base = self.profiles[idx]
        copy = Profile(name=f"{base.name} (copy)", steps=[Step.from_dict(s.to_dict()) for s in base.steps])
        self.profiles.append(copy)
        save_profiles(self.profiles)
        self._reload_listbox(select_name=copy.name)
        self.status.set(f"Duplicated profile: {copy.name}")

    def _delete_profile(self):
        idx = self._selected_index()
        if idx is None:
            return
        name = self.profiles[idx].name
        if ask_yes_no(APP_NAME, f"Delete profile '{name}'?"):
            self.profiles.pop(idx)
            save_profiles(self.profiles)
            self._reload_listbox()

    def _reload_listbox(self, select_name: Optional[str] = None):
        self.listbox.delete(0, "end")
        for p in self.profiles:
            self.listbox.insert("end", p.name)
        if select_name:
            for i, p in enumerate(self.profiles):
                if p.name == select_name:
                    self.listbox.selection_clear(0, "end")
                    self.listbox.selection_set(i)
                    self.listbox.see(i)
                    break
        elif self.profiles:
            self.listbox.selection_set(0)
        self._refresh_steps_view()

    def _run_selected(self):
        idx = self._selected_index()
        if idx is None:
            return
        p = self.profiles[idx]
        self.status.set(f"Launching profile: {p.name}")
        self.update_idletasks()
        screens = get_screens_geometry(self)
        for s in p.steps:
            pid, app_hint = launch_step(s)
            try:
                place_window(s, screens, app_hint, pid)
            except Exception:
                pass
        self.status.set(f"Done: {p.name}")

def main():
    try:
        app = QuickLaunchApp()
        app.mainloop()
    except Exception as e:
        traceback.print_exc()
        messagebox.showerror(APP_NAME, f"Fatal error:\n{e}")

if __name__ == "__main__":
    main()