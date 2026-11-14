import pytest

from paysentineliq.application.locale import DEFAULT_LOCALE, resolve_locale


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, "en"),
        ("", "en"),
        ("pt-BR", "pt-BR"),
        ("pt", "pt-BR"),
        ("pt-BR,pt;q=0.9,en;q=0.8", "pt-BR"),
        ("fr;q=0.5,ja;q=0.9", "ja"),
        ("de;q=0,fr;q=0.1", "fr"),
        ("zh-CN,zh;q=0.9", "zh"),
        ("zh-TW", "zh"),
        ("es-419", "es"),
        ("it,en;q=0.5", "en"),
        ("*", "en"),
        ("PT-br", "pt-BR"),
        ("fr;q=invalid", "en"),
        ("ko;q=0.8,ar;q=0.7", "ko"),
    ],
)
def test_resolve_locale(header: str | None, expected: str) -> None:
    assert resolve_locale(header) == expected


def test_default_locale_is_english() -> None:
    assert DEFAULT_LOCALE == "en"
