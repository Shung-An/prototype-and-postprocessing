from __future__ import annotations

import argparse
import csv
import math
import re
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
SAMPLE_RATE_HZ = 608_000_000.0
TWO_TAP_DELAY_SAMPLES = round(SAMPLE_RATE_HZ / CENTER_HZ)
FIR_DB_FLOOR = -160.0
ALL_RAW_TRACE_OFFSET_DB = 12.0
SELECTED_RUNS = [
    "20260515_092941",
    "20260515_133100",
    "20260515_134951",
    "20260515_140509",
    "20260521_162959",
]
LABELS = {
    "20260515_092941": "Dark noise reference",
    "20260515_133100": "Flint2 laser @1030 nm",
    "20260515_134951": "OPO single point @800 nm",
    "20260515_140509": "OPO scanning @800 nm",
    "20260521_162959": "Vacuum highpass filter @780 nm",
}
COLORS = {
    "20260515_092941": "#4C78A8",
    "20260515_133100": "#F58518",
    "20260515_134951": "#54A24B",
    "20260515_140509": "#B279A2",
    "20260521_162959": "#E45756",
}
PALETTE = [
    "#4C78A8",
    "#F58518",
    "#54A24B",
    "#B279A2",
    "#E45756",
    "#72B7B2",
    "#EECA3B",
    "#FF9DA6",
    "#9D755D",
    "#BAB0AC",
]


def short_note(note: str) -> str:
    pieces = [part.strip() for part in note.split(";") if part.strip()]
    keep = []
    for piece in pieces:
        if piece in {"Vacuum", "4 interleaved channels"}:
            continue
        keep.append(piece)
        if len(keep) == 2:
            break
    return "; ".join(keep) if keep else note[:70]


def populate_labels_and_colors(summary_rows: list[dict[str, str]]) -> None:
    for index, run in enumerate(SELECTED_RUNS):
        COLORS.setdefault(run, PALETTE[index % len(PALETTE)])
    for row in summary_rows:
        run = row["run_name"]
        if run not in LABELS:
            LABELS[run] = short_note(row.get("measurement_note", "")) or run


def label_for(run: str) -> str:
    return LABELS.get(run, run)


def color_for(run: str) -> str:
    if run not in COLORS:
        COLORS[run] = PALETTE[len(COLORS) % len(PALETTE)]
    return COLORS[run]


def infer_window_label(path: Path) -> str:
    match = re.search(r"ch1_1_76mhz_(pm[^_]+)_raw_highres", path.name)
    if match:
        return match.group(1)
    return "pm10khz"


def display_half_width_khz(frequency_offsets_khz: list[float]) -> float:
    return max(abs(offset) for offset in frequency_offsets_khz)


def safe_db_power(value: float) -> float:
    return 10.0 * math.log10(max(value, 1e-300))


def two_tap_fir_attenuation_db(frequency_hz: float) -> float:
    # Normalized 2-tap delay-line notch: H(f) = (1 - exp(-j 2 pi f D / Fs)) / 2.
    magnitude = abs(math.sin(math.pi * TWO_TAP_DELAY_SAMPLES * frequency_hz / SAMPLE_RATE_HZ))
    if magnitude <= 0:
        return FIR_DB_FLOOR
    return max(20.0 * math.log10(magnitude), FIR_DB_FLOOR)


def two_tap_rejection_half_width_hz(rejection_db: float) -> float:
    amplitude = 10.0 ** (-abs(rejection_db) / 20.0)
    return SAMPLE_RATE_HZ / (math.pi * TWO_TAP_DELAY_SAMPLES) * math.asin(amplitude)


def write_fir_rejection_csv(path: Path, frequency_offsets_khz: list[float]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "Offset_Hz",
                "Frequency_Hz",
                "TwoTapDelaySamples",
                "NormalizedFirAttenuation_dB",
            ]
        )
        for offset_khz in frequency_offsets_khz:
            frequency_hz = CENTER_HZ + offset_khz * 1e3
            writer.writerow(
                [
                    f"{offset_khz * 1e3:.12g}",
                    f"{frequency_hz:.17g}",
                    TWO_TAP_DELAY_SAMPLES,
                    f"{two_tap_fir_attenuation_db(frequency_hz):.12g}",
                ]
            )


