"""File Metadata Bulk Editor (Standard Library only).

Builds customizable PowerShell scripts for:
1) Timestamp updates (created / modified / accessed)
2) Property metadata updates for top common fields
3) Power rename (counting + custom patterns)
"""

from __future__ import annotations

import random
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

APP_TITLE = "File Metadata Bulk Editor"
DATE_FMT = "%m/%d/%Y %I:%M:%S %p"

COMMON_METADATA_FIELDS = {
    "Title": 21,
    "Subject": 3,
    "Authors": 20,
    "Tags": 18,
    "Comments": 24,
    "Category": 2,
    "Rating": 19,
    "Album": 14,
    "Track Number": 26,
    "Year": 15,
}


@dataclass
class RenameConfig:
    mode: str
    placement: str
    separator: str
    start: int
    padding: int
    prefix_text: str
    suffix_text: str
    custom_pattern: str


class FileMetadataBulkEditor(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1240x860")
        self.minsize(1020, 700)
        ttk.Style(self).theme_use("clam")

        self.folder_path = tk.StringVar()
        self.operation = tk.StringVar(value="timestamps")

        self.date_value = tk.StringVar(value="03/11/2026")
        self.time_value = tk.StringVar(value="12:00:00 PM")
        self.change_created = tk.BooleanVar(value=True)
        self.change_modified = tk.BooleanVar(value=True)
        self.change_accessed = tk.BooleanVar(value=True)
        self.include_root = tk.BooleanVar(value=True)
        self.include_subfolders = tk.BooleanVar(value=True)
        self.include_files = tk.BooleanVar(value=True)
        self.timestamp_mode = tk.StringVar(value="fixed")
        self.range_start_date = tk.StringVar(value="03/01/2026")
        self.range_end_date = tk.StringVar(value="03/31/2026")
        self.work_start_time = tk.StringVar(value="09:00:00 AM")
        self.work_end_time = tk.StringVar(value="05:00:00 PM")
        self.workflow_gap_min = tk.StringVar(value="5")
        self.workflow_gap_max = tk.StringVar(value="45")

        self.meta_recursive = tk.BooleanVar(value=True)
        self.meta_target = tk.StringVar(value="files")
        self.meta_sort = tk.StringVar(value="name")
        self.meta_field = tk.StringVar(value="Track Number")
        self.meta_mode = tk.StringVar(value="counter_only")
        self.meta_mode_token = tk.StringVar(value="numeric")
        self.meta_base_text = tk.StringVar(value="")
        self.meta_start = tk.StringVar(value="1")
        self.meta_padding = tk.StringVar(value="2")
        self.meta_separator = tk.StringVar(value=" - ")
        self.meta_custom_pattern = tk.StringVar(value="{base}{sep}{token}")

        self.rename_recursive = tk.BooleanVar(value=False)
        self.rename_sort = tk.StringVar(value="name")
        self.rename_target = tk.StringVar(value="files")
        self.rename_mode = tk.StringVar(value="numeric")
        self.rename_placement = tk.StringVar(value="prefix")
        self.rename_separator = tk.StringVar(value="_")
        self.rename_start = tk.StringVar(value="1")
        self.rename_padding = tk.StringVar(value="3")
        self.rename_prefix_text = tk.StringVar(value="")
        self.rename_suffix_text = tk.StringVar(value="")
        self.rename_custom_pattern = tk.StringVar(value="ITEM-{token}")

        self._build_ui()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text=APP_TITLE, font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(
            root,
            text="Modern PowerShell script builder for bulk metadata and naming operations.",
            foreground="#4b5563",
        ).pack(anchor="w", pady=(2, 12))

        top = ttk.LabelFrame(root, text="Target Folder", padding=10)
        top.pack(fill="x", pady=(0, 10))
        ttk.Entry(top, textvariable=self.folder_path).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(top, text="Browse…", command=self.browse_folder).pack(side="left")

        op_frame = ttk.LabelFrame(root, text="Operation", padding=10)
        op_frame.pack(fill="x", pady=(0, 10))
        ops = [
            ("Change Created / Modified / Accessed timestamps", "timestamps"),
            ("Power Metadata Editor (10 common fields)", "metadata"),
            ("Power Rename (custom numbering and naming patterns)", "rename"),
        ]
        for label, value in ops:
            ttk.Radiobutton(
                op_frame,
                text=label,
                variable=self.operation,
                value=value,
                command=self.refresh_option_panels,
            ).pack(anchor="w")

        self.options_container = ttk.Frame(root)
        self.options_container.pack(fill="x", pady=(0, 10))

        self.timestamp_frame = ttk.LabelFrame(self.options_container, text="Timestamp Options", padding=10)
        self._build_timestamp_options()

        self.meta_frame = ttk.LabelFrame(self.options_container, text="Power Metadata Options", padding=10)
        self._build_metadata_options()

        self.rename_frame = ttk.LabelFrame(self.options_container, text="Power Naming / Bulk Rename", padding=10)
        self._build_rename_options()

        actions = ttk.Frame(root)
        actions.pack(fill="x", pady=(0, 10))
        for text, cmd in [
            ("Generate Script", self.generate_script),
            ("Self-Check", self.self_check),
            ("Copy Script", self.copy_script),
            ("Save .ps1", self.save_script),
            ("Clear", self.clear_preview),
        ]:
            ttk.Button(actions, text=text, command=cmd).pack(side="left", padx=(0, 8))

        preview_card = ttk.LabelFrame(root, text="Script Preview", padding=8)
        preview_card.pack(fill="both", expand=True)
        self.preview = tk.Text(
            preview_card,
            wrap="none",
            undo=True,
            font=("Cascadia Code", 10),
            bg="#0f172a",
            fg="#e2e8f0",
            insertbackground="#e2e8f0",
        )
        self.preview.pack(side="left", fill="both", expand=True)
        y = ttk.Scrollbar(preview_card, orient="vertical", command=self.preview.yview)
        y.pack(side="right", fill="y")
        x = ttk.Scrollbar(root, orient="horizontal", command=self.preview.xview)
        x.pack(fill="x")
        self.preview.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        self.refresh_option_panels()

    def _build_timestamp_options(self) -> None:
        r1 = ttk.Frame(self.timestamp_frame)
        r1.pack(fill="x", pady=(0, 8))
        ttk.Label(r1, text="Date").pack(side="left")
        ttk.Entry(r1, textvariable=self.date_value, width=14).pack(side="left", padx=(6, 14))
        ttk.Label(r1, text="Time").pack(side="left")
        ttk.Entry(r1, textvariable=self.time_value, width=14).pack(side="left", padx=(6, 14))
        ttk.Label(self.timestamp_frame, text="Format: 03/11/2026 and 12:00:00 PM", foreground="#6b7280").pack(anchor="w", pady=(0, 8))

        r2 = ttk.Frame(self.timestamp_frame)
        r2.pack(fill="x", pady=(0, 8))
        ttk.Checkbutton(r2, text="CreationTime", variable=self.change_created).pack(side="left", padx=(0, 16))
        ttk.Checkbutton(r2, text="LastWriteTime", variable=self.change_modified).pack(side="left", padx=(0, 16))
        ttk.Checkbutton(r2, text="LastAccessTime", variable=self.change_accessed).pack(side="left")

        r3 = ttk.Frame(self.timestamp_frame)
        r3.pack(fill="x")
        ttk.Checkbutton(r3, text="Include root folder", variable=self.include_root).pack(side="left", padx=(0, 16))
        ttk.Checkbutton(r3, text="Include subfolders", variable=self.include_subfolders).pack(side="left", padx=(0, 16))
        ttk.Checkbutton(r3, text="Include files", variable=self.include_files).pack(side="left")

        r4 = ttk.Frame(self.timestamp_frame)
        r4.pack(fill="x", pady=(8, 8))
        ttk.Label(r4, text="Timestamp Mode").pack(side="left")
        ttk.Combobox(r4, textvariable=self.timestamp_mode, values=["fixed", "workflow", "random"], state="readonly", width=12).pack(side="left", padx=(6, 14))

        r5 = ttk.Frame(self.timestamp_frame)
        r5.pack(fill="x", pady=(0, 8))
        ttk.Label(r5, text="Range Start Date").pack(side="left")
        ttk.Entry(r5, textvariable=self.range_start_date, width=12).pack(side="left", padx=(6, 10))
        ttk.Label(r5, text="Range End Date").pack(side="left")
        ttk.Entry(r5, textvariable=self.range_end_date, width=12).pack(side="left", padx=(6, 10))
        ttk.Label(r5, text="Work Start").pack(side="left")
        ttk.Entry(r5, textvariable=self.work_start_time, width=11).pack(side="left", padx=(6, 10))
        ttk.Label(r5, text="Work End").pack(side="left")
        ttk.Entry(r5, textvariable=self.work_end_time, width=11).pack(side="left", padx=(6, 0))

        r6 = ttk.Frame(self.timestamp_frame)
        r6.pack(fill="x")
        ttk.Label(r6, text="Workflow gap minutes (min/max)").pack(side="left")
        ttk.Entry(r6, textvariable=self.workflow_gap_min, width=6).pack(side="left", padx=(6, 6))
        ttk.Entry(r6, textvariable=self.workflow_gap_max, width=6).pack(side="left")

    def _build_metadata_options(self) -> None:
        r1 = ttk.Frame(self.meta_frame)
        r1.pack(fill="x", pady=(0, 8))
        ttk.Label(r1, text="Field").pack(side="left")
        ttk.Combobox(r1, textvariable=self.meta_field, values=list(COMMON_METADATA_FIELDS.keys()), state="readonly", width=18).pack(side="left", padx=(6, 14))
        ttk.Label(r1, text="Target").pack(side="left")
        ttk.Combobox(r1, textvariable=self.meta_target, values=["files", "folders", "files_and_folders"], state="readonly", width=18).pack(side="left", padx=(6, 14))
        ttk.Checkbutton(r1, text="Include subfolders", variable=self.meta_recursive).pack(side="left")

        r2 = ttk.Frame(self.meta_frame)
        r2.pack(fill="x", pady=(0, 8))
        ttk.Label(r2, text="Write Mode").pack(side="left")
        ttk.Combobox(r2, textvariable=self.meta_mode, values=["counter_only", "base_plus_counter", "custom_pattern", "fixed_value", "clear"], state="readonly", width=18).pack(side="left", padx=(6, 14))
        ttk.Label(r2, text="Counter Type").pack(side="left")
        ttk.Combobox(r2, textvariable=self.meta_mode_token, values=["numeric", "alpha", "roman"], state="readonly", width=12).pack(side="left", padx=(6, 14))
        ttk.Label(r2, text="Sort").pack(side="left")
        ttk.Combobox(r2, textvariable=self.meta_sort, values=["name", "created", "modified"], state="readonly", width=10).pack(side="left")

        r3 = ttk.Frame(self.meta_frame)
        r3.pack(fill="x", pady=(0, 8))
        for label, var, w in [
            ("Base Text", self.meta_base_text, 24),
            ("Start", self.meta_start, 6),
            ("Padding", self.meta_padding, 6),
            ("Separator", self.meta_separator, 10),
        ]:
            ttk.Label(r3, text=label).pack(side="left")
            ttk.Entry(r3, textvariable=var, width=w).pack(side="left", padx=(6, 12))

        r4 = ttk.Frame(self.meta_frame)
        r4.pack(fill="x")
        ttk.Label(r4, text="Custom Pattern ({base},{token},{index},{name},{ext},{sep})").pack(side="left")
        ttk.Entry(r4, textvariable=self.meta_custom_pattern).pack(side="left", fill="x", expand=True, padx=(6, 0))

    def _build_rename_options(self) -> None:
        r1 = ttk.Frame(self.rename_frame)
        r1.pack(fill="x", pady=(0, 8))
        ttk.Label(r1, text="Apply To").pack(side="left")
        ttk.Combobox(r1, textvariable=self.rename_target, values=["files", "folders", "files_and_folders"], state="readonly", width=18).pack(side="left", padx=(6, 16))
        ttk.Checkbutton(r1, text="Include subfolders", variable=self.rename_recursive).pack(side="left")

        r2 = ttk.Frame(self.rename_frame)
        r2.pack(fill="x", pady=(0, 8))
        ttk.Label(r2, text="Scheme").pack(side="left")
        ttk.Combobox(r2, textvariable=self.rename_mode, values=["numeric", "alpha", "roman"], state="readonly", width=12).pack(side="left", padx=(6, 16))
        ttk.Label(r2, text="Placement").pack(side="left")
        ttk.Combobox(r2, textvariable=self.rename_placement, values=["prefix", "suffix", "replace"], state="readonly", width=10).pack(side="left", padx=(6, 16))
        ttk.Label(r2, text="Sort").pack(side="left")
        ttk.Combobox(r2, textvariable=self.rename_sort, values=["name", "created", "modified"], state="readonly", width=10).pack(side="left")

        r3 = ttk.Frame(self.rename_frame)
        r3.pack(fill="x", pady=(0, 8))
        for label, var, w in [("Start", self.rename_start, 6), ("Padding", self.rename_padding, 6), ("Separator", self.rename_separator, 8)]:
            ttk.Label(r3, text=label).pack(side="left")
            ttk.Entry(r3, textvariable=var, width=w).pack(side="left", padx=(6, 16))

        r4 = ttk.Frame(self.rename_frame)
        r4.pack(fill="x", pady=(0, 8))
        ttk.Label(r4, text="Fixed Prefix").pack(side="left")
        ttk.Entry(r4, textvariable=self.rename_prefix_text, width=18).pack(side="left", padx=(6, 16))
        ttk.Label(r4, text="Fixed Suffix").pack(side="left")
        ttk.Entry(r4, textvariable=self.rename_suffix_text, width=18).pack(side="left")

        r5 = ttk.Frame(self.rename_frame)
        r5.pack(fill="x")
        ttk.Label(r5, text="Custom Pattern ({name},{ext},{token},{index})").pack(side="left")
        ttk.Entry(r5, textvariable=self.rename_custom_pattern).pack(side="left", fill="x", expand=True, padx=(6, 0))

    def refresh_option_panels(self) -> None:
        for frame in (self.timestamp_frame, self.meta_frame, self.rename_frame):
            frame.pack_forget()
        mapping = {
            "timestamps": self.timestamp_frame,
            "metadata": self.meta_frame,
            "rename": self.rename_frame,
        }
        mapping[self.operation.get()].pack(fill="x")

    @staticmethod
    def ps_escape(value: str) -> str:
        return value.replace("'", "''")

    def browse_folder(self) -> None:
        selected = filedialog.askdirectory(title="Select Folder")
        if selected:
            self.folder_path.set(selected)

    def validate_folder(self) -> str | None:
        folder = self.folder_path.get().strip()
        if not folder:
            messagebox.showerror("Missing Folder", "Please select or enter a folder path.")
            return None
        return folder

    def validate_datetime(self) -> str | None:
        raw = f"{self.date_value.get().strip()} {self.time_value.get().strip()}"
        try:
            return datetime.strptime(raw, DATE_FMT).strftime(DATE_FMT)
        except ValueError:
            messagebox.showerror("Invalid Date/Time", "Expected Date: 03/11/2026 and Time: 12:00:00 PM")
            return None

    def _validate_time(self, value: str) -> datetime | None:
        try:
            return datetime.strptime(value.strip(), "%I:%M:%S %p")
        except ValueError:
            return None

    def _validate_timestamp_range(self) -> tuple[str, str, str, str, int, int] | None:
        try:
            start_d = datetime.strptime(self.range_start_date.get().strip(), "%m/%d/%Y")
            end_d = datetime.strptime(self.range_end_date.get().strip(), "%m/%d/%Y")
        except ValueError:
            messagebox.showerror("Invalid Date Range", "Use mm/dd/yyyy for start/end dates.")
            return None
        if start_d > end_d:
            messagebox.showerror("Invalid Date Range", "Range start date must be before end date.")
            return None
        if not self._validate_time(self.work_start_time.get()) or not self._validate_time(self.work_end_time.get()):
            messagebox.showerror("Invalid Work Hours", "Use hh:mm:ss AM/PM for work start/end times.")
            return None
        try:
            gap_min = int(self.workflow_gap_min.get().strip())
            gap_max = int(self.workflow_gap_max.get().strip())
        except ValueError:
            messagebox.showerror("Invalid Gap", "Workflow gap min/max must be integers.")
            return None
        if gap_min < 1 or gap_max < gap_min:
            messagebox.showerror("Invalid Gap", "Gap min must be >= 1 and max must be >= min.")
            return None
        return (
            start_d.strftime("%m/%d/%Y"),
            end_d.strftime("%m/%d/%Y"),
            self.work_start_time.get().strip(),
            self.work_end_time.get().strip(),
            gap_min,
            gap_max,
        )

    def generate_script(self) -> None:
        folder = self.validate_folder()
        if not folder:
            return
        builders = {
            "timestamps": self.build_timestamp_script,
            "metadata": self.build_metadata_script,
            "rename": self.build_rename_script,
        }
        script = builders[self.operation.get()](folder)
        if script:
            self.preview.delete("1.0", "end")
            self.preview.insert("1.0", script)

    def build_timestamp_script(self, folder: str) -> str | None:
        mode = self.timestamp_mode.get()
        target = self.validate_datetime() if mode == "fixed" else None
        if mode == "fixed" and not target:
            return None
        range_values = self._validate_timestamp_range() if mode in {"workflow", "random"} else None
        if mode in {"workflow", "random"} and not range_values:
            return None

        if not any([self.change_created.get(), self.change_modified.get(), self.change_accessed.get()]):
            messagebox.showerror("No Timestamp Selected", "Select at least one timestamp field.")
            return None

        folder = self.ps_escape(folder)
        lines = []
        if self.change_created.get():
            lines.append("        $_.CreationTime = $targetDate")
        if self.change_modified.get():
            lines.append("        $_.LastWriteTime = $targetDate")
        if self.change_accessed.get():
            lines.append("        $_.LastAccessTime = $targetDate")
        block = "\n".join(lines)

        include_root = "$true" if self.include_root.get() else "$false"
        include_subfolders = "$true" if self.include_subfolders.get() else "$false"
        include_files = "$true" if self.include_files.get() else "$false"

        base = f"""# Power Timestamp Update
$folderPath = '{folder}'
$includeRoot = {include_root}
$includeSubfolders = {include_subfolders}
$includeFiles = {include_files}
"""
        if mode == "fixed":
            return base + f"""
$targetDate = Get-Date '{target}'

if ($includeRoot) {{
    Get-Item -LiteralPath $folderPath -Force | ForEach-Object {{
{block}
    }}
}}

if ($includeSubfolders -or $includeFiles) {{
    $items = Get-ChildItem -LiteralPath $folderPath -Recurse -Force
    if ($includeSubfolders -and -not $includeFiles) {{
        $items = $items | Where-Object {{ $_.PSIsContainer }}
    }} elseif ($includeFiles -and -not $includeSubfolders) {{
        $items = $items | Where-Object {{ -not $_.PSIsContainer }}
    }}

    $items | ForEach-Object {{
{block}
    }}
}}

Write-Host 'Done.'
"""
        start_d, end_d, work_start, work_end, gap_min, gap_max = range_values
        randomize = "$true" if mode == "random" else "$false"
        return base + f"""
$rangeStartDate = Get-Date '{start_d}'
$rangeEndDate = Get-Date '{end_d}'
$workStart = [datetime]::ParseExact('{work_start}', 'hh:mm:ss tt', $null)
$workEnd = [datetime]::ParseExact('{work_end}', 'hh:mm:ss tt', $null)
$gapMin = {gap_min}
$gapMax = {gap_max}
$randomize = {randomize}

$allItems = @()
if ($includeRoot) {{ $allItems += Get-Item -LiteralPath $folderPath -Force }}
if ($includeSubfolders -or $includeFiles) {{
    $child = Get-ChildItem -LiteralPath $folderPath -Recurse -Force
    if ($includeSubfolders -and -not $includeFiles) {{
        $child = $child | Where-Object {{ $_.PSIsContainer }}
    }} elseif ($includeFiles -and -not $includeSubfolders) {{
        $child = $child | Where-Object {{ -not $_.PSIsContainer }}
    }}
    $allItems += $child
}}
$allItems = $allItems | Sort-Object FullName

$dayCount = [int]($rangeEndDate.Date - $rangeStartDate.Date).TotalDays + 1
$cursor = [datetime]::ParseExact(\"$($rangeStartDate.ToString('MM/dd/yyyy')) $($workStart.ToString('hh:mm:ss tt'))\", 'MM/dd/yyyy hh:mm:ss tt', $null)

foreach($it in $allItems) {{
    if ($randomize) {{
        $dayOffset = Get-Random -Minimum 0 -Maximum $dayCount
        $datePart = $rangeStartDate.Date.AddDays($dayOffset)
        $startMin = ($workStart.Hour * 60 + $workStart.Minute)
        $endMin = ($workEnd.Hour * 60 + $workEnd.Minute)
        $minuteOffset = Get-Random -Minimum 0 -Maximum (($endMin - $startMin) + 1)
        $targetDate = $datePart.AddMinutes($startMin + $minuteOffset)
    }} else {{
        $targetDate = $cursor
        $addMin = Get-Random -Minimum $gapMin -Maximum ($gapMax + 1)
        $cursor = $cursor.AddMinutes($addMin)
        if ($cursor.TimeOfDay -gt $workEnd.TimeOfDay) {{
            $cursor = $cursor.Date.AddDays(1).Add($workStart.TimeOfDay)
        }}
        if ($cursor.Date -gt $rangeEndDate.Date) {{
            $cursor = $rangeStartDate.Date.Add($workStart.TimeOfDay)
        }}
    }}
    $_ = $it
{block}
}}
Write-Host 'Done.'
"""

    def self_check(self) -> None:
        folder = self.validate_folder()
        if not folder:
            return
        issues: list[str] = []
        if self.operation.get() == "timestamps":
            if not any([self.change_created.get(), self.change_modified.get(), self.change_accessed.get()]):
                issues.append("Select at least one timestamp field.")
            if self.timestamp_mode.get() == "fixed" and not self.validate_datetime():
                issues.append("Fixed mode requires valid date/time.")
            if self.timestamp_mode.get() in {"workflow", "random"} and not self._validate_timestamp_range():
                issues.append("Workflow/Random mode requires valid date range, work hours, and gaps.")
        elif self.operation.get() == "metadata":
            if not self._validate_counter_values(self.meta_start.get(), self.meta_padding.get()):
                issues.append("Metadata counter start/padding are invalid.")
        elif self.operation.get() == "rename":
            if not self._validate_counter_values(self.rename_start.get(), self.rename_padding.get()):
                issues.append("Rename counter start/padding are invalid.")

        if issues:
            messagebox.showerror("Self-Check Failed", "\n".join(f"- {i}" for i in issues))
        else:
            messagebox.showinfo("Self-Check", "All settings look valid for script generation.")

    def _token_expr(self, mode: str) -> str:
        if mode == "numeric":
            return "$token = ($i).ToString().PadLeft($padding, '0')"
        if mode == "alpha":
            return "$token = [char](64 + $i)"
        return "$roman=@('I','II','III','IV','V','VI','VII','VIII','IX','X'); $token = if($i -le 10){$roman[$i-1]} else {$i}"

    def _validate_counter_values(self, start_raw: str, padding_raw: str) -> tuple[int, int] | None:
        try:
            start = int(start_raw.strip())
            padding = int(padding_raw.strip())
            if padding < 0:
                raise ValueError
            return start, padding
        except ValueError:
            messagebox.showerror("Invalid Counter Settings", "Start/Padding must be valid integers (padding >= 0).")
            return None

    def build_metadata_script(self, folder: str) -> str | None:
        values = self._validate_counter_values(self.meta_start.get(), self.meta_padding.get())
        if not values:
            return None
        start, padding = values

        field = self.meta_field.get()
        index = COMMON_METADATA_FIELDS[field]
        folder = self.ps_escape(folder)

        target_map = {"files": "-File", "folders": "-Directory", "files_and_folders": ""}
        recurse = "-Recurse" if self.meta_recursive.get() else ""
        token_expr = self._token_expr(self.meta_mode_token.get())

        return f"""# Power Metadata Editor
$folderPath = '{folder}'
$fieldIndex = {index}
$mode = '{self.meta_mode.get()}'
$base = '{self.ps_escape(self.meta_base_text.get())}'
$start = {start}
$padding = {padding}
$sep = '{self.ps_escape(self.meta_separator.get())}'
$pattern = '{self.ps_escape(self.meta_custom_pattern.get())}'

$shell = New-Object -ComObject Shell.Application
$items = Get-ChildItem -LiteralPath $folderPath {recurse} -Force {target_map[self.meta_target.get()]} | Sort-Object {self.meta_sort.get()}
$counter = 0
foreach($item in $items) {{
    $counter++
    $i = $start + $counter - 1
    {token_expr}
    $name = [System.IO.Path]::GetFileNameWithoutExtension($item.Name)
    $ext = [System.IO.Path]::GetExtension($item.Name)

    switch($mode) {{
        'clear' {{ $value = '' }}
        'fixed_value' {{ $value = $base }}
        'counter_only' {{ $value = $token }}
        'base_plus_counter' {{ $value = "$base$sep$token" }}
        'custom_pattern' {{ $value = $pattern.Replace('{{base}}',$base).Replace('{{token}}',$token).Replace('{{index}}',$i).Replace('{{name}}',$name).Replace('{{ext}}',$ext).Replace('{{sep}}',$sep) }}
    }}

    $dir = Split-Path -Parent $item.FullName
    $leaf = Split-Path -Leaf $item.FullName
    $ns = $shell.Namespace($dir)
    if ($null -ne $ns) {{
        $entry = $ns.ParseName($leaf)
        if ($null -ne $entry) {{
            $ns.SetDetailsOf($entry, $fieldIndex, $value)
            Write-Host "Updated {field}: $($item.FullName) -> $value"
        }}
    }}
}}
Write-Host 'Done.'
"""

    def build_rename_script(self, folder: str) -> str | None:
        parsed = self._validate_counter_values(self.rename_start.get(), self.rename_padding.get())
        if not parsed:
            return None
        start, padding = parsed
        cfg = RenameConfig(
            mode=self.rename_mode.get(),
            placement=self.rename_placement.get(),
            separator=self.rename_separator.get(),
            start=start,
            padding=padding,
            prefix_text=self.rename_prefix_text.get(),
            suffix_text=self.rename_suffix_text.get(),
            custom_pattern=self.rename_custom_pattern.get(),
        )

        folder = self.ps_escape(folder)
        target_map = {"files": "-File", "folders": "-Directory", "files_and_folders": ""}
        recurse = "-Recurse" if self.rename_recursive.get() else ""

        return f"""# Power Rename
$folderPath = '{folder}'
$start = {cfg.start}
$padding = {cfg.padding}
$sep = '{self.ps_escape(cfg.separator)}'
$fixedPrefix = '{self.ps_escape(cfg.prefix_text)}'
$fixedSuffix = '{self.ps_escape(cfg.suffix_text)}'
$pattern = '{self.ps_escape(cfg.custom_pattern)}'

$items = Get-ChildItem -LiteralPath $folderPath {recurse} -Force {target_map[self.rename_target.get()]} | Sort-Object {self.rename_sort.get()}
$index = 0
foreach($item in $items) {{
    $index++
    $i = $start + $index - 1
    {self._token_expr(cfg.mode)}
    $name = [System.IO.Path]::GetFileNameWithoutExtension($item.Name)
    $ext = [System.IO.Path]::GetExtension($item.Name)
    $custom = $pattern.Replace('{{name}}',$name).Replace('{{ext}}',$ext).Replace('{{token}}',$token).Replace('{{index}}',$i)

    switch ('{cfg.placement}') {{
        'prefix' {{ $newBase = "$fixedPrefix$token$sep$name$fixedSuffix" }}
        'suffix' {{ $newBase = "$fixedPrefix$name$sep$token$fixedSuffix" }}
        'replace' {{ $newBase = $custom }}
    }}

    $newName = if($item.PSIsContainer) {{ $newBase }} else {{ "$newBase$ext" }}
    Rename-Item -LiteralPath $item.FullName -NewName $newName -ErrorAction Stop
    Write-Host "Renamed: $($item.Name) -> $newName"
}}
Write-Host 'Done.'
"""

    def copy_script(self) -> None:
        text = self.preview.get("1.0", "end").strip()
        if not text:
            messagebox.showinfo("Nothing to Copy", "Generate a script first.")
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Copied", "Script copied to clipboard.")

    def save_script(self) -> None:
        text = self.preview.get("1.0", "end").strip()
        if not text:
            messagebox.showinfo("Nothing to Save", "Generate a script first.")
            return

        path = filedialog.asksaveasfilename(
            title="Save Script",
            defaultextension=".ps1",
            filetypes=[("PowerShell", "*.ps1"), ("Text", "*.txt")],
        )
        if not path:
            return

        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        messagebox.showinfo("Saved", f"Script saved to:\n{path}")

    def clear_preview(self) -> None:
        self.preview.delete("1.0", "end")


if __name__ == "__main__":
    app = FileMetadataBulkEditor()
    app.mainloop()
