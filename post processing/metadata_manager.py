from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
DEFAULT_ROOT = Path(r"D:\Quantum Squeezing Project\DataFiles")

FIELD_SPECS = [
    ("Sample", "Sample", "text"),
    ("Experiment Tag", "ExperimentTag", "text"),
    ("Description", "Description", "text"),
    ("Tags", "Tags", "tags"),
    ("Filename", "Filename", "text"),
    ("Duration", "Duration", "text"),
    ("Star Measurement", "StarMeasurement", "bool"),
    ("Temperature K", "PhysicsData.Temperature_K", "float"),
    ("Temperature C", "PhysicsData.EnvironmentTemperature_C", "float"),
    ("Sample Power mW", "PhysicsData.OnSamplePower_mW", "float"),
    ("Power 1 mW", "PhysicsData.Power_mW_1", "float"),
    ("Power 2 mW", "PhysicsData.Power_mW_2", "float"),
    ("Use OPO", "PhysicsData.UseOPO", "bool"),
    ("Attenuator Applied", "PhysicsData.PowerDetectorAttenuatorApplied", "bool"),
    ("Attenuator Count", "PhysicsData.PowerDetectorAttenuatorCount", "float"),
    ("Attenuator Each dB", "PhysicsData.PowerDetectorAttenuatorEach_dB", "float"),
    ("Attenuator Total dB", "PhysicsData.PowerDetectorAttenuatorTotal_dB", "float"),
    ("Attenuator Correction Factor", "PhysicsData.PowerDetectorAttenuatorCorrectionFactor", "float"),
    ("Laser Wavelength nm", "PhysicsData.LaserWavelength_nm", "float"),
    ("Detector", "PhysicsData.Detector", "text"),
    ("Detector Responsivity A/W", "PhysicsData.DetectorResponsivity_A_per_W", "float"),
    ("Shot Noise urad2/rtHz", "PhysicsData.ShotNoiseResult_urad2_rtHz", "float"),
    ("Shot Noise V2/rtHz", "PhysicsData.ShotNoiseResult_V2_rtHz", "float"),
    ("Scan Range mm", "PhysicsData.ScanRange_mm", "float"),
    ("Scan Min mm", "PhysicsData.ScanMin_mm", "float"),
    ("Scan Max mm", "PhysicsData.ScanMax_mm", "float"),
]
HTML_EDITOR_SERVERS: list[object] = []


def safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return ", ".join(safe_text(item) for item in value if safe_text(item))
    return default


def safe_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [safe_text(item) for item in value if safe_text(item)]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def safe_float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def first_value(payload: dict[str, Any], *paths: tuple[str, ...]) -> Any:
    for path in paths:
        current: Any = payload
        for key in path:
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(key)
        if current not in (None, ""):
            return current
    return None


def normalize_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    physics_source = payload.get("PhysicsData")
    physics = dict(physics_source) if isinstance(physics_source, dict) else {}

    normalized["MetadataSchemaVersion"] = SCHEMA_VERSION
    normalized["Sample"] = safe_text(payload.get("Sample"))
    normalized["ExperimentTag"] = safe_text(
        first_value(
            payload,
            ("ExperimentTag",),
            ("ExpTag",),
            ("Experiment",),
            ("ExperimentName",),
            ("Configuration", "ExperimentTag"),
            ("Configuration", "ExpTag"),
            ("PhysicsData", "ExperimentTag"),
            ("PhysicsData", "ExpTag"),
        )
    )
    normalized["Description"] = safe_text(payload.get("Description"))
    normalized["Tags"] = safe_tags(payload.get("Tags"))
    normalized["Filename"] = safe_text(payload.get("Filename"))
    normalized["Duration"] = safe_text(payload.get("Duration"))

    for key in (
        "Power_mW_1",
        "Power_mW_2",
        "OnSamplePower_mW",
        "SamplePower_mW",
        "Temperature_K",
        "EnvironmentTemperature_K",
        "EnvironmentTemperature_C",
        "Sensitivity_V_photon",
        "ShotNoiseResult_urad2_rtHz",
        "ShotNoiseResult_V2_rtHz",
        "ScanRange_mm",
        "ScanMin_mm",
        "ScanMax_mm",
        "PowerDetectorAttenuatorCount",
        "PowerDetectorAttenuatorEach_dB",
        "PowerDetectorAttenuatorTotal_dB",
        "PowerDetectorAttenuatorCorrectionFactor",
    ):
        value = safe_float_or_none(first_value(payload, ("PhysicsData", key), (key,)))
        if value is not None:
            physics[key] = value

    for key in ("UseOPO", "PowerDetectorAttenuatorApplied", "IsDarkNoiseRun", "StarMeasurement"):
        value = first_value(payload, ("PhysicsData", key), (key,))
        if value is not None:
            if isinstance(value, str):
                value = value.strip().lower() in {"1", "true", "yes", "on"}
            else:
                value = bool(value)
            if key == "StarMeasurement":
                normalized[key] = value
            else:
                physics[key] = value

    normalized["PhysicsData"] = physics
    return normalized


def normalize_file(path: Path, write: bool = False) -> bool:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} does not contain a JSON object")

    normalized = normalize_metadata(payload)
    changed = normalized != payload
    if changed and write:
        path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    return changed


def find_metadata_paths(root: Path) -> list[Path]:
    if root.name.lower() == "metadata.json":
        return [root]
    return sorted(root.rglob("metadata.json"))


