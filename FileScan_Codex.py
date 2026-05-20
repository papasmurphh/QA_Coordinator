import csv
import json
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

PREFS_FILE = Path.home() / ".hd_scan_tool_prefs.json"


def human_readable_size(num_bytes):
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)

    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            return f"{size:,.2f} {unit}"
        size /= 1024.0


def scan_folder(root_path, include_files=True, progress_queue=None):
    folder_sizes = {}
    folder_items = {}
    file_sizes = {}

    root_path = os.path.abspath(root_path)

    for dirpath, dirnames, filenames in os.walk(root_path, topdown=False):
        total_size = 0
        total_items = 0

        for filename in filenames:
            file_path = os.path.join(dirpath, filename)

            try:
                file_size = os.path.getsize(file_path)
            except OSError:
                continue

            total_size += file_size
            total_items += 1

            if include_files:
                file_sizes[file_path] = file_size

        for dirname in dirnames:
            child_path = os.path.join(dirpath, dirname)
            total_size += folder_sizes.get(child_path, 0)
            total_items += folder_items.get(child_path, 0)

        folder_sizes[dirpath] = total_size
        folder_items[dirpath] = total_items

        if progress_queue is not None:
            try:
                progress_queue.put_nowait(f"Scanned: {dirpath}")
            except queue.Full:
                pass

    return folder_sizes, folder_items, file_sizes


