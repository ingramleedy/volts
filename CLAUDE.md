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
- `Docs/AMM_p1908_G1000_wiring.png` through `AMM_p1912_G1000_wiring.png` - G1000 NXi wiring diagrams (Drawing D44-9231-60-03_01, Sheets 2/6-6/6), 5100x3300 px each

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
  -> battery negative terminal (aft fuselage)
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

## Historical Voltage Analysis (184 flights)

### FlySto Download
All 184 G1000 NXi CSV source logs were bulk-downloaded from FlySto.net using `flysto_download.py`. Date range: July 14, 2023 (first flight after delivery) to February 13, 2026.

### Change-Point Detection (Pettitt's Test)
A nonparametric Pettitt's test on mean cruise voltage across all 184 flights detected a statistically significant change-point:

| Metric | Value |
|---|---|
| Change-point date | **2024-02-29** (flight #53) |
| Pettitt p-value | 3.75e-13 |
| Before (53 flights) | mean=27.44V, noise=0.251V |
| After (131 flights) | mean=26.90V, noise=0.390V |
| Voltage drop | 0.54V |
| Noise increase | 55% |

### ECU Historical Reference (265 sessions)
ECU battery voltage from 265 parsed sessions (Oct 2023 - Feb 2026) shows:
- ECU mean cruise voltage: 27.82V (stable across entire period)
- ECU mean noise: 0.240V
- G1000 under-reports by 0.76V on average vs ECU
- ECU voltage does NOT show a change-point — the drop is G1000-specific

## Maintenance History (from Aircraft Logs)

### Complete Maintenance Timeline (N239PS-AIRCRAFT-LOGS.pdf)

| Date | TT (hrs) | Event | Relevance |
|---|---|---|---|
| Jun 26, 2023 | 3.2 | Aircraft delivered new | Baseline |
| Nov 8, 2023 | 48.7 | ECU software update BC33_07_26 | Minor |
| **Feb 28, 2024** | **54.5** | **Engine removed for oil leak repair** (prop off, engine off, R&I cylinder head cover, R&R oil sump gasket, engine+prop reinstalled) | **PRIMARY EVENT — coincides exactly with statistically detected change-point** |
| Mar 27, 2024 | 57.7 | Replaced alternator #2 (secondary) S/N H-X010804 → H-X120098 | Shop chasing voltage issue |
| Apr 15, 2024 | 61.4 | R&R voltage regulator (VR2000-28-1) | Shop chasing voltage issue |
| Jun 7, 2024 | 89.2 | Replaced turbo | Unrelated |
| Jun 30, 2024 | 100.7 | Replaced voltage regulator AGAIN (E4A-91-200-000) + repaired wire terminal at plug P2208 | Shop chasing voltage issue |
| Jul 26, 2024 | 95.6 | Annual: replaced P2413 connector with new repinned HSDB harness; RSB 40NG-052 alt mounting; replaced alt #2 belt; ECU backup batteries | G1000 comms fix + alt work |
| Sep 5, 2024 | 103.2 | Battery Minder interface installed; piston borescope | Minor |
| Feb 21, 2025 | 136.9 | Replaced MAIN alternator (EA4-91-400-000) AND voltage regulator (3rd VR replacement) | Shop still chasing voltage |
| Apr 30, 2025 | 147.5 | Engine removed (#1 piston crack, AD 2024-19-10) | Second engine R&R |
| Jul 1, 2025 | 147.5 | Engine reinstalled (pistons+connecting rods replaced). Battery failed cap test at 68%, replaced. G1000 SW updated to 1669.14 | Battery degraded from chronic undercharging? |

### Key Findings from Maintenance Correlation
1. The **Feb 28, 2024 engine R&R** aligns precisely (within 1 day) with the statistically detected change-point
2. When the engine was removed, all firewall pass-through connections (ground straps, harness connectors) were disconnected and reconnected
3. The shop then chased the voltage issue for over a year with component replacements:
   - 3 voltage regulator replacements
   - 2 alternator replacements (secondary + main)
   - 1 wire terminal repair
   - None resolved the issue because it's a ground path resistance problem
4. The ECU reads correctly throughout (27.82V), proving the alternator and regulators are functioning normally
5. The main battery failed capacity test at 68% in Jul 2025 — possibly degraded from chronic undercharging due to the G1000 reporting low voltage

### Second Engine R&R Analysis (Differential Diagnosis)

The engine was removed and reinstalled a second time in **Apr-Jul 2025** (piston crack, AD 2024-19-10). This second R&R required disconnecting and reconnecting the **same firewall pass-through connectors** as the first R&R. If the fault were at the firewall, the second R&R should have either fixed it (by remaking the connection) or at least changed the reading.

**Three-Period Comparison:**

| Period | Flights | Mean Voltage | Mean Noise (σ) |
|---|---|---|---|
| Before R&R #1 (pre Feb 2024) | 50 | 27.46 V | 0.253 V |
| Between R&Rs (Mar 2024 – Apr 2025) | 88 | 26.84 V | 0.374 V |
| After R&R #2 (Jul 2025+) | 46 | 27.03 V | 0.410 V |

**Result:** The problem **did NOT resolve** after R&R #2. The voltage remains ~0.4 V below the pre-fault baseline and noise actually increased slightly. This rules out the firewall pass-through connectors as the fault location, since they were reconnected during R&R #2 with no improvement.

**Narrowed Failure Location:**
- **Ruled out:** Firewall pass-through connectors, engine compartment ground straps (GS-RP) — these were all reconnected during R&R #2
- **Most likely:** Instrument panel ground path (GS-IP ground studs, ground bus bar, or G1000 harness ground pins) — these areas were NOT disturbed during either engine R&R
- **Note:** The pitch servo (also worked during the Feb 2024 shop visit) is located under the seats, not in the instrument panel, so it would not have required access to instrument panel ground studs
- **Possible mechanism:** Something during the Feb 2024 shop visit (not necessarily the engine R&R itself) disturbed an instrument panel ground connection, or the introduction of slightly higher resistance at the firewall during R&R #1 shifted enough current through the instrument panel ground path to expose a pre-existing marginal connection

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
- Extracted AMM CH.92 electrical system schematics (pages 1857-1861) to `docs/` as high-res PNGs
- Analyzed bus architecture and G1000 voltage sensing/ground path from wiring diagrams
- Identified specific failure points: GS-IP ground studs, harness ground pins, bus bar-to-fuselage bond

### 2026-02-15: Forum Feedback & Bus Investigation
- Investigated AMM 24-60-00 bus structure diagrams for all DA40 NG variants
- **Finding: The G1000 is on the AVIONIC BUS, NOT the Essential Bus.**
- Updated README.md with bus structure clarification and Mermaid diagrams

### 2026-02-15: Historical Analysis & FlySto Download
- Reverse-engineered FlySto.net API and created `flysto_download.py` for bulk CSV download
- Downloaded all 184 G1000 NXi source logs to `data/source/` (Jul 2023 - Feb 2026)
- Created `voltage_history.py` - historical analysis with change-point detection
- Ran Pettitt's test: change-point at Feb 29, 2024 (p=3.75e-13)
- Added CUSUM visualization, before/after distributions
- Integrated ECU data from AustroView (265 sessions, Oct 2023 - Feb 2026) as independent reference
- Processed older `.ae3` files through AustroView decrypt/parse pipeline to extend ECU date range
- Parsed aircraft maintenance logs (N239PS-AIRCRAFT-LOGS.pdf, 115 pages)
- **Key discovery**: Engine R&R on Feb 28, 2024 for oil leak repair aligns exactly with the change-point
- Identified pattern of the shop chasing the voltage issue with component replacements (3 VRs, 2 alternators) without addressing the ground path root cause
- New outputs: `voltage_history.png`, `voltage_noise_history.png`, `voltage_changepoint.png`, `voltage_before_after.png`, `voltage_maintenance_correlation.png`

### 2026-02-15: Second R&R Differential Diagnosis
- Compared three periods: before R&R #1 (50 flights), between R&Rs (88 flights), after R&R #2 (46 flights)
- Found R&R #2 did NOT resolve the problem (27.03V vs 27.46V baseline, noise still elevated)
- Ruled out firewall pass-through connectors as the fault location
- Narrowed failure to instrument panel ground path (GS-IP studs, ground bus bar, harness ground pins)
- Corrected assumption about pitch servo location (under seats, not instrument panel)

### 2026-02-15: R&R #1 vs R&R #2 Analysis & Compartment-Based Troubleshooting
- Analyzed what specific work was done during R&R #1 (oil leak: cyl head cover, oil sump gasket) that was NOT done during R&R #2 (piston replacement)
- Recognized that collateral damage during R&R #1 maintenance window is the most likely introduction point
- Added compartment-by-compartment inspection guide: Instrument Panel (highest), Fuselage (medium), Engine Compartment (suspect — R&R #1 specific), Relay Panel (reference)
- Engine compartment included as suspect area: oil leak repair access (cylinder head, oil sump) required harness/ground strap manipulation that R&R #2 piston work did not
- Key insight: even though ECU grounds through GS-RP and reads correctly, the GS-IP return path passes through the firewall area and could be affected by engine compartment work independently

### 2026-02-15: Complete Ground Path Documentation
- Traced all G1000 ground return paths through AMM CH.92 schematics (D44-9224-30-01 through -05)
- Documented 6-segment ground path from LRU pins → harness → GS-IP studs → bus bar → IP frame → fuselage → battery negative
- Catalogued all wire numbers, connectors, and gauge sizes from CH.92 drawings
- Documented GS-RP vs GS-IP ground stud group separation and component assignments
- Created detailed Mermaid diagrams: segment map, ground stud groups, diagnostic flowchart
- Wrote complete diagnostic/troubleshooting procedure with resistance thresholds and step-by-step isolation
- Added visual inspection checklist, priority-ranked failure points, and post-repair verification criteria
- Replaced generic "Recommended Actions" with comprehensive "Diagnostic & Troubleshooting Procedure"
- Noted AMM CH.31/34/23 cross-references for G1000 LRU-specific pin assignments (not in CH.92)

### 2026-02-16: G1000 NXi Ground Stud Inventory (from LRU Wiring Diagrams)
- Extracted AMM pages 1908-1912 (Drawing D44-9231-60-03_01, G1000 NXi Phase III, Sheets 2/6-6/6) to `docs/`
- Processed 5100x3300 px schematics using parallel subagents to avoid API image dimension limits
- Catalogued all G1000 power ground connections by LRU, connector, pin, wire number, gauge, and ground stud
- **Key findings:**
  - **GS IP-6**: Both GIA 63W #1 (wire 23011A20N, pin 14 on 1P604) and GIA 63W #2 (wire 23001A20N, pin 14 on 2P604) share this single ground stud — the primary voltage sensors
  - **GS IP-4**: Most loaded stud — GDU 1050 PFD (31106A22N), GDU 1060 MFD (31158A22N), GEA 71S (77015A22N), GMA 1360 (23201A20N), COM 1 (23001A20N) — 5 LRUs on one stud
  - **GS IP-5**: Both GRS 79 AHRS units via GS AVB intermediate bus bar with 53V TVS diode protection
  - **GS IP-3**: GPS/NAV 1 (34001A22N) + Wx 500 Stormscope (34402A20N)
  - **GS IP-10**: GPS/NAV 2 (34101A22N) — isolated
  - **GS IP-14**: GEA 71S current monitor (74005A22N)
  - **GS IP-8**: Config/power ground (31108A22N)
- Updated Ground Stud Groups section in README with complete wire-level LRU ground inventory
- Drawing reference: D44-9231-60-03_01, Doc 6.02.15, Rev. 5, 15 July 2024

### 2026-02-16: External Voltage Comparison (Diamond Aviators Forum)
- Forum post by geekmug (Scott), aircraft N541SA (DA40NG), on Diamond Aviators forum
- URL: https://www.diamondaviators.net/forum/viewtopic.php?p=108026#p108026
- FlySto graph from N541SA shows substantially more stable voltage than N238PS
- Confirms the G1000 is capable of reading steady, accurate voltage when ground paths are healthy
- Rules out Garmin firmware or sensor design as the cause — issue is aircraft-specific to N238PS
- Added to README as external comparison reference supporting the high-resistance ground hypothesis

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

### voltage_history.py
Historical analysis across all 184 G1000 logs with change-point detection, ECU overlay, and maintenance event correlation. Requires G1000 CSVs in `data/source/` and AustroView parsed ECU data at `../AustroView/Data/Parsed/`.
```bash
python voltage_history.py
```

### flysto_download.py
Bulk download of G1000 NXi CSV source logs from FlySto.net. Credentials from `FLYSTO_EMAIL`/`FLYSTO_PASSWORD` env vars or interactive prompt.
```bash
python flysto_download.py --list          # List available logs
python flysto_download.py                 # Download all G3000 CSVs
python flysto_download.py --last 10       # Download last 10 logs
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