def path_get(payload: dict[str, Any], dotted_path: str) -> Any:
    current: Any = payload
    for part in dotted_path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def path_set(payload: dict[str, Any], dotted_path: str, value: Any) -> None:
    parts = [part.strip() for part in dotted_path.split(".") if part.strip()]
    if not parts:
        raise ValueError("Field path is empty.")
    current: dict[str, Any] = payload
    for part in parts[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    current[parts[-1]] = value


def editor_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ", ".join(safe_text(item) for item in value if safe_text(item))
    return str(value)


def parse_custom_value(raw_value: str) -> Any:
    value = raw_value.strip()
    if not value:
        return ""
    lower_value = value.lower()
    if lower_value in {"true", "false"}:
        return lower_value == "true"
    if lower_value in {"null", "none"}:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def parse_field_value(raw_value: Any, kind: str) -> Any:
    if kind == "bool":
        if isinstance(raw_value, str):
            return raw_value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(raw_value)
    if kind == "tags":
        return [tag.strip() for tag in str(raw_value).split(",") if tag.strip()]
    if kind == "float":
        return safe_float_or_none(raw_value)
    return str(raw_value).strip()


def html_editor_page() -> str:
    field_specs_json = json.dumps(
        [{"label": label, "path": path, "kind": kind} for label, path, kind in FIELD_SPECS]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Metadata Editor</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #12353c;
      --muted: #60747a;
      --line: #d7e1e3;
      --paper: #ffffff;
      --bg: #f3f1ea;
      --accent: #176f7a;
      --danger: #9b2f2f;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", Arial, sans-serif;
      background: var(--bg);
      color: var(--ink);
    }}
    header {{
      display: flex;
      gap: 16px;
      align-items: center;
      justify-content: space-between;
      padding: 16px 22px;
      background: var(--ink);
      color: white;
    }}
    h1 {{ margin: 0; font-size: 22px; font-weight: 700; }}
    main {{
      display: grid;
      grid-template-columns: minmax(260px, 360px) 1fr;
      gap: 16px;
      padding: 16px;
      min-height: calc(100vh - 66px);
    }}
    aside, section {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 6px;
      min-width: 0;
    }}
    aside {{ padding: 12px; }}
    section {{ padding: 16px; }}
    input, textarea, select, button {{
      font: inherit;
    }}
    input, textarea, select {{
      width: 100%;
      border: 1px solid #b9c6c9;
      border-radius: 4px;
      padding: 8px 9px;
      background: white;
      color: var(--ink);
    }}
    textarea {{
      min-height: 300px;
      font-family: Consolas, "Courier New", monospace;
      resize: vertical;
    }}
    button {{
      border: 1px solid #0f5962;
      border-radius: 4px;
      background: var(--accent);
      color: white;
      padding: 8px 12px;
      cursor: pointer;
    }}
    button.secondary {{
      background: white;
      color: var(--ink);
      border-color: #b9c6c9;
    }}
    button.danger {{
      background: var(--danger);
      border-color: var(--danger);
    }}
    .toolbar {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
      margin-bottom: 14px;
    }}
    .view-tabs {{
      display: flex;
      gap: 4px;
      padding: 3px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #f7fafb;
    }}
    .view-tabs button {{
      background: transparent;
      color: var(--ink);
      border-color: transparent;
      padding: 7px 10px;
    }}
    .view-tabs button.active {{
      background: var(--accent);
      color: white;
      border-color: var(--accent);
    }}
    .view.hidden {{ display: none; }}
    .run-list {{
      margin-top: 10px;
      display: grid;
      gap: 6px;
      max-height: calc(100vh - 160px);
      overflow: auto;
    }}
    .run-item {{
      border: 1px solid var(--line);
      border-radius: 4px;
      padding: 8px;
      cursor: pointer;
      background: #fbfcfc;
      overflow-wrap: anywhere;
    }}
    .run-item.active {{
      border-color: var(--accent);
      background: #e8f4f5;
    }}
    .run-item-main {{
      font-weight: 700;
      margin-bottom: 4px;
    }}
    .run-item-sub {{
      color: var(--muted);
      font-size: 12px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(220px, 1fr));
      gap: 12px 16px;
    }}
    .workbook-toolbar {{
      display: grid;
      grid-template-columns: minmax(220px, 380px) 1fr;
      gap: 12px;
      align-items: center;
      margin-bottom: 10px;
    }}
    .workbook-wrap {{
      border: 1px solid var(--line);
      border-radius: 4px;
      height: calc(100vh - 190px);
      overflow: auto;
      background: white;
    }}
    .workbook-table {{
      border-collapse: separate;
      border-spacing: 0;
      min-width: 1700px;
      width: max-content;
      font-size: 13px;
    }}
    .workbook-table th, .workbook-table td {{
      border-right: 1px solid #e5ecee;
      border-bottom: 1px solid #e5ecee;
      padding: 0;
      height: 35px;
      vertical-align: middle;
      background: white;
    }}
    .workbook-table th {{
      top: 0;
      z-index: 4;
      background: #edf5f6;
      color: var(--ink);
      font-weight: 700;
      padding: 8px;
      white-space: nowrap;
    }}
    .workbook-table th:first-child, .workbook-table td:first-child {{
      position: sticky;
      left: 0;
      z-index: 3;
      width: 190px;
      min-width: 190px;
      max-width: 190px;
      font-family: "Segoe UI", Arial, sans-serif;
      overflow-wrap: anywhere;
      background: #f8fbfb;
      padding: 8px;
    }}
    .workbook-table th:first-child {{
      z-index: 5;
      background: #edf5f6;
    }}
    .workbook-table tr.active td:first-child {{
      background: #dff0f2;
    }}
    .workbook-table td.dirty {{
      background: #fff8d7;
    }}
    .cell-input {{
      width: 100%;
      min-width: 110px;
      height: 34px;
      border: 0;
      border-radius: 0;
      padding: 6px 8px;
      background: transparent;
    }}
    .cell-input:focus {{
      outline: 2px solid var(--accent);
      outline-offset: -2px;
      background: white;
    }}
    .cell-check {{
      width: 100%;
      height: 34px;
      display: grid;
      place-items: center;
    }}
    .cell-check input {{
      width: 16px;
      height: 16px;
      accent-color: var(--accent);
    }}
    label {{
      display: grid;
      gap: 5px;
      color: var(--muted);
      font-size: 13px;
    }}
    label span {{
      color: var(--ink);
      font-weight: 600;
    }}
    .checkbox-row {{
      display: flex;
      align-items: center;
      gap: 8px;
      min-height: 37px;
    }}
    .checkbox-row input {{ width: auto; }}
    .custom {{
      display: grid;
      grid-template-columns: minmax(180px, 1fr) minmax(240px, 2fr);
      gap: 12px;
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid var(--line);
    }}
    .raw-panel {{
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid var(--line);
    }}
    .all-metadata {{
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid var(--line);
    }}
    .all-metadata-header {{
      display: grid;
      grid-template-columns: 1fr minmax(220px, 360px);
      gap: 12px;
      align-items: center;
      margin-bottom: 8px;
    }}
    .all-metadata-title {{
      font-weight: 700;
    }}
    .metadata-table-wrap {{
      border: 1px solid var(--line);
      border-radius: 4px;
      max-height: 360px;
      overflow: auto;
      background: #fbfcfc;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      border-bottom: 1px solid #e5ecee;
      padding: 7px 8px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      position: sticky;
      top: 0;
      background: #edf5f6;
      z-index: 1;
    }}
    td:first-child {{
      width: 34%;
      font-family: Consolas, "Courier New", monospace;
      color: var(--ink);
      overflow-wrap: anywhere;
    }}
    td:last-child {{
      font-family: Consolas, "Courier New", monospace;
      overflow-wrap: anywhere;
      white-space: pre-wrap;
    }}
    .status {{
      color: var(--muted);
      min-height: 22px;
      overflow-wrap: anywhere;
    }}
    .error {{ color: var(--danger); }}
    @media (max-width: 900px) {{
      main {{ grid-template-columns: 1fr; }}
      .grid, .custom, .all-metadata-header {{ grid-template-columns: 1fr; }}
      .workbook-toolbar {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Metadata Editor</h1>
    <div id="status" class="status">Loading...</div>
  </header>
  <main>
    <aside>
      <input id="search" type="search" placeholder="Search runs">
      <div id="runList" class="run-list"></div>
    </aside>
    <section>
      <div class="toolbar">
        <div class="view-tabs">
          <button id="workbookViewButton" class="active" type="button">Workbook</button>
          <button id="formViewButton" type="button">Run Form</button>
        </div>
        <button id="saveWorkbook">Save Workbook</button>
        <button id="saveFields" class="secondary">Save Fields</button>
        <button id="saveRaw" class="secondary">Save Raw JSON</button>
        <button id="reload" class="secondary">Reload</button>
      </div>
      <div id="workbookView" class="view">
        <div class="workbook-toolbar">
          <input id="workbookSearch" type="search" placeholder="Search workbook">
          <div id="workbookCount" class="status"></div>
        </div>
        <div class="workbook-wrap">
          <table id="workbookTable" class="workbook-table">
            <thead id="workbookHead"></thead>
            <tbody id="workbookBody"></tbody>
          </table>
        </div>
      </div>
      <div id="formView" class="view hidden">
        <div id="pathLabel" class="status"></div>
        <div id="fields" class="grid"></div>
        <div class="custom">
          <label><span>Custom field path</span><input id="customPath" placeholder="PhysicsData.NewField"></label>
          <label><span>Custom value</span><input id="customValue" placeholder="JSON value or text"></label>
        </div>
        <div class="all-metadata">
          <div class="all-metadata-header">
            <div class="all-metadata-title">All Metadata Fields</div>
            <input id="allMetadataSearch" type="search" placeholder="Search metadata paths or values">
          </div>
          <div class="metadata-table-wrap">
            <table>
              <thead><tr><th>Path</th><th>Value</th></tr></thead>
              <tbody id="allMetadataRows"></tbody>
            </table>
          </div>
        </div>
        <div class="raw-panel">
          <label><span>Raw metadata.json</span><textarea id="rawJson" spellcheck="false"></textarea></label>
        </div>
      </div>
    </section>
  </main>
  <script>
    const FIELD_SPECS = {field_specs_json};
    let paths = [];
    let activePath = null;
    let activePayload = {{}};
    let workbookRows = [];
    let dirtyWorkbookRows = new Set();
    let activeView = "workbook";

    const statusEl = document.getElementById("status");
    const runListEl = document.getElementById("runList");
    const fieldsEl = document.getElementById("fields");
    const pathLabelEl = document.getElementById("pathLabel");
    const rawJsonEl = document.getElementById("rawJson");
    const allMetadataRowsEl = document.getElementById("allMetadataRows");
    const allMetadataSearchEl = document.getElementById("allMetadataSearch");
    const workbookHeadEl = document.getElementById("workbookHead");
    const workbookBodyEl = document.getElementById("workbookBody");
    const workbookSearchEl = document.getElementById("workbookSearch");
    const workbookCountEl = document.getElementById("workbookCount");

    function setStatus(text, isError = false) {{
      statusEl.textContent = text;
      statusEl.className = isError ? "status error" : "status";
    }}

    function pathGet(obj, dottedPath) {{
      return dottedPath.split(".").reduce((current, key) => {{
        if (!current || typeof current !== "object") return undefined;
        return current[key];
      }}, obj);
    }}

    function setView(viewName) {{
      activeView = viewName;
      document.getElementById("workbookView").classList.toggle("hidden", viewName !== "workbook");
      document.getElementById("formView").classList.toggle("hidden", viewName !== "form");
      document.getElementById("workbookViewButton").classList.toggle("active", viewName === "workbook");
      document.getElementById("formViewButton").classList.toggle("active", viewName === "form");
    }}

    function editorValue(value) {{
      if (value === undefined || value === null) return "";
      if (Array.isArray(value)) return value.join(", ");
      if (typeof value === "boolean") return value ? "true" : "false";
      return String(value);
    }}

    function displayMetadataValue(value) {{
      if (value === undefined) return "";
      if (value === null) return "null";
      if (typeof value === "object") return JSON.stringify(value);
      return String(value);
    }}

    function flattenMetadata(value, prefix = "") {{
      if (Array.isArray(value)) {{
        if (value.length === 0) return [{{ path: prefix, value: "[]" }}];
        return value.flatMap((item, index) => flattenMetadata(item, `${{prefix}}[${{index}}]`));
      }}
      if (value && typeof value === "object") {{
        const entries = Object.entries(value);
        if (entries.length === 0) return [{{ path: prefix, value: "{{}}" }}];
        return entries.flatMap(([key, item]) => flattenMetadata(item, prefix ? `${{prefix}}.${{key}}` : key));
      }}
      return [{{ path: prefix, value: displayMetadataValue(value) }}];
    }}

    function renderAllMetadata(payload) {{
      const needle = allMetadataSearchEl.value.trim().toLowerCase();
      const rows = flattenMetadata(payload)
        .filter(row => !needle || row.path.toLowerCase().includes(needle) || row.value.toLowerCase().includes(needle));
      allMetadataRowsEl.innerHTML = "";
      rows.forEach(row => {{
        const tr = document.createElement("tr");
        const pathCell = document.createElement("td");
        const valueCell = document.createElement("td");
        pathCell.textContent = row.path;
        valueCell.textContent = row.value;
        tr.append(pathCell, valueCell);
        allMetadataRowsEl.appendChild(tr);
      }});
    }}

    function renderRuns() {{
      const needle = document.getElementById("search").value.trim().toLowerCase();
      runListEl.innerHTML = "";
      paths
        .filter(item => !needle || [
          item.label, item.path, item.sample, item.expTag, item.attenuation
        ].join(" ").toLowerCase().includes(needle))
        .forEach(item => {{
          const div = document.createElement("div");
          div.className = "run-item" + (item.path === activePath ? " active" : "");
          div.innerHTML = `
            <div class="run-item-main">${{item.label}}</div>
            <div class="run-item-sub">${{item.sample || "-"}} - ${{item.expTag || "-"}}</div>
            <div class="run-item-sub">Atten. factor: ${{item.attenuation || "-"}}</div>
          `;
          div.title = item.path;
          div.addEventListener("click", () => loadMetadata(item.path));
          runListEl.appendChild(div);
        }});
    }}

    function renderWorkbookHeader() {{
      const tr = document.createElement("tr");
      const runTh = document.createElement("th");
      runTh.textContent = "Run";
      tr.appendChild(runTh);
      FIELD_SPECS.forEach(spec => {{
        const th = document.createElement("th");
        th.textContent = spec.label;
        th.title = spec.path;
        tr.appendChild(th);
      }});
      workbookHeadEl.innerHTML = "";
      workbookHeadEl.appendChild(tr);
    }}

    function workbookSearchBlob(row) {{
      return [
        row.label, row.path, row.sample, row.expTag,
        ...Object.values(row.fields || {{}})
      ].join(" ").toLowerCase();
    }}

    function markWorkbookDirty(path, cell) {{
      dirtyWorkbookRows.add(path);
      cell.classList.add("dirty");
      setStatus(`${{dirtyWorkbookRows.size}} workbook row(s) changed.`);
    }}

    function renderWorkbook() {{
      const needle = workbookSearchEl.value.trim().toLowerCase();
      const rows = workbookRows.filter(row => !needle || workbookSearchBlob(row).includes(needle));
      workbookCountEl.textContent = `${{rows.length}} of ${{workbookRows.length}} rows`;
      workbookBodyEl.innerHTML = "";
      rows.forEach(row => {{
        const tr = document.createElement("tr");
        tr.className = row.path === activePath ? "active" : "";
        const runCell = document.createElement("td");
        runCell.innerHTML = `<strong>${{row.label}}</strong><br><span class="run-item-sub">${{row.sample || "-"}} - ${{row.expTag || "-"}}</span>`;
        runCell.title = row.path;
        runCell.addEventListener("click", () => loadMetadata(row.path));
        tr.appendChild(runCell);

        FIELD_SPECS.forEach(spec => {{
          const td = document.createElement("td");
          td.dataset.path = row.path;
          td.dataset.field = spec.path;
          if (dirtyWorkbookRows.has(row.path)) td.classList.add("dirty");
          if (spec.kind === "bool") {{
            const wrapper = document.createElement("div");
            wrapper.className = "cell-check";
            const input = document.createElement("input");
            input.type = "checkbox";
            input.checked = row.fields[spec.path] === true || row.fields[spec.path] === "true";
            input.addEventListener("change", () => markWorkbookDirty(row.path, td));
            wrapper.appendChild(input);
            td.appendChild(wrapper);
          }} else {{
            const input = document.createElement("input");
            input.className = "cell-input";
            input.value = row.fields[spec.path] ?? "";
            input.addEventListener("input", () => markWorkbookDirty(row.path, td));
            td.appendChild(input);
          }}
          tr.appendChild(td);
        }});
        workbookBodyEl.appendChild(tr);
      }});
    }}

    function renderFields(payload) {{
      fieldsEl.innerHTML = "";
      FIELD_SPECS.forEach(spec => {{
        if (spec.kind === "bool") {{
          const label = document.createElement("label");
          label.className = "checkbox-row";
          const input = document.createElement("input");
          input.type = "checkbox";
          input.dataset.path = spec.path;
          input.checked = Boolean(pathGet(payload, spec.path));
          const text = document.createElement("span");
          text.textContent = spec.label;
          label.append(input, text);
          fieldsEl.appendChild(label);
          return;
        }}
        const label = document.createElement("label");
        const span = document.createElement("span");
        span.textContent = spec.label;
        const input = document.createElement("input");
        input.dataset.path = spec.path;
        input.dataset.kind = spec.kind;
        input.value = editorValue(pathGet(payload, spec.path));
        label.append(span, input);
        fieldsEl.appendChild(label);
      }});
    }}

    async function loadIndex() {{
      const response = await fetch("/api/index");
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      paths = data.paths;
      renderRuns();
      const initial = paths.find(item => item.path === data.initialPath) || paths[0];
      await loadWorkbook();
      if (initial) await loadMetadata(initial.path);
      else setStatus("No metadata.json files found.", true);
    }}

    async function loadWorkbook() {{
      const response = await fetch("/api/workbook");
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      workbookRows = data.rows;
      dirtyWorkbookRows.clear();
      renderWorkbookHeader();
      renderWorkbook();
    }}

    async function loadMetadata(path) {{
      const response = await fetch(`/api/metadata?path=${{encodeURIComponent(path)}}`);
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      activePath = data.path;
      activePayload = data.payload;
      pathLabelEl.textContent = activePath;
      rawJsonEl.value = JSON.stringify(activePayload, null, 2);
      document.getElementById("customPath").value = "";
      document.getElementById("customValue").value = "";
      renderFields(activePayload);
      renderAllMetadata(activePayload);
      renderRuns();
      renderWorkbook();
      setStatus("Loaded.");
    }}

    function collectFields() {{
      const fields = {{}};
      fieldsEl.querySelectorAll("input[data-path]").forEach(input => {{
        fields[input.dataset.path] = input.type === "checkbox" ? input.checked : input.value;
      }});
      return fields;
    }}

    async function saveFields() {{
      if (!activePath) return;
      const response = await fetch("/api/metadata", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{
          path: activePath,
          mode: "fields",
          fields: collectFields(),
          customPath: document.getElementById("customPath").value,
          customValue: document.getElementById("customValue").value
        }})
      }});
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      activePayload = data.payload;
      rawJsonEl.value = JSON.stringify(activePayload, null, 2);
      renderFields(activePayload);
      renderAllMetadata(activePayload);
      setStatus("Saved fields.");
    }}

    async function saveRaw() {{
      if (!activePath) return;
      const rawPayload = JSON.parse(rawJsonEl.value);
      const response = await fetch("/api/metadata", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ path: activePath, mode: "raw", payload: rawPayload }})
      }});
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      activePayload = data.payload;
      rawJsonEl.value = JSON.stringify(activePayload, null, 2);
      renderFields(activePayload);
      renderAllMetadata(activePayload);
      setStatus("Saved raw JSON.");
    }}

    function collectWorkbookChanges() {{
      const rowMap = new Map(workbookRows.map(row => [row.path, row]));
      const changes = [];
      dirtyWorkbookRows.forEach(path => {{
        const row = rowMap.get(path);
        if (!row) return;
        const fields = {{}};
        workbookBodyEl.querySelectorAll("td[data-path]").forEach(td => {{
          if (td.dataset.path !== path) return;
          const fieldPath = td.dataset.field;
          const input = td.querySelector("input");
          if (!fieldPath || !input) return;
          fields[fieldPath] = input.type === "checkbox" ? input.checked : input.value;
        }});
        changes.push({{ path, fields }});
      }});
      return changes;
    }}

    async function saveWorkbook() {{
      const rows = collectWorkbookChanges();
      if (!rows.length) {{
        setStatus("No workbook changes to save.");
        return;
      }}
      const response = await fetch("/api/workbook", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ rows }})
      }});
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      workbookRows = data.rows;
      paths = data.paths;
      dirtyWorkbookRows.clear();
      renderRuns();
      renderWorkbook();
      if (activePath) await loadMetadata(activePath);
      setStatus("Saved workbook.");
    }}

    document.getElementById("search").addEventListener("input", renderRuns);
    workbookSearchEl.addEventListener("input", renderWorkbook);
    allMetadataSearchEl.addEventListener("input", () => renderAllMetadata(activePayload));
    document.getElementById("workbookViewButton").addEventListener("click", () => setView("workbook"));
    document.getElementById("formViewButton").addEventListener("click", () => setView("form"));
    document.getElementById("saveWorkbook").addEventListener("click", () => saveWorkbook().catch(err => setStatus(err.message, true)));
    document.getElementById("saveFields").addEventListener("click", () => saveFields().catch(err => setStatus(err.message, true)));
    document.getElementById("saveRaw").addEventListener("click", () => saveRaw().catch(err => setStatus(err.message, true)));
    document.getElementById("reload").addEventListener("click", () => activePath && loadMetadata(activePath).catch(err => setStatus(err.message, true)));

    loadIndex().catch(err => setStatus(err.message, true));
  </script>
