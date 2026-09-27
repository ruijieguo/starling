"""Capacity recovery preserves sealed inputs and permits only one extraction request."""
from copy import deepcopy
from contextlib import closing
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/run_socialmem_r55_capacity_probe.py'


def driver():
    assert SCRIPT.is_file(), 'independent R55 capacity probe is required'
    spec = importlib.util.spec_from_file_location('r55_probe_tests', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def text_sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def healthy_response():
    raw = ' {"schema_version":2,"statements":[{"fixture":"native parser owns this"}]}\n'
    body = json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': raw}}],
                       'usage': {'prompt_tokens': 22123, 'completion_tokens': 9000, 'total_tokens': 31123}})
    return dict(ok=True, error='', refusal=False, finish_reason='stop', attempt_count=1,
                raw_completion=raw, raw_response=raw, raw_http_response=body,
                output_contract='claim_extraction_v2', output_mode='json_object', schema_sha256='schema',
                prompt_tokens=22123, completion_tokens=9000, total_tokens=31123, latency_ms=125000,
                http_attempts=[dict(attempt=1, http_status=200, curl_code=0,
                    execution_certainty='response_received', response_body=body,
                    response_bytes=len(body.encode()), streamed_bytes=0, elapsed_ms=125000,
                    retry_policy='connect_only')])


@pytest.fixture
def case(tmp_path, monkeypatch):
    m = driver()
    prepare, failed = tmp_path / 'prepare', tmp_path / 'failed'
    runtime = prepare / 'frozen/python/starling'; runtime.mkdir(parents=True)
    core_path = runtime / '_core.fixture.so'; core_path.write_bytes(b'frozen native core fixture')
    (prepare / 'frozen/scripts').mkdir()
    (prepare / 'frozen/scripts/run_socialmem_baseline.py').write_text('# frozen runtime fixture\n')
    m.r55.write(prepare / 'seal.json', {'fixture': 'prepare'})
    scope = failed / 'runs' / m.SCOPE; scope.mkdir(parents=True)
    payload, prompt = 'Kwame: I am sad about leaving the team.\n', 'exact original prompt\n'
    with closing(sqlite3.connect(scope / 'frozen.db')) as conn:
        conn.executescript('CREATE TABLE source_documents (tenant_id TEXT,holder_id TEXT,engram_ref TEXT);'
                           'CREATE TABLE engrams (id TEXT,tenant_id TEXT,payload_inline BLOB);')
        conn.execute('INSERT INTO source_documents VALUES (?,?,?)', ('default', 'Kwame', 'source-1'))
        conn.execute('INSERT INTO engrams VALUES (?,?,?)', ('source-1', 'default', payload.encode()))
        conn.commit()
    original = healthy_response()
    original.update(ok=False, error='completion_truncated', finish_reason='length', completion_tokens=8192,
                    prompt=prompt, prompt_input_hash=text_sha(prompt), schema_sha256='schema')
    channel = dict(holder='Kwame', source_payload_hash=text_sha(payload), prompt=prompt,
                   prompt_input_hash=text_sha(prompt), attempts=[{'attempt': 1, 'extraction': original}])
    metadata = dict(group=m.SCOPE, scope_state='partial', extraction=[dict(holder='Kwame', engram_ref='source-1',
                    extraction_failed=True, receipt={'channels': {'belief': channel}})])
    m.r55.write(scope / 'scope.json', metadata)
    prepare_sha = m.r55.sha(prepare / 'seal.json')
    m.r55.write(failed / 'stage.json', dict(stage='build', input=str(prepare), input_stage='prepare',
                                        input_seal_sha256=prepare_sha))
    (failed / 'input-seal.json').write_bytes((prepare / 'seal.json').read_bytes())
    m.r55.seal_output(failed, 'build', 'incomplete')
    monkeypatch.setattr(m, 'FAILED_SEAL_SHA256', m.r55.sha(failed / 'seal.json'))
    monkeypatch.setattr(m, 'PREPARE_SEAL_SHA256', prepare_sha)
    monkeypatch.setattr(m, 'CORE_SHA256', m.r55.sha(core_path))
    config = dict(core_sha256=m.CORE_SHA256, extract_model='qwen3.8-27b',
                  extract_endpoint='https://example.invalid/compatible-mode/v1', extract_enable_thinking=False,
                  extract_max_tokens=8192, timeout_ms=120000, max_retries=0)
    m.r55.write(failed / 'config.json', config)
    (failed / 'seal.json').unlink(); m.r55.seal_output(failed, 'build', 'incomplete')
    monkeypatch.setattr(m, 'FAILED_SEAL_SHA256', m.r55.sha(failed / 'seal.json'))
    identity = dict(frozen_files=m.r55.inventory(prepare / 'frozen'))
    checked = dict(config=config, identity=identity, seal_sha256=prepare_sha)
    monkeypatch.setattr(m.r55, 'check', lambda path, stage=None: checked)
    c = SimpleNamespace(m=m, prepare=prepare, failed=failed, scope=scope, payload=payload, prompt=prompt,
                        out=tmp_path / 'probe', calls=[], constructions=[], parses=[], error=None,
                        response=healthy_response(), parsed=dict(errors=[], statements=[{'native': 'qualified'}],
                        semantic_rejections=[{'kind': 'scope_failure'}], row_diagnostics=[]))
    class Provider:
        def extract_with_contract(self, received_prompt, prompt_hash, request):
            c.calls.append((received_prompt, prompt_hash, request))
            if c.error:
                raise c.error
            return SimpleNamespace(to_json=lambda: json.dumps(c.response))
    def construct(config):
        c.constructions.append(config)
        return Provider()
    def parse(raw, source, holder, allow_code_fence):
        c.parses.append((raw, source, holder, allow_code_fence))
        return json.dumps(c.parsed)
    core = SimpleNamespace(__file__=str(core_path), claim_extraction_prompt=lambda source, holder: prompt,
        claim_parse_response=parse, StructuredOutputRequest=lambda contract, mode: (contract, mode),
        OutputContractKind=SimpleNamespace(ClaimExtractionV2='native-extraction'),
        OutputMode=SimpleNamespace(JsonObject='native-json-object'),
        OpenAIAdapterConfig=SimpleNamespace(from_env=lambda: SimpleNamespace()), OpenAIAdapter=construct,
        structured_output_schema_sha256=lambda contract: 'schema')
    c.core = core
    monkeypatch.setattr(m.r55, 'frozen_modules', lambda *_: (m.r55.baseline, (core,) + (None,) * 5))
    monkeypatch.setenv('DASHSCOPE_API_KEY', 'offline-fixture-not-a-secret')
    return c


