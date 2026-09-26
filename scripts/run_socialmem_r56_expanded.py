#!/usr/bin/env python3
"""R5.6扩大开发集：原生分批prepare/build/check；不覆盖、不续跑。"""
from __future__ import annotations

import argparse
from contextlib import closing
import gc
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import traceback

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PARENT = ROOT / 'build/socialmem_20260925_r55_expanded/prepare'
DEFAULT_PROBE = ROOT / 'build/socialmem_20260925_r56_kwame/run'
PARENT_SEAL_SHA256 = '66b13d7e22b0794903467d9ea89f21b91379118d43866b4504b49fd9bd0178d0'
PROBE_SEAL_SHA256 = '30f33e4437f09eaf7b080b7bd630c11afb4f2e10b0767e6e083d95f170f716a7'
CORE_SHA256 = '4c5a7c39ae708a13d10065a0816a5c97a994929479cb0898f504c21e12b422f9'
BUILD_BUDGET = 12000
OVERRIDES = dict(core_sha256=CORE_SHA256, claim_batch_size=8, arm='r56_expanded_development')
DATA_FILES = ('corpus.jsonl', 'network-split.json', 'old-sample.json', 'sample.json', 'groups.json', 'scope-manifest.json')
INPUT_FILES = (*DATA_FILES, 'parent-config.json', 'parent-seal.json', 'probe-seal.json', 'provenance.json', 'batch-plans.json')
RUNTIME_SCRIPTS = ('run_socialmem_baseline.py', 'eval_judge_audit.py', 'eval_ladder.py',
                   'eval_ladder_pipeline.py', 'eval_longmemeval.py', 'eval_adapters.py')


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


previous = load(ROOT / 'scripts/run_socialmem_r55_expanded.py', 'r56_expanded_previous')
baseline = previous.baseline
read, write, sha, inventory = previous.read, previous.write, previous.sha, previous.inventory
copy_file, new_output = previous._copy_file, previous.new_output


def identical(left, right):
    return json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)


def verify_historical(out, expected_hash, schema, stage):
    out = Path(out).resolve()
    if sha(out / 'seal.json') != expected_hash: raise ValueError('fixed historical seal mismatch')
    seal = read(out / 'seal.json'); actual = inventory(out); actual.pop('seal.json', None)
    if (seal.get('schema') != schema or seal.get('state') != 'complete'
        or seal.get('stage') != stage or not actual or seal.get('files') != actual):
        raise ValueError('historical seal file set/hash mismatch')
    return seal


def validate_parents(parent, probe):
    """Pinned historical artifacts remain readable when live source advances."""
    parent, probe = Path(parent).resolve(), Path(probe).resolve()
    verify_historical(parent, PARENT_SEAL_SHA256, 'r55-seal-v1', 'prepare')
    verify_historical(probe, PROBE_SEAL_SHA256, 'r56-kwame-seal-v1', 'run')
    probe_stage = read(probe / 'stage.json'); probe_prepare = Path(probe_stage['input']).resolve()
    verify_historical(probe_prepare, probe_stage['input_seal_sha256'], 'r56-kwame-seal-v1', 'prepare')
    if sha(probe / 'prepare-seal.json') != probe_stage['input_seal_sha256']:
        raise ValueError('historical probe prepare seal mismatch')
    parent_config, probe_config = read(parent / 'config.json'), read(probe / 'config.json')
    if not identical(probe_config, {**parent_config, 'core_sha256': CORE_SHA256, 'claim_batch_size': 8}):
        raise ValueError('successful probe config differs from fixed parent')
    if (read(probe / 'summary.json') != read(probe / 'terminal.json')
        or read(probe / 'summary.json').get('status') != 'kwame_probe_passed'
        or read(probe / 'identity.json').get('core_sha256') != CORE_SHA256):
        raise ValueError('successful probe/core evidence missing')
    records, groups, manifest = previous._cohort_from_files(parent)
    for name, value in [('sample.json', records), ('groups.json', groups), ('scope-manifest.json', manifest)]:
        if read(parent / name) != value: raise ValueError('historical cohort mismatch')
    return dict(parent=parent, probe=probe, records=records, groups=groups, manifest=manifest,
                config={**parent_config, **OVERRIDES})


