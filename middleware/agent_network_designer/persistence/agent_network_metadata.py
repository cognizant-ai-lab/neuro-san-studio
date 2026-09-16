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

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime
from datetime import timezone
from logging import getLogger
from typing import Any
from typing import ClassVar

from coded_tools.agent_network_editor.and_logger import AndLogger
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_METADATA


class AgentNetworkMetadata:
    """
    Policy for the top-level "metadata" block of a designed agent network.

    The designer is stateless: the client owns the network's metadata block the same
    way it owns the definition and the name, receives it back after every save under
    the sly_data key AGENT_NETWORK_METADATA, and sends it again with the next request.
    The server adds only what it produced itself. This class is the one place that
    says how:

    - merge() builds the block to save from the block the client sent and the sample
      queries generated on this turn.
    - apply_file_timestamps() stamps the provenance dates that only a persisted file
      carries (a temporary network gets its own stamps from neuro-san's storage).
    - stash() records the block of a network the designer loaded from a HOCON file or
      a reservation, so it reaches the client like a block the client had sent.

    The merge is block-level on purpose (issue #1398): any key the client or a person
    added to the block survives a save that did not regenerate it, not only
    sample_queries.
    """

    SAMPLE_QUERIES_KEY: ClassVar[str] = "sample_queries"
    DATE_CREATED_KEY: ClassVar[str] = "date_created"
    DATE_MODIFIED_KEY: ClassVar[str] = "date_modified"
    # Keys neuro-san's reservation storage writers add to a stored spec's metadata. They
    # describe one temporary deployment, so they must never be carried into the next save.
    STORAGE_OWNED_KEYS: ClassVar[frozenset[str]] = frozenset({"reservation", "stored_at"})
    LOGGER: ClassVar[AndLogger] = AndLogger(getLogger("AgentNetworkMetadata"))

    @staticmethod
    def sanitize(candidate: Any) -> dict[str, Any] | None:
        """
        Copy a metadata block, dropping what must not be carried forward.

        :param candidate: The value a client sent, or the value found under "metadata"
                in a parsed network config. Anything that is not a mapping is not a block.
        :return: A deep copy of the block, as a plain dict, without the storage-owned keys,
                without None-valued keys (a None would otherwise be written as null) and
                without the keys a HOCON file cannot hold (see is_storable_key; each one is
                logged), or None when candidate is not a mapping
        """
        # Mapping rather than dict: the assemblers accept any Mapping for the block, so a
        # read-only proxy or another mapping type must not be mistaken for "no block".
        if not isinstance(candidate, Mapping):
            return None
        block: dict[str, Any] = {}
        for key, value in candidate.items():
            if key in AgentNetworkMetadata.STORAGE_OWNED_KEYS or value is None:
                continue
            if not AgentNetworkMetadata.is_storable_key(key):
                AgentNetworkMetadata._warn_unstorable_key(str(key))
                continue
            block[key] = AgentNetworkMetadata._copy_storable(value, key)
        return block

    @staticmethod
    def is_storable_key(key: Any) -> bool:
        """
        Tell whether a metadata key survives the trip through a generated HOCON file.

        pyhocon reads object keys back raw, without decoding JSON escapes, so a key holding a
        double quote, a backslash or a control character (a newline, a tab, ...) comes back
        changed or split into a path, and the block written to the file would no longer match
        the block handed back to the client. A non-string key would come back as a string for
        the same reason. Every other character, dots, spaces, '#', '$', non-ASCII text and the
        Unicode line separator included, reads back as written (verified with pyhocon 0.3.63
        through the assembler and neuro-san's restorer). The rule is applied in both
        persistence modes so that the saved block never depends on the mode.

        :param key: The key to check
        :return: True when the key reads back from a HOCON file exactly as written
        """
        if not isinstance(key, str):
            return False
        for char in key:
            if char in '"\\' or ord(char) < 32:
                return False
        return True

    @staticmethod
    def _copy_storable(value: Any, path: str) -> Any:
        """
        Deep-copy a metadata value, dropping the nested keys a HOCON file cannot hold.

        The block is rendered as one JSON object, so the key rule applies at every depth:
        inside nested objects and inside objects held in lists alike.

        :param value: The value to copy
        :param path: The path of value inside the block, named in the warning for a dropped key
        :return: A copy of value with the unstorable keys removed at every level
        """
        if isinstance(value, Mapping):
            copied: dict[str, Any] = {}
            for key, item in value.items():
                if not AgentNetworkMetadata.is_storable_key(key):
                    AgentNetworkMetadata._warn_unstorable_key(f"{path}.{key}")
                    continue
                copied[key] = AgentNetworkMetadata._copy_storable(item, f"{path}.{key}")
            return copied
        if isinstance(value, list):
            copied_list: list[Any] = []
            for index, item in enumerate(value):
                copied_list.append(AgentNetworkMetadata._copy_storable(item, f"{path}[{index}]"))
            return copied_list
        return deepcopy(value)

    @staticmethod
    def _warn_unstorable_key(path: str) -> None:
        """
        Log that a metadata key was dropped because a HOCON file cannot hold it.

        :param path: The path of the key inside the block
        """
        AgentNetworkMetadata.LOGGER.warning(
            "Dropping metadata key %r: a key holding a double quote, a backslash or a control "
            "character cannot be stored in an agent network file.",
            path,
        )

    @staticmethod
    def sanitize_or_warn(candidate: Any, source: str) -> dict[str, Any]:
        """
        Sanitize a metadata block, warning when a present value is not a block at all.

        Both places a block enters the designer (the client's sly_data and a loaded network
        config) use this so that a value of the wrong shape is ignored the same way and leaves
        the same trace in the log, instead of being dropped silently on one path only.

        :param candidate: The value to sanitize; None means no block was given at all
        :param source: Where the value came from (sly_data key, file path or reservation id),
                named in the warning for a non-mapping value
        :return: The sanitized block, or an empty dict when candidate is None or not a mapping
        """
        block: dict[str, Any] | None = AgentNetworkMetadata.sanitize(candidate)
        if block is None:
            # None is the ordinary "nothing sent" case and deserves no noise; any other
            # non-mapping value is a client or file bug worth a trace.
            if candidate is not None:
                AgentNetworkMetadata.LOGGER.warning(
                    "Ignoring metadata block of type %s (not a dict) from %s.",
                    type(candidate).__name__,
                    source,
                )
            block = {}
        return block

    @staticmethod
    def is_query_list(candidate: Any) -> bool:
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

    @staticmethod
    def merge(client_block: Any, sample_queries: Any) -> dict[str, Any]:
        """
        Build the metadata block to save from what the client sent and what this turn generated.

        The client's block is the base, sanitized: description, tags and any other key are
        written as received. sample_queries is replaced only when this turn actually produced
        a non-empty list of strings, i.e. the query generator ran; otherwise the client's list
        is kept, which is what makes a skip_designer save, or a designer turn that skipped the
        generator, keep the existing queries.

        :param client_block: The metadata block the client sent back under AGENT_NETWORK_METADATA,
                or the block stashed by the load path; None or a non-mapping means none
        :param sample_queries: Sample queries generated on this turn; None or [] means none
        :return: A new dict that aliases neither input, empty when there is nothing to say
        """
        block: dict[str, Any] | None = AgentNetworkMetadata.sanitize(client_block)
        if block is None:
            block = {}
        if AgentNetworkMetadata.is_query_list(sample_queries):
            block[AgentNetworkMetadata.SAMPLE_QUERIES_KEY] = list(sample_queries)
        return block

    @staticmethod
    def apply_file_timestamps(block: dict[str, Any], now: str | None = None) -> None:
        """
        Stamp the provenance dates of a network persisted as a file, in place.

        date_created is set once, on the first save, and kept afterwards; date_modified is
        rewritten on every save. Both are stamped by the server and travel back with the rest
        of the block; date_created is kept as the client returned it, unvalidated, like every
        other client-owned key. Temporary networks get no studio timestamps at all, so callers
        apply this only in file mode.

        :param block: The block returned by merge(), modified in place
        :param now: UTC ISO-8601 timestamp to stamp with; defaults to the current time.
                Injectable so tests are deterministic.
        """
        stamp: str = now if now is not None else AgentNetworkMetadata.utc_now_iso()
        if AgentNetworkMetadata.DATE_CREATED_KEY not in block:
            block[AgentNetworkMetadata.DATE_CREATED_KEY] = stamp
        block[AgentNetworkMetadata.DATE_MODIFIED_KEY] = stamp

    @staticmethod
    def stash(sly_data: dict[str, Any], candidate: Any, source: str) -> None:
        """
        Record the metadata block of a network the designer just loaded, for the persist step
        and for the client.

        Always sets the key once a network loaded: a loaded network without a usable block is
        recorded as an empty dict, so that the block the client sent for a different network
        cannot leak into this one and the client receives the loaded network's true state.

        :param sly_data: The request's sly_data, written under AGENT_NETWORK_METADATA
        :param candidate: The value found under "metadata" in the loaded config, None when
                absent
        :param source: Where the config came from (file path or reservation id), named in
                the warning for a non-dict block
        """
        sly_data[AGENT_NETWORK_METADATA] = AgentNetworkMetadata.sanitize_or_warn(candidate, source)

    @staticmethod
    def utc_now_iso() -> str:
        """
        Produce the timestamp format date_created has always used.

        :return: The current UTC time as an ISO-8601 string
        """
        return datetime.now(tz=timezone.utc).isoformat()
