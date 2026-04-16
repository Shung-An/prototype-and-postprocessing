from __future__ import annotations

import argparse
import csv
import json
import math
import re
import tkinter as tk
import warnings
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import filedialog

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

try:
    import imageio.v2 as imageio  # type: ignore
except ImportError:
    imageio = None


BIN_MM = 0.1
# Area scaling from detector pixel units to percent:
# - 0.24 is the detector pitch in mm per pixel.
# - 32768 is the full-scale detector count used to normalize the raw signal.
# - 100 converts the resulting fraction to percent.
SCALE_FACTOR = (0.24**2) / (32768**2) * 100
# Conversion factor from distance in millimeters to time in picoseconds for this setup.
MM_TO_PS = 6.6
# Time per processed frame, in seconds:
# 67 acquired samples at a 4861 Hz acquisition rate.
FRAME_DT_S = 67 / 4861
RAW_STD_FRAME_INTEGRATION_S = FRAME_DT_S
# Relative gating threshold expressed as a fraction of the reference level (20%).
REL_THRESHOLD = 0.20
# Empirical saturation cutoff for channel 11 signal values.
# Samples above this level are treated as saturated during cleanup/gating.
SATURATION_THRESHOLD_CH11 = 3e-7

ENABLE_DROPPED_WINDOW_GATING = False
ENABLE_SATURATION_CLEANUP = False
ENABLE_VARIANCE_GATING = False
ENABLE_CHANNEL_HEALTH_GATING = False
ENABLE_EVEN_FRAMES_ONLY = True

PAIRS = np.array(
    [
        [1, 1, 8, 8],
        [1, 2, 7, 8],
        [1, 3, 6, 8],
        [1, 4, 5, 8],
        [1, 5, 4, 8],
        [1, 6, 3, 8],
        [1, 7, 2, 8],
        [2, 2, 8, 8],
        [2, 3, 7, 8],
        [2, 4, 6, 8],
        [2, 5, 5, 8],
        [2, 6, 4, 8],
        [2, 7, 3, 8],
        [3, 3, 8, 8],
        [3, 4, 7, 8],
        [3, 5, 6, 8],
        [3, 6, 5, 8],
        [3, 7, 4, 8],
        [4, 4, 8, 8],
        [4, 5, 7, 8],
        [4, 6, 6, 8],
        [4, 7, 5, 8],
        [5, 5, 8, 8],
        [5, 6, 7, 8],
        [5, 7, 6, 8],
        [6, 6, 8, 8],
        [6, 7, 7, 8],
        [7, 7, 8, 8],
        [2, 1, 8, 7],
        [3, 1, 8, 6],
        [4, 1, 8, 5],
        [5, 1, 8, 4],
        [6, 1, 8, 3],
        [7, 1, 8, 2],
        [3, 2, 8, 7],
        [4, 2, 8, 6],
        [5, 2, 8, 5],
        [6, 2, 8, 4],
        [7, 2, 8, 3],
        [4, 3, 8, 7],
        [5, 3, 8, 6],
        [5, 4, 8, 7],
        [6, 4, 8, 6],
        [7, 4, 8, 5],
        [6, 5, 8, 7],
        [7, 5, 8, 6],
        [7, 6, 8, 7],
    ],
    dtype=int,
)

# A pair is treated as "critical" when its metric exceeds a 3-sigma deviation from
# the expected distribution. 3.0 was chosen as a conventional outlier cutoff: it is
# strict enough to suppress most noise-driven excursions, while still surfacing
# pair behavior that is statistically unusual and likely to reflect a real issue in
# the measurement rather than normal frame-to-frame variation.
# Cap the number of displayed critical pairs to keep the summary plots readable.
CRITICAL_PAIR_MAX_COUNT = 8


@dataclass
class Meta:
    p1_mw: float = math.nan
    p2_mw: float = math.nan
    sensitivity: float = math.nan
    shot_noise1_v: float = math.nan
    shot_noise2_v: float = math.nan
    signal_level: float = math.nan
    conversion_factor: float = math.nan
    shot_noise_result: float = math.nan
    scan_range: float = 0.0
    scan_min: float = 25.058
    scan_max: float = 25.058


def pair_labels(pairs: np.ndarray) -> list[str]:
    return [f"({r1},{c1})-({r2},{c2})" for r1, c1, r2, c2 in pairs]


def idx_lin(r: int, c: int) -> int:
    return (r - 1) * 8 + (c - 1)


def read_cm64(path: Path) -> np.ndarray:
    raw = np.fromfile(path, dtype=np.float64)
    if raw.size % 64 != 0:
        raise ValueError(f"{path} does not contain a whole number of 64-wide frames.")
    return raw.reshape((-1, 64))