</body>
</html>
"""


def launch_html_editor(root: Path, wait: bool = True) -> str:
    import http.server
    import socketserver
    import threading
    import urllib.parse
    import webbrowser

    requested_root = root.resolve()
    initial_path: Path | None = None
    if requested_root.name.lower() == "metadata.json":
        initial_path = requested_root
        root = requested_root.parent.parent if requested_root.parent.parent.exists() else requested_root.parent
        paths = find_metadata_paths(root)
        if initial_path not in paths:
            paths.insert(0, initial_path)
    elif (requested_root / "metadata.json").is_file():
        initial_path = (requested_root / "metadata.json").resolve()
        root = requested_root.parent if requested_root.parent.exists() else requested_root
        paths = find_metadata_paths(root)
        if initial_path not in paths:
            paths.insert(0, initial_path)
    else:
        root = requested_root
        paths = find_metadata_paths(root)
        if not paths and root.name.lower() != "metadata.json":
            candidate = root / "metadata.json"
            paths = [candidate]
    if not paths:
        paths = [requested_root]
        initial_path = requested_root
    initial_path = initial_path or paths[0]

    allowed_paths = {path.resolve(): path for path in paths}

    def resolve_allowed(raw_path: str) -> Path:
        path = Path(raw_path).resolve()
        if path not in allowed_paths:
            raise ValueError("Metadata path is outside this editor session.")
        return allowed_paths[path]

    def payload_for(path: Path) -> dict[str, Any]:
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError(f"{path} does not contain a JSON object")
            return normalize_metadata(payload)
        return normalize_metadata({})

    def refresh_datafiles_browser_index(path: Path) -> None:
        try:
            from datafiles_browser import index_run_folder

            index_run_folder(path.parent, root)
        except Exception as exc:
            print(f"Warning: could not update DataFiles Browser index for {path.parent}: {exc}")

    def save_payload(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_metadata(payload)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
        refresh_datafiles_browser_index(path)
        return normalized

    def index_item(path: Path) -> dict[str, str]:
        try:
            payload = payload_for(path)
        except Exception:
            payload = {}
        physics = payload.get("PhysicsData")
        physics = physics if isinstance(physics, dict) else {}
        attenuation = physics.get("PowerDetectorAttenuatorCorrectionFactor", "")
        return {
            "path": str(path.resolve()),
            "label": path.parent.name if path.name.lower() == "metadata.json" else path.name,
            "sample": safe_text(payload.get("Sample")),
            "expTag": safe_text(payload.get("ExperimentTag")),
            "attenuation": editor_value(attenuation),
        }

    def workbook_row(path: Path) -> dict[str, object]:
        payload = payload_for(path)
        fields = {
            field_path: editor_value(path_get(payload, field_path))
            for _label, field_path, _kind in FIELD_SPECS
        }
        for _label, field_path, kind in FIELD_SPECS:
            if kind == "bool":
                fields[field_path] = bool(path_get(payload, field_path))
        return {**index_item(path), "fields": fields}

    def save_field_values(path: Path, fields: dict[str, object]) -> dict[str, Any]:
        payload = payload_for(path)
        spec_by_path = {field_path: kind for _label, field_path, kind in FIELD_SPECS}
        for field_path, raw_value in fields.items():
            kind = spec_by_path.get(field_path, "text")
            path_set(payload, field_path, parse_field_value(raw_value, kind))
        return save_payload(path, payload)

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def send_json(self, data: object, status: int = 200) -> None:
            body = json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def send_text(self, text: str, status: int = 200, content_type: str = "text/plain") -> None:
            body = text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            try:
                if parsed.path == "/":
                    self.send_text(html_editor_page(), content_type="text/html")
                    return
                if parsed.path == "/api/index":
                    self.send_json(
                        {
                            "root": str(root),
                            "initialPath": str(initial_path.resolve()),
                            "paths": [index_item(path) for path in paths],
                        }
                    )
                    return
                if parsed.path == "/api/metadata":
                    query = urllib.parse.parse_qs(parsed.query)
                    path = resolve_allowed(query.get("path", [""])[0])
                    self.send_json({"path": str(path.resolve()), "payload": payload_for(path)})
                    return
                if parsed.path == "/api/workbook":
                    self.send_json({"rows": [workbook_row(path) for path in paths]})
                    return
                self.send_text("Not found", status=404)
            except Exception as exc:
                self.send_text(str(exc), status=400)

        def do_POST(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/api/workbook":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    data = json.loads(self.rfile.read(length).decode("utf-8"))
                    rows = data.get("rows")
                    if not isinstance(rows, list):
                        raise ValueError("Workbook rows must be a list.")
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        path = resolve_allowed(str(row.get("path", "")))
                        fields = row.get("fields")
                        if not isinstance(fields, dict):
                            continue
                        save_field_values(path, fields)
                    self.send_json({"paths": [index_item(path) for path in paths], "rows": [workbook_row(path) for path in paths]})
                except Exception as exc:
                    self.send_text(str(exc), status=400)
                return

            if parsed.path != "/api/metadata":
                self.send_text("Not found", status=404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                path = resolve_allowed(str(data.get("path", "")))
                mode = data.get("mode")
                if mode == "raw":
                    payload = data.get("payload")
                    if not isinstance(payload, dict):
                        raise ValueError("Raw payload must be a JSON object.")
                else:
                    payload = payload_for(path)
                    fields = data.get("fields")
                    if not isinstance(fields, dict):
                        fields = {}
                    spec_by_path = {field_path: kind for _label, field_path, kind in FIELD_SPECS}
                    for field_path, raw_value in fields.items():
                        kind = spec_by_path.get(field_path, "text")
                        path_set(payload, field_path, parse_field_value(raw_value, kind))
                    custom_path = str(data.get("customPath", "")).strip()
                    if custom_path:
                        path_set(payload, custom_path, parse_custom_value(str(data.get("customValue", ""))))
                saved = save_payload(path, payload)
                self.send_json({"path": str(path.resolve()), "payload": saved})
            except Exception as exc:
                self.send_text(str(exc), status=400)

    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}/"
    HTML_EDITOR_SERVERS.append(server)
    print(f"Metadata HTML editor: {url}")
    webbrowser.open(url)

    if not wait:
        return url

    try:
        input("Press Enter to stop the metadata editor server...")
    finally:
        server.shutdown()
        server.server_close()
        if server in HTML_EDITOR_SERVERS:
            HTML_EDITOR_SERVERS.remove(server)
    return url


def launch_editor(root: Path) -> None:
    import tkinter as tk
    from tkinter import messagebox

    field_specs = FIELD_SPECS

    class MetadataEditor(tk.Tk):
        def __init__(self) -> None:
            super().__init__()
            self.title("Metadata Editor")
            self.geometry("1080x720")
            self.minsize(900, 560)

            self.paths = find_metadata_paths(root)
            self.filtered_paths = list(self.paths)
            self.current_path: Path | None = None
            self.entry_vars: dict[str, tk.StringVar] = {}
            self.bool_vars: dict[str, tk.BooleanVar] = {}
            self.custom_path_var = tk.StringVar()
            self.custom_value_var = tk.StringVar()
            self.status_var = tk.StringVar(value=f"Loaded {len(self.paths)} metadata files from {root}")
            self.search_var = tk.StringVar()
            self.search_var.trace_add("write", lambda *_: self.apply_filter())

            self.columnconfigure(1, weight=1)
            self.rowconfigure(1, weight=1)

            tk.Label(self, text="Search").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))
            tk.Entry(self, textvariable=self.search_var).grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=(10, 4))

            left = tk.Frame(self)
            left.grid(row=1, column=0, sticky="nsew", padx=10, pady=6)
            left.rowconfigure(0, weight=1)

            self.listbox = tk.Listbox(left, width=42, exportselection=False)
            self.listbox.grid(row=0, column=0, sticky="nsew")
            scrollbar = tk.Scrollbar(left, orient="vertical", command=self.listbox.yview)
            scrollbar.grid(row=0, column=1, sticky="ns")
            self.listbox.configure(yscrollcommand=scrollbar.set)
            self.listbox.bind("<<ListboxSelect>>", lambda _event: self.load_selected())

            right = tk.Frame(self)
            right.grid(row=1, column=1, sticky="nsew", padx=(0, 10), pady=6)
            right.columnconfigure(1, weight=1)

            for row, (label, path, kind) in enumerate(field_specs):
                tk.Label(right, text=label).grid(row=row, column=0, sticky="w", pady=3)
                if kind == "bool":
                    var = tk.BooleanVar(value=False)
                    self.bool_vars[path] = var
                    tk.Checkbutton(right, variable=var).grid(row=row, column=1, sticky="w", pady=3)
                    continue
                var = tk.StringVar()
                self.entry_vars[path] = var
                tk.Entry(right, textvariable=var).grid(row=row, column=1, sticky="ew", pady=3)

            custom_row = len(field_specs) + 1
            tk.Label(right, text="Custom field").grid(row=custom_row, column=0, sticky="w", pady=(12, 3))
            tk.Entry(right, textvariable=self.custom_path_var).grid(row=custom_row, column=1, sticky="ew", pady=(12, 3))
            tk.Label(right, text="Custom value").grid(row=custom_row + 1, column=0, sticky="w", pady=3)
            tk.Entry(right, textvariable=self.custom_value_var).grid(row=custom_row + 1, column=1, sticky="ew", pady=3)

            buttons = tk.Frame(right)
            buttons.grid(row=custom_row + 2, column=0, columnspan=2, sticky="e", pady=(14, 0))
            tk.Button(buttons, text="Save", width=12, command=self.save_current).pack(side="left", padx=(0, 8))
            tk.Button(buttons, text="Save && Next", width=12, command=self.save_and_next).pack(side="left", padx=(0, 8))
            tk.Button(buttons, text="Reload", width=12, command=self.reload_current).pack(side="left")

            tk.Label(self, textvariable=self.status_var, anchor="w").grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
            self.populate_list()
            if self.filtered_paths:
                self.listbox.selection_set(0)
                self.load_selected()

        def populate_list(self) -> None:
            self.listbox.delete(0, tk.END)
            for path in self.filtered_paths:
                self.listbox.insert(tk.END, path.parent.name)

        def apply_filter(self) -> None:
            needle = self.search_var.get().strip().lower()
            if not needle:
                self.filtered_paths = list(self.paths)
            else:
                filtered = []
                for path in self.paths:
                    haystack = f"{path.parent.name} {path}".lower()
                    try:
                        payload = normalize_metadata(json.loads(path.read_text(encoding="utf-8")))
                        haystack += " " + " ".join(
                            safe_text(path_get(payload, key))
                            for key in ("Sample", "ExperimentTag", "Description", "Filename", "Duration")
                        ).lower()
                        haystack += " " + ", ".join(safe_tags(payload.get("Tags"))).lower()
                    except Exception:
                        pass
                    if needle in haystack:
                        filtered.append(path)
                self.filtered_paths = filtered
            self.populate_list()
            self.status_var.set(f"Showing {len(self.filtered_paths)} of {len(self.paths)} metadata files.")

        def selected_index(self) -> int | None:
            selection = self.listbox.curselection()
            if not selection:
                return None
            return int(selection[0])

        def load_selected(self) -> None:
            index = self.selected_index()
            if index is None or index >= len(self.filtered_paths):
                return
            self.load_path(self.filtered_paths[index])

        def load_path(self, path: Path) -> None:
            try:
                payload = normalize_metadata(json.loads(path.read_text(encoding="utf-8")))
                self.current_path = path
                for _label, field_path, kind in field_specs:
                    value = path_get(payload, field_path)
                    if kind == "bool":
                        self.bool_vars[field_path].set(bool(value))
                    else:
                        self.entry_vars[field_path].set(editor_value(value))
                self.custom_path_var.set("")
                self.custom_value_var.set("")
                self.status_var.set(f"Editing {path}")
            except Exception as exc:
                messagebox.showerror("Load Failed", f"Could not load metadata:\n{exc}")

        def payload_from_form(self) -> dict[str, Any]:
            if self.current_path is None:
                raise ValueError("No metadata file selected.")
            payload = json.loads(self.current_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                payload = {}
            payload = normalize_metadata(payload)

            for _label, field_path, kind in field_specs:
                if kind == "bool":
                    path_set(payload, field_path, self.bool_vars[field_path].get())
                    continue
                raw_value = self.entry_vars[field_path].get().strip()
                if kind == "tags":
                    value: Any = [tag.strip() for tag in raw_value.split(",") if tag.strip()]
                elif kind == "float":
                    value = safe_float_or_none(raw_value)
                else:
                    value = raw_value
                path_set(payload, field_path, value)

            custom_path = self.custom_path_var.get().strip()
            if custom_path:
                path_set(payload, custom_path, parse_custom_value(self.custom_value_var.get()))

            return normalize_metadata(payload)

        def save_current(self) -> bool:
            if self.current_path is None:
                return False
            try:
                payload = self.payload_from_form()
                self.current_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                self.status_var.set(f"Saved {self.current_path}")
                return True
            except Exception as exc:
                messagebox.showerror("Save Failed", f"Could not save metadata:\n{exc}")
                return False

        def save_and_next(self) -> None:
            if not self.save_current():
                return
            index = self.selected_index()
            if index is None:
                return
            next_index = min(index + 1, len(self.filtered_paths) - 1)
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(next_index)
            self.listbox.see(next_index)
            self.load_selected()

        def reload_current(self) -> None:
            if self.current_path is not None:
                self.load_path(self.current_path)

    MetadataEditor().mainloop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize Quantum Measurement metadata.json files.")
    parser.add_argument(
        "root",
        type=Path,
        nargs="?",
        default=DEFAULT_ROOT,
        help=f"Run folder or root folder containing run folders. Defaults to {DEFAULT_ROOT}.",
    )
    parser.add_argument("--edit", action="store_true", help="Open the HTML metadata editor.")
    parser.add_argument("--edit-tk", action="store_true", help="Open the legacy Tk metadata editor.")
    parser.add_argument("--write", action="store_true", help="Write normalized metadata files. Without this, only reports changes.")
    args = parser.parse_args()

    if args.edit:
        launch_html_editor(args.root)
        return

    if args.edit_tk:
        launch_editor(args.root)
        return

    paths = find_metadata_paths(args.root)
    changed_count = 0
    for path in paths:
        try:
            changed = normalize_file(path, write=args.write)
        except Exception as exc:
            print(f"ERROR {path}: {exc}")
            continue
        if changed:
            changed_count += 1
            action = "updated" if args.write else "would update"
            print(f"{action}: {path}")

    mode = "Updated" if args.write else "Would update"
    print(f"{mode} {changed_count} of {len(paths)} metadata files.")


if __name__ == "__main__":
    main()
