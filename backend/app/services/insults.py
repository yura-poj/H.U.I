import re
from functools import lru_cache
from typing import Any

try:
    from model.predict import load_artifact, predict_text
except Exception:
    load_artifact = None
    predict_text = None


def normalize_insult(text: str) -> str:
    return " ".join(text.casefold().strip().split())


def count_words(text: str) -> int:
    return len(re.findall(r"\S+", text.strip()))


def fallback_damage(text: str) -> int:
    words = count_words(text)
    unique_words = len(set(normalize_insult(text).split()))
    length_bonus = min(len(text.strip()) // 18, 3)
    damage = words + unique_words + length_bonus

    return clamp_damage(damage)


def calculate_damage(text: str) -> int:
    return score_insult(text)["damage"]


def score_insult(text: str) -> dict[str, Any]:
    try:
        prediction = _predict_with_model(text)
    except Exception:
        return {
            "damage": fallback_damage(text),
            "source": "fallback",
            "toxic": None,
            "toxicity_score": None,
            "label": None,
            "signals": {},
        }

    return {
        "damage": clamp_damage(prediction.get("insult_score", 0)),
        "source": "model",
        "toxic": bool(prediction.get("toxic", False)),
        "toxicity_score": prediction.get("toxicity_score"),
        "label": prediction.get("label"),
        "signals": prediction.get("signals", {}),
    }


def clamp_damage(value: Any) -> int:
    try:
        damage = int(value)
    except (TypeError, ValueError):
        damage = 0

    return max(0, min(10, damage))


def _predict_with_model(text: str) -> dict[str, Any]:
    if load_artifact is None or predict_text is None:
        raise RuntimeError("Model prediction module is unavailable.")

    return predict_text(text, _model_artifact())


@lru_cache(maxsize=1)
def _model_artifact() -> dict[str, Any]:
    if load_artifact is None:
        raise RuntimeError("Model artifact loader is unavailable.")

    return load_artifact()


def monster_reply(damage: int, won: bool) -> str:
    if won:
        return "Монстр повержен обзывательством."

    if damage == 0:
        return "Фраза засчитана, но монстр только моргнул."

    if damage < 3:
        return "Монстр хмурится, но пока стоит."

    if damage < 7:
        return "Монстра качнуло от словесного удара."

    return "Монстр выглядит глубоко оскорбленным."
