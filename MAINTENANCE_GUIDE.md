# N238PS — G1000 LOW VOLTS Troubleshooting Guide

**Aircraft:** N238PS (Diamond DA40NG, MAM40-858)
**Problem:** G1000 NXi displays lower voltage than actual bus voltage, causing intermittent LOW VOLTS annunciations
**Date:** February 2026
**Prepared by:** Aircraft Owner (Ingram Leedy)

---

## The Problem

The G1000 consistently reads **1–2 volts lower** than actual bus voltage, with transient dips up to **5.6 volts low** during high-current events. This causes false LOW VOLTS annunciations in flight even though the electrical system is charging normally.

## How We Know It's Real

Three independent measurements were taken on the same aircraft, on the same flights. Two agree. One doesn't.

| Source | Where It Measures | Average Reading | Verdict |
|--------|------------------|-----------------|---------|
| **VDL48 data logger** (plugged into AUX POWER) | HOT BUS — direct battery | **28.3V** | Correct |
| **ECU battery voltage** (engine computer) | ECU BUS — own ground to GS-RP | **27.8V** | Correct |
| **G1000 volt1** | AVIONIC BUS — ground through GS-IP studs | **26.9V** | **Reads low** |

The VDL48 and ECU agree — the bus voltage is normal (~28V with alternator). The G1000 is the only instrument reading low.

### Ground Test (Aug 18, 2025 — battery only, no engine)

| Condition | Meter at AUX POWER | G1000 Display | Difference |
|-----------|-------------------|---------------|------------|
| Master ON, G1000 on, no other loads | **25.2V** | **23.7V** | **-1.5V** |

The offset exists on the ground with battery only. This rules out the alternator, voltage regulator, and charging system entirely.

### Another DA40NG for Comparison (N541SA)

A FlySto voltage graph from another DA40NG (N541SA) shows rock-steady voltage at ~27.8V with barely any fluctuation. The G1000 is capable of reading stable, accurate voltage — the problem is specific to N238PS.

![N541SA voltage — stable](docs/N541SA_flysto_voltage.png)

### GEA 71B Configuration Confirms No Software Issue

The G1000 voltage channel (GEA 1, Analog In 5) is configured with:
- **Slope (m) = 1.0** and **Offset (b) = 0.0** — no software correction is applied
- The G1000 displays exactly what arrives at the GEA 71B input pin
- The offset is a **hardware voltage drop**, not a calibration or firmware problem
- Adjusting the offset (b) parameter would only mask the symptom — the underlying problem would remain and continue to degrade

## What's Causing It

**A high-resistance ground connection** somewhere in the G1000's ground return path.

The G1000 measures voltage at its power input pins **relative to its own ground pins**. If there's extra resistance in the ground path, current flowing through that resistance creates a voltage drop that only the G1000 sees:

```
V_displayed = V_actual - (I_load × R_bad_ground)
```

At 20 amps of avionics load, just **0.05 ohms** of extra ground resistance = **1.0 volt** of under-reading. That's all it takes.

### Why Only the G1000 Reads Low

The G1000 avionics ground through the **GS-IP** (Instrument Panel) ground studs, which take a long path through the instrument panel structure, fuselage, and firewall to reach the battery negative terminal.

The ECU and alternator ground through the **GS-RP** (Relay Panel) ground studs, which have a short, direct path to battery negative. That's why the ECU reads correctly.

```
G1000 → GS-IP studs → IP bus bar → IP structure → fuselage → battery negative
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                        HIGH RESISTANCE somewhere in here

ECU   → GS-RP studs → short ground strap → battery negative  (reads correctly)
```

## When the Problem Started

Statistical analysis of **184 flight logs** (Jul 2023 – Feb 2026) detected a change-point on **February 29, 2024** (p < 0.001). This aligns exactly with the **engine R&R for oil leak repair** on February 28, 2024.

| Period | Mean G1000 Voltage | Voltage Noise |
|--------|-------------------|---------------|
| Before engine R&R (53 flights) | 27.44V | 0.25V |
| After engine R&R (131 flights) | 26.90V | 0.39V |
| **Change** | **-0.54V** | **+55% noisier** |

