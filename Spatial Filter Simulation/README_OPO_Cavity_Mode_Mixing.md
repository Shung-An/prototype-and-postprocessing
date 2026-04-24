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

## Figure Links

Current generated figures in this repo:

- [OPO mode mixing vs tilt](opo_output/opo_mode_mixing_vs_tilt.png)
- [OPO mode mixing vs thermal lens](opo_output/opo_mode_mixing_vs_thermal_lens.png)
- [OPO mode mixing vs aperture](opo_output/opo_mode_mixing_vs_aperture.png)

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

## Why These Effects Cause Mode Mixing

The OPO cavity supports a particular transverse eigenmode.

If the circulating field matches that eigenmode well, the cavity stays close to pure `TEM00`.
If something changes the transverse phase, beam centering, waist size, symmetry, or clipping boundary, the field after one round trip no longer matches a single Gaussian mode exactly.
The result is that the field must be described as a sum of `TEM00` plus higher-order transverse modes.

In that sense, mode mixing is fundamentally a mode-overlap problem:

```text
perfect overlap with the cavity eigenmode -> mostly TEM00
imperfect overlap or broken symmetry -> power leaks into higher-order modes
```

### Mirror Tilt

Mirror tilt changes the cavity axis and adds a transverse phase gradient across the beam.

That kind of perturbation is odd in space, so it tends to couple the symmetric `TEM00` mode into odd modes such as:

- `TEM10`
- `TEM01`

This is why tilt-like errors are often associated with first-order transverse modes appearing first.

### Thermal Lensing

Heating in the nonlinear crystal changes the refractive index and acts like an additional lens inside the cavity.

That changes:

- waist size
- waist position
- overall mode-matching condition

Even if the cavity remains centered, the fundamental Gaussian of the original cavity is no longer the exact eigenmode of the perturbed cavity.
That kind of symmetric mismatch often couples `TEM00` into even modes such as:

- `TEM20`
- `TEM02`

### Aperture Clipping

Clipping truncates part of the spatial field.

A clipped Gaussian is not itself a pure Gaussian mode anymore.
Sharp edges in the transverse profile require a combination of many Hermite-Gaussian modes to represent the field, so clipping naturally creates higher-order mode content.

In practice, clipping can come from:

- mirror clear aperture
- crystal mount geometry
- irises
- housing edges
- beam walking off-center through a finite opening

### Decenter And Displacement

A displaced Gaussian beam is not equal to the centered cavity `TEM00` mode.
When expanded in the centered cavity basis, it becomes a mixture of the fundamental and higher-order modes.

That is why beam walkoff, mis-centering, or cavity-axis shifts often show up as mode mixing even without obvious clipping.

### Astigmatism And Asymmetry

If the cavity focuses differently in x and y, or if the crystal introduces anisotropic lensing, the transverse mode is no longer described by one circularly symmetric Gaussian.

This breaks the simple `TEM00` condition and can populate different x and y higher-order modes differently.

### Pump Mismatch In A Real OPO

Although the current script is a cavity perturbation model rather than a full nonlinear gain model, in a real OPO the pump also matters.

If the pump does not overlap well with the cavity fundamental mode, the nonlinear interaction can preferentially reinforce distorted or higher-order spatial structure.
So poor pump matching can indirectly increase effective mode mixing even when the passive cavity alignment looks acceptable.

### Near-Degenerate Cavities

If the cavity geometry makes the transverse-mode frequency spacing small, different modes become closer to resonance.

Then weak perturbations are more effective at mixing them, because the cavity is less selective about which transverse mode it supports.

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
