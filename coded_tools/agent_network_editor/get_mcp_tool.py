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

import asyncio
import logging
import os
from math import isfinite
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool
from neuro_san.interfaces.coded_tool import CodedTool
from neuro_san.internals.run_context.langchain.mcp.langchain_mcp_adapter import LangChainMcpAdapter
from neuro_san.internals.run_context.langchain.mcp.mcp_servers_info_restorer import McpServersInfoRestorer

from coded_tools.agent_network_editor.and_logger import AndLogger
from coded_tools.agent_network_editor.shared_process_cache import SharedProcessCache
from neuro_san_studio import mcp as _mcp_pkg

# Path to the mcp_info.hocon shipped inside the neuro_san_studio package.
# Resolved via the imported package's __file__ so it works both in-repo and
# after `pip install` on every platform. Mirrors run.py.
BUNDLED_MCP_INFO_FILE: Path = Path(_mcp_pkg.__file__).parent / "mcp_info.hocon"

# Default cap on how long one MCP server may take to answer a tool listing
# (see _mcp_tools_fetch_timeout_seconds for the env-var override). The
# listings are fetched by a process-wide shared load, so without a cap a
# single hung server would stall every conversation's get_mcp_tool call
# (previously it only stalled the one conversation doing the fetch). A slow
# server is logged, omitted from this round's result, and retried after the
# TTL window. The cap bounds the listing attempt itself, not the whole
# stall: cancelling a timed-out fetch awaits the MCP client's teardown,
# which talks to the same unresponsive server under the HTTP client's own,
# much longer timeouts — bounding that too needs a fix in the MCP client,
# not here.
DEFAULT_MCP_TOOLS_FETCH_TIMEOUT_SECONDS: float = 30.0

# Default for how long fetched tool listings may be served before being
# re-fetched (see _mcp_tools_ttl_seconds for the env-var override).
DEFAULT_MCP_TOOLS_TTL_SECONDS: float = 300.0

logger = AndLogger(logging.getLogger(__name__))


