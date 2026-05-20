import datetime as dt
import html
import json
import queue
import sqlite3
import threading
import time
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import tkinter as tk
from tkinter import messagebox, ttk


APP_TITLE = "Project & Work Task Tracker"
DB_FILE = Path(__file__).with_name("task_tracker.db")
WEB_HOST = "127.0.0.1"
WEB_PORT = 8765

STATUS_OPTIONS = [
    "New",
    "Investigating",
    "Working On",
    "Paused",
    "Almost Done",
    "Done Sign Off Needed",
    "Done",
    "Complete",
]

PRIORITY_OPTIONS = ["Low", "Normal", "High", "Critical"]


@dataclass
class Task:
    task_id: int
    title: str
    project: str
    status: str
    progress: int
    priority: str
    owner: str
    due_date: str
    paused_date: str
    remaining_work: str
    notes: str
    created_at: str
    updated_at: str


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self.lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    project TEXT DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'New',
                    progress INTEGER NOT NULL DEFAULT 0,
                    priority TEXT NOT NULL DEFAULT 'Normal',
                    owner TEXT DEFAULT '',
                    due_date TEXT DEFAULT '',
                    paused_date TEXT DEFAULT '',
                    remaining_work TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tasks_status
                ON tasks(status)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tasks_project
                ON tasks(project)
                """
            )

    @staticmethod
    def now_text() -> str:
        return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def add_task(self, data: dict[str, Any]) -> int:
        now = self.now_text()
        with self.lock, self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO tasks (
                    title, project, status, progress, priority, owner,
                    due_date, paused_date, remaining_work, notes,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data.get("title", "").strip(),
                    data.get("project", "").strip(),
                    data.get("status", "New"),
                    int(data.get("progress", 0)),
                    data.get("priority", "Normal"),
                    data.get("owner", "").strip(),
                    data.get("due_date", "").strip(),
                    data.get("paused_date", "").strip(),
                    data.get("remaining_work", "").strip(),
                    data.get("notes", "").strip(),
                    now,
                    now,
                ),
            )
            return int(cur.lastrowid)

    def update_task(self, task_id: int, data: dict[str, Any]) -> None:
        now = self.now_text()
        with self.lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET title = ?, project = ?, status = ?, progress = ?,
                    priority = ?, owner = ?, due_date = ?, paused_date = ?,
                    remaining_work = ?, notes = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (
                    data.get("title", "").strip(),
                    data.get("project", "").strip(),
                    data.get("status", "New"),
                    int(data.get("progress", 0)),
                    data.get("priority", "Normal"),
                    data.get("owner", "").strip(),
                    data.get("due_date", "").strip(),
                    data.get("paused_date", "").strip(),
                    data.get("remaining_work", "").strip(),
                    data.get("notes", "").strip(),
                    now,
                    task_id,
                ),
            )

    def quick_update(self, task_id: int, status: Optional[str], progress: Optional[int]) -> None:
        fields = []
        values: list[Any] = []
        if status is not None:
            fields.append("status = ?")
            values.append(status)
            if status == "Paused":
                fields.append("paused_date = ?")
                values.append(dt.date.today().isoformat())
            if status == "Complete":
                fields.append("progress = ?")
                values.append(100)
        if progress is not None:
            fields.append("progress = ?")
            values.append(max(0, min(100, int(progress))))
        fields.append("updated_at = ?")
        values.append(self.now_text())
        values.append(task_id)

        with self.lock, self._connect() as conn:
            conn.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE task_id = ?", values)

    def delete_task(self, task_id: int) -> None:
        with self.lock, self._connect() as conn:
            conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))

    def get_task(self, task_id: int) -> Optional[Task]:
        with self.lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        return self._row_to_task(row) if row else None

    def list_tasks(self, search: str = "", status: str = "All", project: str = "All") -> list[Task]:
        query = "SELECT * FROM tasks WHERE 1=1"
        params: list[Any] = []

        if search:
            query += " AND (title LIKE ? OR notes LIKE ? OR project LIKE ? OR owner LIKE ?)"
            value = f"%{search}%"
            params.extend([value, value, value, value])

        if status != "All":
            query += " AND status = ?"
            params.append(status)

        if project != "All":
            query += " AND project = ?"
            params.append(project)

        query += """
            ORDER BY
                CASE status
                    WHEN 'Working On' THEN 1
                    WHEN 'Investigating' THEN 2
                    WHEN 'Almost Done' THEN 3
                    WHEN 'Done Sign Off Needed' THEN 4
                    WHEN 'Paused' THEN 5
                    WHEN 'New' THEN 6
                    WHEN 'Done' THEN 7
                    WHEN 'Complete' THEN 8
                    ELSE 9
                END,
                CASE priority
                    WHEN 'Critical' THEN 1
                    WHEN 'High' THEN 2
                    WHEN 'Normal' THEN 3
                    WHEN 'Low' THEN 4
                    ELSE 5
                END,
                due_date = '',
                due_date,
                updated_at DESC
        """

        with self.lock, self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_task(row) for row in rows]

    def projects(self) -> list[str]:
        with self.lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT project FROM tasks WHERE project <> '' ORDER BY project"
            ).fetchall()
        return [str(row["project"]) for row in rows]

    def summary(self) -> dict[str, Any]:
        tasks = self.list_tasks()
        total = len(tasks)
        complete = sum(1 for task in tasks if task.status == "Complete")
        active = sum(1 for task in tasks if task.status in {"Investigating", "Working On", "Almost Done"})
        paused = sum(1 for task in tasks if task.status == "Paused")
        signoff = sum(1 for task in tasks if task.status == "Done Sign Off Needed")
        avg_progress = round(sum(task.progress for task in tasks) / total, 1) if total else 0
        return {
            "total": total,
            "active": active,
            "paused": paused,
            "signoff": signoff,
            "complete": complete,
            "avg_progress": avg_progress,
        }

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> Task:
        return Task(
            task_id=int(row["task_id"]),
            title=str(row["title"]),
            project=str(row["project"]),
            status=str(row["status"]),
            progress=int(row["progress"]),
            priority=str(row["priority"]),
            owner=str(row["owner"]),
            due_date=str(row["due_date"]),
            paused_date=str(row["paused_date"]),
            remaining_work=str(row["remaining_work"]),
            notes=str(row["notes"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )


class WebHandler(BaseHTTPRequestHandler):
    db: Database

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/tasks":
            self._send_json([task.__dict__ for task in self.db.list_tasks()])
            return
        if parsed.path == "/api/summary":
            self._send_json(self.db.summary())
            return
        self._send_html(self._page())

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        data = parse_qs(raw)

        if parsed.path == "/api/quick-update":
            task_id = int(data.get("task_id", ["0"])[0])
            status = data.get("status", [None])[0]
            progress_raw = data.get("progress", [None])[0]
            progress = int(progress_raw) if progress_raw not in (None, "") else None
            self.db.quick_update(task_id, status, progress)
            self._send_json({"ok": True})
            return

        self._send_json({"ok": False, "error": "Unknown endpoint"}, status=404)

    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    @staticmethod
    def _page() -> str:
        return """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Task Tracker Dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root {
    --bg: #0f172a;
    --panel: #111827;
    --card: #1f2937;
    --text: #e5e7eb;
    --muted: #9ca3af;
    --accent: #38bdf8;
    --border: #334155;
}
* { box-sizing: border-box; }
body {
    margin: 0;
    font-family: Segoe UI, Arial, sans-serif;
    background: linear-gradient(135deg, var(--bg), #111827);
    color: var(--text);
}
header {
    padding: 24px;
    border-bottom: 1px solid var(--border);
}
h1 { margin: 0; font-size: 28px; }
main { padding: 24px; }
.summary {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 14px;
    margin-bottom: 20px;
}
.metric, .task {
    background: rgba(31, 41, 55, .88);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 16px;
    box-shadow: 0 16px 40px rgba(0,0,0,.22);
}
.metric b { font-size: 28px; display: block; }
.metric span { color: var(--muted); }
.toolbar {
    display: flex;
    gap: 10px;
    margin-bottom: 16px;
}
input {
    width: 100%;
    padding: 12px;
    border-radius: 12px;
    border: 1px solid var(--border);
    background: #020617;
    color: var(--text);
}
.task-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(310px, 1fr));
    gap: 14px;
}
.task h2 {
    margin: 0 0 8px 0;
    font-size: 18px;
}
.meta {
    color: var(--muted);
    font-size: 13px;
    margin-bottom: 12px;
}
.progress {
    height: 10px;
    background: #020617;
    border-radius: 999px;
    overflow: hidden;
    margin: 10px 0;
}
.bar {
    height: 100%;
    background: linear-gradient(90deg, var(--accent), #22c55e);
}
.controls {
    display: grid;
    grid-template-columns: 1fr 90px;
    gap: 8px;
    margin-top: 12px;
}
select, button {
    padding: 10px;
    border-radius: 12px;
    border: 1px solid var(--border);
    background: #020617;
    color: var(--text);
}
button { cursor: pointer; }
button:hover { border-color: var(--accent); }
</style>
</head>
<body>
<header>
    <h1>Project & Work Task Tracker</h1>
    <p>Local web dashboard served from your Python app. Data stays on this computer.</p>
</header>
<main>
    <section class="summary" id="summary"></section>
    <div class="toolbar">
        <input id="search" placeholder="Search tasks, projects, owners, notes..." oninput="render()">
    </div>
    <section class="task-grid" id="tasks"></section>
</main>
<script>
let TASKS = [];

async function loadData() {
    const [tasks, summary] = await Promise.all([
        fetch('/api/tasks').then(r => r.json()),
        fetch('/api/summary').then(r => r.json())
    ]);
    TASKS = tasks;
    document.getElementById('summary').innerHTML = [
        ['Total', summary.total],
        ['Active', summary.active],
        ['Paused', summary.paused],
        ['Sign Off', summary.signoff],
        ['Complete', summary.complete],
        ['Avg Progress', summary.avg_progress + '%']
    ].map(([label, value]) => `<div class="metric"><b>${value}</b><span>${label}</span></div>`).join('');
    render();
}

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, m => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[m]));
}

