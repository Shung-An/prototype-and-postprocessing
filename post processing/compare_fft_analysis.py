from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from raw_interleaved_fft import (
    HIGH_FREQUENCY_CSV_NAME,
    LOW_FREQUENCY_CSV_NAME,
    MODE_METADATA,
    infer_physical_channel_index,
)


FftMode = Literal["low", "high"]
DEFAULT_ROOT = Path(r"D:\Quantum Squeezing Project\DataFiles")
OUTPUT_DIR_NAME = "fft_analysis_comparison"


@dataclass(frozen=True)
class FftCsvSeries:
    run_name: str
    run_description: str
    csv_path: Path
    series_name: str
    channel_index: int
    channel_label: str
    frequency_hz: np.ndarray
    psd: np.ndarray


def compare_fft_analysis(
    root: Path | str = DEFAULT_ROOT,
    *,
    mode: FftMode = "low",
    max_plot_points: int = 0,
) -> Path:
    root = Path(root).expanduser().resolve()
    csv_name = LOW_FREQUENCY_CSV_NAME if mode == "low" else HIGH_FREQUENCY_CSV_NAME
    csv_paths = discover_fft_csv_paths(root, mode, csv_name)
    if not csv_paths:
        raise FileNotFoundError(f"No {csv_name} files were found under {root}")

    series: list[FftCsvSeries] = []
    for csv_path in csv_paths:
        series.extend(load_fft_csv(csv_path))
    if not series:
        raise RuntimeError("FFT CSV files were found, but no plottable series were loaded.")

    output_dir = root / OUTPUT_DIR_NAME
    output_dir.mkdir(exist_ok=True)
    plot_path = output_dir / (
        "all_low_frequency_fft_loglog_comparison.png"
        if mode == "low"
        else "all_high_frequency_fft_semilog_comparison.png"
    )
    html_path = output_dir / (
        "all_low_frequency_fft_loglog_comparison_interactive.html"
        if mode == "low"
        else "all_high_frequency_fft_semilog_comparison_interactive.html"
    )
    manifest_path = output_dir / (
        "all_low_frequency_fft_loglog_comparison_manifest.json"
        if mode == "low"
        else "all_high_frequency_fft_semilog_comparison_manifest.json"
    )

    save_comparison_plot(plot_path, series, mode, max_plot_points=max_plot_points)
    save_interactive_canvas_html(html_path, series, mode, max_plot_points=max_plot_points)
    save_manifest(manifest_path, series, mode, plot_path, html_path)
    return html_path


def discover_fft_csv_paths(root: Path, mode: FftMode, csv_name: str) -> list[Path]:
    discovered: dict[str, Path] = {}
    mode_key = MODE_METADATA[mode]["key"]

    for metadata_path in root.rglob("metadata.json"):
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue

        analysis = payload.get("FFTAnalysis")
        if not isinstance(analysis, dict):
            continue
        modes = analysis.get("Modes")
        if not isinstance(modes, dict):
            continue
        mode_payload = modes.get(mode_key)
        if not isinstance(mode_payload, dict):
            continue
        csv_value = mode_payload.get("OutputCsv")
        if not csv_value:
            continue
        csv_path = Path(str(csv_value))
        if not csv_path.is_absolute():
            csv_path = metadata_path.parent / csv_path
        if csv_path.exists():
            discovered[str(csv_path.resolve())] = csv_path.resolve()

    for csv_path in root.rglob(csv_name):
        discovered[str(csv_path.resolve())] = csv_path.resolve()

    return sorted(discovered.values())


def load_fft_csv(csv_path: Path) -> list[FftCsvSeries]:
    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader)

    if len(header) < 2:
        return []

    data = np.loadtxt(csv_path, delimiter=",", skiprows=1)
    if data.ndim == 1:
        data = data.reshape(1, -1)
    if data.shape[1] < 2:
        return []

    frequency_hz = data[:, 0]
    run_name = infer_run_name(csv_path)
    run_description = read_run_description(csv_path)
    loaded: list[FftCsvSeries] = []
    for column_index, series_name in enumerate(header[1:], start=1):
        if column_index >= data.shape[1]:
            continue
        psd = data[:, column_index]
        finite = np.isfinite(frequency_hz) & np.isfinite(psd) & (frequency_hz > 0) & (psd > 0)
        if not np.any(finite):
            continue
        channel_index = infer_physical_channel_index(series_name)
        loaded.append(
            FftCsvSeries(
                run_name=run_name,
                run_description=run_description or run_name,
                csv_path=csv_path,
                series_name=series_name,
                channel_index=channel_index,
                channel_label=f"Ch{channel_index}" if channel_index else "Ch?",
                frequency_hz=frequency_hz[finite],
                psd=psd[finite],
            )
        )
    return loaded


