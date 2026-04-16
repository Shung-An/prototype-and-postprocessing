# DataFiles Browser

`datafiles_browser.py` is a lightweight Tkinter browser for reviewing processed Quantum Squeezing runs inside the `DataFiles` results tree.

It is designed for quickly scanning runs that already contain:

- `final_clean_result.png`
- optional `raw_std_within_parity.png`
- optional `signal_emergence.mp4`
- optional `metadata.json`

## What It Does

- scans a root folder recursively for runs containing `final_clean_result.png`
- builds a sortable table of runs
- previews the main result image and the std-evolution plot
- reads metadata such as sample, duration, sample power, temperature, shot noise, and scan range
- lets you star a run directly from the table
- lets you hide/show and reorder table columns
- can rerun `cm_pipeline_all_in_one.py` for the selected run, all filtered runs, or manually picked folders

## Main UI Features

- `Search` panel:
  - free-text search across run folder, sample, description, tags, filename, power, temperature, and star state
  - optional `Scan range >=` filter
  - foldable with `Hide Filters` / `Show Filters`
- run table:
  - default columns: `Star`, `Date`, `Sample`, `Power (mW)`, `Temp (C)`, `Elapsed`, `Shot Noise`, `Range (mm)`
  - `Run Folder` exists but is hidden by default
  - click a column header to sort
  - double-click the `Star` cell to toggle `[ ]` / `[x]`
- preview area:
  - left: `final_clean_result.png`
  - right: `raw_std_within_parity.png`
  - double-click the main preview to open the MP4

## Metadata Handling

The browser reads `metadata.json` when present.

Top-level fields used:

- `Timestamp`
- `Sample`
- `Description`
- `Tags`
- `Filename`
- `Duration`
- `StarMeasurement` or similar star aliases

`PhysicsData` fields used:

- `Power_mW_1`
- `Power_mW_2`
- `SamplePower_mW`
- `EnvironmentTemperature_C`
- `ShotNoiseResult_urad2_rtHz`
- `ScanRange_mm`
- `ScanMin_mm`
- `ScanMax_mm`

The browser is intentionally tolerant of a few alternate key names for sample power, temperature, and star state.

## Starred Measurements

Star state is stored back into the run's `metadata.json` as:

```json
{
  "StarMeasurement": true
}
```

If `metadata.json` does not exist yet, the browser creates one when you star a run.

## Expected Folder Layout

Typical run folder:

```text
20260415_185747/
├─ final_clean_result.png
├─ raw_std_within_parity.png
├─ signal_emergence.mp4
└─ metadata.json
```

## Running It

From the `post processing` folder:

```powershell
python .\datafiles_browser.py
```

## Requirements

- Python 3.10+
- standard library only for core behavior
- optional: `Pillow` for better image loading and resizing

If Pillow is missing, the app still runs and falls back to Tk image loading.

## Rerun Analysis

The rerun buttons call `cm_pipeline_all_in_one.py` located in the same folder as `datafiles_browser.py`.

Supported actions:

- `Rerun Selected`
- `Rerun Filtered`
- `Run Picked Folders`

The browser launches the pipeline with the selected folder paths and refreshes the run list when processing finishes successfully.

## Root Folder

Default root:

```text
D:\Quantum Squeezing Project\DataFiles
```

You can change it in the top-right `Root` entry before pressing `Refresh`.

## Notes

- the browser only lists folders that contain `final_clean_result.png`
- missing metadata or missing std plots do not prevent a run from showing up
- the current UI is optimized for desktop review, not for headless batch processing
