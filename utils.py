"""
utils.py — Color palettes and figure export helpers.
"""

from __future__ import annotations

import io

import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns

# ---------------------------------------------------------------------------
# Color palettes
# ---------------------------------------------------------------------------

def _hex_list(cmap_name: str, n: int = 10) -> list[str]:
    cmap = plt.get_cmap(cmap_name)
    return [matplotlib.colors.to_hex(cmap(i / (n - 1))) for i in range(n)]


PALETTES: dict[str, list[str]] = {
    "iGEM": ["#E03BFF", "#ED7A3E", "#FCCF00", "#3D2652", "#D3D3D3",
             "#4EC9FF", "#FF6B6B", "#6BCB77", "#FFD166", "#118AB2"],
    "Tab10": [matplotlib.colors.to_hex(c) for c in plt.get_cmap("tab10").colors],
    "Viridis": _hex_list("viridis", 10),
    "Pastel": sns.color_palette("pastel").as_hex(),
    "Colorblind": sns.color_palette("colorblind").as_hex(),
    "Set2": sns.color_palette("Set2").as_hex(),
}

PALETTE_NAMES = list(PALETTES.keys()) + ["Custom"]


def get_palette(name: str, n: int) -> list[str]:
    """
    Return a list of at least *n* hex colors for the named palette.
    Cycles if n > palette length.
    """
    if name == "Custom":
        # Caller must supply custom colors; fall back to Tab10
        name = "Tab10"
    base = PALETTES.get(name, PALETTES["Tab10"])
    # Cycle to cover more treatments than the palette has entries
    return [base[i % len(base)] for i in range(n)]


# ---------------------------------------------------------------------------
# Figure export
# ---------------------------------------------------------------------------

def fig_to_bytes(fig: matplotlib.figure.Figure, fmt: str, dpi: int = 300) -> bytes:
    """Render *fig* to bytes in the requested format."""
    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, dpi=dpi, bbox_inches="tight")
    buf.seek(0)
    return buf.read()