def reseal_failure(c):
    (c.failed / 'seal.json').unlink()
    c.m.r55.seal_output(c.failed, 'build', 'incomplete')
    c.m.FAILED_SEAL_SHA256 = c.m.r55.sha(c.failed / 'seal.json')


def test_validate_only_never_constructs_provider(case):
    result = case.m.validate_inputs(case.prepare, case.failed)
    assert result['binding']['prompt_sha256'] == text_sha('exact original prompt\n')
    assert result['binding']['payload_sha256'] == text_sha('Kwame: I am sad about leaving the team.\n')
    assert case.calls == case.constructions == []
    assert not case.out.exists()


@pytest.mark.parametrize('change', ['seal', 'file_hash', 'extra_file', 'holder', 'payload', 'prompt',
                                   'prompt_hash', 'core', 'failure', 'prepare', 'source_ref'])
def test_binding_drift_is_rejected_before_provider_construction(case, change):
    c = case; m = c.m
    if change == 'seal': m.FAILED_SEAL_SHA256 = '0' * 64
    elif change == 'prepare': m.PREPARE_SEAL_SHA256 = '0' * 64
    elif change == 'file_hash': (c.scope / 'scope.json').write_text('{}')
    elif change == 'extra_file': (c.failed / 'unexpected').write_text('x')
    elif change == 'core': Path(c.core.__file__).write_bytes(b'changed core')
    elif change == 'payload':
        with closing(sqlite3.connect(c.scope / 'frozen.db')) as conn:
            conn.execute('UPDATE engrams SET payload_inline=?', (b'wrong payload',)); conn.commit()
        reseal_failure(c)
    else:
        meta = m.r55.read(c.scope / 'scope.json'); row = meta['extraction'][0]
        channel = row['receipt']['channels']['belief']; response = channel['attempts'][0]['extraction']
        if change == 'holder': row['holder'] = 'Someone Else'
        elif change == 'prompt': response['prompt'] += ' changed'
        elif change == 'prompt_hash': response['prompt_input_hash'] = '0' * 64
        elif change == 'failure': response.update(ok=True, error='', finish_reason='stop')
        elif change == 'source_ref': row['engram_ref'] = 'wrong-source'
        m.r55.write(c.scope / 'scope.json', meta); reseal_failure(c)
    with pytest.raises(ValueError):
        m.run(c.prepare, c.failed, c.out)
    assert c.calls == c.constructions == []


