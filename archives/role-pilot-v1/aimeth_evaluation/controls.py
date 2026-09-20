"""Bounded exact certificates for six public, non-held-out development controls."""
from fractions import Fraction
import json
import re

TASKS = {
    'poly-square': {'family': 'polynomial-identity', 'statement':
        'Over Q[x], expand (x+1)^2. Return JSON {"coefficients":[c0,c1,c2]} in ascending powers; coefficients are integers or rational strings.'},
    'poly-difference': {'family': 'polynomial-identity', 'statement':
        'Over Q[x], expand (2*x-3)*(x+4). Return JSON {"coefficients":[c0,c1,c2]} in ascending powers; coefficients are integers or rational strings.'},
    'integral-cubic': {'family': 'antiderivative', 'statement':
        'Find P in Q[x] with P(0)=0 and P\u0027(x)=3*x^2+2*x+1. Return JSON {"coefficients":[c0,c1,...]} in ascending powers; use integers or rational strings.'},
    'integral-rational': {'family': 'antiderivative', 'statement':
        'Find P in Q[x] with P(0)=0 and P\u0027(x)=x^3-x. Return JSON {"coefficients":[c0,c1,...]} in ascending powers; use integers or rational strings.'},
    'bezout': {'family': 'integer-certificate', 'statement':
        'Find integers a,b such that 240*a+46*b=2. Return JSON {"a":integer,"b":integer}.'},
    'prime-counterexample': {'family': 'counterexample', 'statement':
        'Refute the claim: for every integer n>=0, n^2+n+41 is prime. Return JSON {"n":integer,"d":integer}, where d is a proper divisor of the displayed value.'},
}


def public_tasks():
    return [{'id': name, 'split': 'public-development-only', **record}
            for name, record in TASKS.items()]


def integer(value):
    if type(value) is not int or abs(value) > 10**12:
        raise ValueError('Expected a bounded integer')
    return value


def rational(value):
    if type(value) is int:
        return Fraction(integer(value))
    if not isinstance(value, str) or not re.fullmatch(r'-?\d{1,12}(?:/[1-9]\d{0,11})?', value):
        raise ValueError('Expected a bounded integer or rational string')
    return Fraction(value)


def trim(values):
    while len(values) > 1 and values[-1] == 0:
        values.pop()
    return values


def evaluate(task_id, candidate):
    if task_id not in TASKS:
        return {'status': 'UNVERIFIED', 'passed': False, 'scope': 'unsupported task',
                'frontier_proof_verified': False}
    try:
        if isinstance(candidate, str):
            if len(candidate.encode('utf-8')) > 8192:
                raise ValueError('Certificate too large')
            def unique_pairs(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError('Duplicate JSON field')
                    result[key] = value
                return result
            candidate = json.loads(candidate, object_pairs_hook=unique_pairs)
        if not isinstance(candidate, dict):
            raise ValueError('Expected a JSON object')
        if task_id.startswith('poly-') or task_id.startswith('integral-'):
            if set(candidate) != {'coefficients'}:
                raise ValueError('Expected only coefficients')
            values = candidate['coefficients']
            if not isinstance(values, list) or not 1 <= len(values) <= 16:
                raise ValueError('Expected 1..16 coefficients')
            values = trim([rational(x) for x in values])
            if task_id.startswith('poly-'):
                # Exact coefficient comparison in Q[x], not finite-point sampling.
                target = [1, 2, 1] if task_id == 'poly-square' else [-12, 5, 2]
                passed = values == target
            else:
                target = [1, 2, 3] if task_id == 'integral-cubic' else [0, -1, 0, 1]
                derivative = trim([i * x for i, x in enumerate(values)][1:] or [Fraction(0)])
                passed = values[0] == 0 and derivative == target
        elif task_id == 'bezout':
            if set(candidate) != {'a', 'b'}:
                raise ValueError('Expected a and b')
            passed = 240 * integer(candidate['a']) + 46 * integer(candidate['b']) == 2
        else:
            if set(candidate) != {'n', 'd'}:
                raise ValueError('Expected n and d')
            n, d = integer(candidate['n']), integer(candidate['d'])
            value = n*n+n+41
            passed = n >= 0 and 1 < d < value and value % d == 0
        return {'status': 'VERIFIED_WITHIN_SCOPE' if passed else 'INVALID_CERTIFICATE',
                'passed': passed, 'scope': 'exact public development task: ' + task_id,
                'frontier_proof_verified': False}
    except (ValueError, TypeError, KeyError, RecursionError, OverflowError):
        return {'status': 'MALFORMED', 'passed': False,
                'scope': 'bounded certificate schema', 'frontier_proof_verified': False}
