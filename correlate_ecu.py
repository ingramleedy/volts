"""
Three-Source Voltage Correlation: G1000 NXi vs VDL48 vs AE300 ECU
=================================================================
Adds the Austro Engine AE300 ECU battery voltage (channel 808) as a third
independent measurement for the two flights of N238PS on 2026-02-08.

Data sources:
  - G1000 NXi volt1:   data/N238PS_*_20260208-*.csv  (1-sec sampling)
  - Triplett VDL48:     data/LOG_VD.CSV               (2-sec sampling)
  - AE300 ECU ch808:    ../AustroView/Data/Parsed/     (1-sec sampling)

Flight 1: KBOW -> KSPG (15:51 - 16:47 UTC)
Flight 2: KSPG -> KBOW (18:10 - 19:25 UTC)
"""

import sys
import io
import csv
import glob
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from scipy import stats
from pathlib import Path

# Fix Windows console encoding
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data"
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

AUSTROVIEW_PARSED = SCRIPT_DIR / ".." / "AustroView" / "Data" / "Parsed"

FLIGHT1_CSV = DATA_DIR / "N238PS_KBOW-KSPG_20260208-1551UTC.csv"
FLIGHT2_CSV = DATA_DIR / "N238PS_KSPG-KBOW_20260208-1812UTC.csv"
VDL_CSV = DATA_DIR / "LOG_VD.CSV"


# =============================================================================
# Parsing (G1000 and VDL reused from voltage_analysis.py)
# =============================================================================

def parse_g1000(filepath):
    """Parse a G1000 NXi data log CSV, returning timestamps and volt1 values."""
    times = []
    volt1 = []
    with open(filepath, "r") as f:
        lines = f.readlines()
    headers = [h.strip() for h in lines[2].split(",")]
    date_idx = headers.index("Lcl Date")
    time_idx = headers.index("Lcl Time")
    volt1_idx = headers.index("volt1")
    for line in lines[7:]:
        parts = line.split(",")
        if len(parts) <= volt1_idx:
            continue
        date_str = parts[date_idx].strip()
        time_str = parts[time_idx].strip()
        v1_str = parts[volt1_idx].strip()
        if not date_str or not time_str or not v1_str:
            continue
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
            v1 = float(v1_str)
            times.append(dt)
            volt1.append(v1)
        except ValueError:
            continue
    return np.array(times), np.array(volt1)


