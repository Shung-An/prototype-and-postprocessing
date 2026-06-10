# Ch1-1 76 MHz FFT Analysis

This folder collects the focused FFT work for the `ch1-1` peak near 76 MHz. It was split out of the main post-processing folder so plots, CSVs, logs, and rerun scripts are easier to find.

## Analysis Browser

Open this file first when you want to navigate the FFT results:

```text
index.html
```

It links the current plots, CSV summaries, older reference files, scripts, logs, and the shared measurement notes. It also has a local search box for quick lookup by run, measurement type, or file purpose.

## Folder Layout

- `raw_highres/`
  - Final high-resolution raw FFT outputs from `Data_1_1.bin`, interleaved channel 1.
  - Uses `FFT length = 4,194,304`, giving `144.958496094 Hz` bin spacing.
  - Main inspection windows are `76 MHz +/- 10 kHz`, `76 MHz +/- 100 kHz`, and DC-to-`100 kHz` offset from the carrier.
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

- `index.html`
  - Local browser page that links all current FFT analysis files.
- `raw_highres/ch1_1_76mhz_pm10khz_raw_highres_selected_db_with_2tap_fir.png`
  - Selected FFT result converted to dB, with the 2-tap FIR rejection curve overlaid.
- `raw_highres/ch1_1_76mhz_pm100khz_raw_highres_selected_db_with_2tap_fir.png`
  - Wider selected FFT result over `76 MHz +/- 100 kHz`, also in dB with the 2-tap FIR rejection curve.
- `raw_highres/ch1_1_76mhz_pm100khz_raw_highres_selected_after_2tap_fir_db.png`
  - Estimated residual spectrum after applying the 2-tap FIR response to the selected `+/-100 kHz` spectra.
- `raw_highres/pending_20260526/ch1_1_76mhz_pm100khz_raw_highres_selected_db_with_2tap_fir.png`
  - Pending May 26 raw-backed runs centered at `76 MHz`, `+/-100 kHz`, with the 2-tap FIR rejection curve.
- `raw_highres/pending_20260526/ch1_1_76mhz_pm100khz_raw_highres_selected_after_2tap_fir_db.png`
  - Pending May 26 runs after the 2-tap FIR estimate.
- `raw_highres/ab_test_76mhz_pm25khz/ab_test_76mhz_pm25khz_raw_db_vs_dark.png`
  - Focused AB comparison for dark noise, Flint2-only, OPO/highpass `780 nm`, OPO `1560 nm` auto/manual, and OPO `1600 nm` manual runs.
- `raw_highres/ab_test_76mhz_pm25khz/ab_test_76mhz_dc_to_25khz_positive_offset_raw_db_vs_dark.png`
  - DC-to-`25 kHz` positive-offset view from the 76 MHz carrier, in dB relative to dark.
- `raw_highres/ab_test_76mhz_pm25khz/ab_test_76mhz_pm25khz_after_2tap_fir_db.png`
  - Same focused AB set after the ideal 8-sample 2-tap FIR estimate.
- `raw_highres/offset_800khz/ch1_1_76mhz_offset800khz_pm100khz_selected_raw_db.png`
  - Selected raw-backed comparison centered at `+800 kHz` from the 76 MHz carrier, with a `+/-100 kHz` window.
- `raw_highres/offset_800khz/ch1_1_76mhz_offset800khz_pm100khz_selected_after_2tap_fir_db.png`
  - Same `+800 kHz` offset window after the 2-tap FIR estimate.
- `raw_highres/full_spectrum/ch1_1_full_spectrum_selected_semilogy.png`
  - Full selected raw spectrum from `0` to `304 MHz`, with PSD on a log axis.
- `raw_highres/full_spectrum/ch1_1_full_spectrum_selected_loglog.png`
  - Full selected raw spectrum in a log-log, log-binned view.
- `raw_highres/ch1_1_76mhz_pm10khz_raw_highres_selected_overlay.png`
  - Clean overlay with only one dark-noise reference, flint2, and OPO measurements.
- `raw_highres/ch1_1_76mhz_pm10khz_raw_highres_selected_peak_comparison.png`
  - Bar-plot comparison of peak height at the exact 76 MHz FFT bin.
- `raw_highres/ch1_1_76mhz_pm10khz_raw_highres_selected_summary.csv`
  - Compact CSV for the selected comparison set.
- `raw_highres/ch1_1_76mhz_pm10khz_raw_highres_selected_spectrum.csv`
  - Narrowband spectrum values for the selected comparison set.

## Newly Added Measurement Notes

Raw-backed measurements are now indexed as FFT-analysis-capable even when they only have `Data_*.bin` files and no canned FFT plot yet. These appear with the mode `raw_fft_candidate`, so they can be found later for customized FFT analysis.

