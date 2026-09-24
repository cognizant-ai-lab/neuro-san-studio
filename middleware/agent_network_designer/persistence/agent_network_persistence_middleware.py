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

from datetime import datetime
from datetime import timezone
from logging import getLogger
from os import environ
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware import AgentState
from langchain.agents.middleware import hook_config
from langchain.messages import AIMessage
from langchain.messages import HumanMessage
from langgraph.runtime import Runtime
from neuro_san.interfaces.reservationist import Reservationist
from neuro_san.internals.validation.network.unreachable_nodes_network_validator import UnreachableNodesNetworkValidator

from coded_tools.agent_network_editor.and_logger import AndLogger
from coded_tools.agent_network_editor.connectivity_dictionary_converter import ConnectivityDictionaryConverter
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_DEFINITION
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_HOCON_TEXT
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_METADATA
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_NAME
from coded_tools.agent_network_editor.get_mcp_tool import GetMcpTool
from coded_tools.agent_network_editor.get_subnetwork import GetSubnetwork
from coded_tools.agent_network_editor.mcp_header_hygiene import McpHeaderHygiene
from coded_tools.agent_network_editor.mcp_servers_load import McpServersLoad
from coded_tools.agent_network_query_generator.set_sample_queries import AGENT_NETWORK_QUERIES
from middleware.agent_network_designer.agent_network_definition_middleware import SKIP_DESIGNER
from middleware.agent_network_designer.persistence.agent_network_assembler import AgentNetworkAssembler
from middleware.agent_network_designer.persistence.agent_network_metadata_block import AgentNetworkMetadataBlock
from middleware.agent_network_designer.persistence.agent_network_persistor import AgentNetworkPersistor
from middleware.agent_network_designer.persistence.agent_network_persistor_factory import AgentNetworkPersistorFactory
from middleware.agent_network_designer.persistence.file_system_agent_network_persistor import DEFAULT_SUBDIRECTORY
from middleware.agent_network_designer.persistence.hocon_agent_network_assembler import HoconAgentNetworkAssembler
from middleware.agent_network_designer.validation.agent_network_instructions_validation_middleware import (
    AgentNetworkInstructionsValidationMiddleware,
)
from middleware.agent_network_designer.validation.agent_network_structure_validation_middleware import (
    AgentNetworkStructureValidationMiddleware,
)

# To use reservations, turn this environment variable to true
WRITE_TO_FILE: bool = environ.get("AGENT_NETWORK_DESIGNER_USE_RESERVATIONS", "false").lower() != "true"

# Set this to False if the agents are grounded and don't need demo mode instructions
DEMO_MODE: bool = environ.get("AGENT_NETWORK_DESIGNER_DEMO_MODE", "true").lower() == "true"

# Subdirectory under registries directory where networks are saved when using file persistence.
SUBDIRECTORY: str = environ.get("AGENT_NETWORK_DESIGNER_SUBDIRECTORY", DEFAULT_SUBDIRECTORY)

# Default number of validation retry rounds when the env var is unset or unparseable.
DEFAULT_MAX_VALIDATION_ATTEMPTS: int = 3


