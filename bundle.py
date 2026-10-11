"""
bundle.py — the "export everything" JSON: one figure's data, settings and the
exact plotter arguments, so it can be redrawn later without the app.

What is in a bundle
-------------------
    format, version     "plotboard-figure", 1
    source              workbook name, sheet, export time
    data                the plotted values in tidy form (condition, treatment,
                        replicate, value) after filtering and renaming, plus
                        the display order of conditions and treatments
    stats               the significance comparisons drawn as brackets, or null
    make_figure_kwargs  everything ``plotter.make_figure`` was called with,
                        already resolved (palette as hex colours, axis limits
                        as numbers, font sizes) — enough to rebuild the plot in
                        plain seaborn/matplotlib too
    preset              the ps_* settings in preset-file form: save this object
                        as ``.presets/<name>.json`` and it loads as a preset

Redrawing it with plotboard::

    df, kwargs = bundle.load(json.load(open("figure.json")))
    fig = plotter.make_figure(df, **kwargs)

JSON has no NaN, so missing numbers (an untestable p-value, say) are null.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any

import pandas as pd

import dataio
import presets

FORMAT = "plotboard-figure"
VERSION = 1


def build(
    df: pd.DataFrame,
    *,
    figure_kwargs: dict,
    settings: dict,
    file_label: str = "",
    sheet: str = "",
) -> dict:
    """Bundle a figure: *df* and *figure_kwargs* exactly as given to
    ``plotter.make_figure``, *settings* as from ``settings.snapshot()``."""
    kwargs = dict(figure_kwargs)
    stats = kwargs.pop("stat_results", None)
    return _clean({
        "format": FORMAT,
        "version": VERSION,
        "source": {
            "file": file_label,
            "sheet": sheet,
            "exported": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "data": {
            "condition_order": dataio.categories(df["condition"]),
            "treatment_order": dataio.categories(df["treatment"]),
            "columns": list(df.columns),
            "records": df.to_dict("records"),
        },
        "stats": None if stats is None or stats.empty else stats.to_dict("records"),
        "make_figure_kwargs": kwargs,
        "preset": presets._preset_payload(settings),
    })


def to_json(bundle: dict) -> str:
    return json.dumps(bundle, indent=2, ensure_ascii=False, allow_nan=False)


def load(bundle: dict) -> tuple[pd.DataFrame, dict]:
    """Inverse of ``build``: ``(df, kwargs)`` ready for ``plotter.make_figure``."""
    if bundle.get("format") != FORMAT:
        raise ValueError("not a plotboard figure export")
    data = bundle["data"]
    df = pd.DataFrame.from_records(data["records"], columns=data["columns"])
    for column, order in (("condition", data["condition_order"]),
                          ("treatment", data["treatment_order"])):
        df[column] = pd.Categorical(df[column], categories=order, ordered=True)

    kwargs = dict(bundle["make_figure_kwargs"])
    # JSON turns tuples into lists; the plotter unpacks these as pairs/quads.
    for key in ("ylim", "xlim"):
        if kwargs.get(key) is not None:
            kwargs[key] = tuple(kwargs[key])
    if kwargs.get("sigmoids") is not None:
        kwargs["sigmoids"] = [tuple(c) for c in kwargs["sigmoids"]]
    if bundle.get("stats"):
        kwargs["stat_results"] = pd.DataFrame.from_records(bundle["stats"])
    return df, kwargs


def _clean(value: Any) -> Any:
    """Make *value* plain JSON: numpy scalars to Python, tuples to lists,
    NaN/inf to None (``json.dumps`` would otherwise write invalid ``NaN``)."""
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        value = value.item()  # numpy scalar
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is pd.NA or value is pd.NaT:
        return None
    return value