def test_existing_output_is_refused_before_inputs_or_provider(case):
    case.out.mkdir()
    with pytest.raises(ValueError, match='already exists'):
        case.m.run(Path('/absent'), Path('/absent'), case.out)
    assert case.calls == case.constructions == []


def test_single_native_request_uses_larger_capacity_and_preserves_raw_receipts(case):
    c = case; result = c.m.run(c.prepare, c.failed, c.out)
    assert result['status'] == 'capacity_probe_passed'
    assert result['qualified_candidate_count'] == 1 and result['semantic_rejection_count'] == 1
    assert result['ledger'] == dict(budget=1, committed=1, reserved=0, charged_upper=0, remaining=0)
    config, = c.constructions
    assert (config.model, config.max_tokens, config.timeout_ms, config.max_retries, config.enable_thinking) == (
        'qwen3.8-27b', 16384, 240000, 0, False)
    assert c.calls == [(c.prompt, text_sha(c.prompt), ('native-extraction', 'native-json-object'))]
    assert c.parses == [(c.response['raw_completion'], c.payload, 'Kwame', True)]
    assert c.m.r55.read(c.out / 'response.json') == c.response
    assert (c.out / 'raw-completion.txt').read_text() == c.response['raw_completion']
    assert c.m.r55.read(c.out / 'native-parse.json') == c.parsed
    assert c.m.verify_output(c.out)['status'] == 'capacity_probe_passed'
    assert (c.out / 'implementation/scripts/run_socialmem_r55_capacity_probe.py').is_file()
    assert (c.out / 'implementation/tests/python/test_socialmem_r55_capacity_probe.py').is_file()
    assert (c.out / 'implementation/scripts/run_socialmem_r55_expanded.py').is_file()
    assert (c.out / 'runtime/python/starling/_core.fixture.so').is_file()
    assert c.m.r55.baseline.BudgetLedger(c.out / 'request-ledger.sqlite', 1).reserve('again', 'extract', 1)['state'] == 'blocked'


@pytest.mark.parametrize('failure', ['transport', 'length', 'exception', 'two_attempts', 'no_usage',
                                    'native_envelope', 'native_schema', 'native_semantic_only'])
def test_all_failed_terminals_are_accounted_and_sealed_without_retry(case, failure):
    c = case
    if failure == 'transport':
        c.response.update(ok=False, error='timeout', finish_reason='')
        c.response['http_attempts'][0].update(http_status=0, curl_code=28, execution_certainty='unknown')
    elif failure == 'length': c.response.update(ok=False, error='completion_truncated', finish_reason='length')
    elif failure == 'exception': c.error = RuntimeError('unknown request outcome')
    elif failure == 'two_attempts':
        c.response['attempt_count'] = 2; c.response['http_attempts'] *= 2
    elif failure == 'no_usage': c.response.update(prompt_tokens=0, completion_tokens=0, total_tokens=0)
    elif failure in ('native_envelope', 'native_schema'):
        c.parsed.update(errors=[{'kind': failure.removeprefix('native_') + '_failure'}], statements=[])
    else: c.parsed['statements'] = []
    result = c.m.run(c.prepare, c.failed, c.out)
    assert result['status'] != 'capacity_probe_passed' and result['terminal'] is True
    assert len(c.calls) == 1 and len(c.constructions) == 1
    assert result['ledger']['committed'] == 1 and result['ledger']['remaining'] == 0
    if failure in ('exception', 'two_attempts'):
        assert result['ledger']['charged_upper'] == 1
    if failure != 'exception': assert c.m.r55.read(c.out / 'response.json') == c.response
    assert c.m.verify_output(c.out)['status'] == result['status']


