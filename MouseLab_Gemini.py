import tkinter as tk
from tkinter import ttk, messagebox
import time
import random
import math
import json
import os
from datetime import datetime

# -----------------------------------------------------------------------------
# CONSTANTS & CONFIG
# -----------------------------------------------------------------------------
DATA_FILE = "mouse_mastery_data.json"
APP_TITLE = "Mouse Mastery: Reflex & Precision Trainer"
WIDTH, HEIGHT = 1000, 700

# Color Palette (Dark/Modern)
BG_COLOR = "#2e2e2e"
FG_COLOR = "#ffffff"
ACCENT_COLOR = "#4a90e2"
SUCCESS_COLOR = "#2ecc71"
WARNING_COLOR = "#f1c40f"
DANGER_COLOR = "#e74c3c"
PANEL_BG = "#3b3b3b"

MODE_DESCRIPTIONS = {
    "1. Speed Test (CPS)": "Click as many times as possible within a set time limit.",
    "2. Perfect Interval": "Try to click exactly every 1.00 or 2.00 seconds. Visual feedback for precision.",
    "3. Reaction Choice": "Click GREEN signals only. Do not click RED signals.",
    "4. Audio/Visual Reflex": "Wait for the flash, then click immediately. Tests raw reaction time.",
    "5. Speed Analysis": "Measures time between individual clicks to find your max burst speed.",
    "6. Rhythm Match": "Click in time with the visual/audio metronome.",
    "7. Precision Hold": "Hold the mouse button and release it after exactly 1.50 seconds.",
    "8. Pattern Copy": "Memorize the flash pattern, then click it back.",
    "9. Reaction Drift": "Keep the moving bar centered by clicking to push it back.",
    "10. Target Chase": "Click the appearing targets as fast as possible before they vanish.",
    "11. Click & Dodge": "Avoid falling red objects. Click falling green objects.",
    "12. Click Builder": "Build a tower. Timing builds; mistiming destroys.",
    "13. Endurance": "Long-form test (5+ mins) to measure fatigue and consistency.",
    "14. Grid Focus": "A grid appears. Click the lit square instantly.",
    "15. Click Sprints": "Interval training: 3s Burst, 3s Rest. Repeat.",
}

# -----------------------------------------------------------------------------
# UTILITIES
# -----------------------------------------------------------------------------
class DataManager:
    def __init__(self):
        self.data = self.load_data()

    def load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_score(self, mode_name, score, metric="points"):
        if mode_name not in self.data:
            self.data[mode_name] = []
        
        entry = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "score": score,
            "metric": metric
        }
        self.data[mode_name].append(entry)
        # Keep only last 50 entries per mode to save space
        self.data[mode_name] = self.data[mode_name][-50:]
        
        with open(DATA_FILE, 'w') as f:
            json.dump(self.data, f, indent=4)

    def get_best_score(self, mode_name, lower_is_better=False):
        if mode_name not in self.data or not self.data[mode_name]:
            return "N/A"
        
        scores = [x['score'] for x in self.data[mode_name]]
        if lower_is_better:
            return min(scores)
        return max(scores)

