"""
Stratified random sample of extracted records for the manual validation of Quinex.

Draws 40 records from each analysis subset used in the main-text figures and 40
abstract-only records from the same subsets, and writes them to an Excel workbook
with columns for the annotator.
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from quinex_application.postprocessing.country_codes import normalize_country_code
from quinex_application.postprocessing.data_loading import filter_by_unit_uri
from quinex_application.postprocessing.data_processing import (
    apply_iqr_filter, classify_dois_full_text, parse_spatial_scope,
    FULL_TEXT_LABEL, ABSTRACT_ONLY_LABEL,
)
from quinex_application.visualisation.temporal_visualisation import TemporalVisualisation


SEED = 42
N_PER_SUBSET = 40

RAW_PATH = "data/quinex/df_quinex.parquet"
TECHNOLOGIES_PATH = "data/visualisation_files/df_technologies.parquet"
TECHNOLOGIES_NAN_PATH = "data/visualisation_files/df_technologies_nan.parquet"
UNIT_CONVERTED_DIR = "data/visualisation_files/unit_converted"
OUTPUT_DIR = "data/validation"
UNIT = "http://qudt.org/vocab/unit/"

# Settings of plot_multiple_properties_over_time in Step5_TemporalVisualisation
TEMPORAL_SETTINGS = dict(
    iqr_filter=True,
    iqr_lower_quantile=0.25,
    iqr_upper_quantile=0.75,
    iqr_multiplier=3,
    temporal_col="temporal_scope",
    publicationyear_col="publication_year",
    min_papers_per_year=3,
    min_datapoints_per_year=3,
    central_tendency="moving average",
    error_type="se",
    doi_col="DOI",
    source_col="source_url",
)

SUBSETS = {
    "pv_capex": "PV capital cost (Fig. 4c)",
    "wind_cf": "Wind capacity factor (Fig. 4d)",
    "pv_lcoe": "PV LCOE (Fig. 5)",
    "hydrogen": "Hydrogen cost (Fig. 4e)",
    "nodes": "Nodes, time steps, scenarios (Fig. 3)",
    "eff_lifetime": "Efficiency and lifetime (Fig. 4a,b)",
    "abstract_only": "Abstract-only records of the figure subsets",
}

# Evaluated fields: (column header, label in the summary table, group, evaluated column);
# each evaluation column is placed right after the column it evaluates
EVAL_FIELDS = [
    ("ok_quantity", "Quantity (value and normalised unit)", "Quinex extraction", "unit_normalized"),
    ("ok_entity", "Entity string", "Quinex extraction", "entity"),
    ("ok_property", "Property string", "Quinex extraction", "property"),
    ("ok_unit", "Unit category", "Quinex extraction", "unit_uris"),
    ("ok_temporal", "Temporal scope (year)", "Quinex extraction", "temporal_scope"),
    ("ok_spatial", "Spatial scope (location)", "Quinex extraction", "spatial_coordinates"),
    ("ok_entity_mapping", "Entity category", "Post-processing", "entity_mapping"),
    ("ok_property_mapping", "Property category", "Post-processing", "property_mapping"),
]
# Whether the record belongs in its figure; not part of 'record correct in all fields'
FIGURE_FIELD = ("ok_figure", "Record suitable for its figure", "Figure", "figure_unit")

# =============================================================================
# Raw records
# =============================================================================

RAW_DETAIL_COLUMNS = [
    "quantity_text", "quote", "unit_normalized", "temporal_scope", "spatial_scope",
]


def load_raw_details(row_ids) -> pd.DataFrame:
    """Load all extracted fields of the given raw rows (the full table does not fit in pandas)."""
    row_ids = np.asarray(row_ids, dtype=np.int64)
    table = pq.read_table(RAW_PATH, columns=RAW_DETAIL_COLUMNS)
    return table.take(pa.array(row_ids)).to_pandas().set_axis(pd.Index(row_ids, name="row_id"))


def load_raw_records() -> pd.DataFrame:
    """
    Load the raw Quinex output (light columns) with the category mappings.

    The published dataset (df_technologies_nan.parquet) is the raw output
    sorted stably by publication year and DOI, so the mappings are aligned to
    the raw rows by redoing that sort. The index (row_id) is the raw row index,
    which is also the index of df_technologies.parquet.
    """
    raw = pd.read_parquet(RAW_PATH, columns=[
        "DOI", "source_url", "license_information", "publication_year",
        "entity", "property", "value_normalized",
    ])
    mappings = pd.read_parquet(TECHNOLOGIES_NAN_PATH, columns=[
        "DOI", "Entity Mapping", "Entity Base Mapping", "Property Mapping", "Property Base Mapping",
    ])
    order = raw.sort_values(["publication_year", "DOI"], kind="stable").index
    if not (raw.loc[order, "DOI"].values == mappings["DOI"].values).all():
        raise ValueError("Raw output and published dataset are not row-aligned.")

    mappings = mappings.drop(columns="DOI").set_axis(order)
    mappings.columns = ["entity_mapping", "entity_base_mapping", "property_mapping", "property_base_mapping"]
    raw = raw.join(mappings)
    raw.index.name = "row_id"
    return raw


def link_to_raw(df: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    """
    Add the raw row_id to records of the unit-converted Excel files, which lost the index.

    Matched on DOI, entity, property and normalized value. If several raw rows
    match, the one with the same quote is preferred (the Excel files lack many
    quotes), otherwise the first; such records are flagged in 'link_ambiguous'.
    """
    df = df.reset_index(drop=True).assign(_xid=lambda d: d.index, _v=lambda d: d["value_normalized"].round(6))
    keys = raw.loc[raw["DOI"].isin(df["DOI"]), ["DOI", "entity", "property"]]
    keys = keys.assign(
        _v=raw["value_normalized"].round(6),
        quote=load_raw_details(keys.index)["quote"],
    )
    candidates = df[["_xid", "DOI", "entity", "property", "_v", "quote"]].merge(
        keys.reset_index(), on=["DOI", "entity", "property", "_v"], suffixes=("", "_raw"),
    )
    candidates["_same_quote"] = candidates["quote"] == candidates["quote_raw"]
    n_candidates = candidates.groupby("_xid")["row_id"].transform("count")
    candidates["link_ambiguous"] = (n_candidates > 1) & ~candidates.groupby("_xid")["_same_quote"].transform("any")
    best = (
        candidates.sort_values(["_xid", "_same_quote", "row_id"], ascending=[True, False, True])
        .drop_duplicates("_xid")
    )
    linked = df.merge(best[["_xid", "row_id", "link_ambiguous"]], on="_xid", how="inner")
    print(f"Linked {len(linked)}/{len(df)} records, ambiguous: {int(linked['link_ambiguous'].sum())}")
    return linked.drop(columns=["_xid", "_v"])


# =============================================================================
# Analysis subsets (records that enter the figures)
# =============================================================================

def contributing_temporal_records(entry: dict) -> pd.DataFrame:
    """Records of one temporal panel that enter the plot (same filters as plot_multiple_properties_over_time)."""
    prepared = TemporalVisualisation()._prepare_temporal_data(
        [entry], **{**TEMPORAL_SETTINGS, "temporal_col": entry.get("temporal_col", "temporal_scope")}
    )[0]
    groups = prepared["agg_df"][["jahr", entry["entity_col"]]].drop_duplicates()
    return prepared["df"].merge(groups, on=["jahr", entry["entity_col"]], how="inner")


def read_unit_converted(name: str, raw: pd.DataFrame) -> pd.DataFrame:
    df = pd.read_excel(f"{UNIT_CONVERTED_DIR}/df_technologies_{name}.xlsx").drop(columns="Unnamed: 0")
    return link_to_raw(df, raw)


def build_subset_pools(raw: pd.DataFrame) -> dict:
    """Return {subset key: DataFrame with row_id, figure value and figure unit} for the figure subsets."""
    pools = {}
    tech = pd.read_parquet(
        TECHNOLOGIES_PATH,
        filters=[("property_mapping", "in", ["Lifetime", "Efficiency", "Capacity Factor"])],
    ).drop(columns=["quote", "Title", "author", "quantity_normalized", "classification"])
    tech = tech.rename_axis("row_id").reset_index()

    # Fig. 4c: CAPEX, PV
    capex = read_unit_converted("capex", raw)
    capex["entity_mapping"] = capex["entity_mapping"].replace({"Wind": "Onshore Wind"})
    capex = contributing_temporal_records({
        "df": capex[capex["entity_mapping"].isin(["PV", "Offshore Wind", "Onshore Wind"])],
        "entity_col": "entity_mapping", "value_col": "value_converted",
    })
    pools["pv_capex"] = capex[capex["entity_mapping"] == "PV"].assign(
        figure_value=lambda d: d["value_converted"], figure_unit="CAPEX [k$/kW]")

    # Fig. 4d: capacity factor, onshore wind ('Wind' counts as onshore, as in the notebook)
    cf_raw = tech[tech["property_mapping"] == "Capacity Factor"]
    percent = filter_by_unit_uri(cf_raw, UNIT + "PERCENT")
    unitless = filter_by_unit_uri(cf_raw, UNIT + "UNITLESS")
    unitless = unitless[unitless["value_normalized"].between(0, 1)]
    unitless["value_normalized"] = unitless["value_normalized"] * 100
    cap_factor = pd.concat([percent, unitless], ignore_index=True)
    cap_factor["entity_mapping"] = cap_factor["entity_mapping"].replace({"Wind": "Onshore Wind"})
    cap_factor = contributing_temporal_records({
        "df": cap_factor[cap_factor["entity_mapping"].isin(["Onshore Wind", "Offshore Wind", "PV"])],
        "entity_col": "entity_mapping", "value_col": "value_normalized",
    })
    pools["wind_cf"] = cap_factor[cap_factor["entity_mapping"] == "Onshore Wind"].assign(
        figure_value=lambda d: d["value_normalized"], figure_unit="Capacity factor [%]")

    # Fig. 4e: LCOH
    lcoh = read_unit_converted("lcoh", raw)
    lcoh = contributing_temporal_records({
        "df": lcoh[lcoh["entity_mapping"].isin(["Hydrogen", "Green Hydrogen"])],
        "entity_col": "entity_mapping", "value_col": "value_converted",
    })
    pools["hydrogen"] = lcoh.assign(figure_value=lambda d: d["value_converted"], figure_unit="LCOH [$/kg]")

    # Fig. 4a,b: efficiency and lifetime of the base technologies
    efficiency = filter_by_unit_uri(tech[tech["property_mapping"] == "Efficiency"], UNIT + "PERCENT")
    efficiency = efficiency[~((efficiency["entity_base_mapping"] == "PV") & (efficiency["value_normalized"] > 33.7))]
    lifetime = filter_by_unit_uri(tech[tech["property_mapping"] == "Lifetime"], UNIT + "YR")
    base_technologies = ["PV", "Battery", "Wind", "Electrolyzer", "Coal"]
    eff_lifetime = [
        contributing_temporal_records({
            "df": df[df["entity_base_mapping"].isin(base_technologies)],
            "entity_col": "entity_base_mapping", "value_col": "value_normalized",
        }).assign(figure_value=lambda d: d["value_normalized"], figure_unit=unit)
        for df, unit in [(efficiency, "Efficiency [%]"), (lifetime, "Lifetime [years]")]
    ]
    pools["eff_lifetime"] = pd.concat(eff_lifetime, ignore_index=True)

    # Fig. 3: number of nodes and time steps (no temporal scope, publication year < 2026)
    nodes = raw[raw["property_mapping"].isin(["Number of Nodes", "Number of Time Steps"])]
    nodes = nodes.join(load_raw_details(nodes.index)[["unit_normalized"]]).reset_index()
    panels = []
    for prop, uris in [("Number of Nodes", [UNIT + "UNITLESS", UNIT + "KN"]),
                       ("Number of Time Steps", [UNIT + "UNITLESS"])]:
        df = filter_by_unit_uri(nodes[nodes["property_mapping"] == prop], uris)
        df = df[df["publication_year"] < 2026].assign(no_scope=pd.NA, panel=prop)
        panels.append(contributing_temporal_records({
            "df": df, "entity_col": "panel", "value_col": "value_normalized", "temporal_col": "no_scope",
        }).assign(figure_value=lambda d: d["value_normalized"], figure_unit=prop))

    # Fig. 3: number of scenarios per location (Step6_SpatialVisualisation, IQR over all records)
    scenarios = raw[raw["property_mapping"] == "Number of Scenarios"]
    scenarios = scenarios.join(load_raw_details(scenarios.index)[["unit_normalized", "spatial_scope"]])
    scenarios = filter_by_unit_uri(scenarios.reset_index(), UNIT + "UNITLESS")
    scenarios = parse_spatial_scope(scenarios, "spatial_scope")
    scenarios = apply_iqr_filter(scenarios.assign(dummy="x"), "value_normalized", "dummy",
                                 lower_quantile=0.25, upper_quantile=0.75, iqr_multiplier=3)
    scenarios = scenarios.dropna(subset=["value_normalized"])
    on_map = scenarios["country"].apply(normalize_country_code).notna() | scenarios["latitude"].notna()
    panels.append(scenarios[on_map].assign(
        figure_value=lambda d: d["value_normalized"], figure_unit="Number of Scenarios"))
    pools["nodes"] = pd.concat(panels, ignore_index=True)

    # Fig. 5: PV LCOE per country (Step6_SpatialVisualisation, IQR over all records)
    lcoe = read_unit_converted("lcoe2024", raw)
    lcoe = parse_spatial_scope(lcoe[lcoe["entity_base_mapping"] == "PV"], "spatial_scope")
    lcoe = lcoe[lcoe["value_converted"] < 510]
    lcoe = apply_iqr_filter(lcoe.assign(dummy="x"), "value_converted", "dummy",
                            lower_quantile=0.25, upper_quantile=0.75, iqr_multiplier=3)
    lcoe = lcoe.dropna(subset=["value_converted"])
    lcoe = lcoe[lcoe["country"].apply(normalize_country_code).notna()]
    pools["pv_lcoe"] = lcoe.assign(figure_value=lambda d: d["value_converted"], figure_unit="LCOE [$/MWh]")

    columns = ["row_id", "figure_value", "figure_unit", "link_ambiguous"]
    return {
        key: pool.reindex(columns=columns).drop_duplicates("row_id")
        for key, pool in pools.items()
    }


# =============================================================================
# Sampling
# =============================================================================

def draw_sample(raw: pd.DataFrame, pools: dict, seed: int = SEED) -> pd.DataFrame:
    """Draw N_PER_SUBSET records per subset without overlap between subsets."""
    full_text = classify_dois_full_text(raw, source_col="source_url")
    text_source = raw["DOI"].astype("string").str.strip().map(full_text).fillna(False)
    text_source = text_source.map({True: FULL_TEXT_LABEL, False: ABSTRACT_ONLY_LABEL})

    # Abstract-only records of all figure subsets (figure value/unit of the subset kept)
    figure_records = pd.concat(pools.values(), ignore_index=True).drop_duplicates("row_id")
    abstract_only = figure_records[figure_records["row_id"].map(text_source) == ABSTRACT_ONLY_LABEL]
    pools = {**pools, "abstract_only": abstract_only}

    drawn, taken = [], set()
    for key in SUBSETS:
        pool = pools[key][~pools[key]["row_id"].isin(taken)]
        print(f"{SUBSETS[key]}: {len(pool):,} records in pool")
        sample = pool.sample(n=N_PER_SUBSET, random_state=seed).assign(subset=SUBSETS[key])
        taken.update(sample["row_id"])
        drawn.append(sample)

    sample = pd.concat(drawn, ignore_index=True)
    sample["text_source"] = sample["row_id"].map(text_source)
    sample.insert(0, "sample_id", [f"V{i:03d}" for i in range(1, len(sample) + 1)])
    return sample.join(raw, on="row_id").join(load_raw_details(sample["row_id"]), on="row_id")


# =============================================================================
# Formatting of extracted fields
# =============================================================================

def _as_list(value) -> list:
    if value is None or isinstance(value, float):
        return []
    return list(value)


def format_unit(units) -> str:
    """'[{text: '€', exponent: 1}, {text: 'kW', exponent: -1}]' -> '€/kW'."""
    numerator, denominator = [], []
    for unit in _as_list(units):
        text = unit.get("text") or unit.get("unit_uri", "").replace(UNIT, "")
        if unit.get("year") and not pd.isna(unit.get("year")):
            text += f" ({int(unit['year'])})"
        exponent = unit.get("exponent")
        exponent = 1.0 if exponent is None or pd.isna(exponent) else exponent
        power = f"^{abs(exponent):g}" if abs(exponent) != 1 else ""
        (numerator if exponent > 0 else denominator).append(text + power)
    unit_text = "·".join(numerator) or ("1" if denominator else "")
    return unit_text + "".join(f"/{d}" for d in denominator)


def format_unit_uris(units) -> str:
    parts = []
    for unit in _as_list(units):
        exponent = unit.get("exponent")
        exponent = 1.0 if exponent is None or pd.isna(exponent) else exponent
        parts.append(f"{(unit.get('unit_uri') or '').replace(UNIT, '')}^{exponent:g}")
    return " ".join(parts)


def _field(value, key):
    return value.get(key) if isinstance(value, dict) else None


def format_temporal(value) -> str:
    text, year = _field(value, "text"), _field(value, "year")
    year = None if year is None or pd.isna(year) else int(year)
    return " | ".join(str(p) for p in [text, year] if p not in (None, ""))


def format_spatial(value) -> str:
    text, country = _field(value, "text"), _field(value, "country")
    return " | ".join(str(p) for p in dict.fromkeys([text, country]) if p not in (None, ""))


def format_coordinates(value) -> str:
    lat, lon = _field(value, "latitude"), _field(value, "longitude")
    if lat is None or lon is None or pd.isna(lat) or pd.isna(lon):
        return ""
    return f"{lat:.4f}, {lon:.4f}"


def _is_true(value) -> bool:
    return value is not None and not pd.isna(value) and bool(value)


def clean_text(value) -> str:
    """Remove characters that are not allowed in Excel cells."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value))


