from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

PROJECT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))

import geocode_buildings_onemap as onemap  # noqa: E402
import retrieve_public_data as retrieval  # noqa: E402
import run_descriptive_analyses as descriptive_export  # noqa: E402
from shi.models import grouped_folds, prepare_rental, _remaining_lease_months  # noqa: E402


class _Response:
    status_code = 200

    def __init__(self, body):
        self.body = body

    def json(self):
        return self.body

    def raise_for_status(self):
        return None


class _Session:
    def __init__(self, bodies):
        self.bodies = bodies
        self.pages = []

    def get(self, url, *, params, headers, timeout):
        assert url == onemap.SEARCH_URL
        assert headers["Authorization"] == "unit-test-token"
        self.pages.append(params["pageNum"])
        return _Response(self.bodies[params["pageNum"]])


def test_onemap_search_reads_every_page_before_unique_match_decision():
    session = _Session({
        1: {"totalNumPages": 2, "results": [{"BLK_NO": "10", "ROAD_NAME": "EXAMPLE ROAD"}]},
        2: {"totalNumPages": 2, "results": [{"BLK_NO": "10", "ROAD_NAME": "EXAMPLE ROAD", "POSTAL": "123456"}]},
    })
    results = onemap.search_candidates(session, "10 EXAMPLE ROAD", "unit-test-token")
    exact = [r for r in results if onemap.normalize_address_key(r["BLK_NO"], r["ROAD_NAME"]) == "10 EXAMPLE ROAD"]
    assert session.pages == [1, 2]
    assert len(exact) == 2  # duplicate exact results remain ambiguous, not first-result selected


def test_onemap_empty_search_is_valid_and_incomplete_full_page_fails():
    empty = _Session({1: {"totalNumPages": 0, "results": []}})
    assert onemap.search_candidates(empty, "NO SUCH ADDRESS", "unit-test-token") == []
    incomplete = _Session({1: {"results": [{"candidate": n} for n in range(10)]}})
    with pytest.raises(ValueError, match="incomplete match decision"):
        onemap.search_candidates(incomplete, "ADDRESS", "unit-test-token")


def test_source_validation_checks_schema_nonempty_rows_and_content_length(tmp_path):
    path = tmp_path / "snapshot.csv"
    headers = sorted(retrieval.REQUIRED_COLUMNS["hdb_rental_approval__retrieved_2026-10-16.csv"])
    path.write_text(",".join(headers) + "\n" + ",".join("x" for _ in headers) + "\n")
    rows = retrieval.validate_csv_snapshot(path, "hdb_rental_approval__retrieved_2026-10-16.csv")
    assert rows == 1
    with pytest.raises(ValueError, match="size-mismatched"):
        retrieval.validate_csv_snapshot(path, "hdb_rental_approval__retrieved_2026-10-16.csv", expected_bytes=path.stat().st_size + 1)
    path.write_text("bad,header\n1,2\n")
    with pytest.raises(ValueError, match="missing required columns"):
        retrieval.validate_csv_snapshot(path, "hdb_rental_approval__retrieved_2026-10-16.csv")


def test_nested_mendeley_manifest_enforces_frozen_checksum_and_bytes():
    manifest = {"files": [{"filename": "data in brief.csv", "downloaded_sha256": "frozen-digest", "size": 12345}]}
    assert retrieval.snapshot_expectations(manifest, "mendeley_shi_dataset_v1__data_in_brief.csv") == ("frozen-digest", 12345)


def test_remaining_lease_parser_does_not_turn_unknown_text_into_zero():
    result = _remaining_lease_months(pd.Series(["95 years", "94 years 10 months", "8 months", "unknown", "96 years 13 months", ""]))
    assert result.iloc[0] == 1140
    assert result.iloc[1] == 1138
    assert result.iloc[2] == 8
    assert result.iloc[3:].isna().all()


def test_rental_model_prep_excludes_nonfinite_coordinates_and_keeps_source_rows():
    linked = pd.DataFrame({
        "building_id": ["b1", "b2", "b3"],
        "date": pd.to_datetime(["2024-01-01"] * 3),
        "year_completed": [2000] * 3,
        "shi": [3.0] * 3,
        "shi_status": ["valid"] * 3,
        "link_status": ["matched_unique"] * 3,
        "flat_type_clean": ["3 ROOM"] * 3,
        "outcome_numeric": [1000.0, 1100.0, 1200.0],
        "source_record_id": [1, 2, 3],
    })
    coordinates = pd.DataFrame({
        "building_id": ["b1", "b2", "b3"],
        "one_map_status": ["exact_onemap_address"] * 3,
        "x_svy21": ["30000", "inf", "bad"],
        "y_svy21": ["32000", "32000", "32000"],
    })
    prepared = prepare_rental(linked, coordinates)
    assert prepared.source_record_id.tolist() == [1]


def test_building_and_postal_alias_rows_stay_in_same_grouped_fold():
    rows = []
    for building in range(15):
        for alias in range(2):
            rows.append({"building_id": f"b{building}", "source_address_key": f"alias-{alias}", "record": f"{building}-{alias}"})
    data = pd.DataFrame(rows)
    row_fold = {}
    for fold, (_, test) in enumerate(grouped_folds(data, seed=47, n_splits=5)):
        row_fold.update({int(row): fold for row in test})
    assert len(row_fold) == len(data)
    for _, group in data.groupby("building_id"):
        assert len(group) == 2
        assert len({row_fold[int(index)] for index in group.index}) == 1


def test_output_generation_writes_matching_csv_and_json(tmp_path, monkeypatch):
    monkeypatch.setattr(descriptive_export, "OUT", tmp_path)
    source = pd.DataFrame({"building_id": ["b1"], "shi": [3.5], "median_rent_sgd": [1200.0]})
    descriptive_export._save_table(source, "test_output")
    csv_result = pd.read_csv(tmp_path / "test_output__2024-2025.csv")
    json_result = pd.read_json(tmp_path / "test_output__2024-2025.json")
    pd.testing.assert_frame_equal(csv_result, json_result, check_dtype=False)
    assert csv_result.isna().sum().sum() == 0



def test_onemap_error_payload_is_not_successful_authenticated_lookup():
    session = _Session({1: {"error": "Authentication token missing", "totalNumPages": 1, "results": [{"POSTAL": "123456"}]}})
    with pytest.raises(PermissionError, match="API error"):
        onemap.search_candidates(session, "ADDRESS", "unit-test-token")
