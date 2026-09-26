#!/usr/bin/env python3
"""两阶段政策配对分析、三阶段成本和原生离线回放；不重算评分。"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze_socialmem_grounded_answer as base
import run_socialmem_evidence_answer as driver

def promotion(delta,lower_ci,free_gain,truncated,observed_tokens):
    return delta>=.05 and lower_ci>0 and free_gain>0 and truncated<=15 and observed_tokens<=6370710

def evidence_resources(rows):
    selected=[r for r in rows if 'evidence' in r]
    responses=[r['evidence']['response'] for r in selected]
    return {**{key:sum(r.get(key,0) for r in responses) for key in
                ('prompt_tokens','completion_tokens','total_tokens','attempt_count')},
        'finish_reasons':dict(Counter(r.get('finish_reason','') for r in responses)),
        'fallback_count':sum(r.get('evidence_fallback',False) for r in selected),
        'fallback_reasons':dict(Counter(r.get('evidence_fallback_reason','') for r in selected if r.get('evidence_fallback'))),
        'unusable_response_count':sum(not r.get('ok',False) for r in responses),
        'accepted_quotes':sum(len(r.get('evidence_validation',{}).get('accepted',[])) for r in selected),
        'rejected_quotes':sum(len(r.get('evidence_validation',{}).get('rejected',[])) for r in selected),
        'unknown_budgets':sum(r.get('budget_unknown',False) for r in rows)}

def replay_final_prompts(work,rows,records):
    runner=driver.base.load_runner(work)
    cfg=driver.read(work/'config.json');identity=driver.read(work/'identity.json')
    runner._verify_identity(work,cfg)
    core,*_=runner._frozen_imports(work,cfg,identity)
    mapping={r['item_id']:r for r in records};checked=0
    for row in rows:
        if mapping[row['item_id']]['answer_format']=='multiple_choice':continue
        if 'final_prompt' not in row:
            if row['correct'] or row['status'] not in ('query_failure','answer_failure','technical_failure'):
                raise ValueError('missing final prompt without failure')
            continue
        payload=row['evidence'];raw=payload['response']
        response=core.LLMResponse(payload['raw_xml'],raw['ok'],raw.get('error',''))
        response.finish_reason=raw.get('finish_reason','');response.refusal=raw.get('refusal',False)
        fake=core.FakeLLMAdapter();fake.set_default_response_object(response)
        result=core.answer_with_evidence(mapping[row['item_id']]['question'],row['recall']['block'],fake)
        if (result.evidence_prompt!=row['evidence_prompt'] or result.answer_prompt!=row['final_prompt']
            or json.loads(result.validation_json)!=row['evidence_validation']
            or result.fallback!=row['evidence_fallback'] or result.fallback_reason!=row['evidence_fallback_reason']):
            raise ValueError('native two-pass replay changed: '+row['item_id'])
        checked+=1
    return checked

def _compute(work,output_dir):
    report=base.analyze(work,output_dir=output_dir);rows=base.stats.receipts(work)
    plan=driver.read(work/'execution-plan.json');ids=set(plan['question_ids'])
    records=[r for r in map(json.loads,(work/'corpus.jsonl').read_text().splitlines()) if r['item_id'] in ids]
    report['native_final_prompt_matches']=replay_final_prompts(work,rows,records)
    evidence=evidence_resources(rows);report['resources']['candidate']['evidence']=evidence
    candidate=report['resources']['candidate'];tokens=sum(candidate[s]['total_tokens'] for s in ('evidence','answer','judge'))
    report['observed_total_tokens']=tokens
    report['promotion_contract']={'minimum_delta':.05,'lower_ci_positive':True,'free_gain_positive':True,
        'max_final_truncated':15,'max_observed_tokens':6370710}
    report['promoted_on_development']=promotion(report['overall']['delta'],report['overall']['network_bootstrap_delta_95ci'][0],
        report['free_text']['candidate_correct']-report['free_text']['parent_correct'],
        candidate['answer']['finish_reasons'].get('length',0),tokens)
    recommended=work.parent/'socialmem_20260917_grounded_answer_v2'
    if driver.sha(recommended/'completion-seal.json')!='5ad3963de6b9e4ce17e5cfa92113edf508724cd0dcbd464a8a9b2aebfc48c01d':
        raise ValueError('recommended 512 archive changed')
    driver.base.verify_files(recommended,driver.read(recommended/'completion-seal.json')['files'])
    old=base.stats.receipts(recommended)
    report['recommended_512_comparison']=base.stats.paired_outcomes(records,old,rows)
    report['limits']='733开发题单次运行；自由回答增加一次证据调用，不是等计算预算；MC完整请求不变；原评分固定。区间不包含模型/裁判复跑方差，无新保留集或全量成绩；超时用量未知。'
    base.stats.write(output_dir/'paired-analysis.json',report)
    return report

def analyze(work):
    work=Path(work)
    if (work/'completion-seal.json').exists():raise ValueError('sealed experiment cannot analyze')
    with tempfile.TemporaryDirectory(prefix='.analysis-',dir=work) as scratch:
        staging=Path(scratch);report=_compute(work,staging)
        # 所有验证通过后才发布；主验收报告最后原子替换。
        for name in ('paired-details.json','mechanism-cases.json','paired-analysis.json'):
            os.replace(staging/name,work/name)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--work',type=Path,required=True)
    work=parser.parse_args().work.resolve();driver.verify_analysis(work)
    frozen=work/'analysis-frozen'/Path(__file__).name
    if Path(__file__).resolve()!=frozen:
        os.execv(sys.executable,[sys.executable,str(frozen),'--work',str(work)])
    for name in driver.ANALYSIS_FILES:
        loaded=sys.modules.get(Path(name).stem)
        if loaded is not None and Path(loaded.__file__).resolve()!=frozen.parent/name:
            raise ValueError('analysis module loaded outside frozen directory: '+name)
    result=analyze(work)
    print(json.dumps({k:result[k] for k in ('overall','free_text','resources','native_final_prompt_matches','promoted_on_development')},ensure_ascii=False,indent=2))
