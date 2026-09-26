#!/usr/bin/env python3
"""R5.5 扩大开发验证：离线 prepare/check，独立封存 build/retrieve/qa。

所有抽取、检索、上下文渲染和回答提示仍由冻结的原生核心与既有 helpers 执行。
已存在的输出永不续跑或覆盖；失败保留账本和原始回执，后续阶段 fail closed。
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import closing
import gc
import hashlib
import importlib.util
import json
from pathlib import Path
import queue
import shutil
import sqlite3
import sys
import tempfile
import traceback

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PARENT = ROOT / 'build/socialmem_20260925_r54_budget_ablation_retry1'
DEFAULT_CORPUS = ROOT / 'build/socialmem_20260917_source_focus/corpus.jsonl'
DEFAULT_SPLIT = ROOT / 'build/socialmem_20260917_source_focus/network-split.json'
DEFAULT_WORK = ROOT / 'build/socialmem_20260925_r55_expanded'
CORPUS_SHA256 = 'ba9d11578f6ebdad5bf3a0e443cf44a0d002fd400e11b243890f3fcc06ec607c'
SPLIT_SHA256 = 'e9c76953955892c18d433d2efadf8532b7909d420853c085d992f912cd80f266'
CORE_SHA256 = '02a2a3d8c653d331c700cdf652c59fefe2b812ff99845271bd5137bebf81dd3d'
NETWORKS = ('grp_c2d3e4f5', 'grp_7a8b9c0d', 'grp_e6f7a8b9', 'grp_d7e8f9a0', 'grp_b1c2d3e4', 'grp_a5b6c7d8')
ARMS = ('baseline', 'source10')
POLICIES = ('legacy', 'grounded_memory_v1')
BUILD_BUDGET, RETRIEVAL_BUDGET, QA_BUDGET = 12000, 1336, 956
EXPECTED_COUNTS = dict(questions=133, scopes=8, holder_scopes=65, history_turns=1322,
                       free_response=106, query_embedding_bound=1336, qa_request_bound=956)
CONFIG_OVERRIDES = dict(arm='r55_expanded_development', source_strategy='evidence_profile_v6', http_budget=BUILD_BUDGET)
IMPLEMENTATION_FILES = (
    'scripts/run_socialmem_r55_expanded.py', 'tests/python/test_socialmem_r55_expanded.py',
    'scripts/run_socialmem_r54_qa.py', 'scripts/run_socialmem_r54_ablation.py',
    'scripts/run_socialmem_r53_offline.py', 'scripts/run_socialmem_r52_v6_v7_qa.py',
    'scripts/run_socialmem_r51_same_db.py', 'scripts/run_socialmem_baseline.py',
)
INPUT_FILES = ('corpus.jsonl', 'network-split.json', 'old-sample.json', 'sample.json', 'groups.json',
               'scope-manifest.json', 'parent-config.json', 'parent-seal.json', 'provenance.json')


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


qa_helpers = load(ROOT / 'scripts/run_socialmem_r54_qa.py', 'r55_qa_helpers')
ablation = qa_helpers.ablation
baseline = load(ROOT / 'scripts/run_socialmem_baseline.py', 'r55_baseline')
previous = load(ROOT / 'scripts/run_socialmem_r51_same_db.py', 'r55_retrieval_adapters')
read, write, sha = qa_helpers.read, qa_helpers.write, qa_helpers.sha


def inventory(directory):
    directory = Path(directory)
    result = {}
    for path in sorted(directory.rglob('*')):
        if '__pycache__' in path.parts:
            continue
        if path.is_symlink():
            raise ValueError('unsafe symlink: ' + str(path))
        if path.is_file():
            result[path.relative_to(directory).as_posix()] = sha(path)
    return result


def seal_output(out, stage, state='complete'):
    out = Path(out)
    if (out / 'seal.json').exists():
        raise ValueError('seal already exists')
    write(out / 'seal.json', dict(schema='r55-seal-v1', stage=stage, state=state, files=inventory(out)))


def verify_seal(out):
    out = Path(out)
    seal = read(out / 'seal.json')
    if seal.get('schema') != 'r55-seal-v1' or seal.get('state') != 'complete':
        raise ValueError('incomplete or unknown stage seal')
    actual = inventory(out)
    actual.pop('seal.json', None)
    if not actual or actual != seal.get('files'):
        raise ValueError('seal file set/hash mismatch')
    return seal


def new_output(out):
    out = Path(out).resolve()
    if out.exists():
        raise ValueError('output already exists: ' + str(out))
    return out


def validate_record_groups(records, groups):
    canonical = baseline.prepare_groups(records)
    if groups != canonical:
        raise ValueError('sample/group full content or history identity mismatch')
    if len(records) != 133 or len({r['item_id'] for r in records}) != 133 or len(groups) != 8:
        raise ValueError('133 unique items and eight groups required')
    return canonical


def select_cohort(corpus, split, old_records):
    # Selection uses network identities only. Gold answers/anchors never enter selection.
    development, reserved = split['development_networks'], split['reserved_networks']
    if len(set(development)) != len(development) or len(set(reserved)) != len(reserved) or set(development) & set(reserved):
        raise ValueError('development/reserved contamination or duplicates')
    excluded = sorted({baseline._network_id(r) for r in old_records})
    if len(old_records) != 57 or len(excluded) != 6:
        raise ValueError('old cohort must have 57 questions/six networks')
    chosen = sorted(set(development) - set(excluded), key=qa_helpers.text_sha)[:6]
    if chosen != list(NETWORKS):
        raise ValueError('fixed network selection drift')
    records = [r for r in corpus if baseline._network_id(r) in chosen]
    groups = baseline.prepare_groups(records)
    validate_record_groups(records, groups)
    manifest = dict(networks=chosen, excluded_networks=excluded,
        questions=len(records), scopes=len(groups),
        holder_scopes=sum(len(baseline.history_holders(g['history'])) for g in groups),
        history_turns=sum(len(g['history']) for g in groups),
        free_response=sum(r.get('answer_format', 'multiple_choice') != 'multiple_choice' for r in records),
        query_embedding_bound=sum(len(baseline.history_holders(r['history'])) for r in records),
        qa_request_bound=4 * sum(1 + int(r.get('answer_format', 'multiple_choice') != 'multiple_choice') for r in records),
        selection='all questions in first six sha256(network)-sorted development networks excluding old six',
        claim='additional historically used development networks; not unseen or reserved data')
    if any(manifest[k] != v for k, v in EXPECTED_COUNTS.items()):
        raise ValueError('fixed cohort count/budget mismatch')
    return records, groups, manifest


def _cohort_from_files(out):
    if sha(out / 'corpus.jsonl') != CORPUS_SHA256 or sha(out / 'network-split.json') != SPLIT_SHA256:
        raise ValueError('fixed corpus/split hash mismatch')
    corpus = [json.loads(line) for line in (out / 'corpus.jsonl').read_text().splitlines() if line.strip()]
    return select_cohort(corpus, read(out / 'network-split.json'), read(out / 'old-sample.json'))


def _copy_file(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def _freeze_identity(out):
    identity = dict(schema='r55-identity-v1', core_sha256=CORE_SHA256,
        config_sha256=sha(out / 'config.json'), inputs={name: sha(out / name) for name in INPUT_FILES},
        frozen_files=inventory(out / 'frozen'), implementation_files=inventory(out / 'implementation'),
        current_source_files=inventory(out / 'current-source'))
    write(out / 'identity.json', identity)
    return identity


def _validate_identity(out):
    identity, config = read(out / 'identity.json'), read(out / 'config.json')
    if identity.get('schema') != 'r55-identity-v1' or identity.get('core_sha256') != CORE_SHA256:
        raise ValueError('identity core/schema mismatch')
    if config != {**read(out / 'parent-config.json'), **CONFIG_OVERRIDES}:
        raise ValueError('fixed config differs from parent protocol')
    fixed = dict(core_sha256=CORE_SHA256, answer_model='qwen3.8-27b', extract_model='qwen3.8-27b',
        embedding_model='qwen3.7-text-embedding', embedding_dim=1024, embedding_max_batch_inputs=10,
        answer_max_tokens=512, judge_max_tokens=64, extract_max_tokens=8192, max_retries=0,
        timeout_ms=120000, answer_enable_thinking=False, extract_enable_thinking=False,
        semantic_claim_contract=True, preserve_text_objects=True, claim_allow_code_fence=True,
        claim_protocol_retry_budget=1, claim_output_mode='json_object', holder_isolation=True,
        retain_sources=True, lifecycle='sleep', recall_mode='hybrid', k=10, min_source_items=7,
        source_dialogue_radius=1, max_context_bytes=8000, created_at='2026-06-01T00:00:00Z',
        query_time='2026-12-08T00:00:00Z')
    if any(config.get(k) != v or type(config.get(k)) is not type(v) for k, v in fixed.items()):
        raise ValueError('fixed config/protocol mismatch')
    if 'judge_enable_thinking' in config or sha(out / 'config.json') != identity.get('config_sha256'):
        raise ValueError('judge/config identity mismatch')
    if identity.get('inputs') != {name: sha(out / name) for name in INPUT_FILES}:
        raise ValueError('input identity mismatch')
    for directory, key in [('frozen', 'frozen_files'), ('implementation', 'implementation_files'), ('current-source', 'current_source_files')]:
        actual = inventory(out / directory)
        if not actual or actual != identity.get(key):
            raise ValueError(directory + ' identity mismatch')
        if directory != 'frozen':
            for relative, digest in actual.items():
                if not (ROOT / relative).is_file() or sha(ROOT / relative) != digest:
                    raise ValueError('current implementation/source drift: ' + relative)
    if set(identity['implementation_files']) != set(IMPLEMENTATION_FILES):
        raise ValueError('implementation dependency inventory mismatch')
    current_core = list((ROOT / 'build/python/starling').glob('_core*.so'))
    frozen_core = list((out / 'frozen/python/starling').glob('_core*.so'))
    if len(current_core) != 1 or len(frozen_core) != 1 or any(sha(p) != CORE_SHA256 for p in current_core + frozen_core):
        raise ValueError('current/frozen core mismatch')
    return config, identity


def prepare(parent, out, corpus=DEFAULT_CORPUS, split=DEFAULT_SPLIT):
    out = new_output(out)
    parent = Path(parent).resolve()
    verified = qa_helpers.validate_inputs(parent)  # The only use of R5.4's 57-question validator.
    if sha(corpus) != CORPUS_SHA256 or sha(split) != SPLIT_SHA256:
        raise ValueError('fixed corpus/split hash mismatch')
    raw = [json.loads(line) for line in Path(corpus).read_text().splitlines() if line.strip()]
    records, groups, manifest = select_cohort(raw, read(split), list(verified['records'].values()))
    out.mkdir(parents=True)
    try:
        for source, name in [(corpus, 'corpus.jsonl'), (split, 'network-split.json'),
                             (parent / 'sample.json', 'old-sample.json'), (parent / 'config.json', 'parent-config.json'),
                             (parent / 'seal.json', 'parent-seal.json')]:
            _copy_file(Path(source), out / name)
        for name, value in [('sample.json', records), ('groups.json', groups), ('scope-manifest.json', manifest),
                            ('config.json', {**verified['config'], **CONFIG_OVERRIDES})]:
            write(out / name, value)
        shutil.copytree(parent / 'frozen', out / 'frozen', ignore=shutil.ignore_patterns('__pycache__'))
        # Explicitly retain the parent's historical tree, and separately archive the live source.
        for name in IMPLEMENTATION_FILES:
            _copy_file(ROOT / name, out / 'implementation' / name)
        for directory in ('src', 'include', 'python'):
            for path in sorted((ROOT / directory).rglob('*')):
                if path.is_file() and '__pycache__' not in path.parts and path.suffix in ('.cpp', '.hpp', '.h', '.py', '.in'):
                    _copy_file(path, out / 'current-source' / path.relative_to(ROOT))
        for path in [ROOT / 'CMakeLists.txt', *sorted((ROOT / 'cmake').glob('*.cmake'))]:
            if path.is_file(): _copy_file(path, out / 'current-source' / path.relative_to(ROOT))
        write(out / 'provenance.json', dict(parent=str(parent), parent_seal_sha256=verified['seal_sha256'],
            parent_core_sha256=CORE_SHA256, inherited_source_tree='historical_R5.0_not_current_core_source',
            source_snapshot='current-source with current checkout hashes; key R5.4 implementation verified by validate_inputs',
            parent_implementation_sha256=inventory(parent / 'implementation'),
            corpus_source=str(Path(corpus).resolve()), split_source=str(Path(split).resolve())))
        _freeze_identity(out)
        write(out / 'stage.json', dict(stage='prepare', input=None, external_requests=0))
        write(out / 'summary.json', dict(stage='prepare', state='complete', **manifest, external_requests=0,
            budgets=dict(build=BUILD_BUDGET, retrieve=RETRIEVAL_BUDGET, qa=QA_BUDGET),
            extraction_conservative_bound=585, total_accounting_bound=14292))
        _validate_identity(out)
        # Detect parent/corpus drift during the copy, before the new input can be accepted.
        qa_helpers.verify_seal(parent)
        if sha(parent / 'seal.json') != verified['seal_sha256']:
            raise ValueError('parent seal changed during prepare')
        seal_output(out, 'prepare')
        return read(out / 'summary.json')
    except BaseException as exc:
        _fail(out, 'prepare', exc)
        raise


def frozen_modules(work, config, identity):
    runner = load(work / 'frozen/scripts/run_socialmem_baseline.py', 'r55_frozen_baseline')
    # The frozen helper removes this project's editable finder and verifies every loaded module.
    modules = runner._frozen_imports(work, config, identity)
    if sha(modules[0].__file__) != CORE_SHA256:
        raise ValueError('loaded core identity mismatch')
    return runner, modules


def validate_scope_health(group, database, metadata, *, native_embedding_health=None):
    holders = baseline.history_holders(group['history'])
    rows = metadata.get('extraction', [])
    if metadata.get('scope_state') != 'complete' or metadata.get('holder_failures') != []:
        raise ValueError('partial/failed scope')
    observed = [r.get('holder') for r in rows]
    if len(observed) != len(holders) or sorted(observed) != holders or any(r.get('extraction_failed') is not False for r in rows):
        raise ValueError('missing/duplicate/failed extraction holder')
    if sorted(metadata.get('holder_complete', [])) != holders:
        raise ValueError('holder completion inventory mismatch')
    response_health = validate_extraction_responses(rows)
    if not isinstance(metadata.get('embedding_request_count'), int):
        raise ValueError('embedding failure/missing request evidence')
    if native_embedding_health is None and metadata.get('embedding', {}).get('failed') != 0:
        raise ValueError('embedding failure/missing request evidence')
    database = Path(database)
    if not database.is_file() or any(Path(str(database) + suffix).exists() for suffix in ('-wal', '-shm')):
        raise ValueError('database absent or not frozen')
    final_health = None
    if native_embedding_health is not None:
        final_health = native_embedding_health(database)
        if (final_health.get('complete') is not True or
            metadata.get('embedding', {}).get('final_health') != final_health):
            raise ValueError('final embedding health incomplete or receipt mismatch')
    # A backup may retain WAL-mode header bytes. Plain mode=ro still creates
    # -wal/-shm files; immutable=1 is safe only after the no-side-files gate above.
    with closing(sqlite3.connect('file:' + str(database) + '?mode=ro&immutable=1', uri=True)) as conn:
        statement_count = conn.execute('SELECT COUNT(*) FROM statements').fetchone()[0]
        vectors = conn.execute('SELECT COUNT(*) FROM statement_vectors').fetchone()[0]
        pending = 0 if final_health is not None else conn.execute("SELECT COUNT(*) FROM statements s LEFT JOIN statement_vectors v ON "
            "s.id=v.stmt_id AND s.tenant_id=v.tenant_id WHERE v.stmt_id IS NULL OR v.status!='embedded' "
            "OR v.dim!=1024 OR v.index_vector IS NULL OR length(v.index_vector)!=4*v.dim").fetchone()[0]
        bad_vectors = 0 if final_health is not None else conn.execute("SELECT COUNT(*) FROM statement_vectors WHERE status!='embedded' OR dim!=1024 "
                                   "OR index_vector IS NULL OR length(index_vector)!=4*dim").fetchone()[0]
        sources = conn.execute('SELECT holder_id,engram_ref FROM source_documents WHERE tenant_id=?', ('default',)).fetchall()
        payloads = conn.execute('SELECT d.holder_id,e.payload_inline FROM source_documents d LEFT JOIN engrams e '
            'ON e.id=d.engram_ref AND e.tenant_id=d.tenant_id WHERE d.tenant_id=?', ('default',)).fetchall()
        foreign = conn.execute("SELECT COUNT(*) FROM statements WHERE tenant_id!='default'").fetchone()[0]
    if statement_count <= 0 or pending or bad_vectors or vectors != statement_count or foreign:
        raise ValueError('zero statements or incomplete embeddings/tenant mismatch')
    if metadata.get('database', {}).get('statements') != statement_count or metadata['database'].get('statement_vectors') != vectors:
        raise ValueError('database count receipt mismatch')
    source_receipt = metadata.get('sources') or {}
    if (len(sources) != len(holders) or sorted(h for h, _ in sources) != holders
            or source_receipt.get('documents') != len(sources) or source_receipt.get('turns') != len(group['history'])
            or sorted(source_receipt.get('engram_refs', [])) != sorted(ref for _, ref in sources)):
        raise ValueError('source inventory/count mismatch')
    observed_turns = []
    for holder, payload in payloads:
        if isinstance(payload, bytes): payload = payload.decode('utf-8')
        if not isinstance(payload, str) or not payload:
            raise ValueError('source payload missing')
        for line in payload.splitlines():
            prefix = next((p for p in ('@starling/source-turn-v1 ', '@starling/source-turn-v2 ') if line.startswith(p)), None)
            if prefix is None:
                raise ValueError('source payload turn framing mismatch')
            turn = json.loads(line[len(prefix):])
            if turn.get('speaker') != holder:
                raise ValueError('source holder/turn mismatch')
            observed_turns.append(turn)
    # This is persistence verification, not semantic extraction or evidence selection.
    def key(turn):
        return (turn.get('speaker'), turn.get('text'), turn.get('turn_id'))
    if Counter(key(t) for t in observed_turns) != Counter(key(t) for t in group['history']):
        raise ValueError('source persisted history turn content/count mismatch')
    return dict(holders=holders, statements=statement_count, vectors=vectors, pending_embeddings=pending,
                source_documents=len(sources), source_turns=len(observed_turns), database_sha256=sha(database),
                **response_health)


def native_extraction_responses(extraction):
    for holder in extraction:
        channels = holder.get('receipt', {}).get('channels', {})
        for name in ('belief', 'general_fact'):
            channel = channels.get(name, {})
            attempts = channel.get('attempts', [])
            if not attempts:
                raise ValueError('missing native channel response: ' + name)
            for attempt in attempts:
                yield attempt.get('extraction', {})
                admission = attempt.get('admission') or {}
                if admission.get('called') is True or admission.get('attempt_count', 0):
                    yield admission
        yield channels.get('episodic', {}).get('response', {})


def validate_extraction_responses(extraction):
    count = 0
    for response in native_extraction_responses(extraction):
        if (response.get('ok') is not True or response.get('error') != ''
            or response.get('refusal') is not False or response.get('finish_reason') != 'stop'
            or response.get('attempt_count') != 1):
            raise ValueError('unhealthy/missing native extraction response')
        attempts = response.get('http_attempts')
        if not isinstance(attempts, list) or len(attempts) != 1:
            raise ValueError('missing native HTTP attempt evidence')
        attempt = attempts[0]
        if (attempt.get('curl_code') != 0 or not 200 <= int(attempt.get('http_status', 0)) < 300
            or attempt.get('execution_certainty') != 'response_received'
            or not isinstance(attempt.get('response_body'), str) or not attempt['response_body']):
            raise ValueError('unhealthy/missing native HTTP response')
        count += 1
    return dict(healthy_native_responses=count, episodic_empty_or_unparsed_count=sum(
        h['receipt']['channels']['episodic'].get('ok') is not True for h in extraction),
        episodic_interpretation='transport healthy; native ok=false may mean empty or unparsed, without Python semantic repair')


def extraction_usage(extraction):
    """Read raw native receipt evidence separately from the conservative ledger charge."""
    requests = tokens = missing_usage = observations = 0
    for receipt in native_extraction_responses(extraction):
        count = receipt.get('attempt_count')
        if isinstance(count, int) and count > 0:
            observations += 1; requests += count
            tokens += int(receipt.get('total_tokens') or 0)
            missing_usage += int(not receipt.get('total_tokens'))
    return dict(observed_native_requests=requests, observed_tokens=tokens,
                response_observations=observations, missing_token_usage=missing_usage,
                accounting='raw native receipt evidence; excludes conservative extraction upper-bound charge')


def _copy_stage_input(source, out, stage):
    out.mkdir(parents=True)
    for directory in ('frozen', 'implementation', 'current-source'):
        shutil.copytree(source / directory, out / directory, ignore=shutil.ignore_patterns('__pycache__'))
    for name in (*INPUT_FILES, 'config.json', 'identity.json'):
        _copy_file(source / name, out / name)
    _copy_file(source / 'seal.json', out / 'input-seal.json')
    write(out / 'stage.json', dict(stage=stage, input=str(source), input_stage=read(source / 'stage.json')['stage'],
                                  input_seal_sha256=sha(source / 'seal.json')))


def _fail(out, stage, exc, ledger=None):
    if out.exists() and not (out / 'seal.json').exists():
        write(out / 'failure-summary.json', dict(stage=stage, state='incomplete', error=f'{type(exc).__name__}: {exc}',
            ledger=ledger.snapshot() if ledger else None, retry='refuse overwrite; diagnose and use a separate output with recorded recovery plan',
            saved_retrieval_receipts=len(list(out.glob('*/recalls/*.json'))),
            saved_qa_terminals=len(list(out.glob('answers/*/*/*.json')))))
        seal_output(out, stage, 'incomplete')


def _check_input_stable(source, digest):
    verify_seal(source)
    if sha(source / 'seal.json') != digest:
        raise ValueError('input seal changed during stage')


def archive_scope_outputs(scratch, destination, *, complete):
    """Archive receipts and stable snapshots, never the helper's live SQLite files."""
    scratch, destination = Path(scratch), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for path in sorted(scratch.rglob('*')):
        if not path.is_file() or path.name.startswith(('network.db', 'frozen.db')):
            continue
        _copy_file(path, destination / path.relative_to(scratch))
    if complete:
        frozen = scratch / 'frozen.db'
        if not frozen.is_file() or any(Path(str(frozen) + suffix).exists() for suffix in ('-wal', '-shm')):
            raise ValueError('helper frozen snapshot absent or still has side files')
        _copy_file(frozen, destination / 'frozen.db')
    elif (scratch / 'network.db').is_file():
        # Backup includes committed WAL data without copying a live main file alone.
        with closing(sqlite3.connect('file:' + str(scratch / 'network.db') + '?mode=ro', uri=True)) as source:
            with closing(sqlite3.connect(destination / 'diagnostic.db')) as snapshot:
                source.backup(snapshot)


