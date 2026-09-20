"""Exact exponent algebra only; not a proof verifier for Navier–Stokes."""
import json

TASK={
    'id':'ns-scaling-algebra-v1','split':'public-development-only','family':'pde-scaling-algebra',
    'statement':
    'Assume a smooth solution of u_t+(u dot grad)u=nu*Delta(u)-grad(p)+f and div(u)=0 '
    'on R^3 with fixed nu>0. For every lambda>0 set '
    'u_lambda(x,t)=lambda^a*u(lambda*x,lambda^b*t), '
    'p_lambda(x,t)=lambda^c*p(lambda*x,lambda^b*t), and '
    'f_lambda(x,t)=lambda^d*f(lambda*x,lambda^b*t). The rescaled time domain consists '
    'of t such that lambda^b*t belongs to the original domain. Find integer a,b,c,d '
    'that preserve the equation for arbitrary smooth solutions with the same viscosity. '
    'Assuming the spatial norms below are finite, also find e2 and e3 defined by '
    '||u_lambda(.,t)||_2^2=lambda^e2*||u(.,lambda^b*t)||_2^2 and '
    '||u_lambda(.,t)||_3=lambda^e3*||u(.,lambda^b*t)||_3. '
    'Return only JSON with exactly integer fields a,b,c,d,e2,e3. '
    'This is a scaling-algebra certificate, not a claim of regularity or blowup.'}


def evaluate(candidate):
    verdict={'scope':'exact development exponent constraints; derivation and PDE proof unverified',
             'frontier_proof_verified':False}
    try:
        if isinstance(candidate,str):
            if len(candidate.encode())>8192:raise ValueError('certificate size')
            def unique(pairs):
                obj={}
                for k,v in pairs:
                    if k in obj:raise ValueError('duplicate key')
                    obj[k]=v
                return obj
            candidate=json.loads(candidate,object_pairs_hook=unique)
        if not isinstance(candidate,dict) or set(candidate)!={'a','b','c','d','e2','e3'}:
            raise ValueError('exact schema required')
        if any(type(v) is not int or abs(v)>32 for v in candidate.values()):raise ValueError('bounded integers')
        a,b,c,d,e2,e3=(candidate[k] for k in ('a','b','c','d','e2','e3'))
        terms={'time':a+b,'transport':2*a+1,'viscosity':a+2,'pressure':c+1,'force':d}
        obligations={'all_pde_term_powers_equal':len(set(terms.values()))==1,
                     'L2_squared_change_of_variables':e2==2*a-3,
                     'L3_norm_change_of_variables':e3==a-1}
        passed=all(obligations.values())
        return dict(verdict,status='VERIFIED_WITHIN_SCOPE' if passed else 'INVALID_CERTIFICATE',
                    passed=passed,obligations=obligations,derived_term_exponents=terms)
    except (ValueError,TypeError,RecursionError,OverflowError):
        return dict(verdict,status='MALFORMED',passed=False)
