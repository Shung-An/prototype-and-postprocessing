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
DEFAULT_OUTPUT_DIR = ANALYSIS_DIR / "raw_highres"
DEFAULT_CENTER_HZ = 76_000_000.0
DEFAULT_HALF_WIDTH_HZ = 10_000.0
DEFAULT_SAMPLE_RATE_HZ = 608_000_000.0
DEFAULT_FFT_LENGTH = 4_194_304
DEFAULT_MAX_FRAMES_PER_RUN = 32
CHANNELS_PER_DATA_FILE = 2
CHANNEL_INDEX_ZERO_BASED = 0
DATA_FILE_NAME = "Data_1_1.bin"
DARK_REFERENCE_RUN = "20260515_092941"


@dataclass(frozen=True)
class RunInfo:
    run_name: str
    measurement_note: str
    run_folder: Path


@dataclass(frozen=True)
class SpectrumResult:
    run: RunInfo
    frequency_hz: np.ndarray
    psd: np.ndarray
    frames_used: int
    bin_spacing_hz: float
    nearest_76_index: int
    peak_index: int
    local_median_psd: float


def read_runs(notes_csv: Path, include_all_raw: bool) -> list[RunInfo]:
    runs: list[RunInfo] = []
    with notes_csv.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            modes = row.get("modes", "")
            if not include_all_raw and "high_frequency" not in modes:
                continue

            run_folder = Path(row["run_folder"])
            raw_file = run_folder / DATA_FILE_NAME
            if not raw_file.is_file():
                continue

            runs.append(
                RunInfo(
                    run_name=row["run_name"],
                    measurement_note=row.get("measurement_note", ""),
                    run_folder=run_folder,
                )
            )

    return sorted(runs, key=lambda item: item.run_name)


def selected_frame_indexes(total_frames: int, max_frames: int) -> list[int]:
    frames_to_use = min(total_frames, max_frames)
    if frames_to_use <= 0:
        return []
    if frames_to_use == 1:
        return [0]
    return sorted({int(round(x)) for x in np.linspace(0, total_frames - 1, frames_to_use)})


def compute_run_spectrum(
    run: RunInfo,
    *,
    sample_rate_hz: float,
    fft_length: int,
    center_hz: float,
    half_width_hz: float,
    max_frames_per_run: int,
) -> SpectrumResult:
    raw_file = run.run_folder / DATA_FILE_NAME
    bytes_per_sample = np.dtype(np.int16).itemsize
    frame_samples = fft_length * CHANNELS_PER_DATA_FILE
    frame_bytes = frame_samples * bytes_per_sample
    total_frames = raw_file.stat().st_size // frame_bytes
    frame_indexes = selected_frame_indexes(total_frames, max_frames_per_run)
    if not frame_indexes:
        raise RuntimeError(f"{raw_file} does not contain one complete {fft_length}-point frame.")

    all_frequency_hz = np.fft.rfftfreq(fft_length, d=1.0 / sample_rate_hz)
    mask = (all_frequency_hz >= center_hz - half_width_hz) & (
        all_frequency_hz <= center_hz + half_width_hz
    )
    indexes = np.flatnonzero(mask)
    if indexes.size == 0:
        raise RuntimeError("Selected frequency window has no FFT bins.")

    window = np.hanning(fft_length)
    window_power = float(np.sum(window * window))
    accumulated = np.zeros(indexes.size, dtype=np.float64)
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
            psd = (np.abs(fft_values[indexes]) ** 2) / (sample_rate_hz * window_power)
            psd *= 2.0
            accumulated += psd
            frames_used += 1

    if frames_used == 0:
        raise RuntimeError(f"No complete frames were read from {raw_file}.")

    frequency_hz = all_frequency_hz[indexes]
    psd = np.maximum(accumulated / frames_used, 1e-30)
    nearest_76_index = int(np.argmin(np.abs(frequency_hz - center_hz)))
    peak_index = int(np.argmax(psd))
    local_median_psd = float(np.median(psd[np.isfinite(psd)]))
    return SpectrumResult(
        run=run,
        frequency_hz=frequency_hz,
        psd=psd,
        frames_used=frames_used,
        bin_spacing_hz=sample_rate_hz / fft_length,
        nearest_76_index=nearest_76_index,
        peak_index=peak_index,
        local_median_psd=local_median_psd,
    )


