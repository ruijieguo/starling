"""独立 schema 对照的本地编排与停止条件。"""
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))


def test_schema_preview_comparison_accepts_only_array_constraints():
    import run_socialmem_schema as runner
    old = {'properties': {'markers': {'type': 'array', 'items': {'type': 'string'}}}}
    new = {'properties': {'markers': {'type': 'array', 'items': {'type': 'string'},
                                      'minItems': 1, 'uniqueItems': True}}}
    # 本地核对不实现 JSON Schema 语义，只检查显式允许的实验差异。
    assert runner.schema_delta(old, new) == [
        ('/properties/markers/minItems', None, 1),
        ('/properties/markers/uniqueItems', None, True)]


def test_sample_worker_requires_reservation_before_real_adapter_call(tmp_path):
    from starling import _core
    import eval_socialmem_r1b as worker
    cfg = _core.OpenAIAdapterConfig()
    cfg.base_url = 'http://127.0.0.1:1/v1'
    cfg.model = 'fixture'
    cfg.max_retries = 0
    cfg.timeout_ms = 1
    llm = _core.OpenAIAdapter(cfg)
    with pytest.raises(ValueError, match='guard'):
        worker.worker_sample(_core, llm,
            {'max_retries':0,'output_mode':'json_schema_strict'},
            {'id':'x','holder':'Mina','track':'fixture','passage':'Mina: hi'},
            artifact_dir=tmp_path)
    assert not list(tmp_path.iterdir())


def test_real_sample_rejects_noop_callback_before_http(tmp_path):
    from starling import _core
    import eval_socialmem_r1b as worker
    cfg = _core.OpenAIAdapterConfig()
    cfg.base_url = 'http://127.0.0.1:1/v1'
    cfg.model, cfg.max_retries, cfg.timeout_ms = 'fixture', 0, 1
    with pytest.raises(ValueError, match='guard'):
        worker.worker_sample(_core, _core.OpenAIAdapter(cfg),
            {'max_retries': 0, 'output_mode': 'json_schema_strict'},
            {'id': 'x', 'holder': 'Mina', 'track': 'fixture', 'passage': 'Mina: hi'},
            artifact_dir=tmp_path, before_request=lambda _kind: None)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('drift', ['core', 'schedule', 'limits', 'source'])
def test_resigned_plan_cannot_change_authorized_experiment(tmp_path, monkeypatch, drift):
    import run_socialmem_schema as runner
    import socialmem_run_guard as guard
    from eval_socialmem_r1b import schedule_samples
    from starling import _core
    # 用固定夹具替换本轮常量，不依赖某次 build 归档；不执行模型。
    cases = [{'id': name, 'track': 'fixture', 'holder': 'Mina', 'passage': 'Mina: hi'}
             for name in runner.SOURCE_IDS]
    monkeypatch.setattr(runner, 'EXPECTED_SOURCES_SHA256', runner.canonical_sha256(cases), raising=False)
    frozen = guard.frozen_identity(_core, runner.CONFIG, cases, runner.code_paths())
    arms = {arm: dict(frozen) for arm in ('C0', 'C1')}
    old_core = tmp_path / 'old-core-fixture'
    old_core.write_bytes(b'frozen old-core identity fixture')
    monkeypatch.setattr(runner, 'EXPECTED_CORE_SHA256',
        {'C0': runner.file_sha256(old_core), 'C1': runner.file_sha256(_core.__file__)}, raising=False)
    arms['C0'].update(core_path=str(old_core), core_sha256=runner.file_sha256(old_core))
    plan = {'schema_version': 1, 'config': runner.CONFIG, 'cases': cases, 'arms': arms,
            'schedule': schedule_samples(cases, arms=('C0', 'C1')),
            'limits': {'probe': 16, 'extract': 16, 'admission': 16, 'total': 48},
            'file_sha256': {}}
    if drift == 'core':
        arms['C0'] = dict(frozen)
    elif drift == 'schedule':
        plan['schedule'] = [plan['schedule'][0]] * 16
    elif drift == 'limits':
        plan['limits']['total'] = 49
    else:
        cases[0]['passage'] += ' Changed source.'
        for arm in arms.values():
            arm['sources'] = {c['id']: runner.canonical_sha256(c) for c in cases}
    plan['plan_sha256'] = runner.canonical_sha256(plan)
    path = tmp_path / 'plan.json'
    runner.write_json_new(path, plan)
    with pytest.raises(ValueError, match='authorized|schedule|limits|source'):
        runner.verify_plan(path)


def test_source_allowlist_drops_answers_and_preserves_metadata():
    import run_socialmem_schema as runner
    case = {'id':'x','track':'fixture','holder':'Mina','passage':'Mina: hi',
            'answer':'secret answer','question':'must not enter prompt','origin':'T-20'}
    frozen = runner.model_case(case)
    assert frozen == {'id':'x','track':'fixture','holder':'Mina','passage':'Mina: hi'}


def test_request_archive_identifies_wire_vs_parse_failure():
    from starling import _core
    import run_socialmem_schema as runner
    assert runner.classify_extraction({'ok':False,'wire_error':None,'parse_result':None}) == 'transport_failure'
    assert runner.classify_extraction({'ok':True,'wire_error':'schema_failure:minItems',
                                     'parse_result':{'errors':[{'kind':'schema_failure'}]}}) == 'wire_failure'
    assert runner.classify_extraction({'ok':True,'wire_error':'','parse_result':{'errors':[{'kind':'scope_failure'}]}}) == 'parse_failure'
    assert runner.classify_extraction({'ok':True,'wire_error':'','parse_result':{'errors':[]}}) == 'parsed'


