#!/usr/bin/env python3
"""固定两组开发诊断，失败计零，按网络重采样，不校改裁判标签。"""
from collections import Counter,defaultdict
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import tempfile
import analyze_socialmem_answer_ablation as previous

ARMS=('dialogue','coverage')

def interval(records,values):
    if not records:return None
    groups=defaultdict(list)
    for r,v in zip(records,values,strict=True):groups[r['source']['network_id']].append(v)
    cells=[(sum(groups[k]),len(groups[k])) for k in sorted(groups)];rng=random.Random(20260919);draws=[]
    for _ in range(5000):
        sample=[rng.choice(cells) for _ in cells];draws.append(sum(s for s,n in sample)/sum(n for s,n in sample))
    draws.sort()
    def quantile(q):
        p=q*(len(draws)-1);i=int(p);return draws[i]+(draws[min(i+1,len(draws)-1)]-draws[i])*(p-i)
    return [quantile(.025),quantile(.975)]

def paired(records,by):
    pairs=[tuple(int(by[r['item_id'],a]['correct']) for a in ARMS) for r in records]
    differences=[b-a for a,b in pairs]
    return {'n':len(records),'delta':sum(differences)/len(records) if records else None,
            'net_correct':sum(differences),'new_correct':sum(a==0 and b==1 for a,b in pairs),
            'regressed':sum(a==1 and b==0 for a,b in pairs),'network_bootstrap_95ci':interval(records,differences)}

def analyze_rows(records,rows):
    wanted={(r['item_id'],a) for r in records for a in ARMS};keys=[(r['item_id'],r['arm']) for r in rows]
    if (len({r['item_id'] for r in records})!=len(records) or len(set(keys))!=len(keys) or set(keys)!=wanted):
        raise ValueError('incomplete, duplicate or unregistered question/arm set')
    for row in rows:
        if (row.get('terminal') is not True or type(row.get('correct')) is not bool or
            row.get('status') not in ('ok','answer_failure','judge_failure') or (row['status']!='ok' and row['correct'])):
            raise ValueError('invalid terminal receipt')
    by={(r['item_id'],r['arm']):r for r in rows};arms={}
    for arm in ARMS:
        group=[r for r in rows if r['arm']==arm];correct=sum(r['correct'] for r in group)
        arms[arm]={'n':len(group),'correct':correct,'accuracy':correct/len(group) if group else None,
            'status_counts':dict(Counter(r['status'] for r in group)),
            'stage_outcomes':{s:dict(Counter(previous.stage_outcome(r,s) for r in group)) for s in ('answer','judge')},
            'observed_total_tokens':sum(r.get(s,{}).get('response',{}).get('total_tokens',0) for r in group for s in ('answer','judge'))}
    common=[r for r in records if all(by[r['item_id'],a]['status']=='ok' for a in ARMS)]
    main=paired(records,by)
    return {'questions':len(records),'networks':len({r['source']['network_id'] for r in records}),'arms':arms,'paired':main,
            'both_ok':{'n':len(common),'paired':paired(common,by),'correct':{a:sum(by[r['item_id'],a]['correct'] for r in common) for a in ARMS}},
            'direction_for_full_validation':bool(records and main['net_correct']>=5 and main['network_bootstrap_95ci'][0]>0),
            'promoted':False,'limitations':'同一99道已用于开发诊断的题；单次生成/原裁判，区间不包含独立复跑方差；共同正常子集仅描述。不是733题或新保留集成绩；超时用量未知。'}

def analyze(work):
    import run_socialmem_source_coverage as driver
    work=Path(work);driver.verify_executor(work)
    plan=driver.read(work/'execution-plan.json')
    for path in (Path(__file__),Path(previous.__file__)):
        if driver.sha(path)!=plan['files'].get(path.name):raise ValueError('executing analyzer differs from freeze')
    driver.check(work);destination=work/'analysis-results'
    if destination.exists() or (work/'completion-seal.json').exists():raise ValueError('already published or sealed')
    audit=driver.verify_terminal(work);records=driver.read(work/'sample.json')
    rows=[driver.read(p) for p in sorted((work/'receipts').glob('*.json'))]
    result=analyze_rows(records,rows);result['request_audit']=audit
    with tempfile.TemporaryDirectory(prefix='.analysis-',dir=work) as tmp:
        folder=Path(tmp);driver.write(folder/'paired-analysis.json',result)
        driver.write(folder/'paired-details.json',[{k:r[k] for k in ('item_id','arm','status','correct')} for r in rows])
        os.replace(folder,destination)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True)
    print(json.dumps(analyze(p.parse_args().work),ensure_ascii=False,indent=2))
