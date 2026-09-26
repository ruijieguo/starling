#!/usr/bin/env python3
"""相同57题、原核心和评分的全文诊断入口。"""
from pathlib import Path
import argparse,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))

def validate_config(parent,candidate):
    if parent.get('recall_mode')!='sources' or candidate!={**parent,'recall_mode':'full','http_budget':101}:
        raise ValueError('full diagnostic changed unrelated configuration')

def validate_code_delta(parent,candidate):
    old,new=parent['frozen_files'],candidate['frozen_files']
    if any(new.get(k)!=v for k,v in old.items()):raise ValueError('full diagnostic changed parent code')
    if set(new)-set(old)!={'scripts/run_socialmem_development_full.py','scripts/run_socialmem_source_speaker.py','tests/python/test_development_full_guard.py'}:
        raise ValueError('full diagnostic unexpected code addition')

def check(work):
    work=Path(work).resolve();plan=json.loads((work/'execution-plan.json').read_text())
    sys.path.insert(0,str(work/'frozen/scripts'))
    # The helper itself is pinned before import; the full manifest is checked next.
    import hashlib
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    if sha(Path(__file__))!=plan['driver_sha256']:raise ValueError('full diagnostic driver drift')
    helper=work/'frozen/scripts/run_socialmem_source_speaker.py'
    if sha(helper)!=plan['files'].get('frozen/scripts/run_socialmem_source_speaker.py'):
        raise ValueError('full diagnostic helper drift')
    import run_socialmem_source_speaker as guard
    if Path(guard.__file__).resolve()!=helper:raise ValueError('full diagnostic helper outside frozen directory')
    guard.verify_manifest(work,plan)
    parent=Path(plan['parent_work'])
    if sha(parent/'completion-seal.json')!=plan['parent_seal_sha256']:raise ValueError('full diagnostic parent seal drift')
    guard.verify_files(parent,json.loads((parent/'completion-seal.json').read_text())['files'])
    report=json.loads((parent/'summary.json').read_text())
    if report['state']!='complete' or report['summary']['executed']!=1031:raise ValueError('full diagnostic parent incomplete')
    cfg=json.loads((work/'config.json').read_text())
    validate_config(json.loads((parent/'config.json').read_text()),cfg)
    validate_code_delta(json.loads((parent/'identity.json').read_text()),json.loads((work/'identity.json').read_text()))
    for name in ('corpus.jsonl','scope-manifest.json','network-split.json'):
        if sha(work/name)!=sha(parent/name):raise ValueError('full diagnostic corpus/scope/split drift')
    from run_socialmem_source_full import load_frozen_runner
    runner=load_frozen_runner(work);fingerprint=runner._verify_identity(work,cfg)
    groups=guard.select_groups(runner.prepare_groups(runner._read_jsonl(work/'corpus.jsonl')))
    if [g['group_id'] for g in groups]!=plan['scope_ids']:raise ValueError('full diagnostic scope set changed')
    for g in groups:
        folder=work/'runs'/g['group_id']
        if runner.scope_state(folder,fingerprint)!='terminal':raise ValueError('full diagnostic source incomplete')
        if sha(folder/'frozen.db')!=sha(parent/'runs'/g['group_id']/'frozen.db'):raise ValueError('full diagnostic source changed')
    if sum(runner.question_request_bound(r,cfg,work/'runs'/g['group_id']/'frozen.db') for g in groups for r in g['records'])!=101:
        raise ValueError('full diagnostic request bound drift')
    return guard,runner,groups

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('check','run'));p.add_argument('--work',type=Path,required=True)
    args=p.parse_args();guard,runner,groups=check(args.work)
    if args.mode=='check':print(json.dumps({'verified':True,'questions':57,'http_limit':101,'requests':0}))
    else:
        result=runner.run(args.work,groups=groups,workers=4)
        selected=guard.summarize_selected(runner,groups,result)
        runner._json_write(args.work/'selected-summary.json',selected);print(json.dumps(selected))
if __name__=='__main__':main()
