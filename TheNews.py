from __future__ import annotations

import json
import platform
import re
import subprocess
import tkinter as tk
import webbrowser
from dataclasses import asdict, dataclass
from pathlib import Path
from tkinter import messagebox, ttk
from typing import List, Optional


APP_TITLE = "Website Library and Chrome Launcher"
DATA_FILE = Path(__file__).with_name("website_library_data.json")


DEFAULT_OLD_DATA = {
    "U.S. Mainstream & Regional": [
        {"name": "Washington Post", "url": "https://www.washingtonpost.com"},
        {"name": "Wall Street Journal", "url": "https://www.wsj.com"},
        {"name": "New York Times", "url": "https://www.nytimes.com"},
        {"name": "Los Angeles Times", "url": "https://www.latimes.com"},
        {"name": "Pittsburgh Post-Gazette", "url": "https://www.post-gazette.com"},
        {"name": "CNN", "url": "https://www.cnn.com"},
        {"name": "Associated Press (AP)", "url": "https://apnews.com"},
        {"name": "Fox News", "url": "https://www.foxnews.com"},
        {"name": "Politico", "url": "https://www.politico.com"},
        {"name": "The Hill", "url": "https://thehill.com"},
        {"name": "New York Post", "url": "https://nypost.com"},
    ],
    "International": [
        {"name": "The Times (London)", "url": "https://www.thetimes.co.uk"},
        {"name": "The Telegraph", "url": "https://www.telegraph.co.uk"},
        {"name": "The Guardian", "url": "https://www.theguardian.com"},
        {"name": "London Evening Standard", "url": "https://www.standard.co.uk"},
        {"name": "BBC", "url": "https://www.bbc.com/news"},
        {"name": "Al Jazeera", "url": "https://www.aljazeera.com"},
        {"name": "Al-Monitor", "url": "https://www.al-monitor.com"},
        {"name": "Electronic Intifada", "url": "https://electronicintifada.net"},
        {"name": "Jerusalem Post", "url": "https://www.jpost.com"},
    ],
    "Independent Media": [
        {"name": "Drop Site News", "url": "https://www.dropsitenews.com"},
        {"name": "Consortium News", "url": "https://consortiumnews.com"},
        {"name": "Axios", "url": "https://www.axios.com"},
        {"name": "CovertAction Magazine", "url": "https://covertactionmagazine.com"},
    ],
    "Local (Wisconsin)": [
        {"name": "Wisconsin News", "url": "https://www.wisconsinpublicradio.org/news"},
        {"name": "Milwaukee Journal Sentinel", "url": "https://www.jsonline.com"},
        {"name": "Milwaukee News", "url": "https://www.tmj4.com"},
        {"name": "Green Bay Press-Gazette", "url": "https://www.greenbaypressgazette.com"},
        {"name": "Green Bay local news", "url": "https://www.wbay.com"},
        {"name": "De Pere local news", "url": "https://www.wbay.com/news/local"},
        {"name": "Appleton News", "url": "https://www.postcrescent.com"},
    ],
}


@dataclass
class Website:
    """Represents one saved website."""

    name: str
    url: str
    starred: bool = False


@dataclass
class Heading:
    """Represents one heading and its websites."""

    name: str
    starred: bool = False
    sites: List[Website] | None = None

    def __post_init__(self) -> None:
        if self.sites is None:
            self.sites = []


