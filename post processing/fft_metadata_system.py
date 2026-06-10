from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


DEFAULT_ROOT = Path(r"D:\Quantum Squeezing Project\DataFiles")
DEFAULT_DB_PATH = Path(tempfile.gettempdir()) / "quantum_fft_metadata_index.sqlite3"
FFT_OUTPUT_DIR_NAME = "fft_analysis"
MEASUREMENT_CHANNEL_COUNT = 4
MEASUREMENT_CHANNEL_LAYOUT = "4 interleaved data channels per measurement"

FFT_FILE_PATTERNS = (
    "*fft*.png",
    "*fft*.csv",
)

KNOWN_FFT_NAMES = {
    "fft_spectrum.png",
    "fft_result.png",
    "raw_std_fft_spectrum.csv",
    "all_channel_fft_peaks_200s.csv",
    "interleaved_fft_low_frequency_loglog.png",
    "interleaved_fft_low_frequency_loglog.csv",
    "interleaved_fft_high_frequency_semilog.png",
    "interleaved_fft_high_frequency_semilog.csv",
}
RAW_FFT_CANDIDATE_MODE = "raw_fft_candidate"


@dataclass(frozen=True)
class FftArtifact:
    root_path: Path
    run_folder: Path
    path: Path
    artifact_type: str
    mode: str
    title: str
    sample: str
    experiment_tag: str
    description: str
    tags: str
    measurement_note: str
    raw_file_count: int
    raw_total_bytes: int
    run_timestamp: str
    metadata_json: str
    summary_json: str
    search_blob: str


def safe_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return ", ".join(safe_text(item) for item in value if safe_text(item))
    return ""


