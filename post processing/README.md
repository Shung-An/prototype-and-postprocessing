# Post Processing Tools

This folder contains the current post-processing workflow for Quantum Squeezing runs. The main entry points are:

- `datafiles_browser.py`: HTML-first browser for reviewing processed runs.
- `index.html`: Data Browser frontend served by `datafiles_browser.py`.
- `metadata_manager.py`: HTML metadata editor with workbook-style bulk editing.
- `cm_pipeline_all_in_one.py`: Python post-processing pipeline for one or more run folders.
- `repair_attenuation_metadata.py`: helper for repairing older attenuator metadata.

The tools expect a `DataFiles` tree containing run folders with processed outputs such as `final_clean_result.png`, `metadata.json`, and optional `signal_emergence.mp4`.

## Quick Start

From this folder:

```powershell
python .\datafiles_browser.py
```

This opens the HTML Data Browser in your default browser. The server prints a local URL such as:

```text
DataFiles HTML browser: http://127.0.0.1:xxxxx/
```

The browser uses the saved root path by default. You can also pass a root folder:

```powershell
python .\datafiles_browser.py "D:\Quantum Squeezing Project\DataFiles"
```

If the temporary `127.0.0.1` server has stopped and Chrome shows `ERR_CONNECTION_REFUSED`, open `index.html` directly instead:

```powershell
start .\index.html
```

In standalone HTML mode, click `Choose DataFiles Folder` and select the folder that contains your run folders. Chrome or Edge will ask for folder permission, then the page scans the folder directly in the browser.

## Data Browser

The Data Browser is fully HTML. The Python file runs the optional local API/static server, and `index.html` is the single UI source served for both `/` and `/index.html`. The same `index.html` can also run as a standalone file with no localhost server.

The browser has two tabs:

- `Run List`: dense sortable table for all indexed runs.
- `Plots`: compact run list, selected-run metadata, preview plots, and embedded MP4 player.

The run list includes:

- star state
- date
- sample
- experiment tag
- port power
- sample power
- attenuator correction factor
- Use OPO
- wavelength in nm
- temperature
- shot noise
- scan range
- scan rate in mm/s
- run folder

Use `Refresh` to reload from the SQLite index. Use `Rebuild Index` when you want to rescan the full `DataFiles` tree from disk.

In standalone HTML mode, `Refresh Folder` and `Rescan Folder` read from the selected folder directly. Preview images, MP4 playback, search, sorting, filtering, and star toggling work in the browser. Actions that launch local programs still need Python, so `Rerun Selected`, `Rerun This Run`, `Open Folder`, and bulk metadata editing are available only through `datafiles_browser.py`.

For selecting runs to rerun, the Data Browser supports normal list-style multi-selection:

- click a checkbox to select or unselect one run
- `Ctrl`+click, or `Cmd`+click on macOS, toggles one run without changing the rest
- `Shift`+click selects or unselects the visible range from the previous selection anchor

## Rerun Analysis

In the HTML Data Browser:

- select one or more runs with the checkboxes
- click `Rerun Selected`
- or select a single run in the Plots tab and click `Rerun This Run`

The browser launches:

```powershell
python .\cm_pipeline_all_in_one.py <run_folder> ...
```

Reruns happen in a background thread. The status line updates while the process runs, and the browser reloads the run index when the process finishes.

## Metadata Editor

Open the metadata editor from Data Browser with:

- `Edit Metadata`: opens the selected run, while also showing sibling runs in the same root.
- `All Metadata`: opens all indexed metadata files under the current DataFiles root.

You can also run it directly:

```powershell
python .\metadata_manager.py --edit "D:\Quantum Squeezing Project\DataFiles"
```

The HTML metadata editor has two views:

- `Workbook`: spreadsheet-style table where runs are rows and metadata fields are columns.
- `Run Form`: detailed single-run form with raw JSON and flattened metadata view.

Workbook edits are saved in bulk with `Save Workbook`. The editor updates the Data Browser SQLite index after saving, so Data Browser picks up changed metadata after refresh or when you return focus to the browser.

In the workbook view, click any column header to sort by that field. Click the same header again to reverse the sort order. Unsaved cell edits are preserved while searching or sorting, then written when you click `Save Workbook`.

## Important Metadata Fields

These fields are first-class in the current tools:

```text
Sample
ExperimentTag
StarMeasurement
PhysicsData.UseOPO
PhysicsData.LaserWavelength_nm
PhysicsData.PowerDetectorAttenuatorApplied
PhysicsData.PowerDetectorAttenuatorCount
PhysicsData.PowerDetectorAttenuatorEach_dB
PhysicsData.PowerDetectorAttenuatorTotal_dB
PhysicsData.PowerDetectorAttenuatorCorrectionFactor
PhysicsData.Detector
PhysicsData.DetectorResponsivity_A_per_W
PhysicsData.OnSamplePower_mW
PhysicsData.Power_mW_1
PhysicsData.Power_mW_2
PhysicsData.Temperature_K
PhysicsData.ShotNoiseResult_urad2_rtHz
PhysicsData.ShotNoiseResult_V2_rtHz
PhysicsData.ScanRange_mm
PhysicsData.ScanMin_mm
PhysicsData.ScanMax_mm
PhysicsData.ScanVelocity_mm_s
```

The Data Browser is tolerant of several alternate key names for OPO and wavelength, but the preferred WPF/metadata names are:

```text
PhysicsData.UseOPO
PhysicsData.LaserWavelength_nm
```

