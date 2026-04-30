from __future__ import annotations

import json
import math
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

try:
    from PIL import Image, ImageTk  # type: ignore
except ImportError:  # Pillow is optional; the app still works without it.
    Image = None
    ImageTk = None

try:
    from metadata_manager import normalize_metadata, safe_tags, safe_text
except ImportError:
    def safe_text(value: object, default: str = "") -> str:
        if value is None:
            return default
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (int, float, bool)):
            return str(value)
        if isinstance(value, list):
            return ", ".join(safe_text(item) for item in value if safe_text(item))
        return default

    def safe_tags(value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [safe_text(item) for item in value if safe_text(item)]
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return []

    def normalize_metadata(payload: dict[str, object]) -> dict[str, object]:
        return payload


ROOT_DEFAULT = Path(r"D:\Quantum Squeezing Project\DataFiles")
FINAL_RESULT_NAME = "final_clean_result.png"
MOVIE_NAME = "signal_emergence.mp4"
PIPELINE_SCRIPT_NAME = "cm_pipeline_all_in_one.py"
LOGLOG_PLOT_NAME = "loglog_eval.png"
DIAGONAL_OFFSET_PLOT_NAMES = ("diagonal_offset_matrix_urad2.png", "diagonal_offset_matrix_V2.png")
RAW_STD_PLOT_NAMES = ("raw_std_over_time.png", "raw_std_within_parity.png")
CONFIG_PATH = Path(tempfile.gettempdir()) / "quantum_datafiles_browser_config.json"
INDEX_DB_PATH = Path(tempfile.gettempdir()) / "quantum_datafiles_browser_index.sqlite3"
INDEX_SCHEMA_VERSION = 2
FILTER_DEBOUNCE_MS = 180
PREVIEW_RESIZE_DEBOUNCE_MS = 120
PREVIEW_SIZE_BUCKET_PX = 64
PREVIEW_CACHE_LIMIT = 48
FFT_DEFAULT_OUTPUT_DIR = Path(r"C:\Quantum Squeezing\Andy test\GageStreamThruGPU-FFT")
FFT_RESULT_IMAGE_NAME = "fft_result_python.png"
FFT_CHANNEL_FILES = (
    ("Board 1 Ch 1", "Data_1_1"),
    ("Board 1 Ch 2", "Data_1_2"),
    ("Board 2 Ch 1", "Data_2_1"),
    ("Board 2 Ch 2", "Data_2_2"),
)


@dataclass
class PhysicsData:
    sample_power_mw: float | None = None
    power_mw_1: float | None = None
    power_mw_2: float | None = None
    environment_temperature_k: float | None = None
    environment_temperature_c: float | None = None
    sensitivity_v_photon: float | None = None
    shot_noise_urad2_rthz: float | None = None
    shot_noise_v2_rthz: float | None = None
    shot_noise_unit: str = ""
    is_dark_noise_run: bool = False
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
    loglog_plot_path: Path | None
    diagonal_offset_path: Path | None
    raw_std_plot_path: Path | None
    metadata_path: Path | None
    sortable_date: datetime
    sample: str = ""
    exp_tag: str = ""
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
        value = self.shot_noise_value_display
        unit = self.shot_noise_unit_display
        if value == "-":
            return value
        return f"{value} {unit}" if unit else value

    @property
    def shot_noise_value_display(self) -> str:
        unit = self.physics.shot_noise_unit.strip().lower()
        if self.physics.shot_noise_v2_rthz is not None and (self.physics.is_dark_noise_run or unit.startswith("v")):
            return f"{self.physics.shot_noise_v2_rthz:.3g}"
        if self.physics.shot_noise_urad2_rthz is not None:
            return f"{self.physics.shot_noise_urad2_rthz:.2f}"
        if self.physics.shot_noise_v2_rthz is not None:
            return f"{self.physics.shot_noise_v2_rthz:.3g}"
        return "-"

    @property
    def shot_noise_unit_display(self) -> str:
        unit = self.physics.shot_noise_unit.strip()
        if self.physics.shot_noise_v2_rthz is not None and (self.physics.is_dark_noise_run or unit.lower().startswith("v")):
            return "V^2/rtHz"
        if self.physics.shot_noise_urad2_rthz is not None:
            return "urad^2/rtHz"
        if self.physics.shot_noise_v2_rthz is not None:
            return "V^2/rtHz"
        return unit

    @property
    def sample_power_display(self) -> str:
        if self.physics.sample_power_mw is not None:
            return f"{self.physics.sample_power_mw:.3f}"
        return "-"

    @property
    def port_power_display(self) -> str:
        if self.physics.power_mw_1 is not None and self.physics.power_mw_2 is not None:
            return f"{self.physics.power_mw_1:.3f} / {self.physics.power_mw_2:.3f}"
        if self.physics.power_mw_1 is not None:
            return f"{self.physics.power_mw_1:.3f}"
        if self.physics.power_mw_2 is not None:
            return f"{self.physics.power_mw_2:.3f}"
        return "-"

    @property
    def environment_temperature_display_k(self) -> str:
        value = self.physics.environment_temperature_k
        if value is None:
            value_c = self.physics.environment_temperature_c
            if value_c is None:
                return "-"
            value = value_c + 273.15
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
        result = float(value)
        return result if math.isfinite(result) else None
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


def first_existing_path(folder_path: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        candidate = folder_path / name
        if candidate.exists():
            return candidate
    return None


def parse_fft_header(header_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in header_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def find_fft_output_dir(preferred_dir: Path | None = None) -> Path:
    candidates = []
    if preferred_dir is not None:
        candidates.append(preferred_dir)
    candidates.extend(
        [
            FFT_DEFAULT_OUTPUT_DIR,
            FFT_DEFAULT_OUTPUT_DIR / "x64" / "Debug",
            Path.cwd(),
        ]
    )

    for candidate in candidates:
        if candidate.exists() and any((candidate / f"{stem}.bin").is_file() for _, stem in FFT_CHANNEL_FILES):
            return candidate

    return (preferred_dir or FFT_DEFAULT_OUTPUT_DIR).expanduser().resolve()


def _average_fft_file(data_path: Path, fft_size: int, chunk_frames: int = 1024) -> tuple[object, int]:
    try:
        import numpy as np  # type: ignore
    except ImportError as exc:
        raise RuntimeError("NumPy is required to average FFT output files.") from exc

    point_count = data_path.stat().st_size // 8
    frame_count = point_count // fft_size
    if frame_count <= 0:
        raise ValueError(f"No complete FFT frames found in {data_path}")

    mmap = np.memmap(data_path, dtype=np.float64, mode="r", shape=(frame_count, fft_size))
    total = np.zeros(fft_size, dtype=np.float64)
    for start in range(0, frame_count, chunk_frames):
        stop = min(start + chunk_frames, frame_count)
        total += mmap[start:stop].sum(axis=0)
    return total / frame_count, frame_count


def build_fft_spectrum_plot(output_dir: Path | None = None, open_image: bool = True) -> Path:
    try:
        import matplotlib.pyplot as plt  # type: ignore
        import numpy as np  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Matplotlib and NumPy are required to plot FFT results.") from exc

    output_dir = find_fft_output_dir(output_dir)
    first_header_path = output_dir / f"{FFT_CHANNEL_FILES[0][1]}.fft"
    if not first_header_path.is_file():
        raise FileNotFoundError(f"Could not find FFT header: {first_header_path}")

    header = parse_fft_header(first_header_path)
    sample_rate_hz = float(header.get("SampleRate", "1000000000"))
    fft_length = int(header.get("FftLength", "8192"))
    fft_size = int(header.get("FftSize", str(fft_length // 2 + 1)))
    freqs_mhz = np.arange(fft_size, dtype=np.float64) * sample_rate_hz / fft_length / 1e6

    fig, ax = plt.subplots(figsize=(12, 7), dpi=120)
    plotted = 0
    frame_counts: list[int] = []
    for label, stem in FFT_CHANNEL_FILES:
        data_path = output_dir / f"{stem}.bin"
        header_path = output_dir / f"{stem}.fft"
        if not data_path.is_file() or not header_path.is_file():
            continue
        channel_header = parse_fft_header(header_path)
        channel_fft_size = int(channel_header.get("FftSize", str(fft_size)))
        if channel_fft_size != fft_size:
            raise ValueError(f"{header_path.name} has FftSize={channel_fft_size}, expected {fft_size}")

        avg_magnitude, frame_count = _average_fft_file(data_path, fft_size)
        frame_counts.append(frame_count)
        db = 20.0 * np.log10(np.maximum(avg_magnitude, 1e-12))
        peak_index = int(np.argmax(db))
        ax.plot(freqs_mhz, db, linewidth=0.9, label=f"{label} | peak {freqs_mhz[peak_index]:.1f} MHz")
        plotted += 1

    if plotted == 0:
        raise FileNotFoundError(f"No FFT Data_*.bin/Data_*.fft pairs found in {output_dir}")

    frame_summary = ", ".join(str(count) for count in frame_counts)
    ax.set_title(f"FFT Spectrum ({plotted} channels, frames: {frame_summary})")
    ax.set_xlabel("Frequency (MHz)")
    ax.set_ylabel("Magnitude (dB)")
    ax.grid(True, which="both", alpha=0.28)
    ax.legend(loc="best", fontsize=9)
    fig.tight_layout()

    image_path = output_dir / FFT_RESULT_IMAGE_NAME
    fig.savefig(image_path)
    plt.close(fig)

    if open_image:
        os.startfile(image_path)  # type: ignore[attr-defined]
    return image_path


def load_run_record(final_result_path: Path) -> RunRecord:
    folder_path = final_result_path.parent
    folder_name = folder_path.name
    metadata_path = folder_path / "metadata.json"

    record = RunRecord(
        folder_name=folder_name,
        folder_path=folder_path,
        final_result_path=final_result_path,
        movie_path=(folder_path / MOVIE_NAME) if (folder_path / MOVIE_NAME).exists() else None,
        loglog_plot_path=(folder_path / LOGLOG_PLOT_NAME) if (folder_path / LOGLOG_PLOT_NAME).exists() else None,
        diagonal_offset_path=first_existing_path(folder_path, DIAGONAL_OFFSET_PLOT_NAMES),
        raw_std_plot_path=first_existing_path(folder_path, RAW_STD_PLOT_NAMES),
        metadata_path=metadata_path if metadata_path.exists() else None,
        sortable_date=parse_folder_datetime(folder_name, folder_path),
    )

    if record.metadata_path and record.metadata_path.exists():
        try:
            record.metadata_text = record.metadata_path.read_text(encoding="utf-8")
            payload = normalize_metadata(json.loads(record.metadata_text))

            timestamp = payload.get("Timestamp")
            if isinstance(timestamp, str):
                try:
                    record.sortable_date = datetime.fromisoformat(timestamp)
                except ValueError:
                    pass

            record.sample = safe_text(payload.get("Sample"))
            record.exp_tag = safe_text(
                first_matching_value(
                    payload,
                    [
                        ("ExperimentTag",),
                        ("ExpTag",),
                        ("Experiment",),
                        ("ExperimentName",),
                        ("Configuration", "ExperimentTag"),
                        ("Configuration", "ExpTag"),
                        ("PhysicsData", "ExperimentTag"),
                        ("PhysicsData", "ExpTag"),
                    ],
                )
            )
            record.description = safe_text(payload.get("Description"))
            record.tags = safe_tags(payload.get("Tags"))
            record.filename = safe_text(payload.get("Filename"))
            record.duration = safe_text(payload.get("Duration"))
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

            physics_value = payload.get("PhysicsData", {}) or {}
            physics = physics_value if isinstance(physics_value, dict) else {}
            record.physics = PhysicsData(
                sample_power_mw=first_matching_float(
                    payload,
                    [
                        ("OnSamplePower_mW",),
                        ("PhysicsData", "OnSamplePower_mW"),
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
                environment_temperature_k=first_matching_float(
                    payload,
                    [
                        ("PhysicsData", "Temperature_K"),
                        ("EnvironmentTemperature_K",),
                        ("EnvironmentTemperatureK",),
                        ("Temperature_K",),
                        ("TemperatureK",),
                        ("PhysicsData", "EnvironmentTemperature_K"),
                        ("PhysicsData", "EnvironmentTemperatureK"),
                        ("Environment", "Temperature_K"),
                        ("Environment", "TemperatureK"),
                    ],
                ),
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
                shot_noise_urad2_rthz=first_matching_float(
                    payload,
                    [
                        ("PhysicsData", "ShotNoiseResult_urad2_rtHz"),
                        ("ShotNoiseResult_urad2_rtHz",),
                    ],
                ),
                shot_noise_v2_rthz=first_matching_float(
                    payload,
                    [
                        ("PhysicsData", "ShotNoiseResult_V2_rtHz"),
                        ("ShotNoiseResult_V2_rtHz",),
                    ],
                ),
                shot_noise_unit=safe_text(
                    first_matching_value(
                        payload,
                        [
                            ("PhysicsData", "DisplayAmplitudeUnit"),
                            ("DisplayAmplitudeUnit",),
                        ],
                    )
                ),
                is_dark_noise_run=safe_bool(
                    first_matching_value(
                        payload,
                        [
                            ("PhysicsData", "IsDarkNoiseRun"),
                            ("IsDarkNoiseRun",),
                        ],
                    )
                ),
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
        record.exp_tag,
        record.description,
        record.tags_display,
        record.filename,
        record.final_result_path.name,
        record.sample_power_display,
        record.port_power_display,
        record.environment_temperature_display_k,
        record.shot_noise_display,
        "star" if record.star_measurement else "",
    ]
    record.search_blob = " ".join(part for part in search_parts if part).lower()
    return record


def scan_runs(root_path: Path) -> list[RunRecord]:
    final_result_paths = [path for path in root_path.rglob(FINAL_RESULT_NAME) if path.is_file()]
    if not final_result_paths:
        return []

    max_workers = min(12, max(2, (os.cpu_count() or 4)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        runs = list(executor.map(load_run_record, final_result_paths))

    runs.sort(key=lambda run: run.sortable_date, reverse=True)
    return runs


def root_db_key(root_path: Path) -> str:
    return str(root_path.expanduser().resolve()).lower()


def ensure_index_db() -> None:
    with sqlite3.connect(INDEX_DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                root_key TEXT NOT NULL,
                folder_path TEXT NOT NULL,
                folder_name TEXT NOT NULL,
                final_result_path TEXT NOT NULL,
                movie_path TEXT,
                loglog_plot_path TEXT,
                diagonal_offset_path TEXT,
                raw_std_plot_path TEXT,
                metadata_path TEXT,
                sortable_date TEXT NOT NULL,
                sample TEXT NOT NULL,
                exp_tag TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL,
                tags_json TEXT NOT NULL,
                filename TEXT NOT NULL,
                duration TEXT NOT NULL,
                star_measurement INTEGER NOT NULL,
                sample_power_mw REAL,
                power_mw_1 REAL,
                power_mw_2 REAL,
                environment_temperature_k REAL,
                environment_temperature_c REAL,
                sensitivity_v_photon REAL,
                shot_noise_urad2_rthz REAL,
                shot_noise_v2_rthz REAL,
                shot_noise_unit TEXT NOT NULL DEFAULT '',
                is_dark_noise_run INTEGER NOT NULL DEFAULT 0,
                scan_range_mm REAL,
                scan_min_mm REAL,
                scan_max_mm REAL,
                metadata_text TEXT NOT NULL,
                search_blob TEXT NOT NULL,
                PRIMARY KEY (root_key, folder_path)
            )
            """
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(runs)").fetchall()}
        if "exp_tag" not in columns:
            conn.execute("ALTER TABLE runs ADD COLUMN exp_tag TEXT NOT NULL DEFAULT ''")
        if "shot_noise_v2_rthz" not in columns:
            conn.execute("ALTER TABLE runs ADD COLUMN shot_noise_v2_rthz REAL")
        if "shot_noise_unit" not in columns:
            conn.execute("ALTER TABLE runs ADD COLUMN shot_noise_unit TEXT NOT NULL DEFAULT ''")
        if "is_dark_noise_run" not in columns:
            conn.execute("ALTER TABLE runs ADD COLUMN is_dark_noise_run INTEGER NOT NULL DEFAULT 0")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_root_date ON runs(root_key, sortable_date DESC)")
        conn.execute("CREATE TABLE IF NOT EXISTS roots (root_key TEXT PRIMARY KEY, root_path TEXT NOT NULL, last_indexed_utc TEXT NOT NULL, run_count INTEGER NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        schema_row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        current_schema = int(schema_row[0]) if schema_row and str(schema_row[0]).isdigit() else 0
        if current_schema < INDEX_SCHEMA_VERSION:
            conn.execute("DELETE FROM runs")
            conn.execute("DELETE FROM roots")
            conn.execute(
                "INSERT INTO meta(key, value) VALUES ('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(INDEX_SCHEMA_VERSION),),
            )


def _serialize_path(path: Path | None) -> str | None:
    return None if path is None else str(path)


def _deserialize_path(value: str | None) -> Path | None:
    return None if not value else Path(value)


def upsert_run_record_in_db(root_path: Path, record: RunRecord) -> None:
    ensure_index_db()
    db_key = root_db_key(root_path)
    with sqlite3.connect(INDEX_DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO runs (
                root_key, folder_path, folder_name, final_result_path, movie_path, loglog_plot_path,
                diagonal_offset_path, raw_std_plot_path, metadata_path, sortable_date, sample,
                exp_tag, description, tags_json, filename, duration, star_measurement, sample_power_mw,
                power_mw_1, power_mw_2, environment_temperature_k, environment_temperature_c,
                sensitivity_v_photon, shot_noise_urad2_rthz, shot_noise_v2_rthz, shot_noise_unit,
                is_dark_noise_run, scan_range_mm, scan_min_mm, scan_max_mm, metadata_text, search_blob
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(root_key, folder_path) DO UPDATE SET
                folder_name=excluded.folder_name,
                final_result_path=excluded.final_result_path,
                movie_path=excluded.movie_path,
                loglog_plot_path=excluded.loglog_plot_path,
                diagonal_offset_path=excluded.diagonal_offset_path,
                raw_std_plot_path=excluded.raw_std_plot_path,
                metadata_path=excluded.metadata_path,
                sortable_date=excluded.sortable_date,
                sample=excluded.sample,
                exp_tag=excluded.exp_tag,
                description=excluded.description,
                tags_json=excluded.tags_json,
                filename=excluded.filename,
                duration=excluded.duration,
                star_measurement=excluded.star_measurement,
                sample_power_mw=excluded.sample_power_mw,
                power_mw_1=excluded.power_mw_1,
                power_mw_2=excluded.power_mw_2,
                environment_temperature_k=excluded.environment_temperature_k,
                environment_temperature_c=excluded.environment_temperature_c,
                sensitivity_v_photon=excluded.sensitivity_v_photon,
                shot_noise_urad2_rthz=excluded.shot_noise_urad2_rthz,
                shot_noise_v2_rthz=excluded.shot_noise_v2_rthz,
                shot_noise_unit=excluded.shot_noise_unit,
                is_dark_noise_run=excluded.is_dark_noise_run,
                scan_range_mm=excluded.scan_range_mm,
                scan_min_mm=excluded.scan_min_mm,
                scan_max_mm=excluded.scan_max_mm,
                metadata_text=excluded.metadata_text,
                search_blob=excluded.search_blob
            """,
            (
                db_key,
                str(record.folder_path),
                record.folder_name,
                str(record.final_result_path),
                _serialize_path(record.movie_path),
                _serialize_path(record.loglog_plot_path),
                _serialize_path(record.diagonal_offset_path),
                _serialize_path(record.raw_std_plot_path),
                _serialize_path(record.metadata_path),
                record.sortable_date.isoformat(),
                record.sample,
                record.exp_tag,
                record.description,
                json.dumps(record.tags),
                record.filename,
                record.duration,
                1 if record.star_measurement else 0,
                record.physics.sample_power_mw,
                record.physics.power_mw_1,
                record.physics.power_mw_2,
                record.physics.environment_temperature_k,
                record.physics.environment_temperature_c,
                record.physics.sensitivity_v_photon,
                record.physics.shot_noise_urad2_rthz,
                record.physics.shot_noise_v2_rthz,
                record.physics.shot_noise_unit,
                1 if record.physics.is_dark_noise_run else 0,
                record.physics.scan_range_mm,
                record.physics.scan_min_mm,
                record.physics.scan_max_mm,
                record.metadata_text,
                record.search_blob,
            ),
        )


def write_runs_to_db(root_path: Path, runs: list[RunRecord]) -> None:
    ensure_index_db()
    db_key = root_db_key(root_path)
    with sqlite3.connect(INDEX_DB_PATH) as conn:
        conn.execute("DELETE FROM runs WHERE root_key = ?", (db_key,))
        conn.executemany(
            """
            INSERT INTO runs (
                root_key, folder_path, folder_name, final_result_path, movie_path, loglog_plot_path,
                diagonal_offset_path, raw_std_plot_path, metadata_path, sortable_date, sample,
                exp_tag, description, tags_json, filename, duration, star_measurement, sample_power_mw,
                power_mw_1, power_mw_2, environment_temperature_k, environment_temperature_c,
                sensitivity_v_photon, shot_noise_urad2_rthz, shot_noise_v2_rthz, shot_noise_unit,
                is_dark_noise_run, scan_range_mm, scan_min_mm, scan_max_mm, metadata_text, search_blob
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    db_key,
                    str(run.folder_path),
                    run.folder_name,
                    str(run.final_result_path),
                    _serialize_path(run.movie_path),
                    _serialize_path(run.loglog_plot_path),
                    _serialize_path(run.diagonal_offset_path),
                    _serialize_path(run.raw_std_plot_path),
                    _serialize_path(run.metadata_path),
                    run.sortable_date.isoformat(),
                    run.sample,
                    run.exp_tag,
                    run.description,
                    json.dumps(run.tags),
                    run.filename,
                    run.duration,
                    1 if run.star_measurement else 0,
                    run.physics.sample_power_mw,
                    run.physics.power_mw_1,
                    run.physics.power_mw_2,
                    run.physics.environment_temperature_k,
                    run.physics.environment_temperature_c,
                    run.physics.sensitivity_v_photon,
                    run.physics.shot_noise_urad2_rthz,
                    run.physics.shot_noise_v2_rthz,
                    run.physics.shot_noise_unit,
                    1 if run.physics.is_dark_noise_run else 0,
                    run.physics.scan_range_mm,
                    run.physics.scan_min_mm,
                    run.physics.scan_max_mm,
                    run.metadata_text,
                    run.search_blob,
                )
                for run in runs
            ],
        )
        conn.execute(
            """
            INSERT INTO roots(root_key, root_path, last_indexed_utc, run_count)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(root_key) DO UPDATE SET
                root_path=excluded.root_path,
                last_indexed_utc=excluded.last_indexed_utc,
                run_count=excluded.run_count
            """,
            (db_key, str(root_path), datetime.utcnow().isoformat(), len(runs)),
        )


def _latest_index_source_state(root_path: Path) -> tuple[int, float]:
    run_count = 0
    newest_mtime = 0.0
    for final_result_path in root_path.rglob(FINAL_RESULT_NAME):
        if not final_result_path.is_file():
            continue
        run_count += 1
        try:
            newest_mtime = max(newest_mtime, final_result_path.stat().st_mtime)
        except OSError:
            pass
        metadata_path = final_result_path.parent / "metadata.json"
        if metadata_path.is_file():
            try:
                newest_mtime = max(newest_mtime, metadata_path.stat().st_mtime)
            except OSError:
                pass
    return run_count, newest_mtime


def is_index_stale(root_path: Path) -> bool:
    ensure_index_db()
    db_key = root_db_key(root_path)
    with sqlite3.connect(INDEX_DB_PATH) as conn:
        row = conn.execute(
            "SELECT last_indexed_utc, run_count FROM roots WHERE root_key = ?",
            (db_key,),
        ).fetchone()
    if row is None:
        return True

    source_count, newest_mtime = _latest_index_source_state(root_path)
    if source_count != int(row[1]):
        return True
    if newest_mtime <= 0:
        return False

    try:
        last_indexed = datetime.fromisoformat(str(row[0]))
    except ValueError:
        return True
    newest_source = datetime.utcfromtimestamp(newest_mtime)
    return newest_source > last_indexed


def load_runs_from_db(root_path: Path) -> list[RunRecord]:
    ensure_index_db()
    db_key = root_db_key(root_path)
    with sqlite3.connect(INDEX_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM runs WHERE root_key = ? ORDER BY sortable_date DESC",
            (db_key,),
        ).fetchall()

    runs: list[RunRecord] = []
    for row in rows:
        runs.append(
            RunRecord(
                folder_name=row["folder_name"],
                folder_path=Path(row["folder_path"]),
                final_result_path=Path(row["final_result_path"]),
                movie_path=_deserialize_path(row["movie_path"]),
                loglog_plot_path=_deserialize_path(row["loglog_plot_path"]),
                diagonal_offset_path=_deserialize_path(row["diagonal_offset_path"]),
                raw_std_plot_path=_deserialize_path(row["raw_std_plot_path"]),
                metadata_path=_deserialize_path(row["metadata_path"]),
                sortable_date=datetime.fromisoformat(row["sortable_date"]),
                sample=row["sample"],
                exp_tag=row["exp_tag"],
                description=row["description"],
                tags=[str(tag) for tag in json.loads(row["tags_json"] or "[]") if tag],
                filename=row["filename"],
                duration=row["duration"],
                star_measurement=bool(row["star_measurement"]),
                physics=PhysicsData(
                    sample_power_mw=row["sample_power_mw"],
                    power_mw_1=row["power_mw_1"],
                    power_mw_2=row["power_mw_2"],
                    environment_temperature_k=row["environment_temperature_k"],
                    environment_temperature_c=row["environment_temperature_c"],
                    sensitivity_v_photon=row["sensitivity_v_photon"],
                    shot_noise_urad2_rthz=row["shot_noise_urad2_rthz"],
                    shot_noise_v2_rthz=row["shot_noise_v2_rthz"],
                    shot_noise_unit=row["shot_noise_unit"],
                    is_dark_noise_run=bool(row["is_dark_noise_run"]),
                    scan_range_mm=row["scan_range_mm"],
                    scan_min_mm=row["scan_min_mm"],
                    scan_max_mm=row["scan_max_mm"],
                ),
                metadata_text=row["metadata_text"],
                search_blob=row["search_blob"],
            )
        )
    return runs


def configured_root_path() -> Path:
    try:
        if CONFIG_PATH.exists():
            payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            root_value = payload.get("root_path")
            if isinstance(root_value, str) and root_value.strip():
                return Path(root_value)
    except Exception:
        pass
    return ROOT_DEFAULT


def infer_index_root_for_run(run_folder: Path) -> Path:
    configured_root = configured_root_path()
    try:
        run_folder.resolve().relative_to(configured_root.resolve())
        return configured_root
    except Exception:
        return run_folder.parent


def index_run_folder(run_folder: Path, root_path: Path | None = None) -> RunRecord:
    run_folder = run_folder.expanduser().resolve()
    root_path = (root_path or infer_index_root_for_run(run_folder)).expanduser().resolve()
    final_result_path = run_folder / FINAL_RESULT_NAME
    if not final_result_path.is_file():
        raise FileNotFoundError(f"Cannot index run because {FINAL_RESULT_NAME} was not found: {final_result_path}")

    record = load_run_record(final_result_path)
    upsert_run_record_in_db(root_path, record)
    return record


class DataFilesBrowser(tk.Tk):
    TABLE_COLUMNS = ("star", "date", "sample", "exp_tag", "power", "sample_power", "temp", "duration", "shot_noise", "range", "run")

    COLUMN_TITLES = {
        "star": "Star",
        "date": "Date",
        "run": "Run Folder",
        "sample": "Sample",
        "exp_tag": "Exp Tag",
        "power": "Port Power (mW)",
        "sample_power": "Sample Power (mW)",
        "temp": "Temp (K)",
        "duration": "Elapsed",
        "shot_noise": "Shot Noise (urad^2/rtHz)",
        "range": "Range (mm)",
    }

    COLUMN_WIDTHS = {
        "star": 62,
        "date": 150,
        "run": 180,
        "sample": 170,
        "exp_tag": 150,
        "power": 140,
        "sample_power": 155,
        "temp": 90,
        "duration": 92,
        "shot_noise": 170,
        "range": 105,
    }

    COLUMN_MIN_WIDTHS = {
        "star": 50,
        "date": 130,
        "run": 130,
        "sample": 90,
        "exp_tag": 110,
        "power": 115,
        "sample_power": 135,
        "temp": 75,
        "duration": 78,
        "shot_noise": 135,
        "range": 90,
    }

    def _load_config(self) -> dict[str, object]:
        try:
            if CONFIG_PATH.exists():
                return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _apply_loaded_config(self) -> None:
        config = self.config_data
        root_value = config.get("root_path")
        if isinstance(root_value, str) and root_value.strip():
            self.root_var.set(root_value)

        geometry = config.get("geometry")
        if isinstance(geometry, str) and geometry:
            self.geometry(geometry)

        filters_expanded = config.get("filters_expanded")
        if isinstance(filters_expanded, bool):
            self.filters_expanded = filters_expanded

        banner_visible = config.get("banner_visible")
        if isinstance(banner_visible, bool):
            self.banner_visible = banner_visible

        table_visible = config.get("table_visible")
        if isinstance(table_visible, bool):
            self.table_visible = table_visible

        column_order = config.get("column_order")
        if isinstance(column_order, list):
            cleaned_order = [str(column) for column in column_order if str(column) in self.COLUMN_TITLES]
            if cleaned_order:
                missing = [column for column in self.COLUMN_TITLES if column not in cleaned_order]
                self.column_order = cleaned_order + missing

        visible_columns = config.get("visible_columns")
        if isinstance(visible_columns, list):
            cleaned_visible = {str(column) for column in visible_columns if str(column) in self.COLUMN_TITLES}
            if cleaned_visible:
                self.visible_columns = cleaned_visible
        self.visible_columns.add("exp_tag")

    def save_config(self) -> None:
        try:
            payload = {
                "root_path": self.root_var.get().strip(),
                "geometry": self.geometry(),
                "filters_expanded": self.filters_expanded,
                "banner_visible": self.banner_visible,
                "table_visible": self.table_visible,
                "column_order": self.column_order,
                "visible_columns": sorted(self.visible_columns),
            }
            CONFIG_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            pass

    def __init__(self) -> None:
        super().__init__()
        self.title("DataFiles Browser")
        self.geometry("1500x900")
        self.minsize(1200, 720)
        self.configure(bg="#f3f1ea")

        self.all_runs: list[RunRecord] = []
        self.filtered_runs: list[RunRecord] = []
        self.preview_images: dict[tk.Label, object] = {}
        self._preview_source_cache: dict[str, object] = {}
        self._preview_photo_cache: dict[tuple[str, int, int], object] = {}
        self._preview_resize_job: str | None = None
        self._filter_job: str | None = None
        self._scan_thread: threading.Thread | None = None
        self._scan_request_id = 0
        self.analysis_thread: threading.Thread | None = None
        self.sort_column = "date"
        self.sort_descending = True
        self.active_run: RunRecord | None = None
        self.filters_expanded = True
        self.banner_visible = True
        self.table_visible = True
        self.run_by_iid: dict[str, RunRecord] = {}
        self.column_order = list(self.TABLE_COLUMNS)
        self.visible_columns = {"star", "date", "sample", "exp_tag", "power", "sample_power", "temp", "duration", "shot_noise", "range"}

        self.root_var = tk.StringVar(value=str(ROOT_DEFAULT))
        self.search_var = tk.StringVar()
        self.scan_range_min_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready.")
        self.count_var = tk.StringVar(value="0 runs")
        self._current_root_path = Path(self.root_var.get())
        self.config_data = self._load_config()
        self._apply_loaded_config()

        self._build_ui()
        self.bind("<Configure>", self._on_window_configure)
        self.refresh_runs()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self.header_frame = tk.Frame(self, bg="#12353c", padx=16, pady=16)
        self.header_frame.grid(row=0, column=0, sticky="nsew", padx=16, pady=(16, 8))
        self.header_frame.columnconfigure(0, weight=1)

        tk.Label(
            self.header_frame,
            text="Quantum DataFiles Browser",
            bg="#12353c",
            fg="white",
            font=("Segoe UI", 20, "bold"),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            self.header_frame,
            text="Fast search over runs with final_clean_result preview, metadata, and one-click open actions.",
            bg="#12353c",
            fg="#d7e8ea",
            font=("Segoe UI", 10),
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        controls = tk.Frame(self.header_frame, bg="#12353c")
        controls.grid(row=0, column=1, rowspan=2, sticky="e")
        tk.Label(controls, text="Root:", bg="#12353c", fg="#d7e8ea").pack(side="left", padx=(0, 8))
        tk.Entry(controls, textvariable=self.root_var, width=48).pack(side="left")
        tk.Button(controls, text="Refresh", width=12, command=self.refresh_runs).pack(side="left", padx=(10, 0))
        tk.Button(controls, text="Rebuild Index", width=12, command=self.rebuild_index).pack(side="left", padx=(8, 0))
        self.banner_toggle_button = tk.Button(controls, text="Hide Banner", width=12, command=self.toggle_banner)
        self.banner_toggle_button.pack(side="left", padx=(8, 0))

        self.body_pane = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=8, bg="#f3f1ea")
        self.body_pane.grid(row=1, column=0, sticky="nsew", padx=16, pady=8)

        self.left_panel = tk.Frame(self.body_pane, bg="#f3f1ea")
        self.right_panel = tk.Frame(self.body_pane, bg="#f3f1ea")
        self.body_pane.add(self.left_panel, stretch="always", minsize=520)
        self.body_pane.add(self.right_panel, stretch="always", minsize=600)

        self.left_panel.columnconfigure(0, weight=1)
        self.left_panel.rowconfigure(1, weight=1)

        search_box = tk.Frame(self.left_panel, bg="white", padx=12, pady=12, highlightthickness=1, highlightbackground="#d8e0e1")
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
        self.search_var.trace_add("write", lambda *_: self._schedule_filter())
        self.scan_filter_row = tk.Frame(search_box, bg="white")
        self.scan_filter_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        tk.Label(self.scan_filter_row, text="Scan range >=", bg="white", fg="#12353c").pack(side="left")
        tk.Entry(self.scan_filter_row, textvariable=self.scan_range_min_var, width=10).pack(side="left", padx=(8, 4))
        tk.Label(self.scan_filter_row, text="mm", bg="white", fg="#62777c").pack(side="left")
        self.scan_range_min_var.trace_add("write", lambda *_: self._schedule_filter())
        tk.Button(self.scan_filter_row, text="Columns...", command=self.open_column_manager).pack(side="right")
        self.top_table_toggle_button = tk.Button(
            self.scan_filter_row,
            text="Hide Table",
            width=12,
            command=self.toggle_table,
        )
        self.top_table_toggle_button.pack(side="right", padx=(0, 8))
        tk.Label(
            self.scan_filter_row,
            text="Shot Noise column: numeric value; optical unit urad^2/rtHz, dark unit V^2/rtHz",
            bg="white",
            fg="#62777c",
        ).pack(side="right", padx=(0, 12))
        tk.Label(search_box, textvariable=self.count_var, bg="white", fg="#62777c").grid(row=1, column=1, rowspan=2, sticky="ne", padx=(12, 0))

        table_wrap = tk.Frame(self.left_panel, bg="white", highlightthickness=1, highlightbackground="#d8e0e1")
        table_wrap.grid(row=1, column=0, sticky="nsew")
        table_wrap.rowconfigure(0, weight=1)
        table_wrap.columnconfigure(0, weight=1)

        columns = self.TABLE_COLUMNS
        self.tree = ttk.Treeview(table_wrap, columns=columns, show="headings", height=24)
        for key in columns:
            self.tree.heading(key, text=self.COLUMN_TITLES[key], command=lambda column=key: self.sort_by_column(column))
            self.tree.column(key, width=self.COLUMN_WIDTHS[key], minwidth=self.COLUMN_MIN_WIDTHS[key], anchor="w", stretch=False)
        self._apply_display_columns()
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self.on_select_run)
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<Button-3>", self.on_tree_right_click)

        self.tree_menu = tk.Menu(self, tearoff=0)
        self.tree_menu.add_command(label="Toggle Star", command=self.toggle_star_from_menu)
        self.tree_menu.add_command(label="Edit Metadata", command=self.edit_metadata)
        self.tree_menu.add_command(label="Normalize Metadata", command=self.normalize_selected_metadata)
        self.tree_menu.add_command(label="Open Folder", command=self.open_selected_folder)
        self.tree_menu.add_command(label="Open Image", command=self.open_selected_image)
        self.tree_menu.add_command(label="Open MP4", command=self.open_selected_mp4)

        scrollbar = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        xscrollbar = ttk.Scrollbar(table_wrap, orient="horizontal", command=self.tree.xview)
        xscrollbar.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.configure(xscrollcommand=xscrollbar.set)

        self.right_panel.columnconfigure(0, weight=1)
        self.right_panel.rowconfigure(1, weight=1)

        selected_header = tk.Frame(self.right_panel, bg="white", padx=14, pady=14, highlightthickness=1, highlightbackground="#d8e0e1")
        selected_header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        selected_header.columnconfigure(0, weight=1)
        tk.Label(selected_header, text="Selected Run", bg="white", fg="#12353c", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        self.selected_title = tk.Label(selected_header, text="Nothing selected", bg="white", font=("Segoe UI", 16, "bold"))
        self.selected_title.grid(row=1, column=0, sticky="w", pady=(6, 0))
        action_frame = tk.Frame(selected_header, bg="white")
        action_frame.grid(row=0, column=1, rowspan=2, sticky="e")
        self.show_banner_button = tk.Button(action_frame, text="Show Banner", width=12, command=self.toggle_banner)
        self.show_banner_button.pack(side="left", padx=(0, 8))
        self.table_toggle_button = tk.Button(action_frame, text="Hide Table", width=12, command=self.toggle_table)
        self.table_toggle_button.pack(side="left", padx=(0, 8))
        tk.Button(action_frame, text="Edit Metadata", width=12, command=self.edit_metadata).pack(side="left", padx=(0, 8))
        tk.Button(action_frame, text="Normalize", width=12, command=self.normalize_selected_metadata).pack(side="left", padx=(0, 8))
        tk.Button(action_frame, text="Open Folder", width=12, command=self.open_selected_folder).pack(side="left", padx=(0, 8))
        tk.Button(action_frame, text="Show FFT", width=12, command=self.show_latest_fft_result).pack(side="left", padx=(0, 8))
        tk.Button(action_frame, text="Rerun", width=12, command=self.rerun_selected_analysis).pack(side="left")

        content = tk.Frame(self.right_panel, bg="#f3f1ea")
        content.grid(row=1, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)
        content.rowconfigure(1, weight=1)

        self.preview_label = self._build_preview_card(
            content,
            row=0,
            column=0,
            title="Final Result",
            open_handler=lambda: self.open_selected_image(),
        )
        self.loglog_preview_label = self._build_preview_card(
            content,
            row=0,
            column=1,
            title="Log-Log Eval",
            open_handler=lambda: self.open_selected_asset("loglog_plot_path", "loglog_eval.png"),
        )
        self.diagonal_preview_label = self._build_preview_card(
            content,
            row=1,
            column=0,
            title="Diagonal Offset",
            open_handler=lambda: self.open_selected_asset(
                "diagonal_offset_path",
                "diagonal_offset_matrix_urad2.png or diagonal_offset_matrix_V2.png",
            ),
        )
        self.std_preview_label = self._build_preview_card(
            content,
            row=1,
            column=1,
            title="Raw Std Over Time",
            open_handler=lambda: self.open_selected_asset(
                "raw_std_plot_path",
                "raw_std_over_time.png or raw_std_within_parity.png",
            ),
        )

        status = tk.Label(self, textvariable=self.status_var, bg="#f3f1ea", fg="#5a6e73", anchor="w")
        status.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 12))

        if not self.filters_expanded:
            self.search_entry.grid_remove()
            self.scan_filter_row.grid_remove()
            self.filter_toggle_button.configure(text="Show Filters")

        self._apply_layout_visibility()

    def refresh_runs(self) -> None:
        self.save_config()
        root_path = Path(self.root_var.get().strip())
        if not root_path.exists():
            messagebox.showwarning("Missing Folder", f"Folder not found:\n{root_path}")
            return

        self._current_root_path = root_path
        self.status_var.set("Loading runs from index...")
        self.update_idletasks()
        try:
            runs = load_runs_from_db(root_path)
        except Exception as exc:
            messagebox.showerror("Index Error", str(exc))
            self.status_var.set("Index load failed.")
            return

        if runs:
            try:
                stale = is_index_stale(root_path)
            except Exception:
                stale = True
            if stale:
                self.status_var.set("Index is older than the DataFiles folder. Rebuilding...")
                self.rebuild_index()
                return
            self.all_runs = runs
            self._schedule_filter(immediate=True)
            self.status_var.set(f"Loaded {len(runs)} runs from the SQLite index.")
            return

        self.status_var.set("No index found for this root. Building index...")
        self.rebuild_index()

    def rebuild_index(self) -> None:
        self.save_config()
        root_path = Path(self.root_var.get().strip())
        if not root_path.exists():
            messagebox.showwarning("Missing Folder", f"Folder not found:\n{root_path}")
            return

        self._current_root_path = root_path
        self._scan_request_id += 1
        request_id = self._scan_request_id
        self.status_var.set("Rebuilding SQLite index...")
        self.update_idletasks()

        def worker() -> None:
            try:
                runs = scan_runs(root_path)
                write_runs_to_db(root_path, runs)
                self.after(0, lambda: self._finish_refresh_runs(request_id, runs, None))
            except Exception as exc:
                self.after(0, lambda: self._finish_refresh_runs(request_id, None, exc))

        self._scan_thread = threading.Thread(target=worker, daemon=True)
        self._scan_thread.start()

    def _finish_refresh_runs(
        self,
        request_id: int,
        runs: list[RunRecord] | None,
        error: Exception | None,
    ) -> None:
        if request_id != self._scan_request_id:
            return

        if error is not None:
            messagebox.showerror("Index Error", str(error))
            self.status_var.set("Index build failed.")
            return

        self.all_runs = runs or []
        self._schedule_filter(immediate=True)
        self.status_var.set(f"Indexed {len(self.all_runs)} runs and loaded them from SQLite.")

    def _schedule_filter(self, immediate: bool = False) -> None:
        if self._filter_job is not None:
            self.after_cancel(self._filter_job)
            self._filter_job = None
        if immediate:
            self.apply_filter()
            return
        self._filter_job = self.after(FILTER_DEBOUNCE_MS, self.apply_filter)

    def apply_filter(self) -> None:
        self._filter_job = None
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
            row_values = {
                "star": "[x]" if run.star_measurement else "[ ]",
                "date": run.sortable_date.strftime("%Y-%m-%d %H:%M"),
                "sample": run.sample or "-",
                "exp_tag": run.exp_tag or "-",
                "power": run.port_power_display,
                "sample_power": run.sample_power_display,
                "temp": run.environment_temperature_display_k,
                "duration": run.duration or "-",
                "shot_noise": run.shot_noise_value_display,
                "range": run.scan_range_display,
                "run": run.folder_name,
            }
            self.tree.insert(
                "",
                "end",
                iid=iid,
                values=tuple(row_values[column] for column in self.TABLE_COLUMNS),
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
        if column == "exp_tag":
            return (0, run.exp_tag.lower())
        if column == "power":
            values = [value for value in (run.physics.power_mw_1, run.physics.power_mw_2) if value is not None]
            value = sum(values) / len(values) if values else None
            return (1 if value is None else 0, value if value is not None else 0.0)
        if column == "sample_power":
            value = run.physics.sample_power_mw
            return (1 if value is None else 0, value if value is not None else 0.0)
        if column == "temp":
            value = run.physics.environment_temperature_k
            if value is None and run.physics.environment_temperature_c is not None:
                value = run.physics.environment_temperature_c + 273.15
            return (1 if value is None else 0, value if value is not None else 0.0)
        if column == "duration":
            return (0, run.duration.lower())
        if column == "shot_noise":
            value = run.physics.shot_noise_urad2_rthz
            if value is None:
                value = run.physics.shot_noise_v2_rthz
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
        self.update_idletasks()
        self._set_image_preview(
            self.preview_label,
            run.final_result_path,
            self._preview_max_size(self.preview_label),
            "No final_clean_result.png found.",
        )
        self._set_image_preview(
            self.loglog_preview_label,
            run.loglog_plot_path,
            self._preview_max_size(self.loglog_preview_label),
            "No loglog_eval.png found.\nRerun analysis for this run.",
        )
        self._set_image_preview(
            self.diagonal_preview_label,
            run.diagonal_offset_path,
            self._preview_max_size(self.diagonal_preview_label),
            "No diagonal offset plot found.\nExpected diagonal_offset_matrix_urad2.png or diagonal_offset_matrix_V2.png.",
        )
        self._set_image_preview(
            self.std_preview_label,
            run.raw_std_plot_path,
            self._preview_max_size(self.std_preview_label),
            "No raw std plot found.\nExpected raw_std_over_time.png or raw_std_within_parity.png.",
        )

    def clear_selection(self) -> None:
        self.active_run = None
        self.selected_title.configure(text="Nothing selected")
        self._clear_preview_label(self.preview_label, "Select a run to preview the final result.")
        self._clear_preview_label(self.loglog_preview_label, "Select a run to preview the log-log evaluation.")
        self._clear_preview_label(self.diagonal_preview_label, "Select a run to preview the diagonal offset plot.")
        self._clear_preview_label(self.std_preview_label, "Select a run to preview the raw std plot.")
        self.preview_images.clear()

    def _build_preview_card(
        self,
        parent: tk.Widget,
        row: int,
        column: int,
        title: str,
        open_handler: callable,
    ) -> tk.Label:
        card = tk.Frame(parent, bg="white", padx=12, pady=12, highlightthickness=1, highlightbackground="#d8e0e1")
        card.grid(row=row, column=column, sticky="nsew", padx=(0 if column == 0 else 5, 0), pady=(0 if row == 0 else 5, 0))
        card.grid_rowconfigure(1, weight=1)
        card.grid_columnconfigure(0, weight=1)

        tk.Label(card, text=title, bg="white", fg="#12353c", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        label = tk.Label(card, bg="#edf2f2", anchor="center")
        label.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        label.bind("<Double-Button-1>", lambda _event: open_handler())
        return label

    def _clear_preview_label(self, label: tk.Label, text: str) -> None:
        label.configure(image="", text=text)
        label.image = None

    def _preview_max_size(self, label: tk.Label) -> tuple[int, int]:
        width = max(240, label.winfo_width() - 12)
        height = max(180, label.winfo_height() - 12)
        return width, height

    def _on_window_configure(self, _event: tk.Event[tk.Widget]) -> None:
        if self.active_run is None:
            return
        if self._preview_resize_job is not None:
            self.after_cancel(self._preview_resize_job)
        self._preview_resize_job = self.after(PREVIEW_RESIZE_DEBOUNCE_MS, self._refresh_active_previews)

    def _refresh_active_previews(self) -> None:
        self._preview_resize_job = None
        if self.active_run is None:
            return
        self.show_run(self.active_run)

    def _set_image_preview(
        self,
        label: tk.Label,
        image_path: Path | None,
        max_size: tuple[int, int],
        missing_text: str,
    ) -> None:
        if image_path is None or not image_path.exists():
            label.configure(image="", text=missing_text)
            label.image = None
            self.preview_images.pop(label, None)
            return

        try:
            if Image is not None and ImageTk is not None:
                source_key = str(image_path)
                bucketed_size = self._bucket_preview_size(max_size)
                cache_key = (source_key, bucketed_size[0], bucketed_size[1])
                photo = self._preview_photo_cache.get(cache_key)
                if photo is None:
                    source_image = self._preview_source_cache.get(source_key)
                    if source_image is None:
                        with Image.open(image_path) as opened_image:
                            source_image = opened_image.copy()
                        self._preview_source_cache[source_key] = source_image
                    image = source_image.copy()
                    image.thumbnail(bucketed_size)
                    photo = ImageTk.PhotoImage(image)
                    self._preview_photo_cache[cache_key] = photo
                    self._trim_preview_cache()
            else:
                photo = tk.PhotoImage(file=str(image_path))
                max_dim = max(max_size)
                shrink = max(1, (max(photo.width(), photo.height()) // max_dim) + 1)
                photo = photo.subsample(shrink, shrink)

            label.configure(image=photo, text="")
            label.image = photo
            self.preview_images[label] = photo
        except Exception as exc:
            label.configure(image="", text=f"Preview unavailable:\n{exc}")
            label.image = None
            self.preview_images.pop(label, None)

    @staticmethod
    def _bucket_preview_size(max_size: tuple[int, int]) -> tuple[int, int]:
        width = max(PREVIEW_SIZE_BUCKET_PX, ((max_size[0] + PREVIEW_SIZE_BUCKET_PX - 1) // PREVIEW_SIZE_BUCKET_PX) * PREVIEW_SIZE_BUCKET_PX)
        height = max(PREVIEW_SIZE_BUCKET_PX, ((max_size[1] + PREVIEW_SIZE_BUCKET_PX - 1) // PREVIEW_SIZE_BUCKET_PX) * PREVIEW_SIZE_BUCKET_PX)
        return width, height

    def _trim_preview_cache(self) -> None:
        while len(self._preview_photo_cache) > PREVIEW_CACHE_LIMIT:
            oldest_key = next(iter(self._preview_photo_cache))
            del self._preview_photo_cache[oldest_key]

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

    def _load_or_create_metadata_payload(self, run: RunRecord) -> dict[str, object]:
        if run.metadata_path and run.metadata_path.exists():
            payload = json.loads(run.metadata_path.read_text(encoding="utf-8"))
            return normalize_metadata(payload) if isinstance(payload, dict) else {}
        run.metadata_path = run.folder_path / "metadata.json"
        return {}

    def _write_metadata_payload(self, run: RunRecord, payload: dict[str, object]) -> None:
        assert run.metadata_path is not None
        payload = normalize_metadata(payload)
        run.metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        run.metadata_text = json.dumps(payload, indent=2)

    def normalize_selected_metadata(self) -> None:
        run = self._selected_run()
        if run is None:
            return
        try:
            selected_iid = str(run.folder_path)
            payload = self._load_or_create_metadata_payload(run)
            self._write_metadata_payload(run, payload)
            updated_run = load_run_record(run.final_result_path)
            upsert_run_record_in_db(self._current_root_path, updated_run)
            self._replace_run_record(updated_run)
            self._refresh_search_blob(updated_run)
            self.apply_filter()
            if self.tree.exists(selected_iid):
                self.tree.selection_set(selected_iid)
                self.tree.focus(selected_iid)
                self.show_run(updated_run)
            self.status_var.set(f"Normalized metadata for {updated_run.folder_name}.")
        except Exception as exc:
            messagebox.showerror("Normalize Metadata Failed", f"Could not normalize metadata.json:\n{exc}")

    @staticmethod
    def _entry_float_or_none(value: str) -> float | None:
        value = value.strip()
        if not value:
            return None
        return float(value)

    def _replace_run_record(self, updated_run: RunRecord) -> None:
        for index, existing in enumerate(self.all_runs):
            if existing.folder_path == updated_run.folder_path:
                self.all_runs[index] = updated_run
                break
        for index, existing in enumerate(self.filtered_runs):
            if existing.folder_path == updated_run.folder_path:
                self.filtered_runs[index] = updated_run
                break

    def edit_metadata(self) -> None:
        run = self._selected_run()
        if run is None:
            return

        dialog = tk.Toplevel(self)
        dialog.title("Edit Metadata")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(bg="#f3f1ea")
        dialog.minsize(560, 420)

        container = tk.Frame(dialog, bg="#f3f1ea")
        container.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        container.columnconfigure(1, weight=1)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)

        use_voltage_shot_noise = (
            run.physics.shot_noise_v2_rthz is not None
            and (run.physics.is_dark_noise_run or run.physics.shot_noise_unit.strip().lower().startswith("v"))
        )
        shot_noise_value = run.physics.shot_noise_v2_rthz if use_voltage_shot_noise else run.physics.shot_noise_urad2_rthz
        shot_noise_label = "Shot Noise (V^2/rtHz)" if use_voltage_shot_noise else "Shot Noise (urad^2/rtHz)"

        fields: list[tuple[str, str, str]] = [
            ("Sample", "sample", run.sample),
            ("Exp Tag", "exp_tag", run.exp_tag),
            ("Description", "description", run.description),
            ("Tags (comma)", "tags", ", ".join(run.tags)),
            ("Filename", "filename", run.filename),
            ("Duration", "duration", run.duration),
            ("Temp (K)", "temperature_k", "-" if run.physics.environment_temperature_k is None else f"{run.physics.environment_temperature_k:g}"),
            ("Sample Power", "sample_power", "-" if run.physics.sample_power_mw is None else f"{run.physics.sample_power_mw:g}"),
            ("Port Power 1", "power_1", "-" if run.physics.power_mw_1 is None else f"{run.physics.power_mw_1:g}"),
            ("Port Power 2", "power_2", "-" if run.physics.power_mw_2 is None else f"{run.physics.power_mw_2:g}"),
            (shot_noise_label, "shot_noise", "-" if shot_noise_value is None else f"{shot_noise_value:g}"),
            ("Scan Range", "scan_range", "-" if run.physics.scan_range_mm is None else f"{run.physics.scan_range_mm:g}"),
            ("Scan Min", "scan_min", "-" if run.physics.scan_min_mm is None else f"{run.physics.scan_min_mm:g}"),
            ("Scan Max", "scan_max", "-" if run.physics.scan_max_mm is None else f"{run.physics.scan_max_mm:g}"),
        ]

        entry_vars: dict[str, tk.StringVar] = {}
        sample_box: ttk.Combobox | None = None
        for row, (label_text, key, initial_value) in enumerate(fields):
            tk.Label(container, text=label_text, bg="#f3f1ea", fg="#12353c").grid(row=row, column=0, sticky="w", pady=4)
            normalized = "" if initial_value == "-" else initial_value
            entry_vars[key] = tk.StringVar(value=normalized)
            if key == "sample":
                sample_options = sorted({loaded_run.sample for loaded_run in self.all_runs if loaded_run.sample})
                if run.sample and run.sample not in sample_options:
                    sample_options.insert(0, run.sample)
                sample_box = ttk.Combobox(
                    container,
                    textvariable=entry_vars[key],
                    values=sample_options,
                    state="normal",
                )
                sample_box.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=4)
            else:
                tk.Entry(container, textvariable=entry_vars[key]).grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=4)

        if sample_box is not None:
            sample_box.focus_set()
            sample_box.icursor(tk.END)

        star_var = tk.BooleanVar(value=run.star_measurement)
        tk.Checkbutton(
            container,
            text="Star measurement",
            variable=star_var,
            bg="#f3f1ea",
            activebackground="#f3f1ea",
        ).grid(row=len(fields), column=0, columnspan=2, sticky="w", pady=(8, 0))

        def save() -> None:
            try:
                selected_iid = str(run.folder_path)
                payload = self._load_or_create_metadata_payload(run)
                physics = payload.get("PhysicsData")
                if not isinstance(physics, dict):
                    physics = {}
                payload["PhysicsData"] = physics

                payload["Sample"] = entry_vars["sample"].get().strip()
                payload["ExperimentTag"] = entry_vars["exp_tag"].get().strip()
                payload["Description"] = entry_vars["description"].get().strip()
                payload["Tags"] = [tag.strip() for tag in entry_vars["tags"].get().split(",") if tag.strip()]
                payload["Filename"] = entry_vars["filename"].get().strip()
                payload["Duration"] = entry_vars["duration"].get().strip()
                payload["StarMeasurement"] = star_var.get()

                physics["Temperature_K"] = self._entry_float_or_none(entry_vars["temperature_k"].get())
                physics["OnSamplePower_mW"] = self._entry_float_or_none(entry_vars["sample_power"].get())
                physics["Power_mW_1"] = self._entry_float_or_none(entry_vars["power_1"].get())
                physics["Power_mW_2"] = self._entry_float_or_none(entry_vars["power_2"].get())
                if use_voltage_shot_noise:
                    physics["ShotNoiseResult_V2_rtHz"] = self._entry_float_or_none(entry_vars["shot_noise"].get())
                    physics["DisplayAmplitudeUnit"] = "V^2"
                    physics["IsDarkNoiseRun"] = True
                else:
                    physics["ShotNoiseResult_urad2_rtHz"] = self._entry_float_or_none(entry_vars["shot_noise"].get())
                    physics["DisplayAmplitudeUnit"] = physics.get("DisplayAmplitudeUnit") or "urad^2"
                physics["ScanRange_mm"] = self._entry_float_or_none(entry_vars["scan_range"].get())
                physics["ScanMin_mm"] = self._entry_float_or_none(entry_vars["scan_min"].get())
                physics["ScanMax_mm"] = self._entry_float_or_none(entry_vars["scan_max"].get())

                self._write_metadata_payload(run, payload)
                updated_run = load_run_record(run.final_result_path)
                upsert_run_record_in_db(self._current_root_path, updated_run)
                self._replace_run_record(updated_run)
                self._refresh_search_blob(updated_run)
                self.apply_filter()
                if self.tree.exists(selected_iid):
                    self.tree.selection_set(selected_iid)
                    self.tree.focus(selected_iid)
                    self.show_run(updated_run)
                self.status_var.set(f"Updated metadata for {updated_run.folder_name}.")
                self.save_config()
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror("Metadata Update Failed", f"Could not update metadata.json:\n{exc}")

        button_row = tk.Frame(dialog, bg="#f3f1ea")
        button_row.grid(row=1, column=0, sticky="e", padx=12, pady=(0, 12))
        tk.Button(button_row, text="Save", width=10, command=save).pack(side="left", padx=(0, 8))
        tk.Button(button_row, text="Cancel", width=10, command=dialog.destroy).pack(side="left")

    def set_star_measurement(self, run: RunRecord, new_value: bool) -> None:
        try:
            selected_iid = str(run.folder_path)
            payload = self._load_or_create_metadata_payload(run)
            payload["StarMeasurement"] = new_value
            self._write_metadata_payload(run, payload)
            updated_run = load_run_record(run.final_result_path)
            upsert_run_record_in_db(self._current_root_path, updated_run)
            self._replace_run_record(updated_run)
            self._refresh_search_blob(updated_run)
            self.apply_filter()
            if self.tree.exists(selected_iid):
                self.tree.selection_set(selected_iid)
                self.tree.focus(selected_iid)
                self.show_run(updated_run)
            self.status_var.set(f"Updated star flag for {updated_run.folder_name}.")
            self.save_config()
        except Exception as exc:
            messagebox.showerror("Star Update Failed", f"Could not update metadata.json:\n{exc}")

    def _refresh_search_blob(self, run: RunRecord) -> None:
        search_parts = [
            run.folder_name,
            str(run.folder_path),
            run.sample,
            run.exp_tag,
            run.description,
            run.tags_display,
            run.filename,
            run.final_result_path.name,
            run.sample_power_display,
            run.port_power_display,
            run.environment_temperature_display_k,
            run.shot_noise_display,
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
        self.save_config()

    def toggle_banner(self) -> None:
        self.banner_visible = not self.banner_visible
        self._apply_layout_visibility()
        self.save_config()

    def toggle_table(self) -> None:
        self.table_visible = not self.table_visible
        self._apply_layout_visibility()
        self.save_config()

    def _apply_layout_visibility(self) -> None:
        if self.banner_visible:
            self.header_frame.grid()
            self.banner_toggle_button.configure(text="Hide Banner")
            self.show_banner_button.pack_forget()
        else:
            self.header_frame.grid_remove()
            self.banner_toggle_button.configure(text="Show Banner")
            if not self.show_banner_button.winfo_manager():
                self.show_banner_button.pack(side="left", padx=(0, 8), before=self.table_toggle_button)

        panes = self.body_pane.panes()
        left_widget = str(self.left_panel)
        right_widget = str(self.right_panel)
        if self.table_visible:
            self.table_toggle_button.configure(text="Hide Table")
            self.top_table_toggle_button.configure(text="Hide Table")
            if left_widget not in panes:
                self.body_pane.add(self.left_panel, before=self.right_panel, stretch="always", minsize=520)
            if right_widget not in self.body_pane.panes():
                self.body_pane.add(self.right_panel, stretch="always", minsize=600)
        else:
            self.table_toggle_button.configure(text="Show Table")
            self.top_table_toggle_button.configure(text="Show Table")
            if left_widget in panes:
                self.body_pane.forget(self.left_panel)

        self.after_idle(self._refresh_active_previews)

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
            self.save_config()
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

    def on_close(self) -> None:
        self.save_config()
        self.destroy()

    def open_selected_image(self) -> None:
        run = self._selected_run()
        if run is None:
            return
        if run.final_result_path.exists():
            os.startfile(run.final_result_path)  # type: ignore[attr-defined]
        else:
            messagebox.showwarning("Missing Image", f"Could not find:\n{run.final_result_path}")

    def open_selected_asset(self, attr_name: str, expected_name: str) -> None:
        run = self._selected_run()
        if run is None:
            return

        image_path = getattr(run, attr_name, None)
        if isinstance(image_path, Path) and image_path.exists():
            os.startfile(image_path)  # type: ignore[attr-defined]
            return

        messagebox.showwarning("Missing Image", f"Could not find:\n{run.folder_path / expected_name}")

    def open_selected_mp4(self) -> None:
        run = self._selected_run()
        if run is None:
            return
        if run.movie_path and run.movie_path.exists():
            os.startfile(run.movie_path)  # type: ignore[attr-defined]
        else:
            messagebox.showwarning("Missing MP4", f"Could not find:\n{run.folder_path / MOVIE_NAME}")

    def show_latest_fft_result(self) -> None:
        def worker() -> None:
            try:
                image_path = build_fft_spectrum_plot(FFT_DEFAULT_OUTPUT_DIR, open_image=True)
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror("FFT Plot Failed", str(exc)))
                self.after(0, lambda: self.status_var.set("FFT plot failed."))
                return
            self.after(0, lambda: self.status_var.set(f"Opened FFT spectrum: {image_path}"))

        self.status_var.set("Building FFT spectrum from latest FFT output...")
        threading.Thread(target=worker, daemon=True).start()

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
            self.rebuild_index()
            try:
                fft_dir = find_fft_output_dir(FFT_DEFAULT_OUTPUT_DIR)
                if any((fft_dir / f"{stem}.bin").is_file() for _, stem in FFT_CHANNEL_FILES):
                    image_path = build_fft_spectrum_plot(fft_dir, open_image=True)
                    message = f"{message}\n\nFFT spectrum opened:\n{image_path}"
            except Exception:
                pass
            messagebox.showinfo("Analysis Complete", message)
            return

        self.status_var.set("Analysis failed.")
        messagebox.showerror("Analysis Failed", message)


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--show-fft":
        requested_dir = Path(sys.argv[2]) if len(sys.argv) >= 3 else FFT_DEFAULT_OUTPUT_DIR
        try:
            image_path = build_fft_spectrum_plot(requested_dir, open_image=True)
        except Exception as exc:
            print(f"FFT plot failed: {exc}", file=sys.stderr)
            raise SystemExit(1)
        print(f"FFT spectrum saved to {image_path}")
        raise SystemExit(0)

    app = DataFilesBrowser()
    app.mainloop()
