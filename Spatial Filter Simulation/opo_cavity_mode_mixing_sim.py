from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


@dataclass(frozen=True)
class ModeIndex:
    nx: int
    ny: int


DEFAULT_BASIS = (
    ModeIndex(0, 0),
    ModeIndex(1, 0),
    ModeIndex(0, 1),
    ModeIndex(2, 0),
    ModeIndex(1, 1),
    ModeIndex(0, 2),
)


def style_matplotlib() -> None:
    plt.style.use("default")
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.grid": True,
            "grid.alpha": 0.2,
            "grid.linestyle": "--",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "font.size": 10,
            "axes.titlesize": 14,
            "axes.labelsize": 11,
            "savefig.dpi": 220,
        }
    )


def hermite_physicist(n: int, x: np.ndarray) -> np.ndarray:
    if n == 0:
        return np.ones_like(x)
    if n == 1:
        return 2.0 * x
    hm2 = np.ones_like(x)
    hm1 = 2.0 * x
    for k in range(1, n):
        h = 2.0 * x * hm1 - 2.0 * k * hm2
        hm2 = hm1
        hm1 = h
    return hm1


def hg_field_1d(n: int, x: np.ndarray, waist: float) -> np.ndarray:
    xi = np.sqrt(2.0) * x / waist
    normalization = 1.0 / math.sqrt((2**n) * math.factorial(n) * math.sqrt(math.pi) * waist)
    return normalization * hermite_physicist(n, xi) * np.exp(-(x**2) / (waist**2))


def hg_field_2d(nx: int, ny: int, x: np.ndarray, y: np.ndarray, wx: float, wy: float) -> np.ndarray:
    return np.outer(hg_field_1d(ny, y, wy), hg_field_1d(nx, x, wx))


def normalize_mode_field(field: np.ndarray, spacing: float) -> np.ndarray:
    norm = math.sqrt(power(field, spacing))
    if norm <= 0:
        return field
    return field / norm


def basis_fields(
    basis: tuple[ModeIndex, ...],
    x: np.ndarray,
    y: np.ndarray,
    wx: float,
    wy: float,
    spacing: float,
) -> dict[tuple[int, int], np.ndarray]:
    fields: dict[tuple[int, int], np.ndarray] = {}
    orthonormal_fields: list[np.ndarray] = []
    for mode in basis:
        field = hg_field_2d(mode.nx, mode.ny, x, y, wx, wy)
        field = field.astype(np.complex128)
        for previous in orthonormal_fields:
            overlap = np.sum(np.conjugate(previous) * field) * spacing * spacing
            field = field - overlap * previous
        field = normalize_mode_field(field, spacing)
        orthonormal_fields.append(field)
        fields[(mode.nx, mode.ny)] = field
    return fields


def power(field: np.ndarray, spacing: float) -> float:
    return float(np.sum(np.abs(field) ** 2) * spacing * spacing)


def normalize_field(field: np.ndarray, spacing: float) -> np.ndarray:
    total = power(field, spacing)
    if total <= 0:
        return field
    return field / math.sqrt(total)


def project(field: np.ndarray, basis: dict[tuple[int, int], np.ndarray], spacing: float) -> dict[tuple[int, int], complex]:
    projections: dict[tuple[int, int], complex] = {}
    for key, mode_field in basis.items():
        projections[key] = np.sum(np.conjugate(mode_field) * field) * spacing * spacing
    return projections


def reconstruct(projections: dict[tuple[int, int], complex], basis: dict[tuple[int, int], np.ndarray]) -> np.ndarray:
    field = np.zeros_like(next(iter(basis.values())), dtype=np.complex128)
    for key, coeff in projections.items():
        field = field + coeff * basis[key]
    return field


def round_trip_operator(
    x: np.ndarray,
    y: np.ndarray,
    wx: float,
    wy: float,
    tilt_x_urad: float,
    tilt_y_urad: float,
    thermal_lens_f_m: float,
    aperture_radius_um: float,
    wavelength_m: float,
) -> np.ndarray:
    xx, yy = np.meshgrid(x, y)
    k = 2.0 * math.pi / wavelength_m

    tilt_phase = np.exp(1j * k * (tilt_x_urad * 1e-6 * xx + tilt_y_urad * 1e-6 * yy))

    if thermal_lens_f_m > 0:
        lens_phase = np.exp(-1j * k * (xx**2 + yy**2) / thermal_lens_f_m)
    else:
        lens_phase = np.ones_like(xx, dtype=np.complex128)

    if aperture_radius_um > 0:
        aperture_radius_m = aperture_radius_um * 1e-6
        aperture = ((xx**2 + yy**2) <= aperture_radius_m**2).astype(np.complex128)
    else:
        aperture = np.ones_like(xx, dtype=np.complex128)

    return tilt_phase * lens_phase * aperture


