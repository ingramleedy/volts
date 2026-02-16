# N238PS — G1000 LOW VOLTS Troubleshooting Guide

**Aircraft:** N238PS (Diamond DA40NG, MAM40-858)
**Problem:** G1000 NXi displays lower voltage than actual bus voltage, causing intermittent LOW VOLTS annunciations
**Date:** February 2026
**Prepared by:** Aircraft Owner (Ingram Leedy)

---

## The Problem

The G1000 consistently reads **1–2 volts lower** than actual bus voltage, with transient dips up to **5.6 volts low** during high-current events. This causes false LOW VOLTS annunciations in flight even though the electrical system is charging normally.

### FlySto LOW VOLTS Events (In-Flight)

These FlySto screenshots show actual LOW VOLTS events captured from G1000 flight logs. The voltage drops below the 25V threshold repeatedly during normal flight operations:

**85 seconds below 25V** — approach and taxi at KBOW, voltage swinging wildly between 24–27V:

![LOW VOLTS event — 85 sec below 25V during approach/taxi](docs/lowvolts_page3_img2.jpeg)

**18 seconds below 25V** — during landing, and **5 seconds below 25V** — at altitude during cruise:

![LOW VOLTS events — 18 sec and 5 sec below 25V](docs/lowvolts_page3_img1.jpeg)

These dips are **not real** — the independent VDL48 logger shows the bus voltage is steady at ~28V during these same periods. The G1000 is the only instrument seeing these drops.

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

Statistical analysis of **184 flight logs** (Jul 2023 – Feb 2026) detected a change-point on **February 29, 2024** (p < 0.001). This aligns exactly with the **Feb 2024 shop visit**.

| Period | Mean G1000 Voltage | Voltage Noise |
|--------|-------------------|---------------|
| Before shop visit (53 flights) | 27.44V | 0.25V |
| After shop visit (131 flights) | 26.90V | 0.39V |
| **Change** | **-0.54V** | **+55% noisier** |

The ECU voltage did NOT change — it reads a steady 27.82V throughout the entire period. The problem is G1000-specific and was introduced during the Feb 2024 shop visit.

### What Happened During That Shop Visit (Feb 2024)

The engine R&R (oil leak) was not the only work performed. During the same visit:

1. **Engine removed and reinstalled** — oil sump gasket and cylinder head cover (firewall connectors disconnected/reconnected)
2. **Alternator #2 replaced** — the RACC (AC system) wasn't turning on and wasn't getting power to the AUX switch
3. **RACC relay troubleshooting** — relays in the **aft avionics bay** were inspected to diagnose the RACC power issue
4. **GSA 91 pitch servo replaced** — autopilot pitch servo (also in the aft area)

**This is critical:** The G1000 avionics rack (GIA 63W, GEA 71B, GRS 79, etc.) is mounted in the **aft avionics bay, near the battery**. While troubleshooting the RACC relays in that same bay, someone likely bumped, loosened, or failed to fully reseat a G1000 ground connection. The RACC got fixed, the engine went back on, and nobody noticed the G1000 was now reading a volt low.

A second engine R&R in Jul 2025 (piston crack) did **not** fix the problem, ruling out the firewall pass-through connectors (which were reconnected during that work). The GSA 91 pitch servo was also replaced a second time — also with no improvement.

## What Has Already Been Tried (and didn't fix it)

| Date | Action | Result |
|------|--------|--------|
| Feb 2024 | Replaced alternator #2 (RACC) + RACC relay troubleshooting | Fixed RACC — but G1000 voltage problem started here |
| Feb 2024 | Replaced GSA 91 pitch servo | No improvement on voltage |
| Apr 2024 | Replaced voltage regulator | No improvement |
| Jun 2024 | Replaced voltage regulator again + repaired wire at P2208 | No improvement |
| Jul 2024 | Replaced P2413 connector (repinned HSDB harness) | No improvement |
| Feb 2025 | Replaced main alternator AND voltage regulator (3rd time) | No improvement |
| Jul 2025 | Engine R&R #2 + new battery + GSA 91 pitch servo replaced again | No improvement |
| Feb 2026 | Cleaned GDL 69A pins (CH.23) | No improvement — wrong unit |

None of these addressed the ground path. The alternator and regulators were never the problem — the ECU confirms the charging system works correctly.

The Feb 2026 pin cleaning targeted the **GDL 69A** (SiriusXM datalink transceiver, CH.23). The voltage measurement comes from the **GIA 63W** and **GEA 71B** — those connectors and ground pins were not inspected.

## Where to Look

### Aft Avionics Bay (CHECK FIRST)

The G1000 LRU rack (GIA 63W, GEA 71B, GRS 79, etc.) is mounted in the **aft avionics bay near the battery**. This is the same area where RACC relays were troubleshot during the Feb 2024 shop visit — someone was working right on top of the G1000 units when the problem started.

