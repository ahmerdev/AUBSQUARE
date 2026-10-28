"""Check whether a third-party page really links to us. SSRF-hardened: only public http(s) hosts, pinned DNS, size/time limits."""
import http.client
import ipaddress
import socket
import ssl
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

MAX_BYTES = 1_500_000
TIMEOUT = 8
MAX_REDIRECTS = 3


class UnsafeURL(Exception):
    pass


def _public_ip(host: str) -> str:
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise UnsafeURL("The domain could not be resolved.")
    for fam, _, _, _, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise UnsafeURL("That address is not a public website, so it won't be requested.")
    return infos[0][4][0]


def _fetch(url: str):
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise UnsafeURL("Only http(s) URLs can be checked.")
    port = u.port or (443 if u.scheme == "https" else 80)
    if port not in (80, 443):
        raise UnsafeURL("Only standard web ports are allowed.")
    ip = _public_ip(u.hostname)  # resolve once, then connect to that exact IP (no DNS rebinding)
    sock = socket.create_connection((ip, port), timeout=TIMEOUT)
    if u.scheme == "https":
        conn = http.client.HTTPSConnection(u.hostname, port, timeout=TIMEOUT)
        sock = ssl.create_default_context().wrap_socket(sock, server_hostname=u.hostname)
    else:
        conn = http.client.HTTPConnection(u.hostname, port, timeout=TIMEOUT)
    conn.sock = sock
    path = (u.path or "/") + (f"?{u.query}" if u.query else "")
    conn.request("GET", path, headers={"User-Agent": "AUBSquareLinkChecker/1.0 (+manual backlink verification)", "Accept": "text/html", "Host": u.netloc})
    resp = conn.getresponse()
    body = resp.read(MAX_BYTES)
    return resp.status, resp.getheader("Location"), resp.getheader("Content-Type", ""), body


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._cur = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            a = dict(attrs)
            self._cur = {"href": a.get("href", ""), "rel": (a.get("rel") or "").lower(), "text": ""}
            self.links.append(self._cur)

    def handle_data(self, data):
        if self._cur is not None:
            self._cur["text"] += data

    def handle_endtag(self, tag):
        if tag == "a":
            self._cur = None


def verify_backlink(source_url: str, our_hosts: set[str]) -> dict:
    """Returns {found, link_type, anchor, message}. Never raises for network problems."""
    url = source_url
    try:
        for _ in range(MAX_REDIRECTS + 1):
            status, loc, ctype, body = _fetch(url)
            if status in (301, 302, 303, 307, 308) and loc:
                url = urljoin(url, loc)
                continue
            break
        else:
            return {"found": False, "message": "Too many redirects."}
        if status >= 400:
            return {"found": False, "message": f"The page returned HTTP {status}."}
        if "html" not in ctype.lower():
            return {"found": False, "message": "The URL is not an HTML page."}
        parser = _Links()
        parser.feed(body.decode("utf-8", "replace"))
        for l in parser.links:
            host = (urlparse(urljoin(url, l["href"])).hostname or "").replace("www.", "")
            if host in our_hosts:
                rel = l["rel"]
                lt = "sponsored" if "sponsored" in rel else "ugc" if "ugc" in rel else "nofollow" if "nofollow" in rel else "dofollow"
                return {"found": True, "link_type": lt, "anchor": " ".join(l["text"].split())[:200], "message": "Link found on the page."}
        return {"found": False, "message": "No link to your site was found on that page."}
    except UnsafeURL as exc:
        return {"found": False, "message": str(exc)}
    except Exception as exc:
        return {"found": False, "message": f"Could not check the page ({exc.__class__.__name__})."}
