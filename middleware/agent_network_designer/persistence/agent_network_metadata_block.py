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

from copy import deepcopy
from logging import getLogger
from typing import Any
from typing import ClassVar
from typing import Self

from coded_tools.agent_network_editor.and_logger import AndLogger
from middleware.agent_network_designer.persistence.hocon_storability_util import HoconStorabilityUtil


class AgentNetworkMetadataBlock:
    """
    The top-level "metadata" block of a designed agent network, as it is about to be saved.

    An instance is short-lived and belongs to one request. It is built from whatever the caller
    holds, sanitized on construction so that it only ever contains what a HOCON file reads back
    as written, takes the sample queries generated on the turn and, for a network saved to a
    file, the studio's timestamps, and hands the result out as a plain dict for the assemblers
    and for sly_data. The designer is stateless, so the block travels with the client like the
    definition and the name do: the persistence middleware takes it from sly_data under
    AGENT_NETWORK_METADATA and returns the saved block there (issue #1398), and #1423 sets it
    from a network loaded from a file or a reservation.

    Sanitizing means, at every depth: the keys neuro-san's reservation storage owns
    (reservation, stored_at) go, None-valued keys go (they would be written as null), and so
    does every entry HoconStorabilityUtil says pyhocon would read back changed, plus empty
    strings inside lists, which pyhocon drops. The first two go silently, because they are
    expected rather than data lost: the storage keys sit on every block read back from a
    reservation, and a null value carries nothing a file could keep. The others are data the
    file cannot hold as sent, so each of those drops is logged with the path of the entry and
    the source the block came from.

    The merge is block-level on purpose (issue #1398): any key the client or a person added to
    the block survives a save that did not regenerate it, not only sample_queries.
    """

    SAMPLE_QUERIES_KEY: ClassVar[str] = "sample_queries"
    DATE_CREATED_KEY: ClassVar[str] = "date_created"
    DATE_MODIFIED_KEY: ClassVar[str] = "date_modified"
    # Keys neuro-san's reservation storage writers add to a stored spec's metadata. They
    # describe one temporary deployment, so they must never be carried into the next save.
    STORAGE_OWNED_KEYS: ClassVar[frozenset[str]] = frozenset({"reservation", "stored_at"})
    LOGGER: ClassVar[AndLogger] = AndLogger(getLogger("AgentNetworkMetadataBlock"))
    # Reasons named in the warning for a dropped entry; see _copy_storable.
    UNSTORABLE_KEY_REASON: ClassVar[str] = "a key holding a double quote, a backslash or a control character"
    UNSTORABLE_VALUE_REASON: ClassVar[str] = (
        "a value holding a control character other than tab, newline or carriage return"
    )
    EMPTY_LIST_ITEM_REASON: ClassVar[str] = "an empty string inside a list"

    def __init__(self, candidate: Any, source: str) -> None:
        """
        Build the block from what a caller holds, sanitizing it on the way in.

        :param candidate: The block to carry forward, or None when there is none. A value that
                is not a dict is not a block: it is ignored with a warning naming the source.
        :param source: Where candidate came from, such as the name of the network being saved,
                named in every warning about a dropped entry
        """
        self._source: str = source
        self._block: dict[str, Any] = {}
        if isinstance(candidate, dict):
            top_level: dict[Any, Any] = {}
            for key, value in candidate.items():
                # The storage writers add their keys at the top level of a stored spec only.
                if key in self.STORAGE_OWNED_KEYS:
                    continue
                top_level[key] = value
            self._block = self._copy_storable(top_level, "")
        elif candidate is not None:
            # None is the ordinary "nothing sent" case and deserves no noise; any other
            # non-dict value is a client or file bug worth a trace.
            self.LOGGER.warning(
                "Ignoring metadata block of type %s (not a dict) from %s.", type(candidate).__name__, source
            )

    def merge_sample_queries(self, sample_queries: Any) -> Self:
        """
        Overlay the sample queries generated on this turn, if any.

        sample_queries is replaced only when this turn actually produced a non-empty list of
        strings, i.e. the query generator ran; otherwise the block's own list is kept, which is
        what makes a skip_designer save, or a designer turn that skipped the generator, keep the
        existing queries. Generated queries go through the same round-trip filter as the rest of
        the block; when nothing storable is left the block's own list is kept too.

        :param sample_queries: Sample queries generated on this turn; None or [] means none
        :return: This block, so a caller can chain as_dict()
        """
        if not self._is_query_list(sample_queries):
            return self
        storable_queries: list[Any] = self._copy_storable(list(sample_queries), self.SAMPLE_QUERIES_KEY)
        if storable_queries:
            self._block[self.SAMPLE_QUERIES_KEY] = storable_queries
        return self

    def stamp_file_dates(self, now: str) -> Self:
        """
        Stamp the studio's timestamps for a network saved to a file.

        date_created is set on the first save and kept afterwards; date_modified is set on every
        save. Both take the same value, so a first save shows one instant. A temporary network
        gets no studio timestamps (neuro-san's reservation storage adds its own stored_at), so
        the caller stamps in file mode only.

        :param now: The current time as an ISO-8601 UTC string; the caller reads the clock so a
                test can pin it
        :return: This block, so a caller can chain as_dict()
        """
        self._block.setdefault(self.DATE_CREATED_KEY, now)
        self._block[self.DATE_MODIFIED_KEY] = now
        return self

    def as_dict(self) -> dict[str, Any]:
        """
        Hand the block out for an assembler or for sly_data.

        :return: A deep copy of the block, so that a caller's later changes never reach this
                instance and this instance never changes what a caller already holds; empty
                when there is nothing to say
        """
        return deepcopy(self._block)

    @staticmethod
    def _is_query_list(candidate: Any) -> bool:
        """
        Tell whether a value is a usable list of sample queries.

        :param candidate: The value to check
        :return: True when candidate is a non-empty list whose items are all strings, the
                only shape SetSampleQueries produces and the UIs read
        """
        if not isinstance(candidate, list) or not candidate:
            return False
        for item in candidate:
            if not isinstance(item, str):
                return False
        return True

    def _copy_storable(self, value: Any, path: str) -> Any:
        """
        Deep-copy a value, dropping what a HOCON file cannot hold as written.

        The block is rendered as one JSON object, so the rules apply at every depth: None-valued
        keys go silently (they would be written as null), keys and string values pyhocon cannot
        read back go with a warning (see HoconStorabilityUtil), and so do empty strings inside
        lists, which pyhocon drops when reading. What is left reads back exactly as written, so
        the block returned to the client is the block the file holds. A None inside a list
        stays: pyhocon reads a null list item back as None.

        :param value: The value to copy
        :param path: The path of value inside the block ("" for the block itself), used in the
                warning for a dropped entry
        :return: A copy of value with the unstorable entries removed at every level
        """
        if isinstance(value, dict):
            copied: dict[str, Any] = {}
            for key, item in value.items():
                item_path: str = f"{path}.{key}" if path else str(key)
                if item is None:
                    continue
                if not HoconStorabilityUtil.is_storable_key(key):
                    self._warn_dropped(item_path, self.UNSTORABLE_KEY_REASON)
                    continue
                if isinstance(item, str) and not HoconStorabilityUtil.is_storable_string(item):
                    self._warn_dropped(item_path, self.UNSTORABLE_VALUE_REASON)
                    continue
                copied[key] = self._copy_storable(item, item_path)
            return copied
        if isinstance(value, list):
            copied_list: list[Any] = []
            for index, item in enumerate(value):
                item_path = f"{path}[{index}]"
                if isinstance(item, str) and item == "":
                    self._warn_dropped(item_path, self.EMPTY_LIST_ITEM_REASON)
                    continue
                if isinstance(item, str) and not HoconStorabilityUtil.is_storable_string(item):
                    self._warn_dropped(item_path, self.UNSTORABLE_VALUE_REASON)
                    continue
                copied_list.append(self._copy_storable(item, item_path))
            return copied_list
        return deepcopy(value)

    def _warn_dropped(self, path: str, reason: str) -> None:
        """
        Log that an entry was dropped because a HOCON file cannot hold it as written.

        :param path: The path of the entry inside the block
        :param reason: What the entry is, one of the *_REASON constants
        """
        self.LOGGER.warning(
            "Dropping metadata entry %r from %s: %s cannot be stored in an agent network file as written.",
            path,
            self._source,
            reason,
        )