def parse_time_string(value: str) -> datetime:
    for fmt in ("%H:%M:%S.%f", "%H:%M:%S"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    raise ValueError(f"Unsupported time format: {value}")


def read_times_from_profile(path: Path, n_frames: int) -> tuple[np.ndarray, np.ndarray]:
    if not path.is_file():
        relative = np.arange(n_frames, dtype=float) * FRAME_DT_S
        return relative, relative.copy()

    text = path.read_text(encoding="utf-8", errors="ignore")
    tokens = re.findall(r"start timestamp:\s*(\S+)", text)
    if not tokens:
        relative = np.arange(n_frames, dtype=float) * FRAME_DT_S
        return relative, relative.copy()

    times = [parse_time_string(token) for token in tokens[:n_frames]]
    t0 = times[0]
    relative_seconds = np.array([(t - t0).total_seconds() for t in times], dtype=float)
    absolute_seconds = np.array(
        [
            t.hour * 3600 + t.minute * 60 + t.second + t.microsecond / 1_000_000.0
            for t in times
        ],
        dtype=float,
    )
    return relative_seconds, absolute_seconds


def find_first(run_folder: Path, names: list[str]) -> Path | None:
    for name in names:
        candidate = run_folder / name
        if candidate.is_file():
            return candidate
    return None


def read_positions_series(path: Path) -> tuple[np.ndarray, np.ndarray]:
    times: list[float] = []
    positions: list[float] = []

    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            parts = [part.strip() for part in re.split(r"[,;]", line.strip()) if part.strip()]
            if len(parts) < 2:
                continue
            try:
                t = parse_time_string(parts[0])
                p = float(parts[-1])
            except ValueError:
                continue
            times.append(
                t.hour * 3600 + t.minute * 60 + t.second + t.microsecond / 1_000_000.0
            )
            positions.append(p)

    if not times:
        raise ValueError(f"Could not parse any positions from {path}")

    times_arr = np.asarray(times, dtype=float)
    positions_arr = np.asarray(positions, dtype=float)
    unique_times, unique_indices = np.unique(times_arr, return_index=True)
    return unique_times, positions_arr[unique_indices]


def align_position_times(
    pos_time: np.ndarray, pos_val: np.ndarray, cm_absolute_seconds: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    if pos_time.size == 0 or pos_val.size == 0:
        return np.array([], dtype=float), np.array([], dtype=float)
    if cm_absolute_seconds.size == 0:
        return np.array([], dtype=float), np.array([], dtype=float)

    dt = pos_time - cm_absolute_seconds[0]
    valid_mask = np.isfinite(dt) & np.isfinite(pos_val)
    if not np.any(valid_mask):
        return np.array([], dtype=float), np.array([], dtype=float)

    dt = dt[valid_mask]
    pv = pos_val[valid_mask]
    unique_dt, unique_indices = np.unique(dt, return_index=True)
    return unique_dt, pv[unique_indices]


def extract_val(text: str, pattern: str) -> float:
    match = re.search(pattern, text)
    return float(match.group(1)) if match else math.nan


def read_sensitivity_log(run_folder: Path) -> Meta:
    meta = Meta()
    path = run_folder / "sensitivity.log"
    if not path.is_file():
        return meta

    text = path.read_text(encoding="utf-8", errors="ignore")
    meta.p1_mw = extract_val(text, r"P1\s*=\s*([\d\.E\+\-]+)\s*mW")
    meta.p2_mw = extract_val(text, r"P2\s*=\s*([\d\.E\+\-]+)\s*mW")
    meta.sensitivity = extract_val(text, r"Sensitivity\s*=\s*([\d\.E\+\-]+)")
    meta.shot_noise1_v = extract_val(text, r"Shot Noise1\s*=\s*([\d\.E\+\-]+)")
    meta.shot_noise2_v = extract_val(text, r"Shot Noise2\s*=\s*([\d\.E\+\-]+)")
    meta.signal_level = extract_val(text, r"Signal Level\s*=\s*([\d\.E\+\-]+)")
    meta.conversion_factor = extract_val(text, r"Conversion Factor\s*=\s*([\d\.E\+\-]+)")
    meta.shot_noise_result = extract_val(text, r"Shot Noise Result\s*=\s*([\d\.E\+\-]+)")
    return meta


def scale_to_urad2(values: np.ndarray, conversion_factor: float) -> np.ndarray:
    cf = 1e4 if not np.isfinite(conversion_factor) else conversion_factor
    return (values / cf) * 1e12


def pair_diagonal_offset(pair: np.ndarray) -> int:
    return max(abs(int(pair[0]) - int(pair[2])), abs(int(pair[1]) - int(pair[3])))


def critical_pair_indices(
    amps: np.ndarray,
    pairs: np.ndarray,
    max_count: int = CRITICAL_PAIR_MAX_COUNT,
) -> tuple[list[int], list[dict[str, float | int]]]:
    if amps.size == 0 or pairs.size == 0:
        return [], []

    offsets = np.asarray([pair_diagonal_offset(pair) for pair in pairs], dtype=int)
    mean_corr = np.nanmean(amps, axis=0)
    global_mean = float(np.nanmean(mean_corr))
    scores = np.abs(mean_corr - global_mean)
    peak_amplitudes = np.nanmax(np.abs(amps), axis=0)

    ranked = np.argsort(np.nan_to_num(scores, nan=-np.inf))[::-1]
    keep_indices = [int(idx) for idx in ranked if np.isfinite(scores[idx]) and np.isfinite(peak_amplitudes[idx])]
    keep_indices = keep_indices[: min(max_count, len(keep_indices))]

    details = [
        {
            "pair_index": int(idx),
            "diagonal_offset": int(offsets[idx]),
            "critical_score": float(scores[idx]),
            "mean_correlation": float(mean_corr[idx]),
            "global_mean_correlation": global_mean,
            "peak_abs_amplitude": float(peak_amplitudes[idx]),
        }
        for idx in keep_indices
    ]
    return keep_indices, details


def write_critical_pairs_summary(
    run_folder: Path,
    details: list[dict[str, float | int]],
    pair_labels_list: list[str],
) -> None:
    with (run_folder / "critical_pairs_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "pair_index",
                "label",
                "diagonal_offset",
                "critical_score",
                "mean_correlation",
                "global_mean_correlation",
                "peak_abs_amplitude",
            ]
        )
        for detail in details:
            pair_index = int(detail["pair_index"])
            writer.writerow(
                [
                    pair_index,
                    pair_labels_list[pair_index],
                    detail["diagonal_offset"],
                    f"{float(detail['critical_score']):.6f}",
                    f"{float(detail['mean_correlation']):.6f}",
                    f"{float(detail['global_mean_correlation']):.6f}",
                    f"{float(detail['peak_abs_amplitude']):.6f}",
                ]
            )


def dropped_window_mask(t_seconds: np.ndarray, t_datetimes: list[datetime], dropped_log: Path) -> np.ndarray:
    if not dropped_log.is_file():
        return np.zeros_like(t_seconds, dtype=bool)

    text = dropped_log.read_text(encoding="utf-8", errors="ignore")
    tokens = re.findall(
        r"Between:\s*(\d{2}:\d{2}:\d{2}\.\d+)\s*-\s*(\d{2}:\d{2}:\d{2}\.\d+)",
        text,
    )
    if not tokens:
        return np.zeros_like(t_seconds, dtype=bool)

    time_of_day = np.array(
        [dt.hour * 3600 + dt.minute * 60 + dt.second + dt.microsecond / 1_000_000 for dt in t_datetimes],
        dtype=float,
    )
    mask = np.zeros_like(t_seconds, dtype=bool)
    for start_text, end_text in tokens:
        start = parse_time_string(start_text)
        end = parse_time_string(end_text)
        start_s = start.hour * 3600 + start.minute * 60 + start.second + start.microsecond / 1_000_000
        end_s = end.hour * 3600 + end.minute * 60 + end.second + end.microsecond / 1_000_000
        mask |= (time_of_day >= start_s) & (time_of_day <= end_s)
    return mask


def otsu_like_threshold(values: np.ndarray) -> float:
    threshold = float(values.mean())
    for _ in range(50):
        g1 = values[values < threshold]
        g2 = values[values >= threshold]
        if g1.size == 0 or g2.size == 0:
            break
        new_threshold = float((g1.mean() + g2.mean()) / 2.0)
        if abs(new_threshold - threshold) < 1e-12:
            break
        threshold = new_threshold
    return threshold


def kurtosis_per_channel(cm: np.ndarray) -> np.ndarray:
    centered = cm - cm.mean(axis=0, keepdims=True)
    variance = np.mean(centered**2, axis=0)
    variance[variance == 0] = np.nan
    fourth = np.mean(centered**4, axis=0)
    return fourth / (variance**2)


def style_matplotlib() -> None:
    plt.style.use("default")
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.grid": True,
            "grid.alpha": 0.25,
            "grid.linestyle": "--",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "font.size": 11,
            "axes.titlesize": 15,
            "axes.labelsize": 12,
            "legend.fontsize": 10,
            "savefig.dpi": 300,
        }
    )


