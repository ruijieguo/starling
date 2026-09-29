"""通过真实原生核心与本地库验证综合回答binding、路由与调用边界。"""
import subprocess
import json
from socialmem_fixtures import source_config
import sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]

@pytest.mark.parametrize('answer_format',['short_answer','long_form','multiple_choice'])
def test_real_native_packet_and_one_answer_request(answer_format,native_core_path):
    program=r'''
import importlib.util,json,sys,tempfile
from pathlib import Path
root=Path(sys.argv[1]);answer_format=sys.argv[2]
sys.path.insert(0,str(root/'scripts'))
p=Path(sys.argv[4])
spec=importlib.util.spec_from_file_location('starling._core',p)
core=importlib.util.module_from_spec(spec);sys.modules['starling._core']=core;spec.loader.exec_module(core)
assert Path(core.__file__).resolve()==p.resolve()
assert hasattr(core,'synthesis_source_answer_packet'),'native synthesis binding missing'
from starling import runtime
import run_socialmem_baseline as runner
import eval_ladder_pipeline as pipe
import eval_ladder as ladder
import eval_judge_audit as audit
import eval_longmemeval as longmem
class ProviderBoundary:
 def __init__(self,text):
  self.prompts=[];self.adapter=core.FakeLLMAdapter();self.adapter.set_default_response(text)
 def extract(self,payload,system):
  self.prompts.append(payload);return self.adapter.extract(payload,system)
history=[{'speaker':name,'text':text,'session_id':session,'turn_index':index,'turn_id':str(index),
 'observed_at':'2025-01-01T00:00:00Z'} for name,text,session,index in
 [('A','以前喜欢茶。','1',1),('B','A changed her view after the visit.','1',2)]]
with tempfile.TemporaryDirectory() as tmp:
 db=Path(tmp)/'test.db';rt=runtime._build_local_store_sqlite_runtime(db);rt.start()
 runner.retain_history_sources(core,rt.adapter,history,'2026-06-01T00:00:00Z')
 config=json.loads(sys.argv[3]);config['answer_policy']='synthesis_v1'
 answer=ProviderBoundary('0' if answer_format=='multiple_choice' else 'A preferred tea.');judge=ProviderBoundary('YES')
 record={'item_id':'fixture','question':'What did A prefer?','history':history,'answer_format':answer_format,
 'answer':0 if answer_format=='multiple_choice' else 'GOLD_NOT_FOR_ANSWER_MODEL','options':['tea','coffee']}
 row=runner._answer_question(record,db,(core,runtime,audit,ladder,pipe,longmem),config,core.StubEmbeddingAdapter(8),answer,judge)
 assert row['status']=='ok',row
 assert len(answer.prompts)==1
 assert len(judge.prompts)==(0 if answer_format=='multiple_choice' else 1)
 assert 'evidence' not in row and row['embedding_request_delta']==0
 assert 'GOLD_NOT_FOR_ANSWER_MODEL' not in answer.prompts[0]
 if answer_format=='multiple_choice':
  old={**config,'answer_policy':'grounded_v1'}
  assert row['prompt']==runner.answer_prompt(core,ladder,record,row['recall'],old)
 else:
  packet=json.loads(row['prompt'].splitlines()[-1])
  assert packet['question']=='What did A prefer?'
  assert packet['semantic_verified'] is False
  assert [(s['source_id'],s['speaker'],s['text']) for s in packet['sources']]==[(1,'A','以前喜欢茶。'),(2,'B','A changed her view after the visit.')]
 for mode in ['hybrid','statements','full']:
  try:runner.validate_answer_policy({**config,'recall_mode':mode})
  except ValueError:pass
  else:raise AssertionError('incompatible recall mode accepted')
'''
    result=subprocess.run([sys.executable,'-c',program,str(ROOT),answer_format,json.dumps(source_config('dialogue')),str(native_core_path)],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
