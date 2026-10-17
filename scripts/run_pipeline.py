"""Run the complete SHI study pipeline from source inputs to final tables."""
from __future__ import annotations

import argparse
import pathlib
import os
import subprocess
import sys
import tempfile

PROJECT = pathlib.Path(__file__).resolve().parents[1]
COORDINATES = PROJECT / "outputs/tables/one_map_coordinates__2026-10-16.csv"
REQUIRED_COORDINATE_COLUMNS = {"building_id", "address_key", "one_map_status", "x_svy21", "y_svy21"}


def check_coordinates() -> None:
    import pandas as pd
    columns = set(pd.read_csv(COORDINATES, nrows=0).columns)
    missing = sorted(REQUIRED_COORDINATE_COLUMNS - columns)
    if missing:
        raise RuntimeError(f"OneMap coordinate file is missing required columns: {', '.join(missing)}")


STAGES = [
    ("Retrieve missing public sources or verify saved snapshots", ["scripts/retrieve_public_data.py"], [
        "data/raw/hdb_property_information__2026-10-08.csv",
        "data/raw/hdb_rental_approval__retrieved_2026-10-16.csv",
        "data/raw/hdb_resale_flat_prices__retrieved_2026-10-16.csv",
        "data/raw/mendeley_shi_dataset_v1__data_in_brief.csv",
    ]),
    ("Reconstruct SHI and compare with the selected public historical dataset", ["scripts/run_reconstruction_stage.py"], [
        "outputs/tables/reconstruction_stage_summary.json",
        "outputs/tables/hdb_buildings__current_2026-10-08.csv",
        "outputs/tables/historical_comparison_buildings__mendeley_v1.csv",
    ]),
    ("Resolve building coordinates through OneMap", None, ["outputs/tables/one_map_coordinates__2026-10-16.csv"]),
    ("Link rental/resale records and write coverage tables", ["scripts/run_economic_coverage.py"], [
        "outputs/tables/economic_coverage_summary__2024-2025.json",
        "outputs/tables/rental_eligible_linked__2024-2025.csv",
        "outputs/tables/resale_eligible_linked__2024-2025.csv",
    ]),
    ("Summarize building-level economic patterns and SHI rank associations", ["scripts/run_descriptive_analyses.py"], [
        "outputs/tables/building_level_rent_by_shi__2024-2025.csv",
        "outputs/tables/building_level_resale_by_shi__2024-2025.csv",
        "outputs/tables/rent_shi_tier_summary__2024-2025.csv",
        "outputs/tables/resale_shi_tier_summary__2024-2025.csv",
        "outputs/tables/shi_economic_rank_associations__2024-2025.csv",
        "outputs/tables/descriptive_analysis_validation__2024-2025.json",
        "outputs/figures/building_rent_by_shi_tier__2024-2025.png",
        "outputs/figures/building_resale_by_shi_tier__2024-2025.png",
    ]),
    ("Fit economic models, run sensitivities, and write final tables", [
        "scripts/run_economic_models.py", "--stage", "all"
    ], [
        "outputs/tables/economic_model_results__2024-2025.json",
        "outputs/tables/rental_oof_predictions.csv",
        "outputs/tables/resale_baseline_oof_predictions.csv",
        "outputs/tables/resale_adjusted_oof_predictions.csv",
    ]),
    ("Prepare traceable release datasets and address cases", ["scripts/prepare_release_materials.py"], [
        "outputs/tables/building_level_shi__release__current_2026-10-08.csv",
        "outputs/tables/address_review_blinded_case_packet__30.csv",
    ]),
    ("Account for housing groups and recorded dwelling coverage", ["scripts/run_housing_group_coverage.py"], [
        "outputs/tables/coverage_by_housing_group__2026-10-17.csv",
    ]),
    ("Verify documented post-analysis address-point decisions", ["scripts/verify_location_resolutions.py", "--output", "outputs/tables/location_resolution_checks.json"], ["outputs/tables/location_resolution_checks.json"]),
    ("Summarise recorded single-reviewer HDB audit", ["scripts/audit_address_validation.py", "--output", "outputs/tables/hdb_visual_audit_summary.json"], ["outputs/tables/hdb_visual_audit_summary.json"]),
    ("Validate release integrity", ["scripts/validate_release_outputs.py"], [
        "outputs/tables/release_integrity_checks__2026-10-17.json",
    ]),
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=["workspace", "reproducibility"], default="workspace", help="Reproducibility profile verifies frozen inputs and omits internal review-workbook checks.")
    args = parser.parse_args(argv)
    stages = list(STAGES)
    if args.profile == "reproducibility":
        stages.insert(0, ("Verify frozen reproduction inputs", ["scripts/stage_frozen_inputs.py", "--check"], []))
        stages = [(label, script_args + ["--skip-review-workbooks"] if script_args and script_args[0] == "scripts/validate_release_outputs.py" else script_args, outputs) for label, script_args, outputs in stages]
    cache_root = pathlib.Path(tempfile.gettempdir()) / "shi-pipeline-cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    child_env = os.environ.copy()
    child_env.setdefault("MPLCONFIGDIR", str(cache_root / "matplotlib"))
    child_env.setdefault("XDG_CACHE_HOME", str(cache_root / "xdg"))
    child_env.setdefault("LOKY_MAX_CPU_COUNT", "4")
    current_stage = "startup"
    try:
        total = len(stages)
        for i, (label, script_args, expected_outputs) in enumerate(stages, start=1):
            current_stage = label
            print(f"\n[{i}/{total}] {label}", flush=True)
            if script_args is None:
                if not COORDINATES.is_file():
                    print("No saved coordinate crosswalk found. The geocoder will request OneMap credentials.", flush=True)
                    subprocess.run([sys.executable, "scripts/geocode_buildings_onemap.py"], cwd=PROJECT, check=True)
                check_coordinates()
            else:
                subprocess.run([sys.executable, *script_args], cwd=PROJECT, env=child_env, check=True)
            missing = [name for name in expected_outputs if not (PROJECT / name).is_file()]
            if missing:
                raise RuntimeError(
                    f"Stage '{label}' did not create expected output(s): {', '.join(missing)}"
                )
    except subprocess.CalledProcessError as exc:
        print(
            f"\nPipeline stopped at stage '{current_stage}' (exit code {exc.returncode}): "
            f"{' '.join(map(str, exc.cmd))}",
            file=sys.stderr,
        )
        return exc.returncode or 1
    except (RuntimeError, OSError) as exc:
        print(f"\nPipeline stopped before the next stage: {exc}", file=sys.stderr)
        return 2
    print("\nPipeline completed. Review outputs/tables/ and outputs/figures/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