def save_variance_gating_check(run_folder: Path, frame_rms: np.ndarray, cutoff: float) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(frame_rms, bins=100, color="#3d6ea8")
    ax.axvline(cutoff, color="#c0392b", linestyle="--", linewidth=2, label="Cutoff")
    ax.set_xlabel("Frame RMS")
    ax.set_ylabel("Count")
    ax.set_title("Distribution of Frame Energy (Auto-Threshold)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(run_folder / "variance_gating_check.png")
    plt.close(fig)


def save_histogram(run_folder: Path, x: np.ndarray) -> None:
    fig, ax = plt.subplots(figsize=(10, 6.5))
    ax.hist(x, bins=80, color="#4b6cb7")
    ax.set_title("Ch(1,1) Amplitude (Raw)")
    fig.tight_layout()
    fig.savefig(run_folder / "hist_ch11_amplitude_V2.png")
    plt.close(fig)


def save_raw_std_analysis(run_folder: Path, raw_cm: np.ndarray, t_seconds: np.ndarray) -> None:
    if raw_cm.size == 0:
        return

    frame_idx = np.arange(raw_cm.shape[0], dtype=int)
    raw_std = raw_cm.std(axis=1)
    parity = np.where(frame_idx % 2 == 0, "even", "odd")
    integrated_time_s = (frame_idx + 1) * RAW_STD_FRAME_INTEGRATION_S

    odd_mask = parity == "odd"
    even_mask = parity == "even"
    threshold = math.nan
    if np.any(odd_mask) and np.any(even_mask):
        threshold = 0.5 * (float(np.mean(raw_std[odd_mask])) + float(np.mean(raw_std[even_mask])))

    with (run_folder / "raw_std_analysis.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "frame_index",
                "frame_number_1based",
                "integrated_time_s",
                "index_parity",
                "raw_std",
                "raw_std_threshold",
                "raw_std_predicted_group",
            ]
        )
        for idx, time_s, std_value, group in zip(frame_idx, integrated_time_s, raw_std, parity, strict=False):
            predicted = ""
            if np.isfinite(threshold):
                predicted = "odd_like" if std_value >= threshold else "even_like"
            writer.writerow([idx, idx + 1, f"{time_s:.6f}", group, f"{std_value:.6f}", threshold, predicted])

    colors = {"odd": "#1f77b4", "even": "#d62728"}
    fig, ax = plt.subplots(figsize=(12, 6.5))
    for group_name in ("odd", "even"):
        mask = parity == group_name
        if not np.any(mask):
            continue
        ax.scatter(integrated_time_s[mask], raw_std[mask], s=20, alpha=0.8, color=colors[group_name], label=group_name)
    if np.isfinite(threshold):
        ax.axhline(threshold, color="black", linestyle="--", linewidth=1.2, label="Std threshold")
    ax.set_title("Raw Std by Frame Parity")
    ax.set_xlabel("Integrated time (s)")
    ax.set_ylabel("Raw std")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(run_folder / "raw_std_by_parity.png")
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(12, 8))
    for ax, group_name in zip(axes, ("odd", "even"), strict=False):
        mask = parity == group_name
        if not np.any(mask):
            ax.set_title(f"{group_name.title()} Frames")
            ax.text(0.5, 0.5, "No frames in this group", transform=ax.transAxes, ha="center", va="center")
            ax.axis("off")
            continue

        group_std = raw_std[mask]
        group_time = integrated_time_s[mask]
        window = min(9, group_std.size)
        if window % 2 == 0:
            window -= 1

        ax.plot(group_time, group_std, "o-", color=colors[group_name], markersize=3.5, linewidth=1.0, label="Raw std")
        if window >= 3:
            kernel = np.ones(window, dtype=float) / window
            trend = np.convolve(group_std, kernel, mode="same")
            ax.plot(group_time, trend, color="black", linewidth=1.5, label=f"Rolling mean ({window})")
        ax.set_title(f"{group_name.title()}-Frame Std Evolution")
        ax.set_xlabel("Integrated time (s)")
        ax.set_ylabel("Raw std")
        ax.grid(True, alpha=0.25)
        ax.legend(frameon=False)

    fig.tight_layout()
    fig.savefig(run_folder / "raw_std_within_parity.png")
    plt.close(fig)


def frame_review_dir_name(start_idx: int, review_count: int) -> str:
    end_idx = start_idx + review_count - 1
    return f"raw_matrix_review_{start_idx:04d}_{end_idx:04d}"


def frame_review_rows(
    raw_cm: np.ndarray,
    cm_scaled: np.ndarray,
    t_seconds: np.ndarray,
    pos_on_cm: np.ndarray,
    start_idx: int,
    review_count: int,
) -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    end_idx = min(start_idx + review_count, raw_cm.shape[0])
    for frame_idx in range(start_idx, end_idx):
        raw_frame = raw_cm[frame_idx]
        scaled_frame = cm_scaled[frame_idx]
        raw_abs = np.abs(raw_frame)
        rows.append(
            {
                "frame_index": frame_idx,
                "frame_number_1based": frame_idx + 1,
                "time_s": float(t_seconds[frame_idx]),
                "position_mm": float(pos_on_cm[frame_idx]),
                "label": "",
                "notes": "",
                "ch11_raw": float(raw_frame[0]),
                "ch11_scaled_v2": float(scaled_frame[0]),
                "raw_min": float(raw_frame.min()),
                "raw_max": float(raw_frame.max()),
                "raw_mean": float(raw_frame.mean()),
                "raw_std": float(raw_frame.std()),
                "raw_abs_max": float(raw_abs.max()),
                "raw_abs_p95": float(np.percentile(raw_abs, 95)),
                "scaled_std_v2": float(scaled_frame.std()),
                "scaled_abs_max_v2": float(np.abs(scaled_frame).max()),
            }
        )
    return rows


