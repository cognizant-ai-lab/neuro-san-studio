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

import logging
import re
import sys
from typing import Any
from urllib.parse import urlsplit

from coded_tools.agent_network_editor.and_logger import AndLogger

# Legal HTTP field-name charset for validating conversation-supplied header
# NAMES: the "token" rule of RFC 9110 §5.6.2
# (https://www.rfc-editor.org/rfc/rfc9110#section-5.6.2). The HTTP stack
# validates outgoing names just like values and raises on the first illegal
# one — failing the whole request, not just the one header — so names
# outside this set are dropped before the fetch (see usable_header_name).
# Matched with fullmatch(); the + quantifier also rejects an empty (blank)
# name.
_HEADER_NAME_RE: re.Pattern[str] = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")

# ExceptionGroup is a builtin from Python 3.11 (the repo minimum is 3.10).
# On 3.10 the conditional's true branch never evaluates, and isinstance
# against the empty tuple is simply always False — those interpreters keep
# the plain str(error) rendering.
_EXCEPTION_GROUP_TYPES: tuple[type[BaseException], ...] = (BaseExceptionGroup,) if sys.version_info >= (3, 11) else ()

# h11's send-time validation embeds the offending raw header material in
# its message ("Illegal header name b'...'" / "Illegal header value
# b'...'") — the one known error shape that carries a header value
# verbatim. redact_values masks this shape by pattern, unconditionally:
# exact-value masking cannot cover the file-configured path, whose header
# values live inside the MCP adapter and are never handed to this module.
# The second group matches one Python str/bytes repr (either quote style,
# escapes included), so masking stops at the repr's closing quote and the
# rest of the message — other group leaves, status text — stays intact.
_VALUE_BEARING_MESSAGE_RE: re.Pattern[str] = re.compile(
    r"(Illegal header (?:name|value) )b?('(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\")"
)

logger = AndLogger(logging.getLogger(__name__))


