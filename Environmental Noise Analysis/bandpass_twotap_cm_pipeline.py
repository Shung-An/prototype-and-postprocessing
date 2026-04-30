"""
Build CM-pipeline input from raw two-board Data_*.dat files.

Processing order:
  1. Read two interleaved two-channel board files.
  2. Apply an FIR bandpass from Fs/32 to Fs/8 to each channel.
  3. Apply the GageStream-style two-tap demodulation:

         y[k] = x[k] - x[k + 8]

     inside each 16-frame demodulation segment.
  4. Average 8x8 cross products into one 64-value cm.bin frame per transfer.
  5. Optionally run the existing cm_pipeline_all_in_one.py on the generated folders.

Each output folder represents one cross-board channel pair.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from scipy.signal import firwin, lfilter


DEFAULT_DATA_DIR = Path(
    r"C:\Quantum Squeezing\Quantum-Measurement-Software"
    r"\Quantum Measurement UI\bin\Debug\net8.0-windows7.0"
)
DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parent / "bandpass_twotap_cm_runs"
DEFAULT_CM_PIPELINE = Path(
    r"C:\Quantum Squeezing\prototype and postprocessing"
    r"\post processing\cm_pipeline_all_in_one.py"
)
DEFAULT_FILES = ("Data_1.dat", "Data_2.dat")
DEFAULT_SAMPLE_RATE_HZ = 600_000_000.0
DEFAULT_TRANSFER_SAMPLES = 1_048_576
DEFAULT_PADDING_SAMPLES = 1_024
DEFAULT_FIR_TAPS = 513
ALL_CHANNEL_PAIRS = ((1, 1), (1, 2), (2, 1), (2, 2))
DEMODOULATION_WINDOW = 8
SEGMENT_FRAMES = DEMODOULATION_WINDOW * 2


@dataclass
class PairOutput:
    channel_a: int
    channel_b: int
    folder: Path
    cm_path: Path
    frames_written: int


def read_interleaved_i16(path: Path) -> np.memmap:
    byte_count = path.stat().st_size
    if byte_count % np.dtype("<i2").itemsize != 0:
        raise ValueError(f"{path} byte count is not divisible by int16 size.")
    sample_count = byte_count // np.dtype("<i2").itemsize
    if sample_count < 2 or sample_count % 2 != 0:
        raise ValueError(f"{path} does not contain an even number of int16 samples.")
    return np.memmap(path, dtype="<i2", mode="r").reshape((-1, 2))


def design_bandpass(sample_rate_hz: float, fir_taps: int) -> tuple[np.ndarray, float, float]:
    if fir_taps < 3 or fir_taps % 2 == 0:
        raise ValueError("--fir-taps must be an odd integer >= 3.")

    band_low_hz = sample_rate_hz / 32.0
    band_high_hz = sample_rate_hz / 8.0
    taps = firwin(
        fir_taps,
        [band_low_hz, band_high_hz],
        pass_zero=False,
        fs=sample_rate_hz,
        window="hamming",
    )
    return taps.astype(np.float64), band_low_hz, band_high_hz


def gage_twotap_cm_frame(
    filtered_a: np.ndarray,
    filtered_b: np.ndarray,
    channel_a: int,
    channel_b: int,
) -> np.ndarray:
    sig_a = filtered_a[:, channel_a - 1]
    sig_b = filtered_b[:, channel_b - 1]
    usable_frames = min(sig_a.size, sig_b.size)
    usable_frames = (usable_frames // SEGMENT_FRAMES) * SEGMENT_FRAMES
    if usable_frames < SEGMENT_FRAMES:
        raise ValueError("Not enough filtered frames to make one two-tap CM segment.")

    a_segments = sig_a[:usable_frames].reshape((-1, SEGMENT_FRAMES))
    b_segments = sig_b[:usable_frames].reshape((-1, SEGMENT_FRAMES))
    diff_a = a_segments[:, :DEMODOULATION_WINDOW] - a_segments[:, DEMODOULATION_WINDOW:]
    diff_b = b_segments[:, :DEMODOULATION_WINDOW] - b_segments[:, DEMODOULATION_WINDOW:]
    matrix = diff_a.T @ diff_b / diff_a.shape[0]
    return matrix.reshape(64).astype(np.float64)


def write_profile(run_folder: Path, n_frames: int) -> None:
    start = datetime.now().replace(microsecond=0)
    with (run_folder / "profile.txt").open("w", encoding="utf-8") as handle:
        for idx in range(n_frames):
            timestamp = (start + timedelta(seconds=idx * 67 / 4861)).strftime("%H:%M:%S.%f")[:-3]
            handle.write(f"frame {idx + 1} start timestamp: {timestamp}\n")


def write_sensitivity_log(run_folder: Path) -> None:
    # These values intentionally mark the run as dark-noise/V^2 in cm_pipeline display logic.
    text = "\n".join(
        [
            "P1 = 0 mW",
            "P2 = 0 mW",
            "Sensitivity = nan",
            "Shot Noise1 = nan",
            "Shot Noise2 = nan",
            "Signal Level = nan",
            "Conversion Factor = nan",
            "Shot Noise Result = 10001",
            "",
        ]
    )
    (run_folder / "sensitivity.log").write_text(text, encoding="utf-8")


def write_run_metadata(
    run_folder: Path,
    *,
    file_a: Path,
    file_b: Path,
    channel_a: int,
    channel_b: int,
    sample_rate_hz: float,
    band_low_hz: float,
    band_high_hz: float,
    fir_taps: int,
    transfer_samples: int,
    padding_samples: int,
    frames_written: int,
) -> None:
    metadata = {
        "GeneratedBy": "bandpass_twotap_cm_pipeline.py",
        "CreatedAt": datetime.now().isoformat(timespec="seconds"),
        "SourceFiles": [str(file_a), str(file_b)],
        "CrossBoardPair": {
            "FileA": file_a.name,
            "ChannelA": channel_a,
            "FileB": file_b.name,
            "ChannelB": channel_b,
        },
        "Processing": {
            "SampleRateHz": sample_rate_hz,
            "BandpassLowHz": band_low_hz,
            "BandpassHighHz": band_high_hz,
            "FirTaps": fir_taps,
            "TwoTapDelayFrames": DEMODOULATION_WINDOW,
            "DemodulationWindow": DEMODOULATION_WINDOW,
            "SegmentFrames": SEGMENT_FRAMES,
            "TransferSamplesPerBoard": transfer_samples,
            "PaddingSamplesSkippedPerTransfer": padding_samples,
            "CmFramesWritten": frames_written,
        },
    }
    (run_folder / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def append_fir_taps(output_root: Path, taps: np.ndarray) -> Path:
    path = output_root / "fir_bandpass_fs32_to_fs8_taps_used_for_cm.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["tap_index", "coefficient"])
        for idx, coefficient in enumerate(taps):
            writer.writerow([idx, coefficient])
    return path


def build_cm_runs(
    *,
    data_dir: Path,
    files: tuple[str, str],
    output_root: Path,
    channel_pairs: tuple[tuple[int, int], ...],
    sample_rate_hz: float,
    fir_taps: int,
    transfer_samples: int,
    padding_samples: int,
    max_transfers: int | None,
) -> list[PairOutput]:
    file_a = data_dir / files[0]
    file_b = data_dir / files[1]
    if not file_a.is_file():
        raise FileNotFoundError(file_a)
    if not file_b.is_file():
        raise FileNotFoundError(file_b)

    data_a = read_interleaved_i16(file_a)
    data_b = read_interleaved_i16(file_b)
    frames_per_transfer = transfer_samples // 2
    usable_samples_per_transfer = transfer_samples - padding_samples
    usable_frames_per_transfer = usable_samples_per_transfer // 2
    usable_frames_per_transfer = (usable_frames_per_transfer // SEGMENT_FRAMES) * SEGMENT_FRAMES

    if transfer_samples % 2 != 0 or usable_frames_per_transfer < SEGMENT_FRAMES:
        raise ValueError("Transfer/padding settings do not leave enough complete frames.")

    total_transfers = min(data_a.shape[0], data_b.shape[0]) // frames_per_transfer
    if max_transfers is not None:
        total_transfers = min(total_transfers, max_transfers)
    if total_transfers <= 0:
        raise ValueError("No complete transfers are available in the two data files.")

    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_root = output_root / f"fs32_fs8_twotap_{run_stamp}"
    output_root.mkdir(parents=True, exist_ok=True)

    taps, band_low_hz, band_high_hz = design_bandpass(sample_rate_hz, fir_taps)
    taps_path = append_fir_taps(output_root, taps)
    print(f"FIR taps written: {taps_path}", flush=True)
    print(
        f"Bandpass: {band_low_hz / 1e6:.6g} MHz to {band_high_hz / 1e6:.6g} MHz",
        flush=True,
    )

    outputs: list[PairOutput] = []
    handles = {}
    frame_counts = {pair: 0 for pair in channel_pairs}
    for channel_a, channel_b in channel_pairs:
        run_folder = output_root / f"Data_1_ch{channel_a}_x_Data_2_ch{channel_b}"
        run_folder.mkdir(parents=True, exist_ok=True)
        cm_path = run_folder / "cm.bin"
        handles[(channel_a, channel_b)] = cm_path.open("wb")
        outputs.append(PairOutput(channel_a, channel_b, run_folder, cm_path, 0))

    zi_a = np.zeros((2, taps.size - 1), dtype=np.float64)
    zi_b = np.zeros((2, taps.size - 1), dtype=np.float64)

    try:
        for transfer_idx in range(total_transfers):
            start = transfer_idx * frames_per_transfer
            stop = start + frames_per_transfer
            chunk_a = np.asarray(data_a[start:stop, :], dtype=np.float64)
            chunk_b = np.asarray(data_b[start:stop, :], dtype=np.float64)

            filtered_a = np.empty_like(chunk_a)
            filtered_b = np.empty_like(chunk_b)
            for channel_idx in range(2):
                filtered_a[:, channel_idx], zi_a[channel_idx] = lfilter(
                    taps, [1.0], chunk_a[:, channel_idx], zi=zi_a[channel_idx]
                )
                filtered_b[:, channel_idx], zi_b[channel_idx] = lfilter(
                    taps, [1.0], chunk_b[:, channel_idx], zi=zi_b[channel_idx]
                )

            filtered_a = filtered_a[:usable_frames_per_transfer, :]
            filtered_b = filtered_b[:usable_frames_per_transfer, :]

            for pair in channel_pairs:
                cm_frame = gage_twotap_cm_frame(filtered_a, filtered_b, pair[0], pair[1])
                cm_frame.tofile(handles[pair])
                frame_counts[pair] += 1

            if (transfer_idx + 1) % 25 == 0 or transfer_idx + 1 == total_transfers:
                print(f"Processed {transfer_idx + 1:,}/{total_transfers:,} transfers", flush=True)
    finally:
        for handle in handles.values():
            handle.close()

    finalized_outputs: list[PairOutput] = []
    for output in outputs:
        frames_written = frame_counts[(output.channel_a, output.channel_b)]
        write_profile(output.folder, frames_written)
        write_sensitivity_log(output.folder)
        write_run_metadata(
            output.folder,
            file_a=file_a,
            file_b=file_b,
            channel_a=output.channel_a,
            channel_b=output.channel_b,
            sample_rate_hz=sample_rate_hz,
            band_low_hz=band_low_hz,
            band_high_hz=band_high_hz,
            fir_taps=fir_taps,
            transfer_samples=transfer_samples,
            padding_samples=padding_samples,
            frames_written=frames_written,
        )
        finalized_outputs.append(
            PairOutput(output.channel_a, output.channel_b, output.folder, output.cm_path, frames_written)
        )

    return finalized_outputs


def run_cm_pipeline(outputs: list[PairOutput], cm_pipeline_path: Path, force: bool) -> None:
    command = ["python", str(cm_pipeline_path), *(str(output.folder) for output in outputs)]
    if force:
        command.append("--force")
    print("Running CM pipeline:", " ".join(command), flush=True)
    subprocess.run(command, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply Fs/32-Fs/8 FIR bandpass, Gage two-tap demodulation, and build cm.bin run folders."
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--files", nargs=2, default=list(DEFAULT_FILES))
    parser.add_argument(
        "--channels",
        nargs=2,
        type=int,
        default=None,
        help="Only build one pair, for example --channels 1 2. Defaults to all four cross-board pairs.",
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--sample-rate-hz", type=float, default=DEFAULT_SAMPLE_RATE_HZ)
    parser.add_argument("--fir-taps", type=int, default=DEFAULT_FIR_TAPS)
    parser.add_argument("--transfer-samples", type=int, default=DEFAULT_TRANSFER_SAMPLES)
    parser.add_argument("--padding-samples", type=int, default=DEFAULT_PADDING_SAMPLES)
    parser.add_argument(
        "--max-transfers",
        type=int,
        default=None,
        help="Limit transfer count for a quick test. Omit for the full data files.",
    )
    parser.add_argument("--run-cm-pipeline", action="store_true")
    parser.add_argument("--cm-pipeline", type=Path, default=DEFAULT_CM_PIPELINE)
    parser.add_argument("--force", action="store_true", help="Pass --force to cm_pipeline_all_in_one.py.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    channel_pairs = (tuple(args.channels),) if args.channels is not None else ALL_CHANNEL_PAIRS
    for channel_a, channel_b in channel_pairs:
        if channel_a not in (1, 2) or channel_b not in (1, 2):
            raise ValueError("Channels must be 1 or 2.")

    outputs = build_cm_runs(
        data_dir=args.data_dir,
        files=(args.files[0], args.files[1]),
        output_root=args.output_root,
        channel_pairs=channel_pairs,
        sample_rate_hz=args.sample_rate_hz,
        fir_taps=args.fir_taps,
        transfer_samples=args.transfer_samples,
        padding_samples=args.padding_samples,
        max_transfers=args.max_transfers,
    )

    print("\nGenerated CM run folders:", flush=True)
    for output in outputs:
        print(
            f"  Data_1 Ch{output.channel_a} x Data_2 Ch{output.channel_b}: "
            f"{output.folder} ({output.frames_written} cm frames)",
            flush=True,
        )

    if args.run_cm_pipeline:
        run_cm_pipeline(outputs, args.cm_pipeline, args.force)


if __name__ == "__main__":
    main()
