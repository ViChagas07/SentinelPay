from datetime import date, timedelta

FEBRABAN_BASE_DATE = date(1997, 10, 7)
MIN_DUE_FACTOR = 0
MAX_DUE_FACTOR = 9999


def due_date_from_factor(factor: int) -> date | None:
    if not MIN_DUE_FACTOR <= factor <= MAX_DUE_FACTOR:
        raise ValueError("due date factor must be between 0 and 9999")
    if factor == 0:
        return None
    return FEBRABAN_BASE_DATE + timedelta(days=factor)


def factor_from_due_date(value: date | None) -> int:
    if value is None:
        return 0
    days = (value - FEBRABAN_BASE_DATE).days
    if not MIN_DUE_FACTOR <= days <= MAX_DUE_FACTOR:
        raise ValueError("due date is outside the documented factor range")
    return days
