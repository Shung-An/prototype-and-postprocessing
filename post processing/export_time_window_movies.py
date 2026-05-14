from __future__ import annotations

import argparse
import csv
import json
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

try:
    import imageio.v2 as imageio  # type: ignore
except ImportError:
    imageio = None

from cm_pipeline_all_in_one import (
    BIN_MM,
    DETECTOR_AREA_SCALE,
    ENABLE_CHANNEL_HEALTH_GATING,
    ENABLE_DROPPED_WINDOW_GATING,
    ENABLE_EVEN_FRAMES_ONLY,
    ENABLE_SATURATION_CLEANUP,
    ENABLE_VARIANCE_GATING,
    FRAME_DT_S,
    MM_TO_PS,
    PAIRS,
    SATURATION_THRESHOLD_CH11,
    STD_GATE_MODE,
    STD_STATE_TO_KEEP,
    align_position_times,
    amplitude_axis_label,
    apply_metadata_attenuator,
    apply_dark_noise_tag_power_estimate,
    build_bin_cumsums_and_counts,
    dropped_window_mask,
    estimate_scan_velocity_mm_s,
    find_first,
    idx_lin,
    is_dark_noise_run,
    kurtosis_per_channel,
    metadata_scan_velocity_mm_s,
    otsu_like_threshold,
    pair_labels,
    read_cm64,
    read_positions_series,
    read_sensitivity_log,
    read_times_from_profile,
    std_state_cutoff,
    std_state_keep_mask,
    style_matplotlib,
)


WINDOWS = [
    ("000_100s", 0.0, 100.0),
    ("101_200s", 100.0, 200.0),
    ("201_300s", 200.0, 300.0),
    ("301_400s", 300.0, 400.0),
    ("401_500s", 400.0, 500.0),
    ("501_last", 500.0, None),
]


def build_clip_windows(clip_seconds: float, last_time_s: float) -> list[tuple[str, float, float | None]]:
    if clip_seconds <= 0:
        return WINDOWS

    windows: list[tuple[str, float, float | None]] = []
    start = 0.0
    while start < last_time_s:
        end = start + clip_seconds
        if end >= last_time_s:
            label_start = int(start) if start == 0 else int(start) + 1
            windows.append((f"{label_start:05d}_last", start, None))
            break
        label_start = int(start) if start == 0 else int(start) + 1
        label_end = int(end)
        windows.append((f"{label_start:05d}_{label_end:05d}s", start, end))
        start = end
    return windows


def unwrap_seconds_of_day(seconds: np.ndarray) -> np.ndarray:
    """Make time-of-day seconds monotonic when a run crosses midnight."""
    if seconds.size <= 1:
        return seconds.copy()

    unwrapped = seconds.astype(float, copy=True)
    day_offset = 0.0
    previous = unwrapped[0]
    for idx in range(1, unwrapped.size):
        current = unwrapped[idx] + day_offset
        if current < previous - 12 * 3600:
            day_offset += 24 * 3600
            current = unwrapped[idx] + day_offset
        unwrapped[idx] = current
        previous = current
    return unwrapped


def load_keep_indices_from_summary(run_folder: Path, pair_count: int) -> list[int]:
    summary_path = run_folder / "critical_pairs_summary.csv"
    if not summary_path.is_file():
        return list(range(min(9, pair_count)))

    keep_indices: list[int] = []
    with summary_path.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            try:
                index = int(row.get("pair_index", ""))
            except ValueError:
                continue
            if 0 <= index < pair_count:
                keep_indices.append(index)
            if len(keep_indices) >= 9:
                break
    return keep_indices or list(range(min(9, pair_count)))


