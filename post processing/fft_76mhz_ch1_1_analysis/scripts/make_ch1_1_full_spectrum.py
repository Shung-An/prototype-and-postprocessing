from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ANALYSIS_DIR = Path(__file__).resolve().parents[1]
POST_PROCESSING_DIR = ANALYSIS_DIR.parent
DEFAULT_NOTES_CSV = POST_PROCESSING_DIR / "raw_backed_fft_measurement_notes.csv"
DEFAULT_OUTPUT_DIR = ANALYSIS_DIR / "raw_highres" / "full_spectrum"
DEFAULT_SAMPLE_RATE_HZ = 608_000_000.0
DEFAULT_FFT_LENGTH = 4_194_304
DEFAULT_MAX_FRAMES_PER_RUN = 32
CHANNELS_PER_DATA_FILE = 2
CHANNEL_INDEX_ZERO_BASED = 0
DATA_FILE_NAME = "Data_1_1.bin"
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


@dataclass(frozen=True)
class RunInfo:
    run_name: str
    measurement_note: str
    run_folder: Path


def read_runs(notes_csv: Path, run_names: list[str]) -> list[RunInfo]:
    selected = set(run_names)
    runs: list[RunInfo] = []
    with notes_csv.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["run_name"] not in selected:
                continue
            raw_file = Path(row["run_folder"]) / DATA_FILE_NAME
            if not raw_file.is_file():
                continue
            runs.append(
                RunInfo(
                    run_name=row["run_name"],
                    measurement_note=row.get("measurement_note", ""),
                    run_folder=Path(row["run_folder"]),
                )
            )

    order = {run_name: index for index, run_name in enumerate(run_names)}
    return sorted(runs, key=lambda item: order[item.run_name])


def selected_frame_indexes(total_frames: int, max_frames: int) -> list[int]:
    frames_to_use = min(total_frames, max_frames)
    if frames_to_use <= 0:
        return []
    if frames_to_use == 1:
        return [0]
    return sorted({int(round(value)) for value in np.linspace(0, total_frames - 1, frames_to_use)})


