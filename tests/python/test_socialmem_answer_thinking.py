"""回答思考参数仅映射到回答角色；通过实际原生HTTP边界观察。"""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[2]
@pytest.mark.parametrize('value',['null','false','true'])
def test_answer_thinking_parameter_isolated_from_extraction_and_judge(value):
    program=r'''
import importlib.util,json,os,sys,threading
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from starling import _core
spec=importlib.util.spec_from_file_location('runner',Path(sys.argv[1])/'scripts/run_socialmem_baseline.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
requests=[]
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  requests.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
  body=b'{"choices":[{"message":{"content":"[]"},"finish_reason":"stop"}]}'
  self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
try:
 cfg=json.loads((Path(sys.argv[1])/'build/socialmem_20260916_baseline/config.json').read_text())
 for role in ['extract','answer','embedding']:cfg[role+'_endpoint']=f'http://127.0.0.1:{server.server_port}/v1'
 os.environ['DASHSCOPE_API_KEY']='local-fixture'
 cfg['extract_enable_thinking']=False
 cfg['answer_enable_thinking']=json.loads(sys.argv[2])
 extractor,_,answerer,judge=r._make_native_adapters(_core,cfg)
 for adapter in [extractor,answerer,judge]:assert adapter.extract('test','').ok
 assert len(requests)==3
 assert requests[0]['enable_thinking'] is False
 if cfg['answer_enable_thinking'] is None:assert 'enable_thinking' not in requests[1]
 else:assert requests[1].get('enable_thinking') is cfg['answer_enable_thinking'],requests[1]
 assert 'enable_thinking' not in requests[2]
finally:
 server.shutdown();server.server_close();thread.join()
'''
    result=subprocess.run([sys.executable,'-c',program,str(ROOT),value],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
