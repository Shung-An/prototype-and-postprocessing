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

The legacy Tkinter browser is still available:

```powershell
python .\datafiles_browser.py --tk
```

## Data Browser

The Data Browser is now HTML-first. The Python file serves `index.html` for both `/` and `/index.html`; if `index.html` is missing, it falls back to the embedded HTML copy in `datafiles_browser.py`.

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
- run folder

Use `Refresh` to reload from the SQLite index. Use `Rebuild Index` when you want to rescan the full `DataFiles` tree from disk.

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
```

The Data Browser is tolerant of several alternate key names for OPO and wavelength, but the preferred WPF/metadata names are:

```text
PhysicsData.UseOPO
PhysicsData.LaserWavelength_nm
```

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
- optional `Pillow` for the legacy Tk image preview path

The browser stores its SQLite index and UI config in the system temp folder.

## Notes

- Restart `datafiles_browser.py` after editing `index.html` or Python server code.
- Browser asset requests for MP4 preview may be cancelled by the browser during seeking; those client disconnects are handled silently.
- The HTML browser is intended for local use on `127.0.0.1`.
