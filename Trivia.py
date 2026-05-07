import tkinter as tk
import threading
import time
import urllib.request
import json
import random
import os
import html

HIGH_SCORE_FILE = 'highscore.json'

class TriviaGame:
    def __init__(self, master):
        self.master = master
        self.master.title('Trivia Game')
        self.master.geometry('800x600')

        self.categories = [
            ('General Knowledge', 9),
            ('Science & Nature', 17),
            ('History', 23),
            ('Sports', 21),
            ('Geography', 22),
            ('Film', 11),
            ('Music', 12),
            ('Computers', 18),
            ('Mythology', 20),
            ('Animals', 27),
        ]

        self.score = 0
        self.correct_count = 0
        self.questions = []
        self.current_q = 0
        self.start_time = None
        self.current_category = None

        self.load_highscores()
        self.main_menu()

    def load_highscores(self):
        if os.path.exists(HIGH_SCORE_FILE):
            with open(HIGH_SCORE_FILE, 'r') as f:
                try:
                    self.highscores = json.load(f)
                except json.JSONDecodeError:
                    self.highscores = []
        else:
            self.highscores = []

    def save_highscores(self):
        self.highscores.append({
            'category': self.current_category,
            'score': self.score,
            'correct': self.correct_count,
            'date': time.strftime('%Y-%m-%d %H:%M:%S')
        })
        self.highscores = sorted(
            self.highscores,
            key=lambda x: x['score'],
            reverse=True
        )[:3]
        with open(HIGH_SCORE_FILE, 'w') as f:
            json.dump(self.highscores, f, indent=4)

    def main_menu(self):
        self.current_category = None
        for w in self.master.winfo_children(): w.destroy()

        tk.Label(self.master, text='Select a Trivia Category', font=('Arial', 18)).pack(pady=20)
        frame = tk.Frame(self.master); frame.pack()

        for idx, (name, cid) in enumerate(self.categories):
            tk.Button(
                frame, text=name, width=20, height=2,
                command=lambda n=name, c=cid: self.start_category(n, c)
            ).grid(row=idx//2, column=idx%2, padx=10, pady=10)

    def start_category(self, category_name, category_id):
        self.current_category = category_name
        self.score = 0
        self.correct_count = 0
        self.current_q = 0

        for w in self.master.winfo_children(): w.destroy()
        tk.Label(self.master, text='Loading questions...', font=('Arial', 16)).pack(pady=20)

        threading.Thread(target=self.fetch_questions, args=(category_id,), daemon=True).start()

    def fetch_questions(self, category_id):
        url = f'https://opentdb.com/api.php?amount=10&category={category_id}&type=multiple'
        try:
            with urllib.request.urlopen(url) as resp:
                data = json.loads(resp.read().decode())
            self.questions = data.get('results', [])
        except:
            self.questions = []
        self.master.after(0, self.show_question)

    def show_question(self):
        for w in self.master.winfo_children(): w.destroy()
        if self.current_q >= len(self.questions):
            return self.end_game()

        q = self.questions[self.current_q]
        text = html.unescape(q['question'])
        self.correct_answer = html.unescape(q['correct_answer'])
        opts = [html.unescape(a) for a in q['incorrect_answers']] + [self.correct_answer]
        random.shuffle(opts)

        tk.Label(self.master, text=text, wraplength=700, font=('Arial', 16)).pack(pady=20)
        self.var = tk.StringVar(value=None)
        for o in opts:
            tk.Radiobutton(self.master, text=o, variable=self.var, value=o, font=('Arial', 14)).pack(anchor='w')

        self.feedback_lbl = tk.Label(self.master, text='', font=('Arial', 14))
        self.feedback_lbl.pack(pady=10)
        self.next_button = tk.Button(self.master, text='Next', font=('Arial', 14), command=self.submit_answer)
        self.next_button.pack(pady=20)

        self.start_time = time.time()

    def submit_answer(self):
        elapsed = time.time() - self.start_time
        sel = self.var.get()
        if sel == self.correct_answer:
            self.correct_count += 1
            bonus = max(0, int(15 - elapsed))
            pts = 10 + bonus
            self.score += pts
            fb = f"Correct! You earned {pts} points."
        else:
            fb = f"Wrong! The correct answer was: {self.correct_answer}"

        self.feedback_lbl.config(text=fb)
        for w in self.master.winfo_children():
            if isinstance(w, tk.Radiobutton): w.config(state='disabled')
        self.next_button.config(state='disabled')
        self.master.after(2000, self.next_question)

    def next_question(self):
        self.current_q += 1
        self.show_question()

    def end_game(self):
        self.save_highscores()
        for w in self.master.winfo_children(): w.destroy()

        tk.Label(self.master, text=f"Quiz Complete! Your Score: {self.score}", font=('Arial', 18)).pack(pady=10)
        tk.Label(self.master, text=f"You answered {self.correct_count} out of 10 correctly.", font=('Arial', 16)).pack(pady=5)
        tk.Label(self.master, text="High Scores:", font=('Arial', 16, 'underline')).pack(pady=10)

        for idx, entry in enumerate(self.highscores):
            cat = entry.get('category', 'Unknown')
            tk.Label(
                self.master,
                text=f"{idx+1}. [{cat}] Score: {entry['score']}, Correct: {entry['correct']}/10 on {entry['date']}",
                font=('Arial', 14)
            ).pack()

        btn_frame = tk.Frame(self.master); btn_frame.pack(pady=20)
        tk.Button(btn_frame, text='Play Again', font=('Arial', 14),
                  command=self.main_menu, width=10).grid(row=0, column=0, padx=10)
        tk.Button(btn_frame, text='Exit', font=('Arial', 14),
                  command=self.master.destroy, width=10).grid(row=0, column=1, padx=10)


if __name__ == '__main__':
    root = tk.Tk()
    TriviaGame(root)
    root.mainloop()
