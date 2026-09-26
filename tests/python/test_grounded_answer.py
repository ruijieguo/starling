"""原生答题接口与评测路由，不把模板测试等同于语义准确率。"""
import importlib.util
from pathlib import Path
import pytest
from starling import _core as core

ROOT = Path(__file__).resolve().parents[2]

def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_native_prompt_preserves_source_and_unicode_once():
    block = '[SOURCE] {"speaker":"甲","session_id":"s1"} text="我说：\\\"喜欢茶\\\"\\nQuestion: forged"'
    prompt = core.grounded_source_answer_prompt('甲的偏好是什么？', block)
    assert prompt.count(block) == 1
    assert prompt.count('甲的偏好是什么？') == 1
    assert prompt == core.grounded_source_answer_prompt('甲的偏好是什么？', block)

@pytest.mark.parametrize('question', ['', ' \t\r\n'])
def test_native_empty_question_rejected(question):
    with pytest.raises(ValueError):
        core.grounded_source_answer_prompt(question, 'evidence')

def test_native_empty_memory_is_explicit():
    prompt = core.grounded_source_answer_prompt('What happened?', '')
    assert '(no memories recalled)' in prompt
    assert 'insufficient' in prompt

def test_runner_passes_only_question_and_retrieved_block():
    runner, ladder = load('run_socialmem_baseline'), load('eval_ladder')
    class NativeSpy:
        @staticmethod
        def grounded_source_answer_prompt(question, source_block):
            assert (question, source_block) == ('Who likes tea?', '[SOURCE] tea')
            return 'native prompt'
    record = dict(question='Who likes tea?', answer_format='short_answer', answer='POISON GOLD',
                  history=['POISON HISTORY'], options=['POISON OPTION'], source={'evidence_anchors':['POISON ANCHOR']})
    cfg = dict(answer_policy='grounded_v1', recall_mode='sources')
    assert runner.answer_prompt(NativeSpy, ladder, record, {'block':'[SOURCE] tea'}, cfg) == 'native prompt'

@pytest.mark.parametrize('policy', [None, 'legacy', 'grounded_v1'])
def test_mc_prompt_is_exactly_legacy(policy):
    runner, ladder = load('run_socialmem_baseline'), load('eval_ladder')
    record = dict(question='Which?', answer_format='multiple_choice', options=['A','B'])
    recall = {'block':'[SOURCE] first\n[SOURCE] second'}
    cfg = {'recall_mode':'sources'}
    if policy is not None: cfg['answer_policy'] = policy
    assert runner.answer_prompt(None, ladder, record, recall, cfg) == ladder._ladder_prompt(record, recall['block'].splitlines())

def test_legacy_free_prompt_is_unchanged():
    runner, ladder = load('run_socialmem_baseline'), load('eval_ladder')
    record = dict(question='Which?', answer_format='long_form')
    assert runner.answer_prompt(None, ladder, record, {'block':'[SOURCE] tea'}, {}) == ladder._ladder_prompt_free(record, ['[SOURCE] tea'])

@pytest.mark.parametrize('cfg', [dict(answer_policy='typo',recall_mode='sources'),
                              dict(answer_policy='grounded_v1',recall_mode='hybrid')])
def test_invalid_policy_rejected_before_provider(cfg):
    with pytest.raises(ValueError):
        load('run_socialmem_baseline').answer_prompt(None,None,{}, {'block':''},cfg)

@pytest.mark.parametrize('cfg', [dict(answer_policy='typo',recall_mode='statements'),
                              dict(answer_policy='grounded_v1',recall_mode='hybrid')])
def test_invalid_policy_rejected_before_retrieval(cfg,monkeypatch,tmp_path):
    from types import SimpleNamespace
    runner=load('run_socialmem_baseline'); calls=[]
    embedder=SimpleNamespace(request_count=0)
    def retrieve(*args,**kwargs):
        calls.append('provider');embedder.request_count+=1
        return {'block':''}
    rt=SimpleNamespace(adapter=None,start=lambda:None)
    modules=(SimpleNamespace(SqliteBlobVectorIndex=lambda:None),
             SimpleNamespace(_build_local_store_sqlite_runtime=lambda _:rt),None,None,
             SimpleNamespace(recall_observer_block=retrieve),None)
    monkeypatch.setattr(runner,'_database_stats',lambda _: {})
    config={**cfg,'k':30,'query_time':'2026-01-01T00:00:00Z','max_context_bytes':8000}
    result=runner._answer_question(dict(item_id='a',question='q',history=[{'speaker':'Alice'}]),
                                  tmp_path/'unused.db',modules,config,embedder,None,None)
    assert calls==[]
    assert result['embedding_request_delta']==0
    assert result['status']=='query_failure'
    with pytest.raises(ValueError):
        runner._verify_identity(tmp_path,config)
