"""R6.4固定控制与k20候选；真实冻结输入、原生localhost请求及篡改反例。"""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/run_socialmem_r64_evaluate.py'


def driver():
    assert SCRIPT.is_file(), '缺少R6.4候选独立评测入口'
    spec = importlib.util.spec_from_file_location('r64_test', SCRIPT)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


@pytest.mark.parametrize('stage', ['prepare', 'qa'])
def test_existing_output_is_refused_before_input_read(tmp_path, stage):
    m = driver(); out = tmp_path / 'exists'; out.mkdir()
    with pytest.raises(ValueError, match='already exists'):
        if stage == 'prepare': m.prepare(tmp_path/'missing', tmp_path/'missing2', out)
        else: m.qa(tmp_path/'missing', out)


def test_wrong_pinned_origin_is_rejected_without_creating_output(tmp_path):
    m = driver(); origin = tmp_path/'origin'; origin.mkdir(); (origin/'seal.json').write_text('{}')
    with pytest.raises(ValueError, match='seal'):
        m.prepare(origin, m.DEFAULT_CONTEXTS, tmp_path/'out')
    assert not (tmp_path/'out').exists()


@pytest.fixture(scope='module')
def prepared(tmp_path_factory):
    m = driver(); out = tmp_path_factory.mktemp('r64')/'prepare'
    def forbidden(*a, **k): pytest.fail('离线准备/检查构造了provider')
    original = m.e.make_adapters; m.e.make_adapters = forbidden
    # 旧轮完整原生审计与100000次bootstrap只运行一次；后续新入口反例
    # 每次重验固定origin清单，复用已验证的只读输入，避免重复测试旧统计器。
    original_inputs = m.load_inputs; cached = {}
    def inputs(control, contexts):
        assert Path(control).resolve() == m.DEFAULT_CONTROL
        assert Path(contexts).resolve() == m.DEFAULT_CONTEXTS
        m.verify_pinned(control, m.CONTROL_SEAL); m.verify_pinned(contexts, m.CONTEXT_SEAL)
        if not cached: cached.update(original_inputs(control, contexts))
        return cached
    m.load_inputs = inputs
    try:
        result = m.prepare(m.DEFAULT_CONTROL, m.DEFAULT_CONTEXTS, out)
        data = m.check(out)
    finally: m.e.make_adapters = original
    assert result['new_external_requests'] == 0
    return m, out, data


def test_prepare_binds_only_candidate_tasks_and_original_control(prepared):
    m, out, data = prepared; tasks = data['tasks']; plan = m.read(out/'execution-plan.json')
    assert len(tasks) == 266 and len({(t['item_id'], t['policy']) for t in tasks}) == 266
    assert {t['arm'] for t in tasks} == {'source20'}
    assert plan['http_budget'] == 478 and plan['control_fresh'] is False
    assert len(data['controls']) == 266
    for policy, correct in [('legacy', 37), ('grounded_memory_v1', 41)]:
        assert sum(r['correct'] for r in data['controls'] if r['policy'] == policy) == correct
    for row in data['controls']:
        rel = Path(row['policy'])/'source10'/(m.e.text_sha(row['item_id'])+'.json')
        assert (out/'control-answers'/rel).read_bytes() == (m.DEFAULT_CONTROL/'answers'/rel).read_bytes()
    assert all(len(t['recall']['block'].encode()) <= 8000 for t in tasks)


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'k10', 'holders', 'database', 'text', 'embedding'])
def test_candidate_context_drift_is_rejected(prepared, fault):
    m, _, data = prepared; rows = deepcopy(data['candidate_rows'])
    if fault == 'missing': rows.pop()
    elif fault == 'duplicate': rows[-1] = rows[0]
    elif fault == 'k10': rows[0]['k'] = 10
    elif fault == 'holders': rows[0]['holders'] = ['not-a-permitted-person']
    elif fault == 'database': rows[0]['database_sha256'] = 'changed'
    elif fault == 'text': rows[0]['recall']['block'] += ' forged'
    else: rows[0]['embedding_requests'] = 1
    with pytest.raises(ValueError): m.validate_candidate_rows(data['checked'], rows, data['modules'])


def test_gold_changes_do_not_enter_candidate_answer_prompt(prepared):
    m, _, data = prepared; checked = dict(data['checked']); records = deepcopy(checked['records'])
    for record in records:
        record['answer'] = 'CANARY_GOLD_ONLY'; record['source']['evidence_anchors'] = []
    checked['records'] = records
    tasks = m.make_tasks(checked, data['candidate_rows'], data['runner'], data['modules'])
    assert [t['prompt'] for t in tasks] == [t['prompt'] for t in data['tasks']]
    assert all('CANARY_GOLD_ONLY' not in t['prompt'] for t in tasks)


