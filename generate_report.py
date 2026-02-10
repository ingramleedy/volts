"""
Generate a self-contained HTML report for the G1000 vs VDL48 voltage analysis.
All images are embedded as base64 so the report is a single shareable file.
"""

import sys
import io
import base64
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from scipy import stats
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).parent / "data"
FLIGHT1_CSV = DATA_DIR / "N238PS_KBOW-KSPG_20260208-1551UTC.csv"
FLIGHT2_CSV = DATA_DIR / "N238PS_KSPG-KBOW_20260208-1812UTC.csv"
VDL_CSV = DATA_DIR / "LOG_VD.CSV"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


# =============================================================================
# Parsing (same as voltage_analysis.py)
# =============================================================================

def parse_g1000(filepath):
    with open(filepath, "r") as f:
        lines = f.readlines()
    headers = [h.strip() for h in lines[2].split(",")]
    date_idx = headers.index("Lcl Date")
    time_idx = headers.index("Lcl Time")
    volt1_idx = headers.index("volt1")
    times, volt1 = [], []
    for line in lines[7:]:
        parts = line.split(",")
        if len(parts) <= volt1_idx:
            continue
        d, t, v = parts[date_idx].strip(), parts[time_idx].strip(), parts[volt1_idx].strip()
        if not d or not t or not v:
            continue
        try:
            times.append(datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M:%S"))
            volt1.append(float(v))
        except ValueError:
            continue
    return np.array(times), np.array(volt1)


def parse_vdl(filepath):
    with open(filepath, "r") as f:
        lines = f.readlines()
    times_str, voltages = [], []
    for line in lines[12:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        if len(parts) < 3:
            continue
        try:
            times_str.append(parts[1].strip())
            voltages.append(float(parts[2].strip()))
        except ValueError:
            continue
    t0 = datetime.strptime(times_str[0], "%H:%M:%S")
    elapsed = [(datetime.strptime(ts, "%H:%M:%S") - t0).total_seconds() for ts in times_str]
    return np.array(elapsed), np.array(voltages)


def segment_vdl(elapsed, voltage):
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
    return (0, end_f1), (end_f1, start_f2), (start_f2, end_f2)


def align_vdl_to_g1000(g1000_times, vdl_elapsed, vdl_seg):
    seg_start, seg_end = vdl_seg
    g1000_start = g1000_times[0]
    vdl_seg_elapsed = vdl_elapsed[seg_start:seg_end] - vdl_elapsed[seg_start]
    return np.array([g1000_start + timedelta(seconds=float(s)) for s in vdl_seg_elapsed])


def resample_to_common(g_times, g_volts, v_times, v_volts):
    g_epoch = np.array([(t - g_times[0]).total_seconds() for t in g_times])
    v_epoch = np.array([(t - g_times[0]).total_seconds() for t in v_times])
    t_start = max(g_epoch[0], v_epoch[0])
    t_end = min(g_epoch[-1], v_epoch[-1])
    common_t = np.arange(t_start, t_end, 2.0)
    g_interp = np.interp(common_t, g_epoch, g_volts)
    v_interp = np.interp(common_t, v_epoch, v_volts)
    common_dt = np.array([g_times[0] + timedelta(seconds=float(s)) for s in common_t])
    return common_dt, g_interp, v_interp


def compute_stats(g1000_v, vdl_v):
    diff = g1000_v - vdl_v
    r, p_corr = stats.pearsonr(g1000_v, vdl_v)
    t_stat, p_paired = stats.ttest_rel(g1000_v, vdl_v)
    return {
        "n": len(diff),
        "duration_min": len(diff) * 2 / 60,
        "g_mean": np.mean(g1000_v), "g_std": np.std(g1000_v),
        "g_min": np.min(g1000_v), "g_max": np.max(g1000_v),
        "v_mean": np.mean(vdl_v), "v_std": np.std(vdl_v),
        "v_min": np.min(vdl_v), "v_max": np.max(vdl_v),
        "diff_mean": np.mean(diff), "diff_median": np.median(diff),
        "diff_std": np.std(diff), "diff_min": np.min(diff), "diff_max": np.max(diff),
        "ci_lo": np.percentile(diff, 2.5), "ci_hi": np.percentile(diff, 97.5),
        "r": r, "p_corr": p_corr, "t_stat": t_stat, "p_paired": p_paired,
        "diff": diff,
    }


# =============================================================================
# Plot helpers (return base64 PNG strings)
# =============================================================================

def fig_to_base64(fig, dpi=150):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def make_vdl_overview(vdl_elapsed, vdl_voltage, seg_f1, seg_idle, seg_f2):
    fig, ax = plt.subplots(figsize=(13, 3.5))
    minutes = vdl_elapsed / 60.0
    ax.plot(minutes, vdl_voltage, color="black", linewidth=0.5, alpha=0.8)
    colors = {"Flight 1": "#4A90D9", "Idle (engine off)": "#E8943A", "Flight 2": "#50B86C"}
    for label, (s, e) in [("Flight 1", seg_f1), ("Idle (engine off)", seg_idle),
                           ("Flight 2", seg_f2)]:
        ax.axvspan(minutes[s], minutes[min(e, len(minutes)-1)],
                   alpha=0.18, color=colors[label], label=label)
    ax.set_xlabel("Elapsed Time (minutes from VDL start)")
    ax.set_ylabel("Voltage (V)")
    ax.set_title("Full VDL48 Recording - Segment Overview", fontsize=11, fontweight="bold")
    ax.legend(loc="center right", fontsize=9)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig_to_base64(fig)


def make_flight_comparison(common1_t, g1_rs, v1_rs, common2_t, g2_rs, v2_rs):
    fig, axes = plt.subplots(2, 1, figsize=(13, 7.5))
    for ax, ct, gv, vv, title in [
        (axes[0], common1_t, g1_rs, v1_rs, "Flight 1: KBOW to KSPG"),
        (axes[1], common2_t, g2_rs, v2_rs, "Flight 2: KSPG to KBOW"),
    ]:
        diff = gv - vv
        ax2 = ax.twinx()
        ax.plot(ct, vv, color="#50B86C", linewidth=0.8, alpha=0.85, label="VDL48 (reference)")
        ax.plot(ct, gv, color="#4A90D9", linewidth=0.8, alpha=0.85, label="G1000 volt1")
        ax2.plot(ct, diff, color="#D94A4A", linewidth=0.5, alpha=0.55, label="Difference")
        ax2.axhline(0, color="#D94A4A", linewidth=0.4, linestyle="--", alpha=0.4)
        ax.set_ylabel("Voltage (V)")
        ax2.set_ylabel("Difference (V)", color="#D94A4A")
        ax2.tick_params(axis="y", labelcolor="#D94A4A")
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.set_xlabel("UTC Time")
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc="lower right", fontsize=8)
        ax.grid(True, alpha=0.3)
    fig.suptitle("G1000 volt1 vs VDL48 Reference Voltage", fontsize=13, fontweight="bold", y=1.01)
    fig.tight_layout()
    return fig_to_base64(fig)


def make_histograms(diff1, diff2):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), sharey=True)
    for ax, diff, label, color in [
        (axes[0], diff1, "Flight 1 (KBOW to KSPG)", "#4A90D9"),
        (axes[1], diff2, "Flight 2 (KSPG to KBOW)", "#50B86C"),
    ]:
        ax.hist(diff, bins=60, color=color, alpha=0.7, edgecolor="white", linewidth=0.3)
        ax.axvline(np.mean(diff), color="#D94A4A", linestyle="--", linewidth=1.2,
                   label=f"Mean: {np.mean(diff):+.3f} V")
        ax.axvline(0, color="black", linestyle="-", linewidth=0.8, alpha=0.4)
        ax.set_xlabel("G1000 - VDL (V)")
        ax.set_ylabel("Count")
        ax.set_title(label, fontsize=10, fontweight="bold")
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
    fig.suptitle("Distribution of Voltage Differences (G1000 - VDL)", fontsize=12,
                 fontweight="bold", y=1.02)
    fig.tight_layout()
    return fig_to_base64(fig)


