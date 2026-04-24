from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1


def safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return ", ".join(safe_text(item) for item in value if safe_text(item))
    return default


def safe_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [safe_text(item) for item in value if safe_text(item)]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def safe_float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def first_value(payload: dict[str, Any], *paths: tuple[str, ...]) -> Any:
    for path in paths:
        current: Any = payload
        for key in path:
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(key)
        if current not in (None, ""):
            return current
    return None


def normalize_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    physics_source = payload.get("PhysicsData")
    physics = dict(physics_source) if isinstance(physics_source, dict) else {}

    normalized["MetadataSchemaVersion"] = SCHEMA_VERSION
    normalized["Sample"] = safe_text(payload.get("Sample"))
    normalized["ExperimentTag"] = safe_text(
        first_value(
            payload,
            ("ExperimentTag",),
            ("ExpTag",),
            ("Experiment",),
            ("ExperimentName",),
            ("Configuration", "ExperimentTag"),
            ("Configuration", "ExpTag"),
            ("PhysicsData", "ExperimentTag"),
            ("PhysicsData", "ExpTag"),
        )
    )
    normalized["Description"] = safe_text(payload.get("Description"))
    normalized["Tags"] = safe_tags(payload.get("Tags"))
    normalized["Filename"] = safe_text(payload.get("Filename"))
    normalized["Duration"] = safe_text(payload.get("Duration"))

    for key in (
        "Power_mW_1",
        "Power_mW_2",
        "OnSamplePower_mW",
        "SamplePower_mW",
        "Temperature_K",
        "EnvironmentTemperature_K",
        "EnvironmentTemperature_C",
        "Sensitivity_V_photon",
        "ShotNoiseResult_urad2_rtHz",
        "ShotNoiseResult_V2_rtHz",
        "ScanRange_mm",
        "ScanMin_mm",
        "ScanMax_mm",
        "PowerDetectorAttenuatorTotal_dB",
        "PowerDetectorAttenuatorCorrectionFactor",
    ):
        value = safe_float_or_none(first_value(payload, ("PhysicsData", key), (key,)))
        if value is not None:
            physics[key] = value

    for key in ("PowerDetectorAttenuatorApplied", "IsDarkNoiseRun", "StarMeasurement"):
        value = first_value(payload, ("PhysicsData", key), (key,))
        if value is not None:
            if isinstance(value, str):
                value = value.strip().lower() in {"1", "true", "yes", "on"}
            else:
                value = bool(value)
            if key == "StarMeasurement":
                normalized[key] = value
            else:
                physics[key] = value

    normalized["PhysicsData"] = physics
    return normalized


def normalize_file(path: Path, write: bool = False) -> bool:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} does not contain a JSON object")

    normalized = normalize_metadata(payload)
    changed = normalized != payload
    if changed and write:
        path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize Quantum Measurement metadata.json files.")
    parser.add_argument("root", type=Path, help="Run folder or root folder containing run folders.")
    parser.add_argument("--write", action="store_true", help="Write normalized metadata files. Without this, only reports changes.")
    args = parser.parse_args()

    paths = [args.root] if args.root.name.lower() == "metadata.json" else list(args.root.rglob("metadata.json"))
    changed_count = 0
    for path in paths:
        try:
            changed = normalize_file(path, write=args.write)
        except Exception as exc:
            print(f"ERROR {path}: {exc}")
            continue
        if changed:
            changed_count += 1
            action = "updated" if args.write else "would update"
            print(f"{action}: {path}")

    mode = "Updated" if args.write else "Would update"
    print(f"{mode} {changed_count} of {len(paths)} metadata files.")


if __name__ == "__main__":
    main()
