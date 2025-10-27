"""
Простейшие тесты для проверки что pytest работает.
"""
import pytest


def test_simple_addition():
    """Простой тест - проверяет что тесты вообще работают"""
    assert 1 + 1 == 2


def test_simple_string():
    """Простой тест со строками"""
    assert "hello" == "hello"


def test_simple_list():
    """Простой тест со списками"""
    test_list = [1, 2, 3]
    assert len(test_list) == 3
    assert test_list[0] == 1
