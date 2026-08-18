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
"""
Unit tests for McpHeaderHygiene: which client-supplied header names count,
how a per-URL header dict is cleaned before it reaches the HTTP stack, how
fetch errors are rendered for the drop-path log, and how header values we
sent are redacted out of it. How GetMcpTool wires these into the fetch
pipeline is covered by test_get_mcp_tool.py.
"""

import sys
from unittest import TestCase

import pytest

pytest.importorskip("coded_tools.agent_network_editor.mcp_header_hygiene")

# The import must stay below importorskip so environments whose dependencies
# predate this module's needs skip cleanly.
# pylint: disable=wrong-import-position
from coded_tools.agent_network_editor.mcp_header_hygiene import McpHeaderHygiene  # noqa: E402

# A server the conversation supplies auth headers for.
CLIENT_URL: str = "https://oauth.example/mcp"


class TestUsableServerUrl(TestCase):
    """The classification gate for conversation-supplied MCP server URLs."""

    def test_well_formed_urls_are_accepted(self):
        """Plain, ported, IPv6-literal, localhost, and non-ASCII URLs all
        pass — including localhost/private hosts, deliberately: local and
        private-network MCP servers are first-class deployments, and WHICH
        servers a conversation may use is the injecting client's trust
        decision, not a shape check's."""
        for url in (
            "https://mcp.example.com/mcp",
            "http://localhost:8000/mcp",
            "https://[::1]:8443/mcp",
            "https://example.com/mçp",
        ):
            self.assertTrue(McpHeaderHygiene.usable_server_url(url), url)

    def test_non_strings_and_other_schemes_are_rejected(self):
        """Only http(s) strings can be MCP server references."""
        for url in (
            None,
            42,
            # bytes, not str — the host is example.com so the CI link
            # checker (lychee, which scans string literals) skips it.
            b"https://example.com/mcp",
            "ftp://host/mcp",
            "/internal_admin_network",
            "file:///etc/passwd",
        ):
            self.assertFalse(McpHeaderHygiene.usable_server_url(url), repr(url))

    def test_control_characters_and_whitespace_are_rejected(self):
        """An accepted URL is written verbatim to log lines; a raw newline
        (or any control char, space, or DEL) would let a client forge log
        entries."""
        for url in (
            "https://example.com/mcp\nFORGED LOG LINE",
            "https://example.com/m cp",
            "https://example.com/\tmcp",
            "https://example.com/mcp\x7f",
        ):
            self.assertFalse(McpHeaderHygiene.usable_server_url(url), repr(url))

    def test_userinfo_and_hostless_urls_are_rejected(self):
        """Credentials do not belong in a URL that gets logged and
        persisted (auth travels in the headers), and a URL with no host —
        including an unparseable IPv6 bracket — is not a server."""
        for url in (
            "https://user:pass@example.com/mcp",
            "https://token@example.com/mcp",
            "http://",
            "http:///mcp",
            "https://[::1",
        ):
            self.assertFalse(McpHeaderHygiene.usable_server_url(url), repr(url))


class TestUsableHeaderNames(TestCase):
    """The single owner of which client-supplied header names count."""

    def test_names_are_stripped_and_deduped_in_first_appearance_order(self):
        """Two raw spellings of one name collapse; order is preserved."""
        headers = {" Authorization ": "Bearer a", "Authorization": "Bearer b", "X-Api-Key": "k"}
        self.assertEqual(McpHeaderHygiene.usable_header_names(headers), ["Authorization", "X-Api-Key"])

    def test_illegal_names_and_credential_less_values_are_excluded(self):
        """Only a legal field name with a non-blank string value counts."""
        headers = {
            "Auth orization": "Bearer x",
            "X-Blank": "   ",
            "X-Non-Str": 123,
            42: "v",
            "X-Good": "v",
        }
        self.assertEqual(McpHeaderHygiene.usable_header_names(headers), ["X-Good"])

    def test_an_empty_dict_reads_as_no_names(self):
        """No headers, no contract."""
        self.assertEqual(McpHeaderHygiene.usable_header_names({}), [])


