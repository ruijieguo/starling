#!/usr/bin/env python3
"""单次综合回答政策的冻结配对统计；不改评分，不请求模型。"""
import argparse
from collections import Counter,defaultdict
import hashlib
import json
import os
import sqlite3
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze_socialmem_grounded_answer as base
import run_socialmem_synthesis_answer as driver
stats,focus=base.stats,base.focus

def promotion(delta,lower_ci,free_gain,truncated,observed_tokens):
    return delta>=.05 and lower_ci>0 and free_gain>0 and truncated<=15 and observed_tokens<=6060610

def paired_subset(records,old,new):
    if not records:
        return {'n':0,'parent_correct':0,'candidate_correct':0,'parent_accuracy':None,
                'candidate_accuracy':None,'delta':None,'new_correct':0,'regressed':0,
                'networks':0,'network_bootstrap_delta_95ci':None,'parent_status':{},'candidate_status':{}}
    return stats.paired_outcomes(records,[old[r['item_id']] for r in records],[new[r['item_id']] for r in records])

def verify_terminal_run(work,rows,records,fingerprint,budget):
    """发布成绩前核对动态运行证据；失败计零且未知调用保守计入预算。"""
    def require(value,message):
        if not value:raise ValueError(message)
    by_id={r['item_id']:r for r in rows};record_by_id={r['item_id']:r for r in records}
    require(len(rows)==len(by_id)==len(records)==len(record_by_id) and by_id.keys()==record_by_id.keys(),'terminal question set mismatch')
    started=list(work.glob('runs/*/questions/*.started'));paths=list(work.glob('runs/*/questions/*.json'))
    require(len(started)==len(rows) and {p.with_suffix('.json') for p in started}==set(paths),'started receipt set mismatch')
    ledger_path=work/'request-ledger.sqlite';require(ledger_path.is_file(),'request ledger missing')
    with sqlite3.connect(f'file:{ledger_path}?mode=ro',uri=True) as con:
        con.row_factory=sqlite3.Row;ledger_rows=[dict(r) for r in con.execute('select * from reservations')]
    ledger={r['id']:r for r in ledger_rows}
    require(len(ledger_rows)==len(ledger)==len(rows),'reservation set mismatch')
    seen=set();seen_ids=set();known_total=charged=unknown_count=0
    for path in started:
        start=driver.read(path);key=start['item_id'];require(key in by_id and key not in seen_ids,'started question mismatch')
        seen_ids.add(key);row=by_id[key];reservation_id=start['reservation']['id']
        require(reservation_id in ledger and reservation_id not in seen,'reservation identity mismatch');seen.add(reservation_id)
        reservation=ledger[reservation_id]
        require(row.get('terminal') is True and type(row.get('correct')) is bool and
                (row.get('status')=='ok' or row['correct'] is False),'invalid terminal receipt')
        require(start.get('fingerprint')==row.get('fingerprint')==fingerprint,'receipt fingerprint mismatch')
        require(row.get('embedding_request_delta',0)==0 and 'evidence' not in row,'unapproved model stage')
        known=0
        for stage in ('answer','judge'):
            response=row.get(stage,{}).get('response',{});count=response.get('attempt_count',0)
            attempts=response.get('http_attempts',[])
            require(type(count) is int and 0<=count<=1 and len(attempts)==count,'invalid native attempt count')
            if attempts:
                require(attempts[0].get('attempt')==1 and attempts[0].get('response_body')==response.get('raw_http_response',''),'HTTP receipt mismatch')
            known+=count
        require(record_by_id[key]['answer_format']!='multiple_choice' or 'judge' not in row,'choice unexpectedly judged')
        unknown=bool(row.get('budget_unknown',False));failed=row['correct'] is False and row['status']!='ok'
        missing_allowed=failed and (unknown or (row['status']=='query_failure' and known==0 and 'answer' not in row and 'judge' not in row))
        require(('native_attempt_count' in row or missing_allowed) and row.get('native_attempt_count',known)==known,'native receipt total mismatch')
        bound=1+int(record_by_id[key]['answer_format']!='multiple_choice')
        require(reservation['upper_bound']==start['reservation']['upper_bound']==bound and known<=bound,'reservation bound mismatch')
        require(reservation['scope']==path.parents[1].name and reservation['stage']=='question:'+path.stem,'reservation scope mismatch')
        if unknown:
            require(failed and reservation['state'] in ('charged_upper','reserved') and reservation['actual'] is None,'unknown requests not charged conservatively')
            charged+=bound;unknown_count+=1
        else:
            require(reservation['state']=='settled' and reservation['actual']==known,'known requests not settled exactly')
            charged+=known
        known_total+=known
    require(seen==set(ledger) and seen_ids==set(by_id) and 0<=known_total<=charged<=budget,'request budget or coverage mismatch')
    return {'verified':True,'questions':len(rows),'known_requests':known_total,'charged_requests':charged,
            'unknown_budget_receipts':unknown_count,'http_budget':budget}