def build(prepared, out):
    out = new_output(out)
    prepared = Path(prepared).resolve()
    checked = check(prepared, 'prepare')
    config, identity, groups = checked['config'], checked['identity'], checked['groups']
    ledger = None
    try:
        _copy_stage_input(prepared, out, 'build')
        # Load from the immutable prepare tree; copying binaries does not change their identity.
        runner, modules = frozen_modules(prepared, config, identity)
        ledger = runner.BudgetLedger(out / 'request-ledger.sqlite', BUILD_BUDGET)
        write(out / 'execution-plan.json', dict(stage='build', workers=1, build_budget=BUILD_BUDGET,
            extraction_accounting='9 per holder charged conservatively; actual receipt counts reported separately',
            extraction_conservative_bound=585, groups=[g['group_id'] for g in groups], loaded_core=str(modules[0].__file__),
            core_sha256=sha(modules[0].__file__), helper='_build_scope_database',
            embedding_accounting='existing _embedding_reservation then native request_count settlement'))
        health = {}
        for group in groups:
            gid = group['group_id']; scope_dir = out / 'runs' / gid; scope_dir.mkdir(parents=True)
            reservation = ledger.reserve(gid, 'scope_extraction', 9 * len(runner.history_holders(group['history'])))
            if reservation['state'] != 'reserved':
                raise runner.BudgetBlocked('build extraction budget exhausted')
            adapters = runner._make_native_adapters(modules[0], config)  # Serial: helper modifies process globals.
            try:
                # The frozen helper retains Python SQLite objects until collection.
                # Keep its live network.db outside the stage's immutable artifact set.
                with tempfile.TemporaryDirectory(prefix='socialmem-r55-build-') as temporary:
                    scratch = Path(temporary)
                    write(scope_dir / 'scope.started.json', dict(group=gid, reservation=reservation,
                        scratch_directory=str(scratch), crash_recovery='preserve unknown ledger reservation; never replay automatically'))
                    try:
                        _, metadata = runner._build_scope_database(group, scratch, modules, config, adapters, ledger, reservation)
                        archive_scope_outputs(scratch, scope_dir, complete=True)
                    except BaseException as exc:
                        archive_scope_outputs(scratch, scope_dir, complete=False)
                        traceback.clear_frames(exc.__traceback__)
                        raise
                    finally:
                        gc.collect()
                database = scope_dir / 'frozen.db'
                write(scope_dir / 'scope.json', dict(group=gid, **metadata,
                    extraction_usage=extraction_usage(metadata['extraction']), extraction_conservative_charge=reservation['upper_bound']))
                health[gid] = validate_scope_health(group, database, metadata)
                write(scope_dir / 'health.json', health[gid])
            except BaseException as exc:
                ledger.charge_upper(reservation['id'])
                write(scope_dir / 'scope.failure.json', dict(group=gid, error=f'{type(exc).__name__}: {exc}',
                    embedding_request_count=getattr(adapters[1], 'request_count', None), ledger=ledger.snapshot()))
                raise
            print(f"build scopes: {len(health)}/8; {gid}; statements={health[gid]['statements']}", flush=True)
        snapshot = ledger.snapshot()
        if snapshot['reserved'] or snapshot['remaining'] < 0 or snapshot['charged_upper'] != 585:
            raise ValueError('build ledger incomplete or conservative extraction charge mismatch')
        usage = [read(out / 'runs' / g['group_id'] / 'scope.json') for g in groups]
        embedding_requests = sum(row['embedding_request_count'] for row in usage)
        if snapshot['committed'] != 585 + embedding_requests:
            raise ValueError('build ledger receipt reconciliation failed')
        _check_input_stable(prepared, checked['seal_sha256'])
        write(out / 'summary.json', dict(stage='build', state='complete', healthy_scopes=8, health=health,
            database_sha256={gid: value['database_sha256'] for gid, value in health.items()}, ledger=snapshot,
            extraction_conservative_charge=585, extraction_observed_requests=sum(r['extraction_usage']['observed_native_requests'] for r in usage),
            embedding_requests=embedding_requests, extraction_observed_tokens=sum(r['extraction_usage']['observed_tokens'] for r in usage)))
        seal_output(out, 'build')
        return read(out / 'summary.json')
    except BaseException as exc:
        _fail(out, 'build', exc, ledger)
        raise


