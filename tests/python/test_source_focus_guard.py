"""人物检索对照必须保留模型/评分/来源/题集；先测试再实现编排。"""
import importlib.util
import json
from pathlib import Path
import pytest
from socialmem_fixtures import source_config
ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'build/socialmem_20260917_k30_controlled'

def module():
    p=ROOT/'scripts/run_socialmem_source_focus.py'
    assert p.is_file(), 'source focus driver missing'
    spec=importlib.util.spec_from_file_location('focus_driver',p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def config():
    old=source_config('k30')
    return old,{**old,'core_sha256':'a'*64,'source_strategy':'focused'}

def test_valid_candidate():
    module().validate_config(*config())

@pytest.mark.parametrize('field,value',[
    ('answer_model','different'),('k',60),('max_context_bytes',12000),('http_budget',1315),
    ('answer_enable_thinking',None),('answer_max_tokens',1024),('judge_max_tokens',512),
    ('max_retries',1),('source_strategy','bm25'),('source_strategy','invalid'),
    ('core_sha256','short'),('include_unknown_time',1),('extra','unreviewed')])
def test_config_drift_rejected(field,value):
    old,new=config();new[field]=value
    with pytest.raises(ValueError):module().validate_config(old,new)

def test_code_drift_is_scoped_to_reviewed_files():
    m=module();old={'frozen_files':{'src/retrieval/source_retriever.cpp':'old','scripts/eval_ladder.py':'prompt'}}
    m.validate_code_delta(old,{'frozen_files':{**old['frozen_files'],'src/retrieval/source_retriever.cpp':'new'}})
    for files in [{'scripts/eval_ladder.py':'changed','src/retrieval/source_retriever.cpp':'new'},
                  {'src/retrieval/source_retriever.cpp':'new'}, {**old['frozen_files'],'new.py':'new'}]:
        with pytest.raises(ValueError):m.validate_code_delta(old,{'frozen_files':files})

def test_ablation_must_preserve_baseline_and_preregistered_choice():
    m=module()
    result={'verified':True,'questions':733,'core_sha256':'a'*64,'selected':'focused',
            'profiles':{'bm25':{'hits':560,'zero':293},'focused':{'hits':800,'zero':100},
                        'focused_window':{'hits':780,'zero':110}}}
    m.validate_ablation(result,'focused','a'*64)
    for strategy,digest in [('focused_window','a'*64),('focused','b'*64)]:
        with pytest.raises(ValueError):m.validate_ablation(result,strategy,digest)
    result['profiles']['focused']['hits']=540
    with pytest.raises(ValueError):m.validate_ablation(result,'focused','a'*64)
