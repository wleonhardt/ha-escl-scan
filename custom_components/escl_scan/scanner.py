"""eSCL client — stub. Phase 2 fills this in."""
from __future__ import annotations

import ssl

import aiohttp


def _ctx(verify: bool, relaxed: bool) -> ssl.SSLContext | bool:
    if not verify and not relaxed:
        return False
    ctx = ssl.create_default_context()
    if not verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    if relaxed:
        ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
    return ctx


class ScannerClient:
    """Minimal eSCL client. Phase 2 expands this with scan job orchestration."""

    def __init__(
        self,
        *,
        host: str,
        port: int = 443,
        use_tls: bool = True,
        user: str = "anonymous",
        password: str = "",
        verify_tls: bool = False,
        relaxed_ciphers: bool = False,
        timeout: float = 30.0,
    ) -> None:
        self._scheme = "https" if use_tls else "http"
        self._base = f"{self._scheme}://{host}:{port}"
        self._auth = aiohttp.BasicAuth(user, password) if password else None
        self._ssl = _ctx(verify_tls, relaxed_ciphers) if use_tls else None
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    @property
    def base_url(self) -> str:
        return self._base

    async def get_scanner_status(self) -> bytes:
        """Probe — returns raw XML body. Caller may parse or just check it
        was a valid response (200 OK with eSCL namespace)."""
        url = f"{self._base}/eSCL/ScannerStatus"
        async with aiohttp.ClientSession(
            timeout=self._timeout, auth=self._auth,
            connector=aiohttp.TCPConnector(ssl=self._ssl),
        ) as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                return await resp.read()
