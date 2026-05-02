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
        tree = ast.parse(code)
    except SyntaxError as e:
        return {
            "success": False,
            "error_type": "SyntaxError",
            "error": str(e),
            "traceback": "",
        }

    try:
        result = None
        if tree.body and isinstance(tree.body[-1], ast.Expr):
            # Split: exec all statements, eval the last expression
            exec_tree = ast.Module(body=tree.body[:-1], type_ignores=[])
            eval_tree = ast.Expression(body=tree.body[-1].value)
            ast.fix_missing_locations(exec_tree)
            ast.fix_missing_locations(eval_tree)
            exec(compile(exec_tree, "<dorm>", "exec"), namespace)
            result = eval(compile(eval_tree, "<dorm>", "eval"), namespace)
        else:
            exec(compile(tree, "<dorm>", "exec"), namespace)

        return {"success": True, "result": result}

    except Exception as e:
        return {
            "success": False,
            "error_type": type(e).__name__,
            "error": str(e),
            "traceback": tb.format_exc(),
        }
