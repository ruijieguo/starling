#!/usr/bin/env python3
"""R5.9 fixed target-unit eight-scope rebuild; offline prepare/check, no resume."""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


old = load(ROOT / 'scripts/run_socialmem_r56_expanded.py', 'r59_scope_helpers')
paired = load(ROOT / 'scripts/run_socialmem_r58_paired_probe.py', 'r59_belief_helpers')
previous, baseline = old.previous, old.baseline
read, write, sha, inventory = old.read, old.write, old.sha, old.inventory
copy_file, new_output, identical = old.copy_file, old.new_output, old.identical
CORE_SHA256 = 'ead8046e4a28d257f3429d865523c1af1f6275fd0cb1ba98d8fa8023894d6fef'
DEFAULT_PARENT = ROOT / 'build/socialmem_20260925_r55_expanded/prepare'
DEFAULT_PROBE = ROOT / 'build/socialmem_20260926_r58_paired/run'
PARENT_SEAL = '66b13d7e22b0794903467d9ea89f21b91379118d43866b4504b49fd9bd0178d0'
PROBE_SEAL = '30d00e455388d6002b692080e0e7b60b13f56d76790245f1b3f8c57971b5735d'
PROBE_PREPARE_SEAL = 'cf95c3412a32f22542f72b5b81d7d4d81b04377d4338a75891f8439dc1be73e0'
BUILD_BUDGET = 12000
PROFILE = 'target_units_v1'
DATA_FILES = old.DATA_FILES
INPUT_FILES = (*DATA_FILES, 'parent-config.json', 'parent-seal.json', 'probe-seal.json',
               'probe-prepare-seal.json', 'qualification.json', 'provenance.json', 'batch-plans.json')
OWN_FILES = ('scripts/run_socialmem_r59_expanded.py', 'tests/python/test_socialmem_r59_expanded.py')


def historical_inputs(parent):
    parent = Path(parent).resolve()
    old.verify_historical(parent, PARENT_SEAL, 'r55-seal-v1', 'prepare')
    records, groups, manifest = previous._cohort_from_files(parent)
    for name, value in [('sample.json', records), ('groups.json', groups), ('scope-manifest.json', manifest)]:
        if not identical(read(parent / name), value): raise ValueError('historical cohort mismatch')
    parent_config = read(parent / 'config.json')
    config = dict(parent_config, core_sha256=CORE_SHA256, claim_batch_size=8,
                  claim_batch_target_units=True, arm='r59_expanded_development')
    return dict(parent=parent, parent_config=parent_config, records=records, groups=groups,
                manifest=manifest, config=config)


def checker_files():
    paths = set(old.source_paths()) | {ROOT / name for name in OWN_FILES}
    paths.update(ROOT / name for name in paired.IMPLEMENTATION)
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(paths) if p.suffix == '.py'}


def qualify_probe(probe):
    probe = Path(probe).resolve()
    old.verify_historical(probe, PROBE_SEAL, 'r58-paired-seal-v1', 'run')
    prepared = Path(read(probe / 'stage.json')['input']).resolve()
    old.verify_historical(prepared, PROBE_PREPARE_SEAL, 'r58-paired-seal-v1', 'prepare')
    if read(probe / 'identity.json').get('core_sha256') != CORE_SHA256:
        raise ValueError('successful paired probe core mismatch')
    command = [sys.executable, str(ROOT / 'scripts/run_socialmem_r58_paired_probe.py'), 'check', '--input', str(probe)]
    before = checker_files()
    result = subprocess.run(command, cwd=ROOT, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                            text=True, capture_output=True)
    if result.returncode != 0: raise ValueError('independent paired qualification check failed: ' + result.stderr[-2000:])
    summary = json.loads(result.stdout)
    candidates = [t for t in summary.get('tasks', []) if t.get('arm') == 'B']
    if (summary.get('candidate_passed') is not True or summary.get('state') != 'complete'
        or len(candidates) != 3 or any(t.get('status') != 'passed' or t.get('statement_count', 0) < 1 for t in candidates)):
        raise ValueError('three healthy paired B terminals are required')
    if before != checker_files(): raise ValueError('qualification checker changed during check')
    old.verify_historical(probe, PROBE_SEAL, 'r58-paired-seal-v1', 'run')
    return dict(command=command, returncode=result.returncode, stdout=result.stdout,
                stdout_sha256=paired.text_sha(result.stdout), stderr=result.stderr,
                summary=summary, checker_files=before)


def current_source_files():
    paths = set(old.source_paths()) | {ROOT / name for name in OWN_FILES}
    paths.update(ROOT / name for name in paired.IMPLEMENTATION)
    paths.update(ROOT / name for name in ('tests/python/test_claim_batch_target_units.py',
                                        'tests/cpp/test_claim_batch_target_units.cpp'))
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(paths)}


def current_core():
    cores = list((ROOT / 'build/python/starling').glob('_core*.so'))
    if len(cores) != 1 or sha(cores[0]) != CORE_SHA256: raise ValueError('fixed candidate core mismatch')
    return cores[0]


def native_plans(runner, modules, groups, config):
    if config.get('claim_batch_target_units') is not True: raise ValueError('strict true target-unit policy required')
    plans = old.native_plans(runner, modules, groups, config)
    if any(p.get('claim_batch_prompt_profile') != PROFILE
           for scope in plans['scopes'].values() for p in scope['holders'].values()):
        raise ValueError('native target-unit profile mismatch')
    return plans


def frozen_modules(prepared, config, identity):
    runner = load(prepared / 'frozen/scripts/run_socialmem_baseline.py', 'r59_frozen_baseline')
    modules = runner._frozen_imports(prepared, config, identity)
    old.validate_loaded(prepared, identity)
    return runner, modules


def seal_output(out, stage, state='complete'):
    if (out / 'seal.json').exists(): raise ValueError('output already sealed')
    write(out / 'seal.json', dict(schema='r59-expanded-seal-v1', stage=stage, state=state, files=inventory(out)))


def verify_seal(out):
    value = read(out / 'seal.json'); files = inventory(out); files.pop('seal.json', None)
    if (value.get('schema') != 'r59-expanded-seal-v1' or value.get('state') not in ('complete', 'incomplete')
        or not files or value.get('files') != files): raise ValueError('stage seal identity/inventory mismatch')
    return value


def prepared_summary(inputs, plans):
    return dict(stage='prepare', state='complete', **inputs['manifest'], external_requests=0,
        core_sha256=CORE_SHA256, claim_batch_target_units=True, claim_batch_prompt_profile=PROFILE,
        native_source_units=plans['source_units'], native_batches=plans['batches'],
        belief_request_upper_bound=plans['belief_request_upper_bound'],
        extraction_conservative_bound=plans['extraction_request_upper_bound'], build_budget=BUILD_BUDGET,
        unexecuted_stages=['build', 'retrieve', 'qa'])


