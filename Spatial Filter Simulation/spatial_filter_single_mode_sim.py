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
class ModeComponent:
    nx: int
    ny: int
    power_fraction: float


DEFAULT_MODES = (
    ModeComponent(0, 0, 0.78),
    ModeComponent(1, 0, 0.08),
    ModeComponent(0, 1, 0.08),
    ModeComponent(2, 0, 0.03),
    ModeComponent(0, 2, 0.03),
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


def hg_field_2d(nx: int, ny: int, x: np.ndarray, y: np.ndarray, waist: float) -> np.ndarray:
    return np.outer(hg_field_1d(ny, y, waist), hg_field_1d(nx, x, waist))


def circular_mask(x: np.ndarray, y: np.ndarray, radius: float, dx: float, dy: float) -> np.ndarray:
    xx, yy = np.meshgrid(x - dx, y - dy)
    return (xx**2 + yy**2) <= radius**2


def power_of_field(field: np.ndarray, spacing: float) -> float:
    return float(np.sum(np.abs(field) ** 2) * spacing * spacing)


def normalize_components(components: list[ModeComponent]) -> list[ModeComponent]:
    total = sum(component.power_fraction for component in components)
    if total <= 0:
        raise ValueError("Mode powers must sum to a positive number.")
    return [
        ModeComponent(component.nx, component.ny, component.power_fraction / total)
        for component in components
    ]


def build_mode_basis(
    components: list[ModeComponent], grid_size: int, window_radius: float, waist: float
) -> tuple[np.ndarray, np.ndarray, dict[tuple[int, int], np.ndarray], float]:
    axis = np.linspace(-window_radius, window_radius, grid_size, dtype=float)
    spacing = float(axis[1] - axis[0])
    basis: dict[tuple[int, int], np.ndarray] = {}
    for component in components:
        basis[(component.nx, component.ny)] = hg_field_2d(component.nx, component.ny, axis, axis, waist)
    return axis, axis, basis, spacing


def filter_transmission(
    field: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    pinhole_radius: float,
    spacing: float,
    dx: float,
    dy: float,
) -> tuple[np.ndarray, float]:
    mask = circular_mask(x, y, pinhole_radius, dx, dy)
    transmitted = field * mask
    return transmitted, power_of_field(transmitted, spacing)


def parse_mode_spec(spec: str) -> list[ModeComponent]:
    components: list[ModeComponent] = []
    for chunk in spec.split(","):
        parts = [part.strip() for part in chunk.split(":")]
        if len(parts) != 3:
            raise ValueError(
                "Each mode must be specified as nx:ny:power_fraction, for example 0:0:0.8"
            )
        nx, ny = int(parts[0]), int(parts[1])
        power_fraction = float(parts[2])
        components.append(ModeComponent(nx, ny, power_fraction))
    return normalize_components(components)


def project_onto_basis(
    filtered_field: np.ndarray,
    basis: dict[tuple[int, int], np.ndarray],
    spacing: float,
) -> dict[tuple[int, int], float]:
    projections: dict[tuple[int, int], float] = {}
    for key, mode_field in basis.items():
        overlap = np.sum(np.conjugate(mode_field) * filtered_field) * spacing * spacing
        projections[key] = float(np.abs(overlap) ** 2)
    return projections


def make_input_field(
    components: list[ModeComponent],
    basis: dict[tuple[int, int], np.ndarray],
) -> np.ndarray:
    field = np.zeros_like(next(iter(basis.values())))
    for component in components:
        amplitude = math.sqrt(component.power_fraction)
        field = field + amplitude * basis[(component.nx, component.ny)]
    return field


def save_csv(rows: list[dict[str, float | int]], path: Path) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def plot_results(
    pinhole_radii_um: np.ndarray,
    total_transmission: np.ndarray,
    tem00_efficiency: np.ndarray,
    tem00_purity: np.ndarray,
    output_path: Path,
) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(8, 10), sharex=True)

    axes[0].plot(pinhole_radii_um, total_transmission, color="#005f73", linewidth=2.0)
    axes[0].set_ylabel("Total Transmission")
    axes[0].set_ylim(0.0, 1.02)
    axes[0].set_title("Spatial Filter Sweep for Single-Mode Cleanup")

    axes[1].plot(pinhole_radii_um, tem00_efficiency, color="#0a9396", linewidth=2.0)
    axes[1].set_ylabel("TEM00 Transmission")
    axes[1].set_ylim(0.0, 1.02)

    axes[2].plot(pinhole_radii_um, tem00_purity, color="#bb3e03", linewidth=2.0)
    axes[2].set_ylabel("TEM00 Purity")
    axes[2].set_xlabel("Pinhole Radius in Fourier Plane (um)")
    axes[2].set_ylim(0.0, 1.02)

    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def plot_purity_vs_focus_spot(
    focus_spot_radius_um: np.ndarray,
    best_tem00_purity: np.ndarray,
    best_tem00_transmission: np.ndarray,
    objective_beam_radius_mm: np.ndarray,
    output_path: Path,
) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(8, 10), sharex=True)

    axes[0].plot(focus_spot_radius_um, best_tem00_purity, color="#9b2226", linewidth=2.0)
    axes[0].set_ylabel("Best TEM00 Purity")
    axes[0].set_ylim(0.0, 1.02)
    axes[0].set_title("Mode Purity vs Focused Spot Size for a 20 mm Objective")

    axes[1].plot(focus_spot_radius_um, best_tem00_transmission, color="#0a9396", linewidth=2.0)
    axes[1].set_ylabel("Best TEM00 Transmission")
    axes[1].set_ylim(0.0, 1.02)

    axes[2].plot(focus_spot_radius_um, objective_beam_radius_mm, color="#005f73", linewidth=2.0)
    axes[2].set_ylabel("Required Beam Radius on Objective (mm)")
    axes[2].set_xlabel("Focused TEM00 1/e Field Radius (um)")

    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def plot_example_fields(
    x_um: np.ndarray,
    input_intensity: np.ndarray,
    filtered_intensity: np.ndarray,
    mask: np.ndarray,
    output_path: Path,
) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.8))
    images = (
        (input_intensity, "Input Intensity"),
        (mask.astype(float), "Pinhole Mask"),
        (filtered_intensity, "Filtered Intensity"),
    )
    for axis, (data, title) in zip(axes, images):
        image = axis.imshow(
            data,
            extent=[x_um[0], x_um[-1], x_um[0], x_um[-1]],
            origin="lower",
            cmap="magma",
            aspect="equal",
        )
        axis.set_title(title)
        axis.set_xlabel("x (um)")
        axis.set_ylabel("y (um)")
        fig.colorbar(image, ax=axis, fraction=0.046, pad=0.04)

    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def radial_enclosed_power(
    x: np.ndarray,
    y: np.ndarray,
    intensity: np.ndarray,
    radii: np.ndarray,
    dx: float,
    dy: float,
    spacing: float,
) -> np.ndarray:
    xx, yy = np.meshgrid(x - dx, y - dy)
    total_power = float(np.sum(intensity) * spacing * spacing)
    if total_power <= 0:
        return np.zeros_like(radii)

    enclosed: list[float] = []
    for radius in radii:
        mask = (xx**2 + yy**2) <= radius**2
        enclosed_power = float(np.sum(intensity[mask]) * spacing * spacing)
        enclosed.append(enclosed_power / total_power)
    return np.asarray(enclosed)


