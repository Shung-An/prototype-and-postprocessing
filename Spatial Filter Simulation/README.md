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

For a non-ideal beam, a useful extension is

```text
w_focus ≈ M^2 * lambda * f / (pi * w_in)
```

So compared with an ideal Gaussian:

- larger `M^2` gives a larger focused spot
- larger wavelength gives a larger focused spot
- larger beam size on the objective gives a smaller focused spot

That means worse spatial purity usually makes the focused spot after the `20 mm` objective larger and therefore changes the pinhole size you need.

## Mode Purity And M^2

`TEM00` mode purity and `M^2` are related, but they are not the same quantity.

- mode purity tells you how much power is in the fundamental Gaussian mode
- `M^2` tells you how far the beam propagation differs from an ideal Gaussian beam

For a beam expanded in Hermite-Gaussian modes with normalized mode powers `p_mn`, the script estimates:

```text
Mx^2 = sum(p_mn * (2m + 1))
My^2 = sum(p_mn * (2n + 1))
```

and reports an average:

```text
M^2_avg = (Mx^2 + My^2) / 2
```

Important consequence:

- pure `TEM00` gives `Mx^2 = My^2 = 1`
- adding higher-order content always increases `M^2`
- the same `TEM00` purity can correspond to different `M^2` values depending on which higher-order modes are present

Examples:

- `TEM10` increases `Mx^2` more than `My^2`
- `TEM01` increases `My^2` more than `Mx^2`
- `TEM20` and `TEM02` increase `M^2` more strongly than first-order modes for the same power fraction

So there is no single universal conversion from purity to `M^2`, but for a given mode family there is a definite relationship.

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
- `build_case_summary.txt`
- `mode_purity_vs_focus_spot_20mm_objective.csv`
- `mode_purity_vs_focus_spot_20mm_objective.png`
- `m2_vs_mode_purity.png`
- `README_results.txt`

You can also run a specific hardware case by providing:

- wavelength
- beam size on the focusing optic
- whether that beam size is a diameter or radius
- actual focusing focal length
- actual pinhole diameter

Example:

```powershell
python .\spatial_filter_single_mode_sim.py `
  --wavelength-nm 780 `
  --input-beam-size-mm 3 `
  --input-beam-size-is-diameter `
  --build-focal-length-mm 250 `
  --build-pinhole-diameter-um 20 `
  --output-dir .\output_780nm_3mm_250mm_20um
```

That build-specific summary is written to `build_case_summary.txt`.

## Figure Links

Current generated figures in this repo:

- [Spatial filter sweep](output/spatial_filter_sweep.png)
- [Spatial filter example fields](output/spatial_filter_example_fields.png)
- [Focal-plane mode distribution](output/focal_plane_mode_distribution.png)
- [Focal-plane enclosed power](output/focal_plane_enclosed_power.png)
- [Mode purity vs focus spot for 20 mm objective](output/mode_purity_vs_focus_spot_20mm_objective.png)
- [Estimated M^2 vs mode purity](output/m2_vs_mode_purity.png)

## How To Read The Figures

### `spatial_filter_sweep.png`

This figure is the main tradeoff plot for choosing a pinhole radius.

- the top panel shows total transmission through the pinhole
- the middle panel shows how much of the original `TEM00` survives
- the bottom panel shows the purity of the transmitted beam

Typical interpretation:

- moving to a larger pinhole usually increases throughput
- moving to a smaller pinhole usually improves filtering but throws away more light
- the useful design region is usually where purity is already high but transmission has not collapsed too much

If the best radius lands at the edge of the sweep range, that means the sweep should be extended before treating the result as final.

### `spatial_filter_example_fields.png`

This figure compares:

- the original focal-plane intensity
- the pinhole mask
- the transmitted intensity after clipping

It is useful for a quick visual sanity check:

- whether the selected pinhole is centered correctly
- whether the filter is cutting into the main lobe
- whether obvious higher-order side lobes are being removed

### `focal_plane_mode_distribution.png`

This is the most direct figure for choosing a pinhole size from the spot geometry.

It shows the focal-plane intensity map with candidate pinhole radii drawn on top.

Use it to judge:

- how tightly concentrated the main lobe is
- whether higher-order mode content sits outside the central spot
- whether a given pinhole radius mostly passes the bright core or also includes outer structure

In practice, this is the figure to compare against available commercial pinhole diameters.

### `focal_plane_enclosed_power.png`

This plot shows enclosed power fraction versus pinhole radius.

- one curve is the total mixed beam
- one curve is the ideal `TEM00` contribution alone
- the vertical marker shows the current best-radius choice from the script's score

This figure helps answer:

- what radius passes `50%`, `80%`, or `95%` of the focal-plane power?
- how much larger the mixed beam is than the clean `TEM00` core?
- whether a candidate pinhole is acting mostly as a cleanup filter or mostly as a throughput limiter

If the total-beam curve rises much more slowly than the `TEM00` curve, that is a sign that higher-order content is spread farther from the center and can in principle be filtered away.

### `mode_purity_vs_focus_spot_20mm_objective.png`

This figure connects spatial filtering to the focusing optic.

- the top panel shows the best achievable `TEM00` purity after optimizing pinhole radius
- the middle panel shows the corresponding best `TEM00` transmission
- the bottom panel shows the beam radius required on the `20 mm` objective to produce that focused spot size

This is mainly a design-space figure:

- if you can only put a certain beam size on the objective, it tells you what focal-plane spot size to expect
- if you want a certain spot size at the pinhole, it tells you what beam size is needed before the objective

If the best purity curve is nearly flat, that means this simplified model is mostly scale-invariant and pinhole sizing matters more than the absolute spot size.

### `m2_vs_mode_purity.png`

This figure shows the estimated relationship between transmitted `TEM00` purity and the corresponding beam-quality factors `Mx^2`, `My^2`, and average `M^2`.

Use it to connect the modal language to the more common beam-quality language:

- higher purity usually means `M^2` closer to `1`
- lower purity usually means larger focused spot after the `20 mm` objective
- unequal `Mx^2` and `My^2` indicate directional asymmetry in the higher-order mode content

This is especially useful if you want to compare the simulation against a beam profiler or knife-edge measurement that reports `M^2` rather than direct mode fractions.

## Practical Pinhole Selection

For real hardware, a useful workflow is:

1. look at `focal_plane_mode_distribution.png` to estimate the central bright-core radius
2. check `focal_plane_enclosed_power.png` to see what fraction of power falls inside that radius
3. compare with `spatial_filter_sweep.png` to see the purity versus throughput tradeoff
4. choose the nearest real pinhole diameter that gives acceptable loss and acceptable cleanup

In other words:

- if you care most about purity, bias smaller
- if you care most about throughput, bias larger
- if the beam is sensitive to alignment, avoid choosing a radius that only barely clears the central lobe

## Notes

- This is a fast design-level simulation, not a full diffraction-limited hardware model.
- It assumes the unwanted spatial structure can be approximated by low-order Hermite-Gaussian content.
- The pinhole is modeled directly in the Fourier plane as a hard circular aperture.
- The script also estimates mode purity versus focused spot size for a `20 mm` objective using `w_focus = lambda * f / (pi * w_in)`.
- It exports the focal-plane intensity distribution and enclosed-power-versus-radius so you can choose a practical pinhole size from the simulated spot.