class GetMcpTool(CodedTool):
    """
    CodedTool implementation which provides a way to get tool definition from given MCP servers
    """

    # TODO: This duplicates NeuroSanRunner._resolve_mcp_info_file in
    # neuro_san_studio/commands/run.py. Refactor so run.py calls this method
    # instead of maintaining its own copy.
    @staticmethod
    def get_mcp_info_file() -> str:
        """Resolve the mcp_info.hocon path at call time.

        Precedence (mirrors NeuroSanRunner._resolve_mcp_info_file):
          1. MCP_SERVERS_INFO_FILE env var (used verbatim if non-empty).
          2. <cwd>/mcp/mcp_info.hocon if it exists (what `init` scaffolds).
          3. The mcp_info.hocon bundled in the neuro_san_studio package.
        """
        env_value = os.getenv("MCP_SERVERS_INFO_FILE")
        if env_value:
            return env_value
        try:
            scaffolded = Path.cwd() / "mcp" / "mcp_info.hocon"
            if scaffolded.is_file():
                return str(scaffolded)
        except OSError:
            # Path.cwd() raises when the working directory has been deleted
            # out from under the process. This resolver runs inside
            # fingerprint probes, which must not raise, so fall through to
            # the bundled file instead.
            pass
        return str(BUNDLED_MCP_INFO_FILE)

    @staticmethod
    def _mcp_info_fingerprint() -> tuple[str, int | None]:
        """
        Freshness probe for the shared MCP-servers cache (see
        SharedProcessCache): the cached list is served only while this value
        is unchanged. Unlike the designer manifest there is no time bucket:
        mcp_info.hocon is a plain config file with no `include`s and nothing
        writes it at runtime, so the two components cover everything the
        probe can see —

        * the resolved path — an env-var change or the cwd-scaffolded file
          appearing takes effect on the next read;
        * the file's modification_time — a direct edit invalidates immediately, and a
          missing file (modification_time None) self-heals the moment it appears.

        Two changes are invisible to this probe: HOCON `${...}` references
        inside the file resolve against the environment at parse time, so
        changing THOSE env vars alters the parse result without touching
        path or modification_time; and LangChainMcpAdapter keeps its own copy of the
        servers info, frozen at its first load — a file edit refreshes
        which URLs this class serves, but not the connection details the
        adapter already latched. Both heal on process restart (or on the
        modification_time change of the next file edit, for the first).

        :return: (path, modification_time_ns or None) tuple.
        """
        mcp_info_file: str = GetMcpTool.get_mcp_info_file()
        return (mcp_info_file, SharedProcessCache.stat_modification_time_ns(mcp_info_file))

    @staticmethod
    def _load_mcp_servers() -> list[str]:
        """
        Loader for the shared MCP-servers list (runs inside
        SharedProcessCache, off the event loop when reached via aget()).

        :return: List of MCP server URLs from mcp_info.hocon. A missing,
                unreadable, or unparseable file returns an empty list, which
                IS published: the fingerprint self-heals it — a missing file
                flips the modification_time component when it appears, and fixing a
                broken file changes its modification_time — so nothing can pin an empty
                list past the next change to the file itself (env-var
                references INSIDE the file are the one exception; see
                _mcp_info_fingerprint).
        """
        mcp_info_file: str = GetMcpTool.get_mcp_info_file()
        logger.info("MCP servers info file: %s", mcp_info_file)

        servers: list[str] = []
        try:
            # McpServersInfoRestorer is constructed with must_exist=False, so
            # a missing file comes back as None rather than an exception.
            info: dict[str, Any] = McpServersInfoRestorer().restore(file_reference=mcp_info_file)
            if info is None:
                logger.warning("MCP servers info file not found at %s. No MCP Servers will be used.", mcp_info_file)
                info = {}
            servers = list(info.keys())
        except (OSError, ValueError) as error:
            # neuro-san re-wraps HOCON parse errors as ValueError; OSError
            # covers a file that exists but cannot be read (permissions, I/O
            # failure). Neither may escape: a loader exception would fail
            # every caller sharing this load, when the healthy answer is
            # simply "no MCP servers right now".
            logger.warning("Failed to read MCP servers info file %s: %s", mcp_info_file, error)
        return servers

    # Process-wide cache of the MCP server URLs parsed from mcp_info.hocon.
    # Previously cached per sly_data scope, so a server handling N concurrent
    # conversations re-parsed the same HOCON N times, on the event loop.
    # The (path, modification_time) fingerprint picks up env-var changes and file edits
    # immediately; there is no time bucket because nothing changes this file
    # at runtime. Locking, publish ordering, and the async once-gate live in
    # SharedProcessCache; access goes through the class by name (not cls) so
    # a hypothetical subclass shares the one cache instead of splitting it.
    _shared_mcp_servers_cache: SharedProcessCache[list[str]] = SharedProcessCache(
        loader=_load_mcp_servers, fingerprint=_mcp_info_fingerprint
    )

    @staticmethod
    def _mcp_tools_fetch_timeout_seconds() -> float | None:
        """
        :return: Cap in seconds on one MCP server's tool-listing fetch, from
                the AGENT_NETWORK_DESIGNER_MCP_TOOLS_FETCH_TIMEOUT_SECONDS
                env var (default 30) — the escape hatch for servers that
                legitimately need longer than the default to answer, which
                the pre-cache code (no cap at all) tolerated. <= 0 removes
                the cap entirely (returned as None, what asyncio.wait_for
                takes for "no timeout"), restoring that old behavior at the
                cost of letting one hung server stall the shared load. An
                unparseable or non-finite value falls back to the default.
        """
        raw: str = os.getenv("AGENT_NETWORK_DESIGNER_MCP_TOOLS_FETCH_TIMEOUT_SECONDS", "")
        try:
            timeout: float = float(raw) if raw else DEFAULT_MCP_TOOLS_FETCH_TIMEOUT_SECONDS
        except ValueError:
            timeout = DEFAULT_MCP_TOOLS_FETCH_TIMEOUT_SECONDS
        if not isfinite(timeout):
            timeout = DEFAULT_MCP_TOOLS_FETCH_TIMEOUT_SECONDS
        return None if timeout <= 0 else timeout

    @staticmethod
    def _mcp_tools_ttl_seconds() -> float:
        """
        :return: How long the shared tool-descriptions mapping may be served
                before the listings are re-fetched from the MCP servers, from
                the AGENT_NETWORK_DESIGNER_MCP_TOOLS_TTL_SECONDS env var
                (default 300). Unlike the file-backed caches there is no
                local change to observe — the servers are external and their
                tool sets can change (or an outage can end) without any local
                signal — so a TTL is the freshness mechanism, and it doubles
                as the recovery bound after a failed or partial fetch.
                <= 0 disables time-based refresh entirely: the listings are
                fetched once and only an mcp_info.hocon change refreshes
                them. An unparseable or non-finite value falls back to the
                default (nan and inf would otherwise silently freeze the
                time bucket). A positive value is clamped to at least twice
                the per-server fetch cap: a TTL shorter than one fetch means
                every fill is already stale by the time it publishes, so no
                call is ever served warm and every call re-fetches every
                server — a permanent fetch storm instead of a cache.
        """
        raw: str = os.getenv("AGENT_NETWORK_DESIGNER_MCP_TOOLS_TTL_SECONDS", "")
        try:
            ttl: float = float(raw) if raw else DEFAULT_MCP_TOOLS_TTL_SECONDS
        except ValueError:
            ttl = DEFAULT_MCP_TOOLS_TTL_SECONDS
        if not isfinite(ttl):
            ttl = DEFAULT_MCP_TOOLS_TTL_SECONDS
        if ttl <= 0:
            return ttl
        fetch_cap: float | None = GetMcpTool._mcp_tools_fetch_timeout_seconds()
        if fetch_cap is None:
            # With the cap disabled a fetch is unbounded, so no clamp can
            # guarantee anything; twice the default cap is the best effort.
            fetch_cap = DEFAULT_MCP_TOOLS_FETCH_TIMEOUT_SECONDS
        return max(ttl, 2 * fetch_cap)

    @staticmethod
    def _mcp_tools_fingerprint() -> tuple[str, int | None, float, int]:
        """
        Freshness probe for the shared tool-descriptions cache: the
        MCP-servers-list fingerprint (so an mcp_info.hocon edit refreshes the
        listings immediately) plus the TTL and a time bucket that rolls once
        per TTL window (see _mcp_tools_ttl_seconds; frozen when TTL <= 0).
        The TTL value itself rides along because bucket numbers from
        different TTL regimes are not comparable — after an env-var change,
        bucket N under the new TTL can collide with bucket N under the old
        one and revive a stale entry; carrying the TTL makes any change to
        it an immediate miss instead.

        :return: (path, modification_time_ns or None, ttl, time bucket) tuple.
        """
        mcp_info_file, modification_time_ns = GetMcpTool._mcp_info_fingerprint()
        ttl: float = GetMcpTool._mcp_tools_ttl_seconds()
        return (mcp_info_file, modification_time_ns, ttl, SharedProcessCache.time_bucket(ttl))

    @staticmethod
    async def _fetch_tool_descriptions(server: str, fetch_timeout: float | None) -> tuple[str, str | None]:
        """
        Fetch one MCP server's tool listing and flatten it into a
        description string, on the private event loop that
        _load_mcp_tool_descriptions runs. LangChainMcpAdapter resolves the
        server's connection details from its own copy of the servers info
        (loaded once per process — see _mcp_info_fingerprint), opens a
        session, and lists the tools.

        :param server: The MCP server URL.
        :param fetch_timeout: Per-server cap in seconds, or None for no cap
                (see _mcp_tools_fetch_timeout_seconds).
        :return: (server, newline-joined tool descriptions) on success,
                (server, None) on any failure — this never raises, so one
                broken server cannot take out the whole gathered batch.
        """
        logger.info("MCP Server: %s", server)
        try:
            tools: list[BaseTool] = await asyncio.wait_for(
                LangChainMcpAdapter().get_mcp_tools(server), timeout=fetch_timeout
            )
            logger.info("Successfully loaded the following tools: %s", str(tools))
            # Flatten the descriptions INSIDE the try: a malformed tool
            # (description None or missing) must degrade to this one
            # server's failure, not escape the gather and fail the load
            # for every server.
            description: str = ""
            for tool in tools:
                description += tool.description + "\n"
        except Exception as error:  # pylint: disable=broad-exception-caught
            # Broad on purpose: this is a shared load, so one bad server
            # (ExceptionGroup out of the MCP client, TimeoutError from the
            # cap above, connection errors, ...) must not take out every
            # conversation's listing of the healthy servers.
            logger.warning("Error: Failed to load tools from %s. %s", server, error)
            return server, None
        return server, description

    @staticmethod
    async def _fetch_all_tool_descriptions(servers: list[str]) -> dict[str, str]:
        """
        Fetch every configured server's tool listing concurrently; the
        entry point of the private event loop that
        _load_mcp_tool_descriptions runs.

        :param servers: The MCP server URLs from the shared servers cache.
        :return: dict mapping each server URL that answered to its tools'
                descriptions; servers that failed are absent.
        """
        fetch_timeout: float | None = GetMcpTool._mcp_tools_fetch_timeout_seconds()
        # return_exceptions=False is safe here because
        # _fetch_tool_descriptions swallows its own errors.
        results = await asyncio.gather(
            *[GetMcpTool._fetch_tool_descriptions(server, fetch_timeout) for server in servers]
        )
        return {server: description for server, description in results if description is not None}

    @staticmethod
    def _load_mcp_tool_descriptions() -> dict[str, str]:
        """
        Loader for the shared tool-descriptions mapping (runs inside
        SharedProcessCache, in a worker thread when reached via aget()).

        Fetches every configured server's tool listing CONCURRENTLY on a
        private event loop (asyncio.run — legal here because the loader runs
        in a worker thread, never on the server's loop). The old per-session
        code fetched sequentially, paying the sum of the servers' latencies
        per conversation; gather pays only the slowest.

        :return: dict mapping each server URL to a newline-joined string of
                its tools' descriptions. Servers that fail or time out are
                logged and omitted (matching the old per-session behavior),
                and the partial — possibly empty — result IS published: the
                entry self-expires via the TTL bucket, so an outage cannot
                poison the process beyond one window, and publishing
                prevents a per-call fetch storm during it.
        :raises RuntimeError: when servers are configured but EVERY fetch
                failed AND time-based refresh is disabled (TTL <= 0, frozen
                bucket). Publishing that all-failed result would pin it
                until an mcp_info.hocon change or a process restart — the
                outage's recovery is invisible to the frozen fingerprint —
                so nothing is published and the next call retries instead.
                Same failure shape, same remedy as the subnetwork
                descriptions filler's all-empty guard.
        """
        # Already in a worker thread here, so the blocking get() is fine.
        servers: list[str] = GetMcpTool._shared_mcp_servers_cache.get()
        descriptions: dict[str, str] = asyncio.run(GetMcpTool._fetch_all_tool_descriptions(servers))
        if servers and not descriptions and GetMcpTool._mcp_tools_ttl_seconds() <= 0:
            raise RuntimeError(
                f"all {len(servers)} MCP tool-listing fetches failed and time-based refresh is disabled; "
                "treating as a failed load"
            )
        return descriptions

    # Process-wide cache of the {server URL: tool descriptions} mapping
    # fetched from the MCP servers themselves. Previously cached per sly_data
    # scope, so every conversation paid the full network round-trip to every
    # server (sequentially). The sources are external servers with no local
    # change signal, so freshness is time-based: the fingerprint reuses the
    # mcp_info.hocon (path, modification_time) probe — a config edit refreshes
    # immediately — plus a TTL bucket (default 300s, see
    # _mcp_tools_ttl_seconds) that bounds both staleness and how long a
    # failed fetch's empty/partial result can be served. (With time-based
    # refresh disabled, an all-failed fetch raises instead of publishing —
    # see the loader.) Locking, publish
    # ordering, and the async once-gate live in SharedProcessCache; access
    # goes through the class by name (not cls) so a hypothetical subclass
    # shares the one cache instead of splitting it.
    _shared_mcp_tool_descriptions_cache: SharedProcessCache[dict[str, str]] = SharedProcessCache(
        loader=_load_mcp_tool_descriptions, fingerprint=_mcp_tools_fingerprint
    )

    @classmethod
    def clear_shared_mcp_servers_for_testing(cls):
        """
        Reset the process-wide MCP-servers cache. For test isolation only.

        Production code must never call this — staleness is already bounded
        by the fingerprint. Tests call it (via tests/conftest.py) so a list
        loaded under one test's MCP_SERVERS_INFO_FILE state cannot leak into
        later tests. Living here rather than in conftest keeps all the
        singleton policy in this one class.
        """
        GetMcpTool._shared_mcp_servers_cache.clear_for_testing()

    @classmethod
    def clear_shared_mcp_tool_descriptions_for_testing(cls):
        """
        Reset the process-wide tool-descriptions cache. For test isolation
        only — see clear_shared_mcp_servers_for_testing.
        """
        GetMcpTool._shared_mcp_tool_descriptions_cache.clear_for_testing()

    @staticmethod
    async def get_mcp_servers() -> list[str]:
        """
        Get the list of MCP server URLs from mcp_info.hocon.

        Used by callers (e.g. middleware) that need to validate MCP
        references. Reads only the config file, not the servers — and at
        most once per process per config change, off the event loop, shared
        by concurrent cold callers.

        :return: List of MCP server URLs, or an empty list if the file is
                missing or fails to parse (see the loader for the
                self-healing semantics). The returned list is a copy, so
                callers may mutate it without corrupting the shared cache.
        """
        return list(await GetMcpTool._shared_mcp_servers_cache.aget())

    @staticmethod
    async def get_mcp_tool_descriptions() -> dict[str, str]:
        """
        Get the {server URL: tool descriptions} mapping, fetching from the
        MCP servers at most once per process per TTL window (or config
        change), off the event loop, shared by concurrent cold callers.

        :return: dict mapping each server URL to a newline-joined string of
                its tools' descriptions; servers that failed this round are
                absent (retried after the TTL window). An empty dict when no
                servers are configured — or, with time-based refresh
                disabled, when every fetch failed: that result is degraded
                per-call rather than published (see the loader), so the
                next call retries. The returned dict is a copy, so callers
                may mutate it without corrupting the shared cache.
        """
        try:
            return dict(await GetMcpTool._shared_mcp_tool_descriptions_cache.aget())
        except RuntimeError as error:
            # The loader refused to publish an all-failed result (frozen
            # TTL). Degrade to an empty dict for THIS call only — nothing
            # was published, so the next call retries immediately.
            logger.warning("MCP tool-listing fetch failed; returning no MCP tools for this call: %s", error)
            return {}

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> str:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    None

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                This dictionary is largely to be treated as read-only.
                It is possible to add key/value pairs to this dict that do not
                yet exist as a bulletin board, as long as the responsibility
                for which coded_tool publishes new entries is well understood
                by the agent chain implementation and the coded_tool implementation
                adding the data is not invoke()-ed more than once.

                Keys expected for this implementation are:
                    None

        :return:
            In case of successful execution:
                a string rendering of the dictionary that maps each MCP
                server URL to the descriptions of the tools it provides.
            otherwise:
                servers that failed to respond are omitted from that
                dictionary; "{}" if none responded or none are configured.
        """

        # Get tool list from MCP servers
        logger.info(">>>>>>>>>>>>>>>>>>>Getting Tool Definition from MCP Servers>>>>>>>>>>>>>>>>>>>")

        return str(await self.get_mcp_tool_descriptions())
