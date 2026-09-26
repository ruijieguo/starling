#!/usr/bin/env python3
"""R6.8原生来源选择：Python仅冻结、编排、账本核验和事后统计。"""
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
import argparse
import importlib.util
import json
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
from types import ModuleType

ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
_spec=importlib.util.spec_from_file_location('r68_previous',ROOT/'scripts/run_socialmem_r65_evaluate.py')
previous=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(previous)
e=previous.e
read,write,sha,inventory=e.read,e.write,e.sha,e.inventory
DEFAULT_ORIGIN=ROOT/'build/socialmem_20260926_r65_expanded/prepare'
ORIGIN_SEAL='f8acc40f45c19b83ddac2e5ff347f975520cbd5323a79e8a00c4f0fabc943784'
NATIVE=ROOT/'build/socialmem_20260926_r68_work/native-build.json'
CORE=ROOT/read(NATIVE)['core']
CORE_SHA256=read(NATIVE)['core_sha256']
ARMS={'v9':['evidence_profile_v9','sources',20],'selector':['semantic_source_selection_json_v1','sources',20]}
BUDGET=133
OWN_FILES=('scripts/run_socialmem_r68_selection.py','tests/python/test_socialmem_r68_selection.py',
    'docs/superpowers/specs/2026-09-26-socialmem-r68-structured-selection-design.md',
    'docs/superpowers/plans/2026-09-26-socialmem-r68-structured-selection.md')


def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))


@contextmanager
def historical_dependencies(origin):
    """只固定历史源码枚举的时间范围；原始验封和所有历史校验函数继续执行。"""
    previous.parent.verify_pinned(origin,ORIGIN_SEAL)
    files=read(origin/'program.json')['files']
    if files!=inventory(origin/'source'):raise ValueError('historical archived program mismatch')
    for name,digest in files.items():
        if name.endswith('.py') and sha(ROOT/name)!=digest:raise ValueError('historical executed Python drift: '+name)
    pending=[previous];seen=set();changed=[]
    try:
        while pending:
            module=pending.pop()
            if id(module) in seen:continue
            seen.add(id(module))
            for value in vars(module).values():
                if isinstance(value,ModuleType) and str(getattr(value,'__file__','')).startswith(str(ROOT/'scripts')):
                    pending.append(value)
            discover=getattr(module,'source_paths',None)
            if callable(discover):
                def scoped(original=discover):
                    return [p for p in original() if p.relative_to(ROOT).as_posix() in files]
                changed.append((module,discover));module.source_paths=scoped
        yield
    finally:
        for module,discover in reversed(changed):module.source_paths=discover


def load_inputs(origin):
    origin=Path(origin).resolve();previous.parent.verify_pinned(origin,ORIGIN_SEAL)
    with historical_dependencies(origin):
        return dict(previous.check_prepared(origin),origin=origin)


def source_files():
    native=read(NATIVE)
    if native['core_sha256']!=CORE_SHA256 or sha(CORE)!=CORE_SHA256:raise ValueError('native build identity drift')
    files=previous.source_files()
    for name,digest in native['source_files'].items():
        if sha(ROOT/name)!=digest:raise ValueError('native source drift: '+name)
        files[name]=digest
    files.update({name:sha(ROOT/name) for name in OWN_FILES})
    return files


def freeze_program(out):
    files=source_files()
    for name in files:e.builder.copy_file(ROOT/name,out/'source'/name)
    write(out/'program.json',dict(files=files,core_sha256=CORE_SHA256))
    shutil.copyfile(NATIVE,out/'native-build.json')


def verify_program(out,current=False):
    p=read(out/'program.json');files=p.get('files',{})
    if p.get('core_sha256')!=CORE_SHA256 or files!=inventory(out/'source') or not set(OWN_FILES).issubset(files):
        raise ValueError('program identity/inventory drift')
    if current and files!=source_files():raise ValueError('current execution program drift')
    for name,digest in files.items():
        if name.endswith('.py') and sha(ROOT/name)!=digest:raise ValueError('executed Python drift: '+name)
    native=read(out/'native-build.json')
    if native['core_sha256']!=CORE_SHA256 or any(files.get(n)!=h for n,h in native['source_files'].items()):
        raise ValueError('native build/program mismatch')