def write_after_fir_spectrum(
    path: Path,
    frequency_offsets_khz: list[float],
    series: dict[str, list[float]],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "Frequency_Hz",
                "Frequency_MHz",
                "Offset_Hz",
                "TwoTapFirRejection_dB",
                *[f"{run}_after_fir_dB" for run in SELECTED_RUNS],
            ]
        )
        for index, offset_khz in enumerate(frequency_offsets_khz):
            frequency_hz = CENTER_HZ + offset_khz * 1e3
            fir_db = two_tap_fir_attenuation_db(frequency_hz)
            writer.writerow(
                [
                    f"{frequency_hz:.17g}",
                    f"{frequency_hz / 1e6:.12f}",
                    f"{offset_khz * 1e3:.12g}",
                    f"{fir_db:.12g}",
                    *[
                        f"{safe_db_power(series[run][index]) + fir_db:.12g}"
                        for run in SELECTED_RUNS
                    ],
                ]
            )


def write_after_fir_summary(
    path: Path,
    frequency_offsets_khz: list[float],
    series: dict[str, list[float]],
) -> None:
    nearest_76_index = min(range(len(frequency_offsets_khz)), key=lambda i: abs(frequency_offsets_khz[i]))
    with path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "run_name",
            "label",
            "after_fir_psd_db_at_76mhz",
            "after_fir_max_psd_db_in_window",
            "after_fir_max_offset_hz",
            "after_fir_median_psd_db_in_window",
            "before_fir_psd_db_at_76mhz",
            "two_tap_fir_rejection_db_at_76mhz",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for run in SELECTED_RUNS:
            after_db = []
            for index, offset_khz in enumerate(frequency_offsets_khz):
                frequency_hz = CENTER_HZ + offset_khz * 1e3
                after_db.append(safe_db_power(series[run][index]) + two_tap_fir_attenuation_db(frequency_hz))
            max_index = max(range(len(after_db)), key=lambda i: after_db[i])
            sorted_values = sorted(after_db)
            median_value = sorted_values[len(sorted_values) // 2]
            writer.writerow(
                {
                    "run_name": run,
                    "label": label_for(run),
                    "after_fir_psd_db_at_76mhz": f"{after_db[nearest_76_index]:.12g}",
                    "after_fir_max_psd_db_in_window": f"{after_db[max_index]:.12g}",
                    "after_fir_max_offset_hz": f"{frequency_offsets_khz[max_index] * 1e3:.12g}",
                    "after_fir_median_psd_db_in_window": f"{median_value:.12g}",
                    "before_fir_psd_db_at_76mhz": f"{safe_db_power(series[run][nearest_76_index]):.12g}",
                    "two_tap_fir_rejection_db_at_76mhz": f"{two_tap_fir_attenuation_db(CENTER_HZ):.12g}",
                }
            )


def write_fir_bandwidth_summary(path: Path, frequency_offsets_khz: list[float]) -> None:
    edge_offset_hz = max(abs(offset_khz) for offset_khz in frequency_offsets_khz) * 1e3
    edge_rejection_db = two_tap_fir_attenuation_db(CENTER_HZ + edge_offset_hz)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Metric", "Value", "Unit", "Note"])
        writer.writerow(["sample_rate", f"{SAMPLE_RATE_HZ:.17g}", "Hz", "ADC sample rate"])
        writer.writerow(["notch_frequency", f"{CENTER_HZ:.17g}", "Hz", "Target notch"])
        writer.writerow(
            [
                "two_tap_delay",
                TWO_TAP_DELAY_SAMPLES,
                "samples",
                "Fs / f0, using y[n] = (x[n] - x[n-D]) / 2",
            ]
        )
        writer.writerow(
            [
                "visible_window_edge_rejection",
                f"{edge_rejection_db:.6g}",
                "dB",
                f"Minimum rejection inside +/-{edge_offset_hz / 1e3:.3g} kHz window",
            ]
        )
        for rejection_db in (40.0, 60.0, 70.0, 80.0):
            half_width_hz = two_tap_rejection_half_width_hz(rejection_db)
            writer.writerow(
                [
                    f"full_bandwidth_at_least_{rejection_db:.0f}_db_rejection",
                    f"{2.0 * half_width_hz:.12g}",
                    "Hz",
                    f"+/-{half_width_hz / 1e3:.6g} kHz around 76 MHz",
                ]
            )


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


def read_all_spectrum(path: Path) -> tuple[list[float], list[str], dict[str, list[float]]]:
    frequency_offsets_khz: list[float] = []
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return frequency_offsets_khz, [], {}
        run_names = reader.fieldnames[2:]
        series = {run: [] for run in run_names}
        for row in reader:
            frequency_offsets_khz.append((float(row["Frequency_Hz"]) - CENTER_HZ) / 1e3)
            for run in run_names:
                series[run].append(float(row[run]))
    return frequency_offsets_khz, run_names, series


def read_summary(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


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
            label=f"{run}: {label_for(run)}",
            color=color_for(run),
        )
    ax.axvline(0, color="black", linewidth=0.8, alpha=0.45)
    ax.set_xlabel("Offset from 76 MHz (kHz)")
    ax.set_ylabel("PSD (counts^2/Hz)")
    ax.set_title(
        f"Ch1-1 raw FFT near 76 MHz, selected measurements, "
        f"+/-{display_half_width_khz(frequency_offsets_khz):g} kHz"
    )
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(loc="best", fontsize=9)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def save_all_raw_offset_plot(
    path: Path,
    frequency_offsets_khz: list[float],
    run_names: list[str],
    series: dict[str, list[float]],
) -> None:
    fig, ax = plt.subplots(figsize=(14, 8), dpi=180)
    for index, run in enumerate(run_names):
        offset_db = index * ALL_RAW_TRACE_OFFSET_DB
        values_db = [safe_db_power(value) + offset_db for value in series[run]]
        ax.plot(
            frequency_offsets_khz,
            values_db,
            linewidth=1.1,
            label=f"{run}: {label_for(run)} (+{offset_db:g} dB)",
            color=PALETTE[index % len(PALETTE)],
        )

    ax.axvline(0, color="black", linewidth=0.8, alpha=0.45)
    ax.set_xlabel("Offset from 76 MHz (kHz)")
    ax.set_ylabel("PSD (dB counts^2/Hz, vertically offset)")
    ax.set_title(
        f"Ch1-1 raw FFT near 76 MHz, all raw-backed measurements, "
        f"+/-{display_half_width_khz(frequency_offsets_khz):g} kHz"
    )
    ax.grid(True, alpha=0.25)
    ax.legend(
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        fontsize=7,
        title=f"{ALL_RAW_TRACE_OFFSET_DB:g} dB per trace",
        title_fontsize=8,
    )
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def save_peak_plot(path: Path, rows: list[dict[str, str]]) -> None:
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8), dpi=180, sharex=True)
    x_values = list(range(len(rows)))
    colors = [color_for(row["run_name"]) for row in rows]
    psd = [float(row["psd_at_nearest_76_bin"]) for row in rows]
    db = [
        float(row["db_vs_20260515_092941_at_76mhz"])
        if row["db_vs_20260515_092941_at_76mhz"]
        else math.nan
        for row in rows
    ]
    tick_labels = [f"{row['run_name']}\n{label_for(row['run_name'])}" for row in rows]

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


