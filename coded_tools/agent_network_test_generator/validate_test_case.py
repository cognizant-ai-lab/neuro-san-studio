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
from typing import Any
from typing import Union

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.agent_network_editor.and_logger import AndLogger
from coded_tools.agent_network_test_generator.stock_test_constants import _FORBIDDEN_RUNTIME_KEYS
from coded_tools.agent_network_test_generator.validate_capture_spec import ValidateCaptureSpec

_NEUTRAL_SCENARIO_FORMAT: str = "antegen_neutral"
_ALLOWED_NEUTRAL_SCENARIO_KEYS: frozenset[str] = frozenset({"agent", "attempts", "required_passes", "turns"})
_ALLOWED_NEUTRAL_TURN_KEYS: frozenset[str] = frozenset({"text", "seeds"})


class ValidateTestCase(CodedTool):
    """
    CodedTool that validates a complete neutral scenario and capture specification.

    Returns a result dictionary with ``valid`` (bool) and, when invalid,
    an ``errors`` list describing every problem found. The frontman agent
    can feed these errors back to the neutral test-case builder for correction.
    """

    @staticmethod
    def _check_positive_integer(value: Any, path: str, errors: list[str]) -> None:
        """
        Validate one positive integer in a neutral scenario.

        :param value: Candidate integer value.
        :param path: Human-readable field path.
        :param errors: Accumulator list; new errors are appended in-place.
        """
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            errors.append(f"{path} must be a positive integer, got: {value!r}.")

    def _validate_neutral_scenario(
        self,
        scenario: dict[str, Any],
        capture_spec: Any,
    ) -> dict[str, Any]:
        """
        Validate a framework-agnostic neutral scenario.

        :param scenario: Neutral scenario dictionary to validate.
        :param capture_spec: Paired capture specification, when provided.
        :return: A validation result with any discovered errors.
        """
        errors: list[str] = []
        for key in ("agent", "attempts", "required_passes", "turns"):
            if key not in scenario:
                errors.append(f"Missing required neutral scenario key: '{key}'.")
        for key in scenario:
            if key not in _ALLOWED_NEUTRAL_SCENARIO_KEYS:
                errors.append(
                    f"Unexpected neutral scenario key: '{key}'. "
                    f"Allowed keys are: {sorted(_ALLOWED_NEUTRAL_SCENARIO_KEYS)}."
                )

        agent: Any = scenario.get("agent")
        if not isinstance(agent, str) or not agent.strip():
            errors.append(f"'agent' must be a non-empty string, got: {agent!r}.")

        attempts: Any = scenario.get("attempts")
        required_passes: Any = scenario.get("required_passes")
        self._check_positive_integer(attempts, "'attempts'", errors)
        self._check_positive_integer(required_passes, "'required_passes'", errors)
        if (
            isinstance(attempts, int)
            and not isinstance(attempts, bool)
            and isinstance(required_passes, int)
            and not isinstance(required_passes, bool)
            and required_passes > attempts
        ):
            errors.append(
                f"'required_passes' must be less than or equal to 'attempts', "
                f"got required_passes={required_passes}, attempts={attempts}."
            )

        turns: Any = scenario.get("turns")
        if not isinstance(turns, list) or not turns:
            errors.append("'turns' must be a non-empty list of dictionaries.")
        else:
            for index, turn in enumerate(turns):
                self._check_neutral_turn(turn, index, errors)

        fuzzy = False
        if isinstance(capture_spec, dict):
            assertions: Any = capture_spec.get("assertions")
            if isinstance(assertions, list):
                fuzzy = any(
                    isinstance(assertion, dict) and assertion.get("determinism") == "fuzzy" for assertion in assertions
                )
        expected_attempts, expected_passes = (3, 2) if fuzzy else (1, 1)
        if attempts != expected_attempts or required_passes != expected_passes:
            errors.append(
                "Neutral scenario 'attempts' and 'required_passes' must be "
                f"{expected_attempts} and {expected_passes} based on capture-spec assertion determinism; "
                f"got attempts={attempts!r}, required_passes={required_passes!r}."
            )
        return {"valid": False, "errors": errors} if errors else {"valid": True}

    @staticmethod
    def _check_neutral_turn(turn: Any, index: int, errors: list[str]) -> None:
        """
        Validate one turn in a neutral scenario.

        :param turn: Candidate turn value.
        :param index: Zero-based turn index.
        :param errors: Accumulator list; new errors are appended in-place.
        """
        path = f"turns[{index}]"
        if not isinstance(turn, dict):
            errors.append(f"{path} must be a dictionary.")
            return
        if "text" not in turn:
            errors.append(f"{path}: missing required key 'text'.")
        elif not isinstance(turn["text"], str) or not turn["text"].strip():
            errors.append(f"{path}.text must be a non-empty string, got: {turn['text']!r}.")
        for key in turn:
            if key not in _ALLOWED_NEUTRAL_TURN_KEYS:
                errors.append(
                    f"{path}: unexpected key '{key}'. Allowed keys are: {sorted(_ALLOWED_NEUTRAL_TURN_KEYS)}."
                )
        seeds: Any = turn.get("seeds")
        if seeds is not None:
            if not isinstance(seeds, dict):
                errors.append(f"{path}.seeds must be a dictionary, got: {type(seeds).__name__}.")
            else:
                for seed_key in seeds:
                    if seed_key in _FORBIDDEN_RUNTIME_KEYS:
                        errors.append(
                            f"{path}.seeds: '{seed_key}' is a runtime-managed key that coded tools "
                            "handle automatically. Remove it from seeds."
                        )

    @staticmethod
    def _append_validation_errors(
        errors: list[str],
        label: str,
        result: dict[str, Any],
    ) -> None:
        """
        Add one validation half's errors while retaining each original message.

        :param errors: Combined error accumulator.
        :param label: Name of the validation half.
        :param result: Result returned by that validation half.
        """
        if not result.get("valid"):
            errors.extend(f"{label}: {message}" for message in result.get("errors", []))

    @staticmethod
    def _check_scenario_format(args: dict[str, Any], errors: list[str]) -> None:
        """
        Validate that the combined validator is being used for a neutral case.

        :param args: The complete built test-case object.
        :param errors: Combined error accumulator.
        """
        if "scenario_format" not in args:
            errors.append("scenario: missing required key 'scenario_format'.")
            return
        scenario_format: Any = args["scenario_format"]
        if not isinstance(scenario_format, str) or not scenario_format.strip():
            errors.append("scenario: 'scenario_format' must be a non-empty string.")
        elif scenario_format != _NEUTRAL_SCENARIO_FORMAT:
            errors.append("scenario: 'scenario_format' must be 'antegen_neutral'.")

    def _validate_scenario_half(self, args: dict[str, Any], errors: list[str]) -> Any:
        """
        Validate the neutral scenario half.

        :param args: The complete built test-case object.
        :param errors: Combined error accumulator.
        :return: The scenario input when provided.
        """
        scenario: Any = args.get("scenario")
        if "scenario" not in args:
            errors.append("scenario: missing required 'scenario'.")
        elif not isinstance(scenario, dict):
            errors.append("scenario: 'scenario' must be a dictionary.")
        else:
            self._check_scenario_format(args, errors)
            if args.get("scenario_format") == _NEUTRAL_SCENARIO_FORMAT:
                result = self._validate_neutral_scenario(scenario, args.get("capture_spec"))
                self._append_validation_errors(errors, "scenario", result)
        return scenario

    async def _validate_capture_half(
        self,
        args: dict[str, Any],
        scenario: Any,
        sly_data: dict[str, Any],
        errors: list[str],
    ) -> None:
        """
        Validate the neutral capture-spec half against the scenario.

        :param args: The complete built test-case object.
        :param scenario: The scenario input from the built object.
        :param sly_data: Shared private agent data.
        :param errors: Combined error accumulator.
        """
        if args.get("scenario_format") != _NEUTRAL_SCENARIO_FORMAT:
            return
        capture_spec: Any = args.get("capture_spec")
        if "capture_spec" not in args:
            errors.append("capture_spec: missing required 'capture_spec'.")
        elif not isinstance(capture_spec, dict):
            errors.append("capture_spec: 'capture_spec' must be a dictionary.")
        elif not isinstance(scenario, dict):
            return
        else:
            capture_args: dict[str, Any] = {
                "capture_spec": capture_spec,
                "scenario": scenario,
                "scenario_format": _NEUTRAL_SCENARIO_FORMAT,
            }
            capture_result = await ValidateCaptureSpec().async_invoke(capture_args, sly_data)
            self._append_validation_errors(errors, "capture_spec", capture_result)

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> Union[dict[str, Any], str]:
        """
        Validate one complete neutral test-case object.

        :param args: A dictionary containing ``scenario``, ``scenario_format``,
                and ``capture_spec`` from one neutral test-case builder result.
        :param sly_data: Shared private agent data; unused by this validator.
        :return: ``{"valid": True}`` or ``{"valid": False, "errors": [...]}``.
        """
        logger = AndLogger(logging.getLogger(self.__class__.__name__))

        if "test_fixture" in args:
            return {
                "valid": False,
                "errors": ["validate_test_case accepts neutral scenario payloads only; use validate_test_fixture."],
            }

        errors: list[str] = []
        scenario = self._validate_scenario_half(args, errors)
        await self._validate_capture_half(args, scenario, sly_data, errors)

        if errors:
            logger.warning("Validation failed with %d error(s).", len(errors))
            for error in errors:
                logger.warning("  - %s", error)
            return {"valid": False, "errors": errors}

        logger.info("Validation PASSED")
        return {"valid": True}
