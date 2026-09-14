# `cm_pipeline_all_in_one.py` Instructions

This guide explains how to run [`cm_pipeline_all_in_one.py`](./cm_pipeline_all_in_one.py), what files it expects, and what it writes. The script processes one or more correlation-matrix measurement folders, produces plots and tables, and updates each run's `metadata.json`.

> **Important:** output files are written directly into each run folder. Existing files with the same names are replaced. The script also updates `metadata.json`, so keep a backup of irreplaceable measurements and metadata.

## 1. Requirements

- Python 3.10 or newer
- `numpy`
- `matplotlib`
- `imageio`
- `imageio-ffmpeg` for `signal_emergence.mp4`
- A Python installation with Tk support (`tkinter`)

From the `post processing` directory, create a virtual environment and install the packages.

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install numpy matplotlib imageio imageio-ffmpeg
```

### macOS or Linux

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install numpy matplotlib imageio imageio-ffmpeg
```

The script imports `tkinter` at startup. Windows and macOS Python installations commonly include it. On Linux, install the operating system's Tk package separately if `import tkinter` fails (for example, `python3-tk` on Debian or Ubuntu). The graphical picker itself is used only when no run-folder argument is supplied.

## 2. Expected Run Folder

Pass the folder that directly contains `cm.bin`, not the parent `DataFiles` directory.

```text
20260508_120000/
|-- cm.bin                         required
|-- profile.txt                    optional, recommended
|-- delay_stage_positions.log      optional
|-- delay_stage_positions.csv      optional alternative
|-- sensitivity.log                optional, recommended
|-- metadata.json                  optional, recommended
`-- dropped_window.log             used only when its source-code gate is enabled
```

### `cm.bin` — required

The file is read as a flat sequence of NumPy `float64` values. Every consecutive 64 values form one correlation-matrix frame. The total number of values must therefore be divisible by 64.

### `profile.txt` — optional

The script looks for entries in this form:

```text
start timestamp: 14:32:08.123456
```

Times may use `HH:MM:SS` or `HH:MM:SS.ffffff`. If the file or timestamps are missing, the script generates a time axis using `67 / 4861` seconds per frame.

### Delay-stage position log — optional

The script uses the first file it finds in this order:

1. `delay_stage_positions.log`
2. `delay_stage_positions.csv`

Each usable row must contain at least a time and a position separated by a comma or semicolon. The first field is interpreted as `HH:MM:SS[.ffffff]`, and the last field is interpreted as the position in millimeters. For example:

```text
14:32:08.123456, 25.058
14:32:08.223456, 25.158
```

Positions are interpolated onto the correlation-matrix frame times and rounded into 0.1 mm bins. If no position file exists, all frames are assigned to 25.058 mm, producing a zero-range result.

### `sensitivity.log` — optional, recommended

When present, the script reads values with labels such as:

```text
P1 = 1.0 mW
P2 = 1.0 mW
Sensitivity = 1.23E-6
Shot Noise1 = 2.34E-6
Shot Noise2 = 2.45E-6
Signal Level = 3.21E-9
Conversion Factor = 4.56E-8
Shot Noise Result = 7.89E-6
```

Missing values become undefined (`NaN`) and can change whether results are displayed in `V^2` or converted to `urad^2`.

### `metadata.json` — optional, recommended

The pipeline reads metadata, preserves fields it does not own, and updates derived values under `PhysicsData` and `PostProcessing`. In particular, it consumes these attenuator fields:

```text
PhysicsData.PowerDetectorAttenuatorApplied
PhysicsData.PowerDetectorAttenuatorTotal_dB
PhysicsData.PowerDetectorAttenuatorCorrectionFactor
```

It uses `PowerDetectorAttenuatorCorrectionFactor` directly as an amplitude correction when the attenuator is marked as applied. It does not calculate that correction from `sensitivity.log`.

The pipeline also reads a scan velocity from common metadata names, preferring `PhysicsData.ScanVelocity_mm_s`. If it is missing and a position log is available, the script estimates the scan velocity.

Keep `metadata.json` valid JSON. If the file cannot be parsed, the script treats it as empty metadata and replaces it with newly generated content.

#### Dark Noise tag behavior

If top-level `Tags` contains `Dark Noise`, the script treats the run specially. It assigns an estimated 0.01 mW to each detector port and searches sibling run folders for the nearest non-dark measurement with a valid conversion factor. If it cannot find one, it uses the script's synthetic conversion-factor estimate. The chosen method is recorded in `metadata.json`.

## 3. Run the Pipeline

Run commands from the `post processing` directory. The examples below use Windows PowerShell; replace the Python executable with `./.venv/bin/python` on macOS or Linux.

### Process one run

```powershell
.\.venv\Scripts\python.exe .\cm_pipeline_all_in_one.py "D:\Quantum Squeezing\DataFiles\20260508_120000"
```

### Process several runs in sequence

```powershell
.\.venv\Scripts\python.exe .\cm_pipeline_all_in_one.py `
  "D:\Quantum Squeezing\DataFiles\20260508_120000" `
  "D:\Quantum Squeezing\DataFiles\20260508_121500"
