"""Independently reconcile core SHI outputs from saved row-level files.

This audit reads the frozen snapshots and pipeline exports; it does not call
the analysis functions that created the published summaries.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
WEIGHTS = {
    "1room_sold": 1, "2room_sold": 2, "3room_sold": 3,
    "4room_sold": 4, "5room_sold": 5, "exec_sold": 5,
    "multigen_sold": 6, "studio_apartment_sold": 1,
    "1room_rental": 1, "2room_rental": 2, "3room_rental": 3,
    "other_room_rental": 4,
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def weighted_building_mae(predictions: pd.DataFrame, column: str) -> float:
    error = (predictions["outcome"] - predictions[column]).abs()
    return float(error.groupby(predictions["building_id"]).mean().mean())


def audit() -> dict:
    checks: dict[str, object] = {}
    buildings = pd.read_csv(TABLES / "building_level_shi__release__current_2026-10-08.csv")
    for col, weight in WEIGHTS.items():
        buildings[col] = pd.to_numeric(buildings[col], errors="coerce")
    buildings["total_dwelling_units"] = pd.to_numeric(buildings["total_dwelling_units"], errors="coerce")
    buildings["shi"] = pd.to_numeric(buildings["shi"], errors="coerce")
    weighted_numerator = sum(buildings[c] * w for c, w in WEIGHTS.items())
    independent_score = weighted_numerator / buildings["total_dwelling_units"]
    valid = buildings["shi_status"].eq("valid") & buildings["composition_complete"].astype(str).str.lower().eq("true")
    score_error = (independent_score[valid] - buildings.loc[valid, "shi"]).abs()
    checks["building_rows"] = len(buildings)
    checks["unique_building_id"] = bool(buildings["building_id"].is_unique)
    checks["valid_complete_shi_rows"] = int(valid.sum())
    checks["incomplete_or_invalid_scored_rows"] = int((~valid & buildings["shi"].notna()).sum())
    checks["max_abs_independent_score_error"] = float(score_error.max()) if len(score_error) else None
    checks["formula_recomputed_all_valid_scores"] = bool(len(score_error) == int(valid.sum()) and score_error.le(1e-10).all())

    reconstruction = json.loads((TABLES / "reconstruction_stage_summary.json").read_text())
    checks["notebook_source_rows"] = reconstruction["notebook_saved_counts"]["source_rows"]
    checks["notebook_residential_filter_rows"] = reconstruction["notebook_saved_counts"]["residential_filter_rows"]
    checks["published_unique_residential_building_benchmark"] = reconstruction["published_2021_paper_benchmark"]["unique_residential_buildings"]
    checks["current_residential_buildings"] = int(buildings.shape[0])
    checks["current_source_count_reconciles"] = int(buildings.shape[0]) == reconstruction["current_source_counts"]["residential_buildings"]

    hist = pd.read_csv(TABLES / "historical_comparison_buildings__mendeley_v1.csv")
    paired = hist["paired_for_agreement"].astype(str).str.lower().eq("true")
    checks["historical_candidate_rows"] = len(hist)
    checks["historical_paired_rows_recomputed"] = int(paired.sum())
    checks["historical_unmatched_rows_recomputed"] = int(hist["historical_shi"].isna().sum() - hist["historical_match_status"].eq("conflicting_historical_scores").sum())
    checks["historical_conflicting_rows_recomputed"] = int(hist["historical_match_status"].eq("conflicting_historical_scores").sum())
    checks["historical_candidate_identity_as_original_2018_not_established"] = True
    values=hist.loc[paired,['shi','historical_shi']].to_numpy(dtype=float)
    difference=values[:,0]-values[:,1]
    n,k=values.shape;grand=values.mean();row_mean=values.mean(axis=1);column_mean=values.mean(axis=0)
    ms_row=k*np.sum((row_mean-grand)**2)/(n-1)
    ms_column=n*np.sum((column_mean-grand)**2)/(k-1)
    residual=values-row_mean[:,None]-column_mean[None,:]+grand
    ms_error=np.sum(residual**2)/((n-1)*(k-1))
    icc=(ms_row-ms_error)/(ms_row+(k-1)*ms_error+k*(ms_column-ms_error)/n)
    historical_metrics={
        'mean_difference_current_minus_historical':float(difference.mean()),
        'mean_absolute_difference':float(np.abs(difference).mean()),
        'limits_of_agreement_lower':float(difference.mean()-1.96*difference.std(ddof=1)),
        'limits_of_agreement_upper':float(difference.mean()+1.96*difference.std(ddof=1)),
        'icc_A_1_two_way_absolute_agreement':float(icc),
    }
    checks['independently_recomputed_historical_agreement']=historical_metrics
    assert all(np.isclose(value,reconstruction['historical_comparison'][key],atol=1e-12) for key,value in historical_metrics.items())

    formula = pd.read_csv(TABLES / "same_input_formula_comparison__current_2026-10-08.csv")
    delta = pd.to_numeric(formula["formula_difference"], errors="coerce")
    checks["formula_comparison_rows"] = len(formula)
    checks["formula_changed_buildings_recomputed"] = int(delta.abs().gt(1e-12).sum())
    checks["formula_max_abs_change_recomputed"] = float(delta.abs().max())

    metrics = json.loads((TABLES / "economic_model_results__2024-2025.json").read_text())
    model_checks = {}
    model_files = {
        "rental": ("rental_oof_predictions.csv", ["A", "B", "C", "D"]),
        "resale_baseline": ("resale_baseline_oof_predictions.csv", ["A", "B"]),
        "resale_adjusted": ("resale_adjusted_oof_predictions.csv", ["C", "D"]),
        "sensitivity_2025": ("sensitivity_2025_oof_predictions.csv", ["A", "B"]),
        "sensitivity_min3": ("sensitivity_min3_oof_predictions.csv", ["A", "B"]),
        "sensitivity_equal_record_weights": ("sensitivity_equal_record_weights_oof_predictions.csv", ["A", "B"]),
        "sensitivity_spatial_holdout": ("sensitivity_spatial_holdout_oof_predictions.csv", ["A", "B"]),
    }
    for model, (filename, cols) in model_files.items():
        df = pd.read_csv(TABLES / filename)
        df["outcome"] = pd.to_numeric(df["outcome"], errors="coerce")
        for col in cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        fold_unique = df.groupby("building_id")["fold"].nunique(dropna=False).max() == 1
        address_fold_unique = df.groupby("source_address_key")["fold"].nunique(dropna=False).max() == 1
        ids_unique = df["source_record_id"].is_unique
        equal_record = model == "sensitivity_equal_record_weights"
        mae = {c: float((df.outcome-df[c]).abs().mean()) if equal_record else weighted_building_mae(df,c) for c in cols}
        weights = np.ones(len(df)) if equal_record else df.building_id.map(1/df.groupby('building_id').size()).to_numpy()
        outcome = df.outcome.to_numpy(); mean = np.average(outcome, weights=weights)
        r2 = {c: float(1-np.average((outcome-df[c])**2,weights=weights)/np.average((outcome-mean)**2,weights=weights)) for c in cols}
        if model.startswith('sensitivity_'):
            expected = metrics['rental_sensitivities'][model]['comparison']
            agrees = np.isclose(mae['A'],expected['mae_a']) and np.isclose(mae['B'],expected['mae_b'])
        else:
            agrees = all(np.isclose(mae[c], metrics[model]['models'][c]['mae_sgd']) for c in cols)
        result = {
            "rows": len(df),
            "buildings": int(df["building_id"].nunique()),
            "source_record_ids_unique": bool(ids_unique),
            "building_one_fold_only": bool(fold_unique),
            "address_key_one_fold_only": bool(address_fold_unique),
            "weighting": "equal records" if equal_record else "equal buildings",
            "recomputed_mae": mae,
            "recomputed_heldout_r2": r2,
            "reported_mae_matches": bool(agrees),
        }
        assert agrees, f"Reported and independently recomputed MAE differ for {model}"
        assert fold_unique and address_fold_unique and ids_unique
        model_checks[model] = result
    checks["models"] = model_checks
    checks['model_diagnostic_rank_deficits'] = {
        path.name: int(pd.read_csv(path)['rank_deficit'].sum())
        for path in sorted(TABLES.glob('*model_diagnostics.csv'))
    }

    for ds in ["rental", "resale"]:
        fn = f"{ds}_analysis_records__release__2024-2025.csv"
        d = pd.read_csv(TABLES / fn, dtype={"source_record_id": str})
        dates = pd.to_datetime(d["date"], errors="coerce")
        checks[f"{ds}_release_rows"] = len(d)
        checks[f"{ds}_unique_source_ids"] = int(d["source_record_id"].nunique())
        checks[f"{ds}_date_min"] = str(dates.min().date())
        checks[f"{ds}_date_max"] = str(dates.max().date())
        checks[f"{ds}_all_dates_in_half_open_window"] = bool(dates.ge("2024-01-01").all() and dates.lt("2026-01-01").all())

    source_files = [
        ROOT / "data/raw/hdb_property_information__2026-10-08.csv",
        ROOT / "data/raw/hdb_rental_approval__retrieved_2026-10-16.csv",
        ROOT / "data/raw/hdb_resale_flat_prices__retrieved_2026-10-16.csv",
        ROOT / "data/raw/mendeley_shi_dataset_v1__data_in_brief.csv",
        ROOT / "outputs/tables/one_map_coordinates__2026-10-16.csv",
    ]
    checks["source_checksums"] = {str(f.relative_to(ROOT)): sha256(f) for f in source_files}

    release_validation = json.loads((TABLES / "release_integrity_checks__2026-10-17.json").read_text())
    checks["release_integrity_check_report"] = release_validation
    return checks


if __name__ == "__main__":
    result = audit()
    out = TABLES / "independent_final_audit__2026-10-17.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"Saved {out.relative_to(ROOT)}")
