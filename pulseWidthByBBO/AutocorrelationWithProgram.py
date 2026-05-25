from __future__ import annotations

import math
import time
import warnings
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import matplotlib.pyplot as plt
import numpy as np


SPAN_MM = 10.0
CENTER_MM = 25.0
HALF_MM = SPAN_MM / 2.0
NUM_SAMPLES = 4000
SAMPLE_PAUSE_S = 0.02
SPEED_OF_LIGHT_M_S = 299_792_458.0

DAQ_DEVICE = "Dev1"
DAQ_AI_CHANNEL = "ai5"
ESP_RESOURCE = "GPIB0::1::INSTR"


@dataclass
class FitResult:
    parameters: np.ndarray
    sigma_ps: float
    fwhm_autocorrelation_ps: float
    fwhm_pulse_ps: float


def gaussian(params: np.ndarray, x: np.ndarray) -> np.ndarray:
    amplitude, center, sigma, offset = params
    return amplitude * np.exp(-((x - center) ** 2) / (2.0 * sigma**2)) + offset


def nelder_mead(
    cost: Callable[[np.ndarray], float],
    initial: np.ndarray,
    max_iter: int = 2000,
    tolerance: float = 1e-9,
) -> np.ndarray:
    """Small scipy-free fallback for MATLAB fminsearch-style fitting."""
    initial = np.asarray(initial, dtype=float)
    n = initial.size
    simplex = [initial]
    for i in range(n):
        point = initial.copy()
        step = 0.05 * abs(point[i]) if point[i] != 0 else 0.00025
        point[i] += step
        simplex.append(point)
    simplex = np.asarray(simplex)
    values = np.asarray([cost(point) for point in simplex])

    alpha = 1.0
    gamma = 2.0
    rho = 0.5
    sigma = 0.5

    for _ in range(max_iter):
        order = np.argsort(values)
        simplex = simplex[order]
        values = values[order]
        if np.std(values) < tolerance:
            break

        centroid = simplex[:-1].mean(axis=0)
        worst = simplex[-1]
        reflected = centroid + alpha * (centroid - worst)
        reflected_value = cost(reflected)

        if values[0] <= reflected_value < values[-2]:
            simplex[-1] = reflected
            values[-1] = reflected_value
            continue

        if reflected_value < values[0]:
            expanded = centroid + gamma * (reflected - centroid)
            expanded_value = cost(expanded)
            if expanded_value < reflected_value:
                simplex[-1] = expanded
                values[-1] = expanded_value
            else:
                simplex[-1] = reflected
                values[-1] = reflected_value
            continue

        contracted = centroid + rho * (worst - centroid)
        contracted_value = cost(contracted)
        if contracted_value < values[-1]:
            simplex[-1] = contracted
            values[-1] = contracted_value
            continue

        best = simplex[0]
        simplex = best + sigma * (simplex - best)
        values = np.asarray([cost(point) for point in simplex])

    return simplex[np.argmin(values)]


def fit_gaussian(x_fit: np.ndarray, y_fit: np.ndarray) -> FitResult:
    max_index = int(np.argmax(y_fit))
    max_y = float(y_fit[max_index])
    min_y = float(np.min(y_fit))
    mu0 = float(x_fit[max_index])
    sigma0 = float((np.max(x_fit) - np.min(x_fit)) / 10.0)
    if sigma0 <= 0:
        sigma0 = 1.0
    initial = np.asarray([max_y - min_y, mu0, sigma0, min_y], dtype=float)

    try:
        from scipy.optimize import curve_fit

        def model(x: np.ndarray, amplitude: float, center: float, sigma: float, offset: float) -> np.ndarray:
            params = np.asarray([amplitude, center, sigma, offset], dtype=float)
            return gaussian(params, x)

        parameters, _ = curve_fit(model, x_fit, y_fit, p0=initial, maxfev=20_000)
    except Exception as exc:
        warnings.warn(f"SciPy curve_fit unavailable or failed ({exc}); using Nelder-Mead fallback.")

        def cost(params: np.ndarray) -> float:
            residual = gaussian(params, x_fit) - y_fit
            return float(np.sum(residual**2))

        parameters = nelder_mead(cost, initial)

    sigma_ps = abs(float(parameters[2]))
    fwhm_ac = 2.0 * math.sqrt(2.0 * math.log(2.0)) * sigma_ps
    fwhm_pulse = fwhm_ac / math.sqrt(2.0)
    return FitResult(parameters, sigma_ps, fwhm_ac, fwhm_pulse)


def query_str(esp: object, command: str, tries: int = 3) -> str:
    for attempt in range(1, max(1, tries) + 1):
        try:
            esp.write(command)
            response = str(esp.read()).strip()
            if response:
                return response
        except Exception:
            try:
                esp.clear()
            except Exception:
                pass
            time.sleep(0.005 * attempt)
    return ""


