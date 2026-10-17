"""Create audit-ready release tables and address-review packets from pipeline outputs.

Does not alter pipeline source data or model outputs. Outputs are deterministic.
"""
from __future__ import annotations

import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "outputs" / "tables"
L = ROOT / "outputs" / "literature"


def write_csv(df: pd.DataFrame, name: str) -> None:
    df.to_csv(T / name, index=False, encoding="utf-8")


def main() -> None:
    L.mkdir(parents=True, exist_ok=True)
    buildings = pd.read_csv(T / "hdb_buildings__current_2026-10-08.csv", dtype={"blk_no": str})
    coords = pd.read_csv(T / "one_map_coordinates__2026-10-16.csv", dtype={"postal_code": str})
    buildings = buildings.merge(coords, on=["building_id", "address_key"], how="left", validate="one_to_one")
    buildings["housing_stock_scope"] = "HDB residential buildings in public HDB Property Information snapshot"
    buildings["shi_unit"] = "building"
    buildings["shi_interpretation"] = "housing-composition marker; not individual income or deprivation"
    buildings["source_version"] = "data.gov.sg HDB Property Information updated 2026-10-08"
    property_manifest = json.loads((ROOT / "data/raw/source_manifests/hdb_property_information__2026-10-08.json").read_text())
    buildings["source_retrieval_date"] = property_manifest["retrieved_at_sgt"].split("T", 1)[0]
    buildings["composition_complete"] = buildings["shi_status"].eq("valid")
    buildings["coordinate_linkage_flag"] = buildings["one_map_status"].fillna("not available")
    buildings["coordinate_linkage_candidates"] = buildings["exact_candidate_count"]
    write_csv(buildings, "building_level_shi__release__current_2026-10-08.csv")

    cross = pd.read_csv(T / "postal_crosswalk__mendeley_v1.csv", dtype={"historical_postal_code_raw": str, "historical_postal_code": str})
    cross["mapping_scope"] = "historical candidate Mendeley Data v1; postal rows mapped to current HDB building address keys"
    cross["comparator_status"] = "candidate only; not verified as original 2018 comparator"
    status = pd.read_csv(T / "historical_match_status__mendeley_v1.csv", dtype={"historical_postal_codes": str})
    unmatched = status[status["historical_match_status"].eq("unmatched_address")].merge(
        buildings[["building_id", "blk_no", "street"]], on="building_id", how="left", validate="one_to_one"
    )
    unmatched_rows = pd.DataFrame({
        "building_id": unmatched["building_id"], "address_key": unmatched["address_key"],
        "block_no": unmatched["blk_no"], "street": unmatched["street"],
        "historical_postal_code_raw": "", "historical_postal_code": "",
        "postal_normalization_status": "not_applicable_unmatched", "historical_shi": pd.NA,
        "historical_address_key": "", "postal_status": "unmatched_address",
        "historical_match_status": "unmatched_address",
        "mapping_scope": "no address edge in Mendeley v1 candidate; retained explicitly",
        "comparator_status": "candidate only; not verified as original 2018 comparator",
    })
    cross = pd.concat([cross, unmatched_rows], ignore_index=True)
    write_csv(cross, "postal_crosswalk__release__mendeley_v1.csv")

    rental = pd.read_csv(T / "rental_eligible_linked__2024-2025.csv", dtype={"block": str})
    resale = pd.read_csv(T / "resale_eligible_linked__2024-2025.csv", dtype={"block": str})
    rental["analysis_period"] = "2024-01-01 through 2025-12-31"
    resale["analysis_period"] = "2024-01-01 through 2025-12-31"
    rental["eligibility_note"] = "source record; coordinate/model complete-case eligibility is reported separately"
    resale["eligibility_note"] = "source record; coordinate/model complete-case eligibility is reported separately"
    write_csv(rental, "rental_analysis_records__release__2024-2025.csv")
    write_csv(resale, "resale_analysis_records__release__2024-2025.csv")

    dictionary = [
        ("building_id", "Stable project-generated identifier for a canonical HDB building address", "text", "one building", "Not a national administrative identifier"),
        ("address_key", "Canonicalized block and street address used for joins", "text", "building", "Normalization described in src/shi/reconstruction.py", "May merge aliases only where canonicalization is supported"),
        ("shi", "Weighted mean room-count composition score from recorded sold and rental dwelling counts", "score", "building", "See shi_formula and original Lim et al. method", "Not individual SES, income or deprivation"),
        ("shi_status", "Whether the available dwelling composition supports a valid SHI score", "category", "building", "valid/invalid status from reconstruction", "Incomplete composition is not a valid SHI"),
        ("composition_count_sum", "Sum of observed room-category composition counts", "count", "building", "Sum of source composition categories", "Do not infer composition from transactions"),
        ("shi_numerator", "Weighted sum used in SHI calculation", "weighted count", "building", "Room-category weights multiplied by corresponding counts", "Interpret only with complete composition"),
        ("one_map_status", "OneMap exact-address candidate status", "category", "building", "Saved coordinate crosswalk 2026-10-16", "Ambiguous and no-match retained; no first-result selection"),
        ("postal_code", "Postal code returned for a uniquely resolved exact OneMap address", "text", "building/address candidate", "OneMap response", "Blank for unresolved/multiple candidates; leading zeros preserved"),
        ("latitude", "Latitude from the uniquely resolved exact OneMap address", "decimal degrees", "building", "OneMap response", "Not assigned for ambiguous candidate matches"),
        ("source_record_id", "Row identifier in the underlying public rental/resale file", "text/integer", "transaction/record", "Source record ordering identifier used by pipeline", "Not a dwelling or tenancy identifier"),
        ("monthly_rent", "Owner-declared HDB rental transaction monthly rent", "SGD/month", "rental record", "HDB rental source", "No floor area, storey, unit identifier, or tenancy-start date"),
        ("resale_price", "Recorded HDB resale transaction price", "SGD", "resale record", "HDB resale source", "Transaction outcome; not household income"),
        ("flat_type_absent_from_composition", "Flag that transaction flat type is absent from recorded building composition categories", "boolean", "transaction", "Comparison of source flat type and composition", "Review flag; does not justify revising composition"),
    ]
    dictdf = pd.DataFrame(dictionary, columns=["column", "definition", "unit_or_type", "unit_of_analysis", "derivation", "limitation"])
    definitions = {
        "blk_no":"HDB block/building number as recorded in source.","street":"HDB street name as recorded in source.","max_floor_lvl":"Recorded maximum floor level of the block.","year_completed":"Recorded building completion year.","residential":"Source indicator for residential use.","commercial":"Source indicator for commercial use.","market_hawker":"Source indicator for market/hawker use.","miscellaneous":"Source indicator for miscellaneous use.","multistorey_carpark":"Source indicator for multistorey carpark use.","precinct_pavilion":"Source indicator for precinct pavilion use.","bldg_contract_town":"Source town/contract-town field.","total_dwelling_units":"Source-reported total dwelling units.",
        "1room_sold":"Count of sold one-room dwellings in recorded building composition.","2room_sold":"Count of sold two-room dwellings in recorded building composition.","3room_sold":"Count of sold three-room dwellings in recorded building composition.","4room_sold":"Count of sold four-room dwellings in recorded building composition.","5room_sold":"Count of sold five-room dwellings in recorded building composition.","exec_sold":"Count of executive dwellings in recorded building composition.","multigen_sold":"Count of multigeneration dwellings in recorded building composition.","studio_apartment_sold":"Count of studio apartments in recorded building composition.","1room_rental":"Count of one-room rental dwellings in recorded building composition.","2room_rental":"Count of two-room rental dwellings in recorded building composition.","3room_rental":"Count of three-room rental dwellings in recorded building composition.","other_room_rental":"Count of other-room rental dwellings in recorded building composition.",
        "source_row_number":"Row number in the current HDB property-information source.","source_record_count":"Number of source rows combined into this building record.","source_row_numbers":"Source row numbers contributing to this building record.","canonical_address_collision":"Flag for distinct source addresses that collapsed to the same canonical key.","source_conflict_fields":"Source fields with conflicting values among records for a building.","source_record_status":"Building source-row reconciliation status.","shi_formula":"Formula version used for this score.","shi_numerator":"Weighted sum in the SHI calculation.","shi_invalid_reason":"Reason a composition was not assigned a valid SHI, if applicable.","composition_count_sum":"Sum of room-category counts included in the composition denominator.",
        "historical_postal_code_raw":"Postal code string exactly as represented in the historical candidate before normalization.","historical_postal_code":"Six-character historical candidate postal code after only restoring a leading zero to five-digit numeric values.","postal_normalization_status":"Whether code was valid six digits or had a leading zero restored.","historical_address_key":"Canonicalized historical block/street address used for candidate linkage.","historical_match_status":"Building-level historical candidate linkage status.","postal_status":"Whether a historical postal code maps to one address or is ambiguous.","historical_postal_count":"Number of unique historical postal codes linked to a current building.","historical_score_count":"Number of distinct historical scores linked to a current building.","postal_ambiguity":"Whether any linked postal code is ambiguous across addresses.","historical_postal_codes":"Semicolon-separated distinct historical postal codes for that building.","historical_shi":"Historical candidate housing-index score.","one_map_status":"Exact-address result status in supplied OneMap crosswalk.","candidate_count":"Number of OneMap search candidates recorded.","exact_candidate_count":"Number of candidates matching the normalized full building address exactly.","one_map_address":"Resolved OneMap result address; blank if unresolved or ambiguous.","postal_code":"Postal code as text from the unique exact OneMap result, where available.","x_svy21":"SVY21 easting from unique exact OneMap result.","y_svy21":"SVY21 northing from unique exact OneMap result.","latitude":"Latitude from unique exact OneMap result.","longitude":"Longitude from unique exact OneMap result.",
        "rent_approval_date":"HDB rental approval month as provided by source.","town":"HDB town as provided by transaction source.","block":"Transaction-record block number.","street_name":"Transaction-record street name.","flat_type":"Transaction-record flat type as supplied by HDB.","monthly_rent":"Owner-declared monthly rent in SGD for an approved rental record.","source_record_id":"Stable row identifier assigned from source-file record order by this project.","source_address_key":"Canonicalized transaction block/street address before building linkage.","date":"Parsed transaction/approval month represented as the first calendar day of the month.","outcome_numeric":"Numeric rent or resale-price outcome used in analysis.","flat_type_clean":"Normalized flat-type category for analysis.","year_completed":"Source completion year joined from building property record.","total_dwelling_units":"Source building dwelling count joined from HDB property record.","link_status":"Address linkage outcome for transaction record.","flat_type_mapping_status":"Status of mapping supplied flat type to building composition category.","flat_type_absent_from_composition":"Flag that transaction flat-type category is absent from composition counts; not a reason to infer or revise composition.","analysis_period":"Analysis-window label applied to linked source record.","eligibility_note":"Explanation that coordinate/model eligibility is reported separately.",
        "month":"Resale transaction month as supplied by HDB.","storey_range":"Resale transaction storey range as supplied by HDB.","floor_area_sqm":"Recorded resale floor area in square metres.","flat_model":"Resale flat model as supplied by HDB.","lease_commence_date":"Recorded lease commencement year/date field from resale source.","remaining_lease":"Remaining lease as supplied by resale source.","resale_price":"Recorded resale transaction price in SGD.",
    }
    known = set(dictdf["column"])
    all_cols = []
    for filename in ["building_level_shi__release__current_2026-10-08.csv", "postal_crosswalk__release__mendeley_v1.csv", "rental_analysis_records__release__2024-2025.csv", "resale_analysis_records__release__2024-2025.csv"]:
        all_cols.extend(pd.read_csv(T / filename, nrows=0).columns.tolist())
    rows = []
    for col in dict.fromkeys(all_cols):
        if col in known: continue
        meaning = definitions.get(col, f"Source or derived field `{col}` retained in the prepared dataset; see the named source file and its source manifest.")
        rows.append((col, meaning, "source-defined or categorical", "varies by dataset", "Retained from source or documented pipeline transformation", "See source manifest; do not interpret beyond source definition."))
    if rows:
        dictdf = pd.concat([dictdf, pd.DataFrame(rows, columns=dictdf.columns)], ignore_index=True)
    dictdf.to_csv(T / "data_dictionary__release.csv", index=False)

    manifests = [
        {"source": "HDB Property Information", "source_url": "https://data.gov.sg/datasets/d_17f5382f26140b1fdae0ba2ef6239d2f/view", "vintage": "Last updated 2026-10-08; source coverage through 2025-12-31", "retrieved": "2026-10-16 Singapore time", "local_file": "data/raw/hdb_property_information__2026-10-08.csv", "sha256": "d528ea2d6fc3f57ab4c8199ed15ea5eaac0109fe659e09ef91910dfe417af2eb", "license_or_access": "Singapore Open Data Licence; retain upstream redistribution conditions", "limitations": "Current public snapshot; not the frozen HDB source used by the 2021 paper."},
        {"source": "HDB Rental Contracts Approved", "source_url": "https://data.gov.sg/datasets/d_c9f57187485a850908655db0e8cfe651/view", "vintage": "Retrieved 2026-10-16", "retrieved": "2026-10-16 Singapore time", "local_file": "data/raw/hdb_rental_approval__retrieved_2026-10-16.csv", "sha256": "767a94819f4bb96bc4cff411064bedf6bef63ed053c05de1e2b560b65d85b1c9", "license_or_access": "Public source; verify field-specific licence terms before redistribution", "limitations": "Owner-declared approved rent; no unit ID, floor area, storey, or tenancy-start date."},
        {"source": "HDB Resale Flat Prices", "source_url": "https://data.gov.sg/datasets/d_8b84c4ee58e3cfc0ece0d773c8ca6abc/view", "vintage": "Retrieved 2026-10-16", "retrieved": "2026-10-16 Singapore time", "local_file": "data/raw/hdb_resale_flat_prices__retrieved_2026-10-16.csv", "sha256": "248694f3cf7cc07e7e166b8eab3c5ebe3b18c39f76156282a6f618137fa49dc8", "license_or_access": "Public source; retain source attribution", "limitations": "Transaction data describe observed resale records, not household income."},
        {"source": "Mendeley SHI dataset v1", "source_url": "https://data.mendeley.com/datasets/pj3dkvskr9/1", "vintage": "Version 1; file timestamp 2021-03-23; DOI 10.17632/pj3dkvskr9.1", "retrieved": "2026-10-16 Singapore time", "local_file": "data/raw/mendeley_shi_dataset_v1__data_in_brief.csv", "sha256": "afd2999803e4677629aa34844162160a441f54c0acc5baf72ec37a23bc2ff1d9", "license_or_access": "See Mendeley dataset record", "limitations": "Historical candidate only; equivalence to original 2018 comparator unresolved."},
        {"source": "OneMap coordinate crosswalk", "source_url": "https://www.onemap.gov.sg/apidocs/search", "vintage": "User-provided coordinates dated 2026-10-16", "retrieved": "Validated 2026-10-16", "local_file": "outputs/tables/one_map_coordinates__2026-10-16.csv", "sha256": "fa7064a4b078165c7c4a1a5aabeaa14f89c9e4c0ec68ba752661ead9d1a741dd", "license_or_access": "OneMap API terms; coordinate snapshot includes no credential", "limitations": "8,779 unique exact coordinates; 1,579 ambiguous and 459 unmatched buildings retained unresolved."},
        {"source": "HDB rental and resale analysis windows", "source_url": "see rental and resale source rows above", "vintage": "2024-01-01 inclusive to 2026-01-01 exclusive", "retrieved": "Derived from saved HDB records retrieved 2026-10-16", "local_file": "outputs/tables/rental_analysis_records__release__2024-2025.csv; outputs/tables/resale_analysis_records__release__2024-2025.csv", "sha256": "generated from these exact released files", "license_or_access": "Upstream terms apply", "limitations": "Source row ID supports traceability; is not a dwelling or tenancy identifier."},
    ]
    pd.DataFrame(manifests).to_csv(T / "source_manifest__release.csv", index=False)

    stage = json.loads((T / "reconstruction_stage_summary.json").read_text())
    econ = json.loads((T / "economic_model_results__2024-2025.json").read_text())
    cov = json.loads((T / "economic_coverage_summary__2024-2025.json").read_text())
    coverage = {
        "notebook_saved_source_rows": stage["notebook_saved_counts"]["source_rows"],
        "notebook_post_filter_rows_not_unique_buildings": stage["notebook_saved_counts"]["residential_filter_rows"],
        "published_paper_unique_residential_building_benchmark": stage["published_2021_paper_benchmark"]["unique_residential_buildings"],
        "current_source_rows": stage["current_source_counts"]["source_rows"],
        "current_residential_buildings": stage["current_source_counts"]["residential_buildings"],
        "current_valid_shi_buildings": stage["current_source_counts"]["composition_valid_scores"],
        "historical_candidate": stage["historical_candidate"],
        "historical_candidate_paired_buildings": stage["historical_comparison"]["paired_buildings"],
        "historical_candidate_unmatched_buildings": stage["historical_comparison"]["historical_unmatched_buildings"],
        "rental_source_records_in_window": cov.get("rental", {}).get("in_window"),
        "rental_unique_linked_buildings": cov.get("rental_eligible_unique_buildings"),
        "rental_model_complete_case_records": econ["rental"]["rows"],
        "rental_model_complete_case_buildings": econ["rental"]["buildings"],
        "resale_source_records_in_window": cov.get("resale", {}).get("in_window"),
        "resale_unique_linked_buildings": cov.get("resale_eligible_unique_buildings"),
        "resale_model_complete_case_records": econ["resale_baseline"]["rows"],
        "resale_model_complete_case_buildings": econ["resale_baseline"]["buildings"],
        "coordinate_unique_exact_buildings": econ["coordinate_linkage"]["exact_unique_address_coordinates"],
        "coordinate_ambiguous_buildings": econ["coordinate_linkage"]["ambiguous_exact_candidate_buildings"],
        "coordinate_unmatched_buildings": econ["coordinate_linkage"]["no_exact_candidate_buildings"],
        "interpretation": "Building and transaction coverage only; not resident coverage or individual socioeconomic measurement.",
    }
    (T / "coverage_report__release.json").write_text(json.dumps(coverage, indent=2) + "\n")
    pd.DataFrame([{"stage": k, "value": v} for k, v in coverage.items()]).to_csv(T / "coverage_report__release.csv", index=False)

    # Prepared up to 30 independent-review cases: all 9 composition/transaction flags,
    # all historical score conflicts, then largest absolute historical differences.
    hist = pd.read_csv(T / "historical_comparison_buildings__mendeley_v1.csv", dtype={"blk_no": str})
    address = hist[["building_id", "address_key", "blk_no", "street", "shi", "historical_shi", "difference_current_minus_historical", "historical_match_status", "postal_ambiguity", "historical_postal_codes", "paired_for_agreement"]].copy()
    flags = rental.loc[rental["flat_type_absent_from_composition"].eq(True), ["building_id", "source_address_key", "flat_type", "source_record_id"]].drop_duplicates("building_id")
    flags["source_record_id"] = pd.to_numeric(flags["source_record_id"], errors="raise").astype("Int64").astype("string")
    picks: list[tuple[str, str]] = []
    picks.extend((x, "transaction flat type absent from recorded building composition") for x in flags["building_id"].tolist())
    sold_cols = ["1room_sold","2room_sold","3room_sold","4room_sold","5room_sold","exec_sold","multigen_sold","studio_apartment_sold"]
    rental_cols = ["1room_rental","2room_rental","3room_rental","other_room_rental"]
    rental_only_observed = buildings.loc[buildings[sold_cols].sum(axis=1).eq(0) & buildings[rental_cols].sum(axis=1).gt(0) & buildings.building_id.isin(rental.building_id), "building_id"]
    for x in rental_only_observed:
        if x not in {y for y, _ in picks}: picks.append((x, "rental-category-only building composition with an observed rental approval; verify source identity and coverage"))
    conflicts = hist[hist["historical_match_status"].astype(str).str.contains("conflict|multiple", case=False, na=False)]
    for x in conflicts["building_id"].tolist():
        if x not in {y for y, _ in picks}: picks.append((x, "historical postal/address candidate has conflicting score or multiple codes"))
    diffs = hist[hist["paired_for_agreement"].eq(True)].assign(_abs=lambda x: x["difference_current_minus_historical"].abs()).sort_values(["_abs", "building_id"], ascending=[False, True])
    for x in diffs["building_id"].tolist():
        if len(picks) >= 30: break
        if x not in {y for y, _ in picks}: picks.append((x, "largest absolute difference in historical candidate comparison; purposive review"))
    picks = picks[:30]
    selected = pd.DataFrame(picks, columns=["building_id", "review_reason"])
    selected = selected.merge(address, on="building_id", how="left", validate="one_to_one")
    selected = selected.merge(flags, on="building_id", how="left", validate="one_to_one")
    composition_cols = ["1room_sold", "2room_sold", "3room_sold", "4room_sold", "5room_sold", "exec_sold", "multigen_sold", "studio_apartment_sold", "1room_rental", "2room_rental", "3room_rental", "other_room_rental"]
    hdb_fields = buildings[["building_id", "residential", "year_completed", "total_dwelling_units", *composition_cols]].copy()
    def composition_summary(row: pd.Series) -> str:
        return "; ".join(f"{col}={int(row[col])}" for col in composition_cols if pd.notna(row[col]) and float(row[col]) != 0)
    hdb_fields["hdb_recorded_composition_summary"] = hdb_fields.apply(composition_summary, axis=1)
    hdb_fields = hdb_fields.rename(columns={"residential": "hdb_source_residential_flag", "year_completed": "hdb_source_year_completed", "total_dwelling_units": "hdb_source_total_dwelling_units"})
    selected = selected.merge(hdb_fields[["building_id", "hdb_source_residential_flag", "hdb_source_year_completed", "hdb_source_total_dwelling_units", "hdb_recorded_composition_summary"]], on="building_id", how="left", validate="one_to_one")
    selected = selected.merge(coords[["building_id", "one_map_status", "candidate_count", "postal_code", "latitude", "longitude"]], on="building_id", how="left", validate="one_to_one")
    selected["case_id"] = [f"SHI-REV-{i:03d}" for i in range(1, len(selected)+1)]
    selected["google_maps_search_url"] = selected.apply(lambda r: "https://www.google.com/maps/search/?api=1&query=" + str(r["blk_no"]) + "%20" + str(r["street"]).replace(" ", "%20") if pd.notna(r["blk_no"]) and pd.notna(r["street"]) else "", axis=1)
    selected["review_status"] = "not reviewed; human classification required"
    proposed_cols = ["case_id", "building_id", "address_key", "blk_no", "street", "review_reason", "shi", "historical_shi", "difference_current_minus_historical", "historical_match_status", "historical_postal_codes", "flat_type", "source_record_id", "hdb_source_residential_flag", "hdb_source_year_completed", "hdb_source_total_dwelling_units", "hdb_recorded_composition_summary", "one_map_status", "candidate_count", "postal_code", "latitude", "longitude", "google_maps_search_url"]
    selected[proposed_cols].to_csv(T / "address_review_proposed_match_key__30.csv", index=False)
    blind = selected[["case_id", "blk_no", "street", "review_reason", "flat_type", "source_record_id", "hdb_source_residential_flag", "hdb_source_year_completed", "hdb_source_total_dwelling_units", "hdb_recorded_composition_summary", "google_maps_search_url"]].copy()
    source_rows = buildings.set_index("building_id")["source_row_number"]
    blind["official_evidence_reference"] = [
        "https://data.gov.sg/datasets/d_17f5382f26140b1fdae0ba2ef6239d2f/view; "
        "data/raw/hdb_property_information__2026-10-08.csv; data row "
        + str(int(source_rows.loc[building_id]))
        for building_id in selected["building_id"]
    ]
    blind["reviewer_classification"] = ""
    blind["reviewer_confidence"] = ""
    blind["reviewer_evidence_or_source"] = ""
    blind["reviewer_id"] = ""
    blind["review_date"] = ""
    blind["review_notes"] = ""
    blind["status"] = "awaiting single human reviewer"
    blind.to_csv(T / "address_review_blinded_case_packet__30.csv", index=False)
    case_dir = ROOT / "outputs/address_review/backend/Preparation_Records/cases"
    case_dir.mkdir(parents=True, exist_ok=True)
    for _, case in blind.fillna("").iterrows():
        packet = f"""# {case['case_id']} Address review case

Status: technical preparation record, not the reviewer form. Actual recorded responses are stored separately in the completed HDB visual audit.

Source address: {case['blk_no']} {case['street']}

Reason for review: {case['review_reason']}

Source record ID (where applicable): {case['source_record_id']}

Recorded official-source evidence: {case['official_evidence_reference']}

HDB residential flag: {case['hdb_source_residential_flag']}; completion year: {case['hdb_source_year_completed']}; dwelling units: {case['hdb_source_total_dwelling_units']}.

Recorded composition: {case['hdb_recorded_composition_summary']}

[Google Maps address search]({case['google_maps_search_url']}). This is a search link; correct location and imagery availability have not been verified. Street View is supplementary evidence only.

Review question: Does the source address identify the expected physical residential building, and does independent evidence resolve the stated discrepancy? Classify before opening the concealed proposed-match key.

The sole reviewer uses HDB_Visual_Audit.xlsx; no extra fields are required here.

Current audit response options are Yes / No / Unable to determine.

Source evidence above is a preparation record, not proof of image inspection.

Retain location and composition uncertainty; do not infer SHI validity from exterior appearance.

Record observations before opening the algorithm key; retain inconclusive cases without forcing a decision.
"""
        (case_dir / f"{case['case_id']}.md").write_text(packet, encoding="utf-8")

    # Screening decisions are curated separately from retrieval and export.
    curation = ROOT / "data/literature/evidence_map_curated__2026-10-17.csv"
    if not curation.is_file():
        raise FileNotFoundError("Run scripts/consolidate_literature_screening.py before release export")
    ev = pd.read_csv(curation).fillna("")
    expanded = ev.to_dict("records")
    ev.to_csv(L / "evidence_map.csv", index=False)
    (L / "evidence_map.json").write_text(json.dumps({"status": "Structured evidence map; targeted full-text assessment and unresolved records explicitly distinguished", "records": expanded}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    candidates = []
    discovery_path = L / "search_snapshots/search_01_openalex_2026-10-16.json"
    if not discovery_path.is_file():
        discovery_path = ROOT / "data/literature/search_01_openalex_2026-10-16.json"
    openalex = json.loads(discovery_path.read_text())
    mapped_by_doi = {
        str(row.get("doi", "")).lower().removeprefix("https://doi.org/"): row
        for row in expanded
    }
    for x in openalex.get("results", []):
        doi = (x.get("doi") or "").lower()
        mapped = mapped_by_doi.get(doi.removeprefix("https://doi.org/"))
        category = mapped.get("screening_category", "") if mapped else ""
        if mapped and category == "direct_shi_abstract_only":
            screening, classification = "abstract assessed; full text pending", mapped["classification"]
        elif mapped and category != "uncertain_fulltext":
            screening, classification = "targeted full-text assessment completed", mapped["classification"]
        else:
            screening, classification = "full text unavailable via Europe PMC; publisher assessment pending", "uncertain; no SHI use asserted"
        candidates.append({"title":x.get("title"),"year":x.get("publication_year"),"doi":x.get("doi"),"openalex_id":x.get("id"),"screening_status":screening,"classification":classification})
    pd.DataFrame(candidates).to_csv(L / "forward_citation_candidates__openalex_2026-10-16.csv", index=False)
    print(f"Prepared building={len(buildings)}, crosswalk={len(cross)}, rental={len(rental)}, resale={len(resale)}, review_cases={len(selected)}, literature_confirmed_map={len(ev)}, forward_candidates={len(candidates)}")


if __name__ == "__main__":
    main()
