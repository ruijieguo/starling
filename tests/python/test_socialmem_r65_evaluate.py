"""R6.5：真实冻结输入与原生工厂，防止容量错臂、配对污染和审计遗漏。"""
from collections import Counter, defaultdict
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import threading

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT/'scripts/run_socialmem_r65_evaluate.py'


def driver():
    assert SCRIPT.is_file(), '缺少R6.5同期容量独立评测入口'
    spec = importlib.util.spec_from_file_location('r65_test', SCRIPT)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


@pytest.mark.parametrize('stage', ['prepare', 'qa'])
def test_existing_output_refused_before_input_read(tmp_path, stage):
    m = driver(); out = tmp_path/'exists'; out.mkdir()
    with pytest.raises(ValueError, match='already exists'):
        getattr(m, stage)(tmp_path/'missing', out)


def test_wrong_origin_refused_without_output(tmp_path):
    m = driver(); origin = tmp_path/'origin'; origin.mkdir(); (origin/'seal.json').write_text('{}')
    with pytest.raises(ValueError, match='seal'): m.prepare(origin, tmp_path/'out')
    assert not (tmp_path/'out').exists()


@pytest.fixture(scope='module')
def prepared(tmp_path_factory):
    m = driver(); original = m.load_inputs; cached = {}
    # 旧历史链及bootstrap验证一次；新阶段每次仍核对固定origin的全部文件。
    def inputs(origin):
        assert Path(origin).resolve() == m.DEFAULT_ORIGIN
        m.parent.verify_pinned(origin, m.ORIGIN_SEAL)
        if not cached: cached.update(original(origin))
        return cached
    m.load_inputs = inputs
    def forbidden(*a, **k): pytest.fail('离线阶段构造了provider')
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(m, 'make_adapters', forbidden)
        out = tmp_path_factory.mktemp('r65-prepare')/'prepare'
        result = m.prepare(m.DEFAULT_ORIGIN, out); data = m.check(out)
    assert result['new_external_requests'] == 0
    return m, out, data


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_prepare_is_full_fresh_paired_and_changes_only_capacity(prepared):
    m, out, data = prepared; tasks = data['tasks']; plan = m.read(out/'execution-plan.json')
    assert len(tasks) == len({(t['item_id'], t['arm']) for t in tasks}) == 266
    assert Counter(t['arm'] for t in tasks) == {'tokens512': 133, 'tokens1024': 133}
    assert Counter(t['arm'] for t in tasks[::2]) == {'tokens512': 67, 'tokens1024': 66}
    assert plan['control_fresh'] is True and plan['candidate_fresh'] is True
    assert plan['http_budget'] == 478 and plan['http_budget_per_arm'] == 239
    assert not (out/'control-answers').exists()
    for left, right in zip(tasks[::2], tasks[1::2]):
        assert left['item_id'] == right['item_id'] and left['arm'] != right['arm']
        assert left['prompt'] == right['prompt'] and left['context_sha256'] == right['context_sha256']
        assert left['policy'] == right['policy'] == 'grounded_memory_v1'
    cfgs = [m.arm_config(data['checked'], arm) for arm in ('tokens512', 'tokens1024')]
    assert {k for k in cfgs[0] if cfgs[0][k] != cfgs[1][k]} == {'answer_max_tokens'}
    assert [c['answer_max_tokens'] for c in cfgs] == [512, 1024]
    assert data['checked']['config']['answer_max_tokens'] == 512


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_gold_does_not_enter_answer_prompt(prepared):
    m, _, data = prepared; checked = dict(data['checked']); records = deepcopy(checked['records'])
    for r in records: r['answer'] = 'GOLD_CANARY'; r['source']['evidence_anchors'] = []
    checked['records'] = records
    tasks = m.make_tasks(checked, data['candidate_rows'], data['runner'], data['modules'])
    assert [t['prompt'] for t in tasks] == [t['prompt'] for t in data['tasks']]