def prepare(parent, out, probe=DEFAULT_PROBE, evidence=()):
    out = new_output(out); core = current_core(); inputs = historical_inputs(parent)
    qualification = qualify_probe(probe); probe = Path(probe).resolve()
    out.mkdir(parents=True)
    stage = dict(stage='prepare', input=None, external_requests=0)
    try:
        write(out / 'stage.json', stage)
        summary = prepare_contents(out, core, inputs, qualification, probe, evidence)
    except BaseException as exc:
        record_interruption(out, stage, 'initialization', exc)
        summary = partial_prepare_summary(out)
    return finalize_stage(out, stage, summary, lambda: partial_prepare_summary(out))


def prepare_contents(out, core, inputs, qualification, probe, evidence):
    for name in DATA_FILES: copy_file(inputs['parent'] / name, out / name)
    probe_prepared = Path(read(probe / 'stage.json')['input']).resolve()
    for source, name in [(inputs['parent'] / 'config.json', 'parent-config.json'),
                         (inputs['parent'] / 'seal.json', 'parent-seal.json'),
                         (probe / 'seal.json', 'probe-seal.json'),
                         (probe_prepared / 'seal.json', 'probe-prepare-seal.json')]: copy_file(source, out / name)
    write(out / 'config.json', inputs['config']); write(out / 'qualification.json', qualification)
    write(out / 'provenance.json', dict(parent=str(inputs['parent']), parent_seal_sha256=PARENT_SEAL,
        probe=str(probe), probe_seal_sha256=PROBE_SEAL, probe_prepare_seal_sha256=PROBE_PREPARE_SEAL))
    for name in current_source_files(): copy_file(ROOT / name, out / 'source' / name)
    for path in (ROOT / 'python/starling').rglob('*.py'):
        if '__pycache__' not in path.parts: copy_file(path, out / 'frozen' / path.relative_to(ROOT))
    for name in old.RUNTIME_SCRIPTS: copy_file(ROOT / 'scripts' / name, out / 'frozen/scripts' / name)
    copy_file(core, out / 'frozen/python/starling' / core.name)
    evidence_sources = {str(Path(p).resolve()): sha(p) for p in evidence}
    for index, path in enumerate(evidence_sources): copy_file(path, out / 'evidence' / f'{index}-{Path(path).name}')
    identity = dict(schema='r59-expanded-identity-v1', core_sha256=CORE_SHA256,
        config_sha256=sha(out / 'config.json'), frozen_files=inventory(out / 'frozen'),
        source_files=inventory(out / 'source'), evidence_files=inventory(out / 'evidence'), evidence_sources=evidence_sources)
    runner, modules = frozen_modules(out, inputs['config'], identity)
    plans = native_plans(runner, modules, inputs['groups'], inputs['config']); old.validate_plan_counts(plans)
    write(out / 'batch-plans.json', plans)
    identity['inputs'] = {name: sha(out / name) for name in INPUT_FILES}; write(out / 'identity.json', identity)
    validate_prepared(out, require_current=True)
    return prepared_summary(inputs, plans)


def record_interruption(out, stage, phase, exc):
    write(out / 'interruption.json', dict(stage=stage, phase=phase, error=f'{type(exc).__name__}: {exc}'))


def partial_prepare_summary(out):
    interruption = read(out / 'interruption.json')
    if interruption['stage'] != dict(stage='prepare', input=None, external_requests=0):
        raise ValueError('partial prepare stage identity mismatch')
    files = inventory(out)
    for name in ('summary.json', 'partial-summary.json', 'seal.json'): files.pop(name, None)
    return dict(stage='prepare', state='incomplete', external_requests=0, interruption=interruption,
        partial_files=files, retrieval_ready=False, qa_ready=False, unexecuted_stages=['build', 'retrieve', 'qa'])


def finalize_stage(out, stage, summary, partial):
    try: write(out / 'summary.json', summary)
    except BaseException as exc:
        record_interruption(out, stage, 'summary_write', exc)
        summary = partial(); write(out / 'partial-summary.json', summary)
    seal_output(out, stage['stage'], summary['state'])
    return summary


def validate_prepared(out, require_current=False):
    provenance = read(out / 'provenance.json'); inputs = historical_inputs(provenance['parent'])
    qualification = qualify_probe(provenance['probe']); archived = read(out / 'qualification.json')
    if (provenance != dict(parent=str(inputs['parent']), parent_seal_sha256=PARENT_SEAL,
        probe=str(Path(provenance['probe']).resolve()), probe_seal_sha256=PROBE_SEAL,
        probe_prepare_seal_sha256=PROBE_PREPARE_SEAL)
        or archived.get('returncode') != 0 or archived.get('summary') != qualification['summary']
        or json.loads(archived['stdout']) != archived['summary']
        or paired.text_sha(archived['stdout']) != archived['stdout_sha256']):
        raise ValueError('paired qualification/provenance mismatch')
    identity, config = read(out / 'identity.json'), read(out / 'config.json')
    if (not identical(config, inputs['config']) or config.get('claim_batch_target_units') is not True
        or identity.get('schema') != 'r59-expanded-identity-v1' or identity.get('core_sha256') != CORE_SHA256
        or sha(out / 'config.json') != identity.get('config_sha256')): raise ValueError('fixed config/core identity mismatch')
    for name in DATA_FILES:
        if sha(out / name) != sha(inputs['parent'] / name): raise ValueError('fixed cohort input drift')
    if read(out / 'parent-config.json') != inputs['parent_config']: raise ValueError('historical config drift')
    for name, digest in [('parent-seal.json', PARENT_SEAL), ('probe-seal.json', PROBE_SEAL),
                         ('probe-prepare-seal.json', PROBE_PREPARE_SEAL)]:
        if sha(out / name) != digest: raise ValueError('historical seal copy mismatch')
    if identity.get('inputs') != {name: sha(out / name) for name in INPUT_FILES}: raise ValueError('input identity mismatch')
    for directory in ('source', 'frozen', 'evidence'):
        if inventory(out / directory) != identity.get(directory + '_files'): raise ValueError('frozen inventory mismatch')
    cores = list((out / 'frozen/python/starling').glob('_core*.so'))
    if len(cores) != 1 or sha(cores[0]) != CORE_SHA256: raise ValueError('frozen candidate core mismatch')
    if require_current:
        current_core()
        if identity['source_files'] != current_source_files(): raise ValueError('current source identity drift')
        for name, digest in identity['frozen_files'].items():
            path = current_core() if name.startswith('python/starling/_core') else ROOT / name
            if sha(path) != digest: raise ValueError('current runtime dependency drift')
        if any(sha(p) != digest for p, digest in identity['evidence_sources'].items()): raise ValueError('validation evidence drift')
    runner, modules = frozen_modules(out, config, identity)
    plans = native_plans(runner, modules, inputs['groups'], config); old.validate_plan_counts(plans)
    if plans != read(out / 'batch-plans.json'): raise ValueError('native target-unit plan drift')
    return dict(inputs, config=config, prepared=out, identity=identity, plans=plans, runner=runner,
                modules=modules, qualification_audit=qualification)


