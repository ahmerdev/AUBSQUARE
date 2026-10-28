"""SSRF-safe HTTP fetching (standard library only).

Every outbound request that touches a URL typed by a person (prospect websites, the free audit tool) goes through
`fetch()`. It: allows only http/https on ports 80/443, refuses credentials in URLs, resolves the host itself,
refuses private / loopback / link-local / reserved addresses, pins the connection to the validated IP (so DNS cannot
change between check and use), re-validates every redirect, and caps time, redirects and response size.
"""
import http.client
import ipaddress
import socket
import ssl
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit, urlunsplit

USER_AGENT = "AUBSquareSiteAudit/1.0 (+website audit; contact via the site owner)"
MAX_BYTES = 1_500_000
MAX_REDIRECTS = 4
TIMEOUT = 8
ALLOWED_PORTS = {80, 443}


class UnsafeURL(ValueError):
    """The URL is not allowed to be fetched (message is safe to show to staff / visitors)."""


class HostNotFound(UnsafeURL):
    """The hostname does not resolve. Safe to retry with a close variant (www / non-www)."""


def host_variants(url: str) -> list:
    """Close alternatives worth trying when a hostname does not resolve or refuses the connection: toggle 'www.' and http/https."""
    try:
        p = urlsplit(url)
    except ValueError:
        return []
    host = (p.hostname or "")
    if not host or host.replace(".", "").isdigit():
        return []
    alt = host[4:] if host.startswith("www.") else "www." + host
    port = f":{p.port}" if p.port else ""
    out = [urlunsplit((p.scheme, alt + port, p.path or "/", p.query, ""))]
    if p.scheme == "https":
        out.append(urlunsplit(("http", host + port, p.path or "/", p.query, "")))
    return out


class FetchError(Exception):
    """Network-level failure (message is safe to show)."""


@dataclass
class Fetched:
    status: int
    url: str
    headers: dict
    body: bytes
    elapsed: float
    redirects: list = field(default_factory=list)
    ssl_error: str = ""

    @property
    def text(self) -> str:
        ctype = self.headers.get("content-type", "")
        charset = "utf-8"
        if "charset=" in ctype:
            charset = ctype.split("charset=")[-1].split(";")[0].strip() or "utf-8"
        try:
            return self.body.decode(charset, errors="replace")
        except LookupError:
            return self.body.decode("utf-8", errors="replace")

    @property
    def is_html(self) -> bool:
        c = self.headers.get("content-type", "").lower()
        return (not c) or "html" in c or "text/" in c


def normalize_url(raw: str) -> str:
    """Turn what a person typed ('example.com', 'https://example.com/x') into a clean absolute URL, or ''."""
    raw = (raw or "").strip().split()[0] if (raw or "").strip() else ""
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    try:
        p = urlsplit(raw)
    except ValueError:
        return ""
    if p.scheme not in ("http", "https") or not p.hostname or "." not in p.hostname:
        return ""
    host = p.hostname.lower()
    netloc = host + (f":{p.port}" if p.port else "")
    return urlunsplit((p.scheme, netloc, p.path or "/", p.query, ""))[:500]


