"""
Plot utilities for consistent styling and legend creation.

This module provides helper functions for matplotlib/seaborn plots,
including font configuration, legend styling, and marker size calculations.
"""

import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
import seaborn as sns


# =============================================================================
# Default Plot Configuration
# =============================================================================

DEFAULT_FONT_SIZE = 12
DEFAULT_FIGSIZE = (16, 8)

# Matplotlib settings for PDF/PS export (editable text)
PDF_FONTTYPE = 42
PS_FONTTYPE = 42


def configure_matplotlib_defaults():
    """
    Configure default matplotlib settings for publication-quality figures.
    """
    mpl.rcParams['pdf.fonttype'] = PDF_FONTTYPE
    mpl.rcParams['ps.fonttype'] = PS_FONTTYPE


def configure_seaborn_defaults():
    """
    Configure default seaborn theme and context.
    """
    sns.set_theme(style="ticks")
    sns.set_context("paper", font_scale=2)


def setup_plotting_environment():
    """
    Set up the complete plotting environment with all defaults.
    """
    configure_matplotlib_defaults()
    configure_seaborn_defaults()


# =============================================================================
# Font Size Configuration
# =============================================================================

def set_font_sizes(font_size: int = DEFAULT_FONT_SIZE):
    """
    Update matplotlib rcParams with consistent font sizes.
    
    Args:
        font_size: Font size to apply to all plot elements.
    """
    mpl.rcParams.update({
        'axes.titlesize': font_size,
        'axes.labelsize': font_size,
        'xtick.labelsize': font_size,
        'ytick.labelsize': font_size,
        'legend.fontsize': font_size,
        'legend.title_fontsize': font_size
    })


# =============================================================================
# Legend Utilities
# =============================================================================

def style_legend_frame(legend):
    """
    Apply consistent styling to a legend frame.
    
    Args:
        legend: matplotlib Legend object to style.
    """
    frame = legend.get_frame()
    frame.set_edgecolor('black')
    frame.set_linewidth(0.4)
    frame.set_alpha(1)


def create_color_legend(
    ax,
    fig,
    color_map: dict,
    categories: list,
    title: str,
    position: tuple = (0, 0),
    marker: str = 'X',
    marker_size: int = 10
):
    """
    Create a color legend for categorical data.
    
    Args:
        ax: Matplotlib axes to attach the legend to.
        fig: Figure object for the legend.
        color_map: Dictionary mapping category names to colors.
        categories: List of category names to include.
        title: Title for the legend.
        position: Bounding box anchor position (x, y).
        marker: Marker style for legend entries.
        marker_size: Size of legend markers.
    """
    handles = [
        mlines.Line2D(
            [], [], 
            marker=marker, 
            linestyle='None',
            markersize=marker_size, 
            markerfacecolor=color_map[cat],
            markeredgecolor='black', 
            label=cat
        )
        for cat in categories
    ]
    
    color_legend = fig.legend(
        handles=handles,
        title=title,
        loc='lower left',
        bbox_to_anchor=position,
        frameon=True
    )
    ax.add_artist(color_legend)
    style_legend_frame(color_legend)
    
    return color_legend


def create_size_legend(
    ax,
    n_values: np.ndarray,
    min_size: int = 20,
    max_size: int = 100,
    color: str = 'gray',
    alpha: float = 0.6
) -> list:
    """
    Create legend handles for sample size visualization.
    
    Args:
        ax: Matplotlib axes object.
        n_values: Array of unique sample size values.
        min_size: Minimum marker size.
        max_size: Maximum marker size.
        color: Color for legend markers.
        alpha: Transparency of legend markers.
        
    Returns:
        List of scatter plot handles for the legend.
    """
    def scale_size(n):
        if max(n_values) == min(n_values):
            return (min_size + max_size) / 2
        return min_size + (n - min(n_values)) * (max_size - min_size) / (max(n_values) - min(n_values))

    # Select representative values for legend
    if len(n_values) >= 3:
        legend_values = [n_values[0], int(np.median(n_values)), n_values[-1]]
    elif len(n_values) == 2:
        legend_values = list(n_values)
    else:
        legend_values = [n_values[0]] if len(n_values) == 1 else []

    handles = [
        ax.scatter([], [], s=scale_size(n), color=color, alpha=alpha, label=f'n = {n}')
        for n in legend_values
    ]
    
    return handles


def create_line_legend_handles(
    entities: list,
    color_map: dict,
    linewidth: int = 2
) -> list:
    """
    Create line legend handles for entity/category plots.
    
    Args:
        entities: List of entity names.
        color_map: Dictionary mapping entities to colors.
        linewidth: Width of legend lines.
        
    Returns:
        List of Line2D handles.
    """
    return [
        plt.Line2D([0], [0], color=color_map[e], lw=linewidth)
        for e in entities
    ]


