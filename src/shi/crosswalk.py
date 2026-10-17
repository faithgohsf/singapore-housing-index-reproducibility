"""Postal crosswalk and historical SHI comparison utilities."""
from __future__ import annotations

import pandas as pd

from .reconstruction import normalize_address_key


def _valid_postcode(value: object) -> bool:
    text = "" if pd.isna(value) else str(value).strip()
    return len(text) == 6 and text.isdigit()


def build_historical_crosswalk(
    buildings: pd.DataFrame,
    historical: pd.DataFrame,
    *,
    building_block_col: str = "blk_no",
    building_street_col: str = "street",
    postal_col: str = "Postal Code",
    hist_block_col: str = "Block Number",
    hist_street_col: str = "Street Name",
    hist_score_col: str = "Housing Index",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Link historical postal records to physical buildings by normalized address.

    Returns (postal_crosswalk, building_status). Multiple postal codes for one
    building remain separate crosswalk rows. No unmatched address is assigned
    to a private category. A postcode mapping to multiple canonical addresses
    is flagged ambiguous; no transaction table is joined through this exploded
    crosswalk.
    """
    required_b = {"building_id", "address_key", building_block_col, building_street_col}
    required_h = {postal_col, hist_block_col, hist_street_col, hist_score_col}
    if missing := required_b - set(buildings.columns):
        raise ValueError(f"Building table missing columns: {sorted(missing)}")
    if missing := required_h - set(historical.columns):
        raise ValueError(f"Historical table missing columns: {sorted(missing)}")
    if buildings["building_id"].duplicated().any():
        raise ValueError("Building table must have one row per physical building_id")

    hist = historical.copy()
    hist["historical_postal_code_raw"] = hist[postal_col].astype("string").str.strip()
    raw_postal = hist["historical_postal_code_raw"]
    five_digit_numeric = raw_postal.str.fullmatch(r"\d{5}").fillna(False)
    six_digit_numeric = raw_postal.str.fullmatch(r"\d{6}").fillna(False)
    hist["historical_postal_code"] = raw_postal.where(~five_digit_numeric, raw_postal.str.zfill(6))
    hist["postal_normalization_status"] = "invalid_postal_format"
    hist.loc[six_digit_numeric, "postal_normalization_status"] = "valid_six_digit"
    hist.loc[five_digit_numeric, "postal_normalization_status"] = "leading_zero_candidate_restored"
    hist["historical_address_key"] = [
        normalize_address_key(b, s) for b, s in zip(hist[hist_block_col], hist[hist_street_col])
    ]
    hist["historical_shi"] = pd.to_numeric(hist[hist_score_col], errors="coerce")
    hist = hist.loc[hist["historical_address_key"].ne("")].copy()
    # One source row per exact postal/address/score tuple. The source file itself
    # is retained unchanged; this removes only redundant join edges.
    hist_edges = hist.drop_duplicates(
        ["historical_postal_code_raw", "historical_postal_code", "historical_address_key", "historical_shi"]
    )
    postal_address_n = hist_edges.groupby("historical_postal_code")["historical_address_key"].nunique()
    ambiguous_postcodes = set(postal_address_n[postal_address_n.gt(1)].index)

    # Vectorized join avoids constructing one pandas DataFrame per source
    # postal-code group (the source contains ~80k rows).
    left = buildings[["building_id", "address_key", building_block_col, building_street_col]].copy()
    edges = left.merge(
        hist_edges[["historical_postal_code_raw", "historical_postal_code", "postal_normalization_status", "historical_address_key", "historical_shi"]],
        left_on="address_key", right_on="historical_address_key", how="inner", validate="one_to_many",
    )
    edges["postal_status"] = edges["historical_postal_code"].map(
        lambda code: "ambiguous_postcode" if code in ambiguous_postcodes else "one_address"
    )
    if not edges.empty:
        edge_status = edges.groupby("building_id", sort=False).agg(
            historical_postal_count=("historical_postal_code", "nunique"),
            historical_score_count=("historical_shi", "nunique"),
            postal_ambiguity=("postal_status", lambda x: x.eq("ambiguous_postcode").any()),
            historical_postal_codes=("historical_postal_code", lambda x: ";".join(sorted(set(x.astype(str))))),
            historical_shi=("historical_shi", "min"),
        ).reset_index()
    else:
        edge_status = pd.DataFrame(columns=[
            "building_id", "historical_postal_count", "historical_score_count", "postal_ambiguity",
            "historical_postal_codes", "historical_shi",
        ])
    building_status = left[["building_id", "address_key"]].merge(edge_status, on="building_id", how="left", validate="one_to_one")
    building_status["historical_postal_count"] = building_status["historical_postal_count"].fillna(0).astype(int)
    building_status["historical_score_count"] = building_status["historical_score_count"].fillna(0).astype(int)
    building_status["postal_ambiguity"] = building_status["postal_ambiguity"].fillna(False).astype(bool)
    building_status["historical_postal_codes"] = building_status["historical_postal_codes"].fillna("")
    building_status["historical_match_status"] = "matched_address"
    building_status.loc[building_status["historical_postal_count"].eq(0), "historical_match_status"] = "unmatched_address"
    building_status.loc[building_status["historical_postal_count"].gt(0) & building_status["historical_score_count"].eq(0), "historical_match_status"] = "missing_historical_score"
    building_status.loc[building_status["historical_score_count"].gt(1), "historical_match_status"] = "conflicting_historical_scores"
    building_status.loc[building_status["postal_ambiguity"], "historical_match_status"] = "ambiguous_postcode"
    use_score = building_status["historical_match_status"].eq("matched_address")
    building_status.loc[~use_score, "historical_shi"] = pd.NA
    crosswalk = edges.rename(columns={building_block_col: "block_no", building_street_col: "street"})[
        ["building_id", "address_key", "block_no", "street", "historical_postal_code_raw", "historical_postal_code", "postal_normalization_status",
         "historical_shi", "historical_address_key", "postal_status"]
    ].merge(building_status[["building_id", "historical_match_status"]], on="building_id", how="left", validate="many_to_one")
    if building_status["building_id"].duplicated().any():
        raise AssertionError("Historical status must have one row per physical building")
    if not crosswalk.empty:
        if not crosswalk["historical_postal_code"].map(_valid_postcode).all():
            raise ValueError("Historical postal code must be retained as a six-digit string")
    return crosswalk, building_status


def _icc_a1(source_a: pd.Series, source_b: pd.Series) -> float | None:
    """Two-way absolute-agreement, single-measure ICC(A,1) for two sources."""
    pair = pd.concat([source_a, source_b], axis=1).dropna().astype(float)
    n, k = pair.shape
    if n < 2 or k != 2:
        return None
    values = pair.to_numpy()
    grand = values.mean()
    row_means = values.mean(axis=1)
    col_means = values.mean(axis=0)
    ss_rows = k * ((row_means - grand) ** 2).sum()
    ss_cols = n * ((col_means - grand) ** 2).sum()
    residual = values - row_means[:, None] - col_means[None, :] + grand
    ss_error = (residual ** 2).sum()
    ms_rows = ss_rows / (n - 1)
    ms_cols = ss_cols / (k - 1)
    ms_error = ss_error / ((n - 1) * (k - 1))
    denominator = ms_rows + (k - 1) * ms_error + (k / n) * (ms_cols - ms_error)
    if denominator == 0:
        return None
    return float((ms_rows - ms_error) / denominator)


def compare_historical(
    buildings: pd.DataFrame,
    building_status: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Pair valid current SHI with unambiguous historical score by building."""
    if buildings["building_id"].duplicated().any() or building_status["building_id"].duplicated().any():
        raise ValueError("Historical comparison requires unique building_id tables")
    required = {"building_id", "shi", "shi_status"}
    if missing := required - set(buildings.columns):
        raise ValueError(f"Current building table missing columns: {sorted(missing)}")
    merged = buildings.merge(building_status, on=["building_id", "address_key"], how="left", validate="one_to_one")
    merged["historical_shi"] = pd.to_numeric(merged["historical_shi"], errors="coerce")
    merged["shi"] = pd.to_numeric(merged["shi"], errors="coerce")
    merged["comparison_status"] = merged["historical_match_status"].fillna("unmatched_address")
    paired = merged["shi_status"].eq("valid") & merged["historical_match_status"].eq("matched_address") & merged["historical_shi"].notna()
    merged["paired_for_agreement"] = paired
    merged["difference_current_minus_historical"] = pd.NA
    merged.loc[paired, "difference_current_minus_historical"] = (
        merged.loc[paired, "shi"].astype(float) - merged.loc[paired, "historical_shi"].astype(float)
    )
    bins = [1, 2, 3, 4, 5, 6.0000000001]
    labels = ["[1,2)", "[2,3)", "[3,4)", "[4,5)", "[5,6)"]
    merged["current_display_band"] = pd.cut(merged["shi"], bins=bins, labels=labels, right=False, include_lowest=True)
    merged["historical_display_band"] = pd.cut(merged["historical_shi"], bins=bins, labels=labels, right=False, include_lowest=True)
    merged["display_band_changed"] = pd.NA
    band_comparable = paired & merged["current_display_band"].notna() & merged["historical_display_band"].notna()
    merged.loc[band_comparable, "display_band_changed"] = (
        merged.loc[band_comparable, "current_display_band"].astype("string").to_numpy()
        != merged.loc[band_comparable, "historical_display_band"].astype("string").to_numpy()
    )

    pair = merged.loc[paired, ["shi", "historical_shi", "difference_current_minus_historical"]].astype(float)
    diff = pair["difference_current_minus_historical"]
    n = int(len(pair))
    sd = float(diff.std(ddof=1)) if n > 1 else None
    mean_diff = float(diff.mean()) if n else None
    summary: dict[str, object] = {
        "hdb_residential_buildings": int(len(merged)),
        "current_valid_shi_buildings": int(merged["shi_status"].eq("valid").sum()),
        "historical_address_matched_buildings": int(merged["historical_match_status"].isin(["matched_address", "conflicting_historical_scores", "ambiguous_postcode", "missing_historical_score"]).sum()),
        "historical_unmatched_buildings": int(merged["historical_match_status"].eq("unmatched_address").sum()),
        "historical_conflicting_score_buildings": int(merged["historical_match_status"].eq("conflicting_historical_scores").sum()),
        "historical_ambiguous_postcode_buildings": int(merged["historical_match_status"].eq("ambiguous_postcode").sum()),
        "historical_multicode_buildings": int(merged["historical_postal_count"].fillna(0).astype(int).gt(1).sum()),
        "paired_buildings": n,
        "mean_difference_current_minus_historical": mean_diff,
        "mean_absolute_difference": float(diff.abs().mean()) if n else None,
        "difference_sd_sample": sd,
        "limits_of_agreement_lower": mean_diff - 1.96 * sd if n and sd is not None else None,
        "limits_of_agreement_upper": mean_diff + 1.96 * sd if n and sd is not None else None,
        "icc_A_1_two_way_absolute_agreement": _icc_a1(pair["shi"], pair["historical_shi"]) if n else None,
        "display_band_comparable_buildings": int(band_comparable.sum()),
        "display_band_changes": int(merged.loc[band_comparable, "display_band_changed"].fillna(False).astype(bool).sum()),
        "display_band_change_basis": "protocol SHI display bands; continuous scores retained",
    }
    return merged, summary