def save_frame_review_csv(review_dir: Path, rows: list[dict[str, float | int | str]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with (review_dir / "frame_review_index.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def save_frame_review_json(review_dir: Path, raw_cm: np.ndarray, start_idx: int, review_count: int) -> None:
    end_idx = min(start_idx + review_count, raw_cm.shape[0])
    payload = []
    for frame_idx in range(start_idx, end_idx):
        payload.append(
            {
                "frame_index": frame_idx,
                "frame_number_1based": frame_idx + 1,
                "matrix_8x8": raw_cm[frame_idx].reshape(8, 8).tolist(),
            }
        )
    (review_dir / "raw_matrices.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def save_frame_review_images(review_dir: Path, raw_cm: np.ndarray, start_idx: int, review_count: int) -> None:
    frames_dir = review_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    end_idx = min(start_idx + review_count, raw_cm.shape[0])
    if end_idx <= start_idx:
        return

    subset = raw_cm[start_idx:end_idx]
    vmax = float(np.percentile(np.abs(subset), 99))
    if not np.isfinite(vmax) or vmax <= 0:
        vmax = float(np.max(np.abs(subset)))
    if not np.isfinite(vmax) or vmax <= 0:
        vmax = 1.0

    for frame_idx in range(start_idx, end_idx):
        matrix = raw_cm[frame_idx].reshape(8, 8)
        fig, ax = plt.subplots(figsize=(6.8, 5.8))
        im = ax.imshow(matrix, cmap="coolwarm", origin="upper", vmin=-vmax, vmax=vmax)
        ax.set_title(f"Raw Matrix Frame {frame_idx} (#{frame_idx + 1})")
        ax.set_xlabel("Column")
        ax.set_ylabel("Row")
        ax.set_xticks(range(8))
        ax.set_yticks(range(8))
        for row in range(8):
            for col in range(8):
                ax.text(col, row, f"{matrix[row, col]:.0f}", ha="center", va="center", fontsize=7, color="black")
        fig.colorbar(im, ax=ax, shrink=0.88, label="Raw value")
        fig.tight_layout()
        fig.savefig(frames_dir / f"frame_{frame_idx:04d}.png")
        plt.close(fig)


def save_frame_review_contact_sheet(review_dir: Path, raw_cm: np.ndarray, start_idx: int, review_count: int) -> None:
    end_idx = min(start_idx + review_count, raw_cm.shape[0])
    n_frames = end_idx - start_idx
    if n_frames <= 0:
        return

    subset = raw_cm[start_idx:end_idx]
    vmax = float(np.percentile(np.abs(subset), 99))
    if not np.isfinite(vmax) or vmax <= 0:
        vmax = float(np.max(np.abs(subset)))
    if not np.isfinite(vmax) or vmax <= 0:
        vmax = 1.0

    ncols = 5
    nrows = math.ceil(n_frames / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(3.3 * ncols, 3.0 * nrows))
    axes_arr = np.atleast_1d(axes).ravel()

    for ax_idx, ax in enumerate(axes_arr):
        if ax_idx >= n_frames:
            ax.axis("off")
            continue
        frame_idx = start_idx + ax_idx
        matrix = raw_cm[frame_idx].reshape(8, 8)
        ax.imshow(matrix, cmap="coolwarm", origin="upper", vmin=-vmax, vmax=vmax)
        ax.set_title(f"{frame_idx}", fontsize=10)
        ax.set_xticks([])
        ax.set_yticks([])

    fig.suptitle("Raw Matrix Contact Sheet", fontsize=16)
    fig.tight_layout()
    fig.savefig(review_dir / "raw_matrix_contact_sheet.png")
    plt.close(fig)


def export_frame_review(
    run_folder: Path,
    raw_cm: np.ndarray,
    cm_scaled: np.ndarray,
    t_seconds: np.ndarray,
    pos_on_cm: np.ndarray,
    start_idx: int,
    review_count: int,
) -> Path:
    safe_start_idx = max(0, start_idx)
    safe_count = max(0, review_count)
    review_dir = run_folder / frame_review_dir_name(safe_start_idx, safe_count)
    review_dir.mkdir(parents=True, exist_ok=True)

    rows = frame_review_rows(raw_cm, cm_scaled, t_seconds, pos_on_cm, safe_start_idx, safe_count)
    save_frame_review_csv(review_dir, rows)
    save_frame_review_json(review_dir, raw_cm, safe_start_idx, safe_count)
    save_frame_review_images(review_dir, raw_cm, safe_start_idx, safe_count)
    save_frame_review_contact_sheet(review_dir, raw_cm, safe_start_idx, safe_count)
    return review_dir


def save_frames_per_position(run_folder: Path, bin_vals: np.ndarray, counts: np.ndarray, min_count: int) -> None:
    with (run_folder / "frames_per_position.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Position_mm", "FrameCount"])
        for position, count in zip(bin_vals, counts, strict=False):
            writer.writerow([f"{position:.6f}", int(count)])

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(bin_vals, counts, color="#3568b8", width=max(BIN_MM * 0.8, 0.02))
    ax.axhline(min_count, color="#c0392b", linestyle="--", label="Threshold")
    ax.set_title("Available Frames per Position (Filtered)")
    ax.set_xlabel("Position (mm)")
    ax.set_ylabel("Frame Count")
    ax.legend()
    fig.tight_layout()
    fig.savefig(run_folder / "frames_per_position_hist.png")
    plt.close(fig)


def build_bin_cumsums_and_counts(
    pair_diffs: np.ndarray,
    inverse: np.ndarray,
    valid_indices: np.ndarray,
    conversion_factor: float,
) -> tuple[list[np.ndarray], np.ndarray]:
    bin_cumsums: list[np.ndarray] = []
    counts = np.zeros(valid_indices.size, dtype=int)
    for b_idx, orig_idx in enumerate(valid_indices):
        members = pair_diffs[inverse == orig_idx]
        counts[b_idx] = members.shape[0]
        if members.size == 0:
            bin_cumsums.append(np.empty((0, pair_diffs.shape[1]), dtype=float))
            continue
        bin_cumsums.append(scale_to_urad2(np.cumsum(members, axis=0), conversion_factor))
    return bin_cumsums, counts


def save_all_pairs_plot(
    run_folder: Path, ts: np.ndarray, amps: np.ndarray, pair_labels_list: list[str], meta: Meta, kmin: int
) -> None:
    fig, ax = plt.subplots(figsize=(16, 9))
    colors = plt.cm.turbo(np.linspace(0, 1, amps.shape[1]))
    for idx, label in enumerate(pair_labels_list):
        ax.plot(ts, amps[:, idx], "-o", color=colors[idx], linewidth=1.0, markersize=4, label=label)

    ax.set_xlabel("Delay (ps)")
    ax.set_ylabel(r"Amplitude ($\mu rad^2$)")
    title_lines = [
        f"ALL Pairs Result at k={kmin}",
        f"Power: {np.nansum([meta.p1_mw, meta.p2_mw]):.2f}mW | Range: {meta.scan_range:.1f}mm | ShotNoise: {meta.shot_noise_result:.1f}",
    ]
    ax.set_title("\n".join(title_lines))
    if amps.shape[1] <= 20:
        ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=False)
    else:
        ax.text(
            0.01,
            0.98,
            "Legend suppressed (too many pairs).",
            transform=ax.transAxes,
            va="top",
            bbox=dict(facecolor="white", edgecolor="black"),
        )
    fig.tight_layout()
    fig.savefig(run_folder / "final_result_ALL_PAIRS.png")
    plt.close(fig)


def save_selected_pairs_plot(
    run_folder: Path,
    ts: np.ndarray,
    amps: np.ndarray,
    pair_labels_list: list[str],
    keep_indices: list[int],
) -> None:
    if not keep_indices:
        keep_indices = list(range(min(CRITICAL_PAIR_MAX_COUNT, len(pair_labels_list))))

    fig, ax = plt.subplots(figsize=(11, 7))
    for idx in keep_indices:
        ax.plot(ts, amps[:, idx], "o-", linewidth=1.8, markersize=4, label=pair_labels_list[idx])

    ax.set_xlabel("Delay (ps)")
    ax.set_ylabel(r"Amplitude ($\mu rad^2$)")
    ax.set_title("Critical Pairs Summary")
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=False)
    fig.tight_layout()
    fig.savefig(run_folder / "final_clean_result.png")
    plt.close(fig)


def save_loglog_eval(
    run_folder: Path,
    time_tail: np.ndarray,
    cm: np.ndarray,
    pairs: np.ndarray,
    labels: list[str],
    conversion_factor: float,
    keep_indices: list[int],
) -> None:
    if not keep_indices:
        keep_indices = list(range(min(CRITICAL_PAIR_MAX_COUNT, len(labels))))

    keep_arr = np.asarray(keep_indices, dtype=int)
    selected_pairs = pairs[keep_arr]
    pair_i1 = np.array([idx_lin(pair[0], pair[1]) for pair in selected_pairs], dtype=int)
    pair_i2 = np.array([idx_lin(pair[2], pair[3]) for pair in selected_pairs], dtype=int)
    diffs = cm[:, pair_i1] - cm[:, pair_i2]
    divisors = np.arange(1, len(time_tail) + 1, dtype=float)[:, None]
    run_means = np.cumsum(diffs, axis=0) / divisors
    yvals = np.abs(scale_to_urad2(run_means, conversion_factor))
    yvals[yvals <= 0] = np.nan

    fig, ax = plt.subplots(figsize=(9, 6.5))
    xvals = np.maximum(time_tail, FRAME_DT_S)
    for col_idx, pair_idx in enumerate(keep_indices):
        ax.loglog(xvals, yvals[:, col_idx], label=labels[pair_idx])
    ax.set_title("Log-Log Evaluation (Cleaned)")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel(r"|Running Mean| ($\mu rad^2$)")
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=False)
    fig.tight_layout()
    fig.savefig(run_folder / "loglog_eval.png")
    plt.close(fig)