def save_spectrum_csv(path: Path, results: list[SpectrumResult]) -> None:
    if not results:
        return
    frequency_hz = results[0].frequency_hz
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Frequency_Hz", "Frequency_MHz", *[result.run.run_name for result in results]])
        for row_index, frequency in enumerate(frequency_hz):
            writer.writerow(
                [
                    f"{frequency:.17g}",
                    f"{frequency / 1e6:.12f}",
                    *[f"{result.psd[row_index]:.17g}" for result in results],
                ]
            )


def save_summary_csv(
    path: Path,
    results: list[SpectrumResult],
    *,
    fft_length: int,
    center_hz: float,
) -> None:
    dark_psd_at_76 = None
    for result in results:
        if result.run.run_name == DARK_REFERENCE_RUN:
            dark_psd_at_76 = float(result.psd[result.nearest_76_index])
            break

    with path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "run_name",
            "measurement_note",
            "raw_file",
            "fft_length",
            "measurement_physical_channels",
            "channels_per_data_file",
            "selected_data_file",
            "selected_interleaved_channel",
            "bin_spacing_hz",
            "frames_used",
            "nearest_76_bin_hz",
            "nearest_76_offset_hz",
            "psd_at_nearest_76_bin",
            "local_peak_hz",
            "local_peak_mhz",
            "local_peak_offset_hz",
            "local_peak_psd",
            "local_median_psd",
            "peak_to_local_median_ratio",
            "ratio_vs_20260515_092941_at_76mhz",
            "db_vs_20260515_092941_at_76mhz",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            psd_at_76 = float(result.psd[result.nearest_76_index])
            peak_psd = float(result.psd[result.peak_index])
            ratio = psd_at_76 / dark_psd_at_76 if dark_psd_at_76 else math.nan
            writer.writerow(
                {
                    "run_name": result.run.run_name,
                    "measurement_note": result.run.measurement_note,
                    "raw_file": str(result.run.run_folder / DATA_FILE_NAME),
                    "fft_length": fft_length,
                    "measurement_physical_channels": 4,
                    "channels_per_data_file": CHANNELS_PER_DATA_FILE,
                    "selected_data_file": DATA_FILE_NAME,
                    "selected_interleaved_channel": CHANNEL_INDEX_ZERO_BASED + 1,
                    "bin_spacing_hz": f"{result.bin_spacing_hz:.12g}",
                    "frames_used": result.frames_used,
                    "nearest_76_bin_hz": f"{result.frequency_hz[result.nearest_76_index]:.17g}",
                    "nearest_76_offset_hz": f"{result.frequency_hz[result.nearest_76_index] - center_hz:.12g}",
                    "psd_at_nearest_76_bin": f"{psd_at_76:.17g}",
                    "local_peak_hz": f"{result.frequency_hz[result.peak_index]:.17g}",
                    "local_peak_mhz": f"{result.frequency_hz[result.peak_index] / 1e6:.12f}",
                    "local_peak_offset_hz": f"{result.frequency_hz[result.peak_index] - center_hz:.12g}",
                    "local_peak_psd": f"{peak_psd:.17g}",
                    "local_median_psd": f"{result.local_median_psd:.17g}",
                    "peak_to_local_median_ratio": f"{peak_psd / result.local_median_psd:.17g}",
                    "ratio_vs_20260515_092941_at_76mhz": f"{ratio:.17g}",
                    "db_vs_20260515_092941_at_76mhz": f"{10 * math.log10(ratio):.12g}"
                    if ratio > 0 and math.isfinite(ratio)
                    else "",
                }
            )


