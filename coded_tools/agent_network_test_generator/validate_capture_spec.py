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
from coded_tools.agent_network_test_generator.stock_test_constants import _KEYWORD_STOCK_TESTS
from coded_tools.agent_network_test_generator.stock_test_constants import _MAX_KEYWORD_WORDS
from coded_tools.agent_network_test_generator.stock_test_constants import _NUMERIC_STOCK_TESTS
from coded_tools.agent_network_test_generator.stock_test_constants import _VALID_STOCK_TESTS

_ALLOWED_CAPTURE_SPEC_KEYS: frozenset[str] = frozenset(
    {
        "turn_count",
        "sly_data_seeds",
        "stateful",
        "reset_required",
        "capture_per_turn",
        "assertions",
        "suggested_timeout_seconds",
    }
)
_CAPTURE_SPEC_TYPES: dict[str, type] = {
    "turn_count": int,
    "sly_data_seeds": dict,
    "stateful": bool,
    "reset_required": list,
    "capture_per_turn": list,
    "assertions": list,
    "suggested_timeout_seconds": list,
}
_ALLOWED_CAPTURE_FIELDS: frozenset[str] = frozenset(
    {"response_text", "response_structure", "sly_data_after", "elapsed_seconds", "error"}
)
_ALLOWED_ASSERTION_KEYS: frozenset[str] = frozenset({"turn", "target", "test", "determinism", "note", "expected"})
_FUZZY_STOCK_TESTS: frozenset[str] = frozenset({"gist", "not_gist"})
_VALID_DETERMINISM: frozenset[str] = frozenset({"deterministic", "fuzzy"})
_RESPONSE_TEXT_TARGET: str = "response.text"
_RESPONSE_STRUCTURE_PREFIX: str = "response.structure."
_NEUTRAL_SCENARIO_FORMAT: str = "antegen_neutral"