def seal_output(out,stage,state='complete'):
    if (out/'seal.json').exists():raise ValueError('already sealed')
    write(out/'seal.json',dict(schema='r68-source-selection-v1',stage=stage,state=state,files=inventory(out)))


def verify_seal(out):
    seal=read(out/'seal.json');actual=inventory(out);actual.pop('seal.json',None)
    if seal.get('schema')!='r68-source-selection-v1' or seal.get('state') not in ('complete','incomplete') or seal.get('files')!=actual:
        raise ValueError('source selection seal mismatch')
    return seal


def plan(data):
    checked=data['checked'];config=checked['config']
    return dict(questions=133,selection_http_budget=133,total_http_budget=611,qa_http_budget=478,
        origin_seal_sha256=ORIGIN_SEAL,core_sha256=CORE_SHA256,answer_core_sha256=e.CORE_SHA256,
        build=str(checked['built']),database_sha256=checked['databases'],arms=ARMS,
        mode='sources',k=20,max_context_bytes=8000,pool_limit=1000,pool_max_context_bytes=131072,
        query_time=config['query_time'],embedding_adapter='StubEmbeddingAdapter',new_embedding_requests=0,
        answer_model='qwen3.8-27b',selection_output_mode='json_object',selection_output_contract='source_selection_v1',selection_max_tokens=512,selection_enable_thinking=False,
        max_retries=0,timeout_ms=120000,public_anchors='post_hoc_diagnostic_only')


def frozen_inputs(data):
    checked=data['checked']
    return {'plan.json':plan(data),'sample.json':checked['records'],'groups.json':checked['groups'],
        'config.json':dict(checked['config'],core_sha256=CORE_SHA256),
        'scope-plans.json':checked['plans'],'source-health.json':checked['summary']['health'],
        'provenance.json':e.provenance(checked)}


def runtime_inventory(data):
    files=inventory(data['checked']['prepared']/'frozen')
    cores=[n for n in files if n.startswith('python/starling/_core') and n.endswith('.so')]
    if len(cores)!=1:raise ValueError('single native core required')
    files[cores[0]]=CORE_SHA256
    return files


def native_modules(prepared):
    identity=read(prepared/'runtime-identity.json');config=read(prepared/'config.json')
    if identity['core_sha256']!=CORE_SHA256 or inventory(prepared/'native-runtime/frozen')!=identity['frozen_files']:
        raise ValueError('native runtime drift')
    return e.baseline._frozen_imports(prepared/'native-runtime',config,identity)


def verify_databases(p):
    for gid,digest in p['database_sha256'].items():
        path=Path(p['build'])/'runs'/gid/'frozen.db'
        if sha(path)!=digest or any(Path(str(path)+s).exists() for s in ('-wal','-shm')):raise ValueError('database drift: '+gid)


def pool_rows(out):
    rows={}
    for path in (out/'pools').glob('*.json'):
        row=read(path);item=row.get('item_id')
        if not isinstance(item,str) or item in rows or path.name!=e.text_sha(item)+'.json':raise ValueError('duplicate/misnamed pool')
        rows[item]=row
    return rows


