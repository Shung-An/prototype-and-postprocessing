from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from PIL import Image, ImageTk  # type: ignore
except ImportError:  # Pillow is optional; the app still works without it.
    Image = None
    ImageTk = None


ROOT_DEFAULT = Path(r"D:\Quantum Squeezing Project\DataFiles")
FINAL_RESULT_NAME = "final_clean_result.png"
MOVIE_NAME = "signal_emergence.mp4"
PIPELINE_SCRIPT_NAME = "cm_pipeline_all_in_one.py"
STD_PLOT_NAME = "raw_std_within_parity.png"


@dataclass
class PhysicsData:
    sample_power_mw: float | None = None
    power_mw_1: float | None = None
    power_mw_2: float | None = None
    environment_temperature_c: float | None = None
    sensitivity_v_photon: float | None = None
    shot_noise_urad2_rthz: float | None = None
    scan_range_mm: float | None = None
    scan_min_mm: float | None = None
    scan_max_mm: float | None = None

    @property
    def center_mm(self) -> float | None:
        if self.scan_min_mm is None or self.scan_max_mm is None:
            return None
        return (self.scan_min_mm + self.scan_max_mm) / 2.0


@dataclass
class RunRecord:
    folder_name: str
    folder_path: Path
    final_result_path: Path
    movie_path: Path | None
    std_plot_path: Path | None
    metadata_path: Path | None
    sortable_date: datetime
    sample: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    filename: str = ""
    duration: str = ""
    star_measurement: bool = False
    physics: PhysicsData = field(default_factory=PhysicsData)
    metadata_text: str = ""
    search_blob: str = ""

    @property
    def tags_display(self) -> str:
        return ", ".join(self.tags)

    @property
    def scan_range_display(self) -> str:
        if self.physics.scan_range_mm is None:
            return "-"
        return f"{self.physics.scan_range_mm:.3f}"

    @property
    def center_display(self) -> str:
        center = self.physics.center_mm
        if center is None:
            return "-"
        return f"{center:.4f}"

    @property
    def shot_noise_display(self) -> str:
        value = self.physics.shot_noise_urad2_rthz
        if value is None:
            return "-"
        return f"{value:.2f}"

    @property
    def sample_power_display(self) -> str:
        if self.physics.sample_power_mw is not None:
            return f"{self.physics.sample_power_mw:.3f}"
        if self.physics.power_mw_1 is not None and self.physics.power_mw_2 is not None:
            return f"{self.physics.power_mw_1:.3f} / {self.physics.power_mw_2:.3f}"
        if self.physics.power_mw_1 is not None:
            return f"{self.physics.power_mw_1:.3f}"
        if self.physics.power_mw_2 is not None:
            return f"{self.physics.power_mw_2:.3f}"
        return "-"

    @property
    def environment_temperature_display(self) -> str:
        value = self.physics.environment_temperature_c
        if value is None:
            return "-"
        return f"{value:.2f}"


def parse_folder_datetime(folder_name: str, fallback_path: Path) -> datetime:
    prefix = folder_name[:15]
    try:
        return datetime.strptime(prefix, "%Y%m%d_%H%M%S")
    except ValueError:
        return datetime.fromtimestamp(fallback_path.stat().st_ctime)


def safe_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _nested_value(payload: object, path: tuple[str, ...]) -> object:
    current = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def first_matching_value(payload: dict[str, object], paths: list[tuple[str, ...]]) -> object:
    for path in paths:
        value = _nested_value(payload, path)
        if value not in (None, ""):
            return value
    return None


def first_matching_float(payload: dict[str, object], paths: list[tuple[str, ...]]) -> float | None:
    return safe_float(first_matching_value(payload, paths))


def safe_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on", "star", "starred"}
    return False


