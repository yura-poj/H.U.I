import re


def normalize_insult(text: str) -> str:
    return " ".join(text.casefold().strip().split())


def count_words(text: str) -> int:
    return len(re.findall(r"\S+", text.strip()))


def calculate_damage(text: str) -> int:
    words = count_words(text)
    unique_words = len(set(normalize_insult(text).split()))
    length_bonus = min(len(text.strip()) // 12, 20)
    damage = words * 7 + unique_words * 5 + length_bonus

    return max(0, min(100, damage))


def monster_reply(damage: int, won: bool) -> str:
    if won:
        return "The monster is defeated by the insult."

    if damage == 0:
        return "The monster barely notices."

    if damage < 25:
        return "The monster frowns, but stays standing."

    if damage < 60:
        return "The monster staggers from the insult."

    return "The monster looks deeply offended."