def test_validate_frozen_rejects_false_ready_after_native_report_check(monkeypatch):
    import run_socialmem_schema as runner
    import socialmem_run_guard as guard
    monkeypatch.setattr(guard, 'verify_identity', lambda *a, **k: True)
    monkeypatch.setattr(guard, 'verify_capability', lambda *a, **k: {'ready':False, 'reasons':['expired']})
    with pytest.raises(ValueError, match='capability gate failed'):
        runner.validate_frozen(None, {}, {}, report_path='fixture', report_sha256='hash')


def test_frozen_code_inventory_includes_native_semantic_and_http_boundaries():
    import run_socialmem_schema as runner
    paths = {p.relative_to(runner.ROOT).as_posix() for p in runner.code_paths()}
    assert {'src/extractor/structured_output.cpp', 'src/extractor/claim_contract.cpp',
            'src/extractor/claim_scope.cpp', 'src/extractor/openai_adapter.cpp',
            'src/net/http_post_json.cpp', 'bindings/python/bind_06_extractor.cpp'} <= paths


@pytest.mark.parametrize('failed_arm,expected_requests', [(None, 48), ('C0', 8), ('C1', 16)])
def test_native_http_run_archives_budget_and_stops_failed_gate(tmp_path, monkeypatch,
                                                              failed_arm, expected_requests):
    """同一新核心的本地调度夹具；实际双模块差异由隔离预览验证。"""
    import json
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    from starling import _core
    import run_socialmem_schema as runner
    from socialmem_run_guard import frozen_identity
    from eval_socialmem_r1b import schedule_samples

    row = {'holder': 'Mina', 'holder_perspective': 'FIRST_PERSON', 'subject': 'Mina',
           'subject_kind': 'cognizer', 'predicate': 'feels', 'object': 'worried about launch',
           'modality': 'BELIEVES', 'polarity': 'POS', 'nesting_depth': 0, 'confidence': None,
           'evidence': {'clause_id': 'c0', 'actor': 'Mina', 'attributed_to': None,
                        'assertion_scope': 'ASSERTED', 'scope_markers': ['ASSERTED'],
                        'time_text': '', 'event_time': None, 'topic': 'launch'}}
    cases = [{'id': name, 'track': 'fixture', 'holder': 'Mina',
              'passage': 'Mina: I am worried about launch.'} for name in runner.SOURCE_IDS]
    sample_prompt = _core.claim_extraction_prompt(cases[0]['passage'], 'Mina')
    captured = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            captured.append(body)
            prompt = body['messages'][0]['content']
            name = body.get('response_format', {}).get('json_schema', {}).get('name', '')
            admission = name == 'claim_admission_v1' or 'candidate list is empty' in prompt
            if prompt == sample_prompt:
                raw = {'schema_version': 2, 'statements': [row]}
            elif admission:
                decisions = [] if len(captured) <= 16 else [
                    {'index': 0, 'retain': True, 'reason': 'supported'}]
                raw = {'schema_version': 1, 'decisions': decisions}
            else:
                raw = {'schema_version': 2, 'statements': []}
            if len(captured) == {'C0': 5, 'C1': 13}.get(failed_arm):
                raw = {'bad': 'fixture protocol failure'}
            payload = json.dumps({'choices': [{'finish_reason': 'stop',
                'message': {'content': json.dumps(raw)}}]}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    try:
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    except PermissionError:
        pytest.skip('loopback listener not permitted')
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv('DASHSCOPE_API_KEY', 'local-fixture-only')
    config = {**runner.CONFIG, 'endpoint': f'http://127.0.0.1:{server.server_port}/v1'}
    monkeypatch.setattr(runner, 'CONFIG', config)
    monkeypatch.setattr(runner, 'EXPECTED_CORE_SHA256',
                        {arm: runner.file_sha256(_core.__file__) for arm in ('C0', 'C1')}, raising=False)
    monkeypatch.setattr(runner, 'EXPECTED_SOURCES_SHA256', runner.canonical_sha256(cases), raising=False)
    monkeypatch.setattr(runner, 'load_stage', lambda _stage: _core)
    plan = {'schema_version': 1, 'config': config, 'cases': cases,
            'limits': {'probe': 16, 'extract': 16, 'admission': 16, 'total': 48},
            'schedule': schedule_samples(cases, arms=('C0', 'C1')), 'file_sha256': {},
            'arms': {arm: {**frozen_identity(_core, config, cases, runner.code_paths()),
                           'stage': 'fixture'} for arm in ('C0', 'C1')}}
    plan['plan_sha256'] = runner.canonical_sha256(plan)
    plan_path = tmp_path / 'plan.json'
    runner.write_json_new(plan_path, plan)

    def invoke(action, path, arm, out, *extra):
        options = dict(zip(extra[::2], extra[1::2]))
        return runner.worker(action, path, arm, out, run_dir=options['--run-dir'],
                             sequence=options.get('--sequence'))

    monkeypatch.setattr(runner, 'invoke', invoke)
    try:
        summary = runner.run(plan_path, tmp_path / 'real')
        assert len(captured) == expected_requests
        assert summary['budget']['reserved_total'] == expected_requests
        assert summary['error'] is None
        if failed_arm:
            assert summary['status'] == 'stopped_capability_gate'
            assert summary['samples_completed'] == 0
        else:
            assert summary['samples_completed'] == 16
            assert summary['status'] == 'complete_with_observations'
            for path in (tmp_path / 'real').glob('sample-*/result.json'):
                result = runner.read(path)
                assert result['extraction_stage'] == 'parsed'
                assert result['status'] == 'admitted' and len(result['retained']) == 1
                assert (path.parent / 'admission_preview.json').is_file()
        with pytest.raises(ValueError, match='already exists'):
            runner.run(plan_path, tmp_path / 'real')
        assert len(captured) == expected_requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
