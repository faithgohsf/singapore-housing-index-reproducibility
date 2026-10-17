"""Compare regenerated numeric outputs with the verified manuscript benchmark."""
from pathlib import Path
import argparse,json,math
ROOT=Path(__file__).resolve().parents[1]
def matches(actual,expected):
 if isinstance(expected,int):return actual==expected
 return isinstance(actual,(int,float)) and math.isclose(actual,expected,rel_tol=1e-8,abs_tol=1e-5)
def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path);a=p.parse_args(argv);spec=json.loads((ROOT/'reference_results.json').read_text());cache={};failures=[]
 for check in spec['checks']:
  source=check['source_file']
  if source not in cache:cache[source]=json.loads((ROOT/source).read_text())
  value=cache[source]
  for key in check['json_pointer'].split('/')[1:]:
   key=key.replace('~1','/').replace('~0','~');value=value[int(key)] if isinstance(value,list) else value[key]
  if not matches(value,check['expected_value']):failures.append({**check,'actual':value})
 result={'checked':len(spec['checks']),'passed':len(spec['checks'])-len(failures),'failed':len(failures),'failures':failures,'absolute_tolerance':1e-5,'relative_tolerance':1e-8,'integer_counts_exact':True}
 text=json.dumps(result,indent=2)+'\n';print(text)
 if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(text)
 return 1 if failures else 0
if __name__=='__main__':raise SystemExit(main())
