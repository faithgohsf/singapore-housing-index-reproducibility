"""Verify documented post-analysis location decisions against retained OneMap payloads.

This validates the recorded decision trail, not surveyed geometry or independent
human image inspection. Frozen analysis coordinates are never overwritten.
"""
from pathlib import Path
import csv,hashlib,json,math,argparse,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from shi.reconstruction import normalize_address_key
from process_address_reviews import default_location_resolutions

def verify(ledger):
    ledger=Path(ledger)
    with ledger.open(newline='') as f:rows=list(csv.DictReader(f))
    seen=set()
    for row in rows:
        if row['case_id'] in seen:raise ValueError('Duplicate case in location ledger')
        seen.add(row['case_id'])
        source=ledger.parent/row['onemap_snapshot']
        if hashlib.sha256(source.read_bytes()).hexdigest()!=row['onemap_snapshot_sha256']:raise ValueError('Location snapshot checksum mismatch')
        payload=json.loads(source.read_text())
        if payload['http_status']!=200 or payload['body']['totalNumPages']!=1:raise ValueError('Incomplete source candidate payload')
        selected=[c for c in payload['body']['results'] if c.get('ADDRESS')==row['selected_onemap_address'] and c.get('POSTAL')==row['selected_postal_code']]
        if len(selected)!=1:raise ValueError('Selected address is not unique in retained source')
        c=selected[0]
        if normalize_address_key(c['BLK_NO'],c['ROAD_NAME'])!=normalize_address_key('',row['building_address'].replace(', Singapore','')):raise ValueError('Selected block/street mismatch')
        for key,source_key in [('latitude','LATITUDE'),('longitude','LONGITUDE'),('x_svy21','X'),('y_svy21','Y')]:
            if not math.isfinite(float(row[key])) or float(row[key])!=float(c[source_key]):raise ValueError('Recorded point differs from source')
        if row['frozen_analysis_coordinates_changed']!='False' or row['historical_score_conflicts_changed']!='False':raise ValueError('Unexpected frozen-data modification')
        if not row['corroborating_source_url'] or not row['decision_reason']:raise ValueError('Missing corroboration')
    return {'documented_cases_checked':len(rows),'source_payload_hashes_and_selected_points_match':True,'frozen_input_changes':0,'scope':'Recorded evidence consistency, not independent proof of physical building geometry or imagery inspection'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ledger',type=Path,default=default_location_resolutions());p.add_argument('--output',type=Path);a=p.parse_args()
    if a.ledger is None:raise SystemExit('Required documented location-resolution ledger is missing')
    result=verify(a.ledger);text=json.dumps(result,indent=2)+'\n'
    if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(text)
    print(text)
if __name__=='__main__':main()
