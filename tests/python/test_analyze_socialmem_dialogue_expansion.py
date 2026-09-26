"""固定对照的晋升、失败计零与来源保留分析。"""
import importlib.util
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
def module():
    p=ROOT/'scripts/analyze_socialmem_dialogue_expansion.py';assert p.is_file(),'dialogue analyzer missing'
    spec=importlib.util.spec_from_file_location('dialogue_analysis',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
@pytest.mark.parametrize('delta,lower,gain,truncated,tokens,want',[
 (37/733,.001,37,15,6370710,True),(36/733,.001,36,15,6370710,False),
 (.1,0,50,0,4000000,False),(.1,.01,0,0,4000000,False),
 (.1,.01,50,16,4000000,False),(.1,.01,50,0,6370711,False)])
def test_precommitted_gate(delta,lower,gain,truncated,tokens,want):
    assert module().promotion(delta,lower,gain,truncated,tokens) is want

def test_sealed_analysis_cannot_rewrite(tmp_path):
    (tmp_path/'completion-seal.json').write_text('{}');p=tmp_path/'paired-analysis.json';p.write_text('sealed')
    with pytest.raises(ValueError,match='sealed experiment cannot analyze'):module().analyze(tmp_path)
    assert p.read_text()=='sealed'

def test_failure_does_not_publish_partial_report(tmp_path):
    # A real incomplete archive must fail closed without publishing any report.
    with pytest.raises((FileNotFoundError,ValueError,RuntimeError)):module().analyze(tmp_path)
    assert not (tmp_path/'paired-analysis.json').exists()
    assert not (tmp_path/'paired-details.json').exists()

REPORTS=('paired-details.json','mechanism-cases.json','paired-analysis.json')

def fake_computation(work, output):
    for name in REPORTS:(output/name).write_text('{"verified":true}')
    return {'verified':True}

def test_publication_failure_cannot_leave_mixed_reports(tmp_path,monkeypatch):
    m=module();monkeypatch.setattr(m,'_compute',fake_computation)
    replace=m.os.replace;calls=0
    def fail_publication(source,target):
        nonlocal calls
        calls+=1
        if Path(source).is_dir() or calls==2:raise OSError('injected publication failure')
        return replace(source,target)
    monkeypatch.setattr(m.os,'replace',fail_publication)
    with pytest.raises(OSError,match='injected publication failure'):m.analyze(tmp_path)
    assert not (tmp_path/'analysis-results').exists()
    assert all(not (tmp_path/name).exists() for name in REPORTS)

def test_reports_publish_together_and_cannot_be_overwritten(tmp_path,monkeypatch):
    m=module();monkeypatch.setattr(m,'_compute',fake_computation)
    assert m.analyze(tmp_path)=={'verified':True}
    folder=tmp_path/'analysis-results'
    assert {p.name for p in folder.iterdir()}==set(REPORTS)
    before={p.name:p.read_bytes() for p in folder.iterdir()}
    with pytest.raises(ValueError,match='published analysis cannot be overwritten'):m.analyze(tmp_path)
    assert {p.name:p.read_bytes() for p in folder.iterdir()}==before
