"""Private child entry point. Receives only candidate source and input grids."""

import ast
import json
from pathlib import Path
import sys

sys.path.insert(0, sys.argv[1])
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as _numpy
from validator import validate_program


class _SafeNumpy:
    """Small numerical vocabulary sufficient for common ARC grid transforms."""

    _names = frozenset(("array", "asarray", "rot90", "flip", "fliplr", "flipud",
                        "transpose", "where", "zeros", "ones", "full", "stack",
                        "concatenate", "tile", "repeat", "unique", "argwhere",
                        "count_nonzero", "sum", "max", "min", "median", "bincount",
                        "zeros_like", "ones_like", "argsort", "isin", "pad",
                        "mean", "prod", "arange", "meshgrid", "uint8", "int64", "int32"))

    def __getattribute__(self, name):
        if name in object.__getattribute__(self, "_names"):
            return getattr(_numpy, name)
        raise AttributeError(name)


def main() -> None:
    payload = json.load(sys.stdin)
    tree = validate_program(payload["source"])
    class RemoveNumpyImport(ast.NodeTransformer):
        def visit_Import(self, node):
            return ast.copy_location(ast.Pass(), node)
    tree = ast.fix_missing_locations(RemoveNumpyImport().visit(tree))
    safe_builtins = {name: getattr(__builtins__, name) for name in (
        "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float",
        "int", "len", "list", "map", "max", "min", "range", "reversed",
        "round", "set", "sorted", "sum", "tuple", "zip")}
    namespace = {"__builtins__": safe_builtins, "np": _SafeNumpy(), "numpy": _SafeNumpy()}
    exec(compile(tree, "<candidate>", "exec"), namespace)
    outputs = [namespace["transform"](grid) for grid in payload["grids"]]
    normalized = [x.tolist() if hasattr(x, "tolist") else x for x in outputs]
    json.dump({"status": "ok", "outputs": normalized}, sys.stdout)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        json.dump({"status": "error", "error": f"{type(exc).__name__}: {exc}"}, sys.stdout)