def load_run_record(final_result_path: Path) -> RunRecord:
    folder_path = final_result_path.parent
    folder_name = folder_path.name
    metadata_path = folder_path / "metadata.json"

    record = RunRecord(
        folder_name=folder_name,
        folder_path=folder_path,
        final_result_path=final_result_path,
        movie_path=(folder_path / MOVIE_NAME) if (folder_path / MOVIE_NAME).exists() else None,
        std_plot_path=(folder_path / STD_PLOT_NAME) if (folder_path / STD_PLOT_NAME).exists() else None,
        metadata_path=metadata_path if metadata_path.exists() else None,
        sortable_date=parse_folder_datetime(folder_name, folder_path),
    )

    if record.metadata_path and record.metadata_path.exists():
        try:
            record.metadata_text = record.metadata_path.read_text(encoding="utf-8")
            payload = json.loads(record.metadata_text)

            timestamp = payload.get("Timestamp")
            if isinstance(timestamp, str):
                try:
                    record.sortable_date = datetime.fromisoformat(timestamp)
                except ValueError:
                    pass

            record.sample = payload.get("Sample", "") or ""
            record.description = payload.get("Description", "") or ""
            record.tags = [str(tag) for tag in payload.get("Tags", []) if tag]
            record.filename = payload.get("Filename", "") or ""
            record.duration = payload.get("Duration", "") or ""
            record.star_measurement = safe_bool(
                first_matching_value(
                    payload,
                    [
                        ("StarMeasurement",),
                        ("StarredMeasurement",),
                        ("IsStarMeasurement",),
                        ("IsStarred",),
                    ],
                )
            )

            physics = payload.get("PhysicsData", {}) or {}
            record.physics = PhysicsData(
                sample_power_mw=first_matching_float(
                    payload,
                    [
                        ("SamplePower_mW",),
                        ("SamplePower_mW_1",),
                        ("PhysicsData", "SamplePower_mW"),
                        ("PhysicsData", "SamplePower_mW_1"),
                        ("PhysicsData", "Power_mW_1"),
                        ("Power_mW_1",),
                    ],
                ),
                power_mw_1=safe_float(physics.get("Power_mW_1")),
                power_mw_2=safe_float(physics.get("Power_mW_2")),
                environment_temperature_c=first_matching_float(
                    payload,
                    [
                        ("EnvironmentTemperature_C",),
                        ("EnvironmentTemperatureC",),
                        ("Temperature_C",),
                        ("TemperatureC",),
                        ("PhysicsData", "EnvironmentTemperature_C"),
                        ("PhysicsData", "EnvironmentTemperatureC"),
                        ("Environment", "Temperature_C"),
                        ("Environment", "TemperatureC"),
                    ],
                ),
                sensitivity_v_photon=safe_float(physics.get("Sensitivity_V_photon")),
                shot_noise_urad2_rthz=safe_float(physics.get("ShotNoiseResult_urad2_rtHz")),
                scan_range_mm=safe_float(physics.get("ScanRange_mm")),
                scan_min_mm=safe_float(physics.get("ScanMin_mm")),
                scan_max_mm=safe_float(physics.get("ScanMax_mm")),
            )
        except Exception:
            record.metadata_text = "Could not parse metadata.json"
    else:
        record.metadata_text = "No metadata.json found for this run."

    search_parts = [
        record.folder_name,
        str(record.folder_path),
        record.sample,
        record.description,
        record.tags_display,
        record.filename,
        record.final_result_path.name,
        record.sample_power_display,
        record.environment_temperature_display,
        "star" if record.star_measurement else "",
    ]
    record.search_blob = " ".join(part for part in search_parts if part).lower()
    return record


def scan_runs(root_path: Path) -> list[RunRecord]:
    runs: list[RunRecord] = []
    for final_result_path in root_path.rglob(FINAL_RESULT_NAME):
        if final_result_path.is_file():
            runs.append(load_run_record(final_result_path))
    runs.sort(key=lambda run: run.sortable_date, reverse=True)
    return runs


