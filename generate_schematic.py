"""Generate GEA 71S voltage measurement path schematic as PNG."""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

fig, ax = plt.subplots(1, 1, figsize=(14, 9))
ax.set_xlim(0, 14)
ax.set_ylim(0, 9)
ax.set_aspect('equal')
ax.axis('off')
fig.patch.set_facecolor('white')

# Colors
GREEN = '#2e7d32'
GREEN_BG = '#e8f5e9'
AMBER = '#e65100'
AMBER_BG = '#fff3e0'
RED = '#c62828'
RED_BG = '#ffebee'
PURPLE = '#6a1b9a'
PURPLE_BG = '#f3e5f5'
BLUE = '#1565c0'
BLUE_BG = '#e3f2fd'
GRAY = '#616161'
LIGHT_GRAY = '#f5f5f5'

# ── GEA 71S Box ──
gea_x, gea_y, gea_w, gea_h = 0.5, 1.2, 4.5, 6.8
gea = FancyBboxPatch((gea_x, gea_y), gea_w, gea_h,
                      boxstyle="round,pad=0.15", linewidth=2.5,
                      edgecolor='#333', facecolor=LIGHT_GRAY)
ax.add_patch(gea)
ax.text(gea_x + gea_w/2, gea_y + gea_h - 0.35, 'GEA 71S',
        ha='center', va='center', fontsize=16, fontweight='bold', color='#333')
ax.text(gea_x + gea_w/2, gea_y + gea_h - 0.8, 'Connector  J701\n(harness plug P701)',
        ha='center', va='center', fontsize=9, color=GRAY, style='italic')


def draw_pin_row(y, pin_num, pin_name, bg_color, border_color, text_color):
    """Draw a pin box inside the GEA."""
    bx, bw, bh = 0.8, 3.8, 0.55
    box = FancyBboxPatch((bx, y), bw, bh, boxstyle="round,pad=0.05",
                         linewidth=1.5, edgecolor=border_color, facecolor=bg_color)
    ax.add_patch(box)
    ax.text(bx + 0.15, y + bh/2, f'Pin {pin_num}', ha='left', va='center',
            fontsize=10, fontweight='bold', color=text_color)
    ax.text(bx + bw - 0.15, y + bh/2, pin_name, ha='right', va='center',
            fontsize=9, color=text_color)
    return bx + bw, y + bh/2  # right edge x, center y


def draw_wire(x_start, y_start, x_end, y_end, color, lw=2):
    """Draw a wire line."""
    ax.plot([x_start, x_end], [y_start, y_end], color=color, linewidth=lw,
            solid_capstyle='round')


def draw_junction(x, y, color, size=0.12):
    """Draw a junction dot."""
    circle = plt.Circle((x, y), size, color=color, zorder=5)
    ax.add_patch(circle)


def draw_dest_box(x, y, w, h, text, bg_color, border_color, text_color='#333', fontsize=11):
    """Draw a destination box."""
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1",
                         linewidth=2, edgecolor=border_color, facecolor=bg_color)
    ax.add_patch(box)
    ax.text(x + w/2, y + h/2, text, ha='center', va='center',
            fontsize=fontsize, fontweight='bold', color=text_color)


# ── Channel 5: Voltage Sense (green) ──
ax.text(1.0, 7.0, 'Channel 5  —  volt1 (bus volts sense)',
        ha='left', va='center', fontsize=10, fontweight='bold', color=GREEN)

pin46_x, pin46_y = draw_pin_row(6.2, 46, 'ANALOG IN 5 HI', GREEN_BG, GREEN, GREEN)
pin47_x, pin47_y = draw_pin_row(5.5, 47, 'ANALOG IN 5 LO', GREEN_BG, GREEN, GREEN)

# Wires from Pin 46, 47 → Essential Bus
junc_sense_x = 6.0
draw_wire(pin46_x, pin46_y, junc_sense_x, pin46_y, GREEN)
draw_wire(junc_sense_x, pin46_y, junc_sense_x, pin47_y, GREEN)
draw_wire(pin47_x, pin47_y, junc_sense_x, pin47_y, GREEN)

# Wire labels
ax.text((pin46_x + junc_sense_x)/2, pin46_y + 0.2, '31299A22WH',
        ha='center', va='bottom', fontsize=8, fontweight='bold', color=GREEN)
ax.text((pin46_x + junc_sense_x)/2, pin46_y + 0.02, '(shielded)',
        ha='center', va='bottom', fontsize=7, color=GREEN, style='italic')
ax.text((pin47_x + junc_sense_x)/2, pin47_y - 0.22, '31299A22BL',
        ha='center', va='top', fontsize=8, fontweight='bold', color=GREEN)
ax.text((pin47_x + junc_sense_x)/2, pin47_y - 0.4, '(shielded)',
        ha='center', va='top', fontsize=7, color=GREEN, style='italic')

# → Essential Bus box (sense)
ess_x, ess_w, ess_h = 10.5, 2.8, 0.9
ess_y_sense = pin46_y - ess_h/2 + (pin47_y - pin46_y)/2
draw_wire(junc_sense_x, (pin46_y + pin47_y)/2, ess_x, ess_y_sense + ess_h/2, GREEN)
draw_dest_box(ess_x, ess_y_sense, ess_w, ess_h, 'ESSENTIAL\nBUS', BLUE_BG, BLUE, BLUE)

# ── Channel 4 / Power (amber) ──
ax.text(1.0, 5.0, 'Power / Channel 4  —  supply self-sense',
        ha='left', va='center', fontsize=10, fontweight='bold', color=AMBER)