The ECU voltage did NOT change — it reads a steady 27.82V throughout the entire period. The problem is G1000-specific and was introduced during the Feb 2024 shop visit.

A second engine R&R in Jul 2025 (piston crack) did **not** fix the problem, ruling out the firewall pass-through connectors (which were reconnected during that work).

## What Has Already Been Tried (and didn't fix it)

| Date | Action | Result |
|------|--------|--------|
| Mar 2024 | Replaced alternator #2 | No improvement |
| Apr 2024 | Replaced voltage regulator | No improvement |
| Jun 2024 | Replaced voltage regulator again + repaired wire at P2208 | No improvement |
| Jul 2024 | Replaced P2413 connector (repinned HSDB harness) | No improvement |
| Feb 2025 | Replaced main alternator AND voltage regulator (3rd time) | No improvement |
| Jul 2025 | Engine R&R #2 + new battery | No improvement |
| Feb 2026 | Cleaned GDL 69A pins (CH.23) | No improvement — wrong unit |

None of these addressed the ground path. The alternator and regulators were never the problem — the ECU confirms the charging system works correctly.

The Feb 2026 pin cleaning targeted the **GDL 69A** (SiriusXM datalink transceiver, CH.23). The voltage measurement comes from the **GIA 63W** and **GEA 71B** — those connectors and ground pins were not inspected.

## Where to Look

### Ground Stud Locations (GS-IP Series)

All G1000 components ground to the **GS-IP** (Instrument Panel) ground stud group. These are the specific studs and what's connected to each:

| Ground Stud | What's Connected | Priority |
|-------------|-----------------|----------|
| **GS IP-6** | GIA 63W #1 (wire 23011A20N, 20 AWG) + GIA 63W #2 (wire 23001A20N, 20 AWG) | **CHECK FIRST** — both avionics computers share this one stud |
| **GS IP-4** | GDU 1050 PFD + GDU 1060 MFD + GEA 71S + GMA 1360 Audio + COM 1 (5 LRUs!) | **CHECK SECOND** — most heavily loaded stud |
| **GS IP-5** | GRS 79 AHRS #1 + AHRS #2 (via GS AVB bus bar) | Check third |
| **GS IP-3** | GPS/NAV 1 + Wx 500 Stormscope | Check fourth |
| **GS IP-10** | GPS/NAV 2 | Lower priority |

### What to Look For at Each Ground Stud

- Loose nut (vibration loosens over time)
- Corrosion under the ring terminal (green/white buildup)
- Paint, primer, or anodize between the ring terminal and the stud surface
- Cracked or deformed ring terminal
- Multiple ring terminals stacked on one stud not all making good contact
- Lock washer missing or flattened

### LRU Connectors to Inspect

The voltage reading comes through these specific units. Their ground pins are the most critical:

| Unit | Connector | Ground Pin | Wire | What It Does |
|------|-----------|-----------|------|-------------|
| **GIA 63W #1** | 1P604 | Pin 14 (POWER GROUND) | 23011A20N (20 AWG) | Primary avionics computer — **this is the voltage sensor** |
| **GIA 63W #2** | 2P604 | Pin 14 (POWER GROUND) | 23001A20N (20 AWG) | Redundant avionics computer |
| **GEA 71B** | P701 | Pin 36 (POWER GROUND) | 77015A22N (22 AWG) | Engine/airframe unit — processes the voltage reading for display |
| **GDU 1050 PFD** | 1P1600 | Pin 27 (POWER GROUND) | 31106A22N (22 AWG) | Primary flight display |
| **GDU 1060 MFD** | 2P1601 | Pin 27 (POWER GROUND) | 31158A22N (22 AWG) | Multi-function display |

**At each connector, check for:**
- Backed-out pins (look from the rear of the connector)
- Corrosion on pin or socket contacts
- Connector not fully seated or lock not engaged
- Damaged strain relief (wires pulling on connector)

### Ground Bus Bar