def iterate_cavity_mode(
    basis: dict[tuple[int, int], np.ndarray],
    perturbation: np.ndarray,
    spacing: float,
    iterations: int,
) -> tuple[np.ndarray, dict[tuple[int, int], complex]]:
    coeffs: dict[tuple[int, int], complex] = {(0, 0): 1.0 + 0j}
    for key in basis:
        coeffs.setdefault(key, 0j)

    field = reconstruct(coeffs, basis)
    field = normalize_field(field, spacing)

    for _ in range(iterations):
        updated = field * perturbation
        coeffs = project(updated, basis, spacing)
        field = reconstruct(coeffs, basis)
        field = normalize_field(field, spacing)

    final_coeffs = project(field, basis, spacing)
    return field, final_coeffs


def coefficients_to_powers(coeffs: dict[tuple[int, int], complex]) -> dict[tuple[int, int], float]:
    raw = {key: float(abs(value) ** 2) for key, value in coeffs.items()}
    total = sum(raw.values())
    if total <= 0:
        return raw
    return {key: value / total for key, value in raw.items()}


def cavity_waist_from_geometry(wavelength_m: float, cavity_length_m: float, mirror_radius_m: float) -> float:
    g = 1.0 - cavity_length_m / mirror_radius_m
    if not (0.0 < g < 1.0):
        raise ValueError("Cavity geometry must satisfy 0 < 1 - L/R < 1 for this simple symmetric model.")
    return math.sqrt((wavelength_m * cavity_length_m / math.pi) * math.sqrt(1.0 / (1.0 - g**2)))


def save_csv(rows: list[dict[str, float | int]], path: Path) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def plot_metric_sweep(
    x_values: np.ndarray,
    purity: np.ndarray,
    higher_order: np.ndarray,
    x_label: str,
    title: str,
    output_path: Path,
) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(8, 8), sharex=True)
    axes[0].plot(x_values, purity, color="#005f73", linewidth=2.0)
    axes[0].set_ylabel("TEM00 Purity")
    axes[0].set_ylim(0.0, 1.02)
    axes[0].set_title(title)

    axes[1].plot(x_values, higher_order, color="#bb3e03", linewidth=2.0)
    axes[1].set_ylabel("Higher-Order Content")
    axes[1].set_xlabel(x_label)
    axes[1].set_ylim(0.0, 1.02)

    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def dominant_mode_lines(mode_powers: dict[tuple[int, int], float]) -> list[str]:
    lines: list[str] = []
    for (nx, ny), value in sorted(mode_powers.items(), key=lambda item: item[1], reverse=True):
        lines.append(f"TEM{nx}{ny}: {value:.6f}")
    return lines