def safe_tags(value: object) -> list[str]:
    if isinstance(value, list):
        return [safe_text(item) for item in value if safe_text(item)]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def nested_value(payload: object, *path: str) -> object:
    current = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def safe_float(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or abs(number) == float("inf"):
        return None
    return number


def first_float(payload: dict[str, object], paths: list[tuple[str, ...]]) -> float | None:
    for path in paths:
        value = safe_float(nested_value(payload, *path))
        if value is not None:
            return value
    return None


def parse_run_timestamp(run_folder: Path, metadata: dict[str, object]) -> str:
    timestamp = metadata.get("Timestamp")
    if isinstance(timestamp, str) and timestamp.strip():
        try:
            return datetime.fromisoformat(timestamp.strip()).isoformat(timespec="seconds")
        except ValueError:
            pass

    prefix = run_folder.name[:15]
    try:
        return datetime.strptime(prefix, "%Y%m%d_%H%M%S").isoformat(timespec="seconds")
    except ValueError:
        try:
            return datetime.fromtimestamp(run_folder.stat().st_ctime).isoformat(timespec="seconds")
        except OSError:
            return ""


def read_run_metadata(run_folder: Path) -> dict[str, object]:
    metadata_path = run_folder / "metadata.json"
    if not metadata_path.is_file():
        return {}
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def infer_run_folder(path: Path) -> Path:
    if path.parent.name.lower() == FFT_OUTPUT_DIR_NAME.lower():
        return path.parent.parent
    return path.parent


def infer_artifact_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".png":
        return "plot"
    if suffix == ".csv":
        return "csv"
    return suffix.removeprefix(".") or "file"


def infer_mode(path: Path) -> str:
    name = path.name.lower()
    if "low_frequency" in name or "low-frequency" in name or "loglog" in name or "log-log" in name:
        return "low_frequency"
    if "high_frequency" in name or "high-frequency" in name or "semilog" in name:
        return "high_frequency"
    if "peak" in name:
        return "peaks"
    if "raw_std" in name:
        return "raw_std"
    if "spectrum" in name or "result" in name:
        return "spectrum"
    return "unknown"


def infer_title(path: Path, mode: str) -> str:
    name = path.name.lower()
    if name == "fft_spectrum.png":
        return "FFT Spectrum"
    if name == "fft_result.png":
        return "FFT Result"
    if name == "all_channel_fft_peaks_200s.csv":
        return "All Channel FFT Peaks 200s"
    if name == "raw_std_fft_spectrum.csv":
        return "Raw Std FFT Spectrum"
    if mode == "low_frequency":
        return "Raw Interleaved FFT Low Frequency"
    if mode == "high_frequency":
        return "Raw Interleaved FFT High Frequency"
    return path.stem.replace("_", " ").replace("-", " ").title()


def png_dimensions(path: Path) -> tuple[int | None, int | None]:
    try:
        with path.open("rb") as handle:
            header = handle.read(24)
    except OSError:
        return None, None
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        return None, None
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    return width, height


def summarize_csv(path: Path) -> dict[str, object]:
    summary: dict[str, object] = {}
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.reader(handle)
            header = next(reader, [])
            rows = []
            for _ in range(5):
                row = next(reader, None)
                if row is None:
                    break
                rows.append(row)
    except Exception as exc:
        return {"error": str(exc)}

    summary["columns"] = header
    summary["column_count"] = len(header)
    summary["preview_rows"] = rows
    if header and header[0].lower() in {"frequency_hz", "frequency"}:
        summary["series_count"] = max(0, len(header) - 1)
    if {"PeakFreq_Hz", "PeakAmp"}.issubset(set(header)) and rows:
        try:
            peak_amp_index = header.index("PeakAmp")
            best_row = max(rows, key=lambda row: float(row[peak_amp_index]) if len(row) > peak_amp_index else float("-inf"))
            summary["first_preview_peak"] = dict(zip(header, best_row))
        except Exception:
            pass

    try:
        if path.stat().st_size < 50 * 1024 * 1024:
            with path.open("r", encoding="utf-8-sig", errors="ignore") as handle:
                summary["row_count"] = max(0, sum(1 for _ in handle) - 1)
    except OSError:
        pass
    return summary


def summarize_artifact(path: Path) -> dict[str, object]:
    summary: dict[str, object] = {
        "file_name": path.name,
        "file_size_bytes": path.stat().st_size,
        "modified_time": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
    }
    if path.suffix.lower() == ".png":
        width, height = png_dimensions(path)
        summary["image_width_px"] = width
        summary["image_height_px"] = height
    elif path.suffix.lower() == ".csv":
        summary.update(summarize_csv(path))
    return summary


def summarize_raw_files(run_folder: Path) -> tuple[int, int, list[dict[str, object]]]:
    raw_files = sorted(path for path in run_folder.glob("Data_*.bin") if path.is_file())
    entries = [
        {
            "name": path.name,
            "size_bytes": path.stat().st_size,
            "modified_time": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
        }
        for path in raw_files
    ]
    return len(raw_files), sum(int(entry["size_bytes"]) for entry in entries), entries


def build_measurement_note(
    metadata: dict[str, object],
    sample: str,
    experiment_tag: str,
    description: str,
    tags: list[str],
    raw_file_count: int,
    raw_total_bytes: int,
) -> str:
    parts: list[str] = []

    if sample:
        parts.append(sample)
    if experiment_tag:
        parts.append(experiment_tag)
    if description:
        parts.append(description)
    if tags:
        parts.append("tags: " + ", ".join(tags))

    lower_context = " ".join([description, experiment_tag, " ".join(tags)]).lower()
    if "dark noise" in lower_context:
        parts.append("dark-noise reference")
    if "no highpass" in lower_context:
        parts.append("no highpass filter")
    elif "highpass" in lower_context:
        parts.append("highpass filter")
    if "single point" in lower_context:
        parts.append("single-point measurement")
    if "scanning" in lower_context or "scan" in lower_context:
        parts.append("scan measurement")
    if "opo" in lower_context:
        parts.append("OPO involved")

    wavelength_nm = first_float(
        metadata,
        [
            ("PhysicsData", "LaserWavelength_nm"),
            ("PhysicsData", "LaserWavelengthNm"),
            ("PhysicsData", "Wavelength_nm"),
            ("LaserWavelength_nm",),
            ("Wavelength_nm",),
        ],
    )
    if wavelength_nm is None:
        match = re.search(r"@\s*([0-9]+(?:\.[0-9]+)?)\s*nm\b", description, flags=re.IGNORECASE)
        if match:
            wavelength_nm = safe_float(match.group(1))
    if wavelength_nm is not None:
        parts.append(f"{wavelength_nm:g} nm")

    detector = safe_text(
        nested_value(metadata, "PhysicsData", "Detector")
        or metadata.get("Detector")
    )
    if detector:
        parts.append(f"detector {detector}")

    scan_range_mm = first_float(metadata, [("PhysicsData", "ScanRange_mm"), ("ScanRange_mm",)])
    scan_velocity_mm_s = first_float(
        metadata,
        [
            ("PhysicsData", "ScanVelocity_mm_s"),
            ("PhysicsData", "ScanRate_mm_s"),
            ("ScanVelocity_mm_s",),
            ("ScanRate_mm_s",),
        ],
    )
    if scan_range_mm is not None and scan_range_mm > 0:
        parts.append(f"scan range {scan_range_mm:g} mm")
    if scan_velocity_mm_s is not None and scan_velocity_mm_s > 0:
        parts.append(f"scan rate {scan_velocity_mm_s:g} mm/s")

    motor1 = safe_text(
        nested_value(metadata, "Configuration", "Motor1Position")
        or metadata.get("Motor1Position")
    )
    motor2 = safe_text(
        nested_value(metadata, "Configuration", "Motor2Position")
        or metadata.get("Motor2Position")
    )
    if motor1:
        parts.append(f"motor1 {motor1}")
    if motor2:
        parts.append(f"motor2 {motor2}")

    shot_noise = first_float(
        metadata,
        [
            ("PhysicsData", "ShotNoiseResult_urad2_rtHz"),
            ("PhysicsData", "ShotNoiseResult"),
            ("ShotNoiseResult_urad2_rtHz",),
        ],
    )
    if shot_noise is not None:
        parts.append(f"shot noise {shot_noise:g} urad^2/rtHz")

    if raw_file_count:
        parts.append(f"{MEASUREMENT_CHANNEL_COUNT} interleaved channels")
        parts.append(f"raw-backed: {raw_file_count} Data_*.bin files, {raw_total_bytes / (1024**3):.2f} GB")

    deduped: list[str] = []
    seen: set[str] = set()
    for part in parts:
        normalized = " ".join(part.split()).lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(part)
    return "; ".join(deduped)


def is_fft_artifact(path: Path) -> bool:
    name = path.name.lower()
    if name in KNOWN_FFT_NAMES:
        return True
    return "fft" in name and path.suffix.lower() in {".png", ".csv"}


def discover_fft_files(root_path: Path) -> list[Path]:
    found: dict[str, Path] = {}
    for pattern in FFT_FILE_PATTERNS:
        for path in root_path.rglob(pattern):
            if path.is_file() and is_fft_artifact(path):
                found[str(path.resolve()).lower()] = path.resolve()
    return sorted(found.values(), key=lambda item: str(item).lower())


def discover_raw_candidate_folders(root_path: Path) -> list[Path]:
    folders: dict[str, Path] = {}
    for path in root_path.rglob("Data_*.bin"):
        if path.is_file():
            folders[str(path.parent.resolve()).lower()] = path.parent.resolve()
    return sorted(folders.values(), key=lambda item: str(item).lower())


def build_raw_candidate_artifact(root_path: Path, run_folder: Path) -> FftArtifact:
    metadata = read_run_metadata(run_folder)
    tags = safe_tags(metadata.get("Tags"))
    raw_file_count, raw_total_bytes, raw_files = summarize_raw_files(run_folder)
    if not raw_files:
        raise ValueError(f"{run_folder} has no Data_*.bin raw files.")

    sample = safe_text(metadata.get("Sample"))
    experiment_tag = safe_text(
        metadata.get("ExperimentTag")
        or metadata.get("ExpTag")
        or nested_value(metadata, "Configuration", "ExperimentTag")
        or nested_value(metadata, "PhysicsData", "ExperimentTag")
    )
    description = safe_text(metadata.get("Description"))
    measurement_note = build_measurement_note(
        metadata,
        sample,
        experiment_tag,
        description,
        tags,
        raw_file_count,
        raw_total_bytes,
    )
    run_timestamp = parse_run_timestamp(run_folder, metadata)
    raw_path = run_folder / str(raw_files[0]["name"])
    summary = {
        "file_name": raw_path.name,
        "file_size_bytes": raw_path.stat().st_size,
        "modified_time": datetime.fromtimestamp(raw_path.stat().st_mtime).isoformat(timespec="seconds"),
        "raw_file_count": raw_file_count,
        "raw_total_bytes": raw_total_bytes,
        "raw_total_gb": round(raw_total_bytes / (1024**3), 3),
        "raw_files": raw_files,
        "purpose": "Raw data is available for customized FFT analysis.",
    }
    metadata_subset = {
        "Sample": sample,
        "ExperimentTag": experiment_tag,
        "Description": description,
        "MeasurementNote": measurement_note,
        "MeasurementChannelCount": MEASUREMENT_CHANNEL_COUNT,
        "MeasurementChannelLayout": MEASUREMENT_CHANNEL_LAYOUT,
        "Tags": tags,
        "RunTimestamp": run_timestamp,
        "FFTAnalysis": metadata.get("FFTAnalysis") if isinstance(metadata.get("FFTAnalysis"), dict) else None,
        "ConfigurationFFT": {
            key: value
            for key, value in (metadata.get("Configuration") if isinstance(metadata.get("Configuration"), dict) else {}).items()
            if "FFT" in key.upper()
        },
        "RawFftCandidate": True,
    }
    blob_parts = [
        "Raw Data FFT Candidate",
        RAW_FFT_CANDIDATE_MODE,
        "raw data",
        raw_path.name,
        str(raw_path),
        run_folder.name,
        str(run_folder),
        sample,
        experiment_tag,
        description,
        " ".join(tags),
        measurement_note,
        "custom fft",
        "customized fft",
        "raw-backed fft",
        f"raw_files_{raw_file_count}",
        json.dumps(summary, sort_keys=True),
    ]
    return FftArtifact(
        root_path=root_path,
        run_folder=run_folder,
        path=raw_path,
        artifact_type="raw",
        mode=RAW_FFT_CANDIDATE_MODE,
        title="Raw Data FFT Candidate",
        sample=sample,
        experiment_tag=experiment_tag,
        description=description,
        tags=", ".join(tags),
        measurement_note=measurement_note,
        raw_file_count=raw_file_count,
        raw_total_bytes=raw_total_bytes,
        run_timestamp=run_timestamp,
        metadata_json=json.dumps(metadata_subset, ensure_ascii=False, sort_keys=True),
        summary_json=json.dumps(summary, ensure_ascii=False, sort_keys=True),
        search_blob=" ".join(part for part in blob_parts if part).lower(),
    )


def build_artifact(root_path: Path, path: Path) -> FftArtifact:
    run_folder = infer_run_folder(path)
    metadata = read_run_metadata(run_folder)
    tags = safe_tags(metadata.get("Tags"))
    mode = infer_mode(path)
    artifact_type = infer_artifact_type(path)
    title = infer_title(path, mode)
    summary = summarize_artifact(path)
    raw_file_count, raw_total_bytes, raw_files = summarize_raw_files(run_folder)
    summary["raw_file_count"] = raw_file_count
    summary["raw_total_bytes"] = raw_total_bytes
    summary["raw_total_gb"] = round(raw_total_bytes / (1024**3), 3)
    summary["raw_files"] = raw_files
    sample = safe_text(metadata.get("Sample"))
    experiment_tag = safe_text(
        metadata.get("ExperimentTag")
        or metadata.get("ExpTag")
        or nested_value(metadata, "Configuration", "ExperimentTag")
        or nested_value(metadata, "PhysicsData", "ExperimentTag")
    )
    description = safe_text(metadata.get("Description"))
    measurement_note = build_measurement_note(
        metadata,
        sample,
        experiment_tag,
        description,
        tags,
        raw_file_count,
        raw_total_bytes,
    )
    run_timestamp = parse_run_timestamp(run_folder, metadata)
    metadata_subset = {
        "Sample": sample,
        "ExperimentTag": experiment_tag,
        "Description": description,
        "MeasurementNote": measurement_note,
        "MeasurementChannelCount": MEASUREMENT_CHANNEL_COUNT,
        "MeasurementChannelLayout": MEASUREMENT_CHANNEL_LAYOUT,
        "Tags": tags,
        "RunTimestamp": run_timestamp,
        "FFTAnalysis": metadata.get("FFTAnalysis") if isinstance(metadata.get("FFTAnalysis"), dict) else None,
        "ConfigurationFFT": {
            key: value
            for key, value in (metadata.get("Configuration") if isinstance(metadata.get("Configuration"), dict) else {}).items()
            if "FFT" in key.upper()
        },
    }
    blob_parts = [
        title,
        mode,
        artifact_type,
        path.name,
        str(path),
        run_folder.name,
        str(run_folder),
        sample,
        experiment_tag,
        description,
        " ".join(tags),
        measurement_note,
        "raw_data" if raw_file_count else "",
        f"raw_files_{raw_file_count}" if raw_file_count else "",
        json.dumps(summary, sort_keys=True),
    ]
    return FftArtifact(
        root_path=root_path,
        run_folder=run_folder,
        path=path,
        artifact_type=artifact_type,
        mode=mode,
        title=title,
        sample=sample,
        experiment_tag=experiment_tag,
        description=description,
        tags=", ".join(tags),
        measurement_note=measurement_note,
        raw_file_count=raw_file_count,
        raw_total_bytes=raw_total_bytes,
        run_timestamp=run_timestamp,
        metadata_json=json.dumps(metadata_subset, ensure_ascii=False, sort_keys=True),
        summary_json=json.dumps(summary, ensure_ascii=False, sort_keys=True),
        search_blob=" ".join(part for part in blob_parts if part).lower(),
    )


def root_key(root_path: Path) -> str:
    return str(root_path.expanduser().resolve()).lower()


def ensure_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fft_artifacts (
                root_key TEXT NOT NULL,
                root_path TEXT NOT NULL,
                run_folder TEXT NOT NULL,
                run_name TEXT NOT NULL,
                artifact_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                artifact_type TEXT NOT NULL,
                mode TEXT NOT NULL,
                title TEXT NOT NULL,
                sample TEXT NOT NULL,
                experiment_tag TEXT NOT NULL,
                description TEXT NOT NULL,
                tags TEXT NOT NULL,
                measurement_note TEXT NOT NULL DEFAULT '',
                raw_file_count INTEGER NOT NULL DEFAULT 0,
                raw_total_bytes INTEGER NOT NULL DEFAULT 0,
                run_timestamp TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                search_blob TEXT NOT NULL,
                indexed_at_utc TEXT NOT NULL,
                PRIMARY KEY (root_key, artifact_path)
            )
            """
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(fft_artifacts)").fetchall()}
        if "raw_file_count" not in columns:
            conn.execute("ALTER TABLE fft_artifacts ADD COLUMN raw_file_count INTEGER NOT NULL DEFAULT 0")
        if "raw_total_bytes" not in columns:
            conn.execute("ALTER TABLE fft_artifacts ADD COLUMN raw_total_bytes INTEGER NOT NULL DEFAULT 0")
        if "measurement_note" not in columns:
            conn.execute("ALTER TABLE fft_artifacts ADD COLUMN measurement_note TEXT NOT NULL DEFAULT ''")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fft_root_time ON fft_artifacts(root_key, run_timestamp DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fft_root_mode ON fft_artifacts(root_key, mode, artifact_type)")
        conn.execute("CREATE TABLE IF NOT EXISTS roots (root_key TEXT PRIMARY KEY, root_path TEXT NOT NULL, indexed_at_utc TEXT NOT NULL, artifact_count INTEGER NOT NULL)")


def rebuild_index(root_path: Path, db_path: Path = DEFAULT_DB_PATH) -> list[FftArtifact]:
    root_path = root_path.expanduser().resolve()
    ensure_db(db_path)
    artifacts = [build_artifact(root_path, path) for path in discover_fft_files(root_path)]
    artifacts.extend(build_raw_candidate_artifact(root_path, folder) for folder in discover_raw_candidate_folders(root_path))
    indexed_at = datetime.now(UTC).replace(tzinfo=None).isoformat(timespec="seconds")
    key = root_key(root_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM fft_artifacts WHERE root_key = ?", (key,))
        conn.executemany(
            """
            INSERT INTO fft_artifacts (
                root_key, root_path, run_folder, run_name, artifact_path, file_name,
                artifact_type, mode, title, sample, experiment_tag, description, tags,
                measurement_note,
                raw_file_count, raw_total_bytes,
                run_timestamp, metadata_json, summary_json, search_blob, indexed_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    key,
                    str(item.root_path),
                    str(item.run_folder),
                    item.run_folder.name,
                    str(item.path),
                    item.path.name,
                    item.artifact_type,
                    item.mode,
                    item.title,
                    item.sample,
                    item.experiment_tag,
                    item.description,
                    item.tags,
                    item.measurement_note,
                    item.raw_file_count,
                    item.raw_total_bytes,
                    item.run_timestamp,
                    item.metadata_json,
                    item.summary_json,
                    item.search_blob,
                    indexed_at,
                )
                for item in artifacts
            ],
        )
        conn.execute(
            """
            INSERT INTO roots(root_key, root_path, indexed_at_utc, artifact_count)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(root_key) DO UPDATE SET
                root_path=excluded.root_path,
                indexed_at_utc=excluded.indexed_at_utc,
                artifact_count=excluded.artifact_count
            """,
            (key, str(root_path), indexed_at, len(artifacts)),
        )
    return artifacts


