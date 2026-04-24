# OPO Cavity Mode Mixing Simulation

This is a prototype transverse-mode mixing simulator for an OPO cavity.

It models the cavity field in a small Hermite-Gaussian basis:

- `TEM00`
- `TEM10`
- `TEM01`
- `TEM20`
- `TEM11`
- `TEM02`

The current model is intentionally simple and useful for trend checking:

- estimates the cavity waist from a symmetric cavity geometry
- applies a round-trip perturbation from mirror tilt
- applies a thermal-lens phase term
- applies aperture clipping
- iterates the cavity mode and projects the result back onto the low-order basis

## Main Script

- `opo_cavity_mode_mixing_sim.py`

## Example

```powershell
python .\opo_cavity_mode_mixing_sim.py
```

With custom geometry and stronger perturbations:

```powershell
python .\opo_cavity_mode_mixing_sim.py `
  --cavity-length-mm 90 `
  --mirror-radius-mm 100 `
  --tilt-x-urad 20 `
  --thermal-lens-f-mm 80 `
  --aperture-radius-um 120
```

Outputs are written to `opo_output/`:

- `opo_mode_mixing_vs_tilt.csv`
- `opo_mode_mixing_vs_tilt.png`
- `opo_mode_mixing_vs_thermal_lens.csv`
- `opo_mode_mixing_vs_thermal_lens.png`
- `opo_mode_mixing_vs_aperture.csv`
- `opo_mode_mixing_vs_aperture.png`
- `README_results.txt`

## How To Read The Figures

### `opo_mode_mixing_vs_tilt.png`

This figure shows how sensitive the cavity spatial purity is to mirror tilt.

- the top panel is the `TEM00` purity
- the bottom panel is the total higher-order mode content

Use it to estimate how much alignment error can be tolerated before the cavity stops looking close to single mode.

Typical interpretation:

- a flat region near zero tilt means the cavity is relatively robust
- a steep drop means the cavity is very alignment-sensitive
- if `TEM10` or `TEM01` grow first in the CSV, that usually indicates tilt-like or decenter-like mixing

### `opo_mode_mixing_vs_thermal_lens.png`

This figure shows how thermal lensing in the crystal can distort the cavity eigenmode.

The horizontal axis is the equivalent thermal-lens focal length:

- very long focal length means weak thermal lensing
- shorter focal length means stronger thermal lensing

Use it to see how much thermal loading can be tolerated before higher-order content becomes important.

If the purity falls only when the focal length becomes quite short, the cavity is comparatively robust to thermal lensing in this simplified model.

### `opo_mode_mixing_vs_aperture.png`

This figure shows how clipping affects the cavity mode.

- large aperture radius means little or no clipping
- small aperture radius means strong clipping

This is useful when you suspect:

- mirror clear-aperture limits
- crystal mount clipping
- iris or housing clipping
- effective clipping from poor alignment through a finite aperture

If the purity collapses quickly as the aperture shrinks, then clipping is likely a strong driver of spatial-mode degradation.

## Practical Reading Of The CSV Files

Each CSV gives:

- `tem00_purity`
- `higher_order_content`
- per-mode fractions like `tem10`, `tem01`, `tem20`, `tem02`, `tem11`

Those per-mode fractions help identify the likely physical origin of the distortion:

- `TEM10` or `TEM01` growth often points to tilt or displacement
- `TEM20` or `TEM02` growth often points to waist mismatch, lensing, or symmetric clipping
- `TEM11` growth can suggest more mixed or asymmetric perturbations

## Interpreting The Default Run

With the current default settings, the simulator is intended to start from a reasonably healthy cavity.

That means:

- baseline `TEM00` should be very close to `1`
- higher-order content should be very small at zero perturbation
- the sweep curves should be read mainly as sensitivity curves rather than absolute predictions

## Notes

- This is a design-level cavity perturbation model, not a full nonlinear OPO propagation code.
- It is best used to see trends and sensitivity, not to claim exact experimental fractions.
- If you later want, this can be extended with:
  - crystal astigmatism
  - decenter and wedge
  - separate x/y waists
  - pump-mode overlap
  - FFT propagation instead of basis-only iteration
