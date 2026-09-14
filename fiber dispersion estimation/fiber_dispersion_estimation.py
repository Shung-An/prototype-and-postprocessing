"""PM780-HP fiber plus SF11 optical rod dispersion estimate.

The script calculates interpolated PM780-HP fiber dispersion, estimates the
fiber and SF11 optical rod GDD, and plots pulse duration vs wavelength.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import NamedTuple

import matplotlib.pyplot as plt
import numpy as np


class SimulationResult(NamedTuple):
    wavelength_nm: np.ndarray
    fiber_model: str
    fiber_length_m: float
    rod_length_mm: float
    grating_lines_per_mm: float
    pulse_duration_fs: float
    l_eff_m: np.ndarray
    interp_dispersion: np.ndarray
    gdd_fiber_fs2: np.ndarray
    gdd_rod_fs2: np.ndarray
    gdd_total_fs2: np.ndarray
    tod_fiber_fs3: np.ndarray
    gdd_grating_fs2: np.ndarray
    tod_grating_fs3: np.ndarray
    pulse_duration_fiber_ps: np.ndarray
    pulse_duration_fiber_rod_ps: np.ndarray
    pulse_duration_grating_fiber_ps: np.ndarray


PM780_HP_WAVELENGTH_NM = np.array(
    [
        600.07,
        615.09,
        630.11,
        647.28,
        665.54,
        683.8,
        703.14,
        724.64,
        746.14,
        768.73,
        792.4,
        816.07,
        840.82,
        866.65,
        891.41,
        916.17,
        942.02,
        967.86,
        992.63,
    ],
    dtype=float,
)

PM780_HP_DISPERSION_PS_PER_NM_KM = np.array(
    [
        -302.97,
        -281.09,
        -258.13,
        -237.34,
        -216.56,
        -196.88,
        -179.38,
        -162.97,
        -147.66,
        -133.44,
        -120.31,
        -109.38,
        -98.44,
        -88.59,
        -80.94,
        -73.28,
        -66.72,
        -60.16,
        -54.69,
    ],
    dtype=float,
)

S630_HP_WAVELENGTH_NM = np.arange(600, 1601, 10, dtype=float)
S630_HP_DISPERSION_PS_PER_NM_KM = np.array(
    [
        -323.3,
        -307.3,
        -292.5,
        -278.6,
        -265.7,
        -253.6,
        -242.3,
        -231.7,
        -221.8,
        -212.4,
        -203.7,
        -195.4,
        -187.7,
        -180.4,
        -173.5,
        -167.0,
        -160.8,
        -155.0,
        -149.4,
        -144.2,
        -139.2,
        -134.5,
        -130.0,
        -125.7,
        -121.6,
        -117.7,
        -113.9,
        -110.4,
        -106.9,
        -103.6,
        -100.5,
        -97.4,
        -94.5,
        -91.7,
        -89.0,
        -86.4,
        -83.8,
        -81.4,
        -79.0,
        -76.6,
        -74.4,
        -72.2,
        -70.1,
        -68.0,
        -66.0,
        -64.0,
        -62.1,
        -60.2,
        -58.3,
        -56.5,
        -54.7,
        -52.9,
        -51.2,
        -49.5,
        -47.8,
        -46.2,
        -44.5,
        -42.9,
        -41.3,
        -39.7,
        -38.2,
        -36.6,
        -35.1,
        -33.6,
        -32.1,
        -30.6,
        -29.1,
        -27.7,
        -26.2,
        -24.8,
        -23.4,
        -22.0,
        -20.6,
        -19.2,
        -17.8,
        -16.5,
        -15.1,
        -13.8,
        -12.4,
        -11.2,
        -9.8,
        -8.5,
        -7.3,
        -5.9,
        -4.7,
        -3.5,
        -2.2,
        -1.0,
        0.3,
        1.5,
        2.7,
        3.9,
        5.1,
        6.3,
        7.5,
        8.6,
        9.8,
        10.9,
        12.1,
        13.2,
        14.3,
    ],
    dtype=float,
)

FIBER_DATASETS = {
    "pm780_hp": (
        "PM780-HP",
        PM780_HP_WAVELENGTH_NM,
        PM780_HP_DISPERSION_PS_PER_NM_KM,
    ),
    "s630_hp": (
        "S630-HP",
        S630_HP_WAVELENGTH_NM,
        S630_HP_DISPERSION_PS_PER_NM_KM,
    ),
}

# SCHOTT SF11 Sellmeier coefficients, with wavelength in micrometers.
SF11_B = np.array([1.73759695, 0.313747346, 1.89878101], dtype=float)
SF11_C_UM2 = np.array([0.013188707, 0.0623068142, 155.23629], dtype=float)


def sf11_refractive_index(wavelength_nm: np.ndarray) -> np.ndarray:
    wavelength_um = wavelength_nm * 1e-3
    wavelength_um2 = wavelength_um**2
    n2 = 1 + np.sum(
        SF11_B[:, None] * wavelength_um2[None, :]
        / (wavelength_um2[None, :] - SF11_C_UM2[:, None]),
        axis=0,
    )
    return np.sqrt(n2)


def sf11_gdd(wavelength_nm: np.ndarray, rod_length_mm: float) -> np.ndarray:
    c_m_per_s = 299_792_458.0
    wavelength_m = wavelength_nm * 1e-9
    omega = 2 * np.pi * c_m_per_s / wavelength_m
    refractive_index = sf11_refractive_index(wavelength_nm)
    wave_number = refractive_index * omega / c_m_per_s

    sort_idx = np.argsort(omega)
    omega_sorted = omega[sort_idx]
    wave_number_sorted = wave_number[sort_idx]
    dk_domega = np.gradient(wave_number_sorted, omega_sorted, edge_order=2)
    k2_s2_per_m = np.gradient(dk_domega, omega_sorted, edge_order=2)

    gdd_sorted_fs2 = k2_s2_per_m * (rod_length_mm * 1e-3) * 1e30
    gdd_fs2 = np.empty_like(gdd_sorted_fs2)
    gdd_fs2[sort_idx] = gdd_sorted_fs2
    return gdd_fs2


def spline_interpolate(x: np.ndarray, y: np.ndarray, x_new: np.ndarray) -> np.ndarray:
    """Match MATLAB interp1(..., 'spline') when SciPy is available."""
    try:
        from scipy.interpolate import CubicSpline
    except ImportError:
        print("SciPy not found; falling back to linear interpolation.")
        return np.interp(x_new, x, y)

    return CubicSpline(x, y, bc_type="not-a-knot")(x_new)


def run_simulation(
    wavelength_start_nm: float | None = None,
    wavelength_stop_nm: float | None = None,
    wavelength_step_nm: float = 1,
    fiber_model: str = "pm780_hp",
    fiber_length_m: float = 1,
    gdd_offset_fs2: float = 0,
    grating_lines_per_mm: float = 1200,
    pulse_duration_fs: float = 100,
    rod_length_mm: float = 300,
    l_eff_start_m: float = 0.20,
    l_eff_stop_m: float = 0.74,
    l_eff_count: int = 120,
) -> SimulationResult:
    if fiber_model not in FIBER_DATASETS:
        supported = ", ".join(sorted(FIBER_DATASETS))
        raise ValueError(f"Unsupported fiber model {fiber_model!r}. Use one of: {supported}")

    fiber_label, source_wavelength_nm, source_dispersion = FIBER_DATASETS[fiber_model]
    wavelength_start_nm = (
        source_wavelength_nm.min() if wavelength_start_nm is None else wavelength_start_nm
    )
    wavelength_stop_nm = (
        source_wavelength_nm.max() if wavelength_stop_nm is None else wavelength_stop_nm
    )
    wavelength_nm = np.arange(
        wavelength_start_nm, wavelength_stop_nm + wavelength_step_nm, wavelength_step_nm
    )
    interp_dispersion = spline_interpolate(source_wavelength_nm, source_dispersion, wavelength_nm)

    c_m_per_s = 3e8
    diffraction_order = -1
    grating_spacing_nm = 1 / grating_lines_per_mm * 1e6
    sin_theta = wavelength_nm / (2 * grating_spacing_nm)
    wavelength_m = wavelength_nm * 1e-9
    l_eff_m = np.linspace(l_eff_start_m, l_eff_stop_m, l_eff_count)

    gvd_fiber_fs2_per_m = (
        -(wavelength_nm**2) / (2 * np.pi * c_m_per_s) * interp_dispersion * 1e6
    )
    gdd_fiber_fs2 = gvd_fiber_fs2_per_m * fiber_length_m + gdd_offset_fs2
    gdd_rod_fs2 = sf11_gdd(wavelength_nm, rod_length_mm)
    gdd_total_fs2 = gdd_fiber_fs2 + gdd_rod_fs2
    pulse_duration_fiber_ps = np.sqrt(
        pulse_duration_fs**2
        + (4 * np.log(2) * gdd_fiber_fs2 / pulse_duration_fs) ** 2
    ) / 1e3
    pulse_duration_fiber_rod_ps = np.sqrt(
        pulse_duration_fs**2
        + (4 * np.log(2) * gdd_total_fs2 / pulse_duration_fs) ** 2
    ) / 1e3

    dispersion_gradient = np.gradient(interp_dispersion, wavelength_nm)
    tod_fiber_fs3 = (
        (
            (wavelength_m**2 / (2 * np.pi * c_m_per_s)) ** 2
            * dispersion_gradient
            * 1e3
            + wavelength_m**3
            / (2 * np.pi**2 * 9e16)
            * interp_dispersion
            * 1e-6
        )
        * fiber_length_m
        * 1e45
    )

    gdd_grating_fs2 = np.zeros((l_eff_count, wavelength_nm.size))
    tod_grating_fs3 = np.zeros_like(gdd_grating_fs2)
    pulse_duration_grating_fiber_ps = np.zeros_like(gdd_grating_fs2)

    grating_angle_term = (
        1 - (-diffraction_order * wavelength_nm / grating_spacing_nm - sin_theta) ** 2
    ) ** (-1.5)

    for i, l_eff in enumerate(l_eff_m):
        gdd_grating = (
            -2
            * diffraction_order**2
            * wavelength_nm**3
            * 1e-9
            * l_eff
            / (2 * np.pi * 9e16 * grating_spacing_nm**2)
            * 1e30
            * grating_angle_term
        )
        gdd_grating_total = gdd_grating + gdd_total_fs2

        gdd_grating_fs2[i, :] = gdd_grating
        tod_grating_fs3[i, :] = (
            -gdd_grating * 3 * wavelength_nm * 1e-9 / 0.2 / np.pi / c_m_per_s * 1e15
        )
        pulse_duration_grating_fiber_ps[i, :] = np.sqrt(
            pulse_duration_fs**2
            + (4 * np.log(2) * gdd_grating_total / pulse_duration_fs) ** 2
        ) / 1e3

    return SimulationResult(
        wavelength_nm=wavelength_nm,
        fiber_model=fiber_label,
        fiber_length_m=fiber_length_m,
        rod_length_mm=rod_length_mm,
        grating_lines_per_mm=grating_lines_per_mm,
        pulse_duration_fs=pulse_duration_fs,
        l_eff_m=l_eff_m,
        interp_dispersion=interp_dispersion,
        gdd_fiber_fs2=gdd_fiber_fs2,
        gdd_rod_fs2=gdd_rod_fs2,
        gdd_total_fs2=gdd_total_fs2,
        tod_fiber_fs3=tod_fiber_fs3,
        gdd_grating_fs2=gdd_grating_fs2,
        tod_grating_fs3=tod_grating_fs3,
        pulse_duration_fiber_ps=pulse_duration_fiber_ps,
        pulse_duration_fiber_rod_ps=pulse_duration_fiber_rod_ps,
        pulse_duration_grating_fiber_ps=pulse_duration_grating_fiber_ps,
    )


def length_label(length_m: float) -> str:
    return f"{length_m:g} m"


def length_slug(length_m: float) -> str:
    return f"{length_m:g}".replace(".", "p").replace("-", "minus")


def default_output_path(
    fiber_model: str,
    fiber_length_m: float,
    rod_length_mm: float,
    grating_lines_per_mm: float,
    plot_kind: str,
) -> Path:
    rod_length_cm = rod_length_mm / 10
    if plot_kind == "grating":
        filename = (
            f"{fiber_model}_fiber_{length_slug(fiber_length_m)}m_"
            f"{length_slug(grating_lines_per_mm)}lines_per_mm_grating_dispersion.png"
        )
    else:
        filename = (
            f"{fiber_model}_fiber_{length_slug(fiber_length_m)}m_sf11_"
            f"{length_slug(rod_length_cm)}cm_pulse_duration_vs_wavelength.png"
        )
    return Path(__file__).with_name(filename)


def write_results_csv(result: SimulationResult, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    best_grating_indices = np.nanargmin(result.pulse_duration_grating_fiber_ps, axis=0)
    best_grating_pulse_ps = result.pulse_duration_grating_fiber_ps[
        best_grating_indices, np.arange(result.wavelength_nm.size)
    ]
    best_l_eff_cm = result.l_eff_m[best_grating_indices] * 100
    with output_path.open("w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(
            [
                "wavelength_nm",
                "dispersion_ps_per_nm_km",
                "gdd_fiber_fs2",
                "gdd_sf11_rod_fs2",
                "gdd_total_fs2",
                "tod_fiber_fs3",
                "pulse_duration_fiber_ps",
                "pulse_duration_fiber_sf11_rod_ps",
                "best_grating_l_eff_cm",
                "best_pulse_duration_grating_fiber_ps",
            ]
        )
        writer.writerows(
            zip(
                result.wavelength_nm,
                result.interp_dispersion,
                result.gdd_fiber_fs2,
                result.gdd_rod_fs2,
                result.gdd_total_fs2,
                result.tod_fiber_fs3,
                result.pulse_duration_fiber_ps,
                result.pulse_duration_fiber_rod_ps,
                best_l_eff_cm,
                best_grating_pulse_ps,
            )
        )
    print(f"Saved results to {output_path}")


def plot_result(result: SimulationResult, output_path: Path | None = None) -> None:
    fig, ax = plt.subplots(figsize=(10, 5), constrained_layout=True)
    ax.plot(
        result.wavelength_nm,
        result.pulse_duration_fiber_ps,
        "k-",
        linewidth=2,
        label=f"{length_label(result.fiber_length_m)} {result.fiber_model} fiber",
    )
    ax.plot(
        result.wavelength_nm,
        result.pulse_duration_fiber_rod_ps,
        color="tab:red",
        linewidth=2,
        label=(
            f"{length_label(result.fiber_length_m)} {result.fiber_model} fiber "
            f"+ {result.rod_length_mm:g} mm SF11 rod"
        ),
    )
    ax.set(
        xlabel="Wavelength (nm)",
        ylabel="Pulse Duration (ps)",
        xlim=(result.wavelength_nm.min(), result.wavelength_nm.max()),
        title="Pulse Duration vs Wavelength",
    )
    ax.grid(True)
    ax.legend()

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=200)
        print(f"Saved plot to {output_path}")
    else:
        plt.show()


def plot_grating_result(result: SimulationResult, output_path: Path | None = None) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(10, 10), constrained_layout=True)
    cmap = plt.get_cmap("jet")
    colors = cmap(np.linspace(0, 1, result.l_eff_m.size))

    for i, color in enumerate(colors):
        axes[0].plot(result.wavelength_nm, result.tod_grating_fs3[i, :], color=color)
    axes[0].plot(result.wavelength_nm, result.tod_fiber_fs3, "b--", linewidth=2)
    axes[0].set(
        xlabel="Wavelength (nm)",
        ylabel="TOD (fs^3)",
        title="TOD of grating and fiber vs wavelength",
    )
    axes[0].grid(True)

    for i, color in enumerate(colors):
        axes[1].plot(
            result.wavelength_nm,
            result.pulse_duration_grating_fiber_ps[i, :],
            color=color,
        )
    axes[1].plot(
        result.wavelength_nm,
        result.pulse_duration_fiber_rod_ps,
        "k--",
        linewidth=2,
        label=(
            "Fiber + SF11, no grating"
            if result.rod_length_mm
            else "Fiber only, no grating"
        ),
    )
    axes[1].set(
        xlabel="Wavelength (nm)",
        ylabel="Pulse Duration (ps)",
        title="Pulse duration vs wavelength for L_eff values",
        ylim=(0, 5),
    )
    axes[1].grid(True)
    axes[1].legend()

    for i, color in enumerate(colors):
        axes[2].plot(result.wavelength_nm, result.gdd_grating_fs2[i, :], color=color)
    axes[2].plot(result.wavelength_nm, result.gdd_total_fs2, "k--", linewidth=2)
    axes[2].set(
        xlabel="Wavelength (nm)",
        ylabel="GDD (fs^2)",
        title="GDD of grating and fiber vs wavelength",
        ylim=(-1e7, 1e7),
    )
    axes[2].grid(True)

    sm = plt.cm.ScalarMappable(
        cmap=cmap,
        norm=plt.Normalize(result.l_eff_m.min() * 100, result.l_eff_m.max() * 100),
    )
    sm.set_array([])
    fig.colorbar(sm, ax=axes, label="L_eff (cm)")
    fig.suptitle(
        f"{result.fiber_model}, {length_label(result.fiber_length_m)}, "
        f"{result.grating_lines_per_mm:g} lines/mm grating, "
        f"{result.pulse_duration_fs:g} fs input"
    )

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=200)
        print(f"Saved plot to {output_path}")
    else:
        plt.show()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Estimate fiber dispersion and grating compensation."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path for the generated plot. Defaults to a name based on fiber and rod length.",
    )
    parser.add_argument(
        "--results-output",
        type=Path,
        default=None,
        help="Optional path for generated CSV results.",
    )
    parser.add_argument(
        "--fiber-length-m",
        type=float,
        default=1,
        help="Fiber length in m.",
    )
    parser.add_argument(
        "--fiber-model",
        choices=sorted(FIBER_DATASETS),
        default="pm780_hp",
        help="Fiber dispersion dataset to use.",
    )
    parser.add_argument(
        "--grating-lines-per-mm",
        type=float,
        default=1200,
        help="Grating groove density in lines/mm.",
    )
    parser.add_argument(
        "--gdd-offset-fs2",
        type=float,
        default=0,
        help="Constant GDD offset added to the fiber GDD, in fs^2.",
    )
    parser.add_argument(
        "--pulse-duration-fs",
        type=float,
        default=100,
        help="Input pulse duration in fs.",
    )
    parser.add_argument(
        "--plot-kind",
        choices=["pulse", "grating"],
        default="pulse",
        help="Generate the simple pulse-duration plot or the grating compensation plot.",
    )
    parser.add_argument(
        "--rod-length-mm",
        type=float,
        default=300,
        help="SF11 optical rod length in mm.",
    )
    parser.add_argument(
        "--wavelength-start-nm",
        type=float,
        default=None,
        help="Start wavelength in nm. Defaults to the selected fiber dataset minimum.",
    )
    parser.add_argument(
        "--wavelength-stop-nm",
        type=float,
        default=None,
        help="Stop wavelength in nm. Defaults to the selected fiber dataset maximum.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Show the plot interactively instead of saving it.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_simulation(
        wavelength_start_nm=args.wavelength_start_nm,
        wavelength_stop_nm=args.wavelength_stop_nm,
        fiber_model=args.fiber_model,
        fiber_length_m=args.fiber_length_m,
        gdd_offset_fs2=args.gdd_offset_fs2,
        grating_lines_per_mm=args.grating_lines_per_mm,
        pulse_duration_fs=args.pulse_duration_fs,
        rod_length_mm=args.rod_length_mm,
    )
    if args.results_output:
        write_results_csv(result, args.results_output)
    output_path = None if args.show else args.output or default_output_path(
        args.fiber_model,
        args.fiber_length_m,
        args.rod_length_mm,
        args.grating_lines_per_mm,
        args.plot_kind,
    )
    if args.plot_kind == "grating":
        plot_grating_result(result, output_path)
    else:
        plot_result(result, output_path)


if __name__ == "__main__":
    main()
