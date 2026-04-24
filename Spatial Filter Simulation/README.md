# Spatial Filter Simulation

This folder contains a simple prototype simulation for sizing a Fourier-plane spatial filter that cleans a beam toward a single spatial mode.

Current task:

- model a mixed Hermite-Gaussian beam
- pass it through a circular pinhole in the Fourier plane
- estimate how much `TEM00` survives
- estimate how much higher-order mode content is rejected
- sweep pinhole radius to find a good tradeoff between purity and throughput

## Physics Behind The Model

The current script uses a low-order transverse-mode model rather than a full wave-optics propagation model.

The main physical assumptions are:

- the input beam can be expanded as a sum of low-order Hermite-Gaussian spatial modes
- the dominant desired mode is `TEM00`
- unwanted beam distortion is represented as admixture of `TEM10`, `TEM01`, `TEM20`, `TEM02`, and similar low-order modes
- the spatial filter is a circular pinhole placed at the focal plane of a lens or objective

In this picture, the focal plane is the Fourier plane of the incoming beam:

- low spatial frequencies concentrate near the center
- higher-order transverse mode content spreads farther away from the center and often has nodal structure
- a circular pinhole therefore acts as a low-pass spatial filter

The script builds the field as:

```text
E(x, y) = sum(a_mn * HG_mn(x, y))
```

where:

- `HG_mn` are Hermite-Gaussian transverse modes
- `a_mn` are amplitudes chosen from the requested mode-power fractions

The pinhole is then applied directly in the focal plane as a hard circular aperture:

```text
E_filtered(x, y) = E(x, y) * P(x, y)
```

where `P(x, y)` is `1` inside the pinhole radius and `0` outside.

After clipping by the pinhole, the filtered field is projected back onto the same Hermite-Gaussian basis to estimate how much of the transmitted light remains in `TEM00`:

```text
mode purity = P(TEM00) / P(transmitted total)
```

and the transmitted fraction of the original fundamental mode is reported as:

```text
TEM00 transmission = P(filtered TEM00) / P(input TEM00)
```

So the model is intended to answer practical design questions like:

- if the incoming beam contains a known amount of low-order mode contamination, how much can a pinhole clean it up?
- how much transmission do I lose for a given pinhole radius?
- what radius encloses `50%`, `80%`, or `95%` of the focal-plane power?
- how does the required spot size relate to beam size on a `20 mm` focusing optic?

## Relation To Focusing Optics

For the focus-spot sweep, the script uses the Gaussian-beam relation

```text
w_focus = lambda * f / (pi * w_in)
```

where:

- `w_focus` is the focused `TEM00` 1/e field radius at the pinhole plane
- `lambda` is the wavelength
- `f` is the focal length of the objective or lens
- `w_in` is the input beam 1/e field radius on the focusing optic

This lets the code translate between:

- desired focal-plane spot size
- required beam size on the objective
- pinhole radius needed to pass a target fraction of the focal-plane power

## What This Model Captures Well

- first-pass spatial filter sizing
- throughput versus cleanup tradeoff
- sensitivity to low-order transverse-mode contamination
- order-of-magnitude pinhole selection
- focal-plane enclosed-power estimates

## What This Model Does Not Yet Capture

- full Fresnel or FFT diffraction propagation through a real lens system
- aberrations from the objective
- non-Gaussian beam defects beyond the chosen low-order mode basis
- scattering from imperfect pinhole edges
- vector/polarization effects
- nonlinear effects in the beam source
- exact cavity-generated mode structure from a real OPO

Because of that, this should be treated as a design-level guide for choosing a reasonable pinhole range, not as a final exact prediction of experimental performance.

## Main Script

- `spatial_filter_single_mode_sim.py`

## Example

From this folder:

```powershell
python .\spatial_filter_single_mode_sim.py
```

With a custom mode mixture and a small pinhole offset:

```powershell
python .\spatial_filter_single_mode_sim.py `
  --modes "0:0:0.72,1:0:0.12,0:1:0.08,2:0:0.05,0:2:0.03" `
  --offset-x-um 8 `
  --offset-y-um -5
```

Outputs are written to `output/`:

- `spatial_filter_sweep.csv`
- `spatial_filter_sweep.png`
- `spatial_filter_example_fields.png`
- `focal_plane_mode_distribution.png`
- `focal_plane_enclosed_power.csv`
- `focal_plane_enclosed_power.png`
- `mode_purity_vs_focus_spot_20mm_objective.csv`
- `mode_purity_vs_focus_spot_20mm_objective.png`
- `README_results.txt`

## Notes

- This is a fast design-level simulation, not a full diffraction-limited hardware model.
- It assumes the unwanted spatial structure can be approximated by low-order Hermite-Gaussian content.
- The pinhole is modeled directly in the Fourier plane as a hard circular aperture.
- The script also estimates mode purity versus focused spot size for a `20 mm` objective using `w_focus = lambda * f / (pi * w_in)`.
- It exports the focal-plane intensity distribution and enclosed-power-versus-radius so you can choose a practical pinhole size from the simulated spot.