def validate_retrieval_inventory(records, groups, rows, databases, config):
    expected = {r['item_id']: r for r in records}
    group_by_item = {r['item_id']: g['group_id'] for g in groups for r in g['records']}
    if set(rows) != set(ARMS):
        raise ValueError('retrieval arm inventory mismatch')
    for arm, receipts in rows.items():
        if len(receipts) != len(records) or {r.get('item_id') for r in receipts} != set(expected):
            raise ValueError('retrieval duplicate/missing terminal inventory')
        for row in receipts:
            item = row['item_id']; gid = group_by_item[item]
            if row.get('group_id') != gid or row.get('holders') != baseline.history_holders(expected[item]['history']):
                raise ValueError('retrieval group/holder identity mismatch')
            ablation.validate_row(row, arm, databases[gid], CORE_SHA256, config['max_context_bytes'])
            if not ablation.healthy_embedding(row):
                raise ValueError('unhealthy retrieval terminal')
    requests = sum(r['embedding_requests'] for receipts in rows.values() for r in receipts)
    if requests != RETRIEVAL_BUDGET:
        raise ValueError('retrieval request/holder inventory mismatch')


def retrieval_comparison(records, rows):
    indexed = {arm: {r['item_id']: r for r in receipts} for arm, receipts in rows.items()}
    anchors = {arm: dict(hit=0, total=0) for arm in ARMS}
    details = []
    for record in records:
        gold = {a['turn_id'] for a in record.get('source', {}).get('evidence_anchors', [])}
        detail = dict(item_id=record['item_id'], anchor_total=len(gold))
        for arm in ARMS:
            recall = indexed[arm][record['item_id']]['recall']
            hit = len(gold & {s.get('turn_id') for s in recall['source_refs']})
            anchors[arm]['hit'] += hit; anchors[arm]['total'] += len(gold)
            detail[arm + '_anchor_hit'] = hit
        details.append(detail)
    return dict(questions=len(records), anchors=anchors, rows=details, qa_gate='passed_technical_health',
                gate_uses_anchor_scores=False, interpretation='anchor scores are diagnostics only; QA does not depend on their direction')


