import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
import datetime
import time
import math
from collections import deque
from lakeshore import Model336, Model336InputSensorSettings
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import sys

class LakeShoreGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Lake Shore 336: Optimized Controller")
        self.root.geometry("1150x750")
        
        # --- CONTROL FLAGS ---
        self.app_running = True   # The "Kill Switch"
        self.loop_id = None       # ID to cancel the scheduled loop
        
        # Styles
        style = ttk.Style()
        style.configure("Big.TButton", font=("Arial", 11, "bold"), padding=10)
        style.configure("Safe.TButton", font=("Arial", 10, "bold"), foreground="green")
        style.configure("Warning.TButton", font=("Arial", 10, "bold"), foreground="red")
        
        # Variables
        self.ls = None
        self.is_connected = False
        self.log_running = False
        self.csv_writer = None
        self.log_file = None
        self.sensor_channels = ["A", "B", "C", "D"]
        self.sensor_rows = {}
        self.sensor_type_names = []
        self.sensor_type_labels = {}
        self.sensor_type_from_label = {}
        self.sensor_unit_names = []
        self.range_options = {}
        self.monitor_channel_var = None
        self.channel_snapshot_var = None
        self.program_running = False
        self.program_points = []
        self.program_steps = []
        self.program_index = 0
        self.program_step_start_time = None
        self.last_requested_setpoint_k = None
        self.max_heater_power_w = 50.0
        self.max_safe_temperature_k = 320.0
        self.power_estimate_low_temp_k = 294.0
        self.power_estimate_low_w = 0.0
        self.power_estimate_high_temp_k = 306.0
        self.power_estimate_high_w = 0.5
        self.quasi_equilibrium_band_k = 0.5
        self.quasi_equilibrium_hold_s = 10.0
        self.auto_range_program_var = None
        self.overtemp_trip_active = False
        self.program_step_in_band_since = None
        self.program_step_quasi_eq_time_s = None
        
        # Plot Data
        self.max_points = 150
        self.time_data = deque(maxlen=self.max_points)
        self.temp_data = deque(maxlen=self.max_points)
        self.max_points_30s = 240
        self.time_data_30s = deque(maxlen=self.max_points_30s)
        self.temp_data_30s = deque(maxlen=self.max_points_30s)
        self.slow_plot_interval_s = 30.0
        self.last_slow_plot_time = None
        self.start_time = time.time()
        
        self._init_ui()
        
        # Start the loop
        self.update_loop()

    def _init_ui(self):
        self.sensor_type_labels = {
            "DISABLED": "Disabled",
            "DIODE": "Silicon Diode",
            "PLATINUM_RTD": "Platinum RTD",
            "NTC_RTD": "Cernox / NTC RTD",
            "THERMOCOUPLE": "Thermocouple",
            "CAPACITANCE": "Capacitance",
        }
        self.sensor_type_from_label = {
            label: enum_name for enum_name, label in self.sensor_type_labels.items()
        }
        self.sensor_type_names = [self.sensor_type_labels[item.name] for item in Model336.InputSensorType]
        self.sensor_unit_names = [item.name for item in Model336.InputSensorUnits]
        self.range_options = {
            "Silicon Diode": [item.name for item in Model336.DiodeRange],
            "Platinum RTD": [item.name for item in Model336.RTDRange],
            "Cernox / NTC RTD": [item.name for item in Model336.RTDRange],
            "Thermocouple": [item.name for item in Model336.ThermocoupleRange],
            "Disabled": [],
            "Capacitance": [],
        }

        # --- LEFT PANEL (CONTROLS) ---
        left_panel = ttk.Frame(self.root, padding=10)
        left_panel.pack(side="left", fill="y")
        
        # --- RIGHT PANEL (PLOT) ---
        right_panel = ttk.Frame(self.root, padding=10)
        right_panel.pack(side="right", fill="both", expand=True)

        self.control_tabs = ttk.Notebook(left_panel)
        self.control_tabs.pack(fill="both", expand=True)
        main_tab = ttk.Frame(self.control_tabs, padding=5)
        admin_tab = ttk.Frame(self.control_tabs, padding=5)
        self.control_tabs.add(main_tab, text="Main")
        self.control_tabs.add(admin_tab, text="Admin")

        # 1. CONNECTION
        conn_frame = ttk.LabelFrame(main_tab, text="Connection")
        conn_frame.pack(fill="x", pady=5)
        self.btn_connect = ttk.Button(conn_frame, text="CONNECT", style="Big.TButton", command=self.connect_instrument)
        self.btn_connect.pack(fill="x", padx=5, pady=5)
        self.lbl_status = ttk.Label(conn_frame, text="Disconnected", foreground="red")
        self.lbl_status.pack(pady=2)
        self.lbl_connection = ttk.Label(conn_frame, text="Instrument: Not connected", foreground="gray", wraplength=250, justify="left")
        self.lbl_connection.pack(fill="x", padx=5, pady=2)

        # 2. MONITOR
        monitor_frame = ttk.LabelFrame(main_tab, text="Live Readings")
        monitor_frame.pack(fill="x", pady=5)
        self.monitor_channel_var = tk.StringVar(value="A")
        self.lbl_temp = ttk.Label(monitor_frame, text="0.000 K", font=("Arial", 32, "bold"), foreground="navy")
        self.lbl_temp.pack(pady=5)
        monitor_row = ttk.Frame(monitor_frame)
        monitor_row.pack(pady=2)
        ttk.Label(monitor_row, text="Display Channel:").pack(side="left")
        self.combo_monitor_channel = ttk.Combobox(
            monitor_row, textvariable=self.monitor_channel_var, values=self.sensor_channels, state="readonly", width=6
        )
        self.combo_monitor_channel.pack(side="left", padx=5)
        self.lbl_mode = ttk.Label(monitor_frame, text="Mode: Unknown", foreground="gray")
        self.lbl_mode.pack()
        self.lbl_heater = ttk.Label(monitor_frame, text="Heater: 0.0 % (0.00 W)")
        self.lbl_heater.pack(pady=2)
        self.lbl_power_estimate = ttk.Label(
            monitor_frame,
            text="Estimated hold power @ target: -",
            foreground="dim gray",
            wraplength=280,
            justify="left",
        )
        self.lbl_power_estimate.pack(pady=2)

        sensor_frame = ttk.LabelFrame(admin_tab, text="Sensor Channels")
        sensor_frame.pack(fill="x", pady=5)
        headers = ["Ch", "Name", "Temp (K)", "Raw", "Type / Units", "Status"]
        for col, text in enumerate(headers):
            ttk.Label(sensor_frame, text=text, font=("Arial", 9, "bold")).grid(row=0, column=col, sticky="w", padx=3, pady=2)

        for row_idx, channel in enumerate(self.sensor_channels, start=1):
            ttk.Label(sensor_frame, text=channel).grid(row=row_idx, column=0, sticky="w", padx=3, pady=1)
            name_lbl = ttk.Label(sensor_frame, text="-", width=10)
            temp_lbl = ttk.Label(sensor_frame, text="-", width=10)
            raw_lbl = ttk.Label(sensor_frame, text="-", width=12)
            type_lbl = ttk.Label(sensor_frame, text="-", width=18)
            status_lbl = ttk.Label(sensor_frame, text="-", width=18)
            name_lbl.grid(row=row_idx, column=1, sticky="w", padx=3, pady=1)
            temp_lbl.grid(row=row_idx, column=2, sticky="w", padx=3, pady=1)
            raw_lbl.grid(row=row_idx, column=3, sticky="w", padx=3, pady=1)
            type_lbl.grid(row=row_idx, column=4, sticky="w", padx=3, pady=1)
            status_lbl.grid(row=row_idx, column=5, sticky="w", padx=3, pady=1)
            self.sensor_rows[channel] = {
                "name": name_lbl,
                "temp": temp_lbl,
                "raw": raw_lbl,
                "type": type_lbl,
                "status": status_lbl,
            }

        test_frame = ttk.LabelFrame(admin_tab, text="Channel Test")
        test_frame.pack(fill="x", pady=5)
        ttk.Label(test_frame, text="Use this to compare channels while moving or unplugging one sensor.").pack(
            anchor="w", padx=5, pady=2
        )
        test_buttons = ttk.Frame(test_frame)
        test_buttons.pack(fill="x", padx=5, pady=2)
        ttk.Button(test_buttons, text="Snapshot All Channels", command=self.capture_channel_snapshot).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(test_buttons, text="Set Main To Selected", command=self.sync_monitor_to_detector_channel).pack(
            side="left", fill="x", expand=True, padx=(5, 0)
        )
        self.channel_snapshot_var = tk.StringVar(value="No snapshot yet.")
        ttk.Label(test_frame, textvariable=self.channel_snapshot_var, wraplength=280, justify="left").pack(
            fill="x", padx=5, pady=3
        )

        det_frame = ttk.LabelFrame(admin_tab, text="Detector Config")
        det_frame.pack(fill="x", pady=5)

        self.detector_channel_var = tk.StringVar(value="A")
        self.detector_type_var = tk.StringVar(value=self.sensor_type_names[0])
        self.detector_units_var = tk.StringVar(value="KELVIN")
        self.detector_autorange_var = tk.BooleanVar(value=True)
        self.detector_comp_var = tk.BooleanVar(value=False)
        self.detector_range_var = tk.StringVar(value="")

        ttk.Label(det_frame, text="Channel").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        self.combo_detector_channel = ttk.Combobox(
            det_frame, textvariable=self.detector_channel_var, values=self.sensor_channels, state="readonly", width=6
        )
        self.combo_detector_channel.grid(row=0, column=1, sticky="w", padx=4, pady=2)
        self.combo_detector_channel.bind("<<ComboboxSelected>>", self.load_detector_config)

        ttk.Label(det_frame, text="Type").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        self.combo_detector_type = ttk.Combobox(
            det_frame, textvariable=self.detector_type_var, values=self.sensor_type_names, state="readonly", width=18
        )
        self.combo_detector_type.grid(row=1, column=1, sticky="we", padx=4, pady=2)
        self.combo_detector_type.bind("<<ComboboxSelected>>", self.on_detector_type_change)

        ttk.Label(det_frame, text="Units").grid(row=2, column=0, sticky="w", padx=4, pady=2)
        self.combo_detector_units = ttk.Combobox(
            det_frame, textvariable=self.detector_units_var, values=self.sensor_unit_names, state="readonly", width=18
        )
        self.combo_detector_units.grid(row=2, column=1, sticky="we", padx=4, pady=2)

        ttk.Label(det_frame, text="Range").grid(row=3, column=0, sticky="w", padx=4, pady=2)
        self.combo_detector_range = ttk.Combobox(
            det_frame, textvariable=self.detector_range_var, values=[], state="readonly", width=18
        )
        self.combo_detector_range.grid(row=3, column=1, sticky="we", padx=4, pady=2)

        ttk.Checkbutton(
            det_frame, text="Autorange", variable=self.detector_autorange_var, command=self.on_detector_autorange_toggle
        ).grid(row=4, column=0, sticky="w", padx=4, pady=2)
        ttk.Checkbutton(
            det_frame, text="Compensation", variable=self.detector_comp_var
        ).grid(row=4, column=1, sticky="w", padx=4, pady=2)

        ttk.Button(det_frame, text="Load Channel", command=self.load_detector_config).grid(row=5, column=0, sticky="we", padx=4, pady=4)
        ttk.Button(det_frame, text="Apply Config", command=self.apply_detector_config).grid(row=5, column=1, sticky="we", padx=4, pady=4)
        det_frame.columnconfigure(1, weight=1)

        # 3. PID CONTROL
        pid_frame = ttk.LabelFrame(main_tab, text="PID Temperature Control")
        pid_frame.pack(fill="x", pady=5)
        
        # Setpoint
        r1 = ttk.Frame(pid_frame)
        r1.pack(fill="x", padx=5, pady=2)
        ttk.Label(r1, text="Setpoint (K):").pack(side="left")
        self.ent_setpoint = ttk.Entry(r1, width=8)
        self.ent_setpoint.pack(side="left", padx=5)
        ttk.Button(r1, text="SET", width=6, command=self.set_temperature).pack(side="left")

        # PID Fields
        r2 = ttk.Frame(pid_frame)
        r2.pack(fill="x", padx=5, pady=5)
        
        f_p = ttk.Frame(r2); f_p.pack(side="left", padx=2)
        ttk.Label(f_p, text="P").pack()
        self.ent_p = ttk.Entry(f_p, width=5)
        self.ent_p.insert(0, "50")
        self.ent_p.pack()
        
        f_i = ttk.Frame(r2); f_i.pack(side="left", padx=2)
        ttk.Label(f_i, text="I").pack()
        self.ent_i = ttk.Entry(f_i, width=5)
        self.ent_i.insert(0, "10")
        self.ent_i.pack()
        
        f_d = ttk.Frame(r2); f_d.pack(side="left", padx=2)
        ttk.Label(f_d, text="D").pack()
        self.ent_d = ttk.Entry(f_d, width=5)
        self.ent_d.insert(0, "0")
        self.ent_d.pack()

        ttk.Button(r2, text="UPDATE PID", command=self.set_pid_values).pack(side="left", padx=10, fill="y")

        cycle_frame = ttk.LabelFrame(main_tab, text="Temperature Cycle Program")
        cycle_frame.pack(fill="x", pady=5)

        r_cycle_1 = ttk.Frame(cycle_frame)
        r_cycle_1.pack(fill="x", padx=5, pady=2)
        ttk.Label(r_cycle_1, text="Start (K):").pack(side="left")
        self.ent_cycle_start = ttk.Entry(r_cycle_1, width=6)
        self.ent_cycle_start.insert(0, "300")
        self.ent_cycle_start.pack(side="left", padx=3)
        ttk.Label(r_cycle_1, text="End (K):").pack(side="left")
        self.ent_cycle_end = ttk.Entry(r_cycle_1, width=6)
        self.ent_cycle_end.insert(0, "310")
        self.ent_cycle_end.pack(side="left", padx=3)

        r_cycle_2 = ttk.Frame(cycle_frame)
        r_cycle_2.pack(fill="x", padx=5, pady=2)
        ttk.Label(r_cycle_2, text="Step (K):").pack(side="left")
        self.ent_cycle_step = ttk.Entry(r_cycle_2, width=6)
        self.ent_cycle_step.insert(0, "1")
        self.ent_cycle_step.pack(side="left", padx=3)
        ttk.Label(r_cycle_2, text="Dwell (s):").pack(side="left")
        self.ent_cycle_dwell = ttk.Entry(r_cycle_2, width=6)
        self.ent_cycle_dwell.insert(0, "100")
        self.ent_cycle_dwell.pack(side="left", padx=3)
        ttk.Label(r_cycle_2, text="Cycles:").pack(side="left")
        self.ent_cycle_count = ttk.Entry(r_cycle_2, width=6)
        self.ent_cycle_count.insert(0, "1")
        self.ent_cycle_count.pack(side="left", padx=3)

        r_cycle_3 = ttk.Frame(cycle_frame)
        r_cycle_3.pack(fill="x", padx=5, pady=4)
        ttk.Button(r_cycle_3, text="Start Program", command=self.start_cycle_program).pack(side="left", fill="x", expand=True)
        ttk.Button(r_cycle_3, text="Stop Program", command=self.stop_cycle_program).pack(side="left", fill="x", expand=True, padx=(5, 0))

        self.auto_range_program_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            cycle_frame,
            text="Auto heater range during program",
            variable=self.auto_range_program_var,
        ).pack(anchor="w", padx=5, pady=2)

        self.lbl_program = ttk.Label(cycle_frame, text="Program: Idle", wraplength=280, justify="left")
        self.lbl_program.pack(fill="x", padx=5, pady=3)

        # 4. MANUAL POWER
        man_frame = ttk.LabelFrame(admin_tab, text="Manual Power")
        man_frame.pack(fill="x", pady=5)
        
        r3 = ttk.Frame(man_frame)
        r3.pack(fill="x", padx=5, pady=5)
        ttk.Label(r3, text="Manual Output (%):").pack(side="left")
        self.ent_manual = ttk.Entry(r3, width=8)
        self.ent_manual.pack(side="left", padx=5)
        ttk.Button(r3, text="FORCE %", width=10, command=self.set_manual_out).pack(side="left")

        # 5. CONFIG
        cfg_frame = ttk.LabelFrame(main_tab, text="Config")
        cfg_frame.pack(fill="x", pady=5)
        
        ttk.Label(cfg_frame, text="Heater Range:").pack(anchor="w", padx=5)
        self.combo_range = ttk.Combobox(cfg_frame, values=["OFF", "LOW", "MEDIUM", "HIGH"], state="readonly")
        self.combo_range.current(0)
        self.combo_range.pack(fill="x", padx=5, pady=2)
        ttk.Button(cfg_frame, text="Set Range", command=self.set_range).pack(fill="x", padx=5, pady=2)
        self.lbl_heater_limit = ttk.Label(cfg_frame, text=f"Heater safety limit: {self.max_heater_power_w:.0f} W max")
        self.lbl_heater_limit.pack(anchor="w", padx=5, pady=2)
        
        ttk.Button(cfg_frame, text="Apply WARM Mode (Safe Presets)", style="Safe.TButton", command=self.apply_warm_mode).pack(fill="x", padx=5, pady=5)
        ttk.Button(cfg_frame, text="Force 50 Ohm Load", style="Warning.TButton", command=lambda: self.set_heater_load(2)).pack(fill="x", padx=5, pady=2)

        # 6. LOGGING
        log_frame = ttk.LabelFrame(main_tab, text="Data Logger")
        log_frame.pack(fill="x", pady=5)
        self.btn_log = ttk.Button(log_frame, text="START LOG", style="Big.TButton", command=self.toggle_logging)
        self.btn_log.pack(fill="x", padx=5, pady=5)

        # --- PLOT SETUP ---
        self.fig, (self.ax, self.ax_30s) = plt.subplots(2, 1, sharex=False, figsize=(7, 8))
        self.fig.patch.set_facecolor('#F0F0F0')
        self.ax.set_title("Temperature Trend")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Kelvin (K)")
        self.ax.grid(True, linestyle='--', alpha=0.6)
        self.line, = self.ax.plot([], [], 'r-', linewidth=2)
        self.ax_30s.set_title("Temperature Trend (30 s Sampling)")
        self.ax_30s.set_xlabel("Time (s)")
        self.ax_30s.set_ylabel("Kelvin (K)")
        self.ax_30s.grid(True, linestyle='--', alpha=0.6)
        self.line_30s, = self.ax_30s.plot([], [], 'b-', linewidth=2)
        self.fig.tight_layout()
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=right_panel)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    # ================= LOGIC =================

    def _enum_text(self, value):
        return getattr(value, "name", str(value))

    def _enum_from_name(self, enum_cls, name):
        return getattr(enum_cls, name)

    def _format_status(self, status_obj):
        active_flags = [
            field.replace("_", " ")
            for field, enabled in vars(status_obj).items()
            if enabled
        ]
        return ", ".join(active_flags) if active_flags else "OK"

    def _apply_setpoint(self, value):
        self.last_requested_setpoint_k = value
        self.ls.set_control_setpoint(1, value)
        self.ls.command("OUTMODE 1, 1, A, 0")

    def _heater_resistance_ohms(self, heater_resistance):
        if heater_resistance == Model336.HeaterResistance.HEATER_25_OHM:
            return 25.0
        if heater_resistance == Model336.HeaterResistance.HEATER_50_OHM:
            return 50.0
        raise ValueError(f"Unsupported heater resistance: {heater_resistance}")

    def _enforce_heater_power_limit(self, heater_resistance=None):
        if not self.is_connected:
            return

        if heater_resistance is None:
            setup = self.ls.get_heater_setup(1)
            heater_resistance = setup["heater_resistance"]

        resistance_ohms = self._heater_resistance_ohms(heater_resistance)
        max_current = math.sqrt(self.max_heater_power_w / resistance_ohms)
        self.ls.set_heater_setup(
            1,
            heater_resistance,
            max_current,
            Model336.HeaterOutputUnits.POWER,
        )
        self._update_heater_limit_label(max_current=max_current, resistance_ohms=resistance_ohms)

    def _heater_range_power_factor(self, heater_range):
        power_factors = {
            Model336.HeaterRange.OFF: 0.0,
            Model336.HeaterRange.LOW: 0.01,
            Model336.HeaterRange.MEDIUM: 0.1,
            Model336.HeaterRange.HIGH: 1.0,
        }
        return power_factors.get(heater_range, 1.0)

    def _get_active_heater_range(self):
        try:
            return self.ls.get_heater_range(1)
        except Exception:
            range_map = {
                "OFF": Model336.HeaterRange.OFF,
                "LOW": Model336.HeaterRange.LOW,
                "MEDIUM": Model336.HeaterRange.MEDIUM,
                "HIGH": Model336.HeaterRange.HIGH,
            }
            return range_map.get(self.combo_range.get(), Model336.HeaterRange.HIGH)

    def _active_heater_power_limit_w(self, heater_range=None):
        if heater_range is None:
            heater_range = self._get_active_heater_range()
        return self.max_heater_power_w * self._heater_range_power_factor(heater_range)

    def _update_heater_limit_label(self, max_current=None, resistance_ohms=None):
        if max_current is None or resistance_ohms is None:
            try:
                setup = self.ls.get_heater_setup(1)
                resistance_ohms = self._heater_resistance_ohms(setup["heater_resistance"])
                max_current = setup["max_current"]
            except Exception:
                resistance_ohms = None
                max_current = None

        active_range = self._get_active_heater_range() if self.is_connected else None
        active_limit_w = self._active_heater_power_limit_w(active_range) if active_range is not None else None
        range_name = self._enum_text(active_range) if active_range is not None else self.combo_range.get()

        label = f"Heater safety limit: {self.max_heater_power_w:.0f} W max"
        if max_current is not None and resistance_ohms is not None:
            label += f" ({max_current:.3f} A @ {resistance_ohms:.0f} ohm)"
        if active_limit_w is not None and range_name:
            label += f" | Active {range_name}: {active_limit_w:.2f} W"
        self.lbl_heater_limit.config(text=label)

    def _heater_applied_power_w(self, heater_percent, heater_range=None):
        """Estimate applied heater power from the live output percentage."""
        heater_fraction = max(0.0, min(heater_percent, 100.0)) / 100.0
        return heater_fraction * self._active_heater_power_limit_w(heater_range)

    def _estimate_required_power_w(self, target_temp_k):
        low_temp = self.power_estimate_low_temp_k
        high_temp = self.power_estimate_high_temp_k
        low_power = self.power_estimate_low_w
        high_power = self.power_estimate_high_w

        if math.isclose(high_temp, low_temp):
            return max(0.0, min(low_power, self.max_heater_power_w))

        slope_w_per_k = (high_power - low_power) / (high_temp - low_temp)
        estimated_power = low_power + (target_temp_k - low_temp) * slope_w_per_k
        return max(0.0, min(estimated_power, self.max_heater_power_w))

    def _current_target_temperature(self):
        if self.program_running and self.program_index < len(self.program_steps):
            return self.program_steps[self.program_index]["target"]
        return self.last_requested_setpoint_k

    def _update_power_estimate_label(self):
        target_temp = self._current_target_temperature()
        if target_temp is None:
            self.lbl_power_estimate.config(text="Estimated hold power @ target: -")
            return

        estimated_power = self._estimate_required_power_w(target_temp)
        self.lbl_power_estimate.config(
            text=(
                f"Estimated hold power @ target {target_temp:.3f} K: "
                f"{estimated_power:.2f} W "
                f"(from {self.power_estimate_low_w:.2f} W @ {self.power_estimate_low_temp_k:.0f} K "
                f"to {self.power_estimate_high_w:.2f} W @ {self.power_estimate_high_temp_k:.0f} K)"
            )
        )

    def _build_cycle_points(self, start_value, end_value, step_value):
        points = []
        current = start_value
        epsilon = max(abs(step_value) / 1000, 1e-9)

        if step_value > 0:
            while current <= end_value + epsilon:
                points.append(round(current, 6))
                current += step_value
        else:
            while current >= end_value - epsilon:
                points.append(round(current, 6))
                current += step_value

        return points

    def _build_cycle_steps(self, start_value, end_value, step_value, cycle_count):
        outbound_step = abs(step_value) if end_value >= start_value else -abs(step_value)
        outbound_points = self._build_cycle_points(start_value, end_value, outbound_step)
        return_step = -outbound_step
        return_start = end_value + return_step
        return_points = self._build_cycle_points(return_start, start_value, return_step)

        steps = []
        for cycle_number in range(1, cycle_count + 1):
            if cycle_number == 1:
                rise_points = outbound_points
            else:
                rise_points = outbound_points[1:]

            for target in rise_points:
                steps.append(
                    {
                        "target": target,
                        "cycle": cycle_number,
                        "phase": "rise",
                    }
                )

            for target in return_points:
                steps.append(
                    {
                        "target": target,
                        "cycle": cycle_number,
                        "phase": "fall",
                    }
                )

        return steps

    def _validate_safe_temperature(self, target_temperature):
        if target_temperature > self.max_safe_temperature_k:
            raise ValueError(
                f"Temperature cannot exceed {self.max_safe_temperature_k:.0f} K."
            )

    def _trigger_overtemp_shutdown(self, measured_temperature):
        if self.overtemp_trip_active:
            return

        self.overtemp_trip_active = True
        self.stop_cycle_program()
        try:
            self.ls.set_heater_range(1, 0)
        except Exception:
            pass
        self.lbl_mode.config(text="Mode: OVERTEMP TRIP", foreground="red")
        self.lbl_program.config(
            text=(
                f"Program: Stopped at {measured_temperature:.3f} K "
                f"(limit {self.max_safe_temperature_k:.0f} K)"
            )
        )
        messagebox.showerror(
            "Overtemperature Shutdown",
            (
                f"Measured temperature reached {measured_temperature:.3f} K.\n"
                f"Heater output was disabled to protect the hardware "
                f"({self.max_safe_temperature_k:.0f} K limit)."
            ),
        )

    def _reset_program_step_tracking(self):
        self.program_step_in_band_since = None
        self.program_step_quasi_eq_time_s = None

    def _update_quasi_equilibrium_timer(self, current_temp):
        if not self.program_running or current_temp is None:
            return
        if self.program_index >= len(self.program_steps):
            return

        current_step = self.program_steps[self.program_index]
        target_temp = current_step["target"]
        now = time.time()

        if abs(current_temp - target_temp) <= self.quasi_equilibrium_band_k:
            if self.program_step_in_band_since is None:
                self.program_step_in_band_since = now
            elif (
                self.program_step_quasi_eq_time_s is None
                and now - self.program_step_in_band_since >= self.quasi_equilibrium_hold_s
            ):
                self.program_step_quasi_eq_time_s = now - self.program_step_start_time
                current_step["quasi_eq_time_s"] = self.program_step_quasi_eq_time_s
        else:
            self.program_step_in_band_since = None

    def _set_heater_range_enum(self, heater_range):
        self.ls.set_heater_range(1, heater_range)
        range_names = {
            Model336.HeaterRange.OFF: "OFF",
            Model336.HeaterRange.LOW: "LOW",
            Model336.HeaterRange.MEDIUM: "MEDIUM",
            Model336.HeaterRange.HIGH: "HIGH",
        }
        range_name = range_names.get(heater_range)
        if range_name:
            self.combo_range.set(range_name)
        self._update_heater_limit_label()

    def _auto_adjust_program_range(self, current_temp, target_temp):
        if not self.auto_range_program_var.get():
            return

        estimated_power_w = self._estimate_required_power_w(target_temp) * 1.2
        if estimated_power_w <= self.max_heater_power_w * 0.01:
            heater_range = Model336.HeaterRange.LOW
        elif estimated_power_w <= self.max_heater_power_w * 0.1:
            heater_range = Model336.HeaterRange.MEDIUM
        else:
            heater_range = Model336.HeaterRange.HIGH

        if current_temp is not None:
            error = abs(target_temp - current_temp)
            if error > 10:
                heater_range = Model336.HeaterRange.HIGH
            elif error > 3 and heater_range == Model336.HeaterRange.LOW:
                heater_range = Model336.HeaterRange.MEDIUM

        try:
            current_range = self.ls.get_heater_range(1)
        except Exception:
            current_range = None

        if current_range != heater_range:
            self._set_heater_range_enum(heater_range)

    def _advance_cycle_program(self):
        if not self.program_running:
            return

        dwell_seconds = float(self.ent_cycle_dwell.get())
        if self.program_index >= len(self.program_steps):
            self.stop_cycle_program(completed=True)
            return

        current_step = self.program_steps[self.program_index]
        current_target = current_step["target"]
        elapsed = time.time() - self.program_step_start_time
        remaining = max(0, dwell_seconds - elapsed)
        self.lbl_program.config(
            text=(
                f"Program: Cycle {current_step['cycle']} | {current_step['phase'].capitalize()} | "
                f"Step {self.program_index + 1}/{len(self.program_steps)} | "
                f"Target {current_target:.3f} K | {remaining:.0f} s remaining"
            )
        )
        if self.program_step_quasi_eq_time_s is not None:
            self.lbl_program.config(
                text=(
                    f"Program: Cycle {current_step['cycle']} | {current_step['phase'].capitalize()} | "
                    f"Step {self.program_index + 1}/{len(self.program_steps)} | "
                    f"Target {current_target:.3f} K | QE in {self.program_step_quasi_eq_time_s:.0f} s | "
                    f"{remaining:.0f} s remaining"
                )
            )
        current_temp = None
        try:
            current_temp = self.ls.get_kelvin_reading("A")
        except Exception:
            pass
        self._auto_adjust_program_range(current_temp, current_target)

        if elapsed >= dwell_seconds:
            self.program_index += 1
            if self.program_index >= len(self.program_steps):
                self.stop_cycle_program(completed=True)
                return

            next_step = self.program_steps[self.program_index]
            next_target = next_step["target"]
            self._apply_setpoint(next_target)
            self.program_step_start_time = time.time()
            self._reset_program_step_tracking()
            self.lbl_program.config(
                text=(
                    f"Program: Cycle {next_step['cycle']} | {next_step['phase'].capitalize()} | "
                    f"Step {self.program_index + 1}/{len(self.program_steps)} | "
                    f"Target {next_target:.3f} K | {dwell_seconds:.0f} s remaining"
                )
            )

    def _refresh_detector_range_options(self):
        sensor_type_name = self.detector_type_var.get()
        choices = self.range_options.get(sensor_type_name, [])
        self.combo_detector_range["values"] = choices

        if self.detector_autorange_var.get() or not choices:
            self.detector_range_var.set("")
            self.combo_detector_range.config(state="disabled")
        else:
            self.combo_detector_range.config(state="readonly")
            if self.detector_range_var.get() not in choices:
                self.detector_range_var.set(choices[0])

    def on_detector_type_change(self, _event=None):
        self._refresh_detector_range_options()

    def on_detector_autorange_toggle(self):
        self._refresh_detector_range_options()

    def _update_sensor_metadata(self):
        for channel in self.sensor_channels:
            try:
                sensor_name = self.ls.get_sensor_name(channel).strip() or "-"
            except Exception:
                sensor_name = "-"
            try:
                sensor_cfg = self.ls.get_input_sensor(channel)
                sensor_type_text = self.sensor_type_labels.get(
                    self._enum_text(sensor_cfg.sensor_type),
                    self._enum_text(sensor_cfg.sensor_type)
                )
                sensor_desc = f"{sensor_type_text} / {self._enum_text(sensor_cfg.units)}"
            except Exception:
                sensor_desc = "Unavailable"

            self.sensor_rows[channel]["name"].config(text=sensor_name)
            self.sensor_rows[channel]["type"].config(text=sensor_desc)

    def load_detector_config(self, _event=None):
        if not self.is_connected:
            return
        channel = self.detector_channel_var.get()
        try:
            sensor_cfg = self.ls.get_input_sensor(channel)
            self.detector_type_var.set(self.sensor_type_labels.get(self._enum_text(sensor_cfg.sensor_type), self._enum_text(sensor_cfg.sensor_type)))
            self.detector_units_var.set(self._enum_text(sensor_cfg.units))
            self.detector_autorange_var.set(bool(sensor_cfg.autorange_enable))
            self.detector_comp_var.set(bool(sensor_cfg.compensation))
            range_name = self._enum_text(sensor_cfg.input_range) if sensor_cfg.input_range not in (None, 0) else ""
            self.detector_range_var.set(range_name)
            self._refresh_detector_range_options()
        except Exception as e:
            messagebox.showerror("Detector Config", str(e))

    def apply_detector_config(self):
        if not self.is_connected:
            return
        channel = self.detector_channel_var.get()
        try:
            sensor_type_name = self.sensor_type_from_label.get(self.detector_type_var.get(), self.detector_type_var.get())
            sensor_type = self._enum_from_name(Model336.InputSensorType, sensor_type_name)
            units = self._enum_from_name(Model336.InputSensorUnits, self.detector_units_var.get())
            autorange = bool(self.detector_autorange_var.get())
            compensation = bool(self.detector_comp_var.get())

            input_range = 0
            if not autorange:
                range_name = self.detector_range_var.get()
                if not range_name:
                    raise ValueError("Select a detector range or enable autorange.")
                if sensor_type == Model336.InputSensorType.DIODE:
                    input_range = self._enum_from_name(Model336.DiodeRange, range_name)
                elif sensor_type in (Model336.InputSensorType.PLATINUM_RTD, Model336.InputSensorType.NTC_RTD):
                    input_range = self._enum_from_name(Model336.RTDRange, range_name)
                elif sensor_type == Model336.InputSensorType.THERMOCOUPLE:
                    input_range = self._enum_from_name(Model336.ThermocoupleRange, range_name)
                else:
                    input_range = 0

            sensor_settings = Model336InputSensorSettings(
                sensor_type, autorange, compensation, units, input_range
            )
            self.ls.set_input_sensor(channel, sensor_settings)
            self._update_sensor_metadata()
            self._update_sensor_readings()
            self.load_detector_config()
            messagebox.showinfo("Detector Config", f"Updated channel {channel}.")
        except Exception as e:
            messagebox.showerror("Detector Config", str(e))
    
    def _update_sensor_readings(self):
        temperatures = {}
        try:
            kelvin_values = self.ls.get_all_kelvin_reading()
            temperatures = dict(zip(self.sensor_channels, kelvin_values))
        except Exception:
            pass

        try:
            sensor_values = self.ls.get_all_sensor_reading()
            raw_readings = dict(zip(self.sensor_channels, sensor_values))
        except Exception:
            raw_readings = {}

        for channel in self.sensor_channels:
            temp_value = temperatures.get(channel)
            raw_value = raw_readings.get(channel)

            try:
                status_text = self._format_status(self.ls.get_input_reading_status(channel))
            except Exception:
                status_text = "Unavailable"

            self.sensor_rows[channel]["temp"].config(
                text="-" if temp_value is None else f"{temp_value:.3f}"
            )
            self.sensor_rows[channel]["raw"].config(
                text="-" if raw_value is None else f"{raw_value:.3f}"
            )
            self.sensor_rows[channel]["status"].config(text=status_text)

        return temperatures.get(self.monitor_channel_var.get())

    def sync_monitor_to_detector_channel(self):
        self.monitor_channel_var.set(self.detector_channel_var.get())

    def capture_channel_snapshot(self):
        if not self.is_connected:
            self.channel_snapshot_var.set("Connect to the controller first.")
            return

        parts = []
        try:
            temperatures = dict(zip(self.sensor_channels, self.ls.get_all_kelvin_reading()))
        except Exception:
            temperatures = {}
        try:
            raw_readings = dict(zip(self.sensor_channels, self.ls.get_all_sensor_reading()))
        except Exception:
            raw_readings = {}

        for channel in self.sensor_channels:
            try:
                status_text = self._format_status(self.ls.get_input_reading_status(channel))
            except Exception:
                status_text = "Unavailable"
            temp_text = "-" if channel not in temperatures else f"{temperatures[channel]:.3f} K"
            raw_text = "-" if channel not in raw_readings else f"{raw_readings[channel]:.3f}"
            parts.append(f"{channel}: {temp_text}, raw {raw_text}, {status_text}")

        self.channel_snapshot_var.set(" | ".join(parts))
    
    def connect_instrument(self):
        try:
            self.ls = Model336()
            idn = self.ls.query('*IDN?')
            self.lbl_status.config(text="CONNECTED", foreground="green")
            self.lbl_connection.config(text=f"Instrument: {idn.strip()}", foreground="black")
            self.is_connected = True
            self.btn_connect.config(state="disabled")
            self._enforce_heater_power_limit()
            self._update_sensor_metadata()
            self._update_sensor_readings()
            self.load_detector_config()
            
            # Read PID
            try:
                pid_str = self.ls.query("PID? 1").strip().split(',')
                self.ent_p.delete(0, tk.END); self.ent_p.insert(0, pid_str[0])
                self.ent_i.delete(0, tk.END); self.ent_i.insert(0, pid_str[1])
                self.ent_d.delete(0, tk.END); self.ent_d.insert(0, pid_str[2])
            except: pass
            
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def update_loop(self):
        # 1. KILL SWITCH CHECK
        if not self.app_running:
            return

        if self.is_connected:
            try:
                temp = self._update_sensor_readings()
                htr = float(self.ls.query("HTR? 1"))
                
                # Check Mode
                mode_map = {'0':'Off', '1':'Open Loop', '2':'Zone', '3':'PID'} # Simplified map
                raw_mode = self.ls.query("MOUT? 1").strip()
                # Sometimes instruments return slightly different codes, handle safely:
                mode_txt = mode_map.get(raw_mode, "PID/Custom")

                if temp is None:
                    temp = float(self.ls.query(f"KRDG? {self.monitor_channel_var.get()}"))
                if temp >= self.max_safe_temperature_k:
                    self._trigger_overtemp_shutdown(temp)
                self._update_quasi_equilibrium_timer(temp)
                self._advance_cycle_program()
                self.lbl_temp.config(text=f"{temp:.3f} K")
                heater_range = self._get_active_heater_range()
                applied_power_w = self._heater_applied_power_w(htr, heater_range)
                self.lbl_heater.config(text=f"Heater: {htr:.1f} % ({applied_power_w:.2f} W)")
                self._update_power_estimate_label()
                if not self.overtemp_trip_active:
                    self.lbl_mode.config(text=f"Mode: {mode_txt}", foreground="gray")
                self._update_heater_limit_label()
                
                # Plot
                elapsed = time.time() - self.start_time
                self.time_data.append(elapsed)
                self.temp_data.append(temp)
                if (
                    self.last_slow_plot_time is None
                    or elapsed - self.last_slow_plot_time >= self.slow_plot_interval_s
                ):
                    self.time_data_30s.append(elapsed)
                    self.temp_data_30s.append(temp)
                    self.last_slow_plot_time = elapsed
                self.line.set_xdata(self.time_data)
                self.line.set_ydata(self.temp_data)
                self.line_30s.set_xdata(self.time_data_30s)
                self.line_30s.set_ydata(self.temp_data_30s)
                self.ax.relim()
                self.ax.autoscale_view()
                self.ax_30s.relim()
                self.ax_30s.autoscale_view()
                self.canvas.draw()
                
                if self.log_running:
                    current_target = ""
                    current_cycle = ""
                    current_phase = ""
                    quasi_eq_time = ""
                    if self.program_running and self.program_index < len(self.program_steps):
                        current_step = self.program_steps[self.program_index]
                        current_target = f"{current_step['target']:.3f}"
                        current_cycle = current_step["cycle"]
                        current_phase = current_step["phase"]
                        if self.program_step_quasi_eq_time_s is not None:
                            quasi_eq_time = f"{self.program_step_quasi_eq_time_s:.1f}"
                    self.csv_writer.writerow(
                        [
                            datetime.datetime.now().strftime("%H:%M:%S"),
                            temp,
                            htr,
                            applied_power_w,
                            current_target,
                            current_cycle,
                            current_phase,
                            quasi_eq_time,
                        ]
                    )
            except: 
                pass # Ignore glitches
        
        # Schedule next loop
        if self.app_running:
            self.loop_id = self.root.after(1000, self.update_loop)

    def set_temperature(self):
        if not self.is_connected: return
        try:
            val = float(self.ent_setpoint.get())
            self._validate_safe_temperature(val)
            self.overtemp_trip_active = False
            self._apply_setpoint(val)
            messagebox.showinfo("PID Mode", f"Setpoint: {val} K")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def set_pid_values(self):
        if not self.is_connected: return
        try:
            p, i, d = float(self.ent_p.get()), float(self.ent_i.get()), float(self.ent_d.get())
            self.ls.set_heater_pid(1, p, i, d)
            messagebox.showinfo("Success", "PID Updated")
        except: messagebox.showerror("Error", "Invalid Numbers")

    def set_manual_out(self):
        if not self.is_connected: return
        try:
            val = float(self.ent_manual.get())
            if 0 <= val <= 100:
                self.ls.command("OUTMODE 1, 3, A, 0") # Force Open Loop
                self.ls.command(f"MOUT 1, {val}")
                messagebox.showinfo("Open Loop", f"Output forced to {val}%")
        except: pass

    def set_range(self):
        if self.is_connected:
            rmap = {"OFF":0, "LOW":1, "MEDIUM":2, "HIGH":3}
            self.ls.set_heater_range(1, rmap[self.combo_range.get()])
            self._update_heater_limit_label()

    def start_cycle_program(self):
        if not self.is_connected:
            messagebox.showerror("Program", "Connect to the controller first.")
            return
        try:
            start_value = float(self.ent_cycle_start.get())
            end_value = float(self.ent_cycle_end.get())
            step_value = float(self.ent_cycle_step.get())
            dwell_seconds = float(self.ent_cycle_dwell.get())
            cycle_count = int(self.ent_cycle_count.get())

            self._validate_safe_temperature(start_value)
            self._validate_safe_temperature(end_value)

            if step_value == 0:
                raise ValueError("Step must be non-zero.")
            if dwell_seconds <= 0:
                raise ValueError("Dwell time must be positive.")
            if cycle_count <= 0:
                raise ValueError("Cycle count must be a positive integer.")
            if start_value == end_value:
                raise ValueError("Start and end temperatures must be different.")

            self.program_steps = self._build_cycle_steps(
                start_value, end_value, step_value, cycle_count
            )
            self.program_points = [step["target"] for step in self.program_steps]
            if not self.program_steps:
                raise ValueError("No valid setpoints generated.")

            self.program_running = True
            self.overtemp_trip_active = False
            self.program_index = 0
            self._reset_program_step_tracking()
            first_step = self.program_steps[0]
            self._apply_setpoint(first_step["target"])
            try:
                current_temp = self.ls.get_kelvin_reading("A")
            except Exception:
                current_temp = None
            self._auto_adjust_program_range(current_temp, first_step["target"])
            self.program_step_start_time = time.time()
            self.lbl_program.config(
                text=(
                    f"Program: Cycle {first_step['cycle']} | {first_step['phase'].capitalize()} | "
                    f"Step 1/{len(self.program_steps)} | "
                    f"Target {first_step['target']:.3f} K | {dwell_seconds:.0f} s remaining"
                )
            )
        except Exception as e:
            messagebox.showerror("Program", str(e))

    def stop_cycle_program(self, completed=False):
        self.program_running = False
        self.program_points = []
        self.program_steps = []
        self.program_index = 0
        self.program_step_start_time = None
        self._reset_program_step_tracking()
        self.lbl_program.config(text="Program: Completed" if completed else "Program: Idle")

    def apply_warm_mode(self):
        if not self.is_connected: return
        self.ent_p.delete(0, tk.END); self.ent_p.insert(0, "50")
        self.ent_i.delete(0, tk.END); self.ent_i.insert(0, "10")
        self.ent_d.delete(0, tk.END); self.ent_d.insert(0, "0")
        self.set_pid_values()
        self.combo_range.current(1); self.set_range() 
        messagebox.showinfo("Warm Mode", "Applied Safe Presets")

    def set_heater_load(self, ohm_setting):
        if self.is_connected:
            resistance_map = {
                1: Model336.HeaterResistance.HEATER_25_OHM,
                2: Model336.HeaterResistance.HEATER_50_OHM,
            }
            heater_resistance = resistance_map[ohm_setting]
            self._enforce_heater_power_limit(heater_resistance)
            messagebox.showinfo("Info", f"Heater load configured with {self.max_heater_power_w:.0f} W safety cap.")

    def toggle_logging(self):
        if not self.log_running:
            f = filedialog.asksaveasfilename(defaultextension=".csv")
            if f:
                self.log_file = open(f, 'w', newline='')
                self.csv_writer = csv.writer(self.log_file)
                self.csv_writer.writerow([
                    "Time",
                    "Temp(K)",
                    "Heater(%)",
                    "Heater(W)",
                    "Target(K)",
                    "Cycle",
                    "Phase",
                    "QuasiEqTime(s)",
                ])
                self.log_running = True
                self.btn_log.config(text="STOP", foreground="red")
        else:
            self.log_running = False
            self.log_file.close()
            self.btn_log.config(text="START LOG", foreground="black")

    def on_close(self):
        """Optimized Shutdown Sequence"""
        # 1. IMMEDIATE KILL SWITCH
        self.app_running = False 
        self.stop_cycle_program()
        
        # 2. Cancel pending loop if it exists
        if self.loop_id:
            try: self.root.after_cancel(self.loop_id)
            except: pass

        # 3. Inform User (Visual Feedback)
        self.root.title("Disconnecting... Please Wait")
        self.root.update()

        # 4. Safety Shutdown (Heater Off)
        if self.is_connected:
            try:
                self.ls.set_heater_range(1, 0)
            except:
                pass # If instrument is stuck, don't hang the GUI forever

        # 5. Destroy
        self.root.destroy()
        sys.exit()

if __name__ == "__main__":
    root = tk.Tk()
    app = LakeShoreGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
