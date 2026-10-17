from __future__ import annotations

import pandas as pd
import pytest

from shi.descriptive import (
    build_building_summaries,
    rank_associations,
    summarize_shi_bands,
    validate_traceability,
)


@pytest.fixture
def economic_records():
    return pd.DataFrame({
        "source_record_id": [101, 102, 201, 301, 302, 401, 501],
        "building_id": ["b1", "b1", "b2", "b3", "b3", "b4", "b5"],
        "source_address_key": ["1 ROAD"] * 2 + ["2 ROAD", "3 ROAD", "3 ROAD", "4 ROAD", "5 ROAD"],
        "town": ["TOWN"] * 7,
        "shi": [1.5, 1.5, 2.5, 3.5, 3.5, 4.5, 5.5],
        "outcome_numeric": [1000, 1200, 2000, 3000, 3200, 4000, 5000],
        "floor_area_sqm": [50, 50, 60, 70, 70, 80, 90],
    })


def test_building_summaries_keep_source_ids_and_reconcile(economic_records):
    buildings = build_building_summaries(
        economic_records, outcome_col="outcome_numeric", outcome_name="rent"
    )
    assert len(buildings) == 5
    assert buildings.loc[buildings.building_id.eq("b1"), "source_record_ids"].item() == "101|102"
    audit = validate_traceability(economic_records, buildings)
    assert audit["all_source_ids_represented_exactly_once"] is True
    assert audit["record_count_reconciles"] is True
    assert buildings.isna().sum().sum() == 0


def test_tier_summaries_are_equal_building_weight_and_complete(economic_records):
    buildings = build_building_summaries(
        economic_records, outcome_col="outcome_numeric", outcome_name="rent"
    )
    tiers = summarize_shi_bands(buildings, metrics=["mean_outcome", "median_outcome"])
    assert tiers.building_count.sum() == 5
    assert tiers.source_record_count.sum() == len(economic_records)
    assert tiers.shi_tier.tolist() == ["[1,2)", "[2,3)", "[3,4)", "[4,5)", "[5,6]"]
    assert not tiers.isna().any().any()


def test_rank_associations_use_one_row_per_building(economic_records):
    buildings = build_building_summaries(
        economic_records, outcome_col="outcome_numeric", outcome_name="rent"
    )
    ranks = rank_associations(buildings, metrics=["median_outcome"], market="rental")
    assert ranks.association_n_buildings.item() == 5
    assert ranks.spearman_rho.item() == pytest.approx(1.0)
    assert ranks.kendall_tau_b.item() == pytest.approx(1.0)
    assert not ranks.isna().any().any()


def test_resale_price_per_area_is_derived_from_observed_area(economic_records):
    buildings = build_building_summaries(
        economic_records, outcome_col="outcome_numeric", outcome_name="resale", include_price_per_sqm=True
    )
    assert buildings.loc[buildings.building_id.eq("b1"), "mean_price_per_sqm"].item() == pytest.approx(22.0)
    assert buildings.isna().sum().sum() == 0


def test_missing_source_outcome_fails_instead_of_being_silently_omitted(economic_records):
    broken = economic_records.copy()
    broken.loc[0, "outcome_numeric"] = float("nan")
    with pytest.raises(ValueError, match="missing building, SHI, outcome, or town"):
        build_building_summaries(broken, outcome_col="outcome_numeric", outcome_name="rent")