def search_index(
    query: str,
    *,
    root_path: Path = DEFAULT_ROOT,
    db_path: Path = DEFAULT_DB_PATH,
    mode: str | None = None,
    artifact_type: str | None = None,
    raw_only: bool = False,
    limit: int = 25,
) -> list[sqlite3.Row]:
    ensure_db(db_path)
    clauses = ["root_key = ?"]
    values: list[object] = [root_key(root_path)]
    if query.strip():
        tokens = [token.lower() for token in query.split() if token.strip()]
        for token in tokens:
            clauses.append("search_blob LIKE ?")
            values.append(f"%{token}%")
    if mode:
        clauses.append("mode = ?")
        values.append(mode)
    if artifact_type:
        clauses.append("artifact_type = ?")
        values.append(artifact_type)
    if raw_only:
        clauses.append("raw_file_count > 0")
    values.append(limit)
    sql = f"""
        SELECT *
        FROM fft_artifacts
        WHERE {' AND '.join(clauses)}
        ORDER BY run_timestamp DESC, artifact_path
        LIMIT ?
    """
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(sql, values).fetchall()


def index_info(root_path: Path = DEFAULT_ROOT, db_path: Path = DEFAULT_DB_PATH) -> dict[str, object]:
    ensure_db(db_path)
    key = root_key(root_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM roots WHERE root_key = ?", (key,)).fetchone()
    return dict(row) if row else {"root_path": str(root_path), "artifact_count": 0, "indexed_at_utc": ""}


def measurement_notes(
    *,
    root_path: Path = DEFAULT_ROOT,
    db_path: Path = DEFAULT_DB_PATH,
    raw_only: bool = True,
) -> list[dict[str, object]]:
    ensure_db(db_path)
    clauses = ["root_key = ?"]
    values: list[object] = [root_key(root_path)]
    if raw_only:
        clauses.append("raw_file_count > 0")
    sql = f"""
        SELECT *
        FROM fft_artifacts
        WHERE {' AND '.join(clauses)}
        ORDER BY run_timestamp DESC, artifact_path
    """
    grouped: dict[str, dict[str, object]] = {}
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, values).fetchall()

    for row in rows:
        run_name = row["run_name"]
        item = grouped.setdefault(
            run_name,
            {
                "run_name": run_name,
                "run_timestamp": row["run_timestamp"],
                "sample": row["sample"],
                "description": row["description"],
                "tags": row["tags"],
                "measurement_note": row["measurement_note"],
                "raw_file_count": row["raw_file_count"],
                "raw_total_gb": round(row["raw_total_bytes"] / (1024**3), 3),
                "modes": set(),
                "artifact_count": 0,
                "run_folder": row["run_folder"],
            },
        )
        item["artifact_count"] = int(item["artifact_count"]) + 1
        item["modes"].add(row["mode"])

    notes: list[dict[str, object]] = []
    for item in grouped.values():
        converted = dict(item)
        converted["modes"] = ", ".join(sorted(converted["modes"]))
        notes.append(converted)
    return notes


