# Copyright © 2025-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# END COPYRIGHT

"""URL-level SSRF policy (scheme, length, hostname canonicalization, domain rules) behind SafeFetch."""

import re
from ipaddress import IPv4Address
from ipaddress import IPv6Address
from ipaddress import ip_address
from typing import Any
from urllib.parse import ParseResult
from urllib.parse import urlparse
from urllib.parse import urlunparse

import idna
from aiohttp.helpers import is_ip_address

from neuro_san_studio.coded_tools.utils.global_only_resolver import GlobalOnlyResolver

# Maximum accepted URL length, shared by every tool on this path (WebFetch and
# the RAG loaders) so they all accept the same URLs. 2000 is what browsers and
# CDNs commonly tolerate, and it leaves room for presigned object-store links
# (S3/Azure SAS), which routinely run 300-1000+ characters; anything longer is
# far more likely malformed or hostile than legitimate.
MAX_URL_LENGTH: int = 2000
# Characters permitted in a canonical (post-IDNA, lower-cased) DNS hostname. IP
# literals are validated separately; a genuine hostname containing anything outside
# this set means IDNA could not canonicalize it and it is not a usable DNS name.
HOSTNAME_ALLOWED_CHARS: frozenset[str] = frozenset("abcdefghijklmnopqrstuvwxyz0123456789.-_")
# A URL with an authority ("scheme://...") embedded in free text, such as an error message. Any
# scheme is matched, not only http(s), and the match runs to the next whitespace: a URL may itself
# contain quotes or brackets, so stopping at one would leave its query behind. Whatever quoting or
# punctuation the surrounding text closed the URL with is peeled off again in _redact_match.
# Case-insensitive because validate_url accepts an upper-case scheme and hands the spelling on.
URL_IN_TEXT_PATTERN: re.Pattern[str] = re.compile(r"[a-z][a-z0-9+.-]*://\S+", re.IGNORECASE)
# Characters that surrounding prose may attach to the end of a quoted URL; they are not part of it.
URL_TRAILING_CHARS: frozenset[str] = frozenset(".,;:)]>'\"")


