"""历史审计必须运行封存程序，当前工作区演进不改变历史结论。"""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def driver():
    path = ROOT / 'scripts/socialmem_frozen_audit.py'
    assert path.is_file(), 'frozen audit launcher required'
    spec = importlib.util.spec_from_file_location('frozen_audit_test', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_historical_build_rechecks_with_original_failure_and_consumption():
    m = driver()
    result = m.run_frozen_check(
        ROOT / 'build/socialmem_20260926_r61_expanded/build',
        ROOT / 'build/socialmem_20260926_r61_expanded/prepare',
        'scripts/run_socialmem_r61_expanded.py',
        '0cbe5bedc8ec203b74780824de6a17d2cee8c7368b46c6753050841902aecb04')
    assert result['returncode'] == 1
    summary = result['summary']
    assert summary['state'] == 'incomplete' and summary['healthy_scopes'] == 1
    assert summary['extraction_known_tokens'] == 1291057
    assert summary['embedding_requests'] == 29
    assert summary['scopes']['1c2838ef51b9983207436fc9']['native_replay']['verified'] is True


def test_wrong_seal_rejected_before_launch():
    m = driver()
    with pytest.raises(ValueError, match='seal'):
        m.run_frozen_check(ROOT / 'build/socialmem_20260926_r61_expanded/build',
            ROOT / 'build/socialmem_20260926_r61_expanded/prepare',
            'scripts/run_socialmem_r61_expanded.py', '0'*64)
