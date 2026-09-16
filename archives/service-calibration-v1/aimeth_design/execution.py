"""Model-free execution and content-blind selection over durable checkpoints."""
import json
from aimeth_runtime.runner import Worker
from aimeth_runtime.store import Conflict, Store, digest


def uniform_index(seed, task_identity, count):
    if type(seed) is not int or type(count) is not int or count < 1:
        raise ValueError('Integer selection seed and positive count required')
    limit = (1 << 256) - ((1 << 256) % count)
    counter = 0
    while True:
        value = int(digest(['selection.v1', seed, task_identity, counter]), 16)
        if value < limit:
            return value % count
        counter += 1


def select_terminal(store, run_id, selection_seed):
    config = store.manifest(run_id)
    if type(selection_seed) is not int or config.get('selection_seed') != selection_seed:
        raise Conflict('Selection seed must be frozen in the run manifest before execution')
    if not store.status(run_id)['complete'] or store.verify(run_id)['status'] != 'verified':
        raise Conflict('Selection requires a complete verified journal')
    names = sorted(config['agents'])
    selected = names[uniform_index(selection_seed, config['identities']['task'], len(names))]
    row = store.db.execute(
        'SELECT * FROM checkpoints WHERE run_id=? AND agent_id=? AND round_index=?',
        (run_id, selected, config['rounds']-1)).fetchone()
    result = {'selector': 'terminal-uniform-lottery.v1', 'selection_seed': selection_seed,
              'agent_id': selected, 'source_event': row['event_id'],
              'candidate': json.loads(row['state'])['candidate'], 'candidate_limit': 1,
              'proof_status': 'unverified',
              'estimand': 'representative-final-agent; not best-of-N discovery'}
    store.observe(run_id, 'terminal.selection', 'observation.terminal_selection', result,
                  parents=[row['event_id']])
    return result


def dry_run(db_path, run_id, config):
    if config.get('transport', {}).get('kind') != 'mock':
        raise ValueError('This command cannot make model calls; mock transport is required')
    with Store(db_path) as store:
        store.create_run(run_id, config)
        worker = Worker(store, run_id)
        for r in range(config['rounds']):
            store.enqueue_round(run_id, r)
            while worker.one('design-dry-run') is not None:
                pass
        selected = select_terminal(store, run_id, config['selection_seed'])
        verification = store.verify(run_id)
        delivered = store.db.execute(
            'SELECT COUNT(*) FROM messages WHERE run_id=? AND bound_event IS NOT NULL '
            'AND consumed_event IS NOT NULL', (run_id,)).fetchone()[0]
        return {'schema_version': '1.0', 'evidence_kind': 'synthetic-engineering-trace',
                'model_calls': 0, 'mathematical_effect_measured': False,
                'status': store.status(run_id), 'verification': verification,
                'delivered_and_consumed_messages': delivered, 'selection': selected}
