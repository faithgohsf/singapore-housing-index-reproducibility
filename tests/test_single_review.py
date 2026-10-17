from pathlib import Path
import sys,pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from process_address_reviews import summarize,read,results_paragraph,update_manuscript
C=[{'case_id':'A','source_address':'1 TEST RD','algorithm_hdb_classification':'Yes'}]
def response(label='',**kwargs):
 r={'case_id':'A','source_address':'1 TEST RD','is_hdb':label,'notes':''};r.update(kwargs);return r

def test_blank_not_reviewed():
 s=summarize(C,[response()]);assert s['number_buildings_reviewed']==0 and s['number_awaiting_review']==1 and s['agreement_proportion_among_comparable_responses'] is None
@pytest.mark.parametrize('label,key',[('Yes','number_confirmed_as_hdb_by_reviewer'),('No','number_identified_as_non_hdb_by_reviewer'),('Unable to determine','number_unable_to_determine')])
def test_three_dropdown_responses(label,key):
 s=summarize(C,[response(label)]);assert s['number_buildings_reviewed']==1 and s[key]==1

def test_optional_notes_not_required():assert summarize(C,[response('Yes')])['number_agreements']==1

def test_unable_not_in_agreement_denominator():
 s=summarize(C,[response('Unable to determine')]);assert s['agreement_comparison_denominator']==0 and s['number_discrepancies']==0

def test_discrepancy_retained_without_data_changes():
 s=summarize(C,[response('No')]);assert s['number_discrepancies']==1 and s['dataset_corrections_applied']==0 and len(s['cases_requiring_further_investigation'])==1

def test_missing_algorithm_not_forced_private():
 s=summarize([{**C[0],'algorithm_hdb_classification':''}],[response('Yes')]);assert s['agreement_comparison_denominator']==0

def test_duplicate_response_rejected():
 with pytest.raises(ValueError,match='Duplicate'):summarize(C,[response(),response()])

def test_changed_address_rejected():
 with pytest.raises(ValueError,match='address'):summarize(C,[response('Yes',source_address='wrong')])

def test_invalid_response_rejected():
 with pytest.raises(ValueError,match='dropdown'):summarize(C,[response('unknown')])

def test_unknown_case_rejected():
 with pytest.raises(ValueError,match='Unprepared'):summarize(C,[response('Yes',case_id='B')])

def test_csv_user_headers(tmp_path):
 p=tmp_path/'review.csv';p.write_text('Case ID,Building address,Google Street View link,Is this an HDB building?,Notes\nA,1 TEST RD,https://example.org,Yes,\n');assert read(p)[0]['is_hdb']=='Yes'

def test_csv_missing_header_rejected(tmp_path):
 p=tmp_path/'bad.csv';p.write_text('wrong,value\nA,1\n')
 with pytest.raises(ValueError,match='header'):read(p)

def test_results_update_preserves_other_text_and_backup(tmp_path):
 p=tmp_path/'manuscript.md';p.write_text('## Results\n\n### HDB building classification visual audit status\n\nOld text.\n\n### Other analysis\nKeep this.\n')
 update_manuscript(p,summarize(C,[response('Yes')]))
 assert '1 of 1' in p.read_text() and 'Keep this.' in p.read_text() and len(list(tmp_path.glob('*.bak')))==1

def test_notes_with_blank_answer_not_counted():assert summarize(C,[response(notes='Unfinished note')])['number_buildings_reviewed']==0

def test_blinded_five_columns_only(tmp_path):
 # Actual workbook checks are performed by the recorded export verification.
 from process_address_reviews import HEADERS
 assert len(HEADERS)==5 and 'algorithm' not in ' '.join(HEADERS).lower()

def test_mixed_responses_have_explicit_denominators():
 cases=[{'case_id':k,'source_address':k,'algorithm_hdb_classification':a} for k,a in [('A','Yes'),('B','No'),('C','Yes'),('D','No'),('E','Yes')]]
 reviews=[{'case_id':k,'source_address':k,'is_hdb':v,'notes':''} for k,v in [('A','Yes'),('B','No'),('C','Unable to determine'),('D','Yes'),('E','')]]
 s=summarize(cases,reviews)
 assert s['number_buildings_reviewed']==4 and s['number_confirmed_as_hdb_by_reviewer']==2 and s['number_identified_as_non_hdb_by_reviewer']==1 and s['number_unable_to_determine']==1
 assert s['agreement_comparison_denominator']==3 and s['number_agreements']==2 and s['number_discrepancies']==1 and s['number_awaiting_review']==1
