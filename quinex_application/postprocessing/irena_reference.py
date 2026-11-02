"""
Extract IRENA reference series from the IRENA Excel files into the CSV format read
by data_loading.load_reference_series (one CSV file per comparison line).
"""

from pathlib import Path

import pandas as pd


# IRENASTAT technology names -> entity names used in the plots (and file names)
FLEET_TECHNOLOGIES = {
    "Solar photovoltaic": ("PV", "pv"),
    "Onshore wind energy": ("Onshore Wind", "onshore_wind"),
    "Offshore wind energy": ("Offshore Wind", "offshore_wind"),
}
FLEET_SERIES = "Existing fleet"
FLEET_LINESTYLE = ":"


def load_fleet_capacity_factors(xlsx_path: str) -> pd.DataFrame:
    """
    Load the 'Tidy' sheet of IRENAStat_Fleet.xlsx.

    The capacity factor there is the one of the existing fleet in a year:
    generation / (8760 h x mean capacity at the end of the previous and current year).

    Returns:
        DataFrame with the columns country, technology, grid, year, generation_gwh,
        capacity_mw and capacity_factor (fraction).
    """
    df = pd.read_excel(xlsx_path, sheet_name="Tidy", skiprows=[1])
    df.columns = [
        "country", "technology", "grid", "year",
        "generation_gwh", "capacity_mw", "capacity_factor",
    ]
    # Drop the source note at the end of the sheet
    df = df.dropna(subset=["technology", "year"])
    df["year"] = df["year"].astype(int)
    return df


def write_world_fleet_capacity_factor_series(xlsx_path: str, out_dir: str) -> list[Path]:
    """
    Write one CSV file per technology (<technology>.csv) with the world fleet
    capacity factor (%). Years without a capacity factor (e.g. not yet published
    generation) are skipped.

    Args:
        xlsx_path: Path to IRENAStat_Fleet.xlsx.
        out_dir: Folder to write to, e.g. .../irena/existing_fleet/capacity_factor.

    Returns:
        Paths of the written files.
    """
    df = load_fleet_capacity_factors(xlsx_path)
    df = df[(df["country"] == "World") & df["capacity_factor"].notna()]

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for technology, (entity, file_stem) in FLEET_TECHNOLOGIES.items():
        rows = df[df["technology"] == technology].sort_values("year")
        if rows.empty:
            continue
        series = pd.DataFrame({
            "entity": entity,
            "year": rows["year"],
            "value": (rows["capacity_factor"] * 100).round(1),
            "unit": "%",
            "source": "IRENASTAT ELEC-C, on-grid fleet capacity factor, World",
            "series": FLEET_SERIES,
            "linestyle": FLEET_LINESTYLE,
        })
        path = out_dir / f"{file_stem}.csv"
        series.to_csv(path, index=False)
        written.append(path)
    return written


NEW_PROJECTS_SERIES = "New projects"
# Datafile sheets with the weighted average capacity factor of new onshore wind
# capacity per country (top markets, smaller markets), one row per country and
# one column per year
ONSHORE_COUNTRY_SHEETS = {"Fig 2.11": "Fig. 2.11", "Fig 2.12": "Fig. 2.12"}


def load_onshore_wind_new_project_country_capacity_factors(datafile_path: str) -> pd.DataFrame:
    """
    Load the new-project onshore wind capacity factors per country (Datafile,
    Fig. 2.11 top markets and Fig. 2.12 smaller markets).

    Returns:
        DataFrame with the columns country (ISO3), country_name, year,
        capacity_factor (fraction) and figure.
    """
    from quinex_application.postprocessing.country_codes import country_to_iso3

    frames = []
    for sheet_name, figure in ONSHORE_COUNTRY_SHEETS.items():
        sheet = pd.read_excel(datafile_path, sheet_name=sheet_name, header=None)
        header_row = sheet.index[sheet[1] == "Country"][0]
        years = pd.to_numeric(sheet.loc[header_row], errors="coerce")
        year_cols = years.dropna().index

        rows = sheet.loc[header_row + 1:, [1, *year_cols]].dropna(subset=[1])
        rows.columns = ["country_name", *years[year_cols].astype(int)]
        df = rows.melt(id_vars="country_name", var_name="year", value_name="capacity_factor")
        df["figure"] = figure
        frames.append(df)

    df = pd.concat(frames, ignore_index=True)
    df["capacity_factor"] = pd.to_numeric(df["capacity_factor"], errors="coerce")
    df = df.dropna(subset=["capacity_factor"])
    df["country"] = df["country_name"].map(country_to_iso3)
    df["year"] = df["year"].astype(int)
    return df[["country", "country_name", "year", "capacity_factor", "figure"]]