def short_note(note: str) -> str:
    pieces = [part.strip() for part in note.split(";") if part.strip()]
    keep = []
    for piece in pieces:
        if piece in {"Vacuum", "4 interleaved channels"}:
            continue
        keep.append(piece)
        if len(keep) == 2:
            break
    return "; ".join(keep) if keep else note[:60]


def save_plot(path: Path, results: list[SpectrumResult], *, center_hz: float) -> None:
    fig, ax = plt.subplots(figsize=(14, 8), dpi=180)
    for result in results:
        label = f"{result.run.run_name}: {short_note(result.run.measurement_note)}"
        ax.semilogy((result.frequency_hz - center_hz) / 1e3, result.psd, linewidth=1.1, label=label)

    bin_spacing_hz = results[0].bin_spacing_hz if results else 0.0
    ax.axvline(0, color="black", linewidth=0.8, alpha=0.45)
    ax.set_xlabel("Offset from 76 MHz (kHz)")
    ax.set_ylabel("PSD (counts^2/Hz)")
    ax.set_title(
        f"Ch1-1 raw FFT near 76 MHz, +/-10 kHz window, bin spacing {bin_spacing_hz:.2f} Hz"
    )
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=7)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="High-resolution raw FFT for Data_1_1 interleaved channel 1 near 76 MHz."
    )
    parser.add_argument("--notes-csv", type=Path, default=DEFAULT_NOTES_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--center-hz", type=float, default=DEFAULT_CENTER_HZ)
    parser.add_argument("--half-width-hz", type=float, default=DEFAULT_HALF_WIDTH_HZ)
    parser.add_argument("--sample-rate-hz", type=float, default=DEFAULT_SAMPLE_RATE_HZ)
    parser.add_argument("--fft-length", type=int, default=DEFAULT_FFT_LENGTH)
    parser.add_argument("--max-frames-per-run", type=int, default=DEFAULT_MAX_FRAMES_PER_RUN)
    parser.add_argument(
        "--include-all-raw",
        action="store_true",
        help="Include every raw-backed measurement in the notes CSV, not only measurements with old high-frequency FFT files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    runs = read_runs(args.notes_csv, include_all_raw=args.include_all_raw)
    if not runs:
        raise SystemExit("No matching raw-backed measurements were found.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    results: list[SpectrumResult] = []
    for index, run in enumerate(runs, start=1):
        print(f"[{index}/{len(runs)}] Processing {run.run_name}", flush=True)
        result = compute_run_spectrum(
            run,
            sample_rate_hz=args.sample_rate_hz,
            fft_length=args.fft_length,
            center_hz=args.center_hz,
            half_width_hz=args.half_width_hz,
            max_frames_per_run=args.max_frames_per_run,
        )
        results.append(result)
        peak_offset = result.frequency_hz[result.peak_index] - args.center_hz
        print(
            f"  frames={result.frames_used}, bin={result.bin_spacing_hz:.2f} Hz, "
            f"peak_offset={peak_offset:.1f} Hz",
            flush=True,
        )

    suffix = "all_raw" if args.include_all_raw else "highfreq_runs"
    plot_path = args.output_dir / f"ch1_1_76mhz_pm10khz_raw_highres_{suffix}.png"
    spectrum_csv_path = args.output_dir / f"ch1_1_76mhz_pm10khz_raw_highres_spectrum_{suffix}.csv"
    summary_csv_path = args.output_dir / f"ch1_1_76mhz_pm10khz_raw_highres_summary_{suffix}.csv"

    save_plot(plot_path, results, center_hz=args.center_hz)
    save_spectrum_csv(spectrum_csv_path, results)
    save_summary_csv(summary_csv_path, results, fft_length=args.fft_length, center_hz=args.center_hz)
    print(f"Saved plot: {plot_path}")
    print(f"Saved spectrum CSV: {spectrum_csv_path}")
    print(f"Saved summary CSV: {summary_csv_path}")


if __name__ == "__main__":
    main()