class UrlPolicy:
    """
    URL-level SSRF policy for the coded tools that fetch through SafeFetch (WebFetch, WebpageRag and PdfRag).

    Answers one question, with no network access: is this URL string allowed under
    these domain rules? validate_url checks the scheme, the length (MAX_URL_LENGTH),
    the port, the presence and canonical form of the hostname (IDNA, Unicode dot
    separators, the DNS root-label dot), the caller's allowed_domains / blocked_domains, and
    finally hands the host to validate_hostname_safety, which rejects localhost names
    and IP literals that are not globally routable. Ordinary hostnames are
    deliberately NOT resolved here: their DNS records are validated at connection
    time by GlobalOnlyResolver on the SafeFetch session, which closes the
    DNS-rebinding gap (see that class for why a pre-fetch lookup is not enough).

    SafeFetch exposes validate_url, validate_hostname_safety and validate_domain_list
    as one-line delegations to this class, so the tools keep a single entry point;
    SafeFetch's network methods and redirect follower call this class directly.
    Split out of SafeFetch in #1442.

    Error types (raised as ValueError with the specified message prefix)
        invalid_input    – URL is not a string, empty, malformed, not http/https, has no or an
                            invalid hostname or port, or a domain-list parameter has an invalid type.
        url_too_long     – URL exceeds MAX_URL_LENGTH characters.
        url_not_allowed  – Host is localhost, an unsupported or non-global IP literal, outside
                            allowed_domains, or inside blocked_domains.
    """

    @staticmethod
    def validate_url(url_value: Any, allowed_domains: Any = None, blocked_domains: Any = None) -> str:
        """
        Validate a URL's format, length, and domain rules and return the cleaned URL.

        :param url_value: The candidate URL; must be an http/https string.
        :param allowed_domains: Optional allow-list (str or list[str]); if non-empty,
                                the host must equal or be a subdomain of one entry.
        :param blocked_domains: Optional block-list (str or list[str]); the host must
                                not equal or be a subdomain of any entry.
        :return: The stripped, validated URL.
        :raises ValueError: invalid_input, url_too_long, or url_not_allowed when the
                URL fails any format, length, domain, or hostname-safety check.
        """
        if not isinstance(url_value, str):
            raise ValueError(f"invalid_input: 'url' must be a string, got {url_value!r}.")

        url: str = url_value.strip()
        if not url:
            raise ValueError("invalid_input: No 'url' provided.")

        # urlparse itself raises ValueError on some malformed authorities (e.g. an
        # unmatched IPv6 bracket "https://[::1/"); translate it to invalid_input
        # rather than let the raw ValueError escape the documented contract.
        try:
            parsed: ParseResult = urlparse(url)
        except ValueError as exc:
            raise ValueError(f"invalid_input: URL is malformed: {exc}") from exc

        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"invalid_input: URL must use http or https scheme, got '{parsed.scheme}'.")

        if len(url) > MAX_URL_LENGTH:
            raise ValueError(f"url_too_long: URL exceeds maximum length of {MAX_URL_LENGTH} characters.")

        raw_hostname: str | None = parsed.hostname
        if not raw_hostname:
            raise ValueError("invalid_input: URL must include a hostname.")

        # urlparse defers port validation until parsed.port is accessed, so a
        # non-numeric or out-of-range port would otherwise slip through and fail
        # later inside aiohttp with an untranslated ValueError.
        try:
            _ = parsed.port
        except ValueError as exc:
            raise ValueError(f"invalid_input: URL has an invalid port: {exc}") from exc

        # Canonicalize the host the same way aiohttp/yarl will before connecting, so
        # every domain and safety check runs on the exact form the request targets.
        # parsed.hostname strips the port/credentials; _to_ascii_host applies IDNA
        # (Unicode IDN -> punycode) and maps Unicode dot separators (U+3002 and
        # friends) to ASCII '.'.
        hostname: str = UrlPolicy._to_ascii_host(raw_hostname.lower())
        # Strip the DNS root-label dot only AFTER IDNA encoding: a Unicode trailing
        # dot becomes a strippable ASCII '.' during encoding. Doing this before the
        # domain and hostname-safety checks stops DNS-equivalent spellings
        # ("example.com.", "example.com。", "localhost。") from bypassing the block
        # list or the loopback guard.
        hostname = hostname.rstrip(".")
        # A root-only authority ("http://./", "http://../") has a non-empty
        # parsed.hostname but canonicalizes to an empty string here; reject it as
        # invalid_input rather than let an empty host slip past the checks and reach
        # DNS.
        if not hostname:
            raise ValueError("invalid_input: URL must include a valid hostname.")

        allowed: list[str] = UrlPolicy.validate_domain_list(allowed_domains, "allowed_domains")
        if allowed and not UrlPolicy._hostname_matches_any(hostname, allowed):
            raise ValueError(f"url_not_allowed: Domain '{hostname}' is not in the allowed_domains list.")

        blocked: list[str] = UrlPolicy.validate_domain_list(blocked_domains, "blocked_domains")
        if blocked and UrlPolicy._hostname_matches_any(hostname, blocked):
            raise ValueError(f"url_not_allowed: Domain '{hostname}' is blocked.")

        UrlPolicy.validate_hostname_safety(hostname)

        return url

    @staticmethod
    def _hostname_matches_any(hostname: str, domains: list[str]) -> bool:
        """
        Return whether a hostname matches any domain under a strict boundary.

        A domain entry "example.com" matches the host "example.com" and any
        subdomain "sub.example.com", but not "badexample.com". Matching is
        case-insensitive.

        :param hostname: The host to test, already canonicalized by validate_url
                (lower-cased, IDNA-ASCII, root-label dot stripped).
        :param domains: The domain entries to test against.
        :return: True if the hostname equals or is a subdomain of any entry.
        """
        # Canonicalize each entry the same way the host was (IDNA-ASCII + trailing
        # dot stripped) so both sides compare in the form aiohttp connects to; a
        # Unicode IDN spelling and its punycode entry (or a "example.com." FQDN
        # entry) would otherwise miss and bypass the configured block/allow rule.
        for domain in domains:
            lowered: str = UrlPolicy._to_ascii_host(domain.lower()).rstrip(".")
            if hostname == lowered or hostname.endswith("." + lowered):
                return True
        return False

    @staticmethod
    def _to_ascii_host(host: str) -> str:
        """
        Return the IDNA (punycode) ASCII form of a host for domain-policy matching.

        aiohttp/yarl connect to the IDNA-ASCII form of a Unicode host, and yarl uses
        this same "idna" package, so matching in its UTS#46 form gives exact parity
        with what the request targets. Falls back to the input unchanged when it
        cannot be encoded (IP literals, underscore labels, invalid IDN input), which
        leaves ASCII inputs exactly as the raw comparison saw them and defers those
        cases to the other checks.

        :param host: The already-lower-cased host or domain entry to canonicalize.
        :return: The IDNA-ASCII form, or the input unchanged if it cannot be encoded.
        """
        try:
            return idna.encode(host, uts46=True).decode("ascii")
        except (idna.IDNAError, UnicodeError):
            return host

    @staticmethod
    def validate_hostname_safety(hostname: str) -> None:
        """
        Reject localhost names and IP literals that are not globally routable.

        Non-IP hostnames are intentionally NOT DNS-resolved here: their records are
        validated at connection time by GlobalOnlyResolver on the session's
        TCPConnector, which checks the exact addresses the client connects to and
        therefore prevents DNS rebinding (a pre-fetch check could be answered with a
        safe address and rebound to an internal one before the connection).

        IP literals must be checked up front because aiohttp short-circuits them in
        TCPConnector._resolve_host and never calls the resolver for them. Zoned IPv6
        literals (e.g. "fe80::1%eth0") are parsed by ip_address() on Python >= 3.9 and
        validated like any other literal; strings that ip_address() cannot parse but
        that contain characters illegal in DNS hostnames ('%' or ':') are rejected
        outright, because aiohttp's own literal detection may still treat them as IP
        literals and bypass the resolver. For the same reason, a host that aiohttp's
        is_ip_address() accepts but ipaddress.ip_address() cannot parse (e.g. the
        integer form "2130706433" or shorthand "127.1", which resolve to loopback)
        is rejected rather than deferred to a resolver that will never run for it.

        :param hostname: The already-lower-cased host to check.
        :raises ValueError: url_not_allowed when the host is localhost, an
                unparseable/zoned/shorthand IP literal, or a non-global IP literal;
                invalid_input when a genuine hostname holds characters that are not
                valid in a DNS name (IDNA could not canonicalize it).
        """
        if hostname == "localhost" or hostname.endswith(".localhost"):
            raise ValueError(f"url_not_allowed: Host '{hostname}' targets a loopback address.")

        addr: IPv4Address | IPv6Address
        try:
            addr = ip_address(hostname)
        except ValueError as parse_exc:
            if "%" in hostname or ":" in hostname:
                # Not parseable as an IP address, yet it cannot be a DNS hostname
                # either: '%' and ':' are illegal in hostnames. Treat it as a
                # malformed or zoned IP literal and fail closed — aiohttp may
                # consider such strings IP literals and skip GlobalOnlyResolver,
                # so anything ip_address() cannot vouch for must not pass.
                raise ValueError(
                    f"url_not_allowed: Host '{hostname}' is not a valid hostname or IP address."
                ) from parse_exc
            if is_ip_address(hostname):
                # ip_address() could not parse this, but aiohttp's own literal
                # detection (the exact is_ip_address() check TCPConnector uses to
                # decide whether to skip the resolver) does treat it as an IP
                # literal — e.g. the 32-bit integer form "2130706433" or
                # dotted-shorthand "127.1", both of which the OS resolves to
                # 127.0.0.1. aiohttp will connect to it without ever calling
                # GlobalOnlyResolver, and ip_address() cannot vouch that it is
                # globally routable, so fail closed instead of deferring to a
                # resolver that will never run for it.
                raise ValueError(
                    f"url_not_allowed: Host '{hostname}' is an unsupported IP-literal form."
                ) from parse_exc
            # A genuine (non-IP) hostname. If IDNA could not canonicalize it,
            # _to_ascii_host returned it unchanged, so reject any host still holding
            # characters invalid in a DNS name (e.g. a space or '$'): that is a
            # malformed URL and must surface as invalid_input here rather than fail
            # later inside aiohttp/yarl with an off-contract error. Otherwise
            # GlobalOnlyResolver validates its DNS records at connection time.
            for char in hostname:
                if char not in HOSTNAME_ALLOWED_CHARS:
                    raise ValueError(
                        f"invalid_input: Host '{hostname}' contains characters that are not valid in a hostname."
                    ) from parse_exc
            return

        GlobalOnlyResolver.ensure_global_address(hostname, addr)

    @staticmethod
    def validate_domain_list(value: Any, param_name: str) -> list[str]:
        """
        Coerce and validate a domain-list parameter.

        :param value: The parameter to coerce; accepts None, a single str, or a
                      list[str].
        :param param_name: The parameter's name, used in error messages.
        :return: The domains as a list[str] (empty for None, single-element for a str).
        :raises ValueError: invalid_input when value is neither None, str, nor a
                list of strings.
        """
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if not isinstance(value, list):
            raise ValueError(f"invalid_input: '{param_name}' must be a list of strings, got {value!r}.")
        for item in value:
            if not isinstance(item, str):
                raise ValueError(
                    f"invalid_input: '{param_name}' must be a list of strings, "
                    f"but contains non-string element {item!r}."
                )
        return value

    @staticmethod
    def redact_for_log(url: str) -> str:
        """
        Return a URL reduced to scheme, host and path, for log lines.

        Redirect targets are server-controlled and routinely carry bearer credentials in the
        query string (presigned object-store links, signed CDN URLs) or, rarely, in userinfo.
        A log line that records such a URL verbatim persists the credential for as long as the
        logs live. This keeps what identifies the resource and replaces the query with a fixed
        marker, so a reader can still tell one was present; the fragment and any userinfo are
        dropped.

        :param url: The URL to redact. Usually one that passed validate_url, but a raw redirect
                    Location of any scheme is accepted too; a string urlparse rejects is cut at
                    its first "?" or "#" instead.
        :return: The redacted URL, e.g. "https://files.example.com/report.pdf?[redacted]".
        """
        try:
            parsed: ParseResult = urlparse(url)
            port: int | None = parsed.port
        except ValueError:
            return UrlPolicy._redact_unparseable(url)
        host: str = parsed.hostname or ""
        # urlparse strips the brackets from an IPv6 literal; put them back so the log stays a URL.
        if ":" in host:
            host = f"[{host}]"
        if port is not None:
            host = f"{host}:{port}"
        query: str = "[redacted]" if parsed.query else ""
        return urlunparse((parsed.scheme, host, parsed.path, "", query, ""))

    @staticmethod
    def redact_urls_in_text(text: str) -> str:
        """
        Redact every URL with an authority embedded in free text, for log lines that quote an error message.

        SafeFetch's translated errors interpolate the URL they were given, and for a body fetch
        that is the server-controlled redirect target; a log line that quotes such a message
        would leak a presigned token exactly as logging the URL itself would. Every match is
        replaced by its redact_for_log form.

        :param text: The text to scan, typically str(exception).
        :return: The text with every embedded URL reduced to scheme, host and path.
        """
        return URL_IN_TEXT_PATTERN.sub(UrlPolicy._redact_match, text)

    @staticmethod
    def _redact_match(match: re.Match[str]) -> str:
        """
        Redact one URL found by URL_IN_TEXT_PATTERN, keeping sentence punctuation that followed it.

        :param match: The regex match holding the URL (and possibly a trailing "." or ",").
        :return: The redacted URL followed by whatever punctuation the match swallowed.
        """
        url: str = match.group(0)
        trailing: str = ""
        # The pattern runs to whitespace, so closing quotes, brackets and sentence punctuation
        # that belong to the prose end up inside the match; peel them off, redact, re-append.
        while url and url[-1] in URL_TRAILING_CHARS:
            trailing = url[-1] + trailing
            url = url[:-1]
        return UrlPolicy.redact_for_log(url) + trailing

    @staticmethod
    def _redact_unparseable(url: str) -> str:
        """
        Redact a URL that urlparse rejected, by text, keeping enough of it to diagnose the refusal.

        An unbalanced IPv6 bracket or a non-numeric port makes urlparse raise, yet the value is
        still worth naming in the error. Cut off anything that could be a query or fragment, and
        drop any userinfo from the authority, so the same guarantees hold as on the parsed path.

        :param url: The string urlparse refused.
        :return: The scheme, host (with port text) and path that remain, plus "?[redacted]" when a
                 query or fragment was removed.
        """
        head: str = url.split("?", 1)[0].split("#", 1)[0]
        marker: str = "" if head == url else "?[redacted]"
        # The authority follows "scheme://", or starts right after a protocol-relative "//".
        authority_start: int
        if head.startswith("//"):
            authority_start = 2
        else:
            scheme_end: int = head.find("://")
            if scheme_end == -1:
                return head + marker
            authority_start = scheme_end + 3
        path_start: int = head.find("/", authority_start)
        authority: str = head[authority_start:] if path_start == -1 else head[authority_start:path_start]
        if "@" in authority:
            # Everything up to the last "@" is userinfo; the host follows it.
            authority = authority.rsplit("@", 1)[1]
        rest: str = "" if path_start == -1 else head[path_start:]
        return head[:authority_start] + authority + rest + marker
