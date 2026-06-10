from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ANALYSIS_DIR = Path(__file__).resolve().parents[1]
DEFAULT_AB_DIR = ANALYSIS_DIR / "raw_highres" / "ab_test_76mhz_pm25khz"
DEFAULT_SPECTRUM_CSV = DEFAULT_AB_DIR / "ch1_1_76mhz_pm25khz_raw_highres_selected_spectrum.csv"

CENTER_HZ = 76_000_000.0
SAMPLE_RATE_HZ = 608_000_000.0
TWO_TAP_DELAY_SAMPLES = round(SAMPLE_RATE_HZ / CENTER_HZ)
FIR_DB_FLOOR = -160.0
AB_TRACE_OFFSET_DB = 12.0

RUNS = [
    "20260515_092941",
    "20260515_133100",
    "20260521_162959",
    "20260526_141535",
    "20260526_143329",
    "20260526_150209",
    "20260526_162112",
]

RUN_INFO = {
    "20260515_092941": {
        "label": "Dark noise",
        "group": "A0 reference",
        "wavelength_nm": "none",
        "mode": "dark",
        "note": "Dark-noise reference, no laser signal",
        "color": "#4C78A8",
    },
    "20260515_133100": {
        "label": "Flint2 only @1030",
        "group": "A laser-only",
        "wavelength_nm": "1030",
        "mode": "laser only",
        "note": "Flint2 laser-only reference",
        "color": "#F58518",
    },
    "20260521_162959": {
        "label": "OPO/highpass @780",
        "group": "B OPO 780",
        "wavelength_nm": "780",
        "mode": "highpass",
        "note": "Using the 20260521 vacuum highpass run per previous comparison",
        "color": "#54A24B",
    },
    "20260526_141535": {
        "label": "OPO @1560 auto",
        "group": "C 1560 auto/manual",
        "wavelength_nm": "1560",
        "mode": "auto",
        "note": "Raw-backed 1560 nm automatic measurement",
        "color": "#B279A2",
    },
    "20260526_143329": {
        "label": "OPO @1560 manual",
        "group": "C 1560 auto/manual",
        "wavelength_nm": "1560",
        "mode": "manual",
        "note": "Raw-backed 1560 nm manual measurement, replacement for the earlier incorrect manual selection",
        "color": "#9D755D",
    },
    "20260526_150209": {
        "label": "OPO @1600 manual A",
        "group": "D 1600 manual",
        "wavelength_nm": "1600",
        "mode": "manual",
        "note": "Raw-backed 1600 nm highpass without SHG, manual mode",
        "color": "#E45756",
    },
    "20260526_162112": {
        "label": "OPO @1600 manual B",
        "group": "D 1600 manual",
        "wavelength_nm": "1600",
        "mode": "manual",
        "note": "Raw-backed 1600 nm highpass without SHG, manual repeat; no raw-backed 1600 auto was found",
        "color": "#72B7B2",
    },
}


def safe_db(value: float) -> float:
    return 10.0 * math.log10(max(value, 1e-300))


def two_tap_fir_attenuation_db(frequency_hz: float) -> float:
    magnitude = abs(math.sin(math.pi * TWO_TAP_DELAY_SAMPLES * frequency_hz / SAMPLE_RATE_HZ))
    if magnitude <= 0:
        return FIR_DB_FLOOR
    return max(20.0 * math.log10(magnitude), FIR_DB_FLOOR)


def read_raw_spectrum(path: Path) -> tuple[list[float], dict[str, list[float]]]:
    offsets_hz: list[float] = []
    series = {run: [] for run in RUNS}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            frequency_hz = float(row["Frequency_Hz"])
            offsets_hz.append(frequency_hz - CENTER_HZ)
            for run in RUNS:
                series[run].append(float(row[run]))
    return offsets_hz, series