def parse_vdl(filepath):
    """Parse the VDL48 CSV, returning elapsed seconds and voltage."""
    times_str = []
    voltages = []
    with open(filepath, "r") as f:
        lines = f.readlines()
    for line in lines[12:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        if len(parts) < 3:
            continue
        try:
            t = parts[1].strip()
            v = float(parts[2].strip())
            times_str.append(t)
            voltages.append(v)
        except ValueError:
            continue
    t0 = datetime.strptime(times_str[0], "%H:%M:%S")
    elapsed = []
    for ts in times_str:
        dt = datetime.strptime(ts, "%H:%M:%S")
        elapsed.append((dt - t0).total_seconds())
    return np.array(elapsed), np.array(voltages)


def segment_vdl(elapsed, voltage):
    """Segment VDL data into Flight 1, Idle, Flight 2."""
    FLIGHT_THRESHOLD = 27.0
    ZERO_THRESHOLD = 1.0
    WINDOW = 30
    last_nonzero = len(voltage) - 1
    while last_nonzero > 0 and voltage[last_nonzero] < ZERO_THRESHOLD:
        last_nonzero -= 1
    end_f1 = None
    for i in range(WINDOW, last_nonzero):
        if all(voltage[i:i + WINDOW] < FLIGHT_THRESHOLD):
            end_f1 = i
            break
    start_f2 = None
    if end_f1 is not None:
        for i in range(end_f1 + WINDOW, last_nonzero):
            if all(voltage[i:i + WINDOW] > FLIGHT_THRESHOLD):
                start_f2 = i
                break
    end_f2 = last_nonzero + 1
    if end_f1 is None or start_f2 is None:
        raise RuntimeError("Could not segment VDL data into flight phases.")
    return (0, end_f1), (end_f1, start_f2), (start_f2, end_f2)


def align_vdl_to_g1000(g1000_times, vdl_elapsed, vdl_seg):
    """Create datetime array for a VDL segment aligned to G1000 timestamps."""
    seg_start, seg_end = vdl_seg
    g1000_start = g1000_times[0]
    vdl_seg_elapsed = vdl_elapsed[seg_start:seg_end] - vdl_elapsed[seg_start]
    return np.array([
        g1000_start + timedelta(seconds=float(s)) for s in vdl_seg_elapsed
    ])


def parse_ecu(session_pattern):
    """Parse an AustroView session CSV, returning timestamps and battery voltage.

    Args:
        session_pattern: glob pattern to find the session CSV file.

    Returns:
        (times, voltage) as numpy arrays.
    """
    matches = sorted(glob.glob(str(session_pattern)))
    if not matches:
        raise FileNotFoundError(f"No AustroView CSV matching: {session_pattern}")
    filepath = matches[-1]  # newest if multiple matches
    print(f"  ECU file: {Path(filepath).name}")

    times = []
    voltages = []
    with open(filepath, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                dt = datetime.strptime(row["Timestamp"], "%Y-%m-%d %H:%M:%S")
                v = float(row["Battery Voltage [V]"])
                times.append(dt)
                voltages.append(v)
            except (ValueError, KeyError):
                continue

    return np.array(times), np.array(voltages)


# =============================================================================
# Three-way resampling
# =============================================================================

def resample_three(g_times, g_volts, v_times, v_volts, e_times, e_volts):
    """Resample G1000, VDL, and ECU onto a common 2-second grid.

    Uses the overlapping time range of all three sources.
    """
    ref_t0 = g_times[0]
    g_sec = np.array([(t - ref_t0).total_seconds() for t in g_times])
    v_sec = np.array([(t - ref_t0).total_seconds() for t in v_times])
    e_sec = np.array([(t - ref_t0).total_seconds() for t in e_times])

    t_start = max(g_sec[0], v_sec[0], e_sec[0])
    t_end = min(g_sec[-1], v_sec[-1], e_sec[-1])
    common_t = np.arange(t_start, t_end, 2.0)

    g_interp = np.interp(common_t, g_sec, g_volts)
    v_interp = np.interp(common_t, v_sec, v_volts)
    e_interp = np.interp(common_t, e_sec, e_volts)

    common_dt = np.array([ref_t0 + timedelta(seconds=float(s)) for s in common_t])
    return common_dt, g_interp, v_interp, e_interp


# =============================================================================
# Statistics
# =============================================================================

def compute_pair_stats(a, b, a_label, b_label):
    """Compute pairwise statistics between two voltage arrays."""
    diff = a - b
    r, p_corr = stats.pearsonr(a, b)
    t_stat, p_paired = stats.ttest_rel(a, b)
    return {
        "a_label": a_label,
        "b_label": b_label,
        "a_mean": np.mean(a),
        "b_mean": np.mean(b),
        "diff_mean": np.mean(diff),
        "diff_median": np.median(diff),
        "diff_std": np.std(diff),
        "diff_min": np.min(diff),
        "diff_max": np.max(diff),
        "diff_p2_5": np.percentile(diff, 2.5),
        "diff_p97_5": np.percentile(diff, 97.5),
        "pearson_r": r,
        "p_corr": p_corr,
        "t_stat": t_stat,
        "p_paired": p_paired,
        "diff": diff,
    }


def print_three_way_stats(g, v, e, label):
    """Print statistics for all three pairs."""
    pairs = [
        compute_pair_stats(g, v, "G1000", "VDL48"),
        compute_pair_stats(g, e, "G1000", "ECU"),
        compute_pair_stats(e, v, "ECU", "VDL48"),
    ]

    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")
    print(f"  Samples (paired, 2-sec grid):  {len(g)}")
    print(f"  Duration:                      {len(g)*2/60:.1f} min")
    print(f"")
    print(f"  G1000 volt1  - mean: {np.mean(g):6.2f} V   std: {np.std(g):.3f} V   "
          f"range: [{np.min(g):.2f}, {np.max(g):.2f}]")
    print(f"  VDL48 ref    - mean: {np.mean(v):6.2f} V   std: {np.std(v):.3f} V   "
          f"range: [{np.min(v):.2f}, {np.max(v):.2f}]")
    print(f"  ECU ch808    - mean: {np.mean(e):6.2f} V   std: {np.std(e):.3f} V   "
          f"range: [{np.min(e):.2f}, {np.max(e):.2f}]")

    for p in pairs:
        sig = "***" if p["p_paired"] < 0.001 else ("**" if p["p_paired"] < 0.01 else "")
        print(f"\n  {p['a_label']} - {p['b_label']}:")
        print(f"    Mean diff:   {p['diff_mean']:+.3f} V")
        print(f"    Std Dev:     {p['diff_std']:.3f} V")
        print(f"    95% range:   [{p['diff_p2_5']:+.3f}, {p['diff_p97_5']:+.3f}] V")
        print(f"    Min/Max:     [{p['diff_min']:+.3f}, {p['diff_max']:+.3f}] V")
        print(f"    Pearson r:   {p['pearson_r']:.4f}  (p = {p['p_corr']:.2e})")
        print(f"    Paired t:    t = {p['t_stat']:.2f},  p = {p['p_paired']:.2e}  {sig}")

    return pairs


# =============================================================================
# Plotting
# =============================================================================

def plot_three_way_comparison(common_dt, g, v, e, title, filename):
    """Time-series overlay of all three voltage sources with difference traces."""
    fig, (ax_volt, ax_diff) = plt.subplots(2, 1, figsize=(14, 7),
                                            height_ratios=[2, 1], sharex=True)

    # Voltage traces
    ax_volt.plot(common_dt, v, color="tab:green", linewidth=0.9,
                 alpha=0.85, label="VDL48 (reference)")
    ax_volt.plot(common_dt, e, color="tab:orange", linewidth=0.9,
                 alpha=0.85, label="ECU ch808")
    ax_volt.plot(common_dt, g, color="tab:blue", linewidth=0.9,
                 alpha=0.85, label="G1000 volt1")
    ax_volt.set_ylabel("Voltage (V)")
    ax_volt.set_title(title)
    ax_volt.legend(loc="lower right", fontsize=9)
    ax_volt.grid(True, alpha=0.3)

    # Difference traces (all relative to VDL reference)
    ax_diff.plot(common_dt, g - v, color="tab:blue", linewidth=0.7,
                 alpha=0.8, label="G1000 - VDL48")
    ax_diff.plot(common_dt, e - v, color="tab:orange", linewidth=0.7,
                 alpha=0.8, label="ECU - VDL48")
    ax_diff.axhline(0, color="black", linewidth=0.5, linestyle="--", alpha=0.4)
    ax_diff.set_ylabel("Difference from VDL48 (V)")
    ax_diff.set_xlabel("UTC Time")
    ax_diff.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax_diff.legend(loc="lower right", fontsize=9)
    ax_diff.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / filename, dpi=150, bbox_inches="tight")
    print(f"  Saved: {OUTPUT_DIR / filename}")
    return fig


def plot_ecu_vs_vdl_scatter(e1, v1, e2, v2):
    """Scatter: ECU vs VDL with 1:1 line to see if ECU agrees with reference."""
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(v1, e1, s=2, alpha=0.4, color="tab:blue", label="Flight 1")
    ax.scatter(v2, e2, s=2, alpha=0.4, color="tab:green", label="Flight 2")

    all_vals = np.concatenate([v1, v2, e1, e2])
    lo, hi = np.min(all_vals) - 0.5, np.max(all_vals) + 0.5
    ax.plot([lo, hi], [lo, hi], "k--", linewidth=0.8, label="1:1 line")

    all_vdl = np.concatenate([v1, v2])
    all_ecu = np.concatenate([e1, e2])
    slope, intercept, r, _, _ = stats.linregress(all_vdl, all_ecu)
    fit_x = np.array([lo, hi])
    ax.plot(fit_x, slope * fit_x + intercept, "r-", linewidth=1,
            label=f"Fit: ECU = {slope:.3f}*VDL {intercept:+.2f}  (r={r:.3f})")

    ax.set_xlabel("VDL48 Voltage (V)")
    ax.set_ylabel("ECU Battery Voltage (V)")
    ax.set_title("ECU vs VDL48 - Scatter (does ECU agree with reference?)")
    ax.legend(fontsize=8)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "ecu_vs_vdl_scatter.png", dpi=150)
    print(f"  Saved: {OUTPUT_DIR / 'ecu_vs_vdl_scatter.png'}")
    return fig