# =============================================================================
# Workbook
# =============================================================================

# (header, width, function of a sample row)
INFO_COLUMNS = [
    ("sample_id", 9, lambda r: r["sample_id"]),
    ("subset", 22, lambda r: r["subset"]),
    ("text_source", 12, lambda r: r["text_source"]),
    ("DOI", 22, lambda r: r["DOI"]),
    ("sentence (quote)", 70, lambda r: r["quote"]),
]
EXTRACTION_COLUMNS = [
    ("quantity_text", 16, lambda r: r["quantity_text"]),
    ("value_normalized", 12, lambda r: r["value_normalized"]),
    ("unit_normalized", 14, lambda r: format_unit(r["unit_normalized"])),
    ("unit_uris", 18, lambda r: format_unit_uris(r["unit_normalized"])),
    ("entity", 22, lambda r: r["entity"]),
    ("property", 22, lambda r: r["property"]),
    ("temporal_scope", 14, lambda r: format_temporal(r["temporal_scope"])),
    ("spatial_scope", 16, lambda r: format_spatial(r["spatial_scope"])),
    ("spatial_coordinates", 16, lambda r: format_coordinates(r["spatial_scope"])),
    ("entity_mapping", 16, lambda r: r["entity_mapping"]),
    ("entity_base_mapping", 14, lambda r: r["entity_base_mapping"]),
    ("property_mapping", 16, lambda r: r["property_mapping"]),
    ("property_base_mapping", 14, lambda r: r["property_base_mapping"]),
    ("figure_value", 11, lambda r: r["figure_value"]),
    ("figure_unit", 16, lambda r: r["figure_unit"]),
    ("link_ambiguous", 9, lambda r: "yes" if _is_true(r["link_ambiguous"]) else ""),
]

