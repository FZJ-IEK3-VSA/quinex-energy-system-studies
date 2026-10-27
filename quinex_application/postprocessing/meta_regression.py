"""
Multivariable meta-regression of extracted LCOE values.
"""

import ast
import re

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from statsmodels.stats.multitest import multipletests
from scipy import stats

from quinex_application.postprocessing.country_codes import normalize_country_code
from quinex_application.postprocessing.data_processing import (
    classify_dois_full_text, parse_temporal_scope,
)


# Regex patterns on the extracted entity text, checked in this order
APPLICATION_PATTERNS = {
    "off-grid": r"off[- ]?grid|stand[- ]?alone|isolated|rural|remote|island|mini[- ]?grid|micro[- ]?grid",
    "rooftop/residential": r"roof|residential|household|home|house|building|bipv|commercial|distributed|small",
    "utility-scale": r"utility|large[- ]scale|grid[- ]scale|plant|farm|park|station|ppa",
}
# Solar technologies other than flat-plate PV mapped to PV
NON_PV_PATTERN = r"\bcsp\b|concentrat|dish|stirling|trough|tower|thermal|heating|iscc|pvt|pv/t"
FINANCING_PATTERN = r"discount rate|interest rate|wacc|cost of capital"
PERCENT_URI = "http://qudt.org/vocab/unit/PERCENT"


def _classify_application(entity: str) -> str:
    for label, pattern in APPLICATION_PATTERNS.items():
        if re.search(pattern, entity, flags=re.IGNORECASE):
            return label
    return "unspecified"


