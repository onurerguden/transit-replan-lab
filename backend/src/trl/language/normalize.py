"""Fold Turkish and English text while keeping each character's source offset."""

import unicodedata


def normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.casefold().replace("ı", "i"))
    return "".join(char for char in folded if not unicodedata.combining(char))


def folded(text: str) -> tuple[str, list[int]]:
    """Return the folded text and, for each folded character, its index in `text`."""
    characters: list[str] = []
    offsets: list[int] = []
    for index, char in enumerate(text):
        normalized = normalize(char)
        characters.append(normalized)
        offsets.extend([index] * len(normalized))
    return "".join(characters), offsets