HEADER_FONT = Font(name="Arial", bold=True, color="FFFFFF")
FONT = Font(name="Arial", size=10)
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")
GROUP_FILLS = {"info": "595959", "extraction": "2F5597", "evaluation": "BF8F00"}
THIN = Side(style="thin", color="BFBFBF")


def _write_records_sheet(ws, sample: pd.DataFrame):
    """Records with the Quinex output and empty evaluation columns (yellow) after the evaluated columns."""
    evaluations = {target: field for field, _, _, target in EVAL_FIELDS + [FIGURE_FIELD]}
    columns = [(h, w, "info", g) for h, w, g in INFO_COLUMNS]
    for header, width, getter in EXTRACTION_COLUMNS:
        columns.append((header, width, "extraction", getter))
        if header in evaluations:
            columns.append((evaluations[header], 9, "evaluation", None))
    columns += [("record_correct_all", 10, "evaluation", None), ("comment", 30, "evaluation", None)]
    for col, (header, width, group, _) in enumerate(columns, start=1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = HEADER_FONT
        cell.fill = PatternFill("solid", fgColor=GROUP_FILLS[group])
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(col)].width = width

    letters = {header: get_column_letter(col) for col, (header, *_) in enumerate(columns, start=1)}
    eval_letters = [letters[field] for field, *_ in EVAL_FIELDS]
    figure_letter = letters[FIGURE_FIELD[0]]
    all_col, comment_col = len(columns) - 1, len(columns)
    n_rows = len(sample)

    for i, (_, record) in enumerate(sample.iterrows(), start=2):
        for col, (_, _, group, getter) in enumerate(columns, start=1):
            if getter is None:
                if group == "evaluation" and col < all_col:
                    cell = ws.cell(row=i, column=col)
                    cell.fill = INPUT_FILL
                    cell.alignment = Alignment(horizontal="center", vertical="top")
                continue
            value = getter(record)
            if isinstance(value, float) and np.isnan(value):
                value = None
            elif not isinstance(value, (int, float, bool, np.integer, np.floating)) and value is not None:
                value = clean_text(value)
            cell = ws.cell(row=i, column=col, value=value)
            if isinstance(value, str):
                cell.data_type = "s"  # e.g. quantity '= 630 €/kW' is text, not a formula
            cell.font = FONT
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        # Correct in all fields once every field is judged: 0 if any field is wrong ('NA' = 0 is false)
        cells = [f"{letter}{i}" for letter in eval_letters]
        ws.cell(row=i, column=all_col, value=(
            f'=IF(OR({",".join(c + "=" + chr(34) * 2 for c in cells)}),"",'
            f'IF(OR({",".join(c + "=0" for c in cells)}),0,1))'
        )).alignment = Alignment(horizontal="center", vertical="top")
        ws.cell(row=i, column=comment_col).fill = INPUT_FILL
        ws.cell(row=i, column=comment_col).alignment = Alignment(wrap_text=True, vertical="top")

    judgement = DataValidation(type="list", formula1='"1,0,NA"', allow_blank=True)
    judgement.error = "Enter 1 (correct), 0 (wrong) or NA (field does not apply)."
    judgement.showErrorMessage = True
    for letter in eval_letters + [figure_letter]:
        judgement.add(f"{letter}2:{letter}{n_rows + 1}")
    ws.add_data_validation(judgement)

    ws.freeze_panes = ws.cell(row=2, column=2)
    ws.auto_filter.ref = f"A1:{get_column_letter(len(columns))}{n_rows + 1}"
    ws.row_dimensions[1].height = 45
    return {
        "eval_letters": eval_letters,
        "figure_letter": figure_letter,
        "all_letter": get_column_letter(all_col),
        "subset_letter": "B",
        "source_letter": "C",
        "last_row": n_rows + 1,
    }


