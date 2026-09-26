#!/usr/bin/env python3
"""严格绑定 R55 Kwame 失败输入的单次容量预检；validate-only 零 provider。"""
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
import traceback

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREPARE = ROOT / 'build/socialmem_20260925_r55_expanded/prepare'
DEFAULT_FAILED = ROOT / 'build/socialmem_20260925_r55_expanded/build'
FAILED_SEAL_SHA256 = '75b2f99f02253a11ea8c03f025a1f6f440bf9e594624eb1e6d06ce6b319af522'
PREPARE_SEAL_SHA256 = '66b13d7e22b0794903467d9ea89f21b91379118d43866b4504b49fd9bd0178d0'
CORE_SHA256 = '02a2a3d8c653d331c700cdf652c59fefe2b812ff99845271bd5137bebf81dd3d'
SCOPE, HOLDER = '1c2838ef51b9983207436fc9', 'Kwame'
OVERRIDES = dict(extract_max_tokens=16384, timeout_ms=240000)

_spec = importlib.util.spec_from_file_location('r55_capacity_parent', ROOT / 'scripts/run_socialmem_r55_expanded.py')
r55 = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = r55
_spec.loader.exec_module(r55)


def text_sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def verify_failed_seal(failed):
    """The established R55 verifier intentionally refuses incomplete stages."""
    if r55.sha(failed / 'seal.json') != FAILED_SEAL_SHA256:
        raise ValueError('fixed failed seal identity mismatch')
    seal = r55.read(failed / 'seal.json')
    if (seal.get('schema'), seal.get('stage'), seal.get('state')) != ('r55-seal-v1', 'build', 'incomplete'):
        raise ValueError('expected incomplete R55 build seal')
    actual = r55.inventory(failed)
    actual.pop('seal.json', None)
    if not actual or actual != seal.get('files'):
        raise ValueError('failed seal file set/hash mismatch')
    return seal


