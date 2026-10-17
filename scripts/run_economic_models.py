"""Run frozen grouped rental/resale models after exact OneMap coordinates exist."""
from __future__ import annotations

import json
import pathlib
import sys
import warnings
import argparse

import numpy as np
import pandas as pd

PROJECT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from shi.models import fit_predict, grouped_folds, prepare_rental, prepare_resale, spatial_folds  # noqa: E402

SEED = 20260908
N_BOOT = 2000


def _cross_validate(data, specs, folds, *, equal_record_weight=False):
    data = data.reset_index(drop=True)
    columns = [c for c in ["source_record_id", "source_address_key", "date", "building_id", "outcome", "flat_type"] if c in data]
    pred = data[columns].copy()
    if "source_record_id" in pred and pred.source_record_id.duplicated().any():
        raise ValueError("source_record_id must uniquely identify each source record")
    pred["fold"] = -1
    diag = []
    for fold, (train_idx, test_idx) in enumerate(folds):
        train, test = data.iloc[train_idx], data.iloc[test_idx]
        pred.loc[test_idx, "fold"] = fold
        for name, spec in specs.items():
            fit, fallback, rank, columns = fit_predict(
                train, test, include_shi=spec["shi"], include_type=spec["type"],
                include_resale_adjustments=spec.get("resale_adjustments", False),
                equal_record_weight=equal_record_weight,
            )
            pred.loc[test_idx, name] = fit
            diag.append({"fold": fold, "model": name, "train_rows": len(train), "test_rows": len(test),
                         "train_buildings": train.building_id.nunique(), "test_buildings": test.building_id.nunique(),
                         "design_rank": rank, "design_columns": columns, "rank_deficit": columns-rank,
                         "linear_fallback_predictors": ";".join(fallback)})
    if pred["fold"].lt(0).any() or pred[list(specs)].isna().any().any():
        raise AssertionError("Every eligible row must have exactly one held-out prediction per model")
    return pred, pd.DataFrame(diag)


def _metric_frame(pred: pd.DataFrame, models: list[str], *, equal_record: bool = False) -> pd.DataFrame:
    out = pred.copy()
    for m in models:
        out[f"abs_error_{m}"] = (out["outcome"] - out[m]).abs()
    if equal_record:
        losses = out.groupby("building_id")[[f"abs_error_{m}" for m in models] + ["outcome"]].agg(list)
        return losses
    return out.groupby("building_id")[[f"abs_error_{m}" for m in models]].mean()


def _metrics(pred: pd.DataFrame, models: list[str], *, equal_record: bool = False) -> dict:
    rows = pred.copy()
    results = {}
    if equal_record:
        loss = {m: float((rows["outcome"] - rows[m]).abs().mean()) for m in models}
        w = np.ones(len(rows))
    else:
        loss = {m: float(rows.assign(error=(rows["outcome"] - rows[m]).abs()).groupby("building_id").error.mean().mean()) for m in models}
        n = rows.groupby("building_id").size()
        w = rows["building_id"].map(1 / n).to_numpy()
    y = rows["outcome"].to_numpy(dtype=float)
    ybar = float(np.average(y, weights=w))
    for m in models:
        error = y - rows[m].to_numpy(dtype=float)
        r2 = 1 - float(np.average(error**2, weights=w)) / float(np.average((y-ybar)**2, weights=w))
        results[m] = {"mae_sgd": loss[m], "weighted_heldout_r2": r2}
    return results


def _paired_bootstrap(pred: pd.DataFrame, model_a: str, model_b: str, *, equal_record=False, n_boot=N_BOOT):
    rng = np.random.default_rng(SEED)
    loss_rows = pred.assign(a=(pred.outcome-pred[model_a]).abs(), b=(pred.outcome-pred[model_b]).abs())
    losses = loss_rows.groupby("building_id").agg(a=("a", "sum"), b=("b", "sum"), n=("a", "size"))
    samples = rng.integers(0, len(losses), size=(n_boot, len(losses)))
    values = losses[["a", "b"]].to_numpy()
    if equal_record:
        draws = values[samples].sum(axis=1) / losses.n.to_numpy()[samples].sum(axis=1)[:, None]
    else:
        # The target is equal building weight, so bootstrap mean within-building errors.
        mean_loss = values / losses.n.to_numpy()[:, None]
        draws = mean_loss[samples].mean(axis=1)
    delta = draws[:, 0] - draws[:, 1]
    point = _metrics(pred, [model_a, model_b], equal_record=equal_record)
    a, b = point[model_a]["mae_sgd"], point[model_b]["mae_sgd"]
    reduction = 100 * (a-b) / a if a else np.nan
    # Paired resampled percentage reduction uses the same building draw for both models.
    pct = 100 * (draws[:, 0] - draws[:, 1]) / draws[:, 0]
    return {"model_a": model_a, "model_b": model_b, "mae_a": a, "mae_b": b,
            "improvement_mae_a_minus_b": a-b, "percent_reduction": reduction,
            "improvement_ci95": np.quantile(delta, [0.025, 0.975]).tolist(),
            "percent_reduction_ci95": np.quantile(pct, [0.025, 0.975]).tolist(),
            "bootstrap_buildings": int(pred.building_id.nunique()), "bootstrap_resamples": n_boot,
            "interval_scope": "conditional on fitted models; paired whole-building resampling of held-out predictions"}