def retrieve(built, out, workers=4):
    out = new_output(out)
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError('workers must be 1..4')
    built = Path(built).resolve(); checked = check(built, 'build')
    config, identity, groups, records = (checked[k] for k in ('config', 'identity', 'groups', 'records'))
    databases = checked['summary']['database_sha256']; ledger = None
    try:
        _copy_stage_input(built, out, 'retrieve')
        runner, modules = frozen_modules(built, config, identity)
        core, runtime, _, _, pipeline, _ = modules
        ledger = runner.BudgetLedger(out / 'request-ledger.sqlite', RETRIEVAL_BUDGET)
        write(out / 'execution-plan.json', dict(stage='retrieve', arms={a: list(ablation.ARMS[a]) for a in ARMS},
            workers=workers, embedding_request_limit=RETRIEVAL_BUDGET, source10_embedding_requests=0,
            database_sha256=databases, loaded_core=str(core.__file__), core_sha256=sha(core.__file__),
            answer_requests=0, judge_requests=0, per_query_copy=True, input_database_hash_check='before_and_after'))
        # Construct adapters serially: configuration helpers temporarily change process environment.
        tasks = [(g['group_id'], r, arm, previous._build_embedder(core, config, 'dashscope') if arm == 'baseline'
                  else core.StubEmbeddingAdapter(config['embedding_dim'])) for g in groups for r in g['records'] for arm in ARMS]
        def execute(task):
            gid, record, arm, _ = task
            upper = len(baseline.history_holders(record['history'])) if arm == 'baseline' else 0
            reservation = ledger.reserve(arm + '/' + record['item_id'], 'query_embedding', upper)
            if reservation['state'] != 'reserved':
                raise runner.BudgetBlocked('query embedding budget exhausted')
            try:
                row = ablation.query_one(task, built, out, {'database_sha256': databases}, config, core, runtime, pipeline)
                row['reservation'] = reservation
                if row['status'] == 'error':
                    ledger.charge_upper(reservation['id']); row.update(charged_requests=upper, budget_unknown=True)
                else:
                    ledger.settle(reservation['id'], row['embedding_requests']); row['charged_requests'] = row['embedding_requests']
                write(out / arm / 'recalls' / (qa_helpers.text_sha(record['item_id']) + '.json'), row)
                return row
            except BaseException:
                ledger.charge_upper(reservation['id'])
                raise
        rows = {arm: [] for arm in ARMS}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for future in as_completed([pool.submit(execute, task) for task in tasks]):
                row = future.result(); rows[row['arm']].append(row)
                count = sum(len(rs) for rs in rows.values())
                if count % 20 == 0: print(f'retrieval terminals: {count}/266', flush=True)
        validate_retrieval_inventory(records, groups, rows, databases, config)
        snapshot = ledger.snapshot()
        if snapshot['reserved'] or snapshot['committed'] != sum(r['charged_requests'] for rs in rows.values() for r in rs):
            raise ValueError('retrieval ledger reconciliation failed')
        _check_input_stable(built, checked['seal_sha256'])
        if {gid: sha(built / 'runs' / gid / 'frozen.db') for gid in databases} != databases:
            raise ValueError('input databases changed during retrieval')
        for arm, receipts in rows.items():
            write(out / arm / 'summary.json', dict(rows=len(receipts), statuses=dict(Counter(r['status'] for r in receipts)),
                embedding_requests=sum(r['embedding_requests'] for r in receipts)))
        write(out / 'comparison.json', retrieval_comparison(records, rows))
        write(out / 'summary.json', dict(stage='retrieve', state='complete', questions=133, terminal_count=266,
            healthy_terminals=266, qa_gate='passed_technical_health', ledger=snapshot, embedding_requests=1336,
            source10_embedding_requests=0, database_sha256=databases))
        seal_output(out, 'retrieve')
        return read(out / 'summary.json')
    except BaseException as exc:
        _fail(out, 'retrieve', exc, ledger)
        raise


