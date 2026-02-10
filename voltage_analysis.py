"""
Voltage Correlation Analysis: G1000 NXi vs Triplett VDL48
=========================================================
Compares voltage readings from the Garmin G1000 NXi avionics (volt1 bus)
against an independent Triplett VDL48 voltage data logger for two flights
of Diamond DA40NG N238PS on 2026-02-08.

Flight 1: KBOW -> KSPG (15:51 - 16:47 UTC)
Flight 2: KSPG -> KBOW (18:10 - 19:25 UTC)
"""

import sys
import io
import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")  # non-interactive backend for saving figures
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from scipy import stats
from pathlib import Path

# Fix Windows console encoding for Unicode characters (e.g. minus signs from numpy)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).parent / "data"

# --- File paths ---
FLIGHT1_CSV = DATA_DIR / "N238PS_KBOW-KSPG_20260208-1551UTC.csv"
FLIGHT2_CSV = DATA_DIR / "N238PS_KSPG-KBOW_20260208-1812UTC.csv"
VDL_CSV = DATA_DIR / "LOG_VD.CSV"

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


# =============================================================================
# Parsing
# =============================================================================

def parse_g1000(filepath):
    """Parse a G1000 NXi data log CSV, returning timestamps and volt1 values.

    The G1000 CSV has 3 header rows (airframe info, units, column names)
    followed by 4 initialization rows, then data starting at row 8.
    We skip rows where volt1 is blank (avionics still initializing).
    """
    times = []
    volt1 = []

    with open(filepath, "r") as f:
        lines = f.readlines()

    # Row 3 (index 2) has the column headers
    headers = [h.strip() for h in lines[2].split(",")]
    date_idx = headers.index("Lcl Date")
    time_idx = headers.index("Lcl Time")
    volt1_idx = headers.index("volt1")

    # Data rows start at line 8 (index 7)
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
    """Parse the Triplett VDL48 CSV, returning elapsed seconds and voltage.

    The VDL has 10 header lines, a blank line, then a column header line,
    with data starting at line 13.  The date/time stamped by the logger is
    incorrect, but the 2-second sampling period is reliable, so we compute
    elapsed seconds from the first sample.
    """
    times_str = []
    voltages = []

    with open(filepath, "r") as f:
        lines = f.readlines()

    for line in lines[12:]:  # data starts at line 13 (index 12)
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

    # Build elapsed seconds array from time strings
    t0 = datetime.strptime(times_str[0], "%H:%M:%S")
    elapsed = []
    for ts in times_str:
        dt = datetime.strptime(ts, "%H:%M:%S")
        elapsed.append((dt - t0).total_seconds())

    return np.array(elapsed), np.array(voltages)


# =============================================================================
# VDL Segmentation
# =============================================================================

def segment_vdl(elapsed, voltage):
    """Segment VDL data into Flight 1, Idle, and Flight 2.

    Strategy:
      - During flight the alternator keeps voltage high (~28 V).
      - During idle (engine off) voltage slowly decays (~26 V dropping).
      - After disconnection voltage reads 0.

    We use a threshold-based approach:
      1. Find where voltage first drops below 27 V for a sustained period
         -> end of flight 1 / start of idle.
      2. Find where voltage rises back above 27 V after the idle period
         -> end of idle / start of flight 2.
      3. Find where voltage drops to near 0
         -> end of flight 2 / logger disconnected.
    """
    FLIGHT_THRESHOLD = 27.0  # volts  - below this is not alternator-charging
    ZERO_THRESHOLD = 1.0     # volts  - below this means disconnected
    WINDOW = 30              # samples (~60 sec) for sustained detection

    # Remove trailing zeros (disconnected)
    last_nonzero = len(voltage) - 1
    while last_nonzero > 0 and voltage[last_nonzero] < ZERO_THRESHOLD:
        last_nonzero -= 1

    # Find end of flight 1: first sustained period below threshold
    end_f1 = None
    for i in range(WINDOW, last_nonzero):
        if all(voltage[i:i + WINDOW] < FLIGHT_THRESHOLD):
            end_f1 = i
            break

    # Find start of flight 2: after idle, first sustained period above threshold
    start_f2 = None
    if end_f1 is not None:
        for i in range(end_f1 + WINDOW, last_nonzero):
            if all(voltage[i:i + WINDOW] > FLIGHT_THRESHOLD):
                start_f2 = i
                break

    end_f2 = last_nonzero + 1  # up to last non-zero reading

    if end_f1 is None or start_f2 is None:
        raise RuntimeError("Could not segment VDL data into flight phases.")

    seg_flight1 = (0, end_f1)
    seg_idle = (end_f1, start_f2)
    seg_flight2 = (start_f2, end_f2)

    return seg_flight1, seg_idle, seg_flight2


