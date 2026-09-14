#!/usr/bin/env python3
"""Read-only source audit with mocked HTTP; never submits a cluster/model job."""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
from unittest.mock import patch


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(source):
    root = Path(source).resolve()
    base = root / "skill/h20_10k_navier_agent_skill"
    result = {"schema_version": "1.0", "audited_at": datetime.now(timezone.utc).isoformat(),
              "live_cluster_tested": False, "proof_verified": False}
    checks = []
    for line in (root / "SHA256SUMS.txt").read_text().splitlines():
        expected, rel = line.split(maxsplit=1)
        p = (root / rel).resolve()
        if root not in p.parents:
            raise ValueError("Checksum entry escapes source root")
        digest = sha256(p)
        checks.append({"path": rel.removeprefix("./"), "sha256": digest, "match": digest == expected})
    result["checksum_checks"] = checks
    # Execute only the known inspected submitter revision, with HTTP mocked below.
    reviewed_submitter = "3ce992ec1fbd5e7c094e065c3d6b85c8fdffeacc7f7b2ad965356a47417a887c"
    submitter = base / "scripts/submit_10k.py"
    if sha256(submitter) != reviewed_submitter:
        raise ValueError("Submitter differs from reviewed baseline; inspect it before running this audit")
    syntax = []
    for p in sorted((base / "scripts").glob("*.py")):
        ast.parse(p.read_text(), filename=p.name)
        syntax.append({"path": str(p.relative_to(root)), "check": "ast.parse", "passed": True})
    for p in [base / "scripts/calibrate_concurrency.sh", base / "slurm/navier_10k.sbatch"]:
        proc = subprocess.run(["bash", "-n", str(p)], capture_output=True, text=True, check=False)
        syntax.append({"path": str(p.relative_to(root)), "check": "bash -n", "passed": proc.returncode == 0})
    result["syntax_checks"] = syntax
    script = (base / "scripts/calibrate_concurrency.sh").read_text()
    limit = int(re.search(r"--limit\s+(\d+)", script).group(1))
    levels = [int(x) for x in re.search(r"for C in ([\d ]+);", script).group(1).split()]
    result["calibration"] = {"task_limit": limit, "client_settings": levels,
                             "upper_bound_actual_requests": [min(limit, c) for c in levels]}
    anchors = {
        "E01": ("scripts/calibrate_concurrency.sh", "--limit"),
        "E02": ("scripts/submit_10k.py", 'done.add(x["agent_id"])'),
        "E03": ("scripts/submit_10k.py", '"stream": False'),
        "E04": ("slurm/navier_10k.sbatch", "python3 scripts/submit_10k.py"),
        "E05": ("scripts/submit_10k.py", '"status": "ok"'),
        "E06": ("scripts/submit_10k.py", 'except Exception:'),
        "E07": ("scripts/generate_population.py", "Do not coordinate"),
        "E08": ("slurm/navier_10k.sbatch", 'ROOT="'),
        "E09": ("scripts/submit_10k.py", 'failed += 1'),
    }
    result["finding_locations"] = {
        key: {"path": rel, "lines": [i for i, line in enumerate((base / rel).read_text().splitlines(), 1) if anchor in line]}
        for key, (rel, anchor) in anchors.items()
    }
    spec = importlib.util.spec_from_file_location("audited_submitter", submitter)
    module = importlib.util.module_from_spec(spec)
    # Suppress bytecode writes into the supplied package.
    exec(compile(submitter.read_text(), str(submitter), "exec"), module.__dict__)
    args = SimpleNamespace(model="synthetic-model", temperature=0.5, top_p=0.9,
                           max_tokens=10, send_seed=False, base_url="http://unused.invalid",
                           api_key="", max_retries=0, timeout=1)
    rec = {"agent_id": "synthetic-agent", "seed": 7, "mode": "independent",
           "suffix": "Synthetic audit fixture", "arm_id": "synthetic-arm", "step_id": 2}
    response = {"choices": [{"message": {"content": None}, "finish_reason": "length"}],
                "usage": {"completion_tokens": 10, "prompt_tokens": 5, "total_tokens": 15}}
    with patch.object(module.urllib.request, "urlopen", return_value=io.BytesIO(json.dumps(response).encode())) as mocked:
        observed = module.request_one(rec, args, "Synthetic system", "Synthetic task")
        request = json.loads(mocked.call_args.args[0].data)
    with tempfile.TemporaryDirectory() as temp:
        p = Path(temp) / "results.jsonl"
        p.write_text(json.dumps({"status": "ok", "agent_id": "synthetic-agent", "model": "old-model"}) + "\n")
        old_done = sorted(module.load_done(p))
    result["mock_observations"] = {
        "fixture_only_not_model_output": True,
        "seed_field_sent_when_default_false": "seed" in request,
        "truncated_null_content_status": observed["status"],
        "finish_reason_preserved": "finish_reason" in observed,
        "arm_id_preserved": "arm_id" in observed,
        "resume_ids_without_model_check": old_done,
    }
    pdf = root / "references/navier-stokes.pdf"
    result["pdf"] = {"sha256": sha256(pdf), "pages": None, "keyword_matches": None}
    if shutil.which("pdfinfo"):
        info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, check=True).stdout
        result["pdf"]["pages"] = int(re.search(r"Pages:\s+(\d+)", info).group(1))
    if shutil.which("pdftotext"):
        content = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True, check=True).stdout
        result["pdf"]["keyword_matches"] = {pattern: len(re.findall(pattern, content, re.I))
            for pattern in [r"\bagents?\b", "10,000", r"multi.agent"]}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    root = Path(args.source).resolve()
    if output == root or root in output.parents:
        parser.error("Output must be outside the original source package")
    result = audit(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    valid = all(x["match"] for x in result["checksum_checks"]) and all(x["passed"] for x in result["syntax_checks"])
    print(json.dumps({"checksum_matches": sum(x["match"] for x in result["checksum_checks"]),
                      "syntax_checks_passed": sum(x["passed"] for x in result["syntax_checks"]),
                      "live_cluster_tested": False, "proof_verified": False}, indent=2))
    if not valid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
