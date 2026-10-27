"""Comparison of publications processed from full text and from abstract only."""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from quinex_application.visualisation.plot_utils import (
    set_font_sizes,
    setup_plotting_environment,
    add_corpus_note,
)
from quinex_application.postprocessing.data_processing import (
    classify_dois_full_text,
    FULL_TEXT_LABEL,
    ABSTRACT_ONLY_LABEL,
)


GROUP_ORDER = [FULL_TEXT_LABEL, ABSTRACT_ONLY_LABEL]

# Categorical slots 1 and 2 of the validated reference palette (blue / orange).
TEXT_AVAILABILITY_COLORS = {
    FULL_TEXT_LABEL: "#2a78d6",
    ABSTRACT_ONLY_LABEL: "#eb6834",
}


class TextAvailabilityVisualisation:
    """Compare the full text and abstract-only subsets of the extracted records."""

    # Display names and label positions (lon, lat of the text box, in degrees)
    # for the example countries on the overview map.
    EXAMPLE_COUNTRY_NAMES = {
        'GB': 'UK', 'IN': 'India', 'US': 'USA', 'CN': 'China', 'BR': 'Brazil',
        'AU': 'Australia', 'DE': 'Germany', 'ZA': 'South Africa', 'DK': 'Denmark',
    }
    EXAMPLE_LABEL_POSITIONS = {
        'US': (-150, 22), 'GB': (-32, 42), 'IN': (66, -12), 'CN': (152, 52),
        'BR': (-18, -28), 'AU': (168, -45), 'DE': (30, 72), 'ZA': (45, -45),
        'DK': (10, 75),
    }

    def __init__(self):
        """Initialize plotting defaults and group colors."""
        self.colors = dict(TEXT_AVAILABILITY_COLORS)
        self._natural_earth = None
        setup_plotting_environment()

    # =========================================================================
    # Data Preparation
    # =========================================================================

    def add_text_availability(
        self,
        df: pd.DataFrame,
        doi_col: str = "DOI",
        source_col: str = "source",
        output_col: str = "text_availability",
    ) -> pd.DataFrame:
        """
        Add a column labelling every record with the text availability of its publication.

        The column is added in place (no copy of the large record DataFrame).

        Args:
            df: Record-level DataFrame (one row per extracted quantity).
            doi_col: Column containing DOI/paper identifiers.
            source_col: Column containing the text source.
            output_col: Name of the new column.

        Returns:
            The same DataFrame with output_col ('Full text' / 'Abstract only').
        """
        is_full_text = classify_dois_full_text(df, doi_col, source_col)
        labels = is_full_text.map({True: FULL_TEXT_LABEL, False: ABSTRACT_ONLY_LABEL})
        df[output_col] = pd.Categorical(
            df[doi_col].astype('string').str.strip().map(labels),
            categories=GROUP_ORDER,
        )
        return df

    def publication_table(
        self,
        df: pd.DataFrame,
        doi_col: str = "DOI",
        year_col: str = "publication_year",
        country_col: str = "associated_countries",
        group_col: str = "text_availability",
    ) -> pd.DataFrame:
        """
        Aggregate records to one row per publication.

        Args:
            df: Record-level DataFrame with group_col (see add_text_availability).
            doi_col: Column containing DOI/paper identifiers.
            year_col: Column containing publication year.
            country_col: Column containing the publication's countries (optional).
            group_col: Column containing the text availability label.

        Returns:
            DataFrame indexed by DOI with columns group_col, year_col,
            'n_records' and (if available) country_col.
        """
        grouped = df.groupby(doi_col, sort=False, observed=True)
        pubs = pd.DataFrame({
            group_col: grouped[group_col].first(),
            year_col: grouped[year_col].first(),
            'n_records': grouped.size(),
        })
        if country_col and country_col in df.columns:
            pubs[country_col] = grouped[country_col].first()
        pubs[group_col] = pd.Categorical(pubs[group_col], categories=GROUP_ORDER)
        return pubs

    def corpus_publication_table(
        self,
        paper_df: pd.DataFrame,
        record_pubs: pd.DataFrame,
        status_col: str = "Download_Status",
        paper_year_col: str = "Year",
        doi_col: str = "DOI",
        year_col: str = "publication_year",
        country_col: str = "associated_countries",
        group_col: str = "text_availability",
    ) -> pd.DataFrame:
        """
        Build the publication table of the complete processed corpus.

        Unlike publication_table, this includes publications from which no
        record was extracted (n_records = 0). Text availability is taken from
        the download status: 'Succeeded' = full text, 'Abstract Succeeded' =
        abstract only; other statuses (failed, not attempted) are excluded.

        Args:
            paper_df: Paper dataset with doi_col, status_col and paper_year_col.
            record_pubs: Publication table from the records (see publication_table).
            status_col: Download status column.
            paper_year_col: Publication year column of paper_df.
            doi_col: DOI column of paper_df.
            year_col: Name of the year column in the result.
            country_col: Country column taken over from record_pubs (publications
                without records have no country information).
            group_col: Name of the text availability column.

        Returns:
            DataFrame indexed by DOI with group_col, year_col, 'n_records' and country_col.
        """
        status_to_group = {'Succeeded': FULL_TEXT_LABEL, 'Abstract Succeeded': ABSTRACT_ONLY_LABEL}
        corpus = paper_df[paper_df[status_col].isin(status_to_group)].drop_duplicates(doi_col)
        corpus = corpus.set_index(corpus[doi_col].astype(str).str.strip())

        pubs = pd.DataFrame({
            group_col: pd.Categorical(corpus[status_col].map(status_to_group), categories=GROUP_ORDER),
            year_col: corpus[paper_year_col].astype('Int64'),
        }, index=corpus.index)
        pubs.index.name = doi_col
        pubs['n_records'] = record_pubs['n_records'].reindex(pubs.index).fillna(0).astype(int)
        if country_col in record_pubs.columns:
            pubs[country_col] = record_pubs[country_col].reindex(pubs.index)

        n_missing = (~record_pubs.index.isin(pubs.index)).sum()
        if n_missing:
            print(f"Note: {n_missing} publications with records are not in the processed corpus "
                  f"({status_col} not in {list(status_to_group)}) and are excluded.")
        return pubs

    def temporal_table(
        self,
        pubs: pd.DataFrame,
        year_col: str = "publication_year",
        group_col: str = "text_availability",
        year_range: tuple = None,
    ) -> pd.DataFrame:
        """Return publications per year and group, the full text share [%] and mean records per publication."""
        data = pubs[pubs[year_col].notna()]
        years = data[year_col].astype(int)
        if year_range is not None:
            data = data[years.between(*year_range)]
            years = years[data.index]

        table = (
            data.groupby([years, data[group_col]], observed=False)
            .size()
            .unstack(group_col, fill_value=0)
            .reindex(columns=GROUP_ORDER, fill_value=0)
        )
        table.index.name = year_col
        table['total'] = table[GROUP_ORDER].sum(axis=1)
        table['full text share [%]'] = (100 * table[FULL_TEXT_LABEL] / table['total']).round(2)

        mean_records = (
            data.groupby([years, data[group_col]], observed=False)['n_records']
            .mean()
            .unstack(group_col)
            .reindex(columns=GROUP_ORDER)
        )
        for group in GROUP_ORDER:
            table[f'{group}: mean records / publication'] = mean_records[group].round(2)
        return table

    def country_table(
        self,
        pubs: pd.DataFrame,
        country_col: str = "associated_countries",
        group_col: str = "text_availability",
    ) -> pd.DataFrame:
        """
        Return publications per country and group (whole counting: a publication
        counts once for each of its countries) plus the full text share [%].

        Indexed by ISO2 code, with the country name as first column.
        """
        exploded = pubs[[group_col, country_col]].explode(country_col)
        exploded = exploded[exploded[country_col].notna() & exploded[country_col].astype(str).str.strip().ne('')]

        table = (
            exploded.groupby([country_col, group_col], observed=False)
            .size()
            .unstack(group_col, fill_value=0)
            .reindex(columns=GROUP_ORDER, fill_value=0)
        )
        table.index.name = 'country'
        table.columns.name = None
        table['total'] = table[GROUP_ORDER].sum(axis=1)
        table = table[table['total'] > 0]
        table['full text share [%]'] = (100 * table[FULL_TEXT_LABEL] / table['total']).round(2)
        table.insert(0, 'country name', [self._country_name(code) for code in table.index])
        return table.sort_values('total', ascending=False)

    # =========================================================================
    # Overview Figure
    # =========================================================================

    def plot_text_availability_overview(
        self,
        pubs: pd.DataFrame,
        year_col: str = "publication_year",
        country_col: str = "associated_countries",
        group_col: str = "text_availability",
        year_range: tuple = (2010, 2024),
        example_countries: list = ('US', 'GB', 'IN', 'CN', 'BR', 'AU'),
        label_positions: dict = None,
        min_publications: int = 30,
        cmap: str = "Blues",
        number_xticks: int = 2,
        note=True,
        figsize: tuple = (24, 20),
        font_size: int = 30,
    ):
        """
        Combined figure on full text vs. abstract-only publications.

        a) mean extracted records per publication per year for both subsets,
           with the mean over all years as dashed reference line,
        b) share of full-text publications per year, with the share over all
           years as dashed reference line,
        c) world map of the full text share per country with labelled examples.

        Args:
            pubs: Publication table of the processed corpus (see corpus_publication_table).
            year_col: Column containing publication year.
            country_col: Column containing lists of country codes.
            group_col: Column containing the text availability label.
            year_range: (min_year, max_year) for panels a and b.
            example_countries: ISO2 codes of the countries labelled on the map.
            label_positions: Optional {ISO2: (lon, lat)} of the label boxes
                (defaults: EXAMPLE_LABEL_POSITIONS).
            min_publications: Countries with fewer publications are hatched.
            cmap: Sequential colormap (single hue) for the map.
            number_xticks: Interval for x-axis ticks of panels a and b.
            note: True adds an automatic corpus note below the figure, a string
                a custom note, False none.
            figsize: Figure size.
            font_size: Font size.

        Returns:
            Tuple of (fig, {'temporal': table, 'countries': table, 'overall': table}).
        """
        import cartopy.crs as ccrs
        from matplotlib.colors import Normalize
        from matplotlib.cm import ScalarMappable
        from matplotlib.gridspec import GridSpec
        from quinex_application.postprocessing.country_codes import ISO2_TO_ISO3
        from quinex_application.visualisation.spatial_visualisation import SpatialVisualisation

        set_font_sizes(font_size)
        label_positions = {**self.EXAMPLE_LABEL_POSITIONS, **(label_positions or {})}

        temporal = self.temporal_table(pubs, year_col, group_col, year_range)
        countries = self.country_table(pubs, country_col, group_col)

        in_range = pubs[pubs[year_col].notna()]
        in_range = in_range[in_range[year_col].astype(int).between(*year_range)]
        overall = pd.DataFrame({
            'publications': in_range.groupby(group_col, observed=False).size(),
            'mean records / publication': in_range.groupby(group_col, observed=False)['n_records'].mean(),
        }).reindex(GROUP_ORDER)
        overall_share = 100 * overall.loc[FULL_TEXT_LABEL, 'publications'] / overall['publications'].sum()

        fig = plt.figure(figsize=figsize)
        gs = GridSpec(2, 2, figure=fig, height_ratios=[1, 1.7], hspace=0.25, wspace=0.25)
        ax_yield = fig.add_subplot(gs[0, 0])
        ax_share = fig.add_subplot(gs[0, 1])
        ax_map = fig.add_subplot(gs[1, :], projection=ccrs.Robinson())

        x_min, x_max = year_range[0] - 0.5, year_range[1] + 0.5

        # a) Mean records per publication
        for group in GROUP_ORDER:
            color = self.colors[group]
            mean_all_years = overall.loc[group, 'mean records / publication']
            ax_yield.plot(
                temporal.index, temporal[f'{group}: mean records / publication'],
                color=color, linewidth=2, marker='o', markersize=10, label=group,
            )
            ax_yield.axhline(mean_all_years, color=color, linestyle='--', linewidth=1.5)
            ax_yield.annotate(
                f"Ø {mean_all_years:.1f}", xy=(x_min, mean_all_years), xytext=(6, 6),
                textcoords='offset points', ha='left', va='bottom', fontsize=font_size * 0.8,
            )
        ax_yield.set_yscale('log')
        ax_yield.set_ylim(1, 300)
        ax_yield.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}"))
        ax_yield.set_ylabel("Mean records\nper publication")
        ax_yield.legend(loc='center right', bbox_to_anchor=(1, 0.55))

        # b) Full text share
        ax_share.plot(
            temporal.index, temporal['full text share [%]'],
            color=self.colors[FULL_TEXT_LABEL], linewidth=2, marker='o', markersize=10,
        )
        ax_share.axhline(overall_share, color=self.colors[FULL_TEXT_LABEL], linestyle='--', linewidth=1.5)
        ax_share.annotate(
            f"All years: {overall_share:.1f}%", xy=(x_min, overall_share), xytext=(6, 6),
            textcoords='offset points', ha='left', va='bottom', fontsize=font_size * 0.8,
        )
        ax_share.set_ylim(0, 100)
        ax_share.set_ylabel("Full text share [%]")

        for ax, title in ((ax_yield, "a"), (ax_share, "b")):
            ax.set_title(title, loc='left', fontweight='bold')
            ax.set_xlabel("Publication Year")
            ax.set_xlim(x_min, x_max)
            ax.xaxis.set_major_locator(mticker.MultipleLocator(number_xticks))
            ax.grid(linestyle='--', alpha=0.4)
            ax.set_axisbelow(True)

        # c) Map of the full text share per country: one row per (publication, country)
        # with 100 for full text and 0 for abstract only, so the per-country mean is
        # the full text share in percent.
        exploded = pubs[[group_col, country_col]].explode(country_col)
        exploded = exploded[exploded[country_col].notna()]
        rows = pd.DataFrame({
            'country': exploded[country_col].astype(str).str.strip(),
            'full_text_share': np.where(exploded[group_col] == FULL_TEXT_LABEL, 100.0, 0.0),
        })
        scalar_map = ScalarMappable(norm=Normalize(vmin=0, vmax=100), cmap=cmap)
        SpatialVisualisation()._plot_world_choropleth_subplot(
            ax_map,
            {'df': rows, 'value_column': 'full_text_share', 'title': 'c'},
            scalar_map,
            continent=None,
            country_column='country',
            aggregation='mean',
            min_datapoints=min_publications,
        )
        ax_map.set_title("c", loc='left', fontweight='bold', fontsize=font_size)
        cbar = fig.colorbar(scalar_map, ax=ax_map, orientation='vertical', fraction=0.02, pad=0.01, shrink=0.7)
        cbar.set_ticks([0, 25, 50, 75, 100])
        cbar.ax.tick_params(labelsize=font_size * 0.8)
        cbar.ax.set_ylabel("Full text share [%]", fontsize=font_size)

        # Example labels with leader lines
        geometries = {iso3: record.geometry for iso3, record in self._natural_earth_records().items()}
        geo_transform = ccrs.PlateCarree()._as_mpl_transform(ax_map)
        for code in example_countries:
            iso3 = ISO2_TO_ISO3.get(code)
            if code not in countries.index or iso3 not in geometries:
                print(f"Note: no data or geometry for example country {code}, skipped.")
                continue
            anchor = geometries[iso3].representative_point()
            row = countries.loc[code]
            ax_map.annotate(
                f"{self.EXAMPLE_COUNTRY_NAMES.get(code, row['country name'])}\n"
                f"{row['full text share [%]']:.0f}% (n = {int(row['total']):,})",
                xy=(anchor.x, anchor.y), xycoords=geo_transform,
                xytext=label_positions.get(code, (anchor.x, anchor.y + 15)), textcoords=geo_transform,
                ha='center', va='center', fontsize=font_size * 0.7,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='#52514e', linewidth=1),
                arrowprops=dict(arrowstyle='-', color='#52514e', linewidth=1.2),
            )

        if note is True:
            n_full_text, n_abstract = (int(overall.loc[g, 'publications']) for g in GROUP_ORDER)
            map_note = self._spatial_note(pubs, country_col, group_col).replace("Corpus: ", "")
            note = (
                f"Corpus: a, b: all processed publications {year_range[0]}–{year_range[1]} "
                f"(incl. those without extracted records); n = {n_full_text + n_abstract:,} publications "
                f"(full text: {n_full_text:,}, abstract only: {n_abstract:,}); Ø = mean over all years\n"
                f"c: {map_note[0].lower()}{map_note[1:]}; hatched: < {min_publications} publications"
            )
        self._add_note(fig, note)

        tables = {
            'temporal': temporal,
            'countries': countries,
            'overall': overall.assign(**{'full text share [%]': overall_share}).round(2),
        }
        return fig, tables

    # =========================================================================
    # Helpers
    # =========================================================================

    def _natural_earth_records(self) -> dict:
        """Return the Natural Earth 110m country records keyed by ISO3 (ADM0_A3), cached."""
        if self._natural_earth is None:
            import cartopy.io.shapereader as shpreader

            reader = shpreader.Reader(
                shpreader.natural_earth(resolution='110m', category='cultural', name='admin_0_countries')
            )
            self._natural_earth = {r.attributes.get('ADM0_A3'): r for r in reader.records()}
        return self._natural_earth

    def _country_name(self, iso2: str) -> str:
        """Return the country name for an ISO2 code (Natural Earth, else first known name variant)."""
        from quinex_application.postprocessing.country_codes import ISO2_TO_ISO3, COUNTRY_NAME_VARIANTS

        iso3 = ISO2_TO_ISO3.get(str(iso2).upper())
        record = self._natural_earth_records().get(iso3)
        if record is not None:
            return record.attributes.get('NAME', iso2)
        variant = next((name for name, code in COUNTRY_NAME_VARIANTS.items() if code == iso3), None)
        return variant or str(iso2)

    def _has_country(self, pubs: pd.DataFrame, country_col: str) -> pd.Series:
        """Return a boolean mask of publications with at least one country code."""
        def _non_empty(countries) -> bool:
            if countries is None or isinstance(countries, float):
                return False
            return any(str(c).strip() for c in countries)
        return pubs[country_col].apply(_non_empty)

    def _spatial_note(self, pubs: pd.DataFrame, country_col: str, group_col: str) -> str:
        """Corpus note for the map panel."""
        with_country = pubs[self._has_country(pubs, country_col)]
        return self.describe_publications(
            with_country,
            "Publications with at least one extracted record and country information (whole counting)",
            group_col,
        )

    def describe_publications(
        self,
        pubs: pd.DataFrame,
        label: str,
        group_col: str = "text_availability",
    ) -> str:
        """Return a corpus statement with publication counts per text availability group."""
        counts = pubs[group_col].value_counts()
        n_full_text = int(counts.get(FULL_TEXT_LABEL, 0))
        n_abstract = int(counts.get(ABSTRACT_ONLY_LABEL, 0))
        return (
            f"Corpus: {label}; n = {n_full_text + n_abstract:,} publications "
            f"(full text: {n_full_text:,}, abstract only: {n_abstract:,})"
        )

    def _add_note(self, fig, note):
        """Add a corpus note below the figure if note is a non-empty string, and print it."""
        if isinstance(note, str) and note:
            add_corpus_note(fig, note)
            print(note)