def find_radius_for_fraction(radii: np.ndarray, enclosed: np.ndarray, fraction: float) -> float:
    index = int(np.searchsorted(enclosed, fraction, side="left"))
    index = min(index, len(radii) - 1)
    return float(radii[index])


def plot_focal_plane_distribution(
    x_um: np.ndarray,
    intensity: np.ndarray,
    candidate_radii_um: list[float],
    output_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(6.2, 5.6))
    image = ax.imshow(
        intensity,
        extent=[x_um[0], x_um[-1], x_um[0], x_um[-1]],
        origin="lower",
        cmap="magma",
        aspect="equal",
    )
    for radius_um, color in zip(candidate_radii_um, ("#0a9396", "#ee9b00", "#bb3e03")):
        circle = plt.Circle((0.0, 0.0), radius_um, fill=False, color=color, linewidth=2.0)
        ax.add_patch(circle)
        ax.text(radius_um * 0.72, radius_um * 0.1, f"{radius_um:.1f} um", color=color, fontsize=9)

    ax.set_title("Focal-Plane Intensity with Candidate Pinhole Radii")
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04, label="Relative Intensity")
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def plot_enclosed_power(
    radii_um: np.ndarray,
    enclosed_total: np.ndarray,
    enclosed_tem00: np.ndarray,
    best_radius_um: float,
    output_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(7.4, 5.0))
    ax.plot(radii_um, enclosed_total, color="#005f73", linewidth=2.0, label="Total Beam")
    ax.plot(radii_um, enclosed_tem00, color="#bb3e03", linewidth=2.0, label="TEM00 Only")
    ax.axvline(best_radius_um, color="#0a9396", linestyle="--", linewidth=1.8, label="Best Radius")
    ax.set_title("Enclosed Power vs Pinhole Radius at Focal Plane")
    ax.set_xlabel("Radius (um)")
    ax.set_ylabel("Enclosed Power Fraction")
    ax.set_ylim(0.0, 1.02)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Simulate a Fourier-plane spatial filter that keeps the fundamental TEM00 mode "
            "while rejecting higher-order Hermite-Gaussian content."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for CSV and plot outputs.",
    )
    parser.add_argument(
        "--waist-um",
        type=float,
        default=80.0,
        help="1/e field waist in the Fourier plane in microns.",
    )
    parser.add_argument(
        "--window-radius-um",
        type=float,
        default=300.0,
        help="Half-width of the simulation window in microns.",
    )
    parser.add_argument(
        "--grid-size",
        type=int,
        default=401,
        help="Square grid size. Larger values are slower but more accurate.",
    )
    parser.add_argument(
        "--radius-start-um",
        type=float,
        default=20.0,
        help="Start of the pinhole-radius sweep in microns.",
    )
    parser.add_argument(
        "--radius-stop-um",
        type=float,
        default=180.0,
        help="End of the pinhole-radius sweep in microns.",
    )
    parser.add_argument(
        "--radius-steps",
        type=int,
        default=60,
        help="Number of radii to evaluate.",
    )
    parser.add_argument(
        "--offset-x-um",
        type=float,
        default=0.0,
        help="Pinhole x misalignment in microns.",
    )
    parser.add_argument(
        "--offset-y-um",
        type=float,
        default=0.0,
        help="Pinhole y misalignment in microns.",
    )
    parser.add_argument(
        "--modes",
        type=str,
        default=",".join(f"{mode.nx}:{mode.ny}:{mode.power_fraction}" for mode in DEFAULT_MODES),
        help=(
            "Comma-separated Hermite-Gaussian content as nx:ny:power_fraction. "
            "Example: 0:0:0.8,1:0:0.1,0:1:0.1"
        ),
    )
    parser.add_argument(
        "--wavelength-nm",
        type=float,
        default=1064.0,
        help="Laser wavelength in nm for converting focus spot size to beam size on the objective.",
    )
    parser.add_argument(
        "--objective-focal-length-mm",
        type=float,
        default=20.0,
        help="Objective focal length in mm for the focus-spot calculation.",
    )
    parser.add_argument(
        "--focus-spot-start-um",
        type=float,
        default=8.0,
        help="Start of focused TEM00 1/e field radius sweep in microns.",
    )
    parser.add_argument(
        "--focus-spot-stop-um",
        type=float,
        default=80.0,
        help="End of focused TEM00 1/e field radius sweep in microns.",
    )
    parser.add_argument(
        "--focus-spot-steps",
        type=int,
        default=36,
        help="Number of focused spot sizes to evaluate.",
    )
    parser.add_argument(
        "--distribution-radius-steps",
        type=int,
        default=120,
        help="Number of radii used for enclosed-power and focal-plane sizing outputs.",
    )
    args = parser.parse_args()

    style_matplotlib()

    components = parse_mode_spec(args.modes)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    waist = args.waist_um * 1e-6
    window_radius = args.window_radius_um * 1e-6
    offset_x = args.offset_x_um * 1e-6
    offset_y = args.offset_y_um * 1e-6

    x, y, basis, spacing = build_mode_basis(components, args.grid_size, window_radius, waist)
    input_field = make_input_field(components, basis)
    input_power = power_of_field(input_field, spacing)
    input_tem00_power = components[0].power_fraction if (components[0].nx, components[0].ny) == (0, 0) else 0.0

    radii = np.linspace(args.radius_start_um, args.radius_stop_um, args.radius_steps, dtype=float) * 1e-6

    rows: list[dict[str, float | int]] = []
    total_transmission: list[float] = []
    tem00_efficiency: list[float] = []
    tem00_purity: list[float] = []

    best_score = -1.0
    best_radius = radii[0]
    best_filtered_field = input_field
    best_mask = circular_mask(x, y, best_radius, offset_x, offset_y)

    for radius in radii:
        filtered_field, transmitted_power = filter_transmission(
            input_field, x, y, radius, spacing, offset_x, offset_y
        )
        projections = project_onto_basis(filtered_field, basis, spacing)
        tem00_power = projections.get((0, 0), 0.0)
        purity = tem00_power / transmitted_power if transmitted_power > 0 else 0.0
        throughput = transmitted_power / input_power if input_power > 0 else 0.0
        tem00_throughput = tem00_power / input_tem00_power if input_tem00_power > 0 else 0.0
        score = purity * tem00_throughput

        if score > best_score:
            best_score = score
            best_radius = radius
            best_filtered_field = filtered_field.copy()
            best_mask = circular_mask(x, y, radius, offset_x, offset_y)

        total_transmission.append(throughput)
        tem00_efficiency.append(tem00_throughput)
        tem00_purity.append(purity)

        row: dict[str, float | int] = {
            "pinhole_radius_um": radius * 1e6,
            "total_transmission": throughput,
            "tem00_transmission": tem00_throughput,
            "tem00_purity": purity,
            "score_purity_times_transmission": score,
        }
        for key, power in sorted(projections.items()):
            row[f"mode_{key[0]}_{key[1]}_power"] = power
        rows.append(row)

    save_csv(rows, output_dir / "spatial_filter_sweep.csv")

    plot_results(
        radii * 1e6,
        np.asarray(total_transmission),
        np.asarray(tem00_efficiency),
        np.asarray(tem00_purity),
        output_dir / "spatial_filter_sweep.png",
    )

    x_um = x * 1e6
    plot_example_fields(
        x_um,
        np.abs(input_field) ** 2,
        np.abs(best_filtered_field) ** 2,
        best_mask,
        output_dir / "spatial_filter_example_fields.png",
    )

    tem00_only_field = math.sqrt(input_tem00_power) * basis[(0, 0)] if (0, 0) in basis else np.zeros_like(input_field)
    focal_plane_intensity = np.abs(input_field) ** 2
    tem00_only_intensity = np.abs(tem00_only_field) ** 2
    distribution_radii = np.linspace(0.0, args.radius_stop_um * 1e-6, args.distribution_radius_steps, dtype=float)
    enclosed_total = radial_enclosed_power(
        x, y, focal_plane_intensity, distribution_radii, offset_x, offset_y, spacing
    )
    enclosed_tem00 = radial_enclosed_power(
        x, y, tem00_only_intensity, distribution_radii, offset_x, offset_y, spacing
    )

    radius_50_um = find_radius_for_fraction(distribution_radii, enclosed_total, 0.50) * 1e6
    radius_80_um = find_radius_for_fraction(distribution_radii, enclosed_total, 0.80) * 1e6
    radius_95_um = find_radius_for_fraction(distribution_radii, enclosed_total, 0.95) * 1e6
    candidate_radii_um = [radius_50_um, radius_80_um, radius_95_um]

    plot_focal_plane_distribution(
        x_um,
        focal_plane_intensity / np.max(focal_plane_intensity),
        candidate_radii_um,
        output_dir / "focal_plane_mode_distribution.png",
    )
    plot_enclosed_power(
        distribution_radii * 1e6,
        enclosed_total,
        enclosed_tem00,
        best_radius * 1e6,
        output_dir / "focal_plane_enclosed_power.png",
    )

    enclosed_rows: list[dict[str, float | int]] = []
    for radius, total_fraction, tem00_fraction in zip(distribution_radii, enclosed_total, enclosed_tem00):
        enclosed_rows.append(
            {
                "radius_um": radius * 1e6,
                "enclosed_total_power_fraction": float(total_fraction),
                "enclosed_tem00_power_fraction": float(tem00_fraction),
            }
        )
    save_csv(enclosed_rows, output_dir / "focal_plane_enclosed_power.csv")

    wavelength = args.wavelength_nm * 1e-9
    objective_focal_length = args.objective_focal_length_mm * 1e-3
    focus_spot_radii_um = np.linspace(
        args.focus_spot_start_um, args.focus_spot_stop_um, args.focus_spot_steps, dtype=float
    )

    focus_rows: list[dict[str, float | int]] = []
    best_purity_vs_focus: list[float] = []
    best_transmission_vs_focus: list[float] = []
    beam_radius_on_objective_mm: list[float] = []

    for focus_spot_radius_um in focus_spot_radii_um:
        focus_waist = focus_spot_radius_um * 1e-6
        _, _, focus_basis, focus_spacing = build_mode_basis(
            components, args.grid_size, window_radius, focus_waist
        )
        focus_input_field = make_input_field(components, focus_basis)
        focus_input_power = power_of_field(focus_input_field, focus_spacing)
        focus_tem00_input_power = (
            components[0].power_fraction if (components[0].nx, components[0].ny) == (0, 0) else 0.0
        )

        best_focus_purity = 0.0
        best_focus_tem00_transmission = 0.0
        best_focus_total_transmission = 0.0
        best_focus_radius_um = radii[0] * 1e6
        best_focus_score = -1.0

        for radius in radii:
            filtered_field, transmitted_power = filter_transmission(
                focus_input_field,
                x,
                y,
                radius,
                focus_spacing,
                offset_x,
                offset_y,
            )
            projections = project_onto_basis(filtered_field, focus_basis, focus_spacing)
            tem00_power = projections.get((0, 0), 0.0)
            purity = tem00_power / transmitted_power if transmitted_power > 0 else 0.0
            tem00_throughput = (
                tem00_power / focus_tem00_input_power if focus_tem00_input_power > 0 else 0.0
            )
            total_throughput = transmitted_power / focus_input_power if focus_input_power > 0 else 0.0
            score = purity * tem00_throughput

            if score > best_focus_score:
                best_focus_score = score
                best_focus_purity = purity
                best_focus_tem00_transmission = tem00_throughput
                best_focus_total_transmission = total_throughput
                best_focus_radius_um = radius * 1e6

        required_beam_radius = wavelength * objective_focal_length / (math.pi * focus_waist)
        beam_radius_on_objective_mm.append(required_beam_radius * 1e3)
        best_purity_vs_focus.append(best_focus_purity)
        best_transmission_vs_focus.append(best_focus_tem00_transmission)
        focus_rows.append(
            {
                "objective_focal_length_mm": args.objective_focal_length_mm,
                "wavelength_nm": args.wavelength_nm,
                "focus_spot_radius_um": focus_spot_radius_um,
                "focus_spot_diameter_um": 2.0 * focus_spot_radius_um,
                "required_beam_radius_on_objective_mm": required_beam_radius * 1e3,
                "required_beam_diameter_on_objective_mm": required_beam_radius * 2e3,
                "best_pinhole_radius_um": best_focus_radius_um,
                "best_tem00_purity": best_focus_purity,
                "best_tem00_transmission": best_focus_tem00_transmission,
                "best_total_transmission": best_focus_total_transmission,
                "score_purity_times_transmission": best_focus_purity * best_focus_tem00_transmission,
            }
        )

    save_csv(focus_rows, output_dir / "mode_purity_vs_focus_spot_20mm_objective.csv")
    plot_purity_vs_focus_spot(
        focus_spot_radii_um,
        np.asarray(best_purity_vs_focus),
        np.asarray(best_transmission_vs_focus),
        np.asarray(beam_radius_on_objective_mm),
        output_dir / "mode_purity_vs_focus_spot_20mm_objective.png",
    )

    summary_lines = [
        "Spatial Filter Single-Mode Simulation",
        f"Input mode mixture: {args.modes}",
        f"Fourier-plane waist: {args.waist_um:.2f} um",
        f"Best pinhole radius by purity*transmission score: {best_radius * 1e6:.2f} um",
        f"Radius for 50% enclosed total power: {radius_50_um:.2f} um",
        f"Radius for 80% enclosed total power: {radius_80_um:.2f} um",
        f"Radius for 95% enclosed total power: {radius_95_um:.2f} um",
        f"Pinhole offset: ({args.offset_x_um:.2f} um, {args.offset_y_um:.2f} um)",
        f"Objective focal length: {args.objective_focal_length_mm:.2f} mm",
        f"Wavelength: {args.wavelength_nm:.2f} nm",
        "",
        "Generated files:",
        "- spatial_filter_sweep.csv",
        "- spatial_filter_sweep.png",
        "- spatial_filter_example_fields.png",
        "- focal_plane_mode_distribution.png",
        "- focal_plane_enclosed_power.csv",
        "- focal_plane_enclosed_power.png",
        "- mode_purity_vs_focus_spot_20mm_objective.csv",
        "- mode_purity_vs_focus_spot_20mm_objective.png",
    ]
    if np.isclose(best_radius, radii[0]) or np.isclose(best_radius, radii[-1]):
        summary_lines.extend(
            [
                "",
                "Note:",
                "The best score landed on the sweep boundary. Expand the radius range to confirm the true optimum.",
            ]
        )
    (output_dir / "README_results.txt").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