def validate_terminal_inventory(records, rows):
    expected = {(r['item_id'], arm, policy) for r in records for arm in ARMS for policy in POLICIES}
    observed = [(r.get('item_id'), r.get('arm'), r.get('policy')) for r in rows]
    if len(observed) != len(expected) or set(observed) != expected:
        raise ValueError('QA terminal inventory duplicate/missing')
    if any(r.get('terminal') is not True or r.get('fresh') is not True or r.get('status') not in baseline.TERMINAL_STATUSES
           or type(r.get('correct')) is not bool or (r['status'] != 'ok' and r['correct']) for r in rows):
        raise ValueError('QA terminal/fresh/failure credit mismatch')


def compare_scores(records, left, right, *, repetitions=None):
    result = qa_helpers.compare_scores(records, left, right, repetitions=repetitions)
    denominator = len(records)
    if denominator != 133:
        raise ValueError('fixed 133-question denominator required')
    result['denominator'] = denominator
    result['accuracy_gain'] = result['net_source10_minus_baseline'] / denominator
    result['baseline_accuracy'] = result['baseline_correct'] / denominator
    result['source10_accuracy'] = result['source10_correct'] / denominator
    result['ok_fraction'] = {arm: sum(r['status'] == 'ok' for r in rows) / denominator for arm, rows in zip(ARMS, (left, right))}
    result['eligible_for_expanded_development'] = bool(result['accuracy_gain'] >= .05
        and result['bootstrap']['ci95_percent'][0] > 0
        and result['common_normal_net_source10_minus_baseline'] > 0 and min(result['ok_fraction'].values()) >= .95)
    return result