def _write_summary_sheet(ws, layout: dict):
    """Summary in the layout of the validation table, computed from the Records sheet."""
    last = layout["last_row"]
    src = f"Records!${layout['source_letter']}$2:${layout['source_letter']}${last}"
    sub = f"Records!${layout['subset_letter']}$2:${layout['subset_letter']}${last}"

    ws["A1"] = "Manual validation of extracted records"
    ws["A1"].font = Font(name="Arial", bold=True, size=13)
    ws["A2"] = "z (95 % Wilson interval)"
    ws["B2"] = 1.959964
    ws["B2"].font = Font(name="Arial", color="0000FF")
    ws["B2"].comment = Comment("Standard normal quantile for a two-sided 95 % interval.", "validation")
    ws["C2"] = "All values below are formulas on the Records sheet; 'NA' and empty judgements are not counted."

    headers = ["Field", "Checked", "Correct", "Precision (%)", "95 % CI low (%)",
               "95 % CI high (%)", "Full text (%)", "Abstract only (%)"]
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=4, column=col, value=header)
        cell.font = HEADER_FONT
        cell.fill = PatternFill("solid", fgColor="404040")
        cell.alignment = Alignment(wrap_text=True, horizontal="center")

    def write_row(row, label, rng, condition_range=None, condition=None, split=True):
        cond = f",{condition_range},\"{condition}\"" if condition_range else ""
        ws.cell(row=row, column=1, value=label)
        ws.cell(row=row, column=2, value=f"=COUNTIFS({rng},1{cond})+COUNTIFS({rng},0{cond})")
        ws.cell(row=row, column=3, value=f"=COUNTIFS({rng},1{cond})")
        ws.cell(row=row, column=4, value=f'=IF(B{row}=0,"",100*C{row}/B{row})')
        # Wilson score interval
        p, n, z = f"(C{row}/B{row})", f"B{row}", "$B$2"
        centre = f"({p}+{z}^2/(2*{n}))"
        half = f"{z}*SQRT({p}*(1-{p})/{n}+{z}^2/(4*{n}^2))"
        ws.cell(row=row, column=5, value=f'=IF(B{row}=0,"",100*({centre}-{half})/(1+{z}^2/{n}))')
        ws.cell(row=row, column=6, value=f'=IF(B{row}=0,"",100*({centre}+{half})/(1+{z}^2/{n}))')
        if split:
            for col, label_source in [(7, FULL_TEXT_LABEL), (8, ABSTRACT_ONLY_LABEL)]:
                ok = f'COUNTIFS({rng},1,{src},"{label_source}")'
                wrong = f'COUNTIFS({rng},0,{src},"{label_source}")'
                ws.cell(row=row, column=col, value=f'=IF({ok}+{wrong}=0,"",100*{ok}/({ok}+{wrong}))')
        for col in range(1, 9):
            ws.cell(row=row, column=col).font = FONT
            if col >= 4:
                ws.cell(row=row, column=col).number_format = "0.0"

    def write_group(row, title):
        ws.cell(row=row, column=1, value=title).font = Font(name="Arial", italic=True)

    row = 5
    for group in dict.fromkeys(g for _, _, g, _ in EVAL_FIELDS):
        write_group(row, group)
        row += 1
        for (field, label, g, _), letter in zip(EVAL_FIELDS, layout["eval_letters"]):
            if g == group:
                write_row(row, label, f"Records!${letter}$2:${letter}${last}")
                row += 1
    all_range = f"Records!${layout['all_letter']}$2:${layout['all_letter']}${last}"
    write_row(row, "Record correct in all fields", all_range)
    ws.cell(row=row, column=1).font = Font(name="Arial", bold=True)
    row += 1
    figure_range = f"Records!${layout['figure_letter']}$2:${layout['figure_letter']}${last}"
    write_row(row, FIGURE_FIELD[1], figure_range)
    ws.cell(row=row, column=1).font = Font(name="Arial", bold=True)
    row += 2
    for title, rng in [("Record-level precision by analysis subset", all_range),
                       (f"{FIGURE_FIELD[1]} by analysis subset", figure_range)]:
        write_group(row, title)
        row += 1
        for label in SUBSETS.values():
            write_row(row, label, rng, sub, label, split=False)
            row += 1
        row += 1

    ws.column_dimensions["A"].width = 40
    for col in "BCDEFGH":
        ws.column_dimensions[col].width = 13