## Scan Rate

WPF records the ESP scan velocity in:

```text
PhysicsData.ScanVelocity_mm_s
```

The acquisition program queries the ESP axis velocity (`VA?`) when it writes `metadata.json`. The post-processing pipeline preserves that value; for older runs that do not have it, the pipeline can estimate scan velocity from the recorded `delay_stage_positions.log` and write the same metadata field. Data Browser shows this as `Scan Rate`.

## Attenuator Rule

The attenuator setting is owned by WPF metadata, not by the post-processing pipeline.

`cm_pipeline_all_in_one.py` reads:

```text
PhysicsData.PowerDetectorAttenuatorApplied
PhysicsData.PowerDetectorAttenuatorTotal_dB
PhysicsData.PowerDetectorAttenuatorCorrectionFactor
```

The pipeline uses `PowerDetectorAttenuatorCorrectionFactor` directly when the attenuator is applied. It does not re-evaluate the attenuator from `sensitivity.log`, and it does not overwrite the attenuator metadata fields when writing `metadata.json`.

For amplitude correction:

```text
40 dB power attenuation -> amplitude correction factor 100
```

So a run with the applied attenuator should usually have:

```json
{
  "PhysicsData": {
    "PowerDetectorAttenuatorApplied": true,
    "PowerDetectorAttenuatorTotal_dB": 40,
    "PowerDetectorAttenuatorCorrectionFactor": 100
  }
}
```

## Detector Responsivity

Responsivity is stored in metadata and can be edited in the metadata workbook:

```text
PhysicsData.Detector
PhysicsData.LaserWavelength_nm
PhysicsData.DetectorResponsivity_A_per_W
```

The expected workflow is that WPF writes detector, wavelength, and responsivity metadata at acquisition time. Post-processing should consume those values rather than guessing them later.

## Pipeline

Run one or more folders:

```powershell
python .\cm_pipeline_all_in_one.py "D:\Quantum Squeezing Project\DataFiles\20260508_120000"
python .\cm_pipeline_all_in_one.py "run_folder_1" "run_folder_2" --force
```

Useful options:

```text
--force             rebuild even when cache says outputs are current
--review-first-n N  export first N raw frames for review
--review-start-idx  zero-based frame index for review export
--review-only       export review assets only
```

The pipeline writes processed plots, updates non-WPF-owned metadata fields, and updates the Data Browser index when it finishes.

## Critical Pairs

The pipeline has a fixed list of candidate channel pairs. Each pair compares two correlation-matrix channels, written as:

```text
(row1,col1)-(row2,col2)
```

For example, `(1,1)-(8,8)` means the pipeline compares the correlation channel at row 1, column 1 against the channel at row 8, column 8. These pairs are used to make the cleaner summary plots and the `signal_emergence.mp4` movie. They do not limit the full analysis: `final_amplitudes_all_pairs.csv` and `final_result_ALL_PAIRS.png` still include every candidate pair.

The previous definition of a critical pair was based on the final binned amplitude curve. For each pair, the code computed the pair's mean amplitude after binning by delay position, compared that value to the global mean across all pairs, and ranked pairs by the absolute deviation from that global mean. In plain terms: it highlighted pairs whose final average looked most unusual compared with the rest of the pair set.

The current definition is based on correlation-channel MSE. For each of the 64 correlation-matrix channels, the pipeline computes:

```text
MSE(channel) = mean((channel_over_time - mean(channel_over_time))^2)
```

This is the same idea shown in the `MSE Corr (V^4)` heatmap: a high value means that channel varies strongly over frames. Then each candidate pair receives a pair score:

```text
Pair MSE score = average(MSE(channel A), MSE(channel B))
```

The 9 pairs with the highest pair MSE score are tracked as critical pairs. This makes the selected plots focus on the channel pairs whose two underlying correlation channels are most variable over time.

The selected pairs are written to:

```text
critical_pairs_summary.csv
```

That file includes:

- `pair_index`: zero-based index into the candidate-pair list used by the Python code
- `label`: human-readable pair label, such as `(1,1)-(8,8)`
- `diagonal_offset`: how far apart the paired matrix locations are
- `mse_corr_pair_score`: average MSE of the two endpoint channels
- `mse_corr_channel_1`: MSE of the first endpoint channel
- `mse_corr_channel_2`: MSE of the second endpoint channel
- `mean_pair_amplitude`: mean final binned pair amplitude
- `peak_abs_amplitude`: largest absolute final binned pair amplitude

## Expected Run Folder

Typical run folder:

```text
20260508_120000/
|-- cm.bin
|-- profile.txt
|-- sensitivity.log
|-- metadata.json
|-- final_clean_result.png
|-- loglog_eval.png
|-- diagonal_offset_matrix_urad2.png
|-- raw_std_over_time.png
`-- signal_emergence.mp4
```

Only `final_clean_result.png` is required for a folder to appear in Data Browser.

## Requirements

- Python 3.10+
- standard library for the HTML servers and browser index
- `numpy`, `matplotlib`, and `imageio` for the processing pipeline

The browser stores its SQLite index and UI config in the system temp folder.

## Notes

- Restart `datafiles_browser.py` after editing `index.html` or Python server code.
- Browser asset requests for MP4 preview may be cancelled by the browser during seeking; those client disconnects are handled silently.
- The Python-assisted HTML browser is intended for local use on `127.0.0.1`; the standalone browser is opened directly from `index.html`.
