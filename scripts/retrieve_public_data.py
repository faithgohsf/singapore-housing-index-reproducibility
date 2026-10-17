"""Download the public source snapshots used by the SHI pipeline.

By default, valid files already in data/raw are reused. Pass --refresh to
retrieve the current public versions; that changes the study vintage.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
import time

import requests

PROJECT = pathlib.Path(__file__).resolve().parents[1]
RAW = PROJECT / "data" / "raw"
MANIFESTS = RAW / "source_manifests"
DATASETS = {
    "hdb_property_information__2026-10-08.csv": "d_17f5382f26140b1fdae0ba2ef6239d2f",
    "hdb_rental_approval__retrieved_2026-10-16.csv": "d_c9f57187485a850908655db0e8cfe651",
    "hdb_resale_flat_prices__retrieved_2026-10-16.csv": "d_8b84c4ee58e3cfc0ece0d773c8ca6abc",
}
REQUIRED_COLUMNS = {
    "hdb_property_information__2026-10-08.csv": {
        "blk_no", "street", "residential", "total_dwelling_units", "1room_sold", "2room_sold",
        "3room_sold", "4room_sold", "5room_sold", "exec_sold", "multigen_sold",
        "studio_apartment_sold", "1room_rental", "2room_rental", "3room_rental", "other_room_rental",
    },
    "hdb_rental_approval__retrieved_2026-10-16.csv": {
        "rent_approval_date", "town", "block", "street_name", "flat_type", "monthly_rent",
    },
    "hdb_resale_flat_prices__retrieved_2026-10-16.csv": {
        "month", "town", "flat_type", "block", "street_name", "storey_range", "floor_area_sqm",
        "lease_commence_date", "remaining_lease", "resale_price",
    },
    "mendeley_shi_dataset_v1__data_in_brief.csv": {
        "Postal Code", "Block Number", "Street Name", "Housing Index",
    },
}
MENDELEY_FILE = "mendeley_shi_dataset_v1__data_in_brief.csv"
MENDELEY_API = "https://data.mendeley.com/api/datasets/pj3dkvskr9/files"


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_csv_snapshot(
    path: pathlib.Path,
    filename: str,
    *,
    expected_bytes: int | None = None,
) -> int:
    """Validate downloaded/saved CSV schema, nonempty records and byte count."""
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"Source file is missing or empty: {path}")
    if expected_bytes is not None and path.stat().st_size != expected_bytes:
        raise ValueError(
            f"Truncated or size-mismatched source file {filename}: "
            f"expected {expected_bytes} bytes, found {path.stat().st_size}"
        )
    required = REQUIRED_COLUMNS.get(filename)
    if required is None:
        raise ValueError(f"No required-column contract is defined for {filename}")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError(f"Source file has no header: {filename}") from exc
        missing = sorted(required - set(header))
        if missing:
            raise ValueError(f"Source file {filename} is missing required columns: {missing}")
        row_count = sum(1 for row in reader if row and any(value.strip() for value in row))
    if row_count == 0:
        raise ValueError(f"Source file {filename} has no data rows")
    return row_count


def _download_data_gov(dataset_id: str, target: pathlib.Path) -> dict:
    base = "https://api-open.data.gov.sg/v1/public/api/datasets/" + dataset_id
    session = requests.Session()
    response = session.get(base + "/initiate-download", timeout=60)
    response.raise_for_status()
    deadline = time.monotonic() + 180
    while True:
        response = session.get(base + "/poll-download", timeout=60)
        response.raise_for_status()
        body = response.json()
        data = body.get("data", {})
        url = data.get("url")
        if url:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Timed out waiting for data.gov.sg dataset {dataset_id}")
        time.sleep(3)
    response = session.get(url, timeout=180, stream=True)
    response.raise_for_status()
    temporary = target.with_suffix(target.suffix + ".part")
    byte_count = 0
    with temporary.open("wb") as stream:
        for chunk in response.iter_content(1024 * 1024):
            if chunk:
                stream.write(chunk)
                byte_count += len(chunk)
    content_length = response.headers.get("Content-Length")
    if content_length and response.headers.get("Content-Encoding", "identity").lower() == "identity":
        if byte_count != int(content_length):
            temporary.unlink(missing_ok=True)
            raise ValueError(f"Truncated data.gov.sg response: expected {content_length} bytes, received {byte_count}")
    try:
        row_count = validate_csv_snapshot(temporary, target.name)
    except (OSError, ValueError):
        temporary.unlink(missing_ok=True)
        raise
    temporary.replace(target)
    return {"dataset_id": dataset_id, "source_url": f"https://data.gov.sg/datasets/{dataset_id}/view", "row_count": row_count}


def _download_mendeley(target: pathlib.Path) -> dict:
    response = requests.get(MENDELEY_API, timeout=60)
    response.raise_for_status()
    payload = response.json()
    files = payload if isinstance(payload, list) else payload.get("files", [])
    item = next((f for f in files if f.get("filename", "").lower() == "data in brief.csv"), None)
    if not item:
        raise RuntimeError("Mendeley Data v1 did not return the expected 'data in brief.csv' file")
    # Current Mendeley metadata nests its actual download URL in content_details.
    # Do not invent an endpoint from a file ID: the former /file fallback is 404.
    details = item.get("content_details") or {}
    url = details.get("download_url") or item.get("download_url") or item.get("downloadUrl") or item.get("url")
    if not url:
        raise RuntimeError("Mendeley file metadata did not include a usable public download URL")
    response = requests.get(url, timeout=180, stream=True)
    response.raise_for_status()
    temporary = target.with_suffix(target.suffix + ".part")
    byte_count = 0
    with temporary.open("wb") as stream:
        for chunk in response.iter_content(1024 * 1024):
            if chunk:
                stream.write(chunk)
                byte_count += len(chunk)
    content_length = response.headers.get("Content-Length")
    if content_length and response.headers.get("Content-Encoding", "identity").lower() == "identity":
        if byte_count != int(content_length):
            temporary.unlink(missing_ok=True)
            raise ValueError(f"Truncated Mendeley response: expected {content_length} bytes, received {byte_count}")
    try:
        row_count = validate_csv_snapshot(temporary, target.name)
    except (OSError, ValueError):
        temporary.unlink(missing_ok=True)
        raise
    temporary.replace(target)
    return {"dataset_doi": "10.17632/pj3dkvskr9.1", "source_url": MENDELEY_API,
            "filename": item.get("filename"), "file_id": item.get("id"), "row_count": row_count}


def snapshot_expectations(manifest: dict, filename: str) -> tuple[str | None, int | None]:
    """Read checksums/bytes from both dataset and nested Mendeley manifests."""
    item = manifest
    if isinstance(manifest.get("files"), list):
        item = next((f for f in manifest["files"] if f.get("filename") == "data in brief.csv"), {})
    checksum = item.get("sha256") or item.get("downloaded_sha256") or item.get("sha256_hash")
    size = item.get("bytes") or item.get("download_size_bytes") or item.get("size")
    return checksum, size


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Download current source versions; updates the data vintage.")
    args = parser.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    MANIFESTS.mkdir(parents=True, exist_ok=True)
    sources = {**DATASETS, MENDELEY_FILE: None}
    for filename, dataset_id in sources.items():
        target = RAW / filename
        manifest_name = ("mendeley_shi_dataset_v1_files.json" if dataset_id is None
                         else filename.removesuffix(".csv") + ".json")
        manifest_path = MANIFESTS / manifest_name
        old_manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
        if target.exists() and not args.refresh:
            expected, expected_bytes = snapshot_expectations(old_manifest, filename)
            actual = sha256(target)
            if expected and actual != expected:
                raise SystemExit(f"Source checksum mismatch for {target}. Restore the saved input from its source manifest before running the study.")
            try:
                validate_csv_snapshot(target, filename, expected_bytes=expected_bytes)
            except (OSError, ValueError) as exc:
                raise SystemExit(f"Saved source validation failed for {target}: {exc}") from exc
            print(f"Using saved source: {target.relative_to(PROJECT)}")
            continue
        print(f"Retrieving {filename} ...", flush=True)
        details = _download_mendeley(target) if dataset_id is None else _download_data_gov(dataset_id, target)
        manifest = {**details, "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "filename": filename, "bytes": target.stat().st_size, "sha256": sha256(target),
                    "retrieval_mode": "downloaded_missing_source"}
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"Saved {target.relative_to(PROJECT)} ({manifest['bytes']:,} bytes)")


if __name__ == "__main__":
    try:
        main()
    except (requests.RequestException, RuntimeError, ValueError, OSError) as exc:
        raise SystemExit(f"Public data retrieval failed: {exc}") from exc