def pool_worker(prepared,out):
    verify_program(prepared);p=read(prepared/'plan.json');verify_databases(p)
    core,runtime,_,_,pipeline,_=native_modules(prepared);config=read(prepared/'config.json')
    scopes=read(prepared/'scope-plans.json')['scopes'];health=read(prepared/'source-health.json')
    validator=e.ablation.load(ROOT/'scripts/run_socialmem_r54_ablation.py','r68_pool_ablation');validator.ARMS=ARMS
    for group in read(prepared/'groups.json'):
        gid=group['group_id']
        for record in group['records']:
            emb=core.StubEmbeddingAdapter(config['embedding_dim'])
            control=validator.query_one((gid,record,'v9',emb),Path(p['build']),out,p,config,core,runtime,pipeline)
            if not validator.healthy_embedding(control):raise ValueError('unhealthy control: '+str(control.get('error')))
            with tempfile.TemporaryDirectory(prefix='r68-pool-') as temp:
                db=Path(temp)/'query.db';shutil.copyfile(Path(p['build'])/'runs'/gid/'frozen.db',db)
                rt=runtime._build_local_store_sqlite_runtime(db);rt.start()
                try:
                    index=core.SqliteBlobVectorIndex();semantic=core.SemanticRetriever(rt.adapter,emb,index)
                    observer=core.ObserverRetriever(rt.adapter,semantic);q=core.ObserverQuery()
                    q.tenant_id='default';q.allowed_holders=e.baseline.history_holders(record['history'])
                    q.question=record['question'];q.as_of_iso8601=config['query_time'];q.include_unknown_time=config['include_unknown_time']
                    raw=core.collect_selection_pool(observer,q);pool=json.loads(raw)
                    prompt=core.source_selection_prompt(q.question,raw)
                finally:
                    stop=getattr(rt,'stop',None)
                    if callable(stop):stop()
            for recall in (control['recall'],pool):
                e.validate_context(core,record,dict(recall=recall),scopes[gid],health[gid]['source_engrams'],lambda _:None)
            row=dict(item_id=record['item_id'],group_id=gid,question=record['question'],holders=q.allowed_holders,
                pool=pool,prompt=prompt,prompt_sha256=e.text_sha(prompt),pool_sha256=e.text_sha(canonical(pool)),
                database_sha256=p['database_sha256'][gid],core_sha256=CORE_SHA256)
            write(out/'pools'/(e.text_sha(row['item_id'])+'.json'),row)
    verify_databases(p)


def invoke_worker(stage,prepared,out,workers=4,receipts=None):
    command=[sys.executable,'-B',str(Path(__file__).resolve()),stage,'--input',str(prepared),'--out',str(out),'--workers',str(workers)]
    if receipts is not None:command+=['--receipts',str(receipts)]
    result=subprocess.run(command,capture_output=True,text=True)
    if result.returncode:raise ValueError('native worker failed: '+result.stderr[-5000:])


def preparation_summary(out):
    records=read(out/'sample.json');p=read(out/'plan.json');rows=pool_rows(out)
    historical={read(f)['item_id']:read(f) for f in (out/'historical-contexts').glob('*.json')}
    controls=read_rows(out,records,p['database_sha256'],arms=('v9',))['v9']
    expected={r['item_id'] for r in records}
    if len(records)!=133 or set(rows)!=expected or set(historical)!=expected:raise ValueError('pool/history cohort inventory mismatch')
    mismatches=0;sizes=[];complete=0
    groups={r['item_id']:g['group_id'] for g in read(out/'groups.json') for r in g['records']}
    for record in records:
        item=record['item_id'];row=rows[item];pool=row['pool'];gid=groups[item]
        if (row['question']!=record['question'] or row['holders']!=e.baseline.history_holders(record['history'])
            or row['group_id']!=gid or row['database_sha256']!=p['database_sha256'][gid] or row['core_sha256']!=CORE_SHA256
            or row['prompt_sha256']!=e.text_sha(row['prompt']) or row['pool_sha256']!=e.text_sha(canonical(pool))):
            raise ValueError('pool identity/prompt binding mismatch')
        if (pool['source_count']!=pool['source_diagnostics']['eligible_sources'] or pool['source_count']>1000
            or pool['context_bytes']!=len(pool['block'].encode()) or pool['context_bytes']>131072):raise ValueError('incomplete pool')
        complete+=1;sizes.append(pool['source_count'])
        mismatches+=any(controls[item]['recall'][key]!=historical[item]['recall'][key] for key in ('source_refs','block'))
    if mismatches:raise ValueError('historical control drift')
    return dict(stage='prepare',state='complete',questions=133,pool_count=len(rows),complete_pools=complete,
        control_mismatches=mismatches,min_pool_count=min(sizes),max_pool_count=max(sizes),
        external_requests=0,new_embedding_requests=0,core_sha256=CORE_SHA256)


