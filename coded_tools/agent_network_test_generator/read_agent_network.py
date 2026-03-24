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

import ast
import asyncio
import logging
import os
import re
import textwrap
from typing import Any
from typing import Union

from leaf_common.persistence.easy.easy_hocon_persistence import EasyHoconPersistence
from neuro_san.interfaces.coded_tool import CodedTool

# Root directory where all coded tool Python modules are located.
_CODED_TOOLS_DIR: str = "coded_tools"

# Method names that are pure boilerplate wrappers and carry no useful
# information for the LLM when generating test expectations.
_SKIP_METHODS: frozenset[str] = frozenset({"async_invoke"})


class ReadAgentNetwork(CodedTool):
    """
    CodedTool implementation that reads a target agent network HOCON file
    and returns a structured summary of its agents, instructions, metadata,
    sample queries, and sly_data schemas suitable for generating test cases.
    """

    @staticmethod
    def _extract_agent_info(tool: dict[str, Any]) -> dict[str, Any]:
        """
        Extract relevant information from a single tool/agent definition.

        :param tool: A single tool definition dictionary from the network HOCON.
        :return: A dictionary summarising the agent's key attributes.
        """
        # Start with the agent/tool name — the only required field.
        agent_info: dict[str, Any] = {
            "name": tool.get("name", ""),
        }

        # Include the agent's system-level instructions if present.
        if tool.get("instructions"):
            agent_info["instructions"] = tool["instructions"]

        # Extract fields from the "function" block (description, parameters,
        # and any declared sly_data schema).
        function_def: dict[str, Any] = tool.get("function", {})
        if function_def.get("description"):
            agent_info["description"] = function_def["description"]
        if function_def.get("parameters"):
            agent_info["parameters"] = function_def["parameters"]
        if function_def.get("sly_data_schema"):
            agent_info["sly_data_schema"] = function_def["sly_data_schema"]

        # Capture which sub-tools this agent can call.
        if tool.get("tools"):
            agent_info["tools"] = tool["tools"]
        # Capture the coded tool class reference (e.g. "accountant.Accountant")
        # so downstream logic can resolve and read its Python source.
        if tool.get("class"):
            agent_info["class"] = tool["class"]
        # Capture any toolbox reference (e.g. MCP or external tool integrations).
        if tool.get("toolbox"):
            agent_info["toolbox"] = tool["toolbox"]

        return agent_info

    # Regex pattern matching logger.debug / logger.info / logger.warning lines.
    _LOGGER_LINE_RE: re.Pattern[str] = re.compile(r"^\s*logger\.\w+\(.*\)\s*$")

    @staticmethod
    def _extract_essential_source(source: str) -> str:
        """Strip boilerplate from coded-tool source, keeping only the class body.

        Uses the :mod:`ast` module to parse the source and rebuild a
        compact version that contains:

        * Class-level constants and assignments (e.g. ``SHOPS = [...]``).
        * ``__init__`` when it initialises instance state used by ``invoke``.
        * ``invoke`` — the core business-logic method.
        * Any helper methods called by ``invoke`` (private or otherwise).

        The following are **stripped out** to reduce token count:

        * License / copyright comment block.
        * Module-level imports and logger declarations.
        * ``async_invoke`` (always a trivial wrapper around ``invoke``).
        * Docstrings inside methods (verbose param descriptions add no value).
        * ``logger.debug`` / ``logger.info`` / ``logger.warning`` lines.

        :param source: Full Python source code of a coded-tool module.
        :return: A compact version of the source retaining only the
            essential class body, or the original *source* unchanged if
            parsing fails.
        """
        try:
            tree: ast.Module = ast.parse(source)
        except SyntaxError:
            # If the source cannot be parsed, return it unchanged so the
            # LLM still has *something* to work with.
            return source

        lines: list[str] = source.splitlines()
        parts: list[str] = []

        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            # Emit the class declaration line (e.g. "class OrderAPI(CodedTool):").
            parts.append(lines[node.lineno - 1])

            # Collect all method names in this class so we can decide
            # whether async_invoke is redundant (has a matching invoke)
            # or is the sole entry point and must be kept.
            method_names: set[str] = {
                child.name
                for child in ast.iter_child_nodes(node)
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            has_invoke: bool = "invoke" in method_names

            for child in ast.iter_child_nodes(node):
                # Keep class-level assignments (constants like SHOPS, FIRST_ORDER_ID).
                if isinstance(child, (ast.Assign, ast.AnnAssign)):
                    snippet = textwrap.dedent("\n".join(lines[child.lineno - 1 : child.end_lineno]))
                    parts.append("    " + snippet.strip())
                    continue

                # Keep methods except those in _SKIP_METHODS.
                # Only skip async_invoke when a separate invoke exists;
                # otherwise async_invoke IS the main logic (e.g. Accountant).
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if child.name in _SKIP_METHODS and has_invoke:
                        continue
                    method_lines = lines[child.lineno - 1 : child.end_lineno]
                    cleaned = ReadAgentNetwork._strip_method_noise(method_lines, child)
                    parts.append(textwrap.dedent("\n".join(cleaned)))

        return "\n\n".join(parts) if parts else source

    @staticmethod
    def _strip_method_noise(
        method_lines: list[str],
        node: ast.FunctionDef,
    ) -> list[str]:
        """Remove docstrings and logger calls from a method's source lines.

        :param method_lines: The raw source lines for the method
            (including the ``def`` line).
        :param node: The AST node for the method, used to locate the
            docstring via ``ast.get_docstring``.
        :return: A filtered list of source lines with docstrings and
            logger calls removed.
        """
        result: list[str] = []

        # Determine the line range of the docstring (if any) so we can
        # skip those lines entirely.  The docstring is always the first
        # statement in the method body.
        docstring_start: int = -1
        docstring_end: int = -1
        if ast.get_docstring(node) is not None:
            first_stmt = node.body[0]
            docstring_start = first_stmt.lineno
            docstring_end = first_stmt.end_lineno or first_stmt.lineno

        # The method_lines are 0-indexed but AST lineno is 1-indexed.
        # method_lines[0] corresponds to node.lineno.
        base_lineno: int = node.lineno

        for i, line in enumerate(method_lines):
            abs_lineno = base_lineno + i

            # Skip docstring lines.
            if docstring_start <= abs_lineno <= docstring_end:
                continue

            # Skip logger.debug / logger.info / logger.warning lines.
            if ReadAgentNetwork._LOGGER_LINE_RE.match(line):
                continue

            result.append(line)

        return result

    @staticmethod
    def _resolve_coded_tool_source(class_ref: str, agent_name: str) -> str:
        """
        Attempt to locate and read the Python source code for a coded tool class.

        The method tries several candidate paths under ``coded_tools/`` that
        mirror the resolution strategies used by the neuro-san runtime.

        :param class_ref: The dot-separated class reference from the HOCON
            (e.g. ``"accountant.Accountant"``).
        :param agent_name: The agent network name used to derive parent
            directories (e.g. ``"basic/coffee_finder_advanced"``).
        :return: The source code of the coded tool, or an empty string if the
            file could not be found.
        """
        # Split the class reference into module path and class name.
        # e.g. "accountant.Accountant" -> module_path="accountant", class="Accountant"
        # e.g. "experimental.kwik_agents.list_topics.ListTopics"
        #       -> module_path="experimental/kwik_agents/list_topics", class="ListTopics"
        parts: list[str] = class_ref.rsplit(".", 1)
        if len(parts) < 2:
            return ""
        # Convert the dot-separated module path to a filesystem path with .py extension.
        module_path: str = parts[0].replace(".", os.sep) + ".py"

        # Derive the parent directory from the agent network name.
        # e.g. "basic/coffee_finder_advanced" -> parent_dir="basic"
        parent_dir: str = os.path.dirname(agent_name)

        # Try multiple candidate paths to locate the source file.
        # This mirrors how neuro-san resolves coded tool classes at runtime:
        #   1. coded_tools/<parent_dir>/<module>.py
        #      e.g. coded_tools/basic/accountant.py
        #   2. coded_tools/<parent_dir>/<network_name>/<module>.py
        #      e.g. coded_tools/basic/coffee_finder_advanced/time_tool.py
        #   3. coded_tools/<module>.py (fully qualified path)
        #      e.g. coded_tools/experimental/kwik_agents/list_topics.py
        candidates: list[str] = [
            os.path.join(_CODED_TOOLS_DIR, parent_dir, module_path),
            os.path.join(_CODED_TOOLS_DIR, parent_dir, agent_name.split("/")[-1], module_path),
            os.path.join(_CODED_TOOLS_DIR, module_path),
        ]

        logger = logging.getLogger("ReadAgentNetwork")
        for candidate in candidates:
            if os.path.isfile(candidate):
                logger.info("Found coded tool source: %s", candidate)
                try:
                    with open(candidate, "r", encoding="utf-8") as source_file:
                        return source_file.read()
                except OSError:
                    continue
        return ""

    def invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> Union[dict[str, Any], str]:
        """
        Reads the specified agent network HOCON file and extracts relevant
        information for test case generation.

        :param args: A dictionary with the following keys:
                "agent_network_hocon_file": the path to the agent network HOCON file
                    relative to the registries directory (e.g., "basic/coffee_finder_advanced.hocon").

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                Keys expected for this implementation are:
                    None

        :return:
            In case of successful execution:
                A dictionary containing the full agent network summary.
            otherwise:
                A text string error message.
        """
        logger = logging.getLogger(self.__class__.__name__)

        hocon_file: str = args.get("agent_network_hocon_file", "")
        if not hocon_file:
            return "Error: No 'agent_network_hocon_file' provided."

        # The user may pass a path with or without the "registries/" prefix.
        # Normalise so it always starts with "registries/" for EasyHoconPersistence.
        if not hocon_file.startswith("registries/"):
            hocon_file = "registries/" + hocon_file

        logger.info(">>>>>>>>>>>>>>>>>>>Reading Agent Network HOCON>>>>>>>>>>>>>>>>>>")
        logger.info("HOCON file: %s", hocon_file)

        # Parse the HOCON file into a Python dictionary.
        try:
            hocon = EasyHoconPersistence(full_ref=hocon_file, must_exist=True)
            network_hocon: dict[str, Any] = hocon.restore()
        except (FileNotFoundError, TypeError) as exc:
            error_msg = f"Error: Could not read HOCON file '{hocon_file}': {exc}"
            logger.error(error_msg)
            return error_msg

        # Derive the agent network name from the file path.
        # e.g. "registries/basic/coffee_finder_advanced.hocon"
        #       -> "basic/coffee_finder_advanced"
        agent_name: str = hocon_file.replace("registries/", "").replace(".hocon", "")

        # Extract a structured summary for each agent/tool in the network.
        agents_summary: list[dict[str, Any]] = [
            self._extract_agent_info(tool) for tool in network_hocon.get("tools", [])
        ]

        # Read the Python source code for every coded tool referenced in the
        # network.  This gives the LLM visibility into the exact runtime
        # behaviour (e.g. that Accountant adds 3.0 per call) so it can
        # generate accurate test expectations.
        coded_tool_sources: dict[str, str] = self._read_all_coded_tool_sources(
            network_hocon.get("tools", []), agent_name, logger
        )

        # Assemble the result dictionary returned to the frontman agent.
        result: dict[str, Any] = {
            "agent_name": agent_name,
            "metadata": network_hocon.get("metadata", {}),
            "agents": agents_summary,
        }
        if coded_tool_sources:
            result["coded_tool_sources"] = coded_tool_sources

        # Store key data in sly_data so the persist_test_fixture tool can
        # access the target agent name without it appearing in the chat stream.
        sly_data["target_agent_name"] = agent_name

        logger.info(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
        logger.info("Extracted %d agents from network '%s'", len(agents_summary), agent_name)
        return result

    @staticmethod
    def _read_all_coded_tool_sources(
        tools: list[dict[str, Any]],
        agent_name: str,
        logger: logging.Logger,
    ) -> dict[str, str]:
        """
        Read Python source code for every coded tool referenced in the network.

        :param tools: The list of tool definition dictionaries from the HOCON.
        :param agent_name: The agent network name for path resolution.
        :param logger: Logger instance.
        :return: A mapping of class references to their source code.
        """
        sources: dict[str, str] = {}
        for tool in tools:
            class_ref: str = tool.get("class", "")
            # Skip tools without a class reference (pure LLM agents) and
            # avoid reading the same source file twice.
            if not class_ref or class_ref in sources:
                continue
            raw_source: str = ReadAgentNetwork._resolve_coded_tool_source(class_ref, agent_name)
            if raw_source:
                # Strip boilerplate (license, imports, async_invoke) to
                # reduce the token payload sent to downstream LLM agents.
                sources[class_ref] = ReadAgentNetwork._extract_essential_source(raw_source)
                logger.info("Loaded source for coded tool: %s", class_ref)
            else:
                logger.warning("Could not find source for coded tool: %s", class_ref)
        return sources

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> Union[dict[str, Any], str]:
        """Run invoke asynchronously."""
        return await asyncio.to_thread(self.invoke, args, sly_data)
