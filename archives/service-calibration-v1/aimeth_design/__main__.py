"""Model-free M2 development commands. No command submits a live job."""
import argparse
import json
from pathlib import Path

from .organizations import compile_arm, submission_plan
from .execution import dry_run, select_terminal
from aimeth_runtime.store import Store


def write(path, record):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as handle:
        json.dump(record, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    compile_p = commands.add_parser('compile')
    compile_p.add_argument('--arm', choices=['S', 'I', 'L', 'X'], required=True)
    for name, default in [('population', 32), ('rounds', 3), ('group-size', 8),
                          ('seed', 914), ('output-tokens', 512), ('concurrency', 4),
                          ('selection-seed', 20260916)]:
        compile_p.add_argument('--' + name, type=int, default=default)
    compile_p.add_argument('--task', help='Public task JSON with id and statement')
    compile_p.add_argument('--output', required=True)
    plan_p = commands.add_parser('plan')
    plan_p.add_argument('manifest')
    plan_p.add_argument('--prompt-token-cap', type=int)
    plan_p.add_argument('--output', required=True)
    dry_p = commands.add_parser('dry-run')
    dry_p.add_argument('manifest')
    dry_p.add_argument('--db', required=True)
    dry_p.add_argument('--run-id', required=True)
    dry_p.add_argument('--output', required=True)
    select_p = commands.add_parser('select')
    select_p.add_argument('--db', required=True)
    select_p.add_argument('--run-id', required=True)
    select_p.add_argument('--selection-seed', type=int, required=True)
    select_p.add_argument('--output', required=True)
    eval_p = commands.add_parser('evaluate')
    eval_p.add_argument('--task-id', required=True)
    eval_p.add_argument('--candidate', required=True)
    eval_p.add_argument('--output', required=True)
    args = parser.parse_args()
    # Check output collision before running or appending observations.
    if Path(args.output).exists():
        parser.error('Output already exists; use a new evidence path')
    if args.command == 'compile':
        task = json.loads(Path(args.task).read_text()) if args.task else None
        result = compile_arm(args.arm, args.population, args.rounds, args.group_size,
                             args.seed, args.output_tokens, args.concurrency, task)
        result['selection_seed'] = args.selection_seed
    elif args.command == 'plan':
        result = submission_plan(json.loads(Path(args.manifest).read_text()), args.prompt_token_cap)
    elif args.command == 'dry-run':
        result = dry_run(args.db, args.run_id, json.loads(Path(args.manifest).read_text()))
    elif args.command == 'select':
        with Store(args.db) as store:
            result = select_terminal(store, args.run_id, args.selection_seed)
    else:
        from aimeth_evaluation.controls import evaluate
        path = Path(args.candidate)
        if path.stat().st_size > 8192:
            parser.error('Candidate exceeds 8192 bytes')
        result = evaluate(args.task_id, path.read_text())
    write(args.output, result)


if __name__ == '__main__':
    main()
