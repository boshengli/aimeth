#!/usr/bin/env python3
"""Describe frozen public M2.3 receipts without changing historical scores."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'archives/role-contract-v2'))
sys.path.insert(0, str(ROOT / 'tools'))
from aimeth_design.role_routing import parse_envelope
from aimeth_evaluation.pde_scaling import evaluate as evaluate_scaling
from role_evidence import envelope_reason


def analysis():
    sources = {
        'summary': ROOT / 'reports/role-contract-v2/summary.json',
        'events': ROOT / 'reports/role-contract-v2/events.jsonl',
        'frozen_parser': ROOT / 'archives/role-contract-v2/aimeth_design/role_routing.py',
        'frozen_scaling_evaluator': ROOT / 'archives/role-contract-v2/aimeth_evaluation/pde_scaling.py',
        'diagnostic_parser': ROOT / 'tools/role_evidence.py',
    }
    summary = json.loads(sources['summary'].read_text())
    grouped = defaultdict(list)
    for line in sources['events'].read_text().splitlines():
        event = json.loads(line)['event']
        grouped[event['run_id']].append(event)
    if set(grouped) != {r['case']['case_id'] for r in summary['results']}:
        raise ValueError('Public summary and trace case sets differ')

    formats, subtypes, strata = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    ns_verdicts, ns_diagnostic = defaultdict(Counter), Counter()
    finish, fingerprints = Counter(), Counter()
    tokens, cases, seeds = [], [], defaultdict(list)
    for row in summary['results']:
        case = row['case']
        events = grouped[case['case_id']]
        manifest = next(e['payload']['manifest'] for e in events if e['kind'] == 'run.created')
        context = json.loads(manifest['frozen_context_fixture']['context_message']['content'].split('\n', 1)[1])
        allowed = [m['message_id'] for m in context['incoming']]
        receipts = [e['payload']['receipt'] for e in events if e['kind'] == 'attempt.received']
        if len(receipts) != 1:
            raise ValueError('Expected exactly one frozen receipt per calibration case')
        response = receipts[0]['response']
        choice = response['choices'][0]
        content = choice['message']['content']
        reason = envelope_reason(content, allowed)
        state, _ = parse_envelope(content, allowed)
        if state['envelope_status'] != row['envelope_status']:
            raise ValueError('Frozen parser result differs from historical summary')
        if (reason == 'valid') != (state['envelope_status'] == 'valid'):
            raise ValueError('Diagnostic reason and frozen parser disagree')
        obj = json.loads(content)
        bare = isinstance(obj, dict) and set(obj) in ({'n', 'd'}, {'a', 'b', 'c', 'd', 'e2', 'e3'})
        subtype = ('bare_certificate' if bare else 'other_envelope_keys') if reason == 'envelope_keys' else reason
        formats[case['contract']][reason] += 1
        subtypes[case['contract']][subtype] += 1
        stratum = '/'.join(case[k] for k in ('task_id', 'contract', 'context'))
        strata[stratum][reason] += 1
        finish[choice['finish_reason']] += 1
        fingerprints[response.get('system_fingerprint')] += 1
        tokens.append(response['usage']['completion_tokens'])
        request = next(e['payload']['request'] for e in events if e['kind'] == 'step.enqueued')
        seeds[case['block_order']].append(request['seed'])
        item = {
            'case_id': case['case_id'],
            **{k: case[k] for k in ('task_id', 'contract', 'context', 'role', 'repetition')},
            'format_reason': reason,
            'format_subtype': subtype,
            'historical_verdict': row['verdict']['status'],
            'historical_passed': row['verdict']['passed'],
            'finish_reason': choice['finish_reason'],
            'completion_tokens': response['usage']['completion_tokens'],
        }
        if case['task_id'] == 'ns-scaling-algebra-v1':
            if reason == 'valid':
                verdict = evaluate_scaling(state['candidate'])
                if verdict != row['verdict']:
                    raise ValueError('Frozen mathematical evaluation differs from historical verdict')
                ns_verdicts[case['contract']][verdict['status']] += 1
            # Diagnostic inspection is explicitly distinct from admitted candidates.
            # No values are repaired, coerced, or written back into historical runs.
            candidate = obj.get('candidate') if isinstance(obj, dict) else None
            if not isinstance(candidate, dict):
                candidate = obj if bare else None
            if candidate is None:
                ns_diagnostic['no_direct_or_bare_certificate'] += 1
                item['diagnostic_certificate_location'] = 'none'
            else:
                ns_diagnostic['direct_or_bare_certificate'] += 1
                ns_diagnostic['contains_noninteger_value'] += any(type(v) is not int for v in candidate.values())
                diagnostic_verdict = evaluate_scaling(candidate)
                ns_diagnostic['diagnostic_' + diagnostic_verdict['status']] += 1
                item['diagnostic_certificate_location'] = 'bare' if bare else 'candidate'
                item['diagnostic_only_verdict'] = diagnostic_verdict['status']
                if case['contract'] == 'output-card' and case['context'] == 'empty':
                    ns_diagnostic['output_card_empty_a_minus_one_b_minus_two'] += candidate.get('a') == -1 and candidate.get('b') == -2
        cases.append(item)

    if len(cases) != 64 or any(len(v) != 2 for v in seeds.values()):
        raise ValueError('Expected the frozen 64-case, 32-pair M2.3 batch')
    return {
        'schema_version': '1.0',
        'analysis_id': 'm2-3-offline-failure-taxonomy-v1',
        'scope': 'Post hoc descriptive review of unchanged public development receipts; not a new experiment or replacement score',
        'historical_source_commit': summary['experiment']['source_commit'],
        'sources': {k: {'path': str(p.relative_to(ROOT)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for k, p in sources.items()},
        'historical_outcomes_unchanged': True,
        'cases': len(cases),
        'format_reasons': dict(formats),
        'format_subtypes': dict(subtypes),
        'format_strata': dict(strata),
        'finish_reasons': dict(finish),
        'completion_tokens': {'min': min(tokens), 'max': max(tokens), 'request_cap': 1024},
        'paired_wire_seed_check': {'pairs': len(seeds), 'same_seed': sum(len(set(v)) == 1 for v in seeds.values()), 'provider_determinism_verified': False},
        'server_reported_fingerprints': dict(fingerprints),
        'model_weight_identity_independently_attested': False,
        'ns_admitted_envelope_verdicts': dict(ns_verdicts),
        'ns_diagnostic_inspection': {
            'scope': 'Post hoc direct nested/bare object inspection only; ignores envelope admission solely to locate errors, never substitutes a historical outcome',
            'counts': dict(ns_diagnostic),
        },
        'interpretation_limits': [
            'Observed compliance failures are not evidence of truncation: all 64 responses stopped before the 1024-token cap.',
            'Standalone task wording and outer-envelope wording are redundant and potentially confusing, but the system instruction explicitly specifies nesting; causal attribution needs a new test.',
            'NS failures persist inside valid envelopes and in diagnostic-only bare-object inspection; parsing repair cannot explain the observed failure set.',
            'Recorded NS contexts include incorrect generated algebra; fixture roles and context content are not independently randomized task samples.',
            'This does not measure organization superiority, scaling reliability, model-weight identity, or a Navier-Stokes regularity result.',
        ],
        'case_diagnostics': sorted(cases, key=lambda x: x['case_id']),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check', type=Path)
    args = parser.parse_args()
    result = analysis()
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + '\n'
    if args.check:
        if json.loads(args.check.read_text()) != result:
            raise SystemExit('Saved analysis differs from recomputed public receipts')
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    if not args.output and not args.check:
        print(text, end='')
    else:
        print(json.dumps({'cases': result['cases'], 'format_reasons': result['format_reasons'], 'historical_outcomes_unchanged': True}))


if __name__ == '__main__':
    main()
