# Single reviewer targeted housing classification audit

## Objective and sample

Assess HDB/non-HDB classification of 30 purposively selected algorithm-positive buildings. Selection priorities: nine transaction/composition triggers, one rental-category-only building with an observed approval, four historical-conflict/multiple-postal cases, and sixteen large remaining historical SHI differences. These triggers are not confirmed errors and are not a probability sample.

## Completed human procedure

One human reviewer completed the five-column sheet: Case ID, address, Google Street View link, Yes/No/Unable to determine, optional notes. Algorithm labels and technical records were withheld in a separate backend where feasible; prior familiarity and navigation cues prevent guaranteed full blinding. The reviewer confirms using supplementary property websites, including PropertyGuru, where Street View was unavailable or insufficient. These are valid housing-classification assessments; lack of Street View alone does not invalidate them. No case-specific website-use log, observation date or imagery date was collected, so no building-specific claim about which website or image the reviewer used is made. External property records may be outdated and are not authoritative evidence of internal dwelling composition.

## Recorded findings

The preserved workbook contains 30 responses, all HDB. There were zero non-HDB or indeterminate responses, 30 agreements among 30 comparable determinate answers, zero classification discrepancies and zero unreviewed cases. The workbook is retained unchanged with its checksum. Automated matching and generated links are not counted as human review. No second reviewer, inter-rater reliability or adjudication is claimed.

## Separate technical location review

Seven original multi-candidate OneMap flags were examined individually after the human form was completed. Exact block/street candidates, postal codes and named developments were compared with frozen HDB residential records and independent corroborating sources. Three cases had POI duplicates within the same development; four had distinct properties sharing a number and street. All seven now have documented selected address points and postcodes; none requires another human classification response. These are provider address points, not surveyed centroids or verified panorama positions. Additional file 7 records the selected points, rationale and source URLs.

OneMap HTTP 200 responses returned candidate records together with a missing-token warning. The raw results and warning are preserved; successful authenticated access is not claimed. An apostrophe-preserving search was required for Queen's Road. All candidates were retained; the first result was never selected automatically.

This post-analysis location addendum does not overwrite the frozen 16 October coordinate snapshot, alter the model-eligibility counts or resolve conflicts in historical SHI scores. Four same-address historical conflicts remain excluded from historical agreement. No SHI/composition correction arose from the classification audit. A future refreshed analysis would require a separately versioned coordinate source and full rerun; no such refresh is presented as the original frozen analysis.

## Recalculation

From the documented code root, run:
python scripts/process_address_reviews.py --backend ../Validation/Address_Review/backend/HDB_Visual_Audit_Backend.csv --review ../Validation/Address_Review/HDB_Visual_Audit.xlsx --output-dir ../Validation/Address_Review/Processed_Results

The standalone repository uses validation_cases/completed_hdb_classification_responses.csv and validation_cases/backend/HDB_Visual_Audit_Backend.csv. The processor automatically reads the documented location-resolution ledger, validates matching case/building IDs and required evidence fields, and reports original flags, completed resolutions and residual follow-up separately. It never modifies frozen analysis data. The backend retains original navigation uncertainty as historical metadata alongside current status.

## Limits

Single-reviewer interpretation, residual confirmation bias, purposive positive-case selection, unavailable/outdated/obscured imagery, incomplete site-use logs and potentially outdated property websites limit interpretation. Agreement does not establish specificity, nationwide linkage accuracy, SHI validity, internal composition or individual socioeconomic status. All sources and exact case decisions are retained in the technical location-resolution ledger.