def infer_run_name(csv_path: Path) -> str:
    try:
        return csv_path.parents[1].name
    except IndexError:
        return csv_path.parent.name


def infer_run_folder(csv_path: Path) -> Path:
    try:
        return csv_path.parents[1]
    except IndexError:
        return csv_path.parent


def read_run_description(csv_path: Path) -> str:
    metadata_path = infer_run_folder(csv_path) / "metadata.json"
    if not metadata_path.exists():
        return ""
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("Description") or "").strip()


def save_comparison_plot(
    plot_path: Path,
    series: list[FftCsvSeries],
    mode: FftMode,
    *,
    max_plot_points: int,
) -> None:
    grouped = group_series_by_channel(series)
    channel_keys = [key for key in [1, 2, 3, 4] if key in grouped]
    channel_keys.extend(key for key in sorted(grouped) if key not in channel_keys)
    if not channel_keys:
        channel_keys = [0]

    fig, axes = plt.subplots(2, 2, figsize=(18, 11), dpi=160, squeeze=False)
    flat_axes = list(axes.ravel())
    for axis_index, ax in enumerate(flat_axes):
        if axis_index >= len(channel_keys):
            ax.axis("off")
            continue
        channel_key = channel_keys[axis_index]
        channel_series = grouped.get(channel_key, [])
        for item in channel_series:
            frequency_hz, psd = downsample_for_plot(item.frequency_hz, item.psd, max_plot_points)
            label = item.run_description or item.run_name
            if mode == "low":
                ax.loglog(frequency_hz, psd, linewidth=0.9, alpha=0.78, label=label)
            else:
                ax.semilogy(frequency_hz / 1e6, psd, linewidth=0.9, alpha=0.78, label=label)
        ax.set_title(channel_series[0].channel_label if channel_series else f"Ch{channel_key}")
        ax.set_ylabel("PSD (counts^2/Hz)")
        ax.grid(True, which="both", alpha=0.28)
        ax.legend(loc="best", fontsize=6)

    for ax in flat_axes[-2:]:
        ax.set_xlabel("Frequency (Hz)" if mode == "low" else "Frequency (MHz)")

    fig.suptitle(
        "All Runs - Low Frequency FFT Log-Log Comparison by Channel"
        if mode == "low"
        else "All Runs - High Frequency FFT Semilog Comparison by Channel"
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(plot_path)
    plt.close(fig)


def group_series_by_channel(series: list[FftCsvSeries]) -> dict[int, list[FftCsvSeries]]:
    grouped: dict[int, list[FftCsvSeries]] = {}
    for item in series:
        key = item.channel_index or 0
        grouped.setdefault(key, []).append(item)
    return grouped


def save_interactive_canvas_html(
    html_path: Path,
    series: list[FftCsvSeries],
    mode: FftMode,
    *,
    max_plot_points: int,
) -> None:
    colors = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
        "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
        "#bcbd22", "#17becf", "#4e79a7", "#f28e2b",
        "#59a14f", "#e15759", "#76b7b2", "#edc948",
    ]
    label_colors: dict[str, str] = {}
    payload_series = []
    for index, item in enumerate(series):
        frequency_hz, psd = downsample_for_plot(item.frequency_hz, item.psd, max_plot_points)
        if mode == "low":
            x_values = frequency_hz
            x_label = "Frequency (Hz)"
            x_scale = "log"
        else:
            x_values = frequency_hz / 1e6
            x_label = "Frequency (MHz)"
            x_scale = "linear"
        label = item.run_description or item.run_name
        if label not in label_colors:
            label_colors[label] = colors[len(label_colors) % len(colors)]
        payload_series.append(
            {
                "name": label,
                "run": item.run_name,
                "channel": item.channel_label,
                "channelIndex": item.channel_index,
                "seriesName": item.series_name,
                "source": str(item.csv_path),
                "color": label_colors[label],
                "x": [float(value) for value in x_values],
                "y": [float(value) for value in psd],
                "visible": True,
            }
        )

    payload = {
        "mode": mode,
        "title": "All Runs - Low Frequency FFT Log-Log Comparison"
        if mode == "low"
        else "All Runs - High Frequency FFT Semilog Comparison",
        "xLabel": x_label,
        "yLabel": "PSD (counts^2/Hz)",
        "xScale": x_scale,
        "yScale": "log",
        "channels": sorted(
            [{"index": key, "label": values[0].channel_label} for key, values in group_series_by_channel(series).items()],
            key=lambda item: item["index"] or 999,
        ),
        "series": payload_series,
    }

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape_html(payload["title"])}</title>
  <style>
    :root {{
      --ink: #12353c;
      --muted: #61767b;
      --line: #d6e0e2;
      --bg: #f3f1ea;
      --paper: #ffffff;
      --accent: #176f7a;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", Arial, sans-serif;
      color: var(--ink);
      background: var(--bg);
      overflow: hidden;
    }}
    header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 14px;
      background: var(--paper);
      border-bottom: 1px solid var(--line);
    }}
    h1 {{ margin: 0; font-size: 18px; }}
    .tools {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
    .channel-tabs {{ display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }}
    button, input {{
      border: 1px solid #b9c8ca;
      border-radius: 4px;
      padding: 7px 10px;
      font: inherit;
      background: white;
      color: var(--ink);
    }}
    button {{
      cursor: pointer;
      background: var(--accent);
      color: white;
      border-color: #0f5962;
    }}
    button.inactive {{
      background: white;
      color: var(--ink);
    }}
    input {{ width: 220px; }}
    main {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 360px;
      height: calc(100vh - 54px);
      min-width: 0;
    }}
    .canvas-wrap {{
      position: relative;
      min-width: 0;
      background: white;
    }}
    canvas {{
      display: block;
      width: 100%;
      height: 100%;
      cursor: grab;
    }}
    canvas.dragging {{ cursor: grabbing; }}
    aside {{
      border-left: 1px solid var(--line);
      background: var(--paper);
      overflow: auto;
      padding: 10px;
    }}
    .hint {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 10px;
      line-height: 1.35;
    }}
    .series-row {{
      display: grid;
      grid-template-columns: auto 34px minmax(0, 1fr);
      gap: 7px;
      align-items: center;
      padding: 5px 2px;
      border-bottom: 1px solid #eef3f4;
      font-size: 12px;
    }}
    .series-color {{
      width: 30px;
      height: 24px;
      min-width: 30px;
      padding: 1px;
      border-radius: 3px;
    }}
    .series-label {{
      width: 100%;
      min-width: 0;
      padding: 5px 6px;
      font-size: 12px;
    }}
    .channel-title {{
      margin: 12px 0 4px;
      font-weight: 700;
      font-size: 12px;
      color: var(--ink);
    }}
    .readout {{
      position: absolute;
      left: 12px;
      bottom: 10px;
      background: rgba(255, 255, 255, 0.92);
      border: 1px solid var(--line);
      border-radius: 4px;
      padding: 5px 7px;
      font-size: 12px;
      color: var(--muted);
      pointer-events: none;
    }}
  </style>
