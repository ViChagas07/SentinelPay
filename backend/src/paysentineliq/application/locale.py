SUPPORTED_LOCALES: tuple[str, ...] = (
    "pt-BR",
    "en",
    "fr",
    "ja",
    "es",
    "de",
    "ar",
    "ko",
    "zh",
)
DEFAULT_LOCALE = "en"


def _normalize_locale(tag: str) -> str | None:
    lowered = tag.strip().lower()
    if not lowered or lowered == "*":
        return None

    primary = lowered.split("-", 1)[0]
    if primary == "pt":
        return "pt-BR"
    if primary in {"en", "fr", "ja", "es", "de", "ar", "ko", "zh"}:
        return primary
    return None


def resolve_locale(header: str | None) -> str:
    if not header:
        return DEFAULT_LOCALE

    candidates: list[tuple[float, int, str]] = []
    for index, part in enumerate(header.split(",")):
        pieces = [piece.strip() for piece in part.split(";") if piece.strip()]
        if not pieces:
            continue

        locale = _normalize_locale(pieces[0])
        if locale is None:
            continue

        quality = 1.0
        for parameter in pieces[1:]:
            name, _, raw_value = parameter.partition("=")
            if name.strip().lower() != "q":
                continue
            try:
                quality = float(raw_value)
            except ValueError:
                quality = 0.0

        if quality <= 0:
            continue

        candidates.append((-quality, index, locale))

    if not candidates:
        return DEFAULT_LOCALE

    candidates.sort()
    return candidates[0][2]
