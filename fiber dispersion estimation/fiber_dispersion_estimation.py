"""PM780-HP fiber plus SF11 optical rod dispersion estimate.

The script calculates interpolated PM780-HP fiber dispersion, estimates the
fiber and SF11 optical rod GDD, and plots pulse duration vs wavelength.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import NamedTuple

import matplotlib.pyplot as plt
import numpy as np


class SimulationResult(NamedTuple):
    wavelength_nm: np.ndarray
    rod_length_mm: float
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


SOURCE_WAVELENGTH_NM = np.array(
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

SOURCE_DISPERSION_PS_PER_NM_KM = np.array(
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
    wavelength_start_nm: float = 600,
    wavelength_stop_nm: float = 992,
    wavelength_step_nm: float = 1,
    fiber_length_m: float = 1,
    gdd_offset_fs2: float = 0,
    grating_lines_per_mm: float = 1200,
    pulse_duration_fs: float = 100,
    rod_length_mm: float = 300,
    l_eff_start_m: float = 0.20,
    l_eff_stop_m: float = 0.74,
    l_eff_count: int = 120,
) -> SimulationResult:
    wavelength_nm = np.arange(
        wavelength_start_nm, wavelength_stop_nm + wavelength_step_nm, wavelength_step_nm
    )
    interp_dispersion = spline_interpolate(
        SOURCE_WAVELENGTH_NM, SOURCE_DISPERSION_PS_PER_NM_KM, wavelength_nm
    )

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
        rod_length_mm=rod_length_mm,
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


def plot_result(result: SimulationResult, output_path: Path | None = None) -> None:
    fig, ax = plt.subplots(figsize=(10, 5), constrained_layout=True)
    ax.plot(
        result.wavelength_nm,
        result.pulse_duration_fiber_ps,
        "k-",
        linewidth=2,
        label="1 m PM780-HP fiber",
    )
    ax.plot(
        result.wavelength_nm,
        result.pulse_duration_fiber_rod_ps,
        color="tab:red",
        linewidth=2,
        label=f"1 m PM780-HP fiber + {result.rod_length_mm:g} mm SF11 rod",
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Estimate fiber dispersion and grating compensation."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("pm780_hp_fiber_sf11_30cm_100fs_pulse_duration_vs_wavelength.png"),
        help="Path for the generated plot. Use --show to display instead.",
    )
    parser.add_argument(
        "--rod-length-mm",
        type=float,
        default=300,
        help="SF11 optical rod length in mm.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Show the plot interactively instead of saving it.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_simulation(rod_length_mm=args.rod_length_mm)
    plot_result(result, None if args.show else args.output)


if __name__ == "__main__":
    main()
