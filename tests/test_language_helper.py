from app.agent.intent_policy.language import is_russian


def test_is_russian_pure_cyrillic():
    assert is_russian("не понял вопрос") is True


def test_is_russian_mixed_majority_cyrillic():
    assert is_russian("можешь на русском объяснить please") is True


def test_is_russian_pure_english():
    assert is_russian("can you explain please") is False


def test_is_russian_empty_or_digits():
    assert is_russian("") is False
    assert is_russian(None) is False
    assert is_russian("123 456") is False
