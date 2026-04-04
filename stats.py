"""
stats.py — Statistical tests and significance bar drawing for grouped plots.

Two test modes:
  "ttest"  — independent two-sample t-test, each condition vs. a chosen reference,
              per treatment group.
  "tukey"  — one-way ANOVA per treatment group followed by Tukey's HSD across
              all pairwise condition combinations.

Significance thresholds: *** p<0.001 | ** p<0.01 | * p<0.05 | ns
"""

from __future__ import annotations

import warnings

import matplotlib.axes
import numpy as np
import pandas as pd
from scipy import stats as scipy_stats


# ---------------------------------------------------------------------------
# p-value → stars
# ---------------------------------------------------------------------------

def pval_to_stars(p: float) -> str:
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "ns"


# ---------------------------------------------------------------------------
# Statistical tests
# ---------------------------------------------------------------------------

def run_ttests_vs_reference(
    df: pd.DataFrame,
    reference_condition: str,
) -> pd.DataFrame:
    """
    For every (treatment, non-reference condition) pair, run an independent
    two-sample t-test against (treatment, reference_condition).

    Returns a DataFrame with columns:
        treatment, condition, reference, t_stat, p_value, stars
    """
    records = []
    ref_rows = df[df["condition"] == reference_condition]

    for treatment in df["treatment"].unique():
        ref_vals = (
            ref_rows[ref_rows["treatment"] == treatment]["value"]
            .dropna()
            .values
        )
        if len(ref_vals) < 2:
            continue

        for condition in df["condition"].unique():
            if condition == reference_condition:
                continue
            test_vals = (
                df[(df["condition"] == condition) & (df["treatment"] == treatment)]["value"]
                .dropna()
                .values
            )
            if len(test_vals) < 2:
                continue

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                t_stat, p_value = scipy_stats.ttest_ind(ref_vals, test_vals)

            records.append(
                {
                    "treatment": str(treatment),
                    "condition": str(condition),
                    "reference": reference_condition,
                    "t_stat": round(float(t_stat), 4),
                    "p_value": float(p_value),
                    "stars": pval_to_stars(p_value),
                }
            )

    return pd.DataFrame(records) if records else pd.DataFrame(
        columns=["treatment", "condition", "reference", "t_stat", "p_value", "stars"]
    )


def run_tukey(df: pd.DataFrame) -> pd.DataFrame:
    """
    One-way ANOVA + Tukey HSD across conditions, per treatment group.
    compare_axis="conditions": for each treatment, compare all condition pairs.

    Returns a DataFrame with columns:
        treatment, group_A, group_B, p_value, stars, compare_axis
    """
    return _run_tukey_impl(df, between="condition", fixed_col="treatment")


def run_tukey_between_treatments(df: pd.DataFrame) -> pd.DataFrame:
    """
    One-way ANOVA + Tukey HSD across treatments, per condition group.
    compare_axis="treatments": for each condition, compare all treatment pairs.

    Returns a DataFrame with columns:
        condition, group_A, group_B, p_value, stars, compare_axis
    """
    return _run_tukey_impl(df, between="treatment", fixed_col="condition")


def _run_tukey_impl(df: pd.DataFrame, *, between: str, fixed_col: str) -> pd.DataFrame:
    try:
        import pingouin as pg
    except ImportError:
        raise ImportError(
            "pingouin is required for Tukey HSD. Install it with: pip install pingouin"
        )

    records = []
    for fixed_val in df[fixed_col].unique():
        sub = (
            df[df[fixed_col] == fixed_val][["condition", "treatment", "value"]]
            .dropna()
            .copy()
        )
        sub[between] = sub[between].astype(str)
        if sub[between].nunique() < 2:
            continue

        try:
            tukey = pg.pairwise_tukey(data=sub, dv="value", between=between)
        except Exception:
            continue

        for _, row in tukey.iterrows():
            records.append(
                {
                    fixed_col: str(fixed_val),
                    "group_A": row["A"],
                    "group_B": row["B"],
                    "p_value": float(row["p_tukey"]),
                    "stars": pval_to_stars(float(row["p_tukey"])),
                    "compare_axis": between + "s",   # "conditions" or "treatments"
                }
            )

    if not records:
        cols = [fixed_col, "group_A", "group_B", "p_value", "stars", "compare_axis"]
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Significance bar drawing
# ---------------------------------------------------------------------------