The GS-IP studs connect to a ground bus bar mounted on the instrument panel frame. Check:
- Bus bar mounting bolts tight
- Clean metal-to-metal contact between bus bar and IP frame
- No cracks in the bus bar

### IP Frame to Fuselage Bond

The instrument panel frame connects to the fuselage structure. Check:
- Bonding strap present and tight (if required by AMM)
- No paint between bonding surfaces
- Metal-to-metal contact confirmed

## How to Test

### Resistance Measurements

**Setup:** Battery master OFF, battery negative cable disconnected. Use a digital multimeter on the lowest ohm range (milliohm mode preferred). Subtract lead resistance first (short the leads together and note the reading).

| Test | From | To | Expected | If High |
|------|------|----|----------|---------|
| **1. End-to-end** | GIA 63W ground pin (at 1P604 pin 14) | Battery negative terminal | **< 0.050 Ω** | Confirms ground path problem — continue testing |
| **2. Fuselage path** | Bare fuselage metal near IP | Battery negative post | < 0.010 Ω | Check battery cable, fuselage ground point |
| **3. IP-to-fuselage** | IP frame metal | Bare fuselage metal | < 0.005 Ω | Check bonding strap, IP mounting |
| **4. Each GS-IP stud** | Each GS-IP stud terminal | IP frame metal | < 0.005 Ω | Clean and retorque that stud |
| **5. Each LRU ground** | LRU ground pin (at connector) | Its GS-IP stud | < 0.010 Ω | Check connector pin, harness wire, crimp |

### What the Numbers Mean

| End-to-End Resistance | Voltage Drop at 20A | What It Means |
|----------------------|---------------------|---------------|
| < 0.010 Ω | < 0.2V | Normal — clean ground path |
| 0.010 – 0.025 Ω | 0.2 – 0.5V | Marginal — may worsen with vibration |
| 0.025 – 0.050 Ω | 0.5 – 1.0V | Degraded — consistent with the ~1.4V average offset we measured |
| 0.050 – 0.100 Ω | 1.0 – 2.0V | Failed — consistent with the -5.6V worst-case dips |
| > 0.100 Ω | > 2.0V | Severe |

**We estimate the total ground path resistance is approximately 0.05–0.09 ohms** based on the observed voltage offsets and typical avionics current draw.

## How to Verify the Fix

A ground test alone cannot reproduce the problem reliably. The offset is worse in flight due to vibration and thermal effects on the bad connection.

**After repair:**
1. Repeat the end-to-end resistance measurement — should be < 0.010 Ω
2. Power on avionics and check G1000 voltage reads within 0.3V of a meter at the AUX POWER plug
3. **Flight test with VDL48** (same test setup as our Feb 8 analysis):
   - Install VDL48 on AUX POWER plug
   - Fly at least 30 minutes with varied loads (radio TX, autopilot, flaps)
   - Compare G1000 log vs VDL48 log
   - **Pass:** Mean offset < 0.3V, no dips > 1.0V, noise < 0.30V
   - The analysis scripts in this repository can process the data automatically

## AMM References

| Reference | Content |
|-----------|---------|
| AMM 24-60-00 | Bus structure, power distribution, troubleshooting table |
| AMM CH.92, D44-9224-30-01 through -05 | Electrical system wiring diagrams (power distribution) |
| AMM CH.92, D44-9231-60-03_01 | G1000 NXi wiring diagrams (Sheets 2-6, pages 1908-1912) |
| AMM CH.31 | GDU 1050/1060 connector pinouts |
| AMM CH.34 | GIA 63W connector pinouts |
| AMM CH.23 | GMA, GTX, GDL connector pinouts |

## Summary

The G1000 reads low because of a high-resistance ground connection — not a calibration issue, not a charging system issue, not a firmware issue. The problem started during the Feb 2024 engine R&R shop visit. Three voltage regulators and two alternators have been replaced unnecessarily. The fix is to find and repair the bad ground connection, most likely at a **GS-IP ground stud** or **LRU connector ground pin** behind the instrument panel.
