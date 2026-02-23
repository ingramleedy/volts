#!/usr/bin/env python3
"""Three-period G1000-ECU differential analysis with Pettitt change-point test."""

import sys
import io
import re
import csv
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from scipy import stats

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ECU_DIR = Path(__file__).parent / ".." / "AustroView" / "Data" / "Parsed"
SOURCE_DIR = Path(__file__).parent / "data" / "source"


def parse_ecu_sessions(ecu_dir):
    files = sorted(ecu_dir.glob("*_session*_2*.csv"))
    sessions = []
    seen_dates = set()
    for fpath in files:
        m = re.search(r"session(\d+)_(\d{8})_(\d{6})\.csv$", fpath.name)
        if not m:
            continue
        sess_date = datetime.strptime(m.group(2) + m.group(3), "%Y%m%d%H%M%S")
        date_key = sess_date.strftime("%Y%m%d%H%M%S")
        if date_key in seen_dates:
            continue
        seen_dates.add(date_key)
        voltages = []
        with open(fpath, "r") as f:
            reader = csv.DictReader(f)
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
            "date": sess_date,
            "mean": float(np.mean(cruise)),
            "std": float(np.std(cruise)),
        })
    sessions.sort(key=lambda s: s["date"])
    return sessions


def parse_g1000_voltage(fpath):
    with open(fpath, "r", errors="replace") as f:
        lines = f.readlines()
    if len(lines) < 8:
        return None, []
    data_lines = lines[7:]
    voltages = []
    flight_date = None
    for line in data_lines:
        parts = line.strip().split(",")
        if len(parts) < 21:
            continue
        try:
            v = float(parts[19])
            if v > 0:
                voltages.append(v)
            if flight_date is None and len(parts[0].strip()) > 0:
                flight_date = datetime.strptime(parts[0].strip(), "%Y-%m-%d")
        except (ValueError, IndexError):
            continue
    return flight_date, voltages


def pettitt_test(x):
    n = len(x)
    U = np.zeros(n, dtype=float)
    for t in range(n):
        for i in range(t + 1):
            for j in range(t + 1, n):
                U[t] += np.sign(x[i] - x[j])
    cp = np.argmax(np.abs(U))
    K = np.abs(U[cp])
    p = 2.0 * np.exp(-6.0 * K**2 / (n**3 + n**2))
    return cp, K, p, U


