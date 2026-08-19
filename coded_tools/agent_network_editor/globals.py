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
Inventory of every process-wide global cache in the Agent Network Designer
family: what each one holds, where it lives, how it expires, and who reads it.

Add an entry (comment block + registry triple in ProcessGlobals) whenever a
new process-wide global is introduced. The shared mechanism — locking,
publish ordering, freshness fingerprints, the async once-gate — lives in
shared_process_cache.SharedProcessCache; each cache's policy lives on its
owning class; this module is the map of all of them.

The instances themselves stay on their owners rather than here because each
loader needs its owner's imports (and moving them would create import
cycles); everything below is therefore strings-and-pointers by design, which
also keeps this module (and test collection through it) free of neuro-san
imports.
"""

import sys


class ProcessGlobals:  # pylint: disable=too-few-public-methods
    """
    The registry of process-wide global caches, documented entry by entry
    below, plus the test-only helper that clears them all.
    """

    # -----------------------------------------------------------------------
    # 1. Shared ToolboxFactory
    #    Holds:   a load()-ed neuro-san ContextTypeToolboxFactory used to render
    #             connectivity-style views of agent network definitions.
    #    Lives:   connectivity_dictionary_converter.ConnectivityDictionaryConverter
    #             (async get_shared_toolbox_factory)
    #    Expiry:  none — loaded once; restart to pick up an edited
    #             AGENT_TOOLBOX_INFO_FILE.
    #    Used by: ConnectivityDictionaryConverter.from_dict() (fallback when no
    #             factory was passed in);
    #             progress_handler.ProgressHandler._send_report() (pre-warm before
    #             connectivity conversion);
    #             agent_network_persistence_middleware.AgentNetworkPersistenceMiddleware
    #             .aafter_agent() (pre-warm before the skip_designer-safe export).
    #
    # 2. Shared toolbox info
    #    Holds:   the {tool_name: description} mapping parsed from the designer's
    #             toolbox info file (AGENT_NETWORK_DESIGNER_TOOLBOX_INFO_FILE).
    #    Lives:   get_toolbox.GetToolbox (async get_toolbox_info)
    #    Expiry:  none — loaded once (a missing file is retried, never cached);
    #             restart to pick up edits.
    #    Used by: GetToolbox.async_invoke() (the coded tool the editor LLM calls);
    #             agent_network_structure_validation_middleware
    #             .AgentNetworkStructureValidationMiddleware.validate().
    #
    # 3. Shared subnetwork names
    #    Holds:   the "/<network_name>" list parsed from the designer manifest
    #             (AGENT_NETWORK_DESIGNER_MANIFEST_FILE).
    #    Lives:   get_subnetwork.GetSubnetwork (async get_subnetwork_names)
    #    Expiry:  manifest path/modification_time change, or one
    #             AGENT_MANIFEST_UPDATE_PERIOD_SECONDS period when manifest
    #             updates are enabled — the same setting that drives the
    #             server's own manifest refresh; <= 0 (static server) means no
    #             time-based expiry. The period matters because the manifest
    #             `include`s other manifests a cheap probe cannot see, notably
    #             registries/generated/manifest.hocon which grows as the designer
    #             saves networks on local runs; server deployments never write
    #             the manifest at runtime.
    #    Used by: GetSubnetwork.get_subnetworks() (the coded tool path);
    #             agent_network_structure_validation_middleware
    #             .AgentNetworkStructureValidationMiddleware.validate();
    #             agent_network_persistence_middleware.AgentNetworkPersistenceMiddleware
    #             ._assemble_and_persist().
    #
    # 4. Shared subnetwork descriptions
    #    Holds:   the {/<network_name>: front-man description} mapping shown
    #             to the designer LLM, fetched via one session.function({})
    #             call per subnetwork.
    #    Lives:   get_subnetwork.GetSubnetwork (async get_subnetworks)
    #    Expiry:  the same fingerprint as the subnetwork names above (they
    #             share _manifest_fingerprint), so names and descriptions go
    #             stale and refresh together. Unlike the other caches it has
    #             no loader: descriptions can only be fetched through a live
    #             run_context's session factory, so the first
    #             get_subnetworks() call of each refresh period fills the
    #             cache in-context (SharedProcessCache.aget_or_fill). A fill
    #             whose fetches ALL failed raises instead of publishing —
    #             that failure's recovery is invisible to the fingerprint —
    #             and the cache is bypassed entirely when AGENT_AUTHORIZER
    #             is set, because /function responses are then
    #             caller-specific (see _shared_descriptions_cache_enabled).
    #    Used by: GetSubnetwork.get_subnetworks() (the coded tool path).
    #
    # 5. Shared MCP servers
    #    Holds:   the list of MCP server URLs parsed from mcp_info.hocon
    #             (MCP_SERVERS_INFO_FILE, the cwd scaffold, or the bundled
    #             copy — see GetMcpTool.get_mcp_info_file). Per-conversation
    #             servers supplied via sly_data http_headers are NOT part of
    #             this cache; callers union them in via
    #             GetMcpTool.sly_data_http_header_urls(sly_data).
    #    Lives:   get_mcp_tool.GetMcpTool (async get_mcp_servers)
    #    Expiry:  resolved path or modification_time change — no time bucket, since
    #             nothing writes the file at runtime.
    #    Used by: GetMcpTool (input to the tool-descriptions cache below);
    #             agent_network_structure_validation_middleware
    #             .AgentNetworkStructureValidationMiddleware.validate();
    #             agent_network_persistence_middleware.AgentNetworkPersistenceMiddleware
    #             ._assemble_and_persist().
    #
    # 6. Shared MCP tool descriptions
    #    Holds:   the {server URL: tool descriptions} mapping fetched from
    #             the file-configured MCP servers themselves (network
    #             calls). Listings for per-conversation sly_data servers
    #             are deliberately NOT cached here — their auth headers
    #             belong to one conversation, and a process-wide entry
    #             would serve one user's authenticated listing to every
    #             other (see GetMcpTool._fetch_sly_data_tool_descriptions).
    #    Lives:   get_mcp_tool.GetMcpTool (async get_mcp_tool_descriptions)
    #    Expiry:  mcp_info.hocon path/modification_time change, or one
    #             AGENT_NETWORK_DESIGNER_MCP_TOOLS_TTL_SECONDS window
    #             (default 300s, clamped to at least twice the per-server
    #             fetch cap; <= 0 disables time-based refresh) — the
    #             sources are external servers with no local change signal,
    #             so the TTL is both the freshness bound and the recovery
    #             bound after a failed or partial fetch. With time-based
    #             refresh disabled, an all-failed fetch raises instead of
    #             publishing, so recovery stays possible.
    #    Used by: GetMcpTool.async_invoke() (the coded tool the editor LLM
    #             calls).
    #
    # 7. Shared external-agents catalog
    #    Holds:   the toggleable external-agent catalog parsed from
    #             EXTERNAL_AGENTS_FILE (default
    #             middleware/agent_network_designer/external_agents.hocon).
    #    Lives:   external_agents_middleware.ExternalAgentsMiddleware
    #    Expiry:  catalog path/modification_time change — no time bucket,
    #             since nothing writes the file at runtime. A failed load is
    #             never published (fail-closed errors recur until the file is
    #             fixed, then the next call recovers).
    #    Used by: ExternalAgentsMiddleware.awrap_model_call() (tool stripping
    #             + instruction injection) and awrap_tool_call()
    #             (execution-time denial of disabled module tools).
    #
    # 8. Shared middleware info catalog
    #    Holds:   the middleware allow-list catalog parsed from
    #             MIDDLEWARE_INFO_FILE (default
    #             middleware/agent_network_designer/middleware_info.hocon).
    #    Lives:   middleware_info_middleware.MiddlewareInfoMiddleware
    #    Expiry:  catalog path/modification_time change — no time bucket,
    #             since nothing writes the file at runtime (a missing or
    #             broken file is retried, never cached).
    #    Used by: MiddlewareInfoMiddleware.awrap_model_call() (system-prompt
    #             injection for the middleware_manager subnetwork).
    # -----------------------------------------------------------------------

    # Machine-readable registry of the entries above, as
    # (module, class, test-only clear method) triples consumed by
    # clear_all_for_testing() below.
    REGISTRY: list[tuple[str, str, str]] = [
        (
            "coded_tools.agent_network_editor.connectivity_dictionary_converter",
            "ConnectivityDictionaryConverter",
            "clear_shared_toolbox_factory_for_testing",
        ),
        (
            "coded_tools.agent_network_editor.get_toolbox",
            "GetToolbox",
            "clear_shared_toolbox_info_for_testing",
        ),
        (
            "coded_tools.agent_network_editor.get_subnetwork",
            "GetSubnetwork",
            "clear_shared_subnetwork_names_for_testing",
        ),
        (
            "coded_tools.agent_network_editor.get_subnetwork",
            "GetSubnetwork",
            "clear_shared_subnetwork_descriptions_for_testing",
        ),
        (
            "coded_tools.agent_network_editor.get_mcp_tool",
            "GetMcpTool",
            "clear_shared_mcp_servers_for_testing",
        ),
        (
            "coded_tools.agent_network_editor.get_mcp_tool",
            "GetMcpTool",
            "clear_shared_mcp_tool_descriptions_for_testing",
        ),
        (
            "middleware.agent_network_designer.external_agents_middleware",
            "ExternalAgentsMiddleware",
            "clear_shared_catalog_for_testing",
        ),
        (
            "middleware.agent_network_designer.middleware_info_middleware",
            "MiddlewareInfoMiddleware",
            "clear_shared_info_for_testing",
        ),
    ]

    @staticmethod
    def clear_all_for_testing():
        """
        Clear every cache registered in REGISTRY. For test isolation only
        (tests/conftest.py runs this around every test).

        Production code must never call this: each cache is deliberately
        load-once (or self-expiring) per the policies above. Each captures file
        and env-var state at its first load, so without clearing between tests a
        test that populates one would leak that state into every later test in
        the same process, producing order-dependent results.

        Modules are looked up via sys.modules instead of imported directly so a
        test run that never touches these classes doesn't pay for importing
        neuro-san internals, and pytest collection stays light. A module absent
        from sys.modules was never imported, so its cache cannot be populated —
        skipping it is correct, not merely convenient. A typo'd class or method
        name still fails loudly via getattr whenever the module IS loaded.
        """
        for module_name, class_name, clear_method_name in ProcessGlobals.REGISTRY:
            module = sys.modules.get(module_name)
            if module is not None:
                getattr(getattr(module, class_name), clear_method_name)()