class ScanTab(ttk.Frame):
    def __init__(self, parent, app, initial_path=""):
        super().__init__(parent)
        self.app = app

        self.path_var = tk.StringVar(value=initial_path)
        self.include_files_var = tk.BooleanVar(value=True)

        self.scan_thread = None
        self.scan_queue = queue.Queue(maxsize=100)

        self.id_to_path = {}
        self.results_rows = []
        self.root_path = ""
        self.root_prefix = ""
        self.custom_tab_name = ""

        self.sort_reverse = {}

        self._create_widgets()
        self._create_context_menu()
        self._poll_queue()

    def _create_widgets(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        top_frame = ttk.Frame(self, padding=(10, 10, 10, 5))
        top_frame.grid(row=0, column=0, sticky="ew")
        top_frame.columnconfigure(1, weight=1)

        ttk.Label(top_frame, text="Folder:").grid(row=0, column=0, sticky="w")

        self.path_entry = ttk.Entry(top_frame, textvariable=self.path_var)
        self.path_entry.grid(row=0, column=1, sticky="ew", padx=5)

        ttk.Button(top_frame, text="Browse...", command=self.browse).grid(
            row=0, column=2, padx=(0, 5)
        )

        ttk.Button(top_frame, text="Scan", command=self.start_scan).grid(
            row=0, column=3
        )

        ttk.Checkbutton(
            top_frame,
            text="Include files",
            variable=self.include_files_var,
        ).grid(row=1, column=1, sticky="w", pady=(5, 0))

        button_frame = ttk.Frame(self, padding=(10, 0, 10, 5))
        button_frame.grid(row=1, column=0, sticky="ew")

        ttk.Button(
            button_frame,
            text="Copy Results for Excel",
            command=self.copy_results_for_excel,
        ).grid(row=0, column=0, padx=(0, 5))

        ttk.Button(
            button_frame,
            text="Export CSV",
            command=self.export_csv,
        ).grid(row=0, column=1, padx=(0, 5))

        ttk.Button(
            button_frame,
            text="Export JSON",
            command=self.export_json,
        ).grid(row=0, column=2, padx=(0, 5))

        ttk.Button(
            button_frame,
            text="Rename Tab",
            command=self.rename_this_tab,
        ).grid(row=0, column=3, padx=(15, 5))

        ttk.Button(
            button_frame,
            text="Close Tab",
            command=self.app.close_current_tab,
        ).grid(row=0, column=4, padx=(0, 5))

        tree_frame = ttk.Frame(self, padding=(10, 0, 10, 5))
        tree_frame.grid(row=2, column=0, sticky="nsew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        columns = ("type", "size", "bytes", "files", "percent", "level", "parent")

        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="tree headings",
            selectmode="browse",
        )
        self.tree.grid(row=0, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscroll=vsb.set, xscroll=hsb.set)

        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self.tree.heading(
            "#0",
            text="Name",
            anchor="w",
            command=lambda: self.sort_by_column("#0"),
        )
        self.tree.heading(
            "type",
            text="Type",
            anchor="w",
            command=lambda: self.sort_by_column("type"),
        )
        self.tree.heading(
            "size",
            text="Size",
            anchor="e",
            command=lambda: self.sort_by_column("size"),
        )
        self.tree.heading(
            "bytes",
            text="Size Bytes",
            anchor="e",
            command=lambda: self.sort_by_column("bytes"),
        )
        self.tree.heading(
            "files",
            text="Files",
            anchor="e",
            command=lambda: self.sort_by_column("files"),
        )
        self.tree.heading(
            "percent",
            text="% of Root",
            anchor="e",
            command=lambda: self.sort_by_column("percent"),
        )
        self.tree.heading(
            "level",
            text="Level",
            anchor="e",
            command=lambda: self.sort_by_column("level"),
        )
        self.tree.heading(
            "parent",
            text="Parent",
            anchor="w",
            command=lambda: self.sort_by_column("parent"),
        )

        self.tree.column("#0", width=300, anchor="w")
        self.tree.column("type", width=80, anchor="w")
        self.tree.column("size", width=110, anchor="e")
        self.tree.column("bytes", width=130, anchor="e")
        self.tree.column("files", width=80, anchor="e")
        self.tree.column("percent", width=90, anchor="e")
        self.tree.column("level", width=70, anchor="e")
        self.tree.column("parent", width=300, anchor="w")

        self.tree.tag_configure("size_high", background="#f8d7da")
        self.tree.tag_configure("size_medium", background="#fff3cd")
        self.tree.tag_configure("size_low", background="#d4edda")
        self.tree.tag_configure("file_item", foreground="#555555")

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Button-3>", self._on_right_click)
        self.tree.bind("<Control-Button-1>", self._on_right_click)

        status_frame = ttk.Frame(self, padding=(10, 0, 10, 10))
        status_frame.grid(row=3, column=0, sticky="ew")
        status_frame.columnconfigure(0, weight=1)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(status_frame, textvariable=self.status_var, anchor="w").grid(
            row=0, column=0, sticky="ew"
        )

    def _create_context_menu(self):
        self.context_menu = tk.Menu(self, tearoff=False)
        self.context_menu.add_command(
            label="Copy full path",
            command=self.copy_selected_path,
        )

    def _poll_queue(self):
        try:
            while True:
                self.status_var.set(self.scan_queue.get_nowait())
        except queue.Empty:
            pass

        self.after(150, self._poll_queue)

    def browse(self):
        initial_dir = self.path_var.get() or str(Path.home())

        if not os.path.isdir(initial_dir):
            initial_dir = str(Path.home())

        selected = filedialog.askdirectory(
            parent=self,
            title="Select folder to scan",
            initialdir=initial_dir,
        )

        if selected:
            self.path_var.set(selected)

    def start_scan(self):
        if self.scan_thread is not None and self.scan_thread.is_alive():
            messagebox.showinfo(
                "Scan in progress",
                "A scan is already running in this tab. Please wait.",
                parent=self,
            )
            return

        folder = self.path_var.get().strip()

        if not folder:
            messagebox.showwarning(
                "No folder",
                "Please enter or choose a folder to scan.",
                parent=self,
            )
            return

        if not os.path.isdir(folder):
            messagebox.showerror(
                "Invalid folder",
                f"The path does not exist or is not a directory:\n{folder}",
                parent=self,
            )
            return

        self.tree.delete(*self.tree.get_children())
        self.id_to_path.clear()
        self.results_rows.clear()
        self.status_var.set("Starting scan...")

        self.root_path = os.path.abspath(folder)
        self.root_prefix = self._make_root_prefix(self.root_path)
        self.app.save_last_path(folder)
        self.update_tab_title()

        self.scan_thread = threading.Thread(
            target=self._scan_worker,
            args=(folder, self.include_files_var.get()),
            daemon=True,
        )
        self.scan_thread.start()

    def _scan_worker(self, folder, include_files):
        try:
            folder_sizes, folder_items, file_sizes = scan_folder(
                folder,
                include_files=include_files,
                progress_queue=self.scan_queue,
            )
        except Exception as exc:
            self.after(
                0,
                lambda: messagebox.showerror(
                    "Scan error",
                    f"An error occurred while scanning:\n{exc}",
                    parent=self,
                ),
            )
            return

        self.after(
            0,
            lambda: self._populate_tree(folder, folder_sizes, folder_items, file_sizes),
        )

    def _populate_tree(self, root_path, folder_sizes, folder_items, file_sizes):
        self.tree.delete(*self.tree.get_children())
        self.id_to_path.clear()
        self.results_rows.clear()

        root_path = os.path.abspath(root_path)
        root_total = folder_sizes.get(root_path, 0) or 1

        path_to_id = {}

        for path in sorted(folder_sizes.keys(), key=lambda p: p.count(os.sep)):
            size = folder_sizes[path]
            files = folder_items.get(path, 0)
            percent = size / root_total * 100.0
            level = self._get_level(root_path, path)
            parent = os.path.dirname(path) if path != root_path else ""

            if path == root_path:
                parent_id = ""
                name = path
            else:
                parent_id = path_to_id.get(parent, "")
                name = os.path.basename(path) or path

            item_id = self.tree.insert(
                parent_id,
                "end",
                text=name,
                values=(
                    "Folder",
                    human_readable_size(size),
                    size,
                    files,
                    f"{percent:.2f}",
                    level,
                    parent,
                ),
                tags=(self._tag_for_percent(percent),),
                open=(path == root_path),
            )

            path_to_id[path] = item_id
            self.id_to_path[item_id] = path

            self.results_rows.append(
                {
                    "Name": name,
                    "Full Path": path,
                    "Type": "Folder",
                    "Size": human_readable_size(size),
                    "Size Bytes": size,
                    "Files": files,
                    "% of Root": round(percent, 2),
                    "Level": level,
                    "Parent": parent,
                }
            )

        if file_sizes:
            for file_path, size in sorted(file_sizes.items()):
                parent = os.path.dirname(file_path)
                parent_id = path_to_id.get(parent)

                if parent_id is None:
                    continue

                name = os.path.basename(file_path)
                percent = size / root_total * 100.0
                level = self._get_level(root_path, file_path)

                item_id = self.tree.insert(
                    parent_id,
                    "end",
                    text=name,
                    values=(
                        "File",
                        human_readable_size(size),
                        size,
                        1,
                        f"{percent:.2f}",
                        level,
                        parent,
                    ),
                    tags=("file_item", self._tag_for_percent(percent)),
                    open=False,
                )

                self.id_to_path[item_id] = file_path

                self.results_rows.append(
                    {
                        "Name": name,
                        "Full Path": file_path,
                        "Type": "File",
                        "Size": human_readable_size(size),
                        "Size Bytes": size,
                        "Files": 1,
                        "% of Root": round(percent, 2),
                        "Level": level,
                        "Parent": parent,
                    }
                )

        self.status_var.set(
            f"Scan complete. Root size: {human_readable_size(root_total)}. "
            f"Rows available for export: {len(self.results_rows):,}"
        )

    def sort_by_column(self, column):
        reverse = self.sort_reverse.get(column, False)

        def value_for_item(item_id):
            if column == "#0":
                return self.tree.item(item_id, "text").lower()

            values = self.tree.item(item_id, "values")
            column_map = {
                "type": 0,
                "size": 1,
                "bytes": 2,
                "files": 3,
                "percent": 4,
                "level": 5,
                "parent": 6,
            }

            index = column_map.get(column)

            if index is None or index >= len(values):
                return ""

            value = values[index]

            if column in {"bytes", "files", "percent", "level"}:
                try:
                    return float(str(value).replace(",", "").replace("%", ""))
                except ValueError:
                    return 0.0

            if column == "size":
                try:
                    number, unit = str(value).split()
                    factor = {
                        "B": 1,
                        "KB": 1024,
                        "MB": 1024**2,
                        "GB": 1024**3,
                        "TB": 1024**4,
                    }.get(unit.upper(), 1)
                    return float(number.replace(",", "")) * factor
                except Exception:
                    return 0.0

            return str(value).lower()

        def sort_children(parent_id):
            children = list(self.tree.get_children(parent_id))
            children.sort(key=value_for_item, reverse=reverse)

            for index, child in enumerate(children):
                self.tree.move(child, parent_id, index)
                sort_children(child)

        sort_children("")
        self.sort_reverse[column] = not reverse

        direction = "descending" if reverse else "ascending"
        heading_name = "Name" if column == "#0" else column
        self.status_var.set(f"Sorted by {heading_name}, {direction}.")

    def rename_this_tab(self):
        current_name = self.custom_tab_name

        new_name = simpledialog.askstring(
            "Rename Tab",
            "Enter a custom tab name:",
            initialvalue=current_name,
            parent=self,
        )

        if new_name is None:
            return

        self.custom_tab_name = new_name.strip()
        self.update_tab_title()

    def update_tab_title(self):
        prefix = self.root_prefix or "Scan"

        if self.custom_tab_name:
            title = f"{prefix} - {self.custom_tab_name}"
        else:
            title = prefix

        self.app.rename_tab(self, title)

    @staticmethod
    def _make_root_prefix(path):
        drive, tail = os.path.splitdrive(path)

        if drive:
            return drive + "\\"

        cleaned = path.strip(os.sep)
        if not cleaned:
            return os.sep

        return os.path.basename(path) or path

    @staticmethod
    def _get_level(root_path, path):
        rel = os.path.relpath(path, root_path)
        if rel == ".":
            return 0
        return rel.count(os.sep) + 1

    @staticmethod
    def _tag_for_percent(percent):
        if percent >= 20.0:
            return "size_high"
        if percent >= 5.0:
            return "size_medium"
        return "size_low"

    def _on_tree_select(self, event=None):
        item_id = self.tree.focus()

        if not item_id:
            return

        name = self.tree.item(item_id, "text")
        path = self.id_to_path.get(item_id, "")

        self.status_var.set(f"Selected: {name} | {path}")

    def _on_right_click(self, event):
        item_id = self.tree.identify_row(event.y)

        if item_id:
            self.tree.selection_set(item_id)
            self.tree.focus(item_id)

            try:
                self.context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.context_menu.grab_release()

    def copy_selected_path(self):
        item_id = self.tree.focus()

        if not item_id:
            messagebox.showinfo(
                "No selection",
                "Please select a folder or file first.",
                parent=self,
            )
            return

        path = self.id_to_path.get(item_id)

        if not path:
            messagebox.showwarning(
                "Path not available",
                "Could not determine the path for this item.",
                parent=self,
            )
            return

        self.clipboard_clear()
        self.clipboard_append(path)
        self.status_var.set(f"Copied path to clipboard: {path}")

    def copy_results_for_excel(self):
        if not self.results_rows:
            messagebox.showinfo(
                "No results",
                "Please run a scan before copying results.",
                parent=self,
            )
            return

        headers = [
            "Name",
            "Full Path",
            "Type",
            "Size",
            "Size Bytes",
            "Files",
            "% of Root",
            "Level",
            "Parent",
        ]

        lines = ["\t".join(headers)]

        for row in self.results_rows:
            values = [str(row.get(header, "")) for header in headers]
            lines.append("\t".join(values))

        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))

        self.status_var.set(
            f"Copied {len(self.results_rows):,} rows to clipboard for Excel."
        )

    def export_csv(self):
        if not self.results_rows:
            messagebox.showinfo(
                "No results",
                "Please run a scan before exporting.",
                parent=self,
            )
            return

        file_path = filedialog.asksaveasfilename(
            parent=self,
            title="Export scan results to CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )

        if not file_path:
            return

        headers = [
            "Name",
            "Full Path",
            "Type",
            "Size",
            "Size Bytes",
            "Files",
            "% of Root",
            "Level",
            "Parent",
        ]

        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=headers)
                writer.writeheader()
                writer.writerows(self.results_rows)
        except Exception as exc:
            messagebox.showerror(
                "Export error",
                f"Could not export CSV:\n{exc}",
                parent=self,
            )
            return

        self.status_var.set(f"Exported CSV: {file_path}")

    def export_json(self):
        if not self.results_rows:
            messagebox.showinfo(
                "No results",
                "Please run a scan before exporting.",
                parent=self,
            )
            return

        file_path = filedialog.asksaveasfilename(
            parent=self,
            title="Export scan results to JSON",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )

        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as json_file:
                json.dump(self.results_rows, json_file, indent=2)
        except Exception as exc:
            messagebox.showerror(
                "Export error",
                f"Could not export JSON:\n{exc}",
                parent=self,
            )
            return

        self.status_var.set(f"Exported JSON: {file_path}")


class HDScanApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("HD Folder Size Scanner")
        self.minsize(1000, 600)

        self.style = ttk.Style()
        if "vista" in self.style.theme_names():
            self.style.theme_use("vista")
        elif "clam" in self.style.theme_names():
            self.style.theme_use("clam")

        self.last_path = self._load_last_path()

        self._create_widgets()
        self._create_bindings()
        self.new_tab()

    def _create_widgets(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self, padding=(10, 10, 10, 5))
        toolbar.grid(row=0, column=0, sticky="ew")

        ttk.Button(toolbar, text="New Tab", command=self.new_tab).grid(
            row=0, column=0, padx=(0, 5)
        )

        ttk.Button(toolbar, text="Rename Tab", command=self.rename_current_tab).grid(
            row=0, column=1, padx=(0, 5)
        )

        ttk.Button(toolbar, text="Close Tab", command=self.close_current_tab).grid(
            row=0, column=2, padx=(0, 15)
        )

        ttk.Label(
            toolbar,
            text=(
                "Shortcuts: Ctrl+T new tab | Ctrl+W close tab | "
                "Ctrl+R scan current tab"
            ),
        ).grid(row=0, column=3, sticky="w")

        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=1, column=0, sticky="nsew")

    def _create_bindings(self):
        self.bind("<Control-t>", lambda event: self.new_tab())
        self.bind("<Control-T>", lambda event: self.new_tab())
        self.bind("<Control-w>", lambda event: self.close_current_tab())
        self.bind("<Control-W>", lambda event: self.close_current_tab())
        self.bind("<Control-r>", lambda event: self.current_tab_start_scan())
        self.bind("<Control-R>", lambda event: self.current_tab_start_scan())
        self.bind("<Control-q>", lambda event: self.quit())
        self.bind("<Control-Q>", lambda event: self.quit())

    def _load_last_path(self):
        if not PREFS_FILE.exists():
            return ""

        try:
            data = json.loads(PREFS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return ""

        last_path = data.get("last_path", "")
        if last_path and os.path.isdir(last_path):
            return last_path

        return ""

    def save_last_path(self, path):
        self.last_path = path

        try:
            PREFS_FILE.write_text(
                json.dumps({"last_path": path}),
                encoding="utf-8",
            )
        except Exception:
            pass

    def new_tab(self):
        tab_number = len(self.notebook.tabs()) + 1
        tab = ScanTab(self.notebook, self, initial_path=self.last_path)
        self.notebook.add(tab, text=f"Scan {tab_number}")
        self.notebook.select(tab)

    def close_current_tab(self):
        tabs = self.notebook.tabs()

        if len(tabs) <= 1:
            messagebox.showinfo(
                "Cannot close tab",
                "At least one scan tab must remain open.",
                parent=self,
            )
            return

        current = self.notebook.select()
        if current:
            self.notebook.forget(current)

    def get_current_tab(self):
        current = self.notebook.select()

        if not current:
            return None

        widget = self.nametowidget(current)

        if isinstance(widget, ScanTab):
            return widget

        return None

    def current_tab_start_scan(self):
        tab = self.get_current_tab()

        if tab is not None:
            tab.start_scan()	

    def rename_current_tab(self):
        tab = self.get_current_tab()

        if tab is not None:
            tab.rename_this_tab()

    def rename_tab(self, tab, title):
        tab_id = str(tab)

        if tab_id not in self.notebook.tabs():
            return

        clean_title = title.strip() or "Scan"

        if len(clean_title) > 36:
            clean_title = clean_title[:33] + "..."

        self.notebook.tab(tab_id, text=clean_title)


def main():
    app = HDScanApp()
    app.mainloop()

if __name__ == "__main__":
    main()