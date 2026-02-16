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
- `Docs/AMM_p622_*_Bus_Structure_G1000.png` - Bus structure diagram from AMM 24-60-00 Figure 1
- `Docs/AMM_p1857_*.png` through `AMM_p1861_*.png` - Electrical system wiring schematics extracted from DA40 NG AMM (Doc 6.02.15, CH.92), pages 1857-1861

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

## Electrical System Architecture (from AMM CH.92 Wiring Diagrams)

Schematics extracted from DA40 NG AMM pages 1857-1861 (Drawing Nos. D44-9224-30-01 through D44-9224-30-05).

### Bus Structure
The DA40 NG has seven buses (per AMM 24-60-00 Figure 1 and 24-00-00 Figure 1):
- **MAIN BUS** - Primary power distribution, fed by battery via Power Relay (PWR 60A breaker) + alternator
- **ESSENTIAL BUS** - Critical systems, fed from MAIN BUS via MAIN TIE 30A + Essential Tie Relay + ESS TIE 30A
- **AVIONIC BUS** - G1000 and avionics, fed from **MAIN BUS** via AV. BUS 25A breaker + Avionic Relay
- **BATT BUS** - Direct battery bus (always connected when battery relay closed)
- **HOT BUS** - Always-on bus, direct battery connection (AUX POWER PLUG is here, 5A fuse)
- **ECU BUS** / **ECU B BUS** - Engine control units (separate from avionics path, 100A fuse from BATT BUS)

**Important:** The G1000 is on the AVIONIC BUS, NOT the Essential Bus. The Avionic Master switch lives on the Essential Bus but only controls the Avionic Relay coil -- it does not carry the power. The AVIONIC BUS and ESSENTIAL BUS are sibling buses that both branch independently from the MAIN BUS.

### Power Path to G1000
```
MAIN BATTERY (B1, 24V/13.6Ah)
  -> 100A fuse -> BATTERY RELAY -> BATT BUS
  -> Power Relay (PWR 60A breaker) -> MAIN BUS
  -> AV. BUS 25A breaker -> AVIONIC RELAY -> AVIONIC BUS
  -> individual circuit breakers -> G1000 GDU/GIA units
```

### VDL48 Connection Point
The VDL48 was connected to the **AUX POWER PLUG** in the cockpit, which is on the **HOT BUS** (direct battery connection via 5A fuse). This gives a clean reference measurement of battery/alternator voltage without relay or breaker voltage drops.

### Ground Path (Critical for Voltage Sensing)
The G1000 measures voltage at its power input pins **relative to its own ground pins**. The ground return path is:
```
G1000 GDU/GIA ground pins
  -> harness wires (22 AWG)
  -> Instrument Panel ground studs (GS-IP-xx series)
  -> ground bus bar
  -> fuselage structure
  -> engine compartment ground strap
  -> battery negative terminal
```

The relay panel and engine compartment components use separate ground studs (GS-RP series). The battery, alternator, and starter grounds return through GS-RP directly to the battery negative.

### Alternator Voltage Regulation
The alternator regulator (J2424) has a **dedicated USENSE wire** (24022A22, 22 AWG, pin 5) for voltage sensing, separate from the G1000's measurement. This means:
- The alternator regulates to the correct voltage (confirmed by VDL48 reading ~28.3V)
- The G1000 reads low because of its own ground path, not because the bus is actually low
- The ECU (on its own bus and ground) also reads near-correct voltage, confirming the G1000 ground path is the problem

### Regulator Connections (D44-9224-30-01_02, p1858; D44-9224-30-05, p1861)
| Pin | Function | Wire |
|-----|----------|------|
| 5 | USENSE (Voltage Sense) | 24022A22 (22 AWG) |
| 7 | EXCITATION | 24017A20 (20 AWG) |
| 6 | SUPPLY | via supply circuit |
| 12 | LAMP | 31004A22 |
| 4 | GROUND | 24018A20N (20 AWG) |

### Where to Look for the Problem
Based on the schematics, the most likely failure points for a high-resistance ground:
1. **G1000 GDU/GIA ground pins at harness connector** - corrosion or loose pin
2. **Instrument panel ground studs (GS-IP)** - loose nut, corrosion, paint under ring terminal
3. **Ground bus bar to fuselage bond** - structural ground point where the instrument panel bus bar connects to the airframe
4. **Firewall ground feedthrough** - where instrument panel grounds transition to the engine compartment/battery ground

The AVIONIC BUS power path (25A breaker, relay contacts) could also contribute series resistance, but this would equally affect all avionics. The fact that only the G1000 reads low (while the ECU on a separate bus reads correctly) points specifically to the G1000's own ground return path.

## Three-Source Correlation (ECU)

### Cross-Project Reference
The AE300 ECU battery voltage data comes from the **AustroView** project (`../AustroView/`). The `correlate_ecu.py` script reads parsed CSV files from `../AustroView/Data/Parsed/` — specifically sessions 80 and 81, which correspond to the same Feb 8, 2026 flights.

### ECU Data Details
- **Source**: AE300 ECU channel 808 ("Battery Voltage"), 1 Hz sampling
- **Conversion**: `eVolt_Batt` signal class — coefficient 0.01955034, offset 0
- **Session 80**: 2026-02-08 15:57:57 - 16:54:23 UTC (Flight 1)
- **Session 81**: 2026-02-08 18:18:47 - 19:32:10 UTC (Flight 2)
- **File pattern**: `DataLog_*_session80_*.csv` / `session81_*.csv`

