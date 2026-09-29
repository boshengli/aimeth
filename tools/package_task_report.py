#!/usr/bin/env python3
"""Hash the completed M2.5 report bundle; excludes private execution records."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
paths=[
    ROOT/'aimeth_pilot/task_continuation.py',ROOT/'tests/test_task_continuation.py',
    *sorted((ROOT/'reports/task-continuation-v1').glob('*')),
    *sorted((ROOT/'milestones').glob('m2-5-task-continuation-v1*')),
    ROOT/'docs/task-continuation-v1.md',ROOT/'docs/task-failure-analysis-v1.md',
    ROOT/'docs/next-population-plan-v1.md',ROOT/'templates/task-milestone-v1.html',
    ROOT/'tools/build_task_milestone.py',ROOT/'tools/check_task_milestone.cjs',
    ROOT/'tools/export_task_evidence.py',ROOT/'tools/analyze_contract_failures.py',
    Path(__file__).resolve(),
]
records=[]
for i,path in enumerate(sorted(set(paths)),1):
    raw=path.read_bytes()
    records.append({'id':f'artifact-{i}','path':str(path.relative_to(ROOT)),
                    'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
out={'schema_version':'1.0','scope':'M2.5 task analysis and bounded gateway submission; no population effect or frontier proof',
     'execution_source':'0b3dfd598b7d4eedb2c36fd1afc7e78da102b3bb','artifacts':records}
(ROOT/'task-continuation-report-manifest.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'artifacts':len(records)}))
