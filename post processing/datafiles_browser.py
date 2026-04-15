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
from tkinter import messagebox, ttk

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
    power_mw_1: float | None = None
    power_mw_2: float | None = None
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
    def sensitivity_display(self) -> str:
        value = self.physics.sensitivity_v_photon
        if value is None:
            return "-"
        return f"{value:.2f}"

    @property
    def shot_noise_display(self) -> str:
        value = self.physics.shot_noise_urad2_rthz
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

            physics = payload.get("PhysicsData", {}) or {}
            record.physics = PhysicsData(
                power_mw_1=safe_float(physics.get("Power_mW_1")),
                power_mw_2=safe_float(physics.get("Power_mW_2")),
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
        tk.Entry(search_box, textvariable=self.search_var, font=("Segoe UI", 11)).grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.search_var.trace_add("write", lambda *_: self.apply_filter())
        scan_filter_row = tk.Frame(search_box, bg="white")
        scan_filter_row.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        tk.Label(scan_filter_row, text="Scan range >=", bg="white", fg="#12353c").pack(side="left")
        tk.Entry(scan_filter_row, textvariable=self.scan_range_min_var, width=10).pack(side="left", padx=(8, 4))
        tk.Label(scan_filter_row, text="mm", bg="white", fg="#62777c").pack(side="left")
        self.scan_range_min_var.trace_add("write", lambda *_: self.apply_filter())
        tk.Label(search_box, textvariable=self.count_var, bg="white", fg="#62777c").grid(row=0, column=1, rowspan=3, sticky="e", padx=(12, 0))

        table_wrap = tk.Frame(left, bg="white", highlightthickness=1, highlightbackground="#d8e0e1")
        table_wrap.grid(row=1, column=0, sticky="nsew")
        table_wrap.rowconfigure(0, weight=1)
        table_wrap.columnconfigure(0, weight=1)

        columns = ("date", "run", "sample", "duration", "sensitivity", "shot_noise", "range")
        self.tree = ttk.Treeview(table_wrap, columns=columns, show="headings", height=24)
        headings = {
            "date": ("Date", 140),
            "run": ("Run Folder", 220),
            "sample": ("Sample", 170),
            "duration": ("Elapsed", 90),
            "sensitivity": ("Sensitivity", 95),
            "shot_noise": ("Shot Noise", 95),
            "range": ("Range (mm)", 90),
        }
        for key, (title, width) in headings.items():
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self.on_select_run)

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

        content = tk.PanedWindow(right, orient=tk.HORIZONTAL, sashwidth=8, bg="#f3f1ea")
        content.grid(row=1, column=0, sticky="nsew")

        preview_wrap = tk.Frame(content, bg="white", padx=12, pady=12, highlightthickness=1, highlightbackground="#d8e0e1")
        preview_wrap.rowconfigure(1, weight=1)
        preview_wrap.columnconfigure(0, weight=1)
        tk.Label(preview_wrap, text="final_clean_result Preview", bg="white", fg="#12353c", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w")

        self.preview_label = tk.Label(preview_wrap, bg="#edf2f2", anchor="center")
        self.preview_label.grid(row=1, column=0, sticky="nsew", pady=(10, 0))

        detail_wrap = tk.Frame(content, bg="#f3f1ea")
        detail_wrap.columnconfigure(0, weight=1)
        detail_wrap.rowconfigure(0, weight=1)

        std_wrap = tk.Frame(detail_wrap, bg="white", padx=12, pady=12, highlightthickness=1, highlightbackground="#d8e0e1")
        std_wrap.grid(row=0, column=0, sticky="nsew")
        tk.Label(std_wrap, text="Std Evolution Preview", bg="white", fg="#12353c", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.std_preview_label = tk.Label(std_wrap, bg="#edf2f2", anchor="center")
        self.std_preview_label.pack(fill="both", expand=True, pady=(10, 0))

        content.add(preview_wrap, stretch="always", minsize=500)
        content.add(detail_wrap, stretch="always", minsize=360)

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

        for item in self.tree.get_children():
            self.tree.delete(item)

        for index, run in enumerate(self.filtered_runs):
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    run.sortable_date.strftime("%Y-%m-%d %H:%M"),
                    run.folder_name,
                    run.sample or "-",
                    run.duration or "-",
                    run.sensitivity_display,
                    run.shot_noise_display,
                    run.scan_range_display,
                ),
            )

        self.count_var.set(f"{len(self.filtered_runs)} runs")
        if self.filtered_runs:
            self.tree.selection_set("0")
            self.tree.focus("0")
            self.show_run(self.filtered_runs[0])
        else:
            self.clear_selection()

    def on_select_run(self, _event: object) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        run = self.filtered_runs[int(selection[0])]
        self.show_run(run)

    def show_run(self, run: RunRecord) -> None:
        self.selected_title.configure(text=run.folder_name)
        self._set_image_preview(self.preview_label, run.final_result_path, (780, 620), "Image not found")
        self._set_image_preview(
            self.std_preview_label,
            run.std_plot_path,
            (720, 620),
            "No raw_std_within_parity.png found.\nRerun analysis for this run.",
        )

    def clear_selection(self) -> None:
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
        return self.filtered_runs[int(selection[0])]

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
