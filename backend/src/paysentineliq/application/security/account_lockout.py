def lockout_delay_seconds(
    failed_attempts: int,
    *,
    max_attempts: int,
    base_seconds: int,
    max_seconds: int,
) -> int:
    if failed_attempts < max_attempts:
        return 0
    exponent = min(failed_attempts - max_attempts, 16)
    delay: int = base_seconds * (2**exponent)
    return delay if delay < max_seconds else max_seconds
