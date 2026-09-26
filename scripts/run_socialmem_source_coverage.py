#!/usr/bin/env python3
"""冻结99题两组来源覆盖实验；检索与提示均由C++执行。"""
from collections import Counter
import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_socialmem_answer_ablation as previous
import run_socialmem_k30_controlled as base

ROOT=Path(__file__).resolve().parents[1]
PARENT_SEAL='a80b946967e6f5ec0ebf44563c207c4b2e4f63dbf30a1ece3cbbbd14713411f1'
SOURCE_SEAL='f7316dea33dcf46fb135f898eb373d79be60ec2229741c9c31ca840c14faebef'
CORE_NAME=previous.CORE_NAME
CHANGED={CORE_NAME,'include/starling/retrieval/source_retriever.hpp','src/retrieval/source_retriever.cpp','tests/cpp/test_source_retriever.cpp'}
ARMS=('dialogue','coverage')
SCRIPTS=('run_socialmem_source_coverage.py','analyze_socialmem_source_coverage.py',
         'run_socialmem_answer_ablation.py','analyze_socialmem_answer_ablation.py','run_socialmem_k30_controlled.py')
sha,read,write=base.sha,base.read,base.write
task_id=previous.task_id

def validate_config(parent,candidate):
    expected={**parent,'core_sha256':candidate.get('core_sha256'),'http_budget':396,'answer_policy':'grounded_v1'}
    digest=candidate.get('core_sha256','')
    if (candidate!=expected or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest)
        or digest==parent.get('core_sha256')):raise ValueError('only reviewed core, budget and grounded policy may change')

def task_order(records):
    return [{'item_id':r['item_id'],'arm':ARMS[(i+j)%2],'position':j,'question_order':i}
            for i,r in enumerate(records) for j in range(2)]

def verify_executor(work):
    plan=json.loads((Path(work)/'execution-plan.json').read_text())
    for path in (Path(__file__),Path(previous.__file__),Path(base.__file__)):
        if hashlib.sha256(path.read_bytes()).hexdigest()!=plan['files'].get(path.name):raise ValueError('executing dependency differs from freeze: '+path.name)

def verify_required_files(work,plan):
    work=Path(work)
    required={'config.json','identity.json','sample.json','corpus.jsonl','scope-manifest.json',
              'network-split.json','tasks.json','inputs.json','prompts.json','native-preflight.json',*SCRIPTS}
    identity=read(work/'identity.json');pre=read(work/'native-preflight.json')
    required.update('source-databases/'+r['group_id']+'.db' for r in pre['rows'])
    required.update('frozen/'+n for n in identity['frozen_files'])
    if not required<=set(plan['files']):raise ValueError('required files missing from freeze')
    if any(plan['files']['frozen/'+n]!=digest for n,digest in identity['frozen_files'].items()):
        raise ValueError('frozen identity differs from execution manifest')

def verify_context(old,candidate,seeds,eligible):
    refkey=lambda ref:json.dumps(ref,sort_keys=True)
    refs=list(map(refkey,candidate['source_refs']));seedrefs=set(map(refkey,seeds['source_refs']))
    if (len(refs)!=len(set(refs)) or not seedrefs<=set(refs) or not set(refs)<=set(map(refkey,eligible['source_refs']))
        or len(refs)>60 or len(candidate['block'].encode())>16000 or candidate['context_bytes']!=len(candidate['block'].encode())
        or Counter(seeds['block'].splitlines())-Counter(candidate['block'].splitlines())):
        raise ValueError('source coverage lost seed, identity or budget')
    trace=candidate['source_diagnostics']['selection_trace']
    selected=[refkey(t['ref']) for t in trace if t['selected_by'] is not None]
    if Counter(selected)!=Counter(refs) or Counter(refkey(t['ref']) for t in trace)!=Counter(map(refkey,eligible['source_refs'])):
        raise ValueError('selection trace mismatch')
    lines=candidate['block'].splitlines();eligible_lines=eligible['block'].splitlines()
    if len(lines)!=len(refs) or len(eligible_lines)!=len(eligible['source_refs']) or candidate['source_count']!=len(refs):
        raise ValueError('source count or line mapping mismatch')
    source_lines={refkey(ref):line for ref,line in zip(eligible['source_refs'],eligible_lines,strict=True)}
    if any(source_lines[ref]!=line for ref,line in zip(refs,lines,strict=True)):
        raise ValueError('selected source text differs from authorized original')
    ranks={refkey(ref):i+1 for i,ref in enumerate(eligible['source_refs'])}
    diagnostics=candidate['source_diagnostics'];names=diagnostics.get('focused_holders',[])
    counts=Counter()
    for t in trace:
        key=refkey(t['ref']);stage=t['selected_by']
        if (stage not in (None,'seed','coverage','dialogue') or t['bm25_rank']!=ranks[key]
            or t['coverage_eligible']!=(t['ref']['speaker'] in names) or (stage=='seed')!=(key in seedrefs)
            or any(type(t[k]) is not bool for k in ('coverage_eligible','coverage_considered','coverage_budget_rejected','dialogue_considered','dialogue_budget_rejected'))
            or (stage=='coverage' and (not t['coverage_eligible'] or not t['coverage_considered'] or t['coverage_budget_rejected']))
            or (stage=='dialogue' and (not t['dialogue_considered'] or t['dialogue_budget_rejected']))):
            raise ValueError('invalid selection trace stage, rank or person')
        if stage:counts[stage]+=1
    if (counts['seed']!=diagnostics['dialogue_seed_count'] or counts['coverage']!=diagnostics['coverage_added_sources']
        or counts['dialogue']!=diagnostics['dialogue_added_sources']):raise ValueError('selection phase count mismatch')