def prepare_run_data(run_folder: Path) -> dict[str, object]:
    cm_path = run_folder / "cm.bin"
    profile_path = run_folder / "profile.txt"
    pos_path = find_first(run_folder, ["delay_stage_positions.log", "delay_stage_positions.csv"])
    if not cm_path.is_file():
        raise FileNotFoundError(f"cm.bin not found in {run_folder}")

    raw_cm = read_cm64(cm_path)
    t_seconds, t_absolute_seconds = read_times_from_profile(profile_path, raw_cm.shape[0])
    t_absolute_seconds = unwrap_seconds_of_day(t_absolute_seconds)
    t_seconds = t_absolute_seconds - t_absolute_seconds[0]
    if ENABLE_EVEN_FRAMES_ONLY:
        raw_cm = raw_cm[::2]
        t_seconds = t_seconds[::2]
        t_absolute_seconds = t_absolute_seconds[::2]

    base_dt = datetime(1900, 1, 1)
    t_datetimes = [base_dt + timedelta(seconds=float(s)) for s in t_absolute_seconds]

    meta = read_sensitivity_log(run_folder)
    apply_metadata_attenuator(run_folder, meta)
    apply_dark_noise_tag_power_estimate(run_folder, meta)
    meta.scan_velocity_mm_s = metadata_scan_velocity_mm_s(run_folder)
    cm_scale_factor = DETECTOR_AREA_SCALE * meta.power_detector_attenuator_correction_factor
    conversion_factor = meta.conversion_factor
    display_in_v2 = is_dark_noise_run(meta)

    if pos_path is None:
        pos_on_cm = np.full(raw_cm.shape[0], 25.058, dtype=float)
    else:
        pos_time, pos_val = read_positions_series(pos_path)
        pos_dt, pos_val_aligned = align_position_times(pos_time, pos_val, t_absolute_seconds)
        if pos_dt.size == 0:
            pos_on_cm = np.full(raw_cm.shape[0], float(pos_val[0]), dtype=float)
        elif pos_dt.size == 1:
            pos_on_cm = np.full(raw_cm.shape[0], float(pos_val_aligned[0]), dtype=float)
        else:
            pos_on_cm = np.interp(
                t_seconds,
                pos_dt,
                pos_val_aligned,
                left=pos_val_aligned[0],
                right=pos_val_aligned[-1],
            )
        meta.scan_range = float(np.max(pos_on_cm) - np.min(pos_on_cm))
        meta.scan_min = float(np.min(pos_on_cm))
        meta.scan_max = float(np.max(pos_on_cm))
        if not np.isfinite(meta.scan_velocity_mm_s):
            meta.scan_velocity_mm_s = estimate_scan_velocity_mm_s(t_seconds, pos_on_cm)

    pairs = PAIRS.copy()
    labels = pair_labels(pairs)

    if ENABLE_SATURATION_CLEANUP or ENABLE_DROPPED_WINDOW_GATING or ENABLE_VARIANCE_GATING or ENABLE_CHANNEL_HEALTH_GATING:
        cm_for_gating = raw_cm * cm_scale_factor

        dirty_mask = cm_for_gating[:, 0] > SATURATION_THRESHOLD_CH11
        if ENABLE_SATURATION_CLEANUP and np.any(dirty_mask):
            keep = ~dirty_mask
            raw_cm = raw_cm[keep]
            cm_for_gating = cm_for_gating[keep]
            t_seconds = t_seconds[keep]
            pos_on_cm = pos_on_cm[keep]
            t_datetimes = [dt for dt, k in zip(t_datetimes, keep, strict=False) if bool(k)]

        if ENABLE_DROPPED_WINDOW_GATING:
            dropped_mask = dropped_window_mask(t_seconds, t_datetimes, run_folder / "dropped_window.log")
            if np.any(dropped_mask):
                keep = ~dropped_mask
                raw_cm = raw_cm[keep]
                cm_for_gating = cm_for_gating[keep]
                t_seconds = t_seconds[keep]
                pos_on_cm = pos_on_cm[keep]
                t_datetimes = [dt for dt, k in zip(t_datetimes, keep, strict=False) if bool(k)]

        dirty_mask = cm_for_gating[:, 0] > SATURATION_THRESHOLD_CH11
        if ENABLE_SATURATION_CLEANUP and np.any(dirty_mask):
            keep = ~dirty_mask
            raw_cm = raw_cm[keep]
            cm_for_gating = cm_for_gating[keep]
            t_seconds = t_seconds[keep]
            pos_on_cm = pos_on_cm[keep]
            t_datetimes = [dt for dt, k in zip(t_datetimes, keep, strict=False) if bool(k)]

        if ENABLE_VARIANCE_GATING:
            frame_rms = raw_cm.std(axis=1)
            state_split_cutoff = otsu_like_threshold(frame_rms)
            rms_cutoff = std_state_cutoff(frame_rms, state_split_cutoff, STD_STATE_TO_KEEP)
            keep = std_state_keep_mask(frame_rms, rms_cutoff, STD_STATE_TO_KEEP)
            print(
                f"Std-state gate kept {int(np.count_nonzero(keep))}/{keep.size} frames "
                f"from {STD_STATE_TO_KEEP!r} (mode={STD_GATE_MODE}).",
                flush=True,
            )
            if not np.any(keep):
                raise ValueError("Std-state gate rejected every frame.")
            raw_cm = raw_cm[keep]
            cm_for_gating = cm_for_gating[keep]
            t_seconds = t_seconds[keep]
            pos_on_cm = pos_on_cm[keep]
            t_datetimes = [dt for dt, k in zip(t_datetimes, keep, strict=False) if bool(k)]

        if ENABLE_CHANNEL_HEALTH_GATING:
            channel_kurt = kurtosis_per_channel(cm_for_gating)
            bad_channels = {idx for idx, value in enumerate(channel_kurt) if np.isfinite(value) and value > 5.0}
            valid_pair_mask = []
            for pair in pairs:
                i1 = idx_lin(pair[0], pair[1])
                i2 = idx_lin(pair[2], pair[3])
                valid_pair_mask.append(i1 not in bad_channels and i2 not in bad_channels)
            valid_pair_mask_arr = np.asarray(valid_pair_mask, dtype=bool)
            pairs = pairs[valid_pair_mask_arr]
            labels = [label for label, keep in zip(labels, valid_pair_mask_arr, strict=False) if keep]

    keep_indices = load_keep_indices_from_summary(run_folder, len(labels))
    global_ts = np.round(pos_on_cm / BIN_MM) * BIN_MM * MM_TO_PS

    return {
        "raw_cm": raw_cm,
        "t_seconds": t_seconds,
        "pos_on_cm": pos_on_cm,
        "pairs": pairs,
        "labels": labels,
        "keep_indices": keep_indices,
        "cm_scale_factor": cm_scale_factor,
        "conversion_factor": conversion_factor,
        "display_in_v2": display_in_v2,
        "xlim": (float(np.nanmin(global_ts)), float(np.nanmax(global_ts))),
    }