</head>
<body>
  <header>
    <h1>{escape_html(payload["title"])}</h1>
    <div class="tools">
      <div id="channels" class="channel-tabs"></div>
      <input id="filter" type="search" placeholder="Filter lines...">
      <button id="selectAll" type="button">All</button>
      <button id="selectNone" type="button">None</button>
      <button id="reset" type="button">Reset View</button>
      <button id="savePng" type="button">Save PNG</button>
    </div>
  </header>
  <main>
    <section class="canvas-wrap">
      <canvas id="plot"></canvas>
      <div id="readout" class="readout"></div>
    </section>
    <aside>
      <div class="hint">Wheel to zoom. Drag to pan. Double-click the plot to reset. Toggle lines in the legend. Edit legend text or colors here; Save PNG includes the visible legend.</div>
      <div id="legend"></div>
    </aside>
  </main>
  <script>
    const plotData = {json.dumps(payload)};
  </script>
  <script>
    const canvas = document.getElementById("plot");
    const ctx = canvas.getContext("2d");
    const legend = document.getElementById("legend");
    const filter = document.getElementById("filter");
    const readout = document.getElementById("readout");
    const channelTabs = document.getElementById("channels");
    const margins = {{ left: 82, right: 24, top: 28, bottom: 68 }};
    let view = null;
    let initialView = null;
    let drag = null;
    let activeChannel = "all";

    function transformX(value) {{
      return plotData.xScale === "log" ? Math.log10(Math.max(value, 1e-300)) : value;
    }}
    function untransformX(value) {{
      return plotData.xScale === "log" ? Math.pow(10, value) : value;
    }}
    function transformY(value) {{
      return Math.log10(Math.max(value, 1e-300));
    }}
    function formatNumber(value) {{
      if (!Number.isFinite(value)) return "-";
      const abs = Math.abs(value);
      if (abs >= 1e6 || abs < 1e-2) return value.toExponential(3);
      return value.toPrecision(5);
    }}
    function visibleSeries() {{
      const needle = filter.value.trim().toLowerCase();
      return plotData.series.filter(s =>
        s.visible
        && (activeChannel === "all" || String(s.channelIndex) === activeChannel)
        && (!needle || s.name.toLowerCase().includes(needle))
      );
    }}
    function allSeriesForBounds() {{
      const needle = filter.value.trim().toLowerCase();
      return plotData.series.filter(s =>
        (activeChannel === "all" || String(s.channelIndex) === activeChannel)
        && (!needle || s.name.toLowerCase().includes(needle))
      );
    }}
    function computeBounds(seriesList) {{
      let xmin = Infinity, xmax = -Infinity, ymin = Infinity, ymax = -Infinity;
      for (const series of seriesList) {{
        for (let i = 0; i < series.x.length; i += 1) {{
          const x = transformX(series.x[i]);
          const y = transformY(series.y[i]);
          if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
          xmin = Math.min(xmin, x); xmax = Math.max(xmax, x);
          ymin = Math.min(ymin, y); ymax = Math.max(ymax, y);
        }}
      }}
      if (!Number.isFinite(xmin) || xmin === xmax) {{ xmin = 0; xmax = 1; }}
      if (!Number.isFinite(ymin) || ymin === ymax) {{ ymin = -12; ymax = -6; }}
      const xPad = (xmax - xmin) * 0.02;
      const yPad = (ymax - ymin) * 0.08;
      return {{ xmin: xmin - xPad, xmax: xmax + xPad, ymin: ymin - yPad, ymax: ymax + yPad }};
    }}
    function resetView() {{
      initialView = computeBounds(allSeriesForBounds());
      view = {{ ...initialView }};
      draw();
    }}
    function resizeCanvas() {{
      const rect = canvas.getBoundingClientRect();
      const scale = window.devicePixelRatio || 1;
      canvas.width = Math.max(1, Math.floor(rect.width * scale));
      canvas.height = Math.max(1, Math.floor(rect.height * scale));
      ctx.setTransform(scale, 0, 0, scale, 0, 0);
      draw();
    }}
    function plotRect() {{
      const rect = canvas.getBoundingClientRect();
      return {{
        x: margins.left,
        y: margins.top,
        w: Math.max(10, rect.width - margins.left - margins.right),
        h: Math.max(10, rect.height - margins.top - margins.bottom)
      }};
    }}
    function sx(x) {{
      const r = plotRect();
      return r.x + (x - view.xmin) / (view.xmax - view.xmin) * r.w;
    }}
    function sy(y) {{
      const r = plotRect();
      return r.y + r.h - (y - view.ymin) / (view.ymax - view.ymin) * r.h;
    }}
    function dataFromScreen(px, py) {{
      const r = plotRect();
      const x = view.xmin + (px - r.x) / r.w * (view.xmax - view.xmin);
      const y = view.ymin + (r.y + r.h - py) / r.h * (view.ymax - view.ymin);
      return {{ x, y }};
    }}
    function drawGrid() {{
      const r = plotRect();
      ctx.strokeStyle = "#dce8ea";
      ctx.lineWidth = 1;
      ctx.strokeRect(r.x, r.y, r.w, r.h);
      ctx.fillStyle = "#12353c";
      ctx.font = "12px Segoe UI, Arial";
      ctx.textAlign = "center";
      ctx.textBaseline = "top";

      const xTicks = ticks(view.xmin, view.xmax, plotData.xScale === "log");
      for (const tick of xTicks) {{
        const x = sx(tick);
        if (x < r.x || x > r.x + r.w) continue;
        ctx.strokeStyle = "#e7eeee";
        ctx.beginPath(); ctx.moveTo(x, r.y); ctx.lineTo(x, r.y + r.h); ctx.stroke();
        ctx.fillText(formatNumber(untransformX(tick)), x, r.y + r.h + 8);
      }}
      const yTicks = ticks(view.ymin, view.ymax, true);
      ctx.textAlign = "right";
      ctx.textBaseline = "middle";
      for (const tick of yTicks) {{
        const y = sy(tick);
        if (y < r.y || y > r.y + r.h) continue;
        ctx.strokeStyle = "#e7eeee";
        ctx.beginPath(); ctx.moveTo(r.x, y); ctx.lineTo(r.x + r.w, y); ctx.stroke();
        ctx.fillText(formatNumber(Math.pow(10, tick)), r.x - 8, y);
      }}
      ctx.fillStyle = "#12353c";
      ctx.textAlign = "center";
      ctx.textBaseline = "bottom";
      ctx.fillText(plotData.xLabel, r.x + r.w / 2, r.y + r.h + 48);
      ctx.save();
      ctx.translate(18, r.y + r.h / 2);
      ctx.rotate(-Math.PI / 2);
      ctx.fillText(plotData.yLabel, 0, 0);
      ctx.restore();
    }}
    function ticks(min, max, logLike) {{
      if (logLike) {{
        const start = Math.ceil(min);
        const end = Math.floor(max);
        const values = [];
        for (let p = start; p <= end; p += 1) values.push(p);
        return values;
      }}
      const span = max - min;
      const step = Math.pow(10, Math.floor(Math.log10(span / 8)));
      const nice = [1, 2, 5, 10].map(v => v * step).find(v => span / v <= 10) || step;
      const values = [];
      for (let v = Math.ceil(min / nice) * nice; v <= max; v += nice) values.push(v);
      return values;
    }}
    function drawSeries() {{
      const r = plotRect();
      ctx.save();
      ctx.beginPath();
      ctx.rect(r.x, r.y, r.w, r.h);
      ctx.clip();
      for (const series of visibleSeries()) {{
        ctx.strokeStyle = series.color;
        ctx.lineWidth = 1.2;
        ctx.globalAlpha = 0.78;
        ctx.beginPath();
        let started = false;
        for (let i = 0; i < series.x.length; i += 1) {{
          const x = sx(transformX(series.x[i]));
          const y = sy(transformY(series.y[i]));
          if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
          if (!started) {{ ctx.moveTo(x, y); started = true; }}
          else ctx.lineTo(x, y);
        }}
        ctx.stroke();
      }}
      ctx.restore();
      ctx.globalAlpha = 1;
    }}
    function draw() {{
      if (!view) return;
      const rect = canvas.getBoundingClientRect();
      ctx.clearRect(0, 0, rect.width, rect.height);
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, rect.width, rect.height);
      drawGrid();
      drawSeries();
    }}
    function renderLegend() {{
      legend.innerHTML = "";
      const groups = new Map();
      plotData.series.forEach((series, index) => {{
        if (activeChannel !== "all" && String(series.channelIndex) !== activeChannel) return;
        if (!groups.has(series.channel)) groups.set(series.channel, []);
        groups.get(series.channel).push({{ series, index }});
      }});
      for (const [channel, items] of groups.entries()) {{
        const title = document.createElement("div");
        title.className = "channel-title";
        title.textContent = channel;
        legend.appendChild(title);
        items.forEach((entry) => {{
        const series = entry.series;
        const index = entry.index;
        const row = document.createElement("div");
        row.className = "series-row";
        row.innerHTML = `<input class="series-visible" type="checkbox" ${{series.visible ? "checked" : ""}} aria-label="Show line">
          <input class="series-color" type="color" value="${{series.color}}" aria-label="Line color">
          <input class="series-label" type="text" aria-label="Legend text">`;
        row.querySelector(".series-label").value = series.name;
        row.querySelector(".series-visible").addEventListener("change", event => {{
          plotData.series[index].visible = event.target.checked;
          draw();
        }});
        row.querySelector(".series-color").addEventListener("input", event => {{
          plotData.series[index].color = event.target.value;
          draw();
        }});
        row.querySelector(".series-label").addEventListener("input", event => {{
          plotData.series[index].name = event.target.value;
          draw();
        }});
        legend.appendChild(row);
      }});
      }}
    }}
    function renderChannelTabs() {{
      channelTabs.innerHTML = "";
      const options = [{{ index: "all", label: "All Ch" }}].concat(
        plotData.channels.map(channel => ({{ index: String(channel.index), label: channel.label }}))
      );
      for (const option of options) {{
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = option.label;
        button.className = activeChannel === option.index ? "" : "inactive";
        button.addEventListener("click", () => {{
          activeChannel = option.index;
          renderChannelTabs();
          renderLegend();
          resetView();
        }});
        channelTabs.appendChild(button);
      }}
    }}
    canvas.addEventListener("wheel", event => {{
      event.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const px = event.clientX - rect.left;
      const py = event.clientY - rect.top;
      const anchor = dataFromScreen(px, py);
      const factor = event.deltaY < 0 ? 0.82 : 1.22;
      view.xmin = anchor.x + (view.xmin - anchor.x) * factor;
      view.xmax = anchor.x + (view.xmax - anchor.x) * factor;
      view.ymin = anchor.y + (view.ymin - anchor.y) * factor;
      view.ymax = anchor.y + (view.ymax - anchor.y) * factor;
      draw();
    }}, {{ passive: false }});
    canvas.addEventListener("pointerdown", event => {{
      canvas.setPointerCapture(event.pointerId);
      canvas.classList.add("dragging");
      drag = {{ x: event.clientX, y: event.clientY, view: {{ ...view }} }};
    }});
    canvas.addEventListener("pointermove", event => {{
      const rect = canvas.getBoundingClientRect();
      const local = dataFromScreen(event.clientX - rect.left, event.clientY - rect.top);
      readout.textContent = `${{plotData.xLabel}} ${{formatNumber(untransformX(local.x))}} | PSD ${{formatNumber(Math.pow(10, local.y))}}`;
      if (!drag) return;
      const r = plotRect();
      const dx = (event.clientX - drag.x) / r.w * (drag.view.xmax - drag.view.xmin);
      const dy = (event.clientY - drag.y) / r.h * (drag.view.ymax - drag.view.ymin);
      view.xmin = drag.view.xmin - dx;
      view.xmax = drag.view.xmax - dx;
      view.ymin = drag.view.ymin + dy;
      view.ymax = drag.view.ymax + dy;
      draw();
    }});
    canvas.addEventListener("pointerup", () => {{
      canvas.classList.remove("dragging");
      drag = null;
    }});
    canvas.addEventListener("dblclick", resetView);
    document.getElementById("reset").addEventListener("click", resetView);
    function wrapLegendText(context, text, maxWidth) {{
      const words = String(text || "").split(/\\s+/).filter(Boolean);
      const lines = [];
      let line = "";
      for (const word of words) {{
        const next = line ? `${{line}} ${{word}}` : word;
        if (context.measureText(next).width <= maxWidth || !line) {{
          line = next;
        }} else {{
          lines.push(line);
          line = word;
        }}
      }}
      if (line) lines.push(line);
      return lines.length ? lines : [""];
    }}
    function visibleLegendItems() {{
      return visibleSeries().map(series => ({{
        name: series.name,
        color: series.color,
        channel: series.channel
      }}));
    }}
    function saveCanvasWithLegend() {{
      draw();
      const rect = canvas.getBoundingClientRect();
      const scale = canvas.width / Math.max(1, rect.width);
      const legendItems = visibleLegendItems();
      const legendWidth = Math.round(430 * scale);
      const padding = Math.round(22 * scale);
      const rowGap = Math.round(9 * scale);
      const lineHeight = Math.round(17 * scale);
      const swatchWidth = Math.round(30 * scale);
      const legendTextWidth = legendWidth - padding * 2 - swatchWidth - Math.round(12 * scale);
      const measure = document.createElement("canvas").getContext("2d");
      measure.font = `${{12 * scale}}px Segoe UI, Arial`;
      const wrappedRows = legendItems.map(item => ({{
        ...item,
        lines: wrapLegendText(measure, item.name, legendTextWidth)
      }}));
      const legendHeight = padding * 2 + Math.round(28 * scale) + wrappedRows.reduce(
        (total, row) => total + Math.max(lineHeight, row.lines.length * lineHeight) + rowGap,
        0
      );
      const output = document.createElement("canvas");
      output.width = canvas.width + legendWidth;
      output.height = Math.max(canvas.height, legendHeight);
      const out = output.getContext("2d");
      out.fillStyle = "#ffffff";
      out.fillRect(0, 0, output.width, output.height);
      out.drawImage(canvas, 0, 0);
      const left = canvas.width + padding;
      let y = padding;
      out.fillStyle = "#12353c";
      out.font = `700 ${{15 * scale}}px Segoe UI, Arial`;
      out.textBaseline = "top";
      out.fillText("Legend", left, y);
      y += Math.round(30 * scale);
      out.font = `${{12 * scale}}px Segoe UI, Arial`;
      for (const row of wrappedRows) {{
        const rowHeight = Math.max(lineHeight, row.lines.length * lineHeight);
        const centerY = y + Math.round(rowHeight / 2);
        out.strokeStyle = row.color;
        out.lineWidth = Math.max(2, Math.round(2 * scale));
        out.beginPath();
        out.moveTo(left, centerY);
        out.lineTo(left + swatchWidth, centerY);
        out.stroke();
        out.fillStyle = "#12353c";
        row.lines.forEach((line, index) => {{
          out.fillText(line, left + swatchWidth + Math.round(12 * scale), y + index * lineHeight);
        }});
        y += rowHeight + rowGap;
      }}
      output.toBlob(blob => {{
        if (!blob) return;
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `${{plotData.mode || "fft"}}_comparison_with_legend.png`;
        link.click();
        URL.revokeObjectURL(url);
      }}, "image/png");
    }}
    document.getElementById("savePng").addEventListener("click", () => {{
      saveCanvasWithLegend();
    }});
    document.getElementById("selectAll").addEventListener("click", () => {{
      plotData.series.forEach(s => s.visible = true);
      renderLegend(); draw();
    }});
    document.getElementById("selectNone").addEventListener("click", () => {{
      plotData.series.forEach(s => s.visible = false);
      renderLegend(); draw();
    }});
    filter.addEventListener("input", () => {{ resetView(); }});
    window.addEventListener("resize", resizeCanvas);
    renderChannelTabs();
    renderLegend();
    resetView();
    resizeCanvas();
  </script>