def print_table(rows: list[sqlite3.Row]) -> None:
    if not rows:
        print("No FFT artifacts matched.")
        return
    headers = ["Run", "Mode", "Type", "Raw", "Title", "Note", "Path"]
    records = [
        [
            row["run_name"],
            row["mode"],
            row["artifact_type"],
            row["raw_file_count"],
            row["title"],
            row["measurement_note"],
            row["artifact_path"],
        ]
        for row in rows
    ]
    max_widths = [15, 14, 5, 3, 28, 64, 40]
    widths = [
        min(max_widths[index], max(len(headers[index]), *(len(str(record[index])) for record in records)))
        for index in range(len(headers))
    ]
    print("  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for record in records:
        cells = []
        for index, value in enumerate(record):
            text = str(value)
            if len(text) > widths[index]:
                text = text[: max(0, widths[index] - 3)] + "..."
            cells.append(text.ljust(widths[index]))
        print("  ".join(cells))


def print_notes_table(notes: list[dict[str, object]]) -> None:
    if not notes:
        print("No measurement notes matched.")
        return
    headers = ["Run", "RawGB", "Modes", "Artifacts", "Note"]
    records = [
        [
            item["run_name"],
            item["raw_total_gb"],
            item["modes"],
            item["artifact_count"],
            item["measurement_note"],
        ]
        for item in notes
    ]
    max_widths = [15, 8, 36, 9, 100]
    widths = [
        min(max_widths[index], max(len(headers[index]), *(len(str(record[index])) for record in records)))
        for index in range(len(headers))
    ]
    print("  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for record in records:
        cells = []
        for index, value in enumerate(record):
            text = str(value)
            if len(text) > widths[index]:
                text = text[: max(0, widths[index] - 3)] + "..."
            cells.append(text.ljust(widths[index]))
        print("  ".join(cells))


def write_notes_csv(notes: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "run_name",
        "run_timestamp",
        "sample",
        "description",
        "tags",
        "measurement_note",
        "raw_file_count",
        "raw_total_gb",
        "modes",
        "artifact_count",
        "run_folder",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(notes)


def write_notes_to_run_metadata(notes: list[dict[str, object]]) -> int:
    updated_count = 0
    timestamp = datetime.now(UTC).replace(tzinfo=None).isoformat(timespec="seconds")
    for item in notes:
        metadata_path = Path(str(item["run_folder"])) / "metadata.json"
        try:
            if metadata_path.is_file():
                payload = json.loads(metadata_path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    payload = {}
            else:
                payload = {}
        except Exception:
            payload = {}

        note = str(item["measurement_note"])
        payload["FFTMeasurementNote"] = note
        analysis = payload.get("FFTAnalysis")
        if not isinstance(analysis, dict):
            analysis = {}
        analysis.update(
            {
                "MeasurementNote": note,
                "MeasurementNoteUpdatedAt": timestamp,
                "MeasurementChannelCount": MEASUREMENT_CHANNEL_COUNT,
                "MeasurementChannelLayout": MEASUREMENT_CHANNEL_LAYOUT,
                "RawBackedMeasurement": int(item["raw_file_count"]) > 0,
                "RawDataFileCount": int(item["raw_file_count"]),
                "RawDataTotalGB": item["raw_total_gb"],
                "SearchableModes": str(item["modes"]).split(", ") if item["modes"] else [],
                "IndexedArtifactCount": int(item["artifact_count"]),
            }
        )
        payload["FFTAnalysis"] = analysis
        metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        updated_count += 1
    return updated_count


def print_json(rows: list[sqlite3.Row]) -> None:
    payload = []
    for row in rows:
        item = dict(row)
        item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
        item["summary"] = json.loads(item.pop("summary_json") or "{}")
        payload.append(item)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def open_artifact(path: str) -> None:
    if os.name == "nt":
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        raise RuntimeError("Opening files is only implemented for Windows in this script.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and search an FFT-only metadata index for DataFiles results.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help=f"DataFiles root. Default: {DEFAULT_ROOT}")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help=f"SQLite index path. Default: {DEFAULT_DB_PATH}")
    subparsers = parser.add_subparsers(dest="command")

    rebuild = subparsers.add_parser("rebuild", help="Scan the DataFiles root and rebuild the FFT metadata index.")
    rebuild.add_argument("--json", action="store_true", help="Print index info as JSON.")

    search = subparsers.add_parser("search", help="Search the FFT metadata index.")
    search.add_argument("query", nargs="*", help="Search terms. All terms must match.")
    search.add_argument("--mode", choices=["low_frequency", "high_frequency", "peaks", "raw_std", "spectrum", RAW_FFT_CANDIDATE_MODE, "unknown"], help="Filter by FFT mode/category.")
    search.add_argument("--type", choices=["plot", "csv"], dest="artifact_type", help="Filter by artifact type.")
    search.add_argument("--raw-only", action="store_true", help="Only show FFT artifacts from folders that still contain Data_*.bin raw files.")
    search.add_argument("--limit", type=int, default=25, help="Maximum rows to show.")
    search.add_argument("--json", action="store_true", help="Print full result metadata as JSON.")
    search.add_argument("--open-first", action="store_true", help="Open the first matching artifact.")

    notes = subparsers.add_parser("notes", help="Show one reminder note per measurement.")
    notes.add_argument("--all", action="store_true", help="Include measurements without raw Data_*.bin files.")
    notes.add_argument("--csv", type=Path, help="Write the notes table to CSV.")
    notes.add_argument("--write-metadata", action="store_true", help="Add the generated note to each run's metadata.json.")

    subparsers.add_parser("info", help="Show current FFT metadata index status.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    command = args.command or "search"

    if command == "rebuild":
        artifacts = rebuild_index(args.root, args.db)
        info = index_info(args.root, args.db)
        if args.json:
            print(json.dumps(info, indent=2))
        else:
            print(f"Indexed {len(artifacts)} FFT artifacts under {args.root}")
            print(f"Index: {args.db}")
        return

    if command == "info":
        print(json.dumps(index_info(args.root, args.db), indent=2))
        return

    if command == "notes":
        info = index_info(args.root, args.db)
        if not info.get("indexed_at_utc"):
            rebuild_index(args.root, args.db)
        notes = measurement_notes(
            root_path=args.root,
            db_path=args.db,
            raw_only=not getattr(args, "all", False),
        )
        print_notes_table(notes)
        if getattr(args, "csv", None):
            write_notes_csv(notes, args.csv)
            print(f"\nWrote {len(notes)} measurement notes to {args.csv}")
        if getattr(args, "write_metadata", False):
            updated_count = write_notes_to_run_metadata(notes)
            print(f"Updated FFTMeasurementNote in {updated_count} metadata.json files")
        return

    if command == "search":
        info = index_info(args.root, args.db)
        if not info.get("indexed_at_utc"):
            rebuild_index(args.root, args.db)
        query = " ".join(getattr(args, "query", []))
        rows = search_index(
            query,
            root_path=args.root,
            db_path=args.db,
            mode=getattr(args, "mode", None),
            artifact_type=getattr(args, "artifact_type", None),
            raw_only=getattr(args, "raw_only", False),
            limit=max(1, getattr(args, "limit", 25)),
        )
        if getattr(args, "json", False):
            print_json(rows)
        else:
            print_table(rows)
        if getattr(args, "open_first", False) and rows:
            open_artifact(rows[0]["artifact_path"])
        return

    parser.print_help()


if __name__ == "__main__":
    main()
