from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

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
DARK_NOISE_TAG_PORT_POWER_ESTIMATE_MW = 0.01
DARK_NOISE_TAG_POWER_ESTIMATE_MW = DARK_NOISE_TAG_PORT_POWER_ESTIMATE_MW * 2.0
DARK_NOISE_SYNTHETIC_WAVELENGTH_NM = 1550.0
DARK_NOISE_SYNTHETIC_RESPONSIVITY_A_PER_W = 1.02
DARK_NOISE_SYNTHETIC_REFERENCE_RESPONSIVITY_A_PER_W = 1.02
DARK_NOISE_SYNTHETIC_DETECTOR_VOLTAGE_PER_MW = 10.0
DARK_NOISE_SYNTHETIC_REP_RATE_HZ = 7.6e7
DARK_NOISE_SYNTHETIC_RESPONSE_TIME_S = 3.5e-9
DARK_NOISE_TAG_NAME = "Dark Noise"
DARK_NOISE_TAG_KEY = "dark noise"


def estimate_dark_noise_synthetic_conversion_factor_v2_rad2(
    port_power_mw: float = DARK_NOISE_TAG_PORT_POWER_ESTIMATE_MW,
    wavelength_nm: float = DARK_NOISE_SYNTHETIC_WAVELENGTH_NM,
    responsivity_a_per_w: float = DARK_NOISE_SYNTHETIC_RESPONSIVITY_A_PER_W,
    reference_responsivity_a_per_w: float = DARK_NOISE_SYNTHETIC_REFERENCE_RESPONSIVITY_A_PER_W,
    detector_voltage_per_mw: float = DARK_NOISE_SYNTHETIC_DETECTOR_VOLTAGE_PER_MW,
    rep_rate_hz: float = DARK_NOISE_SYNTHETIC_REP_RATE_HZ,
    response_time_s: float = DARK_NOISE_SYNTHETIC_RESPONSE_TIME_S,
) -> float:
    planck_constant = 6.62607015e-34
    speed_of_light = 299792458.0
    photon_energy_j = planck_constant * speed_of_light / (wavelength_nm * 1e-9)
    port_power_w = port_power_mw * 1e-3
    photons_per_pulse = port_power_w / (photon_energy_j * rep_rate_hz)
    sensitivity = (
        responsivity_a_per_w
        * photon_energy_j
        / response_time_s
        * detector_voltage_per_mw
        * 1e3
        / reference_responsivity_a_per_w
    )
    conversion_per_port = 2.0 * photons_per_pulse * sensitivity
    return conversion_per_port * conversion_per_port


DARK_NOISE_SYNTHETIC_CONVERSION_FACTOR_V2_RAD2 = estimate_dark_noise_synthetic_conversion_factor_v2_rad2()


def dark_noise_synthetic_note(factor: float | None = None) -> str:
    value = factor if factor is not None and factor > 0 else DARK_NOISE_SYNTHETIC_CONVERSION_FACTOR_V2_RAD2
    return (
        f"{DARK_NOISE_TAG_NAME} tag: synthetic conversion factor {value:.6g} V^2/rad^2 applied "
        f"from {DARK_NOISE_SYNTHETIC_WAVELENGTH_NM:g} nm, "
        f"{DARK_NOISE_TAG_PORT_POWER_ESTIMATE_MW:g} mW per detector port; "
        "results shown in artificial urad^2"
    )


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
    polarizer_used: bool | None = None
    polarizer_name: str = ""
    polarizer_extinction_ratio: str = ""
    scan_range_mm: float | None = None
    scan_min_mm: float | None = None
    scan_max_mm: float | None = None
    scan_velocity_mm_s: float | None = None
    synthetic_conversion_factor_applied: bool = False
    synthetic_conversion_factor_v2_rad2: float | None = None

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
    def scan_velocity_display_mm_s(self) -> str:
        if self.physics.scan_velocity_mm_s is None:
            return "-"
        return f"{self.physics.scan_velocity_mm_s:.4g}"

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
        if (
            self.physics.synthetic_conversion_factor_applied
            and self.physics.synthetic_conversion_factor_v2_rad2
            and self.physics.synthetic_conversion_factor_v2_rad2 > 0
            and self.physics.shot_noise_v2_rthz is not None
            and self.physics.shot_noise_urad2_rthz is None
        ):
            return f"{self.physics.shot_noise_v2_rthz / self.physics.synthetic_conversion_factor_v2_rad2 * 1e12:.2f}"
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
        if (
            self.physics.synthetic_conversion_factor_applied
            and self.physics.synthetic_conversion_factor_v2_rad2
            and self.physics.synthetic_conversion_factor_v2_rad2 > 0
            and self.physics.shot_noise_v2_rthz is not None
            and self.physics.shot_noise_urad2_rthz is None
        ):
            return "urad^2/rtHz"
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
    def polarizer_display(self) -> str:
        if self.physics.polarizer_used is False:
            return "No"
        name = self.physics.polarizer_name.strip()
        ratio = self.physics.polarizer_extinction_ratio.strip()
        if self.physics.polarizer_used is None and not name and not ratio:
            return "-"
        parts = []
        if self.physics.polarizer_used is True:
            parts.append("Yes")
        if name:
            parts.append(name)
        if ratio:
            parts.append(f"ER {ratio}")
        return " / ".join(parts) if parts else "Yes"

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


