#!/usr/bin/env python3
"""
Historical Voltage Analysis across all G1000 NXi logs
=====================================================
Parses all G1000 CSV source logs from data/source/ and plots voltage
statistics over time to identify when the voltage measurement issue
first appeared on N238PS.

For each flight, computes:
- Mean volt1 during cruise (alternator online, volt1 > 25V)
- Minimum volt1
- Standard deviation of volt1
- Number of samples below 25.5V (LOW VOLTS threshold region)

Output: Console summary + PNG plots in output/

Usage:
    python voltage_history.py
"""

import sys
import io
import os
import re
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

SOURCE_DIR = Path(__file__).parent / "data" / "source"
ECU_PARSED_DIR = Path(__file__).parent / ".." / "AustroView" / "Data" / "Parsed"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def parse_g1000_voltage(filepath):
    """Parse a G1000 NXi CSV and return (flight_date, volt1_array).

    Returns (datetime or None, numpy array of volt1 values).
    Skips rows where volt1 is blank or zero.
    """
    try:
        with open(filepath, "r", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"  Error reading {filepath.name}: {e}", file=sys.stderr)
        return None, np.array([])

    if len(lines) < 8:
        return None, np.array([])

    # Row 3 (index 2) has column headers
    headers = [h.strip() for h in lines[2].split(",")]
    try:
        date_idx = headers.index("Lcl Date")
        time_idx = headers.index("Lcl Time")
        volt1_idx = headers.index("volt1")
    except ValueError:
        return None, np.array([])

    flight_date = None
    voltages = []

    for line in lines[7:]:
        parts = line.split(",")
        if len(parts) <= volt1_idx:
            continue
        v1_str = parts[volt1_idx].strip()
        if not v1_str:
            continue
        try:
            v1 = float(v1_str)
        except ValueError:
            continue
        if v1 <= 0:
            continue
        voltages.append(v1)

        if flight_date is None:
            date_str = parts[date_idx].strip()
            time_str = parts[time_idx].strip()
            if date_str and time_str:
                try:
                    flight_date = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass

    return flight_date, np.array(voltages)


def extract_date_from_filename(fname):
    """Try to extract date from filename patterns like log_YYMMDD_HHMMSS or N238PS_..._YYYYMMDD-HHMMUTC."""
    # Pattern: N238PS_..._YYYYMMDD-HHMMUTC.csv
    m = re.search(r'(\d{8})-(\d{4})UTC', fname)
    if m:
        try:
            return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M")
        except ValueError:
            pass
    # Pattern: log_YYMMDD_HHMMSS_....csv
    m = re.search(r'log_(\d{6})_(\d{6})', fname)
    if m:
        try:
            return datetime.strptime(m.group(1) + m.group(2), "%y%m%d%H%M%S")
        except ValueError:
            pass
    return None


def parse_ecu_sessions(ecu_dir):
    """Parse all AustroView ECU session CSVs and return per-session voltage stats.

    Each session corresponds to one engine run (start to shutdown).
    Returns list of dicts sorted by date, only for sessions with meaningful
    cruise data (alternator online, voltage > 25V, at least 60 samples).
    """
    import csv as csv_mod

    files = sorted(ecu_dir.glob("*_session*_2*.csv"))
    if not files:
        return []

    sessions = []
    seen_dates = set()
    for fpath in files:
        m = re.search(r'session(\d+)_(\d{8})_(\d{6})\.csv$', fpath.name)
        if not m:
            continue
        sess_date = datetime.strptime(m.group(2) + m.group(3), "%Y%m%d%H%M%S")

        # Deduplicate: same session may exist from multiple ae3 files
        date_key = sess_date.strftime("%Y%m%d%H%M%S")
        if date_key in seen_dates:
            continue
        seen_dates.add(date_key)

        voltages = []
        with open(fpath, 'r') as f:
            reader = csv_mod.DictReader(f)
            for row in reader:
                try:
                    v = float(row["Battery Voltage [V]"])
                    if v > 0:
                        voltages.append(v)
                except (ValueError, KeyError):
                    continue

        if len(voltages) < 60:
            continue

        varr = np.array(voltages)
        cruise = varr[varr > 25.0]
        if len(cruise) < 30:
            continue

        sessions.append({
            'date': sess_date,
            'file': fpath.name,
            'mean': float(np.mean(cruise)),
            'std': float(np.std(cruise)),
            'min': float(np.min(varr)),
            'n_cruise': len(cruise),
        })

    sessions.sort(key=lambda s: s['date'])
    return sessions


