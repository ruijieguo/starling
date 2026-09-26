#!/usr/bin/env python3
"""R6.6同库原生消融。Python仅冻结、编排、重放核验与事后统计。"""
from collections import Counter, defaultdict
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
_spec = importlib.util.spec_from_file_location('r66_previous', ROOT/'scripts/run_socialmem_r65_evaluate.py')
previous = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(previous)
e = previous.e
read, write, sha, inventory = e.read, e.write, e.sha, e.inventory
DEFAULT_ORIGIN = ROOT/'build/socialmem_20260926_r65_expanded/prepare'
ORIGIN_SEAL = 'f8acc40f45c19b83ddac2e5ff347f975520cbd5323a79e8a00c4f0fabc943784'
CORE = ROOT/'build/socialmem_20260926_r66_work/cmake/python/starling/_core.cpython-314-darwin.so'
CORE_SHA256 = 'd2c8dbafd1d531dd068999bd97e46c807ddb9f56be07ce8c244b539cac96a957'
ARMS = {'v9': ['evidence_profile_v9', 'sources', 20], 'v10': ['evidence_profile_v10', 'sources', 20]}
OWN_FILES = ('scripts/run_socialmem_r66_offline.py', 'tests/python/test_socialmem_r66_offline.py',
    'tests/cpp/test_source_retriever.cpp', 'tests/python/test_source_retriever_binding.py',
    'docs/superpowers/specs/2026-09-26-socialmem-r66-temporal-response-design.md',
    'docs/superpowers/plans/2026-09-26-socialmem-r66-temporal-response.md')


def load_inputs(origin):
    origin = Path(origin).resolve(); previous.parent.verify_pinned(origin, ORIGIN_SEAL)
    return dict(previous.check_prepared(origin), origin=origin)


def source_files():
    files = previous.source_files()
    native = read(ROOT/'build/socialmem_20260926_r66_work/native-build.json')
    if native['core_sha256'] != CORE_SHA256: raise ValueError('native build identity mismatch')
    for name, digest in native['source_files'].items():
        if sha(ROOT/name) != digest: raise ValueError('native build source drift: '+name)
        files[name] = digest
    files.update({name: sha(ROOT/name) for name in OWN_FILES})
    return files


def freeze_program(out):
    files = source_files()
    for name in files: e.builder.copy_file(ROOT/name, out/'source'/name)
    write(out/'program.json', dict(files=files, core_sha256=CORE_SHA256))


def verify_program(out, current=False):
    program = read(out/'program.json'); files = program.get('files', {})
    if (program.get('core_sha256') != CORE_SHA256 or files != inventory(out/'source')
        or not set(OWN_FILES).issubset(files)): raise ValueError('program identity/inventory mismatch')
    if current and files != source_files(): raise ValueError('execution program drift')


def verify_execution(out):
    verify_program(out)
    for name, digest in read(out/'program.json')['files'].items():
        if name.endswith('.py') and sha(ROOT/name) != digest:
            raise ValueError('execution program drift: '+name)


def seal_output(out, stage, state='complete'):
    if (out/'seal.json').exists(): raise ValueError('already sealed')
    write(out/'seal.json', dict(schema='r66-native-offline-v1', stage=stage, state=state, files=inventory(out)))


def verify_seal(out):
    seal = read(out/'seal.json'); actual = inventory(out); actual.pop('seal.json', None)
    if (seal.get('schema') != 'r66-native-offline-v1' or actual != seal.get('files')
        or seal.get('state') not in ('complete', 'incomplete')): raise ValueError('offline seal mismatch')
    return seal


def plan(data):
    checked = data['checked']
    return dict(questions=133, tasks=266, arms=ARMS, core_sha256=CORE_SHA256,
        origin_seal_sha256=ORIGIN_SEAL, database_sha256=checked['databases'],
        build=str(checked['built']), build_seal_sha256=checked['seal_sha256'],
        mode='sources', k=20, max_context_bytes=8000, source_dialogue_radius=1,
        query_time=checked['config']['query_time'], embedding_adapter='StubEmbeddingAdapter',
        expected_external_requests=0, public_anchors='post_hoc_diagnostic_only')