def has_dark_noise_tag(tags: list[str]) -> bool:
    normalized = {" ".join(tag.strip().lower().replace("_", " ").replace("-", " ").split()) for tag in tags}
    return DARK_NOISE_TAG_KEY in normalized


def canonicalize_dark_noise_tags(tags: list[str]) -> list[str]:
    result: list[str] = []
    has_dark_noise = False
    for tag in tags:
        normalized = " ".join(tag.strip().lower().replace("_", " ").replace("-", " ").split())
        if normalized == DARK_NOISE_TAG_KEY:
            has_dark_noise = True
            continue
        if tag.strip():
            result.append(tag.strip())
    if has_dark_noise:
        result.append(DARK_NOISE_TAG_NAME)
    return result


def apply_dark_noise_tag_power_estimate(record: RunRecord) -> None:
    if not has_dark_noise_tag(record.tags):
        return
    record.physics.sample_power_mw = DARK_NOISE_TAG_POWER_ESTIMATE_MW
    record.physics.power_mw_1 = DARK_NOISE_TAG_PORT_POWER_ESTIMATE_MW
    record.physics.power_mw_2 = DARK_NOISE_TAG_PORT_POWER_ESTIMATE_MW
    record.physics.is_dark_noise_run = True
    record.physics.synthetic_conversion_factor_applied = True
    record.physics.synthetic_conversion_factor_v2_rad2 = DARK_NOISE_SYNTHETIC_CONVERSION_FACTOR_V2_RAD2


def dark_noise_note(record: RunRecord) -> str:
    if not record.physics.synthetic_conversion_factor_applied and not has_dark_noise_tag(record.tags):
        return ""
    return dark_noise_synthetic_note(record.physics.synthetic_conversion_factor_v2_rad2)


def apply_dark_noise_metadata_config(payload: dict[str, object]) -> bool:
    tags = canonicalize_dark_noise_tags(safe_tags(payload.get("Tags")))
    if not has_dark_noise_tag(tags):
        return False
    payload["Tags"] = tags
    physics_value = payload.get("PhysicsData")
    physics = physics_value if isinstance(physics_value, dict) else {}
    updated = dict(physics)
    updated["Power_mW_1"] = DARK_NOISE_TAG_PORT_POWER_ESTIMATE_MW
    updated["Power_mW_2"] = DARK_NOISE_TAG_PORT_POWER_ESTIMATE_MW
    updated["OnSamplePower_mW"] = DARK_NOISE_TAG_POWER_ESTIMATE_MW
    updated["DarkNoiseTagPowerEstimate_mW"] = DARK_NOISE_TAG_POWER_ESTIMATE_MW
    updated["DarkNoiseTagPortPowerEstimate_mW"] = DARK_NOISE_TAG_PORT_POWER_ESTIMATE_MW
    updated["DarkNoiseSyntheticWavelength_nm"] = DARK_NOISE_SYNTHETIC_WAVELENGTH_NM
    updated["DarkNoiseSyntheticDetectorResponsivity_A_per_W"] = DARK_NOISE_SYNTHETIC_RESPONSIVITY_A_PER_W
    updated["DarkNoiseSyntheticRepRate_Hz"] = DARK_NOISE_SYNTHETIC_REP_RATE_HZ
    updated["DarkNoiseSyntheticResponseTime_s"] = DARK_NOISE_SYNTHETIC_RESPONSE_TIME_S
    updated["IsDarkNoiseRun"] = True
    updated["DarkNoiseLabel"] = DARK_NOISE_TAG_NAME
    updated["DarkNoiseReason"] = (
        f"metadata tag {DARK_NOISE_TAG_NAME} uses {DARK_NOISE_TAG_PORT_POWER_ESTIMATE_MW:g} mW per detector port "
        f"at {DARK_NOISE_SYNTHETIC_WAVELENGTH_NM:g} nm and synthetic conversion factor "
        f"{DARK_NOISE_SYNTHETIC_CONVERSION_FACTOR_V2_RAD2:.6g} V^2/rad^2"
    )
    updated["DisplayAmplitudeUnit"] = "urad^2"
    updated["SyntheticConversionFactorApplied"] = True
    updated["SyntheticConversionFactor_V2_rad2"] = DARK_NOISE_SYNTHETIC_CONVERSION_FACTOR_V2_RAD2
    updated["SyntheticConversionFactorNote"] = dark_noise_synthetic_note()
    payload["PhysicsData"] = updated
    return updated != physics


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


