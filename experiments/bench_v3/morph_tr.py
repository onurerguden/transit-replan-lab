# pyright: basic
"""Turkish case suffixes with vowel harmony, consonant assimilation and the buffer letter."""

BACK = set("aıou")
FRONT = set("eiöü")
VOWELS = BACK | FRONT
VOICELESS = set("çfhkpsşt")
APOSTROPHE = "'"


def fold_i(text: str) -> str:
    return text.replace("İ", "i").replace("I", "ı").lower()


def last_vowel(word: str) -> str:
    return next((char for char in reversed(fold_i(word)) if char in VOWELS), "e")


def ends_in_vowel(word: str) -> bool:
    return fold_i(word)[-1] in VOWELS


def locative(word: str) -> str:
    voiceless = fold_i(word)[-1] in VOICELESS
    consonant = "t" if voiceless else "d"
    vowel = "a" if last_vowel(word) in BACK else "e"
    return f"{word}{APOSTROPHE}{consonant}{vowel}"


def ablative(word: str) -> str:
    return locative(word) + "n"


def dative(word: str) -> str:
    vowel = "a" if last_vowel(word) in BACK else "e"
    glide = "y" if ends_in_vowel(word) else ""
    return f"{word}{APOSTROPHE}{glide}{vowel}"


SPOKEN = {
    "0": "sıfır", "1": "bir", "2": "iki", "3": "üç", "4": "dört",
    "5": "beş", "6": "altı", "7": "yedi", "8": "sekiz", "9": "dokuz",
}  # fmt: skip
TENS = {"1": "on", "2": "yirmi", "3": "otuz", "4": "kırk", "5": "elli"}


def spoken_tail(hour: int, minute: int) -> str:
    """The last spoken word of a clock time, which decides the suffix."""
    if minute == 0:
        return (
            TENS[str(hour // 10)]
            if hour >= 10 and hour % 10 == 0
            else SPOKEN[str(hour % 10)]
        )
    return SPOKEN[str(minute % 10)] if minute % 10 else TENS[str(minute // 10)]


def clock_ablative(text: str) -> str:
    hour, minute = (int(part) for part in text.split(":"))
    tail = spoken_tail(hour, minute)
    return locative(tail).replace(tail, text, 1) + "n"


def clock_dative(text: str) -> str:
    hour, minute = (int(part) for part in text.split(":"))
    return dative(spoken_tail(hour, minute)).replace(spoken_tail(hour, minute), text, 1)