def frozen_inputs(data):
    checked = data['checked']
    return {'plan.json': plan(data), 'sample.json': checked['records'], 'groups.json': checked['groups'],
        'config.json': dict(checked['config'], core_sha256=CORE_SHA256),
        'scope-plans.json': checked['plans'], 'source-health.json': checked['summary']['health'],
        'provenance.json': e.provenance(checked)}


def runtime_inventory(data):
    files = inventory(data['checked']['prepared']/'frozen')
    cores = [name for name in files if name.startswith('python/starling/_core') and name.endswith('.so')]
    if len(cores) != 1: raise ValueError('expected single native runtime')
    files[cores[0]] = CORE_SHA256
    return files


def prepare_summary():
    return dict(stage='prepare', state='complete', questions=133, tasks=266, external_requests=0,
        core_sha256=CORE_SHA256, origin_seal_sha256=ORIGIN_SEAL)


def prepare(origin, out):
    out = e.builder.new_output(out); data = load_inputs(origin)
    if sha(CORE) != CORE_SHA256: raise ValueError('native core identity mismatch')
    source_files()
    out.mkdir(parents=True); freeze_program(out)
    write(out/'stage.json', dict(stage='prepare', origin=str(data['origin'])))
    for name, value in frozen_inputs(data).items(): write(out/name, value)
    shutil.copytree(data['origin']/'contexts', out/'historical-contexts')
    shutil.copyfile(data['origin']/'seal.json', out/'origin-seal.json')
    target = out/'native-runtime/frozen'
    shutil.copytree(data['checked']['prepared']/'frozen', target)
    native = next((target/'python/starling').glob('_core*.so')); shutil.copyfile(CORE, native)
    files = runtime_inventory(data)
    if inventory(target) != files: raise ValueError('copied runtime drift')
    write(out/'runtime-identity.json', dict(core_sha256=CORE_SHA256, frozen_files=files))
    summary = prepare_summary(); write(out/'summary.json', summary); seal_output(out, 'prepare')
    return summary


def check_prepared(out):
    seal = verify_seal(out); stage = read(out/'stage.json')
    if seal['stage'] != 'prepare' or stage.get('stage') != 'prepare' or seal['state'] != 'complete':
        raise ValueError('invalid prepare stage')
    verify_program(out); data = load_inputs(stage['origin'])
    for name, value in frozen_inputs(data).items():
        if not e.builder.identical(read(out/name), value): raise ValueError('frozen input drift: '+name)
    expected = runtime_inventory(data)
    if (read(out/'runtime-identity.json') != dict(core_sha256=CORE_SHA256, frozen_files=expected)
        or inventory(out/'native-runtime/frozen') != expected
        or inventory(out/'historical-contexts') != inventory(data['origin']/'contexts')
        or sha(out/'origin-seal.json') != ORIGIN_SEAL
        or read(out/'summary.json') != prepare_summary()): raise ValueError('runtime/context/summary drift')
    return dict(data, summary=prepare_summary(), seal_sha256=sha(out/'seal.json'))


def verify_databases(p):
    for gid, digest in p['database_sha256'].items():
        path = Path(p['build'])/'runs'/gid/'frozen.db'
        if (sha(path) != digest or any(Path(str(path)+s).exists() for s in ('-wal', '-shm'))):
            raise ValueError('database drift/live database: '+gid)