def read_rows(out,records,databases,arms=None):
    expected={r['item_id'] for r in records};result={}
    validator=e.ablation.load(ROOT/'scripts/run_socialmem_r54_ablation.py','r68_context_validator');validator.ARMS=ARMS
    for arm in arms or ARMS:
        indexed={}
        for path in (out/arm/'recalls').glob('*.json'):
            row=read(path);item=row.get('item_id');gid=row.get('group_id')
            if item not in expected or item in indexed or path.name!=e.text_sha(item)+'.json' or gid not in databases:
                raise ValueError('context inventory mismatch')
            validator.validate_row(row,arm,databases[gid],CORE_SHA256,8000)
            if arm=='v9' and not validator.healthy_embedding(row):raise ValueError('unhealthy v9')
            indexed[item]=row
        if set(indexed)!=expected:raise ValueError('missing contexts')
        result[arm]=indexed
    return result


def prepare(origin,out):
    out=e.builder.new_output(out);data=load_inputs(origin);out.mkdir(parents=True);freeze_program(out)
    write(out/'stage.json',dict(stage='prepare',origin=str(data['origin'])))
    for name,value in frozen_inputs(data).items():write(out/name,value)
    shutil.copytree(data['origin']/'contexts',out/'historical-contexts')
    shutil.copyfile(data['origin']/'seal.json',out/'origin-seal.json')
    target=out/'native-runtime/frozen'
    shutil.copytree(data['checked']['prepared']/'frozen',target,ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copyfile(CORE,next((target/'python/starling').glob('_core*.so')))
    files=runtime_inventory(data)
    if inventory(target)!=files:raise ValueError('copied runtime drift')
    write(out/'runtime-identity.json',dict(core_sha256=CORE_SHA256,frozen_files=files))
    try:
        invoke_worker('_pool_worker',out,out);summary=preparation_summary(out)
        write(out/'summary.json',summary);seal_output(out,'prepare')
    except BaseException as exc:
        write(out/'failure.json',dict(exception=f'{type(exc).__name__}: {exc}'));seal_output(out,'prepare','incomplete');raise
    return summary


def check_prepared(out,replay=True):
    out=Path(out).resolve();seal=verify_seal(out);stage=read(out/'stage.json')
    if seal['stage']!='prepare' or seal['state']!='complete' or stage.get('stage')!='prepare':raise ValueError('invalid prepare stage')
    verify_program(out);data=load_inputs(stage['origin'])
    for name,value in frozen_inputs(data).items():
        if not e.builder.identical(read(out/name),value):raise ValueError('frozen input drift: '+name)
    if (inventory(out/'native-runtime/frozen')!=runtime_inventory(data) or
        read(out/'runtime-identity.json')!=dict(core_sha256=CORE_SHA256,frozen_files=runtime_inventory(data)) or
        inventory(out/'historical-contexts')!=inventory(data['origin']/'contexts') or sha(out/'origin-seal.json')!=ORIGIN_SEAL):
        raise ValueError('frozen runtime/control drift')
    summary=preparation_summary(out)
    if read(out/'summary.json')!=summary:raise ValueError('prepare summary drift')
    if replay:
        with tempfile.TemporaryDirectory(prefix='r68-pool-replay-') as temp:
            replay_path=Path(temp);invoke_worker('_pool_worker',out,replay_path)
            for name in ('pools','v9'):
                if inventory(out/name)!=inventory(replay_path/name):raise ValueError('native pool/control replay drift')
    verify_seal(out)
    return dict(data,summary=summary,prepared_selection=out,seal_sha256=sha(out/'seal.json'))


def make_adapter(core,config):
    with e.baseline._provider_environment(config['answer_key_env'],config['answer_endpoint']):
        c=core.OpenAIAdapterConfig.from_env()
        c.model='qwen3.8-27b';c.max_tokens=512;c.enable_thinking=False;c.max_retries=0;c.timeout_ms=120000
        c.json_object_output=True
        return core.OpenAIAdapter(c)


def selection_binding(task):
    return dict({key:task[key] for key in ('item_id','group_id','question','holders','prompt_sha256','pool_sha256','database_sha256','core_sha256')},
        selection_output_mode='json_object',selection_output_contract='source_selection_v1')


def empty_context(core,task):
    return json.loads(core.apply_source_selection(task['question'],canonical(task['pool']),'{"source_ids":[]}'))


def selection_verdict(core,task,native):
    invoked=native['invoked'];payload=native.get('response')
    if type(invoked) is not bool or type(native['budget_unknown']) is not bool:raise ValueError('invalid native invocation evidence')
    cost=e.raw_accounting([payload] if invoked else [],missing_response=native['budget_unknown'],native=(core,))
    if invoked and cost['observed_http_attempts']:
        response=payload['response']
        expected=dict(output_mode='json_object',output_contract='source_selection_v1',
            schema_sha256=core.structured_output_schema_sha256(core.OutputContractKind.SourceSelectionV1))
        if any(response.get(k)!=v for k,v in expected.items()):
            raise ValueError('structured selection response contract identity mismatch')
    recall=empty_context(core,task);valid=False
    if not invoked:
        if task['pool']['source_count']!=0:raise ValueError('nonempty pool lacks invocation')
        valid=True
    elif cost['healthy_http']:
        try:
            recall=json.loads(core.apply_source_selection(task['question'],canonical(task['pool']),payload['raw_xml']))
            valid=True
        except ValueError:pass
    # native ok可先于HTTP用量审计为真；最终健康状态必须同时满足两层合同。
    if valid and (native['ok'] is not True or json.loads(native['recall_json'])!=recall):
        raise ValueError('native selection replay/result mismatch')
    return ('ok' if valid else 'error'),(recall if valid else empty_context(core,task)),cost


def execute_selection(task,out,core,ledger,adapter):
    scope='selector/'+task['item_id'];binding=selection_binding(task)
    reservation=ledger.reserve(scope,'source_selection',int(task['pool']['source_count']>0))
    if reservation.get('state')!='reserved':raise ValueError('selection budget exhausted')
    e.write_started(out,scope,'source_selection',reservation,binding,False)
    invoked=bool(task['pool']['source_count']);e.write_started(out,scope,'source_selection',reservation,binding,invoked)
    result=core.select_sources_structured(task['question'],canonical(task['pool']),adapter)
    native=dict(ok=result.ok,invoked=result.invoked,budget_unknown=result.budget_unknown,error=result.error,
        prompt=result.prompt,recall_json=result.recall_json,response=e.baseline._response_payload(result.response))
    if native['invoked']!=invoked or native['prompt']!=task['prompt']:raise ValueError('native selection prompt/invocation drift')
    status,recall,cost=selection_verdict(core,task,native)
    row=dict(binding,terminal=True,status=status,recall=recall,native=native,native_invoked=invoked,
        reservation=reservation,accounting=cost,charged_requests=e.charge_for(reservation['upper_bound'],cost['observed_http_attempts'],cost['local_attempt_count_unknown']))
    write(out/'selections'/(e.text_sha(task['item_id'])+'.json'),row)
    e.settle(ledger,reservation,cost['observed_http_attempts'],cost['local_attempt_count_unknown'])
    return row


def audit_selection(task,row,out,core):
    binding=selection_binding(task)
    if any(row.get(k)!=v for k,v in binding.items()) or row.get('terminal') is not True:raise ValueError('selection terminal task drift')
    native=row['native'];scope='selector/'+task['item_id'];reservation=row['reservation']
    if (native['prompt']!=task['prompt'] or row['native_invoked']!=native['invoked']
        or reservation['state']!='reserved' or reservation['upper_bound']!=int(task['pool']['source_count']>0)):
        raise ValueError('selection prompt/reservation mismatch')
    if core.source_selection_prompt(task['question'],canonical(task['pool']))!=native['prompt']:raise ValueError('native prompt drift')
    status,recall,cost=selection_verdict(core,task,native)
    charge=e.charge_for(reservation['upper_bound'],cost['observed_http_attempts'],cost['local_attempt_count_unknown'])
    if (row['status']!=status or row['recall']!=recall or row['accounting']!=cost or row['charged_requests']!=charge):
        raise ValueError('selection raw response/verdict/accounting mismatch')
    e.validate_started(out,scope,'source_selection',reservation,binding,row['native_invoked'])
    return e.reservation_evidence(row,scope,'source_selection',int(task['pool']['source_count']>0),
        cost['observed_http_attempts'],cost['local_attempt_count_unknown'])


def selection_row(task,row):
    return dict(item_id=task['item_id'],group_id=task['group_id'],arm='selector',strategy=ARMS['selector'][0],mode='sources',k=20,
        holders=task['holders'],database_sha256=task['database_sha256'],core_sha256=CORE_SHA256,
        status=row['status'],terminal=True,embedding_requests=0,recall=row['recall'],selection_status=row['status'])


def summarize_selection(prepared,out,core,partial=False):
    tasks=pool_rows(prepared);rows={};reservations=[];costs=[];errors=[]
    for path in (out/'selections').glob('*.json'):
        row=read(path);item=row.get('item_id')
        try:
            if item not in tasks or item in rows or path.name!=e.text_sha(item)+'.json':raise ValueError('unknown/duplicate terminal')
            reservations.append(audit_selection(tasks[item],row,out,core));rows[item]=row;costs.append(row['accounting'])
        except (ValueError,TypeError,KeyError,OSError) as exc:errors.append(f'{item}: {exc}')
    ledger_rows=e.ledger_rows(out/'request-ledger.sqlite',BUDGET);ledger=e.previous.read_ledger(out/'request-ledger.sqlite',BUDGET)
    starts={p.name for p in (out/'started').glob('*.json')};expected_starts={e.text_sha(r['scope'])+'.json' for r in reservations}
    complete=set(rows)==set(tasks) and not errors and starts==expected_starts
    if not partial:
        if not complete:raise ValueError('selection terminal inventory/audit failed: '+str(errors[:2]))
        e.reconcile_ledger(out/'request-ledger.sqlite',BUDGET,reservations)
    else:
        actual={r['id']:r for r in ledger_rows}
        for reservation in reservations:
            if actual.get(reservation['id'])!=reservation:errors.append('partial terminal/ledger mismatch')
    unknown=bool(errors or any(r['state']=='reserved' for r in ledger_rows) or starts-expected_starts or any(c['local_attempt_count_unknown'] for c in costs))
    usage_complete=not unknown and all(c['usage_complete'] for c in costs)
    healthy=sum(r['status']=='ok' for r in rows.values())
    summary=dict(stage='select',state='incomplete' if partial else 'complete',questions=133,terminal_count=len(rows),
        healthy_selections=healthy,selection_errors=len(rows)-healthy,terminal_inventory_complete=complete,
        observed_http_attempts=sum(c['observed_http_attempts'] for c in costs),
        known_tokens=sum(c['known_tokens'] for c in costs),total_tokens=sum(c['known_tokens'] for c in costs) if usage_complete else None,
        usage_complete=usage_complete,missing_token_usage=sum(c['missing_token_usage'] for c in costs),
        local_attempt_count_unknown=unknown,remote_execution_unknown=unknown or any(c['remote_execution_unknown'] for c in costs),
        ledger=ledger,audit_errors=errors,unresolved_reservations=[r['scope'] for r in ledger_rows if r['state']=='reserved'],
        new_embedding_requests=0,control_mismatches=0,qa_executed=False,automatic_promotion=False,core_sha256=CORE_SHA256)
    if partial:return summary
    totals={a:Counter() for a in ARMS};types={a:defaultdict(Counter) for a in ARMS};details=[]
    records=read(prepared/'sample.json');p=read(prepared/'plan.json')
    controls=read_rows(prepared,records,p['database_sha256'],arms=('v9',))['v9']
    for record in records:
        item=record['item_id'];gold={a['turn_id'] for a in record['source'].get('evidence_anchors',[])}
        chosen={'v9':controls[item]['recall'],'selector':rows[item]['recall']}
        selected={a:{r['turn_id'] for r in chosen[a]['source_refs']} for a in ARMS}
        for arm in ARMS:
            counts=Counter(questions=1,anchors=len(gold),anchor_hit=len(gold&selected[arm]))
            totals[arm].update(counts);types[arm][record['query_type']].update(counts)
        details.append(dict(item_id=item,query_type=record['query_type'],network_id=record['source']['network_id'],
            status=rows[item]['status'],context_changed=chosen['v9']['block']!=chosen['selector']['block'],
            gained_anchors=sorted(gold&(selected['selector']-selected['v9'])),lost_anchors=sorted(gold&(selected['v9']-selected['selector'])),
            added_sources=sorted(selected['selector']-selected['v9']),removed_sources=sorted(selected['v9']-selected['selector'])))
    changed=sum(r['context_changed'] for r in details)
    gate='blocked_health' if healthy<127 else 'blocked_unchanged_context' if not changed else 'blocked_anchor_recall' if totals['selector']['anchor_hit']<194 else 'passed'
    summary.update(changed_contexts=changed,qa_gate=gate,healthy_contexts=133+healthy,
        arms={a:dict(totals[a],query_type=dict(types[a])) for a in ARMS},rows=details)
    return summary


def select_worker(prepared,out,workers):
    if verify_seal(prepared)['state']!='complete':raise ValueError('incomplete input')
    verify_program(prepared,current=True);core,*_=native_modules(prepared)
    config=read(prepared/'config.json');tasks=pool_rows(prepared);ledger=e.make_ledger(out/'request-ledger.sqlite',BUDGET)
    try:
        adapters=queue.Queue()
        for _ in range(workers):adapters.put(make_adapter(core,config))
        def execute(task):
            adapter=adapters.get()
            try:return execute_selection(task,out,core,ledger,adapter)
            finally:adapters.put(adapter)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures=[pool.submit(execute,t) for t in tasks.values()]
            try:
                for future in as_completed(futures):future.result()
            except BaseException:
                for future in futures:future.cancel()
                raise
        for item,task in tasks.items():
            row=read(out/'selections'/(e.text_sha(item)+'.json'))
            write(out/'selector/recalls'/(e.text_sha(item)+'.json'),selection_row(task,row))
        write(out/'summary.json',summarize_selection(prepared,out,core))
    except BaseException as exc:
        write(out/'failure.json',dict(exception=f'{type(exc).__name__}: {exc}'))
        write(out/'summary.json',summarize_selection(prepared,out,core,partial=True));raise


def select(prepared,out,workers=4):
    out=e.builder.new_output(out);e.validate_workers(workers);prepared=Path(prepared).resolve();data=check_prepared(prepared)
    verify_program(prepared,current=True)
    out.mkdir(parents=True);freeze_program(out)
    write(out/'stage.json',dict(stage='select',input=str(prepared),input_seal_sha256=data['seal_sha256'],workers=workers))
    shutil.copytree(prepared/'v9',out/'v9');shutil.copyfile(prepared/'seal.json',out/'prepare-seal.json')
    try:
        e.make_ledger(out/'request-ledger.sqlite',BUDGET)
        invoke_worker('_select_worker',prepared,out,workers)
        verify_seal(prepared);verify_program(prepared,current=True);verify_databases(read(prepared/'plan.json'))
        seal_output(out,'select')
    except BaseException as exc:
        if not (out/'failure.json').exists():write(out/'failure.json',dict(exception=f'{type(exc).__name__}: {exc}'))
        try:
            with tempfile.TemporaryDirectory(prefix='r68-interrupted-audit-') as temp:
                replay=Path(temp);invoke_worker('_audit_worker',prepared,replay,receipts=out)
                write(out/'summary.json',read(replay/'summary.json'))
        except BaseException as audit_exc:
            write(out/'audit-failure.json',dict(exception=f'{type(audit_exc).__name__}: {audit_exc}'))
        seal_output(out,'select','incomplete');raise
    return read(out/'summary.json')


def audit_worker(prepared,out,receipts):
    verify_program(prepared);core,*_=native_modules(prepared)
    if (receipts/'seal.json').exists():partial=verify_seal(receipts)['state']=='incomplete'
    elif (receipts/'failure.json').exists():partial=True
    else:raise ValueError('unsealed input without failure evidence')
    summary=summarize_selection(prepared,receipts,core,partial=partial)
    if not partial:
        for item,task in pool_rows(prepared).items():
            row=read(receipts/'selections'/(e.text_sha(item)+'.json'))
            write(out/'selector/recalls'/(e.text_sha(item)+'.json'),selection_row(task,row))
    write(out/'summary.json',summary)


def check(out):
    out=Path(out).resolve();seal=verify_seal(out)
    if seal['stage']=='prepare':return check_prepared(out)
    if seal['stage']!='select':raise ValueError('unknown selection stage')
    verify_program(out);stage=read(out/'stage.json');prepared=Path(stage['input']).resolve();e.validate_workers(stage['workers'])
    if prepared==out:raise ValueError('cyclic input')
    data=check_prepared(prepared)
    if (stage.get('stage')!='select' or stage['input_seal_sha256']!=data['seal_sha256'] or
        sha(out/'prepare-seal.json')!=data['seal_sha256'] or read(out/'program.json')!=read(prepared/'program.json') or
        inventory(out/'v9')!=inventory(prepared/'v9')):raise ValueError('selection input/program/control drift')
    if (out/'failure.json').exists()!=(seal['state']=='incomplete'):raise ValueError('failure/seal mismatch')
    with tempfile.TemporaryDirectory(prefix='r68-selection-audit-') as temp:
        replay=Path(temp);invoke_worker('_audit_worker',prepared,replay,receipts=out)
        summary=read(replay/'summary.json')
        if read(out/'summary.json')!=summary or (seal['state']=='complete' and inventory(replay/'selector')!=inventory(out/'selector')):
            raise ValueError('selection native replay/summary drift')
    verify_seal(out)
    return dict(data,summary=summary,seal_sha256=sha(out/'seal.json'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['prepare','select','check','_pool_worker','_select_worker','_audit_worker'])
    parser.add_argument('--input',type=Path,default=DEFAULT_ORIGIN);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=4);parser.add_argument('--receipts',type=Path)
    args=parser.parse_args()
    if args.stage=='_pool_worker':pool_worker(args.input,args.out);return
    if args.stage=='_select_worker':select_worker(args.input,args.out,args.workers);return
    if args.stage=='_audit_worker':audit_worker(args.input,args.out,args.receipts);return
    if args.stage=='check':result=check(args.out)['summary']
    elif args.stage=='select':result=select(args.input,args.out,args.workers)
    else:result=prepare(args.input,args.out)
    print(json.dumps(result,ensure_ascii=False,indent=2,default=str))


if __name__=='__main__':main()
