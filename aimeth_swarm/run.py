"""Direct 10K exploratory population; phased journals reuse the frozen runtime."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import threading
import time

from aimeth_runtime.runner import demo_manifest, http_response, TransportFailure
from aimeth_runtime.store import Store, canonical, digest
from .budget import Budget
from .design import counts, default_config, phase_agents, prompt, roster, worker_peers

STOP = threading.Event()
PHASES = ('worker', 'observer', 'chief', 'global')


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w') as f:
        f.write(canonical(value) + '\n'); f.flush(); os.fsync(f.fileno())
    os.replace(temporary, path)


def source_identity():
    root = Path(__file__).resolve().parents[1]
    return digest({str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for directory in ('aimeth_swarm', 'aimeth_runtime')
                   for p in sorted((root/directory).glob('*.py'))})


def wire_call(claim, config, synthetic=False):
    if synthetic:
        text = canonical({'candidate': 'Synthetic plumbing fixture; not mathematics.',
                          'assumptions': [], 'obligations': ['unverified fixture'],
                          'dissent': ['Do not discard minority evidence.'],
                          'coordination_status': 'unresolved'})
        return {'response': {'choices': [{'message': {'content': text}, 'finish_reason': 'stop'}],
                             'model': 'synthetic', 'synthetic': True,
                             'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}}}
    try:
        return {'response': http_response(claim, {'endpoint': config['endpoint'],
                         'timeout_seconds': config['request_timeout_seconds']})}
    except TransportFailure as exc:
        return {'error': exc.details}
    except Exception as exc:
        return {'error': {'category': type(exc).__name__}}


def normalized_wire(wire):
    """Preserve final content and usage without retaining hidden reasoning."""
    if 'error' in wire or 'response' not in wire:
        return wire, False
    raw = wire['response']
    choices = []
    raw_choices = raw.get('choices', [])
    valid_content = bool(raw_choices)
    for choice in raw_choices:
        message = choice.get('message') or {}
        content = message.get('content')
        valid_content = valid_content and isinstance(content, str) and bool(content.strip())
        choices.append({'index': choice.get('index'), 'finish_reason': choice.get('finish_reason'),
                        'message': {'role': message.get('role'), 'content': content,
                                    'refusal': message.get('refusal')}})
    response = {key: raw[key] for key in ('id', 'model', 'created', 'object',
                'system_fingerprint', 'service_tier', 'usage') if key in raw}
    response['choices'] = choices
    result = {'response': response}
    if not valid_content:
        result['error'] = {'category': 'missing_final_content'}
    return result, valid_content


def finish(store, claim, wire):
    if 'error' in wire:
        return store.fail(claim['token'], wire['error'], retryable=False)
    response = wire['response']
    try:
        content = response['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError):
        content = None
    return store.complete(claim['token'], response,
                          {'candidate': content, 'proof_verification_status': 'unverified'}, [])


def read_outcomes(store, run_ids):
    outcomes = {}
    for run_id in run_ids:
        for step in store.db.execute('SELECT * FROM steps WHERE run_id=?', (run_id,)):
            attempt = store.db.execute('SELECT * FROM attempts WHERE run_id=? AND step_id=? ORDER BY number DESC LIMIT 1',
                                      (run_id, step['step_id'])).fetchone()
            event_id = (attempt['receipt_event'] or attempt['started_event']) if attempt else step['created_event']
            event = store.db.execute('SELECT payload,event_hash FROM events WHERE event_id=?', (event_id,)).fetchone()
            payload = json.loads(event['payload'])
            response = payload.get('receipt', {}).get('response', {})
            try:
                content = response['choices'][0]['message']['content']
                if not isinstance(content, str): content = None
            except (KeyError, IndexError, TypeError):
                content = None
            outcomes[step['agent_id']] = {'agent_id': step['agent_id'], 'source_run': run_id,
                'source_event': event_id, 'source_hash': event['event_hash'],
                'execution_status': step['status'], 'content': content,
                'error': payload.get('failure') or payload.get('receipt', {}).get('error'),
                'proof_verification_status': 'unverified'}
    return outcomes


@lru_cache(maxsize=4)
def routing_index(serialized_config):
    config = json.loads(serialized_config)
    roles = {p: phase_agents(config, p) for p in PHASES}
    by_group = {(p, g): [a for a in roles[p] if a['group'] == g]
                for p in PHASES for g in range(config['groups'])}
    inboxes = {}
    for cycle in range(config['cycles']):
        inbox = {a['agent_id']: [] for a in roles['worker']}
        for sender in roles['worker']:
            for recipient in worker_peers(config, sender, cycle):
                inbox[recipient].append(sender['agent_id'])
        inboxes[cycle] = inbox
    return roles, by_group, inboxes


def select_incoming(config, agent, cycle, current, previous):
    roles, by_group, inboxes = routing_index(canonical(config))
    role, group = agent['role'], agent['group']
    selected = []
    if role == 'worker' and cycle:
        peer_ids = [agent['agent_id'], *inboxes[cycle-1][agent['agent_id']]]
        selected += [previous['worker'][k] for k in peer_ids]
        region = agent['index'] * config['observers_per_group'] // config['workers_per_group']
        for p in ('observer', 'chief', 'global'):
            for other in (roles[p] if p == 'global' else by_group[p, group]):
                if other['group'] == group or p == 'global':
                    if p != 'observer' or other['index'] == region:
                        selected.append(previous[p][other['agent_id']])
    elif role == 'observer':
        for other in by_group['worker', group]:
            if other['index'] * config['observers_per_group'] // config['workers_per_group'] == agent['index']:
                selected.append(current['worker'][other['agent_id']])
    elif role == 'chief':
        selected = [current['observer'][other['agent_id']] for other in by_group['observer', group]]
    elif role == 'global':
        selected = list(current['chief'].values())
    return selected


def preview(record, limit):
    result = {k: v for k, v in record.items() if k != 'content'}
    raw = record.get('content')
    # Full responses remain in the journal; prioritise explicit dissent in bounded messages.
    try:
        decoded = json.loads(raw) if isinstance(raw, str) else None
    except ValueError:
        decoded = None
    if isinstance(decoded, dict):
        value = {'dissent': decoded.get('dissent'), 'obligations': decoded.get('obligations'),
                 'candidate': decoded.get('candidate'), 'assumptions': decoded.get('assumptions')}
        text = canonical(value)
    else:
        text = raw or '[No usable content; see execution_status and source evidence.]'
    result['content'] = text[:limit]
    result['preview_truncated'] = len(text) > limit
    result['full_content_sha256'] = digest(raw)
    return result


def token_counter(model_dir, synthetic, config=None):
    if synthetic:
        return lambda messages: len(canonical(messages).encode()) // 4 + 1
    if not model_dir:
        raise ValueError('Live execution requires the served local tokenizer directory')
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True, trust_remote_code=False)
    config = config or {}
    encoder = config.get('token_count_encoder', 'huggingface-chat-template')
    if encoder == 'sglang-dsv4-native-v1':
        if tokenizer.chat_template is not None:
            raise ValueError('Frozen SGLang DSV4 mode expected a checkpoint without a Hugging Face chat template')
        from sglang.srt.entrypoints.openai.encoding_dsv4 import encode_messages
        thinking_mode = config.get('thinking_mode', 'thinking')
        if thinking_mode not in ('chat', 'thinking'):
            raise ValueError('DeepSeek-V4 thinking_mode must be chat or thinking')
        def count(messages):
            # DeepSeek-V4 intentionally has no tokenizer_config chat_template.
            # Reuse the exact encoder shipped by the frozen SGLang container,
            # then tokenize the rendered prompt as the server does.
            rendered = encode_messages(messages, thinking_mode=thinking_mode)
            return len(tokenizer.encode(rendered, add_special_tokens=False))
        return count
    if encoder != 'huggingface-chat-template':
        raise ValueError(f'Unsupported frozen token_count_encoder: {encoder}')
    if tokenizer.chat_template is None:
        raise ValueError('The checkpoint has no Hugging Face chat_template; freeze a model-specific server-equivalent encoder')
    def count(messages):
        # Some recent Transformers backends return only the template's special
        # tokens when tokenization is requested here. Render first, then encode
        # the exact string sent as OpenAI-style messages so long inputs cannot
        # silently collapse to a two-token count.
        rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        return len(tokenizer.encode(rendered, add_special_tokens=False))
    return count


def tokenizer_identity(model_dir, synthetic, config=None):
    if synthetic: return {'kind': 'synthetic-byte-count-fixture'}
    root = Path(model_dir)
    names = ('tokenizer.json', 'tokenizer_config.json', 'special_tokens_map.json', 'chat_template.jinja', 'config.json')
    identity = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in names if (root/name).is_file()}
    config = config or {}
    identity['chat_encoder_mode'] = config.get('token_count_encoder', 'huggingface-chat-template')
    identity['thinking_mode'] = config.get('thinking_mode', 'unspecified')
    return identity


def make_manifest(config, agents, cycle, phase, current, previous, count, synthetic):
    manifest = demo_manifest(len(agents), 1)
    manifest.update(agents=[a['agent_id'] for a in agents], rounds=1, max_attempts=1,
                    max_inflight=config['max_inflight'], max_output_tokens=config['max_output_tokens'],
                    max_messages_per_step=1, max_message_chars=2048, seed=config['seed'],
                    temperature=0.7, top_p=1, round_edges={'0': []},
                    context_mode='none.v1', model_name=config['model_name'])
    manifest['transport'] = ({'kind': 'mock'} if synthetic else
                            {'kind': 'openai', 'endpoint': config['endpoint'],
                             'timeout_seconds': config['request_timeout_seconds']})
    manifest['request_options'] = config.get('request_options', {})
    manifest['identities'].update(model=config['model_name'], policy='slcw-phased-v1',
                                   task='navier-stokes-obligation-exploration-v1',
                                   code='sha256:' + source_identity())
    manifest['agent_base_messages'] = {}
    manifest['lineage_imports'] = {}
    for agent in agents:
        incoming = select_incoming(config, agent, cycle, current, previous)
        cap = config.get('input_token_limits', {}).get(phase, config['max_input_tokens'])
        limit = {'worker': 1800, 'observer': 1600, 'chief': 4000, 'global': 800}[phase]
        while True:
            selected = [preview(record, limit) for record in incoming]
            messages = prompt(config, agent, cycle, selected)
            if count(messages) <= cap: break
            if limit <= 48:
                raise ValueError('Source references exceed frozen input token cap; do not silently drop sources')
            limit = max(48, limit // 2)
        manifest['agent_base_messages'][agent['agent_id']] = messages
        manifest['lineage_imports'][agent['agent_id']] = [
            {k: v for k, v in record.items() if k in ('agent_id', 'source_run', 'source_event', 'source_hash')}
            for record in incoming]
    manifest['swarm'] = {'cycle': cycle, 'phase': phase, 'parent_population_id': config['population_id'],
                         'lineage_mode': 'explicit-cross-run-source-event-and-hash',
                         'proof_verification_status': 'unverified'}
    return manifest


def verify_imports(store, manifest):
    for imports in manifest['lineage_imports'].values():
        for item in imports:
            row = store.db.execute('SELECT run_id,event_hash FROM events WHERE event_id=?', (item['source_event'],)).fetchone()
            if not row or row['run_id'] != item['source_run'] or row['event_hash'] != item['source_hash']:
                raise ValueError('Missing or mismatched cross-phase source evidence')


def snapshot(store, budget, root, output, label):
    tail = store.db.execute('SELECT COALESCE(MAX(seq),0) FROM events').fetchone()[0]
    target = output / 'snapshots' / f'{label}-e{tail}'
    target.mkdir(parents=True, exist_ok=True)
    if not (target / 'journal.sqlite').exists():
        receipt = store.backup(target / 'journal.sqlite')
        with sqlite3.connect(target / 'budget.sqlite') as db:
            budget.db.backup(db)
        save(target / 'identity.json', {'journal_sha256': receipt['sha256'],
             'budget_sha256': hashlib.sha256((target / 'budget.sqlite').read_bytes()).hexdigest(),
             'scope': 'single-coordinator consistent boundary; raw receipts remain on local disk'})
    save(output / 'progress.json', {'population_id': root.name, 'budget': budget.summary(),
         'steps': {r[0]: r[1] for r in store.db.execute('SELECT status,COUNT(*) FROM steps GROUP BY status')},
         'snapshot': str(target.name), 'proof_verified': False})


def verify_phase(store, run_ids):
    # The unchanged runtime verifier scans the entire SQLite database per call.
    # Verify all event chains here, and run its full projection audit once per phase.
    chains = {}
    for run_id in run_ids:
        previous, seen, n = '0' * 64, set(), 0
        for record in store.events(run_id):
            expected = {k: v for k, v in record.items() if k not in ('seq', 'event_hash')}
            if digest(expected) != record['event_hash'] or record['prev_hash'] != previous:
                raise ValueError('Event chain corrupted')
            if any(parent not in seen for parent in record['parents']):
                raise ValueError('Event parent missing')
            seen.add(record['event_id']); previous = record['event_hash']; n += 1
        manifest = store.manifest(run_id)
        verify_imports(store, manifest)
        chains[run_id] = {'events': n, 'tail_hash': previous}
    sample = store.verify(run_ids[0])
    return {'all_event_chains_and_imports': chains,
            'full_projection_sample_run': run_ids[0], 'full_projection_sample': sample,
            'full_projection_audit_of_every_child_run': False,
            'mathematical_validity_checked': False}


def execute(config, root, output, *, synthetic=False, model_dir=None):
    STOP.clear()
    root, output = Path(root), Path(output)
    if (root / 'technical-stop.json').exists():
        raise ValueError('Frozen technical stop reached; preserve this run and use a separately versioned continuation')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = (root / 'coordinator.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    count = token_counter(model_dir, synthetic, config)
    tokenizer_hashes = tokenizer_identity(model_dir, synthetic, config)
    settings_path = root / 'population.json'
    if settings_path.exists():
        saved = json.loads(settings_path.read_text())
        if saved['config'] != config or saved['code_sha256'] != source_identity() or saved['synthetic'] != synthetic or saved['tokenizer_identity'] != tokenizer_hashes:
            raise ValueError('Resume must use identical config, mode and code')
    else:
        saved = {'config': config, 'started_unix': time.time(), 'code_sha256': source_identity(), 'synthetic': synthetic, 'tokenizer_identity': tokenizer_hashes}
        save(settings_path, saved)
    save(output / 'population.json', saved)
    total = len(roster(config)) * config['cycles']
    limits = config.get('input_token_limits', {})
    max_input = config['cycles'] * sum(len(phase_agents(config, p)) * limits.get(p, config['max_input_tokens']) for p in PHASES)
    budget = Budget(root / 'budget.sqlite', calls=total, input_tokens=max_input,
                    output_tokens=total*config['max_output_tokens'], deadline=saved['started_unix']+config['wall_seconds'])
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: STOP.set())
    receipt_root = root / 'receipts'; receipt_root.mkdir(exist_ok=True)
    results, previous, halted = [], {}, False
    halt_reason = None
    with Store(root / 'journal.sqlite') as store:
        # Reconcile receipt-first files before leases are recovered; late receipts remain evidence.
        for path in receipt_root.glob('*.json'):
            recorded = json.loads(path.read_text()); claim = recorded['claim']; wire = recorded['wire']
            attempt = store.db.execute('SELECT receipt_hash FROM attempts WHERE token=?', (claim['token'],)).fetchone()
            if attempt and not attempt['receipt_hash']:
                finish(store, claim, wire)
            budget.settle(claim['token'], {'usage': wire.get('response', {}).get('usage'), 'error': wire.get('error')})
        consecutive = 0
        with ThreadPoolExecutor(max_workers=config['max_inflight']) as pool:
            for cycle in range(config['cycles']):
                current = {}
                for phase in PHASES:
                    run_ids = []
                    agents = phase_agents(config, phase)
                    for start in range(0, len(agents), 12):
                        run_id = f"{config['population_id']}.c{cycle}.{phase}.b{start//12:04d}"
                        existing = store.db.execute('SELECT manifest FROM runs WHERE run_id=?', (run_id,)).fetchone()
                        manifest = json.loads(existing['manifest']) if existing else make_manifest(
                            config, agents[start:start+12], cycle, phase, current, previous, count, synthetic)
                        verify_imports(store, manifest)
                        store.create_run(run_id, manifest); store.enqueue_round(run_id, 0)
                        run_ids.append(run_id)
                    active, next_run = {}, 0
                    while True:
                        if STOP.is_set() or time.time() >= saved['started_unix'] + config['wall_seconds']:
                            halted = True
                            halt_reason = halt_reason or ('signal' if STOP.is_set() else 'wall_deadline')
                        while not halted and len(active) < config['max_inflight']:
                            claim = None
                            for _ in range(len(run_ids)):
                                run_id = run_ids[next_run % len(run_ids)]; next_run += 1
                                claim = store.claim(run_id, 'swarm-coordinator', lease_seconds=config['request_timeout_seconds']+60)
                                if claim: break
                            if claim is None: break
                            input_count = count(claim['request']['messages'])
                            if input_count > limits.get(phase, config['max_input_tokens']):
                                store.fail(claim['token'], {'category': 'input_token_cap'}, retryable=False)
                                halted = True; halt_reason = 'input_token_cap'; break
                            try:
                                reserved = budget.reserve(claim['token'], claim['run_id'], input_count, config['max_output_tokens'])
                            except ValueError:
                                store.fail(claim['token'], {'category': 'budget_exhausted'}, retryable=False)
                                halted = True; halt_reason = 'budget_exhausted'; break
                            if not reserved:
                                raise ValueError('A previously reserved call must not be redispatched')
                            active[pool.submit(wire_call, claim, config, synthetic)] = claim
                        done = [future for future in active if future.done()]
                        for future in done:
                            claim = active.pop(future); wire, has_final_content = normalized_wire(future.result())
                            save(receipt_root / (claim['token']+'.json'), {'claim': claim, 'wire': wire})
                            finish(store, claim, wire)
                            budget.settle(claim['token'], {'usage': wire.get('response', {}).get('usage'), 'error': wire.get('error')})
                            if 'response' in wire and not has_final_content:
                                halted = True; halt_reason = 'missing_final_content'
                            consecutive = consecutive + 1 if 'error' in wire else 0
                            if consecutive >= config.get('consecutive_transport_error_stop', 5):
                                halted = True
                                halt_reason = halt_reason or 'consecutive_transport_errors'
                                save(root / 'technical-stop.json', {'reason': 'consecutive_transport_errors', 'count': consecutive})
                            used = budget.summary()['reserved_calls']
                            if used and used % 1000 == 0:
                                snapshot(store, budget, root, output, f'calls-{used:06d}')
                        if not active:
                            pending = sum(store.db.execute("SELECT COUNT(*) FROM steps WHERE run_id=? AND status IN ('pending','running')", (rid,)).fetchone()[0] for rid in run_ids)
                            if halted or pending == 0: break
                        time.sleep(0.01)
                    current[phase] = read_outcomes(store, run_ids)
                    verifications = verify_phase(store, run_ids)
                    results.append({'cycle': cycle, 'phase': phase, 'run_ids': run_ids,
                                    'verification': verifications, 'outcomes': current[phase]})
                    save(output / f'cycle-{cycle}-{phase}.json', results[-1])
                    snapshot(store, budget, root, output, f'cycle-{cycle}-{phase}')
                    print(canonical({'cycle': cycle, 'phase': phase, 'budget': budget.summary(), 'halted': halted}), flush=True)
                    if halted: break
                previous = current
                if halted: break
        summary = {'schema_version': '1.0', 'population_id': config['population_id'],
                   'counting': counts(config), 'synthetic': synthetic, 'halted': halted,
                   'halt_reason': halt_reason,
                   'finished_phases': len(results), 'planned_phases': 4*config['cycles'],
                   'analysis_agent_identities_with_attempt_record': store.db.execute(
                       "SELECT COUNT(DISTINCT s.agent_id) FROM steps s JOIN attempts a ON s.run_id=a.run_id AND s.step_id=a.step_id WHERE s.run_id LIKE '%worker%'"
                   ).fetchone()[0],
                   'attempt_count_is_not_confirmed_dispatch_count': True,
                   'budget': budget.summary(), 'final_global_candidates': previous.get('global', {}),
                   'mathematical_verification': 'not performed; all candidates unverified',
                   'organization_superiority_established': False}
        save(output / 'summary.json', summary)
        snapshot(store, budget, root, output, 'final')
    budget.close(); lock.close()
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--local-root', required=True)
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--tokenizer-dir')
    parser.add_argument('--synthetic', action='store_true')
    parser.add_argument('--allow-model-calls', action='store_true')
    args = parser.parse_args()
    if not args.synthetic and not args.allow_model_calls:
        parser.error('Live execution requires --allow-model-calls')
    cfg = json.loads(Path(args.config).read_text())
    summary = execute(cfg, args.local_root, args.output_root, synthetic=args.synthetic, model_dir=args.tokenizer_dir)
    print(canonical(summary))


if __name__ == '__main__': main()
