from paysentineliq.domain.payslip.i18n import (
    LABELS,
    MESSAGES,
    SUPPORTED_LOCALES,
    translate,
)
from paysentineliq.domain.payslip.rules import active_rules

LOCALES = ("pt", "es", "en")


def test_supported_locales_are_pt_es_en() -> None:
    assert SUPPORTED_LOCALES == LOCALES


def test_all_rule_messages_have_three_locales() -> None:
    keys = {rule.message_key for rule in active_rules()} | {"payslip.not_verifiable"}

    for key in keys:
        assert key in MESSAGES
        for locale in LOCALES:
            assert MESSAGES[key][locale].strip()


def test_all_labels_have_three_locales() -> None:
    for key, translations in LABELS.items():
        assert translations.keys() >= set(LOCALES), key
        for locale in LOCALES:
            assert translations[locale].strip()


def test_translate_returns_requested_locale_and_falls_back_to_pt() -> None:
    key = "payslip.net_mismatch"

    assert translate(key, "en") == MESSAGES[key]["en"]
    assert translate(key, "es") == MESSAGES[key]["es"]
    assert translate(key, "fr") == MESSAGES[key]["pt"]