def save_heatmaps(run_folder: Path, cm: np.ndarray, conversion_factor: float) -> None:
    matrix_mean = cm.mean(axis=0).reshape(8, 8)
    matrix_mse = ((cm - cm.mean(axis=0, keepdims=True)) ** 2).mean(axis=0).reshape(8, 8)
    matrix_mean_urad = scale_to_urad2(matrix_mean, conversion_factor)

    diag_offset = np.zeros((8, 8))
    for d in range(-7, 8):
        diag_vals = np.diag(matrix_mean, d)
        if diag_vals.size == 0:
            continue
        offset = diag_vals[-1]
        for k, val in enumerate(diag_vals):
            if d >= 0:
                i, j = k, k + d
            else:
                i, j = k - d, k
            diag_offset[i, j] = val - offset

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    payload = [
        (matrix_mean, "Mean Corr (V^2)"),
        (matrix_mse, "MSE Corr (V^4)"),
        (matrix_mean_urad, r"Mean Corr ($\mu rad^2$)"),
        (diag_offset, "Diagonal Tail-Offset (V^2)"),
    ]
    for ax, (data, title) in zip(axes.flat, payload, strict=False):
        im = ax.imshow(data, cmap="jet", origin="upper")
        ax.set_title(title)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(run_folder / "matrix_pattern_heatmaps.png")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    im0 = axes[0].imshow(matrix_mean, cmap="jet", origin="upper")
    axes[0].set_title("Mean Corr (V^2)")
    fig.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04)
    im1 = axes[1].imshow(matrix_mse, cmap="jet", origin="upper")
    axes[1].set_title("MSE Corr (V^4)")
    fig.colorbar(im1, ax=axes[1], fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(run_folder / "combined_heatmap_V2.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(matrix_mean_urad, cmap="jet", origin="upper")
    ax.set_title(r"Mean Corr ($\mu rad^2$)")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(run_folder / "heatmap_mean_urad2.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(diag_offset, cmap="jet", origin="upper")
    ax.set_title("Diagonal Tail-Offset (V^2)")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(run_folder / "diagonal_offset_matrix_V2.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(scale_to_urad2(diag_offset, conversion_factor), cmap="jet", origin="upper")
    ax.set_title(r"Diagonal Tail-Offset ($\mu rad^2$)")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(run_folder / "diagonal_offset_matrix_urad2.png")
    plt.close(fig)


def save_semilogy_grouped_64channels(run_folder: Path, cm: np.ndarray, conversion_factor: float) -> None:
    n_frames = cm.shape[0]
    xvals = np.arange(1, n_frames + 1, dtype=float) * FRAME_DT_S
    acu_sums_64 = np.cumsum(cm, axis=0) / np.arange(1, n_frames + 1)[:, None]

    for suffix, transform, ylabel in [
        ("V2", lambda x: np.abs(x), "Abs Running Mean (V^2)"),
        ("urad2", lambda x: np.abs(scale_to_urad2(x, conversion_factor)), r"Abs Running Mean ($\mu rad^2$)"),
    ]:
        fig, axes = plt.subplots(2, 4, figsize=(16, 9))
        for row in range(8):
            ax = axes.flat[row]
            for col in range(8):
                idx = row * 8 + col
                yvals = transform(acu_sums_64[:, idx])
                yvals[yvals <= 0] = np.nan
                ax.semilogy(xvals, yvals, label=f"({row+1},{col+1})", linewidth=1.0)
            ax.set_title(f"Row {row + 1}")
            ax.set_xlabel("Time (s)")
            ax.set_ylabel(ylabel)
            ax.grid(True, which="both", alpha=0.25)
        fig.tight_layout()
        fig.savefig(run_folder / f"semilogy_grouped_64channels_{suffix}.png")
        plt.close(fig)


def dedupe_pairs(pairs: np.ndarray, labels: list[str]) -> tuple[np.ndarray, list[str]]:
    seen: set[tuple[int, int, int, int]] = set()
    keep_indices: list[int] = []
    for idx, (r1, c1, r2, c2) in enumerate(pairs):
        key = (min(r1, r2), min(c1, c2), max(r1, r2), max(c1, c2))
        if key not in seen:
            seen.add(key)
            keep_indices.append(idx)
    return pairs[keep_indices], [labels[idx] for idx in keep_indices]


def save_loglog_eval_pairs_runmean(run_folder: Path, cm: np.ndarray, pairs: np.ndarray, labels: list[str], conversion_factor: float) -> None:
    use_abs = True
    warmup_s = 1.0
    start_idx = max(0, round(warmup_s / FRAME_DT_S))
    time_tail = np.arange(start_idx, cm.shape[0], dtype=float) * FRAME_DT_S
    time_tail = time_tail - time_tail[0] if time_tail.size else np.array([], dtype=float)
    if time_tail.size == 0:
        return

    pairs_uni, labels_uni = dedupe_pairs(pairs, labels)
    pair_i1 = np.array([idx_lin(pair[0], pair[1]) for pair in pairs_uni], dtype=int)
    pair_i2 = np.array([idx_lin(pair[2], pair[3]) for pair in pairs_uni], dtype=int)
    diff_v2 = cm[start_idx:, pair_i1] - cm[start_idx:, pair_i2]
    run_mean = np.cumsum(diff_v2, axis=0) / np.arange(1, diff_v2.shape[0] + 1, dtype=float)[:, None]
    curves = scale_to_urad2(run_mean, conversion_factor)
    if use_abs:
        curves = np.abs(curves)
    curves[~np.isfinite(curves) | (curves <= 0)] = np.nan

    max_lines_per_plot = 8
    for group_idx, lo in enumerate(range(0, curves.shape[1], max_lines_per_plot), start=1):
        hi = min(lo + max_lines_per_plot, curves.shape[1])
        fig, ax = plt.subplots(figsize=(10, 7))
        for idx in range(lo, hi):
            ax.plot(time_tail, curves[:, idx], linewidth=1.8, label=labels_uni[idx])
        ax.set_xscale("log")
        if use_abs:
            ax.set_yscale("log")
            ax.set_ylabel(r"Abs Running Mean ($\mu rad^2$)")
        else:
            ax.set_ylabel(r"Running Mean ($\mu rad^2$)")
        ax.set_xlabel("Time (s)")
        ax.set_title(f"Running-Mean of Cumsum, Pairs {lo + 1}-{hi}")
        ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=False)
        fig.tight_layout()
        fig.savefig(run_folder / f"loglog_eval_pairs_runmean_urad2_group_{group_idx:02d}.png")
        plt.close(fig)


def save_variation_and_fft(
    run_folder: Path,
    ts: np.ndarray,
    counts: np.ndarray,
    bin_cumsums: list[np.ndarray],
    labels: list[str],
    keep_indices: list[int],
) -> None:
    if counts.size == 0:
        return

    if not keep_indices:
        keep_indices = list(range(min(5, len(labels))))

    best_bin_idx = int(np.argmax(counts))

    fig_var, ax_var = plt.subplots(figsize=(12, 7))
    fig_fft, ax_fft = plt.subplots(figsize=(12, 7))
    best_bin = bin_cumsums[best_bin_idx]
    for idx in keep_indices:
        if best_bin.size == 0:
            continue
        v = best_bin[:, idx]
        if v.size <= 2:
            continue
        raw_vals = np.concatenate(([v[0]], np.diff(v)))
        if raw_vals.size > 1:
            ax_var.plot(np.arange(1, raw_vals.size) * FRAME_DT_S, np.diff(raw_vals), label=labels[idx], linewidth=1.2)

        length = raw_vals.size
        fft_vals = np.fft.rfft(raw_vals)
        spectrum = np.abs(fft_vals / length)
        if spectrum.size > 2:
            spectrum[1:-1] *= 2
        freqs = np.fft.rfftfreq(length, d=FRAME_DT_S)
        ax_fft.plot(freqs, spectrum, label=labels[idx], linewidth=1.2)

    ax_var.set_title("Frame Variation (Cleaned)")
    ax_var.set_xlabel("Time (s)")
    ax_var.set_ylabel(r"$\Delta$ amplitude")
    ax_var.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=False)
    fig_var.tight_layout()
    fig_var.savefig(run_folder / "variation_vs_time.png")
    plt.close(fig_var)

    ax_fft.set_title("FFT Spectrum (Cleaned)")
    ax_fft.set_xlabel("Frequency (Hz)")
    ax_fft.set_ylabel("Amplitude")
    ax_fft.set_yscale("log")
    ax_fft.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=False)
    fig_fft.tight_layout()
    fig_fft.savefig(run_folder / "fft_spectrum.png")
    plt.close(fig_fft)


def save_signal_emergence_movie(
    run_folder: Path,
    ts: np.ndarray,
    counts: np.ndarray,
    bin_cumsums: list[np.ndarray],
    labels: list[str],
    keep_indices: list[int],
) -> None:
    if imageio is None or counts.size == 0:
        warnings.warn("imageio is not installed, so signal_emergence.mp4 was skipped.")
        return

    finite_ts = ts[np.isfinite(ts)]
    if finite_ts.size == 0:
        warnings.warn("No finite delay values were available for signal_emergence.mp4.")
        return

    if not keep_indices:
        keep_indices = list(range(min(5, len(labels))))

    k_max_common = int(np.min(counts))
    if k_max_common < 2:
        warnings.warn("Not enough frames per bin to build signal_emergence.mp4.")
        return

    n_movie_frames = min(400, k_max_common)
    frame_steps = np.unique(np.round(np.linspace(1, k_max_common, n_movie_frames)).astype(int))
    selected_bin_cumsums = [
        bin_curve[:, keep_indices] if bin_curve.size else np.empty((0, len(keep_indices)), dtype=float)
        for bin_curve in bin_cumsums
    ]

    movie_path = run_folder / "signal_emergence.mp4"
    fig, ax = plt.subplots(figsize=(12, 7))
    line_handles = []
    for idx in keep_indices:
        (line,) = ax.plot([], [], "o-", linewidth=1.5, markersize=4, label=labels[idx])
        line_handles.append(line)
    ax.set_xlabel("Delay (ps)")
    ax.set_ylabel(r"Amplitude ($\mu rad^2$)")
    ax.set_xlim(float(np.min(finite_ts)), float(np.max(finite_ts)))
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=False)

    with imageio.get_writer(movie_path, fps=15, macro_block_size=1) as writer:
        for k in frame_steps:
            current_matrix = np.full((len(keep_indices), len(ts)), np.nan, dtype=float)
            for b_idx, bin_curve in enumerate(selected_bin_cumsums):
                if bin_curve.shape[0] >= k:
                    current_matrix[:, b_idx] = bin_curve[k - 1, :] / k

            current_stack = []
            for line_idx, line in enumerate(line_handles):
                current = current_matrix[line_idx]
                line.set_data(ts, current)
                current_stack.append(current)

            if current_stack:
                current_arr = np.asarray(current_stack, dtype=float)
                finite_vals = current_arr[np.isfinite(current_arr)]
                if finite_vals.size > 0:
                    y_min = float(np.min(finite_vals))
                    y_max = float(np.max(finite_vals))
                    span = y_max - y_min
                    pad = max(0.05 * span, 0.05 * max(abs(y_min), abs(y_max), 1.0), 1e-6)
                    if span < 1e-12:
                        y_min -= pad
                        y_max += pad
                    else:
                        y_min -= pad
                        y_max += pad
                    ax.set_ylim(y_min, y_max)

            ax.set_title(f"Integration: {k} Frames ({k * FRAME_DT_S:.2f}s)")
            fig.tight_layout()
            fig.canvas.draw()
            frame = np.asarray(fig.canvas.buffer_rgba())[:, :, :3]
            writer.append_data(frame)
    plt.close(fig)