def save_db_overlay_with_fir_plot(
    path: Path,
    frequency_offsets_khz: list[float],
    series: dict[str, list[float]],
) -> None:
    fig, ax = plt.subplots(figsize=(12, 7), dpi=180)
    for run in SELECTED_RUNS:
        values_db = [safe_db_power(value) for value in series[run]]
        ax.plot(
            frequency_offsets_khz,
            values_db,
            linewidth=1.4,
            label=f"{run}: {label_for(run)}",
            color=color_for(run),
        )

    fir_db = [
        two_tap_fir_attenuation_db(CENTER_HZ + offset_khz * 1e3)
        for offset_khz in frequency_offsets_khz
    ]
    ax2 = ax.twinx()
    ax2.plot(
        frequency_offsets_khz,
        fir_db,
        color="black",
        linestyle="--",
        linewidth=1.5,
        label=f"2-tap FIR rejection, D={TWO_TAP_DELAY_SAMPLES} samples",
    )

    half_width_70_db_khz = two_tap_rejection_half_width_hz(70.0) / 1e3
    ax.axvline(0, color="black", linewidth=0.8, alpha=0.45)
    ax2.axhline(-70.0, color="black", linewidth=0.8, linestyle=":", alpha=0.65)
    for boundary in (-half_width_70_db_khz, half_width_70_db_khz):
        ax.axvline(boundary, color="black", linewidth=0.8, linestyle=":", alpha=0.65)
    ax.axvspan(-half_width_70_db_khz, half_width_70_db_khz, color="black", alpha=0.06)

    half_width_60_db_hz = two_tap_rejection_half_width_hz(60.0)
    edge_rejection_db = two_tap_fir_attenuation_db(
        CENTER_HZ + max(abs(offset_khz) for offset_khz in frequency_offsets_khz) * 1e3
    )
    annotation = (
        "2-tap FIR notch: y[n] = (x[n] - x[n-8]) / 2\n"
        f"Visible +/-{display_half_width_khz(frequency_offsets_khz):g} kHz edge rejection: "
        f"{edge_rejection_db:.1f} dB\n"
        f">=60 dB rejection BW: {2 * half_width_60_db_hz / 1e3:.1f} kHz\n"
        f">=70 dB rejection BW: {2 * half_width_70_db_khz:.1f} kHz"
    )
    ax.text(
        0.02,
        0.03,
        annotation,
        transform=ax.transAxes,
        fontsize=9,
        va="bottom",
        ha="left",
        bbox={"facecolor": "white", "edgecolor": "0.7", "alpha": 0.9},
    )

    ax.set_xlabel("Offset from 76 MHz (kHz)")
    ax.set_ylabel("PSD (dB counts^2/Hz)")
    ax2.set_ylabel("Normalized FIR rejection (dB)")
    ax.set_title(
        f"Ch1-1 raw FFT near 76 MHz with 2-tap FIR rejection, "
        f"+/-{display_half_width_khz(frequency_offsets_khz):g} kHz, dB scale"
    )
    ax.grid(True, alpha=0.25)
    ax2.set_ylim(FIR_DB_FLOOR, 2.0)

    lines, labels = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines + lines2, labels + labels2, loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def save_after_fir_plot(
    path: Path,
    frequency_offsets_khz: list[float],
    series: dict[str, list[float]],
) -> None:
    fig, ax = plt.subplots(figsize=(12, 7), dpi=180)
    for run in SELECTED_RUNS:
        after_db = [
            safe_db_power(series[run][index])
            + two_tap_fir_attenuation_db(CENTER_HZ + offset_khz * 1e3)
            for index, offset_khz in enumerate(frequency_offsets_khz)
        ]
        ax.plot(
            frequency_offsets_khz,
            after_db,
            linewidth=1.4,
            label=f"{run}: {label_for(run)}",
            color=color_for(run),
        )

    ax.axvline(0, color="black", linewidth=0.8, alpha=0.45)
    half_width_60_db_khz = two_tap_rejection_half_width_hz(60.0) / 1e3
    half_width_70_db_khz = two_tap_rejection_half_width_hz(70.0) / 1e3
    ax.axvspan(-half_width_60_db_khz, half_width_60_db_khz, color="black", alpha=0.05)
    for boundary in (-half_width_60_db_khz, half_width_60_db_khz):
        ax.axvline(boundary, color="black", linestyle="--", linewidth=0.8, alpha=0.55)
    for boundary in (-half_width_70_db_khz, half_width_70_db_khz):
        ax.axvline(boundary, color="black", linestyle=":", linewidth=0.8, alpha=0.65)

    ax.text(
        0.02,
        0.03,
        "After filter: PSD_out = PSD_in * |H(f)|^2\n"
        f">=60 dB rejection BW: {2 * half_width_60_db_khz:.1f} kHz\n"
        f">=70 dB rejection BW: {2 * half_width_70_db_khz:.1f} kHz",
        transform=ax.transAxes,
        fontsize=9,
        va="bottom",
        ha="left",
        bbox={"facecolor": "white", "edgecolor": "0.7", "alpha": 0.9},
    )

    ax.set_xlabel("Offset from 76 MHz (kHz)")
    ax.set_ylabel("Residual PSD after 2-tap FIR (dB counts^2/Hz)")
    ax.set_title(
        f"Ch1-1 residual after 2-tap FIR, +/-{display_half_width_khz(frequency_offsets_khz):g} kHz"
    )
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper right", fontsize=8)
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
    parser.add_argument(
        "--run-names",
        nargs="+",
        default=None,
        help="Optional explicit run names to extract from the spectrum and summary CSV files.",
    )
    return parser.parse_args()


