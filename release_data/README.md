# Prepared release datasets

- `building_level_shi__hdb_only__2026-10-08.csv`: one row per current residential HDB building, complete composition/SHI and source-quality fields. OneMap returned fields are excluded.
- `postal_crosswalk__mendeley_v1.csv`: separate one-to-many historical postal mapping, with explicit ambiguity/unmatched status. Candidate source is Mendeley v1, declared 2020 update, not verified as the 2018 comparator. Read postal fields as text.
- `data_dictionary.csv`: definitions for these two datasets; source URLs, provenance and source-defined limitations accompany the release.
- `source_manifest.csv`: required frozen input sources, retrieval versions, byte counts and checksums. Large raw inputs and the OneMap coordinate snapshot are not bundled.

These files are prepared for release under their recorded source terms and attribution; author/institutional approval and persistent deposition remain pending. HDB-only composition coverage is not resident coverage or individual socioeconomic validity. See `../THIRD_PARTY_DATA.md` for attribution and terms.