def metadata_polarizer_used(payload: dict[str, object]) -> bool | None:
    value = first_matching_value(
        payload,
        [
            ("PhysicsData", "PolarizerUsed"),
            ("PhysicsData", "UsePolarizer"),
            ("PhysicsData", "PolarizerApplied"),
            ("Configuration", "PolarizerUsed"),
            ("Configuration", "UsePolarizer"),
            ("PolarizerUsed",),
            ("UsePolarizer",),
            ("PolarizerApplied",),
        ],
    )
    if value is None:
        return None
    return safe_bool(value)


def metadata_polarizer_name(payload: dict[str, object]) -> str:
    return safe_text(
        first_matching_value(
            payload,
            [
                ("PhysicsData", "Polarizer"),
                ("PhysicsData", "PolarizerName"),
                ("Configuration", "Polarizer"),
                ("Configuration", "PolarizerName"),
                ("Polarizer",),
                ("PolarizerName",),
            ],
        )
    )


def metadata_polarizer_extinction_ratio(payload: dict[str, object]) -> str:
    return safe_text(
        first_matching_value(
            payload,
            [
                ("PhysicsData", "PolarizerExtinctionRatio"),
                ("PhysicsData", "PolarizerExtinctionRatioText"),
                ("PhysicsData", "ExtinctionRatio"),
                ("Configuration", "PolarizerExtinctionRatio"),
                ("Configuration", "ExtinctionRatio"),
                ("PolarizerExtinctionRatio",),
                ("ExtinctionRatio",),
            ],
        )
    )


def metadata_scan_velocity_mm_s(payload: dict[str, object]) -> float | None:
    return first_matching_float(
        payload,
        [
            ("PhysicsData", "ScanVelocity_mm_s"),
            ("PhysicsData", "ScanRate_mm_s"),
            ("PhysicsData", "ESPScanVelocity_mm_s"),
            ("Configuration", "ScanVelocity_mm_s"),
            ("Configuration", "ScanRate_mm_s"),
            ("Configuration", "ESPScanVelocity_mm_s"),
            ("ScanVelocity_mm_s",),
            ("ScanRate_mm_s",),
            ("ESPScanVelocity_mm_s",),
        ],
    )


def apply_browser_metadata_fields(record: RunRecord, payload: dict[str, object]) -> None:
    record.physics.use_opo = metadata_use_opo(payload)
    record.physics.laser_wavelength_nm = metadata_laser_wavelength_nm(payload)
    record.physics.polarizer_used = metadata_polarizer_used(payload)
    record.physics.polarizer_name = metadata_polarizer_name(payload)
    record.physics.polarizer_extinction_ratio = metadata_polarizer_extinction_ratio(payload)
    record.physics.scan_velocity_mm_s = metadata_scan_velocity_mm_s(payload)