@pytest.fixture(scope='module')
def localhost_qa(prepared, tmp_path_factory):
    m, prepared_path, data = prepared; core = data['modules'][0]; calls = []; lock = threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            with lock: calls.append(request)
            content = 'yes' if request['max_tokens'] == 64 else '0'
            body = dict(choices=[dict(message=dict(content=content, refusal=None), finish_reason='stop')],
                        usage=dict(prompt_tokens=10, completion_tokens=2, total_tokens=12))
            raw = json.dumps(body).encode(); self.send_response(200)
            self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(raw)))
            self.end_headers(); self.wfile.write(raw)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    patch = pytest.MonkeyPatch(); patch.setenv('OPENAI_API_KEY', 'offline-fixture')
    def adapters(*_):
        result = []
        for tokens in (512, 64):
            cfg = core.OpenAIAdapterConfig.from_env(); cfg.base_url = f'http://127.0.0.1:{server.server_port}/v1'
            cfg.model = 'qwen3.8-27b'; cfg.timeout_ms = 120000; cfg.max_retries = 0; cfg.max_tokens = tokens
            if tokens == 512: cfg.enable_thinking = False
            result.append(core.OpenAIAdapter(cfg))
        return None, None, *result
    patch.setattr(m.e, 'make_adapters', adapters)
    out = tmp_path_factory.mktemp('r64-qa')/'qa'
    try: result = m.qa(prepared_path, out, workers=4)
    finally:
        patch.undo(); server.shutdown(); server.server_close(); thread.join()
    return m, out, result, calls


def test_native_candidate_stage_keeps_inherited_cost_out_of_new_ledger(localhost_qa):
    m, out, result, calls = localhost_qa
    assert result['state'] == 'complete' and result['terminal_count'] == result['healthy_terminals'] == 266
    assert len(calls) == result['observed_http_attempts'] == result['ledger']['committed'] == 478
    assert result['known_tokens'] == result['total_tokens'] == 5736
    assert sum(r['max_tokens'] == 512 for r in calls) == 266
    assert sum(r['max_tokens'] == 64 for r in calls) == 212
    assert all(r['model'] == 'qwen3.8-27b' for r in calls)
    assert all(r.get('enable_thinking') is False for r in calls if r['max_tokens'] == 512)
    assert all('enable_thinking' not in r for r in calls if r['max_tokens'] == 64)
    assert result['policies']['grounded_memory_v1']['control_correct'] == 41
    assert result['policies']['legacy']['control_correct'] == 37
    assert result['automatic_promotion'] is False
    before = m.inventory(out); assert m.check(out)['summary'] == result; assert m.inventory(out) == before


@pytest.mark.parametrize('fault', ['answer', 'prompt', 'context', 'started', 'ledger', 'summary'])
def test_resealed_candidate_tampering_fails_independent_check(localhost_qa, tmp_path, fault):
    m, source, _, _ = localhost_qa; out = tmp_path/'copy'; shutil.copytree(source, out)
    if fault in ('answer', 'prompt', 'context'):
        p = next((out/'answers').glob('*/*/*.json')); row = m.read(p)
        if fault == 'answer': row['correct'] = not row['correct']
        elif fault == 'prompt': row['prompt'] += ' forged'
        else: row['context_sha256'] = 'changed'
        m.write(p, row)
    elif fault == 'started':
        p = next((out/'started').glob('*.json')); row = m.read(p); row['native_invoked'] = False; m.write(p, row)
    elif fault == 'ledger':
        with sqlite3.connect(out/'request-ledger.sqlite') as db: db.execute('UPDATE reservations SET actual=0')
    else:
        p = out/'summary.json'; row = m.read(p); row['known_tokens'] = 0; m.write(p, row)
    seal = m.read(out/'seal.json'); files = m.inventory(out); files.pop('seal.json'); seal['files'] = files; m.write(out/'seal.json', seal)
    with pytest.raises(ValueError): m.check(out)


def test_interrupted_stage_is_sealed_with_partial_cost_and_never_resumed(prepared, tmp_path, monkeypatch):
    m, source, _ = prepared
    monkeypatch.setattr(m.e, 'make_adapters', lambda *_: None)
    original = m.e.execute_qa; calls = 0
    def interrupted(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2: raise RuntimeError('fixture interrupt')
        return original(*args, **kwargs)
    monkeypatch.setattr(m.e, 'execute_qa', interrupted)
    out = tmp_path/'partial'; result = m.qa(source, out, workers=1)
    assert result['state'] == 'incomplete' and 'policies' not in result
    assert (out/'failure.json').is_file() and m.read(out/'seal.json')['state'] == 'incomplete'
    assert m.check(out)['summary'] == result
    with pytest.raises(ValueError, match='already exists'): m.qa(source, out)