def _breakdowns(records, rows):
    indexed = {arm: {r['item_id']: r for r in rows if r['arm'] == arm} for arm in ARMS}
    result = {}
    for dimension in ('network', 'question_type'):
        buckets = defaultdict(list)
        for record in records:
            label = baseline._network_id(record) if dimension == 'network' else str(record.get('query_type') or 'unknown')
            buckets[label].append(record['item_id'])
        result[dimension] = {label: dict(questions=len(ids), **{arm: dict(correct=sum(indexed[arm][i]['correct'] for i in ids),
            ok=sum(indexed[arm][i]['status'] == 'ok' for i in ids)) for arm in ARMS}) for label, ids in sorted(buckets.items())}
    return result


def judge_flip_audit(rows):
    # The entire stage fixes model, endpoint, retry, tokens and provider-default thinking.
    # Identical actual judge prompt bytes therefore mean identical observed judge inputs.
    grouped = defaultdict(list)
    for row in rows:
        if row.get('status') == 'ok' and 'judge' in row:
            grouped[row['judge_prompt']].append(row)
    repeated = [rs for rs in grouped.values() if len(rs) > 1]
    flips = [rs for rs in repeated if len({r['correct'] for r in rs}) > 1]
    return dict(grouping='exact UTF-8 judge_prompt under fixed stage judge configuration',
        identical_judge_input_groups=len(repeated), judge_flip_groups=len(flips),
        flips=[[{k: r[k] for k in ('item_id', 'arm', 'policy', 'correct', 'prompt_sha256')} for r in rs] for rs in flips])


def _qa_summary(records, rows, ledger):
    # Completion order and directory listing order must yield the same sealed audit.
    rows = sorted(rows, key=lambda r: (r['item_id'], r['arm'], r['policy']))
    comparisons = {}
    for policy in POLICIES:
        selected = [r for r in rows if r['policy'] == policy]
        pairs = {arm: [r for r in selected if r['arm'] == arm] for arm in ARMS}
        comparisons[policy] = compare_scores(records, pairs['baseline'], pairs['source10'])
        comparisons[policy]['breakdowns'] = _breakdowns(records, selected)
        for arm in ARMS:
            comparisons[policy][arm + '_summary'] = qa_helpers.statistics._summary(pairs[arm], policy, arm)
    usage = [r[stage].get('response', {}) for r in rows for stage in ('answer', 'judge') if isinstance(r.get(stage), dict)]
    return dict(stage='qa', state='complete', questions=133, terminal_count=len(rows), policies=comparisons,
        primary_endpoint='grounded_memory_v1_all_question_accuracy_gain',
        eligible_for_expanded_development=comparisons['grounded_memory_v1']['eligible_for_expanded_development'],
        automatic_promotion=False, ledger=ledger, status_counts=dict(Counter(r['status'] for r in rows)),
        native_requests=sum(r['native_attempt_count'] for r in rows), tokens=sum(r['tokens'] for r in rows),
        response_usage_count=len(usage), missing_token_usage_count=sum(not p.get('total_tokens') for p in usage),
        missing_token_usage_fraction=sum(not p.get('total_tokens') for p in usage) / len(usage) if usage else None,
        judge_flip_audit=judge_flip_audit(rows),
        strict_answer_prompt_judge_flip_audit=qa_helpers.judge_flip_audit(rows),
        interpretation='additional six development networks; source expansion plus statement removal; historical 57 not pooled as fresh')


