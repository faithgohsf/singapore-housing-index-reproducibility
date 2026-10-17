"""Create building-level economic gradients and SHI rank-association outputs."""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile

PROJECT = pathlib.Path(__file__).resolve().parents[1]
MPL_CACHE = pathlib.Path(tempfile.gettempdir()) / "shi-mpl-cache"
MPL_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE))
os.environ.setdefault("XDG_CACHE_HOME", str(pathlib.Path(tempfile.gettempdir()) / "shi-xdg-cache"))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(PROJECT / "src"))
from shi.descriptive import (  # noqa: E402
    build_building_summaries,
    descriptive_metadata,
    rank_associations,
    summarize_shi_bands,
    validate_traceability,
)

OUT = PROJECT / "outputs" / "tables"
FIGURES = PROJECT / "outputs" / "figures"
SUFFIX = "__2024-2025"


def _save_table(frame: pd.DataFrame, stem: str) -> None:
    frame.to_csv(OUT / f"{stem}{SUFFIX}.csv", index=False)
    (OUT / f"{stem}{SUFFIX}.json").write_text(frame.to_json(orient="records", indent=2, double_precision=10) + "\n")


def _tier_plot(buildings: pd.DataFrame, *, metric: str, ylabel: str, title: str, filename: str) -> None:
    order = ["[1,2)", "[2,3)", "[3,4)", "[4,5)", "[5,6]"]
    present = [tier for tier in order if tier in set(buildings["shi_tier"])]
    samples = [buildings.loc[buildings["shi_tier"].eq(tier), metric].astype(float).to_numpy() for tier in present]
    if not samples or any(len(values) == 0 for values in samples):
        raise ValueError(f"No building observations available for {title}")
    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.boxplot(samples, tick_labels=present, showfliers=False, showmeans=True)
    ax.set_xlabel("SHI display band")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.text(0.01, 0.99, "One value per building; boxes show median and interquartile range",
            transform=ax.transAxes, va="top", fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES / filename, dpi=180)
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    rental_path = OUT / "rental_eligible_linked__2024-2025.csv"
    resale_path = OUT / "resale_eligible_linked__2024-2025.csv"
    if not rental_path.is_file() or not resale_path.is_file():
        raise SystemExit("Economic eligible-link files are missing. Run `python scripts/run_pipeline.py` first.")
    rental = pd.read_csv(rental_path, dtype={"building_id": "string"})
    resale = pd.read_csv(resale_path, dtype={"building_id": "string"})
    rent_buildings = build_building_summaries(
        rental, outcome_col="outcome_numeric", outcome_name="monthly_rent_sgd"
    )
    resale_buildings = build_building_summaries(
        resale, outcome_col="outcome_numeric", outcome_name="resale_price_sgd", include_price_per_sqm=True
    )
    rent_metrics = ["mean_outcome", "median_outcome"]
    resale_metrics = ["mean_outcome", "median_outcome", "mean_price_per_sqm", "median_price_per_sqm"]
    rent_tiers = summarize_shi_bands(rent_buildings, metrics=rent_metrics)
    resale_tiers = summarize_shi_bands(resale_buildings, metrics=resale_metrics)
    ranks = pd.concat([
        rank_associations(rent_buildings, metrics=["median_outcome", "mean_outcome"], market="rental"),
        rank_associations(resale_buildings,
                          metrics=["median_outcome", "mean_outcome", "median_price_per_sqm", "mean_price_per_sqm"],
                          market="resale"),
    ], ignore_index=True)
    rent_trace = validate_traceability(rental, rent_buildings)
    resale_trace = validate_traceability(resale, resale_buildings)

    _save_table(rent_buildings, "building_level_rent_by_shi")
    _save_table(resale_buildings, "building_level_resale_by_shi")
    _save_table(rent_tiers, "rent_shi_tier_summary")
    _save_table(resale_tiers, "resale_shi_tier_summary")
    _save_table(ranks, "shi_economic_rank_associations")

    _tier_plot(rent_buildings, metric="median_outcome", ylabel="Building median approved monthly rent (S$)",
               title="Building rent patterns by SHI band", filename="building_rent_by_shi_tier__2024-2025.png")
    _tier_plot(resale_buildings, metric="median_outcome", ylabel="Building median registered resale price (S$)",
               title="Building resale patterns by SHI band", filename="building_resale_by_shi_tier__2024-2025.png")

    report = {
        "study": "Singapore Housing Index: reconstruction, coverage and economic validation",
        "inputs": {
            "rental_eligible_records": rental_path.relative_to(PROJECT).as_posix(),
            "resale_eligible_records": resale_path.relative_to(PROJECT).as_posix(),
        },
        "method": descriptive_metadata(),
        "rental": {
            **rent_trace,
            "building_count_by_shi_band": {r.shi_tier: int(r.building_count) for r in rent_tiers.itertuples()},
        },
        "resale": {
            **resale_trace,
            "building_count_by_shi_band": {r.shi_tier: int(r.building_count) for r in resale_tiers.itertuples()},
        },
        "rank_associations": ranks.to_dict(orient="records"),
        "outputs": [
            f"outputs/tables/{name}{SUFFIX}.{extension}"
            for name in ["building_level_rent_by_shi", "building_level_resale_by_shi",
                         "rent_shi_tier_summary", "resale_shi_tier_summary", "shi_economic_rank_associations"]
            for extension in ["csv", "json"]
        ] + [
            "outputs/figures/building_rent_by_shi_tier__2024-2025.png",
            "outputs/figures/building_resale_by_shi_tier__2024-2025.png",
        ],
        "scientific_boundary": "Descriptive housing-related economic patterns only; no individual income/deprivation or causal interpretation.",
    }
    if any(pd.isna(value) for row in ranks.to_dict(orient="records") for value in row.values()):
        raise AssertionError("Rank association output contains a missing value")
    report_path = OUT / f"descriptive_analysis_validation{SUFFIX}.json"
    report_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
