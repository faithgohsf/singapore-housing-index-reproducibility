"""Building-level economic summaries and descriptive SHI rank associations."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import kendalltau, spearmanr

SHI_BANDS = [
    (1.0, 2.0, "[1,2)"),
    (2.0, 3.0, "[2,3)"),
    (3.0, 4.0, "[3,4)"),
    (4.0, 5.0, "[4,5)"),
    (5.0, 6.0, "[5,6]"),
]


def _validate_input(records: pd.DataFrame, *, outcome_col: str, require_area: bool = False) -> pd.DataFrame:
    required = {"source_record_id", "building_id", "shi", outcome_col, "town"}
    if require_area:
        required.add("floor_area_sqm")
    missing = sorted(required - set(records.columns))
    if missing:
        raise ValueError(f"Descriptive input is missing required columns: {missing}")
    out = records.copy()
    out["source_record_id"] = pd.to_numeric(out["source_record_id"], errors="coerce")
    out["shi"] = pd.to_numeric(out["shi"], errors="coerce")
    out[outcome_col] = pd.to_numeric(out[outcome_col], errors="coerce")
    if out["source_record_id"].isna().any():
        raise ValueError("Missing or nonnumeric source_record_id values are not allowed")
    if out["source_record_id"].duplicated().any():
        raise ValueError("source_record_id must be unique within a source dataset")
    if out[["building_id", "shi", outcome_col, "town"]].isna().any().any():
        raise ValueError("Eligible descriptive records contain missing building, SHI, outcome, or town values")
    if not out[outcome_col].gt(0).all():
        raise ValueError("Descriptive economic outcomes must be positive")
    if not out["shi"].between(1.0, 6.0, inclusive="both").all():
        raise ValueError("Eligible SHI values must lie within [1, 6]")
    if require_area:
        out["floor_area_sqm"] = pd.to_numeric(out["floor_area_sqm"], errors="coerce")
        if out["floor_area_sqm"].isna().any() or not out["floor_area_sqm"].gt(0).all():
            raise ValueError("Resale price-per-square-metre summaries require positive observed floor area")
    return out


def _band(score: float) -> str:
    for lower, upper, label in SHI_BANDS:
        if lower <= score < upper or (label == "[5,6]" and score <= upper):
            return label
    raise ValueError(f"SHI value outside display bands: {score}")


def build_building_summaries(
    records: pd.DataFrame,
    *,
    outcome_col: str,
    outcome_name: str,
    include_price_per_sqm: bool = False,
) -> pd.DataFrame:
    """Aggregate source records to one row per building, retaining source IDs."""
    data = _validate_input(records, outcome_col=outcome_col, require_area=include_price_per_sqm)
    if "source_address_key" not in data:
        raise ValueError("source_address_key is required to make each result traceable to its matched source address")
    for column in ["shi", "town", "source_address_key"]:
        if data.groupby("building_id")[column].nunique(dropna=False).gt(1).any():
            raise ValueError(f"{column} must be consistent within each building")
    if include_price_per_sqm:
        data["price_per_sqm"] = data[outcome_col] / data["floor_area_sqm"]
    aggregations: dict[str, tuple[str, str]] = {
        "shi": ("shi", "first"),
        "town": ("town", "first"),
        "source_address_key": ("source_address_key", "first"),
        "source_record_count": ("source_record_id", "size"),
        "source_record_ids": ("source_record_id", lambda values: "|".join(str(int(x)) for x in sorted(values))),
        "mean_outcome": (outcome_col, "mean"),
        "median_outcome": (outcome_col, "median"),
        "p25_outcome": (outcome_col, lambda values: values.quantile(0.25)),
        "p75_outcome": (outcome_col, lambda values: values.quantile(0.75)),
    }
    if include_price_per_sqm:
        aggregations.update({
            "mean_price_per_sqm": ("price_per_sqm", "mean"),
            "median_price_per_sqm": ("price_per_sqm", "median"),
            "p25_price_per_sqm": ("price_per_sqm", lambda values: values.quantile(0.25)),
            "p75_price_per_sqm": ("price_per_sqm", lambda values: values.quantile(0.75)),
        })
    buildings = data.groupby("building_id", sort=True).agg(**aggregations).reset_index()
    if buildings["building_id"].duplicated().any():
        raise AssertionError("Building summaries must have one row per physical building")
    buildings["shi_tier"] = buildings["shi"].map(_band)
    buildings["outcome_name"] = outcome_name
    return buildings


def summarize_shi_bands(buildings: pd.DataFrame, *, metrics: list[str]) -> pd.DataFrame:
    """Summarize building-level outcome distributions within observed SHI bands."""
    rows = []
    for tier, group in buildings.groupby("shi_tier", sort=False):
        row: dict[str, object] = {
            "shi_tier": tier,
            "building_count": int(group["building_id"].nunique()),
            "source_record_count": int(group["source_record_count"].sum()),
            "mean_shi": float(group["shi"].mean()),
            "median_shi": float(group["shi"].median()),
        }
        for metric in metrics:
            values = pd.to_numeric(group[metric], errors="raise")
            row.update({
                f"mean_building_{metric}": float(values.mean()),
                f"median_building_{metric}": float(values.median()),
                f"p25_building_{metric}": float(values.quantile(0.25)),
                f"p75_building_{metric}": float(values.quantile(0.75)),
            })
        rows.append(row)
    result = pd.DataFrame(rows)
    if result.empty or result.isna().any().any():
        raise AssertionError("SHI band summaries must contain observed tiers and no missing values")
    return result


def rank_associations(buildings: pd.DataFrame, *, metrics: list[str], market: str) -> pd.DataFrame:
    """Compute descriptive Spearman rho and Kendall tau using one row per building."""
    rows = []
    for metric in metrics:
        pair = buildings[["building_id", "shi", metric]].copy()
        if pair.isna().any().any():
            raise ValueError(f"Rank association inputs contain missing values for {market}/{metric}")
        if pair["building_id"].duplicated().any():
            raise ValueError("Rank associations require one row per building")
        rho = spearmanr(pair["shi"], pair[metric]).statistic
        tau = kendalltau(pair["shi"], pair[metric]).statistic
        if not np.isfinite(rho) or not np.isfinite(tau):
            raise ValueError(f"Rank statistic undefined for {market}/{metric}; check for constant values")
        rows.append({
            "market": market,
            "building_metric": metric,
            "association_unit": "physical building",
            "association_n_buildings": int(len(pair)),
            "spearman_rho": float(rho),
            "kendall_tau_b": float(tau),
            "interpretation": "descriptive rank association; no causal or individual-SES interpretation",
        })
    return pd.DataFrame(rows)


def validate_traceability(records: pd.DataFrame, buildings: pd.DataFrame) -> dict[str, object]:
    """Check complete source-ID accounting between records and building outputs."""
    record_ids = records["source_record_id"].astype(int)
    output_ids = [int(value) for cell in buildings["source_record_ids"] for value in cell.split("|") if value]
    if len(output_ids) != len(set(output_ids)):
        raise AssertionError("A source record ID occurs in multiple building summaries")
    if set(output_ids) != set(record_ids):
        missing = sorted(set(record_ids) - set(output_ids))[:10]
        extra = sorted(set(output_ids) - set(record_ids))[:10]
        raise AssertionError(f"Source record IDs are not fully traceable; missing={missing}, extra={extra}")
    if buildings.isna().any().any():
        raise AssertionError("Building-level output contains missing values")
    if int(buildings["source_record_count"].sum()) != len(records):
        raise AssertionError("Building source-record counts do not reconcile to input records")
    return {
        "input_source_records": int(len(records)),
        "output_buildings": int(buildings["building_id"].nunique()),
        "source_ids_unique": True,
        "all_source_ids_represented_exactly_once": True,
        "building_output_missing_cells": int(buildings.isna().sum().sum()),
        "record_count_reconciles": True,
    }


def descriptive_metadata() -> dict[str, object]:
    return {
        "study_period": "2024-01-01 inclusive through 2026-01-01 exclusive",
        "shi_display_bands": [label for _, _, label in SHI_BANDS],
        "analysis_unit": "physical HDB building",
        "building_outcomes": "mean, median, 25th percentile and 75th percentile of eligible source-record outcomes within building",
        "band_summaries": "equal weight per building within observed SHI band; source-record count reported separately",
        "rank_statistics": "Spearman rho and Kendall tau-b between continuous SHI and building-level median outcome",
        "rank_statistics_interpretation": "descriptive association; no p-value, causal, household, or individual-SES claim",
        "source_record_id": "row ordinal assigned during frozen source ingestion; resolves to the corresponding saved raw dataset row",
        "resale_price_per_sqm": "descriptive only; transaction total price divided by source-reported approximate floor area",
    }