# =============================================================================
# Time Alignment
# =============================================================================

def align_vdl_to_g1000(g1000_times, vdl_elapsed, vdl_seg):
    """Create a datetime array for a VDL segment aligned to G1000 timestamps.

    We match the start of the VDL segment to the start of the G1000 flight,
    then space VDL samples at their original 2-second intervals.
    """
    seg_start, seg_end = vdl_seg
    g1000_start = g1000_times[0]
    vdl_seg_elapsed = vdl_elapsed[seg_start:seg_end] - vdl_elapsed[seg_start]
    aligned_times = np.array([
        g1000_start + timedelta(seconds=float(s)) for s in vdl_seg_elapsed
    ])
    return aligned_times


def resample_to_common(g_times, g_volts, v_times, v_volts):
    """Resample both series to a common 2-second grid for direct comparison.

    We use the overlapping time range and linearly interpolate both signals
    onto a shared grid.
    """
    # Convert to seconds-from-epoch for interpolation
    g_epoch = np.array([(t - g_times[0]).total_seconds() for t in g_times])
    v_epoch = np.array([(t - g_times[0]).total_seconds() for t in v_times])

    # Overlapping window
    t_start = max(g_epoch[0], v_epoch[0])
    t_end = min(g_epoch[-1], v_epoch[-1])
    common_t = np.arange(t_start, t_end, 2.0)  # 2-second grid

    g_interp = np.interp(common_t, g_epoch, g_volts)
    v_interp = np.interp(common_t, v_epoch, v_volts)

    common_dt = np.array([
        g_times[0] + timedelta(seconds=float(s)) for s in common_t
    ])
    return common_dt, g_interp, v_interp


# =============================================================================
# Statistics
# =============================================================================

def compute_stats(g1000_v, vdl_v, label):
    """Compute and print correlation statistics between G1000 and VDL."""
    diff = g1000_v - vdl_v  # G1000 minus VDL (expect negative = G1000 reads low)

    r, p_corr = stats.pearsonr(g1000_v, vdl_v)
    t_stat, p_paired = stats.ttest_rel(g1000_v, vdl_v)

    report = []
    report.append(f"\n{'='*65}")
    report.append(f"  {label}")
    report.append(f"{'='*65}")
    report.append(f"  Samples (paired, 2-sec grid):  {len(diff)}")
    report.append(f"  Duration:                      {len(diff)*2/60:.1f} min")
    report.append(f"")
    report.append(f"  G1000 volt1   - mean: {np.mean(g1000_v):6.2f} V   "
                  f"std: {np.std(g1000_v):.3f} V   "
                  f"range: [{np.min(g1000_v):.2f}, {np.max(g1000_v):.2f}]")
    report.append(f"  VDL voltage   - mean: {np.mean(vdl_v):6.2f} V   "
                  f"std: {np.std(vdl_v):.3f} V   "
                  f"range: [{np.min(vdl_v):.2f}, {np.max(vdl_v):.2f}]")
    report.append(f"")
    report.append(f"  Difference (G1000 − VDL):")
    report.append(f"    Mean:    {np.mean(diff):+.3f} V")
    report.append(f"    Median:  {np.median(diff):+.3f} V")
    report.append(f"    Std Dev: {np.std(diff):.3f} V")
    report.append(f"    Min:     {np.min(diff):+.3f} V")
    report.append(f"    Max:     {np.max(diff):+.3f} V")
    report.append(f"    95% CI:  [{np.percentile(diff, 2.5):+.3f}, "
                  f"{np.percentile(diff, 97.5):+.3f}] V")
    report.append(f"")
    report.append(f"  Pearson r:         {r:.4f}  (p = {p_corr:.2e})")
    report.append(f"  Paired t-test:     t = {t_stat:.2f},  p = {p_paired:.2e}")
    if p_paired < 0.001:
        report.append(f"  -> Highly significant difference (p < 0.001)")
    elif p_paired < 0.05:
        report.append(f"  -> Statistically significant difference (p < 0.05)")
    else:
        report.append(f"  -> No significant difference at α = 0.05")

    text = "\n".join(report)
    print(text)
    return text, diff


# =============================================================================
# Plotting
# =============================================================================

