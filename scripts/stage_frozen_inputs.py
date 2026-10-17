"""Stage or check the checksum-pinned inputs; never substitute a newer snapshot."""
from pathlib import Path
import argparse,hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1]
def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def verified_copy(source,target,expected):
 if digest(source)!=expected:raise ValueError(f'Frozen input checksum mismatch: {source.name}; no file copied')
 if target.exists():
  if digest(target)!=expected:raise ValueError(f'Destination differs from frozen input: {target.name}; refusing overwrite')
  return
 target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
def main(argv=None):
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--from-dir',type=Path);parser.add_argument('--check',action='store_true');args=parser.parse_args(argv)
 spec=ROOT/'frozen_inputs.json'
 if not spec.exists():raise FileNotFoundError('frozen_inputs.json is required for the reproducibility profile')
 for item in json.loads(spec.read_text())['inputs']:
  target=ROOT/item['path']
  if args.from_dir:
   matches=list(args.from_dir.rglob(Path(item['path']).name))
   valid=[p for p in matches if p.is_file() and digest(p)==item['sha256']]
   if not valid:raise FileNotFoundError(f"No checksum-matching frozen input found: {Path(item['path']).name}")
   verified_copy(valid[0],target,item['sha256'])
  if not target.is_file() or digest(target)!=item['sha256']:raise ValueError(f"Missing or checksum-mismatched frozen input: {item['path']}. Stage the documented snapshot; a current download cannot be assumed equivalent.")
  print('VERIFIED',item['path'])
 if not args.from_dir and not args.check:parser.error('Use --from-dir SNAPSHOT_DIRECTORY or --check')
 return 0
if __name__=='__main__':raise SystemExit(main())