@pytest.fixture(scope='module')
def localhost_qa(prepared, tmp_path_factory):
    m, source, data = prepared; calls = []; lock = threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            with lock: calls.append(request)
            body = dict(choices=[dict(message=dict(content='yes' if request['max_tokens'] == 64 else '0', refusal=None), finish_reason='stop')],
                        usage=dict(prompt_tokens=10, completion_tokens=2, total_tokens=12))
            raw = json.dumps(body).encode(); self.send_response(200)
            self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(raw)))
            self.end_headers(); self.wfile.write(raw)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    original_factory = data['runner']._make_native_adapters
    def local_factory(core, config):
        # 仅替换传输目的地，容量参数必须来自被测生产编排。
        config = dict(config)
        for role in ('extract', 'answer', 'embedding'): config[role+'_endpoint'] = f'http://127.0.0.1:{server.server_port}/v1'
        return original_factory(core, config)
    out = tmp_path_factory.mktemp('r65-qa')/'qa'
    try:
        with pytest.MonkeyPatch.context() as patch:
            patch.setenv('DASHSCOPE_API_KEY', 'localhost-fixture')
            patch.setattr(data['runner'], '_make_native_adapters', local_factory)
            result = m.qa(source, out, workers=4)
    finally:
        server.shutdown(); server.server_close(); thread.join()
    return m, out, result, calls


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_native_factory_sends_both_capacities_and_unchanged_judge(localhost_qa):
    m, out, result, calls = localhost_qa
    assert result['state'] == 'complete' and result['terminal_count'] == result['healthy_terminals'] == 266
    assert Counter(r['max_tokens'] for r in calls) == {512: 133, 1024: 133, 64: 212}
    assert all(r['model'] == 'qwen3.8-27b' for r in calls)
    assert all(r.get('enable_thinking') is False for r in calls if r['max_tokens'] != 64)
    assert all('enable_thinking' not in r for r in calls if r['max_tokens'] == 64)
    prompts = defaultdict(list)
    for r in calls:
        if r['max_tokens'] != 64: prompts[json.dumps(r['messages'], sort_keys=True)].append(r['max_tokens'])
    assert len(prompts) == 133 and all(sorted(v) == [512, 1024] for v in prompts.values())
    assert result['observed_http_attempts'] == result['ledger']['committed'] == 478
    assert result['known_tokens'] == result['total_tokens'] == 5736
    assert result['comparison']['denominator'] == 133
    for arm in ('tokens512', 'tokens1024'):
        assert result['arms'][arm]['observed_http_attempts'] == 239
        assert result['arms'][arm]['known_tokens'] == 2868
    assert result['automatic_promotion'] is False
    before = m.inventory(out); assert m.check(out)['summary'] == result; assert m.inventory(out) == before


def reseal(m, out):
    seal = m.read(out/'seal.json'); files = m.inventory(out); files.pop('seal.json')
    seal['files'] = files; m.write(out/'seal.json', seal)


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
@pytest.mark.parametrize('fault', ['answer', 'prompt', 'capacity', 'started', 'ledger', 'summary', 'config'])
def test_resealed_drift_refused(localhost_qa, tmp_path, fault):
    m, source, _, _ = localhost_qa; out = tmp_path/'copy'; shutil.copytree(source, out)
    if fault in ('answer', 'prompt', 'capacity'):
        p = next((out/'answers').glob('*/*/*.json')); row = m.read(p)
        if fault == 'answer': row['correct'] = not row['correct']
        elif fault == 'prompt': row['prompt'] += ' forged'
        else: row['execution_config_sha256'] = 'changed'
        m.write(p, row)
    elif fault == 'started':
        p = next((out/'started').glob('*.json')); row = m.read(p); row['native_invoked'] = False; m.write(p, row)
    elif fault == 'ledger':
        with sqlite3.connect(out/'request-ledger.sqlite') as db: db.execute('UPDATE reservations SET actual=0')
    elif fault == 'config':
        p = out/'execution-plan.json'; row = m.read(p); row['arms']['tokens1024']['answer_max_tokens'] = 512; m.write(p, row)
    else:
        p = out/'summary.json'; row = m.read(p); row['known_tokens'] = 0; m.write(p, row)
    reseal(m, out)
    with pytest.raises(ValueError): m.check(out)


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_missing_usage_stays_unknown_and_failure_keeps_denominator(prepared, tmp_path, monkeypatch):
    m, source, data = prepared
    # 缺usage与截断由本机HTTP发送，保留响应原文并重新走原生审计。
    from http.server import HTTPServer
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']))
            raw = b'{"choices":[{"message":{"content":"0"},"finish_reason":"length"}]}'
            self.send_response(200); self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
    server = HTTPServer(('127.0.0.1', 0), Handler); thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    monkeypatch.setenv('DASHSCOPE_API_KEY', 'localhost-fixture')
    original = data['runner']._make_native_adapters
    def local_factory(core, config):
        config = dict(config)
        for role in ('extract', 'answer', 'embedding'): config[role+'_endpoint'] = f'http://127.0.0.1:{server.server_port}/v1'
        return original(core, config)
    monkeypatch.setattr(data['runner'], '_make_native_adapters', local_factory)
    out = tmp_path/'no-usage'
    try: result = m.qa(source, out, workers=4)
    finally: server.shutdown(); server.server_close(); thread.join()
    assert result['state'] == 'complete' and result['terminal_count'] == 266
    assert result['healthy_terminals'] == 0 and result['comparison']['denominator'] == 133
    assert result['comparison']['control_correct'] == result['comparison']['candidate_correct'] == 0
    assert result['missing_token_usage'] == 266 and result['total_tokens'] is None
    assert result['observed_http_attempts'] == 266 and result['ledger']['committed'] == 266
    assert all(a['answer_truncated'] == 133 for a in result['arms'].values())


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_interruption_sealed_without_partial_score_or_resume(prepared, tmp_path, monkeypatch):
    m, source, _ = prepared
    monkeypatch.setattr(m, 'make_adapters', lambda *_: None)
    original = m.e.execute_qa; count = 0
    def interrupted(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 2: raise RuntimeError('fixture interrupt')
        return original(*args, **kwargs)
    monkeypatch.setattr(m.e, 'execute_qa', interrupted)
    out = tmp_path/'partial'; result = m.qa(source, out, workers=1)
    assert result['state'] == 'incomplete' and 'comparison' not in result
    assert (out/'failure.json').exists() and m.read(out/'seal.json')['state'] == 'incomplete'
    assert m.check(out)['summary'] == result
    with pytest.raises(ValueError, match='already exists'): m.qa(source, out)
