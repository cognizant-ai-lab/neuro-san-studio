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

"""Unit tests for AgentNetworkMetadataBlock, a designed network's "metadata" block as it is saved (#1398)."""

import logging
from collections import OrderedDict
from copy import deepcopy
from typing import Any
from unittest import TestCase

from middleware.agent_network_designer.persistence.agent_network_metadata_block import AgentNetworkMetadataBlock

# Fixed timestamps a block the client sends back already carries; construction and merge_sample_queries()
# must neither drop nor rewrite them, and stamp_file_dates() may rewrite only date_modified.
OLD_CREATED_STAMP: str = "2020-01-02T03:04:05+00:00"
OLD_MODIFIED_STAMP: str = "2021-06-07T08:09:10+00:00"
# What the persistence middleware reads from its clock on a file-mode save and hands to stamp_file_dates();
# two distinct values, so a second save is distinguishable from the first.
NOW_STAMP: str = "2026-09-16T10:11:12+00:00"
LATER_STAMP: str = "2026-09-16T10:20:30+00:00"

# The name of the stdlib logger AgentNetworkMetadataBlock.LOGGER wraps, as declared in the source.
LOGGER_NAME: str = "AgentNetworkMetadataBlock"

# Where the candidate block "came from" in these tests; every warning about a dropped entry must name it.
SOURCE: str = "sly_data['agent_network_metadata']"


