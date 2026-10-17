"""Protocol-fixed grouped validation models for SHI economic information."""
from __future__ import annotations

import numpy as np
import pandas as pd
import patsy
import statsmodels.api as sm
from scipy.linalg import qr
from sklearn.cluster import KMeans
from sklearn.model_selection import GroupKFold


def _design(train: pd.DataFrame, test: pd.DataFrame, *, include_shi: bool, include_type: bool,
            include_resale_adjustments: bool = False) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Fit patsy natural spline bases on training rows and apply unchanged to test rows."""
    # The adjusted resale specification substitutes remaining lease for age.
    cont = ([] if include_resale_adjustments else ["age"]) + (["shi"] if include_shi else [])
    if include_resale_adjustments:
        cont += ["floor_area_sqm", "remaining_lease_months"]
    train_parts, test_parts, fallback = [], [], []
    # A full four-by-four natural-spline tensor must span the marginal x/y
    # effects as well as their interaction. Multiplying separately centered
    # bases alone omits those marginal effects. Build uncentered bases, then
    # remove the tensor's intercept redundancy using training predictors only.
    coordinate_train, coordinate_test = [], []
    for name in ("coord_x", "coord_y"):
        if train[name].nunique(dropna=True) >= 4:
            basis = patsy.dmatrix(f"cr({name}, df=4) - 1", train, return_type="dataframe")
            heldout = patsy.build_design_matrices([basis.design_info], test)[0]
            coordinate_train.append(np.asarray(basis))
            coordinate_test.append(np.asarray(heldout))
        else:
            center = float(train[name].mean())
            scale = float(train[name].std(ddof=0)) or 1.0
            coordinate_train.append(np.column_stack([np.ones(len(train)), (train[name] - center) / scale]))
            coordinate_test.append(np.column_stack([np.ones(len(test)), (test[name] - center) / scale]))
            fallback.append(name)
    tensor_train = np.einsum("ni,nj->nij", *coordinate_train).reshape(len(train), -1)
    tensor_test = np.einsum("ni,nj->nij", *coordinate_test).reshape(len(test), -1)
    tensor_mean = tensor_train.mean(axis=0)
    centered = tensor_train - tensor_mean
    _, r, pivot = qr(centered, mode="economic", pivoting=True)
    diagonal = np.abs(np.diag(r))
    tolerance = max(centered.shape) * np.finfo(float).eps * (diagonal.max() if len(diagonal) else 0)
    location_rank = int((diagonal > tolerance).sum())
    selected = np.sort(pivot[:location_rank])
    names = [f"coord_tensor_{i}" for i in selected]
    train_parts.append(pd.DataFrame(centered[:, selected], index=train.index, columns=names))
    test_parts.append(pd.DataFrame((tensor_test - tensor_mean)[:, selected], index=test.index, columns=names))
    infos = {}
    for name in cont:
        df = 3
        distinct = train[name].nunique(dropna=True)
        if distinct < df:
            center = float(train[name].mean())
            scale = float(train[name].std(ddof=0)) or 1.0
            train_parts.append(pd.DataFrame({f"{name}_linear": (train[name] - center) / scale}, index=train.index))
            test_parts.append(pd.DataFrame({f"{name}_linear": (test[name] - center) / scale}, index=test.index))
            fallback.append(name)
        else:
            # Training-derived centering makes each additive natural-spline
            # term identifiable alongside the intercept; the same training
            # constraint is applied unchanged to held-out rows.
            formula = f'cr({name}, df={df}, constraints="center") - 1'
            xtr = patsy.dmatrix(formula, train, return_type="dataframe")
            info = xtr.design_info
            xte = patsy.build_design_matrices([info], test, return_type="dataframe")[0]
            xtr.index, xte.index = train.index, test.index
            train_parts.append(xtr.add_prefix(f"{name}_"))
            test_parts.append(xte.add_prefix(f"{name}_"))
            infos[name] = train_parts[-1].columns.tolist()
    for col in ["approval_month"]:
        levels = sorted(train[col].dropna().unique())
        unseen = set(test[col].dropna().unique()) - set(levels)
        if unseen:
            raise ValueError(f"Held-out {col} levels absent from training: {sorted(unseen)}")
        tr = pd.get_dummies(pd.Categorical(train[col], categories=levels), prefix=col, drop_first=True, dtype=float)
        te = pd.get_dummies(pd.Categorical(test[col], categories=levels), prefix=col, drop_first=True, dtype=float)
        tr.index, te.index = train.index, test.index
        train_parts.append(tr.reindex(columns=te.columns, fill_value=0))
        test_parts.append(te.reindex(columns=tr.columns, fill_value=0))
    if include_type:
        levels = sorted(train["flat_type"].dropna().unique())
        unseen = set(test["flat_type"].dropna().unique()) - set(levels)
        if unseen:
            raise ValueError(f"Held-out flat_type levels absent from training: {sorted(unseen)}")
        tr = pd.get_dummies(pd.Categorical(train["flat_type"], categories=levels), prefix="flat_type", drop_first=True, dtype=float)
        te = pd.get_dummies(pd.Categorical(test["flat_type"], categories=levels), prefix="flat_type", drop_first=True, dtype=float)
        tr.index, te.index = train.index, test.index
        train_parts.append(tr)
        test_parts.append(te.reindex(columns=tr.columns, fill_value=0))
    if include_resale_adjustments:
        for col in ["storey_range"]:
            levels = sorted(train[col].dropna().unique())
            unseen = set(test[col].dropna().unique()) - set(levels)
            if unseen:
                raise ValueError(f"Held-out {col} levels absent from training: {sorted(unseen)}")
            tr = pd.get_dummies(pd.Categorical(train[col], categories=levels), prefix=col, drop_first=True, dtype=float)
            te = pd.get_dummies(pd.Categorical(test[col], categories=levels), prefix=col, drop_first=True, dtype=float)
            tr.index, te.index = train.index, test.index
            train_parts.append(tr)
            test_parts.append(te.reindex(columns=tr.columns, fill_value=0))
    Xtr = pd.concat(train_parts, axis=1).astype(float)
    Xte = pd.concat(test_parts, axis=1).astype(float).reindex(columns=Xtr.columns, fill_value=0)
    Xtr = sm.add_constant(Xtr, has_constant="add")
    Xte = sm.add_constant(Xte, has_constant="add")
    return Xtr, Xte, fallback


def _remaining_lease_months(values: pd.Series) -> pd.Series:
    """Parse HDB lease strings without converting unknown text to zero months."""
    text = values.astype("string").str.strip()
    parts = text.str.extract(
        r"^(?:(\d+)\s+years?)?\s*(?:(\d+)\s+months?)?$",
        flags=0,
        expand=True,
    )
    has_value = parts.notna().any(axis=1)
    years = pd.to_numeric(parts[0], errors="coerce").fillna(0)
    months = pd.to_numeric(parts[1], errors="coerce").fillna(0)
    valid_months = months.between(0, 11)
    parsed = years * 12 + months
    return parsed.where(has_value & valid_months & parsed.gt(0))


def prepare_rental(linked: pd.DataFrame, coordinates: pd.DataFrame) -> pd.DataFrame:
    """Prepare common complete-case rental cohort, without imputing excluded fields."""
    if coordinates["building_id"].duplicated().any():
        raise ValueError("Coordinate crosswalk must be unique by building_id")
    exact_coordinates = coordinates.loc[coordinates["one_map_status"].eq("exact_onemap_address")]
    out = linked.merge(exact_coordinates[["building_id", "x_svy21", "y_svy21"]], on="building_id", how="left", validate="many_to_one")
    if "flat_type" in out.columns:
        out = out.rename(columns={"flat_type": "source_flat_type"})
    out["coord_x"] = pd.to_numeric(out["x_svy21"], errors="coerce")
    out["coord_y"] = pd.to_numeric(out["y_svy21"], errors="coerce")
    out["age"] = out["date"].dt.year - pd.to_numeric(out["year_completed"], errors="coerce")
    out["approval_month"] = out["date"].dt.strftime("%Y-%m")
    eligible = (
        out["date"].ge("2024-01-01") & out["date"].lt("2026-01-01")
        & out["outcome_numeric"].gt(0) & out["link_status"].eq("matched_unique")
        & out["shi_status"].eq("valid") & out["age"].ge(0)
    )
    cols = ["coord_x", "coord_y", "age", "shi", "flat_type_clean", "approval_month", "outcome_numeric", "building_id"]
    finite_coordinates = np.isfinite(out["coord_x"]) & np.isfinite(out["coord_y"])
    return out.loc[eligible & finite_coordinates].dropna(subset=cols).rename(columns={"flat_type_clean": "flat_type", "outcome_numeric": "outcome"}).reset_index(drop=True)


def prepare_resale(linked: pd.DataFrame, coordinates: pd.DataFrame) -> pd.DataFrame:
    """Prepare common complete-case resale cohort for both predeclared pairs."""
    if coordinates["building_id"].duplicated().any():
        raise ValueError("Coordinate crosswalk must be unique by building_id")
    exact_coordinates = coordinates.loc[coordinates["one_map_status"].eq("exact_onemap_address")]
    out = linked.merge(exact_coordinates[["building_id", "x_svy21", "y_svy21"]], on="building_id", how="left", validate="many_to_one")
    if "flat_type" in out.columns:
        out = out.rename(columns={"flat_type": "source_flat_type"})
    out["coord_x"] = pd.to_numeric(out["x_svy21"], errors="coerce")
    out["coord_y"] = pd.to_numeric(out["y_svy21"], errors="coerce")
    out["age"] = out["date"].dt.year - pd.to_numeric(out["year_completed"], errors="coerce")
    out["approval_month"] = out["date"].dt.strftime("%Y-%m")
    out["floor_area_sqm"] = pd.to_numeric(out["floor_area_sqm"], errors="coerce")
    out["remaining_lease_months"] = _remaining_lease_months(out["remaining_lease"])
    eligible = (
        out["date"].ge("2024-01-01") & out["date"].lt("2026-01-01")
        & out["outcome_numeric"].gt(0) & out["link_status"].eq("matched_unique")
        & out["shi_status"].eq("valid") & out["age"].ge(0)
    )
    cols = ["coord_x", "coord_y", "age", "shi", "flat_type_clean", "approval_month", "outcome_numeric",
            "building_id", "floor_area_sqm", "storey_range", "remaining_lease_months"]
    finite_coordinates = np.isfinite(out["coord_x"]) & np.isfinite(out["coord_y"])
    return out.loc[eligible & finite_coordinates].dropna(subset=cols).rename(columns={"flat_type_clean": "flat_type", "outcome_numeric": "outcome"}).reset_index(drop=True)


def fit_predict(train: pd.DataFrame, test: pd.DataFrame, *, include_shi: bool, include_type: bool,
                include_resale_adjustments: bool = False, equal_record_weight: bool = False) -> tuple[np.ndarray, list[str], int, int]:
    Xtr, Xte, fallback = _design(train, test, include_shi=include_shi, include_type=include_type,
                                include_resale_adjustments=include_resale_adjustments)
    if equal_record_weight:
        w = np.ones(len(train), dtype=float)
    else:
        train_n = train.groupby("building_id")["building_id"].transform("size")
        w = 1 / train_n.to_numpy(dtype=float)
    fit = sm.WLS(train["outcome"].astype(float), Xtr, weights=w).fit()
    return np.asarray(fit.predict(Xte)), fallback, int(np.linalg.matrix_rank(Xtr.to_numpy())), int(Xtr.shape[1])


def grouped_folds(data: pd.DataFrame, *, seed: int = 20260908, n_splits: int = 5) -> list[tuple[np.ndarray, np.ndarray]]:
    """Building-grouped folds; every building is assigned wholly to one fold."""
    splitter = GroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    return [(a, b) for a, b in splitter.split(data, groups=data["building_id"])]


def spatial_folds(data: pd.DataFrame, *, seed: int = 20260908, n_clusters: int = 5) -> tuple[list[tuple[np.ndarray, np.ndarray]], pd.DataFrame]:
    buildings = data[["building_id", "coord_x", "coord_y"]].drop_duplicates("building_id").reset_index(drop=True)
    km = KMeans(n_clusters=n_clusters, random_state=seed, n_init=20).fit(buildings[["coord_x", "coord_y"]])
    buildings["spatial_group"] = km.labels_
    group_map = buildings.set_index("building_id")["spatial_group"]
    groups = data["building_id"].map(group_map).to_numpy()
    all_rows = np.arange(len(data))
    folds = [(all_rows[groups != group], all_rows[groups == group]) for group in range(n_clusters)]
    return folds, buildings
