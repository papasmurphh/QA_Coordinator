import tkinter as tk
from tkinter import font as tkfont
import time
import random

# --- Visual Configuration ---
# A modern, flat UI color palette and font configuration.
class Theme:
    BACKGROUND = "#1e1e1e"  # Very dark grey
    FOREGROUND = "#f0f0f0"  # Off-white
    PRIMARY = "#00bcd4"      # Vibrant Teal
    PRIMARY_HOVER = "#00acc1" # Darker Teal
    SECONDARY = "#9c27b0"    # Vibrant Purple
    SECONDARY_HOVER = "#8e24aa" # Darker Purple
    
    WAIT_COLOR = "#f44336"   # Red
    GO_COLOR = "#4CAF50"     # Green
    RESULT_COLOR = "#FFC107"  # Amber/Yellow
    ERROR_COLOR = "#37474F"    # Slate Grey
    
    FONT_TITLE = ("Segoe UI", 36, "bold")
    FONT_HEADER = ("Segoe UI", 24, "bold")
    FONT_BODY = ("Segoe UI", 16)
    FONT_BUTTON = ("Segoe UI", 14, "bold")
    FONT_CANVAS_BIG = ("Segoe UI", 72, "bold")
    FONT_CANVAS_SMALL = ("Segoe UI", 20)

# --- Game Configuration ---
TOTAL_ROUNDS = 5
MIN_WAIT_TIME = 1.5
MAX_WAIT_TIME = 4.0

# --- Custom Widget for Hover Effects ---
class HoverButton(tk.Button):
    """A custom button that changes color on mouse hover."""
    def __init__(self, master, hover_bg, **kw):
        super().__init__(master=master, **kw)
        self.default_bg = self["background"]
        self.hover_bg = hover_bg
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)

    def on_enter(self, e):
        self["background"] = self.hover_bg

    def on_leave(self, e):
        self["background"] = self.default_bg

# --- Main Application Class ---
class ReactionTesterApp(tk.Tk):
    """
    The main window for the application. Manages switching between frames
    and handles global key bindings.
    """
    def __init__(self):
        super().__init__()
        self.title("Reaction Time Tester")
        self.geometry("800x600")
        self.configure(bg=Theme.BACKGROUND)
        self.resizable(False, False)

        # Global key binding to exit the app with the Escape key
        self.bind('<Escape>', lambda e: self.destroy())

        container = tk.Frame(self, bg=Theme.BACKGROUND)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for F in (MainMenuFrame, GameFrame, ResultsFrame):
            frame = F(container, self)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame(MainMenuFrame)

    def show_frame(self, cont):
        frame = self.frames[cont]
        frame.tkraise()

    def start_game(self, mode):
        game_frame = self.frames[GameFrame]
        game_frame.setup_game(mode)
        self.show_frame(GameFrame)

    def show_results(self, results, mode):
        results_frame = self.frames[ResultsFrame]
        results_frame.display_results(results, mode)
        self.show_frame(ResultsFrame)

# --- Main Menu Frame ---
class MainMenuFrame(tk.Frame):
    """The first screen, providing game mode selection."""
    def __init__(self, parent, controller):
        super().__init__(parent, bg=Theme.BACKGROUND)
        
        title_label = tk.Label(self, text="Reaction Time Tester", font=Theme.FONT_TITLE, fg=Theme.FOREGROUND, bg=Theme.BACKGROUND)
        title_label.pack(pady=(80, 10))

        subtitle_label = tk.Label(self, text="Select your challenge. Press ESC at any time to quit.", font=Theme.FONT_BODY, fg=Theme.PRIMARY, bg=Theme.BACKGROUND)
        subtitle_label.pack(pady=(0, 40))

        button_frame = tk.Frame(self, bg=Theme.BACKGROUND)
        button_frame.pack(pady=20)
        
        # Mode 1: Mouse click
        mouse_button = HoverButton(button_frame, text="Mouse Reaction Test", font=Theme.FONT_BUTTON,
                                   command=lambda: controller.start_game('mouse'),
                                   bg=Theme.PRIMARY, fg=Theme.FOREGROUND, relief="flat",
                                   hover_bg=Theme.PRIMARY_HOVER, borderwidth=0, padx=20, pady=10)
        mouse_button.pack(pady=10)

        # Mode 2: Any key press
        keyboard_any_button = HoverButton(button_frame, text="Keyboard Reaction Test (Any Key)", font=Theme.FONT_BUTTON,
                                          command=lambda: controller.start_game('keyboard_any'),
                                          bg=Theme.SECONDARY, fg=Theme.FOREGROUND, relief="flat",
                                          hover_bg=Theme.SECONDARY_HOVER, borderwidth=0, padx=20, pady=10)
        keyboard_any_button.pack(pady=10)
        
        # Mode 3: Specific key press
        keyboard_choice_button = HoverButton(button_frame, text="Keyboard Reaction Test (Choice)", font=Theme.FONT_BUTTON,
                                             command=lambda: controller.start_game('keyboard_choice'),
                                             bg=Theme.PRIMARY, fg=Theme.FOREGROUND, relief="flat",
                                             hover_bg=Theme.PRIMARY_HOVER, borderwidth=0, padx=20, pady=10)
        keyboard_choice_button.pack(pady=10)

