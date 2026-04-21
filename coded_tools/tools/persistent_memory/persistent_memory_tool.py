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
PersistentMemoryTool — a CodedTool exposing persistent long-term memory
as a single dispatcher tool with seven operations
(``create``, ``read``, ``update``, ``append``, ``delete``, ``search``, ``list``).

Memory is scoped per topic, per agent, per agent network. A topic can be
anything the caller wants — a user's name, a project id, a session id —
it just becomes the on-disk filename for that slice of memory::

    namespace = (agent_network_name, agent_name, topic)

Supported operations (each independently enabled/disabled via HOCON):

    create  — store a new memory entry (auto-generates a key if not provided)
    read    — retrieve a specific entry by exact key
    update  — overwrite an existing entry by key
    delete  — remove an entry by key
    search  — keyword or semantic search over the topic's entries
    list    — list all keys in the topic's namespace

The backend is selected by the ``MEMORY_BACKEND`` environment variable (or by
the ``store_config`` block in HOCON). See :py:class:`MemoryStoreFactory`
in ``coded_tools.tools.persistent_memory.memory_store_factory`` for the full
resolution chain.

Example HOCON snippet::

    {
      "name": "PersistentMemoryTool",
      "class": "coded_tools.tools.persistent_memory.persistent_memory_tool.PersistentMemoryTool",
      "tool_config": {
        "agent_network_name": "intranet_agents",
        "agent_name":         "hr_agent",
        "store_config": {
            "backend":   "markdown_file",
            "root_path": "./memory"
        },
        "enabled_operations": ["create", "read", "update", "delete", "search", "list"]
      },
      "function": { ... }
    }