def run_sweep(
    sweep_values: np.ndarray,
    sweep_name: str,
    basis: dict[tuple[int, int], np.ndarray],
    x: np.ndarray,
    y: np.ndarray,
    spacing: float,
    wx: float,
    wy: float,
    wavelength_m: float,
    fixed_tilt_x_urad: float,
    fixed_tilt_y_urad: float,
    fixed_thermal_lens_f_m: float,
    fixed_aperture_radius_um: float,
    iterations: int,
) -> tuple[list[dict[str, float | int]], np.ndarray, np.ndarray]:
    rows: list[dict[str, float | int]] = []
    purity_values: list[float] = []
    higher_order_values: list[float] = []

    for value in sweep_values:
        tilt_x = fixed_tilt_x_urad
        tilt_y = fixed_tilt_y_urad
        thermal_lens_f_m = fixed_thermal_lens_f_m
        aperture_radius_um = fixed_aperture_radius_um

        if sweep_name == "mirror_tilt_urad":
            tilt_x = float(value)
        elif sweep_name == "thermal_lens_f_mm":
            thermal_lens_f_m = float(value) * 1e-3
        elif sweep_name == "aperture_radius_um":
            aperture_radius_um = float(value)

        perturbation = round_trip_operator(
            x,
            y,
            wx,
            wy,
            tilt_x,
            tilt_y,
            thermal_lens_f_m,
            aperture_radius_um,
            wavelength_m,
        )
        _, coeffs = iterate_cavity_mode(basis, perturbation, spacing, iterations)
        mode_powers = coefficients_to_powers(coeffs)
        tem00_purity = mode_powers.get((0, 0), 0.0)
        higher_order = max(0.0, 1.0 - tem00_purity)

        row: dict[str, float | int] = {
            sweep_name: float(value),
            "tem00_purity": tem00_purity,
            "higher_order_content": higher_order,
        }
        for key, mode_power in sorted(mode_powers.items()):
            row[f"tem{key[0]}{key[1]}"] = mode_power
        rows.append(row)
        purity_values.append(tem00_purity)
        higher_order_values.append(higher_order)

    return rows, np.asarray(purity_values), np.asarray(higher_order_values)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prototype OPO cavity transverse mode-mixing simulator in a low-order Hermite-Gaussian basis."
    )
    parser.add_argument("--output-dir", type=Path, default=Path("opo_output"), help="Output directory.")
    parser.add_argument("--wavelength-nm", type=float, default=1064.0, help="Wavelength in nm.")
    parser.add_argument("--cavity-length-mm", type=float, default=80.0, help="Cavity length in mm.")
    parser.add_argument("--mirror-radius-mm", type=float, default=100.0, help="Mirror radius of curvature in mm.")
    parser.add_argument("--grid-size", type=int, default=351, help="Simulation grid size.")
    parser.add_argument("--window-radius-um", type=float, default=250.0, help="Simulation half-width in um.")
    parser.add_argument("--iterations", type=int, default=40, help="Round-trip iterations.")
    parser.add_argument("--tilt-x-urad", type=float, default=0.0, help="Fixed x tilt in urad.")
    parser.add_argument("--tilt-y-urad", type=float, default=0.0, help="Fixed y tilt in urad.")
    parser.add_argument("--thermal-lens-f-mm", type=float, default=1.0e6, help="Thermal lens focal length in mm.")
    parser.add_argument(
        "--aperture-radius-um",
        type=float,
        default=500.0,
        help="Aperture radius in um. Use a large value to approximate no clipping.",
    )
    parser.add_argument("--tilt-sweep-max-urad", type=float, default=250.0, help="Tilt sweep max in urad.")
    parser.add_argument("--tilt-sweep-steps", type=int, default=50, help="Number of tilt sweep points.")
    parser.add_argument(
        "--thermal-lens-sweep-start-mm",
        type=float,
        default=20.0,
        help="Thermal lens sweep start in mm.",
    )
    parser.add_argument(
        "--thermal-lens-sweep-stop-mm",
        type=float,
        default=500.0,
        help="Thermal lens sweep stop in mm.",
    )
    parser.add_argument(
        "--thermal-lens-sweep-steps",
        type=int,
        default=50,
        help="Number of thermal lens sweep points.",
    )
    parser.add_argument(
        "--aperture-sweep-start-um",
        type=float,
        default=40.0,
        help="Aperture sweep start in um.",
    )
    parser.add_argument(
        "--aperture-sweep-stop-um",
        type=float,
        default=220.0,
        help="Aperture sweep stop in um.",
    )
    parser.add_argument(
        "--aperture-sweep-steps",
        type=int,
        default=50,
        help="Number of aperture sweep points.",
    )
    args = parser.parse_args()

    style_matplotlib()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    wavelength_m = args.wavelength_nm * 1e-9
    cavity_length_m = args.cavity_length_mm * 1e-3
    mirror_radius_m = args.mirror_radius_mm * 1e-3
    wx = cavity_waist_from_geometry(wavelength_m, cavity_length_m, mirror_radius_m)
    wy = wx

    axis = np.linspace(-args.window_radius_um * 1e-6, args.window_radius_um * 1e-6, args.grid_size, dtype=float)
    spacing = float(axis[1] - axis[0])
    basis = basis_fields(DEFAULT_BASIS, axis, axis, wx, wy, spacing)

    baseline_perturbation = round_trip_operator(
        axis,
        axis,
        wx,
        wy,
        args.tilt_x_urad,
        args.tilt_y_urad,
        args.thermal_lens_f_mm * 1e-3,
        args.aperture_radius_um,
        wavelength_m,
    )
    _, baseline_coeffs = iterate_cavity_mode(basis, baseline_perturbation, spacing, args.iterations)
    baseline_powers = coefficients_to_powers(baseline_coeffs)

    tilt_sweep = np.linspace(0.0, args.tilt_sweep_max_urad, args.tilt_sweep_steps, dtype=float)
    tilt_rows, tilt_purity, tilt_higher = run_sweep(
        tilt_sweep,
        "mirror_tilt_urad",
        basis,
        axis,
        axis,
        spacing,
        wx,
        wy,
        wavelength_m,
        args.tilt_x_urad,
        args.tilt_y_urad,
        args.thermal_lens_f_mm * 1e-3,
        args.aperture_radius_um,
        args.iterations,
    )
    save_csv(tilt_rows, output_dir / "opo_mode_mixing_vs_tilt.csv")
    plot_metric_sweep(
        tilt_sweep,
        tilt_purity,
        tilt_higher,
        "Mirror Tilt (urad)",
        "OPO Cavity Mode Purity vs Mirror Tilt",
        output_dir / "opo_mode_mixing_vs_tilt.png",
    )

    thermal_sweep = np.linspace(
        args.thermal_lens_sweep_start_mm,
        args.thermal_lens_sweep_stop_mm,
        args.thermal_lens_sweep_steps,
        dtype=float,
    )
    thermal_rows, thermal_purity, thermal_higher = run_sweep(
        thermal_sweep,
        "thermal_lens_f_mm",
        basis,
        axis,
        axis,
        spacing,
        wx,
        wy,
        wavelength_m,
        args.tilt_x_urad,
        args.tilt_y_urad,
        args.thermal_lens_f_mm * 1e-3,
        args.aperture_radius_um,
        args.iterations,
    )
    save_csv(thermal_rows, output_dir / "opo_mode_mixing_vs_thermal_lens.csv")
    plot_metric_sweep(
        thermal_sweep,
        thermal_purity,
        thermal_higher,
        "Thermal Lens Focal Length (mm)",
        "OPO Cavity Mode Purity vs Thermal Lens",
        output_dir / "opo_mode_mixing_vs_thermal_lens.png",
    )

    aperture_sweep = np.linspace(
        args.aperture_sweep_start_um,
        args.aperture_sweep_stop_um,
        args.aperture_sweep_steps,
        dtype=float,
    )
    aperture_rows, aperture_purity, aperture_higher = run_sweep(
        aperture_sweep,
        "aperture_radius_um",
        basis,
        axis,
        axis,
        spacing,
        wx,
        wy,
        wavelength_m,
        args.tilt_x_urad,
        args.tilt_y_urad,
        args.thermal_lens_f_mm * 1e-3,
        args.aperture_radius_um,
        args.iterations,
    )
    save_csv(aperture_rows, output_dir / "opo_mode_mixing_vs_aperture.csv")
    plot_metric_sweep(
        aperture_sweep,
        aperture_purity,
        aperture_higher,
        "Aperture Radius (um)",
        "OPO Cavity Mode Purity vs Aperture Clipping",
        output_dir / "opo_mode_mixing_vs_aperture.png",
    )

    summary_lines = [
        "OPO Cavity Mode Mixing Simulation",
        f"Wavelength: {args.wavelength_nm:.2f} nm",
        f"Cavity length: {args.cavity_length_mm:.2f} mm",
        f"Mirror ROC: {args.mirror_radius_mm:.2f} mm",
        f"Estimated cavity waist: {wx * 1e6:.2f} um",
        "",
        "Baseline dominant mode content:",
        *dominant_mode_lines(baseline_powers),
        "",
        "Generated files:",
        "- opo_mode_mixing_vs_tilt.csv",
        "- opo_mode_mixing_vs_tilt.png",
        "- opo_mode_mixing_vs_thermal_lens.csv",
        "- opo_mode_mixing_vs_thermal_lens.png",
        "- opo_mode_mixing_vs_aperture.csv",
        "- opo_mode_mixing_vs_aperture.png",
        "",
        "Interpretation note:",
        "The default settings are intended to represent a reasonably healthy cavity with minimal clipping.",
    ]
    (output_dir / "README_results.txt").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