function render() {
    const q = document.getElementById('search').value.toLowerCase();
    const tasks = TASKS.filter(t => JSON.stringify(t).toLowerCase().includes(q));
    document.getElementById('tasks').innerHTML = tasks.map(t => `
        <article class="task">
            <h2>${escapeHtml(t.title)}</h2>
            <div class="meta">
                ${escapeHtml(t.project || 'No Project')} · ${escapeHtml(t.priority)} · Updated ${escapeHtml(t.updated_at)}
            </div>
            <div>${escapeHtml(t.status)} · ${t.progress}%</div>
            <div class="progress"><div class="bar" style="width:${t.progress}%"></div></div>
            ${t.remaining_work ? `<p><b>Remaining:</b> ${escapeHtml(t.remaining_work)}</p>` : ''}
            ${t.notes ? `<p>${escapeHtml(t.notes)}</p>` : ''}
            <div class="controls">
                <select id="s-${t.task_id}">
                    ${["New","Investigating","Working On","Paused","Almost Done","Done Sign Off Needed","Done","Complete"].map(s =>
                        `<option ${s === t.status ? 'selected' : ''}>${s}</option>`
                    ).join('')}
                </select>
                <button onclick="quickUpdate(${t.task_id})">Save</button>
            </div>
        </article>
    `).join('');
}