def plot_three_way_histograms(pairs1, pairs2):
    """Histograms of voltage differences for all three pairs, both flights."""
    fig, axes = plt.subplots(2, 3, figsize=(15, 7), sharey="row")

    pair_labels = ["G1000 - VDL48", "G1000 - ECU", "ECU - VDL48"]
    pair_colors = ["tab:blue", "tab:purple", "tab:orange"]
    flight_labels = ["Flight 1 (KBOW->KSPG)", "Flight 2 (KSPG->KBOW)"]

    for row, (pairs, flight_lbl) in enumerate([(pairs1, flight_labels[0]),
                                                (pairs2, flight_labels[1])]):
        for col, (pair, plbl, pclr) in enumerate(zip(pairs, pair_labels, pair_colors)):
            ax = axes[row, col]
            diff = pair["diff"]
            ax.hist(diff, bins=50, color=pclr, alpha=0.7, edgecolor="white",
                    linewidth=0.3)
            ax.axvline(np.mean(diff), color="red", linestyle="--", linewidth=1.2,
                       label=f"Mean: {np.mean(diff):+.3f} V")
            ax.axvline(0, color="black", linestyle="-", linewidth=0.8, alpha=0.4)
            ax.set_xlabel(f"{plbl} (V)")
            if col == 0:
                ax.set_ylabel(flight_lbl)
            ax.legend(fontsize=7)
            ax.grid(True, alpha=0.3)
            if row == 0:
                ax.set_title(plbl)

    fig.suptitle("Voltage Difference Distributions - Three Sources", y=1.02,
                 fontsize=13)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "three_way_histograms.png", dpi=150,
                bbox_inches="tight")
    print(f"  Saved: {OUTPUT_DIR / 'three_way_histograms.png'}")
    return fig


