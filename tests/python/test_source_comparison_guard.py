"""真实来源消融入口在发送请求前必须验证范围、身份和四臂预算。"""
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/run_socialmem_source_comparison.py'

def driver():
    assert SCRIPT.is_file(), 'frozen comparison entry guard missing'
    spec = importlib.util.spec_from_file_location('source_comparison', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def plan():
    return {'arms':['statements','sources','hybrid','full'],
            'group_id':'135c86f3d282d1560e6fe9e7',
            'question_ids':['Q3_ph9s1c1','Q4_ph9s1c2','Q5_ph9s2c1','Q8_ph9s3c1','Q8_ph9s4c1','Q7_ph9s5c1'],
            'budgets':{'statements':35,'sources':11,'hybrid':35,'full':11},
            'http_budget':92, 'holders':['Anika','Diane','Luca','Raj']}


def test_exact_frozen_design_is_accepted():
    driver().validate_plan(plan())


@pytest.mark.parametrize('field,value', [('arms',['sources']),('http_budget',100),
    ('holders',['Diane','Raj']), ('group_id','other'),('question_ids',['a'])])
def test_scope_and_budget_drift_rejected(field, value):
    p = plan(); p[field] = value
    with pytest.raises(ValueError):
        driver().validate_plan(p)


def test_tampered_artifact_fails_before_runtime(tmp_path):
    d = driver(); (tmp_path/'scope.json').write_text('{}')
    expected = d.sha256(tmp_path/'scope.json')
    (tmp_path/'scope.json').write_text('{"changed":true}')
    with pytest.raises(ValueError, match='hash'):
        d.verify_files(tmp_path, {'scope.json':expected})


def frozen_fixture(tmp_path):
    d = driver()
    files = {}
    for arm in d.ARMS:
        prefix = f'{arm}/'
        frozen = {'scripts/run_socialmem_baseline.py': 'runner',
                  'python/starling/runtime.py': 'module'}
        identity = {'frozen_files': {name: d.sha256(write_file(tmp_path, prefix+'frozen/'+name, body))
                                     for name, body in frozen.items()}}
        for name, body in {'config.json': '{}', 'identity.json': json.dumps(identity),
                           'corpus.jsonl': '{}', 'scope-manifest.json': '{}',
                           f'runs/{d.GROUP}/scope.json': '{}',
                           f'runs/{d.GROUP}/frozen.db': 'snapshot'}.items():
            write_file(tmp_path, prefix+name, body)
        for name in (*identity['frozen_files'],):
            files[prefix+'frozen/'+name] = identity['frozen_files'][name]
        for name in ('config.json', 'identity.json', 'corpus.jsonl', 'scope-manifest.json',
                     f'runs/{d.GROUP}/scope.json', f'runs/{d.GROUP}/frozen.db'):
            files[prefix+name] = d.sha256(tmp_path / (prefix+name))
    return d, files


def write_file(root, name, body):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return path


def test_complete_manifest_passes(tmp_path):
    d, files = frozen_fixture(tmp_path)
    d.verify_file_manifest(tmp_path, files)


@pytest.mark.parametrize('missing', ['config.json', 'identity.json', 'corpus.jsonl',
    'scope-manifest.json', 'scope.json', 'frozen.db',
    'frozen/scripts/run_socialmem_baseline.py', 'frozen/python/starling/runtime.py'])
def test_manifest_rejects_missing_required_or_frozen_file(tmp_path, missing):
    d, files = frozen_fixture(tmp_path)
    name = (f'statements/runs/{d.GROUP}/{missing}' if missing in ('scope.json', 'frozen.db')
            else 'statements/'+missing)
    del files[name]
    with pytest.raises(ValueError, match='manifest'):
        d.verify_file_manifest(tmp_path, files)


def test_manifest_rejects_empty_list_and_identity_hash_disagreement(tmp_path):
    d, files = frozen_fixture(tmp_path)
    with pytest.raises(ValueError, match='manifest'):
        d.verify_file_manifest(tmp_path, {})
    files['statements/frozen/python/starling/runtime.py'] = '0'*64
    with pytest.raises(ValueError, match='manifest'):
        d.verify_file_manifest(tmp_path, files)


@pytest.mark.parametrize('planned,configured', [(False,None),(None,False),(False,True),(False,0)])
def test_answer_setting_must_match_frozen_plan(planned,configured):
    d=driver()
    assert hasattr(d,'validate_answer_setting'), 'answer setting identity guard missing'
    with pytest.raises(ValueError, match='answer_enable_thinking'):
        d.validate_answer_setting({'answer_enable_thinking':planned},{'answer_enable_thinking':configured})


@pytest.mark.parametrize('value',[None,False])
def test_answer_setting_preserves_old_and_explicit_off_plan(value):
    d=driver()
    assert hasattr(d,'validate_answer_setting'), 'answer setting identity guard missing'
    d.validate_answer_setting({'answer_enable_thinking':value},{'answer_enable_thinking':value})
