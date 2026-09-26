#!/usr/bin/env python3
"""R56 Kwame 原生分批验收：prepare/check 零 provider，run 有界且不续跑。"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import traceback

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PARENT = ROOT / 'build/socialmem_20260925_r55_capacity_probe'
PARENT_SEAL_SHA256 = '7c6f48b79f05d960201c5d2a9f13312c1c6c17686c4c8021236ff317aa888a04'
PARENT_FILE_COUNT = 859
PAYLOAD_SHA256 = '739a240bde63ee1286da19474305fb620be683fd48f4bf29defd3144cac7fab9'
PAYLOAD_BYTES = 12133
PROMPT_SHA256 = '615351de9d8c0a8e477232190d6b95c05c9848623482d3d4a0e5467c0b4cb52a'
SCOPE, HOLDER, TENANT = '1c2838ef51b9983207436fc9', 'Kwame', 'default'
BUDGET = 15
IMPLEMENTATION = ('scripts/run_socialmem_r56_kwame_probe.py', 'scripts/run_socialmem_baseline.py',
                  'tests/python/test_socialmem_r56_kwame_probe.py')
FIXED = dict(extract_model='qwen3.8-27b', extract_enable_thinking=False, extract_max_tokens=8192,
    timeout_ms=120000, max_retries=0, semantic_claim_contract=True, preserve_text_objects=True,
    claim_allow_code_fence=True, claim_protocol_retry_budget=1, claim_output_mode='json_object')


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


baseline = load(ROOT / 'scripts/run_socialmem_baseline.py', 'r56_budget_helpers')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text_sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def inventory(directory):
    result = {}
    for path in sorted(Path(directory).rglob('*')):
        if '__pycache__' in path.parts: continue
        if path.is_symlink(): raise ValueError('unsafe symlink: ' + str(path))
        if path.is_file(): result[path.relative_to(directory).as_posix()] = sha(path)
    return result


def new_output(path):
    path = Path(path).resolve()
    if path.exists(): raise ValueError('output already exists: ' + str(path))
    return path


def seal(out, stage, state='complete'):
    if (out / 'seal.json').exists(): raise ValueError('output already sealed')
    write(out / 'seal.json', dict(schema='r56-kwame-seal-v1', stage=stage, state=state, files=inventory(out)))


def verify_seal(out):
    metadata = read(out / 'seal.json'); actual = inventory(out); actual.pop('seal.json', None)
    if metadata.get('schema') != 'r56-kwame-seal-v1' or metadata.get('state') != 'complete':
        raise ValueError('incomplete or unknown R56 seal')
    if not actual or metadata.get('files') != actual:
        raise ValueError('R56 seal file set/hash mismatch')
    return metadata


def validate_parent(parent):
    """Verify all 859 files without old R55 current-core/source checks."""
    parent = Path(parent).resolve()
    if sha(parent / 'seal.json') != PARENT_SEAL_SHA256: raise ValueError('fixed parent seal mismatch')
    metadata = read(parent / 'seal.json'); actual = inventory(parent); actual.pop('seal.json', None)
    if (metadata.get('schema') != 'r55-capacity-seal-v1' or metadata.get('state') != 'complete'
        or len(actual) != PARENT_FILE_COUNT or actual != metadata.get('files')):
        raise ValueError('parent seal complete file set/hash mismatch')
    binding = read(parent / 'binding.json')
    expected = dict(scope=SCOPE, holder=HOLDER, tenant_id=TENANT, payload_sha256=PAYLOAD_SHA256,
                    payload_bytes=PAYLOAD_BYTES, prompt_sha256=PROMPT_SHA256)
    if any(binding.get(k) != v for k, v in expected.items()): raise ValueError('parent holder/source binding mismatch')
    payload_bytes = (parent / 'source-payload.txt').read_bytes()
    prompt_bytes = (parent / 'prompt.txt').read_bytes()
    if len(payload_bytes) != PAYLOAD_BYTES or sha(parent / 'source-payload.txt') != PAYLOAD_SHA256:
        raise ValueError('parent payload bytes/hash mismatch')
    if sha(parent / 'prompt.txt') != PROMPT_SHA256: raise ValueError('parent original prompt hash mismatch')
    database = parent / 'inputs/source.db'
    if sha(database) != binding.get('database_sha256'): raise ValueError('parent source DB hash mismatch')
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro&immutable=1', uri=True)) as db:
        rows = db.execute('SELECT s.engram_ref,e.payload_inline FROM source_documents s JOIN engrams e '
            'ON e.id=s.engram_ref AND e.tenant_id=s.tenant_id WHERE s.tenant_id=? AND s.holder_id=?',
            (TENANT, HOLDER)).fetchall()
    if rows != [(binding.get('engram_ref'), payload_bytes)]: raise ValueError('parent DB holder/payload mismatch')
    scope = read(parent / 'inputs/failed-scope.json')
    holders = [r for r in scope.get('extraction', []) if r.get('holder') == HOLDER]
    if scope.get('group') != SCOPE or len(holders) != 1 or holders[0].get('engram_ref') != binding['engram_ref']:
        raise ValueError('parent scope/holder engram mismatch')
    channel = holders[0]['receipt']['channels']['belief']
    if (channel.get('source_payload_hash') != PAYLOAD_SHA256 or channel.get('prompt_input_hash') != PROMPT_SHA256
        or channel.get('prompt', '').encode('utf-8') != prompt_bytes):
        raise ValueError('parent original receipt mismatch')
    config = read(parent / 'original-config.json')
    if any(config.get(k) != v or type(config.get(k)) is not type(v) for k, v in FIXED.items()):
        raise ValueError('parent original protocol mismatch')
    return dict(parent=parent, binding=binding, config=config, payload=payload_bytes.decode('utf-8'),
                prompt=prompt_bytes.decode('utf-8'), database=database)


def source_paths():
    paths = {ROOT / name for name in IMPLEMENTATION}
    for directory in ('src', 'include', 'python', 'bindings/python', 'cmake', 'migrations'):
        paths.update(p for p in (ROOT / directory).rglob('*') if p.is_file()
            and '__pycache__' not in p.parts and p.suffix in ('.cpp', '.hpp', '.h', '.py', '.in', '.cmake', '.sql'))
    for name in ('CMakeLists.txt', 'build/CMakeCache.txt', 'tests/cpp/test_claim_batching.cpp'):
        if (ROOT / name).is_file(): paths.add(ROOT / name)
    return sorted(paths)


def copy_file(source, target):
    target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, target)


def load_frozen(out, identity):
    frozen = (out / 'frozen').resolve()
    for name, module in tuple(sys.modules.items()):
        if name == 'starling' or name.startswith('starling.'):
            if not Path(getattr(module, '__file__', '')).is_relative_to(frozen):
                raise ValueError('non-frozen Starling module already loaded: ' + name)
    sys.meta_path[:] = [f for f in sys.meta_path if type(f).__module__ != '_starling_memory_editable']
    entry = str(frozen / 'python')
    while entry in sys.path: sys.path.remove(entry)
    sys.path.insert(0, entry)
    from starling import _core, runtime
    for name, module in tuple(sys.modules.items()):
        if name == 'starling' or name.startswith('starling.'):
            path = Path(module.__file__).resolve()
            if not path.is_relative_to(frozen) or sha(path) != identity['frozen_files'].get(path.relative_to(frozen).as_posix()):
                raise ValueError('loaded frozen dependency mismatch: ' + name)
    if sha(_core.__file__) != identity['core_sha256']: raise ValueError('loaded frozen core identity mismatch')
    return _core, runtime


def make_policy(core, config):
    policy = core.ValidationPolicy()
    for key in ('semantic_claim_contract', 'preserve_text_objects', 'claim_allow_code_fence',
                'claim_protocol_retry_budget', 'claim_batch_size'):
        setattr(policy, key, config[key])
    policy.claim_output_mode = core.OutputMode.JsonObject
    return policy


def native_plan(core, payload, prompt, config):
    if core.claim_extraction_prompt(payload, HOLDER) != prompt:
        raise ValueError('new core changed the original unbatched prompt')
    plan = json.loads(core.claim_extraction_batch_plan(payload, make_policy(core, config)))
    if (plan.get('claim_batch_size') != 8 or plan.get('claim_protocol_retry_budget') != 1
        or plan.get('source_payload_hash') != PAYLOAD_SHA256 or len(plan.get('source_units', [])) != 33
        or len(plan.get('batches', [])) != 5 or plan.get('belief_request_upper_bound') != BUDGET):
        raise ValueError('native batch plan does not match the fixed 33-unit/5-batch/15-request experiment')
    return plan


def prepare(parent, out, evidence=()):
    out = new_output(out); original = validate_parent(parent)
    cores = list((ROOT / 'build/python/starling').glob('_core*.so'))
    if len(cores) != 1: raise ValueError('one newly built native core is required')
    core_path = cores[0]
    sources = {p.relative_to(ROOT).as_posix(): sha(p) for p in source_paths()}
    evidence_paths = {str(Path(p).resolve()): sha(p) for p in evidence}
    core_sha = sha(core_path)
    out.mkdir(parents=True)
    try:
        for relative in sources: copy_file(ROOT / relative, out / 'source' / relative)
        for path in sorted((ROOT / 'python/starling').rglob('*.py')):
            if '__pycache__' not in path.parts: copy_file(path, out / 'frozen/python/starling' / path.relative_to(ROOT / 'python/starling'))
        copy_file(core_path, out / 'frozen/python/starling' / core_path.name)
        for index, (path, digest) in enumerate(evidence_paths.items()):
            copy_file(Path(path), out / 'evidence' / (str(index) + '-' + Path(path).name))
        for source, name in [(original['parent'] / 'seal.json', 'parent-seal.json'),
            (original['database'], 'source.db'), (original['parent'] / 'source-payload.txt', 'source-payload.txt'),
            (original['parent'] / 'prompt.txt', 'original-prompt.txt'),
            (original['parent'] / 'binding.json', 'parent-binding.json'),
            (original['parent'] / 'inputs/failed-scope.json', 'failed-scope.json')]:
            copy_file(source, out / 'inputs' / name)
        config = {**original['config'], 'core_sha256': core_sha, 'claim_batch_size': 8}
        identity = dict(core_sha256=core_sha, current_core=str(core_path.resolve()), source_files=sources,
                        frozen_files=inventory(out / 'frozen'), evidence_sources=evidence_paths,
                        evidence_files=inventory(out / 'evidence'))
        binding = dict(parent=str(original['parent']), parent_seal_sha256=PARENT_SEAL_SHA256,
            parent_database_sha256=sha(original['database']), holder=HOLDER, tenant_id=TENANT, scope=SCOPE,
            original_engram_ref=original['binding']['engram_ref'], payload_sha256=PAYLOAD_SHA256,
            payload_bytes=PAYLOAD_BYTES, original_prompt_sha256=PROMPT_SHA256)
        for name, value in [('identity.json', identity), ('config.json', config), ('binding.json', binding),
                            ('original-config.json', original['config'])]: write(out / name, value)
        core, runtime = load_frozen(out, identity)
        plan = native_plan(core, original['payload'], original['prompt'], config)
        write(out / 'batch-plan.json', plan)
        write(out / 'stage.json', dict(stage='prepare', parent=str(original['parent'])))
        summary = dict(stage='prepare', state='complete', external_requests=0, source_units=33, batches=5,
                       belief_request_upper_bound=BUDGET, core_sha256=core_sha)
        write(out / 'summary.json', summary)
        validate_prepared(out)
        seal(out, 'prepare')
        return summary
    except BaseException:
        (out / 'exception.txt').write_text(traceback.format_exc())
        seal(out, 'prepare', 'incomplete')
        raise


def validate_prepared(out):
    identity, binding, config = read(out / 'identity.json'), read(out / 'binding.json'), read(out / 'config.json')
    original = validate_parent(binding['parent'])
    expected_binding = dict(parent=str(original['parent']), parent_seal_sha256=PARENT_SEAL_SHA256,
        parent_database_sha256=sha(original['database']), holder=HOLDER, tenant_id=TENANT, scope=SCOPE,
        original_engram_ref=original['binding']['engram_ref'], payload_sha256=PAYLOAD_SHA256,
        payload_bytes=PAYLOAD_BYTES, original_prompt_sha256=PROMPT_SHA256)
    if binding != expected_binding: raise ValueError('prepared parent/holder binding mismatch')
    if config != {**original['config'], 'core_sha256': identity['core_sha256'], 'claim_batch_size': 8}:
        raise ValueError('prepared fixed protocol mismatch')
    if read(out / 'original-config.json') != original['config']: raise ValueError('prepared original protocol mismatch')
    current_sources = {p.relative_to(ROOT).as_posix(): sha(p) for p in source_paths()}
    if current_sources != identity['source_files'] or inventory(out / 'source') != current_sources:
        raise ValueError('current or frozen source identity mismatch')
    cores = list((ROOT / 'build/python/starling').glob('_core*.so'))
    if (len(cores) != 1 or str(cores[0].resolve()) != identity['current_core']
        or sha(cores[0]) != identity['core_sha256'] or inventory(out / 'frozen') != identity['frozen_files']):
        raise ValueError('current or frozen core identity mismatch')
    if (any(sha(path) != digest for path, digest in identity['evidence_sources'].items())
        or inventory(out / 'evidence') != identity['evidence_files']):
        raise ValueError('build/test evidence changed')
    for name, source in [('parent-seal.json', original['parent'] / 'seal.json'), ('source.db', original['database']),
        ('source-payload.txt', original['parent'] / 'source-payload.txt'), ('original-prompt.txt', original['parent'] / 'prompt.txt'),
        ('parent-binding.json', original['parent'] / 'binding.json'), ('failed-scope.json', original['parent'] / 'inputs/failed-scope.json')]:
        if sha(out / 'inputs' / name) != sha(source): raise ValueError('prepared input copy drift: ' + name)
    core, runtime = load_frozen(out, identity)
    if sha(core.__file__) != identity['core_sha256'] or not Path(core.__file__).resolve().is_relative_to((out / 'frozen').resolve()):
        raise ValueError('loaded core path/hash mismatch')
    plan = native_plan(core, original['payload'], original['prompt'], config)
    if plan != read(out / 'batch-plan.json'): raise ValueError('native plan drift')
    return dict(core=core, runtime=runtime, config=config, plan=plan, payload=original['payload'],
                identity=identity, binding=binding)


def read_ledger(path):
    if any(Path(str(path) + suffix).exists() for suffix in ('-wal', '-shm')): raise ValueError('unsealed ledger WAL')
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro&immutable=1', uri=True)) as db:
        rows = db.execute('SELECT upper_bound,actual,state FROM reservations').fetchall()
    if len(rows) > 1: raise ValueError('only one upfront reservation is allowed')
    committed = charged = reserved = 0
    for upper, actual, state in rows:
        if upper != BUDGET or state not in ('reserved', 'settled', 'charged_upper'): raise ValueError('invalid ledger reservation')
        if state == 'reserved': reserved += upper
        elif state == 'charged_upper': committed += upper; charged += upper
        elif type(actual) is int and 0 <= actual <= upper: committed += actual
        else: raise ValueError('invalid ledger settlement')
    return dict(budget=BUDGET, committed=committed, charged_upper=charged, reserved=reserved,
                remaining=BUDGET - committed - reserved)


def check(out):
    out = Path(out).resolve(); metadata = verify_seal(out); stage = read(out / 'stage.json')
    if metadata.get('stage') != stage.get('stage'): raise ValueError('stage identity mismatch')
    if stage['stage'] == 'prepare':
        result = validate_prepared(out); result['summary'] = read(out / 'summary.json')
        if result['summary'].get('external_requests') != 0: raise ValueError('prepare must be offline')
        return result
    if stage['stage'] != 'run': raise ValueError('unknown R56 stage')
    prepared = Path(stage['input']); validated = check(prepared)
    validate_run_inputs(out, prepared, stage['input_seal_sha256'])
    terminal = read(out / 'terminal.json')
    ledger = read_ledger(out / 'request-ledger.sqlite')
    if (terminal != read(out / 'summary.json') or terminal.get('terminal') is not True
        or terminal.get('ledger') != ledger or ledger['reserved'] or ledger['remaining'] < 0):
        raise ValueError('run terminal/ledger mismatch')
    invoked = terminal.get('native_entry_invoked')
    if type(invoked) is not bool: raise ValueError('native entry invocation evidence missing')
    receipt = read(out / 'native-receipt.json') if (out / 'native-receipt.json').exists() else None
    commit = read(out / 'commit.json') if (out / 'commit.json').exists() else None
    accounting = terminal_accounting(receipt, invoked)
    if accounting != terminal.get('accounting') or accounting != read(out / 'usage-and-http.json'):
        raise ValueError('native accounting mismatch')
    charged = BUDGET if invoked and (accounting['local_attempt_count_unknown']
        or accounting['observed_local_http_attempts'] > BUDGET) else 0
    expected_committed = charged or accounting['observed_local_http_attempts']
    if ledger['charged_upper'] != charged or ledger['committed'] != expected_committed:
        raise ValueError('native HTTP receipt costs do not match ledger settlement')
    if (out / 'frozen.db').exists():
        database = database_report(out / 'frozen.db', validated, commit)
        if database != terminal.get('database'): raise ValueError('database proof mismatch')
    if terminal['status'] == 'kwame_probe_passed':
        if terminal.get('input_revalidation_ok') is not True or not invoked:
            raise ValueError('passed terminal requires revalidated input and a native extraction entry')
        require_success(receipt, commit, database, accounting, validated['plan'])
    return dict(summary=terminal)


def make_extract_adapter(core, config):
    with baseline._provider_environment('DASHSCOPE_API_KEY', config['extract_endpoint']):
        native = core.OpenAIAdapterConfig.from_env()
        native.model, native.max_tokens = config['extract_model'], config['extract_max_tokens']
        native.timeout_ms, native.max_retries = config['timeout_ms'], config['max_retries']
        native.enable_thinking, native.json_object_output = config['extract_enable_thinking'], False
        return core.OpenAIAdapter(native)


def receipt_accounting(receipt):
    report = dict(observed_local_http_attempts=0, local_attempt_count_unknown=receipt is None,
        remote_execution_unknown_attempts=0, remote_execution_unknown=receipt is None,
        usage_complete=receipt is not None, observed_total_tokens=None, responses=[], extraction_responses=0,
        admission_responses=0, healthy_http=True)
    tokens = []
    if receipt is None: return report
    attempts = receipt.get('attempts')
    if not isinstance(attempts, list) or not attempts:
        report.update(local_attempt_count_unknown=True, usage_complete=False, healthy_http=False)
        return report
    for attempt in attempts:
        entries = [('extraction', attempt.get('extraction'))]
        admission = attempt.get('admission')
        if not isinstance(admission, dict) or type(admission.get('called')) is not bool:
            report['local_attempt_count_unknown'] = True
        elif admission['called']: entries.append(('admission', admission))
        elif admission.get('attempt_count', 0) or admission.get('http_attempts', []):
            entries.append(('admission', admission))
            report.update(local_attempt_count_unknown=True, healthy_http=False)
        for kind, response in entries:
            report[kind + '_responses'] += 1
            row = dict(attempt=attempt.get('attempt'), batch_index=attempt.get('batch_index'), channel=kind,
                       local_http_attempts=None, usage=None)
            if not isinstance(response, dict):
                report.update(local_attempt_count_unknown=True, usage_complete=False, healthy_http=False)
                report['responses'].append(row); continue
            http, count = response.get('http_attempts'), response.get('attempt_count')
            if isinstance(http, list):
                report['observed_local_http_attempts'] += len(http); row['local_http_attempts'] = len(http)
                if type(count) is not int or count != len(http): report['local_attempt_count_unknown'] = True
                for h in http:
                    unknown = h.get('execution_certainty') == 'unknown'
                    report['remote_execution_unknown_attempts'] += int(unknown)
                    report['remote_execution_unknown'] |= unknown
                healthy = (count == 1 and len(http) == 1 and http[0].get('http_status') == 200
                    and http[0].get('curl_code') == 0 and http[0].get('execution_certainty') == 'response_received'
                    and bool(http[0].get('response_body')))
            else:
                report['local_attempt_count_unknown'] = True; healthy = False
            healthy = (healthy and response.get('ok') is True and response.get('error') == ''
                and response.get('finish_reason') == 'stop' and response.get('refusal') is False
                and response.get('output_mode') == 'json_object'
                and response.get('output_contract') == ('claim_extraction_v2' if kind == 'extraction' else 'claim_admission_v1'))
            report['healthy_http'] &= bool(healthy)
            usage = {k: response.get(k) for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')}
            values = list(usage.values())
            if (all(type(v) is int and v > 0 for v in values) and values[0]+values[1] == values[2]):
                row['usage'] = usage; tokens.append(values[2])
            else: report['usage_complete'] = False
            report['responses'].append(row)
    report['observed_total_tokens'] = sum(tokens) if tokens else None
    report['remote_execution_unknown'] |= report['local_attempt_count_unknown']
    return report


def terminal_accounting(receipt, native_invoked):
    if not native_invoked and receipt is not None: raise ValueError('receipt without native invocation')
    accounting = receipt_accounting(receipt)
    if not native_invoked:
        accounting.update(local_attempt_count_unknown=False, remote_execution_unknown=False,
                          usage_complete=True, observed_total_tokens=0)
    return accounting


def database_report(path, validated, commit):
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro&immutable=1', uri=True)) as db:
        rows = db.execute('SELECT id,tenant_id,holder_id,semantic_claim_json FROM statements ORDER BY id').fetchall()
        engrams = db.execute('SELECT id,tenant_id,payload_inline FROM engrams').fetchall()
        attempts = db.execute('SELECT COUNT(*) FROM extraction_attempt').fetchone()[0]
    if commit is None:
        if rows: raise ValueError('claims were persisted without a native commit receipt')
    else:
        ids = [r[0] for r in rows]
        if ids != sorted(commit.get('statement_ids', [])) or len(ids) != len(set(ids)):
            raise ValueError('database IDs do not match native commit')
        if engrams != [(commit.get('engram_ref'), TENANT, validated['payload'].encode('utf-8'))]:
            raise ValueError('database source engram payload mismatch')
        if commit.get('extraction_failed') is True and rows: raise ValueError('failed native extraction persisted claims')
        if attempts < 1: raise ValueError('native commit failure/success audit is missing')
        units = {unit['clause_id']: unit for unit in validated['plan']['source_units']}
        for sid, tenant, holder, raw in rows:
            if tenant != TENANT or holder != HOLDER: raise ValueError('persisted claim holder/tenant mismatch')
            claim = json.loads(raw); unit = units.get(claim.get('clause_id'))
            if unit is None: raise ValueError('persisted claim references an unknown native source unit')
            expected = dict(engram_ref=commit['engram_ref'], span_start=unit['byte_start'], span_end=unit['byte_end'],
                            source_hash=unit['payload_hash'])
            if claim.get('source_span') != expected: raise ValueError('persisted claim native source proof mismatch')
            if 'speaker' in unit:
                turn = {k: unit.get(k) for k in ('speaker', 'session_id', 'turn_id', 'turn_index', 'observed_at')}
                if claim.get('source_turn') != turn: raise ValueError('persisted native SourceTurn proof mismatch')
    return dict(statement_ids=[r[0] for r in rows], statement_count=len(rows), engram_count=len(engrams),
                extraction_attempt_count=attempts, database_sha256=sha(path))


def require_success(receipt, commit, database, accounting, plan):
    if (receipt.get('claim_batches_complete') is not True or receipt.get('claim_batch_integrity_detail', '') != ''
        or receipt.get('claim_batch_plan') != plan or receipt.get('claim_batch_size') != 8
        or receipt.get('source_payload_hash') != PAYLOAD_SHA256 or receipt.get('holder') != HOLDER
        or receipt.get('failure_category') not in ('', 'semantic_rejection') or receipt.get('persistence_error') != ''):
        raise ValueError('native batch completion/integrity failed')
    if (accounting['local_attempt_count_unknown'] or accounting['observed_local_http_attempts'] > BUDGET
        or not accounting['healthy_http'] or not accounting['usage_complete']):
        raise ValueError('native HTTP/usage evidence failed')
    if (commit.get('extraction_failed') is not False or commit.get('source_preserved') is not True
        or commit.get('structured_claims_persisted') is not True or not database['statement_ids']):
        raise ValueError('native commit did not persist qualified claims')


def validate_run_inputs(out, prepared, prepare_sha):
    checked = check(prepared)
    if sha(prepared / 'seal.json') != prepare_sha or sha(out / 'prepare-seal.json') != prepare_sha:
        raise ValueError('run prepare seal mismatch')
    for name in ('config.json', 'binding.json', 'batch-plan.json', 'identity.json'):
        if sha(out / name) != sha(prepared / name): raise ValueError('run input copy drift: ' + name)
    return checked


def run(prepared, out):
    out = new_output(out); prepared = Path(prepared).resolve(); validated = check(prepared)
    if read(prepared / 'stage.json')['stage'] != 'prepare': raise ValueError('run requires a prepared input')
    prepare_sha = sha(prepared / 'seal.json'); out.mkdir(parents=True)
    ledger = baseline.BudgetLedger(out / 'request-ledger.sqlite', BUDGET)
    result = dict(stage='run', terminal=True, status='technical_failure', input_revalidation_ok=False,
        accounting=receipt_accounting(None), protocol_error_attempts=0, semantic_rejections=0,
        admission_rejections=0, general_fact_requests=0, episodic_requests=0, embedding_requests=0, qa_requests=0,
        limitation='Only the bound Kwame input is tested; no full-build, semantic recall or QA claim.')
    receipt = commit = reservation = None
    native_invoked = False
    live_path = None
    with tempfile.TemporaryDirectory(prefix='r56-kwame-live-') as scratch:
        try:
            for name in ('config.json', 'binding.json', 'batch-plan.json', 'identity.json'):
                copy_file(prepared / name, out / name)
            copy_file(prepared / 'seal.json', out / 'prepare-seal.json')
            write(out / 'stage.json', dict(stage='run', input=str(prepared), input_seal_sha256=prepare_sha))
            validated = validate_run_inputs(out, prepared, prepare_sha)
            core, runtime, config = validated['core'], validated['runtime'], validated['config']
            policy = make_policy(core, config)
            live_path = Path(scratch) / 'live.db'
            rt = runtime._build_local_store_sqlite_runtime(live_path); rt.start()
            prepared_native = core.memory_remember_prepare(rt.adapter, tenant_id=TENANT, holder_id=HOLDER,
                interlocutor='', adapter_name='r56_kwame_probe', source_prefix='r56_kwame_probe',
                created_at_iso8601=config['created_at'], payload=validated['payload'].encode('utf-8'))
            write(out / 'remember-prepare.json', {k: getattr(prepared_native, k) for k in
                ('engram_ref', 'outcome', 'should_extract', 'created_at_iso8601')})
            if prepared_native.should_extract is not True: raise ValueError('native prepare did not authorize extraction')
            adapter = make_extract_adapter(core, config)
            reservation = ledger.reserve(SCOPE + '/' + HOLDER, 'native_belief_batches', BUDGET)
            if reservation['state'] != 'reserved': raise ValueError('native batch budget exhausted')
            native_invoked = True
            extracted = core.memory_extract_llm(rt.adapter, adapter, '', HOLDER,
                                               validated['payload'].encode('utf-8'), policy)
            native_json = core.claim_extraction_receipt(extracted)
            (out / 'native-receipt.json').write_text(native_json, encoding='utf-8'); receipt = json.loads(native_json)
            # Commit failed results too: native persistence owns the zero-claim failure audit.
            commit = core.memory_remember_commit(rt.adapter, adapter, tenant_id=TENANT, holder_id=HOLDER,
                interlocutor='', prepared=prepared_native, llm_result=extracted, policy=policy)
            write(out / 'commit.json', commit)
        except BaseException as exc:
            result['error'] = type(exc).__name__ + ': ' + str(exc)
            (out / 'exception.txt').write_text(traceback.format_exc(), encoding='utf-8')
        finally:
            result['native_entry_invoked'] = native_invoked
            accounting = terminal_accounting(receipt, native_invoked)
            result['accounting'] = accounting
            write(out / 'usage-and-http.json', accounting)
            if reservation and reservation.get('state') == 'reserved':
                if accounting['local_attempt_count_unknown'] or accounting['observed_local_http_attempts'] > BUDGET:
                    ledger.charge_upper(reservation['id'])
                else: ledger.settle(reservation['id'], accounting['observed_local_http_attempts'])
            try:
                if live_path is not None and live_path.is_file():
                    with closing(sqlite3.connect(live_path)) as source, closing(sqlite3.connect(out / 'frozen.db')) as target:
                        source.backup(target)
                    result['database'] = database_report(out / 'frozen.db', validated, commit)
                if receipt is not None:
                    attempts = receipt.get('attempts', [])
                    result.update(protocol_error_attempts=sum(bool(a.get('errors')) for a in attempts),
                        semantic_rejections=sum(len(a.get('semantic_rejections', [])) for a in attempts),
                        admission_rejections=sum(int(a.get('admission', {}).get('semantic_rejected', 0)) for a in attempts))
                if receipt is not None and commit is not None and 'error' not in result:
                    require_success(receipt, commit, result['database'], accounting, validated['plan'])
                    result['status'] = 'kwame_probe_passed'
            except BaseException as exc:
                result.update(status='technical_failure', validation_error=type(exc).__name__ + ': ' + str(exc))
            try:
                validate_run_inputs(out, prepared, prepare_sha); result['input_revalidation_ok'] = True
            except BaseException as exc:
                result.update(status='technical_failure', revalidation_error=type(exc).__name__ + ': ' + str(exc))
            result['ledger'] = ledger.snapshot()
            write(out / 'terminal.json', result); write(out / 'summary.json', result)
            seal(out, 'run')
    verify_seal(out)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__); stages = parser.add_subparsers(dest='stage', required=True)
    p = stages.add_parser('prepare'); p.add_argument('--parent', type=Path, default=DEFAULT_PARENT)
    p.add_argument('--out', type=Path, required=True); p.add_argument('--evidence', type=Path, action='append', default=[])
    p = stages.add_parser('check'); p.add_argument('--input', type=Path, required=True)
    p = stages.add_parser('run'); p.add_argument('--input', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.stage == 'prepare': result = prepare(args.parent, args.out, args.evidence)
    elif args.stage == 'check': result = check(args.input)['summary']
    else: result = run(args.input, args.out)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return int(result.get('status') == 'technical_failure')


if __name__ == '__main__': raise SystemExit(main())