async function quickUpdate(taskId) {
    const status = document.getElementById(`s-${taskId}`).value;
    const body = new URLSearchParams({task_id: taskId, status});
    await fetch('/api/quick-update', {method: 'POST', body});
    await loadData();
}

loadData();
setInterval(loadData, 10000);
</script>
</body>
</html>"""


def start_web_server(db: Database, notify_queue: queue.Queue[str]) -> ThreadingHTTPServer:
    WebHandler.db = db
    server = ThreadingHTTPServer((WEB_HOST, WEB_PORT), WebHandler)

    def serve() -> None:
        notify_queue.put(f"Web dashboard running at http://{WEB_HOST}:{WEB_PORT}")
        server.serve_forever(poll_interval=0.5)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return server


class TaskEditor(tk.Toplevel):
    def __init__(self, parent: "TaskTrackerApp", task: Optional[Task] = None) -> None:
        super().__init__(parent)
        self.parent = parent
        self.task = task
        self.title("Edit Task" if task else "New Task")
        self.geometry("720x650")
        self.minsize(620, 540)
        self.configure(background=parent.colors["bg"])

        self.vars: dict[str, tk.StringVar] = {
            "title": tk.StringVar(value=task.title if task else ""),
            "project": tk.StringVar(value=task.project if task else ""),
            "status": tk.StringVar(value=task.status if task else "New"),
            "progress": tk.StringVar(value=str(task.progress if task else 0)),
            "priority": tk.StringVar(value=task.priority if task else "Normal"),
            "owner": tk.StringVar(value=task.owner if task else ""),
            "due_date": tk.StringVar(value=task.due_date if task else ""),
            "paused_date": tk.StringVar(value=task.paused_date if task else ""),
            "remaining_work": tk.StringVar(value=task.remaining_work if task else ""),
        }

        self._build()
        self.grab_set()
        self.entry_title.focus_set()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        frame = ttk.Frame(self, padding=18, style="Panel.TFrame")
        frame.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(9, weight=1)

        self.entry_title = self._entry(frame, "Task Title", "title", 0)
        self._entry(frame, "Project", "project", 1)

        self._combo(frame, "Status", "status", STATUS_OPTIONS, 2)
        self._spin(frame, "Progress 0-100", "progress", 3)
        self._combo(frame, "Priority", "priority", PRIORITY_OPTIONS, 4)
        self._entry(frame, "Owner", "owner", 5)
        self._entry(frame, "Due Date", "due_date", 6, hint="YYYY-MM-DD")
        self._entry(frame, "Paused Date", "paused_date", 7, hint="YYYY-MM-DD")
        self._entry(frame, "Remaining Work", "remaining_work", 8)

        ttk.Label(frame, text="Notes").grid(row=9, column=0, sticky="nw", pady=(8, 4))
        self.notes = tk.Text(
            frame,
            height=8,
            wrap="word",
            bg=self.parent.colors["entry"],
            fg=self.parent.colors["fg"],
            insertbackground=self.parent.colors["fg"],
            relief="flat",
            padx=10,
            pady=10,
        )
        self.notes.grid(row=9, column=1, sticky="nsew", pady=(8, 4))
        if self.task:
            self.notes.insert("1.0", self.task.notes)

        buttons = ttk.Frame(frame, style="Panel.TFrame")
        buttons.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        buttons.columnconfigure(0, weight=1)

        ttk.Button(buttons, text="Cancel", command=self.destroy).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(buttons, text="Save Task", style="Accent.TButton", command=self._save).grid(row=0, column=2)

    def _entry(self, parent: ttk.Frame, label: str, key: str, row: int, hint: str = "") -> ttk.Entry:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=6)
        entry = ttk.Entry(parent, textvariable=self.vars[key])
        entry.grid(row=row, column=1, sticky="ew", pady=6)
        if hint and not self.vars[key].get():
            entry.insert(0, "")
        return entry

    def _combo(self, parent: ttk.Frame, label: str, key: str, values: list[str], row: int) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=6)
        combo = ttk.Combobox(parent, textvariable=self.vars[key], values=values, state="readonly")
        combo.grid(row=row, column=1, sticky="ew", pady=6)

    def _spin(self, parent: ttk.Frame, label: str, key: str, row: int) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=6)
        spin = ttk.Spinbox(parent, from_=0, to=100, increment=5, textvariable=self.vars[key])
        spin.grid(row=row, column=1, sticky="ew", pady=6)

    def _save(self) -> None:
        title = self.vars["title"].get().strip()
        if not title:
            messagebox.showwarning("Task Required", "Please enter a task title.")
            return

        try:
            progress = int(self.vars["progress"].get())
        except ValueError:
            messagebox.showwarning("Invalid Progress", "Progress must be a number from 0 to 100.")
            return

        progress = max(0, min(100, progress))
        status = self.vars["status"].get()
        if status == "Complete":
            progress = 100

        if status == "Paused" and not self.vars["paused_date"].get().strip():
            self.vars["paused_date"].set(dt.date.today().isoformat())

        data = {key: var.get() for key, var in self.vars.items()}
        data["progress"] = progress
        data["notes"] = self.notes.get("1.0", "end").strip()

        if self.task:
            self.parent.db.update_task(self.task.task_id, data)
        else:
            self.parent.db.add_task(data)

        self.parent.refresh()
        self.destroy()


class TaskTrackerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1180x760")
        self.minsize(960, 620)

        self.colors = {
            "bg": "#0f172a",
            "panel": "#111827",
            "card": "#1f2937",
            "fg": "#e5e7eb",
            "muted": "#9ca3af",
            "accent": "#38bdf8",
            "entry": "#020617",
        }

        self.configure(bg=self.colors["bg"])
        self.db = Database(DB_FILE)
        self.queue: queue.Queue[str] = queue.Queue()
        self.web_server = start_web_server(self.db, self.queue)
        self.selected_task_id: Optional[int] = None

        self.search_var = tk.StringVar()
        self.status_filter = tk.StringVar(value="All")
        self.project_filter = tk.StringVar(value="All")
        self.quick_status = tk.StringVar(value="Working On")
        self.quick_progress = tk.IntVar(value=50)

        self._style()
        self._build()
        self.refresh()
        self.after(500, self._poll_queue)

    def _style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", font=("Segoe UI", 10), background=self.colors["bg"], foreground=self.colors["fg"])
        style.configure("Panel.TFrame", background=self.colors["panel"])
        style.configure("Card.TFrame", background=self.colors["card"])
        style.configure("TLabel", background=self.colors["panel"], foreground=self.colors["fg"])
        style.configure("Muted.TLabel", background=self.colors["panel"], foreground=self.colors["muted"])
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"), background=self.colors["bg"])
        style.configure("Metric.TLabel", font=("Segoe UI", 16, "bold"), background=self.colors["card"])
        style.configure("TButton", padding=8)
        style.configure("Accent.TButton", padding=8)
        style.map("Accent.TButton", background=[("active", self.colors["accent"])])
        style.configure("Treeview", rowheight=30, fieldbackground=self.colors["entry"], background=self.colors["entry"], foreground=self.colors["fg"])
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("Horizontal.TProgressbar", troughcolor=self.colors["entry"], background=self.colors["accent"])

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, padding=(18, 16), style="Panel.TFrame")
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text=APP_TITLE, style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Fast status updates, progress tracking, local database, desktop UI, and local web dashboard.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        ttk.Button(header, text="New Task", style="Accent.TButton", command=self.new_task).grid(row=0, column=1, rowspan=2, padx=6)
        ttk.Button(header, text="Open Web Dashboard", command=self.open_web).grid(row=0, column=2, rowspan=2, padx=6)
        ttk.Button(header, text="Refresh", command=self.refresh).grid(row=0, column=3, rowspan=2, padx=6)

        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=14, pady=14)

        self.dashboard_tab = ttk.Frame(self.notebook, padding=14, style="Panel.TFrame")
        self.tasks_tab = ttk.Frame(self.notebook, padding=14, style="Panel.TFrame")
        self.quick_tab = ttk.Frame(self.notebook, padding=14, style="Panel.TFrame")

        self.notebook.add(self.dashboard_tab, text="Dashboard")
        self.notebook.add(self.tasks_tab, text="Tasks")
        self.notebook.add(self.quick_tab, text="Quick Update")

        self._build_dashboard()
        self._build_tasks()
        self._build_quick_update()

    def _build_dashboard(self) -> None:
        self.dashboard_tab.columnconfigure((0, 1, 2, 3, 4), weight=1)
        self.dashboard_tab.rowconfigure(2, weight=1)

        self.metric_vars = {
            "Total": tk.StringVar(value="0"),
            "Active": tk.StringVar(value="0"),
            "Paused": tk.StringVar(value="0"),
            "Sign Off": tk.StringVar(value="0"),
            "Complete": tk.StringVar(value="0"),
        }

        for col, (label, var) in enumerate(self.metric_vars.items()):
            card = ttk.Frame(self.dashboard_tab, padding=16, style="Card.TFrame")
            card.grid(row=0, column=col, sticky="nsew", padx=6, pady=6)
            ttk.Label(card, textvariable=var, style="Metric.TLabel").grid(row=0, column=0, sticky="w")
            ttk.Label(card, text=label, background=self.colors["card"], foreground=self.colors["muted"]).grid(row=1, column=0, sticky="w")

        ttk.Label(self.dashboard_tab, text="Overall Progress").grid(row=1, column=0, sticky="w", pady=(18, 4))
        self.overall_progress = ttk.Progressbar(self.dashboard_tab, maximum=100, mode="determinate")
        self.overall_progress.grid(row=1, column=1, columnspan=4, sticky="ew", padx=6, pady=(18, 4))

        columns = ("id", "title", "project", "status", "progress", "priority", "due")
        self.dashboard_tree = ttk.Treeview(self.dashboard_tab, columns=columns, show="headings")
        for col in columns:
            self.dashboard_tree.heading(col, text=col.title())
        self.dashboard_tree.column("id", width=60, anchor="center")
        self.dashboard_tree.column("title", width=320)
        self.dashboard_tree.column("project", width=160)
        self.dashboard_tree.column("status", width=160)
        self.dashboard_tree.column("progress", width=90, anchor="center")
        self.dashboard_tree.column("priority", width=90, anchor="center")
        self.dashboard_tree.column("due", width=110, anchor="center")
        self.dashboard_tree.grid(row=2, column=0, columnspan=5, sticky="nsew", pady=(14, 0))
        self.dashboard_tree.bind("<<TreeviewSelect>>", self._tree_select)
        self.dashboard_tree.bind("<Double-1>", lambda event: self.edit_task())

    def _build_tasks(self) -> None:
        self.tasks_tab.columnconfigure(0, weight=1)
        self.tasks_tab.rowconfigure(1, weight=1)

        filters = ttk.Frame(self.tasks_tab, style="Panel.TFrame")
        filters.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        filters.columnconfigure(1, weight=1)

        ttk.Label(filters, text="Search").grid(row=0, column=0, sticky="w", padx=(0, 8))
        search_entry = ttk.Entry(filters, textvariable=self.search_var)
        search_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        search_entry.bind("<KeyRelease>", lambda event: self.refresh())

        ttk.Label(filters, text="Status").grid(row=0, column=2, sticky="w", padx=(0, 8))
        status_combo = ttk.Combobox(
            filters,
            textvariable=self.status_filter,
            values=["All"] + STATUS_OPTIONS,
            state="readonly",
            width=22,
        )
        status_combo.grid(row=0, column=3, sticky="ew", padx=(0, 10))
        status_combo.bind("<<ComboboxSelected>>", lambda event: self.refresh())

        ttk.Label(filters, text="Project").grid(row=0, column=4, sticky="w", padx=(0, 8))
        self.project_combo = ttk.Combobox(filters, textvariable=self.project_filter, values=["All"], state="readonly", width=22)
        self.project_combo.grid(row=0, column=5, sticky="ew", padx=(0, 10))
        self.project_combo.bind("<<ComboboxSelected>>", lambda event: self.refresh())

        ttk.Button(filters, text="Clear", command=self.clear_filters).grid(row=0, column=6)

        columns = ("id", "title", "project", "status", "progress", "priority", "owner", "due", "paused", "updated")
        self.task_tree = ttk.Treeview(self.tasks_tab, columns=columns, show="headings")
        for col in columns:
            self.task_tree.heading(col, text=col.title())
        widths = {
            "id": 55,
            "title": 300,
            "project": 140,
            "status": 165,
            "progress": 85,
            "priority": 85,
            "owner": 100,
            "due": 100,
            "paused": 100,
            "updated": 155,
        }
        for col, width in widths.items():
            self.task_tree.column(col, width=width, anchor="center" if col != "title" else "w")
        self.task_tree.grid(row=1, column=0, sticky="nsew")
        self.task_tree.bind("<<TreeviewSelect>>", self._tree_select)
        self.task_tree.bind("<Double-1>", lambda event: self.edit_task())

        actions = ttk.Frame(self.tasks_tab, style="Panel.TFrame")
        actions.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        actions.columnconfigure(0, weight=1)
        ttk.Button(actions, text="New Task", command=self.new_task).grid(row=0, column=1, padx=5)
        ttk.Button(actions, text="Edit Selected", command=self.edit_task).grid(row=0, column=2, padx=5)
        ttk.Button(actions, text="Delete Selected", command=self.delete_task).grid(row=0, column=3, padx=5)

    def _build_quick_update(self) -> None:
        self.quick_tab.columnconfigure(0, weight=1)
        self.quick_tab.rowconfigure(1, weight=1)

        top = ttk.Frame(self.quick_tab, padding=14, style="Card.TFrame")
        top.grid(row=0, column=0, sticky="ew")
        for col in range(6):
            top.columnconfigure(col, weight=1)

        ttk.Label(top, text="Selected Task", background=self.colors["card"]).grid(row=0, column=0, sticky="w")
        self.selected_label = ttk.Label(top, text="None selected", background=self.colors["card"], foreground=self.colors["muted"])
        self.selected_label.grid(row=1, column=0, columnspan=6, sticky="ew", pady=(4, 12))

        ttk.Label(top, text="Quick Status", background=self.colors["card"]).grid(row=2, column=0, sticky="w")
        ttk.Combobox(top, textvariable=self.quick_status, values=STATUS_OPTIONS, state="readonly").grid(row=3, column=0, columnspan=2, sticky="ew", padx=(0, 10))

        ttk.Label(top, text="Progress", background=self.colors["card"]).grid(row=2, column=2, sticky="w")
        scale = ttk.Scale(top, from_=0, to=100, variable=self.quick_progress, orient="horizontal")
        scale.grid(row=3, column=2, columnspan=2, sticky="ew", padx=(0, 10))

        self.quick_progress_label = ttk.Label(top, text="50%", background=self.colors["card"])
        self.quick_progress_label.grid(row=3, column=4, sticky="w")
        scale.configure(command=lambda value: self.quick_progress_label.configure(text=f"{int(float(value))}%"))

        ttk.Button(top, text="Apply Update", style="Accent.TButton", command=self.apply_quick_update).grid(row=3, column=5, sticky="ew")

        ttk.Label(
            self.quick_tab,
            text="Tip: select a task from the table below, choose a status and percentage, then apply. Paused automatically records today's paused date. Complete sets progress to 100%.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="nw", pady=14)

        columns = ("id", "title", "project", "status", "progress", "remaining")
        self.quick_tree = ttk.Treeview(self.quick_tab, columns=columns, show="headings")
        for col in columns:
            self.quick_tree.heading(col, text=col.title())
        self.quick_tree.column("id", width=60, anchor="center")
        self.quick_tree.column("title", width=320)
        self.quick_tree.column("project", width=160)
        self.quick_tree.column("status", width=165)
        self.quick_tree.column("progress", width=90, anchor="center")
        self.quick_tree.column("remaining", width=360)
        self.quick_tree.grid(row=2, column=0, sticky="nsew")
        self.quick_tree.bind("<<TreeviewSelect>>", self._tree_select)

    def refresh(self) -> None:
        projects = ["All"] + self.db.projects()
        self.project_combo.configure(values=projects)
        if self.project_filter.get() not in projects:
            self.project_filter.set("All")

        tasks = self.db.list_tasks(
            search=self.search_var.get().strip(),
            status=self.status_filter.get(),
            project=self.project_filter.get(),
        )
        all_tasks = self.db.list_tasks()

        for tree in (self.dashboard_tree, self.task_tree, self.quick_tree):
            tree.delete(*tree.get_children())

        for task in all_tasks[:30]:
            self.dashboard_tree.insert(
                "",
                "end",
                iid=f"d-{task.task_id}",
                values=(task.task_id, task.title, task.project, task.status, f"{task.progress}%", task.priority, task.due_date),
            )

        for task in tasks:
            self.task_tree.insert(
                "",
                "end",
                iid=f"t-{task.task_id}",
                values=(
                    task.task_id,
                    task.title,
                    task.project,
                    task.status,
                    f"{task.progress}%",
                    task.priority,
                    task.owner,
                    task.due_date,
                    task.paused_date,
                    task.updated_at,
                ),
            )
            self.quick_tree.insert(
                "",
                "end",
                iid=f"q-{task.task_id}",
                values=(task.task_id, task.title, task.project, task.status, f"{task.progress}%", task.remaining_work),
            )

        summary = self.db.summary()
        self.metric_vars["Total"].set(str(summary["total"]))
        self.metric_vars["Active"].set(str(summary["active"]))
        self.metric_vars["Paused"].set(str(summary["paused"]))
        self.metric_vars["Sign Off"].set(str(summary["signoff"]))
        self.metric_vars["Complete"].set(str(summary["complete"]))
        self.overall_progress["value"] = summary["avg_progress"]

    def _tree_select(self, event: tk.Event) -> None:
        tree = event.widget
        selected = tree.selection()
        if not selected:
            return
        item_id = selected[0]
        try:
            self.selected_task_id = int(str(item_id).split("-", 1)[1])
        except (IndexError, ValueError):
            values = tree.item(item_id, "values")
            self.selected_task_id = int(values[0]) if values else None

        task = self.db.get_task(self.selected_task_id) if self.selected_task_id else None
        if task:
            self.selected_label.configure(text=f"#{task.task_id} · {task.title} · {task.status} · {task.progress}%")
            self.quick_status.set(task.status)
            self.quick_progress.set(task.progress)
            self.quick_progress_label.configure(text=f"{task.progress}%")

    def new_task(self) -> None:
        TaskEditor(self)

    def edit_task(self) -> None:
        if not self.selected_task_id:
            messagebox.showinfo("No Task Selected", "Please select a task first.")
            return
        task = self.db.get_task(self.selected_task_id)
        if not task:
            messagebox.showerror("Task Not Found", "The selected task could not be found.")
            return
        TaskEditor(self, task)

    def delete_task(self) -> None:
        if not self.selected_task_id:
            messagebox.showinfo("No Task Selected", "Please select a task first.")
            return
        task = self.db.get_task(self.selected_task_id)
        if not task:
            return
        confirm = messagebox.askyesno("Delete Task", f"Delete this task?\n\n{task.title}")
        if confirm:
            self.db.delete_task(task.task_id)
            self.selected_task_id = None
            self.selected_label.configure(text="None selected")
            self.refresh()

    def apply_quick_update(self) -> None:
        if not self.selected_task_id:
            messagebox.showinfo("No Task Selected", "Please select a task first.")
            return
        self.db.quick_update(
            self.selected_task_id,
            self.quick_status.get(),
            int(self.quick_progress.get()),
        )
        self.refresh()

    def clear_filters(self) -> None:
        self.search_var.set("")
        self.status_filter.set("All")
        self.project_filter.set("All")
        self.refresh()

    def open_web(self) -> None:
        webbrowser.open(f"http://{WEB_HOST}:{WEB_PORT}")

    def _poll_queue(self) -> None:
        try:
            while True:
                _message = self.queue.get_nowait()
        except queue.Empty:
            pass
        self.after(500, self._poll_queue)

    def destroy(self) -> None:
        try:
            self.web_server.shutdown()
        except Exception:
            pass
        super().destroy()


def main() -> None:
    app = TaskTrackerApp()
    app.mainloop()


if __name__ == "__main__":
    main()