</body>
</html>
"""
    html_path.write_text(html, encoding="utf-8")


def downsample_for_plot(
    frequency_hz: np.ndarray,
    psd: np.ndarray,
    max_plot_points: int,
) -> tuple[np.ndarray, np.ndarray]:
    if max_plot_points <= 0 or frequency_hz.size <= max_plot_points:
        return frequency_hz, psd

    bucket_count = max(1, max_plot_points // 4)
    edges = np.linspace(0, frequency_hz.size - 1, bucket_count + 1).astype(int)
    selected: list[int] = [0, frequency_hz.size - 1]
    for start, stop in zip(edges[:-1], edges[1:]):
        if stop <= start:
            continue
        segment = psd[start : stop + 1]
        finite = np.flatnonzero(np.isfinite(segment))
        if finite.size == 0:
            continue
        finite_indexes = start + finite
        selected.append(start)
        selected.append(stop)
        selected.append(int(finite_indexes[np.argmax(psd[finite_indexes])]))
        selected.append(int(finite_indexes[np.argmin(psd[finite_indexes])]))

    indexes = np.array(sorted(set(index for index in selected if 0 <= index < frequency_hz.size)), dtype=int)
    return frequency_hz[indexes], psd[indexes]


def save_manifest(manifest_path: Path, series: list[FftCsvSeries], mode: FftMode, plot_path: Path, html_path: Path) -> None:
    payload = {
        "mode": mode,
        "plot_path": str(plot_path),
        "interactive_html_path": str(html_path),
        "series_count": len(series),
        "csv_count": len({str(item.csv_path) for item in series}),
        "series": [
            {
                "run_name": item.run_name,
                "run_description": item.run_description,
                "series_name": item.series_name,
                "channel_index": item.channel_index,
                "channel_label": item.channel_label,
                "csv_path": str(item.csv_path),
                "min_frequency_hz": float(np.min(item.frequency_hz)),
                "max_frequency_hz": float(np.max(item.frequency_hz)),
                "points": int(item.frequency_hz.size),
            }
            for item in series
        ],
    }
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def escape_html(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Overlay all saved raw-interleaved FFT analysis CSV lines.")
    parser.add_argument("root", nargs="?", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--mode", choices=["low", "high"], default="low")
    parser.add_argument(
        "--max-plot-points",
        type=int,
        default=0,
        help="Maximum points per line for display payloads. Use 0 to include every CSV point.",
    )
    args = parser.parse_args()

    plot_path = compare_fft_analysis(args.root, mode=args.mode, max_plot_points=args.max_plot_points)
    print(f"Saved comparison plot: {plot_path}")


if __name__ == "__main__":
    main()