# Datafile sheet with PV cost and performance of new capacity in selected countries
# (China, United States, India, Brazil, Germany; 2022-2024 only)
PV_COUNTRY_SHEET = ("Fig 1.14", "Fig. 1.14")


def load_pv_new_project_country_capacity_factors(datafile_path: str) -> pd.DataFrame:
    """
    Load the new-project PV capacity factors per country (Datafile, Fig. 1.14,
    block 'Capacity factor (%)').

    Returns:
        DataFrame with the columns country (ISO3), country_name, year,
        capacity_factor (fraction) and figure.
    """
    from quinex_application.postprocessing.country_codes import country_to_iso3

    sheet_name, figure = PV_COUNTRY_SHEET
    sheet = pd.read_excel(datafile_path, sheet_name=sheet_name, header=None)
    # The sheet holds three blocks (costs, capacity factor, LCOE), each with a title
    # row, a year header row and one row per country, separated by empty rows
    title_row = sheet.index[sheet[2].astype(str).str.startswith("Capacity factor")][0]
    header_row = title_row + 1
    years = pd.to_numeric(sheet.loc[header_row], errors="coerce")
    year_cols = years.dropna().index

    rows = sheet.loc[header_row + 1:, [2, *year_cols]]
    rows = rows.iloc[:rows[2].isna().argmax() or len(rows)]
    rows.columns = ["country_name", *years[year_cols].astype(int)]
    df = rows.melt(id_vars="country_name", var_name="year", value_name="capacity_factor")
    df["figure"] = figure

    df["capacity_factor"] = pd.to_numeric(df["capacity_factor"], errors="coerce")
    df = df.dropna(subset=["capacity_factor"])
    df["country_name"] = df["country_name"].str.strip()
    df["country"] = df["country_name"].map(country_to_iso3)
    df["year"] = df["year"].astype(int)
    return df[["country", "country_name", "year", "capacity_factor", "figure"]]


# Plausible fleet capacity factors (fraction) per entity. Country values outside
# (reporting errors of small markets, e.g. Iraq PV > 100 %, or capacity added late
# in the year) are set to NaN and left out of country and region series.
PLAUSIBLE_FLEET_CAPACITY_FACTORS = {
    "PV": (0.05, 0.35),
    "Onshore Wind": (0.05, 0.65),
    "Offshore Wind": (0.10, 0.70),
}


def _load_fleet_with_iso3(fleet_path: str) -> pd.DataFrame:
    """
    Fleet capacity factors of FLEET_TECHNOLOGIES with ISO3 code and plot entity;
    implausible capacity factors (PLAUSIBLE_FLEET_CAPACITY_FACTORS) are set to NaN.
    """
    from quinex_application.postprocessing.country_codes import country_to_iso3

    fleet = load_fleet_capacity_factors(fleet_path)
    fleet = fleet[fleet["technology"].isin(FLEET_TECHNOLOGIES)].copy()
    fleet["iso3"] = fleet["country"].map(country_to_iso3)
    fleet["entity"] = fleet["technology"].map(lambda t: FLEET_TECHNOLOGIES[t][0])

    low = fleet["entity"].map(lambda e: PLAUSIBLE_FLEET_CAPACITY_FACTORS[e][0])
    high = fleet["entity"].map(lambda e: PLAUSIBLE_FLEET_CAPACITY_FACTORS[e][1])
    fleet.loc[~fleet["capacity_factor"].between(low, high), "capacity_factor"] = None
    return fleet.sort_values(["entity", "iso3", "year"])


def _series_frame(entity, years, values, source, series, linestyle, **extra) -> pd.DataFrame:
    """Reference rows in the format of load_reference_series (fractions converted to %)."""
    return pd.DataFrame({
        "entity": entity,
        "year": list(years),
        "value": (pd.Series(list(values), dtype=float) * 100).round(1).values,
        "unit": "%",
        "source": source,
        "series": series,
        "linestyle": linestyle,
        **extra,
    })