GUIDELINES = [
    ("General", "Judge every field against the sentence in 'sentence (quote)' (open the DOI only if the sentence is ambiguous). Enter 1 = correct, 0 = wrong, NA = field does not apply. Only the yellow columns are edited; 'record_correct_all' and the Summary sheet update automatically."),
    ("Correctly absent", "A field that is empty because the sentence states nothing (no year, no location) counts as correct (1). An empty field although the sentence states it counts as wrong (0)."),
    ("ok_quantity", "Value AND normalised unit (value_normalized + unit_normalized) match the quantity in the sentence, incl. prefixes (k, M), currency and currency year."),
    ("ok_entity", "The entity string names the system/technology the quantity belongs to. Naming a component instead of the system (e.g. 'inverter' for a PV system cost) is wrong."),
    ("ok_property", "The property string names what is quantified (e.g. 'capital cost', 'capacity factor')."),
    ("ok_unit", "unit_uris (QUDT unit category with exponent) matches the unit in the sentence, e.g. CCY_USD^1 KiloW^-1 for $/kW; wrong prefix (W vs. kW) or wrong currency is wrong. UNITLESS is correct for counts and ratios."),
    ("ok_temporal", "The year in temporal_scope is the year the value refers to (not the publication year). Empty if no year is stated."),
    ("ok_spatial", "The location in spatial_scope is the location the value refers to; the normalised country and the spatial_coordinates (latitude, longitude; check e.g. in a map) must also be right."),
    ("ok_entity_mapping", "entity_mapping (regex category) fits the entity string as used in the sentence. Empty mapping: 1 if no category applies, 0 if a category should have matched."),
    ("ok_property_mapping", "property_mapping (regex category) fits the property string as used in the sentence; same rule for empty mappings."),
    ("ok_figure", "Whether the record belongs in the figure named by figure_unit (subset shows the figure; for abstract-only records figure_unit names the figure the record comes from), with the value figure_value as plotted after unit conversion. 1 if the sentence really reports this property for the plotted technology (e.g. a capacity factor of an onshore wind system for 'Capacity factor [%]', a PV capital cost per kW for 'CAPEX [k$/kW]') and figure_value is the correctly converted value. 0 if the record does not belong there, e.g. other technology or property (component cost, offshore instead of onshore, LCOE instead of CAPEX), a value that is not a single quantity of this kind (difference, share, range end used as value, sensitivity case), or a wrong conversion. A record can be 0 here although all extraction fields are 1. Not part of record_correct_all; reported separately in the Summary sheet."),
    ("record_correct_all", "Calculated automatically, do not edit: empty until every ok_ column of the record is filled (except ok_figure), 0 if any field is 0, otherwise 1 (fields with NA are ignored). Used for 'Record correct in all fields' and the precision per subset in the Summary sheet."),
    ("comment", "For every record with a 0, describe the error briefly (e.g. 'fraction recorded as percentage', 'entity names component instead of system'), so the most frequent error types can be counted."),
    ("Example", "Sentence: 'The capital cost of utility-scale PV in Germany fell to 600 €/kW in 2020 [12].' Quinex: 600 €/kW, CCY_EUR^1 KiloW^-1, entity 'utility-scale PV', property 'capital cost', 2020, Germany (51.1657, 10.4515), PV, Capital Cost -> all fields 1. If the year were empty: ok_temporal = 0, comment 'year 2020 missing'."),
    ("link_ambiguous", "Information only, nothing to evaluate. The cost records (PV capital cost, hydrogen cost, PV LCOE) come from unit-converted Excel files that lost the link to the raw Quinex output; they were linked back by DOI, entity, property and value. 'yes' means several raw records matched and none had the same quote, so the sentence shown may belong to a duplicate extraction (same entity, property and value) from another sentence of the same paper. Judge the record against the sentence shown; if the sentence does not contain the value at all, note it in 'comment'."),
    ("Sampling", f"Stratified random sample: {N_PER_SUBSET} records per figure subset and {N_PER_SUBSET} abstract-only records drawn from the same figure subsets, seed {SEED}, no record drawn twice (quinex_application/postprocessing/validation_sampling.py). Subsets contain only records that enter the figures (after IQR filter and minimum papers/data points per year)."),
    ("Confidential", "The sentences of non-open-access publications are included for annotation only; do not share this file publicly."),
]


