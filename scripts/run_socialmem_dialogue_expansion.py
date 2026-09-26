#!/usr/bin/env python3
"""保留种子并扩展连续对话的冻结评测；全部检索逻辑在C++。"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_socialmem_k30_controlled as base

ROOT=Path(__file__).resolve().parents[1]
PARENT_SEAL='75f49fd3fa3ae3d78faa8e36d5c75987b933e85ccf44c39b4542a98b720cea06'
PARENT_CORE='fa538db8dd1afcea01817e590ae893c59e0ff85f19e90e263dbe24c3dcc226de'
CODE_PARENT_SEAL='c9170626e8d875206466e3ba535d4218530037c7b5bf25cc2f954406f9ed2c3e'
CODE_PARENT_CORE='05f6e9b21356b7b727254d002aff292adcabd4f6662a131c4616e2ac68aaf8e1'
CORE_NAME='python/starling/_core.cpython-314-darwin.so'
CHANGED={CORE_NAME,'include/starling/retrieval/source_retriever.hpp','src/retrieval/source_retriever.cpp',
 'bindings/python/bind_05_retrieval.cpp','scripts/eval_ladder_pipeline.py',
 'scripts/run_socialmem_baseline.py','tests/cpp/test_source_retriever.cpp'}
ANALYSIS_FILES=('analyze_socialmem_dialogue_expansion.py','run_socialmem_dialogue_expansion.py',
 'analyze_socialmem_grounded_answer.py','analyze_socialmem_source_focus.py',
 'analyze_socialmem_k30.py','run_socialmem_k30_controlled.py')
EXPANSION={'source_strategy':'focused_dialogue','k':60,'max_context_bytes':16000,
 'source_seed_k':30,'source_seed_max_context_bytes':8000,'source_dialogue_radius':2}
read,write,sha=base.read,base.write,base.sha

def freeze_analysis(work):
    folder=Path(work)/'analysis-frozen';folder.mkdir()
    for name in ANALYSIS_FILES:shutil.copyfile(ROOT/'scripts'/name,folder/name)
    write(folder/'manifest.json',{name:sha(folder/name) for name in ANALYSIS_FILES})

def verify_analysis(work):
    folder=Path(work)/'analysis-frozen';manifest=read(folder/'manifest.json')
    if set(manifest)!=set(ANALYSIS_FILES):raise ValueError('analysis dependency set changed')
    base.verify_files(folder,manifest)

def validate_config(parent,candidate):
    digest=candidate.get('core_sha256','')
    required={'core_sha256':PARENT_CORE,'source_strategy':'focused_window','k':30,'max_context_bytes':8000,
     'http_budget':1314,'answer_max_tokens':1024,'answer_policy':'grounded_v1','recall_mode':'sources'}
    expected={**parent,**EXPANSION,'core_sha256':digest}
    if (any(parent.get(k)!=v for k,v in required.items()) or not isinstance(digest,str)
        or not re.fullmatch('[0-9a-f]{64}',digest) or digest in (PARENT_CORE,CODE_PARENT_CORE)
        or json.dumps(candidate,sort_keys=True)!=json.dumps(expected,sort_keys=True)):
        raise ValueError('only reviewed dialogue strategy, budgets and native core may change')

def validate_code_delta(parent,candidate):
    old,new=parent['frozen_files'],candidate['frozen_files']
    if old.keys()!=new.keys() or any(old[n]!=new[n] for n in old if n not in CHANGED):
        raise ValueError('unreviewed code or scoring change')

def verify_archive(work,digest,correct):
    if sha(work/'completion-seal.json')!=digest:raise ValueError('parent seal changed')
    seal=read(work/'completion-seal.json');base.verify_files(work,seal['files'])
    if (seal['questions'],seal['correct'])!=(733,correct):raise ValueError('parent incomplete')

def verify_parent(work):verify_archive(work,PARENT_SEAL,345)

def verify_code_parent(work):
    verify_archive(work,CODE_PARENT_SEAL,313)
    if read(work/'identity.json')['core_sha256']!=CODE_PARENT_CORE:raise ValueError('code parent changed')

def verify_preflight_rows(records,parent,rows):
    ids=[r['item_id'] for r in rows];expected={r['item_id'] for r in records}
    if len(expected)!=len(records) or len(ids)!=len(set(ids)) or set(ids)!=expected:
        raise ValueError('preflight question set changed')
    refkey=lambda ref:json.dumps(ref,sort_keys=True)
    for row in rows:
        old=parent[row['item_id']]
        if (row['baseline_block']!=old['recall']['block'] or row['baseline_source_refs']!=old['recall']['source_refs']
            or row['baseline_prompt']!=old['prompt']):raise ValueError('old native path changed: '+row['item_id'])
        original=Counter(map(refkey,old['recall']['source_refs']));actual=Counter(map(refkey,row['source_refs']))
        if (original-actual or any(n!=1 for n in actual.values()) or len(row['source_refs'])>60
            or len(row['block'].encode())>16000
            or Counter(old['recall']['block'].splitlines())-Counter(row['block'].splitlines())):
            raise ValueError('seed source lost, mutated or context budget exceeded: '+row['item_id'])

def selected_groups(runner,work):
    records=base.select_records(runner._read_jsonl(work/'corpus.jsonl'),read(work/'network-split.json'))
    return records,runner.prepare_groups(records)

def native_preflight(work,parent,runner,records,groups,config):
    core,runtime,_,ladder,pipe,_=runner._frozen_imports(work,config,read(work/'identity.json'))
    old={r['item_id']:r for r in (read(p) for p in parent.glob('runs/*/questions/*.json'))}
    rows=[]
    with tempfile.TemporaryDirectory(prefix='starling-dialogue-') as scratch:
        for group in groups:
            database=Path(scratch)/(group['group_id']+'.db');shutil.copyfile(work/'runs'/group['group_id']/'frozen.db',database)
            rt=runtime._build_local_store_sqlite_runtime(database);rt.start()
            embedding,index=core.StubEmbeddingAdapter(8),core.SqliteBlobVectorIndex()
            for record in group['records']:
                common=dict(adapter=rt.adapter,embedder=embedding,index=index,question=record['question'],
                  allowed_holders=runner.history_holders(group['history']),mode='sources',now_iso=config['query_time'],
                  include_unknown_time=config['include_unknown_time'])
                baseline=pipe.recall_observer_block(core,**common,k=30,max_context_bytes=8000,source_strategy='focused_window')
                recall=pipe.recall_observer_block(core,**common,**EXPANSION)
                rows.append({'item_id':record['item_id'],'baseline_block':baseline['block'],
                 'baseline_source_refs':baseline['source_refs'],'baseline_prompt':runner.answer_prompt(core,ladder,record,baseline,config),
                 'block':recall['block'],'source_refs':recall['source_refs'],'prompt':runner.answer_prompt(core,ladder,record,recall,config),
                 'diagnostics':recall['source_diagnostics']})
    verify_preflight_rows(records,old,rows)
    digest=lambda text:hashlib.sha256(text.encode()).hexdigest()
    return {'verified':True,'requests':0,'questions':len(rows),'baseline_context_matches':len(rows),
     'baseline_prompt_matches':len(rows),'preserved_seed_contexts':len(rows),'core_sha256':sha(core.__file__),
     'changed_contexts':sum(r['block']!=r['baseline_block'] for r in rows),
     'rows':[{'item_id':r['item_id'],'block_sha256':digest(r['block']),'source_refs':r['source_refs'],
       'prompt_sha256':digest(r['prompt']),'baseline_block_sha256':digest(r['baseline_block']),
       'baseline_prompt_sha256':digest(r['baseline_prompt']),'diagnostics':r['diagnostics']} for r in rows]}

def prepare(work,parent,code_parent):
    work,parent,code_parent=(Path(p).resolve() for p in (work,parent,code_parent))
    verify_parent(parent);verify_code_parent(code_parent)
    if work.exists():raise ValueError('prepare requires a new directory')
    original=read(code_parent/'identity.json');work.mkdir(parents=True)
    for name,expected in original['frozen_files'].items():
        source=ROOT/'build'/name if name==CORE_NAME else ROOT/name
        if name not in CHANGED:
            if source.is_file() and sha(source)!=expected:raise ValueError('unreviewed workspace drift: '+name)
            source=code_parent/'frozen'/name
        target=work/'frozen'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    for name in ('corpus.jsonl','scope-manifest.json','network-split.json'):shutil.copyfile(parent/name,work/name)
    config={**read(parent/'config.json'),**EXPANSION,'core_sha256':sha(work/'frozen'/CORE_NAME)}
    validate_config(read(parent/'config.json'),config);write(work/'config.json',config)
    identity={**original,'core_path':str(work/'frozen'/CORE_NAME),'core_sha256':config['core_sha256'],
     'config_sha256':sha(work/'config.json'),'parent_grounded_seal_sha256':PARENT_SEAL,'code_parent_seal_sha256':CODE_PARENT_SEAL,
     'candidate_change':'C++保留种子并扩展连续对话；总60条/16000字节；grounded/1024、模型与评分不变',
     'frozen_files':{name:sha(work/'frozen'/name) for name in original['frozen_files']}}
    validate_code_delta(original,identity);write(work/'identity.json',identity)
    runner=base.load_runner(work);fingerprint=runner._verify_identity(work,config)
    records,groups=selected_groups(runner,work)
    for group in groups:
        folder=work/'runs'/group['group_id'];folder.mkdir(parents=True);old=parent/'runs'/group['group_id']
        shutil.copyfile(old/'frozen.db',folder/'frozen.db');metadata=read(old/'scope.json')
        metadata['fingerprint']=fingerprint;write(folder/'scope.json',metadata)
    shutil.copyfile(Path(__file__),work/'run.py');shutil.copyfile(Path(base.__file__),work/'run_socialmem_k30_controlled.py')
    sources=[ROOT/name for name in ('scripts/run_socialmem_dialogue_expansion.py','scripts/analyze_socialmem_dialogue_expansion.py',
      'tests/python/test_dialogue_expansion.py','tests/python/test_dialogue_expansion_guard.py',
      'tests/python/test_analyze_socialmem_dialogue_expansion.py')]+list((ROOT/'docs').rglob('*.md'))
    for source in sources:
        target=work/'execution-sources'/source.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    write(work/'native-preflight.json',native_preflight(work,parent,runner,records,groups,config));freeze_analysis(work)
    plan={'parent_work':str(parent),'parent_seal_sha256':PARENT_SEAL,'code_parent_work':str(code_parent),
     'code_parent_seal_sha256':CODE_PARENT_SEAL,'driver_sha256':sha(work/'run.py'),'core_sha256':config['core_sha256'],
     'answer_policy':'grounded_v1','questions':733,'groups':39,'http_budget':1314,
     'scope_ids':[g['group_id'] for g in groups],'question_ids':[r['item_id'] for r in records]}
    plan['files']={str(p.relative_to(work)):sha(p) for p in sorted(work.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
    write(work/'execution-plan.json',plan)

def check(work):
    work=Path(work).resolve();plan=read(work/'execution-plan.json')
    # Analysis imports this module from analysis-frozen, whose manifest is checked separately.
    if sha(work/'run.py')!=plan['driver_sha256'] or plan['parent_seal_sha256']!=PARENT_SEAL or plan['code_parent_seal_sha256']!=CODE_PARENT_SEAL:
        raise ValueError('driver or parent identity changed')
    base.verify_manifest(work,plan);verify_analysis(work)
    parent,code_parent=Path(plan['parent_work']),Path(plan['code_parent_work'])
    verify_parent(parent);verify_code_parent(code_parent)
    config,identity=read(work/'config.json'),read(work/'identity.json')
    validate_config(read(parent/'config.json'),config);validate_code_delta(read(code_parent/'identity.json'),identity)
    for name in ('corpus.jsonl','scope-manifest.json','network-split.json'):
        if sha(work/name)!=sha(parent/name):raise ValueError('input or split changed')
    runner=base.load_runner(work);fingerprint=runner._verify_identity(work,config);records,groups=selected_groups(runner,work)
    if ([g['group_id'] for g in groups]!=plan['scope_ids'] or [r['item_id'] for r in records]!=plan['question_ids']
        or (plan['questions'],plan['groups'],plan['http_budget'],plan['answer_policy'])!=(733,39,1314,'grounded_v1')
        or plan['core_sha256']!=config['core_sha256']):raise ValueError('selected set or plan changed')
    for group in groups:
        folder=work/'runs'/group['group_id']
        if runner.scope_state(folder,fingerprint)!='terminal' or (folder/'scope.failure.json').exists():raise ValueError('source unavailable')
        if sha(folder/'frozen.db')!=sha(parent/'runs'/group['group_id']/'frozen.db'):raise ValueError('database changed')
    pre=read(work/'native-preflight.json')
    if (pre['verified'] is not True or pre['core_sha256']!=config['core_sha256'] or pre['requests']!=0
        or any(pre[k]!=733 for k in ('questions','baseline_context_matches','baseline_prompt_matches','preserved_seed_contexts'))
        or sorted(r['item_id'] for r in pre['rows'])!=sorted(plan['question_ids'])):raise ValueError('native preflight changed')
    if sum(runner.question_request_bound(r,config,work/'runs'/g['group_id']/'frozen.db') for g in groups for r in g['records'])!=1314:
        raise ValueError('request bound changed')
    return runner,groups

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['prepare','check','run'])
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--parent',type=Path,default=ROOT/'build/socialmem_20260918_answer_capacity_v2')
    parser.add_argument('--code-parent',type=Path,default=ROOT/'build/socialmem_20260918_evidence_answer')
    args=parser.parse_args()
    if args.mode=='run' and (args.work/'completion-seal.json').exists():raise ValueError('sealed experiment cannot run')
    if args.mode=='prepare':prepare(args.work,args.parent,args.code_parent)
    runner,groups=check(args.work)
    if sha(Path(__file__))!=read(args.work/'execution-plan.json')['driver_sha256']:raise ValueError('executing driver changed')
    if args.mode!='run':
        print(json.dumps({'verified':True,'questions':733,'groups':39,'http_limit':1314,'requests':0}));return
    report=runner.run(args.work,groups=groups,workers=4)
    summary=runner.summarize([r for g in groups for r in g['records']],[r for g in report['groups'] for r in g['results']])
    result={'state':'complete' if summary['executed']==733 else 'partial','summary':summary,
      'ledger':report['ledger'],'scope_ids':[g['group_id'] for g in groups]}
    write(args.work/'selected-summary.json',result);print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
