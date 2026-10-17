"""Building-level SHI reconstruction from HDB Property Information."""
from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping

import pandas as pd


# Official source field to room-equivalent count. The 2021 paper recommends
# studio flats=1 and other_room_rental=4; established larger classes cap at 6.
ROOM_WEIGHTS: dict[str, int] = {
    "1room_sold": 1,
    "2room_sold": 2,
    "3room_sold": 3,
    "4room_sold": 4,
    "5room_sold": 5,
    "exec_sold": 5,
    "multigen_sold": 6,
    "studio_apartment_sold": 1,
    "1room_rental": 1,
    "2room_rental": 2,
    "3room_rental": 3,
    "other_room_rental": 4,
}

# Historical formula described in the 2021 article before its recommended
# corrections: studio=3 and other_room_rental contributes 0 to the numerator.
# The published total dwelling count remains the denominator, reproducing the
# known historical treatment while keeping this variant explicit.
LEGACY_2021_WEIGHTS = {**ROOM_WEIGHTS, "studio_apartment_sold": 3, "other_room_rental": 0}

_REQUIRED_ADDRESS_COLUMNS = ("blk_no", "street", "residential")
_REQUIRED_COMPOSITION_COLUMNS = ("total_dwelling_units", *ROOM_WEIGHTS)

# Expand only known abbreviation tokens. ST is treated as STREET only when it
# is the last token or immediately precedes a numeric street segment, avoiding
# unintended changes to names beginning with Saint (e.g. ST GEORGE).
_STREET_EXPANSIONS = {
    "AVE": "AVENUE",
    "RD": "ROAD",
    "DR": "DRIVE",
    "CRES": "CRESCENT",
    "CTRL": "CENTRAL",
    "LOR": "LORONG",
    "NTH": "NORTH",
    "STH": "SOUTH",
    "BT": "BUKIT",
    "BLVD": "BOULEVARD",
    "PK": "PARK",
    "GDNS": "GARDENS",
    "HTS": "HEIGHTS",
    "TER": "TERRACE",
    "CL": "CLOSE",
    "PL": "PLACE",
}


def _normalise_tokens(value: object) -> list[str]:
    if value is None or pd.isna(value):
        return []
    text = str(value).upper().replace("'", "")
    return re.findall(r"[A-Z0-9]+", text)


def normalize_address_key(block_no: object, street: object) -> str:
    """Return a conservative canonical block/street key.

    Raw source values are never changed. Postal codes are not normalized here;
    callers must retain them as strings so leading zeroes survive.
    """
    block_tokens = _normalise_tokens(block_no)
    street_tokens = _normalise_tokens(street)
    expanded: list[str] = []
    for i, token in enumerate(street_tokens):
        if token == "ST" and (i == len(street_tokens) - 1 or street_tokens[i + 1].isdigit()):
            expanded.append("STREET")
        else:
            expanded.append(_STREET_EXPANSIONS.get(token, token))
    return " ".join(block_tokens + expanded)


def _stable_building_id(address_key: str) -> str:
    digest = hashlib.sha256(address_key.encode("utf-8")).hexdigest()[:20]
    return f"hdb-{digest}"


def _distinct_nonempty(values: pd.Series) -> list[str]:
    return sorted({str(v) for v in values if not pd.isna(v) and str(v).strip() != ""})