class ToolTip:
    """Displays text when hovering over a widget."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        x, y, _, _ = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 25
        y = y + self.widget.winfo_rooty() + 25
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                       background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                       font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def hide_tip(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

# -----------------------------------------------------------------------------
# MAIN APPLICATION
# -----------------------------------------------------------------------------
class MouseApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(f"{WIDTH}x{HEIGHT}")
        self.configure(bg=BG_COLOR)
        
        # Styles
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background=BG_COLOR)
        style.configure("Sidebar.TFrame", background=PANEL_BG)
        style.configure("TLabel", background=BG_COLOR, foreground=FG_COLOR, font=("Segoe UI", 10))
        style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"), background=BG_COLOR, foreground=ACCENT_COLOR)
        style.configure("TButton", padding=6, font=("Segoe UI", 9))
        
        # State
        self.data_manager = DataManager()
        self.current_mode = None
        self.mute_sounds = tk.BooleanVar(value=False)
        self.running_job = None # For after() cancelation

        self.setup_ui()

    def play_sound(self):
        if not self.mute_sounds.get():
            self.bell()

    def setup_ui(self):
        # Top Bar
        top_bar = ttk.Frame(self)
        top_bar.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(top_bar, text="MOUSE MASTERY", style="Header.TLabel").pack(side=tk.LEFT)
        
        controls = ttk.Frame(top_bar)
        controls.pack(side=tk.RIGHT)
        
        ttk.Checkbutton(controls, text="Mute Sounds", variable=self.mute_sounds).pack(side=tk.LEFT, padx=10)
        ttk.Button(controls, text="Guide", command=self.show_guide).pack(side=tk.LEFT)

        # Main Layout
        container = ttk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Sidebar (Mode Selection)
        sidebar = ttk.Frame(container, style="Sidebar.TFrame", width=250)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        ttk.Label(sidebar, text="Select Mode", background=PANEL_BG, font=("Segoe UI", 12, "bold")).pack(pady=10)
        
        # Scrollable list for modes
        canvas_sb = tk.Canvas(sidebar, bg=PANEL_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(sidebar, orient="vertical", command=canvas_sb.yview)
        scrollable_frame = ttk.Frame(canvas_sb, style="Sidebar.TFrame")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas_sb.configure(scrollregion=canvas_sb.bbox("all"))
        )

        canvas_sb.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas_sb.configure(yscrollcommand=scrollbar.set)

        canvas_sb.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Create Mode Buttons
        for mode_name, desc in MODE_DESCRIPTIONS.items():
            btn = tk.Button(scrollable_frame, text=mode_name, 
                            bg=PANEL_BG, fg=FG_COLOR, 
                            activebackground=ACCENT_COLOR, activeforeground="white",
                            relief=tk.FLAT, anchor="w", padx=10, pady=5,
                            command=lambda m=mode_name: self.load_mode(m))
            btn.pack(fill=tk.X, pady=1)
            ToolTip(btn, desc)

        # Content Area
        self.content_frame = tk.Frame(container, bg=BG_COLOR)
        self.content_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10)
        
        # Default Welcome Screen
        self.show_welcome()

    def show_guide(self):
        guide_text = "MODE GUIDE:\n\n" + "\n\n".join([f"{k}: {v}" for k,v in MODE_DESCRIPTIONS.items()])
        
        win = tk.Toplevel(self)
        win.title("User Guide")
        win.geometry("600x500")
        txt = tk.Text(win, wrap=tk.WORD, padx=10, pady=10)
        txt.insert(tk.END, guide_text)
        txt.config(state=tk.DISABLED)
        txt.pack(fill=tk.BOTH, expand=True)

    def show_welcome(self):
        self.clear_content()
        tk.Label(self.content_frame, text="Welcome to Mouse Mastery", 
                 font=("Segoe UI", 24), bg=BG_COLOR, fg=FG_COLOR).pack(pady=50)
        tk.Label(self.content_frame, text="Select a training mode from the sidebar to begin.\nHover over modes for details.", 
                 font=("Segoe UI", 12), bg=BG_COLOR, fg="#aaaaaa").pack()

    def clear_content(self):
        if self.running_job:
            self.after_cancel(self.running_job)
            self.running_job = None
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def load_mode(self, mode_name):
        self.clear_content()
        self.current_mode = mode_name
        
        # Header for the mode
        header = tk.Frame(self.content_frame, bg=BG_COLOR)
        header.pack(fill=tk.X, pady=(0, 20))
        tk.Label(header, text=mode_name, font=("Segoe UI", 18, "bold"), bg=BG_COLOR, fg=FG_COLOR).pack(side=tk.LEFT)
        
        best = self.data_manager.get_best_score(mode_name, lower_is_better=("Reflex" in mode_name or "Drift" in mode_name))
        tk.Label(header, text=f"Personal Best: {best}", font=("Segoe UI", 12), bg=BG_COLOR, fg=ACCENT_COLOR).pack(side=tk.RIGHT)

        # Dispatcher
        mode_id = int(mode_name.split(".")[0])
        
        if mode_id == 1: self.mode_cps()
        elif mode_id == 2: self.mode_interval()
        elif mode_id == 3: self.mode_reaction_choice()
        elif mode_id == 4: self.mode_reflex()
        elif mode_id == 5: self.mode_speed_analysis()
        elif mode_id == 6: self.mode_rhythm()
        elif mode_id == 7: self.mode_precision_hold()
        elif mode_id == 8: self.mode_pattern()
        elif mode_id == 9: self.mode_drift()
        elif mode_id == 10: self.mode_targets()
        elif mode_id == 11: self.mode_dodge()
        elif mode_id == 12: self.mode_builder()
        elif mode_id == 13: self.mode_endurance()
        elif mode_id == 14: self.mode_grid()
        elif mode_id == 15: self.mode_sprints()

    # -------------------------------------------------------------------------
    # MODE IMPLEMENTATIONS
    # -------------------------------------------------------------------------

    # --- Mode 1: Speed Test (CPS) ---
    def mode_cps(self):
        duration_var = tk.IntVar(value=10)
        
        controls = tk.Frame(self.content_frame, bg=BG_COLOR)
        controls.pack()
        tk.Label(controls, text="Duration (s):", bg=BG_COLOR, fg=FG_COLOR).pack(side=tk.LEFT)
        tk.Spinbox(controls, from_=1, to=60, textvariable=duration_var, width=5).pack(side=tk.LEFT, padx=5)
        
        click_area = tk.Button(self.content_frame, text="CLICK TO START", font=("Arial", 20, "bold"),
                               bg=PANEL_BG, fg=FG_COLOR, activebackground=PANEL_BG, activeforeground=FG_COLOR)
        click_area.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)
        
        state = {"clicks": 0, "active": False, "start_time": 0}

        def end_game():
            state["active"] = False
            click_area.config(text=f"Done! {state['clicks']} clicks.\nCPS: {state['clicks']/duration_var.get():.2f}", state=tk.NORMAL)
            self.data_manager.save_score(self.current_mode, state['clicks'], "clicks")

        def click_handler(e):
            if not state["active"]:
                if click_area['text'].startswith("Done"):
                    # Reset
                    state["clicks"] = 0
                    click_area.config(text="CLICK TO START")
                    return

                state["active"] = True
                state["start_time"] = time.time()
                state["clicks"] = 1
                self.play_sound()
                # Schedule end
                self.running_job = self.after(duration_var.get() * 1000, end_game)
                update_timer()
            else:
                state["clicks"] += 1
                self.play_sound()
        
        def update_timer():
            if state["active"]:
                elapsed = time.time() - state["start_time"]
                remaining = max(0, duration_var.get() - elapsed)
                click_area.config(text=f"{state['clicks']}\n{remaining:.1f}s")
                if remaining > 0:
                    self.after(50, update_timer)

        click_area.bind("<Button-1>", click_handler)

    # --- Mode 2: Perfect Interval ---
    def mode_interval(self):
        tk.Label(self.content_frame, text="Try to click exactly every 1.00 seconds.", bg=BG_COLOR, fg="#aaa").pack()
        
        feedback_lbl = tk.Label(self.content_frame, text="WAITING...", font=("Arial", 24), bg=BG_COLOR, fg=FG_COLOR)
        feedback_lbl.pack(expand=True)
        
        state = {"last_click": 0}

        def click_handler(e):
            now = time.time()
            if state["last_click"] == 0:
                state["last_click"] = now
                feedback_lbl.config(text="Timer Started...")
                return
            
            diff = now - state["last_click"]
            state["last_click"] = now
            
            # Grading
            score = abs(1.0 - diff)
            if score < 0.05:
                bg = SUCCESS_COLOR
                msg = "PERFECT!"
                self.play_sound()
            elif score < 0.15:
                bg = WARNING_COLOR
                msg = "Good"
            else:
                bg = DANGER_COLOR
                msg = "Miss"

            feedback_lbl.config(text=f"{diff:.3f}s\n{msg}", bg=bg)
            self.content_frame.config(bg=bg) # Flash background
            self.after(100, lambda: self.content_frame.config(bg=BG_COLOR))
            
            self.data_manager.save_score(self.current_mode, round(diff, 3), "seconds")

        self.content_frame.bind("<Button-1>", click_handler)

    # --- Mode 3: Reaction Choice ---
    def mode_reaction_choice(self):
        canvas = tk.Canvas(self.content_frame, bg=BG_COLOR, highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        
        state = {"score": 0, "active": False}
        
        score_lbl = canvas.create_text(WIDTH/2, 50, text="Score: 0", fill="white", font=("Arial", 16))
        
        def flash():
            if not self.current_mode: return
            is_target = random.choice([True, False])
            color = SUCCESS_COLOR if is_target else DANGER_COLOR
            text = "CLICK!" if is_target else "DON'T CLICK!"
            
            rect = canvas.create_rectangle(0, 100, WIDTH, HEIGHT, fill=color, outline="")
            txt = canvas.create_text(WIDTH/2, HEIGHT/2, text=text, font=("Arial", 40, "bold"))
            
            state["is_target"] = is_target
            state["clicked"] = False
            
            # Window to react
            self.running_job = self.after(random.randint(400, 800), lambda: clear_flash(rect, txt))
        
        def clear_flash(rect, txt):
            canvas.delete(rect)
            canvas.delete(txt)
            state["is_target"] = None
            # Next round delay
            self.running_job = self.after(random.randint(1000, 2000), flash)

        def on_click(e):
            if state.get("is_target") is True:
                if not state["clicked"]:
                    state["score"] += 1
                    state["clicked"] = True
                    self.play_sound()
            elif state.get("is_target") is False:
                state["score"] -= 1
                canvas.config(bg=DANGER_COLOR)
                self.after(50, lambda: canvas.config(bg=BG_COLOR))
            
            canvas.itemconfig(score_lbl, text=f"Score: {state['score']}")
            self.data_manager.save_score(self.current_mode, state['score'], "points")

        canvas.bind("<Button-1>", on_click)
        flash()

    # --- Mode 4: Audio/Visual Reflex ---
    def mode_reflex(self):
        canvas = tk.Canvas(self.content_frame, bg=BG_COLOR)
        canvas.pack(fill=tk.BOTH, expand=True)
        
        lbl = tk.Label(self.content_frame, text="Click when the screen flashes GREEN.", font=("Arial", 14), bg=BG_COLOR, fg=FG_COLOR)
        lbl.place(relx=0.5, rely=0.1, anchor="center")
        
        state = {"waiting": True, "flash_time": 0}

        def start_sequence():
            canvas.config(bg=BG_COLOR)
            state["waiting"] = True
            delay = random.randint(2000, 5000)
            self.running_job = self.after(delay, trigger_flash)

        def trigger_flash():
            canvas.config(bg=SUCCESS_COLOR)
            state["waiting"] = False
            state["flash_time"] = time.time()
            self.play_sound()

        def on_click(e):
            if state["waiting"]:
                lbl.config(text="Too early! Wait for green.")
                if self.running_job: self.after_cancel(self.running_job)
                start_sequence()
            else:
                reaction = (time.time() - state["flash_time"]) * 1000
                lbl.config(text=f"Reaction: {int(reaction)} ms")
                self.data_manager.save_score(self.current_mode, int(reaction), "ms")
                start_sequence()

        canvas.bind("<Button-1>", on_click)
        start_sequence()

    # --- Mode 5: Speed Analysis ---
    def mode_speed_analysis(self):
        # Similar to CPS but calculates average delta
        lbl = tk.Label(self.content_frame, text="Click as fast as you can!\nAnalyzing interval...", font=("Arial", 16), bg=BG_COLOR, fg=FG_COLOR)
        lbl.pack(expand=True)
        
        state = {"clicks": [], "last_click": 0}

        def on_click(e):
            now = time.time()
            if state["last_click"] != 0:
                delta = (now - state["last_click"]) * 1000
                state["clicks"].append(delta)
                
                # Keep last 10
                state["clicks"] = state["clicks"][-10:]
                avg = sum(state["clicks"]) / len(state["clicks"])
                lbl.config(text=f"Instant: {int(delta)}ms\nAvg (last 10): {int(avg)}ms")
                self.play_sound()
            
            state["last_click"] = now
            if len(state["clicks"]) > 5:
                self.data_manager.save_score(self.current_mode, int(sum(state["clicks"])/len(state["clicks"])), "ms_avg")

        self.content_frame.bind("<Button-1>", on_click)

    # --- Mode 6: Rhythm Match ---
    def mode_rhythm(self):
        bpm = 60
        interval_ms = int(60000 / bpm)
        
        canvas = tk.Canvas(self.content_frame, bg=BG_COLOR)
        canvas.pack(fill=tk.BOTH, expand=True)
        
        info = tk.Label(canvas, text="Click on the beat (Visual pulse)", bg=BG_COLOR, fg="white", font=("Arial", 12))
        info.place(x=10, y=10)
        
        state = {"last_beat": 0}

        def beat():
            state["last_beat"] = time.time()
            self.play_sound()
            # Visual Pulse
            canvas.create_oval(WIDTH/2-50, HEIGHT/2-50, WIDTH/2+50, HEIGHT/2+50, fill=ACCENT_COLOR, outline="")
            self.after(100, lambda: canvas.delete("all"))
            self.running_job = self.after(interval_ms, beat)

        def check_click(e):
            now = time.time()
            # Calculate distance to nearest beat
            # We predict the next beat based on interval
            time_since = (now - state["last_beat"]) * 1000
            time_to_next = interval_ms - time_since
            
            offset = min(time_since, abs(time_to_next))
            
            accuracy = max(0, 100 - (offset / 5)) # Simple scoring
            info.config(text=f"Offset: {int(offset)}ms | Accuracy: {int(accuracy)}%")
            self.data_manager.save_score(self.current_mode, int(accuracy), "%")

        canvas.bind("<Button-1>", check_click)
        beat()

    # --- Mode 7: Precision Hold ---
    def mode_precision_hold(self):
        target = 1.50
        lbl = tk.Label(self.content_frame, text=f"Hold Mouse for exactly {target}s", font=("Arial", 20), bg=BG_COLOR, fg=FG_COLOR)
        lbl.pack(expand=True)
        
        state = {"start": 0}

        def press(e):
            state["start"] = time.time()
            lbl.config(text="Holding...", fg=ACCENT_COLOR)

        def release(e):
            duration = time.time() - state["start"]
            diff = abs(target - duration)
            color = SUCCESS_COLOR if diff < 0.1 else DANGER_COLOR
            lbl.config(text=f"Held: {duration:.3f}s\nDiff: {diff:.3f}s", fg=color)
            if diff < 0.1: self.play_sound()
            self.data_manager.save_score(self.current_mode, round(diff, 3), "diff_sec")

        self.content_frame.bind("<Button-1>", press)
        self.content_frame.bind("<ButtonRelease-1>", release)

    # --- Mode 8: Pattern Copy ---
    def mode_pattern(self):
        # Simply mimics Short-Long-Short patterns visually
        lbl = tk.Label(self.content_frame, text="Watch the circle, then mimic.", font=("Arial", 14), bg=BG_COLOR, fg=FG_COLOR)
        lbl.pack(pady=20)
        
        canvas = tk.Canvas(self.content_frame, bg=BG_COLOR, height=200)
        canvas.pack(fill=tk.X)
        indicator = canvas.create_oval(WIDTH/2-30, 70, WIDTH/2+30, 130, fill="#444")
        
        btn = tk.Button(self.content_frame, text="Start Pattern", font=("Arial", 12),
                        command=lambda: play_pattern())
        btn.pack()
        
        current_pattern = [] # list of durations
        user_input = []
        state = {"last_press": 0}

        def play_pattern():
            user_input.clear()
            current_pattern.clear()
            # Generate random pattern (e.g. 3 blinks)
            pattern_steps = [random.choice([0.2, 0.6]) for _ in range(4)]
            
            def run_step(idx):
                if idx >= len(pattern_steps):
                    lbl.config(text="YOUR TURN!")
                    return
                
                dur = pattern_steps[idx]
                current_pattern.append(dur)
                
                canvas.itemconfig(indicator, fill=ACCENT_COLOR)
                self.play_sound()
                # Light on duration
                self.after(int(dur*1000), lambda: canvas.itemconfig(indicator, fill="#444"))
                # Pause between
                self.after(int(dur*1000) + 300, lambda: run_step(idx+1))

            run_step(0)

        def press(e):
            state["last_press"] = time.time()
            canvas.itemconfig(indicator, fill=SUCCESS_COLOR)

        def release(e):
            dur = time.time() - state["last_press"]
            user_input.append(dur)
            canvas.itemconfig(indicator, fill="#444")
            
            if len(user_input) == len(current_pattern):
                # Grade
                total_err = sum([abs(u - p) for u, p in zip(user_input, current_pattern)])
                lbl.config(text=f"Total Error: {total_err:.2f}s")
                self.data_manager.save_score(self.current_mode, round(total_err, 2), "err_sec")

        self.content_frame.bind("<Button-1>", press)
        self.content_frame.bind("<ButtonRelease-1>", release)

    # --- Mode 9: Reaction Drift ---
    def mode_drift(self):
        canvas = tk.Canvas(self.content_frame, bg=BG_COLOR)
        canvas.pack(fill=tk.BOTH, expand=True)
        
        # Center marker
        canvas.create_line(WIDTH/2, 0, WIDTH/2, HEIGHT, fill="gray", dash=(4, 4))
        
        state = {"pos": WIDTH/2, "velocity": 2, "score": 0}
        
        player = canvas.create_rectangle(state["pos"]-20, HEIGHT/2-20, state["pos"]+20, HEIGHT/2+20, fill=ACCENT_COLOR)
        score_txt = canvas.create_text(50, 50, text="Score: 0", fill="white", anchor="nw")

        def loop():
            # Drift logic: increase velocity over time
            state["velocity"] += 0.05 if state["velocity"] > 0 else -0.05
            
            # Move
            state["pos"] += state["velocity"]
            canvas.coords(player, state["pos"]-20, HEIGHT/2-20, state["pos"]+20, HEIGHT/2+20)
            
            # Check bounds
            if state["pos"] < 0 or state["pos"] > WIDTH:
                canvas.create_text(WIDTH/2, HEIGHT/2, text="GAME OVER", fill=DANGER_COLOR, font=("Arial", 30))
                self.data_manager.save_score(self.current_mode, state["score"], "pushes")
                return

            self.running_job = self.after(20, loop)

        def push_back(e):
            # Reverse velocity and reduce it slightly (stabilize)
            state["velocity"] = -state["velocity"] * 0.8
            # Add random erratic behavior
            state["velocity"] += random.uniform(-1, 1)
            state["score"] += 1
            canvas.itemconfig(score_txt, text=f"Score: {state['score']}")

        canvas.bind("<Button-1>", push_back)
        loop()

    # --- Mode 10: Target Chase ---
    def mode_targets(self):
        canvas = tk.Canvas(self.content_frame, bg=BG_COLOR)
        canvas.pack(fill=tk.BOTH, expand=True)
        
        state = {"score": 0, "active_target": None}
        score_display = canvas.create_text(50, 30, text="Score: 0", fill="white", anchor="nw")

        def spawn():
            if state["active_target"]:
                canvas.delete(state["active_target"])
                state["score"] -= 1 # Penalty for miss
            
            r = 20
            x = random.randint(r, WIDTH-r)
            y = random.randint(r, HEIGHT-r)
            
            state["active_target"] = canvas.create_oval(x-r, y-r, x+r, y+r, fill=ACCENT_COLOR, outline="white")
            canvas.tag_bind(state["active_target"], "<Button-1>", hit)
            
            canvas.itemconfig(score_display, text=f"Score: {state['score']}")
            
            # Speed increases with score
            delay = max(400, 1000 - (state["score"] * 10))
            self.running_job = self.after(delay, spawn)

        def hit(e):
            state["score"] += 1
            self.play_sound()
            canvas.delete(state["active_target"])
            state["active_target"] = None
            if self.running_job: self.after_cancel(self.running_job)
            spawn()

        spawn()

    # --- Mode 11: Click & Dodge ---
    def mode_dodge(self):
        canvas = tk.Canvas(self.content_frame, bg=BG_COLOR)
        canvas.pack(fill=tk.BOTH, expand=True)
        
        player = canvas.create_oval(0,0,30,30, fill="white", outline=ACCENT_COLOR)
        
        objects = [] # {id, type, speed}
        state = {"score": 0, "game_over": False}
        
        score_txt = canvas.create_text(WIDTH-100, 30, text="Score: 0", fill="white")

        def game_loop():
            if state["game_over"]: return
            
            # Spawn
            if random.random() < 0.05:
                x = random.randint(20, WIDTH-20)
                is_bad = random.choice([True, True, False]) # More bad than good
                color = DANGER_COLOR if is_bad else SUCCESS_COLOR
                oid = canvas.create_rectangle(x-15, -30, x+15, 0, fill=color)
                objects.append({"id": oid, "bad": is_bad, "speed": random.randint(3, 8)})

            # Move
            px1, py1, px2, py2 = canvas.coords(player)
            pcx, pcy = (px1+px2)/2, (py1+py2)/2
            
            for obj in objects[:]:
                canvas.move(obj["id"], 0, obj["speed"])
                c = canvas.coords(obj["id"])
                
                # Collision with player
                if c[3] >= py1 and c[1] <= py2 and c[2] >= px1 and c[0] <= px2:
                    if obj["bad"]:
                        end_game()
                        return
                
                # Cleanup
                if c[1] > HEIGHT:
                    canvas.delete(obj["id"])
                    objects.remove(obj)

            self.running_job = self.after(20, game_loop)

        def mouse_move(e):
            if state["game_over"]: return
            canvas.coords(player, e.x-15, e.y-15, e.x+15, e.y+15)

        def click_obj(e):
            # Check if clicked a green object
            x, y = e.x, e.y
            closest = canvas.find_closest(x, y)
            for obj in objects:
                if obj["id"] == closest[0] and not obj["bad"]:
                    state["score"] += 10
                    canvas.itemconfig(score_txt, text=f"Score: {state['score']}")
                    canvas.delete(obj["id"])
                    objects.remove(obj)
                    self.play_sound()
                    return

        def end_game():
            state["game_over"] = True
            canvas.create_text(WIDTH/2, HEIGHT/2, text="GAME OVER", fill="white", font=("Arial", 40))
            self.data_manager.save_score(self.current_mode, state["score"], "points")

        canvas.bind("<Motion>", mouse_move)
        canvas.bind("<Button-1>", click_obj)
        game_loop()

    # --- Mode 12: Click Builder ---
    def mode_builder(self):
        canvas = tk.Canvas(self.content_frame, bg=BG_COLOR)
        canvas.pack(fill=tk.BOTH, expand=True)
        
        # Pendulum line
        line = canvas.create_line(0, 50, WIDTH, 50, fill="gray")
        block_width = 100
        
        state = {"layer": 0, "dir": 5, "x": 0, "width": block_width, "game_over": False}
        
        current_block = canvas.create_rectangle(0, HEIGHT-30, block_width, HEIGHT, fill=ACCENT_COLOR)

        def loop():
            if state["game_over"]: return
            
            # Move current block back and forth
            x1, y1, x2, y2 = canvas.coords(current_block)
            
            if x2 >= WIDTH or x1 <= 0:
                state["dir"] *= -1
            
            canvas.move(current_block, state["dir"], 0)
            self.running_job = self.after(20, loop)

        def place_block(e):
            if state["game_over"]: 
                reset()
                return

            x1, y1, x2, y2 = canvas.coords(current_block)
            
            # Check overlap with previous (or ground)
            # Simplification: If it's the first block, it's always safe
            # If layer > 0, check against width
            
            state["layer"] += 1
            self.play_sound()
            
            # Create new moving block on top
            new_y = HEIGHT - 30 * (state["layer"] + 1)
            
            # Make the old block static (visual only, logic simplified for brevity)
            canvas.create_rectangle(x1, y1, x2, y2, fill="#555")
            
            # Reset current block to top
            canvas.coords(current_block, 0, new_y, state["width"], new_y+30)
            
            if state["layer"] > 20:
                canvas.create_text(WIDTH/2, HEIGHT/2, text="WINNER!", fill=SUCCESS_COLOR, font=("Arial", 40))
                state["game_over"] = True
                self.data_manager.save_score(self.current_mode, state["layer"], "floors")

        def reset():
            self.load_mode("12. Click Builder")

        canvas.bind("<Button-1>", place_block)
        loop()

    # --- Mode 13: Endurance ---
    def mode_endurance(self):
        lbl = tk.Label(self.content_frame, text="Endurance: Click consistently for 60 seconds.", font=("Arial", 14), bg=BG_COLOR, fg=FG_COLOR)
        lbl.pack(pady=20)
        
        stats = tk.Label(self.content_frame, text="Clicks: 0 | Time: 0s", font=("Arial", 12), bg=BG_COLOR, fg="#aaa")
        stats.pack()
        
        btn = tk.Button(self.content_frame, text="CLICK HERE", font=("Arial", 20), height=5, width=20, bg=PANEL_BG, fg=FG_COLOR)
        btn.pack(pady=20)
        
        state = {"clicks": 0, "start": 0, "active": False}
        
        def click(e):
            if not state["active"]:
                state["active"] = True
                state["start"] = time.time()
                update_time()
            
            state["clicks"] += 1
            
        def update_time():
            if not state["active"]: return
            elapsed = time.time() - state["start"]
            stats.config(text=f"Clicks: {state['clicks']} | Time: {int(elapsed)}s")
            
            if elapsed >= 60:
                state["active"] = False
                btn.config(state=tk.DISABLED, text="FINISHED")
                self.data_manager.save_score(self.current_mode, state['clicks'], "clicks_60s")
            else:
                self.running_job = self.after(100, update_time)

        btn.bind("<Button-1>", click)

    # --- Mode 14: Grid Focus ---
    def mode_grid(self):
        frame = tk.Frame(self.content_frame, bg=BG_COLOR)
        frame.pack(expand=True)
        
        grid_buttons = []
        rows, cols = 5, 5
        
        state = {"active_idx": -1, "score": 0}

        def click_handler(idx):
            if idx == state["active_idx"]:
                state["score"] += 1
                self.play_sound()
                next_light()
            else:
                state["score"] -= 1
            
            # Update score in title or separate label (simplified here)
            self.title(f"{APP_TITLE} - Score: {state['score']}")

        for i in range(rows * cols):
            btn = tk.Button(frame, width=8, height=4, bg="#444", 
                            command=lambda x=i: click_handler(x))
            btn.grid(row=i//cols, column=i%cols, padx=2, pady=2)
            grid_buttons.append(btn)

        def next_light():
            # Reset old
            if state["active_idx"] != -1:
                grid_buttons[state["active_idx"]].config(bg="#444")
            
            state["active_idx"] = random.randint(0, len(grid_buttons)-1)
            grid_buttons[state["active_idx"]].config(bg=SUCCESS_COLOR)

        next_light()

    # --- Mode 15: Click Sprints ---
    def mode_sprints(self):
        lbl = tk.Label(self.content_frame, text="Sprint (3s) / Rest (3s)", font=("Arial", 24), bg=BG_COLOR, fg=FG_COLOR)
        lbl.pack(pady=50)
        
        state = {"phase": "REST", "clicks": 0, "round": 1}
        
        def cycle():
            if state["phase"] == "REST":
                state["phase"] = "SPRINT"
                lbl.config(text="GO! GO! GO!", fg=SUCCESS_COLOR)
                state["clicks"] = 0
                self.content_frame.bind("<Button-1>", count_click)
                self.running_job = self.after(3000, cycle)
            else:
                state["phase"] = "REST"
                lbl.config(text=f"Round {state['round']} Score: {state['clicks']}\nRest...", fg=WARNING_COLOR)
                self.content_frame.unbind("<Button-1>")
                
                self.data_manager.save_score(self.current_mode, state['clicks'], f"rnd_{state['round']}")
                state["round"] += 1
                self.running_job = self.after(3000, cycle)

        def count_click(e):
            state["clicks"] += 1
            self.play_sound()

        cycle()

# -----------------------------------------------------------------------------
# ENTRY POINT
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app = MouseApp()
    app.mainloop()