from __future__ import annotations

import argparse
import csv
import json
import math
import re
import tkinter as tk
import warnings
from datetime import datetime
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


FRAME_DT_S = 0.025
SCALE_FACTOR = (0.24**2) / (32768**2) * 100
DEFAULT_POSITION_MM = 25.058
DEFAULT_REVIEW_COUNT = 100


def parse_time_string(value: str) -> datetime:
    for fmt in ("%H:%M:%S.%f", "%H:%M:%S"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    raise ValueError(f"Unsupported time format: {value}")


def read_cm64(path: Path) -> np.ndarray:
    raw = np.fromfile(path, dtype=np.float64)
    if raw.size % 64 != 0:
        raise ValueError(f"{path} does not contain a whole number of 64-wide frames.")
    return raw.reshape((-1, 64))


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
    if pos_time.size == 0 or pos_val.size == 0 or cm_absolute_seconds.size == 0:
        return np.array([], dtype=float), np.array([], dtype=float)

    dt = pos_time - cm_absolute_seconds[0]
    valid_mask = np.isfinite(dt) & np.isfinite(pos_val)
    if not np.any(valid_mask):
        return np.array([], dtype=float), np.array([], dtype=float)

    dt = dt[valid_mask]
    pv = pos_val[valid_mask]
    unique_dt, unique_indices = np.unique(dt, return_index=True)
    return unique_dt, pv[unique_indices]


def find_first(run_folder: Path, names: list[str]) -> Path | None:
    for name in names:
        candidate = run_folder / name
        if candidate.is_file():
            return candidate
    return None


def style_matplotlib() -> None:
    plt.style.use("default")
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.grid": True,
            "grid.alpha": 0.2,
            "grid.linestyle": "--",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "font.size": 10,
            "axes.titlesize": 14,
            "axes.labelsize": 11,
            "savefig.dpi": 220,
        }
    )


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
    bin_mm: float,
) -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    end_idx = min(start_idx + review_count, raw_cm.shape[0])
    for frame_idx in range(start_idx, end_idx):
        raw_frame = raw_cm[frame_idx]
        scaled_frame = cm_scaled[frame_idx]
        raw_abs = np.abs(raw_frame)
        position_mm = float(pos_on_cm[frame_idx])
        rows.append(
            {
                "frame_index": frame_idx,
                "frame_number_1based": frame_idx + 1,
                "index_parity": "even" if frame_idx % 2 == 0 else "odd",
                "time_s": float(t_seconds[frame_idx]),
                "position_mm": position_mm,
                "position_bin_mm": float(np.round(position_mm / bin_mm) * bin_mm),
                "label": "",
                "notes": "",
                "ch11_raw": float(raw_frame[0]),
                "ch11_scaled_v2": float(scaled_frame[0]),
                "raw_min": float(raw_frame.min()),
                "raw_max": float(raw_frame.max()),
                "raw_mean": float(raw_frame.mean()),
                "raw_std": float(raw_frame.std()),
                "raw_abs_mean": float(raw_abs.mean()),
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


def save_frame_review_parity_videos(review_dir: Path, rows: list[dict[str, float | int | str]]) -> None:
    if imageio is None or not rows:
        if imageio is None:
            warnings.warn("imageio is not installed, so parity review videos were skipped.")
        return

    frames_dir = review_dir / "frames"
    parity_groups = {
        "all": rows,
        "even": [row for row in rows if row["index_parity"] == "even"],
        "odd": [row for row in rows if row["index_parity"] == "odd"],
    }

    for parity_name, parity_rows in parity_groups.items():
        if not parity_rows:
            continue

        movie_path = review_dir / f"raw_matrix_{parity_name}.mp4"
        with imageio.get_writer(movie_path, fps=8, macro_block_size=1) as writer:
            for row in parity_rows:
                frame_idx = int(row["frame_index"])
                frame_path = frames_dir / f"frame_{frame_idx:04d}.png"
                if frame_path.is_file():
                    writer.append_data(imageio.imread(frame_path))


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


def save_position_diagnostic(review_dir: Path, rows: list[dict[str, float | int | str]], bin_mm: float) -> None:
    if not rows:
        return

    frame_idx = np.asarray([int(row["frame_index"]) for row in rows], dtype=int)
    positions = np.asarray([float(row["position_mm"]) for row in rows], dtype=float)
    bins = np.asarray([float(row["position_bin_mm"]) for row in rows], dtype=float)

    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.plot(frame_idx, positions, marker="o", linewidth=1.2, label="Interpolated position")
    ax.step(frame_idx, bins, where="mid", linewidth=1.5, label=f"Rounded bin ({bin_mm:.3f} mm)")
    ax.set_xlabel("Frame index")
    ax.set_ylabel("Position (mm)")
    ax.set_title("Position Diagnostic for Reviewed Frames")
    ax.legend()
    fig.tight_layout()
    fig.savefig(review_dir / "position_diagnostic.png")
    plt.close(fig)


def assign_std_threshold_labels(rows: list[dict[str, float | int | str]]) -> float | None:
    if not rows:
        return None

    odd_values = np.asarray(
        [float(row["raw_std"]) for row in rows if row["index_parity"] == "odd"],
        dtype=float,
    )
    even_values = np.asarray(
        [float(row["raw_std"]) for row in rows if row["index_parity"] == "even"],
        dtype=float,
    )
    if odd_values.size == 0 or even_values.size == 0:
        return None

    threshold = 0.5 * (float(np.mean(odd_values)) + float(np.mean(even_values)))
    odd_center = float(np.mean(odd_values))
    even_center = float(np.mean(even_values))

    for row in rows:
        raw_std = float(row["raw_std"])
        predicted_group = "odd_like" if raw_std >= threshold else "even_like"
        expected_group = "odd_like" if row["index_parity"] == "odd" else "even_like"
        row["raw_std_threshold"] = threshold
        row["raw_std_predicted_group"] = predicted_group
        row["raw_std_expected_group"] = expected_group
        row["raw_std_matches_parity"] = predicted_group == expected_group
        row["raw_std_distance_to_odd"] = abs(raw_std - odd_center)
        row["raw_std_distance_to_even"] = abs(raw_std - even_center)

    return threshold


def save_frame_metric_parity_diagnostics(
    review_dir: Path, rows: list[dict[str, float | int | str]]
) -> None:
    if not rows:
        return

    frame_idx = np.asarray([int(row["frame_index"]) for row in rows], dtype=int)
    parity = np.asarray([str(row["index_parity"]) for row in rows], dtype=object)
    raw_mean = np.asarray([float(row["raw_mean"]) for row in rows], dtype=float)
    raw_std = np.asarray([float(row["raw_std"]) for row in rows], dtype=float)
    raw_abs_mean = np.asarray([float(row["raw_abs_mean"]) for row in rows], dtype=float)
    raw_abs_max = np.asarray([float(row["raw_abs_max"]) for row in rows], dtype=float)

    metrics = [
        ("raw_std", raw_std, "Raw std"),
        ("raw_mean", raw_mean, "Raw mean"),
        ("raw_abs_mean", raw_abs_mean, "Raw |x| mean"),
        ("raw_abs_max", raw_abs_max, "Raw |x| max"),
    ]
    colors = {"even": "#d62728", "odd": "#1f77b4"}
    threshold = rows[0].get("raw_std_threshold")

    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
    axes_flat = axes.ravel()
    for ax, (_, values, ylabel) in zip(axes_flat, metrics, strict=False):
        for group_name in ("odd", "even"):
            mask = parity == group_name
            if not np.any(mask):
                continue
            ax.scatter(
                frame_idx[mask],
                values[mask],
                s=20,
                alpha=0.75,
                color=colors[group_name],
                label=group_name if ylabel == "Raw mean" else None,
            )
        if ylabel == "Raw std" and threshold is not None:
            ax.axhline(float(threshold), color="black", linestyle="--", linewidth=1.2, label="Std threshold")
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.25)
    axes_flat[0].set_title("Per-Frame Metrics by Parity")
    axes_flat[0].legend(frameon=False)
    axes_flat[2].set_xlabel("Frame index")
    axes_flat[3].set_xlabel("Frame index")
    fig.tight_layout()
    fig.savefig(review_dir / "frame_metrics_by_parity.png")
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=False)
    for ax, group_name in zip(axes, ("odd", "even"), strict=False):
        mask = parity == group_name
        if not np.any(mask):
            ax.set_title(f"{group_name.title()} Frames")
            ax.text(0.5, 0.5, "No frames in this group", transform=ax.transAxes, ha="center", va="center")
            ax.axis("off")
            continue

        group_values = raw_std[mask]
        group_order = np.arange(group_values.size, dtype=int)
        group_baseline = float(np.mean(group_values))
        centered_values = group_values - group_baseline
        window = min(9, group_values.size)
        if window % 2 == 0:
            window -= 1
        if window >= 3:
            kernel = np.ones(window, dtype=float) / window
            trend = np.convolve(group_values, kernel, mode="same")
            ax.plot(group_order, trend, color="black", linewidth=1.5, label=f"Rolling mean ({window})")

        ax.plot(
            group_order,
            group_values,
            "o-",
            color=colors[group_name],
            markersize=3.5,
            linewidth=1.0,
            alpha=0.8,
            label="Raw std",
        )
        ax.plot(
            group_order,
            centered_values,
            color="#2f2f2f",
            linewidth=1.0,
            alpha=0.85,
            linestyle="--",
            label="Centered raw std",
        )
        ax.set_title(f"{group_name.title()}-Frame Std Evolution")
        ax.set_xlabel(f"{group_name.title()} frame order")
        ax.set_ylabel("Raw std")
        ax.grid(True, alpha=0.25)
        ax.legend(frameon=False)

    fig.tight_layout()
    fig.savefig(review_dir / "frame_std_within_parity.png")
    plt.close(fig)


