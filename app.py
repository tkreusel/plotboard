"""
app.py — Streamlit entry point for the experimental results plotting tool.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

import parser as xparser
import plotter
import presets as xpresets
import stats as xstats
import utils

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Experimental Plotter",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🔬 Experimental Results Plotter")
st.caption(
    "Upload a GraphPad Prism-style Excel file, configure the plot in the "
    "sidebar, and download publication-ready figures."
)


# ---------------------------------------------------------------------------
# Session state initialisation
# Populate any missing preset keys with their defaults so every widget has
# a value on first load and after a preset is applied.
# ---------------------------------------------------------------------------
for _k, _v in xpresets.DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# Shorthand: read a preset-keyed value from session_state.
def _ps(key: str):
    return st.session_state[key]


# ---------------------------------------------------------------------------
# Cached data loading
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Parsing sheet…")
def _load_sheet(file_bytes: bytes, sheet_name: str) -> pd.DataFrame:
    wb = xparser.load_workbook(file_bytes)
    return xparser.parse_sheet(wb, sheet_name)


@st.cache_data(show_spinner="Opening workbook…")
def _get_sheet_names(file_bytes: bytes) -> list[str]:
    wb = xparser.load_workbook(file_bytes)
    return xparser.sheet_names(wb)


# ---------------------------------------------------------------------------
# Sidebar — file loading
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("📂 Data")

    upload = st.file_uploader("Upload .xlsx file", type=["xlsx"])
    local_path = st.text_input(
        "…or enter a local file path",
        placeholder=r"C:\Users\you\data\results.xlsx",
    )

    file_bytes: bytes | None = None
    file_label = ""

    if upload is not None:
        file_bytes = upload.read()
        file_label = upload.name
    elif local_path.strip():
        p = Path(local_path.strip())
        if p.exists() and p.suffix.lower() == ".xlsx":
            file_bytes = p.read_bytes()
            file_label = p.name
        else:
            st.error("File not found or not an .xlsx file.")

# ---------------------------------------------------------------------------
# If no file: show instructions and stop
# ---------------------------------------------------------------------------

if file_bytes is None:
    st.info(
        "**Getting started**\n\n"
        "1. Upload an Excel file using the sidebar (or enter a local path).\n"
        "2. Select the sheet to plot.\n"
        "3. Adjust the plot settings in the sidebar.\n"
        "4. Download your figure using the buttons below the plot.\n\n"
        "**Expected data format** — one row per condition, treatments in groups "
        "of columns (treatment name in the first column of each group, replicate "
        "values in subsequent columns). This is the GraphPad Prism grouped layout."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Sheet selection
# ---------------------------------------------------------------------------

with st.sidebar:
    all_sheets = _get_sheet_names(file_bytes)
    sheet = st.selectbox("Sheet", all_sheets)

df = _load_sheet(file_bytes, sheet)

if df.empty:
    st.warning(
        f"Sheet **{sheet}** contains no parseable numeric data. "
        "Try a different sheet, or check that the file uses the expected layout."
    )
    st.stop()

conditions = list(df["condition"].cat.categories) if hasattr(df["condition"], "cat") else list(df["condition"].unique())
treatments = list(df["treatment"].cat.categories) if hasattr(df["treatment"], "cat") else list(df["treatment"].unique())

# ---------------------------------------------------------------------------
# Sidebar — presets
# ---------------------------------------------------------------------------

with st.sidebar:
    with st.expander("💾 Presets", expanded=False):
        saved = xpresets.list_presets()

        # -- Load ------------------------------------------------------------
        if saved:
            col_ps, col_pl = st.columns([3, 1])
            with col_ps:
                preset_choice = st.selectbox(
                    "Saved presets", saved, label_visibility="collapsed"
                )
            with col_pl:
                if st.button("Load", use_container_width=True):
                    loaded = xpresets.load(preset_choice)
                    st.session_state.update(loaded)
                    # Restore custom color picker keys
                    for _i, _c in enumerate(loaded.get("ps_custom_colors", [])):
                        if _c:
                            st.session_state[f"cp_{_i}"] = _c
                    st.toast(f"Loaded preset '{preset_choice}'", icon="✅")
                    st.rerun()

            # -- Delete ------------------------------------------------------
            if st.button(f"🗑 Delete '{preset_choice}'", use_container_width=True):
                xpresets.delete(preset_choice)
                st.toast(f"Deleted preset '{preset_choice}'", icon="🗑")
                st.rerun()
        else:
            st.caption("No saved presets yet.")

        st.divider()

        # -- Save ------------------------------------------------------------
        col_sn, col_sb = st.columns([3, 1])
        with col_sn:
            new_preset_name = st.text_input(
                "Preset name", placeholder="e.g. Publication style",
                label_visibility="collapsed",
            )
        with col_sb:
            if st.button("Save", use_container_width=True):
                if new_preset_name.strip():
                    settings = {k: st.session_state[k] for k in xpresets.DEFAULTS}
                    # Capture custom color picker values if palette is Custom
                    if st.session_state.get("ps_palette_name") == "Custom":
                        settings["ps_custom_colors"] = [
                            st.session_state.get(f"cp_{_i}", "")
                            for _i in range(len(treatments))
                        ]
                    xpresets.save(new_preset_name.strip(), settings)
                    st.toast(f"Saved preset '{new_preset_name.strip()}'", icon="💾")
                    st.rerun()
                else:
                    st.warning("Enter a name first.")

# ---------------------------------------------------------------------------
# Sidebar — filter
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("🔍 Filter")
    selected_conditions = st.multiselect(
        "Show conditions",
        options=conditions,
        default=conditions,
    )

if not selected_conditions:
    st.warning("Select at least one condition.")
    st.stop()

if selected_conditions != conditions:
    df = df[df["condition"].isin(selected_conditions)].copy()
    if hasattr(df["condition"], "cat"):
        df["condition"] = df["condition"].cat.remove_unused_categories()
    conditions = selected_conditions

# ---------------------------------------------------------------------------
# Sidebar — reorder conditions / treatments
# ---------------------------------------------------------------------------

with st.sidebar:
    with st.expander("↕ Reorder", expanded=False):
        st.caption("Change the order number to reorder items in the plot.")
        reorder_col1, reorder_col2 = st.columns(2)

        with reorder_col1:
            st.caption("Conditions (x-axis)")
            cond_order_df = pd.DataFrame({
                "Condition": conditions,
                "Order": list(range(1, len(conditions) + 1)),
            })
            edited_cond_order = st.data_editor(
                cond_order_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Condition": st.column_config.TextColumn(disabled=True),
                    "Order": st.column_config.NumberColumn(min_value=1, step=1),
                },
                key="cond_order_editor",
            )
            conditions = (
                edited_cond_order.sort_values("Order", kind="stable")["Condition"]
                .tolist()
            )

        with reorder_col2:
            st.caption("Treatments (legend)")
            treat_order_df = pd.DataFrame({
                "Treatment": treatments,
                "Order": list(range(1, len(treatments) + 1)),
            })
            edited_treat_order = st.data_editor(
                treat_order_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Treatment": st.column_config.TextColumn(disabled=True),
                    "Order": st.column_config.NumberColumn(min_value=1, step=1),
                },
                key="treat_order_editor",
            )
            treatments = (
                edited_treat_order.sort_values("Order", kind="stable")["Treatment"]
                .tolist()
            )

# Apply reordering to df so downstream plotting respects the new order
df["condition"] = pd.Categorical(df["condition"], categories=conditions, ordered=True)
df["treatment"] = pd.Categorical(df["treatment"], categories=treatments, ordered=True)

n_treatments = len(treatments)

# Warn about missing replicates
min_reps = df.groupby(["condition", "treatment"], observed=True)["value"].count().min()
if min_reps < 2:
    st.warning("Some groups have fewer than 2 replicates — error bars and statistical tests will be skipped for those groups.")

# ---------------------------------------------------------------------------
# Sidebar — plot configuration
# All interactive widgets carry key="ps_xxx" so their values live in
# session_state and are automatically captured / restored by presets.
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("📊 Plot type")
    plot_type = st.radio(
        "Plot type",
        ["bar+strip", "box+strip", "violin+strip"],
        key="ps_plot_type",
        label_visibility="collapsed",
    )
    _base_type = plot_type.split("+")[0]

    # ---- Y-axis -----------------------------------------------------------
    st.header("📐 Y-axis")
    log_scale_req = st.checkbox("Log scale", key="ps_log_scale")
    log_scale = log_scale_req
    if log_scale_req and df["value"].min() <= 0:
        st.error("Log scale requires all values > 0. Falling back to linear scale.")
        log_scale = False

    show_grid = st.checkbox("Y-axis gridlines", key="ps_show_grid")

    if _base_type == "bar":
        col_eb, col_cap = st.columns(2)
        with col_eb:
            error_bar = st.radio(
                "Error bar",
                ["sd", "sem", "ci95"],
                key="ps_error_bar",
                format_func=lambda x: {"sd": "SD", "sem": "SEM", "ci95": "95 % CI"}[x],
            )
        with col_cap:
            cap_size = st.slider("Cap size", 0.0, 0.3, key="ps_cap_size", step=0.01)
    else:
        error_bar = "sd"
        cap_size = 0.08

    show_points = st.checkbox("Show individual data points", key="ps_show_points")
    if show_points:
        col_ps2, col_pa = st.columns(2)
        with col_ps2:
            point_size = st.slider("Dot size", 1.0, 12.0, key="ps_point_size", step=0.5)
        with col_pa:
            point_alpha = st.slider("Dot opacity", 0.1, 1.0, key="ps_point_alpha", step=0.05)
    else:
        point_size = _ps("ps_point_size")
        point_alpha = _ps("ps_point_alpha")

    # ---- Labels -----------------------------------------------------------
    st.header("🏷️ Labels")
    default_title = f"{file_label}  ·  {sheet}" if file_label else sheet
    # Title is intentionally NOT preset-keyed — it's file/sheet specific.
    title = st.text_input("Title", value=default_title)

    xlabel    = st.text_input("X-axis label", key="ps_xlabel")
    # ylabel defaults to the sheet name on first load; preset overrides after that.
    if "ps_ylabel" not in st.session_state or st.session_state["ps_ylabel"] == "":
        st.session_state["ps_ylabel"] = sheet
    ylabel    = st.text_input("Y-axis label", key="ps_ylabel")
    leg_title = st.text_input("Legend title", key="ps_leg_title")
    col_sl, col_li = st.columns(2)
    with col_sl:
        show_legend = st.checkbox("Show legend", key="ps_show_legend")
    with col_li:
        legend_inside = st.checkbox("Legend inside", key="ps_legend_inside")

    # ---- Colors -----------------------------------------------------------
    st.header("🎨 Colors")
    palette_name = st.selectbox("Palette", utils.PALETTE_NAMES, key="ps_palette_name")

    custom_colors: list[str] = []
    if palette_name == "Custom":
        st.caption("Pick a color for each treatment:")
        default_palette = utils.get_palette("iGEM", n_treatments)
        for i, t in enumerate(treatments):
            col = st.color_picker(
                f"{t}",
                value=default_palette[i % len(default_palette)],
                key=f"cp_{i}",
            )
            custom_colors.append(col)
        palette = custom_colors
    else:
        palette = utils.get_palette(palette_name, n_treatments)

    if _base_type == "bar":
        col_ew, col_ec = st.columns(2)
        with col_ew:
            bar_edge_width = st.slider("Edge width", 0.0, 3.0, key="ps_bar_edge_width", step=0.1)
        with col_ec:
            bar_edge_color = st.color_picker("Edge color", key="ps_bar_edge_color")
        bar_alpha = st.slider("Bar opacity", 0.1, 1.0, key="ps_bar_alpha", step=0.05)
    else:
        bar_edge_width = 0.8
        bar_edge_color = _ps("ps_bar_edge_color")
        bar_alpha = 1.0

    # ---- Figure size ------------------------------------------------------
    st.header("📏 Figure size")
    col_w, col_h = st.columns(2)
    with col_w:
        fig_width = st.slider("Width (in)", 6, 20, key="ps_fig_width")
    with col_h:
        fig_height = st.slider("Height (in)", 4, 12, key="ps_fig_height")
    bar_gap = st.slider(
        "Bar gap", 0.0, 0.8, key="ps_bar_gap", step=0.05,
        help="Gap between bars within the same condition group.",
    )

    # ---- Statistics -------------------------------------------------------
    st.header("📈 Statistics")
    run_stats = st.checkbox("Run statistical tests", key="ps_run_stats")
    stat_results: pd.DataFrame | None = None
    stat_results_all: pd.DataFrame | None = None
    test_mode    = _ps("ps_test_mode")
    compare_axis = _ps("ps_compare_axis")
    show_ns      = _ps("ps_show_ns")
    bracket_linewidth = _ps("ps_bracket_linewidth")
    bracket_fontsize  = _ps("ps_bracket_fontsize")
    show_pvalue  = _ps("ps_show_pvalue")

    if run_stats:
        test_mode = st.radio(
            "Test",
            ["ttest", "tukey"],
            key="ps_test_mode",
            format_func=lambda x: {
                "ttest": "t-test vs reference condition",
                "tukey": "ANOVA + Tukey HSD (all pairs)",
            }[x],
        )

        if test_mode == "tukey":
            compare_axis = st.radio(
                "Compare",
                ["conditions", "treatments"],
                key="ps_compare_axis",
                format_func=lambda x: {
                    "conditions": "Conditions (per treatment)",
                    "treatments": "Treatments (per condition)",
                }[x],
                horizontal=True,
            )

        show_ns     = st.checkbox("Show 'ns' (non-significant)", key="ps_show_ns")
        show_pvalue = st.checkbox("Show p-values instead of stars", key="ps_show_pvalue")

        if test_mode == "ttest":
            ref_cond = st.selectbox("Reference condition", conditions)
        else:
            ref_cond = conditions[0]

        with st.spinner("Running tests…"):
            try:
                if test_mode == "ttest":
                    stat_results_all = xstats.run_ttests_vs_reference(df, ref_cond)
                elif compare_axis == "conditions":
                    stat_results_all = xstats.run_tukey(df)
                else:
                    stat_results_all = xstats.run_tukey_between_treatments(df)
            except Exception as e:
                st.error(f"Statistical test failed: {e}")
                stat_results_all = None

        if stat_results_all is not None and not stat_results_all.empty:
            def _pair_label(row) -> str:
                if compare_axis == "treatments":
                    return f"{row['group_A']} vs {row['group_B']}  [{row['condition']}]  {row['stars']}"
                elif test_mode == "ttest":
                    return f"{row['condition']} vs {row['reference']}  [{row['treatment']}]  {row['stars']}"
                else:
                    return f"{row['group_A']} vs {row['group_B']}  [{row['treatment']}]  {row['stars']}"

            stat_results_all = stat_results_all.copy()
            stat_results_all["_label"] = stat_results_all.apply(_pair_label, axis=1)

            sig_labels = stat_results_all.loc[
                stat_results_all["stars"] != "ns", "_label"
            ].tolist()

            selected_pairs = st.multiselect(
                "Show brackets for",
                options=stat_results_all["_label"].tolist(),
                default=sig_labels,
                help="Only selected comparisons are drawn. Defaults to significant pairs.",
            )

            stat_results = stat_results_all[
                stat_results_all["_label"].isin(selected_pairs)
            ].drop(columns=["_label"])
            stat_results_all = stat_results_all.drop(columns=["_label"])

        st.caption("Bracket style")
        col_blw, col_bfs = st.columns(2)
        with col_blw:
            bracket_linewidth = st.slider("Line width", 0.3, 3.0, key="ps_bracket_linewidth", step=0.1)
        with col_bfs:
            bracket_fontsize = st.slider("Font size", 6.0, 18.0, key="ps_bracket_fontsize", step=0.5)

    # ---- Typography -------------------------------------------------------
    with st.expander("🔤 Typography"):
        font_family = st.selectbox(
            "Font family",
            ["sans-serif", "serif", "monospace"],
            key="ps_font_family",
        )
        font_mode = st.radio(
            "Font sizing",
            ["Global scale", "Per element"],
            key="ps_font_mode",
            horizontal=True,
        )
        fontsizes: dict | None = None
        font_scale = _ps("ps_font_scale")
        if font_mode == "Global scale":
            font_scale = st.slider("Font scale", 0.5, 2.5, key="ps_font_scale", step=0.1)
        else:
            col_ft, col_fa = st.columns(2)
            col_ftk, col_fl = st.columns(2)
            with col_ft:
                fs_title  = st.number_input("Title",       key="ps_fs_title",  min_value=4, max_value=40)
            with col_fa:
                fs_axis   = st.number_input("Axis labels", key="ps_fs_axis",   min_value=4, max_value=40)
            with col_ftk:
                fs_tick   = st.number_input("Tick labels", key="ps_fs_tick",   min_value=4, max_value=40)
            with col_fl:
                fs_legend = st.number_input("Legend",      key="ps_fs_legend", min_value=4, max_value=40)
            fontsizes = {
                "title": fs_title, "axis_label": fs_axis,
                "tick":  fs_tick,  "legend":     fs_legend,
            }

    # ---- Advanced ---------------------------------------------------------
    with st.expander("⚙️ Advanced"):
        y_format = st.selectbox(
            "Y-axis number format",
            ["auto", "plain", "sci", "SI"],
            key="ps_y_format",
            format_func=lambda x: {
                "auto":  "Auto",
                "plain": "Plain (no sci notation)",
                "sci":   "Scientific (×10ⁿ)",
                "SI":    "SI prefix (M, k…)",
            }[x],
        )

        col_tr, col_tf = st.columns(2)
        with col_tr:
            tick_rotation = st.slider("Tick rotation °", 0, 90, key="ps_tick_rotation")
        with col_tf:
            tick_fontsize_adv = st.number_input(
                "Tick font size", key="ps_tick_fontsize_adv",
                min_value=4, max_value=40,
                help="Overrides global/per-element tick setting when changed.",
            )

        spines = st.radio(
            "Axis border style",
            ["open", "all", "none"],
            key="ps_spines",
            format_func=lambda x: {"open": "Open (L-shape)", "all": "Full box", "none": "None"}[x],
            horizontal=True,
        )
        spine_width = st.slider("Border / tick width", 0.3, 3.0, key="ps_spine_width", step=0.1)

        st.caption("Axis limits (leave blank for auto)")
        col_y1, col_y2 = st.columns(2)
        with col_y1:
            ymin_str = st.text_input("Y min", key="ps_ymin_str", placeholder="auto")
        with col_y2:
            ymax_str = st.text_input("Y max", key="ps_ymax_str", placeholder="auto")
        col_x1, col_x2 = st.columns(2)
        with col_x1:
            xmin_str = st.text_input("X min", key="ps_xmin_str", placeholder="auto")
        with col_x2:
            xmax_str = st.text_input("X max", key="ps_xmax_str", placeholder="auto")

        def _parse_lim(s: str):
            s = s.strip()
            if not s:
                return None
            try:
                return float(s)
            except ValueError:
                return None

        ylim = (_parse_lim(ymin_str), _parse_lim(ymax_str))
        xlim = (_parse_lim(xmin_str), _parse_lim(xmax_str))
        if all(v is None for v in ylim):
            ylim = None
        if all(v is None for v in xlim):
            xlim = None

        if ylim is not None and stat_results is not None:
            st.info("Y limits override bracket-driven axis expansion.")

    # ---- Data preview toggle ----------------------------------------------
    st.header("🗂️ Data preview")
    show_preview = st.checkbox("Show / edit labels & raw data", value=False)


# ---------------------------------------------------------------------------
# Resolve effective tick font size
# ---------------------------------------------------------------------------
_effective_tick_fs: float | None = None
if tick_fontsize_adv != 10:
    _effective_tick_fs = float(tick_fontsize_adv)
elif fontsizes is not None:
    _effective_tick_fs = fontsizes.get("tick")


# ---------------------------------------------------------------------------
# Label renaming (applied to df before plotting)
# ---------------------------------------------------------------------------

cond_rename: dict[str, str] = {}
treat_rename: dict[str, str] = {}

if show_preview:
    st.subheader("✏️ Rename labels")
    rename_col1, rename_col2 = st.columns(2)

    with rename_col1:
        st.caption("Condition labels (x-axis)")
        cond_df = pd.DataFrame({"Original": conditions, "Display": conditions})
        edited_cond = st.data_editor(
            cond_df,
            use_container_width=True,
            hide_index=True,
            column_config={"Original": st.column_config.TextColumn(disabled=True)},
            key="cond_editor",
        )
        cond_rename = dict(zip(edited_cond["Original"], edited_cond["Display"]))

    with rename_col2:
        st.caption("Treatment labels (legend)")
        treat_df = pd.DataFrame({"Original": treatments, "Display": treatments})
        edited_treat = st.data_editor(
            treat_df,
            use_container_width=True,
            hide_index=True,
            column_config={"Original": st.column_config.TextColumn(disabled=True)},
            key="treat_editor",
        )
        treat_rename = dict(zip(edited_treat["Original"], edited_treat["Display"]))

# Apply renames to a plotting copy (raw df is never mutated)
df_plot = df.copy()
if any(v != k for k, v in cond_rename.items()):
    df_plot["condition"] = df_plot["condition"].map(cond_rename)
    df_plot["condition"] = pd.Categorical(
        df_plot["condition"],
        categories=[cond_rename.get(c, c) for c in conditions],
        ordered=True,
    )
if any(v != k for k, v in treat_rename.items()):
    df_plot["treatment"] = df_plot["treatment"].map(treat_rename)
    df_plot["treatment"] = pd.Categorical(
        df_plot["treatment"],
        categories=[treat_rename.get(t, t) for t in treatments],
        ordered=True,
    )

if stat_results is not None and not stat_results.empty and (cond_rename or treat_rename):
    stat_results = stat_results.copy()
    for col in ["condition", "reference", "group_A", "group_B"]:
        if col in stat_results.columns:
            stat_results[col] = stat_results[col].map(lambda v: cond_rename.get(v, v))
    if "treatment" in stat_results.columns:
        stat_results["treatment"] = stat_results["treatment"].map(lambda v: treat_rename.get(v, v))


# ---------------------------------------------------------------------------
# Main area — "Plot All Sheets" batch export
# ---------------------------------------------------------------------------

def _build_fig_for_sheet(sheet_name: str) -> matplotlib.figure.Figure | None:
    d = _load_sheet(file_bytes, sheet_name)
    if d.empty:
        return None
    n_t = len(d["treatment"].unique())
    pal = utils.get_palette(palette_name if palette_name != "Custom" else "iGEM", n_t)
    fig = plotter.make_figure(
        d,
        plot_type=_base_type,
        error_bar=error_bar,
        cap_size=cap_size,
        show_points=show_points,
        point_size=point_size,
        point_alpha=point_alpha,
        log_scale=log_scale,
        show_grid=show_grid,
        palette=pal,
        bar_edge_width=bar_edge_width,
        bar_edge_color=bar_edge_color,
        bar_alpha=bar_alpha,
        bar_gap=bar_gap,
        title=sheet_name,
        xlabel=xlabel,
        ylabel=sheet_name,
        legend_title=leg_title,
        show_legend=show_legend,
        legend_inside=legend_inside,
        fig_width=fig_width,
        fig_height=fig_height,
        font_family=font_family,
        font_scale=font_scale,
        fontsizes=fontsizes,
        tick_rotation=tick_rotation,
        tick_fontsize=_effective_tick_fs,
        spines=spines,
        spine_width=spine_width,
        y_format=y_format,
        stat_results=None,
    )
    return fig


with st.expander("📦 Batch export — plot all sheets", expanded=False):
    st.caption(
        "Generates one PNG (300 DPI) per sheet and bundles them into a ZIP archive. "
        "Plot settings from the sidebar are applied to all sheets."
    )
    if st.button("Generate ZIP of all sheets"):
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            progress = st.progress(0, text="Plotting…")
            for idx, sname in enumerate(all_sheets):
                progress.progress((idx + 1) / len(all_sheets), text=f"Plotting {sname}…")
                fig_s = _build_fig_for_sheet(sname)
                if fig_s is None:
                    continue
                png_bytes = utils.fig_to_bytes(fig_s, "png", dpi=300)
                zf.writestr(f"{sname}.png", png_bytes)
                plt.close(fig_s)
            progress.empty()
        zip_buf.seek(0)
        st.download_button(
            "⬇️ Download ZIP",
            data=zip_buf.read(),
            file_name=f"{file_label.replace('.xlsx','')}_all_sheets.zip",
            mime="application/zip",
        )


# ---------------------------------------------------------------------------
# Main area — current sheet figure
# ---------------------------------------------------------------------------

fig = plotter.make_figure(
    df_plot,
    plot_type=_base_type,
    error_bar=error_bar,
    cap_size=cap_size,
    show_points=show_points,
    point_size=point_size,
    point_alpha=point_alpha,
    log_scale=log_scale,
    show_grid=show_grid,
    palette=palette,
    bar_edge_width=bar_edge_width,
    bar_edge_color=bar_edge_color,
    bar_alpha=bar_alpha,
    bar_gap=bar_gap,
    title=title,
    xlabel=xlabel,
    ylabel=ylabel,
    legend_title=leg_title,
    show_legend=show_legend,
    legend_inside=legend_inside,
    fig_width=fig_width,
    fig_height=fig_height,
    font_family=font_family,
    font_scale=font_scale,
    fontsizes=fontsizes,
    tick_rotation=tick_rotation,
    tick_fontsize=_effective_tick_fs,
    spines=spines,
    spine_width=spine_width,
    y_format=y_format,
    ylim=ylim,
    xlim=xlim,
    stat_results=stat_results,
    show_ns=show_ns,
    test_mode=test_mode,
    compare_axis=compare_axis,
    bracket_linewidth=bracket_linewidth,
    bracket_fontsize=bracket_fontsize,
    show_pvalue=show_pvalue,
)

st.pyplot(fig, use_container_width=False)

# ---------------------------------------------------------------------------
# Download buttons
# ---------------------------------------------------------------------------

safe_name = f"{file_label.replace('.xlsx','').replace(' ','_')}_{sheet}"

dl_cols = st.columns(4)
with dl_cols[0]:
    st.download_button(
        "⬇️ PNG 300 DPI",
        data=utils.fig_to_bytes(fig, "png", 300),
        file_name=f"{safe_name}_300dpi.png",
        mime="image/png",
    )
with dl_cols[1]:
    st.download_button(
        "⬇️ PNG 600 DPI",
        data=utils.fig_to_bytes(fig, "png", 600),
        file_name=f"{safe_name}_600dpi.png",
        mime="image/png",
    )
with dl_cols[2]:
    st.download_button(
        "⬇️ SVG",
        data=utils.fig_to_bytes(fig, "svg"),
        file_name=f"{safe_name}.svg",
        mime="image/svg+xml",
    )
with dl_cols[3]:
    st.download_button(
        "⬇️ PDF",
        data=utils.fig_to_bytes(fig, "pdf"),
        file_name=f"{safe_name}.pdf",
        mime="application/pdf",
    )

plt.close(fig)

# ---------------------------------------------------------------------------
# Stats table
# ---------------------------------------------------------------------------

if run_stats and stat_results is not None and not stat_results.empty:
    st.subheader("Statistical results")
    display_df = stat_results.copy()
    display_df["p_value"] = display_df["p_value"].map("{:.4f}".format)
    st.dataframe(display_df, use_container_width=True)

# ---------------------------------------------------------------------------
# Data preview
# ---------------------------------------------------------------------------

if show_preview:
    st.subheader("Summary statistics")
    pivot = (
        df.groupby(["condition", "treatment"], observed=True)["value"]
        .agg(["mean", "std", "count"])
        .rename(columns={"mean": "Mean", "std": "SD", "count": "N"})
        .reset_index()
    )
    st.dataframe(pivot, use_container_width=True)
    with st.expander("All individual values"):
        st.dataframe(
            df.sort_values(["condition", "treatment", "replicate"]),
            use_container_width=True,
        )