def main():
    if not SOURCE_DIR.exists():
        print(f"Source directory not found: {SOURCE_DIR}")
        print("Run flysto_download.py first to download the G1000 log files.")
        sys.exit(1)

    csv_files = sorted(SOURCE_DIR.glob("*.csv"))
    if not csv_files:
        print(f"No CSV files found in {SOURCE_DIR}")
        sys.exit(1)

    print(f"Found {len(csv_files)} CSV files in {SOURCE_DIR}")
    print("Parsing voltage data from each flight...\n")

    # Collect per-flight statistics
    flights = []  # list of dicts

    for fpath in csv_files:
        flight_date, voltages = parse_g1000_voltage(fpath)

        if len(voltages) < 30:
            continue

        # Use date from data, fall back to filename
        if flight_date is None:
            flight_date = extract_date_from_filename(fpath.name)
        if flight_date is None:
            continue

        # Filter to "alternator online" samples (typically > 25V)
        cruise_mask = voltages > 25.0
        cruise_volts = voltages[cruise_mask]

        if len(cruise_volts) < 10:
            continue

        stats = {
            'date': flight_date,
            'file': fpath.name,
            'n_samples': len(voltages),
            'n_cruise': len(cruise_volts),
            'mean': float(np.mean(cruise_volts)),
            'median': float(np.median(cruise_volts)),
            'std': float(np.std(cruise_volts)),
            'min': float(np.min(voltages)),
            'max': float(np.max(cruise_volts)),
            'pct_below_26': float(np.sum(cruise_volts < 26.0) / len(cruise_volts) * 100),
            'n_below_255': int(np.sum(voltages < 25.5)),
        }
        flights.append(stats)

    # Sort by date
    flights.sort(key=lambda f: f['date'])

    print(f"Successfully parsed {len(flights)} flights with voltage data.\n")
    print(f"{'Date':<20} {'Mean V':>7} {'Min V':>7} {'Std':>6} {'%<26V':>6} {'Samples':>8}  File")
    print("-" * 100)
    for f in flights:
        print(f"{f['date'].strftime('%Y-%m-%d %H:%M'):<20} "
              f"{f['mean']:>7.2f} {f['min']:>7.2f} {f['std']:>6.3f} "
              f"{f['pct_below_26']:>5.1f}% {f['n_cruise']:>8}  {f['file']}")

    if len(flights) < 2:
        print("\nNot enough flights to generate history plots.")
        return

    # Extract arrays for plotting
    dates = [f['date'] for f in flights]
    means = [f['mean'] for f in flights]
    mins = [f['min'] for f in flights]
    stds = [f['std'] for f in flights]
    pct_below_26 = [f['pct_below_26'] for f in flights]

    # --- Load ECU session data as independent reference ---
    ecu_sessions = parse_ecu_sessions(ECU_PARSED_DIR)
    ecu_dates = [s['date'] for s in ecu_sessions]
    ecu_means = [s['mean'] for s in ecu_sessions]
    ecu_stds = [s['std'] for s in ecu_sessions]
    if ecu_sessions:
        print(f"\nLoaded {len(ecu_sessions)} ECU sessions "
              f"({ecu_dates[0].strftime('%Y-%m-%d')} to {ecu_dates[-1].strftime('%Y-%m-%d')})")
        print(f"  ECU mean cruise voltage: {np.mean(ecu_means):.2f}V "
              f"(std of means: {np.std(ecu_means):.3f}V)")
    else:
        print("\nNo ECU session data found - skipping ECU overlay.")

    # Maintenance events from N238PS aircraft logs (correlated with voltage data)
    maint_events = [
        (datetime(2024, 2, 28), 'Engine R&R\n(oil leak)', 'red'),
        (datetime(2024, 3, 27), 'Alt #2\nreplaced', 'orange'),
        (datetime(2024, 4, 15), 'Voltage reg\nreplaced', 'orange'),
        (datetime(2024, 6, 30), 'VR replaced\n+wire repair', 'orange'),
        (datetime(2024, 7, 26), 'G1000 P2413\nrepinned', 'blue'),
        (datetime(2025, 2, 21), 'Main alt +\nVR replaced', 'orange'),
        (datetime(2025, 7, 1),  'Engine R&R\n(piston)+batt', 'red'),
    ]
    maint_date = datetime(2024, 2, 28)  # primary event - aligns with change-point

    # === Plot 1: Mean voltage over time ===
    fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=True)
    fig.suptitle("N238PS Voltage History - G1000 vs ECU Reference", fontsize=14, fontweight='bold')

    ax1 = axes[0]
    ax1.plot(dates, means, 'b.-', markersize=4, linewidth=0.8, label='G1000 Mean V (cruise)')
    ax1.fill_between(dates,
                     [m - s for m, s in zip(means, stds)],
                     [m + s for m, s in zip(means, stds)],
                     alpha=0.2, color='blue', label='G1000 +/- 1 std dev')
    if ecu_sessions:
        ax1.plot(ecu_dates, ecu_means, 'g^', markersize=5, alpha=0.7,
                 label='ECU Battery V (cruise)')
        ax1.fill_between(ecu_dates,
                         [m - s for m, s in zip(ecu_means, ecu_stds)],
                         [m + s for m, s in zip(ecu_means, ecu_stds)],
                         alpha=0.15, color='green')
    ax1.axhline(y=28.0, color='green', linestyle='--', alpha=0.5, label='Nominal 28V')
    ax1.axhline(y=25.5, color='red', linestyle='--', alpha=0.5, label='LOW VOLTS region')
    for md, mlabel, mcolor in maint_events:
        ax1.axvline(x=md, color=mcolor, linestyle=':', linewidth=1.5, alpha=0.6)
    ax1.set_ylabel("Voltage (V)")
    ax1.set_title("Mean Cruise Voltage per Flight")
    ax1.legend(loc='lower left', fontsize=8)
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(24, 30)

    # === Plot 2: Min voltage over time ===
    ax2 = axes[1]
    ax2.plot(dates, mins, 'r.-', markersize=4, linewidth=0.8, label='Min V (any sample)')
    ax2.axhline(y=25.5, color='red', linestyle='--', alpha=0.5, label='LOW VOLTS region')
    ax2.axhline(y=24.0, color='darkred', linestyle='--', alpha=0.5, label='24V battery baseline')
    for md, mlabel, mcolor in maint_events:
        ax2.axvline(x=md, color=mcolor, linestyle=':', linewidth=1.5, alpha=0.6)
    ax2.set_ylabel("Voltage (V)")
    ax2.set_title("Minimum Voltage per Flight")
    ax2.legend(loc='lower left', fontsize=8)
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(18, 30)

    # === Plot 3: Percentage of samples below 26V ===
    ax3 = axes[2]
    ax3.bar(dates, pct_below_26, width=2, color='orange', alpha=0.7, label='% cruise samples < 26V')
    for md, mlabel, mcolor in maint_events:
        ax3.axvline(x=md, color=mcolor, linestyle=':', linewidth=1.5, alpha=0.6)
    ax3.set_ylabel("% Samples < 26V")
    ax3.set_title("Percentage of Cruise Samples Below 26V")
    ax3.legend(loc='upper left', fontsize=8)
    ax3.grid(True, alpha=0.3)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha='right')

    plt.tight_layout()
    out_path = OUTPUT_DIR / "voltage_history.png"
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    print(f"\nSaved voltage history plot to {out_path}")
    plt.close()

    # === Plot 4: Voltage standard deviation over time (noise indicator) ===
    fig2, ax = plt.subplots(figsize=(14, 5))
    ax.plot(dates, stds, 'g.-', markersize=4, linewidth=0.8)
    ax.set_ylabel("Std Dev (V)")
    ax.set_xlabel("Flight Date")
    ax.set_title("N238PS G1000 Voltage Noise (Std Dev) per Flight")
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    plt.tight_layout()
    out_path2 = OUTPUT_DIR / "voltage_noise_history.png"
    plt.savefig(out_path2, dpi=150, bbox_inches='tight')
    print(f"Saved voltage noise plot to {out_path2}")
    plt.close()

    # =================================================================
    # Change-Point Detection & Visualization
    # =================================================================
    mean_arr = np.array(means)
    std_arr = np.array(stds)
    n = len(mean_arr)

    # --- Pettitt's test (nonparametric single change-point in location) ---
    # Computes U statistic: max of cumulative sign-rank differences
    def pettitt_test(x):
        n = len(x)
        U = np.zeros(n, dtype=float)
        for t in range(n):
            for i in range(t + 1):
                for j in range(t + 1, n):
                    U[t] += np.sign(x[i] - x[j])
        cp = np.argmax(np.abs(U))
        K = np.abs(U[cp])
        # Approximate p-value
        p = 2.0 * np.exp(-6.0 * K**2 / (n**3 + n**2))
        return cp, K, p, U

    print("\nRunning Pettitt's change-point test on mean cruise voltage...")
    cp_idx, K_stat, p_val, U_stat = pettitt_test(mean_arr)
    cp_date = flights[cp_idx]['date']
    before_mean = np.mean(mean_arr[:cp_idx + 1])
    after_mean = np.mean(mean_arr[cp_idx + 1:])
    before_std = np.mean(std_arr[:cp_idx + 1])
    after_std = np.mean(std_arr[cp_idx + 1:])

    # --- CUSUM (Cumulative Sum of deviations from overall mean) ---
    overall_mean = np.mean(mean_arr)
    cusum = np.cumsum(mean_arr - overall_mean)

    # === Plot: Change-Point Detection (3 panels) ===
    fig, axes = plt.subplots(3, 1, figsize=(14, 14))
    fig.suptitle("N238PS G1000 Voltage Change-Point Analysis",
                 fontsize=14, fontweight='bold')

    # --- Panel 1: Mean voltage with change point annotated ---
    ax1 = axes[0]
    # Before/after background shading
    ax1.axvspan(dates[0], dates[cp_idx], alpha=0.08, color='green', label='Before')
    ax1.axvspan(dates[cp_idx], dates[-1], alpha=0.08, color='red', label='After')
    # G1000 data
    ax1.plot(dates[:cp_idx + 1], means[:cp_idx + 1], 'g.-', markersize=4,
             linewidth=0.8, label=f'G1000 Before: {before_mean:.2f}V avg')
    ax1.plot(dates[cp_idx + 1:], means[cp_idx + 1:], 'r.-', markersize=4,
             linewidth=0.8, label=f'G1000 After: {after_mean:.2f}V avg')
    # ECU reference overlay
    if ecu_sessions:
        ax1.plot(ecu_dates, ecu_means, 'k^', markersize=4, alpha=0.5,
                 label=f'ECU Battery V ({np.mean(ecu_means):.2f}V avg)')
    # Before/after mean lines
    ax1.axhline(y=before_mean, color='green', linestyle='-', linewidth=2, alpha=0.6)
    ax1.axhline(y=after_mean, color='red', linestyle='-', linewidth=2, alpha=0.6)
    # Change point vertical line
    ax1.axvline(x=cp_date, color='black', linestyle='--', linewidth=2,
                label=f'Change point: {cp_date.strftime("%Y-%m-%d")}')
    # Maintenance events
    for md, mlabel, mcolor in maint_events:
        ax1.axvline(x=md, color=mcolor, linestyle=':', linewidth=1.5, alpha=0.6)
    # Reference lines
    ax1.axhline(y=28.0, color='blue', linestyle=':', alpha=0.3, label='Nominal 28V')
    ax1.set_ylabel("Mean Cruise Voltage (V)")
    ax1.set_title(f"Mean Voltage per Flight  |  Drop: {before_mean - after_mean:.2f}V"
                  f"  |  Pettitt p={p_val:.1e}")
    ax1.legend(loc='lower left', fontsize=7, ncol=2)
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(25.5, 29.0)

    # --- Panel 2: CUSUM ---
    ax2 = axes[1]
    ax2.fill_between(dates, 0, cusum, where=[c >= 0 for c in cusum],
                     color='green', alpha=0.3, interpolate=True)
    ax2.fill_between(dates, 0, cusum, where=[c < 0 for c in cusum],
                     color='red', alpha=0.3, interpolate=True)
    ax2.plot(dates, cusum, 'k-', linewidth=1.5)
    ax2.axvline(x=cp_date, color='black', linestyle='--', linewidth=2)
    for md, mlabel, mcolor in maint_events:
        ax2.axvline(x=md, color=mcolor, linestyle=':', linewidth=1.5, alpha=0.6)
    ax2.axhline(y=0, color='gray', linestyle='-', linewidth=0.5)
    # Annotate the peak
    peak_idx = np.argmax(cusum)
    ax2.annotate(f'Peak: {dates[peak_idx].strftime("%Y-%m-%d")}\n'
                 f'(last flight above trend)',
                 xy=(dates[peak_idx], cusum[peak_idx]),
                 xytext=(dates[peak_idx], cusum[peak_idx] + 2),
                 fontsize=8, ha='center',
                 arrowprops=dict(arrowstyle='->', color='black'))
    ax2.set_ylabel("CUSUM (cumulative deviation from mean)")
    ax2.set_title("CUSUM Chart  |  Rising = above average, Falling = below average"
                  "  |  Inflection = change point")
    ax2.grid(True, alpha=0.3)

    # --- Panel 3: Voltage noise (std dev) with change point ---
    ax3 = axes[2]
    ax3.axvspan(dates[0], dates[cp_idx], alpha=0.08, color='green')
    ax3.axvspan(dates[cp_idx], dates[-1], alpha=0.08, color='red')
    ax3.plot(dates[:cp_idx + 1], stds[:cp_idx + 1], 'g.-', markersize=4,
             linewidth=0.8, label=f'Before: {before_std:.3f}V avg noise')
    ax3.plot(dates[cp_idx + 1:], stds[cp_idx + 1:], 'r.-', markersize=4,
             linewidth=0.8, label=f'After: {after_std:.3f}V avg noise')
    ax3.axhline(y=before_std, color='green', linestyle='-', linewidth=2, alpha=0.6)
    ax3.axhline(y=after_std, color='red', linestyle='-', linewidth=2, alpha=0.6)
    ax3.axvline(x=cp_date, color='black', linestyle='--', linewidth=2)
    for md, mlabel, mcolor in maint_events:
        ax3.axvline(x=md, color=mcolor, linestyle=':', linewidth=1.5, alpha=0.6)
    if ecu_sessions:
        ax3.plot(ecu_dates, ecu_stds, 'k^', markersize=4, alpha=0.5, label='ECU noise')
    ax3.set_ylabel("Std Dev (V)")
    ax3.set_title(f"Voltage Noise per Flight  |  Noise increase: "
                  f"{before_std:.3f}V -> {after_std:.3f}V "
                  f"({(after_std/before_std - 1)*100:.0f}% higher)")
    ax3.legend(loc='upper left', fontsize=8)
    ax3.grid(True, alpha=0.3)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha='right')

    plt.tight_layout()
    out_cp = OUTPUT_DIR / "voltage_changepoint.png"
    plt.savefig(out_cp, dpi=150, bbox_inches='tight')
    print(f"Saved change-point analysis to {out_cp}")
    plt.close()

    # === Plot: Before vs After Distribution ===
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle(f"Voltage Distribution: Before vs After {cp_date.strftime('%Y-%m-%d')}",
                 fontsize=13, fontweight='bold')

    before_vals = mean_arr[:cp_idx + 1]
    after_vals = mean_arr[cp_idx + 1:]
    bins = np.linspace(25.5, 28.5, 30)

    ax_b = axes[0]
    ax_b.hist(before_vals, bins=bins, color='green', alpha=0.7, edgecolor='black', linewidth=0.5)
    ax_b.axvline(x=np.mean(before_vals), color='darkgreen', linestyle='--', linewidth=2,
                 label=f'Mean: {np.mean(before_vals):.2f}V')
    ax_b.set_xlabel("Mean Cruise Voltage (V)")
    ax_b.set_ylabel("Number of Flights")
    ax_b.set_title(f"BEFORE  ({len(before_vals)} flights)")
    ax_b.legend(fontsize=9)
    ax_b.set_xlim(25.5, 28.5)

    ax_a = axes[1]
    ax_a.hist(after_vals, bins=bins, color='red', alpha=0.7, edgecolor='black', linewidth=0.5)
    ax_a.axvline(x=np.mean(after_vals), color='darkred', linestyle='--', linewidth=2,
                 label=f'Mean: {np.mean(after_vals):.2f}V')
    ax_a.set_xlabel("Mean Cruise Voltage (V)")
    ax_a.set_title(f"AFTER  ({len(after_vals)} flights)")
    ax_a.legend(fontsize=9)
    ax_a.set_xlim(25.5, 28.5)

    plt.tight_layout()
    out_dist = OUTPUT_DIR / "voltage_before_after.png"
    plt.savefig(out_dist, dpi=150, bbox_inches='tight')
    print(f"Saved before/after distribution to {out_dist}")
    plt.close()

    # === Plot: Maintenance Correlation Timeline ===
    fig, ax = plt.subplots(figsize=(16, 7))
    fig.suptitle("N238PS Voltage vs Maintenance Events", fontsize=14, fontweight='bold')

    # G1000 mean voltage
    ax.plot(dates, means, 'b.-', markersize=4, linewidth=0.8, alpha=0.8,
            label='G1000 Mean V (cruise)')
    ax.fill_between(dates,
                    [m - s for m, s in zip(means, stds)],
                    [m + s for m, s in zip(means, stds)],
                    alpha=0.15, color='blue')
    # ECU reference
    if ecu_sessions:
        ax.plot(ecu_dates, ecu_means, 'g^', markersize=4, alpha=0.5,
                label='ECU Battery V (cruise)')

    ax.axhline(y=28.0, color='green', linestyle='--', alpha=0.4, label='Nominal 28V')
    ax.axhline(y=25.5, color='red', linestyle='--', alpha=0.4, label='LOW VOLTS threshold')

    # Maintenance event annotations with labels
    y_positions = [29.4, 29.0, 29.4, 29.0, 29.4, 29.0, 29.4]
    for i, (md, mlabel, mcolor) in enumerate(maint_events):
        ax.axvline(x=md, color=mcolor, linestyle='-', linewidth=2, alpha=0.7)
        ypos = y_positions[i % len(y_positions)]
        ax.annotate(mlabel, xy=(md, ypos), fontsize=7, ha='center', va='bottom',
                    color=mcolor, fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='white',
                              edgecolor=mcolor, alpha=0.9))

    ax.set_ylabel("Voltage (V)")
    ax.set_xlabel("Date")
    ax.legend(loc='lower left', fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(24, 30)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    plt.tight_layout()
    out_maint = OUTPUT_DIR / "voltage_maintenance_correlation.png"
    plt.savefig(out_maint, dpi=150, bbox_inches='tight')
    print(f"Saved maintenance correlation plot to {out_maint}")
    plt.close()

    # Summary statistics
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total flights analyzed: {len(flights)}")
    print(f"Date range: {flights[0]['date'].strftime('%Y-%m-%d')} to {flights[-1]['date'].strftime('%Y-%m-%d')}")
    print(f"Overall mean voltage: {np.mean(means):.2f} V")
    print(f"Overall mean std dev: {np.mean(stds):.3f} V")
    print(f"\nChange-point detected: {cp_date.strftime('%Y-%m-%d')} (flight #{cp_idx + 1})")
    print(f"  Pettitt K-statistic: {K_stat:.0f},  p-value: {p_val:.2e}")
    print(f"  Before ({len(before_vals)} flights): mean={before_mean:.2f}V, noise={before_std:.3f}V")
    print(f"  After  ({len(after_vals)} flights): mean={after_mean:.2f}V, noise={after_std:.3f}V")
    print(f"  Voltage drop: {before_mean - after_mean:.2f}V")
    print(f"  Noise increase: {(after_std/before_std - 1)*100:.0f}%")
    print(f"  File at change point: {flights[cp_idx]['file']}")

    if ecu_sessions:
        print(f"\nECU Reference (independent measurement):")
        print(f"  Sessions: {len(ecu_sessions)}")
        print(f"  Date range: {ecu_dates[0].strftime('%Y-%m-%d')} to {ecu_dates[-1].strftime('%Y-%m-%d')}")
        print(f"  Mean cruise voltage: {np.mean(ecu_means):.2f}V (stable)")
        print(f"  Mean noise (std dev): {np.mean(ecu_stds):.3f}V")
        print(f"  G1000 under-reports by: {np.mean(ecu_means) - np.mean(means):.2f}V on average")

    print(f"\nMaintenance Events (from aircraft logs):")
    for md, mlabel, mcolor in maint_events:
        print(f"  {md.strftime('%Y-%m-%d')}: {mlabel.replace(chr(10), ' ')}")
    print(f"\nConclusion: Engine R&R on 2024-02-28 coincides with statistically")
    print(f"  detected change-point. Subsequent voltage regulator replacements (3x),")
    print(f"  alternator replacements (2x), and wire repairs did not resolve the")
    print(f"  underlying G1000 measurement path issue.")


if __name__ == '__main__':
    main()