def save_grouped_loglog_convergence(
    run_folder: Path,
    bin_vals: np.ndarray,
    bin_cumsums: list[np.ndarray],
    labels: list[str],
    pair_count: int,
) -> None:
    groups = [
        list(range(1, 8)),
        list(range(8, 14)),
        list(range(14, 19)),
        list(range(19, 23)),
        list(range(23, 26)),
        list(range(26, 28)),
        [28],
        list(range(29, 35)),
        list(range(35, 40)),
        list(range(40, 44)),
        list(range(44, 47)),
        list(range(47, 49)),
        [49],
    ]

    if len(bin_vals) <= 1:
        return

    for g_idx, group in enumerate(groups, start=1):
        idx_list = [idx - 1 for idx in group if idx - 1 < pair_count]
        if not idx_list:
            continue
        n_plots = len(idx_list)
        n_rows = math.ceil(math.sqrt(n_plots))
        n_cols = math.ceil(n_plots / n_rows)
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(16, 9), squeeze=False)
        axes_flat = axes.flatten()
        for ax_idx, pair_idx in enumerate(idx_list):
            ax = axes_flat[ax_idx]
            frame_counts = [bin_curve.shape[0] for bin_curve in bin_cumsums if bin_curve.shape[0] > 0]
            if not frame_counts:
                continue
            frames_per_bin = min(frame_counts)
            time_axis = np.arange(1, frames_per_bin + 1, dtype=float) * FRAME_DT_S
            color_map = plt.cm.jet(np.linspace(0, 1, len(bin_vals)))
            for b_idx, bin_curve in enumerate(bin_cumsums):
                if bin_curve.shape[0] < frames_per_bin:
                    continue
                curve = bin_curve[:frames_per_bin, pair_idx]
                cumavg = curve[:frames_per_bin] / np.arange(1, frames_per_bin + 1)
                y = np.abs(cumavg)
                y[y <= 0] = np.nan
                ax.loglog(time_axis, y, color=color_map[b_idx], linewidth=1)
            ax.set_title(labels[pair_idx], fontsize=10)
            ax.grid(True, which="both", alpha=0.25)
            if ax_idx >= (n_rows - 1) * n_cols:
                ax.set_xlabel("Time (s)")
            if ax_idx % n_cols == 0:
                ax.set_ylabel(r"|$\mu rad^2$|")
        for ax in axes_flat[n_plots:]:
            ax.axis("off")
        fig.suptitle(f"Log-Log Convergence (Group {g_idx})", fontsize=14)
        fig.tight_layout()
        fig.savefig(run_folder / f"loglog_convergence_group{g_idx}.png")
        plt.close(fig)


