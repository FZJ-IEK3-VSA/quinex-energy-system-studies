"""
Visualisation of the LCOE meta-regression (see postprocessing.meta_regression).
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.ticker import FixedLocator, NullLocator

from quinex_application.visualisation.plot_utils import (
    add_corpus_note, set_font_sizes, style_legend_frame,
)

UNADJUSTED_COLOR = '#8a8985'
ADJUSTED_COLOR = '#2a78d6'
TEXT_COLOR = '#0b0b0b'
MUTED_COLOR = '#52514e'
GRID_COLOR = '#e4e3df'

EFFECT_TICKS = [-75, -50, -25, 0, 50, 100, 200]


def plot_country_effects_dumbbell(
    country_effects: pd.DataFrame,
    reference_label: str = "Other",
    country_names: dict = None,
    alpha: float = 0.05,
    figsize: tuple = (11, 12),
    font_size: int = 16,
    corpus_note: str = None,
):
    """
    Dumbbell plot of unadjusted vs. adjusted country effects on LCOE.

    Each row is a country: the grey circle is the effect without covariates,
    the blue dot the effect after controlling for study composition, with its
    95% CI. Effects are LCOE differences relative to the pooled reference group,
    on a log scale so that -50% and +100% are equally far from 0.
    Countries significant after Holm correction are labelled in bold.

    Args:
        country_effects: Output of compare_country_effects.
        reference_label: Name of the reference group shown in the axis label.
        country_names: Optional mapping ISO3 -> display name.
        alpha: Significance level for the Holm-adjusted p-values.
        corpus_note: Optional note below the plot (e.g. describe_corpus output).

    Returns:
        Matplotlib figure.
    """
    set_font_sizes(font_size)
    df = country_effects.sort_values("adjusted_effect_%").reset_index(drop=True)

    def to_ratio(effect):
        return 1 + np.asarray(effect, dtype=float) / 100

    unadjusted = to_ratio(df["unadjusted_effect_%"])
    adjusted = to_ratio(df["adjusted_effect_%"])
    ci_low = to_ratio(df["adjusted_ci_low_%"])
    ci_high = to_ratio(df["adjusted_ci_high_%"])
    y = np.arange(len(df))

    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xscale('log')
    ax.axvline(1, color=MUTED_COLOR, linewidth=1, zorder=1)

    ax.hlines(y, ci_low, ci_high, color=ADJUSTED_COLOR, alpha=0.35, linewidth=2, zorder=2)
    ax.hlines(y, unadjusted, adjusted, color=MUTED_COLOR, linewidth=1.5, zorder=3)
    ax.scatter(unadjusted, y, s=70, facecolor='white', edgecolor=UNADJUSTED_COLOR,
               linewidth=2, zorder=4)
    ax.scatter(adjusted, y, s=70, color=ADJUSTED_COLOR, edgecolor='white',
               linewidth=1.5, zorder=5)

    names = df["country"].map(country_names or {}).fillna(df["country"])
    labels = [f"{name} ({n})" for name, n in zip(names, df["n_publications"])]
    ax.set_yticks(y)
    ax.set_yticklabels(labels, color=TEXT_COLOR)
    for tick, significant in zip(ax.get_yticklabels(), df["adjusted_p_holm"] < alpha):
        if significant:
            tick.set_fontweight('bold')
    ax.set_ylim(-0.7, len(df) - 0.3)

    x_min = min(unadjusted.min(), ci_low.min()) / 1.1
    x_max = max(unadjusted.max(), ci_high.max()) * 1.1
    ax.set_xlim(x_min, x_max)
    ticks = [t for t in EFFECT_TICKS if x_min <= to_ratio(t) <= x_max]
    ax.xaxis.set_major_locator(FixedLocator(to_ratio(ticks)))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_xticklabels([f"{t:+d}%" if t else "0%" for t in ticks])
    ax.set_xlabel(f"LCOE difference vs. {reference_label}")
    ax.set_ylabel("Country (number of publications)")

    ax.grid(axis='x', color=GRID_COLOR, linewidth=0.8, zorder=0)
    ax.tick_params(colors=MUTED_COLOR, labelcolor=TEXT_COLOR)
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    for side in ('left', 'bottom'):
        ax.spines[side].set_color(MUTED_COLOR)

    handles = [
        Line2D([], [], marker='o', linestyle='', markersize=9, markerfacecolor='white',
               markeredgecolor=UNADJUSTED_COLOR, markeredgewidth=2, label='Unadjusted'),
        Line2D([], [], marker='o', linestyle='', markersize=9, color=ADJUSTED_COLOR,
               label='Adjusted for study composition'),
        Line2D([], [], color=ADJUSTED_COLOR, alpha=0.35, linewidth=2,
               label='95% CI (adjusted)'),
    ]
    legend = ax.legend(handles=handles, loc='lower center', bbox_to_anchor=(0.5, 1.0), ncol=3)
    style_legend_frame(legend)

    fig.tight_layout()
    if corpus_note:
        add_corpus_note(fig, corpus_note + f"; bold: Holm-adjusted p < {alpha}")
    return fig
