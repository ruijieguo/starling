"""真实C++来源选择和localhost HTTP边界；Python不实现选择规则。"""
import json
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import pytest
from starling import _core as core,runtime

@pytest.fixture
def pool(tmp_path):
    rt=runtime._build_local_store_sqlite_runtime(tmp_path/'memory.db');rt.start()
    emb=core.StubEmbeddingAdapter(8);idx=core.SqliteBlobVectorIndex()
    semantic=core.SemanticRetriever(rt.adapter,emb,idx);observer=core.ObserverRetriever(rt.adapter,semantic)
    turns=[dict(speaker='Ada',text='I now help with the timetable.',turn_id='s1_t1',session_id='s1',
        turn_index=1,observed_at='2025-01-01T10:00:00Z')]
    core.retain_source_turns(rt.adapter,'default',['Ada'],json.dumps(turns),'2026-01-01T00:00:00Z')
    q=core.ObserverQuery();q.tenant_id='default';q.allowed_holders=['Ada'];q.question='How does Ada help?'
    q.as_of_iso8601='2026-06-01T00:00:00Z';q.mode='sources'
    yield q.question,core.collect_selection_pool(observer,q)

@pytest.fixture
def http():
    state=dict(requests=[],content='{"source_ids":[1]}',finish='stop',status=200,usage=True,refusal=False)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            state['requests'].append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            body=dict(choices=[dict(message=dict(content=state['content'],refusal=state['refusal']),finish_reason=state['finish'])])
            if state['status']!=200:body={'error':{'message':'response_format json_object not supported'}}
            if state['usage']:body['usage']=dict(prompt_tokens=20,completion_tokens=5,total_tokens=25)
            raw=json.dumps(body).encode();self.send_response(state['status']);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    cfg=core.OpenAIAdapterConfig();cfg.base_url=f'http://127.0.0.1:{server.server_port}/v1'
    cfg.model='qwen3.8-27b';cfg.max_tokens=512;cfg.max_retries=0;cfg.enable_thinking=False
    cfg.json_object_output=False  # 显式合同必须独立于旧配置开关生效。
    try:yield core.OpenAIAdapter(cfg),state
    finally:server.shutdown();server.server_close();thread.join()

def select(pool,adapter):
    assert hasattr(core,'select_sources_structured'),'missing explicit native structured selector'
    return core.select_sources_structured(*pool,adapter)

def test_wire_format_and_native_contract_are_explicit(pool,http):
    adapter,state=http;r=select(pool,adapter)
    assert r.ok and json.loads(r.recall_json)['source_count']==1
    assert len(state['requests'])==1
    request=state['requests'][0]
    assert request['response_format']=={'type':'json_object'}
    assert request['model']=='qwen3.8-27b' and request['max_tokens']==512 and request['enable_thinking'] is False
    assert r.response.output_mode==core.OutputMode.JsonObject
    assert r.response.output_contract==core.OutputContractKind.SourceSelectionV1
    assert r.response.raw_completion==state['content']

@pytest.mark.parametrize('fault',['unsupported','fenced','truncated','refusal','unknown_id'])
def test_provider_failure_preserves_raw_without_retry_or_fallback(pool,http,fault):
    adapter,state=http
    if fault=='unsupported':state['status']=400
    if fault=='fenced':state['content']='```json\n{"source_ids":[1]}\n```'
    if fault=='truncated':state['finish']='length'
    if fault=='refusal':state['refusal']='refused'
    if fault=='unknown_id':state['content']='{"source_ids":[99]}'
    r=select(pool,adapter)
    assert not r.ok and r.invoked and not r.recall_json
    assert len(state['requests'])==1 and r.response.raw_http_response
    if fault not in ('unsupported',):assert r.response.raw_completion==state['content']

def test_legacy_selection_keeps_free_form_wire_behavior(pool,http):
    adapter,state=http;r=core.select_sources(*pool,adapter)
    assert r.ok
    assert len(state['requests'])==1 and 'response_format' not in state['requests'][0]

def test_explicit_source_contract_probe_replays_its_native_evidence(http):
    assert hasattr(core.OutputContractKind,'SourceSelectionV1'),'missing source selection contract'
    adapter,state=http;state['content']='{"source_ids":[]}'
    request=core.StructuredOutputRequest(core.OutputContractKind.SourceSelectionV1,core.OutputMode.JsonObject)
    evidence=adapter.probe_structured_output(request)
    assert evidence.state==core.CapabilityState.ObservedConformant
    assert len(state['requests'])==2
    assert all('source_ids' in r['messages'][0]['content'] for r in state['requests'])
    assert core.validate_capability_evidence_json(core.capability_evidence_json(evidence))==''
