#!/usr/bin/env python3
"""
Annotate AMM electrical schematics with highlighted G1000 ground path
inspection areas, color-coded by compartment and priority.

Produces:
  output/bus_structure_annotated.png   - AMM 24-60-00 Figure 1 with highlights
  output/wiring_diagram_annotated.png  - AMM CH.92 D44-9224-30-01 with highlights
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
from PIL import Image


def annotate_bus_structure():
    """Annotate the bus structure diagram (p622) with G1000 ground path highlights."""
    img = Image.open('docs/AMM_p622_24-60-00_Bus_Structure_G1000.png')
    w, h = img.size  # 1224 x 1584

    fig, ax = plt.subplots(1, 1, figsize=(w / 100, h / 100), dpi=150)
    ax.imshow(np.array(img), extent=[0, w, h, 0])
    ax.set_xlim(0, w)
    ax.set_ylim(h, 0)
    ax.axis('off')

    # ---- COMPARTMENT HIGHLIGHTS ----
    # Instrument Panel zone (left side of dashed line)
    ip_rect = mpatches.FancyBboxPatch(
        (30, 90), 540, 1020,
        boxstyle="round,pad=10", linewidth=3,
        edgecolor='#dc3545', facecolor='#dc354520',
        linestyle='--', zorder=2
    )
    ax.add_patch(ip_rect)

    # Engine Compartment zone (right side of dashed line)
    ec_rect = mpatches.FancyBboxPatch(
        (590, 90), 590, 600,
        boxstyle="round,pad=10", linewidth=3,
        edgecolor='#ff9800', facecolor='#ff980020',
        linestyle='--', zorder=2
    )
    ax.add_patch(ec_rect)

    # Fuselage zone (right side, lower)
    fu_rect = mpatches.FancyBboxPatch(
        (590, 700), 590, 420,
        boxstyle="round,pad=10", linewidth=3,
        edgecolor='#ffc107', facecolor='#ffc10720',
        linestyle='--', zorder=2
    )
    ax.add_patch(fu_rect)

    # ---- AVIONIC BUS PATH HIGHLIGHT (G1000 power source) ----
    # AV.BUS 25A CB → Avionic Relay → AVIONIC BUS
    # Draw a thick red path along the avionic bus line
    ax.annotate('',
                xy=(80, 175), xytext=(80, 245),
                arrowprops=dict(arrowstyle='->', color='#dc3545',
                                lw=4, connectionstyle='arc3,rad=0'))

    # Highlight circle on AV.BUS 25A breaker
    avbus_circle = plt.Circle((95, 200), 30, linewidth=3,
                               edgecolor='#dc3545', facecolor='#dc354540', zorder=3)
    ax.add_patch(avbus_circle)

    # Highlight circle on Avionic Relay
    avrelay_circle = plt.Circle((175, 165), 40, linewidth=3,
                                 edgecolor='#dc3545', facecolor='#dc354540', zorder=3)
    ax.add_patch(avrelay_circle)

    # ---- GROUND PATH ANNOTATION (not shown in original diagram) ----
    # Add a text box showing the invisible ground return path
    ground_text = (
        "G1000 GROUND RETURN PATH\n"
        "(not shown in bus diagram)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "G1000 LRU GND pins\n"
        "  ↓ 22 AWG harness wires\n"
        "GS-IP ground studs\n"
        "  ↓ ring terminals\n"
        "Ground bus bar\n"
        "  ↓ bolted to IP frame\n"
        "IP structure → fuselage\n"
        "  ↓ structural bond\n"
        "Fuselage → firewall\n"
        "  ↓ bonding strap\n"
        "Battery negative terminal"
    )
    ax.text(30, 1200, ground_text, fontsize=6.5, fontfamily='monospace',
            verticalalignment='top',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#fff3cd',
                      edgecolor='#dc3545', linewidth=2, alpha=0.95),
            zorder=5)

    # ---- INSPECTION CALLOUTS ----
    # AVIONIC BUS - G1000 is on this bus
    ax.annotate('G1000 on\nAVIONIC BUS',
                xy=(250, 155), xytext=(350, 100),
                fontsize=7, fontweight='bold', color='#dc3545',
                arrowprops=dict(arrowstyle='->', color='#dc3545', lw=2),
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                          edgecolor='#dc3545', linewidth=2),
                zorder=5)

    # Essential Tie Relay - affects ESSENTIAL BUS path
    ax.annotate('CHECK:\nAV.BUS 25A CB\ncontact resistance',
                xy=(95, 200), xytext=(250, 275),
                fontsize=6, fontweight='bold', color='#dc3545',
                arrowprops=dict(arrowstyle='->', color='#dc3545', lw=1.5),
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                          edgecolor='#dc3545', linewidth=1.5),
                zorder=5)

    # Avionic relay contacts
    ax.annotate('CHECK:\nAvionic Relay\ncontact resistance',
                xy=(175, 165), xytext=(350, 190),
                fontsize=6, fontweight='bold', color='#dc3545',
                arrowprops=dict(arrowstyle='->', color='#dc3545', lw=1.5),
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                          edgecolor='#dc3545', linewidth=1.5),
                zorder=5)

    # Engine compartment - alternator area
    ax.annotate('R&R #1: Oil leak repair\nCyl head cover + oil sump\nCHECK: disturbed wiring',
                xy=(780, 200), xytext=(830, 350),
                fontsize=6, fontweight='bold', color='#ff9800',
                arrowprops=dict(arrowstyle='->', color='#ff9800', lw=1.5),
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                          edgecolor='#ff9800', linewidth=1.5),
                zorder=5)

    # ECU reads correctly callout
    ax.annotate('ECU reads CORRECTLY\n→ GS-RP ground OK\n→ Charging system OK',
                xy=(760, 470), xytext=(830, 550),
                fontsize=6, fontweight='bold', color='#28a745',
                arrowprops=dict(arrowstyle='->', color='#28a745', lw=1.5),
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#d4edda',
                          edgecolor='#28a745', linewidth=1.5),
                zorder=5)

    # Fuselage ground path
    ax.annotate('CHECK: Fuselage\nground path continuity\nIP → firewall → battery neg',
                xy=(780, 850), xytext=(830, 780),
                fontsize=6, fontweight='bold', color='#e6a817',
                arrowprops=dict(arrowstyle='->', color='#e6a817', lw=1.5),
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                          edgecolor='#e6a817', linewidth=1.5),
                zorder=5)

    # ---- LEGEND ----
    legend_elements = [
        mpatches.Patch(facecolor='#dc354540', edgecolor='#dc3545',
                       linewidth=2, label='INSTRUMENT PANEL (Highest Priority)'),
        mpatches.Patch(facecolor='#ff980040', edgecolor='#ff9800',
                       linewidth=2, label='ENGINE COMPARTMENT (R&R #1 Suspect)'),
        mpatches.Patch(facecolor='#ffc10740', edgecolor='#ffc107',
                       linewidth=2, label='FUSELAGE (Medium Priority)'),
        mpatches.Patch(facecolor='#28a74540', edgecolor='#28a745',
                       linewidth=2, label='RELAY PANEL / ECU (Reads Correctly)'),
    ]
    ax.legend(handles=legend_elements, loc='lower right', fontsize=7,
              framealpha=0.95, edgecolor='black', fancybox=True,
              bbox_to_anchor=(0.98, 0.02))

    # Title
    ax.set_title('AMM 24-60-00 Figure 1 — Annotated for G1000 Ground Path Inspection',
                 fontsize=10, fontweight='bold', pad=5)

    plt.tight_layout()
    plt.savefig('output/bus_structure_annotated.png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close()
    print('Saved: output/bus_structure_annotated.png')


def annotate_wiring_diagram():
    """Annotate the main wiring diagram (p1857) with ground path highlights."""
    img = Image.open('docs/AMM_p1857_D44-9224-30-01_Electrical_System.png')
    w, h = img.size  # 5100 x 3300

    fig, ax = plt.subplots(1, 1, figsize=(w / 150, h / 150), dpi=200)
    ax.imshow(np.array(img), extent=[0, w, h, 0])
    ax.set_xlim(0, w)
    ax.set_ylim(h, 0)
    ax.axis('off')

    # ---- COMPARTMENT ZONE OVERLAYS ----
    # Instrument Panel zone (left portion)
    ip_rect = mpatches.FancyBboxPatch(
        (50, 200), 2450, 2750,
        boxstyle="round,pad=20", linewidth=4,
        edgecolor='#dc3545', facecolor='#dc354512',
        linestyle='--', zorder=2
    )
    ax.add_patch(ip_rect)

    # Engine Compartment zone (upper right)
    ec_rect = mpatches.FancyBboxPatch(
        (2550, 200), 2450, 1400,
        boxstyle="round,pad=20", linewidth=4,
        edgecolor='#ff9800', facecolor='#ff980012',
        linestyle='--', zorder=2
    )
    ax.add_patch(ec_rect)

    # Fuselage zone (lower right)
    fu_rect = mpatches.FancyBboxPatch(
        (2550, 1650), 2450, 1300,
        boxstyle="round,pad=20", linewidth=4,
        edgecolor='#ffc107', facecolor='#ffc10712',
        linestyle='--', zorder=2
    )
    ax.add_patch(fu_rect)

    # ---- GROUND STUD GROUP HIGHLIGHTS ----
    # GS-IP area (instrument panel ground studs) - bottom of IP section
    gsip_rect = mpatches.FancyBboxPatch(
        (100, 2550), 800, 350,
        boxstyle="round,pad=10", linewidth=4,
        edgecolor='#dc3545', facecolor='#dc354530',
        zorder=3
    )
    ax.add_patch(gsip_rect)
    ax.text(500, 2560, 'GS-IP GROUND STUDS\n(INSPECT FIRST)', fontsize=9,
            fontweight='bold', color='#dc3545', ha='center', va='top',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                      edgecolor='#dc3545', linewidth=2, alpha=0.9),
            zorder=5)

    # GS-RP area (relay panel ground studs) - engine compartment side
    gsrp_rect = mpatches.FancyBboxPatch(
        (2600, 2550), 800, 350,
        boxstyle="round,pad=10", linewidth=4,
        edgecolor='#28a745', facecolor='#28a74530',
        zorder=3
    )
    ax.add_patch(gsrp_rect)
    ax.text(3000, 2560, 'GS-RP GROUND STUDS\n(ECU here — reads OK)', fontsize=9,
            fontweight='bold', color='#28a745', ha='center', va='top',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#d4edda',
                      edgecolor='#28a745', linewidth=2, alpha=0.9),
            zorder=5)

    # ---- KEY COMPONENT HIGHLIGHTS ----
    # Avionic Relay area
    ax.annotate('AVIONIC RELAY\nCHECK: contact resistance',
                xy=(700, 600), xytext=(200, 400),
                fontsize=8, fontweight='bold', color='#dc3545',
                arrowprops=dict(arrowstyle='->', color='#dc3545', lw=2),
                bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                          edgecolor='#dc3545', linewidth=2),
                zorder=5)

    # AV.BUS circuit breaker
    ax.annotate('AV.BUS 25A CB\nCHECK: contact resistance',
                xy=(400, 550), xytext=(200, 700),
                fontsize=8, fontweight='bold', color='#dc3545',
                arrowprops=dict(arrowstyle='->', color='#dc3545', lw=2),
                bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                          edgecolor='#dc3545', linewidth=2),
                zorder=5)

    # Firewall area
    ax.annotate('FIREWALL AREA\nCHECK: bonding straps\nground feedthrough\nharness grommets',
                xy=(2550, 1500), xytext=(2000, 1700),
                fontsize=8, fontweight='bold', color='#ff9800',
                arrowprops=dict(arrowstyle='->', color='#ff9800', lw=2),
                bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                          edgecolor='#ff9800', linewidth=2),
                zorder=5)

    # Engine area - R&R #1 specific
    ax.annotate('R&R #1 OIL LEAK REPAIR\nCyl head cover + oil sump\nCHECK: harness routing\nnear these work areas',
                xy=(3800, 600), xytext=(3800, 350),
                fontsize=8, fontweight='bold', color='#ff9800',
                arrowprops=dict(arrowstyle='->', color='#ff9800', lw=2),
                bbox=dict(boxstyle='round,pad=0.4', facecolor='#ffe0b2',
                          edgecolor='#ff9800', linewidth=2),
                zorder=5)

    # Battery area
    ax.annotate('BATTERY NEG TERMINAL\nCHECK: clean, tight',
                xy=(4500, 2200), xytext=(4200, 2500),
                fontsize=8, fontweight='bold', color='#ffc107',
                arrowprops=dict(arrowstyle='->', color='#e6a817', lw=2),
                bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                          edgecolor='#e6a817', linewidth=2),
                zorder=5)

    # ---- GROUND PATH FLOW ANNOTATION ----
    ground_text = (
        "G1000 GROUND RETURN PATH\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "1. G1000 LRU GND pins (IP)\n"
        "2. 22 AWG harness wires (IP)\n"
        "3. GS-IP ground studs (IP)\n"
        "4. Ground bus bar (IP)\n"
        "5. IP frame → fuselage bond\n"
        "6. Fuselage → firewall → batt neg\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Fault: ~0.05-0.09 Ω somewhere\n"
        "in this path = 1.4V drop"
    )
    ax.text(100, 300, ground_text, fontsize=8, fontfamily='monospace',
            verticalalignment='top',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#fff3cd',
                      edgecolor='#dc3545', linewidth=3, alpha=0.95),
            zorder=5)

    # ---- LEGEND ----
    legend_elements = [
        mpatches.Patch(facecolor='#dc354530', edgecolor='#dc3545',
                       linewidth=2, label='INSTRUMENT PANEL — Highest Priority'),
        mpatches.Patch(facecolor='#ff980030', edgecolor='#ff9800',
                       linewidth=2, label='ENGINE COMPARTMENT — R&R #1 Suspect'),
        mpatches.Patch(facecolor='#ffc10730', edgecolor='#ffc107',
                       linewidth=2, label='FUSELAGE — Medium Priority'),
        mpatches.Patch(facecolor='#28a74530', edgecolor='#28a745',
                       linewidth=2, label='GS-RP / ECU — Reads Correctly'),
    ]
    ax.legend(handles=legend_elements, loc='lower left', fontsize=8,
              framealpha=0.95, edgecolor='black', fancybox=True,
              bbox_to_anchor=(0.02, 0.02))

    ax.set_title('AMM CH.92 D44-9224-30-01 — Annotated for G1000 Ground Path Inspection',
                 fontsize=12, fontweight='bold', pad=8)

    plt.tight_layout()
    plt.savefig('output/wiring_diagram_annotated.png', dpi=200, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close()
    print('Saved: output/wiring_diagram_annotated.png')


def annotate_wiring_detail():
    """Annotate the wiring detail diagram (p1858) with ground path highlights."""
    img = Image.open('docs/AMM_p1858_D44-9224-30-01_02_Electrical_System_Wiring.png')
    w, h = img.size  # 5100 x 3300

    fig, ax = plt.subplots(1, 1, figsize=(w / 150, h / 150), dpi=200)
    ax.imshow(np.array(img), extent=[0, w, h, 0])
    ax.set_xlim(0, w)
    ax.set_ylim(h, 0)
    ax.axis('off')

    # ---- COMPARTMENT ZONE OVERLAYS ----
    # Instrument Panel zone
    ip_rect = mpatches.FancyBboxPatch(
        (50, 200), 2450, 2750,
        boxstyle="round,pad=20", linewidth=4,
        edgecolor='#dc3545', facecolor='#dc354512',
        linestyle='--', zorder=2
    )
    ax.add_patch(ip_rect)

    # Engine Compartment zone
    ec_rect = mpatches.FancyBboxPatch(
        (2550, 200), 2450, 1400,
        boxstyle="round,pad=20", linewidth=4,
        edgecolor='#ff9800', facecolor='#ff980012',
        linestyle='--', zorder=2
    )
    ax.add_patch(ec_rect)

    # Fuselage zone
    fu_rect = mpatches.FancyBboxPatch(
        (2550, 1650), 2450, 1300,
        boxstyle="round,pad=20", linewidth=4,
        edgecolor='#ffc107', facecolor='#ffc10712',
        linestyle='--', zorder=2
    )
    ax.add_patch(fu_rect)

    # ---- KEY INSPECTION POINTS ----
    # Ground studs - IP side
    ax.annotate('GS-IP GROUND STUDS\nPRIMARY SUSPECT\nCheck torque, corrosion,\npaint under terminals',
                xy=(500, 2700), xytext=(200, 2300),
                fontsize=8, fontweight='bold', color='#dc3545',
                arrowprops=dict(arrowstyle='->', color='#dc3545', lw=2.5),
                bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                          edgecolor='#dc3545', linewidth=2.5),
                zorder=5)

    # P2208 connector (repaired Jun 2024)
    ax.annotate('P2208 AREA\nWire terminal repaired\nJun 2024 — verify quality',
                xy=(2600, 1200), xytext=(2000, 1100),
                fontsize=8, fontweight='bold', color='#ff9800',
                arrowprops=dict(arrowstyle='->', color='#ff9800', lw=2),
                bbox=dict(boxstyle='round,pad=0.4', facecolor='#ffe0b2',
                          edgecolor='#ff9800', linewidth=2),
                zorder=5)

    # Avionic bus / relay area
    ax.annotate('AVIONIC BUS PATH\nAV.BUS 25A CB → Avionic Relay\n→ AVIONIC BUS → G1000\nCheck both power AND ground side',
                xy=(600, 500), xytext=(100, 350),
                fontsize=8, fontweight='bold', color='#dc3545',
                arrowprops=dict(arrowstyle='->', color='#dc3545', lw=2),
                bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                          edgecolor='#dc3545', linewidth=2),
                zorder=5)

    # Firewall pass-through
    ax.annotate('FIREWALL PASS-THROUGH\nConnectors & grommets\nBonding straps\nR&R #1 & #2 both touched\nthese — but check anyway',
                xy=(2550, 1600), xytext=(1800, 1800),
                fontsize=8, fontweight='bold', color='#ff9800',
                arrowprops=dict(arrowstyle='->', color='#ff9800', lw=2),
                bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                          edgecolor='#ff9800', linewidth=2),
                zorder=5)

    # ECU area - reads correctly
    ax.annotate('ECU A & B\nRead CORRECTLY via GS-RP\n→ Ground path OK here',
                xy=(3500, 1000), xytext=(3800, 800),
                fontsize=8, fontweight='bold', color='#28a745',
                arrowprops=dict(arrowstyle='->', color='#28a745', lw=2),
                bbox=dict(boxstyle='round,pad=0.4', facecolor='#d4edda',
                          edgecolor='#28a745', linewidth=2),
                zorder=5)

    # Ground path flow
    ground_text = (
        "INSPECTION PRIORITY\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "1. GS-IP ground studs (IP)\n"
        "2. Ground bus bar bolts (IP)\n"
        "3. IP frame-to-fuselage bond\n"
        "4. GIA 63W GND pins (IP)\n"
        "5. Firewall bonding (ENG)\n"
        "6. R&R #1 work areas (ENG)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Use milliohm meter at each\n"
        "segment to isolate fault"
    )
    ax.text(3800, 1800, ground_text, fontsize=8, fontfamily='monospace',
            verticalalignment='top',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#fff3cd',
                      edgecolor='#dc3545', linewidth=3, alpha=0.95),
            zorder=5)

    # ---- LEGEND ----
    legend_elements = [
        mpatches.Patch(facecolor='#dc354530', edgecolor='#dc3545',
                       linewidth=2, label='INSTRUMENT PANEL — Highest Priority'),
        mpatches.Patch(facecolor='#ff980030', edgecolor='#ff9800',
                       linewidth=2, label='ENGINE COMPARTMENT — R&R #1 Suspect'),
        mpatches.Patch(facecolor='#ffc10730', edgecolor='#ffc107',
                       linewidth=2, label='FUSELAGE — Medium Priority'),
        mpatches.Patch(facecolor='#28a74530', edgecolor='#28a745',
                       linewidth=2, label='GS-RP / ECU — Reads Correctly'),
    ]
    ax.legend(handles=legend_elements, loc='lower left', fontsize=8,
              framealpha=0.95, edgecolor='black', fancybox=True,
              bbox_to_anchor=(0.02, 0.02))

    ax.set_title('AMM CH.92 D44-9224-30-01_02 — Wiring Detail with Inspection Highlights',
                 fontsize=12, fontweight='bold', pad=8)

    plt.tight_layout()
    plt.savefig('output/wiring_detail_annotated.png', dpi=200, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close()
    print('Saved: output/wiring_detail_annotated.png')


if __name__ == '__main__':
    print('Annotating AMM schematics with G1000 ground path inspection highlights...\n')
    annotate_bus_structure()
    annotate_wiring_diagram()
    annotate_wiring_detail()
    print('\nDone. Annotated schematics saved to output/')