def _is_public(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if getattr(addr, "ipv4_mapped", None):
        addr = addr.ipv4_mapped
    return not (addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_multicast or addr.is_reserved or addr.is_unspecified
                or (addr.version == 4 and addr in ipaddress.ip_network("100.64.0.0/10")))


def validate_url(url: str):
    """Returns (scheme, host, port, request_target, [public ips]) or raises UnsafeURL."""
    try:
        p = urlsplit(url)
        port = p.port
    except ValueError:
        raise UnsafeURL("That doesn't look like a valid web address.")
    if p.scheme not in ("http", "https"):
        raise UnsafeURL("Only http:// and https:// addresses can be checked.")
    if p.username or p.password:
        raise UnsafeURL("Addresses with a username or password are not allowed.")
    host = (p.hostname or "").strip(".").lower()
    if not host:
        raise UnsafeURL("That doesn't look like a valid web address.")
    port = port or (443 if p.scheme == "https" else 80)
    if port not in ALLOWED_PORTS:
        raise UnsafeURL("Only the standard web ports (80 and 443) can be checked.")
    try:
        ipaddress.ip_address(host)
        literal = True
    except ValueError:
        literal = False
    if not literal and ("." not in host or host.endswith((".local", ".internal", ".localhost", ".lan", ".home", ".corp"))):
        raise UnsafeURL("Only public websites can be checked.")
    try:
        infos = socket.getaddrinfo(host.encode("idna").decode(), port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError):
        raise HostNotFound(f"We couldn't find “{host}” – the address does not resolve (DNS lookup failed). Check the spelling, or the website may be offline or the domain expired.")
    ips = []
    for info in infos:
        ip = info[4][0]
        if not _is_public(ip):
            raise UnsafeURL("Only public websites can be checked.")
        if ip not in ips:
            ips.append(ip)
    if not ips:
        raise HostNotFound(f"We couldn't find “{host}” – the address does not resolve (DNS lookup failed).")
    target = (p.path or "/") + (("?" + p.query) if p.query else "")
    return p.scheme, host, port, target, ips


class _PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, host, ip, **kw):
        super().__init__(host, **kw)
        self._ip = ip

    def connect(self):
        self.sock = socket.create_connection((self._ip, self.port), self.timeout)


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, ip, verify=True, **kw):
        ctx = ssl.create_default_context()
        if not verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        super().__init__(host, context=ctx, **kw)
        self._ip = ip

    def connect(self):
        sock = socket.create_connection((self._ip, self.port), self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


def _one(url, ips, scheme, host, port, target, timeout, max_bytes, verify=True, method="GET"):
    last = None
    for ip in ips[:3]:
        conn = None
        try:
            conn = _PinnedHTTPS(host, ip, verify=verify, port=port, timeout=timeout) if scheme == "https" else _PinnedHTTP(host, ip, port=port, timeout=timeout)
            conn.request(method, target, headers={"Host": host if port in (80, 443) else f"{host}:{port}", "User-Agent": USER_AGENT,
                                                  "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5", "Accept-Encoding": "identity",
                                                  "Accept-Language": "en", "Connection": "close"})
            resp = conn.getresponse()
            body = b"" if method == "HEAD" else resp.read(max_bytes + 1)[:max_bytes]
            return resp.status, {k.lower(): v for k, v in resp.getheaders()}, body
        except ssl.SSLCertVerificationError:
            raise
        except (OSError, http.client.HTTPException) as exc:
            last = exc
        finally:
            if conn is not None:
                conn.close()
    raise FetchError(f"The website did not answer ({last.__class__.__name__}).")


def fetch(url: str, timeout: int = TIMEOUT, max_bytes: int = MAX_BYTES, method: str = "GET") -> Fetched:
    """GET a public URL safely. Raises UnsafeURL / FetchError. A bad HTTPS certificate is reported in `ssl_error`
    (and the page is fetched without verification only to be able to audit it)."""
    start = time.monotonic()
    redirects, ssl_error = [], ""
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        scheme, host, port, target, ips = validate_url(current)
        verify = True
        try:
            status, headers, body = _one(current, ips, scheme, host, port, target, timeout, max_bytes, True, method)
        except ssl.SSLCertVerificationError as exc:
            ssl_error = f"The security certificate could not be verified ({exc.verify_message or 'invalid certificate'})."
            status, headers, body = _one(current, ips, scheme, host, port, target, timeout, max_bytes, False, method)
        if status in (301, 302, 303, 307, 308) and headers.get("location"):
            nxt = urljoin(current, headers["location"])
            redirects.append(nxt)
            current = nxt
            if time.monotonic() - start > timeout * 2:
                raise FetchError("The website redirected too many times.")
            continue
        return Fetched(status=status, url=current, headers=headers, body=body, elapsed=round(time.monotonic() - start, 2), redirects=redirects, ssl_error=ssl_error)
    raise FetchError("The website redirected too many times.")
