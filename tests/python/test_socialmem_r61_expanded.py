"""R6.1 绑定候选探测的八库入口，复用原生stage回归。"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/run_socialmem_r61_expanded.py'
CANDIDATE = 'd2f60d1836336f9114efd437fec428050ac77e6bbec6abeea02a0e219b9df793'


def driver():
    assert SCRIPT.is_file(), 'R6.1 expanded entry is required'
    spec = importlib.util.spec_from_file_location('r61_expanded_test', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.engine


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_fixed_identity_uses_isolated_candidate_core():
    m = driver()
    assert m.CORE_SHA256 == CANDIDATE and m.sha(m.current_core()) == CANDIDATE
    assert 'socialmem_20260926_r61_work/cmake/' in str(m.current_core())
    value = m.historical_inputs(m.DEFAULT_PARENT)
    assert len(value['records']) == 133 and len(value['groups']) == 8
    assert value['config']['arm'] == 'r61_scope_correction_development'
    assert value['config']['core_sha256'] == CANDIDATE


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_historical_probe_is_not_candidate_qualification():
    m = driver()
    with pytest.raises(ValueError, match='seal'):
        m.qualify_probe(ROOT / 'build/socialmem_20260926_r58_paired/run')


@pytest.mark.parametrize('stage', ['prepare', 'build'])
def test_existing_output_precedes_qualification(tmp_path, stage):
    m = driver(); out = tmp_path / 'exists'; out.mkdir()
    with pytest.raises(ValueError, match='already exists'):
        getattr(m, stage)(tmp_path / 'missing', out)


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_wrong_core_is_rejected_before_output(tmp_path, monkeypatch):
    m = driver(); monkeypatch.setattr(m, 'CORE_SHA256', '0' * 64)
    with pytest.raises(ValueError, match='core'):
        m.prepare(m.DEFAULT_PARENT, tmp_path / 'prepare')
    assert not (tmp_path / 'prepare').exists()

# 共享原生stage的行为测试复用函数；历史文件的core/profile期望保持原样。
# 在本模块显式替换driver和子进程bootstrap，确保所有断言实际运行R6.1实例。
_spec = importlib.util.spec_from_file_location('r61_shared_stage_tests', ROOT / 'tests/python/test_socialmem_r59_expanded.py')
_shared = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_shared)


def run_code(code, *args):
    import subprocess
    import sys
    setup = '''
import importlib.util,json,sys,tempfile,sqlite3
from pathlib import Path
s=importlib.util.spec_from_file_location('r61','scripts/run_socialmem_r61_expanded.py')
entry=importlib.util.module_from_spec(s);s.loader.exec_module(entry);m=entry.engine
'''
    result = subprocess.run([sys.executable, '-c', setup + code, *map(str, args)],
                            cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


_shared.driver = driver
_shared.run_code = run_code
prepared = _shared.prepared
built = _shared.built
for _name, _test in vars(_shared).items():
    if _name.startswith('test_') and _name not in (
        'test_historical_cohort_identity_is_distinct_from_candidate_core',
        'test_current_core_full_cohort_native_plans_and_qualification'):
        globals()['test_shared_' + _name[5:]] = _test


@pytest.mark.historical_eval(reason='复用 prepared 夹具，依赖 R6.1 固定原生构建和封存语料；见 tests/README.md')
def test_new_prepare_qualifies_same_core_and_all_native_plans(prepared):
    m = driver(); plans = m.read(prepared / 'batch-plans.json')
    assert {k: plans[k] for k in ('holder_count', 'source_units', 'batches', 'belief_request_upper_bound',
                                'extraction_request_upper_bound')} == dict(holder_count=65, source_units=1322,
                                 batches=197, belief_request_upper_bound=591, extraction_request_upper_bound=851)
    assert all(p['claim_batch_prompt_profile'] == m.PROFILE for scope in plans['scopes'].values() for p in scope['holders'].values())
    qualification = m.read(prepared / 'qualification.json')
    assert qualification['summary']['core_sha256']['candidate'] == CANDIDATE
    assert qualification['summary']['candidate_passed'] is True
    assert m.read(prepared / 'identity.json')['schema'] == 'r61-expanded-identity-v1'
    assert m.read(prepared / 'seal.json')['schema'] == 'r61-expanded-seal-v1'
    assert m.read(prepared / 'summary.json')['external_requests'] == 0
