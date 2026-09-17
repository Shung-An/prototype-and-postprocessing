"""Merge saved millisecond and long-term ADEV, averaging equally across pairs."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter

# Support direct CLI execution while importing the shared processing pipeline.
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from allan_deviation.plot_allan_slope_example import load_curves


def average_curves(curves, labels):
    tau = curves[labels[0]][0]
    for label in labels:
        if not np.array_equal(curves[label][0], tau):
            raise ValueError(f"Averaging times differ for {label}")
    return tau, np.mean([curves[label][1] for label in labels], axis=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--millisecond-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--condition", action="append", default=[],
                        help="Metadata-grounded experiment condition line (repeat up to three times).")
    args = parser.parse_args()
    if len(args.condition) > 3:
        parser.error("Use at most three condition lines.")
    short = load_curves(args.millisecond_csv)
    long = load_curves(args.run / "allan_deviation_long_term.csv")
    if set(short) != set(long):
        raise ValueError("Both time ranges must contain exactly the same pairs.")
    labels = list(long)
    st, sy = average_curves(short, labels)
    lt, ly = average_curves(long, labels)
    with args.millisecond_csv.open(encoding="utf-8-sig", newline="") as handle:
        short_units = {row["deviation_unit"] for row in csv.DictReader(handle)}
    with (args.run / "allan_deviation_long_term.csv").open(encoding="utf-8-sig", newline="") as handle:
        long_units = {row["deviation_unit"] for row in csv.DictReader(handle)}
    if short_units != long_units or len(short_units) != 1:
        raise ValueError("Both time ranges must use the same deviation unit.")
    unit = short_units.pop()
    unit_math = "µrad²" if unit == "urad^2" else "V²"
    # Prefer the saved long-term result if the two ranges overlap.
    keep = st < lt[0]
    tau, mean = np.r_[st[keep], lt], np.r_[sy[keep], ly]
    if not np.all(np.diff(tau) > 0):
        raise ValueError("Combined averaging times must increase strictly.")
    tail_slope = float(np.polyfit(np.log10(lt[-8:]), np.log10(ly[-8:]), 1)[0])
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 13,
                         "font.weight": "bold", "axes.labelweight": "bold",
                         "axes.titleweight": "bold", "mathtext.default": "bf",
                         "axes.labelsize": 16, "axes.edgecolor": "#a5b0bd",
                         "text.color": "#17263a", "axes.labelcolor": "#17263a",
                         "pdf.fonttype": 42, "svg.fonttype": "none"})
    fig, ax = plt.subplots(figsize=(12, 13), facecolor="white")
    # Equal physical axis lengths, without changing either logarithmic scale.
    ax.set_box_aspect(1)
    fig.subplots_adjust(left=.12, right=.965, bottom=.23, top=.74)
    ax.loglog(tau, mean, color="#126b9a", lw=3)
    ax.set_xlim(tau[0] / 1.15, tau[-1] * 1.15)
    ax.set_xlabel(r"Averaging time $\tau$", labelpad=12)
    ax.set_ylabel(f"Mean Allan deviation ({unit_math})", labelpad=12)
    ticks = [(t, label) for t, label in zip(
        [.02, .1, 1, 10, 100, 1000],
        ["20 ms", "100 ms", "1 s", "10 s", "100 s", "1000 s"])
        if tau[0]/1.15 <= t <= tau[-1]*1.15]
    ax.set_xticks([t for t, _ in ticks], [label for _, label in ticks])
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.yaxis.set_major_locator(LogLocator(base=10, subs=(1, 2, 5)))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}"))
    ax.yaxis.set_minor_formatter(NullFormatter())
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(which="major", color="#dbe2e9", lw=.85)
    ax.grid(which="minor", color="#eff2f6", lw=.5)
    ax.tick_params(which="both", direction="out", labelsize=13)
    fig.text(.095, .93, "Mean Allan deviation", fontsize=25, weight="bold")
    fig.text(.095, .885,
             f"Run {args.run.name}  |  Arithmetic mean across {len(labels)} channel pairs",
             fontsize=12, color="#53677d")
    fig.text(.095, .803, f"{tau[0]*1000:.2f} ms:  {mean[0]:.3f} {unit_math}", fontsize=14, weight="bold")
    fig.text(.425, .803, f"{tau[-1]:.0f} s:  {mean[-1]:.4f} {unit_math}", fontsize=14, weight="bold")
    fig.text(.755, .803, f"Tail slope:  {tail_slope:+.3f}", fontsize=14, weight="bold")
    notes = [
        "Equal-weight mean of the nine individual Allan deviations at each averaging time; no smoothing or detrending.",
        "Ranges joined near 1 s: nominal frame timing below the join; saved profile-timed, binned results above it.",
        "Tail slope fits the final eight mean-curve points. This delay-scan record does not identify a stationary noise process.",
    ]
    footer = args.condition + notes
    if args.condition:
        fig.text(.095, .173, "Measurement conditions (recorded metadata)",
                 fontsize=11, weight="bold", color="#17263a")
    footer_y = np.linspace(.15, .03, len(footer)) if args.condition else [.127, .093, .059]
    for y, note in zip(footer_y, footer):
        fig.text(.095, y, note, fontsize=9, color="#53677d")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.canvas.draw()
    bounds = ax.get_window_extent()
    if not np.isclose(bounds.width, bounds.height, atol=.01):
        raise ValueError("The exported plotting area must be square.")
    for extension in ("png", "pdf", "svg"):
        path = args.output.with_suffix("." + extension)
        fig.savefig(path, dpi=300, facecolor="white")
        print(path.resolve())
    plt.close(fig)
    csv_path = args.output.with_name(args.output.name + "_mean").with_suffix(".csv")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["tau_s", "mean_allan_deviation", "pair_count", "deviation_unit", "source"])
        for i, (t, value) in enumerate(zip(tau, mean)):
            writer.writerow([t, value, len(labels), unit, "raw_frame_nominal_timing" if i < keep.sum() else "long_term_binned_profile_timing"])
    report = {"run": str(args.run.resolve()), "pair_labels": labels,
              "aggregation": "equal-weight arithmetic mean of individual Allan deviations",
              "deviation_unit": unit, "first_tau_s": float(tau[0]), "first_mean_deviation": float(mean[0]),
              "last_tau_s": float(tau[-1]), "last_mean_deviation": float(mean[-1]),
              "mean_curve_tail_slope": tail_slope, "fit_points": 8,
              "last_short_tau_s": float(st[keep][-1]), "first_long_tau_s": float(lt[0]),
              "short_source": str(args.millisecond_csv.resolve()),
              "long_source": str((args.run / "allan_deviation_long_term.csv").resolve()),
              "method_notes": notes, "experiment_conditions": args.condition,
              "conditions_source": str((args.run / "metadata.json").resolve()) if args.condition else None}
    args.output.with_suffix(".json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