def _write_series_files(frames: dict, out_dir: str, key_col: str) -> list[Path]:
    """Write {key: list of DataFrames} as <key>.csv into out_dir, with the key in key_col."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for key, key_frames in frames.items():
        key_frames = [f for f in key_frames if not f.empty]
        if not key_frames:
            continue
        series = pd.concat(key_frames, ignore_index=True)
        series[key_col] = key
        path = out_dir / f"{str(key).replace(' ', '_')}.csv"
        series.to_csv(path, index=False)
        written.append(path)
    return written


def write_country_capacity_factor_series(
    datafile_path: str,
    fleet_path: str,
    fleet_dir: str,
    new_projects_dir: str,
    countries: list[str],
) -> list[Path]:
    """
    Write one CSV file per country (<ISO3>.csv) with capacity factors (%):

    - fleet_dir: existing fleet of PV, onshore and offshore wind (IRENASTAT)
    - new_projects_dir: new onshore wind projects (Datafile, Fig. 2.11 and 2.12) and
      new PV projects in China, USA, India, Brazil and Germany for 2022-2024 only
      (Datafile, Fig. 1.14; IRENA publishes no new-project values per country for
      offshore wind)

    Files hold all available years; the extra column 'country' (ISO3) allows
    filtering after load_reference_series.

    Args:
        datafile_path: Path to IRENA-Datafile-RenPwrGenCosts-in-2024.xlsx.
        fleet_path: Path to IRENAStat_Fleet.xlsx.
        fleet_dir: e.g. .../irena/existing_fleet/capacity_factor_countries.
        new_projects_dir: e.g. .../irena/new_projects/capacity_factor_countries.
        countries: ISO3 codes, e.g. ['USA', 'GBR']. Countries without IRENA data
            are skipped.

    Returns:
        Paths of the written files.
    """
    onshore = load_onshore_wind_new_project_country_capacity_factors(datafile_path)
    pv = load_pv_new_project_country_capacity_factors(datafile_path)
    new = pd.concat(
        [onshore.assign(entity="Onshore Wind"), pv.assign(entity="PV")], ignore_index=True
    )
    fleet = _load_fleet_with_iso3(fleet_path).dropna(subset=["capacity_factor"])

    fleet_frames, new_frames = {}, {}
    for country in countries:
        new_frames[country] = [
            _series_frame(
                entity, rows["year"], rows["capacity_factor"],
                "IRENA Renewable Power Generation Costs in 2024, " + rows["figure"].values,
                NEW_PROJECTS_SERIES, "--",
            )
            for entity, rows in new[new["country"] == country].sort_values("year").groupby("entity")
        ]
        fleet_frames[country] = [
            _series_frame(
                entity, rows["year"], rows["capacity_factor"],
                "IRENASTAT ELEC-C, on-grid fleet capacity factor", FLEET_SERIES, FLEET_LINESTYLE,
            )
            for entity, rows in fleet[fleet["iso3"] == country].groupby("entity")
        ]
    return (
        _write_series_files(fleet_frames, fleet_dir, "country")
        + _write_series_files(new_frames, new_projects_dir, "country")
    )


def weight_reference_by_country_mix(
    reference: pd.DataFrame,
    data_df: pd.DataFrame,
    entity_col: str = "entity_mapping",
    country_col: str = "country",
) -> pd.DataFrame:
    """
    Average country reference series with the country mix of the extracted values.

    For every entity, year and series, the country values are weighted by the number
    of extracted values of that entity per country; countries without a reference
    value in a year are left out and the weights of the others renormalised.

    Args:
        reference: Country series as written by write_country_capacity_factor_series
            (columns entity, year, value, series, country).
        data_df: Extracted values with entity and country (ISO3) columns.
        entity_col: Entity column of data_df (same names as reference 'entity').
        country_col: Country column of data_df.

    Returns:
        Reference DataFrame (entity, year, value, series, linestyle, coverage), where
        coverage is the share of the extracted values of the entity whose country has
        a reference value in that year.
    """
    counts = (
        data_df.dropna(subset=[country_col])
        .groupby([entity_col, country_col]).size()
        .rename("weight").reset_index()
        .rename(columns={entity_col: "entity", country_col: "country"})
    )
    df = reference.merge(counts, on=["entity", "country"], how="inner")
    df["weighted"] = df["value"] * df["weight"]
    out = df.groupby(["entity", "series", "year"], as_index=False).agg(
        weighted=("weighted", "sum"), weight=("weight", "sum"), linestyle=("linestyle", "first")
    )
    out["value"] = (out["weighted"] / out["weight"]).round(1)
    out["coverage"] = (out["weight"] / out["entity"].map(counts.groupby("entity")["weight"].sum())).round(2)
    return out[["entity", "year", "value", "series", "linestyle", "coverage"]]


def write_region_capacity_factor_series(
    datafile_path: str,
    fleet_path: str,
    fleet_dir: str,
    new_projects_dir: str,
    regions: dict[str, list[str]],
) -> list[Path]:
    """
    Write one CSV file per region with capacity factors (%), aggregated over the
    countries of the region:

    - fleet_dir: existing fleet of PV, onshore and offshore wind; total generation /
      (8760 h x total mean capacity) of all countries of the region in IRENASTAT (the
      capacity-weighted average of their fleet values).
    - new_projects_dir: new onshore wind projects; average of the country values of
      the Datafile (Fig. 2.11, 2.12), weighted by the capacity added in that year
      (IRENASTAT). IRENA does not publish new-project values for every country; the
      column 'coverage' gives the share of the capacity added in the region that these
      countries represent.

    Files are named after the region (spaces replaced by '_') and hold all available
    years; the extra column 'region' allows filtering after load_reference_series.

    Args:
        datafile_path: Path to IRENA-Datafile-RenPwrGenCosts-in-2024.xlsx.
        fleet_path: Path to IRENAStat_Fleet.xlsx.
        fleet_dir: e.g. .../irena/existing_fleet/capacity_factor_regions.
        new_projects_dir: e.g. .../irena/new_projects/capacity_factor_regions.
        regions: Region name -> ISO3 codes, e.g. country_codes.REGION_COUNTRIES.

    Returns:
        Paths of the written files.
    """
    new = load_onshore_wind_new_project_country_capacity_factors(datafile_path)
    fleet = _load_fleet_with_iso3(fleet_path)
    # Mean capacity of the year as used for the capacity factor (generation / 8760 h / CF)
    fleet["mean_capacity_mw"] = fleet["generation_gwh"] * 1000 / 8760 / fleet["capacity_factor"]
    fleet["added_mw"] = fleet.groupby(["entity", "iso3"])["capacity_mw"].diff().clip(lower=0)

    fleet_frames, new_frames = {}, {}
    for region, countries in regions.items():
        region_fleet = fleet[fleet["iso3"].isin(countries)]
        frames = fleet_frames.setdefault(region, [])

        # Existing fleet: only country-years with generation and capacity factor
        valid = region_fleet.dropna(subset=["generation_gwh", "mean_capacity_mw"])
        for entity, rows in valid.groupby("entity"):
            totals = rows.groupby("year")[["generation_gwh", "mean_capacity_mw"]].sum()
            fleet_cf = totals["generation_gwh"] * 1000 / 8760 / totals["mean_capacity_mw"]
            frames.append(_series_frame(
                entity, fleet_cf.index, fleet_cf.values,
                "IRENASTAT ELEC-C, on-grid fleet capacity factor", FLEET_SERIES, FLEET_LINESTYLE,
            ))

        # New onshore wind projects: country values weighted by the capacity added in that year
        onshore = region_fleet[region_fleet["entity"] == "Onshore Wind"]
        added = onshore[["iso3", "year", "added_mw"]].dropna()
        added_total = added.groupby("year")["added_mw"].sum()
        weighted = new[new["country"].isin(countries)].merge(
            added, left_on=["country", "year"], right_on=["iso3", "year"], how="inner"
        )
        weighted = weighted[weighted["added_mw"] > 0]
        weighted["cf_x_added"] = weighted["capacity_factor"] * weighted["added_mw"]
        new_sums = weighted.groupby("year")[["cf_x_added", "added_mw"]].sum()
        new_cf = new_sums["cf_x_added"] / new_sums["added_mw"]
        coverage = new_sums["added_mw"] / added_total.reindex(new_sums.index)
        new_frames[region] = [_series_frame(
            "Onshore Wind", new_cf.index, new_cf.values,
            "IRENA Renewable Power Generation Costs in 2024, Fig. 2.11, 2.12; "
            "weighted by capacity additions (IRENASTAT)",
            NEW_PROJECTS_SERIES, "--", coverage=coverage.values.round(2),
        )]
    return (
        _write_series_files(fleet_frames, fleet_dir, "region")
        + _write_series_files(new_frames, new_projects_dir, "region")
    )
