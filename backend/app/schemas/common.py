"""Common API schemas and reusable validated types."""

import unicodedata
from typing import Annotated, Generic, TypeVar

from fastapi import Query
from pydantic import AfterValidator, BaseModel, Field

T = TypeVar("T")

# Shared database integer limit (PostgreSQL 32-bit signed INTEGER range)
MAX_DB_INT: int = 2_147_483_647
MAX_PAGINATION_LIMIT: int = 500


# Disallowed invisible formatting, line/paragraph breaks, and bidirectional override characters.
# - U+200B: ZERO WIDTH SPACE (invisible delimiter used for visual spoofing and filter bypass)
# - U+2028: LINE SEPARATOR (ambiguous multiline break that disrupts single-line records)
# - U+2029: PARAGRAPH SEPARATOR (ambiguous paragraph break disrupting structured logs and tables)
# - U+202A..U+202E: LRE, RLE, PDF, LRO, RLO (bidi embedding and override controls used for spoofing)
# - U+2060: WORD JOINER (zero-width invisible formatting character)
# - U+2066..U+2069: LRI, RLI, FSI, PDI (bidi isolate controls used for visual spoofing)
# - U+FEFF: ZERO WIDTH NO-BREAK SPACE / BOM (invisible artifact from byte order mark encoding)
DISALLOWED_INVISIBLE_AND_BIDI_CHARS: frozenset[str] = frozenset(
    {
        "\u200b",  # U+200B ZERO WIDTH SPACE
        "\u2028",  # U+2028 LINE SEPARATOR
        "\u2029",  # U+2029 PARAGRAPH SEPARATOR
        "\u202a",  # U+202A LEFT-TO-RIGHT EMBEDDING
        "\u202b",  # U+202B RIGHT-TO-LEFT EMBEDDING
        "\u202c",  # U+202C POP DIRECTIONAL FORMATTING
        "\u202d",  # U+202D LEFT-TO-RIGHT OVERRIDE
        "\u202e",  # U+202E RIGHT-TO-LEFT OVERRIDE
        "\u2060",  # U+2060 WORD JOINER
        "\u2066",  # U+2066 LEFT-TO-RIGHT ISOLATE
        "\u2067",  # U+2067 RIGHT-TO-LEFT ISOLATE
        "\u2068",  # U+2068 FIRST STRONG ISOLATE
        "\u2069",  # U+2069 POP DIRECTIONAL ISOLATE
        "\ufeff",  # U+FEFF ZERO WIDTH NO-BREAK SPACE (BOM)
    }
)


def validate_single_line_text(v: str) -> str:
    """Validate single-line text: reject NUL, Cc controls, unencodable UTF-8, and bidi blocklist."""
    if not isinstance(v, str):
        return v
    if "\x00" in v:
        raise ValueError("NUL characters (0x00) are not permitted.")
    try:
        v.encode("utf-8")
    except (UnicodeEncodeError, UnicodeError) as e:
        raise ValueError(f"Text cannot be encoded as valid UTF-8: {e}") from e

    cleaned = v.strip()
    if not cleaned:
        raise ValueError("Must not be empty or whitespace only.")

    for ch in cleaned:
        if ch in DISALLOWED_INVISIBLE_AND_BIDI_CHARS:
            raise ValueError("Invisible formatting and bidi override characters are not permitted.")
        if unicodedata.category(ch) == "Cc":
            raise ValueError("Control characters are not permitted in single-line text.")

    return cleaned


def validate_optional_single_line_text(v: str | None) -> str | None:
    """Validate optional single-line text: return None if None or validate text."""
    if v is None:
        return None
    return validate_single_line_text(v)


def validate_note_text(v: str | None) -> str | None:
    """Validate multi-line note: reject NUL, Cc controls (except \\n, \\r, \\t), bidi blocklist."""
    if v is None:
        return None
    if not isinstance(v, str):
        return v
    if "\x00" in v:
        raise ValueError("NUL characters (0x00) are not permitted.")
    try:
        v.encode("utf-8")
    except (UnicodeEncodeError, UnicodeError) as e:
        raise ValueError(f"Text cannot be encoded as valid UTF-8: {e}") from e

    cleaned = v.strip()
    if not cleaned:
        return None

    for ch in cleaned:
        if ch in DISALLOWED_INVISIBLE_AND_BIDI_CHARS:
            raise ValueError("Invisible formatting and bidi override characters are not permitted.")
        if unicodedata.category(ch) == "Cc" and ch not in ("\n", "\r", "\t"):
            raise ValueError("Control characters are not permitted in note text.")

    return cleaned


def validate_patch_note_text(v: str | None) -> str | None:
    """Validate patch condition note.

    Rejects NUL, Cc controls (except \\n, \\r, \\t), unencodable UTF-8, and bidi blocklist;
    preserves empty string.
    """
    if v is None:
        return None
    if not isinstance(v, str):
        return v
    if "\x00" in v:
        raise ValueError("NUL characters (0x00) are not permitted.")
    try:
        v.encode("utf-8")
    except (UnicodeEncodeError, UnicodeError) as e:
        raise ValueError(f"Text cannot be encoded as valid UTF-8: {e}") from e

    cleaned = v.strip()

    for ch in v:
        if ch in ("\n", "\r", "\t", " "):
            continue
        if ch in DISALLOWED_INVISIBLE_AND_BIDI_CHARS:
            raise ValueError("Invisible formatting and bidi override characters are not permitted.")
        if unicodedata.category(ch) == "Cc":
            raise ValueError("Control characters are not permitted in note text.")

    return cleaned


# Reusable numeric and identifier types bounded by PostgreSQL 32-bit integer
PositiveId = Annotated[
    int,
    Field(ge=1, le=MAX_DB_INT, description="Positive database integer ID (1 to 2147483647)"),
]

OptionalIdQuery = Annotated[
    int | None,
    Query(ge=1, le=MAX_DB_INT, description="Optional ID filter (1 to 2147483647)"),
]

PositivePaise = Annotated[
    int,
    Field(gt=0, le=MAX_DB_INT, description="Positive amount in integer paise (1 to 2147483647)"),
]

PaginationLimit = Annotated[
    int,
    Query(ge=1, le=MAX_PAGINATION_LIMIT, description="Max records to return"),
]

PaginationOffset = Annotated[
    int,
    Query(ge=0, le=MAX_DB_INT, description="Offset for pagination"),
]

# Reusable string types
SingleLineText = Annotated[str, AfterValidator(validate_single_line_text)]
OptionalSingleLineText = Annotated[str | None, AfterValidator(validate_optional_single_line_text)]
NoteText = Annotated[str | None, AfterValidator(validate_note_text)]


class ErrorResponse(BaseModel):
    """Standard API error response envelope."""

    error: str
    detail: str
    code: str
    request_id: str | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated collection response."""

    items: list[T]
    total: int
    limit: int
    offset: int