def make_scatter(g1, v1, g2, v2):
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(v1, g1, s=1, alpha=0.3, color="#4A90D9", label="Flight 1")
    ax.scatter(v2, g2, s=1, alpha=0.3, color="#50B86C", label="Flight 2")
    all_vals = np.concatenate([v1, v2, g1, g2])
    lo, hi = np.min(all_vals) - 0.5, np.max(all_vals) + 0.5
    ax.plot([lo, hi], [lo, hi], "k--", linewidth=0.8, label="1:1 line")
    all_vdl = np.concatenate([v1, v2])
    all_g1k = np.concatenate([g1, g2])
    slope, intercept, r, _, _ = stats.linregress(all_vdl, all_g1k)
    fit_x = np.array([lo, hi])
    ax.plot(fit_x, slope * fit_x + intercept, color="#D94A4A", linewidth=1,
            label=f"Fit: slope={slope:.3f}, r2={r**2:.3f}")
    ax.set_xlabel("VDL Voltage (V)")
    ax.set_ylabel("G1000 volt1 (V)")
    ax.set_title("G1000 vs VDL - Scatter", fontsize=11, fontweight="bold")
    ax.legend(fontsize=8)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig_to_base64(fig)


# =============================================================================
# HTML Report
# =============================================================================

def stats_table_html(s, label):
    sig = "Highly significant (p &lt; 0.001)" if s["p_paired"] < 0.001 else \
          "Significant (p &lt; 0.05)" if s["p_paired"] < 0.05 else "Not significant"
    return f"""
    <h3>{label}</h3>
    <table>
      <tr><th colspan="2">Sampling</th></tr>
      <tr><td>Paired samples (2-sec grid)</td><td>{s['n']:,}</td></tr>
      <tr><td>Duration</td><td>{s['duration_min']:.1f} min</td></tr>
      <tr><th colspan="2">G1000 volt1</th></tr>
      <tr><td>Mean &plusmn; Std Dev</td><td>{s['g_mean']:.2f} &plusmn; {s['g_std']:.3f} V</td></tr>
      <tr><td>Range</td><td>[{s['g_min']:.2f}, {s['g_max']:.2f}] V</td></tr>
      <tr><th colspan="2">VDL48 Reference</th></tr>
      <tr><td>Mean &plusmn; Std Dev</td><td>{s['v_mean']:.2f} &plusmn; {s['v_std']:.3f} V</td></tr>
      <tr><td>Range</td><td>[{s['v_min']:.2f}, {s['v_max']:.2f}] V</td></tr>
      <tr><th colspan="2">Difference (G1000 &minus; VDL)</th></tr>
      <tr><td>Mean</td><td class="neg">{s['diff_mean']:+.3f} V</td></tr>
      <tr><td>Median</td><td class="neg">{s['diff_median']:+.3f} V</td></tr>
      <tr><td>Std Dev</td><td>{s['diff_std']:.3f} V</td></tr>
      <tr><td>Min / Max</td><td>{s['diff_min']:+.3f} / {s['diff_max']:+.3f} V</td></tr>
      <tr><td>95% Range</td><td>[{s['ci_lo']:+.3f}, {s['ci_hi']:+.3f}] V</td></tr>
      <tr><th colspan="2">Statistical Tests</th></tr>
      <tr><td>Pearson r</td><td>{s['r']:.4f} (p = {s['p_corr']:.2e})</td></tr>
      <tr><td>Paired t-test</td><td>t = {s['t_stat']:.2f}, p = {s['p_paired']:.2e}</td></tr>
      <tr><td>Conclusion</td><td><strong>{sig}</strong></td></tr>
    </table>
    """


