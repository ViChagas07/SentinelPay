import pytest
from pydantic import BaseModel, ValidationError

from paysentineliq.interface.api.validators import MAX_TEXT_LENGTH, PlainText

pytestmark = pytest.mark.unit


class Payload(BaseModel):
    text: PlainText


def test_plain_text_is_accepted() -> None:
    payload = Payload(text="  documento sem html  ")

    assert payload.text == "documento sem html"


def test_html_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Payload(text="<script>alert(1)</script>")


def test_control_characters_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Payload(text="texto\x00com controle")


def test_text_over_limit_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Payload(text="a" * (MAX_TEXT_LENGTH + 1))
