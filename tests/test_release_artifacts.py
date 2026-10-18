from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"


def test_release_datasets_preserve_building_coverage_and_explicit_unmatched():
    buildings = pd.read_csv(TABLES / "building_level_shi__release__current_2026-10-08.csv", dtype={"blk_no": str})
    crosswalk = pd.read_csv(TABLES / "postal_crosswalk__release__mendeley_v1.csv", dtype=str, keep_default_na=False)
    assert len(buildings) == 10_817
    assert buildings["building_id"].is_unique
    assert buildings["shi"].notna().all()
    manifest = json.loads((ROOT / "data/raw/source_manifests/hdb_property_information__2026-10-08.json").read_text())
    assert buildings["source_retrieval_date"].eq(manifest["retrieved_at_sgt"].split("T")[0]).all()
    assert crosswalk["historical_match_status"].eq("unmatched_address").sum() == 1_219
    codes = crosswalk.loc[crosswalk["historical_postal_code"].ne(""), "historical_postal_code"]
    assert codes.str.fullmatch(r"\d{6}").all()
    assert codes.str.startswith("0").sum() >= 1  # text codes preserve legitimate/restored leading zeroes
    groups = pd.read_csv(TABLES / 'coverage_by_housing_group__2026-10-17.csv')
    for _, group in groups.groupby('dimension'):
        assert group['buildings'].sum() == len(buildings)
        assert group['recorded_dwelling_units'].sum() == buildings['total_dwelling_units'].sum()


def test_release_analysis_records_keep_unique_traceable_source_ids():
    for filename, expected in [
        ("rental_analysis_records__release__2024-2025.csv", 75_607),
        ("resale_analysis_records__release__2024-2025.csv", 52_916),
    ]:
        data = pd.read_csv(TABLES / filename)
        assert len(data) == expected
        assert data["source_record_id"].is_unique
        assert data["building_id"].notna().all()


def test_evidence_map_csv_is_parseable_and_screening_limits_are_explicit():
    evidence = pd.read_csv(ROOT / "outputs/literature/evidence_map.csv")
    assert len(evidence) == 39
    assert evidence["record_id"].is_unique
    assert evidence["classification"].notna().all()
    assert evidence["full_citation"].notna().all()
    assert evidence["study_objective_and_design"].notna().all()
    assert evidence["evidence_location"].notna().all()
    candidates = pd.read_csv(ROOT / "outputs/literature/forward_citation_candidates__openalex_2026-10-16.csv")
    assert len(candidates) == 36
    assert candidates["screening_status"].notna().all()
    assert evidence["screening_category"].notna().all()
    uncertain = evidence["screening_category"].eq("uncertain_fulltext")
    assert evidence.loc[uncertain, "classification"].eq("Uncertain; full text not assessed").all()
    direct = evidence["screening_category"].eq("direct_shi_application")
    assert evidence.loc[direct, "fulltext_snapshot"].notna().all()


def test_completed_review_case_ids_are_not_reassigned_after_reconstruction():
    options = [ROOT.parent / "Validation/Address_Review/backend/HDB_Visual_Audit_Backend.csv",
               ROOT / "validation_cases/backend/HDB_Visual_Audit_Backend.csv"]
    backend = next(p for p in options if p.is_file())
    frozen = pd.read_csv(backend).set_index("case_id").building_id.sort_index()
    generated = pd.read_csv(TABLES / "address_review_proposed_match_key__30.csv").set_index("case_id").building_id.sort_index()
    assert frozen.equals(generated)
