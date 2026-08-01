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
from functools import partial
from typing import Any

from leaf_common.config.config_filter_chain import ConfigFilterChain
from neuro_san.interfaces.coded_tool import CodedTool
from neuro_san.internals.graph.activations.branch_activation import BranchActivation
from neuro_san.internals.graph.persistence.manifest_dict_config_filter import ManifestDictConfigFilter
from neuro_san.internals.graph.persistence.manifest_key_config_filter import ManifestKeyConfigFilter
from neuro_san.internals.graph.persistence.raw_manifest_restorer import RawManifestRestorer
from neuro_san.internals.graph.persistence.registry_manifest_restorer import RegistryManifestRestorer
from neuro_san.internals.graph.persistence.served_manifest_config_filter import ServedManifestConfigFilter
from pyparsing.exceptions import ParseException

from coded_tools.agent_network_editor.and_logger import AndLogger
from coded_tools.agent_network_editor.shared_process_cache import SharedProcessCache

DEFAULT_MANIFEST_FILE = os.path.join("registries", "manifest_and.hocon")

logger = AndLogger(logging.getLogger(__name__))


# pylint: disable=too-many-ancestors
class GetSubnetwork(BranchActivation, CodedTool):
    """
    CodedTool which exposes the subnetworks available to the designer LLM.

    Inherits from BranchActivation (in addition to CodedTool) so the framework injects
    `run_context` into the instance. From there we reach the InvocationContext's
    `AsyncAgentSessionFactory` and use it to make a `session.function({})` call per
    subnetwork — the same routing mechanism `CallAgent` uses to invoke other agents.
    The framework picks direct (in-process) or http (loopback) under the hood, so this
    works uniformly in both deployment modes without needing to reach the server's
    internal `AgentNetworkStorage` directly. The fetched mapping is published to a
    process-wide cache (see _shared_subnetwork_descriptions_cache below), so the
    per-subnetwork fan-out runs once per refresh period rather than once per editor
    invocation.

    The static helper `get_subnetwork_names()` is preserved for callers that do not
    have access to a run_context (e.g. middleware classes).
    """

    @staticmethod
    def _resolve_manifest_file() -> str:
        """
        :return: The designer manifest path: the AGENT_NETWORK_DESIGNER_MANIFEST_FILE
                env var, or the default. We use a designer-specific env var
                (rather than AGENT_MANIFEST_FILE) so the designer's subnetwork
                pool can be a narrow, curated subset of what the server hosts —
                e.g. only industry/ + generated/ networks, not basic/, tools/,
                experimental/, or the designer-family agents themselves. The
                default points at manifest_and.hocon, which composes just those
                two via `include`.
        """
        return os.getenv("AGENT_NETWORK_DESIGNER_MANIFEST_FILE") or DEFAULT_MANIFEST_FILE

    @staticmethod
    def _manifest_update_period_seconds() -> float:
        """
        :return: The manifest refresh period, read from the same
                AGENT_MANIFEST_UPDATE_PERIOD_SECONDS setting that drives the
                neuro-san server's own periodic manifest updates (<= 0
                disables them; unset mirrors the server's default of 0, and
                the studio's local runner exports 5). Keying the shared
                subnetwork-names cache to this signal keeps the designer's
                view aligned with what the server can actually serve: when
                the server never picks up new manifest entries, a fresher
                name list would only advertise networks that are not
                reachable yet — so on a static server the cached list goes
                static too (a manifest path or modification_time change still refreshes
                it). When updates are enabled, one manifest parse per period
                (~15-20ms, off the event loop, and only if a caller actually
                reads in that period) is the whole steady-state refresh cost.
        """
        try:
            return float(os.getenv("AGENT_MANIFEST_UPDATE_PERIOD_SECONDS", "0"))
        except ValueError:
            return 0.0

    @staticmethod
    def _manifest_fingerprint() -> tuple[str, int | None, int]:
        """
        Freshness probe for the shared subnetwork-names cache (see
        SharedProcessCache): the cached list is served only while this value is
        unchanged. Three components, each covering a different way the list can
        go stale:

        * the resolved path — an env-var change takes effect on the next read;
        * the manifest file's modification_time — a direct edit invalidates immediately, and
          a missing manifest (modification_time None) self-heals the moment the file appears;
        * a time bucket that rolls once per manifest-update period (see
          _manifest_update_period_seconds) — the manifest composes other
          manifests via `include` (notably registries/generated/manifest.hocon,
          which grows every time the designer saves a network on a local run;
          server deployments never write the manifest), and a cheap probe
          cannot see those included files, so the rolling bucket bounds that
          staleness instead. With updates disabled (period <= 0, the
          static-server default) the bucket is constant, so only a path or
          modification_time change invalidates.

        :return: (path, modification_time_ns or None, time bucket) tuple.
        """
        manifest_file: str = GetSubnetwork._resolve_manifest_file()
        modification_time_ns: int | None = SharedProcessCache.stat_modification_time_ns(manifest_file)
        period: float = GetSubnetwork._manifest_update_period_seconds()
        return (manifest_file, modification_time_ns, SharedProcessCache.time_bucket(period))

    @staticmethod
    def _load_subnetwork_names() -> list[str]:
        """
        Loader for the shared subnetwork-names list (runs inside
        SharedProcessCache, off the event loop when reached via aget()).

        Parses the designer manifest HOCON. pyhocon resolves `include`
        statements, so composed manifests (e.g. manifest_and.hocon) flatten into
        a single mapping of "path/to/file.hocon" -> enabled-bool-or-dict entries.

        :return: List of subnetwork name strings (in "/<network_name>" form).
                A missing or unparseable manifest returns an empty list, which IS
                published: unlike an immortal cache this entry expires on its own
                (modification_time change or manifest-update-period roll, whichever comes
                first), so a bad manifest cannot poison the process beyond one
                refresh period — and publishing the empty result prevents a
                per-call parse storm within it. (On a static server with
                updates disabled, healing relies on the modification_time/path change that
                fixing the manifest entails.)
        """
        manifest_file: str = GetSubnetwork._resolve_manifest_file()

        logger.info(">>>>>>>>>>>>>>>>>>>Getting Subnetwork Names from Manifest>>>>>>>>>>>>>>>>>>>")
        logger.info("Manifest file: %s", manifest_file)

        names: list[str] = []
        try:
            # RawManifestRestorer returns None if the file is missing — treated as
            # an empty manifest (no subnetworks available).
            raw_manifest: dict[str, Any] = RawManifestRestorer().restore(file_reference=manifest_file)
            if raw_manifest is None:
                logger.warning(
                    "Manifest file '%s' not found, no external agents/subnetworks will be available "
                    "in the generated network",
                    manifest_file,
                )
                raw_manifest = {}

            # Use neuro-san's canonical manifest filters so we don't reimplement manifest semantics:
            #   - ManifestKeyConfigFilter:    strips quote chars from quoted HOCON keys
            #   - ManifestDictConfigFilter:   normalizes bool values to {"serve": ..., ...}
            #   - ServedManifestConfigFilter: drops non-served entries
            # We assemble our own chain rather than using ManifestFilterChain because the latter
            # registers ServedManifestConfigFilter with warn_on_skip=True/entry_for_skipped=True,
            # which would log a warning per disabled entry and keep them in the result. Here we
            # want unserved entries silently dropped.
            filter_chain = ConfigFilterChain()
            filter_chain.register(ManifestKeyConfigFilter(manifest_file))
            filter_chain.register(ManifestDictConfigFilter(manifest_file))
            filter_chain.register(
                ServedManifestConfigFilter(manifest_file, warn_on_skip=False, entry_for_skipped=False)
            )
            one_manifest: dict[str, Any] = filter_chain.filter_config(raw_manifest)

            # Derive external network names ("/<network_name>") via neuro-san's
            # canonical implementation instead of re-rolling its mapper walk.
            # Passing manifest_files explicitly keeps the constructor away from
            # the server-wide AGENT_MANIFEST_FILE fallback; construction is cheap
            # (it just stores the path and a default AgentFileTreeMapper).
            names = RegistryManifestRestorer(manifest_files=manifest_file).find_external_network_names(one_manifest)
        except (ParseException, ValueError) as parse_error:
            # neuro-san's restorer deliberately re-wraps HOCON parse errors
            # (pyparsing ParseException, pyhocon ConfigException) as ValueError,
            # so ValueError is what actually arrives here; ParseException stays
            # in the tuple in case that wrapping ever goes away.
            logger.warning(
                "Failed to parse manifest '%s', no subnetwork names will be available: %s",
                manifest_file,
                parse_error,
            )

        return names

    # Process-wide cache of the "/<network_name>" list parsed from the
    # designer manifest. Previously cached per sly_data scope,
    # so a server handling N concurrent conversations re-parsed the same
    # manifest N times, on the event loop. Unlike the immortal toolbox
    # caches, this source legitimately changes at runtime on local runs —
    # the designer saves every generated network into a manifest the top
    # file `include`s; server deployments persist elsewhere and never write
    # it — so the fingerprint (path + modification_time + a manifest-update-period
    # bucket, see _manifest_fingerprint) keeps the list at most one
    # AGENT_MANIFEST_UPDATE_PERIOD_SECONDS period stale, the same cadence at
    # which the server itself picks up new manifest entries.
    # Locking, publish ordering, and the async once-gate live in
    # SharedProcessCache; access goes through the class by name (not cls) so
    # a hypothetical subclass shares the one cache instead of splitting it.
    _shared_subnetwork_names_cache: SharedProcessCache[list[str]] = SharedProcessCache(
        loader=_load_subnetwork_names, fingerprint=_manifest_fingerprint
    )

    @classmethod
    def clear_shared_subnetwork_names_for_testing(cls):
        """
        Reset the process-wide subnetwork-names cache. For test isolation only.

        Production code must never call this — staleness is already bounded
        by the fingerprint. Tests call it (via tests/conftest.py) so names
        loaded under one test's manifest/env state cannot leak into later
        tests within the same TTL window. Living here rather than in conftest
        keeps all the singleton policy in this one class.
        """
        GetSubnetwork._shared_subnetwork_names_cache.clear_for_testing()

    # Process-wide cache of the {/<network_name>: front-man description}
    # mapping shown to the designer LLM. Previously cached per sly_data
    # scope, which does not survive across editor invocations — so every
    # user request re-fetched every description: one session.function({})
    # call per subnetwork which, in http mode, is a loopback round trip
    # processed by the same event loop that is serving the request.
    # Constructed WITHOUT a loader: the fetch needs the framework session
    # factory, which only a live run_context can reach, so get_subnetworks()
    # fills the cache in-context via aget_or_fill(). Shares
    # _manifest_fingerprint with the names cache above so names and
    # descriptions go stale and refresh together — descriptions live in each
    # subnetwork's own hocon, which a manifest probe cannot see, and the
    # manifest-update-period bucket bounds that staleness at the same cadence
    # at which the server itself picks up registry changes.
    # Not consulted at all when AGENT_AUTHORIZER is set — see
    # _shared_descriptions_cache_enabled below.
    _shared_subnetwork_descriptions_cache: SharedProcessCache[dict[str, str]] = SharedProcessCache(
        fingerprint=_manifest_fingerprint
    )

    @classmethod
    def clear_shared_subnetwork_descriptions_for_testing(cls):
        """
        Reset the process-wide subnetwork-descriptions cache. For test
        isolation only — see clear_shared_subnetwork_names_for_testing();
        the same reasoning applies here.
        """
        GetSubnetwork._shared_subnetwork_descriptions_cache.clear_for_testing()

    @staticmethod
    def _shared_descriptions_cache_enabled() -> bool:
        """
        :return: True when descriptions may be shared process-wide. With an
                AGENT_AUTHORIZER configured (non-empty env var; empty is the
                server's allow-all default), the /function endpoint is
                authorization-gated per caller identity — the metadata each
                request forwards decides which networks answer and which
                return 403 — so a mapping fetched under one user's identity
                must not be served to other users: whichever user won the
                cold race would blank out, or expose, networks according to
                THEIR permissions for everyone. get_subnetworks() then skips
                the shared cache and fetches once per invocation, the
                pre-cache behavior.
        """
        return not os.getenv("AGENT_AUTHORIZER")

    @staticmethod
    async def get_subnetwork_names() -> list[str]:
        """
        Get the list of subnetwork names from the **designer manifest** only.

        Used by callers (e.g. middleware) that need to validate subnetwork references
        but do not have access to a run_context. Reads only the manifest HOCON, not
        each subnetwork's HOCON — and at most once per process per
        manifest-update period (or manifest edit), off the event loop,
        shared by concurrent cold callers.

        :return: List of subnetwork name strings (in "/<network_name>" form), or an
                empty list if the manifest is missing or fails to parse (see
                the loader for the self-healing semantics). The returned list
                is a copy, so callers may mutate it without corrupting the
                shared cache.
        """
        return list(await GetSubnetwork._shared_subnetwork_names_cache.aget())

    async def get_subnetworks(self) -> dict[str, str]:
        """
        Return the {/<name>: front-man-description} mapping shown to the designer LLM.

        Served from the process-wide descriptions cache when warm. On a miss, this
        invocation fills it: for each name from the designer manifest, we open an
        `AsyncAgentSession` to that agent and call its `function({})` endpoint to get
        the front-man's function spec (the same JSON-schema-ish structure the LLM sees
        when wiring tools). The session is created via
        `invocation_context.get_async_session_factory().create_session()` — the same
        hook `CallAgent` uses, and the framework decides whether to dispatch
        in-process (direct mode) or via loopback HTTP (server mode) based on the
        factory's `use_direct` setting. Caching the result process-wide is what keeps
        that fan-out — one `function` call per subnetwork, per editor invocation, i.e.
        per user request — off the server's event loop in http mode.

        :return: dict mapping "/<network_name>" -> front-man's function.description.
                Networks that fail to respond, return no front man, or have an empty
                description are still included with an empty-string value so the LLM
                at least sees the name — unless EVERY description came back empty,
                the signature of a fetch outage, in which case nothing is published
                and this call returns an empty dict (the next call retries). Also an
                empty dict if no names or no run_context. The returned dict is a
                copy, so callers may mutate it without corrupting the shared cache.
        """
        use_shared_cache: bool = GetSubnetwork._shared_descriptions_cache_enabled()
        if use_shared_cache:
            # Besides skipping the factory resolution below on warm calls,
            # this peek is what serves warm reads to callers WITHOUT a
            # run_context (e.g. tests instantiating the tool directly): such
            # callers degrade to an empty dict only when the cache is
            # actually cold. aget_or_fill() peeks again on the miss path;
            # that duplication is deliberate.
            cached: dict[str, str] | None = GetSubnetwork._shared_subnetwork_descriptions_cache.peek()
            if cached is not None:
                return dict(cached)

        # Resolve the session factory BEFORE entering the shared fill.
        # `run_context` is injected by BranchActivation.__init__; if this CodedTool is
        # ever instantiated outside that flow (e.g. tests bypassing __init__), this
        # call degrades to a per-call empty dict — crucially WITHOUT publishing that
        # emptiness into the process-wide cache, where it would blank out every other
        # conversation's view of the available subnetworks. None-checks rather than a
        # broad `except AttributeError`, which would also mask a genuine
        # AttributeError raised INSIDE the neuro-san accessors (e.g. version skew).
        run_context = getattr(self, "run_context", None)
        invocation_context = run_context.get_invocation_context() if run_context is not None else None
        factory = invocation_context.get_async_session_factory() if invocation_context is not None else None
        if factory is None:
            logger.warning("No invocation context / session factory available; returning empty subnetworks.")
            return {}

        filler = partial(GetSubnetwork._fill_subnetwork_descriptions, factory, invocation_context)
        try:
            if use_shared_cache:
                subnetworks: dict[str, str] = await GetSubnetwork._shared_subnetwork_descriptions_cache.aget_or_fill(
                    filler
                )
            else:
                # An authorizer is configured: descriptions are caller-specific,
                # so fetch under this invocation's own identity every time.
                subnetworks = await filler()
        except RuntimeError as error:
            # The filler refused to build a publishable mapping (every fetch
            # failed). Degrade to an empty dict for THIS call only — nothing
            # was published, so the next call retries immediately.
            logger.warning("Subnetwork description fetch failed; returning empty subnetworks for this call: %s", error)
            return {}
        return dict(subnetworks)

    @staticmethod
    async def _fill_subnetwork_descriptions(factory: Any, invocation_context: Any) -> dict[str, str]:
        """
        Filler for the shared descriptions cache: builds the complete mapping on
        the event loop inside SharedProcessCache.aget_or_fill(), once per refresh
        period, shared by every concurrent cold caller on the loop.

        Whichever invocation reaches the cold cache first supplies the factory and
        invocation_context the fill runs under; invocations are interchangeable for
        this purpose because every factory routes `function({})` to the same server
        state.

        :param factory: The `AsyncAgentSessionFactory` of the filling invocation.
        :param invocation_context: That invocation's `InvocationContext`.
        :return: dict mapping "/<network_name>" -> description. An empty mapping
                from an empty manifest IS returned, and therefore published: like
                the names cache, it heals when the fingerprint changes — and the
                manifest fix that emptiness calls for is itself a modification_time change
                the fingerprint sees.
        :raises RuntimeError: when names exist but EVERY description fetch came
                back empty — the signature of a fetch outage, whose recovery
                changes nothing the fingerprint observes. Publishing it would
                blank every conversation's view, on a static server (manifest
                update period <= 0, manifest never rewritten) until the process
                restarts. Same failure shape, same remedy as the toolbox loader's
                empty-mapping guard: raise so nothing is published and the next
                call retries.
        """
        names: list[str] = await GetSubnetwork.get_subnetwork_names()
        if not names:
            return {}
        descriptions: dict[str, str] = await GetSubnetwork._collect_via_sessions(names, factory, invocation_context)
        if descriptions and not any(descriptions.values()):
            raise RuntimeError(
                f"all {len(descriptions)} subnetwork description fetches came back empty; treating as a failed load"
            )
        return descriptions

    @staticmethod
    async def _collect_via_sessions(
        names: list[str],
        factory: Any,
        invocation_context: Any,
    ) -> dict[str, str]:
        """Query each network's `function` endpoint to get its front-man description.

        Dispatches one `session.function({})` call per name concurrently via
        `asyncio.gather`. Each call routes through `factory.create_session()` — the
        same mechanism `CallAgent` uses — which transparently picks in-process direct
        or loopback HTTP. Per-call cost is dominated by:
          - direct mode: a single dict lookup on the live AgentNetwork.
          - http mode: a loopback HTTP round-trip to this same server's
            `/api/v1/<name>/function` endpoint.

        :param names: Curated list of "/<network_name>" strings from the designer manifest.
        :param factory: The `AsyncAgentSessionFactory` from the invocation context.
                Typed as Any to avoid hard-coupling to the concrete factory class.
        :param invocation_context: The current `InvocationContext`; passed through to the
                session so it can carry metadata/port/etc.
        :return: Dict mapping "/<network_name>" -> description string. Networks whose
                session creation fails, whose `function({})` raises, or whose response
                lacks a usable description are kept with an empty-string value
                (errors are logged at warning level inside `_fetch_description`).
        """
        # Build the task list explicitly (no generator expression) so additional
        # per-task setup or instrumentation is easy to add later without restructuring.
        tasks: list[Any] = []
        for name in names:
            tasks.append(GetSubnetwork._fetch_description(name, factory, invocation_context))

        # gather() fires all calls in parallel. In http mode the server processes them
        # on a single event loop so they effectively serialise behind it, but the work
        # per call is small (~ms each) and gather amortises the await overhead.
        # return_exceptions=False is safe here because _fetch_description swallows its own errors.
        results: list[tuple[str, str]] = await asyncio.gather(*tasks)

        # Keep every name in the result, even when the description came back empty —
        # the LLM at least gets visibility into the available subnetwork names and can
        # still wire them if it knows what they do. A few empty entries ride along in
        # the published mapping (a network may legitimately have no description) and
        # refresh only when the fingerprint changes; the pathological case — EVERY
        # description empty, the signature of a fetch outage — is rejected by the
        # filler before anything is published.
        subnetworks: dict[str, str] = {}
        for name, desc in results:
            subnetworks[name] = desc
        return subnetworks

    @staticmethod
    async def _fetch_description(
        name: str,
        factory: Any,
        invocation_context: Any,
    ) -> tuple[str, str]:
        """Fetch one subnetwork's front-man description via the framework session factory.

        `session.function({})` returns the front-man's tool spec; the format is
        ``{"function": {"description": "...", "parameters": {...}, ...}}``. In direct
        mode this is built straight from the loaded AgentNetwork (see
        AsyncDirectAgentSession.function). In http mode it's a loopback call to the
        server's own /function endpoint, which does the same work server-side. Either
        way the response shape is identical, which is what lets this helper stay
        mode-agnostic.

        :param name: The subnetwork name in "/<network_name>" form. Passed straight to
                `factory.create_session()` as the agent URL.
        :param factory: The `AsyncAgentSessionFactory` that decides direct vs http routing.
        :param invocation_context: The current `InvocationContext`, threaded into the
                session for metadata / port / etc.
        :return: (name, description) tuple. `description` is the empty string when the
                session can't be created, the call raises, or the response doesn't carry
                a usable description. Errors are logged at warning level. We always
                return a tuple (never raise) so a single broken subnetwork doesn't take
                out the rest of the gathered batch.
        """
        # We don't want one slow/broken subnetwork to take out the whole list, so we
        # catch broadly here. Could be a parse error in that network's hocon, a network
        # timeout in http mode, or a transient server issue. Log and skip.
        try:
            session = factory.create_session(name, invocation_context)
            if session is None:
                # Factory couldn't resolve the URL — most likely a malformed name or a
                # host the parser doesn't recognise. Skip rather than fail loudly.
                return name, ""
            result = await session.function({})
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning("Failed to fetch function spec for %s: %s", name, exc)
            return name, ""

        # Defensive shape checks: the wire format should always be a dict, but malformed
        # responses (e.g. an old server version, a transport error returning a string)
        # would otherwise crash the whole gather batch.
        if not isinstance(result, dict):
            return name, ""
        function_spec = result.get("function") or {}
        if not isinstance(function_spec, dict):
            return name, ""
        desc_val = function_spec.get("description") or ""
        return name, desc_val if isinstance(desc_val, str) else ""

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any]:
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
                the names and descriptions as keys and values of a dictionary.
            otherwise:
                an empty dictionary.
        """
        return await self.get_subnetworks()
