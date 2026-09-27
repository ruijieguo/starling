"""R6.0 离线入口身份与 profile 门禁；不调用真实 provider。"""
import hashlib
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/run_socialmem_r60_expanded.py'
EXPECTED_CORE = '600a17182d920d4a7379892eec5440dec4409516352c3fee4750f70706ceaf27'


def driver():
    assert SCRIPT.is_file(), 'R6.0 expanded entry is required'
    spec = importlib.util.spec_from_file_location('r60_expanded_test', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r60_identity_is_distinct_from_r59_and_uses_statement_first_profile():
    module = driver()
    assert module.CORE_SHA256 == EXPECTED_CORE
    assert module.PROFILE == 'target_units_statement_first_v1'
    assert 'target_units_v1' not in module.PROFILE
    assert 'ead8046e4a28d257f3429d865523c1af1f6275fd0cb1ba98d8fa8023894d6fef' not in module.CORE_SHA256


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_r60_current_core_is_the_fresh_candidate():
    module = driver()
    core = module.current_core()
    assert core.is_file()
    assert hashlib.sha256(core.read_bytes()).hexdigest() == EXPECTED_CORE


def test_r60_output_refuses_existing_directory_before_any_provider_work(tmp_path):
    module = driver()
    output = tmp_path / 'existing'
    output.mkdir()
    try:
        module.prepare(tmp_path / 'missing-parent', output)
    except ValueError as exc:
        assert 'already exists' in str(exc)
    else:
        raise AssertionError('existing R6.0 output was accepted')


def test_r60_source_identity_names_only_r60_entry_and_test():
    module = driver()
    assert 'scripts/run_socialmem_r60_expanded.py' in module.OWN_FILES
    assert 'tests/python/test_socialmem_r60_expanded.py' in module.OWN_FILES
    assert 'scripts/run_socialmem_r59_expanded.py' not in module.OWN_FILES