def _run_primary(data, specs, pairs, name):
    folds = grouped_folds(data, seed=SEED, n_splits=5)
    pred, diagnostics = _cross_validate(data, specs, folds)
    pred.to_csv(PROJECT / f"outputs/tables/{name}_oof_predictions.csv", index=False)
    diagnostics.to_csv(PROJECT / f"outputs/tables/{name}_model_diagnostics.csv", index=False)
    outcome_scale = "registered resale price (S$ total price)" if name.startswith("resale") else "monthly rent (S$ per month)"
    summary = {"rows": len(data), "buildings": int(data.building_id.nunique()), "outcome_scale": outcome_scale,
               "models": _metrics(pred, list(specs))}
    summary["comparisons"] = [_paired_bootstrap(pred, a, b) for a, b in pairs]
    pd.DataFrame([{"fold": f, "building_id": bid} for f, (_, te) in enumerate(folds) for bid in data.iloc[te].building_id.unique()]).to_csv(
        PROJECT / f"outputs/tables/{name}_fold_manifest.csv", index=False)
    return summary


def _fold_unseen_levels(data, column):
    unseen = set()
    for train_idx, test_idx in grouped_folds(data, seed=SEED, n_splits=5):
        unseen.update(set(data.iloc[test_idx][column].dropna().unique()) - set(data.iloc[train_idx][column].dropna().unique()))
    return sorted(unseen)


def _coord_coverage(linked, coordinates):
    status = linked[["building_id"]].merge(
        coordinates[["building_id", "one_map_status"]], on="building_id", how="left", validate="many_to_one"
    )["one_map_status"].fillna("no_coordinate_row")
    return status.value_counts(dropna=False).astype(int).to_dict()


