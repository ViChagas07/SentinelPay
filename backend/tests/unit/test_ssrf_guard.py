import pytest

from paysentineliq.application.errors import SSRFBlockedError
from paysentineliq.infrastructure.security.ssrf import SSRFGuard


async def _public_resolver(host: str, port: int) -> list[str]:
    return ["93.184.216.34"]


async def _private_resolver(host: str, port: int) -> list[str]:
    return ["127.0.0.1"]


async def _mixed_resolver(host: str, port: int) -> list[str]:
    return ["93.184.216.34", "10.0.0.5"]


@pytest.mark.unit
async def test_public_https_url_is_allowed() -> None:
    guard = SSRFGuard(require_https=True, resolver=_public_resolver)

    validated = await guard.validate_url("https://public.example/path")

    assert validated.pinned_ip == "93.184.216.34"
    assert validated.port == 443


@pytest.mark.unit
@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1/",
        "https://10.0.0.1/",
        "https://169.254.169.254/latest/meta-data",
        "http://[::1]/",
        "http://[fe80::1]/",
    ],
)
async def test_private_loopback_link_local_and_metadata_are_blocked(url: str) -> None:
    guard = SSRFGuard(require_https=False)

    with pytest.raises(SSRFBlockedError):
        await guard.validate_url(url)


@pytest.mark.unit
async def test_http_is_blocked_when_https_is_required() -> None:
    guard = SSRFGuard(require_https=True, resolver=_public_resolver)

    with pytest.raises(SSRFBlockedError):
        await guard.validate_url("http://public.example/")


@pytest.mark.unit
async def test_private_resolution_is_blocked() -> None:
    guard = SSRFGuard(require_https=True, resolver=_private_resolver)

    with pytest.raises(SSRFBlockedError):
        await guard.validate_url("https://public.example/")


@pytest.mark.unit
async def test_any_private_ip_in_multi_resolution_is_blocked() -> None:
    guard = SSRFGuard(require_https=True, resolver=_mixed_resolver)

    with pytest.raises(SSRFBlockedError):
        await guard.validate_url("https://public.example/")


@pytest.mark.unit
async def test_credentials_in_url_are_blocked() -> None:
    guard = SSRFGuard(require_https=True, resolver=_public_resolver)

    with pytest.raises(SSRFBlockedError):
        await guard.validate_url("https://user:pass@public.example/")


@pytest.mark.unit
async def test_non_standard_port_is_blocked_for_user_url() -> None:
    guard = SSRFGuard(require_https=True, resolver=_public_resolver)

    with pytest.raises(SSRFBlockedError):
        await guard.validate_url("https://public.example:8443/")


@pytest.mark.unit
async def test_allowlisted_infrastructure_can_use_private_host_and_port() -> None:
    guard = SSRFGuard(
        require_https=False,
        allowed_hosts={"localhost"},
        resolver=_private_resolver,
    )

    validated = await guard.validate_url("http://localhost:1234/v1", allow_internal=True)

    assert validated.host == "localhost"
    assert validated.port == 1234
    assert validated.pinned_ip == "127.0.0.1"


@pytest.mark.unit
async def test_allowlist_does_not_apply_to_user_urls() -> None:
    guard = SSRFGuard(
        require_https=False,
        allowed_hosts={"localhost"},
        resolver=_private_resolver,
    )

    with pytest.raises(SSRFBlockedError):
        await guard.validate_url("http://localhost:1234/v1")


@pytest.mark.unit
async def test_non_http_scheme_is_blocked() -> None:
    guard = SSRFGuard(require_https=False)

    with pytest.raises(SSRFBlockedError):
        await guard.validate_url("file:///etc/passwd")
