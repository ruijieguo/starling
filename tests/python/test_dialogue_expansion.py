"""通过实际C++核心验证binding和编排；不实现Python检索替身。"""
import subprocess
import json
from socialmem_fixtures import source_config
import sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]

@pytest.mark.parametrize('boundary',['pipeline','runner','private_gap'])
def test_native_dialogue_configuration_reaches_retrieval(boundary,native_core_path):
    program=r'''
import importlib.util,json,sys,tempfile
from pathlib import Path
root=Path(sys.argv[1]);boundary=sys.argv[2]
sys.path.insert(0,str(root/'scripts'))
path=Path(sys.argv[4])
spec=importlib.util.spec_from_file_location('starling._core',path)
core=importlib.util.module_from_spec(spec);sys.modules['starling._core']=core;spec.loader.exec_module(core)
assert Path(core.__file__).resolve()==path.resolve()
assert hasattr(core.ObserverQuery(),'source_seed_k'),'native seed budget binding missing'
from starling import runtime
import run_socialmem_baseline as runner
import eval_ladder_pipeline as pipe
import eval_ladder as ladder
import eval_judge_audit as audit
import eval_longmemeval as longmem
history=[{'speaker':person,'text':text,'session_id':'s','turn_index':index,'turn_id':str(index),
          'observed_at':'2025-01-01T00:00:00Z'} for person,text,index in
         [('Carol','Earlier background',8),('Bob','Are you sure?',9),('Alice','I prefer tea',10),('Carol','Confirmed',11)]]
with tempfile.TemporaryDirectory() as tmp:
 db=Path(tmp)/'test.db';rt=runtime._build_local_store_sqlite_runtime(db);rt.start()
 runner.retain_history_sources(core,rt.adapter,history,'2026-06-01T00:00:00Z')
 embedder=core.StubEmbeddingAdapter(8)
 cfg=json.loads(sys.argv[3])
 cfg.update(source_strategy='focused_dialogue',source_seed_k=1,source_seed_max_context_bytes=1000,
            source_dialogue_radius=2,k=5,max_context_bytes=4000)
 if boundary=='runner':
  answer=core.FakeLLMAdapter();answer.set_default_response('tea')
  judge=core.FakeLLMAdapter();judge.set_default_response('YES')
  record={'item_id':'fixture','question':'What does Alice prefer?','history':history,'answer_format':'short_answer','answer':'tea'}
  row=runner._answer_question(record,db,(core,runtime,audit,ladder,pipe,longmem),cfg,embedder,answer,judge)
  assert row['status']=='ok',row
  assert 'evidence' not in row
  result=row['recall']
 else:
  result=pipe.recall_observer_block(core,adapter=rt.adapter,embedder=embedder,index=core.SqliteBlobVectorIndex(),
   question='What does Alice prefer?',allowed_holders=['Alice','Carol'] if boundary=='private_gap' else ['Alice','Bob','Carol'],
   mode='sources',now_iso=cfg['query_time'],k=5,max_context_bytes=4000,source_strategy='focused_dialogue',
   source_seed_k=1,source_seed_max_context_bytes=1000,source_dialogue_radius=2)
 assert [r['turn_index'] for r in result['source_refs']]==([10,11] if boundary=='private_gap' else [8,9,10,11]),result
 assert result['source_diagnostics']['dialogue_seed_count']==1
 assert result['context_bytes']==len(result['block'].encode())<=4000
 if boundary=='runner':assert row['embedding_request_delta']==0
'''
    result=subprocess.run([sys.executable,'-c',program,str(ROOT),boundary,json.dumps(source_config('capacity')),str(native_core_path)],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
