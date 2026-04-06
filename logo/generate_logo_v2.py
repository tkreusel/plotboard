"""
generate_logo_v2.py — Alternative esoteric/fractal retro logo for plotboard.
Run:  python logo/generate_logo_v2.py
Out:  logo/logo_v2.png
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle
from pathlib import Path

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
BLACK   = '#000000'

FIG_W, FIG_H = 12, 4.8
DPI = 200

fig = plt.figure(figsize=(FIG_W, FIG_H), dpi=DPI)
ax  = fig.add_axes([0, 0, 1, 1])

CX, CY = 160, 64
ax.set_xlim(0, CX)
ax.set_ylim(0, CY)
ax.axis('off')
fig.patch.set_facecolor(DARK)
ax.set_facecolor(DARK)

def px(x, y, w=1, h=1, color=WHITE, alpha=1.0, zorder=4):
    ax.add_patch(Rectangle((x, y), w, h, fc=color, ec='none',
                            alpha=alpha, zorder=zorder))

# ---------------------------------------------------------------------------
# Background — Sierpinski triangle rendered in pixel blocks
# Fills the entire canvas, very dark, as a texture
# ---------------------------------------------------------------------------
def sierpinski_pixels(order, x0, y0, size):
    """Yield (col, row) pixel coords of a pixel-art Sierpinski triangle."""
    pts = []
    def draw(x, y, s, depth):
        if depth == 0 or s < 1:
            pts.append((int(x), int(y), int(s)))
            return
        half = s / 2
        draw(x,        y,        half, depth - 1)
        draw(x + half, y,        half, depth - 1)
        draw(x + half/2, y + half, half, depth - 1)
    draw(x0, y0, size, order)
    return pts

tri_pts = sierpinski_pixels(5, 2, 2, 60)
tri_colors = [PURPLE, BLUE_D, BLUE_L, GOLD, GREEN]
for i, (tx, ty, ts) in enumerate(tri_pts):
    c = tri_colors[i % len(tri_colors)]
    block = max(1, int(ts))
    px(tx, ty, block, block, color=c, alpha=0.13, zorder=1)

# ---------------------------------------------------------------------------
# Dragon curve (pixel art) — drawn left side
# Generate N iterations of the dragon curve, scale to fit
# ---------------------------------------------------------------------------
def dragon_curve(n_iter):
    """Return list of (x,y) integer steps for the dragon curve."""
    dirs = [(1,0),(0,1),(-1,0),(0,-1)]
    seq = [0]  # start going right
    for _ in range(n_iter):
        turn = [1] + [1 - 2*((i >> (len(seq).bit_length()-1)) & 1)
                      for i in range(len(seq)-1, -1, -1)]
        new_seq = []
        for t in seq:
            new_seq.append(t)
        # fold: new_seq = seq + [1] + reversed(rotated seq)
        new_seq = seq + [1] + [(s + 1) % 4 for s in reversed(seq)]
        seq = new_seq
    # Walk the curve
    x, y = 0, 0
    pts = [(x, y)]
    d = 0
    for turn in seq:
        d = (d + (1 if turn == 1 else -1)) % 4
        dx, dy = dirs[d]
        x += dx
        y += dy
        pts.append((x, y))
    return pts

dragon = dragon_curve(9)
xs = [p[0] for p in dragon]
ys = [p[1] for p in dragon]
x_min, x_max = min(xs), max(xs)
y_min, y_max = min(ys), max(ys)
# Scale into a 50×50 pixel box starting at (4, 7)
x_range = max(x_max - x_min, 1)
y_range = max(y_max - y_min, 1)
scale = min(50 / x_range, 44 / y_range)

dragon_colors = [PURPLE, ORANGE, BLUE_L, GREEN, YELLOW, RED, GOLD]
prev = None
for i, (px_c, py_c) in enumerate(dragon):
    sx = int((px_c - x_min) * scale) + 3
    sy = int((py_c - y_min) * scale) + 9
    if 2 <= sx <= 58 and 4 <= sy <= 60:
        c = dragon_colors[i % len(dragon_colors)]
        alpha = 0.55 + 0.4 * (i / len(dragon))
        px(sx, sy, 1, 1, color=c, alpha=alpha, zorder=3)

# Bright highlight dots along the dragon
highlight_step = len(dragon) // 18
for i in range(0, len(dragon), highlight_step):
    px_c, py_c = dragon[i]
    sx = int((px_c - x_min) * scale) + 3
    sy = int((py_c - y_min) * scale) + 9
    if 2 <= sx <= 58 and 4 <= sy <= 60:
        px(sx, sy, 2, 2, color=WHITE, alpha=0.7, zorder=4)

# ---------------------------------------------------------------------------
# Pixel axes + bar chart ghost (same position as v1, fainter)
# ---------------------------------------------------------------------------
for x in range(4, 56):
    px(x, 5, 1, 1, color=GRAY, alpha=0.25, zorder=4)
for y in range(4, 58):
    px(4, y, 1, 1, color=GRAY, alpha=0.25, zorder=4)

BARS = [
    (6,  20, ORANGE),
    (13, 32, PURPLE),
    (20, 14, GREEN),
    (27, 42, BLUE_L),
    (34, 26, RED),
    (41, 36, GOLD),
    (48, 18, BLUE_D),
]
for bx, bh, bc in BARS:
    for dy in range(bh):
        px(bx, 6+dy, 4, 1, color=bc, alpha=0.18, zorder=2)
    px(bx, 6+bh, 4, 1, color=WHITE, alpha=0.12, zorder=2)

# ---------------------------------------------------------------------------
# Mandelbrot-inspired pixel scatter — right half background texture
# Sample a grid, colour by iteration count using iGEM palette
# ---------------------------------------------------------------------------
mand_colors = [PURPLE, BLUE_D, BLUE_L, GREEN, GOLD, ORANGE, RED, YELLOW]
for gx in range(62, 158, 2):
    for gy in range(4, 62, 2):
        # Map pixel to complex plane
        c = complex((gx - 110) / 38, (gy - 33) / 22)
        z = 0j
        it = 0
        for it in range(12):
            if abs(z) > 2:
                break
            z = z*z + c
        if it > 1:
            col = mand_colors[it % len(mand_colors)]
            alpha = 0.06 + 0.07 * (it / 12)
            px(gx, gy, 2, 2, color=col, alpha=alpha, zorder=1)

# ---------------------------------------------------------------------------
# Pixel-art spiral — golden ratio approximation, right side decoration
# ---------------------------------------------------------------------------
spiral_colors = [YELLOW, ORANGE, RED, PURPLE, BLUE_L, GREEN, GOLD]
cx_s, cy_s = 130, 32
for i in range(180):
    angle = i * 0.18
    r = 0.28 * i ** 0.72
    sx = int(cx_s + r * np.cos(angle))
    sy = int(cy_s + r * np.sin(angle) * 0.6)
    if 62 <= sx <= 157 and 4 <= sy <= 61:
        c = spiral_colors[i % len(spiral_colors)]
        px(sx, sy, 2, 2, color=c, alpha=0.55, zorder=3)

# ---------------------------------------------------------------------------
# Outer border — 2px, PURPLE top/bottom, corners YELLOW
# ---------------------------------------------------------------------------
for x in range(CX):
    px(x, 0,      1, 2, color=PURPLE)
    px(x, CY-2,   1, 2, color=PURPLE)
for y in range(CY):
    px(0,    y, 2, 1, color=PURPLE)
    px(CX-2, y, 2, 1, color=PURPLE)
for cx2, cy2 in [(0,0),(0,CY-2),(CX-2,0),(CX-2,CY-2)]:
    px(cx2, cy2, 2, 2, color=YELLOW)

# ---------------------------------------------------------------------------
# Scanline overlay
# ---------------------------------------------------------------------------
for y in range(0, CY, 2):
    px(0, y, CX, 1, color=BLACK, alpha=0.09, zorder=20)

# ---------------------------------------------------------------------------
# Pixel stars / sparkles
# ---------------------------------------------------------------------------
def star(cx2, cy2, color, s=1):
    px(cx2,   cy2,   s, s, color=color, zorder=6)
    px(cx2-s, cy2,   s, s, color=color, alpha=0.6, zorder=6)
    px(cx2+s, cy2,   s, s, color=color, alpha=0.6, zorder=6)
    px(cx2,   cy2-s, s, s, color=color, alpha=0.6, zorder=6)
    px(cx2,   cy2+s, s, s, color=color, alpha=0.6, zorder=6)

star(66, 55, YELLOW)
star(155, 10, GREEN)
star(148, 52, ORANGE)
star(66,  8, BLUE_L)
star(153, 33, RED, s=1)

# ---------------------------------------------------------------------------
# PLOTBOARD text — right half
# ---------------------------------------------------------------------------
# Glitch shadow: offset copies in iGEM accent colors
for dx2, dy2, col2, a2 in [(-1.5, 0, PURPLE, 0.6), (1.5, 0, BLUE_L, 0.4)]:
    ax.text(72 + dx2, 41 + dy2,
            'PLOTBOARD',
            fontsize=42, fontweight='bold', color=col2,
            fontfamily='monospace', va='center', ha='left',
            zorder=9, alpha=a2)
# Main white text
ax.text(72, 41,
        'PLOTBOARD',
        fontsize=42, fontweight='bold', color=WHITE,
        fontfamily='monospace', va='center', ha='left',
        zorder=10)

# Tagline
ax.text(72, 26,
        'EXPERIMENTAL  PLOTTER',
        fontsize=10.5, color=YELLOW,
        fontfamily='monospace', va='center', ha='left',
        zorder=10, alpha=0.92)

# Three coloured blocks
for i, c in enumerate([ORANGE, GREEN, BLUE_L]):
    px(72 + i*3, 22, 2, 2, color=c, zorder=10)

# Small fractal label
ax.text(72, 16,
        '[ v1.0 ]',
        fontsize=7.5, color=GRAY,
        fontfamily='monospace', va='center', ha='left',
        zorder=10, alpha=0.7)

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------
out = Path(__file__).parent / 'logo_v2.png'
plt.savefig(out, dpi=DPI, bbox_inches='tight', pad_inches=0,
            facecolor=DARK, transparent=False)
plt.close()
print(f"Saved: {out}")