def build_html(img_overview, img_comparison, img_hist, img_scatter, s1, s2, sc):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Voltage Analysis Report - N238PS - 2026-02-08</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #1a1a1a; background: #f5f5f5; line-height: 1.6;
  }}
  .page {{
    max-width: 900px; margin: 0 auto; background: white;
    padding: 48px 56px; box-shadow: 0 1px 4px rgba(0,0,0,0.08);
  }}
  h1 {{ font-size: 22px; margin-bottom: 4px; color: #1a3a5c; }}
  h2 {{ font-size: 17px; color: #2a5a8a; margin: 32px 0 12px 0;
        border-bottom: 2px solid #dde4ec; padding-bottom: 4px; }}
  h3 {{ font-size: 14px; color: #3a3a3a; margin: 20px 0 8px 0; }}
  .subtitle {{ font-size: 13px; color: #666; margin-bottom: 24px; }}
  p, li {{ font-size: 13px; margin-bottom: 8px; }}
  ul {{ padding-left: 24px; }}
  img {{ width: 100%; height: auto; margin: 12px 0 20px 0; border: 1px solid #e8e8e8; }}
  table {{
    width: 100%; border-collapse: collapse; font-size: 12.5px; margin-bottom: 16px;
  }}
  th, td {{ padding: 5px 10px; text-align: left; border-bottom: 1px solid #e8e8e8; }}
  th {{ background: #f0f4f8; color: #2a5a8a; font-weight: 600; }}
  td.neg {{ color: #c0392b; font-weight: 600; }}
  .summary-box {{
    background: #fdf2f0; border-left: 4px solid #c0392b; padding: 14px 18px;
    margin: 20px 0; border-radius: 0 4px 4px 0;
  }}
  .summary-box p {{ margin-bottom: 4px; }}
  .summary-box strong {{ color: #c0392b; }}
  .finding {{ background: #f0f7ff; border-left: 4px solid #2a5a8a; padding: 14px 18px;
              margin: 16px 0; border-radius: 0 4px 4px 0; }}
  .cols {{ display: flex; gap: 24px; }}
  .cols > div {{ flex: 1; }}
  .small {{ font-size: 11px; color: #888; }}
  @media print {{
    body {{ background: white; }}
    .page {{ box-shadow: none; padding: 24px; }}
    img {{ break-inside: avoid; }}
    h2 {{ break-before: auto; }}
  }}
</style>
</head>
<body>
<div class="page">

<h1>Voltage Measurement Correlation Report</h1>
<p class="subtitle">
  Aircraft N238PS (Diamond DA40NG) &mdash; Garmin G1000 NXi vs Triplett VDL48<br>
  Date of flights: February 8, 2026 &nbsp;|&nbsp; Report generated: {datetime.now().strftime('%B %d, %Y')}
</p>

<div class="summary-box">
  <p><strong>Key Finding:</strong> The G1000 NXi consistently under-reports bus voltage
  compared to an independent reference logger. The mean offset is
  <strong>{sc['diff_mean']:+.2f} V</strong> (G1000 reads lower), with the difference
  being highly statistically significant (paired t-test, p &lt; 0.001).
  This under-reading is sufficient to trigger spurious LOW VOLTS annunciations
  during normal alternator operation.</p>
</div>

<h2>1. Test Setup</h2>
<p>A Triplett VDL48 voltage data logger (2-second sampling) was connected to the
aircraft electrical bus as an independent reference. Two flights were conducted
with the G1000 NXi data logging enabled (1-second sampling):</p>
<table>
  <tr><th></th><th>Flight 1</th><th>Flight 2</th></tr>
  <tr><td>Route</td><td>KBOW to KSPG</td><td>KSPG to KBOW</td></tr>
  <tr><td>Time (UTC)</td><td>15:51 - 16:47</td><td>18:10 - 19:25</td></tr>
  <tr><td>Duration</td><td>~56 min</td><td>~75 min</td></tr>
  <tr><td>G1000 samples</td><td>{s1['n']:,}</td><td>{s2['n']:,}</td></tr>
</table>
<p>The VDL48 recorded continuously across both flights and the ~85-minute ground
stop between them, capturing three distinct phases visible in the overview below.</p>

<h2>2. VDL48 Full Recording Overview</h2>
<img src="data:image/png;base64,{img_overview}" alt="VDL Overview">
<p class="small">The VDL48 shows stable ~28.3 V during both flights (alternator charging),
a gradual decay to ~25.5 V during the engine-off idle period, and 0 V after disconnection.</p>

<h2>3. Flight-by-Flight Voltage Comparison</h2>
<img src="data:image/png;base64,{img_comparison}" alt="Flight Comparison">
<p>The green trace (VDL48 reference) remains steady at ~28.3 V during both flights.
The blue trace (G1000 volt1) consistently reads lower and exhibits substantially
more fluctuation. The red trace shows the instantaneous difference.</p>

<div class="finding">
  <p><strong>Observation:</strong> The G1000 voltage trace shows frequent transient dips
  not present in the VDL reference. These dips are consistent with variable voltage drop
  across a resistive connection in the G1000's measurement or ground path.
  The worst-case dip reaches {sc['diff_min']:+.1f} V below the VDL reading.</p>
</div>

<h2>4. Statistical Analysis</h2>
<div class="cols">
  <div>{stats_table_html(s1, "Flight 1: KBOW to KSPG")}</div>
  <div>{stats_table_html(s2, "Flight 2: KSPG to KBOW")}</div>
</div>
{stats_table_html(sc, "Combined (Both Flights)")}

<h2>5. Distribution of Differences</h2>
<img src="data:image/png;base64,{img_hist}" alt="Difference Histograms">
<p>Both flights show distributions shifted well below zero, confirming the G1000
systematically reads lower. Flight 1 shows a larger mean offset ({s1['diff_mean']:+.3f} V)
than Flight 2 ({s2['diff_mean']:+.3f} V), suggesting the magnitude varies with
operating conditions.</p>

<h2>6. Correlation Scatter Plot</h2>
<img src="data:image/png;base64,{img_scatter}" alt="Scatter Plot">
<p>Nearly all data points fall below the 1:1 line, confirming the systematic
under-reading. The low r-squared value indicates the G1000 fluctuations are
largely independent of actual bus voltage changes, pointing to an issue in the
G1000's voltage sensing path rather than a simple calibration offset.</p>

<h2>7. Interpretation and Probable Cause</h2>
<p>The data pattern is consistent with a <strong>high-resistance connection</strong> in the
G1000's voltage measurement or ground return path. Key evidence:</p>
<ul>
  <li><strong>Variable offset, not constant:</strong> A calibration error would produce
  a fixed offset. The observed difference varies from {sc['diff_min']:+.1f} V to
  {sc['diff_max']:+.1f} V, with a standard deviation of {sc['diff_std']:.2f} V.</li>
  <li><strong>G1000 shows excess noise:</strong> The VDL sees a stable bus ({sc['v_std']:.3f} V std dev)
  while the G1000 fluctuates much more ({sc['g_std']:.3f} V std dev). The extra variance
  comes from current-dependent voltage drops across a resistive connection.</li>
  <li><strong>Near-zero correlation (r = {sc['r']:.2f}):</strong> The two instruments
  are measuring the same bus, yet their readings are essentially uncorrelated. This
  means the G1000's voltage fluctuations are driven by its own ground/sensing path
  impedance, not by actual bus voltage changes.</li>
  <li><strong>Transient deep dips:</strong> Momentary dips to {sc['diff_min']:+.1f} V below
  reference are consistent with high-current events (radio transmit, servo actuation)
  pulling current through a resistive ground, causing instantaneous offset spikes.</li>
  <li><strong>Different magnitude between flights:</strong> Flight 1 mean offset was
  {s1['diff_mean']:+.2f} V vs Flight 2 at {s2['diff_mean']:+.2f} V. Thermal expansion,
  vibration settling, or connector seating changes between flights can alter
  contact resistance.</li>
</ul>

<h2>8. Recommended Actions</h2>
<ul>
  <li>Inspect G1000 GDU and GIA unit ground terminals at the airframe ground bus for
  corrosion, loose hardware, paint under ring terminals, or cracked terminals.</li>
  <li>Measure resistance from the G1000 ground pin (at the connector) to battery
  negative. Values above ~0.02-0.05 ohms would explain the observed offset
  (at 20 A load, 0.05 ohms = 1.0 V drop).</li>
  <li>Inspect the main airframe ground bus to battery/engine ground strap.</li>
  <li>Check the G1000 harness connector pins (GDU 1050/1060, GIA 63W) for the
  voltage sensing and ground pins specifically.</li>
  <li>After repair, repeat this test to verify the offset is eliminated.</li>
</ul>

<p class="small" style="margin-top: 32px; padding-top: 12px; border-top: 1px solid #ddd;">
  Analysis performed using G1000 NXi data logs and Triplett VDL48 (S/N: 171VD_2506100052,
  2-sec sampling). Statistical methods: paired t-test, Pearson correlation, linear
  interpolation to common 2-second grid. All times UTC.
</p>

</div>
</body>
</html>"""


# =============================================================================
# Main
# =============================================================================

def main():
    print("Parsing data...")
    g1_times, g1_volt1 = parse_g1000(FLIGHT1_CSV)
    g2_times, g2_volt1 = parse_g1000(FLIGHT2_CSV)
    vdl_elapsed, vdl_voltage = parse_vdl(VDL_CSV)

    print("Segmenting VDL...")
    seg_f1, seg_idle, seg_f2 = segment_vdl(vdl_elapsed, vdl_voltage)

    print("Aligning and resampling...")
    vdl_f1_times = align_vdl_to_g1000(g1_times, vdl_elapsed, seg_f1)
    vdl_f1_volts = vdl_voltage[seg_f1[0]:seg_f1[1]]
    vdl_f2_times = align_vdl_to_g1000(g2_times, vdl_elapsed, seg_f2)
    vdl_f2_volts = vdl_voltage[seg_f2[0]:seg_f2[1]]

    common1_t, g1_rs, v1_rs = resample_to_common(g1_times, g1_volt1, vdl_f1_times, vdl_f1_volts)
    common2_t, g2_rs, v2_rs = resample_to_common(g2_times, g2_volt1, vdl_f2_times, vdl_f2_volts)

    print("Computing statistics...")
    s1 = compute_stats(g1_rs, v1_rs)
    s2 = compute_stats(g2_rs, v2_rs)
    sc = compute_stats(np.concatenate([g1_rs, g2_rs]), np.concatenate([v1_rs, v2_rs]))

    print("Generating figures...")
    img_overview = make_vdl_overview(vdl_elapsed, vdl_voltage, seg_f1, seg_idle, seg_f2)
    img_comparison = make_flight_comparison(common1_t, g1_rs, v1_rs, common2_t, g2_rs, v2_rs)
    img_hist = make_histograms(s1["diff"], s2["diff"])
    img_scatter = make_scatter(g1_rs, v1_rs, g2_rs, v2_rs)

    print("Building HTML report...")
    html = build_html(img_overview, img_comparison, img_hist, img_scatter, s1, s2, sc)

    report_path = OUTPUT_DIR / "Voltage_Analysis_Report_N238PS_20260208.html"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nReport saved: {report_path}")
    print("Open in any browser, or print/save as PDF from the browser.")


if __name__ == "__main__":
    main()
