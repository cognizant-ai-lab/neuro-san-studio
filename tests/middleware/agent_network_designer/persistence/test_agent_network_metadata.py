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

"""Unit tests for AgentNetworkMetadata, the policy behind a designed network's "metadata" block (issue #1398)."""

import logging
import unittest
from copy import deepcopy
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any
from unittest.mock import patch

from coded_tools.agent_network_editor.constants import AGENT_NETWORK_METADATA
from middleware.agent_network_designer.persistence.agent_network_metadata import AgentNetworkMetadata

# Fixed timestamps so that results are deterministic and clearly distinguishable from one
# another: the OLD_* stamps are what a block the client sends back already carries, NOW_STAMP
# is what the code under test stamps on this turn.
OLD_CREATED_STAMP: str = "2020-01-02T03:04:05+00:00"
OLD_MODIFIED_STAMP: str = "2021-06-07T08:09:10+00:00"
NOW_STAMP: str = "2026-09-16T10:11:12+00:00"

# The name of the stdlib logger AgentNetworkMetadata.LOGGER wraps, as declared in the source.
LOGGER_NAME: str = "AgentNetworkMetadata"


class TestAgentNetworkMetadata(unittest.TestCase):  # pylint: disable=too-many-public-methods
    """
    Unit tests for AgentNetworkMetadata.

    Covers the static entry points the persistence and definition middlewares share under the
    stateless design: sanitize() (copy + strip), is_query_list() (shape check), merge() (the
    client's block as the base, freshly generated sample queries as the only overlay, no
    timestamps), apply_file_timestamps() (file-mode provenance dates, in place), stash()
    (recording a loaded block in sly_data) and utc_now_iso() (timestamp format).
    """

    @staticmethod
    def _client_block() -> dict[str, Any]:
        """
        Build a fresh copy of a representative metadata block a client sends back.

        A new dict is returned on every call so that tests never share mutable state and
        aliasing assertions compare against an untouched snapshot.

        :return: A metadata block carrying both server-owned dates, sample_queries and user-added keys
        """
        return {
            "description": "a network",
            "date_created": OLD_CREATED_STAMP,
            "date_modified": OLD_MODIFIED_STAMP,
            "sample_queries": ["old query"],
            "tags": ["finance", "demo"],
            "owner": "someone",
        }

    # ------------------------------------------------------------------ sanitize

    def test_sanitize_deep_copies_nested_values(self) -> None:
        """
        sanitize() returns a deep copy: mutating nested containers of the result leaves the input untouched.
        """
        candidate: dict[str, Any] = {"tags": ["a"], "nested": {"k": 1}}
        snapshot: dict[str, Any] = deepcopy(candidate)

        result: dict[str, Any] | None = AgentNetworkMetadata.sanitize(candidate)

        self.assertIsNotNone(result)
        self.assertIsNot(result, candidate)
        self.assertIsNot(result["tags"], candidate["tags"])
        self.assertIsNot(result["nested"], candidate["nested"])
        # Mutate every level of the result; the input must not observe any of it.
        result["tags"].append("b")
        result["nested"]["k"] = 2
        result["added"] = True
        self.assertEqual(candidate, snapshot)

    def test_sanitize_strips_storage_owned_and_none_keys_keeping_order(self) -> None:
        """
        sanitize() drops "reservation", "stored_at" and None-valued keys and keeps the surviving keys in input order.
        """
        candidate: dict[str, Any] = {
            "description": "first",
            "reservation": {"id": "r-1"},
            "sample_queries": ["q"],
            "stored_at": "2026-01-01T00:00:00+00:00",
            "tags": ["t"],
            "owner": None,
            "date_created": OLD_CREATED_STAMP,
        }

        result: dict[str, Any] | None = AgentNetworkMetadata.sanitize(candidate)

        self.assertEqual(
            result,
            {
                "description": "first",
                "sample_queries": ["q"],
                "tags": ["t"],
                "date_created": OLD_CREATED_STAMP,
            },
        )
        # Dict equality ignores order, so check the order of the surviving keys explicitly.
        self.assertEqual(list(result.keys()), ["description", "sample_queries", "tags", "date_created"])
        # The input itself is not modified by the stripping.
        self.assertIn("reservation", candidate)
        self.assertIn("stored_at", candidate)
        self.assertIn("owner", candidate)

    def test_sanitize_returns_none_for_non_dict(self) -> None:
        """
        sanitize() answers None for anything that is not a dict: a str, a list and None itself.
        """
        candidates: list[Any] = ["a string", ["a", "list"], None]
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                self.assertIsNone(AgentNetworkMetadata.sanitize(candidate))

    # -------------------------------------------------------------- is_query_list

    def test_sanitize_or_warn_returns_block_or_empty_dict(self) -> None:
        """
        sanitize_or_warn() returns the sanitized block for a dict and {} for None, logging nothing either way.
        """
        cases: list[tuple[Any, dict[str, Any]]] = [
            ({"description": "d", "reservation": "r", "empty": None}, {"description": "d"}),
            (None, {}),
        ]
        for candidate, expected in cases:
            with self.subTest(candidate=candidate):
                with self.assertNoLogs(LOGGER_NAME, level="WARNING"):
                    result: dict[str, Any] = AgentNetworkMetadata.sanitize_or_warn(candidate, "source")
                self.assertEqual(result, expected)

    def test_sanitize_or_warn_non_mapping_returns_empty_dict_and_warns(self) -> None:
        """
        sanitize_or_warn() with a list returns {} and logs one WARNING naming the type and the source.
        """
        source: str = "sly_data['agent_network_metadata']"
        with self.assertLogs(LOGGER_NAME, level="WARNING") as captured:
            result: dict[str, Any] = AgentNetworkMetadata.sanitize_or_warn(["not", "a", "block"], source)
        self.assertEqual(result, {})
        self.assertEqual(len(captured.records), 1)
        message: str = captured.records[0].getMessage()
        self.assertIn("list", message)
        self.assertIn(source, message)

    def test_is_storable_key_accepts_ordinary_keys_and_rejects_unstorable_ones(self) -> None:
        """
        is_storable_key() is True for keys pyhocon reads back verbatim (dots, spaces, '#', '${', '//', non-ASCII
        text, U+2028) and False for a double quote, a backslash, a newline, a tab, another control character
        and a non-str key.
        """
        storable: list[str] = [
            "dot.key",
            "space key",
            "hash#key",
            "dollar${x}",
            "slashes//key",
            "caf\u00e9",
            "sep\u2028arated",
        ]
        unstorable: list[Any] = ['we"ird', "back\\slash", "a\nb", "tab\there", "bell\x07x", 7]
        for key in storable:
            with self.subTest(key=key):
                self.assertTrue(AgentNetworkMetadata.is_storable_key(key))
        for key in unstorable:
            with self.subTest(key=key):
                self.assertFalse(AgentNetworkMetadata.is_storable_key(key))

    def test_sanitize_drops_unstorable_keys_at_every_level_and_warns(self) -> None:
        """
        sanitize() drops a key a HOCON file cannot hold at the top level, inside a nested object and inside an
        object held in a list; every sibling is kept, the input is untouched, and one WARNING names each
        dropped key by its path.
        """
        supplied: dict[str, Any] = {
            "description": "A demo",
            'we"ird': "top",
            "owner": {"team": "platform", "back\\slash": 1},
            "notes": [{"ok": True, "a\nb": 2}, "plain"],
        }
        snapshot: dict[str, Any] = deepcopy(supplied)
        expected: dict[str, Any] = {
            "description": "A demo",
            "owner": {"team": "platform"},
            "notes": [{"ok": True}, "plain"],
        }

        with self.assertLogs(LOGGER_NAME, level="WARNING") as captured:
            result: dict[str, Any] | None = AgentNetworkMetadata.sanitize(supplied)

        self.assertEqual(result, expected)
        self.assertEqual(supplied, snapshot)
        messages: list[str] = []
        for record in captured.records:
            messages.append(record.getMessage())
        self.assertEqual(len(messages), 3)
        self.assertIn(repr('we"ird'), messages[0])
        self.assertIn(repr("owner.back\\slash"), messages[1])
        self.assertIn(repr("notes[0].a\nb"), messages[2])

    def test_is_storable_string_allows_tab_newline_return_and_rejects_other_control_characters(self) -> None:
        """
        is_storable_string() is True for text with a tab, a newline, a carriage return, quotes, backslashes,
        non-ASCII text, DEL, U+2028 and for the empty string, and False for any other control character (NUL,
        bell, backspace, form feed, U+001F).
        """
        storable: list[str] = [
            "plain",
            "tab\there",
            "line\nbreak",
            "cr\rx",
            'quote"back\\slash',
            "caf\u00e9",
            "del\x7fx",
            "sep\u2028arated",
            "",
        ]
        unstorable: list[str] = ["nul\x00x", "bell\x07x", "back\x08space", "form\x0cfeed", "unit\x1fsep"]
        for text in storable:
            with self.subTest(text=text):
                self.assertTrue(AgentNetworkMetadata.is_storable_string(text))
        for text in unstorable:
            with self.subTest(text=text):
                self.assertFalse(AgentNetworkMetadata.is_storable_string(text))

    def test_sanitize_drops_none_valued_keys_at_every_depth_but_keeps_null_list_items(self) -> None:
        """
        A None-valued key is dropped inside a nested object and inside an object held in a list, as at the top
        level, without a warning; a None item inside a list stays, since pyhocon reads a null item back as None.
        """
        supplied: dict[str, Any] = {
            "owner": {"team": "platform", "lead": None},
            "notes": [{"ok": True, "gone": None}, None, "plain"],
        }
        expected: dict[str, Any] = {"owner": {"team": "platform"}, "notes": [{"ok": True}, None, "plain"]}

        with self.assertNoLogs(LOGGER_NAME, level="WARNING"):
            result: dict[str, Any] | None = AgentNetworkMetadata.sanitize(supplied)

        self.assertEqual(result, expected)

    def test_sanitize_drops_unstorable_strings_and_empty_list_items_and_warns(self) -> None:
        """
        A string value holding a control character pyhocon does not decode is dropped, as a key's value and as a
        list item; an empty string inside a list is dropped while an empty string as a value is kept; and one
        WARNING names each dropped entry by its path.
        """
        supplied: dict[str, Any] = {
            "description": "",
            "beep": "a\x07b",
            "tags": ["", "ok", "form\x0cfeed", "tab\tfine"],
            "owner": {"note": "bell\x07"},
        }
        expected: dict[str, Any] = {"description": "", "tags": ["ok", "tab\tfine"], "owner": {}}

        with self.assertLogs(LOGGER_NAME, level="WARNING") as captured:
            result: dict[str, Any] | None = AgentNetworkMetadata.sanitize(supplied)

        self.assertEqual(result, expected)
        messages: list[str] = []
        for record in captured.records:
            messages.append(record.getMessage())
        self.assertEqual(len(messages), 4)
        self.assertIn(repr("beep"), messages[0])
        self.assertIn(repr("tags[0]"), messages[1])
        self.assertIn(repr("tags[2]"), messages[2])
        self.assertIn(repr("owner.note"), messages[3])

    def test_is_query_list_true_for_non_empty_str_list(self) -> None:
        """
        is_query_list() accepts a non-empty list whose items are all strings.
        """
        self.assertTrue(AgentNetworkMetadata.is_query_list(["a"]))
        self.assertTrue(AgentNetworkMetadata.is_query_list(["a", "b"]))

    def test_is_query_list_false_for_other_shapes(self) -> None:
        """
        is_query_list() rejects an empty list, None, a bare str, a list with a non-str item and a list of None.
        """
        candidates: list[Any] = [[], None, "a", ["a", 1], [None]]
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                self.assertFalse(AgentNetworkMetadata.is_query_list(candidate))

    # -------------------------------------------------------------------- merge

    def test_merge_client_block_only_keeps_every_key_unchanged(self) -> None:
        """
        merge() with no new queries returns the client's block sanitized but otherwise as-is, both dates included.
        """
        with self.subTest(case="clean block passes through"):
            client: dict[str, Any] = self._client_block()

            result: dict[str, Any] = AgentNetworkMetadata.merge(client, None)

            self.assertEqual(result, self._client_block())
            # The server-owned dates travel with the block: merge() neither drops nor rewrites them.
            self.assertEqual(result["date_created"], OLD_CREATED_STAMP)
            self.assertEqual(result["date_modified"], OLD_MODIFIED_STAMP)
            self.assertIsNot(result, client)
        with self.subTest(case="storage-owned and None keys are stripped"):
            client = {
                "tags": ["t"],
                "reservation": {"id": "r-1"},
                "stored_at": "2026-01-01T00:00:00+00:00",
                "owner": None,
            }

            result = AgentNetworkMetadata.merge(client, None)

            self.assertEqual(result, {"tags": ["t"]})

    def test_merge_without_client_block_returns_empty_dict(self) -> None:
        """
        merge() with no usable client block and no queries returns {}: nothing is invented, no timestamp either.
        """
        candidates: list[Any] = [None, "junk"]
        for candidate in candidates:
            with self.subTest(client_block=candidate):
                self.assertEqual(AgentNetworkMetadata.merge(candidate, None), {})

    def test_merge_str_queries_replace_only_sample_queries(self) -> None:
        """
        merge() overlays sample_queries with a non-empty list of str and touches no other key of the client's block.
        """
        queries: list[str] = ["new one", "new two"]

        with self.subTest(case="client block present"):
            expected: dict[str, Any] = self._client_block()
            expected["sample_queries"] = ["new one", "new two"]

            result: dict[str, Any] = AgentNetworkMetadata.merge(self._client_block(), queries)

            self.assertEqual(result, expected)
        with self.subTest(case="no client block"):
            # Without a client block the queries are the whole block: no dates are stamped here.
            result = AgentNetworkMetadata.merge(None, queries)

            self.assertEqual(result, {"sample_queries": ["new one", "new two"]})

    def test_merge_unusable_queries_keep_client_sample_queries(self) -> None:
        """
        merge() keeps the client's block whole, queries included, for [], None, a non-list and a list with a non-str.
        """
        candidates: list[Any] = [[], None, "not a list", ("a", "tuple"), ["a", 1], [None]]
        for candidate in candidates:
            with self.subTest(sample_queries=candidate):
                result: dict[str, Any] = AgentNetworkMetadata.merge(self._client_block(), candidate)

                self.assertEqual(result, self._client_block())
                self.assertEqual(result["sample_queries"], ["old query"])

    def test_merge_result_does_not_alias_inputs(self) -> None:
        """
        merge() returns a dict sharing no object with the client's block, its nested containers or the queries list.
        """
        client: dict[str, Any] = {"tags": ["client"], "nested": {"k": [1]}, "date_created": OLD_CREATED_STAMP}
        snapshot: dict[str, Any] = deepcopy(client)
        queries: list[str] = ["fresh"]

        result: dict[str, Any] = AgentNetworkMetadata.merge(client, queries)

        self.assertIsNot(result, client)
        self.assertIsNot(result["tags"], client["tags"])
        self.assertIsNot(result["nested"], client["nested"])
        self.assertIsNot(result["nested"]["k"], client["nested"]["k"])
        self.assertIsNot(result["sample_queries"], queries)
        # Mutate the result at every level; neither input may observe it.
        result["tags"].append("mutated")
        result["nested"]["k"].append(2)
        result["sample_queries"].append("mutated")
        result["new_key"] = "x"
        self.assertEqual(client, snapshot)
        self.assertEqual(queries, ["fresh"])

    # ------------------------------------------------------ apply_file_timestamps

    def test_merge_filters_generated_queries_like_the_client_block(self) -> None:
        """
        merge() drops a generated query that is empty or holds a control character pyhocon does not decode,
        with one WARNING each naming sample_queries[<index>], and keeps the client's list when nothing is left.
        """
        client: dict[str, Any] = {"sample_queries": ["Old one?"]}

        with self.assertLogs(LOGGER_NAME, level="WARNING") as captured:
            result: dict[str, Any] = AgentNetworkMetadata.merge(client, ["", "Fine?", "bell\x07"])

        self.assertEqual(result, {"sample_queries": ["Fine?"]})
        self.assertEqual(len(captured.records), 2)
        self.assertIn(repr("sample_queries[0]"), captured.records[0].getMessage())
        self.assertIn(repr("sample_queries[2]"), captured.records[1].getMessage())

        with self.assertLogs(LOGGER_NAME, level="WARNING"):
            kept: dict[str, Any] = AgentNetworkMetadata.merge(client, ["\x07"])

        self.assertEqual(kept, {"sample_queries": ["Old one?"]})

    def test_apply_file_timestamps_on_empty_block_sets_both_dates_to_now(self) -> None:
        """
        apply_file_timestamps() on {} stamps date_created and date_modified with now, in place, and returns None.
        """
        block: dict[str, Any] = {}

        with patch.object(AgentNetworkMetadata, "utc_now_iso", return_value="unexpected") as clock:
            returned: None = AgentNetworkMetadata.apply_file_timestamps(block, now=NOW_STAMP)

        self.assertIsNone(returned)
        self.assertEqual(block, {"date_created": NOW_STAMP, "date_modified": NOW_STAMP})
        # An explicit now must be used as-is; the class clock is not consulted.
        clock.assert_not_called()

    def test_apply_file_timestamps_keeps_date_created_and_rewrites_date_modified(self) -> None:
        """
        apply_file_timestamps() leaves an existing date_created alone and overwrites date_modified with now.
        """
        block: dict[str, Any] = self._client_block()
        expected: dict[str, Any] = self._client_block()
        expected["date_modified"] = NOW_STAMP

        AgentNetworkMetadata.apply_file_timestamps(block, now=NOW_STAMP)

        self.assertEqual(block, expected)
        self.assertEqual(block["date_created"], OLD_CREATED_STAMP)
        self.assertEqual(block["date_modified"], NOW_STAMP)
        # The previous modification stamp must really have been replaced, not merely kept.
        self.assertNotEqual(block["date_modified"], OLD_MODIFIED_STAMP)

    def test_apply_file_timestamps_defaults_to_utc_now_iso(self) -> None:
        """
        apply_file_timestamps() without a now argument asks utc_now_iso() exactly once and stamps with its answer.
        """
        block: dict[str, Any] = {"tags": ["t"]}

        with patch.object(AgentNetworkMetadata, "utc_now_iso", return_value=NOW_STAMP) as clock:
            AgentNetworkMetadata.apply_file_timestamps(block)

        clock.assert_called_once_with()
        self.assertEqual(block, {"tags": ["t"], "date_created": NOW_STAMP, "date_modified": NOW_STAMP})

    # -------------------------------------------------------------------- stash

    def test_stash_sets_sanitized_block(self) -> None:
        """
        stash() records the sanitized block under AGENT_NETWORK_METADATA: storage-owned and None keys stripped.
        """
        sly_data: dict[str, Any] = {}
        candidate: dict[str, Any] = {
            "sample_queries": ["q"],
            "reservation": {"id": "r-1"},
            "stored_at": "2026-01-01T00:00:00+00:00",
            "tags": ["t"],
            "owner": None,
            "date_created": OLD_CREATED_STAMP,
        }

        with self.assertNoLogs(LOGGER_NAME, level="WARNING"):
            AgentNetworkMetadata.stash(sly_data, candidate, "registries/net.hocon")

        self.assertEqual(
            sly_data,
            {AGENT_NETWORK_METADATA: {"sample_queries": ["q"], "tags": ["t"], "date_created": OLD_CREATED_STAMP}},
        )
        # The stash is a copy, not the candidate itself.
        self.assertIsNot(sly_data[AGENT_NETWORK_METADATA], candidate)

    def test_stash_none_candidate_sets_empty_dict(self) -> None:
        """
        stash() with candidate None (config had no "metadata") records {} silently.
        """
        sly_data: dict[str, Any] = {}

        with self.assertNoLogs(LOGGER_NAME, level="WARNING"):
            AgentNetworkMetadata.stash(sly_data, None, "registries/net.hocon")

        self.assertEqual(sly_data, {AGENT_NETWORK_METADATA: {}})

    def test_stash_non_dict_candidate_sets_empty_dict_and_warns(self) -> None:
        """
        stash() with a str candidate records {} and logs one WARNING on "AgentNetworkMetadata" naming the source.
        """
        sly_data: dict[str, Any] = {}
        source: str = "reservation-abc123"

        with self.assertLogs(LOGGER_NAME, level="WARNING") as captured:
            AgentNetworkMetadata.stash(sly_data, "not a block", source)

        self.assertEqual(sly_data, {AGENT_NETWORK_METADATA: {}})
        self.assertEqual(len(captured.records), 1)
        record: logging.LogRecord = captured.records[0]
        self.assertEqual(record.levelno, logging.WARNING)
        self.assertEqual(record.name, LOGGER_NAME)
        message: str = record.getMessage()
        self.assertIn("str", message)
        self.assertIn(source, message)

    def test_stash_leaves_unrelated_sly_data_keys_alone(self) -> None:
        """
        stash() overwrites only AGENT_NETWORK_METADATA; every other sly_data entry keeps its very object.
        """
        definition: dict[str, Any] = {"frontman": {"instructions": "hi"}}
        sly_data: dict[str, Any] = {
            "agent_network_name": "my_network",
            "agent_network_definition": definition,
            # A block the client sent for a previously loaded network must not survive a new load.
            AGENT_NETWORK_METADATA: {"description": "previous network"},
        }

        AgentNetworkMetadata.stash(sly_data, {"tags": ["t"]}, "registries/net.hocon")

        self.assertEqual(
            sly_data,
            {
                "agent_network_name": "my_network",
                "agent_network_definition": {"frontman": {"instructions": "hi"}},
                AGENT_NETWORK_METADATA: {"tags": ["t"]},
            },
        )
        self.assertIs(sly_data["agent_network_definition"], definition)

    # -------------------------------------------------------------- utc_now_iso

    def test_utc_now_iso_is_parseable_utc_timestamp(self) -> None:
        """
        utc_now_iso() returns a str that datetime.fromisoformat() parses to a UTC-aware time close to now.
        """
        before: datetime = datetime.now(tz=timezone.utc)

        value: str = AgentNetworkMetadata.utc_now_iso()

        after: datetime = datetime.now(tz=timezone.utc)
        self.assertIsInstance(value, str)
        parsed: datetime = datetime.fromisoformat(value)
        self.assertEqual(parsed.tzinfo, timezone.utc)
        self.assertEqual(parsed.utcoffset(), timedelta(0))
        # Sanity: the stamp is the current time, not some constant or a naive local time.
        self.assertLessEqual(before, parsed)
        self.assertLessEqual(parsed, after)
