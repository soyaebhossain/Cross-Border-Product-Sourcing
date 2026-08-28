from __future__ import annotations

import unicodedata

from email_validator import EmailNotValidError, validate_email


def normalize_identifier_key(value: str | None) -> str | None:
    """Return the Unicode-stable, case-insensitive key used for login identity."""

    if value is None:
        return None
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    return normalized or None


def normalize_username(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip()
    if not normalized:
        raise ValueError("Username cannot be blank")
    if any(unicodedata.category(character).startswith("C") for character in normalized):
        raise ValueError("Username contains unsupported control characters")
    return normalized


def normalize_email_address(value: str) -> str:
    """Validate and normalize an address without making a network/DNS request.

    ``test_environment=True`` preserves the repository's reserved ``.test``
    addresses while applying the same syntax and header-injection checks.
    """

    if "\r" in value or "\n" in value:
        raise ValueError("Email address must not contain line breaks")
    try:
        result = validate_email(
            unicodedata.normalize("NFKC", value).strip(),
            check_deliverability=False,
            test_environment=True,
        )
    except EmailNotValidError as exc:
        raise ValueError("Enter a valid email address") from exc
    return result.normalized