def check(out, expected_stage=None, require_current=False):
    out = Path(out).resolve(); sealed = verify_seal(out)
    interruption = read(out / 'interruption.json') if (out / 'interruption.json').exists() else None
    stage = read(out / 'stage.json') if (out / 'stage.json').exists() else interruption['stage']
    if interruption is not None and interruption['stage'] != stage: raise ValueError('partial stage identity mismatch')
    if stage.get('stage') != sealed['stage']: raise ValueError('stage/seal mismatch')
    if expected_stage and (stage['stage'] != expected_stage or sealed['state'] != 'complete'):
        raise ValueError('incomplete or wrong input stage')
    if stage['stage'] == 'prepare':
        if stage != dict(stage='prepare', input=None, external_requests=0): raise ValueError('prepare stage identity mismatch')
        if interruption:
            checked = {}; summary = partial_prepare_summary(out)
        else:
            checked = validate_prepared(out, require_current)
            summary = prepared_summary(checked, checked['plans'])
    elif stage['stage'] == 'build':
        prepared = Path(stage['input']).resolve()
        if prepared == out: raise ValueError('cyclic build input')
        checked = check(prepared, 'prepare', require_current)
        if stage != dict(stage='build', input=str(prepared), input_seal_sha256=checked['seal_sha256']):
            raise ValueError('prepare seal binding mismatch')
        for name in (*INPUT_FILES, 'config.json', 'identity.json', 'prepare-seal.json'):
            if interruption and not (out / name).exists(): continue
            if name == 'prepare-seal.json':
                if sha(out / name) != checked['seal_sha256']: raise ValueError('prepare seal copy mismatch')
                continue
            if sha(out / name) != sha(prepared / name): raise ValueError('build fixed input copy mismatch')
        if not interruption or (out / 'execution-plan.json').exists():
            if read(out / 'execution-plan.json') != execution_plan(checked): raise ValueError('build execution plan mismatch')
        summary = partial_build_summary(out, checked) if interruption else build_summary(out, checked)
    else: raise ValueError('unsupported stage')
    summary_file = out / ('partial-summary.json' if (out / 'partial-summary.json').exists() else 'summary.json')
    if not identical(summary, read(summary_file)) or sealed['state'] != summary['state']:
        raise ValueError('recomputed stage summary mismatch')
    verify_seal(out)
    return dict(checked, stage=stage['stage'], summary=summary, seal_sha256=sha(out / 'seal.json'),
                audit_program_files=checker_files())


def make_adapters(checked):
    return checked['runner']._make_native_adapters(checked['modules'][0], checked['config'])


def scope_worker(checked, group, scratch, adapters, ledger, reservation):
    return checked['runner']._build_scope_database(group, scratch, checked['modules'], checked['config'],
                                                   adapters, ledger, reservation)


def archive_scope(scratch, scope, complete):
    previous.archive_scope_outputs(scratch, scope, complete=complete)


def complete_structured_copy(response, native_fields):
    nested = response.get('structured_output') if isinstance(response, dict) else None
    return (isinstance(nested, dict) and set(nested) == set(native_fields)
            and all(type(response.get(key)) is type(example) and type(nested[key]) is type(example)
                    and identical(response[key], nested[key]) for key, example in native_fields.items()))