def write_workbook(sample: pd.DataFrame, path: Path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Records"
    layout = _write_records_sheet(ws, sample)
    _write_summary_sheet(wb.create_sheet("Summary"), layout)

    guide = wb.create_sheet("Guidelines")
    guide["A1"], guide["B1"] = "Topic", "Guideline"
    for cell in (guide["A1"], guide["B1"]):
        cell.font = HEADER_FONT
        cell.fill = PatternFill("solid", fgColor="404040")
    for i, (topic, text) in enumerate(GUIDELINES, start=2):
        guide.cell(row=i, column=1, value=topic).font = Font(name="Arial", bold=True, size=10)
        cell = guide.cell(row=i, column=2, value=text)
        cell.font = FONT
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    guide.column_dimensions["A"].width = 20
    guide.column_dimensions["B"].width = 120

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    print(f"Saved {path}")


def main():
    raw = load_raw_records()
    pools = build_subset_pools(raw)
    sample = draw_sample(raw, pools)

    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    sample[["sample_id", "row_id", "subset", "text_source", "DOI"]].to_csv(
        output_dir / "validation_sample_ids.csv", index=False)
    write_workbook(sample, output_dir / "validation_sample.xlsx")
    print(sample.groupby(["subset", "text_source"]).size().unstack(fill_value=0))


if __name__ == "__main__":
    main()
