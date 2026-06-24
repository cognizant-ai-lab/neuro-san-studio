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
from typing import Any

from leaf_common.config.config_filter_chain import ConfigFilterChain
from neuro_san.interfaces.coded_tool import CodedTool
from neuro_san.internals.graph.activations.branch_activation import BranchActivation
from neuro_san.internals.graph.persistence.agent_filetree_mapper import AgentFileTreeMapper
from neuro_san.internals.graph.persistence.manifest_dict_config_filter import ManifestDictConfigFilter
from neuro_san.internals.graph.persistence.manifest_key_config_filter import ManifestKeyConfigFilter
from neuro_san.internals.graph.persistence.raw_manifest_restorer import RawManifestRestorer
from neuro_san.internals.graph.persistence.served_manifest_config_filter import ServedManifestConfigFilter
from pyparsing.exceptions import ParseException

from coded_tools.agent_network_editor.constants import SUBNETWORK_NAMES
from coded_tools.agent_network_editor.constants import SUBNETWORKS
from coded_tools.agent_network_editor.sly_data_lock import SlyDataLock

DEFAULT_MANIFEST_FILE = os.path.join("registries", "manifest_and.hocon")
logger = logging.getLogger(__name__)


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
    internal `AgentNetworkStorage` directly.

    The static helper `get_subnetwork_names()` is preserved for callers that do not
    have access to a run_context (e.g. middleware classes).
    """

    @staticmethod
    async def get_subnetwork_names(sly_data: dict[str, Any]) -> list[str]:
        """
        Get the list of subnetwork names from the **designer manifest** only.

        Used by callers (e.g. middleware) that need to validate subnetwork references
        but do not have access to a run_context. Reads only the manifest HOCON, not
        each subnetwork's HOCON.

        :param sly_data: The sly_data dictionary from the agent hierarchy. Acts as a
                per-session cache via the `SUBNETWORK_NAMES` and `SUBNETWORKS` keys.
                A `SlyDataLock` named "subnetwork_names_lock" is acquired here so
                concurrent intra-session callers don't both parse the manifest.
        :return: List of subnetwork name strings (in "/<network_name>" form), or an
                empty list if the manifest is missing or fails to parse. Empty results
                are cached too so we don't keep retrying.
        """
        # Lock per-sly_data so two concurrent intra-session callers don't both parse
        # the manifest. Lock name is distinct from get_subnetworks() so the two methods
        # don't block each other.
        async with await SlyDataLock.get_lock(sly_data, "subnetwork_names_lock"):
            # Per-session cache hit: if the full subnetwork dict was already loaded by
            # get_subnetworks(), reuse its keys instead of re-reading the manifest.
            if SUBNETWORKS in sly_data:
                return list(sly_data[SUBNETWORKS].keys())
            if SUBNETWORK_NAMES in sly_data:
                return sly_data[SUBNETWORK_NAMES]

            # We use a designer-specific env var (rather than AGENT_MANIFEST_FILE) so the designer's
            # subnetwork pool can be a narrow, curated subset of what the server hosts — e.g. only
            # industry/ + generated/ networks, not basic/, tools/, experimental/, or the
            # designer-family agents themselves. Default points at manifest_and.hocon which composes
            # just those two via `include`.
            manifest_file: str = os.getenv("AGENT_NETWORK_DESIGNER_MANIFEST_FILE") or DEFAULT_MANIFEST_FILE

            logger.info(">>>>>>>>>>>>>>>>>>>Getting Subnetwork Names from Manifest>>>>>>>>>>>>>>>>>>>")
            logger.info("Manifest file: %s", manifest_file)

            # Parse the manifest HOCON. pyhocon resolves `include` statements, so composed manifests
            # (e.g. manifest_and.hocon) flatten into a single mapping of
            # "path/to/file.hocon" -> enabled-bool-or-dict entries. RawManifestRestorer returns None
            # if the file is missing — treated as an empty manifest (no subnetworks available).
            names: list[str] = []
            try:
                raw_manifest: dict[str, Any] = await RawManifestRestorer().async_restore(file_reference=manifest_file)
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

                # Derive external network names ("/<network_name>") via the canonical mapper used by
                # neuro-san (matches RegistryManifestRestorer.find_external_network_names).
                agent_mapper = AgentFileTreeMapper()
                for manifest_key in one_manifest.keys():
                    agent_filepath: str = agent_mapper.agent_name_to_filepath(manifest_key)
                    network_name: str = agent_mapper.filepath_to_agent_network_name(agent_filepath)
                    names.append(f"/{network_name}")
            except ParseException as parse_error:
                logger.warning(
                    "Failed to parse manifest '%s', no subnetwork names will be available: %s",
                    manifest_file,
                    parse_error,
                )

            sly_data[SUBNETWORK_NAMES] = names
        return names

    async def get_subnetworks(self, sly_data: dict[str, Any]) -> dict[str, Any]:
        """
        Return the {/<name>: front-man-description} mapping shown to the designer LLM.

        For each name from the designer manifest, we open an `AsyncAgentSession` to that
        agent and call its `function({})` endpoint to get the front-man's function spec
        (the same JSON-schema-ish structure the LLM sees when wiring tools). The session
        is created via `invocation_context.get_async_session_factory().create_session()`
        — the same hook `CallAgent` uses, and the framework decides whether to dispatch
        in-process (direct mode) or via loopback HTTP (server mode) based on the factory's
        `use_direct` setting.

        :param sly_data: sly_data dict; result is cached at `sly_data[SUBNETWORKS]` and a
                `SlyDataLock` named "subnetworks_lock" is held during the load.
        :return: dict mapping "/<network_name>" -> front-man's function.description.
                Networks that fail to respond, return no front man, or have an empty
                description are still included with an empty-string value so the LLM
                at least sees the name. May be an empty dict if no names or no
                run_context.
        """
        # Lock per-sly_data so two concurrent intra-session callers don't both do the work
        # (e.g. when a parent tool fans out via asyncio.gather and several writers each
        # transitively reach get_subnetwork).
        async with await SlyDataLock.get_lock(sly_data, "subnetworks_lock"):
            # Per-session cache hit (including an explicitly cached empty mapping).
            if SUBNETWORKS in sly_data:
                return sly_data[SUBNETWORKS]

            # Get the curated subset of names from the designer manifest. Cheap and cached.
            names: list[str] = await self.get_subnetwork_names(sly_data)
            if not names:
                sly_data[SUBNETWORKS] = {}
                return {}

            # Reach the framework's session factory through run_context.
            # `run_context` is injected by BranchActivation.__init__; if this CodedTool is
            # ever instantiated outside that flow (e.g. tests bypassing __init__), the chain
            # raises AttributeError and we return an empty dict rather than crashing.
            try:
                invocation_context = self.run_context.get_invocation_context()
                factory = invocation_context.get_async_session_factory()
            except AttributeError:
                logger.warning("No invocation context / session factory available; returning empty subnetworks.")
                sly_data[SUBNETWORKS] = {}
                return {}

            subnetworks: dict[str, str] = await self._collect_via_sessions(names, factory, invocation_context)
            sly_data[SUBNETWORKS] = subnetworks
            return subnetworks

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
        # still wire them if it knows what they do. Empty-description entries are
        # cached too, so we don't keep retrying within the session.
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
        return await self.get_subnetworks(sly_data)
