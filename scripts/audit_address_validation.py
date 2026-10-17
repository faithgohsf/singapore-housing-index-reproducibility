"""Report actual HDB visual-audit responses; generated links are not inspections."""
from pathlib import Path
import argparse,json
from process_address_reviews import read,summarize,default_location_resolutions

def main():
 root=Path(__file__).resolve().parents[1]
 default=root/'validation_cases/backend/HDB_Visual_Audit_Backend.csv'
 if not default.exists():default=root/'../Validation/Address_Review/backend/HDB_Visual_Audit_Backend.csv'
 p=argparse.ArgumentParser();p.add_argument('--backend',type=Path,default=default);p.add_argument('--reviews',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
 review=a.reviews or (root/'validation_cases/completed_hdb_classification_responses.csv' if (root/'validation_cases/completed_hdb_classification_responses.csv').exists() else root/'../Validation/Address_Review/HDB_Visual_Audit.xlsx')
 decisions=default_location_resolutions()
 s=summarize(read(a.backend),read(review) if review.exists() else [],read(decisions) if decisions else []);s={k:v for k,v in s.items() if k not in ['case_results','cases_requiring_further_investigation']};t=json.dumps(s,indent=2)+'\n'
 if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(t)
 print(t)
if __name__=='__main__':main()
