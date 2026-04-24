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

## Notes

- This is a design-level cavity perturbation model, not a full nonlinear OPO propagation code.
- It is best used to see trends and sensitivity, not to claim exact experimental fractions.
- If you later want, this can be extended with:
  - crystal astigmatism
  - decenter and wedge
  - separate x/y waists
  - pump-mode overlap
  - FFT propagation instead of basis-only iteration