```

### Select a folder interactively

```powershell
.\.venv\Scripts\python.exe .\cm_pipeline_all_in_one.py
```

Running without a folder opens a directory picker. Change `DATAFILES_DEFAULT_DIR` near the top of the script if you want the picker to start somewhere else.

### Force a complete rebuild

```powershell
.\.venv\Scripts\python.exe .\cm_pipeline_all_in_one.py "D:\path\to\run" --force
```

Without `--force`, the pipeline skips a run when its cache signature matches and all required outputs are newer than the tracked input files. Use `--force` after editing metadata that affects scaling or interpretation, including attenuator, detector, or dark-noise metadata.

## 4. Review Raw Matrix Frames

Use the review options to export individual raw 8 x 8 matrices, statistics, JSON data, and a contact sheet.

### Review the first 25 frames and continue processing

```powershell
.\.venv\Scripts\python.exe .\cm_pipeline_all_in_one.py "D:\path\to\run" --review-first-n 25
```

### Review 25 frames starting at zero-based frame index 100

```powershell
.\.venv\Scripts\python.exe .\cm_pipeline_all_in_one.py "D:\path\to\run" `
  --review-start-idx 100 --review-first-n 25
```

### Export review files without running the remaining analysis

```powershell
.\.venv\Scripts\python.exe .\cm_pipeline_all_in_one.py "D:\path\to\run" `
  --review-start-idx 100 --review-first-n 25 --review-only
```

`--review-only` must be combined with a positive `--review-first-n` value. Review output is placed in a folder such as:

```text
raw_matrix_review_0100_0124/
|-- frame_review_index.csv
|-- raw_matrices.json
|-- raw_matrix_contact_sheet.png
`-- frames/
    |-- frame_0100.png
    `-- ...