def plot_flight_comparison(ax, common_dt, g_volts, v_volts, diff, title):
    """Plot G1000 vs VDL voltage and their difference for one flight."""
    ax_diff = ax.twinx()

    ax.plot(common_dt, v_volts, color="tab:green", linewidth=0.8,
            alpha=0.85, label="VDL (reference)")
    ax.plot(common_dt, g_volts, color="tab:blue", linewidth=0.8,
            alpha=0.85, label="G1000 volt1")
    ax_diff.plot(common_dt, diff, color="tab:red", linewidth=0.6,
                 alpha=0.6, label="Difference (G1000 − VDL)")
    ax_diff.axhline(0, color="tab:red", linewidth=0.4, linestyle="--", alpha=0.4)

    ax.set_ylabel("Voltage (V)")
    ax_diff.set_ylabel("Difference (V)", color="tab:red")
    ax_diff.tick_params(axis="y", labelcolor="tab:red")
    ax.set_title(title)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.set_xlabel("UTC Time")

    # Combined legend
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax_diff.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc="lower right",
              fontsize=8)
    ax.grid(True, alpha=0.3)


def plot_full_vdl_overview(vdl_elapsed, vdl_voltage, seg_f1, seg_idle, seg_f2):
    """Plot the full VDL recording with segments shaded."""
    fig, ax = plt.subplots(figsize=(14, 4))
    minutes = vdl_elapsed / 60.0

    ax.plot(minutes, vdl_voltage, color="black", linewidth=0.5, alpha=0.8)

    colors = {"Flight 1": "tab:blue", "Idle (engine off)": "tab:orange",
              "Flight 2": "tab:green"}
    for label, (s, e) in [("Flight 1", seg_f1), ("Idle (engine off)", seg_idle),
                           ("Flight 2", seg_f2)]:
        ax.axvspan(minutes[s], minutes[min(e, len(minutes) - 1)],
                   alpha=0.15, color=colors[label], label=label)

    ax.set_xlabel("Elapsed Time (minutes from VDL start)")
    ax.set_ylabel("Voltage (V)")
    ax.set_title("Full VDL48 Recording  - Segment Overview")
    ax.legend(loc="center right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "vdl_overview.png", dpi=150)
    print(f"\nSaved: {OUTPUT_DIR / 'vdl_overview.png'}")
    return fig


def plot_difference_histograms(diff1, diff2):
    """Histogram of voltage differences for both flights."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), sharey=True)

    for ax, diff, label, color in [
        (axes[0], diff1, "Flight 1 (KBOW->KSPG)", "tab:blue"),
        (axes[1], diff2, "Flight 2 (KSPG->KBOW)", "tab:green"),
    ]:
        ax.hist(diff, bins=60, color=color, alpha=0.7, edgecolor="white",
                linewidth=0.3)
        ax.axvline(np.mean(diff), color="red", linestyle="--", linewidth=1.2,
                   label=f"Mean: {np.mean(diff):+.3f} V")
        ax.axvline(0, color="black", linestyle="-", linewidth=0.8, alpha=0.4)
        ax.set_xlabel("G1000 − VDL (V)")
        ax.set_ylabel("Count")
        ax.set_title(label)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)

    fig.suptitle("Distribution of Voltage Differences (G1000 − VDL)", y=1.02)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "difference_histograms.png", dpi=150,
                bbox_inches="tight")
    print(f"Saved: {OUTPUT_DIR / 'difference_histograms.png'}")
    return fig


def plot_scatter(g1, v1, g2, v2):
    """Scatter plot: G1000 vs VDL with 1:1 reference line."""
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(v1, g1, s=1, alpha=0.3, color="tab:blue", label="Flight 1")
    ax.scatter(v2, g2, s=1, alpha=0.3, color="tab:green", label="Flight 2")

    all_v = np.concatenate([v1, v2, g1, g2])
    lo, hi = np.min(all_v) - 0.5, np.max(all_v) + 0.5
    ax.plot([lo, hi], [lo, hi], "k--", linewidth=0.8, label="1:1 line")

    # Linear fit across both flights
    all_vdl = np.concatenate([v1, v2])
    all_g1k = np.concatenate([g1, g2])
    slope, intercept, r, _, _ = stats.linregress(all_vdl, all_g1k)
    fit_x = np.array([lo, hi])
    ax.plot(fit_x, slope * fit_x + intercept, "r-", linewidth=1,
            label=f"Fit: G1000 = {slope:.3f}×VDL {intercept:+.2f}  (r²={r**2:.3f})")

    ax.set_xlabel("VDL Voltage (V)")
    ax.set_ylabel("G1000 volt1 (V)")
    ax.set_title("G1000 vs VDL  - Scatter")
    ax.legend(fontsize=8)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "scatter.png", dpi=150)
    print(f"Saved: {OUTPUT_DIR / 'scatter.png'}")
    return fig


# =============================================================================
# Main
# =============================================================================

def main():
    print("Voltage Correlation Analysis: G1000 NXi vs Triplett VDL48")
    print("Aircraft: N238PS (Diamond DA40NG)  Date: 2026-02-08")
    print("=" * 65)

    # --- Parse all data ---
    print("\nParsing G1000 Flight 1 (KBOW -> KSPG)...")
    g1_times, g1_volt1 = parse_g1000(FLIGHT1_CSV)
    print(f"  {len(g1_volt1)} samples, "
          f"{g1_times[0].strftime('%H:%M:%S')} - {g1_times[-1].strftime('%H:%M:%S')} UTC")

    print("Parsing G1000 Flight 2 (KSPG -> KBOW)...")
    g2_times, g2_volt1 = parse_g1000(FLIGHT2_CSV)
    print(f"  {len(g2_volt1)} samples, "
          f"{g2_times[0].strftime('%H:%M:%S')} - {g2_times[-1].strftime('%H:%M:%S')} UTC")

    print("Parsing VDL48 log...")
    vdl_elapsed, vdl_voltage = parse_vdl(VDL_CSV)
    print(f"  {len(vdl_voltage)} samples over "
          f"{vdl_elapsed[-1]/60:.1f} min ({vdl_elapsed[-1]/3600:.2f} hr)")

    # --- Segment VDL ---
    print("\nSegmenting VDL data into flight phases...")
    seg_f1, seg_idle, seg_f2 = segment_vdl(vdl_elapsed, vdl_voltage)
    for label, (s, e) in [("Flight 1", seg_f1), ("Idle", seg_idle),
                           ("Flight 2", seg_f2)]:
        dur = (vdl_elapsed[min(e, len(vdl_elapsed)-1)] - vdl_elapsed[s]) / 60
        mean_v = np.mean(vdl_voltage[s:e])
        print(f"  {label}: indices {s}–{e} ({dur:.1f} min, mean {mean_v:.2f} V)")

    # --- Align VDL segments to G1000 timestamps ---
    print("\nAligning VDL segments to G1000 flight times...")
    vdl_f1_times = align_vdl_to_g1000(g1_times, vdl_elapsed, seg_f1)
    vdl_f1_volts = vdl_voltage[seg_f1[0]:seg_f1[1]]

    vdl_f2_times = align_vdl_to_g1000(g2_times, vdl_elapsed, seg_f2)
    vdl_f2_volts = vdl_voltage[seg_f2[0]:seg_f2[1]]

    # --- Resample to common grid ---
    print("Resampling to common 2-second grid...")
    common1_t, g1_rs, v1_rs = resample_to_common(
        g1_times, g1_volt1, vdl_f1_times, vdl_f1_volts)
    common2_t, g2_rs, v2_rs = resample_to_common(
        g2_times, g2_volt1, vdl_f2_times, vdl_f2_volts)

    # --- Statistics ---
    report1, diff1 = compute_stats(g1_rs, v1_rs, "Flight 1: KBOW -> KSPG")
    report2, diff2 = compute_stats(g2_rs, v2_rs, "Flight 2: KSPG -> KBOW")

    # Combined stats
    all_g = np.concatenate([g1_rs, g2_rs])
    all_v = np.concatenate([v1_rs, v2_rs])
    report_all, diff_all = compute_stats(all_g, all_v, "Combined (Both Flights)")

    # --- Save text report ---
    report_path = OUTPUT_DIR / "voltage_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("Voltage Correlation Analysis: G1000 NXi vs Triplett VDL48\n")
        f.write("Aircraft: N238PS (Diamond DA40NG)  Date: 2026-02-08\n")
        f.write(report1 + "\n")
        f.write(report2 + "\n")
        f.write(report_all + "\n")
    print(f"\nSaved: {report_path}")

    # --- Plots ---
    print("\nGenerating plots...")

    # 1. Full VDL overview
    plot_full_vdl_overview(vdl_elapsed, vdl_voltage, seg_f1, seg_idle, seg_f2)

    # 2. Side-by-side flight comparisons
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=False)
    plot_flight_comparison(axes[0], common1_t, g1_rs, v1_rs,
                           g1_rs - v1_rs, "Flight 1: KBOW -> KSPG")
    plot_flight_comparison(axes[1], common2_t, g2_rs, v2_rs,
                           g2_rs - v2_rs, "Flight 2: KSPG -> KBOW")
    fig.suptitle("G1000 volt1 vs VDL48 Reference Voltage", fontsize=13, y=1.01)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "flight_comparison.png", dpi=150,
                bbox_inches="tight")
    print(f"Saved: {OUTPUT_DIR / 'flight_comparison.png'}")

    # 3. Difference histograms
    plot_difference_histograms(diff1, diff2)

    # 4. Scatter plot with regression
    plot_scatter(g1_rs, v1_rs, g2_rs, v2_rs)

    print("\nAll plots saved to:", OUTPUT_DIR)
    print("\nAnalysis complete.")


if __name__ == "__main__":
    main()