class DataFilesBrowser(tk.Tk):
    COLUMN_TITLES = {
        "star": "Star",
        "date": "Date",
        "run": "Run Folder",
        "sample": "Sample",
        "power": "Power (mW)",
        "temp": "Temp (C)",
        "duration": "Elapsed",
        "shot_noise": "Shot Noise",
        "range": "Range (mm)",
    }

    COLUMN_WIDTHS = {
        "star": 55,
        "date": 140,
        "run": 220,
        "sample": 185,
        "power": 95,
        "temp": 85,
        "duration": 90,
        "shot_noise": 95,
        "range": 90,
    }

    def __init__(self) -> None:
        super().__init__()
        self.title("DataFiles Browser")
        self.geometry("1500x900")
        self.minsize(1200, 720)
        self.configure(bg="#f3f1ea")

        self.all_runs: list[RunRecord] = []
        self.filtered_runs: list[RunRecord] = []
        self.preview_image = None
        self.analysis_thread: threading.Thread | None = None
        self.sort_column = "date"
        self.sort_descending = True
        self.active_run: RunRecord | None = None
        self.filters_expanded = True
        self.run_by_iid: dict[str, RunRecord] = {}
        self.column_order = ["star", "date", "sample", "power", "temp", "duration", "shot_noise", "range", "run"]
        self.visible_columns = {"star", "date", "sample", "power", "temp", "duration", "shot_noise", "range"}

        self.root_var = tk.StringVar(value=str(ROOT_DEFAULT))
        self.search_var = tk.StringVar()
        self.scan_range_min_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready.")
        self.count_var = tk.StringVar(value="0 runs")

        self._build_ui()
        self.refresh_runs()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = tk.Frame(self, bg="#12353c", padx=16, pady=16)
        header.grid(row=0, column=0, sticky="nsew", padx=16, pady=(16, 8))
        header.columnconfigure(0, weight=1)

        tk.Label(
            header,
            text="Quantum DataFiles Browser",
            bg="#12353c",
            fg="white",
            font=("Segoe UI", 20, "bold"),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            header,
            text="Fast search over runs with final_clean_result preview, metadata, and one-click open actions.",
            bg="#12353c",
            fg="#d7e8ea",
            font=("Segoe UI", 10),
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        controls = tk.Frame(header, bg="#12353c")
        controls.grid(row=0, column=1, rowspan=2, sticky="e")
        tk.Label(controls, text="Root:", bg="#12353c", fg="#d7e8ea").pack(side="left", padx=(0, 8))
        tk.Entry(controls, textvariable=self.root_var, width=48).pack(side="left")
        tk.Button(controls, text="Refresh", width=12, command=self.refresh_runs).pack(side="left", padx=(10, 0))

        body = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=8, bg="#f3f1ea")
        body.grid(row=1, column=0, sticky="nsew", padx=16, pady=8)

        left = tk.Frame(body, bg="#f3f1ea")
        right = tk.Frame(body, bg="#f3f1ea")
        body.add(left, stretch="always", minsize=520)
        body.add(right, stretch="always", minsize=600)

        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        search_box = tk.Frame(left, bg="white", padx=12, pady=12, highlightthickness=1, highlightbackground="#d8e0e1")
        search_box.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        search_box.columnconfigure(0, weight=1)
        tk.Label(search_box, text="Search", bg="white", fg="#12353c", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        self.filter_toggle_button = tk.Button(
            search_box,
            text="Hide Filters",
            width=12,
            command=self.toggle_filter_panel,
        )
        self.filter_toggle_button.grid(row=0, column=1, sticky="e", padx=(8, 0))
        self.search_entry = tk.Entry(search_box, textvariable=self.search_var, font=("Segoe UI", 11))
        self.search_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.search_var.trace_add("write", lambda *_: self.apply_filter())
        self.scan_filter_row = tk.Frame(search_box, bg="white")
        self.scan_filter_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        tk.Label(self.scan_filter_row, text="Scan range >=", bg="white", fg="#12353c").pack(side="left")
        tk.Entry(self.scan_filter_row, textvariable=self.scan_range_min_var, width=10).pack(side="left", padx=(8, 4))
        tk.Label(self.scan_filter_row, text="mm", bg="white", fg="#62777c").pack(side="left")
        self.scan_range_min_var.trace_add("write", lambda *_: self.apply_filter())
        tk.Button(self.scan_filter_row, text="Columns...", command=self.open_column_manager).pack(side="right")
        tk.Label(search_box, textvariable=self.count_var, bg="white", fg="#62777c").grid(row=1, column=1, rowspan=2, sticky="ne", padx=(12, 0))

        table_wrap = tk.Frame(left, bg="white", highlightthickness=1, highlightbackground="#d8e0e1")
        table_wrap.grid(row=1, column=0, sticky="nsew")
        table_wrap.rowconfigure(0, weight=1)
        table_wrap.columnconfigure(0, weight=1)

        columns = tuple(self.column_order)
        self.tree = ttk.Treeview(table_wrap, columns=columns, show="headings", height=24)
        for key in columns:
            self.tree.heading(key, text=self.COLUMN_TITLES[key], command=lambda column=key: self.sort_by_column(column))
            self.tree.column(key, width=self.COLUMN_WIDTHS[key], anchor="w")
        self._apply_display_columns()
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self.on_select_run)
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<Button-3>", self.on_tree_right_click)

        self.tree_menu = tk.Menu(self, tearoff=0)
        self.tree_menu.add_command(label="Toggle Star", command=self.toggle_star_from_menu)
        self.tree_menu.add_command(label="Open Folder", command=self.open_selected_folder)
        self.tree_menu.add_command(label="Open Image", command=self.open_selected_image)
        self.tree_menu.add_command(label="Open MP4", command=self.open_selected_mp4)

        scrollbar = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)

        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        selected_header = tk.Frame(right, bg="white", padx=14, pady=14, highlightthickness=1, highlightbackground="#d8e0e1")
        selected_header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        selected_header.columnconfigure(0, weight=1)
        tk.Label(selected_header, text="Selected Run", bg="white", fg="#12353c", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        self.selected_title = tk.Label(selected_header, text="Nothing selected", bg="white", font=("Segoe UI", 16, "bold"))
        self.selected_title.grid(row=1, column=0, sticky="w", pady=(6, 0))
        action_frame = tk.Frame(selected_header, bg="white")
        action_frame.grid(row=0, column=1, rowspan=2, sticky="e")
        tk.Button(action_frame, text="Open Folder", width=12, command=self.open_selected_folder).pack(side="left", padx=(0, 8))
        tk.Button(action_frame, text="Open Image", width=12, command=self.open_selected_image).pack(side="left", padx=(0, 8))
        tk.Button(action_frame, text="Open MP4", width=12, command=self.open_selected_mp4).pack(side="left", padx=(0, 8))
        tk.Button(action_frame, text="Rerun Selected", width=14, command=self.rerun_selected_analysis).pack(side="left", padx=(0, 8))
        tk.Button(action_frame, text="Rerun Filtered", width=14, command=self.rerun_filtered_analysis).pack(side="left")
        tk.Button(action_frame, text="Run Picked Folders", width=16, command=self.run_picked_folders).pack(side="left", padx=(8, 0))

        content = tk.Frame(right, bg="#f3f1ea")
        content.grid(row=1, column=0, sticky="nsew")
        content.columnconfigure(0, weight=2)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        preview_wrap = tk.Frame(content, bg="white", padx=12, pady=12, highlightthickness=1, highlightbackground="#d8e0e1")
        preview_wrap.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        preview_wrap.rowconfigure(1, weight=1)
        preview_wrap.columnconfigure(0, weight=1)
        tk.Label(preview_wrap, text="final_clean_result Preview", bg="white", fg="#12353c", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w")

        self.preview_label = tk.Label(preview_wrap, bg="#edf2f2", anchor="center")
        self.preview_label.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        self.preview_label.bind("<Double-Button-1>", lambda _event: self.open_selected_mp4())

        detail_wrap = tk.Frame(content, bg="#f3f1ea")
        detail_wrap.grid(row=0, column=1, sticky="nsew")
        detail_wrap.columnconfigure(0, weight=1)
        detail_wrap.rowconfigure(0, weight=1)

        std_wrap = tk.Frame(detail_wrap, bg="white", padx=12, pady=12, highlightthickness=1, highlightbackground="#d8e0e1")
        std_wrap.grid(row=0, column=0, sticky="nsew")
        tk.Label(std_wrap, text="Std Evolution Preview", bg="white", fg="#12353c", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.std_preview_label = tk.Label(std_wrap, bg="#edf2f2", anchor="center")
        self.std_preview_label.pack(fill="both", expand=True, pady=(10, 0))

        status = tk.Label(self, textvariable=self.status_var, bg="#f3f1ea", fg="#5a6e73", anchor="w")
        status.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 12))

    def refresh_runs(self) -> None:
        root_path = Path(self.root_var.get().strip())
        if not root_path.exists():
            messagebox.showwarning("Missing Folder", f"Folder not found:\n{root_path}")
            return

        self.status_var.set("Scanning runs...")
        self.update_idletasks()
        try:
            self.all_runs = scan_runs(root_path)
        except Exception as exc:
            messagebox.showerror("Scan Error", str(exc))
            self.status_var.set("Scan failed.")
            return

        self.apply_filter()
        self.status_var.set(f"Loaded {len(self.all_runs)} runs with {FINAL_RESULT_NAME}.")

    def apply_filter(self) -> None:
        query = self.search_var.get().strip().lower()
        tokens = [token for token in query.split() if token]
        min_range = self._parse_optional_float(self.scan_range_min_var.get())
        if not tokens:
            self.filtered_runs = [
                run for run in self.all_runs
                if self._matches_scan_range(run, min_range)
            ]
        else:
            self.filtered_runs = [
                run for run in self.all_runs
                if all(token in run.search_blob for token in tokens)
                and self._matches_scan_range(run, min_range)
            ]

        self._sort_filtered_runs()
        self._populate_tree()

        self.count_var.set(f"{len(self.filtered_runs)} runs")
        if self.filtered_runs:
            first_iid = str(self.filtered_runs[0].folder_path)
            self.tree.selection_set(first_iid)
            self.tree.focus(first_iid)
            self.show_run(self.filtered_runs[0])
        else:
            self.clear_selection()

    def _populate_tree(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.run_by_iid.clear()

        for run in self.filtered_runs:
            iid = str(run.folder_path)
            self.run_by_iid[iid] = run
            self.tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    "[x]" if run.star_measurement else "[ ]",
                    run.sortable_date.strftime("%Y-%m-%d %H:%M"),
                    run.sample or "-",
                    run.sample_power_display,
                    run.environment_temperature_display,
                    run.duration or "-",
                    run.shot_noise_display,
                    run.scan_range_display,
                    run.folder_name,
                ),
            )

    def _sort_filtered_runs(self) -> None:
        self.filtered_runs.sort(
            key=lambda run: self._sort_key(run, self.sort_column),
            reverse=self.sort_descending,
        )

    def _sort_key(self, run: RunRecord, column: str) -> tuple[int, object]:
        if column == "star":
            return (0, 1 if run.star_measurement else 0)
        if column == "date":
            return (0, run.sortable_date)
        if column == "run":
            return (0, run.folder_name.lower())
        if column == "sample":
            return (0, run.sample.lower())
        if column == "power":
            value = run.physics.sample_power_mw
            if value is None:
                value = run.physics.power_mw_1
            return (1 if value is None else 0, value if value is not None else 0.0)
        if column == "temp":
            value = run.physics.environment_temperature_c
            return (1 if value is None else 0, value if value is not None else 0.0)
        if column == "duration":
            return (0, run.duration.lower())
        if column == "shot_noise":
            value = run.physics.shot_noise_urad2_rthz
            return (1 if value is None else 0, value if value is not None else 0.0)
        if column == "range":
            value = run.physics.scan_range_mm
            return (1 if value is None else 0, value if value is not None else 0.0)
        return (0, run.folder_name.lower())

    def sort_by_column(self, column: str) -> None:
        if self.sort_column == column:
            self.sort_descending = not self.sort_descending
        else:
            self.sort_column = column
            self.sort_descending = column == "date"
        self._sort_filtered_runs()
        self._populate_tree()
        if self.filtered_runs:
            first_iid = str(self.filtered_runs[0].folder_path)
            self.tree.selection_set(first_iid)
            self.tree.focus(first_iid)
            self.show_run(self.filtered_runs[0])
        else:
            self.clear_selection()

    def on_select_run(self, _event: object) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        run = self.run_by_iid.get(selection[0])
        if run is None:
            return
        self.show_run(run)

    def on_tree_double_click(self, event: tk.Event[tk.Widget]) -> None:
        region = self.tree.identify("region", event.x, event.y)
        column_id = self.tree.identify_column(event.x)
        row_id = self.tree.identify_row(event.y)
        if region != "cell" or column_id != "#1" or not row_id:
            return
        run = self.run_by_iid.get(row_id)
        if run is None:
            return
        self.set_star_measurement(run, not run.star_measurement)

    def on_tree_right_click(self, event: tk.Event[tk.Widget]) -> None:
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        self.tree.selection_set(row_id)
        self.tree.focus(row_id)
        run = self.run_by_iid.get(row_id)
        if run is None:
            return
        toggle_label = "Unstar Measurement" if run.star_measurement else "Star Measurement"
        self.tree_menu.entryconfigure(0, label=toggle_label)
        self.tree_menu.tk_popup(event.x_root, event.y_root)

    def toggle_star_from_menu(self) -> None:
        run = self._selected_run()
        if run is None:
            return
        self.set_star_measurement(run, not run.star_measurement)

    def show_run(self, run: RunRecord) -> None:
        self.active_run = run
        summary = run.sample or "Unknown sample"
        self.selected_title.configure(text=f"{summary}   {run.sortable_date.strftime('%Y-%m-%d %H:%M')}")
        self._set_image_preview(self.preview_label, run.final_result_path, (780, 620), "Image not found")
        self._set_image_preview(
            self.std_preview_label,
            run.std_plot_path,
            (720, 620),
            "No raw_std_within_parity.png found.\nRerun analysis for this run.",
        )

    def clear_selection(self) -> None:
        self.active_run = None
        self.selected_title.configure(text="Nothing selected")
        self.preview_label.configure(image="", text="")
        self.std_preview_label.configure(image="", text="Select a run to preview std evolution.")
        self.preview_image = None

    def _set_image_preview(
        self,
        label: tk.Label,
        image_path: Path | None,
        max_size: tuple[int, int],
        missing_text: str,
    ) -> None:
        if image_path is None or not image_path.exists():
            label.configure(image="", text=missing_text)
            if label is self.preview_label:
                self.preview_image = None
            else:
                label.image = None
            return

        try:
            if Image is not None and ImageTk is not None:
                image = Image.open(image_path)
                image.thumbnail(max_size)
                photo = ImageTk.PhotoImage(image)
            else:
                photo = tk.PhotoImage(file=str(image_path))
                max_dim = max(max_size)
                shrink = max(1, (max(photo.width(), photo.height()) // max_dim) + 1)
                photo = photo.subsample(shrink, shrink)

            label.configure(image=photo, text="")
            label.image = photo
            if label is self.preview_label:
                self.preview_image = photo
        except Exception as exc:
            label.configure(image="", text=f"Preview unavailable:\n{exc}")
            if label is self.preview_label:
                self.preview_image = None
            else:
                label.image = None

    @staticmethod
    def _format_number(value: float | None) -> str:
        return "-" if value is None else f"{value:.2f}"

    @staticmethod
    def _parse_optional_float(value: str) -> float | None:
        value = value.strip()
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    @staticmethod
    def _matches_scan_range(run: RunRecord, min_range: float | None) -> bool:
        scan_range = run.physics.scan_range_mm
        if min_range is None:
            return True
        if scan_range is None:
            return False
        if min_range is not None and scan_range < min_range:
            return False
        return True

    def _selected_run(self) -> RunRecord | None:
        selection = self.tree.selection()
        if not selection:
            return None
        return self.run_by_iid.get(selection[0])

    def set_star_measurement(self, run: RunRecord, new_value: bool) -> None:
        try:
            selected_iid = str(run.folder_path)
            payload: dict[str, object]
            if run.metadata_path and run.metadata_path.exists():
                payload = json.loads(run.metadata_path.read_text(encoding="utf-8"))
            else:
                payload = {}
                run.metadata_path = run.folder_path / "metadata.json"

            payload["StarMeasurement"] = new_value
            run.metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            run.star_measurement = new_value
            run.metadata_text = json.dumps(payload, indent=2)
            self._refresh_search_blob(run)
            self._populate_tree()
            if self.tree.exists(selected_iid):
                self.tree.selection_set(selected_iid)
                self.tree.focus(selected_iid)
                self.show_run(run)
            self.status_var.set(f"Updated star flag for {run.folder_name}.")
        except Exception as exc:
            messagebox.showerror("Star Update Failed", f"Could not update metadata.json:\n{exc}")

    def _refresh_search_blob(self, run: RunRecord) -> None:
        search_parts = [
            run.folder_name,
            str(run.folder_path),
            run.sample,
            run.description,
            run.tags_display,
            run.filename,
            run.final_result_path.name,
            run.sample_power_display,
            run.environment_temperature_display,
            "star" if run.star_measurement else "",
        ]
        run.search_blob = " ".join(part for part in search_parts if part).lower()

    def _apply_display_columns(self) -> None:
        visible = [column for column in self.column_order if column in self.visible_columns]
        self.tree.configure(displaycolumns=visible)

    def toggle_filter_panel(self) -> None:
        self.filters_expanded = not self.filters_expanded
        if self.filters_expanded:
            self.search_entry.grid()
            self.scan_filter_row.grid()
            self.filter_toggle_button.configure(text="Hide Filters")
        else:
            self.search_entry.grid_remove()
            self.scan_filter_row.grid_remove()
            self.filter_toggle_button.configure(text="Show Filters")

    def open_column_manager(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Column Manager")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(bg="#f3f1ea")

        tk.Label(dialog, text="Reorder columns and choose which ones are visible.", bg="#f3f1ea", fg="#12353c").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 8)
        )

        listbox = tk.Listbox(dialog, height=10, activestyle="dotbox")
        listbox.grid(row=1, column=0, rowspan=4, sticky="nsew", padx=(12, 8), pady=(0, 12))
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)

        visibility_vars: dict[str, tk.BooleanVar] = {}
        checks = tk.Frame(dialog, bg="#f3f1ea")
        checks.grid(row=1, column=1, sticky="nw", padx=(0, 12), pady=(0, 8))

        def refresh_listbox() -> None:
            listbox.delete(0, tk.END)
            for column in self.column_order:
                visible_label = "Shown" if visibility_vars[column].get() else "Hidden"
                listbox.insert(tk.END, f"{self.COLUMN_TITLES[column]} ({visible_label})")

        for column in self.column_order:
            visibility_vars[column] = tk.BooleanVar(value=column in self.visible_columns)
            tk.Checkbutton(
                checks,
                text=self.COLUMN_TITLES[column],
                variable=visibility_vars[column],
                command=refresh_listbox,
                bg="#f3f1ea",
                activebackground="#f3f1ea",
            ).pack(anchor="w")

        def move_selected(delta: int) -> None:
            selection = listbox.curselection()
            if not selection:
                return
            index = selection[0]
            new_index = index + delta
            if new_index < 0 or new_index >= len(self.column_order):
                return
            self.column_order[index], self.column_order[new_index] = self.column_order[new_index], self.column_order[index]
            refresh_listbox()
            listbox.selection_set(new_index)

        def apply_columns() -> None:
            self.visible_columns = {column for column, var in visibility_vars.items() if var.get()}
            if not self.visible_columns:
                self.visible_columns = {"date"}
            self._apply_display_columns()
            dialog.destroy()

        tk.Button(dialog, text="Move Up", width=14, command=lambda: move_selected(-1)).grid(row=1, column=1, sticky="ne", padx=(0, 12))
        tk.Button(dialog, text="Move Down", width=14, command=lambda: move_selected(1)).grid(row=2, column=1, sticky="ne", padx=(0, 12), pady=(6, 0))
        tk.Button(dialog, text="Apply", width=14, command=apply_columns).grid(row=3, column=1, sticky="se", padx=(0, 12), pady=(18, 0))
        tk.Button(dialog, text="Close", width=14, command=dialog.destroy).grid(row=4, column=1, sticky="ne", padx=(0, 12), pady=(6, 12))

        refresh_listbox()

    def open_selected_folder(self) -> None:
        run = self._selected_run()
        if run is None:
            return
        os.startfile(run.folder_path)  # type: ignore[attr-defined]

    def open_selected_image(self) -> None:
        run = self._selected_run()
        if run is None:
            return
        if run.final_result_path.exists():
            os.startfile(run.final_result_path)  # type: ignore[attr-defined]
        else:
            messagebox.showwarning("Missing Image", f"Could not find:\n{run.final_result_path}")

    def open_selected_mp4(self) -> None:
        run = self._selected_run()
        if run is None:
            return
        if run.movie_path and run.movie_path.exists():
            os.startfile(run.movie_path)  # type: ignore[attr-defined]
        else:
            messagebox.showwarning("Missing MP4", f"Could not find:\n{run.folder_path / MOVIE_NAME}")

    def rerun_selected_analysis(self) -> None:
        run = self._selected_run()
        if run is None:
            messagebox.showinfo("No Selection", "Select a run first.")
            return
        self._start_analysis([run.folder_path], "selected run")

    def rerun_filtered_analysis(self) -> None:
        if not self.filtered_runs:
            messagebox.showinfo("No Runs", "There are no filtered runs to process.")
            return
        folder_paths = [run.folder_path for run in self.filtered_runs]
        self._start_analysis(folder_paths, f"{len(folder_paths)} filtered runs")

    def run_picked_folders(self) -> None:
        folder_paths = self._pick_folder_paths()
        if not folder_paths:
            return
        self._start_analysis(folder_paths, f"{len(folder_paths)} picked folders")

    def _pick_folder_paths(self) -> list[Path]:
        picked_paths: list[Path] = []
        initial_dir = self.root_var.get().strip() or str(ROOT_DEFAULT)

        while True:
            selected = filedialog.askdirectory(
                title="Select a Run Folder for cm_pipeline_all_in_one",
                initialdir=initial_dir,
            )
            if not selected:
                break

            selected_path = Path(selected)
            if selected_path not in picked_paths:
                picked_paths.append(selected_path)
            initial_dir = str(selected_path.parent)

            add_more = messagebox.askyesno(
                "Add Another Folder",
                f"Added:\n{selected_path}\n\nDo you want to add another folder?",
            )
            if not add_more:
                break

        return picked_paths

    def _start_analysis(self, folder_paths: list[Path], label: str) -> None:
        if self.analysis_thread is not None and self.analysis_thread.is_alive():
            messagebox.showinfo("Analysis Running", "A rerun is already in progress.")
            return

        script_path = Path(__file__).with_name(PIPELINE_SCRIPT_NAME)
        if not script_path.is_file():
            messagebox.showerror("Missing Pipeline", f"Could not find:\n{script_path}")
            return

        preview_list = "\n".join(str(path) for path in folder_paths[:8])
        if len(folder_paths) > 8:
            preview_list += f"\n... and {len(folder_paths) - 8} more"
        confirm = messagebox.askyesno(
            "Rerun Analysis",
            f"Rerun cm_pipeline_all_in_one.py for {label}?\n\n{preview_list}",
        )
        if not confirm:
            return

        self.status_var.set(f"Running analysis for {label}...")
        self.analysis_thread = threading.Thread(
            target=self._run_analysis_subprocess,
            args=(script_path, folder_paths, label),
            daemon=True,
        )
        self.analysis_thread.start()

    def _run_analysis_subprocess(self, script_path: Path, folder_paths: list[Path], label: str) -> None:
        command = [sys.executable, str(script_path), *[str(path) for path in folder_paths]]
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as exc:
            self.after(0, lambda: self._handle_analysis_complete(False, label, str(exc)))
            return

        output_lines: list[str] = []
        assert process.stdout is not None
        for raw_line in process.stdout:
            line = raw_line.strip()
            if not line:
                continue
            output_lines.append(line)
            self.after(0, lambda text=line: self.status_var.set(text))

        return_code = process.wait()
        message = "\n".join(output_lines).strip()

        if return_code == 0:
            if not message:
                message = f"Finished rerunning analysis for {label}."
            self.after(0, lambda: self._handle_analysis_complete(True, label, message))
            return

        error_text = message or "Unknown analysis error."
        self.after(0, lambda: self._handle_analysis_complete(False, label, error_text))

    def _handle_analysis_complete(self, success: bool, label: str, message: str) -> None:
        if success:
            self.status_var.set(f"Finished analysis for {label}.")
            self.refresh_runs()
            messagebox.showinfo("Analysis Complete", message)
            return

        self.status_var.set("Analysis failed.")
        messagebox.showerror("Analysis Failed", message)


if __name__ == "__main__":
    app = DataFilesBrowser()
    app.mainloop()