class McpHeaderHygiene:
    """
    Hygiene for the per-conversation MCP auth headers a chat client supplies
    via sly_data["http_headers"], and for the fetch errors they can cause.

    The headers carry credential material a client controls, so two things
    must hold everywhere they flow: a malformed entry must degrade to that
    one header (or one server), never fail a whole request or conversation,
    and no header VALUE may ever reach a log — not directly, and not echoed
    through an exception message.

    One policy, three call sites: usable_header_names decides which names
    count, and URL classification (GetMcpTool.sly_data_http_header_urls),
    the outgoing fetch (sanitized_headers), and the persisted schema
    (AgentNetworkPersistenceMiddleware) all read it, so a generated network
    never requires a header the fetch would not actually send.
    """

    @staticmethod
    def usable_server_url(url: Any) -> bool:
        """
        Whether a sly_data["http_headers"] key is a well-formed http(s) MCP
        server URL, safe to fetch from, log, and declare.

        An accepted URL becomes an outbound request target and appears
        verbatim in log lines and in persisted sly_data_schema artifacts,
        so shape problems are rejected here, at the single classification
        gate every consumer shares: a non-string; a scheme other than
        http(s); any control character, whitespace, or DEL anywhere in the
        URL (a raw newline would forge log lines); userinfo (user:pass@ —
        credentials do not belong in a URL that gets logged and persisted;
        auth travels in the headers); and a missing host. Non-ASCII is NOT
        rejected: international URLs are supported end to end and carry no
        log-forgery risk.

        Deliberately NOT a destination policy: no private/loopback/
        link-local address blocking. Localhost and private-network MCP
        servers are first-class deployments here (development runs them
        alongside the studio), the generated networks connect to whatever
        server URLs they are configured with at runtime anyway, and WHICH
        servers a conversation may use is the injecting client's trust
        decision (nsflow injects only its vetted connected-server
        records). Resolver-level controls (DNS pinning, redirect policy)
        need to live in the shared MCP client layer, not per coded tool.

        :param url: One key from sly_data["http_headers"].
        :return: True when the URL is well-formed enough to use.
        """
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            return False
        for char in url:
            if ord(char) <= 0x20 or ord(char) == 0x7F:
                return False
        try:
            parsed = urlsplit(url)
            if parsed.username is not None or parsed.password is not None:
                return False
            if not parsed.hostname:
                return False
        except ValueError:
            # urlsplit (or its lazy component properties) rejects some
            # malformed inputs, e.g. an unclosed IPv6 bracket.
            return False
        return True

    @staticmethod
    def usable_header_name(name: Any) -> str | None:
        """
        Validate and normalize one conversation-supplied header name.

        Outer whitespace is stripped (recoverable, the same treatment
        values get). What remains must be a legal HTTP field name (RFC
        9110 token — see _HEADER_NAME_RE): the HTTP stack validates names
        on send exactly like values, so a blank name or one holding a
        colon, space, control, or non-ASCII character would fail the whole
        request rather than just this header.

        :param name: One key from a per-URL header dict.
        :return: The stripped name, or None when the name is not a string
                or not a legal field name.
        """
        if not isinstance(name, str):
            return None
        stripped: str = name.strip()
        if not _HEADER_NAME_RE.fullmatch(stripped):
            return None
        return stripped

    @staticmethod
    def usable_header_names(headers: dict[Any, Any]) -> list[str]:
        """
        Get the header names in a per-URL header dict that supply a usable
        credential: a legal HTTP header name (see usable_header_name)
        whose value is a string that is not blank after stripping.

        Single owner of what counts as a usable client-supplied header —
        see the class docstring for the three call sites that read it.

        :param headers: A per-URL header dict from sly_data["http_headers"].
        :return: The stripped names in first-appearance order, deduped (two
                raw spellings of one name collapse into the first). Names
                only — no header value leaves this function.
        """
        names: dict[str, None] = {}
        for name, value in headers.items():
            usable_name: str | None = McpHeaderHygiene.usable_header_name(name)
            if usable_name is not None and isinstance(value, str) and value.strip():
                names[usable_name] = None
        return list(names)

    @staticmethod
    def sanitized_headers(server: str, headers: dict[str, Any]) -> dict[str, str]:
        """
        Clean a conversation's per-URL header dict before it reaches the
        HTTP stack.

        The HTTP client validates outgoing names AND values and raises on
        the first illegal one — failing the whole listing for this server,
        and, for values, embedding the raw value (most often a token read
        with a trailing newline) in the exception, which would put token
        material on the drop path. So both halves are cleaned here.

        Names: outer whitespace is stripped; what remains must be a legal
        field name (see usable_header_name) or the header is dropped with
        a warning that does NOT echo the name — an arbitrary junk name
        could hold anything, including a misplaced secret. Values: outer
        whitespace is stripped (the common, recoverable case, so a
        newline-tailed token still authenticates); a blank value supplies
        no credential and is skipped silently, matching
        usable_header_names; a value still holding a control character is
        genuinely malformed and dropped, logging the (already validated)
        header name only. Non-string names/values are skipped. A value is
        never logged.

        :param server: The MCP server URL, for the drop warning.
        :param headers: The conversation's per-URL header dict (from
                sly_data["http_headers"][server]).
        :return: The cleaned headers to hand to the adapter; may be empty,
                in which case the fetch runs unauthenticated and a private
                server simply drops out of the listing (attempt-and-drop).
        """
        cleaned: dict[str, str] = {}
        for name, value in headers.items():
            if not isinstance(name, str) or not isinstance(value, str):
                continue
            usable_name: str | None = McpHeaderHygiene.usable_header_name(name)
            if usable_name is None:
                logger.warning("Dropping malformed MCP header for %s (illegal name characters).", server)
                continue
            stripped: str = value.strip()
            if not stripped:
                continue
            if McpHeaderHygiene._has_illegal_value_character(stripped):
                logger.warning(
                    "Dropping malformed MCP header %r for %s (illegal value characters).", usable_name, server
                )
                continue
            cleaned[usable_name] = stripped
        return cleaned

    @staticmethod
    def _has_illegal_value_character(value: str) -> bool:
        """
        Whether a header value holds a character the HTTP stack rejects:
        any control character except horizontal tab, which is the one
        control character legal inside an HTTP field value.

        :param value: A header value, already stripped of outer whitespace.
        :return: True if any character would fail send-time validation.
        """
        for char in value:
            if (ord(char) < 0x20 and char != "\t") or ord(char) == 0x7F:
                return True
        return False

    @staticmethod
    def error_summary(error: BaseException) -> str:
        """
        Render a fetch failure as the end error message an operator acts on.

        The MCP streamable-http client surfaces failures as an anyio
        ExceptionGroup whose own str() is just "unhandled errors in a
        TaskGroup (1 sub-exception)" — hiding the actual cause (e.g. a 401
        from a stale or revoked token), which is the one hint that picks
        the right remedy (re-auth in the client vs. a server outage). For a
        group, only the leaf messages are returned ("Type: message; ...");
        the group's own text adds nothing once its leaves are shown. No
        traceback is ever rendered.

        Leaf messages from this stack usually carry only the URL and
        status line, but a header VALIDATION failure (e.g. h11's
        LocalProtocolError) can embed the raw header value, so the caller
        validates the values it sends up front (see sanitized_headers) and
        redacts them from this string before logging (see redact_values) —
        this renderer itself makes no such guarantee.

        :param error: The exception caught by the fetch.
        :return: str(error) for a plain exception; the flattened
                "Type: message; ..." leaves for an ExceptionGroup.
        """
        if not isinstance(error, _EXCEPTION_GROUP_TYPES):
            return str(error)
        leaves: list[str] = []
        stack: list[BaseException] = list(error.exceptions)
        while stack:
            sub: BaseException = stack.pop(0)
            if isinstance(sub, _EXCEPTION_GROUP_TYPES):
                stack.extend(sub.exceptions)
            else:
                leaves.append(f"{type(sub).__name__}: {sub}")
        # A group is constructed with at least one exception, so leaves is
        # only empty if a group nested nothing but empty groups — fall back
        # to str(error) rather than returning an empty message.
        return "; ".join(leaves) if leaves else str(error)

    @staticmethod
    def redact_values(text: str, headers: dict[str, str] | None) -> str:
        """
        Mask header material out of a log-bound string.

        Defense in depth for the drop-path warning, in two layers. First,
        the known value-bearing message shape — h11's "Illegal header
        name/value b'...'" — is masked by pattern, unconditionally: on the
        file-configured path the header values live inside the MCP adapter
        (headers is None here), so a malformed operator-configured token
        would otherwise be echoed verbatim, and exact masking below cannot
        reach it. Second, when the headers ARE known (the sly_data path),
        each value is masked wherever it appears: sanitized_headers already
        blocks the values that make the HTTP stack raise a value-bearing
        error, but no exception renderer should be trusted with token
        material, so each value is masked in the plain, str-repr, and
        bytes-repr forms an error might use — longest first so a shorter
        form cannot leave a fragment behind.

        :param text: The rendered error summary bound for the log.
        :param headers: The header dict handed to this fetch, or None (the
                file-configured path, whose values live in the adapter and
                are operator-controlled, not client-supplied).
        :return: text with the value-bearing message shape and every
                non-empty header value we sent masked.
        """
        text = _VALUE_BEARING_MESSAGE_RE.sub(r"\1***", text)
        if not headers:
            return text
        for value in headers.values():
            if not isinstance(value, str) or not value:
                continue
            try:
                forms: tuple[str, ...] = (repr(value.encode()), repr(value), value)
            except UnicodeEncodeError:
                # A client-controlled value can hold a lone surrogate, which
                # str.encode() rejects. Such a value has no bytes form in the
                # error text either — the HTTP stack could not have rendered
                # one — so masking the str forms is complete, and redaction
                # itself must never raise (it runs inside the fetch's
                # except handler, where an escape would fail the whole
                # gathered listing).
                forms = (repr(value), value)
            for form in forms:
                text = text.replace(form, "***")
        return text
