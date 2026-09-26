"""固定对照的晋升、失败计零与来源保留分析。"""
import importlib.util
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
def module():
    p=ROOT/'scripts/analyze_socialmem_synthesis_answer.py';assert p.is_file(),'synthesis analyzer missing'
    spec=importlib.util.spec_from_file_location('synthesis_analysis',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
@pytest.mark.parametrize('delta,lower,gain,truncated,tokens,want',[
 (37/733,.001,37,15,6060610,True),(36/733,.001,36,15,6060610,False),
 (.1,0,50,0,4000000,False),(.1,.01,0,0,4000000,False),
 (.1,.01,50,16,4000000,False),(.1,.01,50,0,6060611,False)])
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


def test_empty_both_ok_subset_has_no_invented_accuracy_or_interval():
    m=module()
    row=m.paired_subset([],{}, {})
    assert row['n']==0
    assert row['parent_accuracy'] is None and row['candidate_accuracy'] is None
    assert row['delta'] is None and row['network_bootstrap_delta_95ci'] is None
    assert row['parent_correct']==row['candidate_correct']==0


def terminal_fixture(tmp_path):
    import json,sqlite3
    folder=tmp_path/'runs'/'g'/'questions';folder.mkdir(parents=True)
    row={'item_id':'a','fingerprint':'fp','terminal':True,'correct':False,'status':'answer_failure',
         'embedding_request_delta':0,'native_attempt_count':1,
         'answer':{'response':{'attempt_count':1,'http_attempts':[{'attempt':1,'response_body':''}],
                              'raw_http_response':'','ok':False}}}
    (folder/'a.json').write_text(json.dumps(row))
    (folder/'a.started').write_text(json.dumps({'item_id':'a','fingerprint':'fp','reservation':{'id':'r','upper_bound':2}}))
    with sqlite3.connect(tmp_path/'request-ledger.sqlite') as con:
        con.execute('CREATE TABLE reservations (id text, scope text, stage text, state text, actual integer, upper_bound integer)')
        con.execute("INSERT INTO reservations VALUES ('r','g','question:a','settled',1,2)")
    return row,[{'item_id':'a','answer_format':'short_answer'}]

def test_terminal_receipts_require_identity_and_real_request_accounting(tmp_path):
    import copy
    m=module();row,records=terminal_fixture(tmp_path)
    assert m.verify_terminal_run(tmp_path,[row],records,'fp',2)['known_requests']==1
    for patch in [{'fingerprint':'wrong'},{'embedding_request_delta':1},{'native_attempt_count':3},
                  {'evidence':{}},{'terminal':False},{'correct':True}]:
        with pytest.raises(ValueError):m.verify_terminal_run(tmp_path,[{**row,**patch}],records,'fp',2)
    bad=copy.deepcopy(row);bad['answer']['response']['http_attempts'].append({'attempt':2,'response_body':''})
    with pytest.raises(ValueError):m.verify_terminal_run(tmp_path,[bad],records,'fp',2)
    with pytest.raises(ValueError):m.verify_terminal_run(tmp_path,[row],records,'fp',0)
    (tmp_path/'runs/g/questions/a.started').unlink()
    with pytest.raises(ValueError):m.verify_terminal_run(tmp_path,[row],records,'fp',2)

def test_missing_ledger_fails_without_creating_one(tmp_path):
    m=module();row,records=terminal_fixture(tmp_path);path=tmp_path/'request-ledger.sqlite';path.unlink()
    with pytest.raises(ValueError):m.verify_terminal_run(tmp_path,[row],records,'fp',2)
    assert not path.exists()

def test_unknown_terminal_attempts_charge_full_reserved_bound(tmp_path):
    import sqlite3
    m=module();row,records=terminal_fixture(tmp_path)
    row.update(budget_unknown=True,status='technical_failure')
    with sqlite3.connect(tmp_path/'request-ledger.sqlite') as con:
        con.execute("UPDATE reservations SET state='reserved',actual=NULL")
    result=m.verify_terminal_run(tmp_path,[row],records,'fp',2)
    assert result['known_requests']==1 and result['charged_requests']==2 and result['unknown_budget_receipts']==1
