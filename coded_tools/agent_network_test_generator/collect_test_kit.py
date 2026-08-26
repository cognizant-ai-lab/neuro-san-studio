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

import json
import logging
from typing import Any
from typing import Union

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.agent_network_editor.and_logger import AndLogger

ANTEGEN_TEST_KIT: str = "antegen_test_kit"
KIT_VERSION: int = 1
SCENARIO_FORMAT: str = "neuro_san_data_driven"
NEUTRAL_SCENARIO_FORMAT: str = "antegen_neutral"
SUPPORTED_SCENARIO_FORMATS: frozenset[str] = frozenset({SCENARIO_FORMAT, NEUTRAL_SCENARIO_FORMAT})


class CollectTestKit(CodedTool):
    """
    CodedTool that collects validated scenarios and capture specs into one in-memory kit.

    Invoke this tool exactly once per run. It publishes the kit to
    ``sly_data["antegen_test_kit"]`` and returns the same dictionary; it never
    writes files. Errors are returned as ``"Error: ..."`` strings.
    """

    @staticmethod
    def _error(message: str) -> str:
        """
        Format a collector error consistently with sibling coded tools.

        :param message: The specific validation or serialization problem.
        :return: A prefixed error message.
        """
        return f"Error: {message}"

    @staticmethod
    def _validate_entry(
        test_entry: Any,
        index: int,
        required_keys: frozenset[str],
        scenario_names: set[str],
    ) -> str | None:
        """
        Validate one test-kit entry and record its scenario name.

        :param test_entry: Candidate scenario and capture-spec entry.
        :param index: Zero-based entry index for error paths.
        :param required_keys: Exactly the keys permitted in each entry.
        :param scenario_names: Previously seen scenario names.
        :return: An error message, or None when the entry is valid.
        """
        path: str = f"tests[{index}]"
        error: str | None = None
        if not isinstance(test_entry, dict):
            error = f"{path} must be a dictionary."
        else:
            unexpected_keys: set[str] = set(test_entry) - required_keys
            missing_keys: set[str] = required_keys - set(test_entry)
            if missing_keys:
                error = f"{path} is missing required keys: {sorted(missing_keys)}."
            elif unexpected_keys:
                error = f"{path} has unexpected keys: {sorted(unexpected_keys)}."
            else:
                scenario_name: Any = test_entry["scenario_name"]
                if not isinstance(scenario_name, str) or not scenario_name.strip():
                    error = f"{path}.scenario_name must be a non-empty string."
                elif scenario_name in scenario_names:
                    error = f"Duplicate scenario_name: '{scenario_name}'."
                elif not isinstance(test_entry["scenario"], dict):
                    error = f"{path}.scenario must be a dictionary."
                elif not isinstance(test_entry["scenario_format"], str) or not test_entry["scenario_format"].strip():
                    error = f"{path}.scenario_format must be a non-empty string."
                elif test_entry["scenario_format"] not in SUPPORTED_SCENARIO_FORMATS:
                    error = f"{path}.scenario_format must be one of {sorted(SUPPORTED_SCENARIO_FORMATS)}."
                elif not isinstance(test_entry["capture_spec"], dict):
                    error = f"{path}.capture_spec must be a dictionary."
                else:
                    scenario_names.add(scenario_name)
        return error

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> Union[dict[str, Any], str]:
        """
        Build and publish the in-memory ANTeGen test kit.

        :param args: A dictionary containing ``agent`` (the network name without
                ``.hocon``) and ``tests`` (a list, or a JSON string containing a
                list, of scenario entries).
        :param sly_data: Shared private agent data where the kit is published.
        :return: The kit dictionary on success, or an ``"Error: ..."`` string.

        This tool must be invoked once per run. It writes nothing to disk because
        the published sly_data crosses a gRPC boundary and must remain plain JSON.
        """
        agent: Any = args.get("agent")
        if not isinstance(agent, str) or not agent.strip():
            return self._error("'agent' must be a non-empty string.")
        tests: Any = args.get("tests")
        if isinstance(tests, str):
            try:
                tests = json.loads(tests)
            except json.JSONDecodeError as exc:
                return self._error(f"'tests' is not valid JSON: {exc.msg}.")
        if not isinstance(tests, list) or not tests:
            return self._error("'tests' must be a non-empty list of test entries.")
        required_keys: frozenset[str] = frozenset({"scenario_name", "scenario", "scenario_format", "capture_spec"})
        scenario_names: set[str] = set()
        for index, test_entry in enumerate(tests):
            entry_error: str | None = self._validate_entry(test_entry, index, required_keys, scenario_names)
            if entry_error is not None:
                return self._error(entry_error)
        kit: dict[str, Any] = {"kit_version": KIT_VERSION, "agent": agent, "tests": tests}
        try:
            json.dumps(kit)
        except TypeError as exc:
            return self._error(
                "The test kit is not JSON-serializable because sly_data crosses a gRPC boundary; "
                f"only plain JSON types are allowed ({exc})."
            )
        logger = AndLogger(logging.getLogger(self.__class__.__name__))
        logger.info(">>>>>>>>>>>>>>>>>>>Collecting ANTeGen Test Kit>>>>>>>>>>>>>>>>>>")
        logger.info("Agent: %s; scenario count: %d", agent, len(tests))
        sly_data[ANTEGEN_TEST_KIT] = kit
        logger.info(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
        return kit
