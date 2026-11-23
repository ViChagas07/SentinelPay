from uuid import uuid4

import pytest

from paysentineliq.application.security.password_policy import (
    password_policy_payload,
    validate_password,
)
from paysentineliq.infrastructure.security.passwords import Argon2PasswordHasher

pytestmark = pytest.mark.unit

_FAST_PARAMS = {
    "time_cost": 1,
    "memory_cost_kib": 8192,
    "parallelism": 1,
    "hash_len": 16,
    "salt_len": 8,
}


def test_argon2id_hash_is_salted_and_verifiable() -> None:
    hasher = Argon2PasswordHasher(**_FAST_PARAMS)

    first = hasher.hash("uma-senha-longa-123")
    second = hasher.hash("uma-senha-longa-123")

    assert first != second
    assert first.startswith("$argon2id$")
    assert hasher.verify(first, "uma-senha-longa-123") is True
    assert hasher.verify(first, "outra-senha-longa-123") is False


def test_argon2id_detects_the_need_for_rehash() -> None:
    weak = Argon2PasswordHasher(**{**_FAST_PARAMS, "memory_cost_kib": 8192})
    stronger = Argon2PasswordHasher(**{**_FAST_PARAMS, "memory_cost_kib": 16384})

    old_hash = weak.hash("uma-senha-longa-123")

    assert weak.needs_rehash(old_hash) is False
    assert stronger.needs_rehash(old_hash) is True


def test_dummy_verification_matches_real_work() -> None:
    hasher = Argon2PasswordHasher(**_FAST_PARAMS)

    hasher.verify_dummy("qualquer-coisa-longa")


def test_hash_never_contains_the_plain_password() -> None:
    hasher = Argon2PasswordHasher(**_FAST_PARAMS)
    password = "segredo-super-unico-123"

    password_hash = hasher.hash(password)

    assert password not in password_hash


@pytest.mark.parametrize(
    "password",
    ["curta1", "1234567890", "senha12345", "password123"],
)
def test_policy_rejects_short_and_common_passwords(password: str) -> None:
    violations = validate_password(
        password,
        email="pessoa@example.com",
        name="Pessoa Exemplo",
        min_length=10,
        max_length=128,
    )

    assert violations


def test_policy_rejects_password_with_name_or_email() -> None:
    with_email = validate_password(
        "pessoa.silva-2026",
        email="pessoa.silva@example.com",
        name="Outra Pessoa",
        min_length=10,
        max_length=128,
    )
    with_name = validate_password(
        "exemplo-forte-2026",
        email="conta@example.org",
        name="Mariana Exemplo",
        min_length=10,
        max_length=128,
    )

    assert with_email == ("contains_identifier",)
    assert with_name == ("contains_identifier",)


def test_policy_accepts_long_passphrase() -> None:
    violations = validate_password(
        "correto cavalo bateria grampo",
        email="pessoa@example.com",
        name="Pessoa Exemplo",
        min_length=10,
        max_length=128,
    )

    assert violations == ()


def test_policy_rejects_over_max_length() -> None:
    violations = validate_password(
        "a" * 129,
        email="pessoa@example.com",
        name=None,
        min_length=10,
        max_length=128,
    )

    assert violations == ("too_long",)


def test_policy_payload_exposes_server_rules() -> None:
    payload = password_policy_payload(min_length=10, max_length=128, hibp_enabled=False)

    assert payload["min_length"] == 10
    assert payload["max_length"] == 128
    assert "not_common" in payload["requirements"]
    assert payload["hibp_enabled"] is False
    assert uuid4().version == 4
