"""
Quinex Application Package

This package provides tools for visualizing and analyzing research paper metadata
and extracted data from the quinex system.

Modules:
    - metadata_visualisation: Visualization for paper metadata (countries, SJR, trends)
    - quinex_visualisation: Visualization for extracted research data
    - plot_utils: Common plotting utilities and styling functions
    - data_processing: Data transformation and statistical functions
    - country_codes: ISO country code mappings and geographic constants
"""

# Core visualization classes
from .metadata_visualisation import VisualisationMetadata
from .quinex_visualisation import QuinexVisualisation

# Utility modules
from . import plot_utils
from . import data_processing
from . import country_codes

# Re-export commonly used functions
from .plot_utils import (
    setup_plotting_environment,
    set_font_sizes,
    style_legend_frame,
)

from .data_processing import (
    apply_iqr_filter,
    calculate_aggregates,
    parse_temporal_scope,
    parse_spatial_scope,
)

from .country_codes import (
    ISO3_TO_ISO2,
    ISO2_TO_ISO3,
    CONTINENT_BOUNDS,
)

__all__ = [
    # Classes
    'VisualisationMetadata',
    'QuinexVisualisation',
    
    # Modules
    'plot_utils',
    'data_processing',
    'country_codes',
    
    # Functions
    'setup_plotting_environment',
    'set_font_sizes',
    'style_legend_frame',
    'apply_iqr_filter',
    'calculate_aggregates',
    'parse_temporal_scope',
    'parse_spatial_scope',
    
    # Constants
    'ISO3_TO_ISO2',
    'ISO2_TO_ISO3',
    'CONTINENT_BOUNDS',
]