class TestSanitizedHeaders(TestCase):
    """Boundary cleaning of the per-conversation header dict before it is sent."""

    def test_outer_whitespace_is_stripped(self):
        """A newline-tailed token is trimmed so it still authenticates."""
        cleaned = McpHeaderHygiene.sanitized_headers(CLIENT_URL, {"Authorization": "  Bearer tok\n"})
        self.assertEqual(cleaned, {"Authorization": "Bearer tok"})

    def test_a_clean_value_passes_through_unchanged(self):
        """A well-formed value is returned as-is."""
        cleaned = McpHeaderHygiene.sanitized_headers(CLIENT_URL, {"Authorization": "Bearer tok", "X-Api-Key": "k"})
        self.assertEqual(cleaned, {"Authorization": "Bearer tok", "X-Api-Key": "k"})

    def test_a_mid_value_tab_is_allowed(self):
        """Tab is a legal header-value character; only other controls are illegal."""
        cleaned = McpHeaderHygiene.sanitized_headers(CLIENT_URL, {"X-Api-Key": "a\tb"})
        self.assertEqual(cleaned, {"X-Api-Key": "a\tb"})

    def test_an_embedded_control_char_drops_the_header_and_logs_name_only(self):
        """A value with an embedded control char is dropped; the value never logs."""
        with self.assertLogs(level="WARNING") as captured:
            cleaned = McpHeaderHygiene.sanitized_headers(CLIENT_URL, {"Authorization": "Bearer\nSECRET"})

        self.assertEqual(cleaned, {})
        logged = "\n".join(captured.output)
        self.assertIn("Authorization", logged)
        self.assertNotIn("SECRET", logged)

    def test_non_string_names_and_values_are_skipped(self):
        """Malformed shapes are dropped rather than raising."""
        cleaned = McpHeaderHygiene.sanitized_headers(CLIENT_URL, {"Authorization": 123, 42: "x", "X-Api-Key": "k"})
        self.assertEqual(cleaned, {"X-Api-Key": "k"})

    def test_a_name_with_outer_whitespace_is_stripped(self):
        """Names get the same recoverable-trim treatment as values."""
        cleaned = McpHeaderHygiene.sanitized_headers(CLIENT_URL, {" Authorization ": "Bearer tok"})
        self.assertEqual(cleaned, {"Authorization": "Bearer tok"})

    def test_an_illegal_name_drops_the_header_without_echoing_it(self):
        """A name that is still illegal after the outer-whitespace trim (an
        EMBEDDED control char, space, or colon) would fail the whole request
        at send time, so it is dropped up front — and never echoed, since
        junk in the name slot could be a misplaced secret. Well-formed
        headers still go through."""
        with self.assertLogs(level="WARNING") as captured:
            cleaned = McpHeaderHygiene.sanitized_headers(
                CLIENT_URL, {"X-NAME\rSECRET": "v", "  ": "w", "X-Api-Key": "k"}
            )

        self.assertEqual(cleaned, {"X-Api-Key": "k"})
        logged = "\n".join(captured.output)
        self.assertNotIn("SECRET", logged)
        self.assertIn(CLIENT_URL, logged)

    def test_a_blank_value_is_skipped_silently(self):
        """A blank value supplies no credential: not sent, and not worth a
        warning — mirroring how usable_header_names classifies it."""
        with self.assertNoLogs(level="WARNING"):
            cleaned = McpHeaderHygiene.sanitized_headers(CLIENT_URL, {"Authorization": "  \n", "X-Api-Key": "k"})
        self.assertEqual(cleaned, {"X-Api-Key": "k"})


class TestErrorSummary(TestCase):
    """Rendering a fetch failure as the end message an operator acts on."""

    def test_a_plain_exception_renders_as_its_message(self):
        """No group, no rewriting: str(error) is already the end message."""
        self.assertEqual(McpHeaderHygiene.error_summary(ValueError("401 Unauthorized")), "401 Unauthorized")

    def test_group_leaves_replace_the_group_text(self):
        """Only the buried causes are rendered — anyio's own 'unhandled
        errors in a TaskGroup (N sub-exceptions)' adds nothing once its
        leaves are shown, and the leaves (e.g. a 401) are what pick the
        remedy."""
        if sys.version_info < (3, 11):
            self.skipTest("ExceptionGroup is a 3.11+ builtin")

        nested = ExceptionGroup(
            "unhandled errors in a TaskGroup",
            [ExceptionGroup("inner", [ValueError("401 Unauthorized for url 'https://auth.example'")]), KeyError("k")],
        )
        summary = McpHeaderHygiene.error_summary(nested)
        self.assertIn("ValueError: 401 Unauthorized", summary)
        self.assertIn("KeyError", summary)
        self.assertNotIn("TaskGroup", summary)
        self.assertNotIn("sub-exception", summary)


class TestRedactValues(TestCase):
    """The drop-path log backstop that masks any header value we sent."""

    def test_masks_plain_str_repr_and_bytes_repr_forms(self):
        """A value must not survive in any form an exception renderer might use."""
        value = "Bearer FAKE-SECRET-xyz\n"
        text = f"raw={value} str={value!r} bytes={value.encode()!r}"
        redacted = McpHeaderHygiene.redact_values(text, {"Authorization": value})
        self.assertNotIn("FAKE-SECRET-xyz", redacted)
        self.assertIn("***", redacted)

    def test_h11_messages_are_masked_even_without_header_values(self):
        """File-configured headers live inside the MCP adapter (headers is
        None on that path), so their values cannot be exact-masked — the one
        known value-bearing message shape is masked by pattern instead,
        while the rest of the message survives for diagnosis."""
        text = "ValueError: Illegal header value b'Bearer FILE-SECRET\\n'; KeyError: 'k'"
        redacted = McpHeaderHygiene.redact_values(text, None)
        self.assertNotIn("FILE-SECRET", redacted)
        self.assertIn("Illegal header value ***", redacted)
        self.assertIn("KeyError: 'k'", redacted)

    def test_an_illegal_name_message_is_masked_too(self):
        """h11 renders an offending header NAME the same way, and junk in
        the name slot could be a misplaced secret."""
        redacted = McpHeaderHygiene.redact_values("Illegal header name b'NAME-SECRET\\rx'", None)
        self.assertNotIn("NAME-SECRET", redacted)
        self.assertIn("***", redacted)

    def test_a_value_that_cannot_utf8_encode_still_redacts_without_raising(self):
        """A client-controlled value can hold a lone surrogate, which
        str.encode() rejects. Redaction runs inside the fetch's except
        handler — raising there would fail the whole gathered listing — so
        it must skip the impossible bytes form and still mask the str
        forms."""
        value = "Bearer FAKE-SECRET-\ud800"
        text = f"raw={value} str={value!r}"
        redacted = McpHeaderHygiene.redact_values(text, {"Authorization": value})
        self.assertNotIn("FAKE-SECRET", redacted)
        self.assertIn("***", redacted)

    def test_none_headers_pass_through(self):
        """The file-configured path (headers=None) leaves the text untouched."""
        self.assertEqual(McpHeaderHygiene.redact_values("401 Unauthorized", None), "401 Unauthorized")

    def test_empty_values_are_ignored(self):
        """An empty header value must not blank-mask unrelated text."""
        self.assertEqual(McpHeaderHygiene.redact_values("some text", {"X": ""}), "some text")
