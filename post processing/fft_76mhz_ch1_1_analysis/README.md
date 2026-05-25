# Ch1-1 76 MHz FFT Analysis

This folder collects the focused FFT work for the `ch1-1` peak near 76 MHz. It was split out of the main post-processing folder so plots, CSVs, logs, and rerun scripts are easier to find.

## Folder Layout

- `raw_highres/`
  - Final high-resolution raw FFT outputs from `Data_1_1.bin`, interleaved channel 1.
  - Uses `FFT length = 4,194,304`, giving `144.958496094 Hz` bin spacing.
  - Main inspection window is `76 MHz +/- 10 kHz`.
- `existing_fft_reference/`
  - Older plots and CSVs made from the previously saved broad high-frequency FFT CSVs.
  - These are useful as a historical reference, but their bin spacing is only `9277.34375 Hz`.
- `scripts/`
  - Reproducible scripts for regenerating the raw high-resolution result and the selected comparison plots.
- `logs/`
  - Runtime logs from the latest high-resolution raw FFT run.

The shared measurement note index is still one folder up:

```text
../raw_backed_fft_measurement_notes.csv
```

## Current Recommended Plots

Use these first:

- `raw_highres/ch1_1_76mhz_pm10khz_raw_highres_selected_overlay.png`
  - Clean overlay with only one dark-noise reference, flint2, and OPO measurements.
- `raw_highres/ch1_1_76mhz_pm10khz_raw_highres_selected_peak_comparison.png`
  - Bar-plot comparison of peak height at the exact 76 MHz FFT bin.
- `raw_highres/ch1_1_76mhz_pm10khz_raw_highres_selected_summary.csv`
  - Compact CSV for the selected comparison set.
- `raw_highres/ch1_1_76mhz_pm10khz_raw_highres_selected_spectrum.csv`
  - Narrowband spectrum values for the selected comparison set.

## Selected Measurement Set

The clean comparison currently uses:

| Run | Meaning | PSD at 76 MHz | dB vs dark |
|---|---|---:|---:|
| `20260515_092941` | Dark noise reference | `5.311923e-05` | `0.00` |
| `20260515_133100` | Flint2 laser @1030 nm | `2.413202e+05` | `96.57` |
| `20260515_134951` | OPO single point @800 nm | `4.642831e+04` | `89.42` |
| `20260515_140509` | OPO scanning @800 nm | `4.615330e+04` | `89.39` |

All four selected measurements peak at the exact `76.000000 MHz` bin in the high-resolution raw FFT.

## Raw Data Interpretation

For this focused inspection:

- Measurement-level physical channels: `4`
- Selected raw file: `Data_1_1.bin`
- Selected interleaved channel inside that file: `1`
- Interpreted signal: `ch1-1`
- Sample rate: `608 MHz`
- FFT length: `4,194,304`
- Frequency bin spacing: `144.958496094 Hz`
- Averaging: up to `32` long FFT frames per run

The raw-backed measurements also include `Data_2_1.bin`. The current scripts intentionally inspect only `Data_1_1.bin` channel 1 because the immediate question was about `ch1-1`.

## Reproduce The Full Raw High-Resolution FFT

Run from anywhere:

```powershell
python "C:\Quantum Squeezing\prototype and postprocessing\post processing\fft_76mhz_ch1_1_analysis\scripts\ch1_1_highres_76mhz_raw_fft.py" --include-all-raw --max-frames-per-run 32
```

Outputs are written to:

```text
raw_highres/
```

The full run processes all raw-backed measurements listed in `../raw_backed_fft_measurement_notes.csv`.

## Reproduce The Selected Dark/Flint2/OPO Plots

After the full raw high-resolution FFT exists, run:

```powershell
python "C:\Quantum Squeezing\prototype and postprocessing\post processing\fft_76mhz_ch1_1_analysis\scripts\make_selected_76mhz_plots.py"
```

This regenerates:

- `raw_highres/ch1_1_76mhz_pm10khz_raw_highres_selected_overlay.png`
- `raw_highres/ch1_1_76mhz_pm10khz_raw_highres_selected_peak_comparison.png`
- `raw_highres/ch1_1_76mhz_pm10khz_raw_highres_selected_summary.csv`
- `raw_highres/ch1_1_76mhz_pm10khz_raw_highres_selected_spectrum.csv`

## When To Use The Older Reference Files

The `existing_fft_reference/` files came from already-saved high-frequency FFT CSVs. They are useful for quick historical checks, but they should not be used for careful peak inspection around 76 MHz because the frequency bin spacing is too coarse.

Use `raw_highres/` for the careful spectrum analysis.
