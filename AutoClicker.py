import sys
import time
import threading
import random
import tkinter as tk
from tkinter import ttk, messagebox

# ============================================================
#                    Platform Adapters
# ============================================================
IS_WIN = sys.platform == "win32"

if IS_WIN:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32

    # SendInput flags
    INPUT_MOUSE = 0
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_RIGHTDOWN = 0x0008
    MOUSEEVENTF_RIGHTUP = 0x0010

    # Virtual keys for polling
    VK_CONTROL = 0x11
    VK_SPACE = 0x20
    VK_F8 = 0x77
    VK_ESCAPE = 0x1B

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("mi", MOUSEINPUT)]

    class POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    def get_cursor_pos():
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    def set_cursor_pos(x, y):
        user32.SetCursorPos(int(x), int(y))

    def _send_mouse(flags):
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.mi = MOUSEINPUT(0, 0, 0, flags, 0, None)
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def click_left():
        _send_mouse(MOUSEEVENTF_LEFTDOWN)
        _send_mouse(MOUSEEVENTF_LEFTUP)

    def click_right():
        _send_mouse(MOUSEEVENTF_RIGHTDOWN)
        _send_mouse(MOUSEEVENTF_RIGHTUP)

    def key_down(vk):
        # High bit means key is currently down
        return (user32.GetAsyncKeyState(vk) & 0x8000) != 0
else:
    # Non-Windows demo functions
    def get_cursor_pos():
        return (0, 0)

    def set_cursor_pos(x, y):
        pass

    def click_left():
        print("Demo left click")

    def click_right():
        print("Demo right click")

    def key_down(vk):
        return False

