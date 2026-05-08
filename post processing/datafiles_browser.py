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
    from metadata_manager import launch_html_editor, normalize_metadata, safe_tags, safe_text
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

    def launch_html_editor(root: Path, wait: bool = True) -> str:
        raise RuntimeError("metadata_manager.py is required for the HTML metadata editor.")


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


def set_dotted_metadata_value(payload: dict[str, object], dotted_path: str, value: object) -> None:
    parts = [part.strip() for part in dotted_path.split(".") if part.strip()]
    if not parts:
        raise ValueError("Custom field is empty.")

    current = payload
    for part in parts[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    current[parts[-1]] = value


def parse_metadata_value(raw_value: str) -> object:
    value = raw_value.strip()
    if not value:
        return ""
    lower_value = value.lower()
    if lower_value in {"true", "false"}:
        return lower_value == "true"
    if lower_value in {"none", "null"}:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


@dataclass
class PhysicsData:
    sample_power_mw: float | None = None
    power_mw_1: float | None = None
    power_mw_2: float | None = None
    use_opo: bool | None = None
    laser_wavelength_nm: float | None = None
    environment_temperature_k: float | None = None
    environment_temperature_c: float | None = None
    sensitivity_v_photon: float | None = None
    shot_noise_urad2_rthz: float | None = None
    shot_noise_v2_rthz: float | None = None
    shot_noise_unit: str = ""
    is_dark_noise_run: bool = False
    attenuation_factor: float | None = None
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
    def attenuation_factor_display(self) -> str:
        if self.physics.attenuation_factor is None:
            return "-"
        return f"{self.physics.attenuation_factor:g}"

    @property
    def use_opo_display(self) -> str:
        if self.physics.use_opo is None:
            return "-"
        return "Yes" if self.physics.use_opo else "No"

    @property
    def wavelength_display_nm(self) -> str:
        if self.physics.laser_wavelength_nm is None:
            return "-"
        return f"{self.physics.laser_wavelength_nm:g}"

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


def effective_attenuation_factor(payload: dict[str, object]) -> float:
    applied = safe_bool(
        first_matching_value(
            payload,
            [
                ("PhysicsData", "PowerDetectorAttenuatorApplied"),
                ("PowerDetectorAttenuatorApplied",),
            ],
        )
    )
    if not applied:
        return 1.0

    stored_factor = first_matching_float(
        payload,
        [
            ("PhysicsData", "PowerDetectorAttenuatorCorrectionFactor"),
            ("PowerDetectorAttenuatorCorrectionFactor",),
        ],
    )
    if stored_factor is not None and stored_factor > 0:
        return stored_factor

    total_db = first_matching_float(
        payload,
        [
            ("PhysicsData", "PowerDetectorAttenuatorTotal_dB"),
            ("PowerDetectorAttenuatorTotal_dB",),
        ],
    )
    if total_db is None or total_db <= 0:
        total_db = 40.0
    return 10 ** (total_db / 20.0)


def metadata_use_opo(payload: dict[str, object]) -> bool | None:
    value = first_matching_value(
        payload,
        [
            ("PhysicsData", "UseOPO"),
            ("PhysicsData", "UseOpo"),
            ("PhysicsData", "Use_OPO"),
            ("PhysicsData", "UseOPOOption"),
            ("PhysicsData", "OPOEnabled"),
            ("PhysicsData", "OPO"),
            ("Configuration", "UseOPO"),
            ("Configuration", "UseOpo"),
            ("Configuration", "UseOPOOption"),
            ("Configuration", "OPOEnabled"),
            ("UseOPO",),
            ("UseOpo",),
            ("UseOPOOption",),
            ("OPOEnabled",),
            ("OPO",),
        ],
    )
    if value is None:
        return None
    return safe_bool(value)


def metadata_laser_wavelength_nm(payload: dict[str, object]) -> float | None:
    return first_matching_float(
        payload,
        [
            ("PhysicsData", "LaserWavelength_nm"),
            ("PhysicsData", "LaserWavelengthNm"),
            ("PhysicsData", "LaserWavelength"),
            ("PhysicsData", "Wavelength_nm"),
            ("PhysicsData", "WavelengthNm"),
            ("PhysicsData", "Wavelength"),
            ("Configuration", "LaserWavelength_nm"),
            ("Configuration", "LaserWavelengthNm"),
            ("Configuration", "Wavelength_nm"),
            ("LaserWavelength_nm",),
            ("LaserWavelengthNm",),
            ("LaserWavelength",),
            ("Wavelength_nm",),
            ("WavelengthNm",),
            ("Wavelength",),
        ],
    )


def apply_browser_metadata_fields(record: RunRecord, payload: dict[str, object]) -> None:
    record.physics.use_opo = metadata_use_opo(payload)
    record.physics.laser_wavelength_nm = metadata_laser_wavelength_nm(payload)


def first_existing_path(folder_path: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        candidate = folder_path / name
        if candidate.exists():
            return candidate
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
                attenuation_factor=effective_attenuation_factor(payload),
                scan_range_mm=safe_float(physics.get("ScanRange_mm")),
                scan_min_mm=safe_float(physics.get("ScanMin_mm")),
                scan_max_mm=safe_float(physics.get("ScanMax_mm")),
            )
            apply_browser_metadata_fields(record, payload)
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
        record.attenuation_factor_display,
        record.use_opo_display,
        record.wavelength_display_nm,
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
                attenuation_factor REAL,
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
        if "attenuation_factor" not in columns:
            conn.execute("ALTER TABLE runs ADD COLUMN attenuation_factor REAL")
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
                is_dark_noise_run, attenuation_factor, scan_range_mm, scan_min_mm, scan_max_mm,
                metadata_text, search_blob
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                attenuation_factor=excluded.attenuation_factor,
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
                record.physics.attenuation_factor,
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
                is_dark_noise_run, attenuation_factor, scan_range_mm, scan_min_mm, scan_max_mm,
                metadata_text, search_blob
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    run.physics.attenuation_factor,
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
        run = RunRecord(
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
                attenuation_factor=row["attenuation_factor"],
                scan_range_mm=row["scan_range_mm"],
                scan_min_mm=row["scan_min_mm"],
                scan_max_mm=row["scan_max_mm"],
            ),
            metadata_text=row["metadata_text"],
            search_blob=row["search_blob"],
        )
        try:
            payload = normalize_metadata(json.loads(run.metadata_text))
            apply_browser_metadata_fields(run, payload)
        except Exception:
            pass
        runs.append(run)
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
    TABLE_COLUMNS = ("star", "date", "sample", "exp_tag", "power", "sample_power", "attenuation", "use_opo", "wavelength", "temp", "duration", "shot_noise", "range", "run")

    COLUMN_TITLES = {
        "star": "Star",
        "date": "Date",
        "run": "Run Folder",
        "sample": "Sample",
        "exp_tag": "Exp Tag",
        "power": "Port Power (mW)",
        "sample_power": "Sample Power (mW)",
        "attenuation": "Atten. Factor",
        "use_opo": "Use OPO",
        "wavelength": "Wavelength (nm)",
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
        "attenuation": 110,
        "use_opo": 90,
        "wavelength": 120,
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
        "attenuation": 95,
        "use_opo": 80,
        "wavelength": 105,
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
        self.visible_columns.add("attenuation")
        self.visible_columns.add("use_opo")
        self.visible_columns.add("wavelength")

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
        self.visible_columns = {"star", "date", "sample", "exp_tag", "power", "sample_power", "attenuation", "use_opo", "wavelength", "temp", "duration", "shot_noise", "range"}

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
            text="Hide Run List",
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
        self.table_toggle_button = tk.Button(action_frame, text="Hide Run List", width=12, command=self.toggle_table)
        self.table_toggle_button.pack(side="left", padx=(0, 8))
        tk.Button(action_frame, text="Edit Metadata", width=12, command=self.edit_metadata).pack(side="left", padx=(0, 8))
        tk.Button(action_frame, text="Normalize", width=12, command=self.normalize_selected_metadata).pack(side="left", padx=(0, 8))
        tk.Button(action_frame, text="Open Folder", width=12, command=self.open_selected_folder).pack(side="left", padx=(0, 8))
        tk.Button(action_frame, text="Play MP4", width=12, command=self.open_selected_mp4).pack(side="left", padx=(0, 8))
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
                "attenuation": run.attenuation_factor_display,
                "use_opo": run.use_opo_display,
                "wavelength": run.wavelength_display_nm,
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
        if column == "attenuation":
            value = run.physics.attenuation_factor
            return (1 if value is None else 0, value if value is not None else 0.0)
        if column == "use_opo":
            value = run.physics.use_opo
            return (1 if value is None else 0, 1 if value else 0)
        if column == "wavelength":
            value = run.physics.laser_wavelength_nm
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
        try:
            editor_root = run.metadata_path if run.metadata_path is not None else run.folder_path / "metadata.json"
            url = launch_html_editor(editor_root, wait=False)
            self.status_var.set(f"Opened HTML metadata editor: {url}")
        except Exception as exc:
            messagebox.showerror("Metadata Editor Failed", f"Could not open HTML metadata editor:\n{exc}")
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

        custom_row = len(fields) + 1
        custom_path_var = tk.StringVar()
        custom_value_var = tk.StringVar()
        tk.Label(container, text="Custom field", bg="#f3f1ea", fg="#12353c").grid(
            row=custom_row,
            column=0,
            sticky="w",
            pady=(14, 4),
        )
        tk.Entry(container, textvariable=custom_path_var).grid(
            row=custom_row,
            column=1,
            sticky="ew",
            padx=(10, 0),
            pady=(14, 4),
        )
        tk.Label(container, text="Custom value", bg="#f3f1ea", fg="#12353c").grid(
            row=custom_row + 1,
            column=0,
            sticky="w",
            pady=4,
        )
        tk.Entry(container, textvariable=custom_value_var).grid(
            row=custom_row + 1,
            column=1,
            sticky="ew",
            padx=(10, 0),
            pady=4,
        )

        def next_filtered_folder() -> Path | None:
            for index, filtered_run in enumerate(self.filtered_runs):
                if filtered_run.folder_path == run.folder_path:
                    if index + 1 < len(self.filtered_runs):
                        return self.filtered_runs[index + 1].folder_path
                    return None
            return None

        def save(open_next: bool = False) -> None:
            try:
                selected_iid = str(run.folder_path)
                next_folder = next_filtered_folder() if open_next else None
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

                custom_path = custom_path_var.get().strip()
                if custom_path:
                    set_dotted_metadata_value(payload, custom_path, parse_metadata_value(custom_value_var.get()))

                self._write_metadata_payload(run, payload)
                updated_run = load_run_record(run.final_result_path)
                upsert_run_record_in_db(self._current_root_path, updated_run)
                self._replace_run_record(updated_run)
                self._refresh_search_blob(updated_run)
                self.apply_filter()

                focus_iid = str(next_folder) if next_folder is not None else selected_iid
                if self.tree.exists(focus_iid):
                    self.tree.selection_set(focus_iid)
                    self.tree.focus(focus_iid)
                    focused_run = self.run_by_iid.get(focus_iid)
                    if focused_run is not None:
                        self.show_run(focused_run)
                self.status_var.set(f"Updated metadata for {updated_run.folder_name}.")
                self.save_config()
                dialog.destroy()
                if open_next and next_folder is not None and self.tree.exists(str(next_folder)):
                    self.after(0, self.edit_metadata)
            except Exception as exc:
                messagebox.showerror("Metadata Update Failed", f"Could not update metadata.json:\n{exc}")

        button_row = tk.Frame(dialog, bg="#f3f1ea")
        button_row.grid(row=1, column=0, sticky="e", padx=12, pady=(0, 12))
        tk.Button(button_row, text="Save", width=10, command=save).pack(side="left", padx=(0, 8))
        tk.Button(button_row, text="Save && Next", width=12, command=lambda: save(open_next=True)).pack(side="left", padx=(0, 8))
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
            run.attenuation_factor_display,
            run.use_opo_display,
            run.wavelength_display_nm,
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
            self.table_toggle_button.configure(text="Hide Run List")
            self.top_table_toggle_button.configure(text="Hide Run List")
            if left_widget not in panes:
                self.body_pane.add(self.left_panel, before=self.right_panel, stretch="always", minsize=520)
            if right_widget not in self.body_pane.panes():
                self.body_pane.add(self.right_panel, stretch="always", minsize=600)
        else:
            self.table_toggle_button.configure(text="Show Run List")
            self.top_table_toggle_button.configure(text="Show Run List")
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
            messagebox.showinfo("Analysis Complete", message)
            return

        self.status_var.set("Analysis failed.")
        messagebox.showerror("Analysis Failed", message)


def serialize_run(run: RunRecord) -> dict[str, object]:
    return {
        "folder_name": run.folder_name,
        "folder_path": str(run.folder_path),
        "date": run.sortable_date.strftime("%Y-%m-%d %H:%M"),
        "date_sort": run.sortable_date.isoformat(),
        "sample": run.sample or "",
        "exp_tag": run.exp_tag or "",
        "description": run.description or "",
        "tags": run.tags,
        "filename": run.filename or "",
        "duration": run.duration or "",
        "star": run.star_measurement,
        "port_power": run.port_power_display,
        "sample_power": run.sample_power_display,
        "attenuation_factor": run.attenuation_factor_display,
        "attenuation_factor_sort": run.physics.attenuation_factor,
        "use_opo": run.use_opo_display,
        "use_opo_sort": -1 if run.physics.use_opo is None else int(run.physics.use_opo),
        "wavelength_nm": run.wavelength_display_nm,
        "wavelength_nm_sort": run.physics.laser_wavelength_nm,
        "temperature": run.environment_temperature_display_k,
        "shot_noise": run.shot_noise_display,
        "shot_noise_value": run.shot_noise_value_display,
        "scan_range": run.scan_range_display,
        "center": run.center_display,
        "final_result_path": str(run.final_result_path) if run.final_result_path else "",
        "movie_path": str(run.movie_path) if run.movie_path else "",
        "loglog_plot_path": str(run.loglog_plot_path) if run.loglog_plot_path else "",
        "diagonal_offset_path": str(run.diagonal_offset_path) if run.diagonal_offset_path else "",
        "raw_std_plot_path": str(run.raw_std_plot_path) if run.raw_std_plot_path else "",
        "metadata_path": str(run.metadata_path) if run.metadata_path else "",
        "metadata_text": run.metadata_text,
    }


def embedded_html_browser_page() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DataFiles Browser</title>
  <style>
    :root {
      --ink: #12353c;
      --muted: #61767b;
      --line: #d6e0e2;
      --bg: #f3f1ea;
      --paper: #ffffff;
      --accent: #176f7a;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", Arial, sans-serif;
      background: var(--bg);
      color: var(--ink);
    }
    header {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      align-items: center;
      background: var(--ink);
      color: white;
      padding: 14px 18px;
    }
    h1 { margin: 0; font-size: 22px; }
    .root { color: #d6e8eb; font-size: 13px; margin-top: 4px; overflow-wrap: anywhere; }
    button {
      border: 1px solid #0f5962;
      background: var(--accent);
      color: white;
      border-radius: 4px;
      padding: 8px 11px;
      font: inherit;
      cursor: pointer;
    }
    button.secondary {
      background: white;
      color: var(--ink);
      border-color: #b9c8ca;
    }
    input {
      border: 1px solid #b9c8ca;
      border-radius: 4px;
      padding: 8px 9px;
      font: inherit;
      min-width: 0;
    }
    input[type="checkbox"] {
      width: 16px;
      height: 16px;
      accent-color: var(--accent);
      cursor: pointer;
    }
    button:disabled {
      opacity: 0.55;
      cursor: default;
    }
    .header-tools {
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
      justify-content: end;
    }
    .tabs {
      display: flex;
      gap: 4px;
      padding: 3px;
      border: 1px solid rgba(255,255,255,0.28);
      border-radius: 6px;
      background: rgba(255,255,255,0.08);
    }
    .tab-button {
      border-color: transparent;
      background: transparent;
      padding: 7px 10px;
    }
    .tab-button.active {
      background: white;
      color: var(--ink);
      border-color: white;
    }
    main {
      padding: 12px;
      min-height: calc(100vh - 68px);
    }
    .tab-panel.hidden { display: none; }
    .run-list-layout { display: block; }
    .plots-layout {
      display: grid;
      grid-template-columns: minmax(270px, 360px) minmax(460px, 1fr);
      gap: 12px;
    }
    .panel {
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 6px;
      min-width: 0;
    }
    .left {
      display: grid;
      grid-template-rows: auto 1fr;
      overflow: hidden;
      height: calc(100vh - 92px);
    }
    .filters {
      display: grid;
      grid-template-columns: 1fr 110px auto auto;
      gap: 8px;
      padding: 12px;
      border-bottom: 1px solid var(--line);
      align-items: center;
    }
    .count { color: var(--muted); font-size: 13px; }
    .table-wrap { overflow: auto; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td {
      border-bottom: 1px solid #e8eeee;
      padding: 7px 8px;
      text-align: left;
      white-space: nowrap;
    }
    th {
      position: sticky;
      top: 0;
      z-index: 1;
      background: #edf5f6;
      cursor: pointer;
      color: var(--ink);
    }
    tr { cursor: pointer; }
    tr:hover { background: #f5fafb; }
    tr.active { background: #dff0f2; }
    .compact-panel {
      display: grid;
      grid-template-rows: auto 1fr;
      overflow: hidden;
      height: calc(100vh - 92px);
    }
    .compact-filters {
      display: grid;
      gap: 8px;
      padding: 12px;
      border-bottom: 1px solid var(--line);
    }
    .compact-run-list {
      overflow: auto;
      padding: 6px;
    }
    .compact-run-item {
      width: 100%;
      border: 1px solid transparent;
      border-radius: 5px;
      background: transparent;
      color: var(--ink);
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 8px;
      align-items: start;
      text-align: left;
      padding: 9px;
      margin: 0 0 4px;
      cursor: pointer;
    }
    .compact-run-item:hover { background: #f5fafb; border-color: #dce8ea; }
    .compact-run-item.active { background: #dff0f2; border-color: #b5d9de; }
    .compact-main {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      font-weight: 700;
    }
    .compact-sub {
      color: var(--muted);
      font-size: 12px;
      margin-top: 4px;
      overflow-wrap: anywhere;
    }
    .right {
      padding: 12px;
      overflow: auto;
      height: calc(100vh - 92px);
    }
    .selected-header {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      align-items: start;
      margin-bottom: 12px;
    }
    .selected-title { font-size: 20px; font-weight: 700; }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; justify-content: end; }
    .meta-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(120px, 1fr));
      gap: 8px;
      margin-bottom: 12px;
    }
    .metric {
      border: 1px solid var(--line);
      border-radius: 4px;
      padding: 8px;
      background: #fbfcfc;
    }
    .metric span { display: block; color: var(--muted); font-size: 12px; margin-bottom: 3px; }
    .preview-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(220px, 1fr));
      gap: 12px;
    }
    .card {
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fbfcfc;
      min-height: 260px;
      display: grid;
      grid-template-rows: auto 1fr;
      overflow: hidden;
    }
    .card-title {
      padding: 8px 10px;
      font-weight: 700;
      border-bottom: 1px solid var(--line);
      display: flex;
      justify-content: space-between;
      gap: 8px;
      align-items: center;
    }
    .card-body {
      display: grid;
      place-items: center;
      min-height: 220px;
      color: var(--muted);
      text-align: center;
      padding: 8px;
    }
    .card-body img {
      max-width: 100%;
      max-height: 430px;
      object-fit: contain;
    }
    .card-body video {
      width: 100%;
      max-height: 520px;
      background: #0b2025;
      border-radius: 4px;
    }
    .video-card { grid-column: 1 / -1; }
    .status { color: var(--muted); font-size: 13px; }
    @media (max-width: 1100px) {
      .plots-layout { grid-template-columns: 1fr; }
      .left, .compact-panel, .right { height: auto; max-height: none; }
      .meta-grid, .preview-grid { grid-template-columns: 1fr; }
      .filters { grid-template-columns: 1fr; }
      header { grid-template-columns: 1fr; }
      .header-tools { justify-content: start; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>DataFiles Browser</h1>
      <div id="root" class="root"></div>
      <div id="analysisStatus" class="root"></div>
    </div>
    <div class="header-tools">
      <div class="tabs" role="tablist" aria-label="DataFiles Browser views">
        <button id="runListTabButton" class="tab-button active" type="button" role="tab" aria-selected="true" aria-controls="runListTab">Run List</button>
        <button id="plotsTabButton" class="tab-button" type="button" role="tab" aria-selected="false" aria-controls="plotsTab">Plots</button>
      </div>
      <div class="actions">
        <button id="refresh">Refresh</button>
        <button id="rerunSelected">Rerun Selected</button>
        <button id="rebuild" class="secondary">Rebuild Index</button>
        <button id="allMetadata" class="secondary">All Metadata</button>
      </div>
    </div>
  </header>
  <main>
    <section id="runListTab" class="tab-panel run-list-layout" role="tabpanel" aria-labelledby="runListTabButton">
      <section class="panel left">
        <div class="filters">
          <input id="search" type="search" placeholder="Search runs, sample, tags, attenuation...">
          <input id="minRange" type="number" step="0.01" placeholder="Range >=">
          <div id="count" class="count">0 runs</div>
          <div id="selectionStatus" class="count">0 selected</div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th data-sort="star">Star</th>
                <th>Select</th>
                <th data-sort="date_sort">Date</th>
                <th data-sort="sample">Sample</th>
                <th data-sort="exp_tag">Exp Tag</th>
                <th data-sort="port_power">Port Power</th>
                <th data-sort="sample_power">Sample Power</th>
                <th data-sort="attenuation_factor_sort">Atten. Factor</th>
                <th data-sort="temperature">Temp</th>
                <th data-sort="shot_noise_value">Shot Noise</th>
                <th data-sort="scan_range">Range</th>
                <th data-sort="folder_name">Run Folder</th>
              </tr>
            </thead>
            <tbody id="runRows"></tbody>
          </table>
        </div>
      </section>
    </section>
    <section id="plotsTab" class="tab-panel plots-layout hidden" role="tabpanel" aria-labelledby="plotsTabButton">
      <section class="panel compact-panel">
        <div class="compact-filters">
          <input id="plotSearch" type="search" placeholder="Find run for plots...">
          <div id="plotCount" class="count">0 runs</div>
        </div>
        <div id="plotRunList" class="compact-run-list"></div>
      </section>
      <section class="panel right">
        <div class="selected-header">
          <div>
            <div id="selectedTitle" class="selected-title">Nothing selected</div>
            <div id="selectedPath" class="status"></div>
          </div>
          <div class="actions">
          <button id="editMetadata">Edit Metadata</button>
          <button id="rerunThisRun" class="secondary">Rerun This Run</button>
          <button id="openFolder" class="secondary">Open Folder</button>
            <button id="playMp4" class="secondary">Play MP4</button>
            <button id="toggleStar" class="secondary">Star</button>
          </div>
        </div>
        <div id="metrics" class="meta-grid"></div>
        <div class="preview-grid">
          <div class="card video-card" data-kind="movie_path" data-media="video"><div class="card-title">MP4 Player <button class="secondary">Open</button></div><div class="card-body"></div></div>
          <div class="card" data-kind="final_result_path"><div class="card-title">Final Result <button class="secondary">Open</button></div><div class="card-body"></div></div>
          <div class="card" data-kind="loglog_plot_path"><div class="card-title">Log-Log Eval <button class="secondary">Open</button></div><div class="card-body"></div></div>
          <div class="card" data-kind="diagonal_offset_path"><div class="card-title">Diagonal Offset <button class="secondary">Open</button></div><div class="card-body"></div></div>
          <div class="card" data-kind="raw_std_plot_path"><div class="card-title">Raw Std Over Time <button class="secondary">Open</button></div><div class="card-body"></div></div>
        </div>
      </section>
    </section>
  </main>
  <script>
    let runs = [];
    let filtered = [];
    let selected = null;
    let checkedRuns = new Set();
    let analysisPoll = null;
    let lastFocusRefresh = 0;
    let sortKey = "date_sort";
    let sortDesc = true;

    const runRows = document.getElementById("runRows");
    const search = document.getElementById("search");
    const minRange = document.getElementById("minRange");
    const plotSearch = document.getElementById("plotSearch");
    const plotRunList = document.getElementById("plotRunList");
    const runListTab = document.getElementById("runListTab");
    const plotsTab = document.getElementById("plotsTab");
    const runListTabButton = document.getElementById("runListTabButton");
    const plotsTabButton = document.getElementById("plotsTabButton");
    const rerunSelectedButton = document.getElementById("rerunSelected");

    function text(value) { return value === undefined || value === null || value === "" ? "-" : String(value); }
    function assetUrl(path) { return path ? "/asset?path=" + encodeURIComponent(path) : ""; }
    function numeric(value) {
      if (value === undefined || value === null || value === "-" || value === "") return null;
      const number = Number(value);
      return Number.isFinite(number) ? number : null;
    }
    function searchBlob(run) {
      return [
        run.folder_name, run.folder_path, run.sample, run.exp_tag, run.description,
        (run.tags || []).join(" "), run.filename, run.duration, run.port_power,
        run.sample_power, run.attenuation_factor, run.temperature, run.shot_noise
      ].join(" ").toLowerCase();
    }
    function applyFilters() {
      const needle = search.value.trim().toLowerCase();
      const min = minRange.value === "" ? null : Number(minRange.value);
      filtered = runs.filter(run => {
        if (needle && !searchBlob(run).includes(needle)) return false;
        const range = numeric(run.scan_range);
        if (Number.isFinite(min) && (range === null || range < min)) return false;
        return true;
      });
      filtered.sort(compareRuns);
      renderRows();
      renderPlotRunList();
      renderSelectionStatus();
      if (!selected && filtered.length) selectRun(filtered[0].folder_path);
    }
    function setTab(tabName) {
      const showPlots = tabName === "plots";
      runListTab.classList.toggle("hidden", showPlots);
      plotsTab.classList.toggle("hidden", !showPlots);
      runListTabButton.classList.toggle("active", !showPlots);
      plotsTabButton.classList.toggle("active", showPlots);
      runListTabButton.setAttribute("aria-selected", String(!showPlots));
      plotsTabButton.setAttribute("aria-selected", String(showPlots));
    }
    function compareRuns(a, b) {
      let av = a[sortKey];
      let bv = b[sortKey];
      const an = numeric(av);
      const bn = numeric(bv);
      if (an !== null || bn !== null) {
        av = an === null ? Number.POSITIVE_INFINITY : an;
        bv = bn === null ? Number.POSITIVE_INFINITY : bn;
      } else {
        av = String(av || "").toLowerCase();
        bv = String(bv || "").toLowerCase();
      }
      if (av < bv) return sortDesc ? 1 : -1;
      if (av > bv) return sortDesc ? -1 : 1;
      return 0;
    }
    function renderRows() {
      document.getElementById("count").textContent = `${filtered.length} runs`;
      runRows.innerHTML = "";
      filtered.forEach(run => {
        const tr = document.createElement("tr");
        tr.className = selected && selected.folder_path === run.folder_path ? "active" : "";
        tr.innerHTML = `
          <td>${run.star ? "[x]" : "[ ]"}</td>
          <td><input class="run-check" type="checkbox" ${checkedRuns.has(run.folder_path) ? "checked" : ""} aria-label="Select ${text(run.folder_name)} for rerun"></td>
          <td>${text(run.date)}</td>
          <td>${text(run.sample)}</td>
          <td>${text(run.exp_tag)}</td>
          <td>${text(run.port_power)}</td>
          <td>${text(run.sample_power)}</td>
          <td>${text(run.attenuation_factor)}</td>
          <td>${text(run.temperature)}</td>
          <td>${text(run.shot_noise_value)}</td>
          <td>${text(run.scan_range)}</td>
          <td>${text(run.folder_name)}</td>`;
        const checkbox = tr.querySelector(".run-check");
        checkbox.addEventListener("click", event => event.stopPropagation());
        checkbox.addEventListener("change", () => toggleRunChecked(run.folder_path, checkbox.checked));
        tr.addEventListener("click", () => selectRun(run.folder_path));
        runRows.appendChild(tr);
      });
    }
    function toggleRunChecked(folderPath, checked) {
      if (checked) checkedRuns.add(folderPath);
      else checkedRuns.delete(folderPath);
      renderRows();
      renderPlotRunList();
      renderSelectionStatus();
    }
    function renderSelectionStatus() {
      const count = checkedRuns.size;
      document.getElementById("selectionStatus").textContent = count ? `${count} selected for rerun` : "0 selected";
      rerunSelectedButton.textContent = count ? `Rerun ${count} Selected` : "Rerun Selected";
    }
    function renderPlotRunList() {
      const needle = plotSearch.value.trim().toLowerCase();
      const plotRuns = needle ? filtered.filter(run => searchBlob(run).includes(needle)) : filtered;
      document.getElementById("plotCount").textContent = `${plotRuns.length} runs`;
      plotRunList.innerHTML = "";
      plotRuns.forEach(run => {
        const item = document.createElement("div");
        item.className = selected && selected.folder_path === run.folder_path ? "compact-run-item active" : "compact-run-item";
        item.innerHTML = `
          <input class="plot-run-check" type="checkbox" ${checkedRuns.has(run.folder_path) ? "checked" : ""} aria-label="Select ${text(run.folder_name)} for rerun">
          <div>
            <div class="compact-main">
              <span>${text(run.date)}</span>
              <span>${text(run.attenuation_factor)}x</span>
            </div>
            <div class="compact-sub">${text(run.sample)} - ${text(run.exp_tag)}</div>
            <div class="compact-sub">${text(run.folder_name)}</div>
          </div>
        `;
        const checkbox = item.querySelector(".plot-run-check");
        checkbox.addEventListener("click", event => event.stopPropagation());
        checkbox.addEventListener("change", () => toggleRunChecked(run.folder_path, checkbox.checked));
        item.addEventListener("click", () => selectRun(run.folder_path));
        plotRunList.appendChild(item);
      });
    }
    function selectRun(folderPath) {
      selected = runs.find(run => run.folder_path === folderPath) || null;
      renderRows();
      renderPlotRunList();
      renderSelected();
    }
    function renderMetric(label, value) {
      return `<div class="metric"><span>${label}</span>${text(value)}</div>`;
    }
    function renderSelected() {
      if (!selected) {
        document.getElementById("selectedTitle").textContent = "Nothing selected";
        document.getElementById("selectedPath").textContent = "";
        document.getElementById("metrics").innerHTML = "";
        document.querySelectorAll(".card .card-body").forEach(body => { body.textContent = "Select a run"; });
        return;
      }
      document.getElementById("selectedTitle").textContent = `${text(selected.sample)}   ${text(selected.date)}`;
      document.getElementById("selectedPath").textContent = selected.folder_path;
      document.getElementById("toggleStar").textContent = selected.star ? "Unstar" : "Star";
      document.getElementById("metrics").innerHTML = [
        renderMetric("Run", selected.folder_name),
        renderMetric("Tags", (selected.tags || []).join(", ")),
        renderMetric("Atten. Factor", selected.attenuation_factor),
        renderMetric("Shot Noise", selected.shot_noise),
        renderMetric("Port Power", selected.port_power),
        renderMetric("Sample Power", selected.sample_power),
        renderMetric("Temperature K", selected.temperature),
        renderMetric("Range mm", selected.scan_range)
      ].join("");
      document.querySelectorAll(".card").forEach(card => {
        const key = card.dataset.kind;
        const isVideo = card.dataset.media === "video";
        const body = card.querySelector(".card-body");
        const button = card.querySelector("button");
        const path = selected[key];
        if (path) {
          body.innerHTML = isVideo
            ? `<video controls preload="metadata" src="${assetUrl(path)}"></video>`
            : `<img src="${assetUrl(path)}" alt="">`;
          button.disabled = false;
          button.onclick = () => openPath(path);
        } else {
          body.textContent = isVideo ? "No MP4 found" : "Not found";
          button.disabled = true;
          button.onclick = null;
        }
      });
    }
    function setAnalysisStatus(message) {
      document.getElementById("analysisStatus").textContent = message || "";
    }
    function rerunTargets(useCurrentOnly = false) {
      if (useCurrentOnly && selected) return [selected.folder_path];
      if (checkedRuns.size) return Array.from(checkedRuns);
      return selected ? [selected.folder_path] : [];
    }
    async function rerunSelected(useCurrentOnly = false) {
      const folderPaths = rerunTargets(useCurrentOnly);
      if (!folderPaths.length) {
        alert("Select at least one run first.");
        return;
      }
      const label = folderPaths.length === 1 ? "1 run" : `${folderPaths.length} runs`;
      const preview = folderPaths.slice(0, 8).map(path => path.split(/[\\\\/]/).pop()).join("\\n");
      const extra = folderPaths.length > 8 ? `\\n... and ${folderPaths.length - 8} more` : "";
      if (!confirm(`Rerun cm_pipeline_all_in_one.py for ${label}?\\n\\n${preview}${extra}`)) return;
      const data = await postJson("/api/rerun", { folder_paths: folderPaths });
      setAnalysisStatus(data.message || "Running analysis...");
      startAnalysisPoll();
    }
    function startAnalysisPoll() {
      if (analysisPoll) clearInterval(analysisPoll);
      const poll = async () => {
        try {
          const response = await fetch("/api/rerun-status");
          if (!response.ok) throw new Error(await response.text());
          const data = await response.json();
          setAnalysisStatus(data.message || (data.running ? "Running analysis..." : ""));
          if (!data.running) {
            clearInterval(analysisPoll);
            analysisPoll = null;
            const folderPath = selected && selected.folder_path;
            await loadRuns(false);
            if (folderPath) selectRun(folderPath);
          }
        } catch (err) {
          setAnalysisStatus(err.message);
        }
      };
      poll();
      analysisPoll = setInterval(poll, 2500);
    }
    async function loadRuns(rebuild = false) {
      const url = rebuild ? "/api/runs?rebuild=1" : "/api/runs";
      const response = await fetch(url);
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      document.getElementById("root").textContent = data.root;
      runs = data.runs;
      const validFolders = new Set(runs.map(run => run.folder_path));
      checkedRuns = new Set(Array.from(checkedRuns).filter(folderPath => validFolders.has(folderPath)));
      selected = null;
      applyFilters();
    }
    async function reloadPreservingSelection(rebuild = false) {
      const folderPath = selected && selected.folder_path;
      await loadRuns(rebuild);
      if (folderPath && runs.some(run => run.folder_path === folderPath)) selectRun(folderPath);
    }
    async function refreshAfterExternalEdit() {
      const now = Date.now();
      if (now - lastFocusRefresh < 1500) return;
      lastFocusRefresh = now;
      await reloadPreservingSelection(false);
    }
    async function postJson(url, payload) {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    }
    async function openPath(path) { await postJson("/api/open", { path }); }
    document.querySelectorAll("th[data-sort]").forEach(th => {
      th.addEventListener("click", () => {
        const next = th.dataset.sort;
        if (sortKey === next) sortDesc = !sortDesc;
        else { sortKey = next; sortDesc = next === "date_sort"; }
        applyFilters();
      });
    });
    search.addEventListener("input", applyFilters);
    minRange.addEventListener("input", applyFilters);
    plotSearch.addEventListener("input", renderPlotRunList);
    runListTabButton.addEventListener("click", () => setTab("runs"));
    plotsTabButton.addEventListener("click", () => setTab("plots"));
    document.getElementById("refresh").addEventListener("click", () => reloadPreservingSelection(false));
    rerunSelectedButton.addEventListener("click", () => rerunSelected(false).catch(err => alert(err.message)));
    document.getElementById("rerunThisRun").addEventListener("click", () => rerunSelected(true).catch(err => alert(err.message)));
    document.getElementById("rebuild").addEventListener("click", () => reloadPreservingSelection(true));
    document.getElementById("allMetadata").addEventListener("click", () => postJson("/api/edit-all-metadata", {}));
    document.getElementById("openFolder").addEventListener("click", () => selected && openPath(selected.folder_path));
    document.getElementById("playMp4").addEventListener("click", () => selected && selected.movie_path && openPath(selected.movie_path));
    document.getElementById("editMetadata").addEventListener("click", () => selected && postJson("/api/edit-metadata", { path: selected.metadata_path || selected.folder_path }));
    document.getElementById("toggleStar").addEventListener("click", async () => {
      if (!selected) return;
      const folderPath = selected.folder_path;
      await postJson("/api/star", { folder_path: selected.folder_path, star: !selected.star });
      await loadRuns(false);
      selectRun(folderPath);
    });
    window.addEventListener("focus", () => refreshAfterExternalEdit().catch(err => setAnalysisStatus(err.message)));
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) refreshAfterExternalEdit().catch(err => setAnalysisStatus(err.message));
    });
    loadRuns(false).catch(err => alert(err.message));
  </script>
</body>
</html>
"""


def html_browser_page() -> str:
    index_path = Path(__file__).with_name("index.html")
    if index_path.is_file():
        return index_path.read_text(encoding="utf-8")
    return embedded_html_browser_page()


def launch_html_browser(root_path: Path | None = None, wait: bool = True) -> str:
    import http.server
    import mimetypes
    import socketserver
    import urllib.parse
    import webbrowser

    root = (root_path or configured_root_path()).expanduser().resolve()
    state: dict[str, list[RunRecord]] = {"runs": []}
    analysis_lock = threading.Lock()
    analysis_state: dict[str, object] = {
        "running": False,
        "message": "",
        "label": "",
        "return_code": None,
        "started_utc": "",
        "finished_utc": "",
    }
    client_disconnect_errors = (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)

    def load_current_runs(rebuild: bool = False) -> list[RunRecord]:
        if rebuild or is_index_stale(root):
            runs = scan_runs(root)
            write_runs_to_db(root, runs)
        else:
            runs = load_runs_from_db(root)
            if not runs:
                runs = scan_runs(root)
                write_runs_to_db(root, runs)
        state["runs"] = runs
        return runs

    def find_run(folder_path: str) -> RunRecord | None:
        resolved = str(Path(folder_path).expanduser().resolve())
        for run in state.get("runs", []):
            if str(run.folder_path.resolve()) == resolved:
                return run
        return None

    def selected_runs_from_payload(data: dict[str, object]) -> list[RunRecord]:
        raw_paths = data.get("folder_paths", [])
        if isinstance(raw_paths, str):
            raw_paths = [raw_paths]
        if not isinstance(raw_paths, list):
            raise ValueError("folder_paths must be a list.")
        selected_runs: list[RunRecord] = []
        seen: set[str] = set()
        for raw_path in raw_paths:
            run = find_run(str(raw_path))
            if run is None:
                raise ValueError(f"Run not found: {raw_path}")
            key = str(run.folder_path.resolve())
            if key not in seen:
                selected_runs.append(run)
                seen.add(key)
        if not selected_runs:
            raise ValueError("Select at least one run to rerun.")
        return selected_runs

    def rerun_analysis_subprocess(script_path: Path, folder_paths: list[Path], label: str) -> None:
        command = [sys.executable, str(script_path), *[str(path) for path in folder_paths]]
        output_lines: list[str] = []
        return_code = -1
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert process.stdout is not None
            for raw_line in process.stdout:
                line = raw_line.strip()
                if not line:
                    continue
                output_lines.append(line)
                if len(output_lines) > 80:
                    output_lines = output_lines[-80:]
                with analysis_lock:
                    analysis_state["message"] = line
            return_code = process.wait()
        except Exception as exc:
            output_lines.append(str(exc))

        message = "\n".join(output_lines).strip()
        if return_code == 0:
            try:
                for folder_path in folder_paths:
                    upsert_run_record_in_db(root, index_run_folder(folder_path, root))
                load_current_runs(rebuild=False)
            except Exception as exc:
                message = f"{message}\nWarning: analysis finished, but index refresh failed: {exc}".strip()
            if not message:
                message = f"Finished rerunning analysis for {label}."
        elif not message:
            message = "Unknown analysis error."

        with analysis_lock:
            analysis_state.update(
                {
                    "running": False,
                    "message": message if return_code != 0 else f"Finished analysis for {label}.",
                    "label": label,
                    "return_code": return_code,
                    "finished_utc": datetime.utcnow().isoformat(timespec="seconds"),
                }
            )

    def allowed_path(raw_path: str) -> Path:
        path = Path(raw_path).expanduser().resolve()
        for run in state.get("runs", []):
            allowed = [
                run.folder_path,
                run.final_result_path,
                run.movie_path,
                run.loglog_plot_path,
                run.diagonal_offset_path,
                run.raw_std_plot_path,
                run.metadata_path,
                run.folder_path / "metadata.json",
            ]
            for candidate in allowed:
                if candidate is not None and path == candidate.expanduser().resolve():
                    return path
        raise ValueError("Path is not part of the current DataFiles Browser index.")

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def send_bytes(self, body: bytes, content_type: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def send_text(self, text: str, status: int = 200, content_type: str = "text/plain") -> None:
            self.send_bytes(text.encode("utf-8"), f"{content_type}; charset=utf-8", status)

        def send_json(self, data: object, status: int = 200) -> None:
            self.send_text(json.dumps(data), status, "application/json")

        def send_file(self, path: Path, content_type: str) -> None:
            file_size = path.stat().st_size
            range_header = self.headers.get("Range", "")
            start = 0
            end = file_size - 1
            status = 200

            if range_header.startswith("bytes="):
                raw_range = range_header.removeprefix("bytes=").split(",", 1)[0].strip()
                raw_start, _, raw_end = raw_range.partition("-")
                if raw_start:
                    start = int(raw_start)
                if raw_end:
                    end = int(raw_end)
                end = min(end, file_size - 1)
                if start > end or start < 0:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{file_size}")
                    self.end_headers()
                    return
                status = 206

            length = end - start + 1
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(length))
            if status == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.end_headers()
            with path.open("rb") as handle:
                handle.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = handle.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)

        def read_json(self) -> dict[str, object]:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                return {}
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            return payload if isinstance(payload, dict) else {}

        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            try:
                if parsed.path in {"/", "/index.html"}:
                    self.send_text(html_browser_page(), content_type="text/html")
                    return
                if parsed.path == "/api/runs":
                    query = urllib.parse.parse_qs(parsed.query)
                    runs = load_current_runs(rebuild=query.get("rebuild", ["0"])[0] == "1")
                    self.send_json({"root": str(root), "runs": [serialize_run(run) for run in runs]})
                    return
                if parsed.path == "/api/rerun-status":
                    with analysis_lock:
                        self.send_json(dict(analysis_state))
                    return
                if parsed.path == "/asset":
                    query = urllib.parse.parse_qs(parsed.query)
                    path = allowed_path(query.get("path", [""])[0])
                    if not path.is_file():
                        self.send_text("File not found", status=404)
                        return
                    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                    self.send_file(path, content_type)
                    return
                self.send_text("Not found", status=404)
            except client_disconnect_errors:
                return
            except Exception as exc:
                try:
                    self.send_text(str(exc), status=400)
                except client_disconnect_errors:
                    return

        def do_POST(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            try:
                data = self.read_json()
                if parsed.path == "/api/open":
                    path = allowed_path(str(data.get("path", "")))
                    os.startfile(path)  # type: ignore[attr-defined]
                    self.send_json({"ok": True})
                    return
                if parsed.path == "/api/rerun":
                    with analysis_lock:
                        if bool(analysis_state.get("running")):
                            raise ValueError("A rerun is already in progress.")
                    selected_runs = selected_runs_from_payload(data)
                    script_path = Path(__file__).with_name(PIPELINE_SCRIPT_NAME)
                    if not script_path.is_file():
                        raise ValueError(f"Could not find pipeline script: {script_path}")
                    folder_paths = [run.folder_path for run in selected_runs]
                    label = "1 run" if len(folder_paths) == 1 else f"{len(folder_paths)} runs"
                    with analysis_lock:
                        analysis_state.update(
                            {
                                "running": True,
                                "message": f"Running analysis for {label}...",
                                "label": label,
                                "return_code": None,
                                "started_utc": datetime.utcnow().isoformat(timespec="seconds"),
                                "finished_utc": "",
                            }
                        )
                    thread = threading.Thread(
                        target=rerun_analysis_subprocess,
                        args=(script_path, folder_paths, label),
                        daemon=True,
                    )
                    thread.start()
                    self.send_json({"ok": True, "message": f"Running analysis for {label}."})
                    return
                if parsed.path == "/api/edit-metadata":
                    raw_path = str(data.get("path", ""))
                    path = Path(raw_path)
                    if path.name.lower() != "metadata.json":
                        path = path / "metadata.json"
                    path = allowed_path(str(path))
                    url = launch_html_editor(path, wait=False)
                    self.send_json({"ok": True, "url": url})
                    return
                if parsed.path == "/api/edit-all-metadata":
                    url = launch_html_editor(root, wait=False)
                    self.send_json({"ok": True, "url": url})
                    return
                if parsed.path == "/api/star":
                    run = find_run(str(data.get("folder_path", "")))
                    if run is None:
                        raise ValueError("Run not found.")
                    star = bool(data.get("star", False))
                    metadata_path = run.metadata_path or (run.folder_path / "metadata.json")
                    payload: dict[str, object]
                    if metadata_path.exists():
                        loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
                        payload = normalize_metadata(loaded) if isinstance(loaded, dict) else {}
                    else:
                        payload = {}
                    payload["StarMeasurement"] = star
                    metadata_path.write_text(json.dumps(normalize_metadata(payload), indent=2), encoding="utf-8")
                    updated = index_run_folder(run.folder_path, root)
                    load_current_runs(rebuild=False)
                    self.send_json({"ok": True, "run": serialize_run(updated)})
                    return
                self.send_text("Not found", status=404)
            except client_disconnect_errors:
                return
            except Exception as exc:
                try:
                    self.send_text(str(exc), status=400)
                except client_disconnect_errors:
                    return

    load_current_runs(rebuild=False)
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"DataFiles HTML browser: {url}")
    webbrowser.open(url)
    if not wait:
        return url
    try:
        input("Press Enter to stop the DataFiles HTML browser server...")
    finally:
        server.shutdown()
        server.server_close()
    return url


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Browse Quantum DataFiles runs.")
    parser.add_argument("root", nargs="?", type=Path, help="DataFiles root. Defaults to the saved browser root.")
    parser.add_argument("--tk", action="store_true", help="Open the legacy Tkinter DataFiles UI.")
    args = parser.parse_args()

    if not args.tk:
        launch_html_browser(args.root)
        return

    if args.root is not None:
        CONFIG_PATH.write_text(
            json.dumps({"root_path": str(args.root.expanduser().resolve())}, indent=2),
            encoding="utf-8",
        )
    app = DataFilesBrowser()
    app.mainloop()


if __name__ == "__main__":
    main()