def query_num(esp: object, command: str, tries: int = 3) -> float:
    response = query_str(esp, command, tries)
    try:
        return float(response)
    except ValueError:
        return float("nan")


def setup_daq() -> object:
    try:
        import nidaqmx
    except ImportError as exc:
        raise RuntimeError("Install nidaqmx to read the NI DAQ: python -m pip install nidaqmx") from exc

    task = nidaqmx.Task()
    task.ai_channels.add_ai_voltage_chan(f"{DAQ_DEVICE}/{DAQ_AI_CHANNEL}")

    # If your MATLAB setup needed SingleEnded or a fixed range, configure it here:
    # from nidaqmx.constants import TerminalConfiguration
    # task.ai_channels.all.ai_term_cfg = TerminalConfiguration.RSE
    # task.ai_channels.all.ai_min = -10.0
    # task.ai_channels.all.ai_max = 10.0

    return task


def setup_esp(center_mm: float) -> object:
    try:
        import pyvisa
    except ImportError as exc:
        raise RuntimeError("Install pyvisa to control the ESP300: python -m pip install pyvisa") from exc

    resource_manager = pyvisa.ResourceManager()
    esp = resource_manager.open_resource(ESP_RESOURCE)
    esp.write_termination = "\r"
    esp.read_termination = "\r"
    esp.timeout = 1000
    try:
        esp.clear()
    except Exception:
        pass

    esp.write("1MO")
    esp.write("1AC0.1")
    esp.write("1AG0.1")
    esp.write("1VA0.1")
    esp.write("1FE100")

    print(f"Moving to center position ({center_mm:.2f} mm)...")
    esp.write(f"1PA{center_mm:.4f}")
    time.sleep(5.0)

    esp.write("EX Scan5")
    print("Scanning started...")
    return esp


def update_top_axis(ax: plt.Axes, top_ax: plt.Axes) -> None:
    ticks = ax.get_xticks()
    top_ax.set_xlim(ax.get_xlim())
    top_ax.set_xticks(ticks)
    labels = [f"{2.0 * tick * 1e-3 / SPEED_OF_LIGHT_M_S * 1e12:.2f}" for tick in ticks]
    top_ax.set_xticklabels(labels)


def update_peak(positions: np.ndarray, voltages: np.ndarray, upto: int, peak_line: object) -> None:
    pos = positions[:upto]
    vol = voltages[:upto]
    valid = np.isfinite(pos) & np.isfinite(vol)
    if not np.any(valid):
        return
    valid_voltages = np.where(valid, vol, -np.inf)
    index = int(np.argmax(valid_voltages))
    peak = valid_voltages[index]
    if np.isfinite(peak):
        peak_line.set_data([pos[index]], [peak])


def collect_data() -> tuple[np.ndarray, np.ndarray]:
    left_mm = CENTER_MM - HALF_MM
    right_mm = CENTER_MM + HALF_MM

    task = None
    esp = None
    try:
        task = setup_daq()
        esp = setup_esp(CENTER_MM)
    except Exception as exc:
        if task is not None:
            task.close()
        raise RuntimeError(f"Hardware init failed: {exc}\nCheck connections, drivers, and GPIB address.") from exc

    positions = np.full(NUM_SAMPLES, np.nan, dtype=float)
    voltages = np.full(NUM_SAMPLES, np.nan, dtype=float)

    plt.ion()
    fig, ax = plt.subplots(num="Realtime Autocorrelation")
    fig.patch.set_facecolor("white")
    (line,) = ax.plot([], [], "r.-", linewidth=1.2)
    (peak_line,) = ax.plot([], [], "ko", markersize=8, linewidth=1.2)
    ax.grid(True)
    ax.set_xlabel("Position (mm)")
    ax.set_ylabel("DAQ Voltage (V)")
    ax.set_xlim(left_mm, right_mm)

    top_ax = ax.twiny()
    top_ax.set_frame_on(False)
    top_ax.set_xlabel("Time Delay (ps)")
    update_top_axis(ax, top_ax)

    try:
        for index in range(NUM_SAMPLES):
            if not plt.fignum_exists(fig.number):
                break

            positions[index] = query_num(esp, "1TP?", 3)
            voltages[index] = float(task.read())
            upto = index + 1

            line.set_data(positions[:upto], voltages[:upto])
            if upto % 10 == 0:
                update_peak(positions, voltages, upto, peak_line)
                ax.relim()
                ax.autoscale_view()
                update_top_axis(ax, top_ax)

            fig.canvas.draw_idle()
            fig.canvas.flush_events()
            time.sleep(SAMPLE_PAUSE_S)
    except KeyboardInterrupt:
        print("Acquisition interrupted by user.")
    except Exception as exc:
        warnings.warn(f"Acquisition stopped early: {exc}")
    finally:
        try:
            if esp is not None:
                esp.write("AB")
        except Exception:
            pass
        try:
            if task is not None:
                task.close()
        except Exception:
            pass

    print("Acquisition complete. Analyzing data...")
    return positions, voltages