# --- Game Frame ---
class GameFrame(tk.Frame):
    """The main game screen where the test takes place."""
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        self.canvas = tk.Canvas(self, bg=Theme.BACKGROUND, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.round_label = tk.Label(self, text="", font=Theme.FONT_BODY, fg=Theme.FOREGROUND, bg=Theme.BACKGROUND)
        self.round_label.place(relx=0.5, rely=0.95, anchor="center")

        self.game_mode = None
        self.results = []
        self.current_round = 0
        self.state = "idle"
        self.start_time = 0
        self.scheduled_task = None
        
        self.color_map = {
            'Red': (Theme.WAIT_COLOR, '1'),
            'Green': (Theme.GO_COLOR, '2'),
            'Blue': (Theme.PRIMARY, '3')
        }
        self.current_color_name = None

    def setup_game(self, mode):
        self.game_mode = mode
        self.results = []
        self.current_round = 0
        self.start_new_round()

    def start_new_round(self):
        self.current_round += 1
        if self.current_round > TOTAL_ROUNDS:
            self.controller.show_results(self.results, self.game_mode)
            return

        self.state = "waiting"
        self.draw_canvas_state("Wait...", Theme.WAIT_COLOR, "The test will begin shortly.")
        self.round_label.config(text=f"Round: {self.current_round} / {TOTAL_ROUNDS}")
        
        self.unbind_all_input()
        delay_ms = int(random.uniform(MIN_WAIT_TIME, MAX_WAIT_TIME) * 1000)
        self.scheduled_task = self.after(delay_ms, self.trigger_change)
        self.bind_input()

    def trigger_change(self):
        self.state = "ready"
        # Logic for simple reaction tests (mouse and any-key)
        if self.game_mode == 'mouse':
            self.draw_canvas_state("CLICK!", Theme.GO_COLOR)
        elif self.game_mode == 'keyboard_any':
            self.draw_canvas_state("PRESS!", Theme.GO_COLOR)
        # Logic for choice reaction test
        else: # keyboard_choice
            self.current_color_name, (color_hex, _) = random.choice(list(self.color_map.items()))
            required_key = self.color_map[self.current_color_name][1]
            self.draw_canvas_state(f"Press '{required_key}'!", color_hex)
        
        self.animate_ready_text()
        self.start_time = time.perf_counter()

    def handle_input(self, event):
        if self.state == "waiting":
            self.state = "false_start"
            self.after_cancel(self.scheduled_task)
            self.unbind_all_input()
            self.draw_canvas_state("Too Soon!", Theme.ERROR_COLOR, "Click or press any key to retry.")
            self.current_round -= 1
            self.bind_all_for_restart()
            return

        if self.state == "ready":
            # Check for wrong key ONLY in the choice-based test
            if self.game_mode == 'keyboard_choice':
                required_key = self.color_map[self.current_color_name][1]
                if not hasattr(event, 'char') or event.char != required_key:
                    self.handle_wrong_key()
                    return

            end_time = time.perf_counter()
            reaction_time_ms = (end_time - self.start_time) * 1000
            self.results.append(reaction_time_ms)
            
            self.state = "idle"
            self.unbind_all_input()
            self.draw_canvas_state(f"{reaction_time_ms:.2f} ms", Theme.RESULT_COLOR, "Next round starting soon...")
            self.after(2000, self.start_new_round)

    def handle_wrong_key(self):
        self.state = "wrong_key"
        self.unbind_all_input()
        self.draw_canvas_state("Wrong Key!", Theme.ERROR_COLOR, "Click or press any key to retry.")
        self.current_round -= 1
        self.bind_all_for_restart()

    def draw_canvas_state(self, main_text, color, sub_text=""):
        self.canvas.delete("all")
        width = self.winfo_width()
        height = self.winfo_height()
        
        diameter = min(width, height) * 0.6
        x1, y1 = (width - diameter) / 2, (height - diameter) / 2
        x2, y2 = x1 + diameter, y1 + diameter
        self.canvas.create_oval(x1, y1, x2, y2, fill=color, outline="")

        self.canvas.create_text(width/2, height/2, text=main_text, font=Theme.FONT_CANVAS_BIG, fill=Theme.FOREGROUND, tags="main_text")
        if sub_text:
            self.canvas.create_text(width/2, y2 + 40, text=sub_text, font=Theme.FONT_BODY, fill=Theme.FOREGROUND)

    def animate_ready_text(self, step=0):
        if self.state != "ready" or step > 10: return
        base_size = Theme.FONT_CANVAS_BIG[1]
        new_size = int(base_size + step * 1.5)
        font_tuple = (Theme.FONT_CANVAS_BIG[0], new_size, Theme.FONT_CANVAS_BIG[2])
        self.canvas.itemconfig("main_text", font=font_tuple)
        self.after(25, self.animate_ready_text, step + 1)

    def bind_input(self):
        self.focus_set()
        if self.game_mode == 'mouse':
            self.canvas.bind("<Button-1>", self.handle_input)
        else: # Covers both 'keyboard_any' and 'keyboard_choice'
            self.bind("<Key>", self.handle_input)

    def bind_all_for_restart(self):
        self.focus_set()
        self.canvas.bind("<Button-1>", lambda e: self.start_new_round())
        self.bind("<Key>", lambda e: self.start_new_round())

    def unbind_all_input(self):
        self.canvas.unbind("<Button-1>")
        self.unbind("<Key>")

# --- Results Frame ---
class ResultsFrame(tk.Frame):
    """Displays the final results and an option to return to the menu."""
    def __init__(self, parent, controller):
        super().__init__(parent, bg=Theme.BACKGROUND)
        self.controller = controller
        
        self.title_label = tk.Label(self, text="", font=Theme.FONT_TITLE, fg=Theme.FOREGROUND, bg=Theme.BACKGROUND)
        self.title_label.pack(pady=(60, 20))

        self.results_text = tk.Text(self, font=("Courier New", 14), height=7, width=30,
                                     bg=Theme.BACKGROUND, fg=Theme.FOREGROUND, relief="flat", highlightthickness=0)
        self.results_text.pack(pady=10)
        
        self.avg_label = tk.Label(self, text="", font=Theme.FONT_HEADER, fg=Theme.PRIMARY, bg=Theme.BACKGROUND)
        self.avg_label.pack(pady=(20, 30))

        menu_button = HoverButton(self, text="Main Menu", font=Theme.FONT_BUTTON,
                                  command=lambda: controller.show_frame(MainMenuFrame),
                                  bg=Theme.PRIMARY, fg=Theme.FOREGROUND, relief="flat",
                                  hover_bg=Theme.PRIMARY_HOVER, borderwidth=0, padx=20, pady=10)
        menu_button.pack(pady=20)

    def display_results(self, results, mode):
        # Create a user-friendly title from the internal mode name
        mode_str = mode.replace('_', ' ').title()
        self.title_label.config(text=f"Results: {mode_str}")
        
        self.results_text.config(state="normal")
        self.results_text.delete('1.0', tk.END)

        if not results:
            self.results_text.insert(tk.END, "No rounds were completed.\n")
            self.avg_label.config(text="Average Time: N/A")
        else:
            header = f"{'Round':<10}{'Time (ms)':>15}\n"
            divider = "-"*25 + "\n"
            self.results_text.insert(tk.END, header)
            self.results_text.insert(tk.END, divider)
            for i, time_ms in enumerate(results):
                self.results_text.insert(tk.END, f"{i+1:<10}{time_ms:>15.2f}\n")
            
            average_time = sum(results) / len(results)
            self.avg_label.config(text=f"Average Time: {average_time:.2f} ms")
        
        self.results_text.config(state="disabled")

# --- Main execution ---
if __name__ == "__main__":
    app = ReactionTesterApp()
    app.mainloop()