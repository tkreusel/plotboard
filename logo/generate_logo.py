"""
generate_logo.py — Render a retro 8-bit logo for plotboard.
Run once:  python generate_logo.py
Output:    logo.png  (in the project root)
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle
import numpy as np

# ---------------------------------------------------------------------------
# iGEM palette
# ---------------------------------------------------------------------------
DARK    = '#3D2652'
PURPLE  = '#E03BFF'
ORANGE  = '#ED7A3E'
YELLOW  = '#FCCF00'
GRAY    = '#D3D3D3'
BLUE_L  = '#4EC9FF'
RED     = '#FF6B6B'
GREEN   = '#6BCB77'
GOLD    = '#FFD166'
BLUE_D  = '#118AB2'
WHITE   = '#FFFFFF'

# ---------------------------------------------------------------------------
# Canvas:  800 x 320 data-units  →  1 data-unit ≈ 2 screen-pixels at 200 dpi
# We'll work in a 160 x 64 "pixel grid" (each pixel = 5 data units)
# ---------------------------------------------------------------------------
FIG_W, FIG_H = 12, 4.8   # inches
DPI           = 200

fig = plt.figure(figsize=(FIG_W, FIG_H), dpi=DPI)
ax  = fig.add_axes([0, 0, 1, 1])

CX, CY = 160, 64          # canvas width / height in "pixels"
ax.set_xlim(0, CX)
ax.set_ylim(0, CY)
ax.axis('off')
fig.patch.set_facecolor(DARK)
ax.set_facecolor(DARK)

P = 1  # 1 pixel unit in data coords

def px(ax, x, y, w=1, h=1, color=WHITE, alpha=1.0, zorder=4):
    ax.add_patch(Rectangle((x, y), w*P, h*P,
                            fc=color, ec='none', alpha=alpha, zorder=zorder))

# ---------------------------------------------------------------------------
# Outer border  — 2px thick, YELLOW on top/bottom, corners in PURPLE
# ---------------------------------------------------------------------------
for x in range(CX):
    px(ax, x, 0,      color=YELLOW)
    px(ax, x, 1,      color=YELLOW)
    px(ax, x, CY-2,   color=YELLOW)
    px(ax, x, CY-1,   color=YELLOW)
for y in range(CY):
    px(ax, 0,      y, color=YELLOW)
    px(ax, 1,      y, color=YELLOW)
    px(ax, CX-2,   y, color=YELLOW)
    px(ax, CX-1,   y, color=YELLOW)
# corner accents
for cx, cy in [(0,0),(0,CY-2),(CX-2,0),(CX-2,CY-2)]:
    px(ax, cx, cy, 2, 2, color=PURPLE)

# ---------------------------------------------------------------------------
# Subtle background grid in chart zone
# ---------------------------------------------------------------------------
for gx in range(4, 68, 6):
    for gy in range(4, 60):
        if gy % 2 == 0:
            px(ax, gx, gy, 1, 1, color='#4A3360', alpha=0.6)

# ---------------------------------------------------------------------------
# Pixel-art bar chart  (chart zone: x 4-68, y 4-58)
# Bars: 4px wide, 2px gap, base at y=6, max up to y=52
# ---------------------------------------------------------------------------
BARS = [
    (6,  20, ORANGE,  '#FF9D6C'),
    (13, 32, PURPLE,  '#EE7BFF'),
    (20, 14, GREEN,   '#9AEBA9'),
    (27, 42, BLUE_L,  '#8FDDFF'),
    (34, 26, RED,     '#FF9999'),
    (41, 36, GOLD,    '#FFE499'),
    (48, 18, BLUE_D,  '#4DB8E8'),
]

for bx, bh, bc, highlight in BARS:
    base_y = 6
    # shadow (1px right+down offset, darker)
    for dy in range(bh):
        px(ax, bx+1, base_y + dy, 4, 1, color='#1A0F2A', alpha=0.5, zorder=2)
    # main bar body
    for dy in range(bh):
        shade = 0.85 if dy < bh - 2 else 1.0
        col   = bc if dy < bh - 1 else highlight
        px(ax, bx, base_y + dy, 4, 1, color=col, zorder=3)
    # top cap highlight (white-ish strip)
    px(ax, bx, base_y + bh, 4, 1, color=WHITE, alpha=0.35, zorder=3)
    # data point above bar  — 3×3 pixel circle approximation
    dot_y = base_y + bh + 3
    dot_x = bx + 1
    for dx, dy, a in [(0,1,1),(1,0,1),(2,1,1),(0,2,1),(2,2,1),(1,1,1),(1,3,0.5),(3,1,0.5)]:
        px(ax, dot_x+dx-1, dot_y+dy-1, 1, 1, color=WHITE, alpha=a, zorder=5)

# Axes lines
for x in range(4, 56):
    px(ax, x, 5, color=GRAY, zorder=4)
    px(ax, x, 4, color=GRAY, alpha=0.4, zorder=4)
for y in range(4, 58):
    px(ax, 4, y, color=GRAY, zorder=4)
    px(ax, 5, y, color=GRAY, alpha=0.4, zorder=4)
# axis tick marks
for bx, bh, bc, _ in BARS:
    px(ax, 3, 6 + bh, 2, 1, color=YELLOW, zorder=5)

# ---------------------------------------------------------------------------
# Pixel stars / sparkles  scattered in right zone
# ---------------------------------------------------------------------------
def star(ax, cx, cy, color, s=1):
    px(ax, cx,   cy,   s, s, color=color, zorder=6)
    px(ax, cx-s, cy,   s, s, color=color, alpha=0.7, zorder=6)
    px(ax, cx+s, cy,   s, s, color=color, alpha=0.7, zorder=6)
    px(ax, cx,   cy-s, s, s, color=color, alpha=0.7, zorder=6)
    px(ax, cx,   cy+s, s, s, color=color, alpha=0.7, zorder=6)

star(ax, 70,  56, YELLOW)
star(ax, 155, 10, PURPLE)
star(ax, 78,  10, BLUE_L,  s=1)
star(ax, 148, 52, GREEN)
star(ax, 120, 14, ORANGE)
star(ax, 100, 48, RED,   s=1)

# small 2×2 pixel dots
for dx, dy, dc in [(85,38,GOLD),(108,22,BLUE_L),(130,35,PURPLE),(142,20,YELLOW),(90,18,RED)]:
    px(ax, dx, dy,   2, 2, color=dc, alpha=0.8, zorder=5)

# ---------------------------------------------------------------------------
# Text — "PLOTBOARD" main title  (right half, x≈70)
# ---------------------------------------------------------------------------
ax.text(72, 38,
        'PLOTBOARD',
        fontsize=42, fontweight='bold', color=WHITE,
        fontfamily='monospace', va='center', ha='left',
        zorder=10)
# drop shadow
ax.text(73.5, 36.5,
        'PLOTBOARD',
        fontsize=42, fontweight='bold', color=PURPLE,
        fontfamily='monospace', va='center', ha='left',
        zorder=9, alpha=0.5)

# Tagline
ax.text(72, 26,
        'EXPERIMENTAL  PLOTTER',
        fontsize=10.5, color=YELLOW,
        fontfamily='monospace', va='center', ha='left',
        zorder=10, alpha=0.92)

# Little decorative bar: 3 coloured 2×2 blocks before tagline
for i, c in enumerate([ORANGE, GREEN, BLUE_L]):
    px(ax, 72 + i*3, 22, 2, 2, color=c, zorder=10)

# Version badge
ax.text(72, 16,
        '[ v1.0 ]',
        fontsize=8, color=GRAY,
        fontfamily='monospace', va='center', ha='left',
        zorder=10, alpha=0.75)

# ---------------------------------------------------------------------------
# CRT scan-line overlay (very subtle alternating dark rows)
# ---------------------------------------------------------------------------
for y in range(0, CY, 2):
    px(ax, 0, y, CX, 1, color='black', alpha=0.07, zorder=20)

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------
out = 'logo.png'
plt.savefig(out, dpi=DPI, bbox_inches='tight', pad_inches=0,
            facecolor=DARK, transparent=False)
plt.close()
print(f"Saved: {out}")
