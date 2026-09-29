#!/usr/bin/env python3
"""Build the source-backed M2.5 report without rendering prompts or answers."""
import argparse
from collections import Counter, defaultdict
import hashlib
from html import escape
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ('glm-5.3-flash', 'deepseek-v4-flash-0731')
TASKS = ('prime-counterexample', 'ns-scaling-algebra-v1')
ARMS = ('legacy-card', 'unified-task-schema')
ARM_LABELS = {'legacy-card': '原任务措辞 + 输出卡', 'unified-task-schema': '统一任务措辞 + 输出卡'}
TASK_LABELS = {'prime-counterexample': '整数反例', 'ns-scaling-algebra-v1': 'NS 缩放代数'}


def esc(value):
    return escape(str(value))


def rows(items):
    return ''.join('<tr>' + ''.join('<td>' + esc(cell) + '</td>' for cell in item) + '</tr>' for item in items)


def build():
    summary_path = ROOT / 'reports/task-continuation-v1/summary.json'
    prior_path = ROOT / 'reports/task-continuation-v1/prior-analysis.json'
    raw, prior_raw = summary_path.read_bytes(), prior_path.read_bytes()
    data, prior = json.loads(raw), json.loads(prior_raw)
    results, unstarted = data['results'], data['unstarted']
    if len(results) + len(unstarted) != 16:
        raise ValueError('The report requires all 16 planned cells, including unstarted cells')
    by_case = {}
    groups = defaultdict(lambda: dict(planned=0, started=0, complete=0, valid=0, math=0, technical=0))
    pairs = defaultdict(dict)
    cell_rows = []
    for started, records in ((True, results), (False, unstarted)):
        for record in records:
            case = record['case']
            model, task, arm = case['model'], case['task_id'], case['contract']
            if model not in MODELS or task not in TASKS or arm not in ARMS or case['case_id'] in by_case:
                raise ValueError('Unexpected or duplicate planned cell')
            by_case[case['case_id']] = record
            group = groups[(model, arm, task)]
            group['planned'] += 1
            group['started'] += int(started)
            complete = bool(started and record['status']['complete'])
            technical = bool(started and (not complete or record['verdict']['status'] == 'TECHNICAL_FAILURE'))
            valid = bool(complete and not technical and record.get('envelope_status') == 'valid')
            passed = bool(valid and record['verdict'].get('passed'))
            group['complete'] += int(complete)
            group['valid'] += int(valid)
            group['math'] += int(passed)
            group['technical'] += int(technical)
            pairs[(model, task, case['repetition'])][arm] = dict(complete=complete, valid=valid, passed=passed)
            if started:
                outcome = '技术失败' if technical else ('格式合格' if valid else '格式失败')
                math = '通过' if passed else ('未通过' if valid else '未获格式准入')
                errors = sorted({str(error.get('category', 'unspecified')) for error in record.get('errors', [])})
                note = ', '.join(errors) or str(record['verdict']['status'])
            else:
                outcome, math, note = '未启动', '未评估', record['reason']
            cell_rows.append((model, TASK_LABELS[task], ARM_LABELS[arm], case['repetition'] + 1, outcome, math, note))
    if len(groups) != 8 or any(g['planned'] != 2 for g in groups.values()):
        raise ValueError('Expected eight model/arm/task cells with two repetitions each')
    totals = {key: sum(g[key] for g in groups.values()) for key in next(iter(groups.values()))}
    ns_passed = sum(g['math'] for (_, _, task), g in groups.items() if task == TASKS[1])
    complete_pairs = [p for p in pairs.values() if len(p) == 2 and all(v['complete'] for v in p.values())]
    paired = Counter()
    for pair in complete_pairs:
        left, right = pair[ARMS[0]]['valid'], pair[ARMS[1]]['valid']
        paired['both_valid' if left and right else 'unified_only' if right else 'legacy_only' if left else 'neither_valid'] += 1
    budget = data['budget']
    safe = {'planned': totals['planned'], 'started': totals['started'], 'complete': totals['complete'],
            'format_valid': totals['valid'], 'math_passed': totals['math'], 'technical_failure': totals['technical'],
            'unstarted': len(unstarted), 'ns_math_passed': ns_passed, 'complete_pairs': len(complete_pairs),
            'paired_format': dict(paired), 'source_commit': data['experiment']['source_commit'],
            'execution_mode': data['metadata'].get('execution_mode'),
            'slurm_job_id': data['metadata'].get('slurm_job_id'),
            'reserved_calls': budget['reserved_calls'], 'known_total_tokens': budget['known_total_tokens'],
            'unknown_usage_attempts': budget['unknown_usage_attempts'],
            'frontier_proof_verified': False, 'population_efficacy_verified': False}
    if safe['slurm_job_id'] is not None or safe['reserved_calls'] > 16:
        raise ValueError('This report describes at most 16 gateway calls with no Slurm allocation')
    group_rows = []
    for model in MODELS:
        for task in TASKS:
            for arm in ARMS:
                g = groups[(model, arm, task)]
                group_rows.append((model, TASK_LABELS[task], ARM_LABELS[arm],
                                   f"{g['started']} / {g['planned']}", f"{g['valid']} / {g['planned']}",
                                   f"{g['math']} / {g['planned']}", g['technical'], g['planned'] - g['started']))
    history = prior['format_reasons']
    baseline, card = history['baseline']['valid'], history['output-card']['valid']
    complete_tokens = prior['completion_tokens']
    title = f"已启动 {totals['started']} / 16 项，格式合格 {totals['valid']} 项。"
    ns_text = (f"NS 缩放代数有 {ns_passed} 项通过精确证书检查。" if ns_passed else 'NS 缩放代数仍无通过的精确证书。')
    lead = f"通过现有院内网关完成有限任务诊断：{totals['complete']} 项收到完整结果，{totals['technical']} 项技术失败，{len(unstarted)} 项未启动。{ns_text}本轮没有测量 Agent 群体组织效果，也没有得到 Navier–Stokes 前沿问题证明。"
    values = {
        'TITLE': esc(title), 'LEAD': esc(lead), 'CALLS': esc(safe['reserved_calls']),
        'VALID': esc(totals['valid']), 'MATH': esc(totals['math']), 'STARTED': esc(totals['started']),
        'COMPLETE': esc(totals['complete']), 'TECHNICAL': esc(totals['technical']), 'UNSTARTED': esc(len(unstarted)),
        'GROUP_ROWS': rows(group_rows), 'CELL_ROWS': rows(cell_rows), 'NS_TEXT': esc(ns_text),
        'PAIRS': esc(len(complete_pairs)), 'BOTH': esc(paired['both_valid']),
        'NEW_ONLY': esc(paired['unified_only']), 'OLD_ONLY': esc(paired['legacy_only']),
        'NEITHER': esc(paired['neither_valid']), 'TOKENS': esc(safe['known_total_tokens']),
        'UNKNOWN': esc(safe['unknown_usage_attempts']), 'SOURCE': esc(safe['source_commit']),
        'OLD_SOURCE': esc(prior['historical_source_commit']), 'HISTORY_BASE': esc(baseline),
        'HISTORY_CARD': esc(card), 'HISTORY_COUNT': esc(prior['cases']),
        'TOKEN_MIN': esc(complete_tokens['min']), 'TOKEN_MAX': esc(complete_tokens['max']),
        'PRIOR_HASH': hashlib.sha256(prior_raw).hexdigest(), 'HASH': hashlib.sha256(raw).hexdigest(),
        'EVIDENCE': esc(json.dumps(safe, ensure_ascii=False, indent=2))}
    template = (ROOT / 'templates/task-milestone-v1.html').read_text()
    for key, value in values.items():
        template = template.replace('@@' + key + '@@', value)
    if '@@' in template:
        raise ValueError('Unresolved template field')
    return template


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'milestones/m2-5-task-continuation-v1.html')
    args = parser.parse_args()
    args.output.write_text(build())
    print('Built M2.5 task analysis and bounded gateway submission report.')
