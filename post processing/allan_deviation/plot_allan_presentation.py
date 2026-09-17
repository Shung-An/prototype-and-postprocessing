"""Presentation figure combining raw-frame millisecond and saved long-term ADEV."""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import LogLocator, NullFormatter, FuncFormatter

# Support direct CLI execution while importing the shared processing pipeline.
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from allan_deviation import allan_deviation_analysis as analysis
import cm_pipeline_all_in_one as pipeline
from allan_deviation.plot_allan_slope_example import load_curves, load_summaries, parse_slope


def millisecond_curves(run: Path, labels: list[str], output: Path):
    """Overlapping adjacent averages, full record, nominal acquisition cadence.

    Profile timestamps are host transfer times, so they are not used to assign
    millisecond acquisition times. No detrending; nonfinite windows excluded.
    """
    payload = json.loads((run / "metadata.json").read_text(encoding="utf-8-sig"))
    scale, in_v2, conversion, unit = analysis.scale_configuration(run, payload)
    if not in_v2:
        if not np.isfinite(conversion) or conversion <= 0:
            raise ValueError("A positive calibration factor is required.")
        scale *= 1e12 / conversion
    raw = np.memmap(run / "cm.bin", dtype=np.float64, mode="r").reshape(-1, 64)
    dt = pipeline.FRAME_DT_S
    factors = np.unique(np.r_[1, np.geomspace(1, int(1 / dt), 32).astype(int)])
    curves = {}
    rows = []
    for label in labels:
        r1, c1, r2, c2 = map(int, re.findall(r"\d+", label))
        values = (raw[:, pipeline.idx_lin(r1, c1)] - raw[:, pipeline.idx_lin(r2, c2)]) * scale
        finite = np.isfinite(values)
        if not finite.any():
            raise ValueError(f"No finite raw samples for {label}")
        centered = np.where(finite, values - np.mean(values[finite]), 0)
        sums = np.r_[0.0, np.cumsum(centered)]
        bad = np.r_[0, np.cumsum(~finite)]
        deviations = []
        for m in factors:
            delta = (sums[2*m:] - 2*sums[m:-m] + sums[:-2*m]) / m
            valid = bad[2*m:] == bad[:-2*m]
            count = int(valid.sum())
            variance = float(np.dot(delta[valid], delta[valid]) / (2 * count)) if count else np.nan
            deviation = float(np.sqrt(variance))
            deviations.append(deviation)
            rows.append([label, int(m), m * dt, deviation, variance, count, unit])
        curves[label] = (factors * dt, np.asarray(deviations))
        print(f"Computed {label}: {deviations[0]:.6g} {unit} at {dt*1000:.5f} ms", flush=True)
    with output.with_suffix(".csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["pair", "averaging_frames", "tau_s", "allan_deviation", "allan_variance", "overlapping_terms", "deviation_unit"])
        writer.writerows(rows)
    return curves, unit, len(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    long = load_curves(args.run / "allan_deviation_long_term.csv")
    summaries = load_summaries(args.run / "allan_deviation_summary.csv")
    labels = list(long)
    short, unit, frames = millisecond_curves(args.run, labels, args.output)
    slopes = [parse_slope(summaries[label]) for label in labels]
    last_tau = next(iter(long.values()))[0][-1]
    dt = pipeline.FRAME_DT_S
    short_median = float(np.median([short[label][1][0] for label in labels]))
    long_median = float(np.median([long[label][1][-1] for label in labels]))
    unit_math = r"$\mu\mathrm{rad}^{2}$" if unit == "urad^2" else r"$\mathrm{V}^{2}$"
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12,
                         "axes.labelsize": 14, "axes.titlesize": 16,
                         "axes.edgecolor": "#9ba7b5", "text.color": "#17263a",
                         "axes.labelcolor": "#17263a", "pdf.fonttype": 42,
                         "svg.fonttype": "none"})
    fig = plt.figure(figsize=(18, 10.125), facecolor="white")
    grid = fig.add_gridspec(1, 3, left=.065, right=.985, bottom=.23, top=.75,
                           width_ratios=[1, 1.23, 1.0], wspace=.25)
    ax_ms, ax_long, ax_table = [fig.add_subplot(grid[0, i]) for i in range(3)]
    colors = [plt.get_cmap("tab10")(i) for i in range(len(labels))]
    for i, label in enumerate(labels):
        tau, deviation = short[label]
        ax_ms.loglog(tau * 1000, deviation, color=colors[i], lw=2.1)
        tau, deviation = long[label]
        ax_long.loglog(tau, deviation, color=colors[i], lw=1.9)
        slope, intercept = np.polyfit(np.log10(tau[-8:]), np.log10(deviation[-8:]), 1)
        if not np.isclose(slope, slopes[i], atol=1e-8):
            raise ValueError(f"Stored tail slope does not match final eight points: {label}")
        ax_long.loglog(tau[-8:], 10 ** (intercept + slope * np.log10(tau[-8:])),
                      color=colors[i], ls="--", lw=2.5)
    fit_start = max(tau[-8] for tau, _ in long.values())
    ax_long.axvspan(fit_start, last_tau, color="#203c58", alpha=.07, zorder=0)
    ax_long.text(.97, .97, "Tail fit", transform=ax_long.transAxes,
                 ha="right", va="top", fontsize=11, color="#53677d")
    ax_ms.set_title("Millisecond averaging", loc="left", pad=17, weight="bold")
    ax_long.set_title("Long-term averaging", loc="left", pad=17, weight="bold")
    ax_ms.set_xlabel(r"Averaging time $\tau$ (ms)", labelpad=10)
    ax_long.set_xlabel(r"Averaging time $\tau$ (s)", labelpad=10)
    ax_ms.set_ylabel(f"Allan deviation ({unit_math})", labelpad=10)
    ax_ms.set_xlim(12, 1100)
    ax_long.set_xlim(.85, last_tau*1.12)
    for ax in (ax_ms, ax_long):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(which="major", color="#dbe2e9", lw=.8)
        ax.grid(which="minor", color="#eef1f5", lw=.45)
        ax.tick_params(which="both", direction="out", labelsize=12)
        ax.yaxis.set_major_locator(LogLocator(base=10, subs=(1, 2, 5)))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}"))
        ax.yaxis.set_minor_formatter(NullFormatter())
    ax_ms.set_xticks([20, 50, 100, 200, 500, 1000], ["20", "50", "100", "200", "500", "1000"])
    ax_long.set_xticks([1, 10, 100, 1000], ["1", "10", "100", "1000"])
    ax_ms.xaxis.set_minor_formatter(NullFormatter())
    ax_long.xaxis.set_minor_formatter(NullFormatter())
    ax_table.axis("off")
    ax_table.set_title("Results by channel pair", loc="left", pad=17, weight="bold")
    cells = [[label, f"{short[label][1][0]:.3f}", f"{long[label][1][-1]:.4f}", f"{slopes[i]:+.3f}"]
             for i, label in enumerate(labels)]
    table = ax_table.table(cellText=cells,
                           colLabels=["Pair", f"{dt*1000:.2f} ms", f"{last_tau:.0f} s", "Slope"],
                           colWidths=[.40, .20, .20, .20], cellLoc="center",
                           bbox=[-.015, .07, 1.055, .93])
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("white")
        cell.set_linewidth(2)
        cell.set_facecolor("#e8edf3" if row == 0 else ("#f3f6f9" if row % 2 else "#fafbfd"))
        if row == 0:
            cell.get_text().set_weight("bold")
        elif col == 0:
            cell.get_text().set_color(colors[row - 1])
            cell.get_text().set_weight("bold")
    ax_table.text(0, .015, f"Deviation columns in {unit_math}", fontsize=11, color="#53677d",
                  transform=ax_table.transAxes)
    fig.text(.065, .943, "Allan deviation across averaging times", fontsize=27, weight="bold")
    fig.text(.065, .902, f"Run {args.run.name}  |  Nine selected covariance-channel differences", fontsize=15, color="#53677d")
    fig.text(.065, .837, f"At {dt*1000:.2f} ms:  {short_median:.3f} {unit_math}", fontsize=17, weight="bold")
    fig.text(.40, .837, f"At {last_tau:.0f} s:  {long_median:.4f} {unit_math}", fontsize=17, weight="bold")
    fig.text(.735, .837, f"Tail slope:  {np.median(slopes):+.3f}", fontsize=17, weight="bold")
    fig.text(.065, .795, "Summary values are medians across the nine pairs.", fontsize=11, color="#53677d")
    notes = [
        "Solid: overlapping Allan deviation. Dashed: log–log fit to the final eight long-term points; shaded area marks the fit interval.",
        f"Millisecond panel: original frames, nominal cadence {dt*1000:.5f} ms. Long-term panel: saved ~1 s bin averages with profile-based timing.",
        "No detrending. This is a delay-scan record; fitted slopes describe curve shape and do not identify a stationary noise process.",
    ]
    for y, note in zip([.135, .104, .073], notes):
        fig.text(.065, y, note, fontsize=11, color="#53677d")
    for extension in ("png", "pdf", "svg"):
        path = args.output.with_suffix("." + extension)
        fig.savefig(path, dpi=300, facecolor="white")
        print(path.resolve(), flush=True)
    plt.close(fig)
    report = {"run": str(args.run.resolve()), "frames": frames, "deviation_unit": unit,
              "nominal_frame_interval_s": dt, "millisecond_timing": "nominal acquisition cadence; host transfer timestamps not used",
              "millisecond_minimum_tau_s": dt, "median_deviation_at_minimum_tau": short_median,
              "long_term_tau_s": float(last_tau), "median_long_term_deviation": long_median,
              "median_tail_slope": float(np.median(slopes)), "method_notes": notes,
              "pairs": [{"pair": label, "deviation_at_minimum_tau": float(short[label][1][0]),
                         "deviation_at_longest_tau": float(long[label][1][-1]), "tail_slope": slopes[i]}
                        for i, label in enumerate(labels)]}
    args.output.with_suffix(".json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
