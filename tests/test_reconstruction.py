from pathlib import Path
import sys

import pandas as pd
import pytest

# Allow this test file to run directly from PyCharm as well as through pytest.
PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(PROJECT_SRC))

from shi.reconstruction import ROOM_WEIGHTS, build_hdb_buildings, compute_shi, normalize_address_key


def _property_row(**overrides):
    row = {
        "blk_no": "01",
        "street": "ANG MO KIO AVE 3",
        "residential": "Y",
        "total_dwelling_units": "15",
        **{column: "0" for column in ROOM_WEIGHTS},
        "4room_sold": "10",
        "studio_apartment_sold": "2",
        "other_room_rental": "3",
    }
    row.update(overrides)
    return row


def test_normalizer_expands_known_abbreviations_and_preserves_block_zero():
    assert normalize_address_key("01", "ANG MO KIO AVE 3") == "01 ANG MO KIO AVENUE 3"
    assert normalize_address_key("1", "ST GEORGE'S LANE") == "1 ST GEORGES LANE"


def test_builds_one_building_from_repeated_identical_source_rows():
    source = pd.DataFrame([_property_row(), _property_row()])
    buildings, counts = build_hdb_buildings(source)
    assert len(buildings) == 1
    assert buildings.iloc[0].source_record_count == 2
    assert counts["residential_source_rows"] == 2
    assert counts["residential_buildings"] == 1
    scored = compute_shi(buildings)
    assert scored.iloc[0].shi_status == "valid"


def test_conflicting_duplicate_composition_is_not_silently_selected():
    source = pd.DataFrame([_property_row(), _property_row(**{"4room_sold": "9", "total_dwelling_units": "14"})])
    buildings, _ = build_hdb_buildings(source)
    assert buildings.iloc[0].source_record_status == "conflicting_source_records"
    scored = compute_shi(buildings)
    assert scored.iloc[0].shi_status == "invalid"
    assert "conflicting_source_records" in scored.iloc[0].shi_invalid_reason


def test_recommended_and_legacy_formula_variants_are_explicit():
    buildings, _ = build_hdb_buildings(pd.DataFrame([_property_row()]))
    corrected = compute_shi(buildings, "recommended").iloc[0]
    legacy = compute_shi(buildings, "legacy_2021").iloc[0]
    assert corrected.shi == pytest.approx(3.6)
    assert legacy.shi == pytest.approx(46 / 15)
    assert corrected.shi_formula == "recommended"
    assert legacy.shi_formula == "legacy_2021"


@pytest.mark.parametrize(
    "overrides,reason",
    [
        ({"2room_sold": ""}, "missing_or_nonnumeric_composition"),
        ({"total_dwelling_units": "0", "4room_sold": "0", "studio_apartment_sold": "0", "other_room_rental": "0"}, "zero_or_nonpositive_total_units"),
        ({"total_dwelling_units": "16"}, "composition_total_mismatch"),
        ({"3room_rental": "-1", "total_dwelling_units": "14"}, "negative_composition_count"),
    ],
)
def test_invalid_composition_yields_reason_not_partial_score(overrides, reason):
    buildings, _ = build_hdb_buildings(pd.DataFrame([_property_row(**overrides)]))
    scored = compute_shi(buildings)
    assert pd.isna(scored.iloc[0].shi)
    assert scored.iloc[0].shi_status == "invalid"
    assert reason in scored.iloc[0].shi_invalid_reason



@pytest.mark.parametrize("field,expected", [("5room_sold", 5), ("exec_sold", 6), ("multigen_sold", 6)])
def test_distinguish_five_room_executive_multigeneration(field, expected):
    row = _property_row(**{k: "0" for k in ROOM_WEIGHTS})
    row.update({"total_dwelling_units": "10", field: "10"})
    buildings, _ = build_hdb_buildings(pd.DataFrame([row]))
    assert compute_shi(buildings).iloc[0].shi == expected

def test_mixed_executive_and_alternative():
    row = _property_row(**{k: "0" for k in ROOM_WEIGHTS})
    row.update({"total_dwelling_units": "10", "exec_sold": "4", "5room_sold": "3", "4room_sold": "3"})
    buildings, _ = build_hdb_buildings(pd.DataFrame([row]))
    primary = compute_shi(buildings).iloc[0]
    alternative = compute_shi(buildings, "executive_weight_5").iloc[0]
    assert primary.shi == pytest.approx(5.1)
    assert alternative.shi == pytest.approx(4.7)
    assert primary.shi-alternative.shi == pytest.approx(4/10)
    assert compute_shi(buildings, "legacy_2021").iloc[0].shi == pytest.approx(5.1)
    assert compute_shi(buildings, "legacy_2021_executive_weight_5").iloc[0].shi == pytest.approx(4.7)

def test_executive_mapping_does_not_rescue_incomplete_counts():
    buildings, _ = build_hdb_buildings(pd.DataFrame([_property_row(**{"exec_sold": ""})]))
    for formula in ["recommended", "executive_weight_5"]:
        scored = compute_shi(buildings, formula).iloc[0]
        assert scored.shi_status == "invalid" and pd.isna(scored.shi)

if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
