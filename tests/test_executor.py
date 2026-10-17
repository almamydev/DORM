import pytest
from dorm.executor import execute, execute_flow


def test_execute_expression():
    result = execute("1 + 1")
    assert result == {"success": True, "result": 2}


def test_execute_multiline():
    result = execute("x = 10\nx * 3")
    assert result == {"success": True, "result": 30}


def test_execute_statement_only():
    result = execute("x = 42")
    assert result["success"] is True
    assert result["result"] is None


def test_execute_syntax_error():
    result = execute("def (")
    assert result["success"] is False
    assert result["error_type"] == "SyntaxError"


def test_execute_runtime_error():
    result = execute("1 / 0")
    assert result["success"] is False
    assert result["error_type"] == "ZeroDivisionError"
    assert "traceback" in result


def test_flow_shares_namespace():
    result = execute_flow(["x = 2", "y = x * 5", "y + 1"])
    assert result == {"success": True, "result": 11}


def test_flow_only_last_cell_is_captured():
    result = execute_flow(["1 + 1", "x = 3"])
    assert result == {"success": True, "result": None}


def test_flow_reports_failing_cell():
    result = execute_flow(["x = 1", "1 / 0", "x"])
    assert result["success"] is False
    assert result["error_type"] == "ZeroDivisionError"
    assert result["cell"] == 1
    assert "<cell 2>" in result["traceback"]


def test_flow_syntax_error_cell():
    result = execute_flow(["x = 1", "def ("])
    assert result["success"] is False
    assert result["error_type"] == "SyntaxError"
    assert result["cell"] == 1