def _parse_classification(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return {}
    return {}


def discount_rate_per_doi(
    df_all: pd.DataFrame,
    doi_col: str = "DOI",
    property_col: str = "Property",
    value_col: str = "Value Normalized",
    unit_col: str = "Unit Normalized",
    valid_range: tuple = (0, 30),
) -> pd.Series:
    """
    Median discount/interest rate [%] reported in each publication.
    """
    is_percent = df_all[unit_col].apply(
        lambda u: u is not None and not isinstance(u, float) and len(u) == 1
        and u[0].get("unit_uri") == PERCENT_URI
    )
    rates = df_all[
        df_all[property_col].str.contains(FINANCING_PATTERN, case=False, regex=True, na=False)
        & is_percent
        & df_all[value_col].between(*valid_range)
    ]
    return rates.groupby(doi_col)[value_col].median().rename("discount_rate")


def build_regression_data(
    df: pd.DataFrame,
    ghi_data: dict,
    discount_rates: pd.Series = None,
    value_col: str = "value_converted",
    country_col: str = "country",
    min_country_records: int = 5,
    min_country_publications: int = 5,
) -> pd.DataFrame:
    """
    Derive the regression covariates from the LCOE records of the spatial plot.
    """
    d = df.dropna(subset=[value_col, country_col]).copy()
    d = d[d[value_col] > 0]
    d["log_lcoe"] = np.log(d[value_col])

    d = parse_temporal_scope(d, output_col="scope_year")
    d["year_c"] = d["scope_year"] - 2020
    d["projection"] = (d["scope_year"] > d["publication_year"]).astype(int)

    d["iso3"] = d[country_col].apply(normalize_country_code)
    d["ghi"] = d["iso3"].map(ghi_data).fillna(d[country_col].map(ghi_data))

    entity = d["entity"].fillna("").astype(str)
    d["application"] = entity.apply(_classify_application)
    d["non_pv"] = entity.str.contains(NON_PV_PATTERN, case=False, regex=True).astype(int)

    if discount_rates is not None:
        d["discount_rate"] = d["DOI"].map(discount_rates)
        d["dr_missing"] = d["discount_rate"].isna().astype(int)
        d["discount_rate"] = d["discount_rate"].fillna(discount_rates.median())

    classification = d["classification"].apply(_parse_classification)
    d["real_world"] = (classification.apply(lambda c: c.get("system")) == "real_world").astype(int)
    references = d["references"].astype(str)
    d["cited"] = (
        (classification.apply(lambda c: c.get("rational")) == "individual_literature_sources")
        | (d["references"].notna() & ~references.str.contains(r"'title': ''", regex=False))
    ).astype(int)

    full_text = classify_dois_full_text(d, source_col="source_url")
    d["full_text"] = d["DOI"].astype(str).str.strip().map(full_text).fillna(False).astype(int)

    n_records = d["iso3"].value_counts()
    n_publications = d.groupby("iso3")["DOI"].nunique()
    frequent = n_records.index[
        (n_records >= min_country_records)
        & (n_publications.reindex(n_records.index) >= min_country_publications)
    ]
    d["country_group"] = d["iso3"].where(d["iso3"].isin(frequent), "Other")

    return d.reset_index(drop=True)


def fit_mixed_model(d: pd.DataFrame, formula: str, group_col: str = "DOI", reml: bool = True):
    """Fit a linear mixed model with a random intercept per publication."""
    model = smf.mixedlm(formula, data=d, groups=d[group_col])
    return model.fit(reml=reml)


def icc(result) -> float:
    """Share of the residual variance that lies between groups (publications)."""
    group_var = result.cov_re.iloc[0, 0]
    return group_var / (group_var + result.scale)


def country_variance_components(d: pd.DataFrame, covariates: dict) -> pd.DataFrame:
    """
    Between-country variance with country as random effect, per covariate set.
    """
    rows = []
    for label, cov in covariates.items():
        formula = f"log_lcoe ~ {cov}" if cov else "log_lcoe ~ 1"
        model = smf.mixedlm(
            formula, data=d, groups=d["iso3"], re_formula="1",
            vc_formula={"publication": "0 + C(DOI)"},
        )
        result = model.fit(reml=True)
        rows.append({
            "model": label,
            "country_var": result.cov_re.iloc[0, 0],
            "publication_var": result.vcomp[0],
            "residual_var": result.scale,
        })
    table = pd.DataFrame(rows)
    table["country_var_explained_%"] = 100 * (1 - table["country_var"] / table["country_var"].iloc[0])
    return table


def country_lr_test(d: pd.DataFrame, covariates: str = None, reference: str = "Other") -> dict:
    """
    Likelihood-ratio test whether country explains LCOE beyond the covariates.
    """
    base = f"log_lcoe ~ {covariates}" if covariates else "log_lcoe ~ 1"
    country_term = f"C(country_group, Treatment('{reference}'))"
    restricted = fit_mixed_model(d, base, reml=False)
    full = fit_mixed_model(d, f"{base} + {country_term}", reml=False)
    lr = 2 * (full.llf - restricted.llf)
    df_diff = len(full.fe_params) - len(restricted.fe_params)
    return {"LR": lr, "df": df_diff, "p": stats.chi2.sf(lr, df_diff)}


def compare_country_effects(
    d: pd.DataFrame,
    covariates: str,
    reference: str = "Other",
) -> pd.DataFrame:
    """
    Country effects on LCOE before and after controlling for the covariates.
    """
    country_term = f"C(country_group, Treatment('{reference}'))"
    unadjusted = fit_mixed_model(d, f"log_lcoe ~ {country_term}")
    adjusted = fit_mixed_model(d, f"log_lcoe ~ {country_term} + {covariates}")

    adjusted_ci = adjusted.conf_int()
    rows = []
    for name in unadjusted.params.index:
        if not name.startswith(country_term):
            continue
        country = name.split("[T.")[1].rstrip("]")
        rows.append({
            "country": country,
            "n_records": int((d["country_group"] == country).sum()),
            "n_publications": d.loc[d["country_group"] == country, "DOI"].nunique(),
            "unadjusted_effect_%": 100 * (np.exp(unadjusted.params[name]) - 1),
            "adjusted_effect_%": 100 * (np.exp(adjusted.params[name]) - 1),
            "adjusted_ci_low_%": 100 * (np.exp(adjusted_ci.loc[name, 0]) - 1),
            "adjusted_ci_high_%": 100 * (np.exp(adjusted_ci.loc[name, 1]) - 1),
            "adjusted_p": adjusted.pvalues[name],
        })
    table = pd.DataFrame(rows)
    table["adjusted_p_holm"] = multipletests(table["adjusted_p"], method="holm")[1]
    return table.sort_values("n_records", ascending=False).reset_index(drop=True)


def effect_table(result) -> pd.DataFrame:
    """Fixed effects as % change of LCOE per unit / vs. reference, with 95% CI."""
    ci = result.conf_int()
    fixed = [p for p in result.fe_params.index if p != "Intercept"]
    return pd.DataFrame({
        "coef": result.fe_params[fixed],
        "effect_%": 100 * (np.exp(result.fe_params[fixed]) - 1),
        "ci_low_%": 100 * (np.exp(ci.loc[fixed, 0]) - 1),
        "ci_high_%": 100 * (np.exp(ci.loc[fixed, 1]) - 1),
        "p": result.pvalues[fixed],
    }).round(3)
