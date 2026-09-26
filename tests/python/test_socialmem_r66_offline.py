"""R6.6真实八库离线消融，独立进程加载新核心并重放；不构造provider。"""
import importlib.util
from pathlib import Path
import shutil

import pytest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'scripts/run_socialmem_r66_offline.py'


def driver():
    assert SCRIPT.is_file(), '缺少R6.6原生离线消融入口'
    spec=importlib.util.spec_from_file_location('r66_test',SCRIPT)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


@pytest.mark.parametrize('stage',['prepare','run'])
def test_output_cannot_overwrite_before_loading_inputs(tmp_path,stage):
    m=driver();out=tmp_path/'exists';out.mkdir()
    with pytest.raises(ValueError,match='already exists'):getattr(m,stage)(tmp_path/'missing',out)


def test_wrong_origin_rejected_without_creating_output(tmp_path):
    m=driver();origin=tmp_path/'bad';origin.mkdir();(origin/'seal.json').write_text('{}')
    with pytest.raises(ValueError,match='seal'):m.prepare(origin,tmp_path/'out')
    assert not (tmp_path/'out').exists()


def test_replay_allows_live_document_update_but_rejects_live_program_drift(tmp_path, monkeypatch):
    m=driver();out=tmp_path/'snapshot';live=tmp_path/'live';files={}
    for name in m.OWN_FILES:
        for base in (out/'source',live):
            p=base/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('frozen')
        files[name]=m.sha(out/'source'/name)
    m.write(out/'program.json',dict(files=files,core_sha256=m.CORE_SHA256))
    monkeypatch.setattr(m,'ROOT',live)
    doc=next(live.rglob('*.md'));doc.write_text('结果已同步')
    m.verify_execution(out)
    code=live/'scripts/run_socialmem_r66_offline.py';code.write_text('changed')
    with pytest.raises(ValueError,match='execution'):m.verify_execution(out)


@pytest.fixture(scope='module')
def prepared(tmp_path_factory):
    m=driver();original=m.load_inputs;cache={}
    def inputs(origin):
        assert Path(origin).resolve()==m.DEFAULT_ORIGIN
        m.previous.parent.verify_pinned(origin,m.ORIGIN_SEAL)
        if not cache:cache.update(original(origin))
        return cache
    m.load_inputs=inputs
    out=tmp_path_factory.mktemp('r66-prepare')/'prepare'
    with pytest.MonkeyPatch.context() as patch:
        def forbidden(*a,**k):pytest.fail('离线阶段构造provider')
        patch.setattr(m.e,'make_adapters',forbidden)
        result=m.prepare(m.DEFAULT_ORIGIN,out);data=m.check(out)
    assert result['external_requests']==0
    return m,out,data


def test_prepared_runtime_pins_new_core_and_same_eight_databases(prepared):
    m,out,data=prepared;p=m.read(out/'plan.json')
    assert p['questions']==133 and p['tasks']==266
    assert p['core_sha256']==m.CORE_SHA256!=m.e.CORE_SHA256
    assert len(p['database_sha256'])==8
    assert p['arms']=={'v9':['evidence_profile_v9','sources',20],'v10':['evidence_profile_v10','sources',20]}
    assert p['expected_external_requests']==0
    assert m.sha(next((out/'native-runtime/frozen/python/starling').glob('_core*.so')))==m.CORE_SHA256
    assert len(list((out/'historical-contexts').glob('*.json')))==133


@pytest.fixture(scope='module')
def offline(prepared,tmp_path_factory):
    m,source,data=prepared;out=tmp_path_factory.mktemp('r66-offline')/'run'
    before={g:m.sha(data['checked']['built']/'runs'/g/'frozen.db') for g in data['checked']['databases']}
    result=m.run(source,out)
    assert before=={g:m.sha(data['checked']['built']/'runs'/g/'frozen.db') for g in before}
    return m,out,result


def test_real_native_replay_and_baseline_byte_identity(offline):
    m,out,result=offline
    assert result['state']=='complete' and result['healthy_contexts']==266
    assert result['external_requests']==0 and result['control_mismatches']==0
    assert result['arms']['v9']['anchor_hit']==194 and result['arms']['v9']['anchors']==263
    assert result['changed_contexts']>0
    before=m.inventory(out);checked=m.check(out)
    assert checked['summary']==result and m.inventory(out)==before


def reseal(m,out):
    seal=m.read(out/'seal.json');files=m.inventory(out);files.pop('seal.json');seal['files']=files;m.write(out/'seal.json',seal)


@pytest.mark.parametrize('fault',['context','missing','core_identity','summary','database_identity'])
def test_resealed_native_result_drift_rejected(offline,tmp_path,fault):
    m,source,_=offline;out=tmp_path/'copy';shutil.copytree(source,out)
    if fault in ('context','missing','core_identity'):
        p=next((out/'v10/recalls').glob('*.json'))
        if fault=='missing':p.unlink()
        else:
            r=m.read(p)
            if fault=='context':r['recall']['block']+=' forged'
            else:r['core_sha256']='forged'
            m.write(p,r)
    elif fault=='database_identity':
        p=out/'plan.json';r=m.read(p);r['database_sha256'][next(iter(r['database_sha256']))]='forged';m.write(p,r)
    else:
        p=out/'summary.json';r=m.read(p);r['arms']['v10']['anchor_hit']+=1;m.write(p,r)
    reseal(m,out)
    with pytest.raises(ValueError):m.check(out)


def test_resealed_native_binary_drift_rejected(prepared,tmp_path):
    m,source,_=prepared;out=tmp_path/'copy';shutil.copytree(source,out)
    p=next((out/'native-runtime/frozen/python/starling').glob('_core*.so'));p.write_bytes(p.read_bytes()+b'corruption')
    reseal(m,out)
    with pytest.raises(ValueError):m.check(out)