def compute_full_spectrum(
    run: RunInfo,
    *,
    sample_rate_hz: float,
    fft_length: int,
    max_frames_per_run: int,
) -> tuple[np.ndarray, int]:
    raw_file = run.run_folder / DATA_FILE_NAME
    bytes_per_sample = np.dtype(np.int16).itemsize
    frame_samples = fft_length * CHANNELS_PER_DATA_FILE
    frame_bytes = frame_samples * bytes_per_sample
    total_frames = raw_file.stat().st_size // frame_bytes
    frame_indexes = selected_frame_indexes(total_frames, max_frames_per_run)
    if not frame_indexes:
        raise RuntimeError(f"{raw_file} does not contain one complete {fft_length}-point frame.")

    window = np.hanning(fft_length)
    window_power = float(np.sum(window * window))
    accumulated = np.zeros(fft_length // 2 + 1, dtype=np.float64)
    frames_used = 0

    with raw_file.open("rb") as handle:
        for frame_index in frame_indexes:
            handle.seek(frame_index * frame_bytes)
            data = np.frombuffer(handle.read(frame_bytes), dtype=np.int16, count=frame_samples)
            if data.size != frame_samples:
                continue
            reshaped = data.reshape(fft_length, CHANNELS_PER_DATA_FILE)
            samples = reshaped[:, CHANNEL_INDEX_ZERO_BASED].astype(np.float64, copy=False)
            samples = (samples - float(np.mean(samples))) * window
            fft_values = np.fft.rfft(samples)
            psd = (np.abs(fft_values) ** 2) / (sample_rate_hz * window_power)
            psd *= 2.0
            psd[0] *= 0.5
            if fft_length % 2 == 0:
                psd[-1] *= 0.5
            accumulated += psd
            frames_used += 1

    if frames_used == 0:
        raise RuntimeError(f"No complete frames were read from {raw_file}.")
    return np.maximum(accumulated / frames_used, 1e-300), frames_used


def save_full_csv(
    path: Path,
    frequency_hz: np.ndarray,
    spectra: dict[str, np.ndarray],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Frequency_Hz", "Frequency_MHz", *spectra.keys()])
        for index, frequency in enumerate(frequency_hz):
            writer.writerow(
                [
                    f"{frequency:.17g}",
                    f"{frequency / 1e6:.12f}",
                    *[f"{spectrum[index]:.17g}" for spectrum in spectra.values()],
                ]
            )


def log_bin_average(
    frequency_hz: np.ndarray,
    spectrum: np.ndarray,
    *,
    bins_per_decade: int,
) -> tuple[np.ndarray, np.ndarray]:
    mask = frequency_hz > 0
    freq = frequency_hz[mask]
    values = spectrum[mask]
    edges = np.logspace(
        math.log10(float(freq[0])),
        math.log10(float(freq[-1])),
        int(math.ceil(math.log10(float(freq[-1] / freq[0])) * bins_per_decade)) + 1,
    )
    bin_index = np.searchsorted(edges, freq, side="right") - 1
    valid = (bin_index >= 0) & (bin_index < edges.size - 1)
    bin_index = bin_index[valid]
    freq = freq[valid]
    values = values[valid]
    counts = np.bincount(bin_index, minlength=edges.size - 1)
    sum_freq = np.bincount(bin_index, weights=freq, minlength=edges.size - 1)
    sum_values = np.bincount(bin_index, weights=values, minlength=edges.size - 1)
    keep = counts > 0
    return sum_freq[keep] / counts[keep], np.maximum(sum_values[keep] / counts[keep], 1e-300)


def save_plot_semilog_y(
    path: Path,
    frequency_hz: np.ndarray,
    spectra: dict[str, np.ndarray],
    *,
    max_plot_points: int,
) -> None:
    stride = max(1, math.ceil(frequency_hz.size / max_plot_points))
    freq_mhz = frequency_hz[::stride] / 1e6
    fig, ax = plt.subplots(figsize=(13, 7), dpi=180)
    for run_name, spectrum in spectra.items():
        ax.semilogy(
            freq_mhz,
            spectrum[::stride],
            color=COLORS[run_name],
            linewidth=0.9,
            label=f"{run_name}: {LABELS[run_name]}",
        )
    ax.axvline(76.0, color="black", linewidth=0.9, alpha=0.5)
    ax.set_xlabel("Frequency (MHz)")
    ax.set_ylabel("PSD (counts^2/Hz)")
    ax.set_title("Ch1-1 full raw spectrum, 0 to 304 MHz")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def save_plot_loglog(
    path: Path,
    frequency_hz: np.ndarray,
    spectra: dict[str, np.ndarray],
    *,
    bins_per_decade: int,
) -> None:
    fig, ax = plt.subplots(figsize=(13, 7), dpi=180)
    for run_name, spectrum in spectra.items():
        freq_binned, psd_binned = log_bin_average(
            frequency_hz,
            spectrum,
            bins_per_decade=bins_per_decade,
        )
        ax.loglog(
            freq_binned,
            psd_binned,
            color=COLORS[run_name],
            linewidth=1.2,
            label=f"{run_name}: {LABELS[run_name]}",
        )
    ax.axvline(76_000_000.0, color="black", linewidth=0.9, alpha=0.5)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("PSD (counts^2/Hz)")
    ax.set_title("Ch1-1 full raw spectrum, log-log binned view")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def save_summary(
    path: Path,
    frequency_hz: np.ndarray,
    spectra: dict[str, np.ndarray],
    frames_used: dict[str, int],
) -> None:
    targets_hz = [76_000_000.0, 76_800_000.0]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "run_name",
                "label",
                "frames_used",
                "bin_spacing_hz",
                "median_psd",
                "max_psd",
                "max_frequency_hz",
                "psd_at_76mhz",
                "psd_db_at_76mhz",
                "psd_at_76p8mhz",
                "psd_db_at_76p8mhz",
            ]
        )
        for run_name, spectrum in spectra.items():
            max_index = int(np.argmax(spectrum))
            target_values = []
            for target_hz in targets_hz:
                target_index = int(np.argmin(np.abs(frequency_hz - target_hz)))
                psd = float(spectrum[target_index])
                target_values.extend([f"{psd:.17g}", f"{10.0 * math.log10(psd):.12g}"])
            writer.writerow(
                [
                    run_name,
                    LABELS[run_name],
                    frames_used[run_name],
                    f"{frequency_hz[1] - frequency_hz[0]:.12g}",
                    f"{float(np.median(spectrum)):.17g}",
                    f"{float(spectrum[max_index]):.17g}",
                    f"{float(frequency_hz[max_index]):.17g}",
                    *target_values,
                ]
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Make full-spectrum ch1-1 FFT plots and CSVs.")
    parser.add_argument("--notes-csv", type=Path, default=DEFAULT_NOTES_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--sample-rate-hz", type=float, default=DEFAULT_SAMPLE_RATE_HZ)
    parser.add_argument("--fft-length", type=int, default=DEFAULT_FFT_LENGTH)
    parser.add_argument("--max-frames-per-run", type=int, default=DEFAULT_MAX_FRAMES_PER_RUN)
    parser.add_argument("--max-plot-points", type=int, default=250_000)
    parser.add_argument("--bins-per-decade", type=int, default=220)
    parser.add_argument("--skip-full-csv", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    runs = read_runs(args.notes_csv, SELECTED_RUNS)
    frequency_hz = np.fft.rfftfreq(args.fft_length, d=1.0 / args.sample_rate_hz)
    spectra: dict[str, np.ndarray] = {}
    frames_used: dict[str, int] = {}
    for index, run in enumerate(runs, start=1):
        print(f"[{index}/{len(runs)}] Processing {run.run_name}", flush=True)
        spectrum, used = compute_full_spectrum(
            run,
            sample_rate_hz=args.sample_rate_hz,
            fft_length=args.fft_length,
            max_frames_per_run=args.max_frames_per_run,
        )
        spectra[run.run_name] = spectrum
        frames_used[run.run_name] = used
        print(f"  frames={used}, bins={spectrum.size}", flush=True)

    full_csv = args.output_dir / "ch1_1_full_spectrum_selected.csv"
    summary_csv = args.output_dir / "ch1_1_full_spectrum_selected_summary.csv"
    semilog_plot = args.output_dir / "ch1_1_full_spectrum_selected_semilogy.png"
    loglog_plot = args.output_dir / "ch1_1_full_spectrum_selected_loglog.png"

    if not args.skip_full_csv:
        save_full_csv(full_csv, frequency_hz, spectra)
        print(f"Saved full spectrum CSV: {full_csv}")
    save_summary(summary_csv, frequency_hz, spectra, frames_used)
    save_plot_semilog_y(semilog_plot, frequency_hz, spectra, max_plot_points=args.max_plot_points)
    save_plot_loglog(loglog_plot, frequency_hz, spectra, bins_per_decade=args.bins_per_decade)
    print(f"Saved summary CSV: {summary_csv}")
    print(f"Saved semilogy plot: {semilog_plot}")
    print(f"Saved loglog plot: {loglog_plot}")


if __name__ == "__main__":
    main()
