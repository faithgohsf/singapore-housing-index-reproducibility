import pandas as pd

from shi.economic import eligibility_summary, link_economic_records
from shi.models import fit_predict, grouped_folds, _design


def _buildings():
    return pd.DataFrame({
        "building_id": ["b1"], "address_key": ["10 EXAMPLE ROAD"],
        "shi": [3.5], "shi_status": ["valid"], "year_completed": [2000],
        "total_dwelling_units": [10],
    })


def test_linkage_preserves_repeated_rows_and_parses_month():
    records = pd.DataFrame({
        "month": ["2024-01", "2024-01"], "block": ["10", "10"],
        "street_name": ["EXAMPLE RD", "EXAMPLE RD"], "price": [100.0, 200.0],
        "flat_type": ["3 ROOM", "3 ROOM"],
    })
    result = link_economic_records(records, _buildings(), date_col="month", block_col="block", street_col="street_name", outcome_col="price", type_col="flat_type")
    assert len(result) == 2
    assert result["building_id"].tolist() == ["b1", "b1"]
    assert result["date"].dt.strftime("%Y-%m").tolist() == ["2024-01", "2024-01"]


def test_eligibility_boundary_is_half_open():
    rows = pd.DataFrame({
        "date": pd.to_datetime(["2023-12-01", "2024-01-01", "2025-12-01", "2026-01-01"]),
        "outcome_numeric": [1, 1, 1, 1], "link_status": ["matched_unique"] * 4,
        "shi_status": ["valid"] * 4, "shi": [3.0] * 4,
    })
    assert eligibility_summary(rows)["in_window"] == 2


def test_model_design_uses_training_spline_basis_and_building_folds():
    rng = __import__("numpy").random.default_rng(17)
    rows = []
    for i in range(200):
        rows.append({"coord_x": rng.uniform(10000, 50000), "coord_y": rng.uniform(25000, 50000),
                     "age": rng.integers(1, 80), "shi": rng.uniform(1, 6), "flat_type": rng.choice(["2 ROOM", "3 ROOM"]),
                     "approval_month": f"2024-{rng.integers(1, 13):02d}", "outcome": 1500 + 10 * i,
                     "building_id": f"b{i}"})
    data = pd.DataFrame(rows)
    train, test = data.iloc[:160], data.iloc[160:]
    pred, fallback, rank, columns = fit_predict(train, test, include_shi=True, include_type=True)
    assert len(pred) == len(test)
    assert fallback == []
    Xtr, _, _ = _design(train, test, include_shi=True, include_type=True)
    assert rank == columns == Xtr.shape[1]
    folds = grouped_folds(data, n_splits=5)
    test_ids = [data.iloc[test_idx].building_id.tolist() for _, test_idx in folds]
    assert sorted(sum(test_ids, [])) == sorted(data.building_id.tolist())


def test_full_location_tensor_preserves_additive_coordinate_effects():
    import numpy as np
    rng = np.random.default_rng(113)
    data = pd.DataFrame({
        "coord_x": rng.uniform(10000, 50000, 400),
        "coord_y": rng.uniform(20000, 50000, 400),
        "age": rng.uniform(1, 80, 400),
        "approval_month": ["2024-01"] * 400,
        "building_id": [f"b{i}" for i in range(400)],
    })
    data["outcome"] = 4000 + 0.03 * data.coord_x - 0.02 * data.coord_y
    train, test = data.iloc[:320], data.iloc[320:]
    predicted, _, rank, columns = fit_predict(train, test, include_shi=False, include_type=False)
    assert np.max(np.abs(predicted - test.outcome)) < 1e-7
    assert rank == columns