def extraction_accounting(rows, invoked, core):
    if type(invoked) is not bool or not invoked and rows is not None: raise ValueError('native invocation/receipt mismatch')
    unknown = invoked and (not isinstance(rows, list) or not rows)
    report = dict(observed_native_requests=0, observed_tokens=None, known_tokens=0, missing_token_usage=0,
        response_observations=0, usage_complete=not unknown, local_attempt_count_unknown=unknown,
        remote_execution_unknown_attempts=0, remote_execution_unknown=unknown, healthy_http=not unknown)
    responses = []
    native_fields = json.loads(core.llm_response_evidence_json(core.LLMResponse('', False, '')))
    for row in rows or []:
        channels = row.get('receipt', {}).get('channels', {})
        for name in ('belief', 'general_fact'):
            attempts = channels.get(name, {}).get('attempts')
            if not isinstance(attempts, list) or not attempts:
                report['local_attempt_count_unknown'] = True; continue
            for attempt in attempts:
                responses.append(attempt.get('extraction'))
                if name == 'belief':
                    report['healthy_http'] &= complete_structured_copy(attempt.get('extraction'), native_fields)
                admission = attempt.get('admission')
                if not isinstance(admission, dict) or type(admission.get('called')) is not bool:
                    report['local_attempt_count_unknown'] = True
                if isinstance(admission, dict) and (admission.get('called') is True or admission.get('http_attempts') or admission.get('attempt_count')):
                    responses.append(admission)
                    if name == 'belief': report['healthy_http'] &= complete_structured_copy(admission, native_fields)
                    if admission.get('called') is not True: report['local_attempt_count_unknown'] = True
        responses.append(channels.get('episodic', {}).get('response'))
        cost = paired.raw_cost(channels.get('belief'), True,
                              {k: v['sha256'] for k, v in paired.schema_identity(core).items()})
        report['healthy_http'] &= cost['healthy_http']
    for response in responses:
        report['response_observations'] += 1
        if not isinstance(response, dict):
            report['local_attempt_count_unknown'] = True; report['missing_token_usage'] += 1; continue
        http = response.get('http_attempts'); count = response.get('attempt_count')
        if not isinstance(http, list): http = []; report['local_attempt_count_unknown'] = True
        if type(count) is not int or count != len(http) or not http: report['local_attempt_count_unknown'] = True
        report['observed_native_requests'] += len(http)
        healthy = (count == 1 and len(http) == 1 and response.get('ok') is True and response.get('error') == ''
                   and response.get('finish_reason') == 'stop' and response.get('refusal') is False)
        if not http: report['missing_token_usage'] += 1
        for raw in http:
            if not isinstance(raw, dict): raw = {}
            remote_unknown = raw.get('execution_certainty') not in ('not_connected', 'response_received')
            report['remote_execution_unknown_attempts'] += int(remote_unknown)
            healthy &= (raw.get('http_status') == 200 and raw.get('curl_code') == 0
                        and raw.get('execution_certainty') == 'response_received')
            try: body = json.loads(raw['response_body'])
            except (ValueError, KeyError, TypeError): body = {}
            try:
                choice = body['choices'][0]; message = choice['message']
                healthy &= (choice['finish_reason'] == 'stop' and not message.get('refusal')
                            and message['content'] == response.get('raw_completion')
                            and raw['response_body'] == response.get('raw_http_response'))
            except (ValueError, KeyError, TypeError, IndexError, AttributeError): healthy = False
            try:
                usage = body['usage']; values = [usage[k] for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')]
                if not all(type(v) is int and v >= 0 for v in values) or values[0] + values[1] != values[2] or values[2] <= 0:
                    raise ValueError('invalid raw usage')
                # Known raw cost remains known even when a duplicate native field contradicts it.
                report['known_tokens'] += values[2]
                if any(response.get(k) != usage[k] for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')):
                    raise ValueError('native/raw usage mismatch')
            except (ValueError, KeyError, TypeError): report['missing_token_usage'] += 1; healthy = False
        report['healthy_http'] &= bool(healthy)
    report['usage_complete'] &= not report['local_attempt_count_unknown'] and not report['missing_token_usage']
    report['healthy_http'] &= not report['local_attempt_count_unknown']
    report['remote_execution_unknown'] |= bool(report['local_attempt_count_unknown'] or report['remote_execution_unknown_attempts'])
    if report['usage_complete']: report['observed_tokens'] = report['known_tokens']
    return report


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def parse_utc(value):
    if not isinstance(value, str) or not value.endswith('Z'): raise ValueError('missing or invalid UTC clock evidence')
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def clock_bounds(window):
    start, end = parse_utc(window.get('start')), parse_utc(window.get('end'))
    if start > end: raise ValueError('native invocation clock window reversed')
    # Native timestamps have second precision; the captured bounds preserve microseconds.
    return start.replace(microsecond=0), end


def stable_rows(database, source_ref, statement_ref, legacy_sources, window):
    """Compare all native rows, binding generated references and justified legacy clocks."""
    start, end = clock_bounds(window)
    with paired.immutable(database) as db:
        db.row_factory = sqlite3.Row
        rows = [dict(r) for r in db.execute('SELECT * FROM statements')]
    references = {**source_ref, **statement_ref}; logical = {}; visiting = set()
    for row in rows:
        value = {key: json.loads(row[key]) if key.endswith('_json') and row[key] is not None else row[key]
                 for key in row if key not in DYNAMIC_STATEMENT_FIELDS}
        if row['id'] in legacy_sources:
            spans = value['source_spans_json']; observed = value['observed_at']
            if (value['semantic_claim_json'] is not None or not spans or not start <= parse_utc(observed) <= end
                or any(span.get('engram_ref') not in legacy_sources[row['id']] or span.get('observed_at') != observed
                       for span in spans)):
                raise ValueError('native legacy default clock/source span outside invocation window or inconsistent')
            value['observed_at'] = '<validated legacy default clock>'
            for span in spans: span['observed_at'] = '<validated legacy default clock>'
        logical[row['id']] = value
    if not set(statement_ref) <= set(logical) or not set(legacy_sources) <= set(statement_ref):
        raise ValueError('commit/database statement inventory mismatch')
    def normalize(value):
        if isinstance(value, dict): return {k: normalize(v) for k, v in value.items()}
        if isinstance(value, list): return [normalize(v) for v in value]
        if not isinstance(value, str): return value
        if value in references: return references[value]
        if value in logical:
            if value in visiting: raise ValueError('cyclic unbound native statement reference')
            visiting.add(value)
            references[value] = '<bound derived statement ' + paired.text_sha(json.dumps(normalized_row(value), sort_keys=True)) + '>'
            visiting.remove(value)
            return references[value]
        return value
    def normalized_row(sid):
        value = normalize(logical[sid])
        for key in ('derived_from_json', 'evidence_json', 'source_spans_json'):
            if isinstance(value[key], list): value[key] = sorted(value[key], key=lambda v: json.dumps(v, sort_keys=True))
        return value
    result = [dict(normalized_row(sid), id=normalize(sid)) for sid in logical]
    return sorted(result, key=lambda r: json.dumps(r, sort_keys=True))


DYNAMIC_STATEMENT_FIELDS = ('id', 'created_at', 'updated_at', 'last_accessed', 'last_replay_batch_id')


def semantic_bundle(receipt):
    value = json.loads(json.dumps(receipt))
    for name in ('belief', 'general_fact'):
        value['channels'][name] = paired.semantic_receipt(value['channels'][name])
    response = value['channels']['episodic'].get('response', {})
    for key in paired.RESPONSE_VOLATILE: response.pop(key, None)
    return value


def native_replay(checked, database, rows, scope_plan, group, window):
    clock_bounds(window)
    core, runtime = checked['modules'][:2]
    with tempfile.TemporaryDirectory(prefix='r59-scope-replay-') as temp:
        path = Path(temp) / 'replay.db'; rt = runtime._build_local_store_sqlite_runtime(path); rt.start()
        try:
            checked['runner'].retain_history_sources(core, rt.adapter, group['history'],
                checked['config']['created_at'], preserve_invalid_time=True)
            # Match remember_holders: shared retained sources, then each holder's
            # prepare -> extract_all -> commit_all with a separate Fake response mapping.
            return replay_holders(checked, database, rows, scope_plan, group, rt, path, window)
        finally:
            stop = getattr(rt, 'stop', None)
            if callable(stop): stop()


def replay_holders(checked, database, rows, scope_plan, group, rt, path, window):
    core, runtime = checked['modules'][:2]; runner = checked['runner']; config = checked['config']
    cfg = runner._build_extraction_config(config); policy = cfg.to_native_policy()
    with paired.immutable(database) as db:
        sources = {h: (ref, payload, created) for h, ref, payload, created in db.execute(
            'SELECT d.holder_id,e.id,e.payload_inline,e.created_at FROM source_documents d JOIN engrams e '
            'ON e.id=d.engram_ref AND e.tenant_id=d.tenant_id WHERE d.tenant_id=?', ('default',))}
    if set(sources) != set(scope_plan['holders']): raise ValueError('native replay source inventory mismatch')
    if [r['holder'] for r in rows] != runner.history_holders(group['history']):
        raise ValueError('native replay holder inventory/order mismatch')
    actual_statement_refs = {}; replay_statement_refs = {}; actual_legacy = {}; replay_legacy = {}
    replay_window = dict(start=utc_now())
    for row in rows:
        holder = row['holder']; ref, payload, created = sources[holder]
        if created != config['created_at'] or row.get('engram_ref') != ref:
            raise ValueError('source creation time/native commit identity mismatch')
        if isinstance(payload, str): payload = payload.encode()
        receipt = row['receipt']; belief = receipt['channels']['belief']; plan = scope_plan['holders'][holder]
        if (belief.get('claim_batch_plan') != plan or belief.get('claim_batch_prompt_profile') != PROFILE
            or belief.get('source_payload_hash') != sha_bytes(payload) or belief.get('holder') != holder):
            raise ValueError('belief native plan/profile/payload identity mismatch')
        fake = core.FakeLLMAdapter(); mapping = {}
        responses = []
        for name in ('belief', 'general_fact'):
            for attempt in receipt['channels'][name].get('attempts', []):
                responses.append(attempt['extraction'])
                if attempt.get('admission', {}).get('called') is True: responses.append(attempt['admission'])
        episodic = receipt['channels']['episodic']
        responses.append(dict(episodic['response'], prompt=episodic['prompt'], prompt_input_hash=episodic['prompt_input_hash']))
        for response in responses:
            digest = response['prompt_input_hash']
            if core.Extractor.compute_prompt_input_hash(response['prompt']) != digest: raise ValueError('native prompt/hash mismatch')
            stable = {k: response.get(k) for k in ('raw_response', 'ok', 'error', 'finish_reason', 'refusal', 'raw_completion', 'capability_evidence_id')}
            if digest in mapping and mapping[digest] != stable: raise ValueError('conflicting native response mapping')
            mapping[digest] = stable
            value = core.LLMResponse(response['raw_response'], response['ok'], response['error'])
            for key in ('finish_reason', 'refusal', 'raw_completion', 'capability_evidence_id'):
                setattr(value, key, response.get(key, False if key == 'refusal' else ''))
            fake.set_response_object(digest, value)
        prepared = core.memory_remember_prepare(rt.adapter, tenant_id='default', holder_id=holder,
            interlocutor='', adapter_name='source_turns', source_prefix=f'source-{holder}-',
            created_at_iso8601=created, payload=payload)
        bundle = core.memory_remember_extract_all(rt.adapter, fake, cfg.belief_prompt, cfg.episodic_prompt,
            cfg.general_fact_prompt, holder, payload, policy=policy)
        commit = core.memory_remember_commit_all(rt.adapter, fake, tenant_id='default', holder_id=holder,
            interlocutor='', prepared=prepared, extracted=bundle, policy=policy)
        actual = json.loads(core.memory_remember_bundle_receipt(bundle))
        if semantic_bundle(actual) != semantic_bundle(receipt): raise ValueError('native per-holder receipt replay mismatch')
        expected_commit = {k: v for k, v in row.items() if k not in ('holder', 'receipt', 'engram_ref', 'statement_ids')}
        actual_commit = {k: v for k, v in commit.items() if k not in ('engram_ref', 'statement_ids')}
        if actual_commit != expected_commit:
            difference = {k: [expected_commit.get(k), actual_commit.get(k)] for k in set(expected_commit) | set(actual_commit)
                          if expected_commit.get(k) != actual_commit.get(k)}
            raise ValueError('native per-holder commit replay mismatch: ' + json.dumps(difference, sort_keys=True))
        actual_ids, replay_ids = row.get('statement_ids'), commit.get('statement_ids')
        if not isinstance(actual_ids, list) or len(actual_ids) != len(replay_ids):
            raise ValueError('native commit statement ID multiplicity mismatch')
        for actual_id, replay_id in zip(actual_ids, replay_ids):
            if not isinstance(actual_id, str) or not actual_id: raise ValueError('invalid native commit statement ID')
            if actual_id in actual_statement_refs or replay_id in replay_statement_refs:
                if actual_statement_refs.get(actual_id) != replay_statement_refs.get(replay_id):
                    raise ValueError('native commit statement ID correspondence mismatch')
            else:
                marker = '<bound commit statement ' + str(len(actual_statement_refs)) + '>'
                actual_statement_refs[actual_id] = replay_statement_refs[replay_id] = marker
        retained = [candidate for attempt in actual['channels']['general_fact']['attempts']
                    for candidate in attempt.get('retained') or []]
        with closing(sqlite3.connect(path)) as db:
            db.row_factory = sqlite3.Row
            persisted = {r['id']: dict(r) for r in db.execute('SELECT * FROM statements')}
        for actual_id, replay_id in zip(actual_ids, replay_ids):
            value = persisted[replay_id]
            spans = json.loads(value['source_spans_json'])
            # The native legacy writer sets source_hash = "chunk-" + chunk_index;
            # episodic persistence uses "episodic-" + seq even for matching tuples.
            # Bind exact native source coordinates before granting clock eligibility.
            legacy_source = bool(spans) and all(
                span.get('engram_ref') == commit['engram_ref'] and type(span.get('chunk_index')) is int
                and span['chunk_index'] >= 0 and span.get('source_hash') == 'chunk-' + str(span['chunk_index'])
                for span in spans)
            if value['semantic_claim_json'] is None and legacy_source and any(
                candidate.get('predicate') == value['predicate'] and candidate.get('object') == value['object_value']
                and candidate.get('modality', '').lower() == value['modality']
                and candidate.get('polarity', '').lower() == value['polarity'] for candidate in retained):
                actual_legacy.setdefault(actual_id, set()).add(ref)
                replay_legacy.setdefault(replay_id, set()).add(commit['engram_ref'])
    replay_window['end'] = utc_now()
    checked['runner'].apply_lifecycle(core, rt.adapter, config)
    snapshot = path.parent / 'frozen.db'
    with closing(sqlite3.connect(path)) as source, closing(sqlite3.connect(snapshot)) as target: source.backup(target)
    actual_refs = {ref: '<bound source ' + holder + '>' for holder, (ref, _, _) in sources.items()}
    with paired.immutable(snapshot) as db:
        replay_refs = {ref: '<bound source ' + holder + '>' for holder, ref in db.execute(
            'SELECT holder_id,engram_ref FROM source_documents WHERE tenant_id=?', ('default',))}
    # Native lifecycle may create common-ground or other derived rows outside
    # source holders. Only the complete native replay can justify such rows.
    actual_rows = stable_rows(database, actual_refs, actual_statement_refs, actual_legacy, window)
    replayed_rows = stable_rows(snapshot, replay_refs, replay_statement_refs, replay_legacy, replay_window)
    if actual_rows != replayed_rows:
        differences = [{key: [left.get(key), right.get(key)] for key in set(left) | set(right)
                        if left.get(key) != right.get(key)} for left, right in zip(actual_rows, replayed_rows)]
        raise ValueError('actual persisted logical rows differ from native replay: ' + json.dumps(
            dict(counts=[len(actual_rows), len(replayed_rows)], differences=[v for v in differences if v]), sort_keys=True))
    return dict(verified=True, holders=len(rows), channels=['belief', 'general_fact', 'episodic'],
                excluded_statement_fields=list(DYNAMIC_STATEMENT_FIELDS),
                legacy_default_clock=dict(validated_rows=len(actual_legacy), invocation_window=window,
                    policy='native legacy retained and commit binding; observed_at and matching source spans only'),
                comparison='shared native scope replay and logical row multiset; exact commit ID correspondence and bound source IDs')


def sha_bytes(value):
    import hashlib
    return hashlib.sha256(value).hexdigest()


def scope_evidence(scope, checked, group):
    started = read(scope / 'scope.started.json'); errors = []
    if started.get('group') != group['group_id'] or type(started.get('native_entry_invoked')) is not bool:
        raise ValueError('scope start/invocation identity mismatch')
    rows = None
    if (scope / 'extraction.completed.json').exists():
        rows = read(scope / 'extraction.completed.json').get('extraction')
        try:
            if old.raw_scope_extraction(scope) != rows: raise ValueError('raw archive mismatch')
        except Exception as exc: errors.append(str(exc))
    accounting = extraction_accounting(rows, started['native_entry_invoked'], checked['modules'][0])
    if started['native_entry_invoked']:
        expected = checked['runner'].history_holders(group['history'])
        holders = [row.get('holder') for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
        if (not all(isinstance(holder, str) for holder in holders) or len(holders) != len(expected)
            or set(holders) != set(expected)):
            errors.append('native receipt holder inventory incomplete or ambiguous')
            accounting.update(usage_complete=False, observed_tokens=None, healthy_http=False,
                local_attempt_count_unknown=True, remote_execution_unknown=True)
    metadata = read(scope / 'scope.json') if (scope / 'scope.json').exists() else None
    if metadata is not None and (metadata.get('group') != group['group_id'] or metadata.get('extraction') != rows):
        errors.append('scope metadata/raw extraction mismatch')
    failures = {name: read(scope / name) for name in ('failure.json', 'analysis-failure.json', 'terminal-failure.json')
                if (scope / name).exists()}
    return started, rows, accounting, metadata, errors, failures


def partial_scope_audit(scope, checked, group):
    started, rows, accounting, metadata, errors, failures = scope_evidence(scope, checked, group)
    snapshots = {name: sha(scope / name) for name in ('frozen.db', 'diagnostic.db') if (scope / name).is_file()}
    return dict(group=group['group_id'], status='technical_failure', evidence_valid=False,
        native_entry_invoked=started['native_entry_invoked'], reservation=started['reservation'], accounting=accounting,
        database=None, database_snapshots=snapshots, native_replay=dict(verified=False, reason='analysis interrupted'),
        embedding_request_count=metadata.get('embedding_request_count') if metadata else None,
        evidence_errors=errors, failures=failures)


def scope_audit(scope, checked, group):
    if (scope / 'analysis-failure.json').exists(): return partial_scope_audit(scope, checked, group)
    started, rows, accounting, metadata, errors, failures = scope_evidence(scope, checked, group)
    plan = checked['plans']['scopes'][group['group_id']]
    proof = None; replay = dict(verified=False, reason='incomplete native evidence')
    database = next((scope / name for name in ('frozen.db', 'diagnostic.db') if (scope / name).is_file()), None)
    if database:
        try: proof = old.database_proof(database, plan, rows)
        except Exception as exc: errors.append(str(exc))
        if rows is not None:
            try:
                ended = read(scope / 'native.finished.json') if (scope / 'native.finished.json').exists() else {}
                replay = native_replay(checked, database, rows, plan, group,
                    dict(start=started.get('native_started_at'), end=ended.get('native_ended_at')))
            except Exception as exc: errors.append(str(exc))
    if metadata is not None and database:
        try: old.validate_scope_health(group, database, metadata, plan)
        except Exception as exc: errors.append(str(exc))
    healthy = (not errors and not failures and metadata is not None and proof is not None and replay['verified']
               and accounting['healthy_http'] and accounting['usage_complete']
               and not accounting['local_attempt_count_unknown'] and not accounting['remote_execution_unknown'])
    embedding = metadata.get('embedding_request_count') if metadata else None
    if embedding is None and 'failure.json' in failures: embedding = failures['failure.json'].get('embedding_request_count')
    return dict(group=group['group_id'], status='passed' if healthy else 'technical_failure', evidence_valid=not errors,
        native_entry_invoked=started['native_entry_invoked'], reservation=started['reservation'], accounting=accounting,
        database=proof, native_replay=replay, embedding_request_count=embedding, evidence_errors=errors, failures=failures)


def run_scope(checked, group, scope, ledger):
    scope.mkdir(parents=True); gid = group['group_id']
    reservation = ledger.reserve(gid, 'scope_extraction', checked['plans']['scopes'][gid]['extraction_request_upper_bound'])
    if reservation['state'] != 'reserved': raise ValueError('scope extraction budget blocked')
    started = dict(group=gid, reservation=reservation, native_entry_invoked=False)
    write(scope / 'scope.started.json', started); adapters = None
    try:
        adapters = make_adapters(checked)
        with tempfile.TemporaryDirectory(prefix='r59-scope-') as temp:
            scratch = Path(temp)
            try:
                started.update(native_entry_invoked=True, native_started_at=utc_now()); write(scope / 'scope.started.json', started)
                try: _, metadata = scope_worker(checked, group, scratch, adapters, ledger, reservation)
                finally: write(scope / 'native.finished.json', dict(native_ended_at=utc_now()))
                archive_scope(scratch, scope, True)
                write(scope / 'scope.json', dict(group=gid, **metadata))
            except BaseException:
                # Preserve completed raw receipts and a stable backup even if the normal archive failed.
                previous.archive_scope_outputs(scratch, scope, complete=False)
                raise
    except BaseException as exc:
        write(scope / 'failure.json', dict(error=f'{type(exc).__name__}: {exc}',
            embedding_request_count=getattr(adapters[1], 'request_count', None) if adapters else 0))
    try:
        # Existing settled rows are never rewritten; a failed unknown extraction stays conservatively charged.
        for row in old.ledger_rows(ledger.path):
            if row['scope'] != gid or row['state'] != 'reserved': continue
            if row['stage'] == 'scope_extraction':
                ledger.charge_upper(row['id']) if started['native_entry_invoked'] else ledger.settle(row['id'], 0)
            else:
                count = getattr(adapters[1], 'request_count', None) if adapters else 0
                if type(count) is int and 0 <= count <= row['upper_bound']: ledger.settle(row['id'], count)
                else: ledger.charge_upper(row['id'])
    except BaseException as exc:
        write(scope / 'failure.json', dict(error=f'{type(exc).__name__}: {exc}',
            embedding_request_count=getattr(adapters[1], 'request_count', None) if adapters else 0))
    try: result = scope_audit(scope, checked, group)
    except BaseException as exc:
        write(scope / 'analysis-failure.json', dict(error=f'{type(exc).__name__}: {exc}'))
        result = partial_scope_audit(scope, checked, group)
    try: write(scope / 'terminal.json', result)
    except BaseException as exc:
        write(scope / 'terminal-failure.json', dict(error=f'{type(exc).__name__}: {exc}'))
        result = partial_scope_audit(scope, checked, group) if (scope / 'analysis-failure.json').exists() else scope_audit(scope, checked, group)
    return result


def make_ledger(path):
    return baseline.BudgetLedger(path, BUILD_BUDGET)


def execution_plan(checked):
    return dict(stage='build', workers=1, groups=[g['group_id'] for g in checked['groups']],
        core_sha256=CORE_SHA256, claim_batch_target_units=True, claim_batch_prompt_profile=PROFILE,
        loaded_core=str(checked['modules'][0].__file__), build_budget=BUILD_BUDGET,
        extraction_conservative_bound=checked['plans']['extraction_request_upper_bound'],
        scope_upper_bounds={gid: value['extraction_request_upper_bound'] for gid, value in checked['plans']['scopes'].items()})


def build_summary(out, checked):
    groups = checked['groups']; expected = [g['group_id'] for g in groups]
    present = {p.name for p in (out / 'runs').iterdir()} if (out / 'runs').exists() else set()
    prefix = [gid for gid in expected if gid in present]
    if set(prefix) != present or prefix != expected[:len(prefix)]: raise ValueError('nonserial or unknown scope inventory')
    stage_failure = read(out / 'failure.json') if (out / 'failure.json').exists() else None
    ledger_error = None; ledger = None; reservations = []
    try:
        reservations = old.ledger_rows(out / 'request-ledger.sqlite')
        ledger = previous.read_ledger(out / 'request-ledger.sqlite', BUILD_BUDGET)
    except Exception as exc:
        if stage_failure is None: raise
        ledger_error = f'{type(exc).__name__}: {exc}'
    health = {}; results = {}; consumed = []; extraction_charge = embedding_count = 0; encountered_failure = False
    for group in groups[:len(prefix)]:
        gid = group['group_id']; scope = out / 'runs' / gid
        if encountered_failure: raise ValueError('scope executed after unhealthy predecessor')
        scope_rows = [r for r in reservations if r['scope'] == gid]
        if not (scope / 'scope.started.json').is_file():
            if stage_failure is None: raise ValueError('scope missing durable start')
            results[gid] = dict(group=gid, status='technical_failure', evidence_valid=False,
                native_entry_invoked=None, database=None, embedding_request_count=None,
                accounting=extraction_accounting(None, True, checked['modules'][0]),
                native_replay=dict(verified=False, reason='missing durable start'), failures={'stage': stage_failure},
                evidence_errors=['scope initialization interrupted'])
            consumed.extend(scope_rows); encountered_failure = True; continue
        result = (partial_scope_audit(scope, checked, group) if (scope / 'analysis-failure.json').exists()
                  else scope_audit(scope, checked, group))
        if (scope / 'terminal.json').exists():
            if not identical(read(scope / 'terminal.json'), result): raise ValueError('recomputed scope terminal mismatch')
        elif result['status'] == 'passed': raise ValueError('healthy scope missing durable terminal')
        results[gid] = result; invoked = result['native_entry_invoked']
        if ledger is not None:
            extraction = [r for r in scope_rows if r['stage'] == 'scope_extraction']
            embeddings = [r for r in scope_rows if r['stage'] == 'scope_embedding']
            if len(extraction) != 1 or len(embeddings) > 1 or len(scope_rows) != 1 + len(embeddings):
                raise ValueError('scope reservation inventory mismatch')
            row = extraction[0]; reservation = result['reservation']; upper = checked['plans']['scopes'][gid]['extraction_request_upper_bound']
            if (type(reservation.get('id')) is not int or type(reservation.get('upper_bound')) is not int
                or reservation != dict(id=row['id'], state='reserved', upper_bound=upper)
                or row['upper_bound'] != upper): raise ValueError('exact started/SQLite reservation binding mismatch')
            expected_state = 'charged_upper' if invoked else 'settled'
            if row['state'] == 'reserved' and (result['failures'] or stage_failure): encountered_failure = True
            elif row['state'] != expected_state or row['actual'] != (None if invoked else 0):
                raise ValueError('scope extraction conservative settlement mismatch')
            extraction_charge += upper if row['state'] == 'charged_upper' else 0
            if result['status'] == 'passed' and len(embeddings) != 1: raise ValueError('healthy scope lacks embedding reservation')
            for row in embeddings:
                actual = result['embedding_request_count']
                if result['database'] is not None and result['status'] == 'passed':
                    if row['upper_bound'] != baseline._embedding_reservation(result['database']['statements']):
                        raise ValueError('native embedding reservation upper bound mismatch')
                if row['state'] == 'reserved' and (result['failures'] or stage_failure): encountered_failure = True
                elif type(actual) is int and 0 <= actual <= row['upper_bound']:
                    if row['state'] != 'settled' or row['actual'] != actual: raise ValueError('embedding actual settlement mismatch')
                    embedding_count += actual
                elif row['state'] != 'charged_upper' or row['actual'] is not None:
                    raise ValueError('unknown embedding cost was not conservatively charged')
            consumed.extend(scope_rows)
        if result['status'] == 'passed': health[gid] = result['database']
        else: encountered_failure = True
    if ledger is not None and consumed != reservations: raise ValueError('unmatched or reordered SQLite reservations')
    complete = (len(health) == len(groups) == 8 and not stage_failure and not encountered_failure
                and ledger is not None and ledger['reserved'] == 0 and extraction_charge == 851)
    if not complete and not encountered_failure and stage_failure is None and ledger_error is None:
        raise ValueError('incomplete scope prefix lacks failure evidence')
    costs = [value['accounting'] for value in results.values()]
    usage_complete = ledger_error is None and all(v['usage_complete'] for v in costs)
    return dict(stage='build', state='complete' if complete else 'incomplete', healthy_scopes=len(health),
        health=health, scopes=results, completed_scopes=list(health), unexecuted_scopes=expected[len(prefix):],
        database_sha256={gid: proof['database_sha256'] for gid, proof in health.items()},
        retrieval_ready=complete, qa_ready=False, unexecuted_stages=['retrieve', 'qa'],
        ledger=ledger, ledger_error=ledger_error, stage_failure=stage_failure,
        extraction_conservative_charge=extraction_charge, extraction_observed_requests=sum(v['observed_native_requests'] for v in costs),
        extraction_known_tokens=sum(v['known_tokens'] for v in costs),
        extraction_observed_tokens=sum(v['known_tokens'] for v in costs) if usage_complete else None,
        usage_complete=usage_complete, local_attempt_count_unknown=ledger_error is not None or any(v['local_attempt_count_unknown'] for v in costs),
        remote_execution_unknown=ledger_error is not None or any(v['remote_execution_unknown'] for v in costs),
        embedding_requests=embedding_count, embedding_raw_http_available=False,
        embedding_token_usage_unknown=bool(embedding_count or any(v.get('embedding_request_count') is None for v in results.values()) or ledger_error),
        stage_total_tokens=None, limitation='Chat tokens only; embedding binding exposes counters without raw HTTP or token usage. No QA score.')


def partial_build_summary(out, checked):
    """Independent raw-evidence fallback; never rerun an interrupted stage analyzer."""
    interruption = read(out / 'interruption.json'); results = {}; errors = []; ledger = None; reservations = []
    expected = [g['group_id'] for g in checked['groups']]
    present = {p.name for p in (out / 'runs').iterdir()} if (out / 'runs').exists() else set()
    if present - set(expected): errors.append('unknown scope artifact')
    try:
        reservations = old.ledger_rows(out / 'request-ledger.sqlite')
        ledger = previous.read_ledger(out / 'request-ledger.sqlite', BUILD_BUDGET)
    except Exception as exc: errors.append(f'ledger: {type(exc).__name__}: {exc}')
    for group in checked['groups']:
        if group['group_id'] not in present: continue
        scope = out / 'runs' / group['group_id']
        try: results[group['group_id']] = partial_scope_audit(scope, checked, group)
        except Exception as exc:
            results[group['group_id']] = dict(status='technical_failure', evidence_valid=False,
                accounting=extraction_accounting(None, True, checked['modules'][0]), embedding_request_count=None,
                evidence_errors=[f'{type(exc).__name__}: {exc}'])
    costs = [value['accounting'] for value in results.values()]
    known = sum(value['known_tokens'] for value in costs)
    usage_complete = not errors and all(value['usage_complete'] for value in costs)
    return dict(stage='build', state='incomplete', healthy_scopes=0, health={}, scopes=results,
        completed_scopes=[], unexecuted_scopes=[gid for gid in expected if gid not in present],
        retrieval_ready=False, qa_ready=False, unexecuted_stages=['retrieve', 'qa'],
        interruption=interruption, evidence_errors=errors, ledger=ledger,
        extraction_conservative_charge=sum(r['upper_bound'] for r in reservations
            if r['stage']=='scope_extraction' and r['state']=='charged_upper'),
        extraction_observed_requests=sum(value['observed_native_requests'] for value in costs),
        extraction_known_tokens=known, extraction_observed_tokens=known if usage_complete else None,
        usage_complete=usage_complete,
        local_attempt_count_unknown=bool(errors) or any(value['local_attempt_count_unknown'] for value in costs),
        remote_execution_unknown=bool(errors) or any(value['remote_execution_unknown'] for value in costs),
        embedding_requests=sum(r['actual'] for r in reservations if r['stage']=='scope_embedding' and r['state']=='settled'),
        embedding_raw_http_available=False, embedding_token_usage_unknown=bool(results or errors), stage_total_tokens=None,
        limitation='Stage analysis incomplete; only raw receipt cost and ledger evidence are reported. No QA score.')


def build(prepared, out):
    out = new_output(out); prepared = Path(prepared).resolve(); checked = check(prepared, 'prepare', require_current=True)
    out.mkdir(parents=True)
    stage = dict(stage='build', input=str(prepared), input_seal_sha256=checked['seal_sha256'])
    try:
        write(out / 'stage.json', stage)
        for name in (*INPUT_FILES, 'config.json', 'identity.json'): copy_file(prepared / name, out / name)
        copy_file(prepared / 'seal.json', out / 'prepare-seal.json')
        write(out / 'execution-plan.json', execution_plan(checked))
    except BaseException as exc:
        record_interruption(out, stage, 'initialization', exc)
        return finalize_stage(out, stage, partial_build_summary(out, checked), lambda: partial_build_summary(out, checked))
    try:
        ledger = make_ledger(out / 'request-ledger.sqlite')
        for index, group in enumerate(checked['groups']):
            result = run_scope(checked, group, out / 'runs' / group['group_id'], ledger)
            print(f"build scopes: {index + 1}/8; {group['group_id']}; {result['status']}", flush=True)
            if result['status'] != 'passed': break
        validate_prepared(prepared, require_current=True)
        if sha(prepared / 'seal.json') != checked['seal_sha256']: raise ValueError('prepare changed during build')
    except BaseException as exc:
        write(out / 'failure.json', dict(error=f'{type(exc).__name__}: {exc}'))
    try: summary = build_summary(out, checked)
    except BaseException as exc:
        record_interruption(out, stage, 'analysis', exc)
        summary = partial_build_summary(out, checked)
    return finalize_stage(out, stage, summary, lambda: partial_build_summary(out, checked))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__); stages = parser.add_subparsers(dest='stage', required=True)
    p = stages.add_parser('prepare'); p.add_argument('--parent', type=Path, default=DEFAULT_PARENT)
    p.add_argument('--probe', type=Path, default=DEFAULT_PROBE); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--evidence', type=Path, action='append', default=[])
    p = stages.add_parser('build'); p.add_argument('--input', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p = stages.add_parser('check'); p.add_argument('--input', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.stage == 'check':
        audited = check(args.input)
        result = dict(audited['summary'], audit_program_files=audited['audit_program_files'])
    else:
        result = prepare(args.parent, args.out, args.probe, args.evidence) if args.stage == 'prepare' else build(args.input, args.out)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False)); return int(result['state'] != 'complete')


if __name__ == '__main__': raise SystemExit(main())