"""

import logging
from typing import Any
from typing import Awaitable
from typing import Callable
from typing import Optional

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.tools.persistent_memory.memory_item import DEFAULT_KEY
from coded_tools.tools.persistent_memory.memory_item import MemoryItem
from coded_tools.tools.persistent_memory.memory_item import MemoryOperation
from coded_tools.tools.persistent_memory.memory_item import Namespace
from coded_tools.tools.persistent_memory.memory_store import MemoryStore
from coded_tools.tools.persistent_memory.memory_store_factory import MemoryStoreFactory
from coded_tools.tools.persistent_memory.path_component import PathComponent

logger = logging.getLogger(__name__)


class PersistentMemoryTool(CodedTool):
    """
    A single dispatcher tool the LLM calls with ``{"operation": "...", ...}``.

    Routing to per-operation handlers is done in :py:meth:`async_invoke`. The
    set of permitted operations is fixed at construction time from HOCON
    ``tool_config.enabled_operations`` — the LLM cannot expand it.
    """

    # ------------------------------------------------------------------
    # Class constants
    # ------------------------------------------------------------------

    # Valid operation names. The canonical set lives on ``MemoryOperation``
    # (see ``memory_item``); this frozenset is just the string values
    # materialised once for O(1) membership tests against raw HOCON / LLM
    # payload strings. ``enabled_operations`` in HOCON selects a subset;
    # unknown names there are logged and ignored.
    ALL_OPERATIONS: frozenset[str] = frozenset(op.value for op in MemoryOperation)

    # Default number of results returned by ``search`` if the LLM does not supply one.
    DEFAULT_SEARCH_LIMIT: int = 5

    # Default topic when the caller supplies none. All callers that omit a
    # topic share this one file — almost always a misconfiguration, so we log
    # a warning when the fallback fires.
    _DEFAULT_TOPIC: str = "default"

    # Default entry key when the LLM omits ``key``. Agents that want clean prose
    # files ("one blob per topic", no section scaffolding) can instruct the LLM
    # to drop the ``key`` arg entirely — everything then lands under this key
    # and the file-system backend writes it without a heading. The string
    # itself is defined once in ``memory_item.DEFAULT_KEY`` — imported here
    # so there is a single source of truth across store, tool, and tests.
    _DEFAULT_KEY: str = DEFAULT_KEY

    def __init__(self, tool_config: Optional[dict[str, Any]] = None) -> None:
        """
        :param tool_config: Dict from the HOCON ``tool_config`` block. Keys:

            agent_network_name   (str, required) — first part of the namespace.
            agent_name           (str, required) — second part of the namespace.
            store_config         (dict, optional) — backend configuration. See
                                 ``memory_store_config.MemoryStoreConfig.resolve``.
            enabled_operations   (list[str], optional) — subset of
                                 ``ALL_OPERATIONS``. Defaults to all seven.
        """
        config: dict[str, Any] = tool_config or {}

        self._agent_network_name: str = config.get("agent_network_name", "unknown_network")
        self._agent_name: str = config.get("agent_name", "unknown_agent")

        # Build the backend. Failures here (bad config, missing optional dep)
        # surface immediately at agent startup rather than on the first LLM call.
        self._store: MemoryStore = MemoryStoreFactory.create(config.get("store_config"))

        # Resolve enabled operations.
        raw_ops: list[str] = list(config.get("enabled_operations") or self.ALL_OPERATIONS)
        cleaned_ops: set[str] = {str(op).strip().lower() for op in raw_ops if op}
        self._enabled_operations: frozenset[str] = frozenset(cleaned_ops) & self.ALL_OPERATIONS

        unknown_ops: set[str] = cleaned_ops - self.ALL_OPERATIONS
        if unknown_ops:
            logger.warning(
                "PersistentMemoryTool (%s/%s): ignoring unknown operations in enabled_operations: %s",
                self._agent_network_name,
                self._agent_name,
                sorted(unknown_ops),
            )

        # Build the dispatch table once per instance rather than per call. The
        # bound-method identities are stable for the life of the tool, so
        # there is no benefit to reconstructing the dict every invocation.
        # Subclasses that want to extend the table should override
        # :py:meth:`_build_handlers`.
        self._handlers: dict[str, Any] = self._build_handlers()

        logger.info(
            "PersistentMemoryTool initialised for %s/%s with operations: %s",
            self._agent_network_name,
            self._agent_name,
            sorted(self._enabled_operations),
        )

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any]:
        """
        Route one LLM call to the right handler.

        Overrides :py:meth:`neuro_san.interfaces.coded_tool.CodedTool.async_invoke`
        — the single entry point neuro-san invokes for every tool call.

        :param args: Arguments provided by the LLM. Expected keys:

            operation   (str, required)    — one of ``ALL_OPERATIONS``.
            topic       (str, optional)    — on-disk filename for this slice
                                              of memory (e.g. a user name,
                                              project id, session id).
            key         (str, conditional) — required for read / update / delete.
            content     (str, conditional) — required for create / update / append.
            query       (str, conditional) — required for search.
            limit       (int, optional)    — for search, defaults to 5.

        :param sly_data: Neuro-SAN private data channel. Reads ``user_id`` as
                         a fallback topic if the LLM did not supply one.
        :return: A dict describing the outcome. Always contains either a
                 ``result`` key on success or an ``error`` key on failure.
        """
        operation: str = str(args.get("operation") or "").strip().lower()

        validation_error: Optional[dict[str, Any]] = self._validate_operation(operation)
        if validation_error is not None:
            return validation_error

        return await self._dispatch_operation(operation, args, sly_data)

    async def async_invoke_internal(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any]:
        """Run an operation bypassing the LLM-facing ``enabled_operations`` whitelist.

        Custom entry point (not a framework hook). Shaped like ``async_invoke``
        on purpose so middleware / plumbing code can reuse the dispatch path
        for trusted internal operations (e.g. auto-compact).

        Intended for middleware-driven internal operations (e.g. auto-compact
        rewriting a file) where the caller is trusted and the whitelist exists
        only to constrain the LLM's schema. Still validates that the operation
        name is known.

        :param args: Same shape as :py:meth:`async_invoke`.
        :param sly_data: Same shape as :py:meth:`async_invoke`.
        :return: Result or error envelope.
        """
        operation: str = str(args.get("operation") or "").strip().lower()
        if not operation:
            return self._error("Missing 'operation'. Must be one of: " + ", ".join(sorted(self.ALL_OPERATIONS)))
        if operation not in self.ALL_OPERATIONS:
            return self._error(
                f"Unknown operation '{operation}'. Must be one of: {', '.join(sorted(self.ALL_OPERATIONS))}"
            )
        return await self._dispatch_operation(operation, args, sly_data)

    async def _dispatch_operation(
        self, operation: str, args: dict[str, Any], sly_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Build the namespace and run the operation's handler with uniform error handling.

        Custom helper (not a framework hook). Shared by :py:meth:`async_invoke`
        and :py:meth:`async_invoke_internal`.

        :param operation: Validated operation name (already in ``ALL_OPERATIONS``).
        :param args: Dispatcher args from the caller.
        :param sly_data: Neuro-SAN private data channel; used to resolve the topic.
        :return: Handler result or an error envelope if the handler raised.
        """
        namespace: Namespace = (
            self._agent_network_name,
            self._agent_name,
            self._resolve_topic(args, sly_data),
        )

        handler = self._handlers[operation]
        try:
            return await handler(args, namespace)

        # Catching the concrete error families the handler stack can raise
        # (filesystem I/O, malformed JSON, bad args, backend misconfig) so
        # that a backend failure returns a readable error to the LLM instead
        # of blowing up the whole agent call. Truly unexpected errors (e.g.
        # KeyboardInterrupt, programmer errors) still propagate. Full
        # traceback is logged via logger.exception.
        except (OSError, ValueError, TypeError, KeyError) as error:
            logger.exception("PersistentMemoryTool: error during '%s'", operation)
            return self._error(f"Unexpected error during '{operation}': {error}")

    def _validate_operation(self, operation: str) -> Optional[dict[str, Any]]:
        """Check that ``operation`` is known AND enabled for this tool.

        Custom helper (not a framework hook). Used only by the LLM-facing
        :py:meth:`async_invoke`; internal callers skip the whitelist check.

        :param operation: Lower-cased operation name from the caller.
        :return: An error envelope if missing / unknown / disabled, else ``None``.
        """
        if not operation:
            return self._error("Missing 'operation'. Must be one of: " + ", ".join(sorted(self.ALL_OPERATIONS)))
        if operation not in self.ALL_OPERATIONS:
            return self._error(
                f"Unknown operation '{operation}'. Must be one of: {', '.join(sorted(self.ALL_OPERATIONS))}"
            )
        if operation not in self._enabled_operations:
            return self._error(
                f"Operation '{operation}' is not enabled for this agent. "
                f"Enabled: {', '.join(sorted(self._enabled_operations))}"
            )
        return None

    def _build_handlers(self) -> dict[str, Any]:
        """Build the dispatch table from operation name to handler coroutine.

        Custom helper (not a framework hook). Called once from ``__init__`` —
        the returned dict is cached on ``self._handlers``. Subclasses that
        want to extend or replace the table should override this method.

        :return: Mapping of operation name → bound ``_handle_*`` coroutine.
        """
        return {
            MemoryOperation.CREATE.value: self._handle_create,
            MemoryOperation.READ.value: self._handle_read,
            MemoryOperation.UPDATE.value: self._handle_update,
            MemoryOperation.APPEND.value: self._handle_append,
            MemoryOperation.DELETE.value: self._handle_delete,
            MemoryOperation.SEARCH.value: self._handle_search,
            MemoryOperation.LIST.value: self._handle_list,
        }

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    async def _handle_create(self, args: dict[str, Any], namespace: Namespace) -> dict[str, Any]:
        """Store a new memory entry. Key is auto-generated if not supplied.

        Uses upsert semantics: if the caller supplies a ``key`` that already
        exists, it is overwritten. This is deliberate — the LLM rarely cares
        about the distinction and a separate "create" vs "update" error would
        only annoy callers.

        :param args: Dispatcher args; requires ``content``.
        :param namespace: Resolved ``(network, agent, topic)`` namespace.
        :return: Result envelope with ``status`` and ``key``.
        """
        content: str = self._str(args.get("content"))
        if not content:
            return self._error("Operation 'create' requires 'content'.")

        key: str = self._str(args.get("key")) or self._DEFAULT_KEY
        await self._store.create(namespace, key, {"content": content})

        logger.debug("PersistentMemoryTool: created key='%s' in %s", key, namespace)
        return {"result": {"status": "created", "key": key}}

    async def _handle_read(self, args: dict[str, Any], namespace: Namespace) -> dict[str, Any]:
        """Retrieve a single entry by key (defaults to the canonical key).

        :param args: Dispatcher args; ``key`` optional.
        :param namespace: Resolved ``(network, agent, topic)`` namespace.
        :return: Result envelope with ``key`` and ``content``, or an error if absent.
        """
        key: str = self._str(args.get("key")) or self._DEFAULT_KEY

        item: Optional[MemoryItem] = await self._store.read(namespace, key)
        if item is None:
            return self._error(f"No memory entry found for key='{key}'.")

        logger.debug("PersistentMemoryTool: read key='%s' from %s", key, namespace)
        return {"result": {"key": key, "content": item.value.get("content", "")}}

    async def _handle_update(self, args: dict[str, Any], namespace: Namespace) -> dict[str, Any]:
        """Overwrite an existing entry.

        Treated as an upsert — we do not error if the key does not already
        exist; the LLM's intent was to store that content under that key
        regardless.

        :param args: Dispatcher args; requires ``content``.
        :param namespace: Resolved ``(network, agent, topic)`` namespace.
        :return: Result envelope with ``status`` and ``key``.
        """
        key: str = self._str(args.get("key")) or self._DEFAULT_KEY
        content: str = self._str(args.get("content"))
        if not content:
            return self._error("Operation 'update' requires 'content'.")

        await self._store.update(namespace, key, {"content": content})

        logger.debug("PersistentMemoryTool: updated key='%s' in %s", key, namespace)
        return {"result": {"status": "updated", "key": key}}

    async def _handle_append(self, args: dict[str, Any], namespace: Namespace) -> dict[str, Any]:
        """Append new content to an existing entry's ``content`` field.

        Unlike ``update`` (which overwrites), ``append`` concatenates the new
        ``content`` onto whatever is already stored at ``key``, separated by a
        blank line. Use this for information that accumulates over time
        (e.g. a user's order history) rather than a single current value.

        If the key does not yet exist, ``append`` behaves like ``create`` —
        the new ``content`` is stored as-is. If ``key`` is omitted, the
        canonical default key is used so callers get a clean single-entry file.

        :param args: Dispatcher args; requires ``content``.
        :param namespace: Resolved ``(network, agent, topic)`` namespace.
        :return: Result envelope with ``status`` and ``key``.
        """
        key: str = self._str(args.get("key")) or self._DEFAULT_KEY
        content: str = self._str(args.get("content"))
        if not content:
            return self._error("Operation 'append' requires 'content'.")

        existing: Optional[MemoryItem] = await self._store.read(namespace, key)
        if existing is None:
            combined: str = content
        else:
            prior: str = str(existing.value.get("content") or "").rstrip()
            combined = f"{prior}\n\n{content}" if prior else content

        await self._store.update(namespace, key, {"content": combined})

        logger.debug("PersistentMemoryTool: appended to key='%s' in %s", key, namespace)
        return {"result": {"status": "appended", "key": key}}

    async def _handle_delete(self, args: dict[str, Any], namespace: Namespace) -> dict[str, Any]:
        """Remove an entry by key (defaults to the canonical key).

        :param args: Dispatcher args; ``key`` optional.
        :param namespace: Resolved ``(network, agent, topic)`` namespace.
        :return: Result envelope with ``status`` and ``key``.
        """
        key: str = self._str(args.get("key")) or self._DEFAULT_KEY

        await self._store.delete(namespace, key)

        logger.debug("PersistentMemoryTool: deleted key='%s' from %s", key, namespace)
        return {"result": {"status": "deleted", "key": key}}

    async def _handle_search(self, args: dict[str, Any], namespace: Namespace) -> dict[str, Any]:
        """Search entries for the current topic.

        Scoring is keyword-based. The tool does not re-rank or filter — it
        trusts the backend's ordering.

        :param args: Dispatcher args; requires ``query``, optional ``limit``.
        :param namespace: Resolved ``(network, agent, topic)`` namespace.
        :return: Result envelope with a ``results`` list of ``{key, content, score?}``.
        """
        query: str = self._str(args.get("query"))
        if not query:
            return self._error("Operation 'search' requires 'query'.")

        limit: int = self._parse_limit(args.get("limit"), self.DEFAULT_SEARCH_LIMIT)
        raw_results: list[MemoryItem] = await self._store.search(namespace, query, limit)

        results: list[dict[str, Any]] = []
        for item in raw_results:
            entry: dict[str, Any] = {
                "key": item.key,
                "content": item.value.get("content", ""),
            }
            if item.score is not None:
                entry["score"] = round(item.score, 4)
            results.append(entry)

        logger.debug(
            "PersistentMemoryTool: search query='%s' returned %d results from %s",
            query,
            len(results),
            namespace,
        )
        return {"result": {"results": results}}

    async def _handle_list(self, args: dict[str, Any], namespace: Namespace) -> dict[str, Any]:
        """List all keys in the topic's namespace.

        :param args: Dispatcher args (unused).
        :param namespace: Resolved ``(network, agent, topic)`` namespace.
        :return: Result envelope with a sorted ``keys`` list.
        """
        # ``list`` takes no caller args — the signature exists only to match
        # the uniform ``(args, namespace)`` shape every ``_handle_*`` shares.
        # Explicit ``del`` keeps linters (unused-arg) quiet and signals intent.
        del args
        keys: list[str] = await self._store.list(namespace)
        logger.debug(
            "PersistentMemoryTool: list returned %d keys from %s",
            len(keys),
            namespace,
        )
        return {"result": {"keys": keys}}

    @property
    def enabled_operations(self) -> frozenset[str]:
        """Which operations the LLM may invoke on this tool.

        :return: Frozen set of enabled operation names.
        """
        return self._enabled_operations

    async def atomic_update_entry(
        self,
        args: dict[str, Any],
        sly_data: dict[str, Any],
        transform: Callable[[Optional[str]], Awaitable[Optional[str]]],
    ) -> Optional[str]:
        """Read-transform-write a single entry's ``content`` atomically.

        Custom entry point (not a framework hook). Exists so middleware — e.g.
        auto-compact in
        :py:class:`middleware.persistent_memory.persistent_memory_middleware.PersistentMemoryMiddleware` —
        can rewrite an entry under one lock acquisition. The read inside the
        transform and the subsequent write share the namespace lock, so
        concurrent writers cannot interleave between them.

        The transform receives the current ``content`` string (or ``None`` if
        the key is absent) and returns the replacement content. Returning
        ``None`` signals "no change" — the file is left untouched.

        :param args: Dispatcher args; resolves ``topic`` and ``key`` from here.
        :param sly_data: Neuro-SAN private data; used for topic fallback.
        :param transform: Async callable receiving current content string,
                          returning the new content string or ``None``.
        :return: The content string that was written, or ``None`` if the
                 transform opted out.
        """
        namespace: Namespace = (
            self._agent_network_name,
            self._agent_name,
            self._resolve_topic(args, sly_data),
        )
        key: str = self._str(args.get("key")) or self._DEFAULT_KEY

        async def _value_transform(current: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
            """Translate between the tool-level (content string) and store-level
            (whole value dict) shapes of the transform callable."""
            current_content: Optional[str] = None
            if current is not None:
                current_content = str(current.get("content") or "")
            new_content: Optional[str] = await transform(current_content)
            if new_content is None:
                return None
            return {"content": new_content}

        new_value: Optional[dict[str, Any]] = await self._store.atomic_update_entry(namespace, key, _value_transform)
        if new_value is None:
            return None
        return str(new_value.get("content") or "")

    async def close(self) -> None:
        """Release the underlying store's resources.

        Callable by :py:class:`middleware.persistent_memory.persistent_memory_middleware.PersistentMemoryMiddleware`
        in its ``aafter_agent`` hook. Safe to call multiple times.
        """
        await self._store.close()

    # ------------------------------------------------------------------
    # Argument helpers
    # ------------------------------------------------------------------

    @classmethod
    def _resolve_topic(cls, args: dict[str, Any], sly_data: dict[str, Any]) -> str:
        """Resolve the topic — the on-disk file name for this slice of memory.

        A topic can be anything the caller wants: a user's name, a project id,
        a session id, a feature area. It simply becomes the filename.

        Priority:
            1. ``args["topic"]`` — LLM-supplied per-call topic (prompt-driven).
               The agent's HOCON instructs the LLM to pass whatever scoping value
               makes sense, so each topic gets its own file (``mike.md``,
               ``project_alpha.md``, ``session_42.md``).
            2. ``sly_data["user_id"]`` — set by the client (e.g. nsflow) when a
               user identifier is supplied on the request. Handy for truly
               authenticated multi-tenant deployments where the topic IS the user.
            3. :py:attr:`_DEFAULT_TOPIC` — hard fallback.

        In all cases the result is normalised to a filesystem-safe slug so the
        backend can use it as a filename without further sanitisation risk.

        :param args: Dispatcher args; may contain ``topic``.
        :param sly_data: Neuro-SAN private data; may contain ``user_id``.
        :return: Filesystem-safe slug for the topic file name.
        """
        raw: Any = args.get("topic") if args else None
        if not raw:
            raw = sly_data.get("user_id") if sly_data else None

        if raw:
            slug: str = PathComponent.slugify(str(raw))
            if slug:
                return slug

        # Not operator-actionable — a missing topic is normally just an agent
        # network configured without per-user scoping. DEBUG keeps it observable
        # when diagnosing cross-user contamination without noise in prod logs.
        logger.debug(
            "PersistentMemoryTool: no 'topic' arg or sly_data['user_id']; falling "
            "back to '%s'. All callers without a topic will share the same file.",
            cls._DEFAULT_TOPIC,
        )
        return cls._DEFAULT_TOPIC

    @staticmethod
    def _str(value: Any) -> str:
        """Normalise an LLM-supplied argument to a trimmed string.

        :param value: Any value the LLM may have passed.
        :return: Trimmed string, or ``''`` if ``value`` is ``None``.
        """
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _parse_limit(value: Any, default: int) -> int:
        """Best-effort int parse. LLMs sometimes pass strings here.

        :param value: Raw value the LLM supplied for ``limit``.
        :param default: Fallback if ``value`` is missing or unparsable.
        :return: Positive int limit.
        """
        if value is None or value == "":
            return default
        try:
            parsed: int = int(value)
        except (TypeError, ValueError):
            return default
        return parsed if parsed > 0 else default

    @staticmethod
    def _error(message: str) -> dict[str, Any]:
        """Build the uniform error envelope returned to the LLM.

        :param message: Human-readable error message.
        :return: ``{"error": message}`` dict.
        """
        return {"error": message}