def write_window_movie(
    output_path: Path,
    ts: np.ndarray,
    counts: np.ndarray,
    bin_cumsums: list[np.ndarray],
    labels: list[str],
    keep_indices: list[int],
    display_in_v2: bool,
    window_title: str,
    xlim: tuple[float, float],
) -> None:
    if imageio is None:
        raise RuntimeError("imageio is not installed, so MP4 export is unavailable.")
    if counts.size == 0:
        raise ValueError(f"No position bins are available for {window_title}.")

    k_max_common = int(np.min(counts))
    if k_max_common < 2:
        raise ValueError(f"Not enough frames per bin for {window_title}.")

    n_movie_frames = min(400, k_max_common)
    frame_steps = np.unique(np.round(np.linspace(1, k_max_common, n_movie_frames)).astype(int))
    selected_bin_cumsums = [
        bin_curve[:, keep_indices] if bin_curve.size else np.empty((0, len(keep_indices)), dtype=float)
        for bin_curve in bin_cumsums
    ]

    fig, ax = plt.subplots(figsize=(12, 7))
    line_handles = []
    for idx in keep_indices:
        (line,) = ax.plot([], [], "o-", linewidth=1.5, markersize=4, label=labels[idx])
        line_handles.append(line)
    ax.set_xlabel("Delay (ps)")
    ax.set_ylabel(amplitude_axis_label(display_in_v2))
    ax.set_xlim(*xlim)
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=False)

    with imageio.get_writer(output_path, fps=15, macro_block_size=1) as writer:
        for k in frame_steps:
            current_matrix = np.full((len(keep_indices), len(ts)), np.nan, dtype=float)
            for b_idx, bin_curve in enumerate(selected_bin_cumsums):
                if bin_curve.shape[0] >= k:
                    current_matrix[:, b_idx] = bin_curve[k - 1, :] / k

            finite_vals = current_matrix[np.isfinite(current_matrix)]
            if finite_vals.size > 0:
                y_min = float(np.min(finite_vals))
                y_max = float(np.max(finite_vals))
                span = y_max - y_min
                pad = max(0.05 * span, 0.05 * max(abs(y_min), abs(y_max), 1.0), 1e-6)
                ax.set_ylim(y_min - pad, y_max + pad)

            for line_idx, line in enumerate(line_handles):
                line.set_data(ts, current_matrix[line_idx])

            ax.set_title(f"{window_title} | Integration: {k} Frames ({k * FRAME_DT_S:.2f}s)")
            fig.tight_layout()
            fig.canvas.draw()
            writer.append_data(np.asarray(fig.canvas.buffer_rgba())[:, :, :3])
    plt.close(fig)