### Three-Way Results Summary
| Pair | Flight 1 | Flight 2 | Combined |
|------|----------|----------|----------|
| G1000 - VDL48 | -1.94 V | -0.98 V | -1.38 V |
| G1000 - ECU | -2.05 V | -0.21 V | -0.99 V |
| ECU - VDL48 | +0.11 V | -0.77 V | -0.40 V |

The ECU closely agrees with the VDL48 reference (especially Flight 1 at +0.11 V offset). Both independent instruments read higher than the G1000, confirming the G1000 is the outlier.

## Maintenance History

### 2026-02-15: Pin Cleaning (Invoice)
- **Squawk:** LOW VOLTS WARNING / INCORRECT READING ON G1000, TROUBLESHOOT
- **Action:** Removed, inspected, cleaned pins, and reinstalled all GDL 69A computers IAW DA40NG MM CH. 23
- **Labor:** 1.50 hrs / $240.00
- **Result:** Could not reproduce voltage drop on ground run; voltage stayed in green

**Concerns with this action:**
- The **GDL 69A is the datalink transceiver** (SiriusXM weather/traffic), not the voltage-sensing avionics. The G1000 `volt1` reading comes from the **GIA 63W** (Integrated Avionics Units) and/or the **GDU 1050/1060** (displays). Those units' ground pins and connectors were not addressed.
- The AMM reference was **CH. 23 (Communications)**, not CH. 24/34/92 where the voltage measurement path lives.
- **Ground running cannot reproduce the issue.** The voltage offset in our data is driven by:
  - Vibration (loosens marginal contacts) — absent on the ground
  - Thermal cycling — absent during a brief ground run
  - High-current transient loads (radio TX, autopilot servos, flap motor) — not exercised during a static check
  - The -5.6 V worst-case dips only appear during flight operations
- With a fully charged battery (owner uses a battery minder/trickle charger in hangar), the steady-state voltage reads in the green even with the ~1.4 V offset. LOW VOLTS only triggers during transient dips under load in flight.

**Recommended next steps:**
- Request inspection of **GIA 63W and GDU 1050/1060** connectors and ground pins specifically
- Inspect **GS-IP instrument panel ground studs** (see Electrical System Architecture section)
- Perform a **resistance measurement** from GIA/GDU ground pin to battery negative
- Repeat the VDL48 flight test after any corrective action to verify

## Session History

### 2026-02-09: Initial Analysis
- Created `voltage_analysis.py` - parses all data, segments VDL, computes statistics, generates PNG plots
- Created `generate_report.py` - produces self-contained HTML report with embedded base64 images
- Output saved to `output/` directory
- Published to https://github.com/ingramleedy/volts

### 2026-02-15: ECU Correlation & Schematic Analysis
- Created `correlate_ecu.py` - three-source analysis adding AE300 ECU battery voltage
- ECU data parsed from AustroView project (sessions 80/81)
- ECU agrees with VDL48 reference, confirming G1000 under-reading
- New outputs: `three_way_flight1.png`, `three_way_flight2.png`, `ecu_vs_vdl_scatter.png`, `three_way_histograms.png`, `three_way_voltage_report.txt`
- Extracted AMM CH.92 electrical system schematics (pages 1857-1861) to `docs/` as high-res PNGs
- Analyzed bus architecture and G1000 voltage sensing/ground path from wiring diagrams
- Identified specific failure points: GS-IP ground studs, harness ground pins, bus bar-to-fuselage bond

### 2026-02-15: Forum Feedback & Bus Investigation
- Forum post suggested "The G1000 is on the essential bus" and recommended monitoring that specific bus
- Investigated AMM 24-60-00 bus structure diagrams (Figures 1, 3, 5) for all DA40 NG variants
- **Finding: The G1000 is on the AVIONIC BUS, NOT the Essential Bus.** The AVIONIC BUS is fed directly from the MAIN BUS (AV. BUS 25A breaker + Avionic Relay). The Avionic Master switch on the Essential Bus only controls the relay coil.
- Extracted and saved AMM 24-60-00 Figure 1 (bus structure diagram) as `docs/AMM_p622_24-60-00_Bus_Structure_G1000.png`
- Confirmed AMM trouble-shooting table (p627): "There is 28 VDC on the main bus (if G1000 is installed)" -- power originates from MAIN BUS
- Identified VDL48 connection point: **AUX POWER PLUG** on the **HOT BUS** (direct battery, 5A fuse) per AMM 24-00-00 Figure 1
- Updated README.md with bus structure clarification, corrected bus feed descriptions, and forum feedback response
- Removed Club variant schematic (p1860) from README since N238PS is MAM40-858 (p1859 is the correct diagram)

## Scripts

### voltage_analysis.py
Two-source analysis (G1000 vs VDL48). Prints statistics to console and saves PNG plots to `output/`.
```bash
python voltage_analysis.py
```

### correlate_ecu.py
Three-source analysis adding AE300 ECU data. Requires AustroView parsed CSVs at `../AustroView/Data/Parsed/`.
```bash
python correlate_ecu.py
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
