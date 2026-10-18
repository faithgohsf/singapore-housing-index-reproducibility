"""Rebuild current HDB buildings and compare with public Mendeley v1 SHI."""
from __future__ import annotations

import json
import argparse
import os
import pathlib
import sys
import tempfile

import pandas as pd
PROJECT = pathlib.Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(pathlib.Path(tempfile.gettempdir()) / "shi-mpl-cache"))
pathlib.Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
import matplotlib.pyplot as plt

sys.path.insert(0, str(PROJECT / "src"))
from shi.reconstruction import build_hdb_buildings, compute_shi, normalize_address_key  # noqa: E402
from shi.crosswalk import build_historical_crosswalk, compare_historical  # noqa: E402


def json_safe(value):
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Not JSON serializable: {type(value)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executive-weight", type=int, choices=[5, 6], default=6, help="6 is published-definition primary; 5 reproduces superseded sensitivity")
    args = parser.parse_args()
    raw = PROJECT / "data" / "raw"
    out = PROJECT / "outputs" / "tables"
    out.mkdir(parents=True, exist_ok=True)
    figures = PROJECT / "outputs" / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    property_path = raw / "hdb_property_information__2026-10-08.csv"
    historical_path = raw / "mendeley_shi_dataset_v1__data_in_brief.csv"
    properties = pd.read_csv(property_path, dtype="string", keep_default_na=False)
    historical = pd.read_csv(historical_path, dtype="string", keep_default_na=False)

    buildings, source_counts = build_hdb_buildings(properties)
    current = compute_shi(buildings, "recommended" if args.executive_weight == 6 else "executive_weight_5")
    legacy = compute_shi(buildings, "legacy_2021" if args.executive_weight == 6 else "legacy_2021_executive_weight_5")
    formula = current[["building_id", "address_key", "shi", "shi_status"]].merge(
        legacy[["building_id", "shi"]].rename(columns={"shi": "shi_legacy_2021"}),
        on="building_id", validate="one_to_one",
    )
    formula["formula_difference"] = formula["shi"] - formula["shi_legacy_2021"]
    valid_formula = formula.dropna(subset=["formula_difference"])
    formula_summary = {
        "formula_comparison_same_current_input": True,
        "formula_versions": [str(current.shi_formula.iloc[0]), str(legacy.shi_formula.iloc[0])],
        "valid_buildings": int(len(valid_formula)),
        "buildings_with_different_scores": int(valid_formula["formula_difference"].ne(0).sum()),
        "mean_absolute_score_change": float(valid_formula["formula_difference"].abs().mean()),
        "maximum_absolute_score_change": float(valid_formula["formula_difference"].abs().max()),
        "score_change_rows_gt_0_1": int(valid_formula["formula_difference"].abs().gt(0.1).sum()),
    }

    crosswalk, historical_status = build_historical_crosswalk(current, historical)
    comparison, agreement = compare_historical(current, historical_status)

    current.to_csv(out / "hdb_buildings__current_2026-10-08.csv", index=False)
    crosswalk.to_csv(out / "postal_crosswalk__mendeley_v1.csv", index=False)
    historical_status.to_csv(out / "historical_match_status__mendeley_v1.csv", index=False)
    comparison.to_csv(out / "historical_comparison_buildings__mendeley_v1.csv", index=False)
    formula.to_csv(out / "same_input_formula_comparison__current_2026-10-08.csv", index=False)
    valid_formula.loc[valid_formula["formula_difference"].abs().gt(0.1)].to_csv(
        out / "formula_change_cases_abs_delta_gt_0.1.csv", index=False
    )

    paired = comparison.loc[comparison["paired_for_agreement"], :]
    ba = paired.copy()
    ba["pair_mean"] = (ba["shi"].astype(float) + ba["historical_shi"].astype(float)) / 2
    ba["pair_difference"] = ba["shi"].astype(float) - ba["historical_shi"].astype(float)
    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.scatter(ba["pair_mean"], ba["pair_difference"], s=9, alpha=0.35, color="#245b87", edgecolors="none")
    mean_diff = agreement["mean_difference_current_minus_historical"]
    lower = agreement["limits_of_agreement_lower"]
    upper = agreement["limits_of_agreement_upper"]
    for y, label, color in [(mean_diff, "Mean difference", "#b03a2e"), (lower, "Lower 95% limits", "#777777"), (upper, "Upper 95% limits", "#777777")]:
        ax.axhline(y, linestyle="--", linewidth=1, color=color, label=f"{label}: {y:.3f}")
    ax.set_xlabel("Mean of current and historical SHI")
    ax.set_ylabel("Current SHI − historical SHI")
    ax.set_title("Current HDB source vs Mendeley v1 (address-linked buildings)")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(figures / "bland_altman_current_vs_mendeley_v1.png", dpi=180)
    plt.close(fig)

    score_valid = current.loc[current["shi_status"].eq("valid"), "shi"].astype(float)
    summary = {
        "executive_room_weight": args.executive_weight,
        "current_source_version": "data.gov.sg HDB Property Information, last updated 2026-10-08",
        "current_source_retrieval_manifest": "data/raw/source_manifests/hdb_property_information__2026-10-08.json",
        "historical_candidate": "Mendeley Data v1, DOI 10.17632/pj3dkvskr9.1, selected public historical SHI dataset; public file data in brief.csv",
        "historical_candidate_manifest": "data/raw/source_manifests/mendeley_shi_dataset_v1_files.json",
        "notebook_saved_counts": {"source_rows": 21272, "residential_filter_rows": 17397},
        "published_2021_paper_benchmark": {"source_rows": 21272, "unique_residential_buildings": 10077},
        "current_source_counts": {
            **source_counts,
            "canonical_address_keys": int(current["address_key"].nunique()),
            "composition_valid_scores": int(current["shi_status"].eq("valid").sum()),
            "composition_invalid_scores": int(current["shi_status"].eq("invalid").sum()),
            "score_min": float(score_valid.min()) if len(score_valid) else None,
            "score_max": float(score_valid.max()) if len(score_valid) else None,
            "score_mean": float(score_valid.mean()) if len(score_valid) else None,
            "score_median": float(score_valid.median()) if len(score_valid) else None,
        },
        "historical_dataset_counts": {
            "postal_rows": int(len(historical)),
            "canonical_address_keys": int(pd.Series([
                normalize_address_key(b, s) for b, s in zip(historical["Block Number"], historical["Street Name"])
            ]).nunique()),
            "multiple_postal_code_address_groups": int(historical.assign(
                address_key=[normalize_address_key(b, s) for b, s in zip(historical["Block Number"], historical["Street Name"])]
            ).groupby("address_key")["Postal Code"].nunique().gt(1).sum()),
            "five_digit_postal_rows_requiring_leading_zero_candidate": int(historical["Postal Code"].astype("string").str.fullmatch(r"\d{5}").fillna(False).sum()),
            "non_six_digit_postal_rows_before_normalization": int((~historical["Postal Code"].astype("string").str.fullmatch(r"\d{6}").fillna(False)).sum()),
        },
        "historical_comparison": agreement,
        "same_input_formula_comparison": formula_summary,
        "interpretation": (
            "Current-source reconstruction and comparison with Mendeley v1; not a reproduction of the 2021 "
            "paper's frozen HDB source snapshot or proof that Mendeley v1 is the original 2018 comparator."
        ),
    }
    (PROJECT / "outputs" / "tables" / "reconstruction_stage_summary.json").write_text(
        json.dumps(summary, indent=2, default=json_safe) + "\n"
    )
    print(json.dumps(summary, indent=2, default=json_safe))


if __name__ == "__main__":
    main()