**Inspect in the aft bay:**
- All G1000 LRU connectors on the rack — are they fully seated with locks engaged?
- Ground connections on or near the avionics rack mounting
- Any ground studs in the aft bay where G1000 harnesses terminate
- Look for anything that appears disturbed, loose, or not fully reconnected
- Check for tools marks, scuffing, or signs that connectors were pulled and reseated

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

**Setup:** Battery master OFF, **battery negative cable physically disconnected from the battery post**.

**Why disconnect the battery?** A multimeter in ohms mode works by pushing a tiny known current through its probes and measuring the voltage drop. If the battery is still connected:
- The battery's 28V overwhelms the meter's test signal — you get garbage readings
- On milliohm ranges, external voltage can damage the meter
- Current can flow through other powered paths (relays, avionics), making a bad connection appear good

Battery master OFF alone is not enough — the HOT BUS and BATT BUS remain live. Disconnecting the negative cable physically isolates the battery so the meter reads only the wire and connection resistance.

**Meter setup:** Use a digital multimeter on the lowest ohm range (milliohm mode preferred). Before testing, short the two leads together and note the reading — subtract this lead resistance from all measurements.

| Test | From | To | Expected | If High |
|------|------|----|----------|---------|
| **1. End-to-end** | GIA 63W ground pin (at 1P604 pin 14) | Battery negative terminal | **< 0.050 Ω** | Confirms ground path problem — continue testing |
| **2. Fuselage path** | Bare fuselage metal near IP | Battery negative post | < 0.010 Ω | Check battery cable, fuselage ground point |
| **3. IP-to-fuselage** | IP frame metal | Bare fuselage metal | < 0.005 Ω | Check bonding strap, IP mounting |
| **4. Each GS-IP stud** | Each GS-IP stud terminal | IP frame metal | < 0.005 Ω | Clean and retorque that stud |
| **5. Each LRU ground** | LRU ground pin (at connector) | Its GS-IP stud | < 0.010 Ω | Check connector pin, harness wire, crimp |

### Where to Put the Probes (Step by Step)

**Test 1 — End-to-End (most important, do this first):**
- **Red probe:** Touch the back of **pin 14** on connector 1P604 (the aircraft-side harness connector for GIA 63W #1). If the connector is mated to the unit, you'll need to back-probe or disconnect it to access the pin.
- **Black probe:** Touch the **battery negative terminal post** — the bolt on the battery itself, not the cable end.
- This measures the entire ground path at once. If it reads good (< 0.050 Ω), the ground path is fine and the problem is elsewhere. If high, continue with Tests 2–5 to find which segment has the resistance.

**Test 2 — Fuselage Path:**
- **Red probe:** Bare/scraped fuselage metal **near the instrument panel** — find an unpainted screw head or lightly sand a small spot to get bare metal contact.
- **Black probe:** **Battery negative terminal post.**
- Tests the fuselage structure itself as a conductor from front to back.

**Test 3 — IP Frame to Fuselage:**
- **Red probe:** Bare metal on the **instrument panel frame** — the structural part the ground studs are mounted to.
- **Black probe:** Bare **fuselage metal** nearby (same spot from Test 2).
- If this reads high, the bonding strap between the IP frame and fuselage is the problem.

**Test 4 — Each GS-IP Ground Stud:**
- **Red probe:** The **nut/terminal surface** of each GS-IP stud — where the ring terminals are stacked.
- **Black probe:** Bare **IP frame metal** right next to that stud.
- Test each stud individually: GS IP-6, GS IP-4, GS IP-5, GS IP-3, GS IP-10. If one reads high while others read near-zero, that's your culprit — clean all surfaces and retorque.

**Test 5 — Each LRU Ground Wire:**
- **Red probe:** The **ground pin** at the aircraft-side harness connector (e.g., pin 14 on 1P604 for GIA 63W #1).
- **Black probe:** The **GS-IP stud** that wire runs to (GS IP-6 for both GIA 63W units).
- Tests the wire, crimp, and connector pin between the LRU and its ground stud.

### Isolation Strategy

Start with **Test 1**. If high, the bad segment will stand out — everything else reads near-zero while the problem connection shows the bulk of the resistance. Work through Tests 2–5 in order to narrow down which segment carries the extra resistance.

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

The G1000 reads low because of a high-resistance ground connection — not a calibration issue, not a charging system issue, not a firmware issue. The problem started during the Feb 2024 shop visit when the engine was removed for an oil leak AND the RACC relays were troubleshot in the aft avionics bay — the same bay where the G1000 rack is mounted. Three voltage regulators, two alternators, and two pitch servos have been replaced unnecessarily. The fix is to find and repair the bad ground connection, most likely at a **G1000 LRU connector or ground point in the aft avionics bay**, or at a **GS-IP ground stud**.
