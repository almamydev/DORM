import ast
import traceback as tb


def _build_namespace() -> dict:
    from django.apps import apps
    from django.db.models import Avg, Count, F, Max, Min, OuterRef, Q, Subquery, Sum, Value

    namespace: dict = {
        "Q": Q, "F": F,
        "Count": Count, "Sum": Sum, "Avg": Avg, "Max": Max, "Min": Min,
        "Value": Value, "OuterRef": OuterRef, "Subquery": Subquery,
    }
    for model in apps.get_models():
        namespace[model.__name__] = model
    return namespace


def _error(e: Exception, **extra) -> dict:
    return {
        "success": False,
        "error_type": type(e).__name__,
        "error": str(e),
        "traceback": "" if isinstance(e, SyntaxError) else tb.format_exc(),
        **extra,
    }


def _run(code: str, namespace: dict, filename: str = "<dorm>", capture: bool = True):
    """
    Execute code in namespace. When capture is True and the block ends with an
    expression, that expression is evaluated and returned (REPL behaviour).
    """
    tree = ast.parse(code, filename)
    if capture and tree.body and isinstance(tree.body[-1], ast.Expr):
        # Split: exec all statements, eval the last expression
        exec_tree = ast.Module(body=tree.body[:-1], type_ignores=[])
        eval_tree = ast.Expression(body=tree.body[-1].value)
        ast.fix_missing_locations(exec_tree)
        ast.fix_missing_locations(eval_tree)
        exec(compile(exec_tree, filename, "exec"), namespace)
        return eval(compile(eval_tree, filename, "eval"), namespace)
    exec(compile(tree, filename, "exec"), namespace)
    return None


def execute(code: str, extra_locals: dict | None = None) -> dict:
    """
    Execute a multi-line ORM code string.

    The last expression in the code block is captured as the result,
    mimicking REPL behaviour. Returns:
      {"success": True,  "result": <any>}
      {"success": False, "error_type": str, "error": str, "traceback": str}
    """
    namespace = _build_namespace()
    if extra_locals:
        namespace.update(extra_locals)
    try:
        return {"success": True, "result": _run(code, namespace)}
    except Exception as e:
        return _error(e)


def execute_flow(cells: list[str], extra_locals: dict | None = None) -> dict:
    """
    Execute notebook cells in order in one shared namespace. Only the last
    cell's trailing expression is captured as the result.

    Same return shape as execute(); errors also carry "cell": the 0-based
    index of the failing cell.
    """
    namespace = _build_namespace()
    if extra_locals:
        namespace.update(extra_locals)

    last = len(cells) - 1
    for i, code in enumerate(cells):
        try:
            result = _run(code, namespace, f"<cell {i + 1}>", capture=(i == last))
        except Exception as e:
            return _error(e, cell=i)
    return {"success": True, "result": result if cells else None}
