from app.services.insults import calculate_damage, count_words, normalize_insult


def test_normalize_insult_collapses_spaces_and_case():
    assert normalize_insult("  BIG   silly  MONSTER  ") == "big silly monster"


def test_count_words_ignores_outer_spaces():
    assert count_words("  one two   three  ") == 3


def test_damage_is_clamped_to_0_100():
    assert 0 <= calculate_damage("") <= 100
    assert calculate_damage("word " * 100) == 100