class AgentNetworkPersistenceMiddleware(AgentMiddleware):
    """
    Middleware that validates and persists an agent network after the agent finishes
    (i.e., no more tool calls are pending).

    If an agent network definition is present in sly_data, runs structural and instruction
    validators against it. If validation errors are found, a human message containing the
    errors is injected and control jumps back to the model so it can self-correct.

    If no agent network definition is present, this middleware does nothing and returns None,
    allowing the agent to respond freely. This handles cases where loading failed upstream
    (e.g., in AgentNetworkDefinitionMiddleware) and the agent needs to report that error
    rather than produce a network definition.

    In reservations mode a third outcome exists: when the persistor reports that the temporary
    network could not be deployed, the turn ends with an error message for the client, the
    HOCON text and the metadata block are still published, and only agent_reservations is
    withheld (issue #1425, see aafter_agent and _deploy_error_response).

    Note: Validation is intentionally duplicated here even though individual subnetworks
    already perform their own validation. This is a safeguard for cases where the agent
    returns a final response without having called the necessary tools or subnetworks —
    meaning the subnetwork validators may never have run. By validating in this middleware,
    we catch those premature completions and force the agent to correct itself.
    """

    def __init__(self, reservationist: Reservationist, sly_data: dict[str, Any]) -> None:
        """
        Initialize agent network persistence middleware.

        :param reservationist: Reservationist interface for making reservations on temporary networks
        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                This dictionary is largely to be treated as read-only.
                It is possible to add key/value pairs to this dict that do not
                yet exist as a bulletin board, as long as the responsibility
                for which coded_tool publishes new entries is well understood
                by the agent chain implementation and the coded_tool implementation
                adding the data is not invoke()-ed more than once.

                Keys expected for this implementation are:
                    "agent_network_definition": an outline of an agent network
                    "agent_network_name": the name to save the network under (optional)
                    "agent_network_queries": sample queries generated on this turn (optional)
                    "agent_network_metadata": the network's metadata block as the client
                        received it after the previous save (optional, issue #1398)
        """
        self.logger: AndLogger = AndLogger(getLogger(self.__class__.__name__))
        self.reservationist = reservationist
        self.sly_data = sly_data
        # Maximum number of validation retry rounds before bailing without persisting.
        # Parsed per-instance so a bad env var degrades this one session, not the whole server.
        raw_max: str = environ.get(
            "AGENT_NETWORK_DESIGNER_MAX_VALIDATION_ATTEMPTS", str(DEFAULT_MAX_VALIDATION_ATTEMPTS)
        )
        try:
            self.max_validation_attempts: int = max(0, int(raw_max))
        except ValueError:
            self.logger.warning(
                "Invalid AGENT_NETWORK_DESIGNER_MAX_VALIDATION_ATTEMPTS=%r; falling back to %d.",
                raw_max,
                DEFAULT_MAX_VALIDATION_ATTEMPTS,
            )
            self.max_validation_attempts = DEFAULT_MAX_VALIDATION_ATTEMPTS
        # Counts validation rounds that failed in this session, used to cap retries.
        self._validation_attempts: int = 0

    # Reenter the agent loop at the model node if validation fails.
    # If no agent network definition is present, return None to let the agent respond freely.
    # If the temporary-network deploy fails, end the turn with an error message and no jump (issue #1425).
    # See https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/user_guide.md#middleware and
    # https://reference.langchain.com/python/langchain/agents/middleware/types/hook_config for details on
    # hook_config and jump_to.
    @hook_config(can_jump_to=["model"])
    async def aafter_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        """
        Validate and persist the agent network after the agent finishes.

        Called when the agent has no more pending tool calls. If an agent network definition
        is present in sly_data, runs structure and instruction validators against it. If any
        errors are found, injects a human message with the errors and jumps back to the model
        so it can self-correct. If no definition is present, returns None so the agent can
        respond freely (e.g., to report a loading error from AgentNetworkDefinitionMiddleware).
        In reservations mode a deployment the persistor reported as failed ends the turn with
        an error message appended for the client; the HOCON text and the metadata block are
        still published, since they describe the design rather than the deploy, and only
        agent_reservations is withheld, see _deploy_error_response (issue #1425).

        This validation acts as a final safety net: even if the agent bypassed calling
        the necessary tools or subnetworks (and thus their built-in validators never ran),
        errors will still be caught here before the network is persisted.

        :param state: Current agent state
        :param runtime: Runtime context
        :return: Dict with error message and jump directive on a validation failure, dict with
                the error message alone on a failed deployment, or None otherwise
        """
        network_def: dict[str, Any] = self.sly_data.get(AGENT_NETWORK_DEFINITION)
        agent_network_name: str = self.sly_data.get(AGENT_NETWORK_NAME)
        # Only validate and persist if there is an agent_network_definition with a valid name; otherwise let
        # the agent respond to the user freely. This allows the agent to ask clarifying questions or report
        # issues without being forced to produce a network definition — for example, when
        # AgentNetworkDefinitionMiddleware failed to load from a HOCON file or S3 reservation and
        # already reported the error (jumping to end), so no network definition will be present.
        # A valid name is also required for file path and reservation name construction.
        if network_def and agent_network_name and isinstance(agent_network_name, str):
            structure_errors, instructions_errors = await self._validate_network(network_def)
            if structure_errors or instructions_errors:
                self.logger.warning("Validation errors: %s", structure_errors + instructions_errors)
                # Bail out if we've already retried the max number of times. Returning None
                # ends the session without persisting; the agent's last message reaches the user.
                # Prevents runaway loops when the model can't fix the errors (e.g., the required
                # tool was silently dropped from the tools array under load).
                if self._validation_attempts >= self.max_validation_attempts:
                    self.logger.warning(
                        "Reached max validation attempts (%d); ending without persisting.",
                        self.max_validation_attempts,
                    )
                    return None
                self._validation_attempts += 1
                self.logger.warning(
                    "Invoking agent network designer to fix the issues (attempt %d/%d).",
                    self._validation_attempts,
                    self.max_validation_attempts,
                )
                message_parts: list[str] = []
                if structure_errors:
                    message_parts.append(
                        f"The agent network definition has structural issues: {structure_errors}. "
                        "Call `agent_network_editor` to fix these structural problems."
                    )
                if instructions_errors:
                    message_parts.append(
                        f"The agent network definition has instructions-related issues: {instructions_errors}. "
                        "Call `agent_network_instructions_editor` to fix these instructions problems."
                    )
                if structure_errors and instructions_errors:
                    message_parts.append(
                        "Fix the structural issues first by calling `agent_network_editor`, "
                        "then address the instructions issues with `agent_network_instructions_editor`."
                    )
                return self._error_response(" ".join(message_parts))

            # Validation succeeded. Reset the counter so a later turn in the same session
            # (e.g., a follow-up modification) gets its own full retry budget.
            self._validation_attempts = 0

            sample_queries: list[str] = self.sly_data.get(AGENT_NETWORK_QUERIES, [])

            # None means the save happened; a str is the deploy error the reservations persistor reported.
            deploy_error: str | None = await self._assemble_and_persist(
                network_def, agent_network_name, sample_queries
            )

            agent_progress_style: str = environ.get("AGENT_NETWORK_DESIGNER_PROGRESS_STYLE", "internal")

            # Pre-warm the shared ToolboxFactory off the event loop before the
            # sync export below converts to connectivity style. In the normal
            # designer flow ProgressHandler has already done this while
            # reporting progress, but a skip_designer run never reports
            # progress, so on a cold process the from_dict() fallback inside
            # the export would otherwise pay the one-time toolbox file read
            # and HOCON parse on the event loop.
            if agent_progress_style == "connectivity":
                await ConnectivityDictionaryConverter.get_shared_toolbox_factory()
            # The export runs on a deploy error too: the definition handed back describes the network
            # the client asked for and is what it needs to retry the save; it does not depend on the
            # deploy. Only agent_reservations is withheld, see _assemble_and_persist.
            self._determine_exported_network_definition(self.sly_data, agent_progress_style)

            self.logger.debug(">>>>>>>>>>>>>>>>>>> DONE %s !!!>>>>>>>>>>>>>>>>>>", self.__class__.__name__)

            if deploy_error is not None:
                return self._deploy_error_response(deploy_error)

        return None

    def _error_response(self, content: str) -> dict[str, Any]:
        """Return a jump-to-model response with the given error content."""
        # Set the skip designer value to False to prevent infinite loop since jumping to model actually jump to the
        # before model method in AgentNetworkDefinitionMiddleware, which jumps back to here if skip designer is True.
        # This is also an indicator for client that there are issues with input agent_network_definition and that the
        # designer has made changes to the definition.
        if self.sly_data.get(SKIP_DESIGNER) is True:
            self.sly_data[SKIP_DESIGNER] = False
        return {
            # Use human message to ensure that the model follows the instructions
            "messages": [HumanMessage(content)],
            "jump_to": "model",
        }

    def _deploy_error_response(self, error: str) -> dict[str, Any]:
        """
        Build the state update that tells the client a temporary-network deployment failed.

        The error is appended to the conversation as an AIMessage and becomes the answer of the
        turn: neuro-san takes the last AIMessage of the final state as the agent's reply
        (neuro-san 0.7.4, run_context_runnable.py, find_ai_message).

        Unlike _error_response there is no jump_to: a deployment failure is infrastructure (a
        spec the server rejected, an external network or MCP server that failed the deploy-time
        validation; ReservationUtil.wait_for_one reports these as the error text), which the
        model cannot fix by editing the definition, and a jump to model would re-run
        validation and attempt the same deploy again. For the same reason neither
        _validation_attempts nor SKIP_DESIGNER is touched: the definition was valid and the
        designer changed nothing in it. A "messages" update without "jump_to" is a plain state
        update: the after_agent edge (langchain 1.4.2, agents/factory.py, _add_middleware_edge)
        resolves state.get("jump_to") and falls back to its default destination, the next
        after_agent hook in the chain (AgentNetworkDefinitionMiddleware.aafter_agent in the
        designer registry, which only flushes progress) and from there END, so the run finishes
        without re-entering the model. hook_config(can_jump_to=["model"]) declares the optional
        jump without requiring it.

        :param error: The error text ReservationsAgentNetworkPersistor.async_persist returned
        :return: The state update carrying the error message and nothing else
        """
        return {
            "messages": [
                AIMessage(content=f"Error: the agent network could not be deployed as a temporary network: {error}")
            ],
        }

    async def _validate_network(self, network_def: dict[str, Any]) -> tuple[list[str], list[str]]:
        """
        Run all validators against the network definition, reusing the validation middlewares.

        :return: Tuple of (structure_errors, instructions_errors), each a list of error strings.
        """
        structure_errors: list[str] = await AgentNetworkStructureValidationMiddleware(self.sly_data).validate(
            network_def
        )
        instructions_errors: list[str] = await AgentNetworkInstructionsValidationMiddleware(self.sly_data).validate(
            network_def
        )
        return structure_errors, instructions_errors

    def _client_token_mcp_headers(self, load: McpServersLoad) -> dict[str, list[str]]:
        """
        Map each client-token MCP server to the header names to declare for
        it in the persisted network's sly_data_schema.

        Client-token servers are the ones this conversation supplied auth
        headers for via sly_data (nsflow injects one per connected server
        when chatting with the designer) that are not file-configured. Each
        maps to the usable header names supplied for it (names only, never
        values), so the schema declares the actual headers a server needs
        rather than assuming "Authorization". McpHeaderHygiene.usable_header_names
        owns which names count — stripped, legal field names with non-blank
        values, exactly what the fetch would send — so the persisted schema
        never requires a header that would not actually authenticate.
        sly_data_http_header_urls only yields URLs whose
        sly_data["http_headers"][url] is a dict with at least one such
        name, so the index below is safe and no entry comes out empty.

        When mcp_info.hocon exists but could not be read (loaded_ok False),
        the file-server set is UNKNOWN, so genuinely client-token servers
        cannot be told apart from file-configured-but-unreadable ones. Emit
        no client-token schema in that case rather than bake a wrong
        required-list into the persisted (durable) network; a re-persist
        once the config is fixed produces the correct schema.

        :param load: The mcp_info.hocon load result.
        :return: {server URL: header names}, empty when the file load
                failed or the conversation supplied no client-token server.
        """
        if not load.loaded_ok:
            self.logger.warning(
                "MCP servers info file could not be read; omitting client-token sly_data_schema "
                "from the persisted network until the file is valid again."
            )
            return {}
        client_token_mcp_headers: dict[str, list[str]] = {}
        for url in GetMcpTool.sly_data_http_header_urls(self.sly_data):
            if url not in load.urls:
                client_token_mcp_headers[url] = McpHeaderHygiene.usable_header_names(
                    self.sly_data["http_headers"][url]
                )
        return client_token_mcp_headers

    async def _create_persistor(self) -> tuple[AgentNetworkPersistor, dict[str, list[str]]]:
        """
        Create the persistor for this save, together with the client-token MCP header map the
        assemblers need for the front man's sly_data_schema.

        Split out of _assemble_and_persist so that method stays within pylint's local-variable
        budget after the metadata block handling was added.

        :return: The persistor and the client-token MCP header map (see _client_token_mcp_headers)
        """
        subnetwork_names: list[str] = await GetSubnetwork.get_subnetwork_names()
        load: McpServersLoad = await GetMcpTool.get_mcp_servers_load()
        client_token_mcp_headers: dict[str, list[str]] = self._client_token_mcp_headers(load)
        mcp_servers: list[str] = load.urls + list(client_token_mcp_headers)
        persistor: AgentNetworkPersistor = AgentNetworkPersistorFactory.create_persistor(
            {"reservationist": self.reservationist},
            WRITE_TO_FILE,
            DEMO_MODE,
            SUBDIRECTORY,
            subnetwork_names,
            mcp_servers,
        )
        return persistor, client_token_mcp_headers

    @staticmethod
    def _utc_now_iso() -> str:
        """
        Read the clock for the file-mode timestamps.

        The one place this middleware reads the clock, so a test can pin it. The format is the
        timezone-aware ISO-8601 UTC string the HOCON header always used for date_created.

        :return: The current UTC time as an ISO-8601 string with an explicit offset
        """
        return datetime.now(tz=timezone.utc).isoformat()

    async def _build_metadata(
        self, persistor: AgentNetworkPersistor, agent_network_name: str, sample_queries: list[str]
    ) -> dict[str, Any]:
        """
        Build the metadata block to save.

        The designer is stateless: the block the client sent back under AGENT_NETWORK_METADATA
        (issue #1398) is the base, exactly as it owns the definition and the name. This turn's
        sample queries replace the block's own only when the generator ran. In file mode the
        server stamps date_created once and date_modified on every save; a temporary network
        gets no studio timestamps in its deployed spec (a reservation is a new network on every
        save and neuro-san records its write time as stored_at), only the HOCON text rendered for
        download carries a date_created, added by the HOCON assembler. The caller
        writes the result back to sly_data once the persistor has returned, a rejected
        temporary-network deploy included, so it flows upstream and the client can send it
        again. A client value that is not a dict is ignored with a warning.

        A client that says nothing about the block (key absent or null) predates the contract;
        nsflow's manual save, as of nsflow 0.7.1, is the known case. Erasing the block on its behalf
        would be the very loss this fixes, so the persistor is asked once for the block of the
        network about to be overwritten and that block is the base instead. A client that sends
        the key, even as an empty object, owns the block and nothing is read.

        :param persistor: The persistor this save goes through; the fallback reads the network
                it is about to overwrite (the reservations persistor has none and answers None)
        :param agent_network_name: The raw network name the persistor reads and writes under
        :param sample_queries: The sample queries generated on this turn, [] when none were
        :return: The block to hand to the assemblers
        """
        candidate: Any = self.sly_data.get(AGENT_NETWORK_METADATA)
        source: str = f"sly_data['{AGENT_NETWORK_METADATA}']"
        if candidate is None:
            # Compatibility fallback for clients that predate the key: the only read of the
            # network being saved (manifest and cached config reads are unrelated), and only
            # when the client said nothing.
            candidate = await persistor.async_restore_metadata(agent_network_name)
            source = f"existing network {agent_network_name}"
        block: AgentNetworkMetadataBlock = AgentNetworkMetadataBlock(candidate, source).merge_sample_queries(
            sample_queries
        )
        if WRITE_TO_FILE:
            block.stamp_file_dates(self._utc_now_iso())
        return block.as_dict()

    async def _assemble_and_persist(
        self,
        network_def: dict[str, Any],
        agent_network_name: str,
        sample_queries: list[str],
    ) -> str | None:
        """
        Assemble the agent network, persist it, and then store HOCON text and metadata in sly_data.

        The metadata block is built from what the client sent back (or, for a client that sent
        no block, from the network being overwritten) plus what this turn generated, see
        _build_metadata; it is never regenerated from the definition alone, so a skip_designer
        save or a designer turn that skipped the query generator keeps the block intact.

        HOCON content is always assembled first; it is stored in sly_data for client consumption
        once the persistor has returned, whether or not a temporary network was deployed (see the
        :return: note).
        If WRITE_TO_FILE is True, that same HOCON content is persisted to disk; the subdirectory
        prefix is added by FileSystemAgentNetworkPersistor internally.
        Otherwise, a deployable config is assembled and registered as a temporary network via
        the reservationist interface using the sanitized raw name.

        :param network_def: The validated agent network definition to persist
        :param agent_network_name: The raw network name without any subdirectory prefix.
        :param sample_queries: The sample queries generated on this turn, [] when none were
        :return: None when the save happened. In reservations mode, the error text the persistor
                reported when the temporary network could not be deployed; the HOCON text and the
                metadata block are published all the same, since they describe the design the
                client may download and retry, and only agent_reservations is left unset (issue #1425)
        :raises ValueError: In file mode, when agent_network_name resolves to a file outside the
                generated directory (see FileSystemAgentNetworkPersistor.get_network_file_path)
        """
        self.logger.info(">>>>>>>>>>>>>>>>>>>Assemble and Persist Agent Network>>>>>>>>>>>>>>>>>>")
        self.logger.info("Agent Network Name: %s", agent_network_name)

        persistor: AgentNetworkPersistor
        client_token_mcp_headers: dict[str, list[str]]
        persistor, client_token_mcp_headers = await self._create_persistor()
        top_agent_name: str = UnreachableNodesNetworkValidator().find_all_front_man_agents(network_def).pop()
        # Built once so the HOCON text handed to the client and the persisted content carry one block,
        # and before the write so the fallback read never sees a half-written file. The assemblers run
        # the same merge again on it; that pass is idempotent (nothing new to drop), at most a generated
        # query that cannot be stored is logged once more per assembler. The HOCON assembler alone adds
        # a date_created when the block has none, so the downloadable text always carries a creation
        # date; in file mode the block already has one, in reservations mode the deployed spec keeps none.
        metadata: dict[str, Any] = await self._build_metadata(persistor, agent_network_name, sample_queries)

        # Always assemble HOCON content for client consumption.
        hocon_text: str = await HoconAgentNetworkAssembler(DEMO_MODE).assemble_agent_network(
            network_def,
            top_agent_name,
            agent_network_name,
            sample_queries,
            client_token_mcp_headers=client_token_mcp_headers,
            metadata=metadata,
        )
        self.logger.info("The resulting agent network content: \n %s", hocon_text)
        persisted_content: str | dict[str, Any] = hocon_text

        # Reservations API forbids '/', ':', and ' ' — sanitize the raw name for that case.
        # FileSystemAgentNetworkPersistor handles its own subdirectory prefixing internally.
        file_reference: str = agent_network_name
        if not WRITE_TO_FILE:
            for char in ["/", ":", " "]:
                file_reference = file_reference.replace(char, "")
            # For reservations, assemble a deployable config instead of HOCON.
            assembler: AgentNetworkAssembler = persistor.get_assembler()
            # The persisted content for reservations is config.
            persisted_content = await assembler.assemble_agent_network(
                network_def,
                top_agent_name,
                agent_network_name,
                sample_queries,
                client_token_mcp_headers=client_token_mcp_headers,
                metadata=metadata,
            )
        # Persist the agent network
        persisted_reference: str | list[dict[str, Any]] | None = await persistor.async_persist(
            obj=persisted_content, file_reference=file_reference
        )
        # A str is a success in file mode (the path written) but the deploy error text in reservations
        # mode: ReservationsAgentNetworkPersistor.async_persist hands back what ReservationUtil.wait_for_one
        # reported instead of raising, so the two contracts have to be told apart by mode (issue #1425).
        deploy_error: str | None = None
        if not WRITE_TO_FILE and isinstance(persisted_reference, str):
            deploy_error = persisted_reference
            self.logger.error(
                "Agent network %s could not be deployed as a temporary network: %s",
                agent_network_name,
                deploy_error,
            )
        # Store information on reservations in the sly data; a failed deploy has none to store.
        if isinstance(persisted_reference, list):
            self.sly_data["agent_reservations"] = persisted_reference
        # The HOCON text and the block go back to the client once the persistor has returned. An exception
        # (in file mode, an unwritable path) skips them, so a failed write never hands out a date_modified
        # for a write that did not take place. A rejected deploy returns normally and skips nothing: the
        # text is a required output the client downloads, the block carries this turn's sample queries,
        # which reach the client no other way, and both describe the design, not the deploy, so they stay
        # valid for a retry.
        self.sly_data[AGENT_NETWORK_HOCON_TEXT] = hocon_text
        self.sly_data[AGENT_NETWORK_METADATA] = metadata
        return deploy_error

    def _determine_exported_network_definition(self, sly_data: dict[str, Any], agent_progress_style: str):
        """
        Determine how to export the agent network definition.

        :param sly_data: The sly_data dictionary whose AGENT_NETWORK_DEFINITION
                entry gets rewritten in place.
        :param agent_progress_style: The AGENT_NETWORK_DESIGNER_PROGRESS_STYLE
                env var value, read once by the caller (which also uses it to
                decide whether to pre-warm the shared ToolboxFactory).
        """
        network_definition: dict[str, Any] = sly_data.get(AGENT_NETWORK_DEFINITION)
        use_network_definition: dict[str, Any] | list[dict[str, Any]] = network_definition

        if agent_progress_style == "connectivity":
            # The idea here is that a multi-user MAUI server can turn on this env variable
            # so that agent network progress is converted to connectivity-style data format
            # that it already knows how to render.  Using the different key name allows the AGENT_PROGRESS
            # dictionary to look just like a ConnectivityResponse from the service.
            converter = ConnectivityDictionaryConverter()
            use_network_definition: list[dict[str, Any]] = converter.from_dict(network_definition)

        elif agent_progress_style == "internal":
            # Report the internal structure used by Agent Network Designer and pals.
            # This is what was used in the first iterations with nsflow.
            use_network_definition: dict[str, Any] = network_definition

        sly_data[AGENT_NETWORK_DEFINITION] = use_network_definition