def prepare(work,parent,source):
    work,parent,source=map(lambda p:Path(p).resolve(),(work,parent,source))
    previous._archive(parent,PARENT_SEAL);previous._archive(source,SOURCE_SEAL)
    if work.exists():raise ValueError('prepare requires new directory')
    records=read(parent/'sample.json');original=read(parent/'identity.json');work.mkdir(parents=True)
    for name,digest in original['frozen_files'].items():
        live=ROOT/'build'/name if name==CORE_NAME else ROOT/name
        if name not in CHANGED and live.is_file() and sha(live)!=digest:raise ValueError('unreviewed code drift: '+name)
        src=live if name in CHANGED else parent/'frozen'/name
        dst=work/'frozen'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
    for name in SCRIPTS:shutil.copyfile(ROOT/'scripts'/name,work/name)
    for name in ('sample.json','corpus.jsonl','network-split.json','scope-manifest.json'):shutil.copyfile(parent/name,work/name)
    config={**read(parent/'config.json'),'core_sha256':sha(work/'frozen'/CORE_NAME),'http_budget':396,'answer_policy':'grounded_v1'}
    validate_config(read(parent/'config.json'),config);write(work/'config.json',config)
    identity={**original,'core_path':str(work/'frozen'/CORE_NAME),'core_sha256':config['core_sha256'],
              'config_sha256':sha(work/'config.json'),'frozen_files':{n:sha(work/'frozen'/n) for n in original['frozen_files']}}
    write(work/'identity.json',identity);write(work/'tasks.json',task_order(records))
    runner=base.load_runner(work);runner._verify_identity(work,config)
    core,runtime,_,_,pipe,_=runner._frozen_imports(work,config,identity)
    wanted={r['item_id'] for r in records}
    full=[r for r in runner._read_jsonl(source/'corpus.jsonl') if r['item_id'] in wanted]
    groups=runner.prepare_groups(full);inputs={};prompts={};old=read(parent/'inputs.json');pre=[]
    with tempfile.TemporaryDirectory(prefix='coverage-preflight-') as tmp:
        for group in groups:
            snapshot=work/'source-databases'/(group['group_id']+'.db');snapshot.parent.mkdir(exist_ok=True)
            shutil.copyfile(source/'runs'/group['group_id']/'frozen.db',snapshot)
            db=Path(tmp)/snapshot.name;shutil.copyfile(snapshot,db)
            rt=runtime._build_local_store_sqlite_runtime(db);rt.start();emb=core.StubEmbeddingAdapter(8)
            for r in group['records']:
                common=dict(adapter=rt.adapter,embedder=emb,index=core.SqliteBlobVectorIndex(),question=r['question'],
                    allowed_holders=runner.history_holders(group['history']),mode='sources',now_iso=config['query_time'],
                    include_unknown_time=config['include_unknown_time'])
                settings=dict(k=60,max_context_bytes=16000,source_seed_k=30,source_seed_max_context_bytes=8000,source_dialogue_radius=2)
                baseline=pipe.recall_observer_block(core,**common,**settings,source_strategy='focused_dialogue')
                candidate=pipe.recall_observer_block(core,**common,**settings,source_strategy='focused_coverage')
                seeds=pipe.recall_observer_block(core,**common,k=30,max_context_bytes=8000,source_strategy='focused_window')
                eligible=pipe.recall_observer_block(core,**common,k=100000,max_context_bytes=100000000,source_strategy='bm25')
                key=r['item_id']
                if baseline['block']!=old[key]['block'] or baseline['source_refs']!=old[key]['source_refs']:raise ValueError('old source path changed')
                verify_context(baseline,candidate,seeds,eligible)
                inputs[key]={'dialogue':baseline,'coverage':candidate}
                prompts[key]={a:core.grounded_source_answer_prompt(r['question'],inputs[key][a]['block']) for a in ARMS}
                if prompts[key]['dialogue']!=read(parent/'prompts.json')[key]['source_grounded']:raise ValueError('old prompt changed')
                pre.append({'item_id':key,'group_id':group['group_id'],'seed_count':len(seeds['source_refs']),
                    'eligible_count':len(eligible['source_refs']),'changed_context':baseline['block']!=candidate['block']})
    if set(inputs)!=wanted or len(wanted)!=99:raise ValueError('incomplete preflight')
    write(work/'inputs.json',inputs);write(work/'prompts.json',prompts)
    write(work/'native-preflight.json',{'verified':True,'requests':0,'questions':99,'rows':pre,'core_sha256':config['core_sha256']})
    for src in [ROOT/'tests/python/test_source_coverage.py',*sorted((ROOT/'docs').rglob('*.md'))]:
        dst=work/'execution-sources'/src.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
    write(work/'execution-plan.json',{'parent':str(parent),'source':str(source),'parent_seal':PARENT_SEAL,'source_seal':SOURCE_SEAL,
        'questions':99,'networks':33,'arms':list(ARMS),'tasks':198,'http_budget':396,'workers':4,
        'files':{str(p.relative_to(work)):sha(p) for p in sorted(work.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}})

def check(work):
    work=Path(work);verify_executor(work);plan=read(work/'execution-plan.json');verify_required_files(work,plan);base.verify_files(work,plan['files'])
    if (plan['parent_seal'],plan['source_seal'])!=(PARENT_SEAL,SOURCE_SEAL):raise ValueError('parent identity changed')
    if (plan['questions'],plan['networks'],plan['tasks'],plan['http_budget'],plan['workers'],plan['arms'])!=(99,33,198,396,4,list(ARMS)):
        raise ValueError('scope changed')
    for name in SCRIPTS:
        if sha(work/name)!=plan['files'].get(name):raise ValueError('unfrozen script')
    parent,source=Path(plan['parent']),Path(plan['source'])
    previous._archive(parent,PARENT_SEAL);previous._archive(source,SOURCE_SEAL)
    config,identity=read(work/'config.json'),read(work/'identity.json');old=read(parent/'identity.json')
    validate_config(read(parent/'config.json'),config)
    if old['frozen_files'].keys()!=identity['frozen_files'].keys() or any(old['frozen_files'][n]!=identity['frozen_files'][n] for n in old['frozen_files'] if n not in CHANGED):
        raise ValueError('unreviewed core delta')
    for name in ('sample.json','corpus.jsonl','network-split.json','scope-manifest.json'):
        if sha(work/name)!=sha(parent/name):raise ValueError('fixed inputs changed')
    records=read(work/'sample.json')
    if read(work/'tasks.json')!=task_order(records):raise ValueError('task order changed')
    pre=read(work/'native-preflight.json')
    if (pre['verified'] is not True or pre['requests']!=0 or pre['questions']!=99 or pre['core_sha256']!=config['core_sha256']
        or sorted(r['item_id'] for r in pre['rows'])!=sorted(r['item_id'] for r in records)):raise ValueError('preflight changed')
    for row in pre['rows']:
        name=row['group_id']+'.db'
        if sha(work/'source-databases'/name)!=sha(source/'runs'/row['group_id']/'frozen.db'):raise ValueError('source database changed')
    runner=base.load_runner(work);runner._verify_identity(work,config)
    return runner

def _run_question(work_str,record,tasks):
    work=Path(work_str);verify_executor(work);runner=base.load_runner(work);config=read(work/'config.json')
    core,_,audit,*_=runner._frozen_imports(work,config,read(work/'identity.json'))
    _,_,answer,judge=runner._make_native_adapters(core,config)
    ledger=runner.BudgetLedger(work/'request-ledger.sqlite',396)
    fingerprint={'execution_plan_sha256':sha(work/'execution-plan.json')};prompts=read(work/'prompts.json')[record['item_id']]
    return [previous.execute_task(work,t,record,prompts[t['arm']],runner,audit,answer,judge,ledger,fingerprint) for t in tasks]

def run(work):
    work=Path(work).resolve()
    if (work/'completion-seal.json').exists():raise ValueError('sealed experiment cannot run')
    runner=check(work)
    with runner._work_lock(work):
        if (work/'run-started.json').exists() or (work/'request-ledger.sqlite').exists() or any((work/'receipts').glob('*.json')):
            raise ValueError('already started; retry prohibited')
        runner.BudgetLedger(work/'request-ledger.sqlite',396)
        if not runner._exclusive_started(work/'run-started.json',{'execution_plan_sha256':sha(work/'execution-plan.json')}):raise ValueError('already started')
        tasks=read(work/'tasks.json');finished=[]
        with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
            futures=[pool.submit(_run_question,str(work),r,[t for t in tasks if t['item_id']==r['item_id']]) for r in read(work/'sample.json')]
            for future in concurrent.futures.as_completed(futures):
                finished.extend(future.result());progress={'terminal_tasks':len(finished),'total_tasks':198,'status_counts':dict(Counter(r['status'] for r in finished))}
                runner._json_write(work/'technical-progress.json',progress);print(json.dumps(progress),flush=True)
        audit=verify_terminal(work);write(work/'run-completion.json',{'state':'complete','audit':audit});return audit

def verify_terminal(work):
    work=Path(work);tasks=read(work/'tasks.json');expected={task_id(t):t for t in tasks};prompts=read(work/'prompts.json')
    if len(tasks)!=198 or len(expected)!=198:raise ValueError('incomplete task set')
    fingerprint={'execution_plan_sha256':sha(work/'execution-plan.json')}
    if read(work/'run-started.json')!=fingerprint:raise ValueError('run identity changed')
    paths=list((work/'receipts').glob('*.json'));starts=list((work/'started').glob('*.json'))
    if len(paths)!=198 or {p.stem for p in paths}!=set(expected) or {p.stem for p in starts}!=set(expected):raise ValueError('incomplete terminal set')
    conn=sqlite3.connect(f'file:{work / "request-ledger.sqlite"}?mode=ro',uri=True)
    try:ledger={r[0]:r for r in conn.execute('SELECT id,scope,stage,upper_bound,actual,state FROM reservations')}
    finally:conn.close()
    if len(ledger)!=198:raise ValueError('reservation set differs')
    spec=importlib.util.spec_from_file_location('coverage_frozen_judge',work/'frozen/scripts/eval_judge_audit.py');audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
    records={r['item_id']:r for r in read(work/'sample.json')};actual=charged=unknown=tokens=0;ids=set();stages=Counter();states=Counter()
    for path in paths:
        row=read(path);task=expected[path.stem];start=read(work/'started'/path.name)
        if (row.get('task')!=task or row.get('fingerprint')!=fingerprint or start!={'task':task,'fingerprint':fingerprint,'reservation':row.get('reservation')}
            or row.get('item_id')!=task['item_id'] or row.get('arm')!=task['arm'] or row.get('terminal') is not True
            or row.get('prompt')!=prompts[task['item_id']][task['arm']] or type(row.get('correct')) is not bool
            or row.get('status') not in ('ok','answer_failure','judge_failure') or (row['status']!='ok' and row['correct'])):
            raise ValueError('receipt identity, prompt or terminal mismatch')
        if any(k in row for k in ('evidence','embedding','recall')):raise ValueError('unexpected extra provider stage')
        previous.verify_score(records[task['item_id']],row,audit);count=0
        for stage in ('answer','judge'):
            raw=row.get(stage,{}).get('response',{});n=raw.get('attempt_count',0)
            if type(n) is not int or n not in (0,1) or n!=len(raw.get('http_attempts',[])):raise ValueError('request envelope mismatch')
            count+=n;stages[stage]+=n;tokens+=raw.get('total_tokens',0)
        if row.get('native_attempt_count')!=count:raise ValueError('native counter mismatch')
        rid=row['reservation']['id'];ids.add(rid);reservation=ledger.get(rid);is_unknown=bool(row.get('budget_unknown'));cost=2 if is_unknown else count
        # execute_task is shared with the prior experiment; its ledger stage name is retained.
        if (reservation is None or reservation[1:4]!=(path.stem,'answer_ablation',2)
            or reservation[5]!=('charged_upper' if is_unknown else 'settled') or reservation[4]!=(None if is_unknown else count)
            or row.get('charged_requests')!=cost):raise ValueError('ledger differs from receipt')
        actual+=count;charged+=cost;unknown+=is_unknown;states[row['status']]+=1
    if ids!=set(ledger) or not actual<=charged<=396:raise ValueError('budget or identity mismatch')
    return {'verified':True,'questions':99,'tasks':198,'actual_requests':actual,'charged_requests':charged,'http_budget':396,
        'unknown_budget_receipts':unknown,'requests_by_stage':dict(stages),'status_counts':dict(states),'observed_total_tokens':tokens}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('prepare','check','run'));p.add_argument('--work',type=Path,required=True)
    p.add_argument('--parent',type=Path,default=ROOT/'build/socialmem_20260918_answer_ablation')
    p.add_argument('--source',type=Path,default=ROOT/'build/socialmem_20260918_synthesis_answer');args=p.parse_args()
    if args.mode=='prepare':prepare(args.work,args.parent,args.source)
    if args.mode=='run':result=run(args.work)
    else:check(args.work);result={'verified':True,'questions':99,'tasks':198,'http_budget':396,'requests':0}
    print(json.dumps(result,ensure_ascii=False,indent=2))