def export_window(context: dict[str, object], run_folder: Path, name: str, start_s: float, end_s: float | None) -> dict[str, object]:
    raw_cm = context["raw_cm"]
    t_seconds = context["t_seconds"]
    pos_on_cm = context["pos_on_cm"]
    pairs = context["pairs"]
    labels = context["labels"]
    keep_indices = context["keep_indices"]

    if not isinstance(raw_cm, np.ndarray) or not isinstance(t_seconds, np.ndarray) or not isinstance(pos_on_cm, np.ndarray):
        raise TypeError("Invalid run context.")
    if not isinstance(pairs, np.ndarray) or not isinstance(labels, list) or not isinstance(keep_indices, list):
        raise TypeError("Invalid pair context.")

    if end_s is None:
        mask = t_seconds > start_s
        title = f"{int(start_s) + 1}s to last frame"
    elif start_s == 0.0:
        mask = (t_seconds >= start_s) & (t_seconds <= end_s)
        title = f"{int(start_s)}s to {int(end_s)}s"
    else:
        mask = (t_seconds > start_s) & (t_seconds <= end_s)
        title = f"{int(start_s) + 1}s to {int(end_s)}s"

    frame_count = int(np.count_nonzero(mask))
    if frame_count == 0:
        raise ValueError(f"No frames were found for {title}.")

    window_raw = raw_cm[mask]
    window_pos = pos_on_cm[mask]
    pos_bin = np.round(window_pos / BIN_MM) * BIN_MM
    unique_bins, inverse = np.unique(pos_bin, return_inverse=True)
    counts_all = np.bincount(inverse)
    keep_bins = counts_all > 0
    bin_vals = unique_bins[keep_bins]
    counts = counts_all[keep_bins]
    valid_indices = np.where(keep_bins)[0]

    pair_i1 = np.array([idx_lin(pair[0], pair[1]) for pair in pairs], dtype=int)
    pair_i2 = np.array([idx_lin(pair[2], pair[3]) for pair in pairs], dtype=int)
    pair_diffs = (window_raw[:, pair_i1] - window_raw[:, pair_i2]) * float(context["cm_scale_factor"])
    bin_cumsums, counts = build_bin_cumsums_and_counts(
        pair_diffs,
        inverse,
        valid_indices,
        float(context["conversion_factor"]),
        bool(context["display_in_v2"]),
    )

    ts = bin_vals * MM_TO_PS
    output_path = run_folder / f"signal_emergence_{name}.mp4"
    write_window_movie(
        output_path,
        ts,
        counts,
        bin_cumsums,
        labels,
        keep_indices,
        bool(context["display_in_v2"]),
        title,
        context["xlim"],  # type: ignore[arg-type]
    )
    return {
        "window": title,
        "frames": frame_count,
        "bins": int(counts.size),
        "min_frames_per_bin": int(np.min(counts)) if counts.size else 0,
        "path": str(output_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export signal-emergence MP4s for fixed time windows.")
    parser.add_argument("run_folder", type=Path)
    parser.add_argument(
        "--clip-seconds",
        type=float,
        default=0.0,
        help="Export consecutive clips of this many seconds instead of the default fixed windows.",
    )
    args = parser.parse_args()

    style_matplotlib()
    run_folder = args.run_folder.expanduser().resolve()
    print(f"Loading run: {run_folder}", flush=True)
    context = prepare_run_data(run_folder)
    print(
        "Prepared "
        f"{context['raw_cm'].shape[0]} frames; "
        f"time range {float(np.nanmin(context['t_seconds'])):.3f}s to {float(np.nanmax(context['t_seconds'])):.3f}s.",
        flush=True,
    )

    last_time_s = float(np.nanmax(context["t_seconds"]))
    windows = build_clip_windows(args.clip_seconds, last_time_s)
    manifest: list[dict[str, object]] = []
    for name, start_s, end_s in windows:
        print(f"Exporting {name}...", flush=True)
        with warnings.catch_warnings():
            warnings.simplefilter("default")
            manifest.append(export_window(context, run_folder, name, start_s, end_s))

    manifest_path = run_folder / "signal_emergence_time_windows_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote manifest: {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