def bin_data(positions_mm: np.ndarray, voltages_v: np.ndarray, nbins: int = 60) -> tuple[np.ndarray, np.ndarray]:
    edges = np.linspace(np.min(positions_mm), np.max(positions_mm), nbins + 1)
    bin_centers = 0.5 * (edges[:-1] + edges[1:])
    bins = np.digitize(positions_mm, edges, right=False) - 1
    bins[bins == nbins] = nbins - 1

    avg_voltage = np.full(nbins, np.nan, dtype=float)
    for index in range(nbins):
        mask = bins == index
        if np.any(mask):
            avg_voltage[index] = float(np.mean(voltages_v[mask]))

    return bin_centers, avg_voltage


def save_mat_file(result_base: Path, result: dict[str, object]) -> None:
    try:
        from scipy.io import savemat

        savemat(result_base.with_suffix(".mat"), {"result": result})
    except Exception as exc:
        warnings.warn(f"Could not save .mat file ({exc}); saving .npz instead.")
        np.savez(result_base.with_suffix(".npz"), **result)


def analyze_and_save(positions: np.ndarray, voltages: np.ndarray) -> None:
    valid = np.isfinite(positions) & np.isfinite(voltages)
    pos = positions[valid]
    vol = voltages[valid]

    if pos.size == 0:
        warnings.warn("No valid data collected.")
        return

    bin_centers, avg_voltages = bin_data(pos, vol)
    time_ps = 2.0 * (bin_centers * 1e-3) / SPEED_OF_LIGHT_M_S * 1e12

    valid_bins = np.isfinite(avg_voltages)
    x_fit = time_ps[valid_bins].astype(float)
    y_fit = avg_voltages[valid_bins].astype(float)
    if x_fit.size < 4:
        warnings.warn("Not enough binned points for a four-parameter Gaussian fit.")
        return

    fit = fit_gaussian(x_fit, y_fit)
    b_fit = fit.parameters

    fig, ax = plt.subplots(num="Gaussian Fit Result")
    fig.patch.set_facecolor("white")
    ax.plot(x_fit, y_fit, "ko", markerfacecolor=(0.8, 0.8, 0.8), label="Raw Data")
    t_smooth = np.linspace(np.min(x_fit), np.max(x_fit), 200)
    ax.plot(t_smooth, gaussian(b_fit, t_smooth), "b-", linewidth=2, label="Gaussian Fit")
    ax.grid(True)
    ax.set_xlabel("Time Delay (ps)")
    ax.set_ylabel("Signal (V)")
    ax.set_title(f"Pulse Duration: {fit.fwhm_pulse_ps:.3f} ps (Gaussian)")
    ax.legend(loc="best")

    script_dir = Path(__file__).resolve().parent
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_base = script_dir / f"AutocorrelationResult_{timestamp}"

    result = {
        "positions_mm": pos,
        "voltages_V": vol,
        "time_ps": x_fit,
        "binned_signal_V": y_fit,
        "fit_parameters": b_fit,
        "sigma_ps": fit.sigma_ps,
        "FWHM_autocorrelation_ps": fit.fwhm_autocorrelation_ps,
        "FWHM_pulse_ps": fit.fwhm_pulse_ps,
    }

    save_mat_file(result_base, result)
    np.savetxt(result_base.with_suffix(".csv"), np.column_stack([x_fit, y_fit]), delimiter=",")
    fig.savefig(result_base.with_suffix(".png"), dpi=150, bbox_inches="tight")

    peak_position_mm = b_fit[1] * SPEED_OF_LIGHT_M_S / 2.0 * 1e-9
    print("\n==================================")
    print("       FIT RESULTS (Gaussian)     ")
    print("==================================")
    print(f"Peak Position:          {peak_position_mm:.4f} mm")
    print(f"Autocorrelation width:  {fit.fwhm_autocorrelation_ps:.3f} ps")
    print(f"PULSE WIDTH:            {fit.fwhm_pulse_ps:.3f} ps")
    print(f"Saved result files:     {result_base}.[mat/csv/png]")
    print("==================================")

    plt.ioff()
    plt.show()


def main() -> None:
    positions, voltages = collect_data()
    analyze_and_save(positions, voltages)


if __name__ == "__main__":
    main()