# ============================================================
#                 Auto Clicker Controller
# ============================================================
class AutoClicker:
    def __init__(self, ui_getters, ui_set_status):
        """
        ui_getters: callable that returns current settings as a dict
        ui_set_status: callable to set status text safely from any thread
        """
        self.ui_getters = ui_getters
        self.ui_set_status = ui_set_status
        self._thread = None
        self._stop_evt = threading.Event()
        self._running_lock = threading.Lock()
        self._is_running = False

    def is_running(self):
        with self._running_lock:
            return self._is_running

    def _set_running(self, val):
        with self._running_lock:
            self._is_running = val

    def start(self, started_by="UI/Hotkey"):
        if self.is_running():
            return
        if not IS_WIN:
            self.ui_set_status("Windows required for real clicking; running in demo mode.")

        s = self.ui_getters()
        cps = self._compute_cps(s["rate_value"], s["rate_unit"])
        cps = max(1.0 / 3600.0, min(200.0, cps))  # allow as slow as 1 per hour if someone wants, cap fast at 200 CPS
        duration = max(0.0, float(s["duration"]))
        total_clicks = max(0, int(s["total_clicks"]))
        follow = s["follow"]
        click_type = s["click_type"]
        jitter_ms = max(0.0, float(s["jitter_ms"]))
        start_delay = max(0.0, float(s["start_delay"]))

        target_xy = None  # fixed target captured after delay

        self._stop_evt.clear()
        self._set_running(True)
        self._thread = threading.Thread(
            target=self._run_loop,
            args=(cps, duration, total_clicks, follow, target_xy, click_type, jitter_ms, start_delay, started_by, s["rate_value"], s["rate_unit"]),
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        self._stop_evt.set()

    @staticmethod
    def _compute_cps(rate_value, rate_unit):
        # rate_unit is "CPS" or "CPM"
        try:
            rv = float(rate_value)
        except:
            rv = 1.0
        if rv <= 0:
            rv = 1.0
        if rate_unit == "CPM":
            return rv / 60.0
        return rv

    def _run_loop(self, cps, duration, total_clicks, follow, target_xy, click_type, jitter_ms, start_delay, started_by, rate_value, rate_unit):
        try:
            # Countdown before capture
            if start_delay > 0:
                t_end = time.perf_counter() + start_delay
                while not self._stop_evt.is_set() and time.perf_counter() < t_end:
                    remain = max(0.0, t_end - time.perf_counter())
                    mode_txt = "follow cursor" if follow else "fixed spot"
                    self.ui_set_status(f"Starting in {remain:.1f}s, {mode_txt}. Hover the target now.")
                    time.sleep(0.05)

            # Capture fixed target right after delay
            if not follow and target_xy is None:
                target_xy = get_cursor_pos()

            # Timing
            interval = 1.0 / cps
            clicks_done = 0
            t0 = time.perf_counter()
            next_time = t0

            self.ui_set_status(self._status_line(cps, duration, total_clicks, follow, click_type, rate_value, rate_unit))

            while not self._stop_evt.is_set():
                if duration > 0 and (time.perf_counter() - t0) >= duration:
                    break
                if total_clicks > 0 and clicks_done >= total_clicks:
                    break

                # Target for this click
                if follow:
                    x, y = get_cursor_pos()
                else:
                    x, y = target_xy

                if not follow:
                    set_cursor_pos(x, y)

                # Click type
                if click_type == "left":
                    click_left()
                elif click_type == "right":
                    click_right()
                else:
                    click_left()
                    time.sleep(0.01)
                    click_left()

                clicks_done += 1

                # Jitter
                jitter = (random.random() - 0.5) * (jitter_ms / 1000.0) if jitter_ms > 0 else 0.0
                next_time += interval + jitter

                # Precision wait
                while True:
                    now = time.perf_counter()
                    if now >= next_time or self._stop_evt.is_set():
                        break
                    time.sleep(min(0.002, max(0.0005, interval * 0.1)))

            self.ui_set_status("Stopped.")
        finally:
            self._set_running(False)

    @staticmethod
    def _status_line(cps, duration, total_clicks, follow, click_type, rate_value, rate_unit):
        stop_bits = []
        if duration > 0:
            stop_bits.append(f"time {duration:.1f}s")
        if total_clicks > 0:
            stop_bits.append(f"{total_clicks} clicks")
        stops = " or ".join(stop_bits) if stop_bits else "manual stop"
        mode = "follow cursor" if follow else "fixed spot"
        human_rate = f"{rate_value:.2f} {rate_unit}"
        return f"Clicking {click_type} at {human_rate} ({cps:.4f} CPS), {mode}; stops on {stops}."

# ============================================================
#                         UI
# ============================================================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RapidClick Studio")
        self.geometry("760x600")
        self.minsize(720, 560)

        # ttk theme and scaling
        try:
            self.call("tk", "scaling", 1.2)
        except tk.TclError:
            pass
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TButton", padding=6)
        style.configure("Card.TLabelframe", padding=12)
        style.configure("Card.TLabelframe.Label", font=("Segoe UI", 11, "bold"))

        # Variables
        self.var_rate_value = tk.DoubleVar(value=10.0)   # value in CPS or CPM depending on unit
        self.var_rate_unit = tk.StringVar(value="CPS")   # "CPS" or "CPM"
        self.var_duration = tk.DoubleVar(value=5.0)
        self.var_total_clicks = tk.IntVar(value=0)
        self.var_follow = tk.BooleanVar(value=False)
        self.var_click_type = tk.StringVar(value="left")
        self.var_jitter_ms = tk.DoubleVar(value=0.0)
        self.var_start_delay = tk.DoubleVar(value=1.0)

        # Build layout
        self._build_header()
        self._build_controls()
        self._build_presets()
        self._build_status()

        # Controller
        self.clicker = AutoClicker(self._collect_settings, self._set_status_threadsafe)

        # Key binds inside the app
        self.bind("<space>", self._toggle_from_space)
        self.bind("<Escape>", self._stop_from_key)

        # Global hotkeys via polling
        if IS_WIN:
            self._start_hotkey_poll()
        else:
            messagebox.showwarning(
                "Platform",
                "Real clicking and global hotkeys require Windows. You can still explore the UI."
            )

        # Clean shutdown
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------- Header ----------------
    def _build_header(self):
        frm = ttk.Frame(self, padding=(10, 10, 10, 0))
        frm.pack(fill="x")
        title = ttk.Label(frm, text="RapidClick Studio", font=("Segoe UI", 16, "bold"))
        title.pack(anchor="w")
        sub = ttk.Label(
            frm,
            text="Ctrl+Space starts globally; F8 or Esc stops; Space toggles when this window is focused.",
            foreground="#444"
        )
        sub.pack(anchor="w", pady=(2, 6))

    # ---------------- Controls ----------------
    def _build_controls(self):
        grid = ttk.Frame(self, padding=10)
        grid.pack(fill="x")

        # Card 1: Rate and stops
        lf1 = ttk.Labelframe(grid, text="Speed and Stop Conditions", style="Card.TLabelframe")
        lf1.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        lf1.columnconfigure(1, weight=1)

        # Rate row
        ttk.Label(lf1, text="Rate value").grid(row=0, column=0, sticky="w")
        rate_row = ttk.Frame(lf1)
        rate_row.grid(row=0, column=1, sticky="ew", pady=2)
        rate_row.columnconfigure(0, weight=1)

        # Scale ranges will depend on unit
        self.scale_rate = ttk.Scale(rate_row, orient="horizontal",
                                    variable=self.var_rate_value,
                                    command=lambda v: self._sync_rate_entry())
        self.scale_rate.grid(row=0, column=0, sticky="ew")
        self.ent_rate = ttk.Entry(rate_row, width=8)
        self.ent_rate.insert(0, f"{self.var_rate_value.get():.2f}")
        self.ent_rate.grid(row=0, column=1, padx=(6, 6))
        self.ent_rate.bind("<Return>", lambda e: self._set_rate_from_entry())
        self.ent_rate.bind("<FocusOut>", lambda e: self._set_rate_from_entry())

        self.cmb_unit = ttk.Combobox(rate_row, state="readonly", width=6,
                                     values=("CPS", "CPM"), textvariable=self.var_rate_unit)
        self.cmb_unit.grid(row=0, column=2)
        self.cmb_unit.bind("<<ComboboxSelected>>", lambda e: self._on_unit_change())

        # Initial unit setup
        self._on_unit_change()

        ttk.Label(lf1, text="Stop after duration, seconds (0 keeps running)").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(lf1, textvariable=self.var_duration, width=10).grid(row=1, column=1, sticky="w", pady=(6, 0))

        ttk.Label(lf1, text="Stop after total clicks (0 means ignore)").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(lf1, textvariable=self.var_total_clicks, width=10).grid(row=2, column=1, sticky="w", pady=(6, 0))

        ttk.Label(lf1, text="Start delay, seconds").grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(lf1, textvariable=self.var_start_delay, width=10).grid(row=3, column=1, sticky="w", pady=(6, 0))

        # Card 2: Target and click type
        lf2 = ttk.Labelframe(grid, text="Target and Click Type", style="Card.TLabelframe")
        lf2.grid(row=0, column=1, sticky="nsew")
        lf2.columnconfigure(0, weight=1)

        ttk.Label(lf2, text="Target mode").grid(row=0, column=0, sticky="w")
        row_tm = ttk.Frame(lf2)
        row_tm.grid(row=1, column=0, sticky="w", pady=(2, 6))
        ttk.Radiobutton(row_tm, text="Fixed spot at start", variable=self.var_follow, value=False).pack(side="left", padx=(0, 10))
        ttk.Radiobutton(row_tm, text="Follow cursor", variable=self.var_follow, value=True).pack(side="left")

        ttk.Label(lf2, text="Click type").grid(row=2, column=0, sticky="w")
        row_ct = ttk.Frame(lf2)
        row_ct.grid(row=3, column=0, sticky="w", pady=(2, 6))
        ttk.Radiobutton(row_ct, text="Left", variable=self.var_click_type, value="left").pack(side="left", padx=(0, 10))
        ttk.Radiobutton(row_ct, text="Right", variable=self.var_click_type, value="right").pack(side="left", padx=(0, 10))
        ttk.Radiobutton(row_ct, text="Double", variable=self.var_click_type, value="double").pack(side="left")

        ttk.Label(lf2, text="Timing jitter, milliseconds").grid(row=4, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(lf2, textvariable=self.var_jitter_ms, width=10).grid(row=5, column=0, sticky="w")

        # Start and Stop buttons
        btns = ttk.Frame(self, padding=(10, 0, 10, 0))
        btns.pack(fill="x", pady=(8, 0))
        self.btn_start = ttk.Button(btns, text="Start (Ctrl+Space)", command=lambda: self._start("Start button"))
        self.btn_start.pack(side="left")
        ttk.Button(btns, text="Stop (F8 or Esc)", command=self._stop).pack(side="left", padx=(8, 0))

    # ---------------- Presets ----------------
    def _build_presets(self):
        outer = ttk.Frame(self, padding=(10, 0, 10, 10))
        outer.pack(fill="x")

        # Fast CPS presets
        lf_fast = ttk.Labelframe(outer, text="Quick Presets, CPS", style="Card.TLabelframe")
        lf_fast.pack(fill="x", pady=(0, 8))
        row1 = ttk.Frame(lf_fast); row1.pack(fill="x", pady=2)
        ttk.Button(row1, text="0.5 CPS", command=lambda: self._set_rate(0.5, "CPS")).pack(side="left")
        ttk.Button(row1, text="1 CPS", command=lambda: self._set_rate(1, "CPS")).pack(side="left", padx=4)
        ttk.Button(row1, text="5 CPS", command=lambda: self._set_rate(5, "CPS")).pack(side="left", padx=4)
        ttk.Button(row1, text="10 CPS", command=lambda: self._set_rate(10, "CPS")).pack(side="left", padx=4)

        row2 = ttk.Frame(lf_fast); row2.pack(fill="x", pady=2)
        ttk.Button(row2, text="25 CPS", command=lambda: self._set_rate(25, "CPS")).pack(side="left")
        ttk.Button(row2, text="50 CPS", command=lambda: self._set_rate(50, "CPS")).pack(side="left", padx=4)
        ttk.Button(row2, text="100 CPS", command=lambda: self._set_rate(100, "CPS")).pack(side="left", padx=4)
        ttk.Button(row2, text="200 CPS", command=lambda: self._set_rate(200, "CPS")).pack(side="left", padx=4)

        # Slow CPM presets
        lf_slow = ttk.Labelframe(outer, text="Slow Presets, CPM", style="Card.TLabelframe")
        lf_slow.pack(fill="x")
        row3 = ttk.Frame(lf_slow); row3.pack(fill="x", pady=2)
        ttk.Button(row3, text="1 per min", command=lambda: self._set_rate(1, "CPM")).pack(side="left")
        ttk.Button(row3, text="2 per min", command=lambda: self._set_rate(2, "CPM")).pack(side="left", padx=4)
        ttk.Button(row3, text="5 per min", command=lambda: self._set_rate(5, "CPM")).pack(side="left", padx=4)
        ttk.Button(row3, text="10 per min", command=lambda: self._set_rate(10, "CPM")).pack(side="left", padx=4)

        # Duration and total click presets for convenience
        row4 = ttk.Frame(outer); row4.pack(fill="x", pady=(8, 2))
        ttk.Button(row4, text="Duration 2s", command=lambda: self.var_duration.set(2.0)).pack(side="left")
        ttk.Button(row4, text="Duration 5s", command=lambda: self.var_duration.set(5.0)).pack(side="left", padx=4)
        ttk.Button(row4, text="Duration 10s", command=lambda: self.var_duration.set(10.0)).pack(side="left", padx=4)
        ttk.Button(row4, text="Unlimited time", command=lambda: self.var_duration.set(0.0)).pack(side="left", padx=4)

        row5 = ttk.Frame(outer); row5.pack(fill="x", pady=2)
        ttk.Button(row5, text="100 clicks", command=lambda: self.var_total_clicks.set(100)).pack(side="left")
        ttk.Button(row5, text="500 clicks", command=lambda: self.var_total_clicks.set(500)).pack(side="left", padx=4)
        ttk.Button(row5, text="1000 clicks", command=lambda: self.var_total_clicks.set(1000)).pack(side="left", padx=4)
        ttk.Button(row5, text="Unlimited clicks", command=lambda: self.var_total_clicks.set(0)).pack(side="left", padx=4)

    # ---------------- Status ----------------
    def _build_status(self):
        self.status = tk.StringVar(value="Ready. Choose CPS for fast rates, or CPM for slow rates like 1 or 2 per minute. Start captures fixed target after the delay.")
        bar = ttk.Label(self, textvariable=self.status, anchor="w", relief=tk.SUNKEN)
        bar.pack(fill="x", side="bottom", ipady=4, padx=0, pady=0)

    # ---------------- Helpers and events ----------------
    def _collect_settings(self):
        def safe_float(v, d):
            try: return float(v)
            except: return d
        def safe_int(v, d):
            try: return int(v)
            except: return d

        rate_value = max(0.01, safe_float(self.var_rate_value.get(), 10.0))
        rate_unit = self.var_rate_unit.get().upper().strip()
        if rate_unit not in ("CPS", "CPM"):
            rate_unit = "CPS"

        duration = max(0.0, safe_float(self.var_duration.get(), 0.0))
        total_clicks = max(0, safe_int(self.var_total_clicks.get(), 0))
        jitter_ms = max(0.0, safe_float(self.var_jitter_ms.get(), 0.0))
        start_delay = max(0.0, safe_float(self.var_start_delay.get(), 1.0))
        return {
            "rate_value": rate_value,
            "rate_unit": rate_unit,
            "duration": duration,
            "total_clicks": total_clicks,
            "follow": bool(self.var_follow.get()),
            "click_type": self.var_click_type.get(),
            "jitter_ms": jitter_ms,
            "start_delay": start_delay,
        }

    def _set_status_threadsafe(self, text):
        self.after(0, lambda: self.status.set(text))

    def _set_rate(self, value, unit):
        self.var_rate_unit.set(unit)
        self._on_unit_change()
        self.var_rate_value.set(float(value))
        self._sync_rate_entry()

    def _sync_rate_entry(self):
        self.ent_rate.delete(0, tk.END)
        self.ent_rate.insert(0, f"{float(self.var_rate_value.get()):.2f}")

    def _set_rate_from_entry(self):
        try:
            val = float(self.ent_rate.get())
        except ValueError:
            self._sync_rate_entry()
            return
        val = max(0.01, val)
        self.var_rate_value.set(val)
        self._sync_rate_entry()

    def _on_unit_change(self):
        unit = self.var_rate_unit.get()
        # Adjust the scale range to make sense for the unit
        if unit == "CPM":
            # 1 to 120 CPM covers 1 click per minute up to 2 per second
            self.scale_rate.configure(from_=1.0, to=120.0)
            if self.var_rate_value.get() < 1.0:
                self.var_rate_value.set(1.0)
        else:
            # CPS mode for fast rates
            self.scale_rate.configure(from_=0.5, to=200.0)
            if self.var_rate_value.get() < 0.5:
                self.var_rate_value.set(10.0)
        self._sync_rate_entry()

    def _toggle_from_space(self, event=None):
        if self.clicker.is_running():
            self._stop()
        else:
            self._start("Space key")

    def _stop_from_key(self, event=None):
        self._stop()

    def _start(self, source="UI"):
        self.clicker.start(started_by=source)

    def _stop(self):
        self.clicker.stop()

    # ---------------- Global hotkey polling ----------------
    def _start_hotkey_poll(self):
        # Poll GetAsyncKeyState on a background thread and trigger UI actions
        def poll():
            prev_ctrl = False
            prev_space = False
            prev_f8 = False
            prev_esc = False
            while True:
                if not self.winfo_exists():
                    break
                ctrl = key_down(0x11)   # VK_CONTROL
                space = key_down(0x20)  # VK_SPACE
                f8 = key_down(0x77)     # VK_F8
                esc = key_down(0x1B)    # VK_ESCAPE

                if ctrl and space and (not prev_ctrl or not prev_space):
                    self.after(0, lambda: self._start("Ctrl+Space"))
                if f8 and not prev_f8:
                    self.after(0, self._stop)
                if esc and not prev_esc:
                    self.after(0, self._stop)

                prev_ctrl, prev_space, prev_f8, prev_esc = ctrl, space, f8, esc
                time.sleep(0.03)  # about 33 Hz polling

        t = threading.Thread(target=poll, daemon=True)
        t.start()

    # ---------------- Shutdown ----------------
    def _on_close(self):
        try:
            self._stop()
        finally:
            self.destroy()

# ============================================================
#                       Main Entrypoint
# ============================================================
if __name__ == "__main__":
    app = App()
    app.mainloop()