def worker(prepared, out):
    """独立进程仅加载新核心；不调用会导入旧核心的历史链核验。"""
    seal = verify_seal(prepared); seal_digest = sha(prepared/'seal.json'); verify_execution(prepared)
    if seal['stage'] != 'prepare' or seal['state'] != 'complete': raise ValueError('worker input stage mismatch')
    p = read(prepared/'plan.json'); config = read(prepared/'config.json')
    identity = read(prepared/'runtime-identity.json')
    if (p['core_sha256'] != CORE_SHA256 or p['arms'] != ARMS or config['core_sha256'] != CORE_SHA256
        or identity['core_sha256'] != CORE_SHA256
        or inventory(prepared/'native-runtime/frozen') != identity['frozen_files']):
        raise ValueError('worker native identity mismatch')
    verify_databases(p)
    core, runtime, _, _, pipeline, _ = e.baseline._frozen_imports(prepared/'native-runtime', config, identity)
    scopes = read(prepared/'scope-plans.json')['scopes']; health = read(prepared/'source-health.json')
    e.ablation.ARMS = ARMS
    count = 0
    for group in read(prepared/'groups.json'):
        gid = group['group_id']
        for record in group['records']:
            for arm in ARMS:
                row = e.ablation.query_one((gid, record, arm, core.StubEmbeddingAdapter(config['embedding_dim'])),
                    Path(p['build']), out, p, config, core, runtime, pipeline)
                if not e.ablation.healthy_embedding(row): raise ValueError('unhealthy native row: '+str(row.get('error')))
                recall = row['recall']
                if (recall['statement_ids'] or recall['statement_context_bytes'] != 0
                    or recall['source_context_bytes'] != recall['context_bytes']):
                    raise ValueError('source-only byte/count drift')
                e.validate_context(core, record, row, scopes[gid], health[gid]['source_engrams'], lambda _: None)
                count += 1
    if count != 266: raise ValueError('worker task inventory mismatch')
    verify_databases(p)
    verify_seal(prepared)
    if sha(prepared/'seal.json') != seal_digest: raise ValueError('worker input changed during retrieval')


def invoke_worker(prepared, out):
    result = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), '_worker',
        '--input', str(prepared), '--out', str(out)], capture_output=True, text=True)
    if result.returncode: raise ValueError('native worker failed: '+result.stderr[-5000:])


def read_rows(out, records, databases):
    expected = {r['item_id'] for r in records}; rows = {}; e.ablation.ARMS = ARMS
    for arm in ARMS:
        files = list((out/arm/'recalls').glob('*.json')); indexed = {}
        for path in files:
            row = read(path); item = row.get('item_id')
            if item not in expected or item in indexed or path.name != e.text_sha(item)+'.json':
                raise ValueError('unknown/duplicate/misnamed context')
            gid = row.get('group_id')
            if gid not in databases: raise ValueError('unknown context database')
            e.ablation.validate_row(row, arm, databases[gid], CORE_SHA256, 8000)
            if not e.ablation.healthy_embedding(row): raise ValueError('unhealthy context')
            indexed[item] = row
        if set(indexed) != expected: raise ValueError('missing context rows')
        rows[arm] = indexed
    return rows


