"""Link current public rental/resale sources and report eligibility/coverage only."""
from __future__ import annotations

import json
import pathlib
import sys

import pandas as pd

PROJECT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from shi.economic import add_flat_type_composition_flags, eligibility_summary, link_economic_records  # noqa: E402


def main() -> None:
    raw, out = PROJECT / "data" / "raw", PROJECT / "outputs" / "tables"
    out.mkdir(parents=True, exist_ok=True)
    buildings = pd.read_csv(out / "hdb_buildings__current_2026-10-08.csv", dtype={"blk_no": "string"})
    buildings["year_completed"] = pd.to_numeric(buildings["year_completed"], errors="coerce")
    rental = pd.read_csv(raw / "hdb_rental_approval__retrieved_2026-10-16.csv", dtype={"block": "string", "street_name": "string"})
    resale = pd.read_csv(raw / "hdb_resale_flat_prices__retrieved_2026-10-16.csv", dtype={"block": "string", "street_name": "string"})
    rental_linked = link_economic_records(rental, buildings, date_col="rent_approval_date", block_col="block", street_col="street_name", outcome_col="monthly_rent", type_col="flat_type")
    resale_linked = link_economic_records(resale, buildings, date_col="month", block_col="block", street_col="street_name", outcome_col="resale_price", type_col="flat_type")
    rental_linked = add_flat_type_composition_flags(rental_linked, buildings)
    resale_linked = add_flat_type_composition_flags(resale_linked, buildings)
    rental_start, rental_end = pd.Timestamp("2024-01-01"), pd.Timestamp("2026-01-01")
    rental_eligible = rental_linked.loc[
        rental_linked["date"].ge(rental_start) & rental_linked["date"].lt(rental_end)
        & rental_linked["outcome_numeric"].gt(0)
        & rental_linked["link_status"].eq("matched_unique")
        & rental_linked["shi_status"].eq("valid")
    ].copy()
    resale_eligible = resale_linked.loc[
        resale_linked["date"].ge(rental_start) & resale_linked["date"].lt(rental_end)
        & resale_linked["outcome_numeric"].gt(0)
        & resale_linked["link_status"].eq("matched_unique")
        & resale_linked["shi_status"].eq("valid")
    ].copy()
    rental_linked.to_csv(out / "rental_source_accounting__retrieved_2026-10-16.csv", index=False)
    resale_linked.to_csv(out / "resale_source_accounting__retrieved_2026-10-16.csv", index=False)
    rental_eligible.to_csv(out / "rental_eligible_linked__2024-2025.csv", index=False)
    resale_eligible.to_csv(out / "resale_eligible_linked__2024-2025.csv", index=False)
    summary = {
        "source_vintage": "Data.gov.sg datasets retrieved 2026-10-16; manifests and checksums under data/raw/source_manifests",
        "rental": eligibility_summary(rental_linked),
        "resale": eligibility_summary(resale_linked),
        "rental_eligible_unique_buildings": int(rental_eligible["building_id"].nunique()),
        "resale_eligible_unique_buildings": int(resale_eligible["building_id"].nunique()),
        "rental_unmapped_flat_type_rows_in_window": int((rental_linked["date"].ge(rental_start) & rental_linked["date"].lt(rental_end) & rental_linked["flat_type_mapping_status"].eq("unmapped_source_category")).sum()),
        "rental_flat_type_absent_from_composition_rows_in_window": int((rental_linked["date"].ge(rental_start) & rental_linked["date"].lt(rental_end) & rental_linked["flat_type_absent_from_composition"]).sum()),
        "resale_unmapped_flat_type_rows_in_window": int((resale_linked["date"].ge(rental_start) & resale_linked["date"].lt(rental_end) & resale_linked["flat_type_mapping_status"].eq("unmapped_source_category")).sum()),
        "resale_flat_type_absent_from_composition_rows_in_window": int((resale_linked["date"].ge(rental_start) & resale_linked["date"].lt(rental_end) & resale_linked["flat_type_absent_from_composition"]).sum()),
        "analysis_models_run": False,
        "model_blocker": "Models are not run in this coverage stage. The next pipeline stage uses only exact, unique, finite OneMap coordinates for coordinate-dependent analyses.",
    }
    (out / "economic_coverage_summary__2024-2025.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