def save_summary(review_dir: Path, rows: list[dict[str, float | int | str]], bin_mm: float) -> None:
    if not rows:
        return
    positions = np.asarray([float(row["position_mm"]) for row in rows], dtype=float)
    bins = np.asarray([float(row["position_bin_mm"]) for row in rows], dtype=float)
    summary = {
        "reviewed_frames": len(rows),
        "even_frames": sum(1 for row in rows if row["index_parity"] == "even"),
        "odd_frames": sum(1 for row in rows if row["index_parity"] == "odd"),
        "raw_std_threshold": rows[0].get("raw_std_threshold"),
        "raw_std_matches_parity_count": sum(1 for row in rows if row.get("raw_std_matches_parity")),
        "bin_mm": bin_mm,
        "position_min_mm": float(np.min(positions)),
        "position_max_mm": float(np.max(positions)),
        "unique_bins_mm": [float(value) for value in np.unique(bins)],
    }
    (review_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def load_positions_for_frames(run_folder: Path, n_frames: int, t_seconds: np.ndarray, t_absolute_seconds: np.ndarray) -> np.ndarray:
    pos_path = find_first(run_folder, ["delay_stage_positions.log", "delay_stage_positions.csv"])
    if pos_path is None:
        return np.full(n_frames, DEFAULT_POSITION_MM, dtype=float)

    pos_time, pos_val = read_positions_series(pos_path)
    pos_dt, pos_val_aligned = align_position_times(pos_time, pos_val, t_absolute_seconds)
    if pos_dt.size == 0:
        return np.full(n_frames, float(pos_val[0]), dtype=float)
    if pos_dt.size == 1:
        return np.full(n_frames, float(pos_val_aligned[0]), dtype=float)
    return np.interp(
        t_seconds,
        pos_dt,
        pos_val_aligned,
        left=pos_val_aligned[0],
        right=pos_val_aligned[-1],
    )


def export_raw_frame_review(run_folder: Path, review_count: int, start_idx: int, bin_mm: float) -> Path:
    cm_path = run_folder / "cm.bin"
    if not cm_path.is_file():
        raise FileNotFoundError(f"cm.bin not found in {run_folder}")

    raw_cm = read_cm64(cm_path)
    scaled_cm = raw_cm * SCALE_FACTOR
    n_frames = raw_cm.shape[0]
    t_seconds, t_absolute_seconds = read_times_from_profile(run_folder / "profile.txt", n_frames)
    pos_on_cm = load_positions_for_frames(run_folder, n_frames, t_seconds, t_absolute_seconds)

    review_dir = run_folder / frame_review_dir_name(start_idx, review_count)
    review_dir.mkdir(parents=True, exist_ok=True)

    rows = frame_review_rows(raw_cm, scaled_cm, t_seconds, pos_on_cm, start_idx, review_count, bin_mm)
    assign_std_threshold_labels(rows)
    save_frame_review_csv(review_dir, rows)
    save_frame_review_json(review_dir, raw_cm, start_idx, review_count)
    save_frame_review_images(review_dir, raw_cm, start_idx, review_count)
    save_frame_review_parity_videos(review_dir, rows)
    save_frame_review_contact_sheet(review_dir, raw_cm, start_idx, review_count)
    save_position_diagnostic(review_dir, rows, bin_mm)
    save_frame_metric_parity_diagnostics(review_dir, rows)
    save_summary(review_dir, rows, bin_mm)
    return review_dir


def select_run_folder() -> str:
    root = tk.Tk()
    root.withdraw()
    selected = filedialog.askdirectory(
        title="Select the Data Run Folder",
        initialdir=str(Path(r"D:\Quantum Squeezing Project\DataFiles")),
    )
    root.destroy()
    if not selected:
        raise SystemExit("No folder selected. Cancelled.")
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description="Export review assets for the first raw correlation-matrix frames.")
    parser.add_argument("run_folder", nargs="?", help="Path to the run folder that contains cm.bin.")
    parser.add_argument("--count", type=int, default=DEFAULT_REVIEW_COUNT, help="Number of raw frames to export.")
    parser.add_argument("--start-idx", type=int, default=0, help="Zero-based frame index to start from.")
    parser.add_argument("--bin-mm", type=float, default=0.1, help="Position bin size in mm for the diagnostic output.")
    args = parser.parse_args()

    run_folder = args.run_folder or select_run_folder()
    style_matplotlib()
    review_dir = export_raw_frame_review(Path(run_folder), args.count, args.start_idx, args.bin_mm)
    print(f"Saved raw frame diagnostics to: {review_dir}")


if __name__ == "__main__":
    main()
