#!/usr/bin/env python3
"""证据约束回答的冻结回执配对分析；不修改评分，不请求模型。"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_socialmem_source_focus as focus

stats = focus.stats


def verify_prompts(rows, expected):
    ids = [r['item_id'] for r in rows]
    if len(ids) != len(set(ids)) or set(ids) != set(expected):
        raise ValueError('prompt question set changed')
    checked = 0
    for row in rows:
        if 'prompt' not in row:
            if row.get('status') not in {'query_failure','technical_failure','budget_failure','ingestion_failure','answer_failure'} or row.get('correct') is not False:
                raise ValueError('missing prompt without a scored failure')
            continue
        if hashlib.sha256(row['prompt'].encode()).hexdigest() != expected[row['item_id']]['prompt_sha256']:
            raise ValueError('native answer prompt changed: ' + row['item_id'])
        checked += 1
    return checked


def promotion(delta, lower_ci, free_gain):
    return delta >= .03 and lower_ci > 0 and free_gain > 0


def analyze(work, output_dir=None):
    work = Path(work); plan = stats.read(work / 'execution-plan.json')
    parent = Path(plan['parent_work']); ids = set(plan['question_ids'])
    records = [json.loads(line) for line in (work / 'corpus.jsonl').read_text().splitlines()]
    records = [r for r in records if r['item_id'] in ids]
    old_rows, new_rows = stats.receipts(parent), stats.receipts(work)
    old, new = ({r['item_id']:r for r in rows} for rows in (old_rows,new_rows))
    expected = {r['item_id']:r for r in stats.read(work/'native-preflight.json')['rows']}
    contexts, prompts = focus.verify_contexts(new_rows, expected), verify_prompts(new_rows, expected)
    report = focus.comparison(records, old, new)
    report['native_context_matches'], report['native_prompt_matches'] = contexts, prompts
    report['resources'] = {'parent':focus.focus_resources(old_rows), 'candidate':focus.focus_resources(new_rows)}
    report['limits'] = '733开发题单次复跑；152选择题输入不变；区间不包含模型与裁判采样波动；无新保留集或全量成绩'
    free = [r for r in records if r['answer_format'] != 'multiple_choice']
    report['free_text'] = stats.paired_outcomes(free,[old[r['item_id']] for r in free],[new[r['item_id']] for r in free])
    report['promoted_on_development'] = promotion(report['overall']['delta'],
        report['overall']['network_bootstrap_delta_95ci'][0],
        report['free_text']['candidate_correct']-report['free_text']['parent_correct'])
    coverage, buckets = defaultdict(list), defaultdict(list)
    details = []
    for record in records:
        key = record['item_id']; before, after = old[key], new[key]
        anchors = {a['turn_id'] for a in record['source']['evidence_anchors']}
        # The evidence is fixed: coverage is always based on the parent even for candidate query failures.
        hit = len(anchors & {s['turn_id'] for s in before['recall']['source_refs']})
        tag = 'all' if hit == len(anchors) else 'partial' if hit else 'none'
        coverage[tag].append(record)
        detail = {'item_id':key, 'query_type':record['query_type'], 'answer_format':record['answer_format'],
            'parent_correct':before['correct'], 'candidate_correct':after['correct'], 'coverage':tag,
            'hits':hit, 'anchors':len(anchors), 'status':after['status']}
        details.append(detail)
        if record['answer_format'] != 'multiple_choice':
            bucket = ('improved' if after['correct'] and not before['correct'] else
                      'regressed' if before['correct'] and not after['correct'] else
                      'all_anchors_wrong' if tag=='all' and not after['correct'] else None)
            if bucket: buckets[bucket].append(record)
    report['fixed_anchor_coverage'] = {k:stats.paired_outcomes(rs,[old[r['item_id']] for r in rs],
                                               [new[r['item_id']] for r in rs]) for k,rs in coverage.items()}
    report['failures'] = [r for r in details if r['status'] != 'ok']
    cases = []
    for bucket, rs in sorted(buckets.items()):
        for record in sorted(rs,key=lambda r:hashlib.sha256(('grounded-audit|'+r['item_id']).encode()).hexdigest())[:3]:
            key=record['item_id'];cases.append({'bucket':bucket,'item_id':key,'question':record['question'],
                'reference':record['answer'],'parent_answer':old[key].get('answer',{}).get('raw_xml',''),
                'candidate_answer':new[key].get('answer',{}).get('raw_xml',''),
                'candidate_judge':new[key].get('judge',{}).get('raw_xml',''),
                'context':old[key]['recall']['block']})
    destination=Path(output_dir) if output_dir is not None else work
    stats.write(destination/'paired-analysis.json',report);stats.write(destination/'paired-details.json',details)
    stats.write(destination/'mechanism-cases.json',{'selection':'三个结果桶各取固定SHA最小3题；开发诊断、非盲审、不改分','cases':cases})
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--work',type=Path,required=True)
    report=analyze(parser.parse_args().work)
    print(json.dumps({'overall':report['overall'],'free_text':report['free_text'],
                      'promoted_on_development':report['promoted_on_development']},ensure_ascii=False,indent=2))