def qa(contexts, out, workers=4):
    out = new_output(out)
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError('workers must be 1..4')
    contexts = Path(contexts).resolve(); checked = check(contexts, 'retrieve')
    config, identity, records = (checked[k] for k in ('config', 'identity', 'records'))
    ledger = None
    try:
        _copy_stage_input(contexts, out, 'qa')
        # Copy all input recall receipts so output seals bind exact context bytes, traces and provenance.
        for arm in ARMS:
            shutil.copytree(contexts / arm / 'recalls', out / 'input-recalls' / arm)
        runner, modules = frozen_modules(contexts, config, identity)
        recalls = {arm: {r['item_id']: r['recall'] for r in checked['rows'][arm]} for arm in ARMS}
        tasks = [qa_helpers.build_task(arm, policy, record, recalls[arm][record['item_id']], runner, config, modules)
                 for record in records for policy in POLICIES for arm in ARMS]
        bound = sum(1 + int(t['record'].get('answer_format', 'multiple_choice') != 'multiple_choice') for t in tasks)
        if len(tasks) != 532 or len({(t['item_id'], t['arm'], t['policy']) for t in tasks}) != 532 or bound != QA_BUDGET:
            raise ValueError('QA task/budget inventory mismatch')
        ledger = runner.BudgetLedger(out / 'request-ledger.sqlite', QA_BUDGET)
        write(out / 'execution-plan.json', dict(stage='qa', tasks=532, questions=133, http_budget=QA_BUDGET, workers=workers,
            arms=list(ARMS), policies=list(POLICIES), fresh=True, answer_model=config['answer_model'],
            answer_max_tokens=512, judge_max_tokens=64, answer_enable_thinking=False,
            judge_enable_thinking='provider_default_unset', max_retries=0, embedding_requests=0,
            bootstrap_seed=20260925, bootstrap_repetitions=100000, loaded_core=str(modules[0].__file__), core_sha256=sha(modules[0].__file__),
            tasks_binding=[{k: t[k] for k in ('item_id', 'arm', 'policy', 'prompt_sha256', 'context_sha256')} for t in tasks]))
        adapters = queue.Queue()
        for _ in range(workers): adapters.put(runner._make_native_adapters(modules[0], config))
        def execute(task):
            pair = adapters.get()
            try: return qa_helpers.run_task(task, out / 'answers', runner, modules, ledger, pair)
            finally: adapters.put(pair)
        rows = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for future in as_completed([pool.submit(execute, task) for task in tasks]):
                rows.append(future.result())
                if len(rows) % 20 == 0: print(f'QA terminals: {len(rows)}/532', flush=True)
        validate_terminal_inventory(records, rows)
        snapshot = ledger.snapshot()
        if snapshot['reserved'] or snapshot['remaining'] < 0 or snapshot['committed'] != sum(r['charged_requests'] for r in rows):
            raise ValueError('QA ledger reconciliation failed')
        _check_input_stable(contexts, checked['seal_sha256'])
        summary = _qa_summary(records, rows, snapshot)
        write(out / 'summary.json', summary)
        seal_output(out, 'qa')
        return summary
    except BaseException as exc:
        _fail(out, 'qa', exc, ledger)
        raise


def _read_receipts(out, pattern):
    rows = []
    for path in sorted(out.glob(pattern)):
        row = read(path)
        if path.stem != qa_helpers.text_sha(row['item_id']):
            raise ValueError('receipt filename/item binding mismatch')
        rows.append(row)
    return rows


def read_ledger(path, budget):
    """Inspect reservations without constructors, DDL, WAL creation or recovery."""
    path = Path(path)
    if not path.is_file() or any(Path(str(path) + suffix).exists() for suffix in ('-wal', '-shm')):
        raise ValueError('ledger absent or not sealed')
    with closing(sqlite3.connect('file:' + str(path) + '?mode=ro&immutable=1', uri=True)) as conn:
        rows = conn.execute('SELECT upper_bound,actual,state FROM reservations').fetchall()
    committed = reserved = charged = 0
    for upper, actual, state in rows:
        if not isinstance(upper, int) or upper < 0 or state not in ('reserved', 'settled', 'charged_upper'):
            raise ValueError('invalid ledger reservation')
        if state == 'reserved': reserved += upper
        elif state == 'charged_upper': charged += upper; committed += upper
        else:
            if not isinstance(actual, int) or not 0 <= actual <= upper:
                raise ValueError('invalid ledger settlement')
            committed += actual
    return dict(budget=budget, committed=committed, reserved=reserved, charged_upper=charged,
                remaining=budget - committed - reserved)


