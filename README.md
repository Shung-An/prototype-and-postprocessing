# Prototype and Postprocessing

This folder is the scratchpad and verification area for the Quantum Squeezing project.

It is mainly used for:

- quick MATLAB test scripts
- prototype analysis pipelines
- simple verification and sanity-check tools
- one-off data inspection
- early post-processing experiments before logic is promoted into more stable software

This is not intended to be a polished, tightly curated production package. It is the working area for trying ideas quickly, checking assumptions, and validating results with minimal overhead.

## What Lives Here

### `post processing/`

The most structured part of this folder.

Contains the current Python/MATLAB post-processing tools, including:

- `cm_pipeline_all_in_one.py`
- `cm_pipeline_all_in_one.m`
- `raw_frame_diagnose.py`
- `datafiles_browser.py`

This is where processed run browsing and the more repeatable analysis pipeline live.

### `Beam Profile Analysis/`

Small MATLAB studies related to beam profile and focusing behavior.

Typical use:

- optical geometry checks
- focusing / NA comparison
- quick beam-shape sanity tests

### `ErFeO3HeatingSimulationByCOMSOL/`

COMSOL models and helper scripts for heating-related checks.

Contains:

- `.mph` model files
- exported `.csv` results
- MATLAB scripts for reading or comparing simulation outputs

### `pulseWidthByBBO/`

Autocorrelation and pulse-width verification experiments.

Contains a mix of:

- MATLAB scripts
- `.mat` output
- `.csv` exports
- generated plots

### `ThermalModulationCheckup/`

Small scripts used to inspect thermal-modulation behavior and related cumulative/raw trends.

### `Unclassified/`

The catch-all prototype area.

This folder contains many single-purpose MATLAB scripts and a few helper Python files for:

- DAQ checks
- ESP300 motion tests
- cross-correlation verification
- demodulation experiments
- noise analysis
- GPU/streaming diagnostics
- plotting and inspection helpers
- quick hardware-control experiments

If a script is useful but still too rough, too narrow, or too experimental to give a dedicated home, it usually ends up here first.

## Intended Use

Use this folder when you want to:

- test an idea quickly
- validate a hardware behavior
- inspect raw or intermediate data
- compare different analysis approaches
- prototype a plotting or gating method
- verify that a result is physically reasonable before integrating the logic elsewhere

## What Not To Assume

Do not assume scripts in this folder are:

- fully documented
- generalized for all datasets
- stable across all hardware setups
- production-ready
- consistently named

Many of them were written for speed of iteration, not for long-term maintainability.

## Conventions

In practice, this folder follows a loose workflow:

1. try an idea quickly in MATLAB or Python
2. use it for verification on a few runs
3. refine it if it proves useful
4. move the more mature version into `post processing/` or into the main software when appropriate

## Recommended Reading Order

If you are new to this folder, start here:

1. `post processing/README.md`
2. `post processing/datafiles_browser.py`
3. `post processing/cm_pipeline_all_in_one.py`

Then explore the more specialized folders only if you need those specific experiments.

## Notes for Future Organization

If a prototype becomes important and gets reused repeatedly, it should usually be:

- cleaned up
- documented
- moved out of `Unclassified/`
- grouped with related scripts or promoted into the main software repository structure
