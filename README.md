# Experimental Results Plotter

A browser-based plotting tool for luciferase reporter assay data (or any GraphPad Prism-style grouped Excel file). Upload your data, configure every visual aspect of the figure in the sidebar, run statistics, and export publication-ready PNG / SVG / PDF — all without writing code.

---

## Quick start

```bash
conda create -n plotting python=3.11
conda activate plotting
pip install -e .
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## Input data format

The tool reads **Excel files (.xlsx)** laid out in the **GraphPad Prism grouped** format:

| Condition | Treatment A |  |  | Treatment B |  |  |
|---|---|---|---|---|---|---|
| Group 1 | rep1 | rep2 | rep3 | rep1 | rep2 | rep3 |
| Group 2 | … |  |  | … |  |  |

Rules:
- **Row 1** — `Condition` in cell A1; treatment names in the **first column of each group**; the remaining replicate columns in that group are left empty.
- **Rows 2+** — one row per experimental condition; numeric replicate values packed into the columns of each group.
- Replicate counts can vary between groups and between files.
- Sheets with Excel formulas (e.g. a `Normalized` sheet computing Nano/Firefly ratios) are supported — the tool reads cached values.
- Multiple sheets per workbook are supported; you switch between them with the **Sheet** selector.

---

## Sidebar reference

### 📂 Data

| Control | Description |
|---|---|
| **Upload .xlsx file** | Drag-and-drop or click to browse. |
| **…or enter a local file path** | Type an absolute path (e.g. `C:\data\results.xlsx`) if the file is already on disk. |
| **Sheet** | Select which sheet of the workbook to plot. |

---

### 🔍 Filter

| Control | Description |
|---|---|
| **Show conditions** | Multiselect. Uncheck conditions you want to hide from the plot. Removed conditions are also excluded from statistical tests. |

---

### 📊 Plot type

| Option | Description |
|---|---|
| **bar+strip** | Grouped bar chart with mean ± error bars, overlaid with individual data points. |
| **box+strip** | Box-and-whisker plot (IQR box, median line, no outlier markers) overlaid with data points. |
| **violin+strip** | Kernel density violin overlaid with data points. |

---

### 📐 Y-axis

| Control | Description |
|---|---|
| **Log scale** | Switches the y-axis to log₁₀. Disabled automatically if any value ≤ 0. |
| **Y-axis gridlines** | Draws light horizontal grid lines behind the bars. |
| **Error bar** *(bar only)* | SD — standard deviation; SEM — standard error of the mean; 95 % CI — confidence interval. |
| **Cap size** *(bar only)* | Width of the horizontal cap on error bars (0 = no caps). |
| **Show individual data points** | Overlay a strip plot of all replicates as black dots. |
| **Dot size** | Diameter of the strip dots (pt). |
| **Dot opacity** | Transparency of the strip dots (1 = opaque). |

---

### 🏷️ Labels

| Control | Description |
|---|---|
| **Title** | Figure title. Pre-filled with `filename · sheet`. |
| **X-axis label** | Label below the x-axis. |
| **Y-axis label** | Label on the y-axis. |
| **Legend title** | Header text of the colour legend. |
| **Show legend** | Toggle legend visibility. |
| **Legend inside** | Place the legend inside the plot area (top-right) instead of outside to the right. |

---

### 🎨 Colors

| Control | Description |
|---|---|
| **Palette** | Choose a preset colour scheme: **iGEM** (lab default), Tab10, Viridis, Pastel, Colorblind, Set2. Select **Custom** to assign a colour to each treatment individually. |
| **Edge width** *(bar only)* | Thickness of the bar outline in pt. Set to 0 to remove outlines entirely. |
| **Edge color** *(bar only)* | Colour of the bar outline. |
| **Bar opacity** *(bar only)* | Transparency of bar fill (1 = fully opaque). |

---

### 📏 Figure size

| Control | Description |
|---|---|
| **Width / Height** | Figure dimensions in inches. |
| **Bar gap** | Fraction of bar width used as intra-group gap. 0 = bars touching (default); 0.5 = bars at half their natural width with space between them. Does not affect strip dot or bracket positions. |

---

### 📈 Statistics

| Control | Description |
|---|---|
| **Run statistical tests** | Master toggle. |
| **Test** | **t-test vs reference condition** — independent two-sample t-test comparing every (treatment, condition) pair against a chosen reference condition. **ANOVA + Tukey HSD** — one-way ANOVA followed by Tukey's honestly significant difference test for all pairwise comparisons. |
| **Compare** *(Tukey only)* | **Conditions (per treatment)** — compares condition groups within each treatment. **Treatments (per condition)** — compares treatments within each condition group. |
| **Reference condition** *(t-test only)* | The baseline condition all others are compared against. |
| **Show 'ns'** | Draw brackets even for non-significant comparisons. |
| **Show p-values instead of stars** | Label brackets with `p=0.023` / `p<0.001` instead of `*` / `***`. |
| **Show brackets for** | Multiselect of all computed pairs. Defaults to significant pairs only (p < 0.05). Add or remove individual brackets as needed. |
| **Bracket line width** | Thickness of the significance bracket lines. |
| **Bracket font size** | Font size of the star / p-value text above brackets. |

Significance thresholds: `***` p < 0.001 · `**` p < 0.01 · `*` p < 0.05 · `ns` p ≥ 0.05

Brackets are stacked automatically so they never overlap: non-overlapping brackets share the same height tier; overlapping brackets are pushed to higher tiers.

---

### 🔤 Typography

| Control | Description |
|---|---|
| **Font family** | sans-serif (default), serif, or monospace. |
| **Font sizing — Global scale** | A single multiplier (0.5–2.5) applied to all text elements simultaneously. |
| **Font sizing — Per element** | Set individual sizes for Title, Axis labels, Tick labels, and Legend text. |

---

### ⚙️ Advanced

| Control | Description |
|---|---|
| **Y-axis number format** | **Auto** — matplotlib default. **Plain** — force integer / decimal notation, no scientific. **Scientific** — always use ×10ⁿ notation. **SI prefix** — display `1M`, `500k`, etc. Useful for raw luminescence counts. |
| **Tick rotation** | Angle of x-axis tick labels in degrees (0–90). |
| **Tick font size** | Overrides the tick size from the Typography section when set to a value other than 10. |
| **Axis border style** | **Open (L-shape)** — top and right spines removed (default). **Full box** — all four borders visible. **None** — no borders. |
| **Border / tick width** | Linewidth of axis spines and tick marks. |
| **Y min / Y max** | Override the automatic y-axis limits. Leave blank for auto. Note: if significance brackets are enabled, they are drawn before the limit is applied — brackets outside the forced range will be clipped. |
| **X min / X max** | Override the automatic x-axis limits. |

---

### 🗂️ Data preview / Label editor

Enable **Show / edit labels & raw data** to reveal three sections:

1. **Rename condition labels** — editable table mapping original condition names (as they appear in the Excel file) to display labels shown on the x-axis. Changes are ephemeral; the source file is never modified.
2. **Rename treatment labels** — same for treatment names shown in the legend.
3. **Summary statistics** — mean, SD, and N for every condition × treatment group.
4. **All individual values** — expandable table of the full long-format dataset.

---

## Export

Four download buttons appear below every plot:

| Button | Format | DPI |
|---|---|---|
| PNG 300 DPI | Raster | 300 |
| PNG 600 DPI | Raster | 600 |
| SVG | Vector | — |
| PDF | Vector (text editable in Illustrator / Inkscape) | — |

### Batch export

The **📦 Batch export** expander generates one PNG (300 DPI) per sheet in the workbook and bundles them into a single ZIP file. All current sidebar settings (plot type, colours, fonts, figure size) are applied to every sheet; statistics are not run in batch mode.

---

## Project structure

```
app.py        # Streamlit entry point — all UI widgets and wiring
parser.py     # Excel → tidy long-format DataFrame
plotter.py    # DataFrame → matplotlib Figure
stats.py      # Statistical tests + significance bar drawing
utils.py      # Colour palettes, figure export helpers
data/         # Example files (E24_Analysis.xlsx, 2025-09-22_results_F43.xlsx)
```

---

## Requirements

```
streamlit>=1.35
pandas>=2.0
openpyxl>=3.1
matplotlib>=3.8
seaborn>=0.13
scipy>=1.10
pingouin>=0.5
numpy>=1.24
```

Install everything at once:

```bash
pip install -e .
# or
pip install -r requirements.txt
```