pin35_x, pin35_y = draw_pin_row(4.2, 35, 'AIRCRAFT POWER', AMBER_BG, AMBER, AMBER)
pin44_x, pin44_y = draw_pin_row(3.5, 44, 'ANALOG IN 4 HI', AMBER_BG, AMBER, AMBER)

# Junction for shared wire
junc_pwr_x = 5.8
junc_pwr_y = (pin35_y + pin44_y) / 2
draw_wire(pin35_x, pin35_y, junc_pwr_x, pin35_y, AMBER)
draw_wire(pin44_x, pin44_y, junc_pwr_x, pin44_y, AMBER)
draw_wire(junc_pwr_x, pin35_y, junc_pwr_x, pin44_y, AMBER)
draw_junction(junc_pwr_x, junc_pwr_y, AMBER)

# Wire to Essential Bus (power)
ess_y_pwr = pin35_y - 0.45
draw_wire(junc_pwr_x, junc_pwr_y, ess_x, ess_y_pwr + ess_h/2, AMBER)
draw_dest_box(ess_x, ess_y_pwr, ess_w, ess_h,
              'ESSENTIAL\nBUS', BLUE_BG, BLUE, BLUE)
ax.text(ess_x + ess_w/2, ess_y_pwr - 0.15, 'via ENG INST 5A',
        ha='center', va='top', fontsize=8, color=GRAY, style='italic')

# Wire label
ax.text((junc_pwr_x + ess_x)/2, junc_pwr_y + 0.2, '77015A22',
        ha='center', va='bottom', fontsize=9, fontweight='bold', color=AMBER)

# ── Ground (red) ──
ax.text(1.0, 3.0, 'Ground  —  suspect path',
        ha='left', va='center', fontsize=10, fontweight='bold', color=RED)

pin20_x, pin20_y = draw_pin_row(2.2, 20, 'POWER GROUND', RED_BG, RED, RED)
pin45_x, pin45_y = draw_pin_row(1.5, 45, 'ANALOG IN 4 LO', RED_BG, RED, RED)

# Junction for shared ground wire
junc_gnd_x = 5.8
junc_gnd_y = (pin20_y + pin45_y) / 2
draw_wire(pin20_x, pin20_y, junc_gnd_x, pin20_y, RED)
draw_wire(pin45_x, pin45_y, junc_gnd_x, pin45_y, RED)
draw_wire(junc_gnd_x, pin20_y, junc_gnd_x, pin45_y, RED)
draw_junction(junc_gnd_x, junc_gnd_y, RED)

# Wire label
ax.text((junc_gnd_x + 7.5)/2, junc_gnd_y + 0.2, '77016A22N',
        ha='center', va='bottom', fontsize=9, fontweight='bold', color=RED)

# → GS-IP-14
gs_x, gs_w, gs_h = 7.5, 1.8, 0.7
gs_y = junc_gnd_y - gs_h/2
draw_wire(junc_gnd_x, junc_gnd_y, gs_x, junc_gnd_y, RED)
draw_dest_box(gs_x, gs_y, gs_w, gs_h, 'GS-IP-14', RED_BG, RED, RED, fontsize=12)

# ── Ground path chain (documented — solid red lines) ──
chain_x = gs_x + gs_w/2

# GS-IP-14 → GS-IP Bus Bar
draw_wire(chain_x, gs_y, chain_x, 1.45, RED)
bb_w, bb_h = 2.0, 0.45
draw_dest_box(chain_x - bb_w/2, 0.95, bb_w, bb_h, 'GS-IP Bus Bar',
              RED_BG, RED, RED, fontsize=9)

# Bus Bar → wire 24008A4N → Battery B1 Negative
draw_wire(chain_x, 0.95, chain_x, 0.65, RED)
ax.text(chain_x + 0.1, 0.8, '24008A4N (4 AWG)',
        ha='left', va='center', fontsize=8, fontweight='bold', color=RED)
bat_w, bat_h = 2.2, 0.45
draw_dest_box(chain_x - bat_w/2, 0.15, bat_w, bat_h, 'Battery B1\nNegative',
              RED_BG, RED, RED, fontsize=9)

# Source drawing annotation
ax.text(chain_x, 0.62, 'per D44-9224-30-01X03',
        ha='center', va='center', fontsize=7, color=GRAY, style='italic')

# ── Warning callout ──
warn_x, warn_y = 10.2, 1.2
warn = FancyBboxPatch((warn_x, warn_y), 3.3, 1.1, boxstyle="round,pad=0.15",
                       linewidth=2.5, edgecolor=RED, facecolor='#fff8e1',
                       linestyle='--')
ax.add_patch(warn)
ax.text(warn_x + 1.65, warn_y + 0.55,
        '⚠  HIGH RESISTANCE\nAT A TERMINAL\nCONNECTION',
        ha='center', va='center', fontsize=10, fontweight='bold', color=RED)
# Arrow from callout to ground path
ax.annotate('', xy=(gs_x + gs_w, junc_gnd_y - 0.3),
            xytext=(warn_x, warn_y + 0.3),
            arrowprops=dict(arrowstyle='->', color=RED, lw=2, ls='--'))

# ── Title ──
ax.text(7.0, 8.7,
        'GEA 71S Voltage Measurement Path — N238PS (DA40 NG)',
        ha='center', va='center', fontsize=14, fontweight='bold', color='#333')
ax.text(7.0, 8.35,
        'All pins on connector P701 (harness plug) → J701 (GEA receptacle)',
        ha='center', va='center', fontsize=10, color=GRAY, style='italic')

plt.tight_layout()
plt.savefig('output/GEA71S_voltage_path.png', dpi=150, bbox_inches='tight',
            facecolor='white', edgecolor='none')
print("Saved: output/GEA71S_voltage_path.png")
