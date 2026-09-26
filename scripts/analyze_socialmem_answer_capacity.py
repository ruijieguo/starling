#!/usr/bin/env python3
"""回答容量配对统计与事前门槛；复用统计及身份核验，不更改评分。"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze_socialmem_grounded_answer as base


def promotion(delta, lower_ci, free_gain, truncated, observed_tokens):
    return (delta >= .01 and lower_ci > 0 and free_gain > 0
            and truncated <= 15 and observed_tokens <= 3803932)


def analyze(work):
    work=Path(work);report=base.analyze(work)
    report['limits'] = ('733开发题单次复跑；全部提示不变，152选择题的回答上限也由512增至1024；'
                        '区间不包含模型与裁判采样波动；无新保留集或全量成绩')
    candidate=report['resources']['candidate']
    truncated=candidate['answer']['finish_reasons'].get('length',0)
    tokens=sum(candidate[stage]['total_tokens'] for stage in ('answer','judge'))
    report['promotion_contract']={'minimum_delta':.01,'lower_ci_positive':True,'free_gain_positive':True,
                                  'max_truncated':15,'max_observed_tokens':3803932}
    report['promoted_on_development']=promotion(report['overall']['delta'],
        report['overall']['network_bootstrap_delta_95ci'][0],
        report['free_text']['candidate_correct']-report['free_text']['parent_correct'],truncated,tokens)
    rows=base.stats.receipts(work)
    ids={r['item_id'] for r in map(json.loads,(work/'corpus.jsonl').read_text().splitlines())
         if r['answer_format']!='multiple_choice'}
    answers=[r for r in rows if r['item_id'] in ids and r.get('answer',{}).get('response',{}).get('ok')]
    # English whitespace word counts are an observational statistic, not a parser or scoring rule.
    lengths=[len(r['answer']['raw_xml'].split()) for r in answers]
    report['free_answer_words']={'method':'whitespace split on successful native answer text',
        'distribution':base.stats.distribution(lengths),'over_180':sum(n>180 for n in lengths),
        'missing_or_failed_answers':len([r for r in rows if r['item_id'] in ids])-len(answers)}
    base.stats.write(work/'paired-analysis.json',report)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True)
    r=analyze(p.parse_args().work)
    print(json.dumps({k:r[k] for k in ('overall','free_text','free_answer_words','promoted_on_development')},ensure_ascii=False,indent=2))
