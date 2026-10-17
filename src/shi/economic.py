"""Source accounting and building linkage for rental and resale records."""
from __future__ import annotations

import pandas as pd

from .reconstruction import normalize_address_key


RENTAL_START = pd.Timestamp("2024-01-01")
RENTAL_END = pd.Timestamp("2026-01-01")


def link_economic_records(
    records: pd.DataFrame,
    buildings: pd.DataFrame,
    *,
    date_col: str,
    block_col: str,
    street_col: str,
    outcome_col: str,
    type_col: str,
    date_format: str | None = None,
) -> pd.DataFrame:
    """Return every source record with parsed date, building match and eligibility flags.

    Source rows are never deduplicated. Linkage is exact after the same documented
    conservative address normalization used for the reconstruction crosswalk.
    """
    needed = {date_col, block_col, street_col, outcome_col, type_col}
    if missing := needed - set(records.columns):
        raise ValueError(f"Records missing fields: {sorted(missing)}")
    if buildings["address_key"].duplicated().any() or buildings["building_id"].duplicated().any():
        raise ValueError("Building table must be unique by address and building ID")
    out = records.copy().reset_index(drop=True)
    out["source_record_id"] = range(1, len(out) + 1)
    address_pairs = pd.MultiIndex.from_arrays([out[block_col].astype("string"), out[street_col].astype("string")])
    unique_pairs = list(dict.fromkeys(address_pairs.tolist()))
    address_map = {pair: normalize_address_key(pair[0], pair[1]) for pair in unique_pairs}
    out["source_address_key"] = [address_map[pair] for pair in address_pairs.tolist()]
    out["date"] = pd.to_datetime(out[date_col], format=date_format, errors="coerce")
    out["outcome_numeric"] = pd.to_numeric(out[outcome_col], errors="coerce")
    out["flat_type_clean"] = out[type_col].astype("string").str.strip().str.upper()
    linked = out.merge(
        buildings[["building_id", "address_key", "shi", "shi_status", "year_completed", "total_dwelling_units"]],
        left_on="source_address_key", right_on="address_key", how="left", validate="many_to_one",
    )
    linked["link_status"] = linked["building_id"].notna().map({True: "matched_unique", False: "unmatched_address"})
    return linked


def eligibility_summary(records: pd.DataFrame, *, start: pd.Timestamp = RENTAL_START, end: pd.Timestamp = RENTAL_END) -> dict[str, int]:
    """Count cohort flow without treating missing links as absence of transactions."""
    in_window = records["date"].ge(start) & records["date"].lt(end)
    positive = records["outcome_numeric"].gt(0)
    linked = records["link_status"].eq("matched_unique")
    valid_shi = records["shi_status"].eq("valid") & records["shi"].notna()
    return {
        "source_records": int(len(records)),
        "unparseable_date": int(records["date"].isna().sum()),
        "in_window": int(in_window.sum()),
        "out_of_window_or_unparseable": int((~in_window).sum()),
        "positive_outcome_in_window": int((in_window & positive).sum()),
        "nonpositive_or_missing_outcome_in_window": int((in_window & ~positive).sum()),
        "matched_unique_in_window": int((in_window & linked).sum()),
        "unmatched_in_window": int((in_window & ~linked).sum()),
        "valid_shi_matched_in_window": int((in_window & linked & valid_shi).sum()),
        "eligible_common_complete_case_before_covariates": int((in_window & linked & valid_shi & positive).sum()),
    }


def add_flat_type_composition_flags(
    linked: pd.DataFrame,
    buildings: pd.DataFrame,
    *,
    observed_type_col: str = "flat_type_clean",
) -> pd.DataFrame:
    """Flag source flat types absent from building composition; no coercive mapping."""
    sold_cols = [c for c in buildings.columns if c.endswith("_sold")]
    rental_cols = [c for c in buildings.columns if c.endswith("_rental")]
    cols = ["building_id", *sold_cols, *rental_cols]
    out = linked.merge(buildings[cols], on="building_id", how="left", validate="many_to_one", suffixes=("", "_composition"))

    def source_category(value: object) -> str | None:
        if pd.isna(value):
            return None
        val = str(value).strip().upper().replace("-", " ")
        if val in {"1 ROOM", "1-ROOM"}:
            return "1room"
        if val in {"2 ROOM", "2-ROOM"}:
            return "2room"
        if val in {"3 ROOM", "3-ROOM"}:
            return "3room"
        if val in {"4 ROOM", "4-ROOM"}:
            return "4room"
        if val in {"5 ROOM", "5-ROOM"}:
            return "5room"
        if val in {"EXECUTIVE", "EXEC"}:
            return "exec"
        if val in {"MULTI-GENERATION", "MULTIGENERATION", "MULTI GENERATION"}:
            return "multigen"
        if val in {"STUDIO APARTMENT", "STUDIO"}:
            return "studio_apartment"
        return None

    cats = out[observed_type_col].map(source_category)
    out["flat_type_mapping_status"] = cats.map(lambda x: "mapped_source_category" if x else "unmapped_source_category")
    out["flat_type_absent_from_composition"] = False
    for category in cats.dropna().unique():
        possible = [f"{category}_sold", f"{category}_rental"] if category not in {"exec", "multigen", "studio_apartment"} else [f"{category}_sold"]
        present = [c for c in possible if c in out.columns]
        if present:
            mask = cats.eq(category)
            counts = out.loc[mask, present].apply(pd.to_numeric, errors="coerce").fillna(0)
            out.loc[mask, "flat_type_absent_from_composition"] = ~counts.gt(0).any(axis=1).to_numpy()
    return out