def update_metadata_json(run_folder: Path, meta: Meta) -> None:
    json_path = run_folder / "metadata.json"
    if json_path.is_file():
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
    else:
        payload = {}

    physics = payload.setdefault("PhysicsData", {})
    physics["Power_mW_1"] = None if not np.isfinite(meta.p1_mw) else meta.p1_mw
    physics["Power_mW_2"] = None if not np.isfinite(meta.p2_mw) else meta.p2_mw
    physics["Sensitivity_V_photon"] = None if not np.isfinite(meta.sensitivity) else meta.sensitivity
    physics["ShotNoise1_V"] = None if not np.isfinite(meta.shot_noise1_v) else meta.shot_noise1_v
    physics["ShotNoise2_V"] = None if not np.isfinite(meta.shot_noise2_v) else meta.shot_noise2_v
    physics["SignalLevel_V2_rtHz"] = None if not np.isfinite(meta.signal_level) else meta.signal_level
    physics["ConversionFactor_V2_rad2"] = None if not np.isfinite(meta.conversion_factor) else meta.conversion_factor
    physics["ShotNoiseResult_urad2_rtHz"] = None if not np.isfinite(meta.shot_noise_result) else meta.shot_noise_result
    physics["ScanRange_mm"] = meta.scan_range
    physics["ScanMin_mm"] = meta.scan_min
    physics["ScanMax_mm"] = meta.scan_max

    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_pipeline(
    target_folder: str,
    review_first_n: int = 0,
    review_start_idx: int = 0,
    review_only: bool = False,
) -> None:
    style_matplotlib()
    run_folder = Path(target_folder)

    cm_path = run_folder / "cm.bin"
    profile_path = run_folder / "profile.txt"
    pos_path = find_first(run_folder, ["delay_stage_positions.log", "delay_stage_positions.csv"])
    sensitivity_path = run_folder / "sensitivity.log"

    if not cm_path.is_file():
        raise FileNotFoundError("cm.bin not found.")

    raw_cm_all = read_cm64(cm_path)
    n_frames_all = raw_cm_all.shape[0]
    t_seconds_all, t_absolute_seconds_all = read_times_from_profile(profile_path, n_frames_all)
    save_raw_std_analysis(run_folder, raw_cm_all, t_seconds_all)

    raw_cm = raw_cm_all
    t_seconds = t_seconds_all
    t_absolute_seconds = t_absolute_seconds_all
    if ENABLE_EVEN_FRAMES_ONLY:
        raw_cm = raw_cm[::2]
        t_seconds = t_seconds[::2]
        t_absolute_seconds = t_absolute_seconds[::2]
    cm = raw_cm * SCALE_FACTOR
    n_frames = raw_cm.shape[0]
    base_dt = datetime(1900, 1, 1)
    t_datetimes = [base_dt + timedelta(seconds=float(s)) for s in t_absolute_seconds]

    meta = read_sensitivity_log(run_folder)
    conversion_factor = meta.conversion_factor

    if pos_path is None:
        pos_on_cm = np.full(n_frames, 25.058, dtype=float)
        meta.scan_range = 0.0
        meta.scan_min = 25.058
        meta.scan_max = 25.058
    else:
        pos_time, pos_val = read_positions_series(pos_path)
        pos_dt, pos_val_aligned = align_position_times(pos_time, pos_val, t_absolute_seconds)
        if pos_dt.size == 0:
            pos_on_cm = np.full(n_frames, float(pos_val[0]), dtype=float)
        elif pos_dt.size == 1:
            pos_on_cm = np.full(n_frames, float(pos_val_aligned[0]), dtype=float)
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

    if review_first_n > 0:
        review_dir = export_frame_review(
            run_folder,
            raw_cm,
            cm,
            t_seconds,
            pos_on_cm,
            review_start_idx,
            review_first_n,
        )
        print(f"Saved raw-matrix review assets to: {review_dir}", flush=True)
        if review_only:
            return

    dirty_mask = cm[:, 0] > SATURATION_THRESHOLD_CH11
    if ENABLE_SATURATION_CLEANUP and np.any(dirty_mask):
        keep = ~dirty_mask
        cm = cm[keep]
        t_seconds = t_seconds[keep]
        pos_on_cm = pos_on_cm[keep]
        t_datetimes = [dt for dt, k in zip(t_datetimes, keep, strict=False) if bool(k)]

    save_histogram(run_folder, cm[:, 0])

    if ENABLE_DROPPED_WINDOW_GATING:
        dropped_mask = dropped_window_mask(t_seconds, t_datetimes, run_folder / "dropped_window.log")
        if np.any(dropped_mask):
            keep = ~dropped_mask
            cm = cm[keep]
            t_seconds = t_seconds[keep]
            pos_on_cm = pos_on_cm[keep]
            t_datetimes = [dt for dt, k in zip(t_datetimes, keep, strict=False) if bool(k)]

    dirty_mask = cm[:, 0] > SATURATION_THRESHOLD_CH11
    if ENABLE_SATURATION_CLEANUP and np.any(dirty_mask):
        keep = ~dirty_mask
        cm = cm[keep]
        t_seconds = t_seconds[keep]
        pos_on_cm = pos_on_cm[keep]
        t_datetimes = [dt for dt, k in zip(t_datetimes, keep, strict=False) if bool(k)]

    frame_rms = cm.std(axis=1)
    rms_cutoff = otsu_like_threshold(frame_rms)
    save_variance_gating_check(run_folder, frame_rms, rms_cutoff)
    if ENABLE_VARIANCE_GATING:
        keep = frame_rms >= rms_cutoff
        cm = cm[keep]
        t_seconds = t_seconds[keep]
        pos_on_cm = pos_on_cm[keep]
        t_datetimes = [dt for dt, k in zip(t_datetimes, keep, strict=False) if bool(k)]

    pairs = PAIRS.copy()
    labels = pair_labels(pairs)
    if ENABLE_CHANNEL_HEALTH_GATING:
        channel_kurt = kurtosis_per_channel(cm)
        bad_channels = {idx for idx, value in enumerate(channel_kurt) if np.isfinite(value) and value > 5.0}
        valid_pair_mask = []
        for pair in pairs:
            i1 = idx_lin(pair[0], pair[1])
            i2 = idx_lin(pair[2], pair[3])
            valid_pair_mask.append(i1 not in bad_channels and i2 not in bad_channels)
        valid_pair_mask_arr = np.asarray(valid_pair_mask, dtype=bool)
        pairs = pairs[valid_pair_mask_arr]
        labels = [label for label, keep in zip(labels, valid_pair_mask_arr, strict=False) if keep]

    pos_bin = np.round(pos_on_cm / BIN_MM) * BIN_MM
    unique_bins, inverse = np.unique(pos_bin, return_inverse=True)
    counts = np.bincount(inverse)
    mean_positive = counts[counts > 0].mean() if np.any(counts > 0) else 0
    min_count = int(round(REL_THRESHOLD * mean_positive))
    keep_bins = counts >= min_count
    bin_vals = unique_bins[keep_bins]
    counts = counts[keep_bins]
    valid_indices = np.where(keep_bins)[0]
    save_frames_per_position(run_folder, bin_vals, counts, min_count)

    pair_i1 = np.array([idx_lin(pair[0], pair[1]) for pair in pairs], dtype=int)
    pair_i2 = np.array([idx_lin(pair[2], pair[3]) for pair in pairs], dtype=int)
    pair_diffs = cm[:, pair_i1] - cm[:, pair_i2]

    bin_cumsums, counts = build_bin_cumsums_and_counts(pair_diffs, inverse, valid_indices, conversion_factor)

    if counts.size == 0 or not np.any(counts > 0):
        raise ValueError("No valid position bins remained after filtering.")

    kmin = int(np.min(counts[counts > 0]))
    amps = np.full((len(bin_vals), len(labels)), np.nan, dtype=float)
    for b_idx, bin_curve in enumerate(bin_cumsums):
        if bin_curve.shape[0] < kmin or kmin <= 0:
            continue
        amps[b_idx, :] = bin_curve[kmin - 1, :] / kmin

    ts = bin_vals * MM_TO_PS
    order = np.argsort(ts)
    ts = ts[order]
    amps = amps[order]
    critical_keep_indices, critical_details = critical_pair_indices(amps, pairs)
    if not critical_keep_indices:
        critical_keep_indices = list(range(min(CRITICAL_PAIR_MAX_COUNT, len(labels))))
    write_critical_pairs_summary(run_folder, critical_details, labels)

    csv_headers = [label.replace("(", "").replace(")", "").replace("-", "_").replace(",", "_") for label in labels]
    with (run_folder / "final_amplitudes_all_pairs.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Delay_ps", *csv_headers])
        for delay, row in zip(ts, amps, strict=False):
            writer.writerow([f"{delay:.6f}", *row])

    save_all_pairs_plot(run_folder, ts, amps, labels, meta, kmin)
    save_selected_pairs_plot(run_folder, ts, amps, labels, critical_keep_indices)
    save_loglog_eval(
        run_folder,
        np.maximum(t_seconds - t_seconds[0], FRAME_DT_S),
        cm,
        pairs,
        labels,
        conversion_factor,
        critical_keep_indices,
    )
    save_heatmaps(run_folder, cm, conversion_factor)
    save_semilogy_grouped_64channels(run_folder, cm, conversion_factor)
    save_loglog_eval_pairs_runmean(run_folder, cm, pairs, labels, conversion_factor)
    save_grouped_loglog_convergence(run_folder, bin_vals, bin_cumsums, labels, len(labels))
    save_variation_and_fft(run_folder, ts, counts, bin_cumsums, labels, critical_keep_indices)
    save_signal_emergence_movie(run_folder, ts, counts, bin_cumsums, labels, critical_keep_indices)
    update_metadata_json(run_folder, meta)


