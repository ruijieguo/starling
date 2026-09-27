"""R6.1 检索/回答入口复用既有原生评测合同，固定新core。"""
import importlib.util
from pathlib import Path
import sqlite3

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/run_socialmem_r61_evaluate.py'
CANDIDATE = 'd2f60d1836336f9114efd437fec428050ac77e6bbec6abeea02a0e219b9df793'


def driver():
    assert SCRIPT.is_file(), 'R6.1 evaluation entry is required'
    spec = importlib.util.spec_from_file_location('r61_evaluation_test', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.engine


def test_fixed_evaluator_identity_and_schema():
    m = driver()
    assert m.CORE_SHA256 == m.builder.CORE_SHA256 == CANDIDATE
    assert m.builder.PROFILE == 'target_units_statement_first_v1'
    assert m.SEAL_SCHEMA == 'r61-evaluation-seal-v1'
    assert m.IDENTITY_SCHEMA == 'r61-evaluation-identity-v1'
    assert m.FAILURE_SCHEMA == 'r61-evaluation-failure-v1'


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
@pytest.mark.parametrize('problem', ['healthy', 'old_core', 'seven', 'true_string', 'profile',
                                     'missing_database', 'database_hash', 'sidecar', 'duplicate_question'])
def test_build_gate_uses_actual_new_profile_before_reaching_provider(tmp_path, monkeypatch, problem):
    m = driver(); checked = m.builder.historical_inputs(m.builder.DEFAULT_PARENT)
    built = tmp_path / 'build'; databases = {}
    for group in checked['groups']:
        path = built / 'runs' / group['group_id'] / 'frozen.db'; path.parent.mkdir(parents=True)
        with sqlite3.connect(path) as db: db.execute('CREATE TABLE fixture_only(value INTEGER)')
        databases[group['group_id']] = m.sha(path)
    gids = list(databases)
    checked.update(stage='build', identity=dict(core_sha256=m.CORE_SHA256), seal_sha256='fixture',
        plans=dict(scopes={gid: dict(holders={'A': dict(claim_batch_prompt_profile=m.builder.PROFILE)}) for gid in gids}),
        summary=dict(state='complete', healthy_scopes=8, retrieval_ready=True, qa_ready=False,
            database_sha256=databases, health={gid: {} for gid in gids}))
    m.write(built / 'stage.json', dict(stage='build', input=str(tmp_path / 'prepare')))
    if problem == 'old_core': checked['config']['core_sha256'] = 'old'
    elif problem == 'seven': checked['summary']['healthy_scopes'] = 7
    elif problem == 'true_string': checked['config']['claim_batch_target_units'] = 'true'
    elif problem == 'profile': checked['plans']['scopes'][gids[0]]['holders']['A']['claim_batch_prompt_profile'] = 'target_units_v1'
    elif problem == 'missing_database': (built / 'runs' / gids[0] / 'frozen.db').unlink()
    elif problem == 'database_hash': databases[gids[0]] = 'changed'
    elif problem == 'sidecar': (built / 'runs' / gids[0] / 'frozen.db-wal').write_bytes(b'live')
    elif problem == 'duplicate_question': checked['records'][-1] = checked['records'][0]
    monkeypatch.setattr(m.builder, 'check', lambda *args, **kwargs: checked)
    if problem == 'healthy':
        assert m.validated_build(built)['databases'] == databases
    else:
        monkeypatch.setattr(m, 'runtime_modules', lambda *_: pytest.fail('provider boundary reached'))
        with pytest.raises(ValueError): m.retrieve(built, tmp_path / 'forbidden')
        assert not (tmp_path / 'forbidden').exists()


_spec = importlib.util.spec_from_file_location('r61_shared_evaluation_tests', ROOT / 'tests/python/test_socialmem_r59_evaluate.py')
_shared = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_shared)
_shared.driver = driver
_shared.SCRIPT = SCRIPT
_shared.FIXTURE_BUILD = ROOT / 'build/socialmem_20260926_r61_work/evaluator-native-fixture/build'
native = _shared.native
synthetic_contexts = _shared.synthetic_contexts
localhost_stages = _shared.localhost_stages
for _name, _test in vars(_shared).items():
    if _name.startswith('test_') and _name != 'test_invalid_build_identity_is_rejected_before_provider':
        globals()['test_shared_' + _name[5:]] = _test
