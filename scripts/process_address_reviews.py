"""Compare a five-column, single-reviewer HDB visual audit with a separate backend.

Blank answers are not reviews. Unable to determine is a response but is excluded
from determinate agreement. This script never changes housing data or asserts
that a particular image was inspected. Notes are optional.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import argparse, csv, hashlib, json, re, shutil

HEADERS = ['Case ID', 'Building address', 'Google Street View link', 'Is this an HDB building?', 'Notes']
LABELS = ('Yes', 'No', 'Unable to determine')
ALIASES = dict(zip(HEADERS, ['case_id', 'source_address', 'review_link', 'is_hdb', 'notes']))

def text(row, key):
    return str(row.get(key, '') or '').strip()

def index(rows):
    indexed = {}
    for row in rows:
        cid = text(row, 'case_id')
        if not cid:
            if any(text(row, k) for k in ('is_hdb', 'notes')):
                raise ValueError('An entered response is missing its Case ID')
            continue
        if cid in indexed:
            raise ValueError('Duplicate case_id: ' + cid)
        indexed[cid] = row
    return indexed

def summarize(cases, reviews=(), location_resolutions=()):
    backend, responses = index(cases), index(reviews)
    resolved = index(location_resolutions)
    for cid, decision in resolved.items():
        if cid not in backend or text(decision, "building_id") != text(backend[cid], "building_id"):
            raise ValueError("Location decision does not identify the prepared building: " + cid)
        if text(decision, "location_resolution_status") != "resolved_documented_address_point":
            raise ValueError("Unsupported location resolution status for " + cid)
        if not all(text(decision, k) for k in ("selected_postal_code", "decision_reason", "corroborating_source_url", "onemap_snapshot_sha256")):
            raise ValueError("Location resolution lacks evidence for " + cid)
    if not backend or len(backend) > 30:
        raise ValueError('Backend must contain 1–30 prepared cases')
    for cid, row in responses.items():
        if cid not in backend:
            raise ValueError('Unprepared case: ' + cid)
        if text(row, 'source_address') != text(backend[cid], 'source_address'):
            raise ValueError('Changed building address for ' + cid)
        if text(row, 'is_hdb') and text(row, 'is_hdb') not in LABELS:
            raise ValueError('Invalid dropdown response for ' + cid)
    counts, results, investigation = Counter(), [], []
    agreements = discrepancies = comparable = 0
    for cid, source in backend.items():
        row = responses.get(cid, {})
        answer, algorithm = text(row, 'is_hdb'), text(source, 'algorithm_hdb_classification')
        reason = []
        if not answer:
            outcome = 'not reviewed'
            reason.append('manual review pending')
        else:
            counts[answer] += 1
            if answer == 'Unable to determine':
                outcome = 'indeterminate'
                reason.append('reviewer unable to determine HDB classification')
            elif algorithm not in ('Yes', 'No'):
                outcome = 'algorithm classification unavailable'
                reason.append('backend algorithm classification unavailable; no forced comparison')
            else:
                comparable += 1
                outcome = 'agreement' if answer == algorithm else 'discrepancy'
                agreements += int(outcome == 'agreement')
                discrepancies += int(outcome == 'discrepancy')
                if outcome == 'discrepancy':
                    reason.append('reviewer and algorithm classifications differ')
            if text(row, 'notes'):
                reason.append('reviewer notes supplied; check whether follow-up is needed')
            if text(source, 'link_requires_manual_location_check').lower() in ('true', 'yes', '1') and cid not in resolved:
                reason.append('location ambiguous in saved geocoding; HDB appearance alone does not resolve identity')
        result = {'case_id': cid, 'building_address': text(source, 'source_address'),
                  'reviewer_response': answer or 'not reviewed', 'algorithm_classification': algorithm,
                  'comparison': outcome, 'notes': text(row, 'notes'),
                  'investigation_reason': '; '.join(reason), 'building_id': text(source, 'building_id'), 'source_record_id': text(source, 'source_record_id'), 'official_evidence_reference': text(source, 'official_evidence_reference'), 'link_location_status': text(source, 'link_location_status')}
        results.append(result)
        if reason:
            investigation.append(result)
    reviewed = sum(counts.values())
    return {'prepared_cases': len(backend), 'number_buildings_reviewed': reviewed,
            'number_confirmed_as_hdb_by_reviewer': counts['Yes'],
            'number_identified_as_non_hdb_by_reviewer': counts['No'],
            'number_unable_to_determine': counts['Unable to determine'],
            'number_awaiting_review': len(backend) - reviewed,
            'agreement_comparison_denominator': comparable,
            'number_agreements': agreements, 'number_discrepancies': discrepancies,
            'agreement_proportion_among_comparable_responses': agreements / comparable if comparable else None,
            'number_cases_requiring_follow_up_including_pending': len(investigation),
            'number_saved_location_ambiguities_for_follow_up': sum('location ambiguous in saved geocoding' in r['investigation_reason'] for r in investigation),
            'number_original_saved_location_flags': sum(text(r, 'link_requires_manual_location_check').lower() in ('true','yes','1') for r in backend.values()),
            'number_documented_location_resolutions': len(resolved),
            'dataset_corrections_applied': 0, 'case_results': results,
            'cases_requiring_further_investigation': investigation,
            'scope': 'Single-reviewer targeted housing-classification audit using Street View and supplementary property websites as reported by the reviewer. Responses are recorded human assessments, not independent proof of image inspection. Agreement is not nationwide accuracy, address-linkage validation, SHI validation or verification of internal flat composition.'}

def read(path):
    path = Path(path)
    if path.suffix.lower() == '.xlsx':
        from openpyxl import load_workbook
        workbook = load_workbook(path, read_only=True, data_only=True)
        if workbook.sheetnames != ['HDB Review']:
            workbook.close()
            raise ValueError('Use the five-column HDB Review workbook')
        values = list(workbook['HDB Review'].values)
        workbook.close()
        if not values or list(values[0]) != HEADERS:
            raise ValueError('Keep the original five column headers')
        raw = [dict(zip(HEADERS, row)) for row in values[1:] if any(v is not None for v in row)]
    else:
        with path.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            if not ({'case_id', 'Case ID'} & set(reader.fieldnames or [])):
                raise ValueError('Input must retain Case ID or case_id header')
            raw = list(reader)
    return [{ALIASES.get(k, k): v for k, v in row.items()} for row in raw]

def results_paragraph(result):
    n = result['number_buildings_reviewed']
    if not n:
        return (f"A targeted sample of {result['prepared_cases']} buildings was prepared for a single-reviewer visual audit of HDB building classification. No completed reviewer responses were recorded; all cases awaited review. Agreement and discrepancy findings were therefore not available, and no dataset correction was made from this audit. Automated address/coordinate checks and prepared navigation links do not establish completed image inspection. Additional file 7 records the pending case status.")
    return (f"The sole reviewer recorded responses for {n} of {result['prepared_cases']} targeted buildings: {result['number_confirmed_as_hdb_by_reviewer']} were classified as HDB, {result['number_identified_as_non_hdb_by_reviewer']} as non-HDB and {result['number_unable_to_determine']} could not be determined. Among {result['agreement_comparison_denominator']} determinate responses with an available algorithm classification, {result['number_agreements']} agreed and {result['number_discrepancies']} differed. Indeterminate and unreviewed cases were excluded from that comparison; {result['number_awaiting_review']} cases remained unreviewed. The saved geocoding initially flagged {result['number_original_saved_location_flags']} cases; {result['number_documented_location_resolutions']} were subsequently resolved by documented cross-source address-point review, leaving {result['number_saved_location_ambiguities_for_follow_up']} unresolved location flags and {result['number_cases_requiring_follow_up_including_pending']} follow-up cases. The reviewer confirmed using supplementary property websites, including PropertyGuru, where Street View was unavailable or insufficient; case-specific website use was not recorded. These location flags do not constitute classification disagreements, and no SHI scores or frozen analysis coordinates were changed. These results describe a targeted single-reviewer classification audit, not nationwide accuracy, address-linkage accuracy, SHI validity or internal dwelling composition. Detailed recorded responses are provided in Additional file 7.")

def update_manuscript(path, result):
    source = path.read_text()
    pattern = r'(?ms)^### HDB building classification visual audit status\n.*?(?=^### |^## |\Z)'
    replacement = '### HDB building classification visual audit status\n\n' + results_paragraph(result) + '\n\n'
    updated, count = re.subn(pattern, lambda match: replacement, source)
    if count != 1:
        raise ValueError('Expected exactly one HDB audit Results subsection; manuscript unchanged')
    if source != updated:
        backup = path.with_name(path.name + '.before_visual_audit_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.bak')
        shutil.copy2(path, backup)
        path.write_text(updated)

def default_location_resolutions():
    root = Path(__file__).resolve().parents[1]
    candidates = [root/"validation_cases/location_resolution/location_resolutions.csv", root/"../Validation/Address_Review/Technical_Location_Resolution__2026-10-17/location_resolutions.csv"]
    return next((p for p in candidates if p.exists()), None)

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', required=True, type=Path)
    parser.add_argument('--review', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--location-resolutions', type=Path, default=default_location_resolutions())
    parser.add_argument('--manuscript', type=Path, help='Optionally replace the dedicated Results subsection from actual responses, preserving a backup')
    args = parser.parse_args(argv)
    result = summarize(read(args.backend), read(args.review), read(args.location_resolutions) if args.location_resolutions else [])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name in ('case_results', 'cases_requiring_further_investigation'):
        with (args.output_dir / (name + '.csv')).open('w', newline='', encoding='utf-8') as stream:
            fields = ['case_id', 'building_address', 'reviewer_response', 'algorithm_classification', 'comparison', 'notes', 'investigation_reason', 'building_id', 'source_record_id', 'official_evidence_reference', 'link_location_status']
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(result[name])
    summary = {k: v for k, v in result.items() if k not in ('case_results', 'cases_requiring_further_investigation')}
    (args.output_dir / 'review_summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    (args.output_dir / 'manuscript_results.md').write_text(results_paragraph(result) + '\n')
    audit = {'processed_at_utc': datetime.now(timezone.utc).isoformat(), 'timestamp_scope': 'processing time, not actual review or imagery date',
             'review_file_sha256': hashlib.sha256(args.review.read_bytes()).hexdigest(),
             'backend_sha256': hashlib.sha256(args.backend.read_bytes()).hexdigest(),
             'review_record_count': result['number_buildings_reviewed'], 'reviewer_role': 'sole human reviewer per protocol; not independently attested by software'}
    (args.output_dir / ('processing_audit_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')).write_text(json.dumps(audit, indent=2) + '\n')
    if args.manuscript:
        update_manuscript(args.manuscript, result)
    print(json.dumps(summary, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
