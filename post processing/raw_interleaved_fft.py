from __future__ import annotations

import argparse
import csv
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Literal

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


FftMode = Literal["low", "high"]
ProgressCallback = Callable[[int, str], None]

LOW_FREQUENCY_PLOT_NAME = "interleaved_fft_low_frequency_loglog.png"
LOW_FREQUENCY_CSV_NAME = "interleaved_fft_low_frequency_loglog.csv"
HIGH_FREQUENCY_PLOT_NAME = "interleaved_fft_high_frequency_semilog.png"
HIGH_FREQUENCY_CSV_NAME = "interleaved_fft_high_frequency_semilog.csv"
FFT_OUTPUT_DIR_NAME = "fft_analysis"
DEFAULT_SAMPLE_RATE_HZ = 608e6

MODE_METADATA: dict[FftMode, dict[str, str]] = {
    "low": {
        "key": "LowFrequencyNoise",
        "label": "Low frequency noise (log-log)",
        "plot": LOW_FREQUENCY_PLOT_NAME,
        "csv": LOW_FREQUENCY_CSV_NAME,
    },
    "high": {
        "key": "HighFrequencySpectrum",
        "label": "High frequency spectrum (semilog)",
        "plot": HIGH_FREQUENCY_PLOT_NAME,
        "csv": HIGH_FREQUENCY_CSV_NAME,
    },
}


@dataclass(frozen=True)
class FftAnalysisResult:
    run_folder: Path
    mode: FftMode
    plot_path: Path
    csv_path: Path
    fft_length: int
    sample_rate_hz: float
    interleaved_channels: int
    max_frames_per_file: int
    series_count: int


def analyze_run_folder(
    run_folder: Path | str,
    mode: FftMode,
    *,
    sample_rate_hz: float | None = None,
    interleaved_channels: int = 2,
    max_frames_per_file: int = 512,
    progress: ProgressCallback | None = None,
) -> FftAnalysisResult:
    run_folder = Path(run_folder).expanduser().resolve()
    if mode not in {"low", "high"}:
        raise ValueError("mode must be 'low' or 'high'.")
    if interleaved_channels < 1:
        raise ValueError("interleaved_channels must be at least 1.")

    progress = progress or (lambda percent, message: None)
    progress(2, "Locating raw Data_*.bin files")

    raw_files = sorted(
        path for path in run_folder.glob("Data_*.bin")
        if path.is_file() and path.stat().st_size >= interleaved_channels * np.dtype(np.int16).itemsize * 4096
    )
    if not raw_files:
        raise FileNotFoundError(f"No raw Data_*.bin files were found in {run_folder}")

    sample_rate_hz = sample_rate_hz or read_sample_rate_hz(run_folder)
    desired_fft_length = 262_144 if mode == "low" else 65_536
    fft_length = choose_fft_length(raw_files, desired_fft_length, interleaved_channels)
    frequency_hz = np.fft.rfftfreq(fft_length, d=1.0 / sample_rate_hz)

    progress(8, f"FFT length {fft_length}, sample rate {sample_rate_hz:g} Hz")
    spectra: list[tuple[str, np.ndarray]] = []
    total_files = len(raw_files)
    for file_index, raw_file in enumerate(raw_files, start=1):
        base = 8 + int((file_index - 1) / total_files * 72)
        progress(base, f"Processing {raw_file.name}")
        file_spectra = compute_file_spectra(
            raw_file,
            fft_length,
            interleaved_channels,
            sample_rate_hz,
            max_frames_per_file,
            lambda local_percent, message: progress(
                base + int(local_percent / 100 * (72 / total_files)),
                message,
            ),
        )
        spectra.extend(file_spectra)

    if not spectra:
        raise RuntimeError("The raw files did not contain enough complete FFT frames.")

    output_dir = run_folder / FFT_OUTPUT_DIR_NAME
    output_dir.mkdir(exist_ok=True)
    plot_name = LOW_FREQUENCY_PLOT_NAME if mode == "low" else HIGH_FREQUENCY_PLOT_NAME
    csv_name = LOW_FREQUENCY_CSV_NAME if mode == "low" else HIGH_FREQUENCY_CSV_NAME
    plot_path = output_dir / plot_name
    csv_path = output_dir / csv_name

    progress(84, "Saving FFT CSV")
    save_spectra_csv(csv_path, frequency_hz, spectra, mode)
    progress(90, "Saving FFT plot")
    save_spectra_plot(plot_path, frequency_hz, spectra, mode, fft_length, sample_rate_hz)

    result = FftAnalysisResult(
        run_folder=run_folder,
        mode=mode,
        plot_path=plot_path,
        csv_path=csv_path,
        fft_length=fft_length,
        sample_rate_hz=sample_rate_hz,
        interleaved_channels=interleaved_channels,
        max_frames_per_file=max_frames_per_file,
        series_count=len(spectra),
    )
    update_metadata(result)
    progress(100, f"Saved {plot_path.name}")
    return result


