"""离线分析通过真实原生核心；时间未知与索引来自原始回执。"""
import hashlib
import json
from pathlib import Path
import sys

import pytest
from starling import _core
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False))
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def inputs(tmp_path):
    source='Mina: I am relieved about the rehearsal. Can you bring the chairs?'
    row=dict(holder='Mina', holder_perspective='FIRST_PERSON', subject='Mina', subject_kind='cognizer',
             predicate='feels', object='relieved about the rehearsal', modality='BELIEVES', polarity='POS',
             nesting_depth=0, confidence=None, evidence=dict(clause_id='c0',actor='Mina',attributed_to=None,
             assertion_scope='ASSERTED',scope_markers=['ASSERTED'],topic=None,time_text='',event_time=None))
    bad=json.loads(json.dumps(row));bad['evidence']['actor']='Other'
    records=[]
    for key,ok,raw in [('complete',True,json.dumps(dict(schema_version=2,statements=[row,bad,row]))),
                       ('empty',True,'{"schema_version":2,"statements":[]}'),
                       ('timeout',False,None),('broken',True,'{} {}')]:
        p=tmp_path/f'{key}.json'
        digest=write(p,{'ok':ok,'raw_response':raw,'parse_result':None})
        records.append(dict(id=key,holder='Mina',passage=source,source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                            receipt_path=str(p),receipt_sha256=digest))
    manifest=tmp_path/'manifest.json'
    write(manifest,dict(schema_version=1,native_core_sha256=hashlib.sha256(Path(_core.__file__).read_bytes()).hexdigest(),records=records))
    notes=tmp_path/'notes.json'
    write(notes,[dict(record_id='complete',state_id='feeling',clause_id='c0',predicate='feels',raw_indexes=[0,2],reason='人工审阅重复情绪候选'),
                 dict(record_id='empty',state_id='feeling',clause_id='c0',predicate='feels',raw_indexes=[],reason='完整响应未生成'),
                 dict(record_id='timeout',state_id='feeling',clause_id='c0',predicate='feels',raw_indexes=[],reason='输出未知')])
    return manifest,notes,Path(_core.__file__),tmp_path/'out'


def test_native_replay_distinguishes_missing_unknown_and_duplicate_indexes(inputs):
    import analyze_socialmem_claim_scope as analysis
    report=analysis.run_analysis(*inputs)
    rows={r['id']:r for r in report['records']}
    assert rows['complete']['generated_candidates']==3
    assert [r['candidate_index'] for r in rows['complete']['parse_result']['row_diagnostics']]==[0,None,1]
    assert rows['complete']['historical_diagnostics_status']=='unknown'
    assert rows['empty']['coverage'][0]['generation_status']=='not_generated'
    assert rows['timeout']['coverage'][0]['generation_status']=='unknown'
    assert rows['timeout']['parse_result'] is None
    assert rows['broken']['generated_candidates'] is None
    assert all(r['admission_status']=='not_executed' for r in rows.values())
    assert report['external_requests']==0
    with pytest.raises(FileExistsError):analysis.run_analysis(*inputs)


@pytest.mark.parametrize('mutation',['source','receipt','core','index','clause','record'])
def test_analysis_rejects_identity_or_annotation_drift(inputs,mutation):
    import analyze_socialmem_claim_scope as analysis
    manifest,notes,stage,out=inputs
    m=json.loads(manifest.read_text());n=json.loads(notes.read_text())
    if mutation=='source':m['records'][0]['passage']='different'
    elif mutation=='receipt':m['records'][0]['receipt_sha256']='0'*64
    elif mutation=='core':m['native_core_sha256']='0'*64
    elif mutation=='index':n[0]['raw_indexes']=[99]
    elif mutation=='clause':n[0]['clause_id']='c88'
    elif mutation=='record':n[0]['record_id']='absent'
    write(manifest,m);write(notes,n)
    with pytest.raises((ValueError,RuntimeError)):analysis.run_analysis(*inputs)
    assert not out.exists()