def write_labels_csv(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = ["run_name", "label", "group", "wavelength_nm", "mode", "note"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for run in RUNS:
            row = {"run_name": run}
            row.update({key: RUN_INFO[run][key] for key in fieldnames if key != "run_name"})
            writer.writerow(row)


def write_summary_csv(path: Path, offsets_hz: list[float], series: dict[str, list[float]]) -> None:
    nearest_76_index = min(range(len(offsets_hz)), key=lambda index: abs(offsets_hz[index]))
    dark_at_76 = series["20260515_092941"][nearest_76_index]
    with path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "run_name",
            "label",
            "group",
            "wavelength_nm",
            "mode",
            "raw_psd_db_at_76mhz",
            "raw_db_vs_dark_at_76mhz",
            "raw_peak_db_in_pm25khz",
            "raw_peak_offset_hz",
            "raw_median_db_in_pm25khz",
            "after_2tap_fir_max_db_in_pm25khz",
            "after_2tap_fir_max_offset_hz",
            "after_2tap_fir_median_db_in_pm25khz",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for run in RUNS:
            raw_db = [safe_db(value) for value in series[run]]
            after_db = [
                raw_db[index] + two_tap_fir_attenuation_db(CENTER_HZ + offset_hz)
                for index, offset_hz in enumerate(offsets_hz)
            ]
            raw_peak_index = max(range(len(raw_db)), key=lambda index: raw_db[index])
            after_peak_index = max(range(len(after_db)), key=lambda index: after_db[index])
            row = {
                "run_name": run,
                "label": RUN_INFO[run]["label"],
                "group": RUN_INFO[run]["group"],
                "wavelength_nm": RUN_INFO[run]["wavelength_nm"],
                "mode": RUN_INFO[run]["mode"],
                "raw_psd_db_at_76mhz": f"{raw_db[nearest_76_index]:.12g}",
                "raw_db_vs_dark_at_76mhz": f"{10.0 * math.log10(series[run][nearest_76_index] / dark_at_76):.12g}",
                "raw_peak_db_in_pm25khz": f"{raw_db[raw_peak_index]:.12g}",
                "raw_peak_offset_hz": f"{offsets_hz[raw_peak_index]:.12g}",
                "raw_median_db_in_pm25khz": f"{sorted(raw_db)[len(raw_db) // 2]:.12g}",
                "after_2tap_fir_max_db_in_pm25khz": f"{after_db[after_peak_index]:.12g}",
                "after_2tap_fir_max_offset_hz": f"{offsets_hz[after_peak_index]:.12g}",
                "after_2tap_fir_median_db_in_pm25khz": f"{sorted(after_db)[len(after_db) // 2]:.12g}",
            }
            writer.writerow(row)


def plot_lines(
    path: Path,
    offsets_hz: list[float],
    y_by_run: dict[str, list[float]],
    title: str,
    ylabel: str,
    xlim_hz: tuple[float, float],
    *,
    x_abs: bool = False,
    zero_line: bool = False,
    offset_step_db: float | None = None,
) -> None:
    fig, ax = plt.subplots(figsize=(11, 6.4), dpi=180)
    offset_step = offset_step_db or 0.0
    for index, run in enumerate(RUNS):
        x_values = [abs(offset) / 1e3 if x_abs else offset / 1e3 for offset in offsets_hz]
        y_offset = index * offset_step
        y_values = [value + y_offset for value in y_by_run[run]]
        label = RUN_INFO[run]["label"]
        if offset_step:
            label = f"{label} (+{y_offset:g} dB)"
        ax.plot(
            x_values,
            y_values,
            label=label,
            color=RUN_INFO[run]["color"],
            linewidth=1.6,
        )
    if zero_line:
        ax.axhline(0, color="black", linestyle=":", linewidth=1)
    if x_abs:
        ax.set_xlim(abs(xlim_hz[0]) / 1e3, abs(xlim_hz[1]) / 1e3)
        ax.set_xlabel("Absolute offset from 76 MHz (kHz)")
    else:
        ax.set_xlim(xlim_hz[0] / 1e3, xlim_hz[1] / 1e3)
        ax.set_xlabel("Offset from 76 MHz (kHz)")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, alpha=0.25)
    legend_title = f"{offset_step:g} dB per trace" if offset_step else None
    ax.legend(loc="best", fontsize=8, title=legend_title, title_fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def positive_offset_subset(
    offsets_hz: list[float],
    values_by_run: dict[str, list[float]],
    max_offset_hz: float,
) -> tuple[list[float], dict[str, list[float]]]:
    indexes = [index for index, offset in enumerate(offsets_hz) if 0 <= offset <= max_offset_hz]
    return [offsets_hz[index] for index in indexes], {
        run: [values_by_run[run][index] for index in indexes] for run in RUNS
    }


def folded_abs_offset_subset(
    offsets_hz: list[float],
    values_by_run: dict[str, list[float]],
    max_offset_hz: float,
) -> tuple[list[float], dict[str, list[float]]]:
    bins: dict[float, dict[str, list[float]]] = {}
    for index, offset in enumerate(offsets_hz):
        abs_offset = abs(offset)
        if abs_offset > max_offset_hz:
            continue
        bucket = round(abs_offset, 9)
        bins.setdefault(bucket, {run: [] for run in RUNS})
        for run in RUNS:
            bins[bucket][run].append(values_by_run[run][index])

    folded_offsets = sorted(bins)
    folded_series = {run: [] for run in RUNS}
    for offset in folded_offsets:
        for run in RUNS:
            values = bins[offset][run]
            folded_series[run].append(sum(values) / len(values))
    return folded_offsets, folded_series


def write_spectrum_csv(
    path: Path,
    offsets_hz: list[float],
    values_by_run: dict[str, list[float]],
    value_suffix: str,
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = ["Offset_Hz", *[f"{run}_{value_suffix}" for run in RUNS]]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index, offset_hz in enumerate(offsets_hz):
            row = {"Offset_Hz": f"{offset_hz:.12g}"}
            for run in RUNS:
                row[f"{run}_{value_suffix}"] = f"{values_by_run[run][index]:.12g}"
            writer.writerow(row)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Make polished AB-test plots for the 76 MHz focused FFT comparison.")
    parser.add_argument("--spectrum-csv", type=Path, default=DEFAULT_SPECTRUM_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_AB_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    offsets_hz, raw_psd = read_raw_spectrum(args.spectrum_csv)
    raw_db = {run: [safe_db(value) for value in raw_psd[run]] for run in RUNS}
    after_fir_db = {
        run: [
            raw_db[run][index] + two_tap_fir_attenuation_db(CENTER_HZ + offset_hz)
            for index, offset_hz in enumerate(offsets_hz)
        ]
        for run in RUNS
    }
    dark_db = raw_db["20260515_092941"]
    raw_db_vs_dark = {
        run: [raw_db[run][index] - dark_db[index] for index in range(len(offsets_hz))]
        for run in RUNS
    }

    write_labels_csv(args.output_dir / "ab_test_76mhz_pm25khz_run_labels.csv")
    write_summary_csv(args.output_dir / "ab_test_76mhz_pm25khz_summary.csv", offsets_hz, raw_psd)
    write_spectrum_csv(args.output_dir / "ab_test_76mhz_pm25khz_raw_db_spectrum.csv", offsets_hz, raw_db, "raw_dB")
    write_spectrum_csv(
        args.output_dir / "ab_test_76mhz_pm25khz_raw_db_vs_dark_spectrum.csv",
        offsets_hz,
        raw_db_vs_dark,
        "raw_dB_vs_dark",
    )
    write_spectrum_csv(
        args.output_dir / "ab_test_76mhz_pm25khz_after_2tap_fir_db_spectrum.csv",
        offsets_hz,
        after_fir_db,
        "after_2tap_fir_dB",
    )

    plot_lines(
        args.output_dir / "ab_test_76mhz_pm25khz_raw_db.png",
        offsets_hz,
        raw_db,
        "AB test near 76 MHz, raw PSD",
        "PSD (dB counts^2/Hz)",
        (-25_000.0, 25_000.0),
    )
    plot_lines(
        args.output_dir / "ab_test_76mhz_pm25khz_raw_db_offset.png",
        offsets_hz,
        raw_db,
        "AB test near 76 MHz, raw PSD, vertically offset",
        "PSD (dB counts^2/Hz, vertically offset)",
        (-25_000.0, 25_000.0),
        offset_step_db=AB_TRACE_OFFSET_DB,
    )
    plot_lines(
        args.output_dir / "ab_test_76mhz_pm25khz_raw_db_vs_dark.png",
        offsets_hz,
        raw_db_vs_dark,
        "AB test near 76 MHz, raw PSD relative to dark",
        "PSD difference vs dark (dB)",
        (-25_000.0, 25_000.0),
        zero_line=True,
    )
    plot_lines(
        args.output_dir / "ab_test_76mhz_pm25khz_after_2tap_fir_db.png",
        offsets_hz,
        after_fir_db,
        "AB test near 76 MHz, residual after 2-tap FIR",
        "Residual PSD (dB counts^2/Hz)",
        (-25_000.0, 25_000.0),
    )

    for name, values, ylabel, title in [
        ("raw_db", raw_db, "PSD (dB counts^2/Hz)", "DC to 25 kHz offset, raw PSD"),
        (
            "raw_db_vs_dark",
            raw_db_vs_dark,
            "PSD difference vs dark (dB)",
            "DC to 25 kHz offset, raw PSD relative to dark",
        ),
        (
            "after_2tap_fir_db",
            after_fir_db,
            "Residual PSD (dB counts^2/Hz)",
            "DC to 25 kHz offset, residual after 2-tap FIR",
        ),
    ]:
        pos_offsets, pos_values = positive_offset_subset(offsets_hz, values, 25_000.0)
        folded_offsets, folded_values = folded_abs_offset_subset(offsets_hz, values, 25_000.0)
        write_spectrum_csv(
            args.output_dir / f"ab_test_76mhz_dc_to_25khz_positive_offset_{name}.csv",
            pos_offsets,
            pos_values,
            name,
        )
        write_spectrum_csv(
            args.output_dir / f"ab_test_76mhz_dc_to_25khz_folded_abs_offset_{name}.csv",
            folded_offsets,
            folded_values,
            name,
        )
        plot_lines(
            args.output_dir / f"ab_test_76mhz_dc_to_25khz_positive_offset_{name}.png",
            pos_offsets,
            pos_values,
            title,
            ylabel,
            (0.0, 25_000.0),
            zero_line=name.endswith("vs_dark"),
        )
        plot_lines(
            args.output_dir / f"ab_test_76mhz_dc_to_25khz_folded_abs_offset_{name}.png",
            folded_offsets,
            folded_values,
            f"{title}, folded +/- offsets",
            ylabel,
            (0.0, 25_000.0),
            x_abs=True,
            zero_line=name.endswith("vs_dark"),
        )

    print(f"Saved polished AB plots and summaries to: {args.output_dir}")


if __name__ == "__main__":
    main()
