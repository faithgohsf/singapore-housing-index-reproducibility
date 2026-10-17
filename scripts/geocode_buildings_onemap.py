"""Resolve current HDB building coordinates using OneMap; never stores the token."""
from __future__ import annotations

import os
import pathlib
import sys
import json
import hashlib
import getpass
import time

import pandas as pd
import requests

PROJECT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from shi.reconstruction import normalize_address_key  # noqa: E402

SEARCH_URL = "https://www.onemap.gov.sg/api/common/elastic/search"


def search_candidates(session: requests.Session, search_value: str, token: str, *, timeout: int = 30) -> list[dict]:
    """Fetch all OneMap search pages so a unique match is not inferred from page 1."""
    candidates: list[dict] = []
    page = 1
    last_page: int | None = None
    while last_page is None or page <= last_page:
        for retry in range(5):
            response = session.get(
                SEARCH_URL,
                params={"searchVal": search_value, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": page},
                headers={"Authorization": token}, timeout=timeout,
            )
            if response.status_code in (401, 403):
                raise PermissionError("OneMap rejected the token. Refresh it and rerun; no token was logged.")
            if response.status_code == 429 or response.status_code >= 500:
                time.sleep(2 * (retry + 1))
                continue
            response.raise_for_status()
            break
        else:
            response.raise_for_status()
        body = response.json()
        if body.get("error"):
            raise PermissionError("OneMap returned an API error; refusing an authenticated match decision. Refresh the token; no token was logged.")
        page_results = body.get("results")
        if not isinstance(page_results, list):
            raise ValueError(f"OneMap page {page} did not contain a results list")
        candidates.extend(page_results)
        total_pages = body.get("totalNumPages")
        if total_pages is not None:
            try:
                last_page = int(total_pages)
            except (TypeError, ValueError) as exc:
                raise ValueError("OneMap returned an invalid totalNumPages value") from exc
            if last_page == 0 and not page_results:
                break
            if last_page < page:
                raise ValueError("OneMap totalNumPages is smaller than the requested page")
        elif not page_results:
            break
        elif len(page_results) < 10:
            # Older responses may omit totalNumPages. A short page is then the
            # only safe end marker; a full page without metadata is incomplete.
            break
        else:
            raise ValueError("OneMap omitted totalNumPages for a full result page; refusing an incomplete match decision")
        page += 1
    return candidates


def main() -> None:
    token = os.environ.get("ONEMAP_TOKEN")
    if not token:
        email = input("OneMap registered email: ")
        password = getpass.getpass("OneMap password (input is hidden): ")
        auth = requests.post("https://www.onemap.gov.sg/api/auth/post/getToken", json={"email": email, "password": password}, timeout=30)
        auth.raise_for_status()
        token = auth.json()["access_token"]
        del password, email
    buildings = pd.read_csv(PROJECT / "outputs/tables/hdb_buildings__current_2026-10-08.csv", dtype={"blk_no": "string"})
    out = PROJECT / "outputs/tables/one_map_coordinates__2026-10-16.csv"
    cache = {r["building_id"]: r for r in pd.read_csv(out).to_dict("records") if not str(r.get("one_map_status", "")).startswith("request_error")} if out.exists() else {}
    input_hash = hashlib.sha256((PROJECT / "data/raw/hdb_property_information__2026-10-08.csv").read_bytes()).hexdigest()
    rows = []
    session = requests.Session()
    for pos, row in enumerate(buildings.itertuples(index=False), start=1):
        if row.building_id in cache:
            rows.append(cache[row.building_id])
            continue
        try:
            candidates = search_candidates(session, f"{row.blk_no} {row.street}", token)
            exact = [c for c in candidates if normalize_address_key(c.get("BLK_NO"), c.get("ROAD_NAME")) == row.address_key]
            status = "exact_onemap_address" if len(exact) == 1 else "no_exact_candidate" if not exact else "multiple_exact_candidates"
            selected = exact[0] if len(exact) == 1 else {}
            rows.append({
                "building_id": row.building_id, "address_key": row.address_key,
                "one_map_status": status, "candidate_count": len(candidates), "exact_candidate_count": len(exact),
                "one_map_address": selected.get("ADDRESS", ""),
                "postal_code": selected.get("POSTAL", ""),
                "x_svy21": selected.get("X", ""), "y_svy21": selected.get("Y", ""),
                "latitude": selected.get("LATITUDE", ""), "longitude": selected.get("LONGITUDE", ""),
            })
        except requests.RequestException as exc:
            rows.append({"building_id": row.building_id, "address_key": row.address_key, "one_map_status": f"request_error:{type(exc).__name__}", "candidate_count": 0, "exact_candidate_count": 0})
        except PermissionError as exc:
            raise SystemExit(str(exc)) from exc
        if pos % 50 == 0:
            pd.DataFrame(rows).to_csv(out, index=False)
            print(f"Processed {pos}/{len(buildings)} buildings; checkpoint saved.", flush=True)
            time.sleep(1.0)
        else:
            time.sleep(0.15)
    pd.DataFrame(rows).to_csv(out, index=False)
    (PROJECT / "outputs/tables/one_map_coordinates__2026-10-16_manifest.json").write_text(json.dumps({
        "retrieval_date": "2026-10-16", "provider": "Singapore Land Authority OneMap Search API",
        "source_property_sha256": input_hash, "buildings_requested": len(buildings),
        "token_stored": False, "file": out.name,
    }, indent=2) + "\n")
    counts = pd.Series([x["one_map_status"] for x in rows]).value_counts(dropna=False).to_dict()
    print({"buildings": len(rows), "statuses": counts, "coordinates_file": str(out)})


if __name__ == "__main__":
    main()
