from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Iterator

import matplotlib.pyplot as plt

# Support direct CLI execution while importing the shared processing pipeline.

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

import cm_pipeline_all_in_one as pipeline


ANALYSIS_VERSION = "2026-09-14-long-term-allan-deviation-v2"
DEFAULT_ROOT = Path(r"D:\Quantum Squeezing Project\DataFiles")
DEFAULT_BASE_TAU_S = 1.0
DEFAULT_MAX_POINTS = 60
DEFAULT_MAX_PAIRS = 9
MIN_LONG_TERM_SLOPE_POINTS = 4
LONG_TERM_SLOPE_POINTS = 8
TIMESTAMP_RE = re.compile(
    rb"start timestamp:\s*(\d{1,2}):(\d{2}):(\d{2})(?:\.(\d+))?",
    re.IGNORECASE,
)


def finite_or_none(value: float | int | np.floating | np.integer | None) -> float | int | None:
    if value is None:
        return None
    numeric = float(value)
    if not math.isfinite(numeric):
        return None
    if isinstance(value, (int, np.integer)):
        return int(value)
    return numeric


def atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    replace_with_retry(temporary, path)


def replace_with_retry(source: Path, destination: Path, attempts: int = 10) -> None:
    for attempt in range(attempts):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if attempt + 1 >= attempts:
                raise
            time.sleep(0.1 * (attempt + 1))


