"""容量实验的预算变化不能夹带核心、提示或裁判漂移。"""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def module():
    p = ROOT / 'scripts/run_socialmem_answer_capacity.py'
    assert p.is_file(), 'answer capacity driver missing'
    spec = importlib.util.spec_from_file_location('capacity_driver', p)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def configs():
    parent = json.loads((ROOT / 'build/socialmem_20260917_grounded_answer_v2/config.json').read_text())
    return parent, {**parent, 'answer_max_tokens': 1024}


def test_accepts_only_budget_change_without_mutating_parent():
    old, new = configs()
    module().validate_config(old, new)
    assert old['answer_max_tokens'] == 512
    assert new['answer_policy'] == 'grounded_v1'


@pytest.mark.parametrize('key,value', [
    ('answer_max_tokens', 512), ('answer_max_tokens', 768), ('answer_max_tokens', True),
    ('judge_max_tokens', 1024), ('answer_model', 'different'), ('timeout_ms', 240000),
    ('workers', 8), ('k', 60), ('max_context_bytes', 16000), ('source_strategy', 'bm25'),
    ('http_budget', 1315), ('max_retries', 1), ('answer_enable_thinking', True),
    ('answer_policy', 'grounded_compact_v1'), ('extra', True), ('core_sha256', 'a' * 64),
    ('include_unknown_time', 1),
])
def test_rejects_confounded_candidate(key, value):
    old, new = configs()
    new[key] = value
    with pytest.raises(ValueError):
        module().validate_config(old, new)


@pytest.mark.parametrize('key,value', [('answer_max_tokens', 1024), ('answer_policy', 'legacy')])
def test_rejects_wrong_parent(key, value):
    old, new = configs()
    old[key] = value
    with pytest.raises(ValueError):
        module().validate_config(old, new)


def test_any_frozen_code_change_is_rejected():
    m = module()
    old = {'frozen_files': {'native.so': 'a', 'runner.py': 'b'}}
    m.validate_code_delta(old, {'frozen_files': dict(old['frozen_files'])})
    for files in [{'native.so': 'c', 'runner.py': 'b'}, {'native.so': 'a'},
                  {**old['frozen_files'], 'new.py': 'c'}]:
        with pytest.raises(ValueError):
            m.validate_code_delta(old, {'frozen_files': files})


def test_copies_parent_bytes_even_when_workspace_has_different_code(tmp_path, monkeypatch):
    m = module()
    parent, work, workspace = [tmp_path / n for n in ['parent', 'work', 'workspace']]
    rel = Path('src/retrieval/source_retriever.cpp')
    for base, content in [(parent / 'frozen', b'parent implementation'), (workspace, b'wrong implementation')]:
        p = base / rel
        p.parent.mkdir(parents=True)
        p.write_bytes(content)
    monkeypatch.setattr(m, 'ROOT', workspace)
    identity = {'frozen_files': {str(rel): m.sha(parent / 'frozen' / rel)}}
    m.copy_frozen_code(parent, work, identity)
    assert (work / 'frozen' / rel).read_bytes() == b'parent implementation'
    (parent / 'frozen' / rel).write_bytes(b'corrupted')
    with pytest.raises(ValueError):
        m.copy_frozen_code(parent, tmp_path / 'second', identity)
    assert not (tmp_path / 'second' / 'frozen' / rel).exists()


@pytest.mark.parametrize('fmt', ['long_form', 'short_answer', 'multiple_choice'])
def test_every_prompt_and_source_must_reproduce_parent(fmt):
    m = module()
    records = [{'item_id': 'a', 'answer_format': fmt}]
    parent = {'a': {'recall': {'block': 'original', 'source_refs': [{'turn_id': 't1'}]},
                    'prompt': 'unchanged prompt'}}
    row = {'item_id': 'a', 'block': 'original', 'source_refs': [{'turn_id': 't1'}],
           'prompt': 'unchanged prompt'}
    m.verify_preflight_rows(records, parent, [row])
    for rows in [[], [row, row], [{**row, 'prompt': 'changed'}],
                 [{**row, 'block': 'changed'}], [{**row, 'source_refs': []}]]:
        with pytest.raises(ValueError):
            m.verify_preflight_rows(records, parent, rows)
    with pytest.raises(ValueError):
        m.verify_preflight_rows(records + records, parent, [row])