def main() -> None:
    global SELECTED_RUNS
    args = parse_args()
    if args.run_names:
        SELECTED_RUNS = args.run_names
    args.output_dir.mkdir(parents=True, exist_ok=True)
    all_frequency_offsets_khz, all_run_names, all_series = read_all_spectrum(args.spectrum_csv)
    frequency_offsets_khz, series = read_spectrum(args.spectrum_csv)
    summary_rows = read_summary(args.summary_csv)
    selected_summary_rows = read_selected_summary(args.summary_csv)
    populate_labels_and_colors(summary_rows)
    window_label = infer_window_label(args.spectrum_csv)

    all_raw_plot_path = args.output_dir / f"ch1_1_76mhz_{window_label}_raw_highres_all_raw.png"
    selected_summary_path = args.output_dir / f"ch1_1_76mhz_{window_label}_raw_highres_selected_summary.csv"
    selected_spectrum_path = args.output_dir / f"ch1_1_76mhz_{window_label}_raw_highres_selected_spectrum.csv"
    overlay_plot_path = args.output_dir / f"ch1_1_76mhz_{window_label}_raw_highres_selected_overlay.png"
    peak_plot_path = args.output_dir / f"ch1_1_76mhz_{window_label}_raw_highres_selected_peak_comparison.png"
    db_fir_plot_path = args.output_dir / f"ch1_1_76mhz_{window_label}_raw_highres_selected_db_with_2tap_fir.png"
    after_fir_plot_path = args.output_dir / f"ch1_1_76mhz_{window_label}_raw_highres_selected_after_2tap_fir_db.png"
    after_fir_spectrum_csv_path = args.output_dir / f"ch1_1_76mhz_{window_label}_raw_highres_selected_after_2tap_fir_spectrum.csv"
    after_fir_summary_csv_path = args.output_dir / f"ch1_1_76mhz_{window_label}_raw_highres_selected_after_2tap_fir_summary.csv"
    fir_curve_csv_path = args.output_dir / f"ch1_1_76mhz_{window_label}_2tap_fir_rejection_curve.csv"
    fir_bandwidth_csv_path = args.output_dir / f"ch1_1_76mhz_{window_label}_2tap_fir_bandwidth_summary.csv"

    write_selected_summary(selected_summary_path, selected_summary_rows)
    write_selected_spectrum(selected_spectrum_path, frequency_offsets_khz, series)
    write_fir_rejection_csv(fir_curve_csv_path, frequency_offsets_khz)
    write_after_fir_spectrum(after_fir_spectrum_csv_path, frequency_offsets_khz, series)
    write_after_fir_summary(after_fir_summary_csv_path, frequency_offsets_khz, series)
    write_fir_bandwidth_summary(fir_bandwidth_csv_path, frequency_offsets_khz)
    save_all_raw_offset_plot(all_raw_plot_path, all_frequency_offsets_khz, all_run_names, all_series)
    save_overlay_plot(overlay_plot_path, frequency_offsets_khz, series)
    save_peak_plot(peak_plot_path, selected_summary_rows)
    save_db_overlay_with_fir_plot(db_fir_plot_path, frequency_offsets_khz, series)
    save_after_fir_plot(after_fir_plot_path, frequency_offsets_khz, series)

    print(f"Saved all-raw offset plot: {all_raw_plot_path}")
    print(f"Saved overlay plot: {overlay_plot_path}")
    print(f"Saved peak plot: {peak_plot_path}")
    print(f"Saved dB/FIR plot: {db_fir_plot_path}")
    print(f"Saved after-FIR plot: {after_fir_plot_path}")
    print(f"Saved selected summary: {selected_summary_path}")
    print(f"Saved selected spectrum: {selected_spectrum_path}")
    print(f"Saved after-FIR spectrum: {after_fir_spectrum_csv_path}")
    print(f"Saved after-FIR summary: {after_fir_summary_csv_path}")
    print(f"Saved FIR rejection curve: {fir_curve_csv_path}")
    print(f"Saved FIR bandwidth summary: {fir_bandwidth_csv_path}")


if __name__ == "__main__":
    main()