def _run_rental_sensitivities(rental):
    specifications = [
        ("sensitivity_2025", rental.loc[rental.date.dt.year.eq(2025)].copy(), False, False),
        ("sensitivity_min3", rental.loc[rental.groupby("building_id").building_id.transform("size").ge(3)].copy(), False, False),
        ("sensitivity_equal_record_weights", rental.copy(), True, True),
    ]
    results = {}
    spec = {"A": {"shi": False, "type": False}, "B": {"shi": True, "type": False}}
    for name, sample, equal_fit, equal_eval in specifications:
        folds = grouped_folds(sample, seed=SEED, n_splits=5)
        pred, diagnostics = _cross_validate(sample, spec, folds, equal_record_weight=equal_fit)
        pred.to_csv(PROJECT / f"outputs/tables/{name}_oof_predictions.csv", index=False)
        diagnostics.to_csv(PROJECT / f"outputs/tables/{name}_model_diagnostics.csv", index=False)
        results[name] = {"rows": len(sample), "buildings": int(sample.building_id.nunique()),
                         "comparison": _paired_bootstrap(pred, "A", "B", equal_record=equal_eval)}
    folds, groups = spatial_folds(rental, seed=SEED, n_clusters=5)
    groups.to_csv(PROJECT / "outputs/tables/rental_spatial_groups.csv", index=False)
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 7))
    scatter = ax.scatter(groups.coord_x, groups.coord_y, c=groups.spatial_group, s=12, cmap="tab10", alpha=0.8)
    ax.set_xlabel("OneMap SVY21 easting")
    ax.set_ylabel("OneMap SVY21 northing")
    ax.set_title("Rental spatial holdout groups (building coordinates)")
    fig.colorbar(scatter, ax=ax, label="Spatial holdout group")
    fig.tight_layout()
    fig.savefig(PROJECT / "outputs/figures/rental_spatial_holdout_groups.png", dpi=180)
    plt.close(fig)
    pred, diag = _cross_validate(rental, spec, folds)
    pred.to_csv(PROJECT / "outputs/tables/sensitivity_spatial_holdout_oof_predictions.csv", index=False)
    diag.to_csv(PROJECT / "outputs/tables/sensitivity_spatial_holdout_model_diagnostics.csv", index=False)
    results["sensitivity_spatial_holdout"] = {"rows": len(rental), "buildings": int(rental.building_id.nunique()),
        "group_sizes": groups.groupby("spatial_group").building_id.nunique().to_dict(),
        "comparison": _paired_bootstrap(pred, "A", "B")}
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["all", "rental", "resale-baseline"], default="all",
                        help="Run all analyses (default), the complete rental stage, or only resale A/B while C/D awaits a rare-category decision.")
    stage = parser.parse_args().stage
    coord_path = PROJECT / "outputs/tables/one_map_coordinates__2026-10-16.csv"
    if not coord_path.exists():
        raise SystemExit("OneMap coordinate crosswalk missing. Configure ONEMAP_TOKEN and run scripts/geocode_buildings_onemap.py first.")
    coordinates = pd.read_csv(coord_path, dtype={"x_svy21": "string", "y_svy21": "string"})
    out = PROJECT / "outputs/tables"
    rental_link = pd.read_csv(out / "rental_eligible_linked__2024-2025.csv", parse_dates=["date"])
    resale_link = pd.read_csv(out / "resale_eligible_linked__2024-2025.csv", parse_dates=["date"])
    rental = prepare_rental(rental_link, coordinates)
    resale = prepare_resale(resale_link, coordinates)
    rental_specs = {"A": {"shi": False, "type": False}, "B": {"shi": True, "type": False},
                    "C": {"shi": False, "type": True}, "D": {"shi": True, "type": True}}
    resale_specs = {"A": {"shi": False, "type": False}, "B": {"shi": True, "type": False},
                    "C": {"shi": False, "type": True, "resale_adjustments": True},
                    "D": {"shi": True, "type": True, "resale_adjustments": True}}
    report = {
        "protocol_version": "CURRENT_RESEARCH_PLAN.md consolidated 2026-10-17; economic specification originally 2026-09-08",
        "seed": SEED,
        "coordinate_linkage": {"buildings_in_crosswalk": int(len(coordinates)),
            "exact_unique_address_coordinates": int(coordinates.one_map_status.eq("exact_onemap_address").sum()),
            "ambiguous_exact_candidate_buildings": int(coordinates.one_map_status.eq("multiple_exact_candidates").sum()),
            "no_exact_candidate_buildings": int(coordinates.one_map_status.eq("no_exact_candidate").sum()),
            "rental_source_rows_in_window": int(len(rental_link)), "rental_model_complete_case_rows": int(len(rental)),
            "rental_model_complete_case_buildings": int(rental.building_id.nunique()),
            "resale_source_rows_in_window": int(len(resale_link)), "resale_model_complete_case_rows": int(len(resale)),
            "resale_model_complete_case_buildings": int(resale.building_id.nunique()),
            "rental_coordinate_status_records": _coord_coverage(rental_link, coordinates),
            "resale_coordinate_status_records": _coord_coverage(resale_link, coordinates)},
        "interpretation_limit": "Housing-related economic prediction only; no individual income, deprivation, or health-confounding validation claim.",
    }
    if stage in {"all", "rental"}:
        report["rental"] = _run_primary(rental, rental_specs, [("A", "B"), ("C", "D"), ("B", "C")], "rental")
        report["rental_sensitivities"] = _run_rental_sensitivities(rental)
    if stage == "all":
        report["resale_baseline"] = _run_primary(resale, {"A": resale_specs["A"], "B": resale_specs["B"]}, [("A", "B")], "resale_baseline")
        unsupported = _fold_unseen_levels(resale, "flat_type")
        adjusted = resale.loc[~resale.flat_type.isin(unsupported)].reset_index(drop=True)
        excluded = resale.loc[resale.flat_type.isin(unsupported)].copy()
        excluded.to_csv(out / "resale_adjusted_pair_excluded_unsupported_type.csv", index=False)
        report["resale_adjusted"] = {
            **_run_primary(adjusted, {"C": resale_specs["C"], "D": resale_specs["D"]}, [("C", "D")], "resale_adjusted"),
            "excluded_unseen_training_categories": unsupported,
            "excluded_rows": int(len(excluded)), "excluded_buildings": int(excluded.building_id.nunique()),
            "exclusion_reason": "A pre-fit grouped-fold support audit found these recorded flat-type levels only in held-out data in at least one fold. The affected category/building was excluded from the shared adjusted C/D sample; no category mapping or effect was invented. Baseline A/B is reported on its full eligible sample.",
        }
    elif stage == "resale-baseline":
        report["resale_baseline"] = _run_primary(resale, {"A": resale_specs["A"], "B": resale_specs["B"]}, [("A", "B")], "resale_baseline")
        report["resale_adjusted_pair_status"] = "not run in this baseline-only stage; full run performs a pre-fit fold-support audit and reports exclusions explicitly"
    report["stage"] = stage
    suffix = "__rental" if stage == "rental" else "__resale_baseline" if stage == "resale-baseline" else ""
    (out / f"economic_model_results__2024-2025{suffix}.json").write_text(json.dumps(report, indent=2, default=lambda x: int(x) if isinstance(x, np.integer) else float(x) if isinstance(x, np.floating) else str(x)) + "\n")
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
