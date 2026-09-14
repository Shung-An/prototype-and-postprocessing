"""Read a fixed-position run and export a reproducible Allan/mean comparison."""
import argparse
import json
from pathlib import Path

import numpy as np
import cm_pipeline_all_in_one as p


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    meta = p.read_sensitivity_log(args.run)
    p.apply_metadata_attenuator(args.run, meta)
    payload = p.metadata_payload(args.run)
    if payload.get("PhysicsData", {}).get("ScanRange_mm") != 0:
        raise ValueError("Select a fixed-position run (ScanRange_mm = 0).")
    cm = p.read_cm64(args.run / "cm.bin")
    cm *= p.DETECTOR_AREA_SCALE * meta.power_detector_attenuator_correction_factor
    time = np.arange(len(cm)) * p.FRAME_DT_S
    keep, _ = p.critical_pair_indices(cm, np.empty((0, len(p.PAIRS))), p.PAIRS)
    labels = p.pair_labels(p.PAIRS)
    v2 = p.display_in_v2_for_meta(meta)
    args.output.mkdir(parents=True, exist_ok=True)
    p.save_loglog_eval(args.output, time, cm, p.PAIRS, labels, meta.conversion_factor, keep, v2)
    pairs = p.PAIRS[keep]
    values = p.scale_for_display(cm[:, [p.idx_lin(r,c) for r,c,_,_ in pairs]] -
                                cm[:, [p.idx_lin(r,c) for _,_,r,c in pairs]], meta.conversion_factor, v2)
    tau, variance, counts, factors = p.overlapping_allan_variance(values, time)
    means = np.cumsum(values, axis=0) / np.arange(1, len(values)+1)[:, None]
    fig, axes = p.plt.subplots(1, 2, figsize=(13, 5.5))
    results = []
    for col, idx in enumerate(keep):
        x, y = p.downsample_for_plot(time + p.FRAME_DT_S, np.abs(means[:, col]))
        axes[0].loglog(x, y, label=labels[idx])
        axes[1].loglog(tau, variance[:, col], label=labels[idx])
        slope = float(np.polyfit(time, values[:, col], 1)[0])
        results.append(dict(pair=labels[idx], final_mean=float(means[-1,col]),
                            linear_fit_slope_per_s=slope, first_variance=float(variance[0,col]),
                            final_variance=float(variance[-1,col]),
                            minimum_tau_s=float(tau[np.nanargmin(variance[:,col])]),
                            tail_log_slope=float(np.polyfit(np.log(tau[-10:]),np.log(variance[-10:,col]),1)[0])))
    axes[0].set(title="Previous: absolute cumulative mean", xlabel="Elapsed acquisition time (s)",
                ylabel="Absolute mean (V²)" if v2 else "Absolute mean (µrad²)")
    axes[1].set(title="Overlapping Allan variance", xlabel="Averaging time τ (s)",
                ylabel="Allan variance (V⁴)" if v2 else "Allan variance (µrad⁴)")
    for ax in axes:
        ax.grid(True, which="both", alpha=0.2)
    axes[1].legend(fontsize=7, loc="best")
    fig.suptitle(f"Fixed-position run {args.run.name}; nominal frame time {p.FRAME_DT_S:.6f} s")
    fig.tight_layout()
    p.save_figure_with_provenance(fig, args.output / "mean_vs_allan.png", args.run)
    fig.savefig(args.output / "mean_vs_allan.pdf", bbox_inches="tight")
    p.plt.close(fig)
    summary = dict(source=str(args.run.resolve()), description=payload.get("Description"),
                   frames=len(cm), nominal_frame_dt_s=p.FRAME_DT_S,
                   nominal_duration_s=len(cm)*p.FRAME_DT_S, maximum_tau_s=float(tau[-1]),
                   conversion_factor=meta.conversion_factor, display_in_v2=v2,
                   notes="No detrending or smoothing. Profile timestamps are transfer times. "
                         "Linear slopes are descriptive full-record fits, not drift-only estimates. "
                         "Allan tails include stochastic noise; overlapping counts are not independent DOF.",
                   pairs=results)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
