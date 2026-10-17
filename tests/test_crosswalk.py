import pandas as pd

from shi.crosswalk import _icc_a1, build_historical_crosswalk, compare_historical
from shi.reconstruction import build_hdb_buildings, compute_shi


def _building():
    row = {
        "blk_no": "01",
        "street": "ANG MO KIO AVE 3",
        "residential": "Y",
        "total_dwelling_units": "15",
        "1room_sold": "0", "2room_sold": "0", "3room_sold": "0",
        "4room_sold": "10", "5room_sold": "0", "exec_sold": "0",
        "multigen_sold": "0", "studio_apartment_sold": "2",
        "1room_rental": "0", "2room_rental": "0", "3room_rental": "0",
        "other_room_rental": "3",
    }
    buildings, _ = build_hdb_buildings(pd.DataFrame([row]))
    return compute_shi(buildings)


def test_multiple_postal_codes_are_preserved_without_multiplying_buildings():
    historical = pd.DataFrame({
        "Postal Code": ["018985", "018986"],
        "Block Number": ["01", "01"],
        "Street Name": ["ANG MO KIO AVENUE 3", "ANG MO KIO AVENUE 3"],
        "Housing Index": ["3.60", "3.60"],
    })
    buildings = _building()
    crosswalk, status = build_historical_crosswalk(buildings, historical)
    assert len(crosswalk) == 2
    assert crosswalk.historical_postal_code.tolist() == ["018985", "018986"]
    assert status.iloc[0].historical_postal_count == 2
    merged, summary = compare_historical(buildings, status)
    assert len(merged) == 1
    assert summary["paired_buildings"] == 1


def test_same_postcode_for_multiple_addresses_is_flagged_ambiguous():
    historical = pd.DataFrame({
        "Postal Code": ["018985", "018985"],
        "Block Number": ["01", "02"],
        "Street Name": ["ANG MO KIO AVENUE 3", "ANG MO KIO AVENUE 3"],
        "Housing Index": ["3.60", "3.70"],
    })
    buildings = _building()
    crosswalk, status = build_historical_crosswalk(buildings, historical)
    assert len(crosswalk) == 1
    assert crosswalk.iloc[0].postal_status == "ambiguous_postcode"
    assert status.iloc[0].historical_match_status == "ambiguous_postcode"
    assert pd.isna(status.iloc[0].historical_shi)


def test_five_digit_export_value_keeps_raw_and_flags_restored_leading_zero():
    historical = pd.DataFrame({
        "Postal Code": ["18985"],
        "Block Number": ["01"],
        "Street Name": ["ANG MO KIO AVENUE 3"],
        "Housing Index": ["3.60"],
    })
    buildings = _building()
    crosswalk, status = build_historical_crosswalk(buildings, historical)
    assert crosswalk.iloc[0].historical_postal_code_raw == "18985"
    assert crosswalk.iloc[0].historical_postal_code == "018985"
    assert crosswalk.iloc[0].postal_normalization_status == "leading_zero_candidate_restored"
    assert status.iloc[0].historical_postal_count == 1


def test_historical_comparison_has_one_row_per_building_and_agreement_outputs():
    buildings = _building()
    historical = pd.DataFrame({
        "Postal Code": ["018985"],
        "Block Number": ["01"],
        "Street Name": ["ANG MO KIO AVENUE 3"],
        "Housing Index": ["3.50"],
    })
    _, status = build_historical_crosswalk(buildings, historical)
    merged, summary = compare_historical(buildings, status)
    assert len(merged) == 1
    assert summary["paired_buildings"] == 1
    assert abs(summary["mean_difference_current_minus_historical"] - 0.1) < 1e-12
    assert summary["icc_A_1_two_way_absolute_agreement"] is None  # insufficient n for an agreement estimate


def test_icc_a1_is_computed_for_multiple_paired_buildings():
    current = pd.Series([1.2, 2.4, 3.6, 4.3])
    historical = pd.Series([1.1, 2.5, 3.4, 4.4])
    value = _icc_a1(current, historical)
    assert value is not None
    assert -1 <= value <= 1