def main():
    # Parse ECU sessions
    sessions = parse_ecu_sessions(ECU_DIR)
    print(f"Parsed {len(sessions)} valid ECU sessions")
    print(f"Date range: {sessions[0]['date'].strftime('%Y-%m-%d')} to "
          f"{sessions[-1]['date'].strftime('%Y-%m-%d')}")

    # Parse G1000 flights
    csv_files = sorted(SOURCE_DIR.glob("*.csv"))
    flights = []
    for fpath in csv_files:
        flight_date, voltages = parse_g1000_voltage(fpath)
        if len(voltages) < 30 or flight_date is None:
            continue
        varr = np.array(voltages)
        cruise = varr[varr > 25.0]
        if len(cruise) < 30:
            cruise = varr
        flights.append({
            "date": flight_date,
            "mean": float(np.mean(cruise)),
            "std": float(np.std(cruise)),
        })
    flights.sort(key=lambda f: f["date"])
    print(f"Parsed {len(flights)} valid G1000 flights")

    # Match G1000 to ECU by same day
    matched = []
    for flight in flights:
        fd = flight["date"].date()
        best_ecu = None
        best_diff = timedelta(days=999)
        for sess in sessions:
            diff = abs(sess["date"].date() - fd)
            if diff < best_diff:
                best_diff = diff
                best_ecu = sess
        if best_diff <= timedelta(days=0):
            matched.append({
                "date": flight["date"],
                "g1000_mean": flight["mean"],
                "g1000_std": flight["std"],
                "ecu_mean": best_ecu["mean"],
                "ecu_std": best_ecu["std"],
                "diff": flight["mean"] - best_ecu["mean"],
            })
    matched.sort(key=lambda m: m["date"])
    print(f"Matched {len(matched)} G1000-ECU pairs (same day)")

    # === ECU Pettitt Test ===
    ecu_means = np.array([s["mean"] for s in sessions])
    print(f"\n{'=' * 70}")
    print("ECU PETTITT CHANGE-POINT TEST")
    print(f"{'=' * 70}")
    cp_idx, K_stat, p_val, _ = pettitt_test(ecu_means)
    cp_date = sessions[cp_idx]["date"]
    before = ecu_means[:cp_idx + 1]
    after = ecu_means[cp_idx + 1:]
    print(f"Change-point: {cp_date.strftime('%Y-%m-%d')} "
          f"(session #{cp_idx + 1} of {len(sessions)})")
    print(f"K-statistic: {K_stat:.0f}, p-value: {p_val:.2e}")
    print(f"Significant: {'YES' if p_val < 0.05 else 'NO'}")
    print(f"Before ({len(before)} sessions): {np.mean(before):.3f}V")
    print(f"After ({len(after)} sessions):  {np.mean(after):.3f}V")
    print(f"Change: {np.mean(after) - np.mean(before):+.3f}V")

    # === Three-period analysis ===
    rr1_date = datetime(2024, 2, 28)
    rr2_remove = datetime(2025, 4, 30)
    rr2_install = datetime(2025, 7, 1)

    period1 = [m for m in matched if m["date"] < rr1_date]
    period2 = [m for m in matched if rr1_date <= m["date"] < rr2_remove]
    period3 = [m for m in matched if m["date"] >= rr2_install]

    print(f"\n{'=' * 70}")
    print("THREE-PERIOD ANALYSIS: G1000-ECU DIFFERENTIAL")
    print("Eliminates shared factors (bus voltage, battery bolt, 24008A4N)")
    print("Isolates GEA-specific changes only")
    print(f"{'=' * 70}")

    period_data = {}
    for label, period, desc in [
        ("Period 1", period1,
         f"Before R&R #1 (before {rr1_date.strftime('%Y-%m-%d')})"),
        ("Period 2", period2,
         f"Between R&Rs ({rr1_date.strftime('%Y-%m-%d')} to "
         f"{rr2_remove.strftime('%Y-%m-%d')})"),
        ("Period 3", period3,
         f"After R&R #2 (after {rr2_install.strftime('%Y-%m-%d')})"),
    ]:
        if not period:
            print(f"\n{label}: {desc}")
            print("  No matched pairs")
            continue
        diffs = [m["diff"] for m in period]
        g_means = [m["g1000_mean"] for m in period]
        e_means = [m["ecu_mean"] for m in period]
        g_stds = [m["g1000_std"] for m in period]
        e_stds = [m["ecu_std"] for m in period]
        period_data[label] = diffs
        print(f"\n{label}: {desc}")
        print(f"  Matched pairs: {len(period)}")
        print(f"  Date range: {period[0]['date'].strftime('%Y-%m-%d')} to "
              f"{period[-1]['date'].strftime('%Y-%m-%d')}")
        print(f"  G1000 mean:     {np.mean(g_means):.3f}V  "
              f"(noise: {np.mean(g_stds):.3f}V)")
        print(f"  ECU mean:       {np.mean(e_means):.3f}V  "
              f"(noise: {np.mean(e_stds):.3f}V)")
        print(f"  G1000 - ECU:    {np.mean(diffs):.3f}V  "
              f"(std: {np.std(diffs):.3f}V)")
        print(f"  Range of diffs: {min(diffs):.3f}V to {max(diffs):.3f}V")

    # Step sizes
    print(f"\n{'=' * 70}")
    print("STEP CHANGES (GEA-specific degradation at each R&R)")
    print(f"{'=' * 70}")

    if "Period 1" in period_data and "Period 2" in period_data:
        d1 = period_data["Period 1"]
        d2 = period_data["Period 2"]
        step = np.mean(d2) - np.mean(d1)
        t, p = stats.ttest_ind(d1, d2, equal_var=False)
        print(f"\nR&R #1 (Feb 2024) step:  {step:+.3f}V  "
              f"(Welch t={t:.2f}, p={p:.2e})")
        print(f"  G1000-ECU gap: {np.mean(d1):.3f}V -> {np.mean(d2):.3f}V")

    if "Period 2" in period_data and "Period 3" in period_data:
        d2 = period_data["Period 2"]
        d3 = period_data["Period 3"]
        step = np.mean(d3) - np.mean(d2)
        t, p = stats.ttest_ind(d2, d3, equal_var=False)
        print(f"\nR&R #2 (Jul 2025) step:  {step:+.3f}V  "
              f"(Welch t={t:.2f}, p={p:.2e})")
        print(f"  G1000-ECU gap: {np.mean(d2):.3f}V -> {np.mean(d3):.3f}V")

    if "Period 1" in period_data and "Period 3" in period_data:
        d1 = period_data["Period 1"]
        d3 = period_data["Period 3"]
        step = np.mean(d3) - np.mean(d1)
        t, p = stats.ttest_ind(d1, d3, equal_var=False)
        print(f"\nTotal degradation:       {step:+.3f}V  "
              f"(Welch t={t:.2f}, p={p:.2e})")
        print(f"  G1000-ECU gap: {np.mean(d1):.3f}V -> {np.mean(d3):.3f}V")

    # Noise comparison
    print(f"\n{'=' * 70}")
    print("NOISE COMPARISON (G1000 vs ECU per period)")
    print(f"{'=' * 70}")
    for label, period in [("Period 1", period1), ("Period 2", period2),
                          ("Period 3", period3)]:
        if not period:
            continue
        g_noise = np.mean([m["g1000_std"] for m in period])
        e_noise = np.mean([m["ecu_std"] for m in period])
        print(f"  {label}: G1000 noise={g_noise:.3f}V  ECU noise={e_noise:.3f}V  "
              f"G1000 excess={g_noise - e_noise:+.3f}V")

    # ECU three-period absolute values
    print(f"\n{'=' * 70}")
    print("ECU ABSOLUTE VALUES (three periods)")
    print(f"{'=' * 70}")
    ecu_p1 = [s for s in sessions if s["date"] < rr1_date]
    ecu_p2 = [s for s in sessions if rr1_date <= s["date"] < rr2_remove]
    ecu_p3 = [s for s in sessions if s["date"] >= rr2_install]
    for label, ep in [("Before R&R #1", ecu_p1), ("Between R&Rs", ecu_p2),
                      ("After R&R #2", ecu_p3)]:
        if ep:
            emeans = [s["mean"] for s in ep]
            estds = [s["std"] for s in ep]
            print(f"  {label}: {len(ep)} sessions, "
                  f"mean={np.mean(emeans):.3f}V, noise={np.mean(estds):.3f}V")

    # G1000 three-period absolute values
    print(f"\n{'=' * 70}")
    print("G1000 ABSOLUTE VALUES (three periods)")
    print(f"{'=' * 70}")
    g_p1 = [f for f in flights if f["date"] < rr1_date]
    g_p2 = [f for f in flights if rr1_date <= f["date"] < rr2_remove]
    g_p3 = [f for f in flights if f["date"] >= rr2_install]
    for label, gp in [("Before R&R #1", g_p1), ("Between R&Rs", g_p2),
                      ("After R&R #2", g_p3)]:
        if gp:
            gmeans = [f["mean"] for f in gp]
            gstds = [f["std"] for f in gp]
            print(f"  {label}: {len(gp)} flights, "
                  f"mean={np.mean(gmeans):.3f}V, noise={np.mean(gstds):.3f}V")

    # ================================================================
    # PLOTS
    # ================================================================
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.patches import FancyArrowPatch

    OUTPUT_DIR = Path(__file__).parent / "output"
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Maintenance events for annotation
    maint_events = [
        (datetime(2024, 2, 28), "R&R #1\n(oil leak)", "red"),
        (datetime(2024, 3, 27), "Alt #2\nreplaced", "orange"),
        (datetime(2024, 4, 15), "VR\nreplaced", "orange"),
        (datetime(2024, 6, 30), "VR #2 +\nwire repair", "orange"),
        (datetime(2024, 7, 26), "Annual\n(HSDB fix)", "purple"),
        (datetime(2025, 2, 21), "Main alt +\nVR #3", "orange"),
        (datetime(2025, 4, 30), "Engine\nremoved", "red"),
        (datetime(2025, 7, 1), "R&R #2\n(pistons)", "red"),
    ]

    # --- Plot 1: G1000 vs ECU absolute voltages with three periods ---
    fig, axes = plt.subplots(3, 1, figsize=(14, 14), sharex=True)
    fig.suptitle("N238PS — G1000 vs ECU: Three-Period Differential Analysis",
                 fontsize=14, fontweight="bold")

    # Panel 1: Absolute voltages
    ax1 = axes[0]
    all_g_dates = [f["date"] for f in flights]
    all_g_means = [f["mean"] for f in flights]
    all_e_dates = [s["date"] for s in sessions]
    all_e_means = [s["mean"] for s in sessions]

    ax1.plot(all_g_dates, all_g_means, "b.", markersize=4, alpha=0.6,
             label="G1000 volt1 (cruise mean)")
    ax1.plot(all_e_dates, all_e_means, "g^", markersize=4, alpha=0.5,
             label="ECU Battery V (cruise mean)")

    # Period mean lines
    for gp, color, label_txt in [
        (g_p1, "blue", "G1000"), (g_p2, "blue", None), (g_p3, "blue", None)
    ]:
        if gp:
            d0, d1x = gp[0]["date"], gp[-1]["date"]
            m = np.mean([f["mean"] for f in gp])
            ax1.hlines(m, d0, d1x, colors=color, linewidth=2, alpha=0.7)
    for ep, color in [(ecu_p1, "green"), (ecu_p2, "green"), (ecu_p3, "green")]:
        if ep:
            d0, d1x = ep[0]["date"], ep[-1]["date"]
            m = np.mean([s["mean"] for s in ep])
            ax1.hlines(m, d0, d1x, colors=color, linewidth=2, alpha=0.7)

    # R&R markers
    for md, mlabel, mcolor in maint_events:
        if "R&R" in mlabel or "removed" in mlabel:
            ax1.axvline(x=md, color=mcolor, linestyle="--", linewidth=1.5,
                        alpha=0.7)

    ax1.axhline(y=28.0, color="gray", linestyle=":", alpha=0.3)
    ax1.set_ylabel("Mean Cruise Voltage (V)")
    ax1.set_title("Absolute Voltages — G1000 drops while ECU rises "
                  "(alternator/VR replacements)")
    ax1.legend(loc="lower left", fontsize=8)
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(25.5, 29.5)

    # Panel 2: G1000 - ECU differential
    ax2 = axes[1]
    m_dates = [m["date"] for m in matched]
    m_diffs = [m["diff"] for m in matched]

    # Color by period
    for period, color, label_txt in [
        (period1, "green", f"Before R&R #1 ({np.mean(period_data.get('Period 1', [0])):.2f}V)"),
        (period2, "orange", f"Between R&Rs ({np.mean(period_data.get('Period 2', [0])):.2f}V)"),
        (period3, "red", f"After R&R #2 ({np.mean(period_data.get('Period 3', [0])):.2f}V)"),
    ]:
        if period:
            pd = [m["date"] for m in period]
            pv = [m["diff"] for m in period]
            ax2.plot(pd, pv, "o", color=color, markersize=5, alpha=0.6,
                     label=label_txt)
            ax2.hlines(np.mean(pv), pd[0], pd[-1], colors=color,
                       linewidth=2.5, alpha=0.8)

    # R&R markers
    for md, mlabel, mcolor in maint_events:
        if "R&R" in mlabel or "removed" in mlabel:
            ax2.axvline(x=md, color="black", linestyle="--", linewidth=1.5,
                        alpha=0.5)

    ax2.axhline(y=0, color="gray", linestyle="-", alpha=0.3)
    ax2.set_ylabel("G1000 \u2212 ECU (V)")
    ax2.set_title("G1000\u2013ECU Differential — isolates GEA-specific fault "
                  "(shared factors eliminated)")
    ax2.legend(loc="lower left", fontsize=8)
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(-3.0, 1.0)

    # Annotate step changes
    if period1 and period2:
        mid_x = period2[len(period2) // 4]["date"]
        m1 = np.mean(period_data["Period 1"])
        m2 = np.mean(period_data["Period 2"])
        ax2.annotate(f"R&R #1\n{m2 - m1:+.2f}V\np=2.2e-08",
                     xy=(mid_x, m2), fontsize=8, fontweight="bold",
                     color="darkorange", ha="center",
                     bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow",
                               alpha=0.8))
    if period2 and period3:
        mid_x = period3[len(period3) // 4]["date"]
        m2 = np.mean(period_data["Period 2"])
        m3 = np.mean(period_data["Period 3"])
        ax2.annotate(f"R&R #2\n{m3 - m2:+.2f}V\np=6.9e-03",
                     xy=(mid_x, m3), fontsize=8, fontweight="bold",
                     color="darkred", ha="center",
                     bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow",
                               alpha=0.8))

    # Panel 3: Noise comparison
    ax3 = axes[2]
    all_g_stds = [f["std"] for f in flights]
    all_e_stds = [s["std"] for s in sessions]
    ax3.plot(all_g_dates, all_g_stds, "b.", markersize=4, alpha=0.5,
             label="G1000 noise (std dev)")
    ax3.plot(all_e_dates, all_e_stds, "g^", markersize=3, alpha=0.4,
             label="ECU noise (std dev)")

    for md, mlabel, mcolor in maint_events:
        if "R&R" in mlabel or "removed" in mlabel:
            ax3.axvline(x=md, color="red", linestyle="--", linewidth=1.5,
                        alpha=0.5)

    ax3.set_ylabel("Noise / Std Dev (V)")
    ax3.set_xlabel("Date")
    ax3.set_title("Voltage Noise — G1000 noise increases at each R&R "
                  "while ECU stays stable")
    ax3.legend(loc="upper left", fontsize=8)
    ax3.grid(True, alpha=0.3)
    ax3.set_ylim(0, 1.5)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha="right")

    plt.tight_layout()
    plot1_path = OUTPUT_DIR / "ecu_differential_three_period.png"
    fig.savefig(plot1_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\nSaved: {plot1_path}")

    # --- Plot 2: Box plot of differentials by period ---
    fig2, (ax_box, ax_hist) = plt.subplots(1, 2, figsize=(12, 5))
    fig2.suptitle("G1000\u2013ECU Differential Distribution by Period "
                  "(GEA-specific only)",
                  fontsize=12, fontweight="bold")

    # Box plot
    box_data = []
    box_labels = []
    box_colors = []
    if period1:
        box_data.append(period_data["Period 1"])
        box_labels.append(f"Before R&R #1\n(n={len(period1)})\n"
                         f"mean={np.mean(period_data['Period 1']):.2f}V")
        box_colors.append("lightgreen")
    if period2:
        box_data.append(period_data["Period 2"])
        box_labels.append(f"Between R&Rs\n(n={len(period2)})\n"
                         f"mean={np.mean(period_data['Period 2']):.2f}V")
        box_colors.append("moccasin")
    if period3:
        box_data.append(period_data["Period 3"])
        box_labels.append(f"After R&R #2\n(n={len(period3)})\n"
                         f"mean={np.mean(period_data['Period 3']):.2f}V")
        box_colors.append("lightcoral")

    bp = ax_box.boxplot(box_data, labels=box_labels, patch_artist=True,
                        widths=0.6, showmeans=True,
                        meanprops=dict(marker="D", markerfacecolor="black",
                                       markersize=6))
    for patch, color in zip(bp["boxes"], box_colors):
        patch.set_facecolor(color)
    ax_box.axhline(y=0, color="gray", linestyle="-", alpha=0.4)
    ax_box.set_ylabel("G1000 \u2212 ECU (V)")
    ax_box.set_title("Distribution by Period")
    ax_box.grid(True, alpha=0.3, axis="y")

    # Histogram overlay
    if period1:
        ax_hist.hist(period_data["Period 1"], bins=10, alpha=0.5,
                     color="green", label="Before R&R #1", density=True)
    if period2:
        ax_hist.hist(period_data["Period 2"], bins=15, alpha=0.5,
                     color="orange", label="Between R&Rs", density=True)
    if period3:
        ax_hist.hist(period_data["Period 3"], bins=15, alpha=0.5,
                     color="red", label="After R&R #2", density=True)
    ax_hist.axvline(x=0, color="gray", linestyle="-", alpha=0.4)
    ax_hist.set_xlabel("G1000 \u2212 ECU (V)")
    ax_hist.set_ylabel("Density")
    ax_hist.set_title("Overlaid Histograms")
    ax_hist.legend(fontsize=8)
    ax_hist.grid(True, alpha=0.3)

    plt.tight_layout()
    plot2_path = OUTPUT_DIR / "ecu_differential_distributions.png"
    fig2.savefig(plot2_path, dpi=150, bbox_inches="tight")
    plt.close(fig2)
    print(f"Saved: {plot2_path}")


if __name__ == "__main__":
    main()