def compute_file_spectra(
    raw_file: Path,
    fft_length: int,
    interleaved_channels: int,
    sample_rate_hz: float,
    max_frames_per_file: int,
    progress: ProgressCallback,
) -> list[tuple[str, np.ndarray]]:
    frame_samples = fft_length * interleaved_channels
    frame_bytes = frame_samples * np.dtype(np.int16).itemsize
    total_frames = raw_file.stat().st_size // frame_bytes
    if total_frames <= 0:
        return []

    frames_to_use = min(total_frames, max_frames_per_file)
    frame_step = max(1, total_frames // frames_to_use)
    window = np.hanning(fft_length)
    window_power = float(np.sum(window * window))
    accumulated = [np.zeros(fft_length // 2 + 1, dtype=np.float64) for _ in range(interleaved_channels)]
    frames_processed = 0

    with raw_file.open("rb") as handle:
        for frame_number in range(frames_to_use):
            frame_index = min(frame_number * frame_step, total_frames - 1)
            handle.seek(frame_index * frame_bytes)
            data = np.frombuffer(handle.read(frame_bytes), dtype=np.int16, count=frame_samples)
            if data.size != frame_samples:
                continue

            reshaped = data.reshape(fft_length, interleaved_channels).astype(np.float64, copy=False)
            for channel in range(interleaved_channels):
                samples = reshaped[:, channel]
                samples = (samples - float(np.mean(samples))) * window
                fft_values = np.fft.rfft(samples)
                psd = (np.abs(fft_values) ** 2) / (sample_rate_hz * window_power)
                if psd.size > 2:
                    psd[1:-1] *= 2.0
                accumulated[channel] += psd

            frames_processed += 1
            if frame_number == 0 or (frame_number + 1) % 16 == 0 or frame_number + 1 == frames_to_use:
                percent = int((frame_number + 1) / frames_to_use * 100)
                progress(percent, f"Processing {raw_file.name}: {frame_number + 1}/{frames_to_use} FFT frames")

    if frames_processed == 0:
        return []

    spectra = []
    file_stem = raw_file.stem
    for channel, psd in enumerate(accumulated, start=1):
        averaged = np.maximum(psd / frames_processed, 1e-30)
        spectra.append((f"{file_stem} interleaved ch{channel}", averaged))
    return spectra


def save_spectra_csv(csv_path: Path, frequency_hz: np.ndarray, spectra: list[tuple[str, np.ndarray]], mode: FftMode) -> None:
    min_frequency_hz, max_frequency_hz = frequency_bounds(mode, float(frequency_hz[-1]))
    mask = (frequency_hz >= min_frequency_hz) & (frequency_hz <= max_frequency_hz)
    indexes = np.flatnonzero(mask)
    indexes = indexes[indexes > 0]

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Frequency_Hz", *[name for name, _ in spectra]])
        for index in indexes:
            writer.writerow([f"{frequency_hz[index]:.17g}", *[f"{psd[index]:.17g}" for _, psd in spectra]])


def save_spectra_plot(
    plot_path: Path,
    frequency_hz: np.ndarray,
    spectra: list[tuple[str, np.ndarray]],
    mode: FftMode,
    fft_length: int,
    sample_rate_hz: float,
) -> None:
    min_frequency_hz, max_frequency_hz = frequency_bounds(mode, float(frequency_hz[-1]))
    mask = (frequency_hz >= min_frequency_hz) & (frequency_hz <= max_frequency_hz)
    mask[0] = False
    bin_width_hz = sample_rate_hz / fft_length

    fig, ax = plt.subplots(figsize=(14, 8), dpi=160)
    for name, psd in spectra:
        x = frequency_hz[mask]
        y = np.maximum(psd[mask], 1e-30)
        if mode == "low":
            ax.loglog(x, y, linewidth=1.1, label=name)
        else:
            ax.semilogy(x / 1e6, y, linewidth=1.1, label=name)

    if mode == "low":
        ax.set_xlabel("Frequency (Hz)")
        ax.set_title(f"Low Frequency Noise - raw interleaved FFT, bin width {bin_width_hz:.1f} Hz")
    else:
        ax.set_xlabel("Frequency (MHz)")
        ax.set_title(f"High Frequency Spectrum - raw interleaved FFT, bin width {bin_width_hz:.1f} Hz")
    ax.set_ylabel("PSD (counts^2/Hz)")
    ax.grid(True, which="both", alpha=0.28)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(plot_path)
    plt.close(fig)


def frequency_bounds(mode: FftMode, nyquist_hz: float) -> tuple[float, float]:
    if mode == "low":
        return 1e3, nyquist_hz
    return min(1e6, nyquist_hz), nyquist_hz


def choose_fft_length(raw_files: list[Path], desired_fft_length: int, interleaved_channels: int) -> int:
    bytes_per_sample = np.dtype(np.int16).itemsize
    max_per_channel_samples = max(path.stat().st_size // (bytes_per_sample * interleaved_channels) for path in raw_files)
    fft_length = desired_fft_length
    while fft_length > 4096 and max_per_channel_samples < fft_length:
        fft_length //= 2
    if max_per_channel_samples < fft_length:
        raise RuntimeError("Raw files do not contain enough samples for a 4096-point FFT.")
    return fft_length


def read_sample_rate_hz(run_folder: Path) -> float:
    return DEFAULT_SAMPLE_RATE_HZ


def nested_value(payload: object, path: tuple[str, ...]) -> object:
    current = payload
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def safe_float(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def update_metadata(result: FftAnalysisResult) -> None:
    sync_fft_metadata_for_run(result.run_folder, latest_result=result)


def sync_fft_metadata_for_run(
    run_folder: Path | str,
    *,
    latest_result: FftAnalysisResult | None = None,
    provider: str = "Existing FFT analysis files",
) -> bool:
    run_folder = Path(run_folder).expanduser().resolve()
    metadata_path = run_folder / "metadata.json"
    if metadata_path.is_file():
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                payload = {}
        except Exception:
            payload = {}
    else:
        payload = {}

    modes = discover_fft_metadata_modes(run_folder, provider=provider)
    if latest_result is not None:
        modes[MODE_METADATA[latest_result.mode]["key"]] = build_fft_mode_metadata(
            latest_result.mode,
            latest_result.plot_path,
            latest_result.csv_path,
            fft_length=latest_result.fft_length,
            sample_rate_hz=latest_result.sample_rate_hz,
            max_frames_per_file=latest_result.max_frames_per_file,
            series_count=latest_result.series_count,
        )

    if not modes:
        return False

    configuration = payload.get("Configuration")
    if not isinstance(configuration, dict):
        configuration = {}
        payload["Configuration"] = configuration

    newest_mode = None
    if latest_result is not None:
        newest_mode = modes.get(MODE_METADATA[latest_result.mode]["key"])
    if newest_mode is None:
        newest_mode = next(iter(modes.values()))

    physical_channels = max(
        (
            int(channel.get("ChannelIndex", 0))
            for mode_payload in modes.values()
            for channel in mode_payload.get("Channels", [])
            if isinstance(channel, dict)
        ),
        default=0,
    )
    interleaved_channels = (
        latest_result.interleaved_channels
        if latest_result is not None
        else infer_interleaved_channel_count(modes)
    )

    configuration.update(
        {
            "FFTEnabled": True,
            "FFTProvider": newest_mode.get("Provider", provider),
            "FFTAnalysisApplied": True,
            "FFTAnalysisMode": newest_mode.get("Mode", ""),
            "FFTRawDataLayout": "Int16 raw samples interleaved by channel",
            "FFTOutputPng": newest_mode.get("OutputPng", ""),
            "FFTOutputCsv": newest_mode.get("OutputCsv", ""),
        }
    )

    payload["FFTAnalysis"] = {
        "Enabled": True,
        "Applied": True,
        "Provider": newest_mode.get("Provider", provider),
        "InputData": "Raw interleaved Data_*.bin files from the measurement folder",
        "Mode": newest_mode.get("Mode", ""),
        "RawDataLayout": "Int16 raw samples interleaved by channel",
        "InterleavedChannels": interleaved_channels or None,
        "PhysicalChannels": physical_channels or None,
        "SampleRateHz": newest_mode.get("SampleRateHz"),
        "FftLength": newest_mode.get("FftLength"),
        "MaxFramesPerFile": newest_mode.get("MaxFramesPerFile"),
        "SeriesCount": newest_mode.get("SeriesCount"),
        "OutputPng": newest_mode.get("OutputPng", ""),
        "OutputCsv": newest_mode.get("OutputCsv", ""),
        "DescriptionLabel": safe_metadata_text(payload.get("Description")),
        "Modes": modes,
        "AvailableModes": list(modes.keys()),
        "LastSyncedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return True


def infer_interleaved_channel_count(modes: dict[str, dict[str, object]]) -> int:
    highest = 0
    for mode_payload in modes.values():
        channels = mode_payload.get("Channels", [])
        if not isinstance(channels, list):
            continue
        for channel in channels:
            if not isinstance(channel, dict):
                continue
            series_name = str(channel.get("SeriesName") or "")
            match = re.search(r"\bch(?:annel)?\s*(\d+)\b", series_name, flags=re.IGNORECASE)
            if match:
                highest = max(highest, int(match.group(1)))
    return highest


def discover_fft_metadata_modes(run_folder: Path, *, provider: str = "Existing FFT analysis files") -> dict[str, dict[str, object]]:
    modes: dict[str, dict[str, object]] = {}
    for mode, details in MODE_METADATA.items():
        plot_path = run_folder / FFT_OUTPUT_DIR_NAME / details["plot"]
        csv_path = run_folder / FFT_OUTPUT_DIR_NAME / details["csv"]
        if csv_path.exists():
            modes[details["key"]] = build_fft_mode_metadata(mode, plot_path, csv_path, provider=provider)
    return modes


def build_fft_mode_metadata(
    mode: FftMode,
    plot_path: Path,
    csv_path: Path,
    *,
    fft_length: int | None = None,
    sample_rate_hz: float | None = None,
    max_frames_per_file: int | None = None,
    series_count: int | None = None,
    provider: str = "DataFiles Browser Python",
) -> dict[str, object]:
    details = MODE_METADATA[mode]
    channels = read_fft_csv_channels(csv_path)
    return {
        "Mode": details["label"],
        "ModeKey": details["key"],
        "Provider": provider,
        "OutputPng": str(plot_path) if plot_path.exists() else "",
        "OutputCsv": str(csv_path),
        "FftLength": fft_length,
        "SampleRateHz": sample_rate_hz,
        "MaxFramesPerFile": max_frames_per_file,
        "SeriesCount": series_count if series_count is not None else len(channels),
        "Channels": channels,
        "AppliedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def read_fft_csv_channels(csv_path: Path) -> list[dict[str, object]]:
    if not csv_path.exists():
        return []
    try:
        with csv_path.open("r", newline="", encoding="utf-8") as handle:
            header = next(csv.reader(handle))
    except Exception:
        return []
    channels = []
    for series_name in header[1:]:
        channel_index = infer_physical_channel_index(series_name)
        channels.append(
            {
                "ChannelIndex": channel_index,
                "ChannelLabel": f"Ch{channel_index}" if channel_index else "Ch?",
                "SeriesName": series_name,
            }
        )
    return channels


def infer_physical_channel_index(series_name: str) -> int:
    data_match = re.search(r"\bData_(\d+)(?:_\d+)?\b", series_name, flags=re.IGNORECASE)
    channel_match = re.search(r"\bch(?:annel)?\s*(\d+)\b", series_name, flags=re.IGNORECASE)
    if not channel_match:
        return 0
    interleaved_channel = int(channel_match.group(1))
    if data_match:
        data_index = int(data_match.group(1))
        if data_index in {1, 2} and interleaved_channel in {1, 2}:
            return (data_index - 1) * 2 + interleaved_channel
    return interleaved_channel


def safe_metadata_text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FFT analysis on raw interleaved Data_*.bin files.")
    parser.add_argument("run_folder", type=Path)
    parser.add_argument("--mode", choices=["low", "high"], default="low")
    parser.add_argument("--sample-rate-hz", type=float, default=None)
    parser.add_argument("--interleaved-channels", type=int, default=2)
    parser.add_argument("--max-frames-per-file", type=int, default=512)
    args = parser.parse_args()

    def print_progress(percent: int, message: str) -> None:
        print(f"PROGRESS {percent} {message}", flush=True)

    result = analyze_run_folder(
        args.run_folder,
        args.mode,
        sample_rate_hz=args.sample_rate_hz,
        interleaved_channels=args.interleaved_channels,
        max_frames_per_file=args.max_frames_per_file,
        progress=print_progress,
    )
    print(f"Saved plot: {result.plot_path}")
    print(f"Saved data: {result.csv_path}")


if __name__ == "__main__":
    main()
