#!/usr/bin/env python3
"""冻结人物检索评测的配对统计；复用已测试统计函数，绝不重算评分。"""
import argparse
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze_socialmem_k30 as stats


def verify_contexts(rows,expected):
    ids=[r['item_id'] for r in rows]
    if len(ids)!=len(set(ids)) or set(ids)!=set(expected):raise ValueError('context question set changed')
    checked=0
    for r in rows:
        if 'recall' not in r:
            if r.get('status') not in {'query_failure','technical_failure','budget_failure','ingestion_failure'} or r.get('correct') is not False:
                raise ValueError('missing context without a scored failure: '+r['item_id'])
            continue
        e=expected[r['item_id']];recall=r['recall']
        if hashlib.sha256(recall['block'].encode()).hexdigest()!=e['block_sha256'] or recall['source_refs']!=e['source_refs']:
            raise ValueError('native context or reference mismatch: '+r['item_id'])
        checked+=1
    return checked


def focus_resources(rows):
    # Unknown context is reported separately; failure rows still contribute requests and usage.
    available=[r for r in rows if 'recall' in r]
    normalized=[{'native_attempt_count':0,'embedding_request_delta':0,'stages':{},
        'recall':{'context_bytes':0,'source_count':0},**r} for r in rows]
    result=stats.resources(normalized)
    result['contexts']=stats.distribution([r['recall']['context_bytes'] for r in available])
    result['sources']=stats.distribution([r['recall']['source_count'] for r in available])
    result['unavailable_contexts']=len(rows)-len(available)
    result['unavailable_attempt_counts']=sum('native_attempt_count' not in r for r in rows)
    return result


def comparison(records,old,new):
    report={'overall':stats.paired_outcomes(records,list(old.values()),list(new.values()))}
    for key in ['answer_format','query_type']:
        report[key]={}
        for value in sorted({r[key] for r in records}):
            selected=[r for r in records if r[key]==value]
            report[key][value]=stats.paired_outcomes(selected,[old[r['item_id']] for r in selected],[new[r['item_id']] for r in selected])
    report['by_network']={}
    for network in sorted({r['source']['network_id'] for r in records}):
        rs=[r for r in records if r['source']['network_id']==network]
        report['by_network'][network]={'n':len(rs),'parent_correct':sum(old[r['item_id']]['correct'] for r in rs),'candidate_correct':sum(new[r['item_id']]['correct'] for r in rs)}
    return report


def analyze(work):
    work=Path(work);plan=stats.read(work/'execution-plan.json');cfg=stats.read(work/'config.json')
    all_records=[json.loads(s) for s in (work/'corpus.jsonl').read_text().splitlines()]
    records=[r for r in all_records if r['item_id'] in plan['question_ids']]
    new_rows=stats.receipts(work);new={r['item_id']:r for r in new_rows}
    expected={r['item_id']:r['profiles'][cfg['source_strategy']] for r in stats.read(work/'native-ablation.json')['rows']}
    checked=verify_contexts(new_rows,expected)
    report={'scope':'733 development questions; single run; unchanged scoring',
            'all_contexts_match_native_preflight':checked,'unavailable_contexts':len(new_rows)-checked,
            'comparisons':{},'resources':{'candidate':focus_resources(new_rows)}}
    maps={}
    for tag,parent in [('k30',Path(plan['parent_work'])),('k10',Path(plan['baseline_work']))]:
        rows=[r for r in stats.receipts(parent) if r['item_id'] in new]
        old={r['item_id']:r for r in rows};maps[tag]=old
        report['comparisons'][tag]=comparison(records,old,new);report['resources'][tag]=focus_resources(rows)
    old=maps['k30'];transitions=defaultdict(lambda:Counter())
    detail=[];same_answers=[];case_buckets=defaultdict(list)
    for r in records:
        key=r['item_id'];before,after=old[key],new[key]
        anchors={a['turn_id'] for a in r['source']['evidence_anchors']}
        hits=[len(anchors&{s['turn_id'] for s in x.get('recall',{}).get('source_refs',[])}) for x in [before,after]]
        coverage=lambda n:'all' if n==len(anchors) else 'partial' if n else 'none'
        transition=coverage(hits[0])+'->'+coverage(hits[1]);b=transitions[transition]
        b['n']+=1;b['new_correct']+=not before['correct'] and after['correct'];b['regressed']+=before['correct'] and not after['correct'];b['parent_correct']+=before['correct'];b['candidate_correct']+=after['correct']
        row={'item_id':key,'query_type':r['query_type'],'format':r['answer_format'],
             'parent_correct':before['correct'],'candidate_correct':after['correct'],
             'old_hits':hits[0],'new_hits':hits[1],'anchors':len(anchors),'transition':transition,
             'status':after['status'],'activated':'focused_holders' in after.get('recall',{}).get('source_diagnostics',{}),
             'context_unchanged':'recall' in before and 'recall' in after and before['recall']['block']==after['recall']['block']}
        detail.append(row)
        if r['answer_format']!='multiple_choice' and before.get('answer',{}).get('raw_xml')==after.get('answer',{}).get('raw_xml'):
            same_answers.append({'item_id':key,'label_changed':before['correct']!=after['correct'],'status_same':before['status']==after['status']})
        bucket='improved' if not before['correct'] and after['correct'] else 'regressed' if before['correct'] and not after['correct'] else 'all_anchors_wrong' if hits[1]==len(anchors) and not after['correct'] else None
        if bucket:case_buckets[bucket].append(r)
    report['anchor_recall']={'denominator':sum(r['anchors'] for r in detail),'parent_hits':sum(r['old_hits'] for r in detail),'candidate_hits':sum(r['new_hits'] for r in detail),'coverage_transitions':dict(transitions)}
    report['same_answer_free_text']={'pairs':len(same_answers),'changed_labels':sum(r['label_changed'] for r in same_answers),'rows':same_answers}
    for field in ['activated','context_unchanged']:
        report[field]={str(flag):{'n':sum(r[field]==flag for r in detail),'parent_correct':sum(r['parent_correct'] for r in detail if r[field]==flag),'candidate_correct':sum(r['candidate_correct'] for r in detail if r[field]==flag)} for flag in [True,False]}
    report['failure_rows']=[{'item_id':r['item_id'],'status':r['status'],'error':r.get('error','')} for r in new_rows if r['status']!='ok']
    cases=[]
    for bucket,rs in case_buckets.items():
        chosen=sorted(rs,key=lambda r:hashlib.sha256(('focus-audit|'+r['item_id']).encode()).hexdigest())[:3]
        for r in chosen:
            key=r['item_id'];cases.append({'bucket':bucket,'item_id':key,'question':r['question'],'reference':r['answer'],'anchors':r['source']['evidence_anchors'],
                'parent_answer':old[key].get('answer',{}).get('raw_xml',''),'candidate_answer':new[key].get('answer',{}).get('raw_xml',''),
                'candidate_judge':new[key].get('judge',{}).get('raw_xml',''),'candidate_context':new[key].get('recall',{}).get('block','')})
    stats.write(work/'paired-analysis.json',report);stats.write(work/'paired-details.json',detail)
    stats.write(work/'mechanism-cases.json',{'selection':'按预定三类结果桶，各取固定SHA最小三题；诊断样本，不估计总体误判率','cases':cases})
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True);args=p.parse_args()
    result=analyze(args.work);print(json.dumps({k:v['overall'] for k,v in result['comparisons'].items()},ensure_ascii=False,indent=2))
