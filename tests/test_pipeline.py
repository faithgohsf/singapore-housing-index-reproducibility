from __future__ import annotations

import pathlib
import sys
import subprocess

import pytest

PROJECT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))
import run_pipeline  # noqa: E402


def test_pipeline_names_failed_stage_and_does_not_start_later_stages(monkeypatch, capsys):
    calls = []

    def fail_first_stage(*args, **kwargs):
        calls.append(args[0])
        raise subprocess.CalledProcessError(9, args[0])

    monkeypatch.setattr(run_pipeline, "STAGES", [
        ("required first stage", ["first.py"], []),
        ("later stage", ["later.py"], []),
    ])
    monkeypatch.setattr(run_pipeline.subprocess, "run", fail_first_stage)

    result = run_pipeline.main([])

    assert result == 9
    assert len(calls) == 1
    assert "Pipeline stopped at stage 'required first stage'" in capsys.readouterr().err