def summarize(out, prepared):
    records = read(prepared/'sample.json'); p = read(prepared/'plan.json')
    rows = read_rows(out, records, p['database_sha256']); totals = {a: Counter() for a in ARMS}
    types = {a: defaultdict(Counter) for a in ARMS}; networks = {a: defaultdict(Counter) for a in ARMS}
    historical = {read(f)['item_id']: read(f) for f in (prepared/'historical-contexts').glob('*.json')}
    details = []; controls = 0
    for record in records:
        item = record['item_id']; gold = {a['turn_id'] for a in record['source'].get('evidence_anchors', [])}
        recalls = {a: rows[a][item]['recall'] for a in ARMS}
        selected = {a: {s['turn_id'] for s in recalls[a]['source_refs']} for a in ARMS}
        for arm in ARMS:
            hits = len(selected[arm] & gold)
            c = Counter(questions=1, anchors=len(gold), anchor_hit=hits,
                all_anchors_hit=int(bool(gold) and hits == len(gold)), zero_anchor_hit=int(bool(gold) and not hits))
            totals[arm].update(c); types[arm][record['query_type']].update(c)
            networks[arm][record['source']['network_id']].update(c)
        controls += any(recalls['v9'][key] != historical[item]['recall'][key] for key in ('source_refs', 'block'))
        details.append(dict(item_id=item, query_type=record['query_type'], network_id=record['source']['network_id'],
            context_changed=recalls['v9']['block'] != recalls['v10']['block'],
            source_set_changed=selected['v9'] != selected['v10'],
            gained_anchors=sorted(gold & (selected['v10']-selected['v9'])),
            lost_anchors=sorted(gold & (selected['v9']-selected['v10'])),
            added_sources=sorted(selected['v10']-selected['v9']), removed_sources=sorted(selected['v9']-selected['v10'])))
    changed = sum(r['context_changed'] for r in details)
    gate = ('blocked_control_drift' if controls else 'blocked_unchanged_context' if not changed
        else 'blocked_anchor_recall' if totals['v10']['anchor_hit'] < totals['v9']['anchor_hit'] else 'passed')
    return dict(state='complete', questions=133, healthy_contexts=266, external_requests=0, new_embedding_requests=0,
        control_mismatches=controls, changed_contexts=changed, qa_gate=gate, qa_executed=False,
        arms={a: dict(totals[a], query_type=dict(types[a]), network=dict(networks[a])) for a in ARMS}, rows=details)


def run(prepared, out):
    out = e.builder.new_output(out); prepared = Path(prepared).resolve(); data = check_prepared(prepared)
    verify_program(prepared, current=True)
    shutil.copytree(prepared, out, ignore=shutil.ignore_patterns('seal.json', 'stage.json', 'summary.json'))
    write(out/'stage.json', dict(stage='run', input=str(prepared), input_seal_sha256=data['seal_sha256']))
    try:
        invoke_worker(prepared, out); summary = summarize(out, prepared)
        verify_program(prepared, current=True); verify_seal(prepared); verify_databases(read(prepared/'plan.json'))
        write(out/'summary.json', summary); seal_output(out, 'run')
    except BaseException as exc:
        write(out/'failure.json', dict(exception=f'{type(exc).__name__}: {exc}'))
        seal_output(out, 'run', 'incomplete'); raise
    return summary


def check(out):
    out = Path(out).resolve(); seal = verify_seal(out)
    if seal['stage'] == 'prepare': return check_prepared(out)
    if seal['stage'] != 'run' or seal['state'] != 'complete': raise ValueError('incomplete/unknown offline stage')
    stage = read(out/'stage.json'); prepared = Path(stage['input']).resolve(); data = check_prepared(prepared)
    if stage != dict(stage='run', input=str(prepared), input_seal_sha256=data['seal_sha256']):
        raise ValueError('run input binding drift')
    for name, digest in inventory(prepared).items():
        if name not in ('seal.json', 'stage.json', 'summary.json') and sha(out/name) != digest:
            raise ValueError('run frozen input drift: '+name)
    summary = summarize(out, prepared)
    if read(out/'summary.json') != summary: raise ValueError('offline summary drift')
    with tempfile.TemporaryDirectory(prefix='socialmem-r66-replay-') as temp:
        replay = Path(temp); invoke_worker(prepared, replay)
        for arm in ARMS:
            if inventory(out/arm) != inventory(replay/arm): raise ValueError('native replay context drift: '+arm)
    verify_seal(out)
    return dict(data, summary=summary, seal_sha256=sha(out/'seal.json'))


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('stage', choices=['prepare', 'run', 'check', '_worker'])
    parser.add_argument('--input', type=Path, default=DEFAULT_ORIGIN); parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.stage == '_worker': worker(args.input.resolve(), args.out.resolve()); return
    result = check(args.out) if args.stage == 'check' else globals()[args.stage](args.input, args.out)
    print(json.dumps(result.get('summary', result), ensure_ascii=False, indent=2, default=str))


if __name__ == '__main__': main()
