import pytest
from dorm.executor import execute


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