```

## 5. Command-Line Reference

```text
run_folders                 Zero or more folders that directly contain cm.bin
--force                     Rebuild even when cached outputs are current
--review-first-n N          Export N raw frames for review
--review-start-idx INDEX    Start review at this zero-based frame index
--review-only               Stop after the review export; requires N greater than 0
-h, --help                  Show the built-in command help
```

To display the current built-in help:

```powershell
.\.venv\Scripts\python.exe .\cm_pipeline_all_in_one.py --help
```

## 6. What the Pipeline Does

At a high level, the script:

1. Reads `cm.bin` as 64-channel frames and constructs the time axis.
2. Saves raw frame standard-deviation statistics and its FFT.
3. Applies the detector-area scale and the metadata attenuator correction.
4. Aligns delay-stage positions to frame times and groups them into 0.1 mm bins.
5. Evaluates the fixed candidate channel-pair list.
6. Ranks up to nine critical pairs by the mean frame-to-frame MSE of their two channels.
7. Produces final pair curves, convergence plots, heatmaps, tables, and an optional MP4.
8. Updates `metadata.json` and attempts to refresh the local Data Browser index.

For this setup, delay-stage position is converted to time using 6.6 ps/mm.

## 7. Main Outputs

All normal outputs are saved in the run folder.

| Output | Purpose |
| --- | --- |
| `metadata.json` | Original metadata plus derived `PhysicsData` values, cache signature, and processing time |
| `raw_std_analysis.csv` | Raw standard deviation for every frame |
| `raw_std_over_time.png` | Raw standard deviation versus integrated time |
| `raw_std_fft_spectrum.csv` | FFT spectrum of the mean-removed raw standard deviation |
| `raw_std_fft_spectrum.png` | Plot of the raw-standard-deviation FFT |
| `final_amplitudes_all_pairs.csv` | Delay and final amplitude for every candidate pair |
| `final_result_ALL_PAIRS.png` | All candidate-pair curves |
| `critical_pairs_summary.csv` | Critical-pair ranking and MSE details |
| `final_clean_result.png` | Selected critical-pair summary |
| `loglog_eval.png` | Running-mean convergence for critical pairs |
| `matrix_pattern_heatmaps.png` | Mean, MSE, converted mean, and diagonal-offset heatmaps |
| `combined_heatmap_V2.png` | Mean and MSE heatmaps in detector units |
| `heatmap_mean_urad2.png` | Mean correlation matrix converted to `urad^2` |
| `diagonal_offset_matrix_V2.png` | Diagonal tail-offset matrix in `V^2` |
| `diagonal_offset_matrix_urad2.png` | Diagonal tail-offset matrix converted to `urad^2` |
| `frames_per_position.csv` | Number of frames in each position bin |
| `frames_per_position_hist.png` | Position-bin frame-count plot |
| `hist_ch11_amplitude_V2.png` | Channel (1,1) amplitude histogram |
| `semilogy_grouped_64channels_*.png` | Running means for all 64 channels |
| `loglog_eval_pairs_runmean_*_group_*.png` | Grouped pair running-mean plots |
| `loglog_convergence_group*.png` | Per-pair convergence at each delay bin |
| `signal_emergence.mp4` | Evolution of critical-pair curves as integration grows |

The MP4 is skipped with a warning if `imageio` is unavailable or the data does not contain enough frames per bin. Installing `imageio-ffmpeg` supplies the usual MP4 backend.

## 8. Cache and Reprocessing

The pipeline skips normal processing only when both conditions are true:

- `metadata.json` contains the current pipeline cache signature.
- Every required output exists and is at least as new as the tracked input files.

The tracked inputs are `cm.bin`, `profile.txt`, `sensitivity.log`, the selected delay-stage position file, and `dropped_window.log` when dropped-window gating is enabled.

Because `metadata.json` itself is not a tracked timestamp input, use `--force` after changing metadata that should affect the numerical results.

Providing `--review-first-n` also bypasses the normal cache skip so that review assets can be regenerated.

## 9. Advanced Source-Code Settings

The following switches are constants near the top of the script; they are not command-line options. Their current defaults are all `False`.

| Setting | Effect when enabled |
| --- | --- |
| `ENABLE_DROPPED_WINDOW_GATING` | Removes time ranges listed in `dropped_window.log` |
| `ENABLE_SATURATION_CLEANUP` | Removes frames whose channel (1,1) exceeds the saturation threshold |
| `ENABLE_VARIANCE_GATING` | Keeps the configured raw-standard-deviation state |
| `ENABLE_CHANNEL_HEALTH_GATING` | Excludes pairs containing channels with high kurtosis |
| `ENABLE_EVEN_FRAMES_ONLY` | Processes every second frame, beginning with frame zero |
| `ENABLE_FFT_ANALYSIS` | Adds `variation_vs_time.png` and `fft_spectrum.png` |

Other important constants include `BIN_MM`, `MM_TO_PS`, `FRAME_DT_S`, `SATURATION_THRESHOLD_CH11`, and `DATAFILES_DEFAULT_DIR`. After changing settings, run with `--force` if you want to rebuild existing results immediately.

## 10. Troubleshooting

### `cm.bin not found.`

You passed the wrong directory level. Pass the individual run folder that directly contains `cm.bin`.

### `cm.bin does not contain a whole number of 64-wide frames.`

The binary file is truncated, uses a different numeric type, or is not a correlation-matrix file in the expected format. Confirm that it consists of `float64` data with 64 values per frame.

### `Could not parse any positions`

Check that the position file uses commas or semicolons, its first field is `HH:MM:SS` or `HH:MM:SS.ffffff`, and its final field is a numeric position in millimeters.

### The results did not change after editing metadata

Run again with `--force`. Metadata changes alone do not invalidate the timestamp-based cache.

### `signal_emergence.mp4` is missing

Install both `imageio` and `imageio-ffmpeg`. The movie is also intentionally skipped when no finite delays are available or fewer than two frames are shared by every position bin.

### The folder picker does not open

Pass the run folder directly on the command line, or install/repair Tk support for your Python installation.

### Processing is slow or uses substantial memory

The pipeline loads the complete `cm.bin` file and creates many high-resolution plots. Large acquisitions and MP4 generation can therefore take time and memory. Process fewer run folders at once when system resources are limited.