Six raw-backed highpass-filter measurements from `2026-05-26` are in the shared measurement note index. The pending PSD pair already analyzed here is `20260526_141535` and `20260526_142458`; the `1600 nm` pair should also be treated as FFT-analysis candidates.

| Run | Meaning | Key reminder |
|---|---|---|
| `20260526_162112` | Vacuum highpass filter without SHG, manual | `1600 nm`, PDB230C/InGaAs, scan `0.1 mm/s`, motor1 `159`, motor2 `-656`, shot noise `0.79 urad^2/rtHz`, raw-backed `16.38 GB`, mode `raw_fft_candidate` |
| `20260526_150209` | Vacuum highpass filter without SHG, manual mode | `1600 nm`, PDB230C/InGaAs, scan `0.1 mm/s`, motor1 `-162`, motor2 `-282`, shot noise `1.12 urad^2/rtHz`, raw-backed `16.38 GB`, modes `low_frequency`, `raw_fft_candidate` |
| `20260526_142458` | Vacuum highpass filter without SHG, manual mode | `1560 nm`, PDB230C/InGaAs, scan `0.1 mm/s`, motor1 `146`, motor2 `-53`, shot noise `1.16 urad^2/rtHz`, raw-backed `16.38 GB` |
| `20260526_141535` | Vacuum highpass filter without SHG, automatic mode | `1560 nm`, PDB230C/InGaAs, scan `0.1 mm/s`, motor1 `96`, motor2 `-7`, shot noise `1.11 urad^2/rtHz`, raw-backed `16.31 GB` |
| `20260526_143329` | Vacuum highpass filter without SHG, manual mode | `1560 nm`, PDB230C/InGaAs, scan `0.1 mm/s`, motor1 `-106`, motor2 `-221`, shot noise `1.12 urad^2/rtHz`, raw-backed `16.38 GB` |
| `20260526_143004` | Vacuum highpass filter without SHG, manual mode | `1560 nm`, PDB230C/InGaAs, scan `0.1 mm/s`, motor1 `202`, motor2 `-149`, shot noise `1.20 urad^2/rtHz`, raw-backed `7.50 GB` |

## Pending May 26 PSD Analysis

The pending raw-backed pair was analyzed with the same high-resolution PSD method as the main `ch1-1` result:

- Center frequency: `76 MHz`
- Window: `+/-100 kHz`
- FFT length: `4,194,304`
- Bin spacing: `144.958496094 Hz`
- Frames averaged: `32`
- Data source: `Data_1_1.bin`, interleaved channel `1`

| Run | Mode | PSD at 76 MHz | dB vs dark | Max after 2-tap FIR |
|---|---|---:|---:|---:|
| `20260526_141535` | highpass without SHG, automatic | `7.834831e+04` | `91.69 dB` | `-61.53 dB` |
| `20260526_142458` | highpass without SHG, manual | `1.804791e+04` | `85.31 dB` | `-67.90 dB` |

Generated pending-run files:

- `raw_highres/pending_20260526/ch1_1_76mhz_pm100khz_raw_highres_selected_db_with_2tap_fir.png`
- `raw_highres/pending_20260526/ch1_1_76mhz_pm100khz_raw_highres_selected_after_2tap_fir_db.png`
- `raw_highres/pending_20260526/ch1_1_76mhz_pm100khz_raw_highres_selected_spectrum.csv`
- `raw_highres/pending_20260526/ch1_1_76mhz_pm100khz_raw_highres_selected_summary.csv`
- `raw_highres/pending_20260526/ch1_1_76mhz_pm100khz_raw_highres_selected_after_2tap_fir_spectrum.csv`
- `raw_highres/pending_20260526/ch1_1_76mhz_pm100khz_raw_highres_selected_after_2tap_fir_summary.csv`

## Focused AB Test, 76 MHz +/- 25 kHz

This AB comparison focuses only on the requested runs and windows:

- Carrier window: `76 MHz +/- 25 kHz`
- DC-style zoom: `0` to `25 kHz` offset from the 76 MHz carrier
- Unit for comparison plots: `dB`
- FFT length: `4,194,304`
- Bin spacing: `144.958496094 Hz`
- Frames averaged: `32`
- Data source: `Data_1_1.bin`, interleaved channel `1`

The selected AB set is:

| Run | Label | Mode | Wavelength | dB vs dark at 76 MHz | Max residual after 2-tap FIR |
|---|---|---|---:|---:|---:|
| `20260515_092941` | Dark noise | dark | none | `0.00 dB` | `-108.26 dB` |
| `20260515_133100` | Flint2 only @1030 | laser only | `1030 nm` | `96.57 dB` | `-56.64 dB` |
| `20260521_162959` | OPO/highpass @780 | highpass | `780 nm` | `97.76 dB` | `-55.46 dB` |
| `20260526_141535` | OPO @1560 auto | auto | `1560 nm` | `91.69 dB` | `-61.53 dB` |
| `20260526_143329` | OPO @1560 manual | manual | `1560 nm` | `99.88 dB` | `-53.34 dB` |
| `20260526_150209` | OPO @1600 manual A | manual | `1600 nm` | `93.20 dB` | `-60.02 dB` |
| `20260526_162112` | OPO @1600 manual B | manual | `1600 nm` | `92.00 dB` | `-61.21 dB` |

