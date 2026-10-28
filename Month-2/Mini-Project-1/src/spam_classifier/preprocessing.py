"""Text/label validation helpers for training and inference."""

from __future__ import annotations

MAX_INPUT_CHARS = 10_000


def normalize_label(value: object) -> str:
    from .data import normalize_label as _norm

    out = _norm(value)
    if out is None:
        raise ValueError(f"Unknown label value: {value!r}. Expected spam/ham variants.")
    return out


def validate_input_text(text: object, max_chars: int = MAX_INPUT_CHARS) -> str:
    """Validate user-supplied message text.

    Returns the stripped text. Raises ValueError with a user-friendly
    message for empty/whitespace-only input or input exceeding max_chars.
    """
    if text is None:
        raise ValueError("Please enter a message to classify.")
    s = str(text).strip()
    if not s:
        raise ValueError("Please enter a message to classify — the input was empty.")
    if len(s) > max_chars:
        raise ValueError(
            f"Message is too long ({len(s):,} characters; limit is {max_chars:,}). "
            "Please shorten it and try again."
        )
    return s


def is_valid_text(text: object) -> bool:
    try:
        validate_input_text(text)
        return True
    except ValueError:
        return False
