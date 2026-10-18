"""
Tests for the "export everything" JSON (bundle.py).

Self-contained: builds its own small Prism-style workbook, so unlike
test_regressions.py it does not need data/E24_Analysis.xlsx.

    python tests/test_json_export.py      (or: pytest tests/)

The core promise is that a figure redrawn from its JSON is the same figure, so
the round trips compare rendered PNG bytes, not just kwargs.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, PROJECT_DIR)
os.chdir(PROJECT_DIR)

import numpy as np  # noqa: E402
import openpyxl  # noqa: E402
import pandas as pd  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

import bundle  # noqa: E402
import dataio  # noqa: E402
import figspec  # noqa: E402
import plotter  # noqa: E402
import presets  # noqa: E402
import stats  # noqa: E402
import utils  # noqa: E402

TREATMENTS = {"Ctrl": [1.0, 1.2, 0.9], "Drug": [2.1, 2.4, 1.9]}
CONDITIONS = {"0.1": 0.5, "1": 1.0, "10": 2.0}


def _workbook_path() -> str:
    """Two sheets in the GraphPad grouped layout the parser expects."""
    wb = openpyxl.Workbook()
    for index, name in enumerate(["Nano", "Firefly"]):
        ws = wb.active if index == 0 else wb.create_sheet()
        ws.title = name
        header = ["Condition"]
        for treatment, reps in TREATMENTS.items():
            header += [treatment] + [None] * (len(reps) - 1)
        ws.append(header)
        for condition, factor in CONDITIONS.items():
            row = [condition]
            for reps in TREATMENTS.values():
                row += [round(v * factor * (index + 1), 3) for v in reps]
            ws.append(row)
    path = os.path.join(tempfile.mkdtemp(), "synthetic.xlsx")
    wb.save(path)
    return path


DATA_FILE = _workbook_path()


def _frame(conditions: list | None = None) -> pd.DataFrame:
    raw = dataio.load_sheet(open(DATA_FILE, "rb").read(), "k", "Nano")
    return dataio.apply_selection(raw, conditions or list(CONDITIONS),
                                  list(TREATMENTS))


def _kwargs(settings: dict, df: pd.DataFrame, stat_results=None) -> dict:
    ylim, xlim = figspec.axis_limits(settings)
    return dict(
        **figspec.figure_size(settings), ylim=ylim, xlim=xlim,
        **figspec.draw_kwargs(settings, n_treatments=len(TREATMENTS),
                              title="T", ylabel="Y", stat_results=stat_results),
    )


def _png(df: pd.DataFrame, kwargs: dict) -> bytes:
    # Strip-plot jitter is random, so two draws of one figure differ unseeded.
    np.random.seed(0)
    return utils.fig_to_bytes(plotter.make_figure(df, **kwargs), "png", 100)


def _roundtrip(df, kwargs, settings) -> tuple[dict, pd.DataFrame, dict]:
    built = bundle.build(df, figure_kwargs=kwargs, settings=settings,
                         file_label="synthetic.xlsx", sheet="Nano")
    parsed = json.loads(bundle.to_json(built))
    return (parsed, *bundle.load(parsed))


# ---------------------------------------------------------------------------

def test_roundtrip_redraws_the_same_figure():
    """Bar plot with brackets, renamed labels and a y-limit."""
    settings = {**presets.DEFAULTS, "ps_ymin_str": "0", "ps_ymax_str": "8",
                "ps_palette_name": "Custom", "ps_custom_colors": ["#123456"]}
    renames = {"0.1": "low"}, {"Drug": "Drug X"}
    # Display order reversed from the row order, so it only survives if the
    # export really carries it.
    df = dataio.apply_renames(_frame(["10", "1", "0.1"]), *renames)
    tukey = dataio.rename_stat_results(stats.run_tukey(_frame()).head(2), *renames)
    kwargs = _kwargs(settings, df, stat_results=tukey)

    parsed, df2, kwargs2 = _roundtrip(df, kwargs, settings)

    assert parsed["data"]["condition_order"] == ["10", "1", "low"]
    assert parsed["make_figure_kwargs"]["palette"] == ["#123456", "#123456"]
    assert len(parsed["stats"]) == 2
    assert _png(df2, kwargs2) == _png(df, kwargs), "redrawn figure differs"


def test_roundtrip_line_plot_with_sigmoid():
    settings = {**presets.DEFAULTS, "ps_plot_type": "line",
                "ps_sigmoids": [{"id": 0, "alow": 0.0, "ahigh": 1.0, "p50": 1.0,
                                 "dp": 1.0, "color": "#112233"}],
                "ps_xmin_str": "0.05"}
    df = _frame()
    kwargs = _kwargs(settings, df)
    _, df2, kwargs2 = _roundtrip(df, kwargs, settings)
    assert kwargs["sigmoids"] and kwargs2["sigmoids"] == kwargs["sigmoids"]
    assert _png(df2, kwargs2) == _png(df, kwargs), "redrawn line plot differs"


def test_nan_becomes_null():
    """JSON has no NaN; json.dumps would write it anyway and break parsers."""
    df = _frame()
    df.loc[df.index[0], "value"] = float("nan")
    built = bundle.build(df, figure_kwargs={}, settings=presets.DEFAULTS)
    text = bundle.to_json(built)  # allow_nan=False: raises if any NaN slipped by
    assert json.loads(text)["data"]["records"][0]["value"] is None


def test_preset_part_loads_as_a_preset():
    settings = {**presets.DEFAULTS, "ps_bar_gap": 0.3, "ps_title": "one-off"}
    built = bundle.build(_frame(), figure_kwargs={}, settings=settings)
    preset = json.loads(bundle.to_json(built))["preset"]
    assert "ps_title" not in preset, "a preset must not carry a figure title"

    original = presets.PRESETS_DIR
    presets.PRESETS_DIR = type(original)(tempfile.mkdtemp())
    try:
        (presets.PRESETS_DIR / "FromJson.json").write_text(json.dumps(preset))
        loaded = presets.load("FromJson")
    finally:
        presets.PRESETS_DIR = original
    assert loaded["ps_bar_gap"] == 0.3
    assert set(loaded) == set(presets.DEFAULTS)


def test_json_bytes_roundtrip_the_data():
    df = _frame(["10", "1", "0.1"])
    built = bundle.build(df, figure_kwargs={}, settings=presets.DEFAULTS, sheet="Nano")
    back = dataio.load_sheet(bundle.to_json(built).encode(), "x", "Nano")
    key = ["condition", "treatment", "replicate"]
    a = df.astype({"condition": str, "treatment": str}).sort_values(key)
    b = back.astype({"condition": str, "treatment": str}).sort_values(key)
    assert a[key + ["value"]].reset_index(drop=True).equals(
        b[key + ["value"]].reset_index(drop=True))
    assert dataio.categories(back["condition"]) == ["10", "1", "0.1"]


def test_app_opens_a_json_with_the_full_sidebar():
    """Open a bundle in the app (uploader stubbed): sidebar tabs appear and the
    bundle's settings and title are applied."""
    df = _frame()
    settings = {**presets.DEFAULTS, "ps_fig_width": 7.0}
    kwargs = {**_kwargs(settings, df), "title": "My title"}
    built = bundle.build(df, figure_kwargs=kwargs, settings=settings, sheet="Nano")
    from ui import sidebar_top
    original = sidebar_top.render_json_input
    sidebar_top.render_json_input = lambda: (json.loads(bundle.to_json(built)), "f.json")
    try:
        app = AppTest.from_file(os.path.join(PROJECT_DIR, "app.py"),
                                default_timeout=180)
        app.run()
        assert not app.exception, [str(e.value)[:300] for e in app.exception]
        assert not app.error, [e.value for e in app.error]
        assert app.session_state["ps_fig_width"] == 7.0
        assert app.text_input(key="ps_title").value == "My title"
        app.session_state["ps_fig_width"] = 8.0
        app.run()
        assert not app.exception and app.session_state["ps_fig_width"] == 8.0
    finally:
        sidebar_top.render_json_input = original