# =============================================================================
# Marker Size Utilities
# =============================================================================

def calculate_marker_sizes(
    values,
    min_size: float = 30,
    max_size: float = 600
) -> np.ndarray:
    """
    Scale numeric values to marker sizes.
    
    Args:
        values: Numeric Series or array to scale.
        min_size: Minimum marker size.
        max_size: Maximum marker size.
        
    Returns:
        Array of scaled marker sizes.
    """
    values = np.asarray(values)
    
    if values.max() == values.min():
        return np.full(len(values), (min_size + max_size) / 2)
    
    return min_size + (values - values.min()) / (values.max() - values.min()) * (max_size - min_size)


def map_values_to_sizes(
    values: np.ndarray,
    min_n: float,
    max_n: float,
    size_range: tuple = (50, 200)
) -> np.ndarray:
    """
    Map values to marker sizes within a specified range.
    
    Args:
        values: Values to map.
        min_n: Minimum value in the dataset.
        max_n: Maximum value in the dataset.
        size_range: Tuple of (min_size, max_size).
        
    Returns:
        Array of mapped sizes.
    """
    return np.interp(values, [min_n, max_n], list(size_range))


# =============================================================================
# Color Palette Utilities
# =============================================================================

def get_color_map(
    datasets: list,
    color_column: str,
    palette: dict = None
) -> tuple:
    """
    Create a color mapping for categorical values across datasets.
    
    Args:
        datasets: List of dicts, each containing a DataFrame under key 'df'.
        color_column: Column name specifying categories to color by.
        palette: Optional dict mapping category names to colors.
        
    Returns:
        Tuple of (color_map dict, ordered category list).
    """
    seen = set()
    all_color_values = []

    for d in datasets:
        color_counts = d['df'][color_column].value_counts()
        for cat in color_counts.index.tolist():
            if cat not in seen:
                seen.add(cat)
                all_color_values.append(cat)

    if palette:
        color_map = {cat: palette.get(cat, "#CCCCCC") for cat in all_color_values}
    else:
        color_list = sns.color_palette("tab10", n_colors=len(all_color_values))
        color_map = dict(zip(all_color_values, color_list))
    
    return color_map, all_color_values


def create_entity_color_palette(entities: list) -> dict:
    """
    Create a color palette for a list of entities.
    
    Args:
        entities: List of entity names.
        
    Returns:
        Dictionary mapping entities to colors.
    """
    palette_colors = sns.color_palette("tab10", n_colors=len(entities))
    return dict(zip(entities, palette_colors))


# =============================================================================
# Subplot Layout Utilities
# =============================================================================

def calculate_subplot_layout(n_plots: int, n_cols: int = 2) -> tuple:
    """
    Calculate the number of rows needed for a subplot grid.
    
    Args:
        n_plots: Number of plots to create.
        n_cols: Number of columns in the grid.
        
    Returns:
        Tuple of (n_rows, n_cols).
    """
    import math
    n_rows = math.ceil(n_plots / n_cols)
    return n_rows, n_cols


def flatten_axes(axes, n_plots: int):
    """
    Flatten axes array for consistent iteration.
    
    Args:
        axes: Axes object(s) from plt.subplots.
        n_plots: Number of plots.
        
    Returns:
        List of axes.
    """
    if n_plots == 1:
        return [axes]
    return axes.flatten()


def hide_empty_axes(axes, n_plots: int):
    """
    Hide unused axes in a subplot grid.
    
    Args:
        axes: Flattened list of axes.
        n_plots: Number of actual plots.
    """
    for ax in axes[n_plots:]:
        ax.axis('off')


# =============================================================================
# Grid and Axis Styling
# =============================================================================

def style_grid(ax, linestyle: str = '--', alpha: float = 0.6):
    """
    Apply consistent grid styling to an axis.
    
    Args:
        ax: Matplotlib axes object.
        linestyle: Grid line style.
        alpha: Grid transparency.
    """
    ax.grid(linestyle=linestyle, alpha=alpha)


def set_axis_labels(
    ax,
    xlabel: str = None,
    ylabel: str = None,
    title: str = None,
    title_loc: str = 'left',
    title_weight: str = 'bold'
):
    """
    Set axis labels and title with consistent styling.
    
    Args:
        ax: Matplotlib axes object.
        xlabel: X-axis label.
        ylabel: Y-axis label.
        title: Plot title.
        title_loc: Title location ('left', 'center', 'right').
        title_weight: Title font weight.
    """
    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title, loc=title_loc, fontweight=title_weight)
