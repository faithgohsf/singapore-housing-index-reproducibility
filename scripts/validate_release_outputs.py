"""Validate prepared, machine-readable release artifacts and write a report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "outputs" / "tables"
L = ROOT / "outputs" / "literature"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-review-workbooks", action="store_true", help="Repository profile: machine-readable analyses only; internal review workbooks are not distributed.")
    args = parser.parse_args(argv)
    checks: list[dict[str, object]] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    buildings = pd.read_csv(T / "building_level_shi__release__current_2026-10-08.csv", dtype={"blk_no": str})
    postal = pd.read_csv(T / "postal_crosswalk__release__mendeley_v1.csv", dtype=str, keep_default_na=False)
    check("building rows and unique identifiers", len(buildings) == 10817 and buildings.building_id.nunique() == 10817, f"{len(buildings)} rows; {buildings.building_id.nunique()} IDs")
    check("valid SHI scores complete", int(buildings.composition_complete.sum()) == 10817 and buildings.shi.notna().all(), f"{int(buildings.composition_complete.sum())} complete scores")
    check("unmatched historical buildings retained", int(postal.historical_match_status.eq("unmatched_address").sum()) == 1219, f"{len(postal)} rows; 1,219 explicit unmatched records")
    codes = postal.loc[postal.historical_postal_code.ne(""), "historical_postal_code"]
    check("postal codes remain six-digit text including leading zero", bool(codes.str.fullmatch(r"\d{6}").all()) and int(codes.str.startswith("0").sum()) == 94, f"{len(codes)} codes; {int(codes.str.startswith('0').sum())} start with zero")
    for filename, expected in [("rental_analysis_records__release__2024-2025.csv", 75607), ("resale_analysis_records__release__2024-2025.csv", 52916)]:
        data = pd.read_csv(T / filename)
        check(f"{filename} IDs traceable and unique", len(data) == expected and data.source_record_id.is_unique and data.building_id.notna().all(), f"{len(data)} rows; {data.source_record_id.nunique()} unique source IDs")
    review = pd.read_csv(T / "address_review_blinded_case_packet__30.csv", dtype=str, keep_default_na=False)
    check("30 address cases remain blinded", len(review) == 30 and review.case_id.is_unique and not {"shi", "historical_shi", "building_id"}.intersection(review.columns), f"{len(review)} unique cases; no proposed scores/building IDs")
    dictionary = pd.read_csv(T / "data_dictionary__release.csv")
    columns = set(buildings.columns) | set(postal.columns)
    for filename in ["rental_analysis_records__release__2024-2025.csv", "resale_analysis_records__release__2024-2025.csv"]:
        columns.update(pd.read_csv(T / filename, nrows=0).columns)
    check("dictionary covers all prepared columns", columns <= set(dictionary.column), f"{len(columns)} columns; {len(columns - set(dictionary.column))} undocumented")
    desc = json.loads((T / "descriptive_analysis_validation__2024-2025.json").read_text())
    reconciled = all(desc[k][q] for k in ("rental", "resale") for q in ("source_ids_unique", "all_source_ids_represented_exactly_once", "record_count_reconciles")) and all(desc[k]["building_output_missing_cells"] == 0 for k in ("rental", "resale"))
    check("descriptive source IDs reconcile and aggregates have no missing cells", reconciled, "rental and resale both pass pipeline reconciliation")
    evidence = pd.read_csv(L / "evidence_map.csv")
    candidates = pd.read_csv(L / "forward_citation_candidates__openalex_2026-10-16.csv")
    literature_ok = len(evidence) == 39 and evidence.record_id.is_unique and evidence.full_citation.notna().all() and evidence.screening_category.notna().all() and len(candidates) == 36 and candidates.screening_status.notna().all()
    check("literature map parses with screening limits recorded", literature_ok, f"{len(evidence)} catalog records; {len(candidates)} citing records; classifications and screening depth retained")
    books = [T / "SHI_Reconstructed_Building_Dataset.xlsx", T / "SHI_Release_Documentation__2026-10-17.xlsx", ROOT / "../Validation/Address_Review/HDB_Visual_Audit.xlsx", L / "SHI_Literature_Evidence_Map__2026-10-17.xlsx"]
    books_ok = all(p.is_file() and p.stat().st_size > 0 for p in books)
    if not args.skip_review_workbooks:
        check("expected workbooks exist and are nonempty", books_ok, "; ".join(f"{p.name}: {p.stat().st_size if p.exists() else 0} bytes" for p in books))
    report = {"run_date_local": "2026-10-17", "scope": "machine-readable repository outputs" if args.skip_review_workbooks else "workspace including review workbooks", "passed": sum(bool(c["passed"]) for c in checks), "total": len(checks), "checks": checks}
    out = T / "release_integrity_checks__2026-10-17.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for item in checks:
        print(("PASS" if item["passed"] else "FAIL"), item["check"], "—", item["detail"])
    print(f"Release checks: {report['passed']}/{report['total']}; report saved to {out.relative_to(ROOT)}")
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