def test_rejects_other_json():
    try:
        bundle.load({"hello": 1})
    except ValueError:
        return
    raise AssertionError("loaded something that is not a plotboard export")


def test_app_figure_survives_the_roundtrip():
    """Capture what the real app passes to make_figure, then round-trip it."""
    calls = []
    original = plotter.make_figure

    def capturing(df, **kwargs):
        calls.append((df, kwargs))
        return original(df, **kwargs)

    plotter.make_figure = capturing
    try:
        app = AppTest.from_file(os.path.join(PROJECT_DIR, "app.py"),
                                default_timeout=180)
        app.run()
        app.text_input[0].set_value(DATA_FILE)
        app.run()  # the startup preset lands on this run, so change settings after
        app.session_state["ps_fig_width"] = 7.0
        app.run()
        assert not app.exception, [str(e.value)[:300] for e in app.exception]
    finally:
        plotter.make_figure = original

    assert calls, "the app never drew a figure"
    df, kwargs = calls[-1]
    _, df2, kwargs2 = _roundtrip(df, kwargs, dict(presets.DEFAULTS))
    assert kwargs2["fig_width"] == 7.0
    assert _png(df2, kwargs2) == _png(df, kwargs)


def test_json_is_not_built_eagerly():
    """Like the images, the JSON is only produced when its button is clicked."""
    calls = []
    original = bundle.build
    bundle.build = lambda *a, **k: calls.append(1) or original(*a, **k)
    try:
        app = AppTest.from_file(os.path.join(PROJECT_DIR, "app.py"),
                                default_timeout=180)
        app.run()
        app.text_input[0].set_value(DATA_FILE)
        app.run()
        assert not app.exception, [str(e.value)[:300] for e in app.exception]
    finally:
        bundle.build = original
    assert not calls, "the JSON export was built on a plain rerun"


# ---------------------------------------------------------------------------

ALL_TESTS = [(n, f) for n, f in list(globals().items())
             if n.startswith("test_") and callable(f)]


def main() -> int:
    failures = 0
    for name, func in ALL_TESTS:
        try:
            func()
        except Exception:  # noqa: BLE001 - the runner reports everything
            failures += 1
            print(f"FAIL  {name}\n{traceback.format_exc()}", flush=True)
        else:
            print(f"ok    {name}", flush=True)
    print(f"\n{len(ALL_TESTS) - failures}/{len(ALL_TESTS)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
