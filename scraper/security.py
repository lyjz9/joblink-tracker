"""Network and workbook validation used at public trust boundaries."""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse
from zipfile import BadZipFile, ZipFile

import requests


URL_PATTERN = re.compile(
    r'https?://(?:(?!https?://)[^\s<>"\'\[\]])+',
    flags=re.I,
)
INVISIBLE_URL_CHARACTERS = re.compile(r"[\u200b\u200c\u200d\ufeff]")
TRACKING_QUERY_PARAMETERS = {
    "from",
    "gh_src",
    "ref",
    "refid",
    "source",
    "src",
    "trackingid",
    "trk",
    "utm_campaign",
    "utm_content",
    "utm_id",
    "utm_medium",
    "utm_source",
    "utm_term",
}
BLOCKED_HOST_NAMES = {
    "localhost",
    "metadata",
    "metadata.google.internal",
    "instance-data",
}
REDIRECT_CODES = {301, 302, 303, 307, 308}


def _clean_pasted_url(value: object) -> str:
    raw = re.sub(r"&amp;", "&", str(value or ""), flags=re.I)
    raw = INVISIBLE_URL_CHARACTERS.sub("", raw)
    match = URL_PATTERN.search(raw)
    if match:
        raw = match.group(0)
    return raw.strip().rstrip(".,;:!?)]}\\")


def canonical_url_key(value: object) -> str:
    """Return a stable identity for duplicate detection without changing the saved URL."""
    text = _clean_pasted_url(value)
    try:
        parsed = urlparse(text)
        host = (parsed.hostname or "").casefold().rstrip(".")
        port = parsed.port
    except ValueError:
        return text.rstrip("/").casefold()
    if not host:
        return text.rstrip("/").casefold()

    if host.startswith("www."):
        host = host[4:]
    path = parsed.path.rstrip("/") or "/"

    if host == "linkedin.com" or host.endswith(".linkedin.com"):
        match = re.search(r"/jobs/view/(?:.*-)?(\d{7,})(?:/|$)", path, flags=re.I)
        if match:
            return f"linkedin.com/jobs/view/{match.group(1)}"

    query_pairs = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if key.casefold() not in TRACKING_QUERY_PARAMETERS
        and not key.casefold().startswith("utm_")
    ]
    query_pairs.sort(key=lambda pair: (pair[0].casefold(), pair[1]))

    if (host == "indeed.com" or host.endswith(".indeed.com")) and path.casefold() == "/viewjob":
        job_key = next(
            (item for key, item in query_pairs if key.casefold() == "jk" and item),
            "",
        )
        if job_key:
            return f"indeed.com/viewjob?jk={job_key.casefold()}"

    default_port = 443 if parsed.scheme.casefold() == "https" else 80
    port_text = f":{port}" if port and port != default_port else ""
    query = urlencode(query_pairs, doseq=True)
    return f"{host}{port_text}{path}{'?' + query if query else ''}"


def validate_public_url(value: object) -> tuple[str | None, str | None]:
    """Check a job link before the scraper opens it."""
    text = _clean_pasted_url(value)
    if len(text) > 4096:
        return None, "The job link is too long."

    try:
        parsed = urlparse(text)
        port = parsed.port
    except ValueError:
        return None, "Add a complete job link."

    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None, "The link must start with http:// or https://."
    if parsed.username or parsed.password:
        return None, "Links containing usernames or passwords are not supported."

    host = parsed.hostname.casefold().rstrip(".")
    if (
        host in BLOCKED_HOST_NAMES
        or host.endswith((".localhost", ".local", ".internal"))
    ):
        return None, "Local and private network links are not allowed."

    try:
        ip_literal = ipaddress.ip_address(host)
    except ValueError:
        ip_literal = None
    if ip_literal is not None and not ip_literal.is_global:
        return None, "Local and private network links are not allowed."

    try:
        default_port = 443 if parsed.scheme == "https" else 80
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(host, port or default_port, type=socket.SOCK_STREAM)
        }
    except (OSError, ValueError):
        return None, "The website address could not be found."

    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return None, "The website address could not be verified."
        if not ip.is_global:
            return None, "Local and private network links are not allowed."
    return parsed.geturl(), None


def safe_requests_get(url: str, *, max_redirects: int = 5, **kwargs):
    """GET a URL while validating every redirect target."""
    current, error = validate_public_url(url)
    if error:
        raise requests.InvalidURL(error)

    kwargs.pop("allow_redirects", None)
    for _ in range(max_redirects + 1):
        response = requests.get(current, allow_redirects=False, **kwargs)
        if response.status_code not in REDIRECT_CODES:
            final_url, final_error = validate_public_url(response.url or current)
            if final_error:
                response.close()
                raise requests.InvalidURL(final_error)
            return response

        location = response.headers.get("Location", "")
        response.close()
        if not location:
            raise requests.TooManyRedirects("Redirect response did not include a destination.")
        current, error = validate_public_url(urljoin(current, location))
        if error:
            raise requests.InvalidURL(error)
    raise requests.TooManyRedirects(f"More than {max_redirects} redirects were returned.")


async def install_playwright_network_guard(context) -> None:
    """Abort browser requests to non-public network destinations."""
    decisions: dict[tuple[str, int | None], bool] = {}

    async def guard(route, request):
        parsed = urlparse(request.url)
        if parsed.scheme in {"about", "blob", "data"}:
            await route.continue_()
            return
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            await route.abort("blockedbyclient")
            return

        try:
            key = (parsed.hostname.casefold(), parsed.port)
        except ValueError:
            await route.abort("blockedbyclient")
            return
        allowed = decisions.get(key)
        if allowed is None:
            _normalized, error = await asyncio.to_thread(validate_public_url, request.url)
            allowed = error is None
            decisions[key] = allowed
        if allowed:
            await route.continue_()
        else:
            await route.abort("blockedbyclient")

    await context.route("**/*", guard)


def validate_workbook_upload(
    file_obj,
    filename: str,
    *,
    max_uncompressed_bytes: int,
    max_members: int,
) -> None:
    """Reject malformed, encrypted, or oversized Excel ZIP archives."""
    extension = str(filename or "").lower().rsplit(".", 1)[-1]
    if extension not in {"xlsx", "xlsm"}:
        raise ValueError("Upload an .xlsx or .xlsm Excel workbook.")

    stream = file_obj.stream if hasattr(file_obj, "stream") else file_obj
    try:
        stream.seek(0)
        with ZipFile(stream) as archive:
            members = archive.infolist()
            names = {member.filename for member in members}
            if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:
                raise ValueError("This file is not a readable Excel workbook.")
            if len(members) > max_members:
                raise ValueError("This workbook contains too many internal files.")
            if sum(member.file_size for member in members) > max_uncompressed_bytes:
                raise ValueError("This workbook expands beyond the allowed size.")
            if any(member.flag_bits & 0x1 for member in members):
                raise ValueError("Password-protected workbooks are not supported.")
    except (BadZipFile, OSError) as exc:
        raise ValueError("This file is not a readable Excel workbook.") from exc
    finally:
        stream.seek(0)
