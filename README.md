# Singapore Housing Index reproducibility release candidate

**Authoritative SHI research repository.** Use this repository for all future code and reproducibility updates. The private `singapore-housing-index-validation` repository is a redundant README-only scaffold retained for history. See [repository authority and comparison](docs/REPOSITORY_AUTHORITY.md). Both repositories remain private; no public release is authorised.

Version 0.1.0-rc.3-executive6. This is a standalone candidate repository, separate from the development workspace. Original project code is MIT licensed by user approval on 17 October 2026. No public software release or Zenodo DOI exists yet. Do not describe this candidate as a published repository.

## Setup

Verified with Python 3.14.6 and pinned dependencies; other versions are not independently verified.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e . --no-deps
python -m pytest -q --ignore=tests/test_release_artifacts.py
```

## Exact frozen-input reproduction

Extract the included `inputs/SHI_Frozen_Inputs__0.1.0-rc.1.zip` into this repository root:

```bash
python -m zipfile -e inputs/SHI_Frozen_Inputs__0.1.0-rc.1.zip .
```

 It contains the exact HDB inputs and saved OneMap address/coordinate responses, with attribution and checksums. Obtain the Mendeley v1 CSV from DOI 10.17632/pj3dkvskr9.1, save it to the path in frozen_inputs.json and verify its checksum. This mixed-source file is not bundled; see THIRD_PARTY_DATA.md. A current download with a different checksum cannot substitute for the archived input. No public archive URL or DOI has been issued. The included archive is checksum-pinned and needs no Desktop-folder access.
```bash
python scripts/retrieve_public_data.py  # obtains missing Mendeley source; existing HDB snapshots are preserved
python scripts/run_pipeline.py --profile reproducibility
python -m pytest -q
python scripts/independent_final_audit.py
```

The main command verifies frozen input hashes before all other stages and stops on failure. It reconstructs SHI, performs the comparison with the selected public historical SHI dataset, checks coordinates, links rental/resale records, produces building descriptives, fits grouped rental/resale models and sensitivities, exports machine-readable tables and checks their integrity. The repository profile omits one internal workbook-presence check; all machine-readable integrity checks remain active. Outputs are created in `outputs/tables/` and `outputs/figures/`.

The staged coordinate file avoids new API calls. Only a coordinate refresh needs `ONEMAP_TOKEN` in the environment. Never commit tokens or `.env` files. The original notebook is not required to run this corrected reconstruction; its saved counts and the unreproduced original-vintage benchmark are documented separately in the study.

## Released data and scope

`release_data/` contains an HDB-only building-composition/SHI dataset, a distinct historical postal crosswalk, dictionary and source manifest. Leading-zero postal strings must be read as text (`dtype=str` for postal fields). These files do not include OneMap coordinate-return fields. Missing market records do not indicate absence of activity. Building coverage is not resident coverage. SHI is not individual income, deprivation or validated socioeconomic confounding control.

The compressed input archive contains the permitted frozen HDB source rows and saved OneMap coordinates. Raw mixed-source Mendeley data, model predictions, reviewer identities, private notes, full-text articles and personal environment files are excluded. The pipeline recreates analytical outputs after authorised input staging. Data terms and attribution are in `THIRD_PARTY_DATA.md`; the MIT code licence is in `LICENSE`. No original-2018-comparator recovery is claimed.

The curated literature seed is a structured evidence map with unresolved records, not a complete systematic review. Source metadata and classifications are included; full-text bodies and long excerpts are omitted. Exact snapshot verification and independent portability checks are recorded outside this release in the study verification report.

## Verify manuscript numbers and address-review status

After the pipeline, run `python scripts/verify_reference_results.py`. It compares reconstructed counts, descriptive summaries, model comparisons and uncertainty intervals against the supplied numeric benchmark using explicit numerical tolerances. `reference_results.json` identifies the source output and JSON pointer for every checked value. An agreement check is not evidence that the original 2018 inputs or human Street View review were recovered.

`docs/address_validation_protocol.md`, `validation_cases/prepared_cases.csv` and `validation_cases/validation_status.json` document the 30 prepared cases and their completed single-reviewer HDB classification responses. Run `python scripts/audit_address_validation.py` for the supplied completed coded-response record, or provide `--reviews` for a completed five-column HDB audit form. The script audits documented fields; it does not inspect imagery. No proposed-match key, reviewer identity or image is included.

The GitHub Actions workflow is configured for procedural tests only; full model reproduction is a separate recorded check. Full-output tests and manuscript-number checks require authorised frozen inputs and the local reproduction pipeline. GitHub/Zenodo publication and persistent exact-input archive links remain pending. See docs/private_release_and_zenodo.md. Do not replace the original-method DOI with this candidate's unassigned software identifier.


## Single-reviewer HDB visual audit

The active reviewer template is validation_cases/HDB_Visual_Audit_Blank.csv, with five columns only: Case ID, Building address, Google Street View link, Is this an HDB building?, Notes. The workspace XLSX provides Yes/No/Unable to determine choices. Algorithm classifications are in a separate backend; do not inspect it before the human form is complete. Thirty recorded sole-reviewer responses are supplied separately in validation_cases/completed_hdb_classification_responses.csv; the blank template remains separate for reuse.

```bash
python scripts/process_address_reviews.py --backend validation_cases/backend/HDB_Visual_Audit_Backend.csv --review validation_cases/completed_hdb_classification_responses.csv --output-dir review_records
```

CSV needs no optional Excel package. For completed XLSX files install requirements-review.txt. The script reports actual responses, HDB/non-HDB/uncertain counts, determinate agreements/discrepancies and follow-up cases. Input hashes and processing timestamps are generated automatically. It does not independently attest imagery use or change source data. See docs/review_workflow.md.

## Private repository and release status

The user authorises PRIVATE upload to https://github.com/fattygohwhere/singapore-housing-index-reproducibility. This is not a publicly accessible release. Never change visibility, create a public release or publish a Zenodo record without a future explicit user instruction. MIT is approved for original code; source datasets retain their separate terms.

All seven original targeted location flags have documented address-point resolutions in validation_cases/location_resolution/. They do not change frozen coordinates, the published model sample or historical-score conflicts. The completed reviewer used Street View and supplementary property websites including PropertyGuru; case-specific site-use logs were not collected. No repeat manual classification is required.


## Executive-flat correction (18 October 2026)

The primary published-definition reconstruction assigns `exec_sold` weight 6, ordinary `5room_sold` weight 5, and `multigen_sold` weight 6. The previous executive=5 mapping is retained as a named sensitivity, not selected according to model performance. See `docs/EXECUTIVE_WEIGHT_CORRECTION.md`.

To reproduce that alternative, use a **separate copy** of the repository and frozen inputs, then run `python scripts/run_pipeline.py --profile reproducibility --executive-weight 5`. This produces outputs in that separate copy and preserves primary results. All other procedures and inputs remain fixed.