def draw_significance_bars(
    ax: matplotlib.axes.Axes,
    df: pd.DataFrame,
    stat_results: pd.DataFrame,
    *,
    show_ns: bool = False,
    test_mode: str = "ttest",
    compare_axis: str = "conditions",   # "conditions" | "treatments"
    log_scale: bool = False,
    bracket_linewidth: float = 0.9,
    bracket_fontsize: float = 11.0,
    show_pvalue: bool = False,
) -> None:
    """
    Draw horizontal significance brackets above the relevant bars on *ax*.

    compare_axis="conditions": brackets span bars of the same treatment across
        different condition groups (the default Tukey / t-test mode).
    compare_axis="treatments": brackets span bars of different treatments within
        the same condition group (between-treatment Tukey).

    Bracket x-positions use seaborn's dodge formula:
        x_center = condition_idx + (treatment_idx - (n_treatments-1)/2) * (0.8/n_treatments)
    """
    if stat_results.empty:
        return

    conditions = _ordered_unique(df["condition"])
    treatments = _ordered_unique(df["treatment"])
    n_treatments = len(treatments)
    dodge_width = 0.8 / n_treatments

    def bar_x(cond_idx: int, treat_idx: int) -> float:
        offset = (treat_idx - (n_treatments - 1) / 2.0) * dodge_width
        return cond_idx + offset

    # ---- Collect bracketing jobs ----------------------------------------
    jobs: list[dict] = []

    for _, row in stat_results.iterrows():
        stars = row["stars"]
        if stars == "ns" and not show_ns:
            continue

        if compare_axis == "treatments":
            # Brackets between two treatments within one condition
            condition = str(row["condition"])
            if condition not in conditions:
                continue
            c_idx = conditions.index(condition)

            treat_a = str(row["group_A"])
            treat_b = str(row["group_B"])
            if treat_a not in treatments or treat_b not in treatments:
                continue

            x1 = bar_x(c_idx, treatments.index(treat_a))
            x2 = bar_x(c_idx, treatments.index(treat_b))
            pair_key = (condition, min(treat_a, treat_b), max(treat_a, treat_b))

        else:
            # Brackets between two conditions for one treatment (default)
            treatment = str(row["treatment"])
            if treatment not in treatments:
                continue
            t_idx = treatments.index(treatment)

            # Infer row format from columns (ttest has "reference"; tukey has "group_A")
            if "reference" in stat_results.columns:
                cond_a = str(row["reference"])
                cond_b = str(row["condition"])
            else:
                cond_a = str(row["group_A"])
                cond_b = str(row["group_B"])

            if cond_a not in conditions or cond_b not in conditions:
                continue

            x1 = bar_x(conditions.index(cond_a), t_idx)
            x2 = bar_x(conditions.index(cond_b), t_idx)
            pair_key = (treatment, min(cond_a, cond_b), max(cond_a, cond_b))

        jobs.append({
            "x1": x1, "x2": x2, "stars": stars,
            "p_value": float(row["p_value"]) if "p_value" in stat_results.columns else None,
            "pair_key": pair_key,
        })

    if not jobs:
        return

    # ---- Assign bracket heights without overlaps -----------------------
    # Sort by x-span width (widest brackets go highest, narrowest stay low).
    # Then use interval-greedy stacking: place each bracket at the lowest
    # available level whose rightmost x does not overlap the new bracket.
    y_lo, y_hi = ax.get_ylim()
    data_range = y_hi - y_lo if not log_scale else None
    margin = 0.05  # a little padding so adjacent brackets don't touch

    jobs_sorted = sorted(
        jobs, key=lambda j: abs(j["x2"] - j["x1"]), reverse=True
    )

    # level_right_x[i] = rightmost x used by any bracket already at level i
    level_right_x: list[float] = []
    annotated: list[tuple[float, float, str, float | None, int]] = []  # x1, x2, stars, p_value, level

    for job in jobs_sorted:
        x_lo = min(job["x1"], job["x2"]) - margin
        x_hi = max(job["x1"], job["x2"]) + margin

        assigned = None
        for i, right_x in enumerate(level_right_x):
            if x_lo >= right_x:          # no overlap at this level
                level_right_x[i] = x_hi
                assigned = i
                break
        if assigned is None:
            assigned = len(level_right_x)
            level_right_x.append(x_hi)

        annotated.append((job["x1"], job["x2"], job["stars"], job.get("p_value"), assigned))

    # Convert levels to y-coordinates
    def level_to_y(level: int) -> float:
        if log_scale:
            return y_hi * (1.08 ** (level + 1))
        return y_hi + data_range * 0.09 * (level + 1)

    # ---- Draw brackets -------------------------------------------------
    for x1, x2, stars, p_value, level in annotated:
        y = level_to_y(level)
        if log_scale:
            tick_h = y * 0.025
        else:
            tick_h = data_range * 0.015

        ax.plot(
            [x1, x1, x2, x2],
            [y - tick_h, y, y, y - tick_h],
            color="black",
            linewidth=bracket_linewidth,
            clip_on=False,
        )
        if show_pvalue and p_value is not None:
            label = f"p={p_value:.3f}" if p_value >= 0.001 else "p<0.001"
        else:
            label = stars
        ax.text(
            (x1 + x2) / 2,
            y,
            label,
            ha="center",
            va="bottom",
            fontsize=bracket_fontsize,
            clip_on=False,
        )

    # ---- Expand y-axis to fit all brackets ----------------------------
    if annotated:
        max_level = max(level for _, _, _, _, level in annotated)
        max_y = level_to_y(max_level)
        if log_scale:
            ax.set_ylim(top=max_y * 1.25)
        else:
            ax.set_ylim(top=max_y + data_range * 0.09 * 1.5)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ordered_unique(series: pd.Series) -> list[str]:
    """Return unique values in first-occurrence order, as strings."""
    if hasattr(series, "cat"):
        return [str(c) for c in series.cat.categories]
    seen: dict[str, None] = {}
    for v in series:
        seen[str(v)] = None
    return list(seen)
