#!/usr/bin/env python3
"""四组合固定来源诊断；配对差值与网络聚类重采样，不修改评分。"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import json
import hashlib
import os
from pathlib import Path
import random
import tempfile

ARMS=('source_grounded','json_grounded','source_synthesis','json_synthesis')
COMPARISONS={
 'representation_grounded':('source_grounded','json_grounded'),
 'representation_synthesis':('source_synthesis','json_synthesis'),
 'guidance_source':('source_grounded','source_synthesis'),
 'guidance_json':('json_grounded','json_synthesis')}

def verify_analyzer(work):
    plan=json.loads((Path(work)/'execution-plan.json').read_text())
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=plan['files'].get('analyze_socialmem_answer_ablation.py'):
        raise ValueError('executing analyzer differs from frozen statistics')

def interval(records,values):
    if not records:return None
    groups=defaultdict(list)
    for record,value in zip(records,values,strict=True):groups[str(record['source']['network_id'])].append(value)
    cells=[(sum(groups[n]),len(groups[n])) for n in sorted(groups)]
    rng=random.Random(20260918);draws=[]
    for _ in range(5000):
        sample=[rng.choice(cells) for _ in cells]
        draws.append(sum(s for s,n in sample)/sum(n for s,n in sample))
    draws.sort()
    def quantile(q):
        pos=q*(len(draws)-1);lo=int(pos);hi=min(lo+1,len(draws)-1)
        return draws[lo]+(draws[hi]-draws[lo])*(pos-lo)
    return [quantile(.025),quantile(.975)]

def effects(records,by_key):
    out={};n=len(records)
    for name,(before,after) in COMPARISONS.items():
        pairs=[(int(by_key[(r['item_id'],before)]['correct']),int(by_key[(r['item_id'],after)]['correct'])) for r in records]
        values=[b-a for a,b in pairs]
        out[name]={'n':n,'delta':sum(values)/n if n else None,'net_correct':sum(values),
            'new_correct':sum(a==0 and b==1 for a,b in pairs),'regressed':sum(a==1 and b==0 for a,b in pairs),
            'network_bootstrap_95ci':interval(records,values)}
    values=[int(by_key[(r['item_id'],'json_synthesis')]['correct'])-int(by_key[(r['item_id'],'source_synthesis')]['correct'])
            -int(by_key[(r['item_id'],'json_grounded')]['correct'])+int(by_key[(r['item_id'],'source_grounded')]['correct']) for r in records]
    out['interaction']={'n':n,'delta':sum(values)/n if n else None,'network_bootstrap_95ci':interval(records,values)}
    return out

def stage_outcome(row,stage):
    payload=row.get(stage)
    if payload is None:
        attempted=stage=='answer' or 'judge_prompt' in row
        return 'exception' if attempted and row.get('budget_unknown') else 'not_called'
    raw=payload.get('response',{});error=str(raw.get('error','')).lower()
    if raw.get('finish_reason')=='length':return 'truncated'
    if 'timeout' in error or 'timed out' in error:return 'timeout'
    if 'http' in error:return 'http_error'
    if raw.get('ok') is not True or error:return 'provider_error'
    if not payload.get('raw_xml','').strip():return 'empty'
    return 'ok'

def analyze_rows(records,rows):
    keys={(r['item_id'],arm) for r in records for arm in ARMS}
    actual=[(r['item_id'],r['arm']) for r in rows]
    if len({r['item_id'] for r in records})!=len(records) or len(actual)!=len(set(actual)) or set(actual)!=keys:
        raise ValueError('incomplete, duplicate or unregistered question/arm set')
    for row in rows:
        if (row.get('terminal') is not True or type(row.get('correct')) is not bool or
            row.get('status') not in ('ok','answer_failure','judge_failure') or
            (row['status']!='ok' and row['correct'])):raise ValueError('invalid terminal receipt')
    by_key={(r['item_id'],r['arm']):r for r in rows}
    arm_stats={}
    for arm in ARMS:
        chosen=[r for r in rows if r['arm']==arm];correct=sum(r['correct'] for r in chosen)
        arm_stats[arm]={'n':len(chosen),'correct':correct,'accuracy':correct/len(chosen) if chosen else None,
          'status_counts':dict(Counter(r['status'] for r in chosen)),
          'observed_total_tokens':sum(r.get(stage,{}).get('response',{}).get('total_tokens',0) for r in chosen for stage in ('answer','judge')),
          'answer_truncated':sum(r.get('answer',{}).get('response',{}).get('finish_reason')=='length' for r in chosen),
          'judge_truncated':sum(r.get('judge',{}).get('response',{}).get('finish_reason')=='length' for r in chosen),
          'stage_outcomes':{stage:dict(Counter(stage_outcome(r,stage) for r in chosen)) for stage in ('answer','judge')},
          'request_seconds':{stage:sum(r.get('stages',{}).get(stage,{}).get('seconds',0) for r in chosen) for stage in ('answer','judge')}}
    joint=[r for r in records if all(by_key[(r['item_id'],a)]['status']=='ok' for a in ARMS)]
    main=effects(records,by_key);directions=[]
    for pair,positive,negative in [
        (('representation_grounded','representation_synthesis'),'json','source'),
        (('guidance_source','guidance_json'),'synthesis','grounded')]:
        if records and all(main[k]['net_correct']>=5 and main[k]['network_bootstrap_95ci'][0]>0 for k in pair):directions.append(positive)
        if records and all(main[k]['net_correct']<=-5 and main[k]['network_bootstrap_95ci'][1]<0 for k in pair):directions.append(negative)
    return {'questions':len(records),'networks':len({r['source']['network_id'] for r in records}),
      'arms':arm_stats,'effects':main,'both_ok':{'n':len(joint),'effects':effects(joint,by_key),
      'correct':{a:sum(by_key[(r['item_id'],a)]['correct'] for r in joint) for a in ARMS}},
      'directions_for_full_validation':directions,'promoted':False,
      'limitations':'99题等网络抽样；固定来源回答层；单次生成和原裁判；区间未校正五项多重比较，也不含复跑方差。共同正常子集受技术结果筛选，仅作描述。表示因素包含格式适配、位置和问题重复方式。不能替代733题或保留集成绩；超时用量未知。'}

def analyze(work):
    import run_socialmem_answer_ablation as driver
    work=Path(work);verify_analyzer(work);driver.check(work)
    destination=work/'analysis-results'
    if destination.exists() or (work/'completion-seal.json').exists():raise ValueError('analysis already published or sealed')
    audit=driver.verify_terminal(work)
    records=driver.read(work/'sample.json');rows=[driver.read(p) for p in sorted((work/'receipts').glob('*.json'))]
    result=analyze_rows(records,rows);result['request_audit']=audit
    with tempfile.TemporaryDirectory(prefix='.analysis-',dir=work) as folder:
        output=Path(folder)
        driver.write(output/'factor-analysis.json',result)
        driver.write(output/'paired-details.json',[{'item_id':r['item_id'],'network':r['source']['network_id'],
          'arms':{a:{k:next(x for x in rows if x['item_id']==r['item_id'] and x['arm']==a)[k] for k in ('status','correct')} for a in ARMS}} for r in records])
        os.replace(output,destination)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True)
    args=p.parse_args();print(json.dumps(analyze(args.work),ensure_ascii=False,indent=2))
