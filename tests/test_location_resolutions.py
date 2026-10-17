from pathlib import Path
import sys,pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from process_address_reviews import summarize
C=[{'case_id':'A','building_id':'b','source_address':'1 TEST RD','algorithm_hdb_classification':'Yes','link_requires_manual_location_check':'True'}]
R=[{'case_id':'A','source_address':'1 TEST RD','is_hdb':'Yes'}]
D=[{'case_id':'A','building_id':'b','location_resolution_status':'resolved_documented_address_point','selected_postal_code':'012345','decision_reason':'Reviewed corroboration','corroborating_source_url':'https://example.org/official','onemap_snapshot_sha256':'x'}]
def test_hdb_confirmation_does_not_clear_location():
 s=summarize(C,R);assert s['number_saved_location_ambiguities_for_follow_up']==1

def test_documented_resolution_separate_from_unchanged_classification():
 s=summarize(C,R,D);assert s['number_agreements']==1 and s['number_documented_location_resolutions']==1 and s['number_saved_location_ambiguities_for_follow_up']==0 and s['dataset_corrections_applied']==0

def test_resolution_requires_evidence():
 with pytest.raises(ValueError,match='lacks evidence'):summarize(C,R,[{**D[0],'corroborating_source_url':''}])

def test_resolution_requires_same_physical_building():
 with pytest.raises(ValueError,match='identify'):summarize(C,R,[{**D[0],'building_id':'other'}])


def test_retained_location_evidence_hashes_and_selected_points():
    from process_address_reviews import default_location_resolutions
    from verify_location_resolutions import verify
    result=verify(default_location_resolutions())
    assert result['documented_cases_checked']==7 and result['frozen_input_changes']==0
