"""A deliberately small syntax vocabulary for model-generated ARC programs."""

import ast


_DENIED = (ast.ClassDef, ast.AsyncFunctionDef, ast.Try, ast.With,
           ast.AsyncWith, ast.Raise, ast.Global, ast.Nonlocal, ast.Yield,
           ast.YieldFrom, ast.Await, ast.Delete, ast.NamedExpr)
_ATTRIBUTES = frozenset((
    "all", "any", "append", "argmax", "argmin", "astype", "copy", "count",
    "extend", "flatten", "get", "index", "item", "items", "keys", "max",
    "min", "ndim", "nonzero", "pop", "reshape", "reverse", "shape", "size",
    "sort", "sum", "T", "tolist", "transpose", "values", "setdefault", "add",
    "array", "asarray", "rot90", "flip", "fliplr", "flipud", "where",
    "zeros", "ones", "full", "stack", "concatenate", "tile", "repeat",
    "unique", "argwhere", "count_nonzero", "median", "bincount",
    "zeros_like", "ones_like", "argsort", "isin", "pad", "mean", "prod",
    "arange", "meshgrid", "uint8", "int64", "int32",
))


def validate_program(source: str) -> ast.Module:
    if len(source) > 32_000:
        raise ValueError("program too long")
    tree = ast.parse(source)
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    targets = [node for node in functions if node.name == "transform"]
    if len(targets) != 1:
        raise ValueError("exactly one transform function is required")
    function = targets[0]
    if (len(function.args.args) != 1 or function.args.args[0].arg != "grid"
            or function.args.vararg or function.args.kwarg or function.args.kwonlyargs
            or function.decorator_list):
        raise ValueError("transform must take only grid")
    for node in tree.body:
        if not isinstance(node, (ast.Import, ast.FunctionDef)):
            raise ValueError("top-level code outside functions is forbidden")
    for node in ast.walk(tree):
        if isinstance(node, _DENIED):
            raise ValueError(f"forbidden syntax: {type(node).__name__}")
        if isinstance(node, ast.ImportFrom):
            raise ValueError("only direct numpy imports are supported")
        if isinstance(node, ast.Import):
            if len(node.names) != 1 or node.names[0].name != "numpy" or node.names[0].asname not in (None, "np"):
                raise ValueError("only import numpy as np is supported")
        if isinstance(node, ast.Attribute) and node.attr not in _ATTRIBUTES:
            raise ValueError(f"attribute is not allowed: {node.attr}")
        if isinstance(node, ast.Name) and "__" in node.id:
            raise ValueError("private names are forbidden")
    for node in functions:
        if "__" in node.name or node.decorator_list:
            raise ValueError("private or decorated functions are forbidden")
        node.returns = None
        for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            arg.annotation = None
    return tree
