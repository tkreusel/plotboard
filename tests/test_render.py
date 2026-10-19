"""
Tests for render.py (a bundle drawn headless as SVG + its plot area).

    python tests/test_render.py      (or: pytest tests/)
"""

from __future__ import annotations

import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(TESTS_DIR))

import render  # noqa: E402

X = [250, 500, 1000, 2000]


def _bundle(**kwargs):
    """A two-line bundle of the kind another tool writes by hand: data, labels and colours only."""
    records = [{"condition": str(x), "treatment": t, "replicate": 0, "value": v * (k + 1), "error": 0.1}
               for k, t in enumerate(("+", "−")) for x, v in zip(X, (1.0, 2.0, 4.0, 3.0))]
    return {"format": "plotboard-figure", "version": 1,
            "data": {"condition_order": [str(x) for x in X], "treatment_order": ["+", "−"],
                     "columns": ["condition", "treatment", "replicate", "value", "error"], "records": records},
            "make_figure_kwargs": {"plot_type": "line", "error_bar": "column", "error_style": "bars",
                                   "palette": ["#50A6A3", "#D76615"], "show_legend": False,
                                   "xlabel": "Peak pressure (kPa)", "ylabel": "Signal", "show_points": False,
                                   "xlim": [250, 2000], "fig_width": 6, "fig_height": 4, **kwargs}}


def test_svg_and_plot_area():
    r = render.render(_bundle())
    assert r["svg"].lstrip().startswith("<?xml") and "<svg" in r["svg"]
    assert (r["W"], r["H"]) == (432, 288)
    assert 0 < r["L"] < r["L"] + r["PW"] <= r["W"] and 0 <= r["T"] < r["T"] + r["PH"] <= r["H"]
    assert r["xlim"] == [250, 2000], r["xlim"]   # the axis edges are the caller's range: a marker lands on the data
    assert not r["ylog"]


def test_same_bundle_same_bytes():
    assert render.render(_bundle())["svg"] == render.render(_bundle())["svg"]


def test_dashes_curves_log():
    plain = render.render(_bundle())["svg"]
    r = render.render(_bundle(line_styles=["-", "--"], log_scale=True,
                              curves=[{"x": [250, 1000, 2000], "y": [1, 3, 4], "color": "#000000", "linestyle": ":"}]))
    assert r["ylog"] and r["svg"] != plain
    assert "stroke-dasharray" in r["svg"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
