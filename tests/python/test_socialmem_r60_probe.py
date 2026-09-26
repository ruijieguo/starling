"""R6.0 真实探测入口的离线身份门禁；不调用 provider。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/run_socialmem_r60_probe.py'


def driver():
    assert SCRIPT.is_file(), 'R6.0 probe entry is required'
    spec = importlib.util.spec_from_file_location('r60_probe_test', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_probe_has_fixed_candidate_profile_and_two_scope_default():
    module = driver()
    assert module.PROFILE == 'target_units_statement_first_v1'
    assert module.DEFAULT_SCOPE_LIMIT == 2
    assert module.CORE_SHA256.startswith('600a1718')


def test_probe_rejects_existing_output_before_provider_work(tmp_path):
    module = driver()
    output = tmp_path / 'existing'
    output.mkdir()
    try:
        module.run(tmp_path / 'missing-prepare', output)
    except ValueError as exc:
        assert 'already exists' in str(exc)
    else:
        raise AssertionError('existing R6.0 probe output was accepted')