def build_hdb_buildings(properties: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Create one residential record per canonical physical-building key.

    Exact repeated source records are retained in the raw input and represented
    by ``source_record_count``. Conflicting records are not silently selected:
    their conflicting fields are nulled and the building is marked invalid for
    scoring. Canonical collisions between distinct raw address strings are
    retained as one ambiguous building key and are also ineligible for scoring.
    """
    df = properties.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    missing = [c for c in (*_REQUIRED_ADDRESS_COLUMNS, *_REQUIRED_COMPOSITION_COLUMNS) if c not in df]
    if missing:
        raise ValueError(f"HDB property source missing required columns: {missing}")
    df["source_row_number"] = range(1, len(df) + 1)
    df["is_residential"] = df["residential"].astype("string").str.strip().str.upper().eq("Y")
    stats = {
        "source_rows": int(len(df)),
        "residential_source_rows": int(df["is_residential"].sum()),
        "nonresidential_source_rows": int((~df["is_residential"]).sum()),
    }
    df = df.loc[df["is_residential"]].copy()
    df["address_key"] = [normalize_address_key(b, s) for b, s in zip(df["blk_no"], df["street"])]
    if df["address_key"].eq("").any():
        raise ValueError("Residential record has empty canonical block/street key")

    # The common case is already one source row per canonical address. Avoid
    # constructing thousands of tiny pandas groups for this path.
    if df["address_key"].is_unique:
        buildings = df.drop(columns=["is_residential"]).copy()
        buildings["building_id"] = buildings["address_key"].map(_stable_building_id)
        buildings["source_record_count"] = 1
        buildings["source_row_numbers"] = buildings["source_row_number"].astype(str)
        buildings["canonical_address_collision"] = False
        buildings["source_conflict_fields"] = ""
        buildings["source_record_status"] = "ok"
        stats["residential_buildings"] = int(len(buildings))
        stats["duplicate_address_groups"] = 0
        stats["canonical_address_collision_groups"] = 0
        stats["conflicting_source_groups"] = 0
        return buildings.reset_index(drop=True), stats

    records: list[dict[str, object]] = []
    metadata_columns = [c for c in df.columns if c not in {"source_row_number", "is_residential", "address_key"}]
    for address_key, group in df.groupby("address_key", sort=True, dropna=False):
        row: dict[str, object] = {
            "building_id": _stable_building_id(str(address_key)),
            "address_key": str(address_key),
            "source_record_count": int(len(group)),
            "source_row_numbers": ";".join(map(str, group["source_row_number"].tolist())),
        }
        conflicts: list[str] = []
        for col in metadata_columns:
            vals = _distinct_nonempty(group[col])
            # Empty/missing among otherwise present values is a conflict, not zero.
            has_missing = group[col].isna().any() or group[col].astype("string").str.strip().eq("").any()
            if len(vals) > 1 or (has_missing and vals):
                conflicts.append(col)
                row[col] = pd.NA
            elif vals:
                row[col] = vals[0]
            else:
                row[col] = pd.NA
        raw_addresses = {(str(b).strip(), str(s).strip()) for b, s in zip(group["blk_no"], group["street"])}
        row["canonical_address_collision"] = len(raw_addresses) > 1
        row["source_conflict_fields"] = ";".join(conflicts)
        row["source_record_status"] = (
            "conflicting_source_records" if conflicts else
            "canonical_address_collision" if len(raw_addresses) > 1 else
            "ok"
        )
        records.append(row)

    buildings = pd.DataFrame.from_records(records)
    stats["residential_buildings"] = int(len(buildings))
    stats["duplicate_address_groups"] = int((buildings["source_record_count"] > 1).sum())
    stats["canonical_address_collision_groups"] = int(buildings["canonical_address_collision"].sum())
    stats["conflicting_source_groups"] = int(buildings["source_record_status"].eq("conflicting_source_records").sum())
    return buildings, stats


def compute_shi(buildings: pd.DataFrame, formula: str = "recommended") -> pd.DataFrame:
    """Calculate a room-weighted building score, preserving invalid rows/reasons.

    ``recommended`` uses the corrections recommended by Lim et al. (2021).
    ``legacy_2021`` retains the historical formula variant for controlled
    same-input formula comparisons. Both require complete, reconciled counts.
    """
    if formula not in {"recommended", "legacy_2021"}:
        raise ValueError("formula must be 'recommended' or 'legacy_2021'")
    weights: Mapping[str, int] = ROOM_WEIGHTS if formula == "recommended" else LEGACY_2021_WEIGHTS
    required = ["total_dwelling_units", *weights]
    missing = [c for c in required if c not in buildings]
    if missing:
        raise ValueError(f"Building table missing composition columns: {missing}")
    out = buildings.copy()
    numeric = out[required].apply(pd.to_numeric, errors="coerce")
    counts = numeric[list(weights)]
    total = numeric["total_dwelling_units"]
    count_sum = counts.sum(axis=1, min_count=len(weights))
    numerator = sum(counts[col] * weight for col, weight in weights.items())

    reasons: list[str] = []
    scores: list[float | None] = []
    for i in range(len(out)):
        row_reasons: list[str] = []
        if out.iloc[i].get("source_record_status", "ok") != "ok":
            row_reasons.append(str(out.iloc[i].get("source_record_status")))
        vals = numeric.iloc[i]
        if vals.isna().any():
            row_reasons.append("missing_or_nonnumeric_composition")
        elif (vals < 0).any():
            row_reasons.append("negative_composition_count")
        elif total.iloc[i] <= 0:
            row_reasons.append("zero_or_nonpositive_total_units")
        elif count_sum.iloc[i] != total.iloc[i]:
            row_reasons.append("composition_total_mismatch")
        score = None if row_reasons else float(numerator.iloc[i] / total.iloc[i])
        scores.append(score)
        reasons.append(";".join(dict.fromkeys(row_reasons)))

    out["shi_formula"] = formula
    out["composition_count_sum"] = count_sum
    out["shi_numerator"] = numerator
    out["shi"] = pd.array(scores, dtype="Float64")
    out["shi_status"] = ["valid" if not reason else "invalid" for reason in reasons]
    out["shi_invalid_reason"] = reasons
    return out
