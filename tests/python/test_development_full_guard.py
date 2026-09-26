"""全文诊断只改变上下文来源，不能同时改模型或裁判。"""
import importlib.util,json
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
def module():
    path=ROOT/'scripts/run_socialmem_development_full.py'
    assert path.exists(),'development full entry missing'
    spec=importlib.util.spec_from_file_location('development_full',path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def configs():
    parent=json.loads((ROOT/'build/socialmem_20260917_source_full/config.json').read_text())
    return parent,{**parent,'recall_mode':'full','http_budget':101}
def test_full_context_config_is_accepted():module().validate_config(*configs())
@pytest.mark.parametrize('key,value',[('core_sha256','changed'),('answer_model','other'),('judge_max_tokens',512),('answer_enable_thinking',None),('http_budget',102)])
def test_unrelated_configuration_changes_are_rejected(key,value):
    parent,candidate=configs();candidate[key]=value
    with pytest.raises(ValueError):module().validate_config(parent,candidate)
def test_frozen_parent_prompt_change_is_rejected():
    parent={'frozen_files':{'scripts/eval_ladder.py':'original'}}
    candidate={'frozen_files':{**parent['frozen_files'],'scripts/run_socialmem_development_full.py':'a','scripts/run_socialmem_source_speaker.py':'b','tests/python/test_development_full_guard.py':'c'}}
    module().validate_code_delta(parent,candidate)
    candidate['frozen_files']['scripts/eval_ladder.py']='changed'
    with pytest.raises(ValueError):module().validate_code_delta(parent,candidate)
