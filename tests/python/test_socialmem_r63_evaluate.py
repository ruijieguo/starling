"""R6.3离线恢复完整真实上下文；所有外部provider调用均禁止。"""
from copy import deepcopy
import importlib.util
from pathlib import Path
import shutil
import sqlite3

import pytest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'scripts/run_socialmem_r63_evaluate.py'
ORIGIN=ROOT/'build/socialmem_20260926_r62_expanded/retrieve'


def driver():
    assert SCRIPT.is_file(), 'R6.3恢复入口尚未实现'
    spec=importlib.util.spec_from_file_location('r63_evaluation_test',SCRIPT)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


@pytest.fixture(scope='module')
def recovered(tmp_path_factory):
    m=driver();out=tmp_path_factory.mktemp('r63-parent')/'recovered'
    def forbidden(*args,**kwargs):pytest.fail('离线恢复构造了provider或发送了请求')
    m.engine.make_embedder=m.engine.make_adapters=m.engine.query_one=forbidden
    before=m.engine.inventory(ORIGIN)
    result=m.recover(ORIGIN,out)
    assert m.engine.inventory(ORIGIN)==before
    return m,out,result


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_recovery_validates_all_real_contexts_without_requests(recovered):
    m,out,result=recovered;proof=m.engine.read(out/'recovery.json')
    assert result['state']=='complete' and result['healthy_terminals']==266
    assert proof['new_external_requests']==0 and proof['inherited_embedding_requests']==1336
    assert proof['mode']=='revalidated_recovery' and proof['origin_state']=='incomplete'
    assert m.check(out)['summary']==result
    for arm in m.engine.ARMS:
        assert m.engine.inventory(out/arm)==m.engine.inventory(ORIGIN/arm)


def test_existing_recovery_output_is_refused_before_reading_input(tmp_path):
    m=driver();out=tmp_path/'exists';out.mkdir()
    with pytest.raises(ValueError,match='already exists'):m.recover(tmp_path/'missing',out)


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_changed_origin_is_rejected_before_provider(tmp_path):
    m=driver();origin=tmp_path/'origin';shutil.copytree(ORIGIN,origin)
    path=next((origin/'baseline/recalls').glob('*.json'));path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(ValueError,match='seal|inventory'):m.recover(origin,tmp_path/'out')
    assert not (tmp_path/'out').exists()


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
@pytest.mark.parametrize('fault',['context','started','ledger','recovery'])
def test_resealed_recovery_tampering_is_rejected(recovered,tmp_path,fault):
    m,source,_=recovered;out=tmp_path/'copy';shutil.copytree(source,out)
    if fault=='context':
        path=next((out/'baseline/recalls').glob('*.json'));row=m.engine.read(path)
        row['recall']['block']+=' forged';m.engine.write(path,row)
    elif fault=='started':
        path=next((out/'started').glob('*.json'));row=m.engine.read(path)
        row['native_invoked']=False;m.engine.write(path,row)
    elif fault=='ledger':
        with sqlite3.connect(out/'request-ledger.sqlite') as db:db.execute('UPDATE reservations SET actual=0 WHERE actual>0')
    else:
        path=out/'recovery.json';row=m.engine.read(path);row['new_external_requests']=1;m.engine.write(path,row)
    seal=m.engine.read(out/'seal.json');files=m.engine.inventory(out);files.pop('seal.json');seal['files']=files;m.engine.write(out/'seal.json',seal)
    with pytest.raises(ValueError,match='recovery|copied|context|ledger|source|settlement|started'):m.check(out)
