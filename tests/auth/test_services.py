"""Tests for ``service_crm.auth.services``.

Pure helpers: Argon2 hash/verify and email normalisation. No DB.
"""

from __future__ import annotations

import pytest

from service_crm.auth import services


@pytest.mark.unit
def test_hash_password_returns_argon2_encoded_string() -> None:
    encoded = services.hash_password("hunter2")
    assert encoded.startswith("$argon2")
    # Argon2 encoded length is ~97 chars; pin a sane minimum.
    assert len(encoded) >= 60


@pytest.mark.unit
def test_hash_password_is_salted_and_unique() -> None:
    a = services.hash_password("same-input")
    b = services.hash_password("same-input")
    assert a != b


@pytest.mark.unit
def test_verify_password_accepts_correct_plaintext() -> None:
    encoded = services.hash_password("correct-horse")
    assert services.verify_password("correct-horse", encoded) is True


@pytest.mark.unit
def test_verify_password_rejects_wrong_plaintext() -> None:
    encoded = services.hash_password("correct-horse")
    assert services.verify_password("wrong-horse", encoded) is False


@pytest.mark.unit
def test_verify_password_reraises_on_malformed_hash() -> None:
    from argon2.exceptions import InvalidHashError

    with pytest.raises(InvalidHashError):
        services.verify_password("anything", "not-a-real-hash")


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Alice@Example.com", "alice@example.com"),
        ("  bob@example.com  ", "bob@example.com"),
        ("CARL@EXAMPLE.COM", "carl@example.com"),
        ("already.lower@example.com", "already.lower@example.com"),
    ],
)
def test_normalize_email(raw: str, expected: str) -> None:
    assert services.normalize_email(raw) == expected
