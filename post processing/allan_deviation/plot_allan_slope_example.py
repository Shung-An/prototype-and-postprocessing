"""Plot Allan-deviation curves and the fitted long-term slopes for one run."""
from __future__ import annotations

import argparse
import csv
import os
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def load_curves(path: Path) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    grouped: dict[str, list[tuple[float, float]]] = defaultdict(list)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                tau = float(row["tau_s"])
                adev = float(row["allan_deviation"])
            except (TypeError, ValueError):
                continue
            if np.isfinite(tau) and tau > 0 and np.isfinite(adev) and adev > 0:
                grouped[row["pair"]].append((tau, adev))
    return {
        label: (np.asarray([p[0] for p in points]), np.asarray([p[1] for p in points]))
        for label, points in grouped.items()
    }


def load_summaries(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {row["Pair"]: row for row in csv.DictReader(handle)}


def noise_shape(slope: float) -> str:
    """Return a cautious curve-shape label for a covariance-difference ADEV."""
    if not np.isfinite(slope):
        return "insufficient points"
    if slope < -0.75:
        return "phase-noise-like"
    if slope < -0.25:
        return "white-noise-like"
    if slope <= 0.25:
        return "floor / flicker-like"
    if slope < 0.75:
        return "random-walk-like"
    return "drift / trend-like"


def parse_slope(summary: dict[str, str]) -> float:
    """Read a stored slope, returning NaN for older short measurements."""
    try:
        slope = float(summary.get("LongTermLogSlope", ""))
    except (TypeError, ValueError):
        return float("nan")
    return slope if np.isfinite(slope) else float("nan")


def deviation_unit_label(summaries: dict[str, dict[str, str]]) -> str:
    unit = next(
        (row.get("DeviationUnit", "") for row in summaries.values() if row.get("DeviationUnit")),
        "",
    )
    if unit == "urad^2":
        return r"$mu$rad$^2$"
    if unit == "V^2":
        return r"V$^2$"
    return unit or "measurement units"


def spread_log_labels(values: list[float], y_limits: tuple[float, float]) -> list[float]:
    """Separate nearby label positions while preserving their vertical order."""
    log_values = np.log10(values)
    log_low, log_high = np.log10(y_limits)
    span = log_high - log_low
    low = log_low + 0.035 * span
    high = log_high - 0.035 * span
    gap = min(0.052 * span, (high - low) / max(1, len(values) - 1))

    order = np.argsort(log_values)
    placed = np.clip(log_values[order], low, high)
    for index in range(1, len(placed)):
        placed[index] = max(placed[index], placed[index - 1] + gap)
    if placed[-1] > high:
        placed -= placed[-1] - high
    for index in range(len(placed) - 2, -1, -1):
        placed[index] = min(placed[index], placed[index + 1] - gap)
    if placed[0] < low:
        placed += low - placed[0]

    result = np.empty_like(placed)
    result[order] = placed
    return list(10**result)


def plot_run(
    run_folder: Path,
    output: Path,
    fit_points: int = 8,
    save_pdf: bool = True,
) -> tuple[Path, Path | None]:
    """Create the slope-annotated Allan plot for one measurement folder."""
    output.parent.mkdir(parents=True, exist_ok=True)

    curves = load_curves(run_folder / "allan_deviation_long_term.csv")
    summaries = load_summaries(run_folder / "allan_deviation_summary.csv")
    if not curves:
        raise ValueError("No finite Allan-deviation curves were found.")

    slopes = {label: parse_slope(summaries.get(label, {})) for label in curves}
    finite_slopes = {label: slope for label, slope in slopes.items() if np.isfinite(slope)}
    median_slope = (
        float(np.median(list(finite_slopes.values()))) if finite_slopes else float("nan")
    )
    representative = (
        min(finite_slopes, key=lambda label: abs(finite_slopes[label] - median_slope))
        if finite_slopes
        else None
    )
    white_like = (
        min(finite_slopes, key=lambda label: abs(finite_slopes[label] + 0.5))
        if finite_slopes
        else None
    )

    fig, ax = plt.subplots(figsize=(13.5, 7.5))
    colors = plt.get_cmap("tab10").colors
    curve_labels: list[dict[str, object]] = []
    for index, (label, (tau, adev)) in enumerate(curves.items()):
        slope = slopes[label]
        color = colors[index % len(colors)]
        emphasized = label in {representative, white_like}
        ax.loglog(
            tau,
            adev,
            color=color,
            linewidth=2.2 if emphasized else 1.15,
            alpha=1.0 if emphasized else 0.58,
        )

        count = min(fit_points, len(tau))
        fit_tau = tau[-count:]
        if count >= 4:
            fit_slope, fit_intercept = np.polyfit(
                np.log10(fit_tau), np.log10(adev[-count:]), 1
            )
            fit_adev = 10 ** (fit_intercept + fit_slope * np.log10(fit_tau))
            ax.loglog(fit_tau, fit_adev, color=color, linestyle="--",
                      linewidth=2.5 if emphasized else 1.2, alpha=0.95)
        curve_labels.append(
            {
                "pair": label,
                "slope": slope,
                "color": color,
                "tau": float(tau[-1]),
                "adev": float(adev[-1]),
            }
        )

    has_tail_fit = any(len(tau) >= 4 for tau, _ in curves.values())
    if has_tail_fit:
        # A slope reference is a shape guide, not a fit to the measurement.
        guide_start = max(3.0, min(values[0][0] for values in curves.values()))
        guide_end = min(30.0, max(values[0][-1] for values in curves.values()))
        guide_tau = np.geomspace(guide_start, guide_end, 40)
        interpolated = [
            10 ** np.interp(np.log10(guide_start), np.log10(tau), np.log10(adev))
            for tau, adev in curves.values()
        ]
        guide_start_adev = max(interpolated) * 1.35
        guide_adev = guide_start_adev * (guide_tau / guide_start) ** -0.5
        ax.loglog(
            guide_tau,
            guide_adev,
            color="#111111",
            linestyle="-.",
            linewidth=2.0,
            zorder=5,
        )
        ax.text(
            guide_tau[-1] * 1.06,
            guide_adev[-1],
            r"$s=-0.5$ white-noise guide",
            color="#111111",
            fontsize=9,
            va="center",
            ha="left",
        )

        fit_curves = [(tau, adev) for tau, adev in curves.values() if len(tau) >= 4]
        first_tau = max(tau[-min(fit_points, len(tau))] for tau, _ in fit_curves)
        last_tau = min(tau[-1] for tau, _ in fit_curves)
        ax.axvspan(first_tau, last_tau, color="#607D8B", alpha=0.08, zorder=0)
        ax.text(
            np.sqrt(first_tau * last_tau),
            0.985,
            "tail-slope fit interval",
            transform=ax.get_xaxis_transform(),
            ha="center",
            va="top",
            fontsize=9,
            color="#455A64",
        )

    median_text = f"{median_slope:+.3f}" if np.isfinite(median_slope) else "N/A"
    ax.set_title(
        f"Long-term Allan deviation with fitted tail slopes\n"
        f"Run {run_folder.name} | median slope {median_text}",
        fontsize=15,
        fontweight="bold",
    )
    ax.set_xlabel(r"Averaging time $\tau$ (s)")
    ax.set_ylabel(f"Allan deviation ({deviation_unit_label(summaries)})")
    ax.grid(True, which="major", color="#BCC7CE", alpha=0.7)
    ax.grid(True, which="minor", color="#E1E6E9", alpha=0.5, linewidth=0.55)
    # Write each result beside its own curve. Crowded endpoints are separated
    # in log-y space, with a short leader connecting each label to its curve.
    ax.relim()
    ax.autoscale_view()
    max_tau = max(float(tau[-1]) for tau, _ in curves.values())
    label_x = max_tau * 1.24
    ax.set_xlim(right=max_tau * 6.0)
    label_y = spread_log_labels(
        [float(item["adev"]) for item in curve_labels], ax.get_ylim()
    )
    for item, placed_y in zip(curve_labels, label_y):
        end_x = float(item["tau"])
        end_y = float(item["adev"])
        color = item["color"]
        ax.plot(
            [end_x, label_x * 0.97],
            [end_y, placed_y],
            color=color,
            linewidth=0.8,
            alpha=0.72,
            zorder=2,
        )
        slope = float(item["slope"])
        slope_text = f"{slope:+.3f}" if np.isfinite(slope) else "N/A"
        ax.text(
            label_x,
            placed_y,
            f'{item["pair"]}   s={slope_text}   {noise_shape(slope)}',
            color=color,
            fontsize=8.5,
            fontweight="semibold",
            va="center",
            ha="left",
            zorder=6,
        )

    fig.text(
        0.01,
        0.012,
        "Solid: overlapping Allan deviation. Dashed: log-log least-squares fit to the final eight valid points. "
        "Slope describes curve shape; this delay-scan measurement is not a stationary noise record.",
        fontsize=8,
        color="#52616B",
    )
    fig.subplots_adjust(left=0.08, right=0.985, top=0.88, bottom=0.12)
    png_path = output.with_suffix(".png")
    pdf_path = output.with_suffix(".pdf") if save_pdf else None
    fig.savefig(png_path, dpi=220, facecolor="white")
    if pdf_path is not None:
        fig.savefig(pdf_path, facecolor="white")
    plt.close(fig)
    return png_path.resolve(), pdf_path.resolve() if pdf_path is not None else None


def plot_run_worker(task: tuple[Path, int]) -> tuple[Path, str | None]:
    """Process-pool entry point for one existing Allan result folder."""
    run_folder, fit_points = task
    try:
        plot_run(
            run_folder,
            run_folder / "allan_deviation_long_term",
            fit_points=fit_points,
            save_pdf=False,
        )
        return run_folder, None
    except Exception as exc:  # Keep a large batch running if one folder is malformed.
        return run_folder, f"{type(exc).__name__}: {exc}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_folder", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fit-points", type=int, default=8)
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Replace Allan PNGs in all analyzed measurement folders below run_folder.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=max(1, min(4, os.cpu_count() or 1)),
        help="Parallel plotting processes used with --recursive (default: up to 4).",
    )
    parser.add_argument(
        "--png-only",
        action="store_true",
        help="Skip the PDF for a single run; recursive mode is always PNG-only.",
    )
    args = parser.parse_args()

    if not args.recursive:
        output = args.output or Path(f"allan_slope_example_{args.run_folder.name}")
        png_path, pdf_path = plot_run(
            args.run_folder,
            output,
            fit_points=args.fit_points,
            save_pdf=not args.png_only,
        )
        print(png_path)
        if pdf_path is not None:
            print(pdf_path)
        return

    if args.output is not None:
        parser.error("--output cannot be used with --recursive")
    if args.workers < 1:
        parser.error("--workers must be at least 1")

    run_folders = sorted(
        path.parent
        for path in args.run_folder.rglob("allan_deviation_long_term.csv")
        if (path.parent / "allan_deviation_summary.csv").is_file()
    )
    print(f"Found {len(run_folders)} analyzed measurement folders.", flush=True)
    started = time.perf_counter()
    completed = 0
    failures: list[tuple[Path, str]] = []
    tasks = [(folder, args.fit_points) for folder in run_folders]
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(plot_run_worker, task) for task in tasks]
        for future in as_completed(futures):
            folder, error = future.result()
            completed += 1
            if error is not None:
                failures.append((folder, error))
            if completed % 100 == 0 or completed == len(run_folders):
                print(
                    f"Processed {completed}/{len(run_folders)}; failures: {len(failures)}",
                    flush=True,
                )

    elapsed = time.perf_counter() - started
    print(f"Finished in {elapsed:.1f} s; updated {completed - len(failures)} PNGs.")
    if failures:
        failure_log = args.run_folder / "allan_plot_update_failures.csv"
        with failure_log.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["run_folder", "error"])
            writer.writerows(failures)
        print(f"Failures written to {failure_log.resolve()}")


if __name__ == "__main__":
    main()
