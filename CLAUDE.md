# CLAUDE.md - Project Context and History

## Project Overview

This project analyzes a voltage measurement discrepancy between the Garmin G1000 NXi avionics system and an independent Triplett VDL48 voltage data logger on aircraft N238PS (Diamond DA40NG). The analysis was built to investigate intermittent LOW VOLTS annunciations.

## Original Prompt

> I have an aircraft that logs flight data per flight, the data for each flight can be found in "data" folder N238PS_KBOW-KSPG_20260208-1551UTC and N238PS_KSPG-KBOW_20260208-1812UTC which are Garmin G1000 NXI data log files. In the "Docs" directory is a document that explains the fields. Also in the folder is LOG_VD which is data from a voltage logger Triplett VDL48. The LOG_VD contain the voltage log of the first flight when the engine was already running with the associate log, N238PS_KBOW-KSPG_20260208-1551UTC, a period of time while the engine was stopped (maybe around an hour), and then the next flight N238PS_KSPG-KBOW_20260208-1812UTC until when I pulled the logger out. The logger timestamps seems to have the incorrect date and time, but the period is still relevant.
>
> I want use use python to parse these file and determine a correlation between what the G1000 logs and what was logged via the VDL48. I suspect the G1000 is reporting a lower voltage causing a LOW VOLTS alarm in the past to indicate when battery voltage dips a little lower.
>
> I want to create a script that reports or correlates the diference in voltage and graphs the two flights voltage against the VDLs logged voltage and determine and satisitcal difference. Note that the VDL looks like it has three distinct voltage reporting, flight 1, idle period, then flight 2. The voltage in the VDL shows these three areas.

## Data Files

### G1000 NXi Logs
- **Format:** CSV with 3 metadata rows + 4 init rows, data starts row 8
- **Sampling:** 1-second intervals
- **Columns:** 58 total; `volt1` (index 19) is the main bus voltage, `volt2` (index 20) is unused (always 0.0)
- **Date/time:** `Lcl Date` (YYYY-MM-DD) + `Lcl Time` (HH:MM:SS), UTC offset in `UTCOfst`
- **Flight 1:** `N238PS_KBOW-KSPG_20260208-1551UTC.csv` - 3,454 voltage samples, 15:50:53-16:47:13 UTC
- **Flight 2:** `N238PS_KSPG-KBOW_20260208-1812UTC.csv` - 4,470 voltage samples, 18:10:34-19:25:02 UTC

### VDL48 Logger
- **Format:** CSV with 10 header lines + blank + column header, data starts line 13
- **Sampling:** 2-second intervals
- **Columns:** `Date(MMDD)`, `Time`, `Voltage(V)`
- **Important:** Logger date/time is incorrect (shows 2019-03-01) but sampling period is accurate
- **Total:** 9,263 data points over 5.15 hours
- **Three segments identified by voltage patterns:**
  - Flight 1: indices 0-1651 (~55 min, mean 28.26 V, alternator charging)
  - Idle: indices 1651-4192 (~85 min, mean 26.26 V, battery decaying)
  - Flight 2: indices 4192-6422 (~74 min, mean 28.31 V, alternator charging)
  - Remainder: 0 V (logger disconnected)

### Documentation
- `Docs/G1000 DataLog Fields.pdf` - Garmin field reference (Appendix I: FDR Data Log Comparison, pages 94-98)

## Analysis Approach

1. **Parse** both G1000 CSVs (skip metadata, extract timestamps + volt1) and VDL CSV (skip header, extract elapsed time + voltage)
2. **Segment** VDL data into three phases using a 27V threshold with 60-second sustained detection window
3. **Align** VDL flight segments to G1000 flight times (match start times, preserve 2-sec intervals)
4. **Resample** both signals onto a common 2-second grid via linear interpolation for paired comparison
5. **Compute** paired t-tests, Pearson correlation, difference distributions
6. **Generate** time-series overlays, difference histograms, scatter plot with regression

## Key Results

| Metric | Flight 1 | Flight 2 | Combined |
|---|---|---|---|
| G1000 mean | 26.40 V | 27.32 V | 26.93 V |
| VDL mean | 28.26 V | 28.31 V | 28.29 V |
| Mean offset | -1.87 V | -0.99 V | -1.36 V |
| Worst dip | -5.58 V | -4.55 V | -5.58 V |
| Pearson r | -0.12 | 0.11 | 0.09 |
| Paired t-test | p < 0.001 | p < 0.001 | p < 0.001 |

The G1000 systematically under-reports by ~1.4 V on average, with erratic fluctuations not present in the VDL reference. The near-zero correlation despite measuring the same bus points to a resistive ground/sensing path issue rather than calibration error.

## Probable Cause

High-resistance ground connection in the G1000's measurement path. Evidence:
- Variable offset (not constant) driven by changing current loads
- G1000 shows 2-3x more voltage noise than VDL on the same bus
- Deep transient dips coincide with high-current events (radio TX, servos)
- Different magnitude between flights (thermal/vibration effects on contact resistance)
- Even 0.05 ohms at 20A = 1.0V drop

## Session History

### 2026-02-09: Initial Analysis
- Created `voltage_analysis.py` - parses all data, segments VDL, computes statistics, generates PNG plots
- Created `generate_report.py` - produces self-contained HTML report with embedded base64 images
- Output saved to `output/` directory
- Published to https://github.com/ingramleedy/volts

## Scripts

### voltage_analysis.py
Main analysis script. Prints statistics to console and saves individual PNG plots to `output/`.
```bash
python voltage_analysis.py
```

### generate_report.py
Generates a single self-contained HTML file with all charts and statistics embedded. Shareable without dependencies.
```bash
python generate_report.py
```

## Dependencies
- Python 3.10+
- numpy
- matplotlib
- scipy
