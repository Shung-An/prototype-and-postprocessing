from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ANALYSIS_DIR = Path(__file__).resolve().parents[1]
RAW_HIGHRES_DIR = ANALYSIS_DIR / "raw_highres"
DEFAULT_SPECTRUM_CSV = RAW_HIGHRES_DIR / "ch1_1_76mhz_pm10khz_raw_highres_spectrum_all_raw.csv"
DEFAULT_SUMMARY_CSV = RAW_HIGHRES_DIR / "ch1_1_76mhz_pm10khz_raw_highres_summary_all_raw.csv"
DEFAULT_OUTPUT_DIR = RAW_HIGHRES_DIR
CENTER_HZ = 76_000_000.0
SELECTED_RUNS = [
    "20260515_092941",
    "20260515_133100",
    "20260515_134951",
    "20260515_140509",
]
LABELS = {
    "20260515_092941": "Dark noise reference",
    "20260515_133100": "Flint2 laser @1030 nm",
    "20260515_134951": "OPO single point @800 nm",
    "20260515_140509": "OPO scanning @800 nm",
}
COLORS = {
    "20260515_092941": "#4C78A8",
    "20260515_133100": "#F58518",
    "20260515_134951": "#54A24B",
    "20260515_140509": "#B279A2",
}


def read_spectrum(path: Path) -> tuple[list[float], dict[str, list[float]]]:
    frequency_offsets_khz: list[float] = []
    series = {run: [] for run in SELECTED_RUNS}
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            frequency_offsets_khz.append((float(row["Frequency_Hz"]) - CENTER_HZ) / 1e3)
            for run in SELECTED_RUNS:
                series[run].append(float(row[run]))
    return frequency_offsets_khz, series


def read_selected_summary(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["run_name"] in SELECTED_RUNS:
                rows.append(row)
    rows.sort(key=lambda row: SELECTED_RUNS.index(row["run_name"]))
    return rows


def write_selected_summary(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def write_selected_spectrum(
    path: Path,
    frequency_offsets_khz: list[float],
    series: dict[str, list[float]],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Frequency_Hz", "Frequency_MHz", *SELECTED_RUNS])
        for index, offset_khz in enumerate(frequency_offsets_khz):
            frequency_hz = CENTER_HZ + offset_khz * 1e3
            writer.writerow(
                [
                    f"{frequency_hz:.17g}",
                    f"{frequency_hz / 1e6:.12f}",
                    *[f"{series[run][index]:.17g}" for run in SELECTED_RUNS],
                ]
            )


def save_overlay_plot(
    path: Path,
    frequency_offsets_khz: list[float],
    series: dict[str, list[float]],
) -> None:
    fig, ax = plt.subplots(figsize=(12, 7), dpi=180)
    for run in SELECTED_RUNS:
        ax.semilogy(
            frequency_offsets_khz,
            series[run],
            linewidth=1.4,
            label=f"{run}: {LABELS[run]}",
            color=COLORS[run],
        )
    ax.axvline(0, color="black", linewidth=0.8, alpha=0.45)
    ax.set_xlabel("Offset from 76 MHz (kHz)")
    ax.set_ylabel("PSD (counts^2/Hz)")
    ax.set_title("Ch1-1 raw FFT near 76 MHz, selected measurements, +/-10 kHz")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(loc="best", fontsize=9)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def save_peak_plot(path: Path, rows: list[dict[str, str]]) -> None:
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8), dpi=180, sharex=True)
    x_values = list(range(len(rows)))
    colors = [COLORS[row["run_name"]] for row in rows]
    psd = [float(row["psd_at_nearest_76_bin"]) for row in rows]
    db = [
        float(row["db_vs_20260515_092941_at_76mhz"])
        if row["db_vs_20260515_092941_at_76mhz"]
        else math.nan
        for row in rows
    ]
    tick_labels = [f"{row['run_name']}\n{LABELS[row['run_name']]}" for row in rows]

    ax1.bar(x_values, psd, color=colors)
    ax1.set_yscale("log")
    ax1.set_ylabel("PSD at 76 MHz\n(counts^2/Hz)")
    ax1.set_title("Ch1-1 76 MHz peak comparison, selected measurements")
    ax1.grid(True, axis="y", which="both", alpha=0.25)

    ax2.bar(x_values, db, color=colors)
    ax2.axhline(0, color="black", linewidth=0.8, alpha=0.5)
    ax2.set_ylabel("dB vs dark noise")
    ax2.set_xticks(x_values)
    ax2.set_xticklabels(tick_labels, rotation=20, ha="right")
    ax2.grid(True, axis="y", alpha=0.25)

    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Make selected dark/flint2/OPO plots from the ch1-1 76 MHz raw FFT result."
    )
    parser.add_argument("--spectrum-csv", type=Path, default=DEFAULT_SPECTRUM_CSV)
    parser.add_argument("--summary-csv", type=Path, default=DEFAULT_SUMMARY_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    frequency_offsets_khz, series = read_spectrum(args.spectrum_csv)
    selected_summary_rows = read_selected_summary(args.summary_csv)

    selected_summary_path = args.output_dir / "ch1_1_76mhz_pm10khz_raw_highres_selected_summary.csv"
    selected_spectrum_path = args.output_dir / "ch1_1_76mhz_pm10khz_raw_highres_selected_spectrum.csv"
    overlay_plot_path = args.output_dir / "ch1_1_76mhz_pm10khz_raw_highres_selected_overlay.png"
    peak_plot_path = args.output_dir / "ch1_1_76mhz_pm10khz_raw_highres_selected_peak_comparison.png"

    write_selected_summary(selected_summary_path, selected_summary_rows)
    write_selected_spectrum(selected_spectrum_path, frequency_offsets_khz, series)
    save_overlay_plot(overlay_plot_path, frequency_offsets_khz, series)
    save_peak_plot(peak_plot_path, selected_summary_rows)

    print(f"Saved overlay plot: {overlay_plot_path}")
    print(f"Saved peak plot: {peak_plot_path}")
    print(f"Saved selected summary: {selected_summary_path}")
    print(f"Saved selected spectrum: {selected_spectrum_path}")


if __name__ == "__main__":
    main()