class WebsiteLibraryApp(tk.Tk):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()

        self.title(APP_TITLE)
        self.geometry("1180x740")
        self.minsize(980, 620)

        self.headings: List[Heading] = []
        self.selected_heading_index: Optional[int] = None
        self.selected_site_index: Optional[int] = None

        self.force_chrome = tk.BooleanVar(value=True)
        self.search_var = tk.StringVar()
        self.site_name_var = tk.StringVar()
        self.site_url_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready.")

        self.bg = "#f4f6f8"
        self.panel = "#ffffff"
        self.text = "#1f2937"
        self.muted = "#6b7280"
        self.accent = "#2563eb"
        self.accent_dark = "#1d4ed8"

        self.configure_styles()
        self.load_data()
        self.create_layout()
        self.bind_shortcuts()
        self.refresh_all()

    def configure_styles(self) -> None:
        """Configure ttk theme and visual styling."""

        style = ttk.Style(self)

        if "clam" in style.theme_names():
            style.theme_use("clam")

        self.configure(bg=self.bg)

        style.configure(".", font=("Segoe UI", 10), background=self.bg, foreground=self.text)
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"), background=self.bg)
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10), background=self.bg, foreground=self.muted)
        style.configure("Panel.TFrame", background=self.panel)
        style.configure("Section.TLabel", font=("Segoe UI", 12, "bold"), background=self.panel)
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), padding=(12, 8), background=self.accent, foreground="white")
        style.map("Accent.TButton", background=[("active", self.accent_dark)], foreground=[("active", "white")])
        style.configure("TButton", padding=(10, 7))
        style.configure("TEntry", padding=7)
        style.configure("Treeview", rowheight=30, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

    def create_layout(self) -> None:
        """Create the full application layout."""

        outer = ttk.Frame(self, padding=18)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 16))

        ttk.Label(header, text="Website Library", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Store, organize, star, reorder, search, bulk-edit, and open your websites.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(3, 0))

        toolbar = ttk.Frame(outer, style="Panel.TFrame", padding=12)
        toolbar.pack(fill="x", pady=(0, 12))

        ttk.Label(toolbar, text="Search").pack(side="left", padx=(0, 8))

        self.search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=45)
        self.search_entry.pack(side="left", padx=(0, 12))
        self.search_entry.bind("<KeyRelease>", lambda _event: self.refresh_all())

        ttk.Checkbutton(
            toolbar,
            text="Google Chrome Open Links",
            variable=self.force_chrome,
        ).pack(side="left", padx=(8, 16))

        ttk.Button(toolbar, text="Clear Search", command=self.clear_search).pack(side="left")

        ttk.Button(
            toolbar,
            text="Open Selected",
            style="Accent.TButton",
            command=self.open_selected,
        ).pack(side="right")

        body = ttk.PanedWindow(outer, orient="horizontal")
        body.pack(fill="both", expand=True)

        left_panel = ttk.Frame(body, style="Panel.TFrame", padding=12)
        middle_panel = ttk.Frame(body, style="Panel.TFrame", padding=12)
        right_panel = ttk.Frame(body, style="Panel.TFrame", padding=12)

        body.add(left_panel, weight=1)
        body.add(middle_panel, weight=2)
        body.add(right_panel, weight=2)

        self.create_headings_panel(left_panel)
        self.create_sites_panel(middle_panel)
        self.create_editor_panel(right_panel)

        status_frame = ttk.Frame(outer)
        status_frame.pack(fill="x", pady=(10, 0))

        ttk.Label(status_frame, textvariable=self.status_var, style="Subtitle.TLabel").pack(side="left")

    def create_headings_panel(self, parent: ttk.Frame) -> None:
        """Create heading list and heading controls."""

        ttk.Label(parent, text="Headings", style="Section.TLabel").pack(anchor="w")

        self.heading_list = tk.Listbox(
            parent,
            height=18,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#d1d5db",
            selectbackground=self.accent,
            selectforeground="white",
            font=("Segoe UI", 10),
            activestyle="none",
        )
        self.heading_list.pack(fill="both", expand=True, pady=10)
        self.heading_list.bind("<<ListboxSelect>>", self.on_heading_select)

        row_one = ttk.Frame(parent, style="Panel.TFrame")
        row_one.pack(fill="x")

        ttk.Button(row_one, text="Add", command=self.add_heading).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ttk.Button(row_one, text="Rename", command=self.rename_heading).pack(side="left", expand=True, fill="x", padx=4)
        ttk.Button(row_one, text="Delete", command=self.delete_heading).pack(side="left", expand=True, fill="x", padx=(4, 0))

        row_two = ttk.Frame(parent, style="Panel.TFrame")
        row_two.pack(fill="x", pady=(8, 0))

        ttk.Button(row_two, text="★ Star", command=self.toggle_heading_star).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ttk.Button(row_two, text="↑ Up", command=self.move_heading_up).pack(side="left", expand=True, fill="x", padx=4)
        ttk.Button(row_two, text="↓ Down", command=self.move_heading_down).pack(side="left", expand=True, fill="x", padx=(4, 0))

        ttk.Button(
            parent,
            text="Open All in Heading",
            style="Accent.TButton",
            command=self.open_all_in_selected_heading,
        ).pack(fill="x", pady=(10, 0))

        ttk.Button(
            parent,
            text="Bulk Add / Edit Heading List",
            command=self.open_bulk_editor,
        ).pack(fill="x", pady=(8, 0))

    def create_sites_panel(self, parent: ttk.Frame) -> None:
        """Create website table and website controls."""

        ttk.Label(parent, text="Websites", style="Section.TLabel").pack(anchor="w")

        self.site_tree = ttk.Treeview(parent, columns=("star", "name", "url"), show="headings", selectmode="browse")
        self.site_tree.heading("star", text="★")
        self.site_tree.heading("name", text="Site Name")
        self.site_tree.heading("url", text="URL")
        self.site_tree.column("star", width=44, anchor="center", stretch=False)
        self.site_tree.column("name", width=200, anchor="w")
        self.site_tree.column("url", width=360, anchor="w")
        self.site_tree.pack(fill="both", expand=True, pady=10)

        self.site_tree.bind("<<TreeviewSelect>>", self.on_site_select)
        self.site_tree.bind("<Double-1>", lambda _event: self.open_selected())

        row_one = ttk.Frame(parent, style="Panel.TFrame")
        row_one.pack(fill="x")

        ttk.Button(row_one, text="Add Site", command=self.add_site).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ttk.Button(row_one, text="Delete Site", command=self.delete_site).pack(side="left", expand=True, fill="x", padx=4)
        ttk.Button(row_one, text="Copy URL", command=self.copy_selected_url).pack(side="left", expand=True, fill="x", padx=(4, 0))

        row_two = ttk.Frame(parent, style="Panel.TFrame")
        row_two.pack(fill="x", pady=(8, 0))

        ttk.Button(row_two, text="★ Star Site", command=self.toggle_site_star).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ttk.Button(row_two, text="↑ Up", command=self.move_site_up).pack(side="left", expand=True, fill="x", padx=4)
        ttk.Button(row_two, text="↓ Down", command=self.move_site_down).pack(side="left", expand=True, fill="x", padx=(4, 0))

    def create_editor_panel(self, parent: ttk.Frame) -> None:
        """Create site editor panel."""

        ttk.Label(parent, text="Site Editor", style="Section.TLabel").pack(anchor="w")

        form = ttk.Frame(parent, style="Panel.TFrame")
        form.pack(fill="x", pady=(14, 10))

        ttk.Label(form, text="Heading").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.heading_combo = ttk.Combobox(form, state="readonly")
        self.heading_combo.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        ttk.Label(form, text="Site Name").grid(row=2, column=0, sticky="w", pady=(0, 6))
        self.site_name_entry = ttk.Entry(form, textvariable=self.site_name_var)
        self.site_name_entry.grid(row=3, column=0, sticky="ew", pady=(0, 12))

        ttk.Label(form, text="URL").grid(row=4, column=0, sticky="w", pady=(0, 6))
        self.site_url_entry = ttk.Entry(form, textvariable=self.site_url_var)
        self.site_url_entry.grid(row=5, column=0, sticky="ew", pady=(0, 12))

        form.columnconfigure(0, weight=1)

        ttk.Button(parent, text="Save Site Changes", style="Accent.TButton", command=self.save_site_changes).pack(fill="x", pady=(0, 8))
        ttk.Button(parent, text="Open URL From Editor", command=self.open_editor_url).pack(fill="x", pady=(0, 8))

        help_text = (
            "Tips:\n"
            "• Select a heading to view its websites.\n"
            "• Use ★ Star to highlight headings or websites.\n"
            "• Use ↑ Up and ↓ Down to reorder headings or websites.\n"
            "• Double-click a website to open it.\n"
            "• Select a heading, then click Open All in Heading.\n"
            "• Use Bulk Add / Edit Heading List to paste many websites at once.\n"
            "• Bulk format: Site Name | https://example.com\n"
            "• URL-only lines also work.\n"
            "• Ctrl+F jumps to search.\n"
            "• Ctrl+N starts a new site.\n"
            "• Ctrl+S saves site changes.\n"
            "• Delete removes the selected site.\n"
            "• Data autosaves to website_library_data.json."
        )

        help_box = tk.Text(
            parent,
            height=15,
            wrap="word",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#d1d5db",
            bg="#f9fafb",
            fg=self.text,
            font=("Segoe UI", 10),
            padx=12,
            pady=12,
        )
        help_box.pack(fill="both", expand=True, pady=(12, 0))
        help_box.insert("1.0", help_text)
        help_box.configure(state="disabled")

    def bind_shortcuts(self) -> None:
        """Bind keyboard shortcuts."""

        self.bind("<Control-f>", lambda _event: self.focus_search())
        self.bind("<Control-n>", lambda _event: self.add_site())
        self.bind("<Control-s>", lambda _event: self.save_site_changes())
        self.bind("<Return>", lambda _event: self.open_selected())
        self.bind("<Delete>", lambda _event: self.delete_site())

    def load_data(self) -> None:
        """Load saved data, including migration from older format."""

        if not DATA_FILE.exists():
            self.headings = self.convert_old_data(DEFAULT_OLD_DATA)
            self.save_data()
            return

        try:
            with DATA_FILE.open("r", encoding="utf-8") as file:
                raw = json.load(file)

            if isinstance(raw, dict) and "headings" in raw:
                self.headings = self.load_new_format(raw)
            elif isinstance(raw, dict):
                self.headings = self.convert_old_data(raw)
                self.save_data()
            else:
                raise ValueError("Unsupported data format")

        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            messagebox.showwarning(
                "Data File Problem",
                "The saved data file could not be read. The default library was loaded instead.",
            )
            self.headings = self.convert_old_data(DEFAULT_OLD_DATA)

    def load_new_format(self, raw: dict) -> List[Heading]:
        """Load the newer JSON format."""

        headings: List[Heading] = []

        for heading_data in raw.get("headings", []):
            sites = [
                Website(
                    name=site.get("name", ""),
                    url=site.get("url", ""),
                    starred=site.get("starred", False),
                )
                for site in heading_data.get("sites", [])
            ]

            headings.append(
                Heading(
                    name=heading_data.get("name", "Untitled"),
                    starred=heading_data.get("starred", False),
                    sites=sites,
                )
            )

        return headings

    def convert_old_data(self, raw: dict) -> List[Heading]:
        """Convert old heading to list data into new structured format."""

        headings: List[Heading] = []

        for heading_name, sites in raw.items():
            heading = Heading(name=heading_name, starred=False, sites=[])

            for site in sites:
                heading.sites.append(
                    Website(
                        name=site.get("name", ""),
                        url=site.get("url", ""),
                        starred=site.get("starred", False),
                    )
                )

            headings.append(heading)

        return headings

    def save_data(self) -> None:
        """Save data to JSON while preserving order and starred status."""

        serializable = {
            "version": 2,
            "headings": [
                {
                    "name": heading.name,
                    "starred": heading.starred,
                    "sites": [asdict(site) for site in heading.sites],
                }
                for heading in self.headings
            ],
        }

        try:
            with DATA_FILE.open("w", encoding="utf-8") as file:
                json.dump(serializable, file, indent=2, ensure_ascii=False)
            self.set_status("Saved.")
        except OSError as error:
            messagebox.showerror("Save Error", f"Could not save data:\n{error}")

    def refresh_all(self) -> None:
        """Refresh all visible data."""

        self.refresh_headings()
        self.refresh_sites()
        self.refresh_heading_combo()

    def refresh_headings(self) -> None:
        """Refresh the heading list without sorting."""

        self.heading_list.delete(0, tk.END)

        query = self.search_var.get().strip().lower()

        for index, heading in enumerate(self.headings):
            marker = "★ " if heading.starred else "  "
            display = f"{marker}{heading.name}"

            if query:
                combined = f"{heading.name} " + " ".join(
                    f"{site.name} {site.url}" for site in heading.sites
                )
                if query not in combined.lower():
                    continue

            self.heading_list.insert(tk.END, display)
            self.heading_list.itemconfig(tk.END, foreground="#b45309" if heading.starred else self.text)

        if self.selected_heading_index is not None and self.selected_heading_index < len(self.headings):
            visible_index = self.get_visible_heading_listbox_index(self.selected_heading_index)
            if visible_index is not None:
                self.heading_list.selection_set(visible_index)
                self.heading_list.see(visible_index)

    def refresh_sites(self) -> None:
        """Refresh website tree for selected heading."""

        for item in self.site_tree.get_children():
            self.site_tree.delete(item)

        if self.selected_heading_index is None or self.selected_heading_index >= len(self.headings):
            self.set_status("No heading selected.")
            return

        heading = self.headings[self.selected_heading_index]
        query = self.search_var.get().strip().lower()
        shown = 0

        for index, site in enumerate(heading.sites):
            searchable = f"{heading.name} {site.name} {site.url}".lower()

            if query and query not in searchable:
                continue

            star = "★" if site.starred else ""
            item_id = self.site_tree.insert("", tk.END, values=(star, site.name, site.url), tags=(str(index),))

            if site.starred:
                self.site_tree.item(item_id, tags=(str(index), "starred"))

            shown += 1

        self.site_tree.tag_configure("starred", foreground="#b45309")
        self.set_status(f"{shown} site(s) shown.")

    def refresh_heading_combo(self) -> None:
        """Refresh heading dropdown in editor."""

        self.heading_combo["values"] = [heading.name for heading in self.headings]

        if self.selected_heading_index is not None and self.selected_heading_index < len(self.headings):
            self.heading_combo.set(self.headings[self.selected_heading_index].name)
        elif self.headings:
            self.heading_combo.set(self.headings[0].name)
        else:
            self.heading_combo.set("")

    def get_visible_heading_listbox_index(self, heading_index: int) -> Optional[int]:
        """Map actual heading index to currently visible listbox index."""

        query = self.search_var.get().strip().lower()
        visible_position = 0

        for index, heading in enumerate(self.headings):
            if query:
                combined = f"{heading.name} " + " ".join(
                    f"{site.name} {site.url}" for site in heading.sites
                )
                if query not in combined.lower():
                    continue

            if index == heading_index:
                return visible_position

            visible_position += 1

        return None

    def get_actual_heading_index_from_visible(self, visible_index: int) -> Optional[int]:
        """Map visible listbox index to actual heading index."""

        query = self.search_var.get().strip().lower()
        visible_position = 0

        for index, heading in enumerate(self.headings):
            if query:
                combined = f"{heading.name} " + " ".join(
                    f"{site.name} {site.url}" for site in heading.sites
                )
                if query not in combined.lower():
                    continue

            if visible_position == visible_index:
                return index

            visible_position += 1

        return None

    def on_heading_select(self, _event: tk.Event) -> None:
        """Handle heading selection."""

        selection = self.heading_list.curselection()

        if not selection:
            return

        actual_index = self.get_actual_heading_index_from_visible(selection[0])

        if actual_index is None:
            return

        self.selected_heading_index = actual_index
        self.selected_site_index = None

        self.clear_editor()
        self.refresh_sites()
        self.refresh_heading_combo()

    def on_site_select(self, _event: tk.Event) -> None:
        """Handle website selection."""

        selected = self.site_tree.selection()

        if not selected or self.selected_heading_index is None:
            return

        item = selected[0]
        tags = self.site_tree.item(item, "tags")

        if not tags:
            return

        try:
            site_index = int(tags[0])
        except ValueError:
            return

        heading = self.headings[self.selected_heading_index]

        if site_index >= len(heading.sites):
            return

        site = heading.sites[site_index]
        self.selected_site_index = site_index

        self.heading_combo.set(heading.name)
        self.site_name_var.set(site.name)
        self.site_url_var.set(site.url)

    def add_heading(self) -> None:
        """Add a new heading."""

        dialog = TextInputDialog(self, "Add Heading", "New heading name:")
        name = dialog.result

        if not name:
            return

        if any(heading.name == name for heading in self.headings):
            messagebox.showwarning("Duplicate Heading", "That heading already exists.")
            return

        self.headings.append(Heading(name=name, starred=False, sites=[]))
        self.selected_heading_index = len(self.headings) - 1

        self.save_data()
        self.refresh_all()

    def rename_heading(self) -> None:
        """Rename selected heading."""

        heading = self.get_selected_heading()

        if heading is None:
            messagebox.showinfo("No Heading Selected", "Select a heading first.")
            return

        dialog = TextInputDialog(
            self,
            "Rename Heading",
            "New heading name:",
            initial_value=heading.name,
        )

        new_name = dialog.result

        if not new_name or new_name == heading.name:
            return

        if any(item.name == new_name for item in self.headings):
            messagebox.showwarning("Duplicate Heading", "That heading already exists.")
            return

        heading.name = new_name
        self.save_data()
        self.refresh_all()

    def delete_heading(self) -> None:
        """Delete selected heading."""

        if self.selected_heading_index is None:
            messagebox.showinfo("No Heading Selected", "Select a heading first.")
            return

        heading = self.headings[self.selected_heading_index]

        confirmed = messagebox.askyesno(
            "Delete Heading",
            f"Delete the heading '{heading.name}' and all websites under it?",
        )

        if not confirmed:
            return

        del self.headings[self.selected_heading_index]

        if self.headings:
            self.selected_heading_index = min(self.selected_heading_index, len(self.headings) - 1)
        else:
            self.selected_heading_index = None

        self.selected_site_index = None
        self.clear_editor()

        self.save_data()
        self.refresh_all()

    def toggle_heading_star(self) -> None:
        """Toggle star on selected heading."""

        heading = self.get_selected_heading()

        if heading is None:
            messagebox.showinfo("No Heading Selected", "Select a heading first.")
            return

        heading.starred = not heading.starred
        self.save_data()
        self.refresh_headings()

    def move_heading_up(self) -> None:
        """Move selected heading up one position."""

        if self.selected_heading_index is None or self.selected_heading_index <= 0:
            return

        index = self.selected_heading_index
        self.headings[index - 1], self.headings[index] = self.headings[index], self.headings[index - 1]
        self.selected_heading_index = index - 1

        self.save_data()
        self.refresh_all()

    def move_heading_down(self) -> None:
        """Move selected heading down one position."""

        if self.selected_heading_index is None:
            return

        index = self.selected_heading_index

        if index >= len(self.headings) - 1:
            return

        self.headings[index + 1], self.headings[index] = self.headings[index], self.headings[index + 1]
        self.selected_heading_index = index + 1

        self.save_data()
        self.refresh_all()

    def add_site(self) -> None:
        """Prepare the editor for a new site."""

        if not self.headings:
            messagebox.showinfo("No Headings", "Create a heading before adding a site.")
            return

        if self.selected_heading_index is None:
            self.selected_heading_index = 0

        self.selected_site_index = None
        self.heading_combo.set(self.headings[self.selected_heading_index].name)
        self.site_name_var.set("")
        self.site_url_var.set("https://")
        self.site_name_entry.focus_set()

    def save_site_changes(self) -> None:
        """Save a new or edited site."""

        heading_name = self.heading_combo.get().strip()
        name = self.site_name_var.get().strip()
        url = self.site_url_var.get().strip()

        if not heading_name:
            messagebox.showwarning("Missing Heading", "Choose a heading.")
            return

        if not name:
            messagebox.showwarning("Missing Site Name", "Enter a site name.")
            return

        if not url:
            messagebox.showwarning("Missing URL", "Enter a URL.")
            return

        target_heading_index = self.find_heading_index_by_name(heading_name)

        if target_heading_index is None:
            messagebox.showwarning("Heading Not Found", "The selected heading could not be found.")
            return

        url = self.normalize_url(url)

        if self.selected_heading_index is not None and self.selected_site_index is not None:
            old_heading = self.headings[self.selected_heading_index]

            if self.selected_site_index < len(old_heading.sites):
                site = old_heading.sites.pop(self.selected_site_index)
                site.name = name
                site.url = url
                self.headings[target_heading_index].sites.append(site)
                self.selected_heading_index = target_heading_index
                self.selected_site_index = len(self.headings[target_heading_index].sites) - 1
            else:
                self.headings[target_heading_index].sites.append(Website(name=name, url=url))
        else:
            self.headings[target_heading_index].sites.append(Website(name=name, url=url))
            self.selected_heading_index = target_heading_index
            self.selected_site_index = len(self.headings[target_heading_index].sites) - 1

        self.save_data()
        self.refresh_all()
        self.set_status(f"Saved site: {name}")

    def delete_site(self) -> None:
        """Delete selected website."""

        heading = self.get_selected_heading()

        if heading is None or self.selected_site_index is None:
            return

        if self.selected_site_index >= len(heading.sites):
            return

        site = heading.sites[self.selected_site_index]

        confirmed = messagebox.askyesno("Delete Site", f"Delete '{site.name}'?")

        if not confirmed:
            return

        del heading.sites[self.selected_site_index]
        self.selected_site_index = None
        self.clear_editor()

        self.save_data()
        self.refresh_sites()

    def toggle_site_star(self) -> None:
        """Toggle star on selected website."""

        heading = self.get_selected_heading()

        if heading is None or self.selected_site_index is None:
            messagebox.showinfo("No Site Selected", "Select a website first.")
            return

        if self.selected_site_index >= len(heading.sites):
            return

        heading.sites[self.selected_site_index].starred = not heading.sites[self.selected_site_index].starred
        self.save_data()
        self.refresh_sites()

    def move_site_up(self) -> None:
        """Move selected website up one position."""

        heading = self.get_selected_heading()

        if heading is None or self.selected_site_index is None:
            return

        index = self.selected_site_index

        if index <= 0:
            return

        heading.sites[index - 1], heading.sites[index] = heading.sites[index], heading.sites[index - 1]
        self.selected_site_index = index - 1

        self.save_data()
        self.refresh_sites()
        self.select_site_by_index(self.selected_site_index)

    def move_site_down(self) -> None:
        """Move selected website down one position."""

        heading = self.get_selected_heading()

        if heading is None or self.selected_site_index is None:
            return

        index = self.selected_site_index

        if index >= len(heading.sites) - 1:
            return

        heading.sites[index + 1], heading.sites[index] = heading.sites[index], heading.sites[index + 1]
        self.selected_site_index = index + 1

        self.save_data()
        self.refresh_sites()
        self.select_site_by_index(self.selected_site_index)

    def select_site_by_index(self, site_index: int) -> None:
        """Select a site row by its actual index."""

        for item in self.site_tree.get_children():
            tags = self.site_tree.item(item, "tags")

            if tags and tags[0] == str(site_index):
                self.site_tree.selection_set(item)
                self.site_tree.see(item)
                break

    def open_bulk_editor(self) -> None:
        """Open bulk editor for selected heading."""

        heading = self.get_selected_heading()

        if heading is None:
            messagebox.showinfo("No Heading Selected", "Select a heading first.")
            return

        BulkEditorDialog(self, heading.name)

    def save_bulk_sites(self, heading_name: str, text: str) -> None:
        """Replace one heading's website list from bulk text."""

        heading_index = self.find_heading_index_by_name(heading_name)

        if heading_index is None:
            messagebox.showwarning("Heading Not Found", "The heading could not be found.")
            return

        parsed_sites = self.parse_bulk_sites(text)

        if not parsed_sites:
            messagebox.showwarning(
                "No Valid Websites",
                "No valid website addresses were found in the bulk list.",
            )
            return

        self.headings[heading_index].sites = parsed_sites
        self.selected_heading_index = heading_index
        self.selected_site_index = None

        self.save_data()
        self.refresh_all()
        self.set_status(f"Saved {len(parsed_sites)} site(s) under {heading_name}.")

    def parse_bulk_sites(self, text: str) -> List[Website]:
        """Parse pasted website lines into Website objects."""

        sites: List[Website] = []
        seen_urls = set()

        for raw_line in text.splitlines():
            line = raw_line.strip()

            if not line:
                continue

            starred = False

            if line.startswith("★"):
                starred = True
                line = line.lstrip("★").strip()

            name, url = self.parse_site_line(line)

            if not url:
                continue

            url = self.normalize_url(url)

            if url in seen_urls:
                continue

            seen_urls.add(url)

            if not name:
                name = self.name_from_url(url)

            sites.append(Website(name=name, url=url, starred=starred))

        return sites

    def parse_site_line(self, line: str) -> tuple[str, str]:
        """Parse one line into name and URL."""

        if "|" in line:
            name_part, url_part = line.split("|", 1)
            name = name_part.strip()
            url = url_part.strip()

            if "." in url:
                return name, url

        url_match = re.search(
            r"(https?://[^\s|]+|www\.[^\s|]+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}[^\s|]*)",
            line,
        )

        if not url_match:
            return "", ""

        url = url_match.group(1).strip()
        name = line[:url_match.start()].strip(" |,\t:-")

        return name, url

    def open_selected(self) -> None:
        """Open selected website."""

        heading = self.get_selected_heading()

        if heading is None or self.selected_site_index is None:
            messagebox.showinfo("No Site Selected", "Select a website first.")
            return

        if self.selected_site_index >= len(heading.sites):
            return

        self.open_url(heading.sites[self.selected_site_index].url)

    def open_all_in_selected_heading(self) -> None:
        """Open every website under selected heading."""

        heading = self.get_selected_heading()

        if heading is None:
            messagebox.showinfo("No Heading Selected", "Select a heading first.")
            return

        if not heading.sites:
            messagebox.showinfo("No Websites", f"There are no websites saved under '{heading.name}'.")
            return

        confirmed = messagebox.askyesno(
            "Open All Websites",
            f"Open all {len(heading.sites)} website(s) under '{heading.name}'?",
        )

        if not confirmed:
            return

        for site in heading.sites:
            self.open_url(site.url)

        self.set_status(f"Opened {len(heading.sites)} website(s) from heading: {heading.name}")

    def open_editor_url(self) -> None:
        """Open URL currently typed in editor."""

        url = self.site_url_var.get().strip()

        if not url:
            messagebox.showinfo("No URL", "Enter a URL first.")
            return

        self.open_url(url)

    def open_url(self, url: str) -> None:
        """Open URL in Chrome or default browser."""

        url = self.normalize_url(url)

        if self.force_chrome.get():
            opened = self.open_in_chrome(url)

            if opened:
                self.set_status(f"Opened in Chrome: {url}")
                return

            messagebox.showwarning(
                "Chrome Not Found",
                "Google Chrome could not be found. The link will open in your default browser instead.",
            )

        webbrowser.open_new_tab(url)
        self.set_status(f"Opened in default browser: {url}")

    def open_in_chrome(self, url: str) -> bool:
        """Try to open URL specifically in Google Chrome."""

        system = platform.system()

        if system == "Windows":
            chrome_commands = [
                ["cmd", "/c", "start", "chrome", url],
                [r"C:\Program Files\Google\Chrome\Application\chrome.exe", url],
                [r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe", url],
            ]
        elif system == "Darwin":
            chrome_commands = [["open", "-a", "Google Chrome", url]]
        else:
            chrome_commands = [
                ["google-chrome", url],
                ["google-chrome-stable", url],
                ["chromium-browser", url],
                ["chromium", url],
            ]

        for command in chrome_commands:
            try:
                subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except OSError:
                continue

        try:
            chrome = webbrowser.get("chrome")
            chrome.open_new_tab(url)
            return True
        except webbrowser.Error:
            return False

    def copy_selected_url(self) -> None:
        """Copy selected URL to clipboard."""

        heading = self.get_selected_heading()

        if heading is None or self.selected_site_index is None:
            messagebox.showinfo("No Site Selected", "Select a website first.")
            return

        if self.selected_site_index >= len(heading.sites):
            return

        url = heading.sites[self.selected_site_index].url

        self.clipboard_clear()
        self.clipboard_append(url)

        self.set_status("URL copied to clipboard.")

    def clear_search(self) -> None:
        """Clear search box."""

        self.search_var.set("")
        self.refresh_all()

    def clear_editor(self) -> None:
        """Clear editor fields."""

        self.site_name_var.set("")
        self.site_url_var.set("")

    def focus_search(self) -> None:
        """Focus search box."""

        self.search_entry.focus_set()
        self.search_entry.select_range(0, tk.END)

    def get_selected_heading(self) -> Optional[Heading]:
        """Return selected heading object."""

        if self.selected_heading_index is None:
            return None

        if self.selected_heading_index >= len(self.headings):
            return None

        return self.headings[self.selected_heading_index]

    def find_heading_index_by_name(self, name: str) -> Optional[int]:
        """Find heading index by name."""

        for index, heading in enumerate(self.headings):
            if heading.name == name:
                return index

        return None

    @staticmethod
    def normalize_url(url: str) -> str:
        """Add https:// when user enters a bare domain."""

        url = url.strip()

        if url.startswith(("http://", "https://")):
            return url

        return f"https://{url}"

    @staticmethod
    def name_from_url(url: str) -> str:
        """Create readable site name from URL."""

        clean = url.replace("https://", "").replace("http://", "")
        clean = clean.split("/")[0]
        clean = clean.replace("www.", "")

        main = clean.split(".")[0]

        return main.replace("-", " ").replace("_", " ").title()

    def set_status(self, message: str) -> None:
        """Update status line."""

        self.status_var.set(message)


class TextInputDialog(tk.Toplevel):
    """Simple modal text input dialog."""

    def __init__(self, parent: tk.Tk, title: str, prompt: str, initial_value: str = "") -> None:
        super().__init__(parent)

        self.result: Optional[str] = None

        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        frame = ttk.Frame(self, padding=18)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text=prompt).pack(anchor="w", pady=(0, 8))

        self.value_var = tk.StringVar(value=initial_value)
        entry = ttk.Entry(frame, textvariable=self.value_var, width=44)
        entry.pack(fill="x", pady=(0, 14))
        entry.focus_set()
        entry.select_range(0, tk.END)

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")

        ttk.Button(buttons, text="Cancel", command=self.cancel).pack(side="right")
        ttk.Button(buttons, text="OK", command=self.accept).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda _event: self.accept())
        self.bind("<Escape>", lambda _event: self.cancel())

        self.update_idletasks()
        self.center_on_parent(parent)

        parent.wait_window(self)

    def center_on_parent(self, parent: tk.Tk) -> None:
        """Center dialog over parent."""

        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (self.winfo_reqwidth() // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (self.winfo_reqheight() // 2)

        self.geometry(f"+{x}+{y}")

    def accept(self) -> None:
        """Accept typed value."""

        value = self.value_var.get().strip()
        self.result = value if value else None
        self.destroy()

    def cancel(self) -> None:
        """Cancel dialog."""

        self.result = None
        self.destroy()


class BulkEditorDialog(tk.Toplevel):
    """Bulk editor for all websites under one heading."""

    def __init__(self, parent: WebsiteLibraryApp, heading_name: str) -> None:
        super().__init__(parent)

        self.parent_app = parent
        self.heading_name = heading_name

        self.title(f"Bulk Add / Edit: {heading_name}")
        self.geometry("780x580")
        self.minsize(700, 480)
        self.transient(parent)
        self.grab_set()

        self.create_widgets()
        self.load_existing_sites()

    def create_widgets(self) -> None:
        """Create bulk editor UI."""

        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text=f"Bulk Add / Edit Websites Under: {self.heading_name}",
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w")

        instructions = (
            "Edit the full list below, then click Save Full List.\n"
            "Accepted formats:\n"
            "★ Site Name | https://example.com\n"
            "Site Name | https://example.com\n"
            "Site Name    https://example.com\n"
            "https://example.com"
        )

        ttk.Label(outer, text=instructions, foreground="#6b7280").pack(anchor="w", pady=(6, 10))

        text_frame = ttk.Frame(outer)
        text_frame.pack(fill="both", expand=True)

        self.text_box = tk.Text(
            text_frame,
            wrap="none",
            undo=True,
            font=("Consolas", 10),
            padx=10,
            pady=10,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#d1d5db",
        )
        self.text_box.pack(side="left", fill="both", expand=True)

        y_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=self.text_box.yview)
        y_scroll.pack(side="right", fill="y")
        self.text_box.configure(yscrollcommand=y_scroll.set)

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(12, 0))

        ttk.Button(buttons, text="Clear Box", command=self.clear_box).pack(side="left")

        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")

        ttk.Button(
            buttons,
            text="Save Full List",
            command=self.save_full_list,
        ).pack(side="right", padx=(0, 8))

    def load_existing_sites(self) -> None:
        """Load existing sites into the text box."""

        heading_index = self.parent_app.find_heading_index_by_name(self.heading_name)

        if heading_index is None:
            return

        heading = self.parent_app.headings[heading_index]

        lines = []

        for site in heading.sites:
            star = "★ " if site.starred else ""
            lines.append(f"{star}{site.name} | {site.url}")

        self.text_box.insert("1.0", "\n".join(lines))

    def save_full_list(self) -> None:
        """Save full edited list."""

        text = self.text_box.get("1.0", tk.END)
        self.parent_app.save_bulk_sites(self.heading_name, text)
        self.destroy()

    def clear_box(self) -> None:
        """Clear the text box."""

        confirmed = messagebox.askyesno(
            "Clear Box",
            "Clear the text box? This will not change your saved websites until you click Save Full List.",
        )

        if confirmed:
            self.text_box.delete("1.0", tk.END)


def main() -> None:
    """Start the application."""

    app = WebsiteLibraryApp()
    app.mainloop()


if __name__ == "__main__":
    main()