Important caveat: raw-backed `1600 nm` automatic runs were not found. The `1600 nm` comparison therefore uses two manual raw-backed runs rather than an auto/manual pair.

Generated AB files:

- `raw_highres/ab_test_76mhz_pm25khz/ab_test_76mhz_pm25khz_raw_db.png`
- `raw_highres/ab_test_76mhz_pm25khz/ab_test_76mhz_pm25khz_raw_db_vs_dark.png`
- `raw_highres/ab_test_76mhz_pm25khz/ab_test_76mhz_pm25khz_after_2tap_fir_db.png`
- `raw_highres/ab_test_76mhz_pm25khz/ab_test_76mhz_dc_to_25khz_positive_offset_raw_db.png`
- `raw_highres/ab_test_76mhz_pm25khz/ab_test_76mhz_dc_to_25khz_positive_offset_raw_db_vs_dark.png`
- `raw_highres/ab_test_76mhz_pm25khz/ab_test_76mhz_dc_to_25khz_positive_offset_after_2tap_fir_db.png`
- `raw_highres/ab_test_76mhz_pm25khz/ab_test_76mhz_dc_to_25khz_folded_abs_offset_raw_db.png`
- `raw_highres/ab_test_76mhz_pm25khz/ab_test_76mhz_dc_to_25khz_folded_abs_offset_raw_db_vs_dark.png`
- `raw_highres/ab_test_76mhz_pm25khz/ab_test_76mhz_dc_to_25khz_folded_abs_offset_after_2tap_fir_db.png`
- `raw_highres/ab_test_76mhz_pm25khz/ab_test_76mhz_pm25khz_summary.csv`
- `raw_highres/ab_test_76mhz_pm25khz/ab_test_76mhz_pm25khz_run_labels.csv`

## Selected Measurement Set

The clean comparison currently uses:

| Run | Meaning | PSD at 76 MHz | dB vs dark |
|---|---|---:|---:|
| `20260515_092941` | Dark noise reference | `5.311923e-05` | `0.00` |
| `20260515_133100` | Flint2 laser @1030 nm | `2.413202e+05` | `96.57` |
| `20260515_134951` | OPO single point @800 nm | `4.642831e+04` | `89.42` |
| `20260515_140509` | OPO scanning @800 nm | `4.615330e+04` | `89.39` |
| `20260521_162959` | Vacuum highpass filter @780 nm | `3.169411e+05` | `97.76` |

All five selected measurements peak at the exact `76.000000 MHz` bin in the high-resolution raw FFT.

## 2-Tap FIR Rejection Estimate

The assumed 2-tap FIR notch is:

```text
y[n] = (x[n] - x[n - 8]) / 2
```

The delay is `8` samples because:

```text
608 MHz / 76 MHz = 8
```

This places a notch exactly at `76 MHz`. The normalized magnitude response is:

```text
|H(f)| = |sin(pi * 8 * f / 608e6)|
```

The current dB plot uses:

```text
20 * log10(|H(f)|)
```

Rejection bandwidth depends on the rejection threshold:

| Rejection threshold | Full bandwidth | Half width around 76 MHz |
|---:|---:|---:|
| `>=40 dB` | `483.839 kHz` | `+/-241.920 kHz` |
| `>=60 dB` | `48.383 kHz` | `+/-24.192 kHz` |
| `>=70 dB` | `15.300 kHz` | `+/-7.650 kHz` |
| `>=80 dB` | `4.838 kHz` | `+/-2.419 kHz` |

Inside the latest `76 MHz +/- 10 kHz` plot, the edge rejection is about `67.8 dB`, so the whole visible window is inside the `>=60 dB` rejection bandwidth.

For the wider `76 MHz +/- 100 kHz` view, the edge rejection is about `47.7 dB`, so that whole window is inside the `>=40 dB` rejection bandwidth but not inside the `>=60 dB` rejection bandwidth.

Estimated strongest residuals after the 2-tap FIR in the `+/-100 kHz` window:

| Run | Max residual after FIR | Offset of max residual |
|---|---:|---:|
| `20260515_092941` dark noise | `-95.87 dB` | `+92.773 kHz` |
| `20260515_133100` flint2 | `-56.64 dB` | `-144.958 Hz` |
| `20260515_134951` OPO single point | `-63.79 dB` | `-144.958 Hz` |
| `20260515_140509` OPO scanning | `-63.82 dB` | `+144.958 Hz` |
| `20260521_162959` vacuum highpass | `-55.46 dB` | `-144.958 Hz` |