def build_search_blob(run: RunRecord) -> str:
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
        run.polarizer_display,
        run.wavelength_display_nm,
        run.scan_velocity_display_mm_s,
        run.environment_temperature_display_k,
        run.shot_noise_display,
        "star" if run.star_measurement else "",
    ]
    return " ".join(part for part in search_parts if part).lower()


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
            if apply_dark_noise_metadata_config(payload):
                normalized_payload = normalize_metadata(payload)
                record.metadata_path.write_text(json.dumps(normalized_payload, indent=2), encoding="utf-8")
                record.metadata_text = json.dumps(normalized_payload, indent=2)
                payload = normalized_payload
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
                        ("PhysicsData", "StarMeasurement"),
                        ("PhysicsData", "StarredMeasurement"),
                        ("PhysicsData", "IsStarMeasurement"),
                        ("PhysicsData", "IsStarred"),
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
                scan_velocity_mm_s=metadata_scan_velocity_mm_s(payload),
                synthetic_conversion_factor_applied=safe_bool(physics.get("SyntheticConversionFactorApplied")),
                synthetic_conversion_factor_v2_rad2=safe_float(physics.get("SyntheticConversionFactor_V2_rad2")),
            )
            apply_browser_metadata_fields(record, payload)
            apply_dark_noise_tag_power_estimate(record)
        except Exception:
            record.metadata_text = "Could not parse metadata.json"
    else:
        record.metadata_text = "No metadata.json found for this run."

    record.search_blob = build_search_blob(record)
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
            if run.metadata_path and run.metadata_path.is_file():
                current_metadata_text = run.metadata_path.read_text(encoding="utf-8")
                if current_metadata_text != run.metadata_text:
                    run = load_run_record(run.final_result_path)
            payload = normalize_metadata(json.loads(run.metadata_text))
            apply_browser_metadata_fields(run, payload)
            apply_dark_noise_tag_power_estimate(run)
        except Exception:
            pass
        run.search_blob = build_search_blob(run)
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
        "polarizer": run.polarizer_display,
        "wavelength_nm": run.wavelength_display_nm,
        "wavelength_nm_sort": run.physics.laser_wavelength_nm,
        "temperature": run.environment_temperature_display_k,
        "shot_noise": run.shot_noise_display,
        "shot_noise_value": run.shot_noise_value_display,
        "dark_noise_note": dark_noise_note(run),
        "scan_range": run.scan_range_display,
        "scan_rate": run.scan_velocity_display_mm_s,
        "scan_rate_sort": run.physics.scan_velocity_mm_s,
        "center": run.center_display,
        "final_result_path": str(run.final_result_path) if run.final_result_path else "",
        "movie_path": str(run.movie_path) if run.movie_path else "",
        "loglog_plot_path": str(run.loglog_plot_path) if run.loglog_plot_path else "",
        "diagonal_offset_path": str(run.diagonal_offset_path) if run.diagonal_offset_path else "",
        "raw_std_plot_path": str(run.raw_std_plot_path) if run.raw_std_plot_path else "",
        "metadata_path": str(run.metadata_path) if run.metadata_path else "",
        "metadata_text": run.metadata_text,
    }


def html_browser_page() -> str:
    index_path = Path(__file__).with_name("index.html")
    if not index_path.is_file():
        raise FileNotFoundError(f"index.html was not found next to datafiles_browser.py: {index_path}")
    return index_path.read_text(encoding="utf-8")


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
        "progress_percent": 0,
        "current_run": 0,
        "total_runs": 0,
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
        command = [sys.executable, str(script_path), "--force", *[str(path) for path in folder_paths]]
        output_lines: list[str] = []
        return_code = -1
        total_runs = max(1, len(folder_paths))
        current_run = 0
        current_run_percent = 0

        def combined_progress() -> int:
            completed_runs = max(0, current_run - 1)
            return max(0, min(99, round(((completed_runs + current_run_percent / 100.0) / total_runs) * 100)))

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
                run_match = re.match(r"\[(\d+)/(\d+)\]\s+Processing\s+(.+)", line)
                progress_match = re.match(r"PROGRESS\s+(\d+)\s*(.*)", line)
                if run_match:
                    current_run = int(run_match.group(1))
                    total_runs = max(1, int(run_match.group(2)))
                    current_run_percent = 0
                elif progress_match:
                    current_run_percent = max(0, min(100, int(progress_match.group(1))))
                display_line = progress_match.group(2).strip() if progress_match else line
                output_lines.append(line)
                if len(output_lines) > 80:
                    output_lines = output_lines[-80:]
                with analysis_lock:
                    analysis_state["message"] = display_line or line
                    analysis_state["progress_percent"] = combined_progress()
                    analysis_state["current_run"] = current_run
                    analysis_state["total_runs"] = total_runs
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
                    "progress_percent": 100 if return_code == 0 else combined_progress(),
                    "current_run": total_runs if return_code == 0 else current_run,
                    "total_runs": total_runs,
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
                                "progress_percent": 0,
                                "current_run": 0,
                                "total_runs": len(folder_paths),
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
                    star = safe_bool(data.get("star", False))
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
    args = parser.parse_args()

    launch_html_browser(args.root)


if __name__ == "__main__":
    main()