def _compute(work,output):
    runner,groups=driver.check(work)
    records=[r for g in groups for r in g['records']];plan=driver.read(work/'execution-plan.json')
    old_rows,new_rows=stats.receipts(Path(plan['parent_work'])),stats.receipts(work)
    old,new=({r['item_id']:r for r in rows} for rows in (old_rows,new_rows))
    if len(new_rows)!=733 or set(new)!=set(plan['question_ids']) or len(new)!=len(new_rows):
        raise ValueError('analysis requires all 733 unique terminal receipts')
    if any(not r.get('terminal') or type(r.get('correct')) is not bool or (r['status']!='ok' and r['correct']) for r in new_rows):
        raise ValueError('nonterminal or nonzero technical failure')
    config=driver.read(work/'config.json')
    terminal_audit=verify_terminal_run(work,new_rows,records,runner._verify_identity(work,config),config['http_budget'])
    expected={r['item_id']:r for r in driver.read(work/'native-preflight.json')['rows']}
    contexts=focus.verify_contexts(new_rows,expected);prompts=base.verify_prompts(new_rows,expected)
    report=focus.comparison(records,old,new)
    report['terminal_run_audit']=terminal_audit
    report.update(native_context_matches=contexts,native_prompt_matches=prompts)
    report['resources']={'parent':focus.focus_resources(old_rows),'candidate':focus.focus_resources(new_rows)}
    free=[r for r in records if r['answer_format']!='multiple_choice']
    report['free_text']=stats.paired_outcomes(free,[old[r['item_id']] for r in free],[new[r['item_id']] for r in free])
    candidate=report['resources']['candidate'];tokens=sum(candidate[s]['total_tokens'] for s in ('answer','judge'))
    report['observed_total_tokens']=tokens
    report['promotion_contract']={'minimum_delta':.05,'lower_ci_positive':True,'free_gain_positive':True,
      'max_final_truncated':15,'max_observed_tokens':6060610}
    report['promoted_on_development']=promotion(report['overall']['delta'],report['overall']['network_bootstrap_delta_95ci'][0],
      report['free_text']['candidate_correct']-report['free_text']['parent_correct'],
      candidate['answer']['finish_reasons'].get('length',0),tokens)
    details=[];transitions=defaultdict(Counter);buckets=defaultdict(list);source_matches=packet_matches=choice_matches=0
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
            preserved=(before['recall']['block']==after['recall']['block'] and
                       before['recall']['source_refs']==after['recall']['source_refs'])
            if not preserved:raise ValueError('real receipt changed sources: '+key)
            source_matches+=1
        if 'prompt' in after:
            if record['answer_format']=='multiple_choice':
                if after['prompt']!=before['prompt']:raise ValueError('real choice prompt changed: '+key)
                choice_matches+=1
            else:
                embedded=json.loads(after['prompt'].rsplit('\n',1)[-1])
                if embedded!=driver.expected_packet(str(record['question']),before['recall']['block']):
                    raise ValueError('real synthesis packet changed: '+key)
                packet_matches+=1
        detail={'item_id':key,'query_type':record['query_type'],'answer_format':record['answer_format'],
          'parent_correct':before['correct'],'candidate_correct':after['correct'],'status':after['status'],
          'old_hits':hits[0],'new_hits':hits[1],'anchors':len(anchors),'coverage_transition':transition,
          'sources_unchanged':preserved,
          'context_unchanged':before['recall']['block']==after.get('recall',{}).get('block')}
        details.append(detail)
        if record['answer_format']!='multiple_choice':
            bucket=('improved' if after['correct'] and not before['correct'] else 'regressed' if before['correct'] and not after['correct']
              else 'all_anchors_wrong' if hits[1]==len(anchors) and not after['correct'] else None)
            if bucket:buckets[bucket].append(record)
    report['unchanged_source_questions']=source_matches
    report['real_lossless_packets']=packet_matches;report['real_choice_prompt_matches']=choice_matches
    report['anchor_recall']={'denominator':sum(r['anchors'] for r in details),'parent_hits':sum(r['old_hits'] for r in details),
      'candidate_hits':sum(r['new_hits'] for r in details),'coverage_transitions':dict(transitions)}
    report['context_unchanged']={str(flag):{'n':sum(r['context_unchanged']==flag for r in details),
      'parent_correct':sum(r['parent_correct'] for r in details if r['context_unchanged']==flag),
      'candidate_correct':sum(r['candidate_correct'] for r in details if r['context_unchanged']==flag)} for flag in (True,False)}
    report['failure_rows']=[r for r in details if r['status']!='ok']
    recommended=work.parent/'socialmem_20260917_grounded_answer_v2'
    driver.verify_archive(recommended,'5ad3963de6b9e4ce17e5cfa92113edf508724cd0dcbd464a8a9b2aebfc48c01d',332)
    report['recommended_512_comparison']=stats.paired_outcomes(records,stats.receipts(recommended),new_rows)
    capacity=work.parent/'socialmem_20260918_answer_capacity_v2'
    driver.verify_archive(capacity,'75f49fd3fa3ae3d78faa8e36d5c75987b933e85ccf44c39b4542a98b720cea06',345)
    report['capacity_1024_comparison']=stats.paired_outcomes(records,stats.receipts(capacity),new_rows)
    for label,subset in [('both_technically_ok',[r for r in records if old[r['item_id']]['status']==new[r['item_id']]['status']=='ok']),
                         ('unchanged_choice_prompts',[r for r in records if r['answer_format']=='multiple_choice'])]:
        report[label]=paired_subset(subset,old,new)
    report['limits']='733开发题单次运行；来源与回答容量相同，JSON表示改变输入token数；原评分固定。区间不包含模型/裁判复跑方差，无新保留或全量成绩；超时用量未知。生成政策不等于已验证的范围、时序、因果或社会语义校验。'
    cases=[]
    for bucket,items in sorted(buckets.items()):
        for record in sorted(items,key=lambda r:hashlib.sha256(('synthesis-case|'+r['item_id']).encode()).hexdigest())[:3]:
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