The exact `76 MHz` FFT bin is suppressed to the configured FIR floor (`-160 dB` rejection), so the remaining peak energy appears in the bins immediately beside the notch.

At `+800 kHz` offset from the 76 MHz carrier, the same 2-tap FIR is no longer near the notch center. Its attenuation is about `-29.61 dB` at the center of the `76.8 MHz +/- 100 kHz` window, and about `-30.77 dB` to `-28.59 dB` across the window.

Generated `+800 kHz` offset files:

- `raw_highres/offset_800khz/ch1_1_76mhz_offset800khz_pm100khz_selected_raw_db.png`
- `raw_highres/offset_800khz/ch1_1_76mhz_offset800khz_pm100khz_selected_after_2tap_fir_db.png`
- `raw_highres/offset_800khz/ch1_1_76mhz_offset800khz_pm100khz_selected_spectrum.csv`
- `raw_highres/offset_800khz/ch1_1_76mhz_offset800khz_pm100khz_selected_summary.csv`

## Full Spectrum Files

The full selected spectrum uses the same five-run set and keeps the complete one-sided FFT from `0` to `304 MHz`.

- `raw_highres/full_spectrum/ch1_1_full_spectrum_selected_semilogy.png`
  - Full-spectrum plot with frequency in MHz and PSD on a logarithmic y-axis.
- `raw_highres/full_spectrum/ch1_1_full_spectrum_selected_loglog.png`
  - Log-log, log-binned view of the same full spectrum.
- `raw_highres/full_spectrum/ch1_1_full_spectrum_selected.csv`
  - Full-resolution CSV with all `2,097,153` one-sided FFT bins. This file is about `302 MB`.
- `raw_highres/full_spectrum/ch1_1_full_spectrum_selected_summary.csv`
  - Compact summary with medians, maxima, and PSD values at `76 MHz` and `76.8 MHz`.

Generated FIR files:

- `raw_highres/ch1_1_76mhz_pm10khz_2tap_fir_bandwidth_summary.csv`
- `raw_highres/ch1_1_76mhz_pm10khz_2tap_fir_rejection_curve.csv`
- `raw_highres/ch1_1_76mhz_pm100khz_2tap_fir_bandwidth_summary.csv`
- `raw_highres/ch1_1_76mhz_pm100khz_2tap_fir_rejection_curve.csv`
- `raw_highres/ch1_1_76mhz_pm100khz_raw_highres_selected_after_2tap_fir_spectrum.csv`
- `raw_highres/ch1_1_76mhz_pm100khz_raw_highres_selected_after_2tap_fir_summary.csv`

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

- `raw_highres/ch1_1_76mhz_pm10khz_raw_highres_selected_db_with_2tap_fir.png`
- `raw_highres/ch1_1_76mhz_pm10khz_raw_highres_selected_overlay.png`
- `raw_highres/ch1_1_76mhz_pm10khz_raw_highres_selected_peak_comparison.png`
- `raw_highres/ch1_1_76mhz_pm10khz_raw_highres_selected_summary.csv`
- `raw_highres/ch1_1_76mhz_pm10khz_raw_highres_selected_spectrum.csv`
- `raw_highres/ch1_1_76mhz_pm10khz_2tap_fir_bandwidth_summary.csv`
- `raw_highres/ch1_1_76mhz_pm10khz_2tap_fir_rejection_curve.csv`

## Reproduce The Focused AB Test

First regenerate the raw spectra for the focused run set:

```powershell
python "C:\Quantum Squeezing\prototype and postprocessing\post processing\fft_76mhz_ch1_1_analysis\scripts\ch1_1_highres_76mhz_raw_fft.py" --center-hz 76000000 --half-width-hz 25000 --max-frames-per-run 32 --output-dir "C:\Quantum Squeezing\prototype and postprocessing\post processing\fft_76mhz_ch1_1_analysis\raw_highres\ab_test_76mhz_pm25khz" --run-names 20260515_092941 20260515_133100 20260521_162959 20260526_141535 20260526_143329 20260526_150209 20260526_162112
```

Then regenerate the labeled AB plots:

```powershell
python "C:\Quantum Squeezing\prototype and postprocessing\post processing\fft_76mhz_ch1_1_analysis\scripts\make_ab_test_focus_plots.py"
```

## When To Use The Older Reference Files

The `existing_fft_reference/` files came from already-saved high-frequency FFT CSVs. They are useful for quick historical checks, but they should not be used for careful peak inspection around 76 MHz because the frequency bin spacing is too coarse.

Use `raw_highres/` for the careful spectrum analysis.
