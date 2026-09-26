#!/usr/bin/env python3
"""R6.1 八库入口：复用共享stage实现，硬绑定双核心真实探测的候选资格。"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('r61_expanded_engine', ROOT / 'scripts/run_socialmem_r60_expanded.py')
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)
engine.CORE_SHA256 = 'd2f60d1836336f9114efd437fec428050ac77e6bbec6abeea02a0e219b9df793'
engine.IDENTITY_SCHEMA = 'r61-expanded-identity-v1'
engine.SEAL_SCHEMA = 'r61-expanded-seal-v1'
engine.ARM = 'r61_scope_correction_development'
engine.DEFAULT_PROBE = ROOT / 'build/socialmem_20260926_r61_work/run-real-retry'
engine.PROBE_SEAL = '1a2a9f20a82e87880272a9058f8599fa8117ff8a92662833b35f560e49f2e60c'
engine.PROBE_PREPARE_SEAL = '285cbea5751c37b6c43809f8e7c3cbafc62ff0159a2dd1dc09cba460d46feedb'
engine.OWN_FILES = (*engine.OWN_FILES, 'scripts/run_socialmem_r61_expanded.py',
    'tests/python/test_socialmem_r61_expanded.py', 'scripts/run_socialmem_r61_scope_probe.py',
    'tests/python/test_socialmem_r61_scope_probe.py', 'tests/python/test_socialmem_r59_expanded.py')
CANDIDATE_CORE = ROOT / 'build/socialmem_20260926_r61_work/cmake/python/starling/_core.cpython-314-darwin.so'


def current_core():
    if not CANDIDATE_CORE.is_file() or engine.sha(CANDIDATE_CORE) != engine.CORE_SHA256:
        raise ValueError('fixed isolated candidate core mismatch')
    return CANDIDATE_CORE


def require_candidate(summary):
    tasks = summary.get('tasks', [])
    expected = [('Lionel', 'old'), ('Lionel', 'candidate'), ('Miriam', 'candidate'), ('Miriam', 'old')]
    if (summary.get('stage') != 'run' or summary.get('state') != 'complete'
        or summary.get('candidate_passed') is not True
        or summary.get('core_sha256', {}).get('candidate') != engine.CORE_SHA256
        or [(t.get('holder'), t.get('revision')) for t in tasks] != expected
        or summary.get('ledger', {}).get('reserved') != 0 or summary.get('stage_failures')
        or summary.get('unexecuted_tasks')):
        raise ValueError('complete fixed candidate probe required')
    for task in tasks:
        cost = task.get('accounting', {})
        if (task.get('native_replay', {}).get('verified') is not True
            or cost.get('healthy_http') is not True or cost.get('usage_complete') is not True
            or cost.get('local_attempt_count_unknown') is not False or cost.get('remote_execution_unknown') is not False):
            raise ValueError('healthy raw HTTP and native replay required')
        if task['revision'] == 'candidate' and (task.get('status') != 'passed'
                or type(task.get('statement_count')) is not int or task['statement_count'] <= 0):
            raise ValueError('nonempty complete candidate holder required')


def qualify_probe(probe):
    probe = Path(probe).resolve()
    engine.old.verify_historical(probe, engine.PROBE_SEAL, 'r61-scope-probe-v1', 'run')
    prepared = Path(engine.read(probe / 'stage.json')['input']).resolve()
    engine.old.verify_historical(prepared, engine.PROBE_PREPARE_SEAL, 'r61-scope-probe-v1', 'prepare')
    identity = engine.read(probe / 'identity.json')
    if identity.get('revisions', {}).get('candidate', {}).get('core_sha256') != engine.CORE_SHA256:
        raise ValueError('probe candidate core identity mismatch')
    command = [sys.executable, str(ROOT / 'scripts/run_socialmem_r61_scope_probe.py'), 'check', '--input', str(probe)]
    before = engine.checker_files()
    result = subprocess.run(command, cwd=ROOT, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                            text=True, capture_output=True)
    if result.returncode != 0: raise ValueError('independent R6.1 qualification failed: ' + result.stderr[-1600:])
    summary = json.loads(result.stdout); require_candidate(summary)
    if before != engine.checker_files(): raise ValueError('qualification checker changed')
    engine.old.verify_historical(probe, engine.PROBE_SEAL, 'r61-scope-probe-v1', 'run')
    return dict(command=command, returncode=0, stdout=result.stdout, stdout_sha256=engine.paired.text_sha(result.stdout),
                stderr=result.stderr, summary=summary, checker_files=before)


engine.current_core = current_core
engine.qualify_probe = qualify_probe
_prepare = engine.prepare


def prepare(parent, out, probe=None, evidence=()):
    # Python 默认参数在定义时绑定；不能沿用共享引擎的旧探测默认值。
    return _prepare(parent, out, engine.DEFAULT_PROBE if probe is None else probe, evidence)


engine.prepare = prepare


if __name__ == '__main__':
    raise SystemExit(engine.main())