def validate_inputs(prepare, failed):
    """Read immutable DB and invoke only native prompt generation; never construct providers."""
    prepare, failed = Path(prepare).resolve(), Path(failed).resolve()
    verify_failed_seal(failed)
    if r55.sha(prepare / 'seal.json') != PREPARE_SEAL_SHA256:
        raise ValueError('fixed prepare seal identity mismatch')
    checked = r55.check(prepare, 'prepare')
    stage = r55.read(failed / 'stage.json')
    if (stage.get('stage') != 'build' or stage.get('input_stage') != 'prepare'
        or Path(stage.get('input', '')).resolve() != prepare
        or stage.get('input_seal_sha256') != PREPARE_SEAL_SHA256
        or r55.sha(failed / 'input-seal.json') != PREPARE_SEAL_SHA256):
        raise ValueError('failed build/prepare chain mismatch')
    config = checked['config']
    if r55.read(failed / 'config.json') != config:
        raise ValueError('failed and prepare config mismatch')
    expected = dict(extract_model='qwen3.8-27b', extract_enable_thinking=False,
                    extract_max_tokens=8192, timeout_ms=120000, max_retries=0, core_sha256=CORE_SHA256)
    if any(config.get(k) != v or type(config.get(k)) is not type(v) for k, v in expected.items()):
        raise ValueError('original extraction protocol mismatch')
    scope = failed / 'runs' / SCOPE
    metadata = r55.read(scope / 'scope.json')
    if metadata.get('group') != SCOPE or metadata.get('scope_state') != 'partial':
        raise ValueError('failed scope identity/state mismatch')
    rows = [r for r in metadata.get('extraction', []) if r.get('holder') == HOLDER]
    if len(rows) != 1 or rows[0].get('extraction_failed') is not True:
        raise ValueError('exactly one failed Kwame holder required')
    row = rows[0]
    channel = row['receipt']['channels']['belief']
    attempts = channel.get('attempts', [])
    if channel.get('holder') != HOLDER or len(attempts) != 1 or attempts[0].get('attempt') != 1:
        raise ValueError('original belief attempt identity mismatch')
    original = attempts[0]['extraction']
    if (original.get('ok') is not False or original.get('error') != 'completion_truncated'
        or original.get('finish_reason') != 'length' or original.get('completion_tokens') != 8192
        or original.get('attempt_count') != 1 or original.get('output_contract') != 'claim_extraction_v2'
        or original.get('output_mode') != 'json_object'):
        raise ValueError('expected first truncated native extraction failure')
    http = original.get('http_attempts', [])
    if (len(http) != 1 or http[0].get('http_status') != 200 or http[0].get('curl_code') != 0
        or http[0].get('execution_certainty') != 'response_received' or not http[0].get('response_body')):
        raise ValueError('original HTTP 200 receipt missing')
    db = scope / 'frozen.db'
    with closing(sqlite3.connect(db.as_uri() + '?mode=ro&immutable=1', uri=True)) as conn:
        payload_rows = conn.execute('SELECT s.engram_ref,e.payload_inline FROM source_documents s '
            'JOIN engrams e ON e.id=s.engram_ref AND e.tenant_id=s.tenant_id '
            'WHERE s.tenant_id=? AND s.holder_id=?', ('default', HOLDER)).fetchall()
    if len(payload_rows) != 1 or payload_rows[0][0] != row.get('engram_ref'):
        raise ValueError('unique holder source engram identity mismatch')
    raw_payload = payload_rows[0][1]
    if not isinstance(raw_payload, bytes):
        raise ValueError('source payload must be preserved UTF-8 bytes')
    payload = raw_payload.decode('utf-8')
    if text_sha(payload) != channel.get('source_payload_hash'):
        raise ValueError('source payload hash mismatch')
    runner, modules = r55.frozen_modules(prepare, config, checked['identity'])
    core = modules[0]
    if r55.sha(core.__file__) != CORE_SHA256:
        raise ValueError('loaded frozen core hash mismatch')
    prompt = core.claim_extraction_prompt(payload, HOLDER)
    if (prompt != original.get('prompt') or prompt != channel.get('prompt')
        or text_sha(prompt) != original.get('prompt_input_hash')
        or text_sha(prompt) != channel.get('prompt_input_hash')):
        raise ValueError('native reconstructed prompt bytes/hash mismatch')
    schema_sha = core.structured_output_schema_sha256(core.OutputContractKind.ClaimExtractionV2)
    if schema_sha != original.get('schema_sha256'):
        raise ValueError('native extraction schema hash mismatch')
    binding = dict(schema='r55-capacity-binding-v1', prepare=str(prepare), failed_build=str(failed),
        prepare_seal_sha256=PREPARE_SEAL_SHA256, failed_seal_sha256=FAILED_SEAL_SHA256,
        core_sha256=CORE_SHA256, loaded_core=str(Path(core.__file__).resolve()),
        database_sha256=r55.sha(db), scope_json_sha256=r55.sha(scope / 'scope.json'),
        scope=SCOPE, holder=HOLDER, channel='belief', original_attempt=1, tenant_id='default',
        engram_ref=row['engram_ref'], payload_sha256=text_sha(payload), payload_bytes=len(raw_payload),
        prompt_sha256=text_sha(prompt), prompt_bytes=len(prompt.encode('utf-8')), schema_sha256=schema_sha,
        original_config_sha256=r55.sha(failed / 'config.json'), overrides=OVERRIDES,
        output_contract='claim_extraction_v2', output_mode='json_object', request_limit=1)
    return dict(binding=binding, core=core, runner=runner, config={**config, **OVERRIDES},
                original_config=config, identity=checked['identity'], prompt=prompt, payload=payload,
                failed_response=original, db=db, scope=scope)


def make_extract_adapter(core, runner, config):
    """Construct only the extraction adapter; no embedding, admission or QA adapters."""
    with runner._provider_environment('DASHSCOPE_API_KEY', config['extract_endpoint']):
        native = core.OpenAIAdapterConfig.from_env()
        native.model = config['extract_model']
        native.max_tokens, native.timeout_ms = config['extract_max_tokens'], config['timeout_ms']
        native.max_retries, native.enable_thinking = config['max_retries'], config['extract_enable_thinking']
        native.json_object_output = False  # StructuredOutputRequest selects JsonObject natively.
        return core.OpenAIAdapter(native)


def freeze_dependencies(out, validated):
    implementation = set(r55.IMPLEMENTATION_FILES) | {
        'scripts/run_socialmem_r55_capacity_probe.py', 'tests/python/test_socialmem_r55_capacity_probe.py'}
    for name in sorted(implementation):
        r55._copy_file(ROOT / name, out / 'implementation' / name)
    prepare, failed = Path(validated['binding']['prepare']), Path(validated['binding']['failed_build'])
    shutil.copytree(prepare / 'frozen', out / 'runtime', ignore=shutil.ignore_patterns('__pycache__'))
    for source, name in [(prepare / 'seal.json', 'prepare-seal.json'), (failed / 'seal.json', 'failed-seal.json'),
                         (validated['scope'] / 'scope.json', 'failed-scope.json'), (validated['db'], 'source.db')]:
        r55._copy_file(source, out / 'inputs' / name)
    (out / 'prompt.txt').write_bytes(validated['prompt'].encode('utf-8'))
    (out / 'source-payload.txt').write_bytes(validated['payload'].encode('utf-8'))
    r55.write(out / 'binding.json', validated['binding'])
    r55.write(out / 'original-config.json', validated['original_config'])
    r55.write(out / 'config.json', validated['config'])
    r55.write(out / 'failed-response.json', validated['failed_response'])
    dependencies = dict(implementation=r55.inventory(out / 'implementation'), runtime=r55.inventory(out / 'runtime'))
    r55.write(out / 'dependencies.json', dependencies)
    return dependencies