def test_post_request_input_drift_cannot_be_promoted(case):
    original = case.core.claim_parse_response
    def tamper(*args):
        value = original(*args)
        (case.failed / 'late-file').write_text('input changed while request was in flight')
        return value
    case.core.claim_parse_response = tamper
    result = case.m.run(case.prepare, case.failed, case.out)
    assert result['status'] == 'technical_failure'
    assert result['input_revalidation_ok'] is False
    assert result['ledger']['committed'] == 1
    assert case.m.verify_output(case.out)['status'] == 'technical_failure'


@pytest.mark.parametrize('archive', ['config.json', 'original-config.json', 'binding.json', 'failed-response.json',
                                    'inputs/prepare-seal.json', 'inputs/failed-seal.json', 'inputs/failed-scope.json',
                                    'prompt.txt'])
def test_archived_evidence_drift_before_request_is_rejected_without_provider(case, monkeypatch, archive):
    freeze = case.m.freeze_dependencies
    def corrupt(out, validated):
        dependencies = freeze(out, validated)
        (out / archive).write_text('{}')
        return dependencies
    monkeypatch.setattr(case.m, 'freeze_dependencies', corrupt)
    result = case.m.run(case.prepare, case.failed, case.out)
    assert result['status'] == 'technical_failure' and not result['input_revalidation_ok']
    assert case.calls == case.constructions == []
    assert result['ledger']['committed'] == 0 and result['external_requests_observed'] == 0


def test_archived_capacity_parameters_drift_during_request_cannot_be_promoted(case):
    parse = case.core.claim_parse_response
    def corrupt(*args):
        result = parse(*args)
        config = case.m.r55.read(case.out / 'config.json')
        config['extract_max_tokens'] = 8192
        case.m.r55.write(case.out / 'config.json', config)
        return result
    case.core.claim_parse_response = corrupt
    result = case.m.run(case.prepare, case.failed, case.out)
    assert result['status'] == 'technical_failure' and not result['input_revalidation_ok']
    assert len(case.calls) == 1


def test_resealed_ledger_drift_cannot_pass_output_verification(case):
    case.m.run(case.prepare, case.failed, case.out)
    with closing(sqlite3.connect(case.out / 'request-ledger.sqlite')) as conn:
        conn.execute('UPDATE reservations SET actual=0'); conn.commit()
    seal = case.m.r55.read(case.out / 'seal.json')
    seal['files']['request-ledger.sqlite'] = case.m.r55.sha(case.out / 'request-ledger.sqlite')
    case.m.r55.write(case.out / 'seal.json', seal)
    with pytest.raises(ValueError, match='ledger'):
        case.m.verify_output(case.out)


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_real_frozen_core_binds_exact_input_and_rejects_truncated_json_offline():
    driver()
    code = '''
import importlib.util,json
from pathlib import Path
spec=importlib.util.spec_from_file_location('probe',Path('scripts/run_socialmem_r55_capacity_probe.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.make_extract_adapter=lambda *a: (_ for _ in ()).throw(AssertionError('provider constructed offline'))
v=m.validate_inputs(m.DEFAULT_PREPARE,m.DEFAULT_FAILED)
assert v['binding']['core_sha256']=='02a2a3d8c653d331c700cdf652c59fefe2b812ff99845271bd5137bebf81dd3d'
assert v['binding']['payload_sha256']=='739a240bde63ee1286da19474305fb620be683fd48f4bf29defd3144cac7fab9'
assert v['binding']['prompt_sha256']=='615351de9d8c0a8e477232190d6b95c05c9848623482d3d4a0e5467c0b4cb52a'
parsed=json.loads(v['core'].claim_parse_response(v['failed_response']['raw_completion'],v['payload'],'Kwame',True))
assert parsed['errors'] and not parsed['statements']
fake=v['core'].FakeLLMAdapter();fake.set_default_response('{"schema_version":2,"statements":[]}')
request=v['core'].StructuredOutputRequest(v['core'].OutputContractKind.ClaimExtractionV2,v['core'].OutputMode.JsonObject)
receipt=json.loads(fake.extract_with_contract(v['prompt'],v['binding']['prompt_sha256'],request).to_json())
assert receipt['attempt_count']==0
assert json.loads(v['core'].claim_parse_response(receipt['raw_completion'],v['payload'],'Kwame',True))['errors']==[]
print(json.dumps(v['binding'],sort_keys=True))
'''
    result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
