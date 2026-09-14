"""Visualize the two Allan-deviation landmarks stored in a batch summary CSV."""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D


BEHAVIOR_COLORS = {
    "improving with averaging": "#2E7D32",
    "stability floor / flicker-like": "#E69F00",
    "random-walk-like long-term drift": "#D55E00",
    "strong drift / trend": "#8E24AA",
    "insufficient data": "#8A8A8A",
}


def number(value: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return np.nan
    return result if np.isfinite(result) and result > 0 else np.nan


def load_rows(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        raw_rows = list(csv.DictReader(handle))
    rows: list[dict[str, object]] = []
    for raw in raw_rows:
        rows.append(
            {
                **raw,
                "tau_min": number(raw.get("median_tau_at_minimum_s", "")),
                "adev_min": number(raw.get("median_minimum_allan_deviation", "")),
                "tau_long": number(raw.get("longest_reliable_tau_s", "")),
                "adev_long": number(raw.get("median_allan_deviation_at_longest_tau", "")),
            }
        )
    return rows


def draw_panel(ax: plt.Axes, rows: list[dict[str, object]], unit: str) -> None:
    panel_rows = [r for r in rows if r["unit"] == unit and np.isfinite(r["tau_min"]) and np.isfinite(r["adev_min"])]
    all_tau = []
    all_adev = []
    for row in panel_rows:
        color = BEHAVIOR_COLORS.get(str(row["long_term_behavior"]), "#607D8B")
        tau0, y0 = float(row["tau_min"]), float(row["adev_min"])
        tau1, y1 = float(row["tau_long"]), float(row["adev_long"])
        all_tau.append(tau0)
        all_adev.append(y0)
        if np.isfinite(tau1) and np.isfinite(y1):
            all_tau.append(tau1)
            all_adev.append(y1)
        alpha = 0.22 if row["status"] == "ok" else 0.10
        if np.isfinite(tau1) and np.isfinite(y1):
            ax.plot([tau0, tau1], [y0, y1], color=color, alpha=alpha, linewidth=0.75, zorder=1)
            ax.scatter(tau1, y1, marker="^", s=13, color=color, alpha=max(alpha, 0.25),
                       edgecolors="none", zorder=2)
        ax.scatter(tau0, y0, marker="o", s=14, facecolor=color, edgecolor="white",
                   linewidth=0.25, alpha=max(alpha, 0.30), zorder=3)

    ax.set_xscale("log")
    ax.set_yscale("log")
    # A handful of malformed/extreme legacy results span many orders of
    # magnitude. Use a declared percentile zoom so the main population remains
    # readable; the CSV is never filtered or modified.
    x_lo, x_hi = np.quantile(all_tau, [0.02, 0.98])
    y_lo, y_hi = np.quantile(all_adev, [0.02, 0.98])
    ax.set_xlim(x_lo / 1.35, x_hi * 1.35)
    ax.set_ylim(y_lo / 2.0, y_hi * 2.0)
    ax.grid(True, which="major", color="#CAD2D9", alpha=0.65, linewidth=0.7)
    ax.grid(True, which="minor", color="#E6EAED", alpha=0.45, linewidth=0.4)
    ax.set_xlabel(r"Averaging time $\tau$ (s)")
    unit_label = r"V$^2$" if unit == "V^2" else r"$\mu$rad$^2$"
    ax.set_ylabel(f"Allan deviation ({unit_label})")
    ax.set_title(f"{unit_label} runs  ·  {len(panel_rows):,} with valid minima", loc="left", fontweight="bold")
    outside = sum(not (x_lo <= x <= x_hi and y_lo <= y <= y_hi) for x, y in zip(all_tau, all_adev))
    ax.text(0.99, 0.02, f"Central 96% zoom · {outside:,} landmarks outside view",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=8, color="#5F6B73")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--output", type=Path, default=Path("allan_deviation_batch_visualization"))
    args = parser.parse_args()
    rows = load_rows(args.csv)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 2, figsize=(15, 6.8), constrained_layout=False)
    draw_panel(axes[0], rows, "V^2")
    draw_panel(axes[1], rows, "urad^2")

    behavior_present = Counter(str(r["long_term_behavior"]) for r in rows if r["long_term_behavior"])
    behavior_handles = [
        Line2D([0], [0], color=color, linewidth=3,
               label=f"{label} ({behavior_present[label]:,})")
        for label, color in BEHAVIOR_COLORS.items() if behavior_present[label]
    ]
    landmark_handles = [
        Line2D([0], [0], marker="o", linestyle="none", markerfacecolor="#455A64",
               markeredgecolor="white", label="Minimum Allan deviation"),
        Line2D([0], [0], marker="^", linestyle="none", markerfacecolor="#455A64",
               markeredgecolor="none", label="Longest reliable τ"),
    ]
    fig.legend(handles=behavior_handles + landmark_handles, loc="lower center", ncol=4,
               frameon=False, bbox_to_anchor=(0.5, 0.01), fontsize=9)
    status = Counter(str(r["status"]) for r in rows)
    fig.suptitle("Allan-deviation stability trajectories across runs", fontsize=17, fontweight="bold", y=0.98)
    fig.text(0.5, 0.925,
             "Each line joins a run’s minimum to its longest reliable averaging time; upward lines expose long-time drift or a stability floor.",
             ha="center", fontsize=10, color="#455A64")
    fig.text(0.01, 0.012,
             f"Source: {args.csv}  |  {len(rows):,} rows: {status.get('ok', 0):,} ok, "
             f"{status.get('skipped', 0):,} skipped, {status.get('failed', 0):,} failed. Failed rows have no plottable values.",
             ha="left", fontsize=7.5, color="#5F6B73")
    fig.subplots_adjust(left=0.075, right=0.985, top=0.865, bottom=0.22, wspace=0.19)
    fig.savefig(args.output.with_suffix(".png"), dpi=220, facecolor="white")
    fig.savefig(args.output.with_suffix(".pdf"), facecolor="white")
    plt.close(fig)
    print(args.output.with_suffix(".png").resolve())
    print(args.output.with_suffix(".pdf").resolve())


if __name__ == "__main__":
    main()
