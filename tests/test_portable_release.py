from pathlib import Path
import sys,hashlib
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from stage_frozen_inputs import verified_copy
import run_pipeline

def test_staging_rejects_wrong_snapshot_before_copy(tmp_path):
 src=tmp_path/'source';src.write_text('wrong');dest=tmp_path/'destination'
 with pytest.raises(ValueError,match='checksum mismatch'):verified_copy(src,dest,'0'*64)
 assert not dest.exists()

def test_staging_preserves_existing_different_file(tmp_path):
 src=tmp_path/'source';src.write_text('correct');dest=tmp_path/'destination';dest.write_text('preserve')
 with pytest.raises(ValueError,match='refusing overwrite'):verified_copy(src,dest,hashlib.sha256(src.read_bytes()).hexdigest())
 assert dest.read_text()=='preserve'

def test_reproduction_profile_stops_at_failed_frozen_input_check(monkeypatch,capsys):
 import subprocess
 calls=[]
 def fail(command,**kwargs):calls.append(command);raise subprocess.CalledProcessError(7,command)
 monkeypatch.setattr(run_pipeline.subprocess,'run',fail)
 assert run_pipeline.main(['--profile','reproducibility'])==7
 assert len(calls)==1 and 'stage_frozen_inputs.py' in calls[0][1]
 assert 'Verify frozen reproduction inputs' in capsys.readouterr().err