def check(out, expected_stage=None):
    """Read-only verification, including prior-stage identity and terminal inventories."""
    out = Path(out).resolve(); seal = verify_seal(out)
    stage = read(out / 'stage.json')
    if stage.get('stage') != seal['stage'] or stage['stage'] not in ('prepare', 'build', 'retrieve', 'qa'):
        raise ValueError('stage identity mismatch')
    if expected_stage is not None and stage['stage'] != expected_stage:
        raise ValueError('incorrect input stage')
    config, identity = _validate_identity(out)
    records, groups, manifest = _cohort_from_files(out)
    if read(out / 'sample.json') != records or read(out / 'groups.json') != groups or read(out / 'scope-manifest.json') != manifest:
        raise ValueError('canonical cohort/group identity mismatch')
    provenance = read(out / 'provenance.json')
    parent = Path(provenance['parent'])
    qa_helpers.verify_seal(parent)
    if sha(parent / 'seal.json') != provenance['parent_seal_sha256'] or sha(out / 'parent-seal.json') != provenance['parent_seal_sha256']:
        raise ValueError('parent seal identity mismatch')
    if read(parent / 'config.json') != read(out / 'parent-config.json') or sha(parent / 'sample.json') != sha(out / 'old-sample.json'):
        raise ValueError('parent protocol/old sample drift')
    if identity['frozen_files'] != read(parent / 'identity.json')['frozen_files']:
        raise ValueError('frozen runtime drift from parent')
    summary = read(out / 'summary.json')
    if summary.get('stage') != stage['stage'] or summary.get('state') != 'complete':
        raise ValueError('summary stage/state mismatch')
    result = dict(stage=stage['stage'], config=config, identity=identity, records=records, groups=groups,
                  summary=summary, seal_sha256=sha(out / 'seal.json'))
    if stage['stage'] == 'prepare':
        if stage.get('input') is not None or summary.get('external_requests') != 0:
            raise ValueError('prepare must be offline')
        return result
    predecessor = {'build': 'prepare', 'retrieve': 'build', 'qa': 'retrieve'}[stage['stage']]
    source = Path(stage['input']).resolve()
    if source == out or stage.get('input_stage') != predecessor:
        raise ValueError('invalid input stage chain')
    checked = check(source, predecessor)
    if checked['seal_sha256'] != stage.get('input_seal_sha256') or sha(out / 'input-seal.json') != checked['seal_sha256']:
        raise ValueError('stage input seal identity mismatch')
    if identity != checked['identity']:
        raise ValueError('stage input immutable identity mismatch')
    plan = read(out / 'execution-plan.json')
    if plan.get('stage') != stage['stage'] or plan.get('core_sha256') != CORE_SHA256:
        raise ValueError('execution plan stage/core mismatch')
    if sha(plan['loaded_core']) != CORE_SHA256 or Path(plan['loaded_core']).resolve().parent != source / 'frozen/python/starling':
        raise ValueError('execution loaded core identity mismatch')
    budget = {'build': BUILD_BUDGET, 'retrieve': RETRIEVAL_BUDGET, 'qa': QA_BUDGET}[stage['stage']]
    ledger = read_ledger(out / 'request-ledger.sqlite', budget)
    if ledger != summary.get('ledger') or ledger['reserved'] or ledger['remaining'] < 0:
        raise ValueError('stage ledger reconciliation mismatch')
    if stage['stage'] == 'build':
        health = {g['group_id']: validate_scope_health(g, out / 'runs' / g['group_id'] / 'frozen.db',
            read(out / 'runs' / g['group_id'] / 'scope.json')) for g in groups}
        if summary.get('health') != health or summary.get('database_sha256') != {g: h['database_sha256'] for g, h in health.items()}:
            raise ValueError('build health/database manifest mismatch')
        embedding = sum(read(out / 'runs' / g['group_id'] / 'scope.json')['embedding_request_count'] for g in groups)
        if ledger['charged_upper'] != 585 or ledger['committed'] != 585 + embedding or plan.get('workers') != 1:
            raise ValueError('build accounting/serial protocol mismatch')
    elif stage['stage'] == 'retrieve':
        rows = {arm: _read_receipts(out, arm + '/recalls/*.json') for arm in ARMS}
        databases = checked['summary']['database_sha256']
        validate_retrieval_inventory(records, groups, rows, databases, config)
        if plan.get('arms') != {a: list(ablation.ARMS[a]) for a in ARMS} or plan.get('embedding_request_limit') != 1336:
            raise ValueError('retrieval plan arm/budget mismatch')
        if summary.get('terminal_count') != 266 or summary.get('database_sha256') != databases or ledger['committed'] != 1336:
            raise ValueError('retrieval terminal/accounting summary mismatch')
        if read(out / 'comparison.json') != retrieval_comparison(records, rows):
            raise ValueError('retrieval comparison drift')
        result['rows'] = rows
    else:
        rows = _read_receipts(out, 'answers/*/*/*.json'); validate_terminal_inventory(records, rows)
        bindings = {(t['item_id'], t['arm'], t['policy']): t for t in plan.get('tasks_binding', [])}
        if len(bindings) != 532 or len(plan.get('tasks_binding', [])) != 532 or plan.get('http_budget') != 956:
            raise ValueError('QA task binding/budget mismatch')
        input_rows = {arm: {r['item_id']: r for r in checked['rows'][arm]} for arm in ARMS}
        for row in rows:
            key = row['item_id'], row['arm'], row['policy']
            binding = bindings[key]
            context = input_rows[row['arm']][row['item_id']]['recall']['block']
            if (row['prompt_sha256'] != qa_helpers.text_sha(row['prompt']) or row['context_sha256'] != qa_helpers.text_sha(context)
                or binding != {k: row[k] for k in ('item_id', 'arm', 'policy', 'prompt_sha256', 'context_sha256')}):
                raise ValueError('QA prompt/context input binding mismatch')
            if read(out / 'input-recalls' / row['arm'] / (qa_helpers.text_sha(row['item_id']) + '.json')) != input_rows[row['arm']][row['item_id']]:
                raise ValueError('QA input recall receipt drift')
        if ledger['committed'] != sum(r['charged_requests'] for r in rows) or summary != _qa_summary(records, rows, ledger):
            raise ValueError('QA terminal summary/accounting mismatch')
    # Read-only validation must not have modified any sealed file.
    verify_seal(out)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare', 'check', 'build', 'retrieve', 'qa'))
    parser.add_argument('--input', type=Path, help='上一阶段已封存目录；prepare 时是 R5.4 contexts')
    parser.add_argument('--out', type=Path, help='新目录，拒绝覆盖')
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args(argv)
    if args.stage == 'check':
        if args.input is None: parser.error('check requires --input')
        result = check(args.input)
        print(json.dumps(dict(state='validated', stage=result['stage'], questions=len(result['records']),
                             seal_sha256=result['seal_sha256']), ensure_ascii=False))
        return
    predecessor = {'build': 'prepare', 'retrieve': 'build', 'qa': 'retrieve'}
    source = args.input or (DEFAULT_PARENT if args.stage == 'prepare' else DEFAULT_WORK / predecessor[args.stage])
    destination = args.out or DEFAULT_WORK / args.stage
    if args.stage in ('retrieve', 'qa'):
        result = globals()[args.stage](source, destination, args.workers)
    else:
        result = globals()[args.stage](source, destination)
    print(json.dumps({k: v for k, v in result.items() if k not in ('policies', 'health')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