# =============================================================================
# Main
# =============================================================================

def main():
    print("Three-Source Voltage Correlation: G1000 vs VDL48 vs AE300 ECU")
    print("Aircraft: N238PS (Diamond DA40NG)  Date: 2026-02-08")
    print("=" * 70)

    # --- Parse G1000 ---
    print("\nParsing G1000 Flight 1 (KBOW -> KSPG)...")
    g1_times, g1_volts = parse_g1000(FLIGHT1_CSV)
    print(f"  {len(g1_volts)} samples, "
          f"{g1_times[0].strftime('%H:%M:%S')} - {g1_times[-1].strftime('%H:%M:%S')} UTC")

    print("Parsing G1000 Flight 2 (KSPG -> KBOW)...")
    g2_times, g2_volts = parse_g1000(FLIGHT2_CSV)
    print(f"  {len(g2_volts)} samples, "
          f"{g2_times[0].strftime('%H:%M:%S')} - {g2_times[-1].strftime('%H:%M:%S')} UTC")

    # --- Parse VDL48 ---
    print("\nParsing VDL48 log...")
    vdl_elapsed, vdl_voltage = parse_vdl(VDL_CSV)
    print(f"  {len(vdl_voltage)} samples over {vdl_elapsed[-1]/60:.1f} min")

    seg_f1, seg_idle, seg_f2 = segment_vdl(vdl_elapsed, vdl_voltage)
    vdl_f1_times = align_vdl_to_g1000(g1_times, vdl_elapsed, seg_f1)
    vdl_f1_volts = vdl_voltage[seg_f1[0]:seg_f1[1]]
    vdl_f2_times = align_vdl_to_g1000(g2_times, vdl_elapsed, seg_f2)
    vdl_f2_volts = vdl_voltage[seg_f2[0]:seg_f2[1]]

    # --- Parse ECU ---
    print("\nParsing AE300 ECU data...")
    ecu1_pattern = AUSTROVIEW_PARSED / "DataLog_*_session80_*.csv"
    ecu2_pattern = AUSTROVIEW_PARSED / "DataLog_*_session81_*.csv"

    print("  Flight 1 (session 80):")
    e1_times, e1_volts = parse_ecu(ecu1_pattern)
    print(f"    {len(e1_volts)} samples, "
          f"{e1_times[0].strftime('%H:%M:%S')} - {e1_times[-1].strftime('%H:%M:%S')} UTC")

    print("  Flight 2 (session 81):")
    e2_times, e2_volts = parse_ecu(ecu2_pattern)
    print(f"    {len(e2_volts)} samples, "
          f"{e2_times[0].strftime('%H:%M:%S')} - {e2_times[-1].strftime('%H:%M:%S')} UTC")

    # --- Three-way resampling ---
    print("\nResampling all three sources to common 2-second grid...")
    common1_t, g1_rs, v1_rs, e1_rs = resample_three(
        g1_times, g1_volts, vdl_f1_times, vdl_f1_volts, e1_times, e1_volts)
    common2_t, g2_rs, v2_rs, e2_rs = resample_three(
        g2_times, g2_volts, vdl_f2_times, vdl_f2_volts, e2_times, e2_volts)

    print(f"  Flight 1: {len(g1_rs)} paired samples ({len(g1_rs)*2/60:.1f} min)")
    print(f"  Flight 2: {len(g2_rs)} paired samples ({len(g2_rs)*2/60:.1f} min)")

    # --- Statistics ---
    pairs1 = print_three_way_stats(g1_rs, v1_rs, e1_rs, "Flight 1: KBOW -> KSPG")
    pairs2 = print_three_way_stats(g2_rs, v2_rs, e2_rs, "Flight 2: KSPG -> KBOW")

    all_g = np.concatenate([g1_rs, g2_rs])
    all_v = np.concatenate([v1_rs, v2_rs])
    all_e = np.concatenate([e1_rs, e2_rs])
    pairs_all = print_three_way_stats(all_g, all_v, all_e, "Combined (Both Flights)")

    # --- Save text report ---
    report_path = OUTPUT_DIR / "three_way_voltage_report.txt"
    # Capture stats output by re-running with string capture
    import io as _io
    old_stdout = sys.stdout
    sys.stdout = buf = _io.StringIO()
    print_three_way_stats(g1_rs, v1_rs, e1_rs, "Flight 1: KBOW -> KSPG")
    print_three_way_stats(g2_rs, v2_rs, e2_rs, "Flight 2: KSPG -> KBOW")
    print_three_way_stats(all_g, all_v, all_e, "Combined (Both Flights)")
    sys.stdout = old_stdout
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("Three-Source Voltage Correlation: G1000 vs VDL48 vs AE300 ECU\n")
        f.write("Aircraft: N238PS (Diamond DA40NG)  Date: 2026-02-08\n")
        f.write(buf.getvalue())
    print(f"\nSaved: {report_path}")

    # --- Plots ---
    print("\nGenerating plots...")

    plot_three_way_comparison(
        common1_t, g1_rs, v1_rs, e1_rs,
        "Flight 1: KBOW -> KSPG  (G1000 vs VDL48 vs ECU)",
        "three_way_flight1.png")

    plot_three_way_comparison(
        common2_t, g2_rs, v2_rs, e2_rs,
        "Flight 2: KSPG -> KBOW  (G1000 vs VDL48 vs ECU)",
        "three_way_flight2.png")

    plot_ecu_vs_vdl_scatter(e1_rs, v1_rs, e2_rs, v2_rs)

    plot_three_way_histograms(pairs1, pairs2)

    print(f"\nAll plots saved to: {OUTPUT_DIR}")
    print("\nAnalysis complete.")


if __name__ == "__main__":
    main()
