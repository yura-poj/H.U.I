import re


OBSCENE_FRAGMENTS = (
    "бляд",
    "еба",
    "ёба",
    "пизд",
    "хуй",
    "хуе",
    "сука",
    "муд",
    "долбо",
    "гандон",
    "говн",
    "хрен",
    "жоп",
)

THREAT_FRAGMENTS = (
    "убить",
    "убью",
    "повес",
    "зареж",
    "заколот",
    "отруб",
    "смерт",
    "казн",
)

MILD_INSULT_FRAGMENTS = (
    "дурак",
    "туп",
    "лох",
    "балабол",
    "пустослов",
    "урод",
    "чучело",
    "болван",
)

ABSURD_GAME_FRAGMENTS = (
    "болот",
    "вонюч",
    "дыряв",
    "картоф",
    "луж",
    "мокр",
    "носок",
    "пельмен",
    "плесен",
    "скрип",
    "слиз",
    "суп",
    "тапк",
)

COMPARISON_WORDS = ("как", "будто", "словно", "похож", "харизм")
COMPOUND_FRAGMENTS = tuple(dict.fromkeys(OBSCENE_FRAGMENTS + ABSURD_GAME_FRAGMENTS + ("проеб", "ебин", "помой", "сран")))
WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+")


def clamp_int(value: float, lower: int, upper: int) -> int:
    return max(lower, min(upper, int(value)))


def clamp_float(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def count_fragments(text: str, fragments: tuple[str, ...]) -> int:
    lowered = text.lower()
    return sum(lowered.count(fragment) for fragment in fragments)


def uppercase_ratio(text: str) -> float:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for char in letters if char.isupper()) / len(letters)


def saturate(value: float, scale: float) -> float:
    if value <= 0:
        return 0.0
    return clamp_float(value / (value + scale))


def lexical_diversity(words: list[str]) -> float:
    if len(words) < 4:
        return 0.0
    unique_ratio = len(set(words)) / len(words)
    diversity = clamp_float((unique_ratio - 0.5) / 0.35)
    useful_length = clamp_float((len(words) - 3) / 7)
    too_long_penalty = clamp_float(24 / max(len(words), 24))
    return diversity * useful_length * too_long_penalty


def length_quality(words: list[str]) -> float:
    word_count = len(words)
    if word_count < 4:
        return 0.0
    if word_count <= 8:
        return clamp_float((word_count - 3) / 5)
    if word_count <= 14:
        return 1.0
    if word_count <= 22:
        return clamp_float(1.0 - ((word_count - 14) / 8) * 0.45)
    return clamp_float(0.45 - ((word_count - 22) / 18) * 0.35)


def comparison_count(words: list[str]) -> int:
    return sum(1 for word in words if any(marker in word for marker in COMPARISON_WORDS))


def short_token_ratio(words: list[str]) -> float:
    if not words:
        return 1.0
    return sum(1 for word in words if len(word) <= 3) / len(words)


def meaningful_word_ratio(words: list[str]) -> float:
    if not words:
        return 0.0
    return sum(1 for word in words if len(word) >= 4) / len(words)


def looks_disconnected(
    words: list[str],
    obscene_hits: int,
    mild_hits: int,
    absurd_hits: int,
    comparisons: int,
    compound_bonus: float,
) -> bool:
    if len(words) < 5:
        return False
    if compound_bonus > 0 or mild_hits or absurd_hits >= 2 or comparisons:
        return False
    if obscene_hits > 1:
        return False
    if short_token_ratio(words) >= 0.55:
        return True
    return meaningful_word_ratio(words) < 0.35


def compound_score(words: list[str]) -> float:
    best = 0.0
    for word in words:
        if len(word) < 9:
            continue
        fragments = {fragment for fragment in COMPOUND_FRAGMENTS if fragment in word}
        if len(fragments) < 2:
            continue
        has_rough_part = any(fragment in word for fragment in OBSCENE_FRAGMENTS)
        if not has_rough_part:
            continue
        best = max(best, 0.65 + min((len(fragments) - 2) * 0.2, 0.35))
    return clamp_float(best)


def score_result(score: int, debug: dict[str, object], return_debug: bool) -> int | tuple[int, dict[str, object]]:
    return (score, debug) if return_debug else score


