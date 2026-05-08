from __future__ import annotations

import argparse
import copy
import json
import math
import shutil
import re
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path(r"D:\Quantum Squeezing Project\DataFiles")
ATTENUATOR_KEYS = (
    "PowerDetectorAttenuatorApplied",
    "PowerDetectorAttenuatorCount",
    "PowerDetectorAttenuatorEach_dB",
    "PowerDetectorAttenuatorTotal_dB",
    "PowerDetectorAttenuatorCorrectionFactor",
)


def metadata_paths(root: Path) -> list[Path]:
    if root.name.lower() == "metadata.json":
        return [root]
    return sorted(root.rglob("metadata.json"))


def as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in {"1", "true", "yes", "y", "on"}:
            return True
        if cleaned in {"0", "false", "no", "n", "off"}:
            return False
    return None


def as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def read_sensitivity_attenuator(run_folder: Path) -> tuple[bool | None, float | None]:
    path = run_folder / "sensitivity.log"
    if not path.is_file():
        return None, None
    text = path.read_text(encoding="utf-8", errors="ignore")
    applied_matches = re.findall(
        r"(?:Power Detector|Gage Signal|Gage signal) Attenuator Applied\s*=\s*(true|false|1|0|yes|no|on|off)",
        text,
        flags=re.IGNORECASE,
    )
    total_matches = re.findall(r"Total\s*=\s*([\d\.E\+\-]+)\s*dB", text, flags=re.IGNORECASE)

    applied = as_bool(applied_matches[-1]) if applied_matches else None
    total_db = as_float(total_matches[-1]) if total_matches else None
    return applied, total_db


def set_if_changed(container: dict[str, Any], key: str, value: Any, changes: list[str], prefix: str) -> None:
    old_value = container.get(key)
    if old_value != value:
        container[key] = value
        changes.append(f"{prefix}{key}: {old_value!r} -> {value!r}")


def choose_applied(payload: dict[str, Any], log_applied: bool | None = None) -> bool:
    if log_applied is not None:
        return log_applied

    physics = payload.get("PhysicsData")
    candidates: list[Any] = []
    if isinstance(physics, dict):
        candidates.append(physics.get("PowerDetectorAttenuatorApplied"))
    candidates.append(payload.get("PowerDetectorAttenuatorApplied"))

    for candidate in candidates:
        value = as_bool(candidate)
        if value is not None:
            return value
    return False


def choose_total_db(payload: dict[str, Any], applied: bool, log_total_db: float | None = None) -> float:
    if not applied:
        return 0.0

    if log_total_db is not None and log_total_db > 0:
        return log_total_db

    physics = payload.get("PhysicsData")
    candidates: list[Any] = []
    if isinstance(physics, dict):
        candidates.append(physics.get("PowerDetectorAttenuatorTotal_dB"))
    candidates.append(payload.get("PowerDetectorAttenuatorTotal_dB"))

    for candidate in candidates:
        value = as_float(candidate)
        if value is not None and value > 0:
            return value
    return 40.0


def repair_attenuator_block(
    container: dict[str, Any],
    applied: bool,
    total_db: float,
    changes: list[str],
    prefix: str,
    force_create: bool,
) -> None:
    has_any_key = any(key in container for key in ATTENUATOR_KEYS)
    if not force_create and not has_any_key:
        return

    count = 2 if applied else 0
    each_db = total_db / count if applied and count else 0.0
    correction_factor = 10 ** (total_db / 20.0) if applied else 1.0

    set_if_changed(container, "PowerDetectorAttenuatorApplied", applied, changes, prefix)
    set_if_changed(container, "PowerDetectorAttenuatorCount", count, changes, prefix)
    set_if_changed(container, "PowerDetectorAttenuatorEach_dB", each_db, changes, prefix)
    set_if_changed(container, "PowerDetectorAttenuatorTotal_dB", total_db, changes, prefix)
    set_if_changed(
        container,
        "PowerDetectorAttenuatorCorrectionFactor",
        correction_factor,
        changes,
        prefix,
    )


def repair_payload(
    payload: dict[str, Any],
    log_applied: bool | None = None,
    log_total_db: float | None = None,
) -> tuple[dict[str, Any], list[str]]:
    repaired = copy.deepcopy(payload)
    changes: list[str] = []
    top_has_attenuator = any(key in repaired for key in ATTENUATOR_KEYS)
    physics_source = repaired.get("PhysicsData")
    physics_has_attenuator = isinstance(physics_source, dict) and any(key in physics_source for key in ATTENUATOR_KEYS)
    if not top_has_attenuator and not physics_has_attenuator and log_applied is None:
        return repaired, changes

    applied = choose_applied(repaired, log_applied)
    total_db = choose_total_db(repaired, applied, log_total_db)

    physics = repaired.get("PhysicsData")
    if not isinstance(physics, dict):
        physics = None

    repair_attenuator_block(repaired, applied, total_db, changes, "", force_create=top_has_attenuator)
    if isinstance(physics, dict):
        repair_attenuator_block(physics, applied, total_db, changes, "PhysicsData.", force_create=physics_has_attenuator or log_applied is not None)
    return repaired, changes


def repair_file(path: Path, write: bool, backup: bool) -> tuple[bool, list[str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("metadata.json does not contain a JSON object")

    log_applied, log_total_db = read_sensitivity_attenuator(path.parent)
    repaired, changes = repair_payload(payload, log_applied, log_total_db)
    changed = repaired != payload
    if changed and write:
        if backup:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.copy2(path, path.with_name(f"{path.name}.{timestamp}.bak"))
        path.write_text(json.dumps(repaired, indent=2), encoding="utf-8")
    return changed, changes


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Repair attenuation metadata so the correction factor is an amplitude factor: "
            "10^(total_dB/20)."
        )
    )
    parser.add_argument("root", nargs="?", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--write", action="store_true", help="Write changes. Default is dry-run.")
    parser.add_argument("--backup", action="store_true", help="Create metadata.json.TIMESTAMP.bak before writing.")
    parser.add_argument("--details", action="store_true", help="Print every field changed for every file.")
    args = parser.parse_args()

    paths = metadata_paths(args.root)
    changed_count = 0
    error_count = 0
    for path in paths:
        try:
            changed, changes = repair_file(path, write=args.write, backup=args.backup)
        except Exception as exc:
            error_count += 1
            print(f"ERROR {path}: {exc}")
            continue

        if not changed:
            continue

        changed_count += 1
        action = "updated" if args.write else "would update"
        print(f"{action}: {path}")
        if args.details:
            for change in changes:
                print(f"  - {change}")

    mode = "Updated" if args.write else "Would update"
    print(f"{mode} {changed_count} of {len(paths)} metadata files. Errors: {error_count}.")


if __name__ == "__main__":
    main()
