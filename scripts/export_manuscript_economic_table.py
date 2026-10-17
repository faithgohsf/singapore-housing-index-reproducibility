"""Export the compact economic manuscript table from verified model output.

This is presentation only; no model is fitted and no scientific result changed.
"""
from pathlib import Path
import argparse,csv,json
ROOT=Path(__file__).resolve().parents[1]

def table_rows(results):
 rows=[['Analysis and comparison','MAE without SHI','MAE with SHI','Difference','95% interval']]
 for label,group,a,b in [('Rental A/B','rental','A','B'),('Rental C/D','rental','C','D'),('Resale A/B','resale_baseline','A','B'),('Resale C/D','resale_adjusted','C','D')]:
  matches=[r for r in results[group]['comparisons'] if r['model_a']==a and r['model_b']==b]
  if len(matches)!=1:raise ValueError('Expected one comparison for '+label)
  r=matches[0];lo,hi=r['improvement_ci95']
  rows.append([label,f"{r['mae_a']:.2f}",f"{r['mae_b']:.2f}",f"{r['improvement_mae_a_minus_b']:.2f}",f"{lo:.2f} to {hi:.2f}"])
 return rows

def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--results',type=Path,default=ROOT/'outputs/tables/economic_model_results__2024-2025.json');p.add_argument('--output',type=Path,default=ROOT/'outputs/tables/manuscript_economic_table.csv');a=p.parse_args(argv);rows=table_rows(json.loads(a.results.read_text()));a.output.parent.mkdir(parents=True,exist_ok=True)
 with a.output.open('w',newline='') as f:csv.writer(f).writerows(rows)
 print(a.output);return 0
if __name__=='__main__':raise SystemExit(main())