def heuristic_insult_score(
    text: str,
    toxicity_score: float,
    signal_scores: dict[str, float],
    coherence_score: float = 1.0,
    return_debug: bool = False,
) -> int | tuple[int, dict[str, object]]:
    words = [word.lower() for word in WORD_RE.findall(text)]
    word_count = len(words)
    insult_signal = clamp_float(signal_scores.get("INSULT", 0.0))
    obscenity_signal = clamp_float(signal_scores.get("OBSCENITY", 0.0))
    threat_signal = clamp_float(signal_scores.get("THREAT", 0.0))
    coherence_score = clamp_float(coherence_score)

    obscene_hits = count_fragments(text, OBSCENE_FRAGMENTS)
    threat_hits = count_fragments(text, THREAT_FRAGMENTS)
    mild_hits = count_fragments(text, MILD_INSULT_FRAGMENTS)
    absurd_hits = count_fragments(text, ABSURD_GAME_FRAGMENTS)
    comparisons = comparison_count(words)
    has_surface_insult = bool(obscene_hits or mild_hits or absurd_hits or comparisons)

    if (
        not has_surface_insult
        and toxicity_score < 0.25
        and insult_signal < 0.18
        and obscenity_signal < 0.15
        and threat_signal < 0.2
    ):
        coherence_penalty = clamp_float((0.55 - coherence_score) / 0.35)
        return score_result(
            0,
            {
                "obscene_bonus": 0.0,
                "originality_bonus": 0.0,
                "compound_bonus": 0.0,
                "length_quality": round(length_quality(words), 4),
                "coherence_penalty": round(coherence_penalty, 4),
                "cap": 0,
                "raw_score": 0.0,
                "reason": "no_insult_signal",
            },
            return_debug,
        )

    obscene_bonus = max(saturate(obscene_hits, 1.6), obscenity_signal * 0.75)
    mild_bonus = saturate(mild_hits, 2.5)
    insult_signal_bonus = max(insult_signal, mild_bonus * 0.55)

    image_component = max(
        saturate(absurd_hits, 2.0),
        saturate(comparisons, 1.5),
    )
    diversity_component = lexical_diversity(words)
    length_component = length_quality(words)
    emphasis_component = clamp_float(min(text.count("!") / 6.0, 0.6) + min(uppercase_ratio(text), 0.35))
    originality_bonus = max(
        image_component,
        min(1.0, (image_component * 0.65) + (diversity_component * 0.25) + (emphasis_component * 0.1)),
    )
    compound_bonus = compound_score(words)
    creativity = max(originality_bonus, compound_bonus)
    creative_structure = compound_bonus >= 0.65 and originality_bonus >= 0.6
    effective_coherence_score = max(coherence_score, 0.75) if creative_structure else coherence_score
    disconnected = looks_disconnected(words, obscene_hits, mild_hits, absurd_hits, comparisons, compound_bonus)
    coherence_penalty = clamp_float((0.55 - effective_coherence_score) / 0.35)
    if disconnected or effective_coherence_score < 0.3:
        return score_result(
            0,
            {
                "obscene_bonus": round(obscene_bonus, 4),
                "originality_bonus": round(originality_bonus, 4),
                "compound_bonus": round(compound_bonus, 4),
                "length_quality": round(length_component, 4),
                "coherence_penalty": 1.0 if disconnected else round(coherence_penalty, 4),
                "coherence_override": creative_structure,
                "cap": 0,
                "raw_score": 0.0,
                "reason": "incoherent_text",
            },
            return_debug,
        )
    low_content_obscenity = (
        obscene_hits == 1
        and not mild_hits
        and not absurd_hits
        and not comparisons
        and compound_bonus == 0
        and word_count >= 5
        and short_token_ratio(words) >= 0.55
    )

    base = max(insult_signal_bonus, obscene_bonus * 0.75)
    base_level = 0.8 + (base * 4.55)
    if obscene_bonus >= 0.35:
        base_level = max(base_level, 4.2 + min(obscene_bonus, 0.65) * 1.65)
    if mild_hits and obscene_bonus < 0.25:
        base_level = max(base_level, 1.8 + mild_bonus * 1.65)

    creativity_gate = clamp_float((base + obscene_bonus + insult_signal_bonus) / 1.4)
    length_gate = 0.55 + (length_component * 0.45)
    creativity_lift = creativity * creativity_gate * length_gate * 3.75
    if compound_bonus >= 0.65 and (obscene_bonus >= 0.35 or insult_signal_bonus >= 0.45):
        compound_lift = (2.35 + compound_bonus * 1.1) * (0.72 + length_component * 0.28)
        creativity_lift = max(creativity_lift, compound_lift)
    if compound_bonus >= 0.65 and originality_bonus >= 0.6 and length_component >= 0.85:
        creativity_lift = max(creativity_lift, 4.15 + compound_bonus * 1.2)

    raw_score = base_level + creativity_lift
    if coherence_penalty > 0:
        raw_score *= 1.0 - (coherence_penalty * 0.6)

    if creativity < 0.25:
        cap = 6.0
    elif creativity < 0.65:
        cap = 8.0
    elif (obscene_bonus >= 0.35 or insult_signal_bonus >= 0.45) and length_component >= 0.85:
        cap = 10.0
    elif obscene_bonus >= 0.35 or insult_signal_bonus >= 0.45:
        cap = 9.0
    else:
        cap = 7.0

    if length_component < 0.85:
        cap = min(cap, 9.0)

    if obscene_bonus < 0.25:
        cap = min(cap, 6.0 if insult_signal_bonus >= 0.45 else 4.0)
        if creativity < 0.25 and word_count <= 4 and mild_hits:
            cap = min(cap, 3.0)
    if obscene_bonus >= 0.35 and creativity < 0.25:
        cap = min(cap, 6.0)
    if low_content_obscenity:
        cap = min(cap, 2.0)
    if coherence_penalty > 0:
        cap = min(cap, 4.0 if coherence_penalty >= 0.55 else 7.0)

    threat_pressure = max(threat_signal, saturate(threat_hits, 1.5))
    if threat_pressure >= 0.55 and creativity < 0.65:
        cap = min(cap, 6.0)
    if toxicity_score >= 0.9 and insult_signal_bonus < 0.2:
        cap = min(cap, 5.0)

    score = clamp_int(min(raw_score, cap) + 0.35, 0, 10)
    return score_result(
        score,
        {
            "obscene_bonus": round(obscene_bonus, 4),
            "originality_bonus": round(originality_bonus, 4),
            "compound_bonus": round(compound_bonus, 4),
            "length_quality": round(length_component, 4),
            "coherence_penalty": round(coherence_penalty, 4),
            "coherence_override": creative_structure,
            "cap": round(cap, 4),
            "raw_score": round(raw_score, 4),
            "base_level": round(base_level, 4),
            "creativity_lift": round(creativity_lift, 4),
            "threat_pressure": round(threat_pressure, 4),
        },
        return_debug,
    )
