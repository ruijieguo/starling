"""真实C++绑定、本机HTTP与运行器账本边界；不请求外部模型。"""
import subprocess
import json
from socialmem_fixtures import source_config
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]

@pytest.mark.parametrize('scenario',['ok','planner_failure','final_truncation'])
def test_native_flow_accounts_for_every_stage(scenario):
    program=r'''
import importlib.util,json,os,sys,threading,tempfile
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
root=Path(sys.argv[1]);scenario=sys.argv[2]
sys.path.insert(0,str(root/'scripts'))
import run_socialmem_baseline as runner
core_path=root/'build/python/starling/_core.cpython-314-darwin.so'
spec=importlib.util.spec_from_file_location('starling._core',core_path)
native=importlib.util.module_from_spec(spec);sys.modules['starling._core']=native;spec.loader.exec_module(native)
from starling import _core as core
assert Path(core.__file__).resolve()==core_path.resolve(),core.__file__
assert hasattr(core,'answer_with_evidence'), 'native evidence answer binding missing'
cfg=json.loads(sys.argv[3]);cfg.update(answer_policy='evidence_v1',http_budget=1895)
from starling import runtime
import eval_judge_audit as audit
import eval_ladder as ladder
import eval_ladder_pipeline as pipe
import eval_longmemeval as longmem
requests=[]
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])));requests.append(payload)
  idx=len(requests)
  if idx==1 and scenario=='planner_failure':
   body=b'{}';self.send_response(500)
  else:
   value=json.dumps({'evidence':[{'source_id':1,'speaker':'Nora','quote':'green tea','interpretation':'drink preference'}]}) if idx==1 else ('green tea' if idx==2 else 'YES')
   finish='length' if idx==2 and scenario=='final_truncation' else 'stop'
   body=json.dumps({'choices':[{'message':{'content':value},'finish_reason':finish}], 'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15}}).encode();self.send_response(200)
  self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
try:
 for role in ['extract','answer','embedding']:cfg[role+'_endpoint']=f'http://127.0.0.1:{server.server_port}/v1'
 os.environ['DASHSCOPE_API_KEY']='local-fixture'
 _,embedder,answerer,judge=runner._make_native_adapters(core,cfg)
 history=[{'speaker':'Nora','text':'Nora preferred green tea.','session_id':'s1','turn_index':1,'turn_id':'t1','observed_at':'2025-01-01T00:00:00Z'}]
 with tempfile.TemporaryDirectory() as tmp:
  db=Path(tmp)/'test.db';rt=runtime._build_local_store_sqlite_runtime(db);rt.start()
  runner.retain_history_sources(core,rt.adapter,history,cfg['created_at'])
  record={'item_id':'synthetic','question':'What does Nora prefer?','history':history,'answer_format':'short_answer','answer':'green tea'}
  row=runner._answer_question(record,db,(core,runtime,audit,ladder,pipe,longmem),cfg,embedder,answerer,judge)
  assert row['status']==('answer_failure' if scenario=='final_truncation' else 'ok'),row
  assert row['correct']==(scenario!='final_truncation'),row
  assert row['native_attempt_count']==len(requests)==(2 if scenario=='final_truncation' else 3),row
  assert row['evidence_fallback']==(scenario=='planner_failure'),row
  assert row['evidence']['response']['attempt_count']==1
  assert len(row['evidence']['response']['http_attempts'])==1
  assert row['evidence']['response']['raw_http_response']
  assert row['answer']['response']['raw_http_response']
  assert row['embedding_request_delta']==0
  assert [p['max_tokens'] for p in requests]==([1024,1024] if scenario=='final_truncation' else [1024,1024,64])
  assert all(p['model']=='qwen3.8-27b' for p in requests)
  assert requests[0]['enable_thinking'] is False and requests[1]['enable_thinking'] is False
  assert requests[0]['messages'][0]['content']==row['prompt']
  assert requests[1]['messages'][0]['content']==row['final_prompt']
finally:
 server.shutdown();server.server_close();thread.join()
'''
    result=subprocess.run([sys.executable,'-c',program,str(ROOT),scenario,json.dumps(source_config('capacity'))],capture_output=True,text=True,timeout=45)
    assert result.returncode==0,result.stdout+result.stderr
