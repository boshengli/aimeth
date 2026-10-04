"""Execute candidate transforms in a bounded child process.

On macOS, sandbox-exec denies network and candidate access to user files. AST
validation, reduced builtins, Python isolated mode, and a hard wall timeout add
defense in depth. This is a research sandbox, not a proof of hostile-code safety.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import resource
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any

import numpy as np

from .data import Grid, _grid
from .validator import validate_program


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    outputs: list[Grid] | None
    error: str | None = None


def _sandbox_profile(worker: Path, python_exe: Path) -> str:
    # macOS's Python launcher and numpy need system reads outside their install
    # tree. Candidate I/O names are unavailable in the reduced builtins; the OS
    # profile additionally denies all writes and network access.
    return "(version 1)\n(deny default)\n(allow process*)\n(allow file-read*)\n(allow sysctl-read)\n"


def run_program(source: str, grids: list[Grid], timeout_s: float = 2.0) -> ExecutionResult:
    """Run one candidate on a batch of inputs; no target outputs enter child."""
    try:
        validate_program(source)
        for grid in grids:
            _grid(grid)
    except (SyntaxError, ValueError, TypeError) as exc:
        return ExecutionResult("invalid_program", None, str(exc)[:250])
    worker = Path(__file__).with_name("_worker.py").resolve()
    python_exe = Path(sys.executable).resolve()
    sandbox = shutil.which("sandbox-exec") if sys.platform == "darwin" else None
    if sys.platform == "darwin" and not sandbox:
        return ExecutionResult("sandbox_unavailable", None)
    numpy_site = str(Path(np.__file__).resolve().parents[1])
    command = [str(python_exe), "-I", str(worker), numpy_site]
    if sandbox:
        command = [sandbox, "-p", _sandbox_profile(worker, python_exe), *command]
    # Linux requires bubblewrap for the same filesystem/network boundary; fail
    # closed if absent rather than silently executing untrusted model output.
    elif sys.platform.startswith("linux"):
        bwrap = shutil.which("bwrap")
        if not bwrap:
            return ExecutionResult("sandbox_unavailable", None)
        command = [bwrap, "--ro-bind", "/usr", "/usr", "--ro-bind", "/lib", "/lib",
                   "--ro-bind", str(worker), str(worker), "--unshare-net", "--dev", "/dev",
                   "--proc", "/proc", "--", *command]
    payload = json.dumps({"source": source, "grids": grids}, separators=(",", ":"))
    def limit_child() -> None:
        resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
        if sys.platform.startswith("linux"):
            resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    try:
        proc = subprocess.run(command, input=payload, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=timeout_s,
                              cwd=tempfile.gettempdir(), env={"PATH": "/usr/bin:/bin"},
                              preexec_fn=limit_child)
    except subprocess.TimeoutExpired:
        return ExecutionResult("timeout", None)
    except OSError as exc:
        return ExecutionResult("sandbox_error", None, str(exc)[:250])
    if proc.returncode:
        return ExecutionResult("execution_error", None, proc.stderr[-400:] or f"exit {proc.returncode}")
    try:
        response: dict[str, Any] = json.loads(proc.stdout)
        if response["status"] != "ok":
            return ExecutionResult("execution_error", None, response.get("error", "candidate failed")[:250])
        outputs = [_grid(x) for x in response["outputs"]]
        if len(outputs) != len(grids):
            raise ValueError("output count mismatch")
        return ExecutionResult("ok", outputs)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return ExecutionResult("invalid_output", None, str(exc)[:250])
