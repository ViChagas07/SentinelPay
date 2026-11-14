import re
from typing import Annotated

from pydantic import AfterValidator, StringConstraints

MAX_TEXT_LENGTH = 10_000

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def validate_plain_text(value: str) -> str:
    if "<" in value or ">" in value:
        raise ValueError("HTML is not allowed")
    if _CONTROL_CHARS.search(value):
        raise ValueError("control characters are not allowed")
    return value.strip()


PlainText = Annotated[
    str,
    StringConstraints(max_length=MAX_TEXT_LENGTH),
    AfterValidator(validate_plain_text),
]
