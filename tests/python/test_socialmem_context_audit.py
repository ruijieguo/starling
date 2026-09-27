"""真实C++结构声明渲染边界；不发送外部请求。"""
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest

ROOT=Path(__file__).resolve().parents[2]


def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


@pytest.fixture(scope='module')
def native():
    m=load('run_socialmem_r62_evaluate').engine
    checked=m.validated_build(ROOT/'build/socialmem_20260926_r62_expanded/build')
    _,modules=m.runtime_modules(checked)
    return m,modules


@pytest.fixture
def statement(native,tmp_path):
    m,modules=native;core,runtime,_,_,pipeline,_=modules
    rt=runtime._build_local_store_sqlite_runtime(tmp_path/'statement.db');rt.start()
    pipeline.seed_history_statements(str(rt.adapter.db_path),'audit-fixture',[
        dict(speaker='Ada',text='I prefer tea.',observed_at='2026-01-01T00:00:00Z')])
    with sqlite3.connect(str(rt.adapter.db_path)) as db:
        sid=db.execute('SELECT id FROM statements LIMIT 1').fetchone()[0]
    row=core.get_statement_row(rt.adapter,'default',sid)
    assert row is not None
    yield core,row
    stop=getattr(rt,"stop",None)
    if callable(stop):stop()


def recall_for(core,row,label):
    block=core.render_context_line(row,getattr(core.ContextPackLabel,label))
    return dict(recall=dict(block=block,labels=[label],statement_ids=[row.id],source_refs=[],
        source_count=0,statement_count=1,context_bytes=len(block.encode())))


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
@pytest.mark.parametrize('label',['FACT','BELIEF','HEARSAY','INFERRED','COMMON','TODO','CONFLICT'])
def test_native_statement_context_passes_audit(native,statement,label):
    m,_=native;core,row=statement;receipt=recall_for(core,row,label)
    packet=json.loads(core.grounded_memory_answer_packet('What does Ada prefer?',json.dumps(receipt['recall'])))
    assert len(packet['statements'])==1
    m.validate_context(core,{'question':'What does Ada prefer?'},receipt,{'holders':{}},{},lambda sid:row if sid==row.id else None)


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
@pytest.mark.parametrize('fault',['missing','text'])
def test_native_statement_audit_rejects_missing_or_changed_rows(native,statement,fault):
    m,_=native;core,row=statement;receipt=recall_for(core,row,'FACT')
    if fault=='text':
        receipt['recall']['block']=receipt['recall']['block'].replace('tea','coffee')
        receipt['recall']['context_bytes']=len(receipt['recall']['block'].encode())
    with pytest.raises(ValueError,match='statement differs'):
        m.validate_context(core,{'question':'What does Ada prefer?'},receipt,{'holders':{}},{},lambda _:None if fault=='missing' else row)
