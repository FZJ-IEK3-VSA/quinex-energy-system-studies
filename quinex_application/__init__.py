"""
Quinex Application Package

This package provides tools for visualizing and analyzing research paper metadata
and extracted data from the quinex system.

Modules:
    - metadata_visualisation: Visualization for paper metadata (countries, SJR, trends)
    - temporal_visualisation: Visualization for extracted research data over time
    - spatial_visualisation: Visualization for spatial distribution of research data
    - plot_utils: Common plotting utilities and styling functions
    - data_processing: Data transformation and statistical functions
    - data_loading: Memory-efficient loading of the large parquet datasets
    - country_codes: ISO country code mappings and geographic constants

Submodules are imported lazily on first access, so importing e.g.
quinex_application.visualisation.temporal_visualisation does not load
unrelated heavy dependencies (plotly, geopy, spaCy).
"""
# The names in __all__ are provided lazily by __getattr__ below.
# pylint: disable=undefined-all-variable

import importlib

# Public name -> (module, attribute). attribute None means the module itself.
_LAZY_ATTRIBUTES = {
    # Classes
    'VisualisationMetadata': ('.visualisation.metadata_visualisation', 'VisualisationMetadata'),
    'TemporalVisualisation': ('.visualisation.temporal_visualisation', 'TemporalVisualisation'),
    'SpatialVisualisation': ('.visualisation.spatial_visualisation', 'SpatialVisualisation'),
    'TextAvailabilityVisualisation': ('.visualisation.text_availability_visualisation', 'TextAvailabilityVisualisation'),

    # Modules
    'plot_utils': ('.visualisation.plot_utils', None),
    'data_processing': ('.postprocessing.data_processing', None),
    'data_loading': ('.postprocessing.data_loading', None),
    'country_codes': ('.postprocessing.country_codes', None),

    # Functions
    'setup_plotting_environment': ('.visualisation.plot_utils', 'setup_plotting_environment'),
    'set_font_sizes': ('.visualisation.plot_utils', 'set_font_sizes'),
    'style_legend_frame': ('.visualisation.plot_utils', 'style_legend_frame'),
    'show_figure': ('.visualisation.plot_utils', 'show_figure'),
    'add_corpus_note': ('.visualisation.plot_utils', 'add_corpus_note'),
    'filter_corpus': ('.postprocessing.data_processing', 'filter_corpus'),
    'describe_corpus': ('.postprocessing.data_processing', 'describe_corpus'),
    'apply_iqr_filter': ('.postprocessing.data_processing', 'apply_iqr_filter'),
    'calculate_aggregates': ('.postprocessing.data_processing', 'calculate_aggregates'),
    'parse_temporal_scope': ('.postprocessing.data_processing', 'parse_temporal_scope'),
    'parse_spatial_scope': ('.postprocessing.data_processing', 'parse_spatial_scope'),
    'load_property_data': ('.postprocessing.data_loading', 'load_property_data'),
    'filter_by_unit_uri': ('.postprocessing.data_loading', 'filter_by_unit_uri'),

    # Constants
    'ISO3_TO_ISO2': ('.postprocessing.country_codes', 'ISO3_TO_ISO2'),
    'ISO2_TO_ISO3': ('.postprocessing.country_codes', 'ISO2_TO_ISO3'),
    'CONTINENT_BOUNDS': ('.postprocessing.country_codes', 'CONTINENT_BOUNDS'),

    # Spatial Normalization
    'SpatialNormalization': ('.postprocessing.spatial_normalization', 'SpatialNormalization'),
}

__all__ = list(_LAZY_ATTRIBUTES)


def __getattr__(name):
    if name not in _LAZY_ATTRIBUTES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = _LAZY_ATTRIBUTES[name]
    module = importlib.import_module(module_name, __name__)
    value = module if attribute is None else getattr(module, attribute)
    globals()[name] = value
    return value


def __dir__():
    return sorted(list(globals()) + __all__)