class ValidateCaptureSpec(CodedTool):
    """
    CodedTool that validates the runner-facing parts of a neutral capture spec.

    The result contains ``valid`` and, when invalid, an ``errors`` list with every
    discovered problem so the capture-spec writer can correct them in one retry.
    """

    @staticmethod
    def _check_top_level(capture_spec: dict[str, Any], errors: list[str]) -> None:
        """
        Validate required capture-spec keys and their top-level types.

        :param capture_spec: The capture specification to validate.
        :param errors: Accumulator list; new errors are appended in-place.
        """
        for key in sorted(_ALLOWED_CAPTURE_SPEC_KEYS):
            if key not in capture_spec:
                errors.append(f"Missing required capture_spec key: '{key}'.")
                continue
            value = capture_spec[key]
            if key == "turn_count" and (not isinstance(value, int) or isinstance(value, bool) or value < 1):
                errors.append(f"'turn_count' must be an integer greater than or equal to 1, got: {value!r}.")
                continue
            if not isinstance(value, _CAPTURE_SPEC_TYPES[key]):
                errors.append(f"'{key}' must be a {_CAPTURE_SPEC_TYPES[key].__name__}, got: {type(value).__name__}.")
        for key in capture_spec:
            if key not in _ALLOWED_CAPTURE_SPEC_KEYS:
                errors.append(
                    f"Unexpected capture_spec key: '{key}'. Allowed keys are: {sorted(_ALLOWED_CAPTURE_SPEC_KEYS)}."
                )

    @staticmethod
    def _check_expected(expected: Any, path: str, test_name: str, errors: list[str]) -> None:
        """
        Validate the expected value type for one stock test.

        :param expected: Expected assertion value.
        :param path: Human-readable assertion path.
        :param test_name: Stock-test name.
        :param errors: Accumulator list; new errors are appended in-place.
        """
        if test_name in _NUMERIC_STOCK_TESTS:
            if isinstance(expected, int) and not isinstance(expected, bool):
                errors.append(
                    f"{path}.expected.{test_name}: numeric value must be a float, not an int. "
                    f"Use {float(expected)} instead of {expected}."
                )
            elif (
                test_name in {"value", "not_value"}
                and not isinstance(expected, float)
                and (not isinstance(expected, str) or not expected.strip())
            ):
                errors.append(
                    f"{path}.expected.{test_name}: expected value must be a float or non-empty string, "
                    f"got: {expected!r}."
                )
            elif test_name not in {"value", "not_value"} and not isinstance(expected, float):
                errors.append(f"{path}.expected.{test_name}: expected value must be a float, got: {expected!r}.")
            return
        if test_name not in _KEYWORD_STOCK_TESTS and test_name not in _FUZZY_STOCK_TESTS:
            return
        if (
            not isinstance(expected, list)
            or not expected
            or any(not isinstance(item, str) or not item.strip() for item in expected)
        ):
            errors.append(
                f"{path}.expected.{test_name}: expected value must be a non-empty list of non-empty strings."
            )
            return
        if test_name in _KEYWORD_STOCK_TESTS:
            for phrase_index, phrase in enumerate(expected):
                if len(phrase.split()) > _MAX_KEYWORD_WORDS:
                    errors.append(
                        f"{path}.expected.{test_name}[{phrase_index}]: keyword has {len(phrase.split())} words "
                        f"(max {_MAX_KEYWORD_WORDS}). Keywords must be short distinctive phrases, not full "
                        "sentences. Use `gist` for full-sentence meaning checks."
                    )

    @staticmethod
    def _check_assertion_semantics(
        assertion: dict[str, Any],
        path: str,
        test_name: str,
        errors: list[str],
    ) -> None:
        """
        Validate determinism, notes, and expected values for one assertion.

        :param assertion: Assertion dictionary to inspect.
        :param path: Human-readable assertion path.
        :param test_name: Valid stock-test name.
        :param errors: Accumulator list; new errors are appended in-place.
        """
        determinism: Any = assertion.get("determinism")
        if determinism not in _VALID_DETERMINISM:
            errors.append(f"{path}.determinism must be one of {sorted(_VALID_DETERMINISM)}, got: {determinism!r}.")
        else:
            required = "fuzzy" if test_name in _FUZZY_STOCK_TESTS else "deterministic"
            if determinism != required:
                reason = (
                    "gist tests are LLM-judged" if required == "fuzzy" else "this stock test is mechanically evaluated"
                )
                errors.append(f"{path}.determinism must be '{required}' for '{test_name}' because {reason}.")
        note: Any = assertion.get("note")
        if "note" in assertion and (not isinstance(note, str) or not note.strip()):
            errors.append(f"{path}.note must be a non-empty string when provided.")
        if determinism == "fuzzy" and (not isinstance(note, str) or not note.strip()):
            errors.append(
                f"{path}.note is required for fuzzy assertions to explain why a failure may not be a regression."
            )
        if "expected" in assertion:
            ValidateCaptureSpec._check_expected(assertion["expected"], path, test_name, errors)

    @staticmethod
    def _check_assertion(assertion: Any, index: int, turn_count: Any, errors: list[str]) -> None:
        """
        Validate the shape and location of one assertion.

        :param assertion: Candidate assertion value.
        :param index: Zero-based assertion index.
        :param turn_count: Capture-spec turn count, when valid.
        :param errors: Accumulator list; new errors are appended in-place.
        """
        path = f"assertions[{index}]"
        if not isinstance(assertion, dict):
            errors.append(f"{path} must be a dictionary.")
            return
        for key in ("turn", "target", "test", "determinism", "expected"):
            if key not in assertion:
                errors.append(f"{path} is missing required key '{key}'.")
        for key in assertion:
            if key not in _ALLOWED_ASSERTION_KEYS:
                errors.append(
                    f"{path} has unexpected key '{key}'. Allowed keys are: {sorted(_ALLOWED_ASSERTION_KEYS)}."
                )

        turn: Any = assertion.get("turn")
        valid_turn_count = isinstance(turn_count, int) and not isinstance(turn_count, bool) and turn_count >= 1
        if not isinstance(turn, int) or isinstance(turn, bool):
            errors.append(f"{path}.turn must be an integer, got: {turn!r}.")
        elif valid_turn_count and not 1 <= turn <= turn_count:
            errors.append(f"{path}.turn must be between 1 and {turn_count!r}, got: {turn}.")

        target: Any = assertion.get("target")
        valid_target = target == _RESPONSE_TEXT_TARGET
        if isinstance(target, str) and target.startswith(_RESPONSE_STRUCTURE_PREFIX):
            field_name = target[len(_RESPONSE_STRUCTURE_PREFIX) :]
            valid_target = bool(field_name) and "." not in field_name
        if not valid_target:
            errors.append(
                f"{path}.target must be exactly 'response.text' or 'response.structure.<key>' "
                f"with a one-level non-empty key, got: {target!r}."
            )

        test_name: Any = assertion.get("test")
        if not isinstance(test_name, str) or test_name not in _VALID_STOCK_TESTS:
            errors.append(
                f"{path}.test must be a valid stock test. Valid tests are: {sorted(_VALID_STOCK_TESTS)}; "
                f"got: {test_name!r}."
            )
            return
        ValidateCaptureSpec._check_assertion_semantics(assertion, path, test_name, errors)

    @staticmethod
    def _check_assertions(capture_spec: dict[str, Any], errors: list[str]) -> None:
        """
        Validate all assertion entries in a capture specification.

        :param capture_spec: The capture specification to validate.
        :param errors: Accumulator list; new errors are appended in-place.
        """
        assertions: Any = capture_spec.get("assertions")
        if not isinstance(assertions, list) or not assertions:
            errors.append("'assertions' must be a non-empty list of dictionaries.")
            return
        for index, assertion in enumerate(assertions):
            ValidateCaptureSpec._check_assertion(assertion, index, capture_spec.get("turn_count"), errors)

    @staticmethod
    def _check_capture_fields(capture_spec: dict[str, Any], errors: list[str]) -> None:
        """
        Validate obtainable per-turn fields and response-target coverage.

        :param capture_spec: The capture specification to validate.
        :param errors: Accumulator list; new errors are appended in-place.
        """
        capture_fields: Any = capture_spec.get("capture_per_turn")
        if not isinstance(capture_fields, list) or not capture_fields:
            errors.append("'capture_per_turn' must be a non-empty list of strings.")
            return
        for index, field_name in enumerate(capture_fields):
            if not isinstance(field_name, str):
                errors.append(f"capture_per_turn[{index}] must be a string, got: {field_name!r}.")
            elif field_name not in _ALLOWED_CAPTURE_FIELDS:
                errors.append(
                    f"capture_per_turn[{index}]='{field_name}' is not available: the platform does not expose "
                    f"that capture field. Allowed fields are: {sorted(_ALLOWED_CAPTURE_FIELDS)}."
                )
        assertions: Any = capture_spec.get("assertions")
        if not isinstance(assertions, list):
            return
        needs_text = any(
            isinstance(assertion, dict) and assertion.get("target") == _RESPONSE_TEXT_TARGET
            for assertion in assertions
        )
        needs_structure = any(
            isinstance(assertion, dict)
            and isinstance(assertion.get("target"), str)
            and assertion["target"].startswith(_RESPONSE_STRUCTURE_PREFIX)
            for assertion in assertions
        )
        if needs_text and "response_text" not in capture_fields:
            errors.append(
                "capture_per_turn must include 'response_text' because the assertions require response.text."
            )
        if needs_structure and "response_structure" not in capture_fields:
            errors.append(
                "capture_per_turn must include 'response_structure' because the assertions require response.structure."
            )

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> Union[dict[str, Any], str]:
        """
        Validate the runnable portions of a neutral capture specification.

        :param args: A dictionary containing ``capture_spec`` and optional
                ``scenario`` plus required ``scenario_format``.
        :param sly_data: Shared private agent data; unused by this validator.
        :return: ``{"valid": True}`` or ``{"valid": False, "errors": [...]}``.
        """
        logger = AndLogger(logging.getLogger(self.__class__.__name__))
        capture_spec: Any = args.get("capture_spec")
        if not isinstance(capture_spec, dict):
            return {"valid": False, "errors": ["'capture_spec' must be a dictionary."]}
        if "test_fixture" in args:
            return {"valid": False, "errors": ["'test_fixture' is not supported; provide 'scenario' instead."]}
        if "scenario" in args and not isinstance(args["scenario"], dict):
            return {"valid": False, "errors": ["'scenario' must be a dictionary when provided."]}
        if args.get("scenario_format") != _NEUTRAL_SCENARIO_FORMAT:
            return {
                "valid": False,
                "errors": [
                    f"'scenario_format' must be '{_NEUTRAL_SCENARIO_FORMAT}', got: {args.get('scenario_format')!r}."
                ],
            }
        logger.info(">>>>>>>>>>>>>>>>>>>Validating Capture Spec>>>>>>>>>>>>>>>>>>")
        errors: list[str] = []
        self._check_top_level(capture_spec, errors)
        self._check_assertions(capture_spec, errors)
        self._check_capture_fields(capture_spec, errors)
        if errors:
            logger.warning("Validation failed with %d error(s).", len(errors))
            for error in errors:
                logger.warning("  - %s", error)
            return {"valid": False, "errors": errors}
        logger.info(">>>>>>>>>>>>>>>>>>>Validation PASSED>>>>>>>>>>>>>>>>>>")
        return {"valid": True}