def revalidate(out, validated, dependencies):
    refreshed = validate_inputs(validated['binding']['prepare'], validated['binding']['failed_build'])
    if refreshed['binding'] != validated['binding']:
        raise ValueError('input binding changed during capacity probe')
    for relative, digest in dependencies['implementation'].items():
        if r55.sha(ROOT / relative) != digest:
            raise ValueError('probe implementation changed: ' + relative)
    if dependencies['runtime'] != refreshed['identity']['frozen_files']:
        raise ValueError('archived frozen runtime identity mismatch')
    if any(r55.inventory(out / name) != manifest for name, manifest in
           [('implementation', dependencies['implementation']), ('runtime', dependencies['runtime'])]):
        raise ValueError('archived dependency content changed')
    if (r55.sha(out / 'inputs/source.db') != refreshed['binding']['database_sha256']
        or r55.sha(out / 'prompt.txt') != refreshed['binding']['prompt_sha256']
        or r55.sha(out / 'source-payload.txt') != refreshed['binding']['payload_sha256']):
        raise ValueError('archived input content changed')
    for name, expected in [('config.json', refreshed['config']), ('original-config.json', refreshed['original_config']),
                           ('binding.json', refreshed['binding']), ('failed-response.json', refreshed['failed_response']),
                           ('dependencies.json', dependencies)]:
        if r55.read(out / name) != expected:
            raise ValueError('archived evidence content changed: ' + name)
    for name, digest in [('prepare-seal.json', PREPARE_SEAL_SHA256), ('failed-seal.json', FAILED_SEAL_SHA256),
                         ('failed-scope.json', refreshed['binding']['scope_json_sha256'])]:
        if r55.sha(out / 'inputs' / name) != digest:
            raise ValueError('archived source evidence hash changed: ' + name)


