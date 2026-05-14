from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from cm_pipeline_all_in_one import (
    BIN_MM,
    FRAME_DT_S,
    MM_TO_PS,
    amplitude_axis_label,
    build_bin_cumsums_and_counts,
    idx_lin,
    style_matplotlib,
)
from export_time_window_movies import build_clip_windows, prepare_run_data


def window_mask(t_seconds: np.ndarray, start_s: float, end_s: float | None) -> tuple[np.ndarray, str]:
    if end_s is None:
        return t_seconds > start_s, f"{int(start_s) + 1}s to last"
    if start_s == 0.0:
        return (t_seconds >= start_s) & (t_seconds <= end_s), f"{int(start_s)}s to {int(end_s)}s"
    return (t_seconds > start_s) & (t_seconds <= end_s), f"{int(start_s) + 1}s to {int(end_s)}s"


def final_window_amplitudes(
    context: dict[str, object],
    start_s: float,
    end_s: float | None,
) -> tuple[str, np.ndarray, np.ndarray, int, int, int]:
    raw_cm = context["raw_cm"]
    t_seconds = context["t_seconds"]
    pos_on_cm = context["pos_on_cm"]
    pairs = context["pairs"]
    keep_indices = context["keep_indices"]

    if not isinstance(raw_cm, np.ndarray) or not isinstance(t_seconds, np.ndarray) or not isinstance(pos_on_cm, np.ndarray):
        raise TypeError("Invalid run context.")
    if not isinstance(pairs, np.ndarray) or not isinstance(keep_indices, list):
        raise TypeError("Invalid pair context.")

    mask, label = window_mask(t_seconds, start_s, end_s)
    frame_count = int(np.count_nonzero(mask))
    if frame_count == 0:
        return label, np.array([]), np.empty((0, len(keep_indices))), 0, 0, 0

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

    if counts.size == 0:
        return label, np.array([]), np.empty((0, len(keep_indices))), frame_count, 0, 0

    integration_frames = int(np.min(counts))
    amps = np.full((len(bin_vals), len(keep_indices)), np.nan, dtype=float)
    for b_idx, bin_curve in enumerate(bin_cumsums):
        if bin_curve.shape[0] >= integration_frames:
            amps[b_idx, :] = bin_curve[integration_frames - 1, keep_indices] / integration_frames

    ts = bin_vals * MM_TO_PS
    order = np.argsort(ts)
    return label, ts[order], amps[order], frame_count, int(counts.size), integration_frames


def save_last_frame_stack(
    run_folder: Path,
    clip_seconds: float,
    output_path: Path,
    hide_from_s: float | None = None,
) -> None:
    style_matplotlib()
    context = prepare_run_data(run_folder)
    last_time_s = float(np.nanmax(context["t_seconds"]))
    windows = build_clip_windows(clip_seconds, last_time_s)
    if hide_from_s is not None:
        windows = [window for window in windows if window[1] < hide_from_s]
    if not windows:
        raise ValueError("No windows remain after applying the hide-from cutoff.")

    labels = context["labels"]
    keep_indices = context["keep_indices"]
    if not isinstance(labels, list) or not isinstance(keep_indices, list):
        raise TypeError("Invalid label context.")

    colors = plt.cm.turbo(np.linspace(0, 1, max(1, len(keep_indices))))
    fig_height = max(9.0, 2.1 * len(windows))
    fig, axes = plt.subplots(len(windows), 1, figsize=(13, fig_height), sharex=True)
    if not isinstance(axes, np.ndarray):
        axes = np.array([axes])

    for ax, (_, start_s, end_s) in zip(axes, windows, strict=False):
        window_label, ts, amps, frame_count, bin_count, integration_frames = final_window_amplitudes(
            context,
            start_s,
            end_s,
        )
        if ts.size == 0:
            ax.text(0.5, 0.5, "No frames in this window", transform=ax.transAxes, ha="center", va="center")
        else:
            for line_idx, pair_idx in enumerate(keep_indices):
                ax.plot(
                    ts,
                    amps[:, line_idx],
                    "o-",
                    color=colors[line_idx],
                    linewidth=1.2,
                    markersize=3,
                    label=labels[pair_idx],
                )

        ax.set_title(
            f"{window_label} | final frame: {integration_frames} frames/bin "
            f"({integration_frames * FRAME_DT_S:.1f}s/bin), {frame_count} frames, {bin_count} bins",
            fontsize=10,
        )
        ax.set_ylabel(amplitude_axis_label(bool(context["display_in_v2"])), fontsize=9)
        ax.grid(True, alpha=0.25)

    xlim = context["xlim"]
    if isinstance(xlim, tuple):
        axes[-1].set_xlim(*xlim)
    axes[-1].set_xlabel("Delay (ps)")

    handles, legend_labels = axes[0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, legend_labels, loc="center right", bbox_to_anchor=(0.985, 0.5), frameon=False)
    fig.suptitle(f"Final Integrated Frame for Each {clip_seconds:g}s Clip", fontsize=16)
    fig.tight_layout(rect=(0.0, 0.0, 0.84, 0.98))
    fig.savefig(output_path, dpi=220)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot the last integrated frame from each time-window movie.")
    parser.add_argument("run_folder", type=Path)
    parser.add_argument("--clip-seconds", type=float, default=5000.0)
    parser.add_argument("--hide-from-seconds", type=float, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    run_folder = args.run_folder.expanduser().resolve()
    output_path = args.output or (run_folder / f"signal_emergence_{int(args.clip_seconds)}s_last_frame_stack.png")
    save_last_frame_stack(run_folder, args.clip_seconds, output_path, args.hide_from_seconds)
    print(f"Wrote stacked last-frame plot: {output_path}", flush=True)


if __name__ == "__main__":
    main()
