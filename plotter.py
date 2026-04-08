"""
plotter.py — Build a publication-quality matplotlib Figure from a tidy DataFrame.

The DataFrame must have columns: condition, treatment, replicate, value
(as produced by parser.parse_sheet).
"""

from __future__ import annotations

import re

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns

matplotlib.rcParams["pdf.fonttype"] = 42   # editable text in PDF/Illustrator
matplotlib.rcParams["svg.fonttype"] = "none"

_DEFAULTS = dict(
    title_fs=14,
    axis_label_fs=12,
    tick_fs=10,
    legend_fs=10,
    legend_title_fs=11,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def make_figure(
    df: pd.DataFrame,
    *,
    # Plot type
    plot_type: str = "bar",          # "bar" | "box" | "violin"
    error_bar: str = "sd",           # "sd" | "sem" | "ci95"  (bar only)
    cap_size: float = 0.08,
    show_points: bool = True,
    point_size: float = 4.0,
    point_alpha: float = 0.7,
    # Scale / grid
    log_scale: bool = False,
    show_grid: bool = False,
    # Colors / style
    palette: list[str],
    bar_edge_width: float = 0.6,
    bar_edge_color: str = "black",
    bar_alpha: float = 1.0,
    bar_gap: float = 0.0,
    # Labels
    title: str = "",
    xlabel: str = "Condition",
    ylabel: str = "Value",
    legend_title: str = "Treatment",
    show_legend: bool = True,
    legend_inside: bool = False,
    # Figure size
    fig_width: float = 10.0,
    fig_height: float = 6.0,
    # Typography
    font_family: str = "sans-serif",
    font_scale: float = 1.0,          # global scale (used when fontsizes is empty)
    fontsizes: dict | None = None,    # per-element: keys title/axis_label/tick/legend
    # Axes
    tick_rotation: float = 40.0,
    tick_fontsize: float | None = None,   # None → use fontsizes / font_scale
    spines: str = "open",             # "open" | "all" | "none"
    spine_width: float = 1.0,
    y_format: str = "auto",           # "auto" | "plain" | "sci" | "SI"
    ylim: tuple | None = None,        # (min, max), either may be None
    xlim: tuple | None = None,
    # Line plot
    x_numeric: bool = False,       # True → proportional x spacing from numeric condition labels
    error_style: str = "band",     # "band" | "bars"
    line_width: float = 1.5,
    marker_style: str = "o",
    marker_size: float = 6.0,
    x_suffix: str = "",            # appended to tick labels when conditions are purely numeric
    # Stats
    stat_results: pd.DataFrame | None = None,
    show_ns: bool = False,
    test_mode: str = "ttest",
    compare_axis: str = "conditions",
    bracket_linewidth: float = 0.9,
    bracket_fontsize: float = 11.0,
    show_pvalue: bool = False,
) -> matplotlib.figure.Figure:
    """
    Render *df* as a grouped bar / box / violin plot with optional
    overlaid individual data points and significance annotations.
    Returns the Figure (not shown or saved — caller decides what to do).
    """
    if df.empty:
        fig, ax = plt.subplots(figsize=(fig_width, fig_height))
        ax.text(0.5, 0.5, "No data to display", ha="center", va="center",
                transform=ax.transAxes, fontsize=14, color="gray")
        return fig

    # ------------------------------------------------------------------
    # Typography setup
    # ------------------------------------------------------------------
    matplotlib.rcParams["font.family"] = font_family

    fs = dict(_DEFAULTS)  # start from defaults
    if fontsizes:
        if "title"       in fontsizes: fs["title_fs"]       = fontsizes["title"]
        if "axis_label"  in fontsizes: fs["axis_label_fs"]  = fontsizes["axis_label"]
        if "tick"        in fontsizes: fs["tick_fs"]        = fontsizes["tick"]
        if "legend"      in fontsizes: fs["legend_fs"]      = fontsizes["legend"]
        if "legend"      in fontsizes: fs["legend_title_fs"] = fontsizes["legend"] + 1
        sns.set_theme(style="white", font_scale=1.0)
    else:
        sns.set_theme(style="white", font_scale=font_scale)
        # scale the defaults too so they're consistent
        for k in fs:
            fs[k] = fs[k] * font_scale

    _tick_fs = tick_fontsize if tick_fontsize is not None else fs["tick_fs"]

    # ------------------------------------------------------------------
    # Ordering
    # ------------------------------------------------------------------
    conditions = list(df["condition"].cat.categories) if hasattr(df["condition"], "cat") else list(df["condition"].unique())
    treatments = list(df["treatment"].cat.categories) if hasattr(df["treatment"], "cat") else list(df["treatment"].unique())

    color_map = {t: palette[i % len(palette)] for i, t in enumerate(treatments)}

    if log_scale and df["value"].min() <= 0:
        log_scale = False

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))

    # ------------------------------------------------------------------
    # Grid (draw before bars so bars sit on top)
    # ------------------------------------------------------------------
    if show_grid:
        ax.yaxis.grid(True, color="lightgray", linewidth=0.5, zorder=0)
        ax.set_axisbelow(True)

    # ------------------------------------------------------------------
    # Base layer
    # ------------------------------------------------------------------
    common_kw = dict(data=df, x="condition", y="value", hue="treatment",
                     hue_order=treatments, order=conditions,
                     palette=color_map, ax=ax)

    _elem_width = 0.8 * (1.0 - bar_gap)

    if plot_type == "bar":
        errorbar_arg = _errorbar_arg(error_bar)
        sns.barplot(
            **common_kw,
            errorbar=errorbar_arg,
            capsize=cap_size,
            edgecolor=bar_edge_color,
            linewidth=bar_edge_width,
            err_kws={"linewidth": 1.2},
            saturation=1.0,
        )
        # Post-draw: shrink bars symmetrically (bar centers fixed → strip/brackets stay aligned)
        if bar_gap > 0:
            for patch in ax.patches:
                if not isinstance(patch, mpatches.Rectangle):
                    continue
                w = patch.get_width()
                if w <= 0:
                    continue
                new_w = w * (1.0 - bar_gap)
                cx = patch.get_x() + w / 2
                patch.set_width(new_w)
                patch.set_x(cx - new_w / 2)
        # Apply alpha post-draw (seaborn doesn't accept alpha directly on barplot)
        if bar_alpha < 1.0:
            for patch in ax.patches:
                if isinstance(patch, mpatches.Rectangle) and patch.get_width() > 0:
                    patch.set_alpha(bar_alpha)
    elif plot_type == "box":
        sns.boxplot(
            **common_kw,
            linewidth=bar_edge_width,
            fliersize=0,
            width=_elem_width,
        )
    elif plot_type == "violin":
        sns.violinplot(
            **common_kw,
            inner=None,
            linewidth=bar_edge_width,
            width=_elem_width,
            cut=0,
        )
    elif plot_type == "line":
        # ---- Resolve x positions -----------------------------------------
        # Try to extract a leading numeric value from each condition label.
        # "1" → 1.0, "24" → 24.0, "1h" → 1.0, "100 nM" → 100.0
        # If all conditions yield a number AND x_numeric is requested, use
        # proportional spacing; otherwise fall back to 0,1,2,… (categorical).
        _NUM_RE = re.compile(r"^\s*([+-]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)")

        def _try_numeric(s: str) -> float | None:
            m = _NUM_RE.match(str(s))
            return float(m.group(1)) if m else None

        _parsed = [_try_numeric(c) for c in conditions]
        _all_numeric = all(v is not None for v in _parsed)

        if x_numeric and _all_numeric:
            x_vals = [v for v in _parsed]      # type: ignore[misc]
            # Tick labels: use original condition string (already contains unit if present)
            # plus x_suffix only when the condition label is purely numeric (no letters)
            _tick_labels = [
                str(c) + (x_suffix if re.fullmatch(r"[+-]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?", str(c).strip()) else "")
                for c in conditions
            ]
        else:
            x_vals = list(range(len(conditions)))
            _tick_labels = [str(c) for c in conditions]

        # ---- One line per treatment ---------------------------------------
        for i, treatment in enumerate(treatments):
            color = palette[i % len(palette)]
            grp = df[df["treatment"] == treatment]
            means: list[float] = []
            errs: list[float] = []
            for cond in conditions:
                vals = grp[grp["condition"] == cond]["value"].dropna().values
                n = len(vals)
                if n == 0:
                    means.append(float("nan"))
                    errs.append(float("nan"))
                    continue
                mean = float(np.mean(vals))
                means.append(mean)
                if n > 1:
                    sd = float(np.std(vals, ddof=1))
                    errs.append({"sd": sd,
                                 "sem": sd / np.sqrt(n),
                                 "ci95": 1.96 * sd / np.sqrt(n)}.get(error_bar, sd))
                else:
                    errs.append(float("nan"))

            m_arr = np.array(means)
            e_arr = np.array(errs)

            ax.plot(x_vals, m_arr, color=color, linewidth=line_width,
                    marker=marker_style if marker_style != "none" else None,
                    markersize=marker_size, label=treatment, zorder=3)

            valid = ~np.isnan(e_arr) & ~np.isnan(m_arr)
            if valid.any():
                xv = np.array(x_vals)
                if error_style == "band":
                    ax.fill_between(xv[valid], (m_arr - e_arr)[valid], (m_arr + e_arr)[valid],
                                    color=color, alpha=0.15, zorder=2)
                else:
                    ax.errorbar(xv[valid], m_arr[valid], yerr=e_arr[valid],
                                fmt="none", ecolor=color,
                                capsize=cap_size * 80, elinewidth=0.8, zorder=2)

            if show_points:
                for j, cond in enumerate(conditions):
                    pts = grp[grp["condition"] == cond]["value"].dropna().values
                    ax.scatter([x_vals[j]] * len(pts), pts,
                               color=color, s=(point_size ** 2) * 0.5,
                               alpha=point_alpha, zorder=4, linewidths=0.3)

        # ---- X ticks -------------------------------------------------------
        ax.set_xticks(x_vals)
        ax.set_xticklabels(_tick_labels, rotation=tick_rotation,
                           fontsize=_tick_fs, ha="right" if tick_rotation > 0 else "center")

        # ---- Legend (from ax.plot labels) ----------------------------------
        if show_legend:
            leg_kw = (dict(loc="upper right", bbox_to_anchor=(0.98, 0.98), borderaxespad=0)
                      if legend_inside else
                      dict(loc="upper left", bbox_to_anchor=(1.02, 1), borderaxespad=0))
            ax.legend(title=legend_title, frameon=False,
                      fontsize=fs["legend_fs"], title_fontsize=fs["legend_title_fs"],
                      **leg_kw)
        else:
            ax.legend_.remove() if ax.get_legend() else None

        # ---- Axes styling (line-specific, then fall through) ---------------
        if log_scale:
            ax.set_yscale("log")
        ax.set_title(title, fontsize=fs["title_fs"], pad=10)
        ax.set_xlabel(xlabel, fontsize=fs["axis_label_fs"], labelpad=6)
        ax.set_ylabel(ylabel, fontsize=fs["axis_label_fs"], labelpad=6)
        ax.tick_params(axis="y", labelsize=_tick_fs)
        if spines == "open":
            sns.despine(ax=ax, top=True, right=True)
        elif spines == "none":
            sns.despine(ax=ax, top=True, right=True, left=True, bottom=True)
            ax.tick_params(left=False, bottom=False)
        else:
            sns.despine(ax=ax, top=False, right=False)
        for spine in ax.spines.values():
            spine.set_linewidth(spine_width)
        ax.tick_params(width=spine_width)
        _apply_y_format(ax, y_format)
        if ylim is not None:
            lo, hi = ylim
            cur_lo, cur_hi = ax.get_ylim()
            ax.set_ylim(lo if lo is not None else cur_lo,
                        hi if hi is not None else cur_hi)
        if xlim is not None:
            lo, hi = xlim
            cur_lo, cur_hi = ax.get_xlim()
            ax.set_xlim(lo if lo is not None else cur_lo,
                        hi if hi is not None else cur_hi)
        fig.tight_layout()
        return fig

    else:
        raise ValueError(f"Unknown plot_type: {plot_type!r}")

    # ------------------------------------------------------------------
    # Strip overlay
    # ------------------------------------------------------------------
    if show_points:
        sns.stripplot(
            data=df,
            x="condition",
            y="value",
            hue="treatment",
            hue_order=treatments,
            order=conditions,
            dodge=True,
            jitter=True,
            marker="o",
            size=point_size,
            palette="dark:black",
            alpha=point_alpha,
            linewidth=0.5,
            ax=ax,
        )

    # ------------------------------------------------------------------
    # Legend
    # ------------------------------------------------------------------
    handles, labels_leg = ax.get_legend_handles_labels()
    n_t = len(treatments)
    if show_legend:
        if legend_inside:
            leg_kw = dict(loc="upper right", bbox_to_anchor=(0.98, 0.98),
                          borderaxespad=0)
        else:
            leg_kw = dict(loc="upper left", bbox_to_anchor=(1.02, 1),
                          borderaxespad=0)
        ax.legend(
            handles[:n_t], labels_leg[:n_t],
            title=legend_title,
            frameon=False,
            fontsize=fs["legend_fs"],
            title_fontsize=fs["legend_title_fs"],
            **leg_kw,
        )
    else:
        ax.legend_.remove() if ax.get_legend() else None

    # ------------------------------------------------------------------
    # Axes styling
    # ------------------------------------------------------------------
    if log_scale:
        ax.set_yscale("log")

    ax.set_title(title, fontsize=fs["title_fs"], pad=10)
    ax.set_xlabel(xlabel, fontsize=fs["axis_label_fs"], labelpad=6)
    ax.set_ylabel(ylabel, fontsize=fs["axis_label_fs"], labelpad=6)
    ax.tick_params(axis="x", rotation=tick_rotation, labelsize=_tick_fs)
    ax.tick_params(axis="y", labelsize=_tick_fs)

    # Spines
    if spines == "open":
        sns.despine(ax=ax, top=True, right=True)
    elif spines == "none":
        sns.despine(ax=ax, top=True, right=True, left=True, bottom=True)
        ax.tick_params(left=False, bottom=False)
    else:  # "all" — full box
        sns.despine(ax=ax, top=False, right=False)

    for spine in ax.spines.values():
        spine.set_linewidth(spine_width)
    ax.tick_params(width=spine_width)

    # Y-axis number format
    _apply_y_format(ax, y_format)

    # ------------------------------------------------------------------
    # Statistical annotations
    # ------------------------------------------------------------------
    if stat_results is not None and not stat_results.empty:
        from stats import draw_significance_bars
        draw_significance_bars(
            ax=ax,
            df=df,
            stat_results=stat_results,
            show_ns=show_ns,
            test_mode=test_mode,
            compare_axis=compare_axis,
            log_scale=log_scale,
            bracket_linewidth=bracket_linewidth,
            bracket_fontsize=bracket_fontsize,
            show_pvalue=show_pvalue,
        )

    # ------------------------------------------------------------------
    # Axis limits (applied last — overrides bracket expansion)
    # ------------------------------------------------------------------
    if ylim is not None:
        lo, hi = ylim
        cur_lo, cur_hi = ax.get_ylim()
        ax.set_ylim(lo if lo is not None else cur_lo,
                    hi if hi is not None else cur_hi)
    if xlim is not None:
        lo, hi = xlim
        cur_lo, cur_hi = ax.get_xlim()
        ax.set_xlim(lo if lo is not None else cur_lo,
                    hi if hi is not None else cur_hi)

    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _errorbar_arg(error_bar: str):
    return {"sd": ("sd", 1), "sem": ("se", 1), "ci95": ("ci", 95)}.get(error_bar, ("sd", 1))


def _apply_y_format(ax, y_format: str) -> None:
    if y_format == "plain":
        fmt = mticker.ScalarFormatter(useOffset=False)
        fmt.set_scientific(False)
        ax.yaxis.set_major_formatter(fmt)
    elif y_format == "sci":
        ax.ticklabel_format(style="sci", axis="y", scilimits=(0, 0))
    elif y_format == "SI":
        def _si(x, _):
            for thresh, suffix in [(1e9, "G"), (1e6, "M"), (1e3, "k")]:
                if abs(x) >= thresh:
                    return f"{x / thresh:.3g}{suffix}"
            return f"{x:.3g}"
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(_si))
    # "auto" → do nothing, matplotlib decides
