import re
import unicodedata

_COMMON_PASSWORDS: frozenset[str] = frozenset(
    {
        "1234567890",
        "123456789",
        "12345678",
        "1234567",
        "123456",
        "12345",
        "qwerty123",
        "qwertyuiop",
        "qwertyui",
        "qwerty",
        "password",
        "password1",
        "password123",
        "senha123",
        "senha1234",
        "senha12345",
        "senhaforte",
        "senhasegura",
        "admin123",
        "admin1234",
        "administrador",
        "welcome123",
        "iloveyou",
        "letmein",
        "monkey123",
        "dragon123",
        "abc123456",
        "abcd1234",
        "a1b2c3d4",
        "1q2w3e4r",
        "1qaz2wsx",
        "zaq12wsx",
        "asdfghjkl",
        "asdf1234",
        "brasil123",
        "brasil2024",
        "brasil2025",
        "brasil2026",
        "familia123",
        "felicidade",
        "meuamor123",
        "deus12345",
        "jesus123",
        "corinthians",
        "flamengo",
        "palmeiras",
        "saopaulo",
        "vasco123",
        "gremio123",
        "internacional",
        "mudar123",
        "trocar123",
        "acesso123",
        "conta1234",
        "usuario123",
        "usuario1234",
        "teste12345",
        "teste1234",
        "teste123",
        "temporary",
        "temporaria",
        "changeme",
        "mudar@123",
        "p@ssw0rd",
        "p@ssword",
        "passw0rd",
        "iloveyou1",
        "sunshine1",
        "princess1",
        "football1",
        "baseball1",
        "superman1",
        "batman123",
        "starwars1",
        "whatever1",
        "trustno1",
        "master123",
        "shadow123",
        "michael123",
        "jennifer1",
        "computer1",
    }
)

_IDENTIFIER_SPLIT = re.compile(r"[^a-z0-9]+")


def normalize_identifier(value: str | None) -> list[str]:
    if not value:
        return []
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return [part for part in _IDENTIFIER_SPLIT.split(ascii_value) if len(part) >= 3]


def validate_password(
    password: str,
    *,
    email: str,
    name: str | None,
    min_length: int,
    max_length: int,
) -> tuple[str, ...]:
    violations: list[str] = []

    if len(password) < min_length:
        violations.append("too_short")
    if len(password) > max_length:
        violations.append("too_long")

    normalized = unicodedata.normalize("NFKD", password)
    ascii_password = normalized.encode("ascii", "ignore").decode("ascii").lower()

    if ascii_password in _COMMON_PASSWORDS:
        violations.append("too_common")

    compact = ascii_password.replace(" ", "")
    local_part = email.split("@", 1)[0]
    identifiers = normalize_identifier(local_part) + normalize_identifier(name)
    if any(identifier in compact for identifier in identifiers):
        violations.append("contains_identifier")

    return tuple(violations)


def password_policy_payload(
    *, min_length: int, max_length: int, hibp_enabled: bool
) -> dict[str, object]:
    return {
        "min_length": min_length,
        "max_length": max_length,
        "requirements": ["min_length", "max_length", "not_common", "not_personal"],
        "hibp_enabled": hibp_enabled,
    }
