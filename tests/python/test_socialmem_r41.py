"""R4.1 运行器配置和封存边界。"""
import importlib.util
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]

def driver():
    spec=importlib.util.spec_from_file_location('r41_driver',ROOT/'scripts/run_socialmem_r41.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def test_r41_uses_new_cpp_profile_and_preserves_budget():
    d=driver();parent=json.loads((ROOT/'build/socialmem_20260921_structured_eval_hybrid_holder_isolation_r35_dashscope/config.json').read_text())
    cfg=d.candidate_config(parent,'a'*64)
    assert cfg['source_strategy']=='evidence_profile_v3'
    assert cfg['arm']=='r41_subject_topic_timeline'
    assert cfg['http_budget']==600
    d.validate_config(parent,cfg)

def test_r41_rejects_v2_or_answer_scope_drift():
    d=driver();parent=json.loads((ROOT/'build/socialmem_20260921_structured_eval_hybrid_holder_isolation_r35_dashscope/config.json').read_text())
    cfg=d.candidate_config(parent,'b'*64)
    for key,value in [('source_strategy','evidence_profile_v2'),('answer_policy','grounded_memory_v1'),('http_budget',601)]:
        with pytest.raises(ValueError):d.validate_config(parent,{**cfg,key:value})

def test_r41_task_order_is_same_paired_contract():
    d=driver();records=[{'item_id':str(i)} for i in range(2)]
    tasks=d.task_order(records)
    assert [(t['item_id'],t['arm']) for t in tasks]==[
        ('0','retrieval'),('0','native_answer'),('1','native_answer'),('1','retrieval')]

def test_r42_driver_selects_support_lane_without_changing_budget():
    spec=importlib.util.spec_from_file_location('r42_driver',ROOT/'scripts/run_socialmem_r42.py')
    d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
    parent=json.loads((ROOT/'build/socialmem_20260921_structured_eval_hybrid_holder_isolation_r35_dashscope/config.json').read_text())
    cfg=d.candidate_config(parent,'c'*64)
    assert cfg['source_strategy']=='evidence_profile_v4'
    assert cfg['arm']=='r42_support_lane' and cfg['http_budget']==600
    d.validate_config(parent,cfg)