def main() -> None:
    parser = argparse.ArgumentParser(description="Python translation of the MATLAB cm_pipeline_all_in_one post-processing pipeline.")
    parser.add_argument(
        "run_folders",
        nargs="*",
        help="One or more run folders that contain cm.bin and related logs.",
    )
    parser.add_argument(
        "--review-first-n",
        type=int,
        default=0,
        help="Export the first N raw 8x8 matrices, per-frame stats, and labeling files for contamination review.",
    )
    parser.add_argument(
        "--review-start-idx",
        type=int,
        default=0,
        help="Zero-based frame index to start the raw matrix review export from.",
    )
    parser.add_argument(
        "--review-only",
        action="store_true",
        help="Only export the raw matrix review assets and skip the rest of the pipeline.",
    )
    args = parser.parse_args()

    run_folders = list(args.run_folders)
    if not run_folders:
        root = tk.Tk()
        root.withdraw()
        selected = filedialog.askdirectory(
            title="Select the Data Run Folder",
            initialdir=str(Path(r"D:\Quantum Squeezing Project\DataFiles")),
        )
        root.destroy()
        if not selected:
            raise SystemExit("No folder selected. Cancelled.")
        run_folders = [selected]

    total_runs = len(run_folders)
    for run_idx, run_folder in enumerate(run_folders, start=1):
        print(f"[{run_idx}/{total_runs}] Processing {run_folder}", flush=True)
        run_pipeline(
            run_folder,
            review_first_n=args.review_first_n,
            review_start_idx=args.review_start_idx,
            review_only=args.review_only,
        )


if __name__ == "__main__":
    main()