class TestAgentNetworkMetadataBlock(TestCase):  # pylint: disable=too-many-public-methods
    """
    Unit tests for AgentNetworkMetadataBlock.

    Covers the four things a block does for one request: sanitizing on construction (storage-owned
    and None-valued keys stripped, entries a HOCON file cannot hold as written dropped with a warning
    naming their path and source, everything deep-copied), merge_sample_queries() (the freshly
    generated queries as the only overlay, filtered the same way, the block kept whole otherwise),
    stamp_file_dates() (date_created set once and kept, date_modified set on every call, from a value
    the caller reads off the clock) and as_dict() (a deep copy on every call). The class constants are
    pinned as well.
    """

    @staticmethod
    def _client_block() -> dict[str, Any]:
        """
        Build a fresh copy of a representative metadata block a client sends back.

        A new dict is returned on every call so that tests never share mutable state and
        aliasing assertions compare against an untouched snapshot.

        :return: A metadata block carrying both dates, sample_queries and user-added keys
        """
        return {
            "description": "a network",
            "date_created": OLD_CREATED_STAMP,
            "date_modified": OLD_MODIFIED_STAMP,
            "sample_queries": ["old query"],
            "tags": ["finance", "demo"],
            "owner": "someone",
        }

    @staticmethod
    def _messages(records: list[logging.LogRecord]) -> list[str]:
        """
        Render captured log records as their formatted messages, in emission order.

        :param records: The records an assertLogs() context captured
        :return: One formatted message per record
        """
        messages: list[str] = []
        for record in records:
            messages.append(record.getMessage())
        return messages

    def _assert_drop_warning(self, message: str, path: str, reason: str) -> None:
        """
        Check that one warning about a dropped entry names the entry's path, the source and the reason.

        :param message: The formatted warning message
        :param path: The expected path of the dropped entry inside the block, before repr()
        :param reason: The expected *_REASON constant
        """
        self.assertIn(repr(path), message)
        self.assertIn(SOURCE, message)
        self.assertIn(reason, message)

    # ------------------------------------------------------------ construction

    def test_init_deep_copies_nested_values(self) -> None:
        """
        The block holds a deep copy: as_dict() shares no container with the candidate, and mutating
        the result at every level leaves the candidate untouched.
        """
        candidate: dict[str, Any] = {"tags": ["a"], "nested": {"k": [1]}, "count": 3, "flag": True}
        snapshot: dict[str, Any] = deepcopy(candidate)

        block: AgentNetworkMetadataBlock = AgentNetworkMetadataBlock(candidate, SOURCE)
        result: dict[str, Any] = block.as_dict()

        self.assertEqual(result, snapshot)
        self.assertIsNot(result, candidate)
        self.assertIsNot(result["tags"], candidate["tags"])
        self.assertIsNot(result["nested"], candidate["nested"])
        self.assertIsNot(result["nested"]["k"], candidate["nested"]["k"])
        # Mutate every level of the result; the candidate must not observe any of it.
        result["tags"].append("b")
        result["nested"]["k"].append(2)
        result["added"] = True
        self.assertEqual(candidate, snapshot)

    def test_init_strips_storage_owned_and_none_keys_keeping_order(self) -> None:
        """
        Top-level "reservation", "stored_at" and None-valued keys are dropped silently, the surviving keys
        keep their input order, a storage-owned key nested below the top level is left alone, and the
        candidate itself is not modified.
        """
        candidate: dict[str, Any] = {
            "description": "first",
            "reservation": {"id": "r-1"},
            "sample_queries": ["q"],
            "stored_at": "2026-01-01T00:00:00+00:00",
            "tags": ["t"],
            "owner": None,
            "date_created": OLD_CREATED_STAMP,
            # The storage writers only ever add their keys at the top level, so this one is a user's.
            "nested": {"stored_at": "kept"},
        }

        with self.assertNoLogs(LOGGER_NAME, level="WARNING"):
            result: dict[str, Any] = AgentNetworkMetadataBlock(candidate, SOURCE).as_dict()

        self.assertEqual(
            result,
            {
                "description": "first",
                "sample_queries": ["q"],
                "tags": ["t"],
                "date_created": OLD_CREATED_STAMP,
                "nested": {"stored_at": "kept"},
            },
        )
        # Dict equality ignores order, so check the order of the surviving keys explicitly.
        self.assertEqual(list(result.keys()), ["description", "sample_queries", "tags", "date_created", "nested"])
        # The candidate itself is not modified by the stripping.
        self.assertIn("reservation", candidate)
        self.assertIn("stored_at", candidate)
        self.assertIn("owner", candidate)

    def test_init_drops_none_valued_keys_at_every_depth_but_keeps_null_list_items(self) -> None:
        """
        A None-valued key is dropped inside a nested object and inside an object held in a list, as at the
        top level, without a warning; a None item inside a list stays, since pyhocon reads a null item back
        as None.
        """
        candidate: dict[str, Any] = {
            "owner": {"team": "platform", "lead": None},
            "notes": [{"ok": True, "gone": None}, None, "plain"],
        }
        expected: dict[str, Any] = {"owner": {"team": "platform"}, "notes": [{"ok": True}, None, "plain"]}

        with self.assertNoLogs(LOGGER_NAME, level="WARNING"):
            result: dict[str, Any] = AgentNetworkMetadataBlock(candidate, SOURCE).as_dict()

        self.assertEqual(result, expected)

    def test_init_drops_unstorable_keys_at_every_level_and_warns(self) -> None:
        """
        A key a HOCON file cannot hold is dropped at the top level, inside a nested object and inside an
        object held in a list; every sibling is kept, the candidate is untouched, and one WARNING names
        each dropped key by its path, the source and the key reason.
        """
        candidate: dict[str, Any] = {
            "description": "A demo",
            'we"ird': "top",
            "owner": {"team": "platform", "back\\slash": 1},
            "notes": [{"ok": True, "a\nb": 2}, "plain"],
        }
        snapshot: dict[str, Any] = deepcopy(candidate)
        expected: dict[str, Any] = {
            "description": "A demo",
            "owner": {"team": "platform"},
            "notes": [{"ok": True}, "plain"],
        }

        with self.assertLogs(LOGGER_NAME, level="WARNING") as captured:
            result: dict[str, Any] = AgentNetworkMetadataBlock(candidate, SOURCE).as_dict()

        self.assertEqual(result, expected)
        self.assertEqual(candidate, snapshot)
        messages: list[str] = self._messages(captured.records)
        self.assertEqual(len(messages), 3)
        self._assert_drop_warning(messages[0], 'we"ird', AgentNetworkMetadataBlock.UNSTORABLE_KEY_REASON)
        self._assert_drop_warning(messages[1], "owner.back\\slash", AgentNetworkMetadataBlock.UNSTORABLE_KEY_REASON)
        self._assert_drop_warning(messages[2], "notes[0].a\nb", AgentNetworkMetadataBlock.UNSTORABLE_KEY_REASON)

    def test_init_drops_unstorable_strings_and_empty_list_items_and_warns(self) -> None:
        """
        A string value holding a control character pyhocon does not decode is dropped, as a key's value and
        as a list item; an empty string inside a list is dropped while an empty string as a value is kept;
        and one WARNING names each dropped entry by its path, the source and the matching reason.
        """
        candidate: dict[str, Any] = {
            "description": "",
            "beep": "a\x07b",
            "tags": ["", "ok", "form\x0cfeed", "tab\tfine"],
            "owner": {"note": "bell\x07"},
        }
        expected: dict[str, Any] = {"description": "", "tags": ["ok", "tab\tfine"], "owner": {}}

        with self.assertLogs(LOGGER_NAME, level="WARNING") as captured:
            result: dict[str, Any] = AgentNetworkMetadataBlock(candidate, SOURCE).as_dict()

        self.assertEqual(result, expected)
        messages: list[str] = self._messages(captured.records)
        self.assertEqual(len(messages), 4)
        self._assert_drop_warning(messages[0], "beep", AgentNetworkMetadataBlock.UNSTORABLE_VALUE_REASON)
        self._assert_drop_warning(messages[1], "tags[0]", AgentNetworkMetadataBlock.EMPTY_LIST_ITEM_REASON)
        self._assert_drop_warning(messages[2], "tags[2]", AgentNetworkMetadataBlock.UNSTORABLE_VALUE_REASON)
        self._assert_drop_warning(messages[3], "owner.note", AgentNetworkMetadataBlock.UNSTORABLE_VALUE_REASON)

    def test_init_keeps_keys_and_values_pyhocon_reads_back_verbatim(self) -> None:
        """
        Keys with dots, spaces, '#', '${', '//', non-ASCII text or U+2028 and values with a tab, a newline, a
        carriage return, quotes, backslashes, DEL or U+2028 all survive construction without a warning.
        """
        candidate: dict[str, Any] = {
            "dot.key": "tab\there",
            "space key": "line\nbreak",
            "hash#key": "cr\rx",
            "dollar${x}": 'quote"back\\slash',
            "slashes//key": "del\x7fx",
            "café": "sep\u2028arated",
            "sep\u2028arated": "plain",
        }
        snapshot: dict[str, Any] = deepcopy(candidate)

        with self.assertNoLogs(LOGGER_NAME, level="WARNING"):
            result: dict[str, Any] = AgentNetworkMetadataBlock(candidate, SOURCE).as_dict()

        self.assertEqual(result, snapshot)

    def test_init_accepts_dict_subclasses_and_yields_plain_dicts(self) -> None:
        """
        A dict subclass, such as the OrderedDict pyhocon hands back for a loaded network, is accepted at the
        top level, nested and inside a list, and every one of them comes back as a plain dict.
        """
        candidate: OrderedDict[str, Any] = OrderedDict(
            {
                "owner": OrderedDict({"team": "platform"}),
                "notes": [OrderedDict({"ok": True})],
                "reservation": {"id": "r-1"},
            }
        )

        result: dict[str, Any] = AgentNetworkMetadataBlock(candidate, SOURCE).as_dict()

        self.assertEqual(result, {"owner": {"team": "platform"}, "notes": [{"ok": True}]})
        self.assertIs(type(result), dict)
        self.assertIs(type(result["owner"]), dict)
        self.assertIs(type(result["notes"][0]), dict)

    def test_init_never_mutates_the_candidate(self) -> None:
        """
        A candidate carrying every kind of dropped entry at once (storage-owned, None-valued, unstorable key,
        unstorable value, empty list item) is exactly as it was after construction.
        """
        candidate: dict[str, Any] = {
            "reservation": {"id": "r-1"},
            "owner": None,
            'we"ird': "top",
            "beep": "a\x07b",
            "tags": ["", "ok"],
            "nested": {"lead": None, "back\\slash": 1, "list": [None, ""]},
        }
        snapshot: dict[str, Any] = deepcopy(candidate)

        with self.assertLogs(LOGGER_NAME, level="WARNING"):
            result: dict[str, Any] = AgentNetworkMetadataBlock(candidate, SOURCE).as_dict()

        self.assertEqual(result, {"tags": ["ok"], "nested": {"list": [None]}})
        self.assertEqual(candidate, snapshot)

    def test_init_none_candidate_gives_empty_block_silently(self) -> None:
        """
        None (nothing sent, or no "metadata" in the config) gives an empty block and logs nothing.
        """
        with self.assertNoLogs(LOGGER_NAME, level="WARNING"):
            block: AgentNetworkMetadataBlock = AgentNetworkMetadataBlock(None, SOURCE)

        self.assertEqual(block.as_dict(), {})

    def test_init_non_dict_candidate_gives_empty_block_and_warns_once(self) -> None:
        """
        A str or a list candidate gives an empty block and exactly one WARNING on the block's logger naming
        the candidate's type and the source.
        """
        cases: list[tuple[Any, str]] = [("a string", "str"), (["a", "list"], "list")]
        for candidate, type_name in cases:
            with self.subTest(candidate=candidate):
                with self.assertLogs(LOGGER_NAME, level="WARNING") as captured:
                    block: AgentNetworkMetadataBlock = AgentNetworkMetadataBlock(candidate, SOURCE)

                self.assertEqual(block.as_dict(), {})
                self.assertEqual(len(captured.records), 1)
                record: logging.LogRecord = captured.records[0]
                self.assertEqual(record.levelno, logging.WARNING)
                self.assertEqual(record.name, LOGGER_NAME)
                message: str = record.getMessage()
                self.assertIn(type_name, message)
                self.assertIn(SOURCE, message)

    # ---------------------------------------------------- merge_sample_queries

    def test_merge_sample_queries_replaces_only_sample_queries(self) -> None:
        """
        A non-empty list of str replaces sample_queries and touches no other key: both dates and every
        user-added key stay as they were.
        """
        expected: dict[str, Any] = self._client_block()
        expected["sample_queries"] = ["new one", "new two"]
        block: AgentNetworkMetadataBlock = AgentNetworkMetadataBlock(self._client_block(), SOURCE)

        with self.assertNoLogs(LOGGER_NAME, level="WARNING"):
            result: dict[str, Any] = block.merge_sample_queries(["new one", "new two"]).as_dict()

        self.assertEqual(result, expected)
        self.assertEqual(result["date_created"], OLD_CREATED_STAMP)
        self.assertEqual(result["date_modified"], OLD_MODIFIED_STAMP)

    def test_merge_sample_queries_on_empty_block_adds_the_key(self) -> None:
        """
        On an empty block the generated queries become the whole block: nothing else is invented.
        """
        block: AgentNetworkMetadataBlock = AgentNetworkMetadataBlock(None, SOURCE)

        result: dict[str, Any] = block.merge_sample_queries(["new one", "new two"]).as_dict()

        self.assertEqual(result, {"sample_queries": ["new one", "new two"]})

    def test_merge_sample_queries_unusable_values_leave_block_whole(self) -> None:
        """
        [], None, a str, a tuple, a list with a non-str item and a list of None each leave the block whole,
        its own sample_queries included, without a warning.
        """
        candidates: list[Any] = [[], None, "not a list", ("a", "tuple"), ["a", 1], [None]]
        for candidate in candidates:
            with self.subTest(sample_queries=candidate):
                block: AgentNetworkMetadataBlock = AgentNetworkMetadataBlock(self._client_block(), SOURCE)

                with self.assertNoLogs(LOGGER_NAME, level="WARNING"):
                    result: dict[str, Any] = block.merge_sample_queries(candidate).as_dict()

                self.assertEqual(result, self._client_block())
                self.assertEqual(result["sample_queries"], ["old query"])

    def test_merge_sample_queries_filters_generated_queries_and_warns(self) -> None:
        """
        A generated query that is empty or holds a control character pyhocon does not decode is dropped, with
        one WARNING each naming sample_queries[<index>], the source and the matching reason; the rest replace
        the block's list.
        """
        block: AgentNetworkMetadataBlock = AgentNetworkMetadataBlock({"sample_queries": ["Old one?"]}, SOURCE)

        with self.assertLogs(LOGGER_NAME, level="WARNING") as captured:
            result: dict[str, Any] = block.merge_sample_queries(["", "Fine?", "bell\x07"]).as_dict()

        self.assertEqual(result, {"sample_queries": ["Fine?"]})
        messages: list[str] = self._messages(captured.records)
        self.assertEqual(len(messages), 2)
        self._assert_drop_warning(messages[0], "sample_queries[0]", AgentNetworkMetadataBlock.EMPTY_LIST_ITEM_REASON)
        self._assert_drop_warning(messages[1], "sample_queries[2]", AgentNetworkMetadataBlock.UNSTORABLE_VALUE_REASON)

    def test_merge_sample_queries_all_unstorable_keeps_own_list(self) -> None:
        """
        When every generated query is dropped the block keeps its own sample_queries, after one WARNING per
        dropped query.
        """
        block: AgentNetworkMetadataBlock = AgentNetworkMetadataBlock({"sample_queries": ["Old one?"]}, SOURCE)

        with self.assertLogs(LOGGER_NAME, level="WARNING") as captured:
            result: dict[str, Any] = block.merge_sample_queries(["\x07", ""]).as_dict()

        self.assertEqual(result, {"sample_queries": ["Old one?"]})
        self.assertEqual(len(captured.records), 2)

    def test_merge_sample_queries_returns_the_same_instance(self) -> None:
        """
        merge_sample_queries() returns the very block it was called on, for a usable and for an unusable
        argument alike, so that calls chain.
        """
        block: AgentNetworkMetadataBlock = AgentNetworkMetadataBlock(self._client_block(), SOURCE)

        self.assertIs(block.merge_sample_queries(["fresh"]), block)
        self.assertIs(block.merge_sample_queries(None), block)
        self.assertIs(block.merge_sample_queries([]), block)
        # The two unusable calls did not undo the usable one.
        self.assertEqual(block.as_dict()["sample_queries"], ["fresh"])

    def test_merge_sample_queries_does_not_alias_the_queries_list(self) -> None:
        """
        The block holds its own copy of the generated queries: the list handed out is not the one passed in,
        and mutating the passed-in list afterwards does not reach the block.
        """
        queries: list[str] = ["fresh"]
        block: AgentNetworkMetadataBlock = AgentNetworkMetadataBlock(None, SOURCE)

        result: dict[str, Any] = block.merge_sample_queries(queries).as_dict()

        self.assertIsNot(result["sample_queries"], queries)
        queries.append("mutated")
        self.assertEqual(block.as_dict(), {"sample_queries": ["fresh"]})
        self.assertEqual(queries, ["fresh", "mutated"])

    # --------------------------------------------------------- stamp_file_dates

    def test_stamp_file_dates_on_empty_block_sets_both_dates_to_now(self) -> None:
        """
        On an empty block stamp_file_dates(now) sets date_created and date_modified, both to now so a first
        save shows one instant, and in that order so the file lists the creation date first.
        """
        block: AgentNetworkMetadataBlock = AgentNetworkMetadataBlock(None, SOURCE)

        result: dict[str, Any] = block.stamp_file_dates(NOW_STAMP).as_dict()

        self.assertEqual(result, {"date_created": NOW_STAMP, "date_modified": NOW_STAMP})
        # Dict equality ignores order, so check the key order explicitly.
        self.assertEqual(list(result.keys()), ["date_created", "date_modified"])

    def test_stamp_file_dates_keeps_date_created_and_rewrites_date_modified(self) -> None:
        """
        A block that already carries date_created keeps it while date_modified is rewritten to now; every
        other key (description, tags, sample_queries, owner and a nested dict) is exactly as it was, and
        no key moves, since both date keys already had a place.
        """
        candidate: dict[str, Any] = self._client_block()
        candidate["nested"] = {"k": [1], "inner": {"x": "y"}}
        expected: dict[str, Any] = deepcopy(candidate)
        expected["date_modified"] = NOW_STAMP
        block: AgentNetworkMetadataBlock = AgentNetworkMetadataBlock(candidate, SOURCE)

        result: dict[str, Any] = block.stamp_file_dates(NOW_STAMP).as_dict()

        self.assertEqual(result, expected)
        self.assertEqual(result["date_created"], OLD_CREATED_STAMP)
        self.assertEqual(result["date_modified"], NOW_STAMP)
        # The previous modification stamp must really have been replaced, not merely kept.
        self.assertNotEqual(result["date_modified"], OLD_MODIFIED_STAMP)
        self.assertEqual(list(result.keys()), list(expected.keys()))

    def test_stamp_file_dates_returns_the_same_instance_and_chains(self) -> None:
        """
        stamp_file_dates() returns the very block it was called on, so that
        merge_sample_queries(...).stamp_file_dates(now).as_dict() chains and the dict holds the generated
        queries and both stamps alongside what the block already had.
        """
        block: AgentNetworkMetadataBlock = AgentNetworkMetadataBlock({"description": "a network"}, SOURCE)

        self.assertIs(block.stamp_file_dates(NOW_STAMP), block)

        chained: AgentNetworkMetadataBlock = AgentNetworkMetadataBlock({"description": "a network"}, SOURCE)
        result: dict[str, Any] = chained.merge_sample_queries(["fresh"]).stamp_file_dates(NOW_STAMP).as_dict()

        self.assertEqual(
            result,
            {
                "description": "a network",
                "sample_queries": ["fresh"],
                "date_created": NOW_STAMP,
                "date_modified": NOW_STAMP,
            },
        )

    def test_stamp_file_dates_logs_nothing(self) -> None:
        """
        Stamping is not a sanitizing step: neither a first stamp on an empty block nor a re-stamp of a block
        that already carries both dates logs anything on the block's logger, at any level.
        """
        # Built outside the context so that only the stamping itself is under observation.
        empty: AgentNetworkMetadataBlock = AgentNetworkMetadataBlock(None, SOURCE)
        full: AgentNetworkMetadataBlock = AgentNetworkMetadataBlock(self._client_block(), SOURCE)

        with self.assertNoLogs(LOGGER_NAME, level="DEBUG"):
            empty.stamp_file_dates(NOW_STAMP)
            full.stamp_file_dates(NOW_STAMP)

    def test_stamp_file_dates_twice_keeps_first_created_and_takes_second_modified(self) -> None:
        """
        Stamping twice with different values, as two saves of one file do, keeps the first date_created and
        takes the second date_modified.
        """
        block: AgentNetworkMetadataBlock = AgentNetworkMetadataBlock(None, SOURCE)

        result: dict[str, Any] = block.stamp_file_dates(NOW_STAMP).stamp_file_dates(LATER_STAMP).as_dict()

        self.assertEqual(result, {"date_created": NOW_STAMP, "date_modified": LATER_STAMP})

    # ------------------------------------------------------------------ as_dict

    def test_as_dict_returns_deep_copies_each_call(self) -> None:
        """
        Two as_dict() calls give equal objects that are distinct at every level: the top-level dict, a nested
        dict, a list and a list inside the nested dict.
        """
        block: AgentNetworkMetadataBlock = AgentNetworkMetadataBlock(
            {"tags": ["a"], "nested": {"k": [1], "inner": {"x": 1}}}, SOURCE
        )

        first: dict[str, Any] = block.as_dict()
        second: dict[str, Any] = block.as_dict()

        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        self.assertIsNot(first["tags"], second["tags"])
        self.assertIsNot(first["nested"], second["nested"])
        self.assertIsNot(first["nested"]["k"], second["nested"]["k"])
        self.assertIsNot(first["nested"]["inner"], second["nested"]["inner"])

    def test_as_dict_result_mutation_does_not_change_later_calls(self) -> None:
        """
        Mutating an as_dict() result at every level leaves the block, and therefore the next as_dict(), as it was.
        """
        expected: dict[str, Any] = {"tags": ["a"], "nested": {"k": [1]}}
        block: AgentNetworkMetadataBlock = AgentNetworkMetadataBlock(deepcopy(expected), SOURCE)

        first: dict[str, Any] = block.as_dict()
        first["tags"].append("b")
        first["nested"]["k"].append(2)
        first["nested"]["added"] = True
        first["added"] = True
        del first["tags"][0]

        self.assertEqual(block.as_dict(), expected)

    def test_as_dict_empty_block_gives_empty_dict(self) -> None:
        """
        A block built from None, from {} or from a dict whose every key was stripped silently hands out {}.
        """
        candidates: list[Any] = [None, {}, {"reservation": "r", "stored_at": "s", "gone": None}]
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                with self.assertNoLogs(LOGGER_NAME, level="WARNING"):
                    result: dict[str, Any] = AgentNetworkMetadataBlock(candidate, SOURCE).as_dict()

                self.assertEqual(result, {})

    # -------------------------------------------------------------- constants

    def test_key_constants(self) -> None:
        """
        SAMPLE_QUERIES_KEY, DATE_CREATED_KEY and DATE_MODIFIED_KEY name the keys the assemblers and UIs read.
        """
        self.assertEqual(AgentNetworkMetadataBlock.SAMPLE_QUERIES_KEY, "sample_queries")
        self.assertEqual(AgentNetworkMetadataBlock.DATE_CREATED_KEY, "date_created")
        self.assertEqual(AgentNetworkMetadataBlock.DATE_MODIFIED_KEY, "date_modified")

    def test_storage_owned_keys(self) -> None:
        """
        STORAGE_OWNED_KEYS is the frozenset of the two keys neuro-san's reservation storage writers add.
        """
        self.assertIsInstance(AgentNetworkMetadataBlock.STORAGE_OWNED_KEYS, frozenset)
        self.assertEqual(AgentNetworkMetadataBlock.STORAGE_OWNED_KEYS, frozenset({"reservation", "stored_at"}))

    def test_reason_constants_are_distinct_non_empty_strings(self) -> None:
        """
        The three *_REASON constants are non-empty and pairwise distinct, so a warning always tells which
        rule dropped an entry.
        """
        reasons: list[str] = [
            AgentNetworkMetadataBlock.UNSTORABLE_KEY_REASON,
            AgentNetworkMetadataBlock.UNSTORABLE_VALUE_REASON,
            AgentNetworkMetadataBlock.EMPTY_LIST_ITEM_REASON,
        ]
        for reason in reasons:
            with self.subTest(reason=reason):
                self.assertIsInstance(reason, str)
                self.assertTrue(reason)
        self.assertEqual(len(set(reasons)), 3)
