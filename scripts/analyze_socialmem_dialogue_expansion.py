#!/usr/bin/env python3
"""连续对话组合政策的冻结配对统计；不改评分，不请求模型。"""
import argparse
from collections import Counter,defaultdict
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze_socialmem_grounded_answer as base
import run_socialmem_dialogue_expansion as driver
stats,focus=base.stats,base.focus

def promotion(delta,lower_ci,free_gain,truncated,observed_tokens):
    return delta>=.05 and lower_ci>0 and free_gain>0 and truncated<=15 and observed_tokens<=6370710

def _compute(work,output):
    runner,groups=driver.check(work)
    records=[r for g in groups for r in g['records']];plan=driver.read(work/'execution-plan.json')
    old_rows,new_rows=stats.receipts(Path(plan['parent_work'])),stats.receipts(work)
    old,new=({r['item_id']:r for r in rows} for rows in (old_rows,new_rows))
    if len(new_rows)!=733 or set(new)!=set(plan['question_ids']) or len(new)!=len(new_rows):
        raise ValueError('analysis requires all 733 unique terminal receipts')
    if any(not r.get('terminal') or type(r.get('correct')) is not bool or (r['status']!='ok' and r['correct']) for r in new_rows):
        raise ValueError('nonterminal or nonzero technical failure')
    expected={r['item_id']:r for r in driver.read(work/'native-preflight.json')['rows']}
    contexts=focus.verify_contexts(new_rows,expected);prompts=base.verify_prompts(new_rows,expected)
    report=focus.comparison(records,old,new)
    report.update(native_context_matches=contexts,native_prompt_matches=prompts)
    report['resources']={'parent':focus.focus_resources(old_rows),'candidate':focus.focus_resources(new_rows)}
    free=[r for r in records if r['answer_format']!='multiple_choice']
    report['free_text']=stats.paired_outcomes(free,[old[r['item_id']] for r in free],[new[r['item_id']] for r in free])
    candidate=report['resources']['candidate'];tokens=sum(candidate[s]['total_tokens'] for s in ('answer','judge'))
    report['observed_total_tokens']=tokens
    report['promotion_contract']={'minimum_delta':.05,'lower_ci_positive':True,'free_gain_positive':True,
      'max_final_truncated':15,'max_observed_tokens':6370710}
    report['promoted_on_development']=promotion(report['overall']['delta'],report['overall']['network_bootstrap_delta_95ci'][0],
      report['free_text']['candidate_correct']-report['free_text']['parent_correct'],
      candidate['answer']['finish_reasons'].get('length',0),tokens)
    details=[];transitions=defaultdict(Counter);buckets=defaultdict(list);seed_matches=0
    for record in records:
        key=record['item_id'];before,after=old[key],new[key]
        anchors={a['turn_id'] for a in record['source']['evidence_anchors']}
        hits=[len(anchors&{s['turn_id'] for s in r.get('recall',{}).get('source_refs',[])}) for r in (before,after)]
        coverage=lambda n:'all' if n==len(anchors) else 'partial' if n else 'none'
        transition=coverage(hits[0])+'->'+coverage(hits[1]);counts=transitions[transition]
        counts.update(n=1,parent_correct=int(before['correct']),candidate_correct=int(after['correct']),
          new_correct=int(not before['correct'] and after['correct']),regressed=int(before['correct'] and not after['correct']))
        preserved=False
        if 'recall' in after:
            original=Counter(json.dumps(ref,sort_keys=True) for ref in before['recall']['source_refs'])
            actual=Counter(json.dumps(ref,sort_keys=True) for ref in after['recall']['source_refs'])
            preserved=not (original-actual or Counter(before['recall']['block'].splitlines())-Counter(after['recall']['block'].splitlines()))
            if not preserved:raise ValueError('real receipt lost seed: '+key)
            seed_matches+=1
        detail={'item_id':key,'query_type':record['query_type'],'answer_format':record['answer_format'],
          'parent_correct':before['correct'],'candidate_correct':after['correct'],'status':after['status'],
          'old_hits':hits[0],'new_hits':hits[1],'anchors':len(anchors),'coverage_transition':transition,
          'seed_preserved':preserved,'added_sources':after.get('recall',{}).get('source_diagnostics',{}).get('dialogue_added_sources',0),
          'context_unchanged':before['recall']['block']==after.get('recall',{}).get('block')}
        details.append(detail)
        if record['answer_format']!='multiple_choice':
            bucket=('improved' if after['correct'] and not before['correct'] else 'regressed' if before['correct'] and not after['correct']
              else 'all_anchors_wrong' if hits[1]==len(anchors) and not after['correct'] else None)
            if bucket:buckets[bucket].append(record)
    report['seed_preserved_questions']=seed_matches
    report['anchor_recall']={'denominator':sum(r['anchors'] for r in details),'parent_hits':sum(r['old_hits'] for r in details),
      'candidate_hits':sum(r['new_hits'] for r in details),'coverage_transitions':dict(transitions)}
    report['added_sources']=stats.distribution([r['added_sources'] for r in details])
    report['context_unchanged']={str(flag):{'n':sum(r['context_unchanged']==flag for r in details),
      'parent_correct':sum(r['parent_correct'] for r in details if r['context_unchanged']==flag),
      'candidate_correct':sum(r['candidate_correct'] for r in details if r['context_unchanged']==flag)} for flag in (True,False)}
    report['failure_rows']=[r for r in details if r['status']!='ok']
    recommended=work.parent/'socialmem_20260917_grounded_answer_v2'
    driver.verify_archive(recommended,'5ad3963de6b9e4ce17e5cfa92113edf508724cd0dcbd464a8a9b2aebfc48c01d',332)
    report['recommended_512_comparison']=stats.paired_outcomes(records,stats.receipts(recommended),new_rows)
    report['limits']='733开发题单次运行；策略与容量共同改变，非等上下文预算；原评分固定。区间不包含模型/裁判复跑方差，无新保留或全量成绩；超时用量未知。邻接不证明回复、事件或因果语义。'
    cases=[]
    for bucket,items in sorted(buckets.items()):
        for record in sorted(items,key=lambda r:hashlib.sha256(('dialogue-audit|'+r['item_id']).encode()).hexdigest())[:3]:
            key=record['item_id'];cases.append({'bucket':bucket,'item_id':key,'question':record['question'],'reference':record['answer'],
             'parent_answer':old[key].get('answer',{}).get('raw_xml',''),'candidate_answer':new[key].get('answer',{}).get('raw_xml',''),
             'candidate_judge':new[key].get('judge',{}).get('raw_xml',''),'parent_context':old[key]['recall']['block'],
             'candidate_context':new[key].get('recall',{}).get('block','')})
    stats.write(output/'paired-details.json',details)
    stats.write(output/'mechanism-cases.json',{'selection':'三个结果桶各取固定SHA最小三题；开发事后诊断、非盲审、不校分','cases':cases})
    stats.write(output/'paired-analysis.json',report)
    return report

def analyze(work):
    work=Path(work)
    if (work/'completion-seal.json').exists():raise ValueError('sealed experiment cannot analyze')
    destination=work/'analysis-results'
    if destination.exists():raise ValueError('published analysis cannot be overwritten')
    with tempfile.TemporaryDirectory(prefix='.analysis-',dir=work) as folder:
        output=Path(folder);report=_compute(work,output)
        os.replace(output,destination)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--work',type=Path,required=True)
    work=parser.parse_args().work.resolve();driver.verify_analysis(work)
    frozen=work/'analysis-frozen'/Path(__file__).name
    if Path(__file__).resolve()!=frozen:os.execv(sys.executable,[sys.executable,str(frozen),'--work',str(work)])
    for name in driver.ANALYSIS_FILES:
        loaded=sys.modules.get(Path(name).stem)
        if loaded is not None and Path(loaded.__file__).resolve()!=frozen.parent/name:raise ValueError('analysis import escaped frozen folder: '+name)
    result=analyze(work)
    print(json.dumps({k:result[k] for k in ('overall','free_text','resources','anchor_recall','promoted_on_development')},ensure_ascii=False,indent=2))
