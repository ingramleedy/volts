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
- `Docs/AMM_p1908_G1000_wiring.png` through `AMM_p1912_G1000_wiring.png` - G1000 NXi wiring diagrams (Drawing D44-9231-60-03, Sheets 2/6-6/6), 5100x3300 px each
- `Docs/GEA71_InstallationManual.pdf` - Garmin GEA 71 Installation Manual (190-00303-40, Revision F). Pages 23-26 contain P701 and P702 connector pin function lists (78 pins each)
- `Docs/Instrument Panel - Breakers.png` - AFM p.361 instrument panel layout showing circuit breaker positions grouped by bus (EECU BUS, ESSENTIAL BUS, MAIN BUS, AVIONICS BUS). Confirms ENG INST breaker (GEA 71S power) is on the Essential Bus.
- `docs/G100 System Maintenance Manaual DA40 - CAUTION ALERTS.png` - G1000 System Maintenance Manual (Garmin 190-00545-01) CAUTION Alerts table. **LOW VOLTS** entry: "On-board voltage is below 24 volts" → Solution: "Inspect GEA 71 connector & wiring. Troubleshoot aircraft electrical system according to DA 40 Airplane Maintenance Manual instructions." Garmin's own troubleshooting procedure names the GEA 71 connector & wiring as the first inspection target for LOW VOLTS — directly supporting our analysis.
- `docs/24-31 Battery Installation.png` - IPC drawing showing battery mounting in aft fuselage. Shows three connections at battery negative: wire 24008A4N (item "To Instrument Panel, See 31-10"), wire 24405A6N (item "To EPU, See 24-40"), and **Cable 200** (P/N D44-2403-160-00, "Cable, Battery GND") which routes to a structural/airframe ground point
- `docs/24-40 External Power.png` - IPC drawing showing EPU (External Power Unit) plug location and routing
- `docs/24-60 Battery Relay.png` - IPC drawing showing battery relay installation
- `docs/24-60 Relay Panel.png` - IPC drawing showing relay panel adjacent to battery in aft fuselage
- `docs/an2551-plug.pdf` - AN2551 external power plug technical instructions
- AMM pages 1936-1937 (Drawing D44-9274-10-00, EECU Wiring) — confirms ECU B grounds to GS-IP-3 and GS-IP-4 (not extracted as images yet)
- IPC source: [Diamond Illustrated Parts Catalog](https://ipc.diamond-air.at/ipp/app?__bk_&__windowid=DSQ82466084&__rid=GWT1771620977044#2V10C9D9248E4C6405)

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

High-resistance power ground connection in the G1000's voltage measurement path. Evidence:
- Variable offset (not constant) driven by changing current loads
- G1000 shows 2-3x more voltage noise than VDL on the same bus
- Deep transient dips coincide with high-current events (radio TX, servos)
- Different magnitude between flights (thermal/vibration effects on contact resistance)
- Even 0.05 ohms at 20A = 1.0V drop

## GEA 71B Voltage Measurement Configuration

The G1000 `volt1` reading comes through the GEA 71B (Engine/Airframe Interface Unit), **Analog In 5 on GEA 1**:
- **m (slope):** 1.0000e+00 — 1:1 scaling, no gain correction
- **b (offset):** 0.0000e+00 — zero offset, no software compensation
- **Filter Coeff:** 0.1000 — moderate smoothing
- **Trans Func Type:** Linear (`Displayed = m × Raw + b`)
- With m=1.0 and b=0.0, the G1000 displays exactly what arrives at the GEA input pin — the offset is hardware (ground path resistance), not calibration

## GEA 71 Connector Pin Assignments (from Garmin Installation Manual 190-00303-40)

The GEA 71 has two 78-pin connectors: **P701** and **P702**. Pin assignments from the Garmin GEA 71 Installation Manual (190-00303-40, Rev F), pages 23-26. The DA40 NG uses the GEA 71S variant; pin functions are compatible.

### P701 — Key Pins for Voltage Investigation

| Pin | Function | I/O | Notes |
|-----|----------|-----|-------|
| 5 | RS 485 1 A | I/O | HSDB to GIA #1 |
| 6 | RS 485 1 B | I/O | HSDB to GIA #1 |
| 7 | RS 485 2 A | I/O | HSDB to GIA #2 |
| 8 | RS 485 2 B | I/O | HSDB to GIA #2 |
| 11 | TRANSDUCER POWER OUT LO (GROUND) | — | Ground return for external transducers (ALT AMPS SENSOR) |
| 12 | TRANSDUCER POWER OUT LO (GROUND) | — | Same as pin 11 |
| 13 | TRANSDUCER POWER OUT LO (GROUND) | — | Same as pin 11 |
| **14** | **+10 VDC TRANSDUCER POWER OUT** | **Out** | **Powers ALT AMPS SENSOR (Hall-effect current transducer)** |
| 15 | +5 VDC TRANSDUCER POWER OUT | Out | |
| 16 | +12 VDC TRANSDUCER POWER OUT | Out | |
| 19 | SIGNAL GROUND | — | |
| **20** | **POWER GROUND** | **—** | **Wire 77016A22N → GS-IP-14 (Ground Stud - Instrument Panel #14). THE BAD GROUND — voltage sensor reference** |
| **35** | **AIRCRAFT POWER 1** | **In** | **Wire 77015A22 from Essential Bus via 5A ENG INST breaker** |
| 37 | AIRCRAFT POWER 2 | In | Second power input |
| **42** | **ANALOG IN 3 HI** | **In** | **ALT AMPS SENSOR OUT HI — differential current measurement** |
| **43** | **ANALOG IN 3 LO** | **In** | **ALT AMPS SENSOR OUT LO — differential current measurement** |
| **44** | **ANALOG IN 4 HI** | **In** | **Wire 77015A22 (tied to Pin 35 power) — measures GEA supply voltage** |
| **45** | **ANALOG IN 4 LO** | **In** | **Wire 77016A22N (tied to Pin 20 power ground) → GS-IP-14 — GEA power ground pin** |
| **46** | **ANALOG IN 5 HI** | **In** | **BUS VOLTS ESSENTIAL BUS (HI) — wire 31299A22WH (shielded), 3A fuse in path (location unknown). Open fuse = 0V reading (not low).** |
| **47** | **ANALOG IN 5 LO** | **In** | **BUS VOLTS ESSENTIAL BUS (LO) — wire 31299A22BL (shielded). This is the voltage measurement reference. Per G1000 wiring diagram (D44-9231-60-03), connects to the low side of the Essential Bus. The Electrical System schematic (D44-9224-30-01X03) shows a generic ground symbol — physical termination point is unknown and needs to be traced. NOTE: Other Diamond variant AMM wiring diagrams explicitly call out a specific ground stud (e.g. GS-IP-X) for the GEA voltage sense LO pin, but the DA40 NG schematic uses only a generic ground symbol. This makes the DA40 NG Pin 47 ground uniquely difficult to troubleshoot — there is no documented stud number to inspect. PRIMARY SUSPECT.** |

### P701 — All Pins (Complete Reference)

| Pin | Function | I/O | Pin | Function | I/O |
|-----|----------|-----|-----|----------|-----|
| 1 | CONFIG MODULE GROUND | — | 40 | CONFIG MODULE DATA | I/O |
| 2 | DIGITAL IN* 1 | In | 41 | DIGITAL IN* 3 | In |
| 3 | DIGITAL IN* 2 | In | 42 | ANALOG IN 3 HI | In |
| 4 | SIGNAL GROUND | — | 43 | ANALOG IN 3 LO | In |
| 5 | RS 485 1 A | I/O | 44 | ANALOG IN 4 HI | In |
| 6 | RS 485 1 B | I/O | 45 | ANALOG IN 4 LO | In |
| 7 | RS 485 2 A | I/O | 46 | ANALOG IN 5 HI | In |
| 8 | RS 485 2 B | I/O | 47 | ANALOG IN 5 LO | In |
| 9 | GEA SYSTEM ID PROGRAM* 1 | In | 48 | ENGINE TEMP ANALOG IN 7 HI | In |
| 10 | GEA SYSTEM ID PROGRAM* 2 | In | 49 | ENGINE TEMP ANALOG IN 7 LO | In |
| 11 | TRANSDUCER POWER OUT LO (GND) | — | 50 | ENGINE TEMP ANALOG IN 8 HI | In |
| 12 | TRANSDUCER POWER OUT LO (GND) | — | 51 | ENGINE TEMP ANALOG IN 8 LO | In |
| 13 | TRANSDUCER POWER OUT LO (GND) | — | 52 | ENGINE TEMP ANALOG IN 9 HI | In |
| 14 | +10 VDC TRANSDUCER POWER OUT | Out | 53 | ENGINE TEMP ANALOG IN 9 LO | In |
| 15 | +5 VDC TRANSDUCER POWER OUT | Out | 54 | ENGINE TEMP ANALOG IN 10 HI | In |
| 16 | +12 VDC TRANSDUCER POWER OUT | Out | 55 | ENGINE TEMP ANALOG IN 10 LO | In |
| 17 | ENGINE TEMP ANALOG IN 6 HI | In | 56 | ENGINE TEMP ANALOG IN 11 HI | In |
| 18 | ENGINE TEMP ANALOG IN 6 LO | In | 57 | ENGINE TEMP ANALOG IN 11 LO | In |
| 19 | SIGNAL GROUND | — | 58 | ENGINE TEMP ANALOG IN 12 HI | In |
| 20 | POWER GROUND | — | 59 | ENGINE TEMP ANALOG IN 12 LO | In |
| 21 | CONFIG MODULE POWER | Out | 60 | CONFIG MODULE CLOCK | Out |
| 22 | ANALOG IN 1 HI | In | 61 | DIGITAL IN* 4 | In |
| 23 | ANALOG IN 1 LO | In | 62 | ANALOG IN 6 HI | In |
| 24 | ANALOG IN 2 HI | In | 63 | ANALOG IN 6 LO | In |
| 25 | ANALOG IN 2 LO | In | 64 | ANALOG IN 7 HI | In |
| 26 | ENGINE TEMP ANALOG IN 1 HI | In | 65 | ANALOG IN 7 LO | In |
| 27 | ENGINE TEMP ANALOG IN 1 LO | In | 66 | ANALOG IN 8 HI | In |
| 28 | ENGINE TEMP ANALOG IN 2 HI | In | 67 | ANALOG IN 8 LO | In |
| 29 | ENGINE TEMP ANALOG IN 2 LO | In | 68 | THERMOCOUPLE REF IN HI | In |
| 30 | ENGINE TEMP ANALOG IN 3 HI | In | 69 | THERMOCOUPLE REF IN LO | In |
| 31 | ENGINE TEMP ANALOG IN 3 LO | In | 70 | DISCRETE IN* 1 | In |
| 32 | SIGNAL GROUND | — | 71 | DISCRETE IN* 2 | In |
| 33 | ENGINE TEMP ANALOG IN 4 HI | In | 72 | ANALOG IN 9 HI | In |
| 34 | ENGINE TEMP ANALOG IN 4 LO | In | 73 | ANALOG IN 9 LO | In |
| 35 | AIRCRAFT POWER 1 | In | 74 | ANALOG IN 10 HI | In |
| 36 | ENGINE TEMP ANALOG IN 5 HI | In | 75 | ANALOG IN 10 LO | In |
| 37 | AIRCRAFT POWER 2 | In | 76 | DISCRETE IN* 3 | In |
| 38 | ENGINE TEMP ANALOG IN 5 LO | In | 77 | GEA REMOTE POWER OFF | In |
| 39 | SIGNAL GROUND | — | 78 | POWER GROUND | — |

### P702 — Key Pins

| Pin | Function | I/O | Notes |
|-----|----------|-----|-------|
| 11-13 | TRANSDUCER POWER OUT LO (GROUND) | — | Transducer ground (A channel) |
| 14 | +10 VDC TRANSDUCER POWER OUT A | Out | Transducer power (A channel) |
| 15 | +5 VDC TRANSDUCER POWER OUT A | Out | |
| 16 | +12 VDC TRANSDUCER POWER OUT A | Out | |
| 44-45 | ANALOG/CURRENT MONITOR IN 1A HI/LO | In | Current monitor input pair |
| 46-47 | ANALOG/CURRENT MONITOR IN 2A HI/LO | In | Current monitor input pair |
| 48-49 | ANALOG/CURRENT MONITOR IN 3A HI/LO | In | Current monitor input pair |
| 50-51 | ANALOG/CURRENT MONITOR IN 4A HI/LO | In | Current monitor input pair |
| 52-53 | ANALOG IN 1A HI/LO | In | |
| 54-55 | ANALOG IN 2A HI/LO | In | |
| 56-57 | ANALOG IN 3A HI/LO | In | |
| 58-59 | ANALOG IN 4A HI/LO | In | |

### ALT AMPS SENSOR Circuit (from AMM D44-9231-60-03 Sheet 4/6)

The alternator current is measured by a **Hall-effect current transducer** (J7700), NOT a resistive shunt:

```
GEA 71S P701                    ALT AMPS SENSOR (J7700)
─────────────                   ───────────────────────
Pin 14 (+10V TRANSDUCER PWR) ──→  V+    (RED,  wire 24331A22OR)
Pin 42 (ANALOG IN 3 HI)     ←──  OUT HI (WHT,  wire 24331A22WH)
Pin 43 (ANALOG IN 3 LO)     ←──  OUT LO (BLK,  wire 24331A22BL)
Pin 11 (TRANSDUCER LO/GND)  ──→  GND
```

- Differential output (HI vs LO) means the bad power ground at Pin 20 does NOT affect the amp reading
- The transducer has its own power supply (+10V) and ground (Pin 11), isolated from the POWER GROUND path
- The G1000 MFD amps display is accurate even with the ground path problem — but amps are not logged to CSV

### GEA 71S Data Flow

```
ECU (AE300) ──RS-232──→ GIA 63W ──HSDB──→ GDU displays     (engine parameters: digital, unaffected by ground)
GEA 71S ────RS-485───→ GIA 63W ──HSDB──→ GDU displays     (airframe measurements: voltage, amps, temps)
```

The GEA 71S does not interface directly with the ECU. Engine parameters flow from the ECU to a GIA 63W via RS-232, then to the displays via HSDB (Ethernet/RS-485). The GEA sends its own airframe measurements (voltage, amps, pitot heat) to the GIAs via RS-485 on pins 5/6 and 7/8.

## Owner Ground Tests

### Aug 18, 2025 (Battery Only)
Static ground test performed after Jul 2025 annual (new battery, VR previously replaced, battery on BatteryMinder):
- **Open circuit (master OFF):** Meter at AUX POWER reads 26.3V → 100% charged per Concorde table
- **G1000 on, no other loads:** Meter reads 25.2V, G1000 displays 23.7V → **1.5V offset with battery only**
- Premier mechanic Raymond independently confirmed variance from cigarette lighter connector
- FlySto LOW VOLTS events: 18s, 85s, 5s below 25V during landing/taxi phases

### Feb 20, 2026 (Battery vs GPU — Same Session)
Two back-to-back tests on the same day, same ground conditions:

| Condition | Meter at AUX POWER | G1000 Display | Offset |
|-----------|-------------------|---------------|--------|
| **Battery only**, G1000 on, no engine | **25.3V** | **24.0V** | **-1.3V** |
| **GPU connected**, G1000 on | **28.79V** | **28.6V** | **-0.19V** |

- Same aircraft, same day — the only variable is battery vs GPU power source
- The 1.3V offset is present on battery and gone on GPU in the same session — eliminates any intermittency argument
- The **24.0V G1000 reading on battery** is right at the LOW VOLTS threshold (24V per Garmin G1000 System Maintenance Manual) — any additional load triggers the annunciation
- The Aug 2025 battery-only test showed similar offset (23.7V vs 25.2V = -1.5V), confirming persistent condition

**Why the GPU test reads nearly correctly is not fully explained.** Per IPC (24-31 Battery Installation), the battery negative terminal has three connections: wire 24008A4N (4 AWG, to instrument panel), wire 24405A6N (6 AWG, to EPU plug), and **Cable 200** (P/N D44-2403-160-00, "Cable, Battery GND") which routes to a structural/airframe ground point. The GPU negative connects to the **same battery negative terminal** via wire 24405A6N. Both tests share the same negative terminal and the same positive path from BATT BUS to the Essential Bus (Power Relay → MAIN TIE → Ess Tie Relay → ESS TIE).

**Cable 200 (Battery GND cable)** is significant because it connects the battery negative terminal to the aircraft's structural grounding system. If Pin 47's ground (wire 31299A22BL) terminates at a structural ground point or intermediate stud that connects back to battery negative through Cable 200's path, then any resistance in Cable 200 or its termination could affect the voltage reading. The GPU's heavy 6 AWG cable (24405A6N) connecting directly to the battery negative terminal could provide an alternate lower-impedance return path that bypasses a degraded Cable 200 connection — potentially explaining why the GPU test reads correctly. **Cable 200's termination point and condition need to be inspected.**

**Note on current direction:** The bus return current through wire 24008A4N flows in the same direction (from GS-IP toward the battery negative terminal) regardless of whether the aircraft is on battery or GPU. The GPU's charging current exits B1(-) but returns to the GPU through wire 24405A6N, not through 24008A4N. Therefore a bad connection at the battery negative terminal on the 24008A4N path alone does not explain the GPU vs battery difference.

Possible factors for the GPU vs battery difference: Cable 200 (Battery GND) may provide Pin 47's ground return path and the GPU may bypass a degraded connection in that path; the positive path relay/breaker contacts may behave differently under different source conditions; Pin 47's unknown ground termination may connect through the structural grounding system that Cable 200 serves; or there are other factors not yet identified.

**The ECU proves the shared GS-IP ground infrastructure is healthy, but does NOT rule out the BATT BUS → Essential Bus positive path.** Per AMM page 1936-1937 (Drawing D44-9274-10-00, EECU Wiring), the AE300 ECU (located under the pilot's seat) grounds to **GS-IP-3 and GS-IP-4** — the same instrument panel ground bus as the G1000, and is on the **ECU BUS** (directly off BATT BUS through a 100A fuse). The ECU reads ~27.8V, essentially correct. The ECU bypasses the Power Relay, MAIN TIE, Ess Tie Relay, and ESS TIE that the Essential Bus must go through.

**Areas to inspect (in order of accessibility):**

1. **Battery negative terminal (aft fuselage)** — Per IPC (24-31), three connections: 24008A4N (instrument panel), 24405A6N (EPU), and **Cable 200** (D44-2403-160-00, "Cable, Battery GND" — routes to structural/airframe ground). Also check the BatteryMinder interface (installed Sep 2024). This terminal has been disturbed during both engine R&Rs and the battery replacement. Clean, check for corrosion, verify torque. **Trace where Cable 200 terminates.**
2. **Pin 47 (ANALOG IN 5 LO) Essential Bus ground** — wire 31299A22BL connects to the low side of the Essential Bus. Physical termination unknown (generic ground symbol on schematic). Other Diamond variants specify a GS-IP-X stud number; the DA40 NG does not. **Must be physically traced.**
3. **Positive path: BATT BUS → Essential Bus** — Four relay/breaker contacts (Power Relay, MAIN TIE, Ess Tie Relay, ESS TIE) between BATT BUS and the Essential Bus. The ECU bypasses all of these. Measure Essential Bus directly and compare to AUX POWER.
4. **GS-IP-14 / Pin 20 (POWER GROUND)** — wire 77016A22N from P701 Pin 20 to GS-IP-14. The GEA's power ground. May cause ADC common-mode issues if it floats far from Pin 47.

The fault is vibration/thermal-sensitive — it worsens in flight (Feb 8 data: -1.4V average, -5.6V worst). The shared GS-IP infrastructure (bus bar, wire 24008A4N) is proven good by the ECU. **The key unknown is where wire 31299A22BL (Pin 47) physically terminates.**

### Feb 20, 2026 (ESS BUS Switch Test)
Tested ESS BUS switch activation with G1000 running:
- MFD turned off (Avionic Bus lost power)
- Engine parameters moved to PFD (reversionary mode)
- **No voltage indicator on PFD** — VOLTS display is MFD-only
- Test requires a multimeter on the Essential Bus to provide reference reading
- Updated MAINTENANCE_GUIDE.md procedure accordingly

**AMM ESS BUS Switch Operation (24-60-00):**
- **OFF (normal):** Gives ground to power relay coil → relay closes → battery bus connects to main bus. Essential Bus is fed from Main Bus via Main Tie + Ess Tie Relay.
- **ON (emergency):** Disconnects ground from power relay coil → power relay opens → main bus disconnected. Also gives ground to essential tie relay coil → relay energizes → breaks main-to-essential connection AND connects battery bus directly to essential bus.
- The ground path does not change — Pin 47 (voltage sense LO) and Pin 20 (power ground) remain on the same ground connections regardless of switch position. Only the power source changes.

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

**Important:** Most G1000 LRUs (GDU displays, GIA computers) are on the AVIONIC BUS. However, the **GEA 71S** (the unit that measures and reports bus voltage) is powered from the **ESSENTIAL BUS** via the 5A ENG INST breaker. The Avionic Master switch lives on the Essential Bus but only controls the Avionic Relay coil -- it does not carry the power. The AVIONIC BUS and ESSENTIAL BUS are sibling buses that both branch independently from the MAIN BUS.

### Power Path to G1000
```
MAIN BATTERY (B1, 24V/13.6Ah)
  -> 100A fuse -> BATTERY RELAY -> BATT BUS
  -> Power Relay (PWR 60A breaker) -> MAIN BUS
  -> AV. BUS 25A breaker -> AVIONIC RELAY -> AVIONIC BUS
  -> individual circuit breakers -> G1000 GDU/GIA units

GEA 71S (voltage sensor) is on the ESSENTIAL BUS, not the AVIONIC BUS:
  MAIN BUS -> MAIN TIE 30A -> Ess Tie Relay -> ESS TIE 30A -> ESSENTIAL BUS
  -> ENG INST 5A breaker -> GEA 71S Pin 35 (AIRCRAFT POWER)
```

### VDL48 Connection Point
The VDL48 was connected to the **AUX POWER PLUG** in the cockpit, which is on the **HOT BUS** (direct battery connection via 5A fuse). This gives a clean reference measurement of battery/alternator voltage without relay or breaker voltage drops.

### External Power Unit (EPU) Plug — AN2551
The GPU connects through an AN2551 external power plug in the engine compartment. Wiring from D44-9224-30-01X03:

| EPU Pin | Wire | Gauge | Connects To |
|---------|------|-------|-------------|
| Jumper/Sense | 24401B22 → J2421 pin 4 → 24401A22 | 22 AWG | EPU RELAY coil (closes relay when GPU plugged in) |
| **Positive** | **24403A6** | **6 AWG** | **BATT BUS** (through EPU RELAY contacts + 100A fuse) |
| **Negative** | **24405A6N** | **6 AWG** | **GS-RP** (relay panel ground, aft fuselage — adjacent to battery) |

**Important:** Per AMM installation drawings (24-31, 24-40, 24-60), the relay panel, battery, EPU plug, and battery relay are all co-located in the **aft fuselage**. GS-RP and the battery B1 negative terminal are adjacent, connected by short straps. The EPU negative connects to GS-RP, providing a parallel connection to the same aft ground network. See GPU ground test results in Owner Ground Tests section.

### Ground Path (Critical for Voltage Sensing)
The G1000 measures voltage at its power input pins **relative to its own ground pins**. The ground return path is now **fully documented** from the AMM CH.92 schematics:
```
G1000 GDU/GIA ground pins
  -> harness wires (20-22 AWG)
  -> Instrument Panel ground studs (GS-IP-xx series)
  -> GS-IP bus bar
  -> wire 24008A4N (4 AWG) -- dedicated ground return wire
  -> crosses firewall (continuous wire, no connector)
  -> Battery B1 negative terminal (aft fuselage)
```
**Source:** D44-9224-30-01X03 Sheet 1/1 (Electrical System, Conversion — p1859). Wire 24008A4N is a heavy 4 AWG negative wire providing a dedicated copper path from the GS-IP (Ground Stud - Instrument Panel) bus bar to the battery negative. This is NOT a structural ground through the fuselage — it is a wired return.

The relay panel components use separate ground studs (GS-RP series). Per AMM installation drawings (24-31, 24-40, 24-60), the **relay panel, battery, EPU plug, and battery relay are all co-located in the aft fuselage** — adjacent to each other. The alternator and starter grounds return through GS-RP. The battery B1 negative terminal connects to both GS-RP (short straps, same aft area) and GS-IP (instrument panel, via the long wire 24008A4N running the full length of the fuselage).

**Important correction:** The AE300 ECU (located under the pilot's seat) grounds to **GS-IP-3 and GS-IP-4** (per AMM p1936-1937, Drawing D44-9274-10-00), NOT GS-RP. This means the ECU shares the GS-IP bus bar, wire 24008A4N, and aft ground termination with the G1000 — and reads correctly. This proves the shared ground infrastructure is healthy and isolates the fault to the GEA 71S's specific ground connection at **GS-IP-14** (wire 77016A22N, P701 Pin 20).

### Alternator Voltage Regulation
The alternator regulator (J2424) has a **dedicated USENSE wire** (24022A22, 22 AWG, pin 5) for voltage sensing, separate from the G1000's measurement. This means:
- The alternator regulates to the correct voltage (confirmed by VDL48 reading ~28.3V)
- The G1000 reads low because of its own ground path, not because the bus is actually low
- The ECU (on ECU BUS, but grounding through GS-IP-3/GS-IP-4 per D44-9274-10-00) also reads near-correct voltage, proving the shared GS-IP bus bar and wire 24008A4N are healthy — the fault is specific to the GEA 71S ground at GS-IP-14

### Regulator Connections (D44-9224-30-01_02, p1858; D44-9224-30-05, p1861)
| Pin | Function | Wire |
|-----|----------|------|
| 5 | USENSE (Voltage Sense) | 24022A22 (22 AWG) |
| 7 | EXCITATION | 24017A20 (20 AWG) |
| 6 | SUPPLY | via supply circuit |
| 12 | LAMP | 31004A22 |
| 4 | GROUND | 24018A20N (20 AWG) |

### Where to Look for the Problem
The ECU grounds through GS-IP-3/GS-IP-4 (per D44-9274-10-00) and reads correctly, proving the shared GS-IP bus bar, wire 24008A4N, and aft termination are healthy. The fault is isolated to the GEA 71S's own connections. In order of priority:

1. **Pin 47 (ANALOG IN 5 LO) Essential Bus ground** — wire 31299A22BL (shielded) connects to the low side of the Essential Bus. The Electrical System schematic (D44-9224-30-01X03) shows a generic ground symbol — **the physical termination point is unknown and must be traced by the shop**. Since Pin 47 is the voltage measurement reference (GEA reads Pin 46 minus Pin 47), any resistance at this ground directly causes a low reading. This is the #1 suspect. **Note:** Other Diamond variant AMM wiring diagrams explicitly specify a ground stud (e.g. GS-IP-X) for this pin, but the DA40 NG schematic uses only a generic ground symbol — making this ground uniquely undocumented and difficult to troubleshoot.
2. **GS-IP-14 ground stud** — where GEA Pin 20 (POWER GROUND) terminates via wire 77016A22N. If the measurement is truly differential, Pin 20 may not directly affect the reading, but it could cause ADC common-mode issues if it floats too far.
3. **Wire 77016A22N** — from P701 Pin 20 to GS-IP-14. Corrosion, chafing, or bad crimp.
4. **GEA P701 connector** — Pin 47 and Pin 20 contacts specifically. Corrosion, loose pin, or poor contact at J701.

**Ruled out by ECU data** (ECU shares these and reads correctly):
- GS-IP bus bar connections
- Wire 24008A4N and its terminations at both ends
- Other GS-IP studs (GS-IP-3, GS-IP-4, GS-IP-6, etc.)

The AVIONIC BUS power path (25A breaker, relay contacts) could also contribute series resistance on the power side, but this would be a separate issue from the ground path.

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
- **Ruled out by R&R #2:** Firewall pass-through connectors, engine compartment ground straps — reconnected during R&R #2 with no improvement
- **Ruled out by ECU data:** GS-IP bus bar, wire 24008A4N, aft termination, GS-IP-3, GS-IP-4 — the ECU shares these (per D44-9274-10-00, p1936-1937) and reads correctly
- **Most likely:** GS-IP-14 stud, wire 77016A22N, or GEA P701 Pin 20 — the only components unique to the GEA 71S ground path, NOT disturbed during either R&R
- **Note:** The pitch servo (also worked during the Feb 2024 shop visit) is located under the seats, not in the instrument panel, so it would not have required access to instrument panel ground studs
- **Possible mechanism:** Something during the Feb 2024 shop visit disturbed the GEA 71S ground connection at GS-IP-14 or the P701 connector area

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
- Key insight: ECU grounds through GS-IP-3/GS-IP-4 (per D44-9274-10-00, p1936-1937) and reads correctly, proving the shared GS-IP bus bar and wire 24008A4N are healthy — fault is isolated to GEA 71S's own ground at GS-IP-14

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
- Extracted AMM pages 1908-1912 (Drawing D44-9231-60-03, G1000 NXi Phase III, Sheets 2/6-6/6) to `docs/`
- Processed 5100x3300 px schematics using parallel subagents to avoid API image dimension limits
- Catalogued all G1000 power ground connections by LRU, connector, pin, wire number, gauge, and ground stud
- **Key findings:**
  - **GS IP-6**: Both GIA 63W #1 (wire 23011A20N, pin 14 on 1P604) and GIA 63W #2 (wire 23001A20N, pin 14 on 2P604) share this single ground stud — the primary voltage sensors
  - **GS IP-4**: Most loaded stud — GDU 1050 PFD (31106A22N), GDU 1060 MFD (31158A22N), GMA 1360 (23201A20N), COM 1 (23001A20N) — 4 LRUs on one stud
  - **GS IP-5 (Ground Stud - Instrument Panel #5)**: Both GRS 79 AHRS units via GS AVB intermediate bus bar with 53V TVS diode protection
  - **GS IP-3 (Ground Stud - Instrument Panel #3)**: GPS/NAV 1 (34001A22N) + Wx 500 Stormscope (34402A20N)
  - **GS IP-10 (Ground Stud - Instrument Panel #10)**: GPS/NAV 2 (34101A22N) — isolated
  - **GS-IP-14**: GEA 71S Pin 20 POWER GROUND + Pin 45 ANALOG IN 4 LO (both wire 77016A22N) + Pin 49 current monitor (74005A22N) — all GEA ground pins terminate here
  - **GS IP-8 (Ground Stud - Instrument Panel #8)**: Config/power ground (31108A22N)
- Updated Ground Stud Groups section in README with complete wire-level LRU ground inventory
- Drawing reference: D44-9231-60-03, Doc 6.02.15, Rev. 5, 15 July 2024

### 2026-02-16: Owner Ground Test Documentation (Aug 2025 LOW VOLTS.docx)
- Source: `LOW VOLTS.docx` and associated PDFs from Premier Aircraft maintenance folder (Aug 2025)
- **Ground test (Aug 18, 2025):**
  - Open circuit battery: meter at AUX POWER reads 26.3V (100% charged per Concorde table)
  - G1000 powered up, no other loads: meter reads 25.2V, G1000 displays 23.7V → **1.5V offset on ground with battery only**
  - Premier mechanic Raymond independently confirmed same variance from cigarette lighter connector
- **FlySto LOW VOLTS events:** 18 sec, 85 sec, and 5 sec below 25V during landing/taxi phases
- **GEA 71B Analog In 5 configuration:** m=1.0000, b=0.0000, Filter=0.1000, Linear — no software correction applied
  - Confirms G1000 displays exactly what arrives at GEA input pin — the offset is hardware, not calibration
- **CALIBRATION ANALOG SENSOR PDF:** Discusses adjusting b (offset) to compensate, but this would be a band-aid
  - The offset is variable (-5.6V to +1.7V per VDL48 data), so a fixed b correction cannot work
  - Correct fix is repairing the ground path so m=1.0, b=0.0 reads correctly
- Added ground test results, FlySto LOW VOLTS events, and GEA 71B config to README
- Added Aug 18 ground test and Feb 2026 events to maintenance timeline

### 2026-02-16: Maintenance Guide (Standalone Troubleshooting Document)
- Created `MAINTENANCE_GUIDE.md` — focused, simplified document for the maintenance shop
- Written for mechanics who may not be strong with G1000/avionics
- Covers: problem statement, evidence summary, root cause explanation, specific inspection targets, resistance test procedure, verification criteria
- Consolidates all findings into actionable format without the statistical analysis detail
- Includes the ground stud inventory, LRU connector pin assignments, and resistance thresholds

### 2026-02-16: External Voltage Comparison (Diamond Aviators Forum)
- Forum post by geekmug (Scott), aircraft N541SA (DA40NG), on Diamond Aviators forum
- URL: https://www.diamondaviators.net/forum/viewtopic.php?p=108026#p108026
- FlySto graph from N541SA shows substantially more stable voltage than N238PS
- Confirms the G1000 is capable of reading steady, accurate voltage when ground paths are healthy
- Rules out Garmin firmware or sensor design as the cause — issue is aircraft-specific to N238PS
- Added to README as external comparison reference supporting the high-resistance ground hypothesis

### 2026-02-17: GEA 71 Pin Assignments & Current Sensing Analysis
- Extracted pages 23-26 from Garmin GEA 71 Installation Manual (190-00303-40, Rev F) as PNGs
- Documented complete P701 (78 pins) and P702 (78 pins) connector pin function lists
- Confirmed Pin 42/43 (ANALOG IN 3 HI/LO) = ALT AMPS SENSOR differential input
- Confirmed Pin 46/47 (ANALOG IN 5 HI/LO) = BUS VOLTS sense
- Confirmed Pin 14 = +10V transducer power for Hall-effect current sensor (J7700)
- Confirmed Pin 20 and Pin 78 = POWER GROUND (two ground pins, both route to GS-IP-14)
- Traced ALT AMPS SENSOR circuit: Hall-effect transducer with differential output, isolated from power ground — G1000 MFD amp reading is unaffected by the bad ground path
- Confirmed GEA 71S does not interface directly with ECU — engine data flows ECU → GIA (RS-232) → displays; GEA sends airframe data to GIAs via RS-485 (pins 5-8)
- G1000 CSV logs do not record amps (only volt1/volt2); ECU logs do not record aircraft electrical current (only fuel system solenoid currents)
- Added pin reference table to MAINTENANCE_GUIDE.md for mechanics working on the P701 connector
- Added complete pin assignments and ALT AMPS SENSOR circuit to CLAUDE.md

### 2026-02-20: Battery Ground Return Wire Discovery (D44-9224-30-01X03)
- Owner identified wire **24008A4N** (4 AWG, negative) on drawing D44-9224-30-01X03 Sheet 1/1 (Electrical System, Conversion — p1859)
- This wire provides a **dedicated copper ground return** from the GS-IP bus bar (instrument panel) to the main battery B1 negative terminal
- **Previously:** The path from GS-IP bus bar → battery negative was documented as "inferred — not on any AMM schematic" and assumed to be structural ground through the fuselage
- **Now:** The entire ground return path is documented as wired: GEA Pin 20 → 77016A22N (22 AWG) → GS-IP-14 → GS-IP bus bar → 24008A4N (4 AWG) → Battery B1 negative
- Wire 24008A4N crosses the firewall as a continuous wire (no connector visible on schematic) running from the instrument panel through the engine compartment to the battery
- Also visible on same drawing: wire 24008A10 (10 AWG, positive) runs the same route from IP to BATT BUS, and wire 24200A10 (10 AWG) to BATT BUS through a 50A fuse
- **Diagnostic implication:** The 4 AWG wire itself has negligible resistance (~0.25 mΩ/ft) — the problem must be at a terminal connection (GS-IP bus bar end, battery negative end, or GS-IP-14 stud)
- **R&R correlation:** Battery negative terminal is disturbed during every engine R&R but R&R #2 did not fix the problem — suggests the fault is at the GS-IP bus bar end (never disturbed during either R&R)
- Updated CLAUDE.md ground path section, README.md Mermaid diagrams and differential diagnosis, and MAINTENANCE_GUIDE.md documentation status and test procedure
- Added D44-9224-30-01X03 schematic image to MAINTENANCE_GUIDE.md
- Created `render_drawio.py` — parses `docs/GEA71S_voltage_path.drawio` XML and renders to PNG using matplotlib. Replaces manual Draw.io desktop export.
- Updated voltage measurement path diagram: ground path chain now solid (documented) with GS-IP Bus Bar, wire 24008A4N (4 AWG), Battery B1 Negative, and "per D44-9224-30-01X03" annotation

### 2026-02-20: ESS BUS Switch Test — Owner Verification
- Owner tested the ESS BUS switch on the aircraft (Feb 20, 2026)
- **Result:** MFD turned off, engine parameters moved to PFD (reversionary mode), but **no voltage indicator available on PFD**
- **Reason:** The G1000 voltage display is only on the MFD. When the ESS switch activates, the Avionic Bus loses power and the MFD goes dark. The GEA 71S stays powered (it's on the Essential Bus), but the voltage reading has no display path to the PFD in reversionary mode.
- **Updated MAINTENANCE_GUIDE.md:** ESS BUS switch test now requires a **multimeter on the Essential Bus** to provide the reference reading. Procedure revised to compare multimeter readings before/after ESS switch activation.

### 2026-02-20: GPU Ground Test & EPU Wiring Analysis
- Owner tested with external GPU connected through EPU plug (AN2551)
- **AUX POWER PLUG:** 28.79V, **G1000:** 28.6V → **only 0.19V offset** (vs 1.5V with battery Aug 2025, vs 1.4V average in flight)
- 0.19V is within normal measurement tolerance — essentially no fault signature
- Traced EPU wiring from D44-9224-30-01X03:
  - EPU positive: wire 24403A6 (6 AWG) → EPU RELAY → BATT BUS
  - EPU negative: wire **24405A6N** (6 AWG) → **GS-RP** (aft fuselage, adjacent to battery)
  - EPU jumper: wire 24401B22 → J2421 pin 4 → 24401A22 (triggers EPU relay)
- **Key finding:** Relay panel, battery, EPU plug, and battery relay are all co-located in the aft fuselage (per AMM 24-31, 24-40, 24-60 installation drawings). GS-RP and battery negative are adjacent — the GPU does NOT provide a significantly shorter alternate ground path. Near-zero offset (0.19V) is primarily because the intermittent fault is in good contact on the ground (no vibration), matching the shop's Feb 15 finding.
- Added AN2551 EPU plug PDF and AMM installation drawings to docs/
- Updated all documentation with GPU test results and corrected aft fuselage layout

### 2026-02-20: Fault Localization — ECU Ground Path & Pin 47 Sense Ground
- Owner asked whether battery negative terminal or GS-RP connection could be the fault (GPU test showing near-zero offset)
- Initially analyzed using Ohm's law assuming ECU grounds through GS-RP — but owner identified AMM p1936-1937 (Drawing D44-9274-10-00, EECU Wiring) showing **ECU grounds to GS-IP-3 and GS-IP-4**, NOT GS-RP
- **Critical correction:** ECU is under the pilot's seat and shares the GS-IP bus bar, wire 24008A4N, and aft ground termination with the G1000
- Since ECU reads correctly (~27.8V) through the same shared GS-IP infrastructure, the shared path is proven healthy
- Wire 24008A4N, GS-IP bus bar, and aft termination are ruled out (ECU uses them and reads correctly)
- **Key insight from owner:** The GEA voltage measurement is differential — Pin 46 (ANALOG IN 5 HI) minus Pin 47 (ANALOG IN 5 LO). Pin 47 is the actual voltage measurement reference, connecting to the low side of the Essential Bus. The Electrical System schematic (D44-9224-30-01X03) shows only a generic ground symbol at Pin 47's termination — **the physical location where wire 31299A22BL terminates is unknown**
- **Two primary suspects:** (1) Pin 47 Essential Bus ground — unknown termination point, directly affects reading; (2) GS-IP-14 / Pin 20 — GEA power ground, may affect reading through ADC common-mode issues
- **GPU bypass hypothesis (owner insight):** If Pin 47's ground is a structural/airframe ground (consistent with generic ground symbol), the GPU negative at GS-RP may provide a lower-impedance alternate return path. This would explain why GPU reads correctly (bypasses the degraded ground path to battery negative) while battery reads low. The GPU test is therefore **diagnostic**, not coincidental — it specifically supports Pin 47's ground as the fault.
- The ECU is unaffected because it uses a wired ground path (GS-IP-3/4 → GS-IP bus bar → 24008A4N) that doesn't depend on the same structural ground as Pin 47
- Added AMM ESS BUS switch operation description (24-60-00): OFF = power relay closes, ON = power relay opens + essential tie relay connects battery bus directly to essential bus
- Updated all documentation with corrected ECU ground path, Pin 47 analysis, GPU bypass hypothesis, and ESS BUS switch description

### 2026-02-20: G1000 System Maintenance Manual — CAUTION Alerts
- Owner added `docs/G100 System Maintenance Manaual DA40 - CAUTION ALERTS.png` — screenshot from Garmin G1000 System Maintenance Manual (190-00545-01) showing the CAUTION Alerts table
- **LOW VOLTS** entry: "On-board voltage is below 24 volts" → Solution: "Inspect GEA 71 connector & wiring. Troubleshoot aircraft electrical system according to DA 40 Airplane Maintenance Manual instructions."
- **Significance:** Garmin's own troubleshooting procedure names the GEA 71 connector & wiring as the **first** inspection target for LOW VOLTS — directly validates our entire analysis
- **24V threshold:** The G1000 LOW VOLTS annunciation triggers at 24V (FlySto uses a 25V threshold for its own alerts)
- Also added: `docs/24-31 Battery Installation.png`, `docs/24-40 External Power.png`, `docs/24-60 Battery Relay.png`, `docs/24-60 Relay Panel.png` — IPC diagrams showing battery area, EPU (External Power Unit) plug, and relay panel physical layouts
- Added image and reference to README.md (inline after Key Finding) and MAINTENANCE_GUIDE.md (new "Garmin's Prescribed Troubleshooting" subsection under The Problem, plus AMM References table)

### 2026-02-20: DA40 NG Pin 47 Ground — Undocumented vs Other Variants
- Owner observed that other Diamond variant AMM wiring diagrams explicitly specify a ground stud number (e.g. GS-IP-X) for the GEA voltage sense LO pin, but the DA40 NG schematic (D44-9231-60-03 / D44-9224-30-01X03) uses only a generic ground symbol
- This means a mechanic on another Diamond variant can look up the stud number and go inspect it directly, but on the DA40 NG there is no documented stud — the wire must be physically traced
- This likely explains why the ground path has never been found despite years of troubleshooting — it's not documented in the schematic
- Updated all three documents (CLAUDE.md Pin 47 table entry and Where to Look, README.md primary suspects section, MAINTENANCE_GUIDE.md suspects section and Where to Look inspection instructions)

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
