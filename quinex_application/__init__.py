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
from .visualisation.metadata_visualisation import VisualisationMetadata
from .visualisation.quinex_visualisation import QuinexVisualisation

# Utility modules
from .visualisation import plot_utils
from .postprocessing import data_processing
from .postprocessing import country_codes

# Re-export commonly used functions
from .visualisation.plot_utils import (
    setup_plotting_environment,
    set_font_sizes,
    style_legend_frame,
)

from .postprocessing.data_processing import (
    apply_iqr_filter,
    calculate_aggregates,
    parse_temporal_scope,
    parse_spatial_scope,
)

from .postprocessing.country_codes import (
    ISO3_TO_ISO2,
    ISO2_TO_ISO3,
    CONTINENT_BOUNDS,
)

from .postprocessing.spatial_normalization import (
    SpatialNormalization
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
    
    # Spatial Normalization
    'SpatialNormalization',
]
