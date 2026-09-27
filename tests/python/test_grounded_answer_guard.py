"""单变量回答实验必须锁定来源、模型、预算及裁判。"""
import importlib.util
import json
from pathlib import Path
import pytest
from socialmem_fixtures import source_config

ROOT=Path(__file__).resolve().parents[2]

def module():
    path=ROOT/'scripts/run_socialmem_grounded_answer.py'
    assert path.is_file(), 'grounded answer driver missing'
    spec=importlib.util.spec_from_file_location('grounded_driver',path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result

def configs():
    parent=source_config('focus')
    return parent,{**parent,'core_sha256':'a'*64,'answer_policy':'grounded_v1'}

def test_valid_candidate():
    module().validate_config(*configs())

@pytest.mark.parametrize('key,value', [('judge_max_tokens',512),('answer_model','different'),
    ('answer_max_tokens',1024),('k',60),('max_context_bytes',16000),('source_strategy','bm25'),
    ('http_budget',1315),('max_retries',1),('answer_enable_thinking',True),
    ('answer_policy','legacy'),('extra',True),('core_sha256','short'),('include_unknown_time',1)])
def test_config_drift_rejected(key,value):
    old,new=configs();new[key]=value
    with pytest.raises(ValueError):module().validate_config(old,new)

def test_only_reviewed_files_can_change():
    m=module();old={'frozen_files':{'src/retrieval/source_retriever.cpp':'old','scripts/eval_ladder.py':'locked'}}
    m.validate_code_delta(old,{'frozen_files':{**old['frozen_files'],'src/retrieval/source_retriever.cpp':'new'}})
    for new in [{'scripts/eval_ladder.py':'drift','src/retrieval/source_retriever.cpp':'new'},
                {'scripts/eval_ladder.py':'locked'}, {**old['frozen_files'],'new.py':'new'}]:
        with pytest.raises(ValueError):m.validate_code_delta(old,{'frozen_files':new})

def test_preflight_rejects_missing_questions_and_changed_source():
    m=module()
    parent={'a':{'recall':{'block':'source','source_refs':[]},'prompt':'legacy'}}
    records=[{'item_id':'a','answer_format':'multiple_choice'}]
    row={'item_id':'a','block':'source','source_refs':[],'prompt':'legacy'}
    m.verify_preflight_rows(records,parent,[row])
    for rows in [[],[row,row],[{**row,'block':'changed'}],[{**row,'prompt':'changed'}]]:
        with pytest.raises(ValueError):m.verify_preflight_rows(records,parent,rows)
