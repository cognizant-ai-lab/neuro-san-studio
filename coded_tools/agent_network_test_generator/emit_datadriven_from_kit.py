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

import logging
import re
from typing import Any
from typing import Union

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.agent_network_editor.and_logger import AndLogger


class EmitDataDrivenFromKit(CodedTool):
    """
    Convert an in-memory neutral ANTeGen kit into DataDriven fixture dictionaries.

    This tool only converts data. The returned fixture dictionaries must be
    validated and passed to ``persist_test_fixture`` by the caller.
    """

    @staticmethod
    def _file_name(scenario_name: str) -> str:
        """
        Convert a scenario name to a snake_case HOCON file name.

        :param scenario_name: The scenario name from the kit entry.
        :return: A lowercased snake_case file name ending in ``.hocon``.
        """
        normalized: str = re.sub(r"[^a-zA-Z0-9]+", "_", scenario_name).strip("_").lower()
        return f"{normalized}.hocon"

    @staticmethod
    def _dropped_fields(capture_spec: dict[str, Any], turns: list[dict[str, Any]]) -> list[str]:
        """
        Identify neutral-kit fields without a DataDriven representation.

        :param capture_spec: Capture specification paired with the scenario.
        :param turns: Scenario turns used to determine represented seed keys.
        :return: Field names that are intentionally not represented in a fixture.
        """
        fields: list[str] = []
        if any(
            isinstance(assertion, dict) and "determinism" in assertion
            for assertion in capture_spec.get("assertions", [])
        ):
            fields.append("determinism")
        if any(
            isinstance(assertion, dict) and isinstance(assertion.get("note"), str) and assertion["note"].strip()
            for assertion in capture_spec.get("assertions", [])
        ):
            fields.append("note")
        fields.extend(key for key in ("capture_per_turn", "stateful", "reset_required") if key in capture_spec)
        seeds: Any = capture_spec.get("sly_data_seeds", {})
        if isinstance(seeds, dict):
            represented_keys: set[str] = set()
            for turn in turns:
                turn_seeds: Any = turn.get("seeds", {})
                if isinstance(turn_seeds, dict):
                    represented_keys.update(turn_seeds)
            fields.extend(f"sly_data_seeds.{key}" for key in sorted(set(seeds) - represented_keys))
        return fields

    @staticmethod
    def _select_entries(
        kit: Any,
        requested_names: Any,
    ) -> tuple[list[Any] | None, str | None]:
        """
        Validate kit selection arguments and return the selected entries.

        :param kit: Candidate in-memory kit from ``sly_data``.
        :param requested_names: Optional scenario-name filter from tool arguments.
        :return: Selected entries and an error string, if validation fails.
        """
        if not isinstance(kit, dict) or not isinstance(kit.get("tests"), list):
            return None, "Error: sly_data['antegen_test_kit'] must be a dictionary with a tests list."
        if requested_names in (None, []):
            selected_names: set[str] | None = None
        elif not isinstance(requested_names, list) or any(
            not isinstance(name, str) or not name.strip() for name in requested_names
        ):
            return None, "Error: 'scenario_names' must be a list of non-empty strings."
        else:
            selected_names = set(requested_names)
        entries: list[Any] = kit["tests"]
        if selected_names is None:
            return entries, None
        available_names: set[str] = {
            entry["scenario_name"]
            for entry in entries
            if isinstance(entry, dict) and isinstance(entry.get("scenario_name"), str)
        }
        missing_names: set[str] = selected_names - available_names
        if missing_names:
            return None, f"Error: scenario_names not found in kit: {sorted(missing_names)}."
        return [
            entry for entry in entries if isinstance(entry, dict) and entry.get("scenario_name") in selected_names
        ], None

    @staticmethod
    def _entry_parts(
        entry: Any,
        index: int,
    ) -> tuple[str | None, dict[str, Any] | None, dict[str, Any] | None, str | None]:
        """
        Validate the required fields used to convert one kit entry.

        :param entry: Candidate kit entry containing scenario and capture data.
        :param index: Zero-based entry index for conversion error paths.
        :return: Scenario name, scenario, capture spec, and an error string.
        """
        path: str = f"tests[{index}]"
        if not isinstance(entry, dict):
            return None, None, None, f"{path} must be a dictionary."
        scenario_name: Any = entry.get("scenario_name")
        scenario: Any = entry.get("scenario")
        capture_spec: Any = entry.get("capture_spec")
        if not isinstance(scenario_name, str) or not scenario_name.strip():
            return None, None, None, f"{path}.scenario_name must be a non-empty string."
        if entry.get("scenario_format") != "antegen_neutral":
            return scenario_name, None, None, f"{path}.scenario_format must be 'antegen_neutral'."
        if not isinstance(scenario, dict):
            return scenario_name, None, None, f"{path}.scenario must be a dictionary."
        if not isinstance(capture_spec, dict):
            return scenario_name, None, None, f"{path}.capture_spec must be a dictionary."
        return scenario_name, scenario, capture_spec, None

    @staticmethod
    def _valid_turns(scenario: dict[str, Any], path: str) -> tuple[list[dict[str, Any]], list[str]]:
        """
        Validate scenario turns and preserve their order.

        :param scenario: Neutral scenario to convert.
        :param path: Human-readable kit-entry path.
        :return: Valid turns and any turn-shape errors.
        """
        turns: Any = scenario.get("turns")
        if not isinstance(turns, list):
            return [], [f"{path}.scenario.turns must be a list."]
        valid_turns: list[dict[str, Any]] = []
        errors: list[str] = []
        for turn_index, turn in enumerate(turns):
            if not isinstance(turn, dict):
                errors.append(f"{path}.scenario.turns[{turn_index}] must be a dictionary.")
            elif not isinstance(turn.get("text"), str):
                errors.append(f"{path}.scenario.turns[{turn_index}].text must be a string.")
            else:
                valid_turns.append(turn)
        return valid_turns, errors

    @staticmethod
    def _response_for_turn(
        assertions: list[Any],
        turn_number: int,
        path: str,
    ) -> tuple[dict[str, Any], list[str]]:
        """
        Convert assertions targeting one turn into a fixture response.

        :param assertions: Capture-spec assertions for the scenario.
        :param turn_number: One-based scenario turn number.
        :param path: Human-readable kit-entry path.
        :return: Response dictionary and conversion errors.
        """
        response: dict[str, Any] = {}
        seen_assertions: set[tuple[str, str]] = set()
        errors: list[str] = []
        targeted = False
        for assertion_index, assertion in enumerate(assertions):
            if not isinstance(assertion, dict) or assertion.get("turn") != turn_number:
                continue
            targeted = True
            target: Any = assertion.get("target")
            test_name: Any = assertion.get("test")
            if not isinstance(target, str) or not isinstance(test_name, str):
                errors.append(f"{path}.capture_spec.assertions[{assertion_index}] must have string target and test.")
                continue
            collision_key: tuple[str, str] = (target, test_name)
            if collision_key in seen_assertions:
                errors.append(
                    f"{path}.capture_spec.assertions has a collision for turn {turn_number}, "
                    f"target '{target}', test '{test_name}'."
                )
                continue
            seen_assertions.add(collision_key)
            expected: Any = assertion.get("expected")
            if target == "response.text":
                response.setdefault("text", {})[test_name] = expected
            elif target.startswith("response.structure.") and target.removeprefix("response.structure."):
                structure_key: str = target.removeprefix("response.structure.")
                response.setdefault("structure", {}).setdefault(structure_key, {})[test_name] = expected
            else:
                errors.append(
                    f"{path}.capture_spec.assertions target '{target}' is not convertible to a fixture response."
                )
        if not targeted:
            errors.append(f"{path}.scenario.turns[{turn_number - 1}] has no targeted assertions.")
        return response, errors

    @staticmethod
    def _interaction(
        turn: dict[str, Any],
        turn_index: int,
        response: dict[str, Any],
        timeout_values: list[Any],
        path: str,
    ) -> tuple[dict[str, Any] | None, str | None]:
        """
        Build one DataDriven interaction from a scenario turn.

        :param turn: Neutral scenario turn.
        :param turn_index: Zero-based turn index.
        :param response: Converted assertion response block.
        :param timeout_values: Optional capture-spec timeout values.
        :param path: Human-readable kit-entry path.
        :return: Interaction and an error string, if conversion fails.
        """
        interaction: dict[str, Any] = {
            "text": turn["text"],
            "timeout_in_seconds": 120,
            "response": response,
        }
        if "seeds" in turn:
            if not isinstance(turn["seeds"], dict):
                return None, f"{path}.scenario.turns[{turn_index}].seeds must be a dictionary."
            if turn["seeds"]:
                interaction["sly_data"] = turn["seeds"]
        if turn_index < len(timeout_values):
            try:
                interaction["timeout_in_seconds"] = int(timeout_values[turn_index])
            except (TypeError, ValueError):
                return (
                    None,
                    f"{path}.capture_spec.suggested_timeout_seconds[{turn_index}] must be integer-convertible.",
                )
        return interaction, None

    @staticmethod
    def _entry_data(
        entry: Any,
        index: int,
    ) -> tuple[dict[str, Any] | None, str | None]:
        """
        Validate and collect the fields needed to convert one kit entry.

        :param entry: Candidate kit entry containing scenario and capture data.
        :param index: Zero-based entry index for conversion error paths.
        :return: Conversion inputs and an error string, if validation fails.
        """
        scenario_name, scenario, capture_spec, error = EmitDataDrivenFromKit._entry_parts(entry, index)
        if scenario_name is None or scenario is None or capture_spec is None:
            return None, error
        path: str = f"tests[{index}]"
        agent: Any = scenario.get("agent")
        attempts: Any = scenario.get("attempts")
        required_passes: Any = scenario.get("required_passes")
        assertions: Any = capture_spec.get("assertions")
        if not isinstance(agent, str) or not agent.strip():
            error = f"{path}.scenario.agent must be a non-empty string."
        elif not isinstance(attempts, int) or isinstance(attempts, bool):
            error = f"{path}.scenario.attempts must be an integer."
        elif not isinstance(required_passes, int) or isinstance(required_passes, bool):
            error = f"{path}.scenario.required_passes must be an integer."
        elif not isinstance(assertions, list):
            error = f"{path}.capture_spec.assertions must be a list."
        if error is not None:
            return None, error
        turns, turn_errors = EmitDataDrivenFromKit._valid_turns(scenario, path)
        if turn_errors:
            error = " ".join(turn_errors)
        timeout_values: Any = capture_spec.get("suggested_timeout_seconds", [])
        if timeout_values is None:
            timeout_values = []
        if not isinstance(timeout_values, list):
            error = f"{path}.capture_spec.suggested_timeout_seconds must be a list."
        if error is not None:
            return None, error
        return {
            "scenario_name": scenario_name,
            "agent": agent,
            "attempts": attempts,
            "required_passes": required_passes,
            "capture_spec": capture_spec,
            "assertions": assertions,
            "turns": turns,
            "timeout_values": timeout_values,
        }, None

    @staticmethod
    def _converted_interactions(
        turns: list[dict[str, Any]],
        assertions: list[Any],
        timeout_values: list[Any],
        path: str,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """
        Convert all scenario turns into DataDriven interactions.

        :param turns: Validated neutral scenario turns.
        :param assertions: Capture-spec assertions for the scenario.
        :param timeout_values: Optional capture-spec timeout values.
        :param path: Human-readable kit-entry path.
        :return: Converted interactions and conversion errors.
        """
        interactions: list[dict[str, Any]] = []
        errors: list[str] = []
        for assertion_index, assertion in enumerate(assertions):
            assertion_turn: Any = assertion.get("turn") if isinstance(assertion, dict) else None
            if (
                not isinstance(assertion_turn, int)
                or isinstance(assertion_turn, bool)
                or not 1 <= assertion_turn <= len(turns)
            ):
                errors.append(
                    f"{path}.capture_spec.assertions[{assertion_index}].turn has invalid value "
                    f"{assertion_turn!r}; expected an integer within 1..{len(turns)}."
                )
        for turn_index, turn in enumerate(turns):
            response, response_errors = EmitDataDrivenFromKit._response_for_turn(assertions, turn_index + 1, path)
            errors.extend(response_errors)
            if not response:
                continue
            interaction, interaction_error = EmitDataDrivenFromKit._interaction(
                turn, turn_index, response, timeout_values, path
            )
            if interaction_error is not None:
                errors.append(interaction_error)
            elif interaction is not None:
                interactions.append(interaction)
        return interactions, errors

    @staticmethod
    def _convert_entry(
        entry: Any,
        index: int,
    ) -> tuple[dict[str, Any] | None, str | None, dict[str, Any] | None]:
        """
        Convert one neutral kit entry into a DataDriven fixture.

        :param entry: Candidate kit entry containing scenario and capture data.
        :param index: Zero-based entry index for conversion error paths.
        :return: Fixture data, an error message, and dropped-field metadata.
        """
        path: str = f"tests[{index}]"
        data, error = EmitDataDrivenFromKit._entry_data(entry, index)
        if data is None:
            return None, error, None
        scenario_name: str = data["scenario_name"]
        capture_spec: dict[str, Any] = data["capture_spec"]
        turns: list[dict[str, Any]] = data["turns"]
        dropped: dict[str, Any] = {
            "scenario_name": scenario_name,
            "fields": EmitDataDrivenFromKit._dropped_fields(capture_spec, turns),
        }
        interactions, errors = EmitDataDrivenFromKit._converted_interactions(
            turns, data["assertions"], data["timeout_values"], path
        )
        if errors:
            return None, " ".join(errors), dropped
        fixture: dict[str, Any] = {
            "agent": data["agent"],
            "success_ratio": f"{data['required_passes']}/{data['attempts']}",
            "interactions": interactions,
        }
        return fixture, None, dropped

    @staticmethod
    def _assemble_result(entries: list[Any]) -> dict[str, Any]:
        """
        Convert entries and assemble fixtures, dropped fields, and errors.

        :param entries: Selected kit entries in their original order.
        :return: The converter result dictionary.
        """
        fixtures: list[dict[str, Any]] = []
        dropped: list[dict[str, Any]] = []
        errors: list[str] = []
        for index, entry in enumerate(entries):
            fixture, error, dropped_entry = EmitDataDrivenFromKit._convert_entry(entry, index)
            if dropped_entry is not None:
                dropped.append(dropped_entry)
            if error is not None:
                errors.append(error)
            elif fixture is not None and dropped_entry is not None:
                fixtures.append(
                    {
                        "scenario_name": dropped_entry["scenario_name"],
                        "file_name": EmitDataDrivenFromKit._file_name(dropped_entry["scenario_name"]),
                        "test_fixture": fixture,
                    }
                )
        return {"fixtures": fixtures, "dropped": dropped, "errors": errors}

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> Union[dict[str, Any], str]:
        """
        Convert selected kit entries into DataDriven fixture dictionaries.

        :param args: A dictionary that may contain ``scenario_names``, a list
                of scenario names to convert; an absent or empty list converts all.
        :param sly_data: Shared private agent data containing
                ``antegen_test_kit``.
        :return: Conversion results with fixtures, dropped fields, and errors,
                or an error string when the kit or arguments are malformed.
        """
        logger = AndLogger(logging.getLogger(self.__class__.__name__))
        requested_names: Any = args.get("scenario_names")
        entries, selection_error = EmitDataDrivenFromKit._select_entries(
            sly_data.get("antegen_test_kit"), requested_names
        )
        if selection_error is not None:
            return selection_error
        if entries is None:
            return "Error: No kit entries were selected."
        result: dict[str, Any] = EmitDataDrivenFromKit._assemble_result(entries)
        logger.info(">>>>>>>>>>>>>>>>>>>Emitting DataDriven Fixtures>>>>>>>>>>>>>>>>>>")
        logger.info("Fixture count: %d; error count: %d", len(result["fixtures"]), len(result["errors"]))
        logger.info(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
        return result
