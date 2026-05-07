
"""
ElegantAlarmTimer.py
A single-file, standard-library-only alarm and timer app for Windows.
- Visually appealing Tkinter UI
- Alarm at specific times, multiple alarms, snooze
- Countdown timer with pause and reset
- Always-on-top toggle, dark mode, flashing alert overlay
- Loops a chosen WAV file until stopped, uses winsound on Windows
No external packages required.
"""

import os
import sys
import json
import time
import math
import platform
import datetime as dt
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Windows-specific sound handling
IS_WINDOWS = platform.system() == "Windows"
if IS_WINDOWS:
    try:
        import winsound
    except Exception:
        winsound = None
else:
    winsound = None

APP_NAME = "Elegant Alarm & Timer"
SETTINGS_FILE = "alarm_timer_settings.json"

# Default paths and settings
DEFAULT_WAV = os.path.abspath(os.path.join(os.path.dirname(__file__), "Modified Win XP Shutdown.wav"))
DEFAULT_SETTINGS = {
    "dark_mode": True,
    "topmost": False,
    "alarm_sound": DEFAULT_WAV if os.path.exists(DEFAULT_WAV) else "",
    "alarms": [],  # list of {"hour":13,"minute":32,"label":"Example","enabled":True,"weekdays":[0..6] or [] for everyday}
    "snooze_minutes": 5
}

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

def load_settings():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Minimal schema guard
        for k, v in DEFAULT_SETTINGS.items():
            if k not in data:
                data[k] = v
        return data
    except Exception:
        return DEFAULT_SETTINGS.copy()

def save_settings(data):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

class ElegantApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("960x580")
        self.minsize(820, 520)
        self.settings = load_settings()

        # Theming
        self.style = ttk.Style(self)
        self._apply_theme()

        # Layout: background canvas for subtle animated gradient
        self.bg_canvas = tk.Canvas(self, highlightthickness=0, bd=0)
        self.bg_canvas.pack(fill="both", expand=True)
        self.bg_canvas.bind("<Configure>", lambda e: self._draw_background())

        # Foreground frame
        self.main = ttk.Frame(self, padding=16)
        self.main.place(relx=0.5, rely=0.5, anchor="center")

        # Title row with clock
        topbar = ttk.Frame(self.main)
        topbar.pack(fill="x")
        self.title_label = ttk.Label(topbar, text=APP_NAME, style="Title.TLabel")
        self.title_label.pack(side="left")

        self.clock_label = ttk.Label(topbar, text="", style="Clock.TLabel")
        self.clock_label.pack(side="right")

        # Notebook
        self.nb = ttk.Notebook(self.main)
        self.nb.pack(fill="both", expand=True, pady=(12, 0))

        # Tabs
        self.alarm_tab = ttk.Frame(self.nb, padding=14)
        self.timer_tab = ttk.Frame(self.nb, padding=14)
        self.settings_tab = ttk.Frame(self.nb, padding=14)

        self.nb.add(self.alarm_tab, text="Alarm")
        self.nb.add(self.timer_tab, text="Timer")
        self.nb.add(self.settings_tab, text="Settings")

        # Build tabs
        self._build_alarm_tab()
        self._build_timer_tab()
        self._build_settings_tab()

        # Alert overlay
        self.overlay = None
        self.overlay_color_state = 0
        self.alarm_ringing = False

        # State
        self.running_timer = False
        self.timer_end_ts = None
        self.timer_paused_remaining = None

        # Apply topmost
        self.attributes("-topmost", bool(self.settings.get("topmost", False)))

        # Start the updaters
        self._tick_clock()
        self._scheduler()

    # ------------------ Theme and background ------------------
    def _apply_theme(self):
        dark = bool(self.settings.get("dark_mode", True))
        if dark:
            bg = "#0f1320"
            panel = "#151b2e"
            accent = "#6ea8fe"
            text = "#e7eaf6"
            subtext = "#9aa5c1"
            alert_red = "#ff4d4d"
        else:
            bg = "#f4f6fb"
            panel = "#ffffff"
            accent = "#3b82f6"
            text = "#1f2937"
            subtext = "#6b7280"
            alert_red = "#dc2626"

        self.colors = {
            "bg": bg,
            "panel": panel,
            "accent": accent,
            "text": text,
            "subtext": subtext,
            "alert": alert_red
        }
        self.configure(bg=bg)
        self.style.theme_use("clam")

        # General
        self.style.configure("TFrame", background=panel)
        self.style.configure("TLabel", background=panel, foreground=text, font=("Segoe UI", 11))
        self.style.configure("Title.TLabel", background=panel, foreground=text, font=("Segoe UI", 20, "bold"))
        self.style.configure("Clock.TLabel", background=panel, foreground=self.colors["accent"], font=("Consolas", 18, "bold"))
        self.style.configure("Small.TLabel", foreground=self.colors["subtext"], font=("Segoe UI", 9))

        # Buttons
        self.style.configure("TButton", background=self.colors["accent"], foreground="#ffffff", font=("Segoe UI", 11, "bold"), padding=8)
        self.style.map("TButton", background=[("active", self.colors["accent"])], foreground=[("active", "#ffffff")])

        # Entries and spinboxes
        self.style.configure("TEntry", fieldbackground="#1f2540" if dark else "#ffffff", foreground=text)
        self.style.configure("TSpinbox", fieldbackground="#1f2540" if dark else "#ffffff", foreground=text)

        # Notebook tabs
        self.style.configure("TNotebook", background=panel, borderwidth=0)
        self.style.configure("TNotebook.Tab", padding=[12, 8], background=panel, foreground=text)
        self.style.map("TNotebook.Tab", background=[("selected", self.colors["bg"])])

    def _draw_background(self):
        self.bg_canvas.delete("all")
        w = self.bg_canvas.winfo_width()
        h = self.bg_canvas.winfo_height()
        # Simple radial glow
        for i in range(12, 0, -1):
            r = int(min(w, h) * (i / 12))
            alpha = int(30 * (i / 12))
            color = self._hex_with_alpha(self.colors["accent"], alpha)
            self.bg_canvas.create_oval((w/2 - r, h/2 - r, w/2 + r, h/2 + r), fill=color, outline="")

        # Panel background under main
        # main size estimate
        mw, mh = 820, 460
        x0, y0 = w/2 - mw/2, h/2 - mh/2
        x1, y1 = w/2 + mw/2, h/2 + mh/2
        self.bg_canvas.create_rectangle(x0, y0, x1, y1, fill=self.colors["panel"], outline=self.colors["panel"])

    def _hex_with_alpha(self, hex_color, alpha_0_255):
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return f"#{r:02x}{g:02x}{b:02x}{alpha_0_255:02x}"

    # ------------------ Top bar clock ------------------
    def _tick_clock(self):
        now = dt.datetime.now()
        self.clock_label.configure(text=now.strftime("%H:%M:%S"))
        self.after(250, self._tick_clock)

    # ------------------ Alarm tab ------------------
    def _build_alarm_tab(self):
        header = ttk.Frame(self.alarm_tab)
        header.pack(fill="x")
        ttk.Label(header, text="Set a time, add a label, choose active days").pack(side="left")
        self.add_alarm_btn = ttk.Button(header, text="Add alarm", command=self._add_alarm_from_inputs)
        self.add_alarm_btn.pack(side="right")

        inputs = ttk.Frame(self.alarm_tab)
        inputs.pack(fill="x", pady=8)

        # Time pickers
        self.al_hour = tk.IntVar(value=dt.datetime.now().hour)
        self.al_minute = tk.IntVar(value=(dt.datetime.now().minute + 1) % 60)

        ttk.Label(inputs, text="Hour").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.hour_sb = ttk.Spinbox(inputs, from_=0, to=23, width=4, textvariable=self.al_hour, wrap=True)
        self.hour_sb.grid(row=1, column=0, sticky="w", padx=(0, 12))

        ttk.Label(inputs, text="Minute").grid(row=0, column=1, sticky="w", padx=(0, 6))
        self.min_sb = ttk.Spinbox(inputs, from_=0, to=59, width=4, textvariable=self.al_minute, wrap=True)
        self.min_sb.grid(row=1, column=1, sticky="w", padx=(0, 12))

        ttk.Label(inputs, text="Label").grid(row=0, column=2, sticky="w", padx=(0, 6))
        self.al_label_var = tk.StringVar(value="Alarm")
        self.al_label_entry = ttk.Entry(inputs, textvariable=self.al_label_var, width=24)
        self.al_label_entry.grid(row=1, column=2, sticky="w", padx=(0, 12))

        # Weekday selectors
        ttk.Label(inputs, text="Days").grid(row=0, column=3, sticky="w", padx=(0, 6))
        self.day_vars = [tk.BooleanVar(value=False) for _ in WEEKDAYS]
        days_frame = ttk.Frame(inputs)
        days_frame.grid(row=1, column=3, sticky="w", padx=(0, 12))
        for i, d in enumerate(WEEKDAYS):
            cb = ttk.Checkbutton(days_frame, text=d, variable=self.day_vars[i])
            cb.grid(row=0, column=i, padx=2)

        # Enable toggle
        self.enable_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(inputs, text="Enabled", variable=self.enable_var).grid(row=1, column=4, sticky="w")

        # Alarm list
        self.alarm_tree = ttk.Treeview(self.alarm_tab, columns=("time", "label", "days", "enabled"), show="headings", height=8)
        for col, w in [("time", 120), ("label", 260), ("days", 260), ("enabled", 100)]:
            self.alarm_tree.heading(col, text=col.title())
            self.alarm_tree.column(col, width=w, anchor="center")
        self.alarm_tree.pack(fill="both", expand=True, pady=(10, 6))

        # Buttons bar
        bar = ttk.Frame(self.alarm_tab)
        bar.pack(fill="x")
        ttk.Button(bar, text="Toggle enable", command=self._toggle_selected_alarm).pack(side="left")
        ttk.Button(bar, text="Delete", command=self._delete_selected_alarm).pack(side="left", padx=8)
        ttk.Button(bar, text="Test alarm now", command=self._test_alarm_now).pack(side="right")

        # Load existing
        for a in self.settings.get("alarms", []):
            self._insert_alarm_row(a)

    def _add_alarm_from_inputs(self):
        hour = int(self.al_hour.get()) % 24
        minute = int(self.al_minute.get()) % 60
        label = self.al_label_var.get().strip() or "Alarm"
        days = [i for i, var in enumerate(self.day_vars) if var.get()]
        enabled = bool(self.enable_var.get())

        alarm = {"hour": hour, "minute": minute, "label": label, "enabled": enabled, "weekdays": days}
        self.settings["alarms"].append(alarm)
        save_settings(self.settings)
        self._insert_alarm_row(alarm)

    def _insert_alarm_row(self, a):
        t = f"{a['hour']:02d}:{a['minute']:02d}"
        days = "Everyday" if not a.get("weekdays") else ",".join(WEEKDAYS[i] for i in a["weekdays"])
        en = "Yes" if a.get("enabled", True) else "No"
        self.alarm_tree.insert("", "end", values=(t, a.get("label", ""), days, en))

    def _toggle_selected_alarm(self):
        sel = self.alarm_tree.selection()
        if not sel:
            return
        idx = self.alarm_tree.index(sel[0])
        try:
            self.settings["alarms"][idx]["enabled"] = not self.settings["alarms"][idx].get("enabled", True)
            save_settings(self.settings)
            self.alarm_tree.delete(*self.alarm_tree.get_children())
            for a in self.settings["alarms"]:
                self._insert_alarm_row(a)
        except Exception:
            pass

    def _delete_selected_alarm(self):
        sel = self.alarm_tree.selection()
        if not sel:
            return
        idx = self.alarm_tree.index(sel[0])
        try:
            del self.settings["alarms"][idx]
            save_settings(self.settings)
            self.alarm_tree.delete(*self.alarm_tree.get_children())
            for a in self.settings["alarms"]:
                self._insert_alarm_row(a)
        except Exception:
            pass

    def _test_alarm_now(self):
        self._fire_alarm(label="Test alarm")

    # ------------------ Timer tab ------------------
    def _build_timer_tab(self):
        top = ttk.Frame(self.timer_tab)
        top.pack(fill="x")

        ttk.Label(top, text="Countdown timer").pack(side="left")
        self.timer_display = ttk.Label(top, text="00:00:00", style="Clock.TLabel")
        self.timer_display.pack(side="right")

        # Inputs row
        inputs = ttk.Frame(self.timer_tab)
        inputs.pack(fill="x", pady=10)
        ttk.Label(inputs, text="Hours").grid(row=0, column=0, padx=(0, 6), sticky="w")
        ttk.Label(inputs, text="Minutes").grid(row=0, column=1, padx=(0, 6), sticky="w")
        ttk.Label(inputs, text="Seconds").grid(row=0, column=2, padx=(0, 6), sticky="w")

        self.t_h = tk.IntVar(value=0)
        self.t_m = tk.IntVar(value=5)
        self.t_s = tk.IntVar(value=0)

        ttk.Spinbox(inputs, from_=0, to=23, width=6, textvariable=self.t_h).grid(row=1, column=0, padx=(0, 12))
        ttk.Spinbox(inputs, from_=0, to=59, width=6, textvariable=self.t_m).grid(row=1, column=1, padx=(0, 12))
        ttk.Spinbox(inputs, from_=0, to=59, width=6, textvariable=self.t_s).grid(row=1, column=2, padx=(0, 12))

        # Progress ring on canvas
        self.timer_canvas = tk.Canvas(self.timer_tab, width=280, height=280, highlightthickness=0, bd=0, bg=self.colors["panel"])
        self.timer_canvas.pack(pady=12)

        # Buttons
        btns = ttk.Frame(self.timer_tab)
        btns.pack()
        ttk.Button(btns, text="Start", command=self._timer_start).grid(row=0, column=0, padx=6)
        ttk.Button(btns, text="Pause", command=self._timer_pause).grid(row=0, column=1, padx=6)
        ttk.Button(btns, text="Reset", command=self._timer_reset).grid(row=0, column=2, padx=6)

    def _timer_start(self):
        if self.running_timer and self.timer_paused_remaining is None:
            return
        total = self._timer_total_seconds()
        if total <= 0 and self.timer_paused_remaining is None:
            messagebox.showinfo(APP_NAME, "Please set a duration greater than zero.")
            return
        now = time.time()
        if self.timer_paused_remaining is not None:
            self.timer_end_ts = now + self.timer_paused_remaining
            self.timer_paused_remaining = None
        else:
            self.timer_end_ts = now + total
        self.running_timer = True

    def _timer_pause(self):
        if not self.running_timer:
            return
        remaining = max(0, int(round(self.timer_end_ts - time.time())))
        self.timer_paused_remaining = remaining
        self.running_timer = False

    def _timer_reset(self):
        self.running_timer = False
        self.timer_end_ts = None
        self.timer_paused_remaining = None
        self._update_timer_display(0, self._timer_total_seconds())

    def _timer_total_seconds(self):
        return int(self.t_h.get()) * 3600 + int(self.t_m.get()) * 60 + int(self.t_s.get())

    def _update_timer_display(self, elapsed, total):
        remaining = max(0, total - elapsed)
        h = remaining // 3600
        m = (remaining % 3600) // 60
        s = remaining % 60
        self.timer_display.configure(text=f"{h:02d}:{m:02d}:{s:02d}")
        # Progress ring
        self._draw_progress_ring(self.timer_canvas, remaining, total)

    def _draw_progress_ring(self, canvas, remaining, total):
        canvas.delete("all")
        w = int(canvas["width"])
        h = int(canvas["height"])
        cx, cy = w // 2, h // 2
        r = min(w, h) // 2 - 16
        # Background ring
        canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline=self.colors["subtext"], width=10)
        # Foreground arc
        if total > 0:
            frac = (total - remaining) / total
            extent = frac * 360.0
            canvas.create_arc(cx - r, cy - r, cx + r, cy + r, start=90, extent=-extent, outline=self.colors["accent"], width=12, style="arc")

    # ------------------ Settings tab ------------------
    def _build_settings_tab(self):
        # Sound picker
        sf = ttk.Frame(self.settings_tab)
        sf.pack(fill="x")
        ttk.Label(sf, text="Alarm sound (WAV)").pack(side="left")
        self.sound_path_var = tk.StringVar(value=self.settings.get("alarm_sound", ""))
        ttk.Entry(sf, textvariable=self.sound_path_var, width=60).pack(side="left", padx=8)
        ttk.Button(sf, text="Browse", command=self._pick_sound).pack(side="left")

        # Snooze
        snf = ttk.Frame(self.settings_tab)
        snf.pack(fill="x", pady=8)
        ttk.Label(snf, text="Snooze minutes").pack(side="left")
        self.snooze_var = tk.IntVar(value=self.settings.get("snooze_minutes", 5))
        ttk.Spinbox(snf, from_=1, to=60, textvariable=self.snooze_var, width=6).pack(side="left", padx=8)

        # Toggles
        tf = ttk.Frame(self.settings_tab)
        tf.pack(fill="x", pady=8)
        self.topmost_var = tk.BooleanVar(value=bool(self.settings.get("topmost", False)))
        self.dark_var = tk.BooleanVar(value=bool(self.settings.get("dark_mode", True)))
        ttk.Checkbutton(tf, text="Always on top", variable=self.topmost_var, command=self._apply_topmost).pack(side="left")
        ttk.Checkbutton(tf, text="Dark mode", variable=self.dark_var, command=self._toggle_dark_mode).pack(side="left", padx=12)

        # Save settings button
        ttk.Button(self.settings_tab, text="Save settings", command=self._save_settings_from_ui).pack(pady=10)

        # Footer
        ttk.Label(self.settings_tab, text="Tip: use weekday selections in Alarm tab to restrict an alarm to specific days", style="Small.TLabel").pack(anchor="w", pady=(12,0))

    def _pick_sound(self):
        file = filedialog.askopenfilename(title="Select WAV file", filetypes=[("WAV", "*.wav"), ("All files", "*.*")])
        if file:
            self.sound_path_var.set(file)

    def _apply_topmost(self):
        self.attributes("-topmost", bool(self.topmost_var.get()))

    def _toggle_dark_mode(self):
        self.settings["dark_mode"] = bool(self.dark_var.get())
        save_settings(self.settings)
        self._apply_theme()
        # Re-draw backgrounds and update widget colors
        self._draw_background()
        self.timer_canvas.configure(bg=self.colors["panel"])

    def _save_settings_from_ui(self):
        self.settings["alarm_sound"] = self.sound_path_var.get().strip()
        self.settings["snooze_minutes"] = int(self.snooze_var.get())
        self.settings["topmost"] = bool(self.topmost_var.get())
        self.settings["dark_mode"] = bool(self.dark_var.get())
        save_settings(self.settings)
        messagebox.showinfo(APP_NAME, "Settings saved.")

    # ------------------ Scheduler ------------------
    def _scheduler(self):
        # Check alarms
        self._check_alarms()
        # Update timer
        self._tick_timer()
        # Re-run
        self.after(500, self._scheduler)

    def _check_alarms(self):
        now = dt.datetime.now()
        cur_wd = (now.weekday())  # 0 Mon .. 6 Sun
        for a in self.settings.get("alarms", []):
            if not a.get("enabled", True):
                continue
            if a.get("weekdays"):
                if cur_wd not in a["weekdays"]:
                    continue
            if now.hour == a.get("hour", -1) and now.minute == a.get("minute", -1) and now.second < 1:
                self._fire_alarm(label=a.get("label", "Alarm"))

    # ------------------ Alarm firing ------------------
    def _fire_alarm(self, label="Alarm"):
        if self.alarm_ringing:
            return
        self.alarm_ringing = True
        self._play_sound_loop()
        self._show_overlay(label)

    def _play_sound_loop(self):
        if winsound and self._sound_path():
            try:
                winsound.PlaySound(self._sound_path(), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
            except Exception:
                self.bell()
        else:
            # Fallback to bell
            try:
                self.bell()
            except Exception:
                pass

    def _stop_sound(self):
        if winsound:
            try:
                winsound.PlaySound(None, 0)
            except Exception:
                pass

    def _sound_path(self):
        p = self.settings.get("alarm_sound") or ""
        return p if os.path.isfile(p) else ""

    def _show_overlay(self, label):
        if self.overlay and tk.Toplevel.winfo_exists(self.overlay):
            return
        self.overlay = tk.Toplevel(self)
        self.overlay.attributes("-topmost", True)
        self.overlay.overrideredirect(True)
        self.overlay.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")

        bg = tk.Frame(self.overlay, bg=self.colors["alert"])
        bg.pack(fill="both", expand=True)

        # Center content
        title = tk.Label(bg, text=label, font=("Segoe UI", 40, "bold"), fg="#ffffff", bg=self.colors["alert"])
        title.place(relx=0.5, rely=0.4, anchor="center")

        btn_Frame = tk.Frame(bg, bg=self.colors["alert"])
        btn_Frame.place(relx=0.5, rely=0.55, anchor="center")
        stop_btn = ttk.Button(btn_Frame, text="Stop", command=self._overlay_stop)
        stop_btn.grid(row=0, column=0, padx=8)
        snooze_btn = ttk.Button(btn_Frame, text=f"Snooze {self.settings.get('snooze_minutes', 5)} min", command=self._overlay_snooze)
        snooze_btn.grid(row=0, column=1, padx=8)

        # Flashing effect
        self.overlay_color_state = 0
        def flash():
            if not self.overlay or not tk.Toplevel.winfo_exists(self.overlay):
                return
            self.overlay_color_state ^= 1
            color = "#ff2b2b" if self.overlay_color_state else self.colors["alert"]
            bg.configure(bg=color)
            title.configure(bg=color)
            btn_Frame.configure(bg=color)
            self.overlay.after(400, flash)
        flash()

        # Keyboard bindings
        self.overlay.bind("<Escape>", lambda e: self._overlay_stop())
        self.overlay.bind("<Return>", lambda e: self._overlay_stop())

        stop_btn.focus_set()

    def _overlay_stop(self):
        self._stop_sound()
        self.alarm_ringing = False
        try:
            if self.overlay and tk.Toplevel.winfo_exists(self.overlay):
                self.overlay.destroy()
        except Exception:
            pass

    def _overlay_snooze(self):
        mins = int(self.settings.get("snooze_minutes", 5))
        when = dt.datetime.now() + dt.timedelta(minutes=mins)
        # Add a one-time alarm entry for snooze, disabled weekdays list to allow immediate trigger at exact minute
        self.settings["alarms"].append({
            "hour": when.hour,
            "minute": when.minute,
            "label": f"Snoozed alarm",
            "enabled": True,
            "weekdays": []  # everyday
        })
        save_settings(self.settings)
        self._overlay_stop()

    # ------------------ Timer ticking ------------------
    def _tick_timer(self):
        if self.running_timer and self.timer_end_ts is not None:
            remaining = int(round(self.timer_end_ts - time.time()))
            if remaining <= 0:
                self.running_timer = False
                self.timer_end_ts = None
                self.timer_paused_remaining = None
                self._update_timer_display(self._timer_total_seconds(), self._timer_total_seconds())
                # Fire alarm for timer done
                self._fire_alarm(label="Timer finished")
            else:
                total = self._timer_total_seconds() if self.timer_paused_remaining is None else (self._timer_total_seconds())
                elapsed = max(0, total - remaining)
                self._update_timer_display(elapsed, total)
        else:
            # Idle, draw idle ring with total=1 to avoid divide by zero
            total = max(1, self._timer_total_seconds())
            self._draw_progress_ring(self.timer_canvas, remaining=total, total=total)

# ------------------ Entry ------------------
if __name__ == "__main__":
    app = ElegantApp()
    app.mainloop()
