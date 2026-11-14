import pytest

from paysentineliq.infrastructure.security.destination_cipher import DestinationCipher

pytestmark = pytest.mark.unit


def test_destination_cipher_roundtrip_and_nondeterministic() -> None:
    cipher = DestinationCipher("test-secret")

    first = cipher.encrypt("+5511999999999")
    second = cipher.encrypt("+5511999999999")

    assert first != second
    assert "+5511999999999" not in first
    assert first.startswith("v1:")
    assert cipher.decrypt(first) == "+5511999999999"
    assert cipher.decrypt(second) == "+5511999999999"


def test_destination_cipher_rejects_wrong_key_and_corrupt_token() -> None:
    cipher = DestinationCipher("test-secret")
    other = DestinationCipher("other-secret")
    token = cipher.encrypt("+5511999999999")

    with pytest.raises(ValueError):
        other.decrypt(token)
    with pytest.raises(ValueError):
        cipher.decrypt("v1:not-base64")
    with pytest.raises(ValueError):
        cipher.decrypt("plain-text")


def test_destination_cipher_requires_secret() -> None:
    with pytest.raises(ValueError):
        DestinationCipher("")