def metadata_payload(run_folder: Path) -> dict[str, object]:
    path = run_folder / "metadata.json"
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def nested_dict(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload.get(key)
    if isinstance(value, dict):
        return value
    replacement: dict[str, object] = {}
    payload[key] = replacement
    return replacement


def metadata_number(mapping: dict[str, object], key: str) -> float | None:
    try:
        value = float(mapping.get(key))
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def scale_configuration(run_folder: Path, payload: dict[str, object]) -> tuple[float, bool, float, str]:
    physics = payload.get("PhysicsData")
    physics = physics if isinstance(physics, dict) else {}

    attenuation_applied = pipeline.metadata_bool(physics.get("PowerDetectorAttenuatorApplied"), False)
    attenuation_factor = metadata_number(physics, "PowerDetectorAttenuatorCorrectionFactor")
    if not attenuation_applied or attenuation_factor is None or attenuation_factor <= 0:
        attenuation_factor = 1.0

    sensitivity_meta = pipeline.read_sensitivity_log(run_folder)
    conversion_factor = metadata_number(physics, "SyntheticConversionFactor_V2_rad2")
    if conversion_factor is None or conversion_factor <= 0:
        conversion_factor = metadata_number(physics, "ConversionFactor_V2_rad2")
    if conversion_factor is None or conversion_factor <= 0:
        candidate = float(sensitivity_meta.conversion_factor)
        conversion_factor = candidate if math.isfinite(candidate) and candidate > 0 else math.nan

    display_unit = str(physics.get("DisplayAmplitudeUnit", "")).strip().lower()
    if display_unit:
        display_in_v2 = display_unit.replace(" ", "") in {"v^2", "v2", "v²"}
    else:
        display_in_v2 = pipeline.is_dark_noise_run(sensitivity_meta)

    cm_scale_factor = pipeline.DETECTOR_AREA_SCALE * attenuation_factor
    unit = "V^2" if display_in_v2 else "urad^2"
    return cm_scale_factor, display_in_v2, conversion_factor, unit


def profile_timestamp_seconds(path: Path) -> Iterator[float]:
    previous: float | None = None
    day_offset = 0.0
    with path.open("rb", buffering=1024 * 1024) as handle:
        for line in handle:
            match = TIMESTAMP_RE.search(line)
            if match is None:
                continue
            hour, minute, second = (int(match.group(index)) for index in (1, 2, 3))
            fraction_raw = match.group(4) or b""
            fraction = int(fraction_raw) / (10 ** len(fraction_raw)) if fraction_raw else 0.0
            seconds = hour * 3600.0 + minute * 60.0 + second + fraction + day_offset
            if previous is not None and seconds < previous - 12 * 3600:
                day_offset += 24 * 3600.0
                seconds += 24 * 3600.0
            previous = seconds
            yield seconds


def source_fingerprint(cm_path: Path) -> dict[str, int]:
    stat = cm_path.stat()
    return {"SourceSizeBytes": int(stat.st_size), "SourceMtimeNs": int(stat.st_mtime_ns)}


def cached_analysis_matches(
    payload: dict[str, object],
    fingerprint: dict[str, int],
    base_tau_s: float,
    max_points: int,
    max_pairs: int,
) -> bool:
    physics = payload.get("PhysicsData")
    physics = physics if isinstance(physics, dict) else {}
    analysis = physics.get("AllanDeviationAnalysis")
    if not isinstance(analysis, dict):
        return False
    return (
        analysis.get("AnalysisVersion") == ANALYSIS_VERSION
        and analysis.get("SourceSizeBytes") == fingerprint["SourceSizeBytes"]
        and analysis.get("SourceMtimeNs") == fingerprint["SourceMtimeNs"]
        and analysis.get("TargetBaseTau_s") == base_tau_s
        and analysis.get("MaxTauPoints") == max_points
        and analysis.get("MaxPairs") == max_pairs
    )


def aggregate_long_term_channels(
    cm_path: Path,
    profile_path: Path,
    base_tau_s: float,
) -> tuple[np.ndarray, np.ndarray, dict[str, object]]:
    file_bytes = cm_path.stat().st_size
    frame_bytes = 64 * np.dtype(np.float64).itemsize
    if file_bytes % frame_bytes:
        raise ValueError(f"cm.bin size is not divisible by one 64-value frame: {cm_path}")
    total_frames = file_bytes // frame_bytes
    target_base_frames = max(1, int(round(base_tau_s / pipeline.FRAME_DT_S)))
    if total_frames < 10:
        raise ValueError(f"Need at least ten frames; found {total_frames} frames.")
    # Preserve at least ten base samples for short acquisitions instead of
    # rejecting every run shorter than ten times the requested base tau.
    base_frames = min(target_base_frames, max(1, total_frames // 10))
    usable_frames = (total_frames // base_frames) * base_frames
    if usable_frames < base_frames * 10:
        raise ValueError(
            f"Need at least ten {base_frames}-frame averaging bins; found {total_frames} frames."
        )

    mapped = np.memmap(cm_path, dtype=np.float64, mode="r", shape=(total_frames, 64))
    profile_available = profile_path.is_file()
    timestamp_iter = profile_timestamp_seconds(profile_path) if profile_available else iter(())
    timestamp_source = "profile.txt"
    last_timestamp: float | None = None
    first_timestamp: float | None = None

    channel_bins: list[np.ndarray] = []
    time_bins: list[np.ndarray] = []
    bins_per_chunk = 2048
    frames_per_chunk = base_frames * bins_per_chunk

    for start in range(0, usable_frames, frames_per_chunk):
        end = min(usable_frames, start + frames_per_chunk)
        count = end - start
        bin_count = count // base_frames
        raw = np.asarray(mapped[start:end]).reshape(bin_count, base_frames, 64)
        channel_bins.append(np.mean(raw, axis=1, dtype=np.float64))

        if profile_available:
            parsed = list(itertools.islice(timestamp_iter, count))
        else:
            parsed = []
        if len(parsed) < count:
            timestamp_source = "profile.txt+nominal-fill" if parsed else "nominal-frame-cadence"
            if parsed:
                fill_start = parsed[-1] + pipeline.FRAME_DT_S
            elif last_timestamp is not None:
                fill_start = last_timestamp + pipeline.FRAME_DT_S
            else:
                fill_start = start * pipeline.FRAME_DT_S
            parsed.extend(fill_start + np.arange(count - len(parsed), dtype=float) * pipeline.FRAME_DT_S)
        timestamp_array = np.asarray(parsed, dtype=float)
        last_timestamp = float(timestamp_array[-1])
        if first_timestamp is None:
            first_timestamp = float(timestamp_array[0])
        time_bins.append(timestamp_array.reshape(bin_count, base_frames).mean(axis=1))

    channels = np.vstack(channel_bins)
    times = np.concatenate(time_bins)
    del mapped

    times = times - times[0]
    time_steps = np.diff(times)
    if not np.all(np.isfinite(times)) or np.any(time_steps <= 0):
        timestamp_source = "nominal-frame-cadence-invalid-profile"
        times = np.arange(len(channels), dtype=float) * base_frames * pipeline.FRAME_DT_S
        time_steps = np.diff(times)

    median_cadence = float(np.median(time_steps))
    gap_count = int(np.count_nonzero((time_steps < 0.5 * median_cadence) | (time_steps > 1.5 * median_cadence)))
    details: dict[str, object] = {
        "TotalFrames": int(total_frames),
        "UsableFrames": int(usable_frames),
        "DroppedTailFrames": int(total_frames - usable_frames),
        "BaseFrames": int(base_frames),
        "BaseTauAdaptedForShortRun": bool(base_frames < target_base_frames),
        "AggregatedSamples": int(len(channels)),
        "TimestampSource": timestamp_source,
        "MedianBaseCadence_s": median_cadence,
        "DetectedTimingGaps": gap_count,
        "RecordedDuration_s": float(times[-1] - times[0]),
    }
    return channels, times, details


def select_critical_pairs(channels: np.ndarray, max_pairs: int) -> tuple[np.ndarray, list[str], np.ndarray]:
    variances = np.nanvar(channels, axis=0)
    pairs = pipeline.PAIRS.copy()
    labels = pipeline.pair_labels(pairs)
    endpoint_1 = np.asarray([pipeline.idx_lin(pair[0], pair[1]) for pair in pairs], dtype=int)
    endpoint_2 = np.asarray([pipeline.idx_lin(pair[2], pair[3]) for pair in pairs], dtype=int)
    scores = np.nanmean(np.column_stack([variances[endpoint_1], variances[endpoint_2]]), axis=1)
    ranked = np.argsort(np.nan_to_num(scores, nan=-np.inf))[::-1]
    selected = np.asarray([idx for idx in ranked if math.isfinite(float(scores[idx]))][:max_pairs], dtype=int)
    if selected.size == 0:
        raise ValueError("No finite channel pairs were available for Allan-deviation analysis.")
    return pairs[selected], [labels[idx] for idx in selected], scores[selected]


def classify_long_term_slope(slope: float | None) -> str:
    if slope is None:
        return "insufficient data"
    if slope < -0.25:
        return "improving with averaging"
    if slope <= 0.25:
        return "stability floor / flicker-like"
    if slope < 0.75:
        return "random-walk-like long-term drift"
    return "strong drift / trend"


def pair_summary(
    label: str,
    score: float,
    tau_s: np.ndarray,
    variance: np.ndarray,
    counts: np.ndarray,
    factors: np.ndarray,
    aggregated_samples: int,
) -> dict[str, object]:
    adev = np.sqrt(np.where(variance >= 0, variance, np.nan))
    valid = np.isfinite(adev) & (adev > 0) & (counts > 0)
    indices = np.flatnonzero(valid)
    if indices.size == 0:
        raise ValueError(f"No finite Allan-deviation results for {label}.")
    minimum_index = int(indices[np.argmin(adev[indices])])
    longest_index = int(indices[-1])
    slope_indices = indices[-min(LONG_TERM_SLOPE_POINTS, len(indices)):]
    slope: float | None = None
    if len(slope_indices) >= MIN_LONG_TERM_SLOPE_POINTS:
        slope = float(np.polyfit(np.log10(tau_s[slope_indices]), np.log10(adev[slope_indices]), 1)[0])
    minimum = float(adev[minimum_index])
    longest = float(adev[longest_index])
    return {
        "Pair": label,
        "SelectionScore": finite_or_none(score),
        "MinimumAllanDeviation": minimum,
        "TauAtMinimum_s": float(tau_s[minimum_index]),
        "AllanDeviationAtLongestTau": longest,
        "LongestTau_s": float(tau_s[longest_index]),
        "LongTermLogSlope": finite_or_none(slope),
        "LongTermBehavior": classify_long_term_slope(slope),
        "LongTermToMinimumRatio": longest / minimum if minimum > 0 else None,
        "OverlappingTermsAtLongestTau": int(counts[longest_index]),
        "NominalIndependentBlocksAtLongestTau": int(aggregated_samples // int(factors[longest_index])),
    }


def write_allan_csv(
    run_folder: Path,
    labels: list[str],
    tau_s: np.ndarray,
    variances: np.ndarray,
    counts: np.ndarray,
    factors: np.ndarray,
    unit: str,
    aggregated_samples: int,
) -> None:
    path = run_folder / "allan_deviation_long_term.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "pair",
                "averaging_bins",
                "tau_s",
                "allan_deviation",
                "allan_variance",
                "overlapping_terms",
                "nominal_independent_blocks",
                "deviation_unit",
            ]
        )
        for row_index, tau in enumerate(tau_s):
            for column_index, label in enumerate(labels):
                variance = float(variances[row_index, column_index])
                writer.writerow(
                    [
                        label,
                        int(factors[row_index]),
                        float(tau),
                        math.sqrt(variance) if variance >= 0 and math.isfinite(variance) else "",
                        variance if math.isfinite(variance) else "",
                        int(counts[row_index, column_index]),
                        int(aggregated_samples // int(factors[row_index])),
                        unit,
                    ]
                )


def write_summary_csv(run_folder: Path, summaries: list[dict[str, object]], unit: str) -> None:
    path = run_folder / "allan_deviation_summary.csv"
    fields = [
        "Pair",
        "SelectionScore",
        "MinimumAllanDeviation",
        "TauAtMinimum_s",
        "AllanDeviationAtLongestTau",
        "LongestTau_s",
        "LongTermLogSlope",
        "LongTermBehavior",
        "LongTermToMinimumRatio",
        "OverlappingTermsAtLongestTau",
        "NominalIndependentBlocksAtLongestTau",
        "DeviationUnit",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for summary in summaries:
            writer.writerow({**summary, "DeviationUnit": unit})


def write_plot(
    run_folder: Path,
    labels: list[str],
    tau_s: np.ndarray,
    variances: np.ndarray,
    unit: str,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 7))
    for column_index, label in enumerate(labels):
        adev = np.sqrt(np.where(variances[:, column_index] > 0, variances[:, column_index], np.nan))
        ax.loglog(tau_s, adev, linewidth=1.5, label=label)
    ax.set_title("Long-term overlapping Allan deviation")
    ax.set_xlabel(r"Averaging time $\tau$ (s)")
    ax.set_ylabel(f"Allan deviation ({unit})")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=False)
    fig.tight_layout()
    fig.savefig(run_folder / "allan_deviation_long_term.png", dpi=180)
    plt.close(fig)


def median_finite(values: list[object]) -> float | None:
    numeric = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return float(np.median(numeric)) if numeric else None


def build_overall_summary(
    run_folder: Path,
    cm_path: Path,
    fingerprint: dict[str, int],
    aggregation: dict[str, object],
    pair_summaries: list[dict[str, object]],
    unit: str,
    base_tau_s: float,
    max_points: int,
    max_pairs: int,
) -> dict[str, object]:
    median_minimum = median_finite([item["MinimumAllanDeviation"] for item in pair_summaries])
    median_tau_minimum = median_finite([item["TauAtMinimum_s"] for item in pair_summaries])
    median_longest = median_finite([item["AllanDeviationAtLongestTau"] for item in pair_summaries])
    median_slope = median_finite([item["LongTermLogSlope"] for item in pair_summaries])
    longest_tau = median_finite([item["LongestTau_s"] for item in pair_summaries])
    worst = max(
        pair_summaries,
        key=lambda item: float(item["AllanDeviationAtLongestTau"] or -math.inf),
    )
    behavior = classify_long_term_slope(median_slope)
    important_result = (
        f"Median critical-pair minimum ADEV={median_minimum:.6g} {unit} at tau={median_tau_minimum:.6g} s; "
        f"median ADEV at longest reliable tau={median_longest:.6g} {unit} at tau={longest_tau:.6g} s; "
        f"median long-term log slope={median_slope:.3f} ({behavior})."
        if None not in (median_minimum, median_tau_minimum, median_longest, longest_tau, median_slope)
        else "Allan-deviation analysis completed, but aggregate metrics were incomplete."
    )
    return {
        "AnalysisVersion": ANALYSIS_VERSION,
        "AnalyzedAt": datetime.now().isoformat(timespec="seconds"),
        "Status": "complete",
        "SourceFile": str(cm_path),
        **fingerprint,
        "TargetBaseTau_s": base_tau_s,
        "MaxTauPoints": max_points,
        "MaxPairs": max_pairs,
        "InputQuantity": "difference between paired covariance-matrix channels",
        "PairSelection": "highest endpoint variance after long-term base-bin averaging",
        "Detrended": False,
        "DeviationUnit": unit,
        **aggregation,
        "AnalyzedPairs": len(pair_summaries),
        "MedianMinimumAllanDeviation": median_minimum,
        "MedianTauAtMinimum_s": median_tau_minimum,
        "MedianAllanDeviationAtLongestTau": median_longest,
        "LongestReliableTau_s": longest_tau,
        "MedianLongTermLogSlope": median_slope,
        "LongTermBehavior": behavior,
        "WorstLongTermPair": worst["Pair"],
        "WorstPairAllanDeviationAtLongestTau": worst["AllanDeviationAtLongestTau"],
        "ImportantResult": important_result,
        "Pairs": pair_summaries,
        "Outputs": {
            "CurveCsv": str(run_folder / "allan_deviation_long_term.csv"),
            "SummaryCsv": str(run_folder / "allan_deviation_summary.csv"),
            "Plot": str(run_folder / "allan_deviation_long_term.png"),
        },
    }


def update_metadata(run_folder: Path, payload: dict[str, object], summary: dict[str, object]) -> None:
    physics = nested_dict(payload, "PhysicsData")
    physics["AllanDeviationAnalysis"] = summary
    physics["AllanDeviationImportantResult"] = summary["ImportantResult"]
    physics["AllanDeviationMedianMinimum"] = summary["MedianMinimumAllanDeviation"]
    physics["AllanDeviationMedianTauAtMinimum_s"] = summary["MedianTauAtMinimum_s"]
    physics["AllanDeviationMedianAtLongestTau"] = summary["MedianAllanDeviationAtLongestTau"]
    physics["AllanDeviationLongestReliableTau_s"] = summary["LongestReliableTau_s"]
    physics["AllanDeviationMedianLongTermLogSlope"] = summary["MedianLongTermLogSlope"]
    physics["AllanDeviationLongTermBehavior"] = summary["LongTermBehavior"]
    physics["AllanDeviationUnit"] = summary["DeviationUnit"]
    physics["AllanDeviationWorstLongTermPair"] = summary["WorstLongTermPair"]

    post_processing = nested_dict(payload, "PostProcessing")
    post_processing["AllanDeviationAnalysis"] = {
        "Script": Path(__file__).name,
        "AnalysisVersion": ANALYSIS_VERSION,
        "ProcessedAt": summary["AnalyzedAt"],
    }
    atomic_write_json(run_folder / "metadata.json", payload)


def analyze_run(
    run_folder: Path,
    base_tau_s: float,
    max_points: int,
    max_pairs: int,
    force: bool,
) -> dict[str, object]:
    cm_path = run_folder / "cm.bin"
    profile_path = run_folder / "profile.txt"
    payload = metadata_payload(run_folder)
    fingerprint = source_fingerprint(cm_path)
    if not force and cached_analysis_matches(payload, fingerprint, base_tau_s, max_points, max_pairs):
        physics = payload.get("PhysicsData")
        analysis = physics.get("AllanDeviationAnalysis") if isinstance(physics, dict) else None
        return {"status": "skipped", "summary": analysis}

    started = time.perf_counter()
    channels, times, aggregation = aggregate_long_term_channels(cm_path, profile_path, base_tau_s)
    cm_scale_factor, display_in_v2, conversion_factor, unit = scale_configuration(run_folder, payload)
    channels = channels * cm_scale_factor
    pairs, labels, selection_scores = select_critical_pairs(channels, max_pairs)
    endpoint_1 = np.asarray([pipeline.idx_lin(pair[0], pair[1]) for pair in pairs], dtype=int)
    endpoint_2 = np.asarray([pipeline.idx_lin(pair[2], pair[3]) for pair in pairs], dtype=int)
    values = channels[:, endpoint_1] - channels[:, endpoint_2]
    if not display_in_v2:
        if not math.isfinite(conversion_factor) or conversion_factor <= 0:
            raise ValueError("A positive conversion factor is required for urad^2 Allan deviation.")
        values = (values / conversion_factor) * 1e12

    tau_s, variances, counts, factors = pipeline.overlapping_allan_variance(
        values,
        times,
        max_points=max_points,
    )
    pair_summaries: list[dict[str, object]] = []
    invalid_pairs: list[str] = []
    for column, label in enumerate(labels):
        try:
            pair_summaries.append(
                pair_summary(
                    label,
                    float(selection_scores[column]),
                    tau_s,
                    variances[:, column],
                    counts[:, column],
                    factors,
                    len(values),
                )
            )
        except ValueError:
            invalid_pairs.append(label)
    if not pair_summaries:
        raise ValueError("No selected channel pair produced a finite Allan-deviation result.")
    write_allan_csv(run_folder, labels, tau_s, variances, counts, factors, unit, len(values))
    write_summary_csv(run_folder, pair_summaries, unit)
    write_plot(run_folder, labels, tau_s, variances, unit)
    aggregation["SelectedPairs"] = len(labels)
    aggregation["InvalidPairs"] = invalid_pairs
    aggregation["ProcessingTime_s"] = time.perf_counter() - started
    summary = build_overall_summary(
        run_folder,
        cm_path,
        fingerprint,
        aggregation,
        pair_summaries,
        unit,
        base_tau_s,
        max_points,
        max_pairs,
    )
    update_metadata(run_folder, payload, summary)
    return {"status": "ok", "summary": summary}


def write_batch_report(root: Path, rows: list[dict[str, object]]) -> None:
    path = root / "allan_deviation_batch_summary.csv"
    fields = [
        "run_folder",
        "status",
        "error",
        "processing_time_s",
        "unit",
        "median_minimum_allan_deviation",
        "median_tau_at_minimum_s",
        "median_allan_deviation_at_longest_tau",
        "longest_reliable_tau_s",
        "median_long_term_log_slope",
        "long_term_behavior",
        "worst_long_term_pair",
        "important_result",
    ]
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    replace_with_retry(temporary, path)


def report_row(run_folder: Path, status: str, summary: dict[str, object] | None, error: str = "") -> dict[str, object]:
    summary = summary or {}
    return {
        "run_folder": str(run_folder),
        "status": status,
        "error": error,
        "processing_time_s": summary.get("ProcessingTime_s", ""),
        "unit": summary.get("DeviationUnit", ""),
        "median_minimum_allan_deviation": summary.get("MedianMinimumAllanDeviation", ""),
        "median_tau_at_minimum_s": summary.get("MedianTauAtMinimum_s", ""),
        "median_allan_deviation_at_longest_tau": summary.get("MedianAllanDeviationAtLongestTau", ""),
        "longest_reliable_tau_s": summary.get("LongestReliableTau_s", ""),
        "median_long_term_log_slope": summary.get("MedianLongTermLogSlope", ""),
        "long_term_behavior": summary.get("LongTermBehavior", ""),
        "worst_long_term_pair": summary.get("WorstLongTermPair", ""),
        "important_result": summary.get("ImportantResult", ""),
    }


def analyze_run_job(
    job: tuple[Path, float, int, int, bool],
) -> tuple[Path, str, dict[str, object] | None, str, float]:
    """Process one run in a worker without writing the root batch report."""
    run_folder, base_tau_s, max_points, max_pairs, force = job
    started = time.perf_counter()
    try:
        result = analyze_run(run_folder, base_tau_s, max_points, max_pairs, force)
        summary = result.get("summary")
        summary = summary if isinstance(summary, dict) else None
        return run_folder, str(result["status"]), summary, "", time.perf_counter() - started
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        return run_folder, "failed", None, error, time.perf_counter() - started


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch long-term Allan-deviation analysis for Quantum Squeezing runs.")
    parser.add_argument("root", nargs="?", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--base-tau", type=float, default=DEFAULT_BASE_TAU_S, help="Target pre-averaging interval in seconds.")
    parser.add_argument("--max-points", type=int, default=DEFAULT_MAX_POINTS)
    parser.add_argument("--max-pairs", type=int, default=DEFAULT_MAX_PAIRS)
    parser.add_argument("--force", action="store_true", help="Recompute runs whose source fingerprint is unchanged.")
    parser.add_argument("--limit", type=int, default=0, help="Analyze only the first N runs; useful for testing.")
    parser.add_argument("--workers", type=int, default=1, help="Independent run workers (default: 1).")
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    if not root.is_dir():
        parser.error(f"DataFiles root was not found: {root}")
    if args.base_tau <= 0 or args.max_points < 2 or args.max_pairs < 1 or args.workers < 1:
        parser.error("base-tau must be positive, max-points >= 2, max-pairs >= 1, and workers >= 1.")

    cm_paths = sorted(root.rglob("cm.bin"), key=lambda path: str(path.parent).lower())
    if args.limit > 0:
        cm_paths = cm_paths[: args.limit]
    total = len(cm_paths)
    print(f"Found {total} runs under {root}", flush=True)
    rows: list[dict[str, object]] = []
    failures = 0
    completed = 0
    skipped = 0
    batch_started = time.perf_counter()

    jobs = [(path.parent, args.base_tau, args.max_points, args.max_pairs, args.force) for path in cm_paths]
    if args.workers == 1:
        results = map(analyze_run_job, jobs)
        executor = None
    else:
        executor = ProcessPoolExecutor(max_workers=args.workers)
        futures = [executor.submit(analyze_run_job, job) for job in jobs]
        results = (future.result() for future in as_completed(futures))

    try:
        for index, (run_folder, status, summary, error, elapsed) in enumerate(results, start=1):
            rows.append(report_row(run_folder, status, summary, error))
            if status == "failed":
                failures += 1
                print(f"[{index}/{total}] FAILED {run_folder.name}: {error}", flush=True)
            elif status == "skipped":
                skipped += 1
                print(f"[{index}/{total}] SKIPPED {run_folder.name} ({elapsed:.2f}s)", flush=True)
            else:
                completed += 1
                print(f"[{index}/{total}] OK {run_folder.name} ({elapsed:.2f}s)", flush=True)
            if index % 10 == 0:
                write_batch_report(root, sorted(rows, key=lambda row: str(row["run_folder"]).lower()))
    finally:
        if executor is not None:
            executor.shutdown()

    elapsed = time.perf_counter() - batch_started
    write_batch_report(root, sorted(rows, key=lambda row: str(row["run_folder"]).lower()))
    print(
        f"Finished {total} runs in {elapsed:.1f}s: completed={completed}, skipped={skipped}, failed={failures}",
        flush=True,
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
