import app.services.insults as insults
from app.services.insults import calculate_damage, count_words, normalize_insult, score_insult


def test_normalize_insult_collapses_spaces_and_case():
    assert normalize_insult("  BIG   silly  MONSTER  ") == "big silly monster"


def test_count_words_ignores_outer_spaces():
    assert count_words("  one two   three  ") == 3


def test_damage_is_clamped_to_0_10():
    assert isinstance(calculate_damage(""), int)
    assert 0 <= calculate_damage("") <= 10
    assert 0 <= calculate_damage("word " * 100) <= 10


def test_damage_uses_small_integer_scale_for_normal_insult():
    damage = calculate_damage("you soggy boot with eyebrows")

    assert isinstance(damage, int)
    assert 0 <= damage <= 10


def test_score_insult_uses_model_prediction(monkeypatch):
    insults._model_artifact.cache_clear()
    monkeypatch.setattr(insults, "load_artifact", lambda: {"loaded": True})
    monkeypatch.setattr(
        insults,
        "predict_text",
        lambda text, artifact: {
            "insult_score": 8,
            "toxic": False,
            "toxicity_score": 0.12,
            "label": "normal",
            "signals": {"insult": 0.7},
        },
    )

    score = score_insult("you soggy boot with eyebrows")

    assert score == {
        "damage": 8,
        "source": "model",
        "toxic": False,
        "toxicity_score": 0.12,
        "label": "normal",
        "signals": {"insult": 0.7},
    }


def test_score_insult_falls_back_when_model_fails(monkeypatch):
    insults._model_artifact.cache_clear()
    monkeypatch.setattr(insults, "load_artifact", lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    score = score_insult("you soggy boot with eyebrows")

    assert score["source"] == "fallback"
    assert isinstance(score["damage"], int)
    assert 0 <= score["damage"] <= 10
    assert score["signals"] == {}
