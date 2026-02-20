"""Render GEA71S_voltage_path.drawio as PNG using matplotlib."""

import xml.etree.ElementTree as ET
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Parse the Draw.io XML
tree = ET.parse('docs/GEA71S_voltage_path.drawio')
root = tree.getroot()

# Canvas dimensions from the mxGraphModel attributes
PAGE_W = 1100
PAGE_H = 700

# Figure: 2x scale for crisp rendering
fig, ax = plt.subplots(1, 1, figsize=(PAGE_W / 80, PAGE_H / 80))
ax.set_xlim(0, PAGE_W)
ax.set_ylim(PAGE_H, 0)  # Inverted Y to match Draw.io (0,0 = top-left)
ax.set_aspect('equal')
ax.axis('off')
fig.patch.set_facecolor('white')
ax.set_facecolor('white')


def parse_style(s):
    """Parse Draw.io style string into dict."""
    if not s:
        return {}
    d = {}
    for part in s.split(';'):
        part = part.strip()
        if '=' in part:
            k, v = part.split('=', 1)
            d[k] = v
        elif part:
            d[part] = True
    return d


def get_geom(cell):
    """Get geometry from mxCell."""
    g = cell.find('mxGeometry')
    if g is None:
        return None
    return {
        'x': float(g.get('x', 0)),
        'y': float(g.get('y', 0)),
        'w': float(g.get('width', 0)),
        'h': float(g.get('height', 0)),
    }


def get_points(cell):
    """Get source/target points from edge."""
    g = cell.find('mxGeometry')
    if g is None:
        return None, None
    src = g.find("*[@as='sourcePoint']")
    tgt = g.find("*[@as='targetPoint']")
    sp = (float(src.get('x')), float(src.get('y'))) if src is not None else None
    tp = (float(tgt.get('x')), float(tgt.get('y'))) if tgt is not None else None
    return sp, tp


# Collect all cells
graph = root.find('.//root')
cells = [c for c in graph if c.tag == 'mxCell' and c.get('id') not in ('0', '1')]

# Draw edges first (behind), then vertices
edges = [c for c in cells if c.get('edge') == '1']
vertices = [c for c in cells if c.get('vertex') == '1']

# Draw edges
for cell in edges:
    style = parse_style(cell.get('style', ''))
    sp, tp = get_points(cell)
    if sp and tp:
        color = style.get('strokeColor', '#333333')
        lw = float(style.get('strokeWidth', '1'))
        dashed = style.get('dashed') == '1'
        dash_pat = style.get('dashPattern', '')
        if dashed:
            if dash_pat:
                # Convert "5 3" to on-off sequence
                segs = [float(x) for x in dash_pat.split()]
                ls = (0, tuple(segs))
            else:
                ls = '--'
        else:
            ls = '-'
        ax.plot([sp[0], tp[0]], [sp[1], tp[1]], color=color, linewidth=lw,
                linestyle=ls, solid_capstyle='round', zorder=1)

# Draw vertices
for cell in vertices:
    cid = cell.get('id', '')
    value = cell.get('value', '')
    style = parse_style(cell.get('style', ''))
    geom = get_geom(cell)
    if geom is None:
        continue

    x, y, w, h = geom['x'], geom['y'], geom['w'], geom['h']

    is_text = 'text' in style
    is_ellipse = 'ellipse' in style

    # Font properties
    fs = float(style.get('fontSize', '10'))
    fc = style.get('fontColor', '#333333')
    fstyle = int(style.get('fontStyle', '0'))
    bold = bool(fstyle & 1)
    italic = bool(fstyle & 2)
    rotation = float(style.get('rotation', '0'))

    ha_val = style.get('align', 'center')
    va_val = style.get('verticalAlign', 'middle')

    # Map alignment
    ha_map = {'left': 'left', 'center': 'center', 'right': 'right'}
    va_map = {'top': 'top', 'middle': 'center', 'bottom': 'bottom'}
    ha = ha_map.get(ha_val, 'center')
    va = va_map.get(va_val, 'center')

    # Text anchor position
    tx = {'left': x, 'center': x + w / 2, 'right': x + w}[ha]
    ty = {'top': y, 'center': y + h / 2, 'bottom': y + h}[va]

    if is_ellipse:
        # Junction dot
        fill = style.get('fillColor', '#333333')
        circle = plt.Circle((x + w / 2, y + h / 2), w / 2, color=fill, zorder=5)
        ax.add_patch(circle)

    elif is_text:
        # Pure text element
        text = value.replace('<br>', '\n').replace('<br/>', '\n')
        bg = style.get('labelBackgroundColor')
        bbox = dict(boxstyle='square,pad=0.5', facecolor=bg, edgecolor='none', zorder=3) if bg else None
        ax.text(tx, ty, text, ha=ha, va=va, fontsize=fs, rotation=rotation,
                fontweight='bold' if bold else 'normal',
                fontstyle='italic' if italic else 'normal',
                color=fc, bbox=bbox, zorder=4)

    else:
        # Rectangle/box
        fill = style.get('fillColor', 'none')
        stroke = style.get('strokeColor', '#333333')
        lw = float(style.get('strokeWidth', '1'))
        dashed = style.get('dashed') == '1'

        if fill == 'none':
            face = 'none'
        else:
            face = fill

        rect = patches.Rectangle(
            (x, y), w, h, linewidth=lw,
            edgecolor=stroke if stroke != 'none' else 'none',
            facecolor=face if face != 'none' else 'none',
            linestyle='--' if dashed else '-',
            zorder=2
        )
        ax.add_patch(rect)

        # Label inside box — use top alignment with padding so
        # separate note text elements inside the box don't overlap
        if value:
            text = value.replace('<br>', '\n').replace('<br/>', '\n')
            pad = 4  # small top padding
            ax.text(x + w / 2, y + pad, text, ha='center', va='top',
                    fontsize=fs, fontweight='bold' if bold else 'normal',
                    fontstyle='italic' if italic else 'normal',
                    color=fc, zorder=3)

plt.tight_layout(pad=0.5)
plt.savefig('output/GEA71S_voltage_path.png', dpi=180, bbox_inches='tight',
            facecolor='white', edgecolor='none')
print("Saved: output/GEA71S_voltage_path.png")
