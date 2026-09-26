"""通过真实父C++核心的本机HTTP请求验证角色容量隔离。"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_frozen_native_answer_capacity_does_not_change_judge_or_extraction():
    program = r'''
import importlib.util,json,os,sys,threading
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
root=Path(sys.argv[1]);parent=root/'build/socialmem_20260917_grounded_answer_v2'
sys.path.insert(0,str(root/'scripts'))
import run_socialmem_answer_capacity as capacity
spec=importlib.util.spec_from_file_location('runner',parent/'frozen/scripts/run_socialmem_baseline.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
old=json.loads((parent/'config.json').read_text());cfg={**old,'answer_max_tokens':1024}
capacity.validate_config(old,cfg)
_core,*_=r._frozen_imports(parent,cfg,json.loads((parent/'identity.json').read_text()))
assert capacity.sha(Path(_core.__file__))==capacity.PARENT_CORE
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
 for role in ['extract','answer','embedding']:cfg[role+'_endpoint']=f'http://127.0.0.1:{server.server_port}/v1'
 os.environ['DASHSCOPE_API_KEY']='local-fixture'
 extractor,_,answerer,judge=r._make_native_adapters(_core,cfg)
 for adapter in [extractor,answerer,judge]:assert adapter.extract('fixture','').ok
 assert len(requests)==3
 assert [p['max_tokens'] for p in requests]==[4096,1024,64]
 assert requests[0]['enable_thinking'] is False
 assert requests[1]['enable_thinking'] is False
 assert 'enable_thinking' not in requests[2]
 assert all(p['model']=='qwen3.8-27b' for p in requests)
finally:
 server.shutdown();server.server_close();thread.join()
'''
    p = subprocess.run([sys.executable, '-c', program, str(ROOT)], capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stdout + p.stderr
