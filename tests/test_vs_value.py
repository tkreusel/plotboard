"""Each bar vs a value (stats.run_tests_vs_value) and its stars above the bars.

    python tests/test_vs_value.py      (or: pytest tests/)
"""

from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats as scipy_stats  # noqa: E402

import plotter  # noqa: E402
import stats  # noqa: E402


def _frame(rows):
    df = pd.DataFrame(rows)
    for c in ("condition", "treatment"):
        df[c] = pd.Categorical(df[c], categories=list(dict.fromkeys(df[c])), ordered=True)
    return df


def test_single_value_with_se_on_log():
    """Fold 2.9886 ± 0.4744 against 1 on log: the gv-verasonics z-test, p = 5.3e-12."""
    df = _frame([{"condition": "v7", "treatment": "Fold", "replicate": 1, "value": 2.9886, "error": 0.4744},
                 {"condition": "v1", "treatment": "Fold", "replicate": 1, "value": 0.9826, "error": 0.1089}])
    r = stats.run_tests_vs_value(df, 1.0, log=True).set_index("condition")
    expect = math.erfc(abs(math.log(2.9886)) / (0.4744 / 2.9886) / math.sqrt(2))
    assert math.isclose(r.loc["v7", "p_value"], expect, rel_tol=1e-9)
    assert r.loc["v7", "stars"] == "***" and r.loc["v1", "stars"] == "ns"


def test_replicates_one_sample_t():
    vals = [2.0, 2.2, 1.9, 2.1]
    df = _frame([{"condition": "a", "treatment": "t", "replicate": i, "value": v} for i, v in enumerate(vals)])
    r = stats.run_tests_vs_value(df, 1.0)
    assert math.isclose(r.p_value[0], scipy_stats.ttest_1samp(vals, 1.0).pvalue)
    assert stats.run_tests_vs_value(df, 0.0, log=True).empty, "log against 0 has no answer"


def test_stars_drawn_above_the_bar():
    df = _frame([{"condition": c, "treatment": "Fold", "replicate": 1, "value": v, "error": e}
                 for c, v, e in (("v7", 2.9886, 0.4744), ("v1", 0.9826, 0.1089))])
    res = stats.run_tests_vs_value(df, 1.0, log=True)
    fig = plotter.make_figure(df, plot_type="bar", error_bar="column", show_points=False,
                              stat_results=res, palette=["#F5AB7F"])
    ax = fig.axes[0]
    labels = {t.get_text(): t.get_position() for t in ax.texts}
    assert set(labels) == {"***", "ns"}, labels
    assert labels["***"][1] > 2.9886 + 0.4744 and labels["***"][1] < ax.get_ylim()[1]
    assert np.isclose(labels["***"][0], 0) and np.isclose(labels["ns"][0], 1)


if __name__ == "__main__":
    for name, func in list(globals().items()):
        if name.startswith("test_"):
            func()
            print("ok   ", name)
