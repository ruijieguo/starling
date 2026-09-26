"""修复后的全量基线不能带失败范围启动，也不能改变时间/评分协议。"""
import importlib.util
from pathlib import Path
import pytest
from test_source_full_guard import prepared


def module():
    path=Path(__file__).resolve().parents[2]/'scripts/run_socialmem_baseline_recovered.py'
    assert path.is_file(), 'recovered baseline driver missing'
    spec=importlib.util.spec_from_file_location('recovered',path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def protocol():
    plan,cfg,groups=prepared()
    plan['failed_scopes']=[]
    cfg.update(preserve_invalid_time=True,include_unknown_time=True,workers=4,
               created_at='2026-06-01T00:00:00Z',
               scoring='existing_ladder_mc_and_single_yes_no_local_protocol')
    return plan,cfg,groups


def test_accepts_complete_fixed_baseline():
    module().validate_protocol(*protocol())


@pytest.mark.parametrize('field,value',[
    ('preserve_invalid_time',False),('include_unknown_time',False),('include_unknown_time',1),
    ('workers',8),('created_at','2025-01-01T00:00:00Z'),('scoring','loose'),
    ('k',30),('max_retries',1),('judge_enable_thinking',False)])
def test_protocol_drift_rejected_before_requests(field,value):
    plan,cfg,groups=protocol();cfg[field]=value
    with pytest.raises(ValueError):module().validate_protocol(plan,cfg,groups)


def test_failed_scope_cannot_be_prefilled_as_zero():
    plan,cfg,groups=protocol();plan['failed_scopes']=['0']
    with pytest.raises(ValueError):module().validate_protocol(plan,cfg,groups)


def test_incomplete_manifest_rejected(tmp_path):
    plan,_,_=protocol();plan['files']={}
    with pytest.raises(ValueError):module().verify_manifest(tmp_path,plan)