def source_paths():
    paths = {ROOT / name for name in previous.IMPLEMENTATION_FILES}
    paths.update(ROOT / 'scripts' / name for name in RUNTIME_SCRIPTS)
    paths.update(ROOT / name for name in ('scripts/run_socialmem_r56_expanded.py',
        'tests/python/test_socialmem_r56_expanded.py', 'tests/python/test_claim_batching.py',
        'tests/python/test_run_socialmem_baseline.py', 'tests/cpp/test_claim_batching.cpp',
        'CMakeLists.txt', 'build/CMakeCache.txt'))
    for directory in ('src', 'include', 'python', 'bindings/python', 'migrations', 'cmake'):
        paths.update(p for p in (ROOT / directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts
            and (p.suffix in ('.cpp', '.hpp', '.h', '.py', '.in', '.cmake', '.sql') or p.name == 'CMakeLists.txt'))
    return sorted(paths)


def current_core():
    cores = list((ROOT / 'build/python/starling').glob('_core*.so'))
    if len(cores) != 1 or sha(cores[0]) != CORE_SHA256: raise ValueError('fixed current core mismatch')
    return cores[0]


def frozen_modules(work, config, identity):
    runner = load(work / 'frozen/scripts/run_socialmem_baseline.py', 'r56_expanded_frozen_baseline')
    modules = runner._frozen_imports(work, config, identity)
    validate_loaded(work, identity)
    return runner, modules


def validate_loaded(work, identity):
    frozen = (work / 'frozen').resolve()
    for name, module in tuple(sys.modules.items()):
        if name == 'starling' or name.startswith('starling.') or name in {
            'eval_judge_audit', 'eval_ladder', 'eval_ladder_pipeline', 'eval_longmemeval', 'eval_adapters'}:
            path = Path(getattr(module, '__file__', '')).resolve()
            if not path.is_relative_to(frozen) or sha(path) != identity['frozen_files'].get(path.relative_to(frozen).as_posix()):
                raise ValueError('loaded dependency outside frozen identity: ' + name)


def native_plans(runner, modules, groups, config):
    """C++ retains full SourceTurns and partitions them; Python only totals plans."""
    core, runtime = modules[:2]; policy = runner._build_extraction_config(config).to_native_policy()
    scopes = {}; holders = units = batches = belief = 0
    with tempfile.TemporaryDirectory(prefix='r56-offline-plans-') as directory:
        for group in groups:
            db_path = Path(directory) / (group['group_id'] + '.db')
            rt = runtime._build_local_store_sqlite_runtime(db_path); rt.start()
            retained = runner.retain_history_sources(core, rt.adapter, group['history'], config['created_at'],
                                                     preserve_invalid_time=True)
            with closing(sqlite3.connect(db_path)) as db:
                rows = db.execute('SELECT d.holder_id,e.payload_inline FROM source_documents d JOIN engrams e '
                    'ON e.id=d.engram_ref AND e.tenant_id=d.tenant_id WHERE d.tenant_id=? ORDER BY d.holder_id',
                    ('default',)).fetchall()
            expected_holders = runner.history_holders(group['history'])
            if [h for h, _ in rows] != expected_holders or retained['turns'] != len(group['history']):
                raise ValueError('native retained source inventory mismatch')
            plans = {holder: json.loads(core.claim_extraction_batch_plan(
                payload.decode('utf-8') if isinstance(payload, bytes) else payload, policy)) for holder, payload in rows}
            scope_belief = sum(p['belief_request_upper_bound'] for p in plans.values())
            scopes[group['group_id']] = dict(holders=plans,
                extraction_request_upper_bound=scope_belief + 4 * len(plans))
            holders += len(plans); units += sum(len(p['source_units']) for p in plans.values())
            batches += sum(len(p['batches']) for p in plans.values()); belief += scope_belief
            del rt; gc.collect()
    return dict(scopes=scopes, holder_count=holders, source_units=units, batches=batches,
                belief_request_upper_bound=belief, extraction_request_upper_bound=belief + 4 * holders)


def validate_plan_counts(plans):
    expected = dict(holder_count=65, source_units=1322, batches=197,
                    belief_request_upper_bound=591, extraction_request_upper_bound=851)
    if any(plans.get(k) != v for k, v in expected.items()): raise ValueError('fixed native plan count/budget mismatch')


def seal_output(out, stage, state='complete'):
    out = Path(out)
    if (out / 'seal.json').exists(): raise ValueError('output already sealed')
    write(out / 'seal.json', dict(schema='r56-expanded-seal-v1', stage=stage, state=state, files=inventory(out)))


def verify_seal(out, *, allow_incomplete=False):
    out = Path(out); seal = read(out / 'seal.json'); actual = inventory(out); actual.pop('seal.json', None)
    states = ('complete', 'incomplete') if allow_incomplete else ('complete',)
    if seal.get('schema') != 'r56-expanded-seal-v1' or seal.get('state') not in states:
        raise ValueError('unknown or incomplete R5.6 seal')
    if not actual or actual != seal.get('files'): raise ValueError('R5.6 seal file set/hash mismatch')
    return seal


def prepared_summary(manifest, plans):
    return dict(stage='prepare', state='complete', **manifest, external_requests=0,
        core_sha256=CORE_SHA256, native_source_units=plans['source_units'], native_batches=plans['batches'],
        belief_request_upper_bound=plans['belief_request_upper_bound'],
        extraction_conservative_bound=plans['extraction_request_upper_bound'], build_budget=BUILD_BUDGET,
        unexecuted_stages=['build', 'retrieve', 'qa'])


def prepare(parent, out, probe=DEFAULT_PROBE, evidence=()):
    out = new_output(out); inputs = validate_parents(parent, probe); core = current_core()
    out.mkdir(parents=True)
    try:
        for name in DATA_FILES: copy_file(inputs['parent'] / name, out / name)
        for source, name in [(inputs['parent'] / 'config.json', 'parent-config.json'),
            (inputs['parent'] / 'seal.json', 'parent-seal.json'), (inputs['probe'] / 'seal.json', 'probe-seal.json')]:
            copy_file(source, out / name)
        write(out / 'config.json', inputs['config'])
        write(out / 'provenance.json', dict(parent=str(inputs['parent']), parent_seal_sha256=PARENT_SEAL_SHA256,
            probe=str(inputs['probe']), probe_seal_sha256=PROBE_SEAL_SHA256,
            runtime_origin='current checkout; historical parents provide only fixed inputs and probe evidence'))
        for path in source_paths(): copy_file(path, out / 'source' / path.relative_to(ROOT))
        for path in (ROOT / 'python/starling').rglob('*.py'):
            if '__pycache__' not in path.parts: copy_file(path, out / 'frozen' / path.relative_to(ROOT))
        copy_file(core, out / 'frozen/python/starling' / core.name)
        for name in RUNTIME_SCRIPTS: copy_file(ROOT / 'scripts' / name, out / 'frozen/scripts' / name)
        evidence_sources = {str(Path(path).resolve()): sha(path) for path in evidence}
        for index, path in enumerate(evidence_sources): copy_file(Path(path), out / 'evidence' / f'{index}-{Path(path).name}')
        identity = dict(schema='r56-expanded-identity-v1', core_sha256=CORE_SHA256,
            config_sha256=sha(out / 'config.json'), frozen_files=inventory(out / 'frozen'),
            source_files=inventory(out / 'source'), evidence_files=inventory(out / 'evidence'), evidence_sources=evidence_sources)
        runner, modules = frozen_modules(out, inputs['config'], identity)
        plans = native_plans(runner, modules, inputs['groups'], inputs['config']); validate_plan_counts(plans)
        write(out / 'batch-plans.json', plans)
        identity['inputs'] = {name: sha(out / name) for name in INPUT_FILES}; write(out / 'identity.json', identity)
        write(out / 'stage.json', dict(stage='prepare', input=None, external_requests=0))
        summary = prepared_summary(inputs['manifest'], plans); write(out / 'summary.json', summary)
        validate_identity(out); validate_loaded(out, identity); seal_output(out, 'prepare')
        return summary
    except BaseException as exc:
        fail_stage(out, 'prepare', exc)
        raise


def validate_identity(out):
    identity, config = read(out / 'identity.json'), read(out / 'config.json')
    provenance = read(out / 'provenance.json'); parents = validate_parents(provenance['parent'], provenance['probe'])
    if (identity.get('schema') != 'r56-expanded-identity-v1' or identity.get('core_sha256') != CORE_SHA256
        or not identical(config, parents['config']) or sha(out / 'config.json') != identity.get('config_sha256')):
        raise ValueError('fixed config/core identity mismatch')
    if (provenance.get('parent_seal_sha256') != PARENT_SEAL_SHA256
        or provenance.get('probe_seal_sha256') != PROBE_SEAL_SHA256
        or sha(out / 'parent-seal.json') != PARENT_SEAL_SHA256 or sha(out / 'probe-seal.json') != PROBE_SEAL_SHA256):
        raise ValueError('historical parent/probe seal identity mismatch')
    for name in DATA_FILES:
        if sha(out / name) != sha(parents['parent'] / name): raise ValueError('fixed input copy drift: ' + name)
    if read(out / 'parent-config.json') != read(parents['parent'] / 'config.json'):
        raise ValueError('parent config copy drift')
    if identity.get('inputs') != {name: sha(out / name) for name in INPUT_FILES}: raise ValueError('input identity mismatch')
    sources = {p.relative_to(ROOT).as_posix(): sha(p) for p in source_paths()}
    if identity.get('source_files') != sources or inventory(out / 'source') != sources:
        raise ValueError('current/frozen source set/hash drift')
    if not identity.get('frozen_files') or identity['frozen_files'] != inventory(out / 'frozen'):
        raise ValueError('frozen dependency set/hash drift')
    expected_runtime = {p.relative_to(ROOT).as_posix(): sha(p) for p in (ROOT / 'python/starling').rglob('*.py') if '__pycache__' not in p.parts}
    expected_runtime.update({'scripts/' + name: sha(ROOT / 'scripts' / name) for name in RUNTIME_SCRIPTS})
    expected_runtime['python/starling/' + current_core().name] = CORE_SHA256
    if identity['frozen_files'] != expected_runtime: raise ValueError('runtime differs from current dependency set/hash')
    if (inventory(out / 'evidence') != identity.get('evidence_files')
        or any(sha(path) != digest for path, digest in identity.get('evidence_sources', {}).items())):
        raise ValueError('verification evidence drift')
    return config, identity, parents


def extraction_accounting(extraction, *, native_invoked=True):
    """Count raw HTTP attempts and raw provider usage; missing usage stays unknown."""
    report = dict(observed_native_requests=0, observed_tokens=None, known_tokens=0, missing_token_usage=0,
        response_observations=0, usage_complete=True, local_attempt_count_unknown=False,
        remote_execution_unknown_attempts=0, remote_execution_unknown=False)
    if not native_invoked:
        if extraction is not None: raise ValueError('extraction receipt without native invocation')
        report['observed_tokens'] = 0
        return report
    if extraction is None:
        report.update(usage_complete=False, local_attempt_count_unknown=True, remote_execution_unknown=True)
        return report
    try:
        responses = list(previous.native_extraction_responses(extraction))
    except (ValueError, TypeError, KeyError):
        # Preserve every response that is available even if a later holder/channel is missing.
        responses = []
        for row in extraction:
            channels = row.get('receipt', {}).get('channels', {})
            for name in ('belief', 'general_fact'):
                for attempt in channels.get(name, {}).get('attempts', []):
                    responses.append(attempt.get('extraction', {}))
                    admission = attempt.get('admission') or {}
                    if admission.get('called') or admission.get('attempt_count'): responses.append(admission)
            responses.append(channels.get('episodic', {}).get('response', {}))
        report.update(usage_complete=False, local_attempt_count_unknown=True)
    for row in extraction:
        channels = row.get('receipt', {}).get('channels', {})
        for name in ('belief', 'general_fact'):
            for attempt in channels.get(name, {}).get('attempts', []):
                admission = attempt.get('admission')
                if not isinstance(admission, dict) or type(admission.get('called')) is not bool:
                    report['local_attempt_count_unknown'] = True
                elif not admission['called'] and (admission.get('attempt_count') or admission.get('http_attempts')):
                    report['local_attempt_count_unknown'] = True
                    if not admission.get('attempt_count'): responses.append(admission)
    for response in responses:
        report['response_observations'] += 1
        http, count = response.get('http_attempts'), response.get('attempt_count')
        if not isinstance(http, list): http = []; report['local_attempt_count_unknown'] = True
        if type(count) is not int or count != len(http): report['local_attempt_count_unknown'] = True
        report['observed_native_requests'] += len(http)
        report['remote_execution_unknown_attempts'] += sum(h.get('execution_certainty') == 'unknown' for h in http)
        if not http: report['usage_complete'] = False; report['missing_token_usage'] += 1
        for attempt in http:
            try:
                usage = json.loads(attempt['response_body'])['usage']
                values = [usage[k] for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')]
                if not all(type(v) is int and v >= 0 for v in values) or values[0] + values[1] != values[2] or values[2] <= 0:
                    raise ValueError('invalid usage')
                if len(http) == 1 and any(response.get(k) != usage[k] for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')):
                    raise ValueError('raw/native usage mismatch')
                report['known_tokens'] += values[2]
            except (ValueError, KeyError, TypeError):
                report['usage_complete'] = False; report['missing_token_usage'] += 1
    report['usage_complete'] &= not report['local_attempt_count_unknown']
    if report['usage_complete']: report['observed_tokens'] = report['known_tokens']
    report['remote_execution_unknown'] = bool(report['remote_execution_unknown_attempts'] or report['local_attempt_count_unknown'])
    return report


def validate_batch_receipts(extraction, scope_plan):
    holders = scope_plan['holders']; observed = [row.get('holder') for row in extraction]
    if sorted(observed) != sorted(holders) or len(set(observed)) != len(observed): raise ValueError('batch holder inventory mismatch')
    for row in extraction:
        channels = row.get('receipt', {}).get('channels', {}); plan = holders[row['holder']]; belief = channels.get('belief', {})
        if (row.get('extraction_failed') is not False or belief.get('claim_batch_plan') != plan
            or belief.get('claim_batches_complete') is not True or belief.get('claim_batch_integrity_detail', '')
            or belief.get('claim_batch_size') != 8 or belief.get('holder') != row['holder']
            or belief.get('source_payload_hash') != plan['source_payload_hash']
            or belief.get('persistence_error', '') or belief.get('failure_category') not in ('', 'semantic_rejection')):
            raise ValueError('native batch completeness/identity failure')
        for name in ('general_fact', 'episodic'):
            if any(k in channels.get(name, {}) for k in ('claim_batch_plan', 'claim_batch_size')):
                raise ValueError('non-belief channel unexpectedly batched')
        for name in ('belief', 'general_fact'):
            for attempt in channels.get(name, {}).get('attempts', []):
                admission = attempt.get('admission')
                if not isinstance(admission, dict) or type(admission.get('called')) is not bool:
                    raise ValueError('missing native admission call evidence')
                if not admission['called'] and (admission.get('attempt_count') or admission.get('http_attempts')):
                    raise ValueError('uncalled admission contains HTTP evidence')
        attempts = belief.get('attempts', []); cursor = 0
        for batch in plan['batches']:
            terminal = False
            for _ in range(plan['claim_protocol_retry_budget'] + 1):
                if cursor >= len(attempts): raise ValueError('missing batch attempt')
                attempt = attempts[cursor]; cursor += 1
                if (attempt.get('attempt') != cursor or attempt.get('batch_index') != batch['batch_index']
                    or attempt.get('target_clause_ids') != batch['target_clause_ids']):
                    raise ValueError('batch attempt numbering/target mismatch')
                terminal = attempt.get('terminal') is True
                if terminal:
                    if attempt.get('errors'): raise ValueError('terminal batch contains protocol errors')
                    break
                if attempt['admission']['called']: raise ValueError('protocol retry unexpectedly calls admission')
                if not attempt.get('errors') or any(e.get('kind') not in ('schema_failure', 'envelope_failure') for e in attempt['errors']):
                    raise ValueError('batch retry lacks native protocol error')
            if not terminal: raise ValueError('batch missing terminal')
        if cursor != len(attempts): raise ValueError('extra batch attempts')
        previous.validate_extraction_responses([row])
        usage = extraction_accounting([row])
        if not usage['usage_complete']: raise ValueError('missing or inconsistent raw native usage')
        if usage['local_attempt_count_unknown'] or usage['observed_native_requests'] > plan['belief_request_upper_bound'] + 4:
            raise ValueError('holder native HTTP upper bound exceeded/unknown')
    usage = extraction_accounting(extraction)
    if usage['observed_native_requests'] > scope_plan['extraction_request_upper_bound']:
        raise ValueError('scope native HTTP upper bound exceeded')
    return dict(holders=len(holders), **usage)


def database_proof(database, scope_plan, extraction=None):
    """Audit partial or complete stable snapshots without requiring complete vectors."""
    database = Path(database)
    if not database.is_file() or any(Path(str(database)+s).exists() for s in ('-wal', '-shm')):
        raise ValueError('database snapshot missing or live')
    with closing(sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro&immutable=1', uri=True)) as db:
        if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]: raise ValueError('database integrity failure')
        sources = db.execute('SELECT d.holder_id,d.engram_ref,e.payload_inline FROM source_documents d JOIN engrams e '
            'ON e.id=d.engram_ref AND e.tenant_id=d.tenant_id WHERE d.tenant_id=?', ('default',)).fetchall()
        claims = db.execute('SELECT holder_id,semantic_claim_json FROM statements WHERE tenant_id=?', ('default',)).fetchall()
        vectors = db.execute('SELECT COUNT(*) FROM statement_vectors').fetchone()[0]
        db.row_factory = sqlite3.Row
        statements = {r['id']: dict(r) for r in db.execute('SELECT * FROM statements WHERE tenant_id=?', ('default',))}
        engrams = {r['id']: dict(r) for r in db.execute('SELECT * FROM engrams WHERE tenant_id=?', ('default',))}
    import hashlib
    refs = {}
    for holder, ref, payload in sources:
        if isinstance(payload, str): payload = payload.encode('utf-8')
        if holder not in scope_plan['holders'] or hashlib.sha256(payload).hexdigest() != scope_plan['holders'][holder]['source_payload_hash']:
            raise ValueError('database native source payload/SourceTurn identity mismatch')
        if holder in refs: raise ValueError('duplicate source holder')
        refs[holder] = ref
    for holder, raw in claims:
        if not raw: continue  # Other native channels can persist legacy statements.
        claim = json.loads(raw); plan = scope_plan['holders'].get(holder)
        if plan is None: raise ValueError('statement holder outside fixed source scope')
        unit = next((u for u in plan['source_units'] if u['clause_id'] == claim.get('clause_id')), None)
        if unit is None: raise ValueError('claim source clause outside native plan')
        expected = dict(engram_ref=refs[holder], span_start=unit['byte_start'], span_end=unit['byte_end'], source_hash=unit['payload_hash'])
        if claim.get('source_span') != expected: raise ValueError('persisted claim source span/hash mismatch')
        turn = {k: unit[k] for k in ('speaker', 'session_id', 'turn_id', 'turn_index', 'observed_at',
                                     'raw_observed_at', 'time_status') if k in unit}
        if 'speaker' in unit and claim.get('source_turn') != turn:
            raise ValueError('persisted claim SourceTurn mismatch')
    if extraction is not None:
        retained = {}
        for row in extraction:
            ids = row.get('statement_ids')
            if not isinstance(ids, list) or any(sid not in statements or statements[sid]['holder_id'] != row['holder'] for sid in ids):
                raise ValueError('native commit statement IDs absent or assigned to another holder')
            if (row['receipt']['channels']['belief'].get('claim_batches_complete') is not True
                and any(statements[sid].get('semantic_claim_json') for sid in ids)):
                raise ValueError('incomplete belief batches persisted semantic claims')
            if row.get('engram_ref') and row['engram_ref'] != refs.get(row['holder']):
                raise ValueError('native commit source engram mismatch')
            retained[row['holder']] = [candidate for attempt in row['receipt']['channels']['belief']['attempts']
                if attempt.get('terminal') is True for candidate in attempt.get('retained', [])]
        for statement in statements.values():
            if not statement.get('semantic_claim_json'): continue
            claim = json.loads(statement['semantic_claim_json']); holder = statement['holder_id']
            candidates = retained.get(holder, [])
            matched = False
            for candidate in candidates:
                evidence = json.loads(json.dumps(candidate['evidence']))
                evidence['source_span']['engram_ref'] = refs[holder]
                evidence['source_time'] = engrams[refs[holder]]['created_at']
                fields = dict(holder_perspective=str(candidate['holder_perspective']).lower(),
                    subject_kind=candidate['subject_kind'], subject_id=candidate['subject'], predicate=candidate['predicate'],
                    object_value=candidate['object'], modality=str(candidate['modality']).lower(),
                    polarity=str(candidate['polarity']).lower(), nesting_depth=candidate['nesting_depth'])
                if claim == evidence and all(statement.get(k) == v for k, v in fields.items()): matched = True; break
            if not matched: raise ValueError('persisted semantic statement differs from native retained receipt')
    return dict(statements=len(claims), vectors=vectors, source_documents=len(sources), source_engrams=refs,
                database_sha256=sha(database))


def validate_scope_health(group, database, metadata, scope_plan):
    batch = validate_batch_receipts(metadata['extraction'], scope_plan)
    health = previous.validate_scope_health(group, database, metadata)
    proof = database_proof(database, scope_plan, metadata['extraction'])
    for row in metadata['extraction']:
        if row.get('engram_ref') != proof['source_engrams'][row['holder']]:
            raise ValueError('holder commit/source engram mismatch')
    return dict(**health, batch_accounting=batch, database_proof=proof)


def ledger_rows(path):
    previous.read_ledger(path, BUILD_BUDGET)  # Reject live side files and malformed accounting first.
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro&immutable=1', uri=True)) as db:
        return [dict(zip(('id', 'scope', 'stage', 'upper_bound', 'actual', 'state'), row))
                for row in db.execute('SELECT id,scope,stage,upper_bound,actual,state FROM reservations ORDER BY id')]


def settle_failed_embedding(ledger, gid, actual):
    for row in ledger_rows(ledger.path):
        if row['scope'] == gid and row['stage'] == 'scope_embedding' and row['state'] == 'reserved':
            if type(actual) is int and 0 <= actual <= row['upper_bound']: ledger.settle(row['id'], actual)
            else: ledger.charge_upper(row['id'])


def raw_scope_extraction(scope):
    completed = scope / 'extraction.completed.json'
    if not completed.is_file(): return None
    rows = read(completed).get('extraction')
    if not isinstance(rows, list): raise ValueError('invalid extraction archive')
    archive = read(scope / 'extraction.receipts.json')
    expected = dict(schema_version=1, holders={row['holder']: row['receipt'] for row in rows})
    if archive != expected: raise ValueError('raw native receipt archive mismatch')
    return rows


def failed_snapshot(scope, scope_plan, extraction):
    database = next((scope / name for name in ('frozen.db', 'diagnostic.db') if (scope / name).is_file()), None)
    if database is None: return None
    try: return dict(file=database.name, **database_proof(database, scope_plan, extraction))
    except (ValueError, sqlite3.Error) as exc:
        return dict(file=database.name, database_sha256=sha(database), validation_error=str(exc))


def build_summary(out, groups, plans, state):
    """Recompute outcomes from raw receipts, immutable databases and every ledger row."""
    rows = ledger_rows(out / 'request-ledger.sqlite'); ledger = previous.read_ledger(out / 'request-ledger.sqlite', BUILD_BUDGET)
    if ledger['reserved'] or ledger['remaining'] < 0: raise ValueError('build ledger unfinished/over budget')
    expected_ids = [g['group_id'] for g in groups]
    present = {p.name for p in (out / 'runs').iterdir()} if (out / 'runs').exists() else set()
    ordered = [gid for gid in expected_ids if gid in present]
    if set(ordered) != present or ordered != expected_ids[:len(ordered)]: raise ValueError('nonserial/unknown scope inventory')
    health = {}; usage = {}; failures = {}; embedding = 0; extraction_charge = 0; consumed_rows = []
    build_failure = read(out / 'build.failure.json') if (out / 'build.failure.json').exists() else None
    for index, group in enumerate(groups[:len(ordered)]):
        gid = group['group_id']; scope = out / 'runs' / gid; scope_plan = plans['scopes'][gid]
        started = read(scope / 'scope.started.json')
        if started.get('group') != gid: raise ValueError('scope start identity mismatch')
        extraction = raw_scope_extraction(scope)
        failure_path = scope / 'scope.failure.json'
        failed = failure_path.is_file()
        failure = read(failure_path) if failed else None
        accounting = extraction_accounting(extraction, native_invoked=failure['native_entry_invoked'] if failed else True)
        if accounting != read(scope / 'usage-and-http.json'): raise ValueError('raw extraction usage accounting mismatch')
        usage[gid] = accounting
        metadata_path = scope / 'scope.json'
        metadata = read(metadata_path) if metadata_path.is_file() else None
        if metadata is not None and (metadata.get('group') != gid or metadata.get('extraction') != extraction):
            raise ValueError('scope metadata/raw extraction mismatch')
        if failed:
            if state != 'incomplete' or index != len(ordered)-1: raise ValueError('scope executed after failure')
            failures[gid] = failure
            if failures[gid].get('group') != gid: raise ValueError('failed scope identity mismatch')
            invoked = failures[gid].get('native_entry_invoked')
            if type(invoked) is not bool: raise ValueError('missing native invocation evidence')
            actual_embedding = failures[gid].get('embedding_request_count')
            database = scope / ('frozen.db' if (scope / 'frozen.db').is_file() else 'diagnostic.db')
            if database.is_file() and any(Path(str(database)+s).exists() for s in ('-wal', '-shm')):
                raise ValueError('failed database snapshot has live side files')
            if failures[gid].get('database_snapshot') != failed_snapshot(scope, scope_plan, extraction):
                raise ValueError('failed database snapshot proof mismatch')
        else:
            if metadata is None: raise ValueError('successful scope missing metadata')
            invoked = True; actual_embedding = metadata['embedding_request_count']
            health[gid] = validate_scope_health(group, scope / 'frozen.db', metadata, scope_plan)
            if read(scope / 'health.json') != health[gid]: raise ValueError('scope health summary mismatch')
        reservations = [row for row in rows if row['scope'] == gid]
        extraction_rows = [row for row in reservations if row['stage'] == 'scope_extraction']
        embedding_rows = [row for row in reservations if row['stage'] == 'scope_embedding']
        if len(extraction_rows) != 1 or len(embedding_rows) > 1 or len(reservations) != 1+len(embedding_rows):
            raise ValueError('scope reservation inventory mismatch')
        er = extraction_rows[0]
        if (er['upper_bound'] != scope_plan['extraction_request_upper_bound']
            or er['state'] != ('charged_upper' if invoked else 'settled')
            or (not invoked and er['actual'] != 0)
            or started.get('reservation') != dict(id=er['id'], state='reserved', upper_bound=er['upper_bound'])):
            raise ValueError('scope extraction reservation/charge mismatch')
        extraction_charge += er['upper_bound'] if invoked else 0
        if not failed and len(embedding_rows) != 1: raise ValueError('successful scope lacks embedding reservation')
        if embedding_rows:
            er = embedding_rows[0]
            if type(actual_embedding) is int and 0 <= actual_embedding <= er['upper_bound']:
                if er['state'] != 'settled' or er['actual'] != actual_embedding: raise ValueError('native embedding settlement mismatch')
                embedding += actual_embedding
            elif not failed or er['state'] != 'charged_upper': raise ValueError('unknown embedding count not conservatively charged')
            if not failed and er['upper_bound'] != baseline._embedding_reservation(metadata['database']['statements']):
                raise ValueError('embedding reservation differs from helper bound')
        consumed_rows.extend(reservations)
    if consumed_rows != rows: raise ValueError('ledger scope/order inventory mismatch')
    if state == 'complete' and (len(health) != 8 or extraction_charge != 851): raise ValueError('incomplete expanded build')
    if build_failure is not None:
        if (state != 'incomplete' or failures or len(ordered) >= len(groups)
            or build_failure != dict(category='budget_blocked', group=expected_ids[len(ordered)],
                upper_bound=plans['scopes'][expected_ids[len(ordered)]]['extraction_request_upper_bound'], remaining=ledger['remaining'])
            or ledger['remaining'] >= build_failure['upper_bound']):
            raise ValueError('invalid budget blocked terminal')
    if state == 'incomplete' and not failures and not build_failure: raise ValueError('failed build lacks a terminal failure')
    complete_usage = all(u['usage_complete'] for u in usage.values())
    return dict(stage='build', state=state, healthy_scopes=len(health), health=health, failures=failures,
        completed_scopes=list(health), unexecuted_scopes=expected_ids[len(ordered):], unexecuted_stages=['retrieve', 'qa'],
        build_failure=build_failure,
        database_sha256={gid: h['database_sha256'] for gid, h in health.items()}, ledger=ledger,
        extraction_conservative_charge=extraction_charge,
        extraction_observed_requests=sum(u['observed_native_requests'] for u in usage.values()),
        extraction_observed_tokens=sum(u['known_tokens'] for u in usage.values()) if complete_usage else None,
        extraction_known_tokens=sum(u['known_tokens'] for u in usage.values()), usage_complete=complete_usage,
        missing_token_usage=sum(u['missing_token_usage'] for u in usage.values()),
        local_attempt_count_unknown=any(u['local_attempt_count_unknown'] for u in usage.values()),
        remote_execution_unknown=any(u['remote_execution_unknown'] for u in usage.values()), embedding_requests=embedding)


def fail_stage(out, stage, exc, ledger=None):
    if out.exists() and not (out / 'seal.json').exists():
        write(out / 'failure-summary.json', dict(stage=stage, state='incomplete',
            error=f'{type(exc).__name__}: {exc}', ledger=ledger.snapshot() if ledger else None,
            unexecuted_stages=['retrieve', 'qa'], retry='refuse overwrite; diagnose before a separate explicitly planned run'))
        (out / 'exception.txt').write_text(traceback.format_exc())
        seal_output(out, stage, 'incomplete')


def build(prepared, out):
    out = new_output(out); prepared = Path(prepared).resolve(); checked = check(prepared, 'prepare')
    config, identity, groups, plans = (checked[k] for k in ('config', 'identity', 'groups', 'plans'))
    ledger = None
    try:
        out.mkdir(parents=True)
        for directory in ('frozen', 'source', 'evidence'):
            if (prepared / directory).exists(): shutil.copytree(prepared / directory, out / directory, ignore=shutil.ignore_patterns('__pycache__'))
        for name in (*INPUT_FILES, 'config.json', 'identity.json'): copy_file(prepared / name, out / name)
        copy_file(prepared / 'seal.json', out / 'input-seal.json')
        write(out / 'stage.json', dict(stage='build', input=str(prepared), input_stage='prepare', input_seal_sha256=checked['seal_sha256']))
        runner, modules = frozen_modules(prepared, config, identity)
        ledger = runner.BudgetLedger(out / 'request-ledger.sqlite', BUILD_BUDGET)
        write(out / 'execution-plan.json', dict(stage='build', workers=1, build_budget=BUILD_BUDGET,
            groups=[g['group_id'] for g in groups], core_sha256=CORE_SHA256, loaded_core=str(modules[0].__file__),
            extraction_conservative_bound=plans['extraction_request_upper_bound'],
            scope_upper_bounds={gid: p['extraction_request_upper_bound'] for gid, p in plans['scopes'].items()}))
        state = 'complete'
        for index, group in enumerate(groups):
            gid = group['group_id']; scope = out / 'runs' / gid
            bound = plans['scopes'][gid]['extraction_request_upper_bound']
            reservation = ledger.reserve(gid, 'scope_extraction', bound)
            if reservation['state'] != 'reserved':
                state = 'incomplete'
                write(out / 'build.failure.json', dict(category='budget_blocked', group=gid,
                    upper_bound=bound, remaining=reservation['remaining']))
                break
            scope.mkdir(parents=True)
            write(scope / 'scope.started.json', dict(group=gid, reservation=reservation))
            adapters = None; invoked = False
            try:
                adapters = runner._make_native_adapters(modules[0], config)
                with tempfile.TemporaryDirectory(prefix='r56-expanded-build-') as temporary:
                    scratch = Path(temporary)
                    try:
                        invoked = True
                        _, metadata = runner._build_scope_database(group, scratch, modules, config, adapters, ledger, reservation)
                        previous.archive_scope_outputs(scratch, scope, complete=True)
                    except BaseException as exc:
                        previous.archive_scope_outputs(scratch, scope, complete=False)
                        traceback.clear_frames(exc.__traceback__)
                        raise
                    finally: gc.collect()
                write(scope / 'scope.json', dict(group=gid, **metadata))
                health = validate_scope_health(group, scope / 'frozen.db', metadata, plans['scopes'][gid])
                write(scope / 'health.json', health)
            except BaseException as exc:
                state = 'incomplete'
                if invoked: ledger.charge_upper(reservation['id'])
                else: ledger.settle(reservation['id'], 0)
                actual_embedding = getattr(adapters[1], 'request_count', None) if adapters else 0
                settle_failed_embedding(ledger, gid, actual_embedding)
                write(scope / 'scope.failure.json', dict(group=gid, error=f'{type(exc).__name__}: {exc}',
                    native_entry_invoked=invoked, embedding_request_count=actual_embedding,
                    database_snapshot=failed_snapshot(scope, plans['scopes'][gid], raw_scope_extraction(scope))))
                (scope / 'exception.txt').write_text(traceback.format_exc())
            write(scope / 'usage-and-http.json', extraction_accounting(raw_scope_extraction(scope), native_invoked=invoked))
            print(f'build scopes: {index+1}/8; {gid}; state={state}', flush=True)
            if state != 'complete': break
        validate_identity(out); validate_identity(prepared); validate_loaded(prepared, identity)
        verify_seal(prepared)
        if sha(prepared / 'seal.json') != checked['seal_sha256']: raise ValueError('prepare changed during build')
        summary = build_summary(out, groups, plans, state); write(out / 'summary.json', summary)
        seal_output(out, 'build', state)
        return summary
    except BaseException as exc:
        fail_stage(out, 'build', exc, ledger)
        raise


def check(out, expected_stage=None):
    out = Path(out).resolve(); seal = verify_seal(out, allow_incomplete=True); stage = read(out / 'stage.json')
    if stage.get('stage') != seal['stage'] or stage['stage'] not in ('prepare', 'build'):
        raise ValueError('unsupported or mismatched stage')
    if expected_stage and (stage['stage'] != expected_stage or seal['state'] != 'complete'):
        raise ValueError('incorrect or incomplete input stage')
    config, identity, parents = validate_identity(out)
    plans = read(out / 'batch-plans.json'); validate_plan_counts(plans)
    if stage['stage'] == 'prepare':
        if stage != dict(stage='prepare', input=None, external_requests=0) or seal['state'] != 'complete':
            raise ValueError('prepare must be complete and offline')
        runner, modules = frozen_modules(out, config, identity)
        actual = native_plans(runner, modules, parents['groups'], config)
        if plans != actual: raise ValueError('native batch plan drift')
        summary = prepared_summary(parents['manifest'], actual)
        validate_loaded(out, identity)
    else:
        source = Path(stage['input']).resolve()
        if source == out or stage.get('input_stage') != 'prepare': raise ValueError('invalid build input chain')
        parent = check(source, 'prepare')
        if (parent['identity'] != identity or stage.get('input_seal_sha256') != parent['seal_sha256']
            or sha(out / 'input-seal.json') != parent['seal_sha256']): raise ValueError('build input identity/seal mismatch')
        plan = read(out / 'execution-plan.json')
        expected = dict(stage='build', workers=1, build_budget=BUILD_BUDGET,
            groups=[g['group_id'] for g in parents['groups']], core_sha256=CORE_SHA256,
            loaded_core=str(next((source / 'frozen/python/starling').glob('_core*.so'))),
            extraction_conservative_bound=plans['extraction_request_upper_bound'],
            scope_upper_bounds={gid: p['extraction_request_upper_bound'] for gid, p in plans['scopes'].items()})
        if plan != expected: raise ValueError('execution plan drift')
        summary = build_summary(out, parents['groups'], plans, seal['state'])
    if not identical(summary, read(out / 'summary.json')): raise ValueError('recomputed terminal summary/accounting mismatch')
    verify_seal(out, allow_incomplete=True)
    return dict(stage=stage['stage'], config=config, identity=identity, groups=parents['groups'], records=parents['records'],
                plans=plans, summary=summary, seal_sha256=sha(out / 'seal.json'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__); stages = parser.add_subparsers(dest='stage', required=True)
    p = stages.add_parser('prepare'); p.add_argument('--parent', type=Path, default=DEFAULT_PARENT)
    p.add_argument('--probe', type=Path, default=DEFAULT_PROBE); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--evidence', type=Path, action='append', default=[])
    p = stages.add_parser('build'); p.add_argument('--input', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p = stages.add_parser('check'); p.add_argument('--input', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.stage == 'prepare': result = prepare(args.parent, args.out, args.probe, args.evidence)
    elif args.stage == 'build': result = build(args.input, args.out)
    else: result = check(args.input)['summary']
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return int(result['state'] != 'complete')


if __name__ == '__main__': raise SystemExit(main())