def response_health(response, binding):
    http = response.get('http_attempts')
    if (response.get('ok') is not True or response.get('error') != '' or response.get('refusal') is not False
        or response.get('finish_reason') != 'stop' or response.get('attempt_count') != 1
        or not isinstance(http, list) or len(http) != 1):
        return 'unhealthy native extraction terminal'
    attempt = http[0]
    if (attempt.get('curl_code') != 0 or attempt.get('http_status') != 200
        or attempt.get('execution_certainty') != 'response_received' or not attempt.get('response_body')):
        return 'unhealthy native HTTP terminal'
    if (response.get('output_contract') != 'claim_extraction_v2' or response.get('output_mode') != 'json_object'
        or response.get('schema_sha256') != binding['schema_sha256']):
        return 'native response contract mismatch'
    usage = [response.get(k) for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')]
    if any(type(v) is not int or v <= 0 for v in usage) or usage[0] + usage[1] != usage[2]:
        return 'native response usage missing or inconsistent'
    return None


def verify_output(out):
    out = Path(out)
    seal = r55.read(out / 'seal.json')
    actual = r55.inventory(out); actual.pop('seal.json', None)
    if (seal.get('schema') != 'r55-capacity-seal-v1' or seal.get('state') != 'complete'
        or actual != seal.get('files') or not actual):
        raise ValueError('capacity probe seal file set/hash mismatch')
    terminal = r55.read(out / 'terminal.json')
    if terminal.get('terminal') is not True or terminal != r55.read(out / 'summary.json'):
        raise ValueError('capacity probe terminal mismatch')
    ledger = r55.read_ledger(out / 'request-ledger.sqlite', 1)
    if terminal.get('ledger') != ledger or ledger['reserved'] or ledger['remaining'] < 0:
        raise ValueError('capacity probe ledger reconciliation mismatch')
    return terminal


def run(prepare, failed, out):
    out = r55.new_output(out)  # Refuse an existing directory even if inputs are unavailable.
    validated = validate_inputs(prepare, failed)
    out.mkdir(parents=True)
    ledger = validated['runner'].BudgetLedger(out / 'request-ledger.sqlite', 1)
    reservation = None
    terminal = dict(terminal=True, status='technical_failure', external_requests_observed=0,
        actual_requests_unknown=False, input_revalidation_ok=False, qualified_candidate_count=0,
        semantic_rejection_count=0, admission_requests=0, embedding_requests=0, qa_requests=0,
        limitation='Only this failed input capacity is tested; no admission, build health or QA claim.')
    dependencies = None
    try:
        dependencies = freeze_dependencies(out, validated)
        revalidate(out, validated, dependencies)
        core = validated['core']
        request = core.StructuredOutputRequest(core.OutputContractKind.ClaimExtractionV2, core.OutputMode.JsonObject)
        adapter = make_extract_adapter(core, validated['runner'], validated['config'])
        reservation = ledger.reserve(SCOPE + '/' + HOLDER, 'capacity_extract', 1)
        if reservation['state'] != 'reserved':
            raise ValueError('capacity request budget exhausted')
        terminal['actual_requests_unknown'] = True
        response = adapter.extract_with_contract(validated['prompt'], validated['binding']['prompt_sha256'], request)
        native_json = response.to_json()
        (out / 'native-response.json').write_text(native_json, encoding='utf-8')
        response = json.loads(native_json)
        r55.write(out / 'response.json', response)
        for field, name in [('raw_completion', 'raw-completion.txt'), ('raw_http_response', 'raw-http-response.txt')]:
            (out / name).write_bytes(response.get(field, '').encode('utf-8'))
        r55.write(out / 'usage.json', {k: response.get(k) for k in
            ('prompt_tokens', 'completion_tokens', 'total_tokens', 'latency_ms', 'attempt_count')})
        count = response.get('attempt_count')
        attempts = response.get('http_attempts')
        if type(count) is int and count >= 0 and isinstance(attempts, list) and count == len(attempts):
            terminal.update(external_requests_observed=count, actual_requests_unknown=False)
            if count <= 1:
                ledger.settle(reservation['id'], count)
            else:
                ledger.charge_upper(reservation['id'])
                terminal['request_budget_violation'] = True
        else:
            ledger.charge_upper(reservation['id'])
        # Parse the exact completion even on a failed terminal, retaining native diagnostics.
        parsed_json = core.claim_parse_response(response.get('raw_completion', ''), validated['payload'], HOLDER, True)
        (out / 'native-parse.json').write_text(parsed_json, encoding='utf-8')
        parsed = json.loads(parsed_json)
        terminal.update(qualified_candidate_count=len(parsed['statements']),
            semantic_rejection_count=len(parsed['semantic_rejections']), native_parse_errors=parsed['errors'])
        reason = response_health(response, validated['binding'])
        if reason:
            terminal['error'] = reason
        elif parsed['errors'] != []:
            terminal['status'] = 'native_parse_rejected'
        elif not parsed['statements']:
            terminal['status'] = 'no_qualified_candidates'
        else:
            terminal['status'] = 'capacity_probe_passed'
    except BaseException as exc:
        if reservation and reservation.get('state') == 'reserved':
            ledger.charge_upper(reservation['id'])
        terminal.update(status='technical_failure', error=type(exc).__name__ + ': ' + str(exc))
        (out / 'exception.txt').write_text(traceback.format_exc(), encoding='utf-8')
    finally:
        if dependencies is not None:
            try:
                revalidate(out, validated, dependencies)
                terminal['input_revalidation_ok'] = True
            except BaseException as exc:
                terminal.update(status='technical_failure', input_revalidation_ok=False,
                                revalidation_error=type(exc).__name__ + ': ' + str(exc))
        terminal['ledger'] = ledger.snapshot()
        r55.write(out / 'terminal.json', terminal)
        r55.write(out / 'summary.json', terminal)
        r55.write(out / 'seal.json', dict(schema='r55-capacity-seal-v1', state='complete', files=r55.inventory(out)))
    return verify_output(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--validate-only', action='store_true')
    mode.add_argument('--run', action='store_true')
    parser.add_argument('--prepare', type=Path, default=DEFAULT_PREPARE)
    parser.add_argument('--failed-build', type=Path, default=DEFAULT_FAILED)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.validate_only:
        if args.out is not None:
            parser.error('--validate-only is read-only and does not take --out')
        result = dict(status='validated_offline', external_requests=0,
                      binding=validate_inputs(args.prepare, args.failed_build)['binding'])
    else:
        if args.out is None:
            parser.error('--run requires a fresh --out directory')
        result = run(args.prepare, args.failed_build, args.out)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result['status'] in ('capacity_probe_passed', 'validated_offline') else 1


if __name__ == '__main__':
    raise SystemExit(main())
