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
import math
from typing import Any
from typing import Union

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.agent_network_editor.and_logger import AndLogger
from coded_tools.agent_network_test_generator.stock_test_constants import _FORBIDDEN_RUNTIME_KEYS
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
_ALLOWED_CAPTURE_FIELDS: frozenset[str] = frozenset(
    {"response_text", "response_structure", "sly_data_after", "elapsed_seconds", "error"}
)
_VALID_DETERMINISM: frozenset[str] = frozenset({"deterministic", "fuzzy"})
_FUZZY_STOCK_TESTS: frozenset[str] = frozenset({"gist", "not_gist"})
_RESPONSE_TEXT_TARGET: str = "response.text"
_RESPONSE_STRUCTURE_PREFIX: str = "response.structure."
_NEUTRAL_SCENARIO_FORMAT: str = "antegen_neutral"


class ValidateCaptureSpec(CodedTool):
    """
    CodedTool that validates a runner capture specification and optional scenario.

    The result contains ``valid`` and, when invalid, an ``errors`` list with every
    discovered problem so the capture-spec writer can correct them in one retry.
    """

    @staticmethod
    def _is_json_safe(value: Any) -> bool:
        """
        Determine whether a value contains only plain JSON-compatible types.

        :param value: The value to inspect recursively.
        :return: True when the value can cross the JSON/gRPC boundary safely.
        """
        if value is None or isinstance(value, (str, bool, int)):
            return True
        if isinstance(value, float):
            return math.isfinite(value)
        if isinstance(value, list):
            return all(ValidateCaptureSpec._is_json_safe(item) for item in value)
        if isinstance(value, dict):
            return all(isinstance(key, str) and ValidateCaptureSpec._is_json_safe(item) for key, item in value.items())
        return False

    @staticmethod
    def _neutral_turns(scenario: dict[str, Any]) -> list[Any]:
        """
        Return neutral scenario turns when the scenario has a usable turn list.

        :param scenario: The neutral scenario dictionary to inspect.
        :return: The turn list, or an empty list for malformed scenario input.
        """
        turns: Any = scenario.get("turns")
        return turns if isinstance(turns, list) else []

    @staticmethod
    def _json_values_equal(left: Any, right: Any) -> bool:
        """
        Compare JSON-compatible values structurally and preserve JSON types.

        :param left: First JSON-compatible value.
        :param right: Second JSON-compatible value.
        :return: True when both values have the same JSON structure and types.
        """
        if type(left) is not type(right):
            return False
        if isinstance(left, dict):
            if set(left) != set(right):
                return False
            return all(ValidateCaptureSpec._json_values_equal(left[key], right[key]) for key in left)
        if isinstance(left, list):
            return len(left) == len(right) and all(
                ValidateCaptureSpec._json_values_equal(left_item, right_item)
                for left_item, right_item in zip(left, right)
            )
        return left == right

    @staticmethod
    def _valid_turn_count(turn_count: Any) -> bool:
        """
        Determine whether a turn count can safely bound assertion turns.

        :param turn_count: Candidate capture-spec turn count.
        :return: True when the value is an integer greater than or equal to one.
        """
        return isinstance(turn_count, int) and not isinstance(turn_count, bool) and turn_count >= 1

    @staticmethod
    def _target_is_valid(target: Any) -> bool:
        """
        Check whether an assertion target names a supported response location.

        :param target: The target value to inspect.
        :return: True for ``response.text`` or one-level structure targets.
        """
        if target == _RESPONSE_TEXT_TARGET:
            return True
        if not isinstance(target, str) or not target.startswith(_RESPONSE_STRUCTURE_PREFIX):
            return False
        field_name: str = target[len(_RESPONSE_STRUCTURE_PREFIX) :]
        return bool(field_name) and "." not in field_name

    def _check_top_level(self, capture_spec: dict[str, Any], errors: list[str]) -> None:
        """
        Validate required and unexpected capture-spec keys.

        :param capture_spec: The capture specification to validate.
        :param errors: Accumulator list; new errors are appended in-place.
        """
        for key in sorted(_ALLOWED_CAPTURE_SPEC_KEYS):
            if key not in capture_spec:
                errors.append(f"Missing required capture_spec key: '{key}'.")
        for key in capture_spec:
            if key not in _ALLOWED_CAPTURE_SPEC_KEYS:
                errors.append(
                    f"Unexpected capture_spec key: '{key}'. Allowed keys are: {sorted(_ALLOWED_CAPTURE_SPEC_KEYS)}."
                )

    def _check_turn_count(
        self,
        capture_spec: dict[str, Any],
        scenario: dict[str, Any] | None,
        errors: list[str],
    ) -> None:
        """
        Validate the turn count and compare it with the neutral scenario turn count.

        :param capture_spec: The capture specification to validate.
        :param scenario: Optional scenario annotated by the specification.
        :param errors: Accumulator list; new errors are appended in-place.
        """
        turn_count: Any = capture_spec.get("turn_count")
        valid_turn_count: bool = isinstance(turn_count, int) and not isinstance(turn_count, bool) and turn_count >= 1
        if not isinstance(turn_count, int) or isinstance(turn_count, bool):
            errors.append(f"'turn_count' must be an integer greater than or equal to 1, got: {turn_count!r}.")
        elif turn_count < 1:
            errors.append(f"'turn_count' must be greater than or equal to 1, got: {turn_count}.")
        if valid_turn_count and scenario is not None:
            turns: list[Any] = self._neutral_turns(scenario)
            if turns and turn_count != len(turns):
                errors.append(
                    f"'turn_count' is {turn_count}, but the neutral scenario contains {len(turns)} turn(s). "
                    "It must equal the neutral scenario turn count."
                )

    @staticmethod
    def _check_suggested_timeout_seconds(capture_spec: dict[str, Any], errors: list[str]) -> None:
        """
        Validate advisory per-turn timeout suggestions.

        :param capture_spec: The capture specification to validate.
        :param errors: Accumulator list; new errors are appended in-place.
        """
        suggested_timeouts: Any = capture_spec.get("suggested_timeout_seconds")
        if not isinstance(suggested_timeouts, list):
            errors.append(
                "'suggested_timeout_seconds' must be a list of positive integers, "
                f"got: {type(suggested_timeouts).__name__}."
            )
            return
        for index, timeout in enumerate(suggested_timeouts):
            if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout < 1:
                errors.append(f"suggested_timeout_seconds[{index}] must be a positive integer, got: {timeout!r}.")
        turn_count: Any = capture_spec.get("turn_count")
        if ValidateCaptureSpec._valid_turn_count(turn_count) and len(suggested_timeouts) != turn_count:
            errors.append(
                f"'suggested_timeout_seconds' must contain exactly {turn_count} value(s), "
                f"one per turn, got: {len(suggested_timeouts)}."
            )

    def _check_sly_data_seeds(
        self,
        capture_spec: dict[str, Any],
        scenario: dict[str, Any] | None,
        errors: list[str],
    ) -> None:
        """
        Validate seed types, runtime keys, and neutral scenario seed correspondence.

        :param capture_spec: The capture specification to validate.
        :param scenario: Optional scenario annotated by the specification.
        :param errors: Accumulator list; new errors are appended in-place.
        """
        seeds: Any = capture_spec.get("sly_data_seeds")
        if not isinstance(seeds, dict):
            errors.append(f"'sly_data_seeds' must be a dictionary, got: {type(seeds).__name__}.")
            return
        for key, value in seeds.items():
            if key in _FORBIDDEN_RUNTIME_KEYS:
                errors.append(
                    f"sly_data_seeds['{key}'] is runtime-managed. These keys are handled automatically; "
                    "do not include them as scenario seeds."
                )
            if not self._is_json_safe(value):
                errors.append(
                    f"sly_data_seeds['{key}'] contains a value that is not a plain JSON type. "
                    "Only strings, numbers, booleans, null, lists, and dictionaries are allowed."
                )
        if scenario is None:
            return
        self._check_seed_neutral_match(seeds, scenario, errors)

    def _check_seed_neutral_match(
        self,
        seeds: dict[str, Any],
        scenario: dict[str, Any],
        errors: list[str],
    ) -> None:
        """
        Compare declared seeds with the values found in neutral scenario turns.

        :param seeds: Seed values declared by the capture specification.
        :param scenario: Neutral scenario annotated by the specification.
        :param errors: Accumulator list; new errors are appended in-place.
        """
        scenario_seed_values: dict[str, list[Any]] = {}
        for turn in self._neutral_turns(scenario):
            if not isinstance(turn, dict):
                continue
            turn_seeds: Any = turn.get("seeds")
            if not isinstance(turn_seeds, dict):
                continue
            for key, value in turn_seeds.items():
                scenario_seed_values.setdefault(key, []).append(value)
        for key, value in seeds.items():
            values: list[Any] = scenario_seed_values.get(key, [])
            if not values:
                errors.append(f"sly_data_seeds['{key}']={value!r} does not appear in any turn's seeds.")
            elif not any(self._json_values_equal(value, scenario_value) for scenario_value in values):
                errors.append(
                    f"sly_data_seeds['{key}']={value!r} does not match neutral scenario seed value(s) {values!r}."
                )
        for key, values in scenario_seed_values.items():
            distinct_values: list[Any] = []
            for value in values:
                if not any(self._json_values_equal(value, distinct_value) for distinct_value in distinct_values):
                    distinct_values.append(value)
            if len(distinct_values) > 1:
                errors.append(
                    f"Neutral scenario seed key '{key}' changes across turns. The flat sly_data_seeds dictionary "
                    f"cannot express per-turn seed changes; distinct values are {distinct_values!r}. Each "
                    "scenario must use a single value per seed key; split the scenario if different turns "
                    "need different values."
                )
            if key not in seeds:
                errors.append(
                    f"Neutral scenario seed key '{key}' is missing from sly_data_seeds (scenario values: {values!r})."
                )

    def _check_state_reset(self, capture_spec: dict[str, Any], errors: list[str]) -> None:
        """
        Validate statefulness and the list of runner reset requirements.

        :param capture_spec: The capture specification to validate.
        :param errors: Accumulator list; new errors are appended in-place.
        """
        stateful: Any = capture_spec.get("stateful")
        if not isinstance(stateful, bool):
            errors.append(f"'stateful' must be a boolean, got: {type(stateful).__name__}.")
        reset_required: Any = capture_spec.get("reset_required")
        if not isinstance(reset_required, list):
            errors.append(
                f"'reset_required' must be a list of non-empty strings, got: {type(reset_required).__name__}."
            )
            return
        for index, reset_item in enumerate(reset_required):
            if not isinstance(reset_item, str) or not reset_item.strip():
                errors.append(f"reset_required[{index}] must be a non-empty string, got: {reset_item!r}.")
        if reset_required and stateful is False:
            errors.append("'reset_required' is non-empty, so 'stateful' must be true.")

    def _check_capture_fields(
        self,
        capture_spec: dict[str, Any],
        errors: list[str],
    ) -> None:
        """
        Validate the per-turn capture field list and neutral assertion requirements.

        :param capture_spec: The capture specification to validate.
        :param errors: Accumulator list; new errors are appended in-place.
        """
        capture_fields: Any = capture_spec.get("capture_per_turn")
        if not isinstance(capture_fields, list) or not capture_fields:
            errors.append("'capture_per_turn' must be a non-empty list of strings.")
            return
        seen: set[str] = set()
        for index, field_name in enumerate(capture_fields):
            if not isinstance(field_name, str):
                errors.append(f"capture_per_turn[{index}] must be a string, got: {field_name!r}.")
                continue
            if field_name in seen:
                errors.append(f"capture_per_turn contains duplicate field '{field_name}'.")
            seen.add(field_name)
            if field_name not in _ALLOWED_CAPTURE_FIELDS:
                errors.append(
                    f"capture_per_turn[{index}]='{field_name}' is not available: the platform does not expose "
                    f"that capture field. Allowed fields are: {sorted(_ALLOWED_CAPTURE_FIELDS)}."
                )
        if "response_text" not in capture_fields and "response_structure" not in capture_fields:
            errors.append("capture_per_turn must include at least one of 'response_text' or 'response_structure'.")
        self._check_neutral_capture_fields(capture_spec, capture_fields, errors)

    @staticmethod
    def _check_neutral_capture_fields(
        capture_spec: dict[str, Any],
        capture_fields: list[Any],
        errors: list[str],
    ) -> None:
        """Ensure neutral assertion targets have matching capture fields."""
        assertions: Any = capture_spec.get("assertions")
        if not isinstance(assertions, list):
            return
        needs_text: bool = any(
            isinstance(assertion, dict) and assertion.get("target") == _RESPONSE_TEXT_TARGET
            for assertion in assertions
        )
        needs_structure: bool = any(
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

    @staticmethod
    def _check_assertion_shape(
        assertion: dict[str, Any],
        path: str,
        errors: list[str],
    ) -> None:
        """
        Validate required and optional keys in one assertion.

        :param assertion: Assertion dictionary to inspect.
        :param path: Human-readable path to the assertion.
        :param errors: Accumulator list; new errors are appended in-place.
        """
        allowed_keys: frozenset[str] = frozenset({"turn", "target", "test", "determinism", "note", "expected"})
        for key in ("turn", "target", "test", "determinism"):
            if key not in assertion:
                errors.append(f"{path} is missing required key '{key}'.")
        if "expected" not in assertion:
            errors.append(f"{path} is missing required key 'expected'.")
        for key in assertion:
            if key not in allowed_keys:
                errors.append(f"{path} has unexpected key '{key}'. Allowed keys are: {sorted(allowed_keys)}.")

    @staticmethod
    def _check_neutral_expected(
        assertion: dict[str, Any],
        path: str,
        test_name: Any,
        errors: list[str],
    ) -> None:
        """Validate the expected value attached to a neutral assertion."""
        if not isinstance(test_name, str) or test_name not in _VALID_STOCK_TESTS:
            return
        if "expected" not in assertion:
            return
        expected: Any = assertion.get("expected")
        if test_name in {"value", "not_value"}:
            ValidateCaptureSpec._check_neutral_value_expected(expected, path, test_name, errors)
            return
        if test_name in _NUMERIC_STOCK_TESTS:
            ValidateCaptureSpec._check_neutral_numeric_expected(expected, path, test_name, errors)
            return
        if test_name not in {"keywords", "not_keywords", "gist", "not_gist"}:
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
            for index, item in enumerate(expected):
                if len(item.split()) > _MAX_KEYWORD_WORDS:
                    errors.append(
                        f"{path}.expected.{test_name}[{index}]: keyword has {len(item.split())} words "
                        f"(max {_MAX_KEYWORD_WORDS}). Keywords must be short distinctive "
                        "phrases, not full sentences. "
                        "Use `gist` for full-sentence meaning checks."
                    )

    @staticmethod
    def _check_neutral_value_expected(
        expected: Any,
        path: str,
        test_name: str,
        errors: list[str],
    ) -> None:
        """Validate an exact float or string value expectation."""
        if isinstance(expected, int) and not isinstance(expected, bool):
            errors.append(
                f"{path}.expected.{test_name}: numeric value must be a float, not an int. "
                f"Use {float(expected)} instead of {expected}."
            )
        elif not isinstance(expected, float) and (not isinstance(expected, str) or not expected.strip()):
            errors.append(
                f"{path}.expected.{test_name}: expected value must be a float or non-empty string, got: {expected!r}."
            )

    @staticmethod
    def _check_neutral_numeric_expected(
        expected: Any,
        path: str,
        test_name: str,
        errors: list[str],
    ) -> None:
        """Validate a comparison's float expectation."""
        if isinstance(expected, int) and not isinstance(expected, bool):
            errors.append(
                f"{path}.expected.{test_name}: numeric value must be a float, not an int. "
                f"Use {float(expected)} instead of {expected}."
            )
        elif not isinstance(expected, float):
            errors.append(f"{path}.expected.{test_name}: expected value must be a float, got: {expected!r}.")

    @staticmethod
    def _check_assertion_turn(
        assertion: dict[str, Any],
        path: str,
        turn_count: Any,
        errors: list[str],
    ) -> tuple[bool, Any]:
        """
        Validate an assertion's one-based turn number.

        :param assertion: Assertion dictionary to inspect.
        :param path: Human-readable path to the assertion.
        :param validation_context: Capture-spec turn count and scenario format.
        :param errors: Accumulator list; new errors are appended in-place.
        :return: A validity flag and the supplied turn value.
        """
        turn: Any = assertion.get("turn")
        valid_turn: bool = isinstance(turn, int) and not isinstance(turn, bool)
        if not isinstance(turn, int) or isinstance(turn, bool):
            errors.append(f"{path}.turn must be an integer, got: {turn!r}.")
        elif ValidateCaptureSpec._valid_turn_count(turn_count) and not 1 <= turn <= turn_count:
            errors.append(f"{path}.turn must be between 1 and {turn_count!r}, got: {turn}.")
        return valid_turn, turn

    @staticmethod
    def _check_assertion_target(assertion: dict[str, Any], path: str, errors: list[str]) -> tuple[bool, Any]:
        """
        Validate an assertion response target.

        :param assertion: Assertion dictionary to inspect.
        :param path: Human-readable path to the assertion.
        :param errors: Accumulator list; new errors are appended in-place.
        :return: A validity flag and the supplied target value.
        """
        target: Any = assertion.get("target")
        valid_target: bool = ValidateCaptureSpec._target_is_valid(target)
        if not valid_target:
            errors.append(
                f"{path}.target must be exactly 'response.text' or 'response.structure.<key>' "
                f"with a one-level non-empty key, got: {target!r}."
            )
        return valid_target, target

    @staticmethod
    def _check_assertion_test(assertion: dict[str, Any], path: str, errors: list[str]) -> tuple[bool, Any]:
        """
        Validate an assertion stock-test name.

        :param assertion: Assertion dictionary to inspect.
        :param path: Human-readable path to the assertion.
        :param errors: Accumulator list; new errors are appended in-place.
        :return: A validity flag and the supplied stock-test value.
        """
        test_name: Any = assertion.get("test")
        valid_test: bool = isinstance(test_name, str) and test_name in _VALID_STOCK_TESTS
        if not valid_test:
            errors.append(
                f"{path}.test must be a valid stock test. Valid tests are: {sorted(_VALID_STOCK_TESTS)}; "
                f"got: {test_name!r}."
            )
        return valid_test, test_name

    @staticmethod
    def _check_assertion_determinism(
        assertion: dict[str, Any],
        path: str,
        test_name: Any,
        valid_test: bool,
        errors: list[str],
    ) -> None:
        """
        Validate determinism and its consistency with the stock test.

        :param assertion: Assertion dictionary to inspect.
        :param path: Human-readable path to the assertion.
        :param test_name: Supplied stock-test value.
        :param valid_test: Whether the stock-test value is valid.
        :param errors: Accumulator list; new errors are appended in-place.
        """
        determinism: Any = assertion.get("determinism")
        valid_determinism: bool = isinstance(determinism, str) and determinism in _VALID_DETERMINISM
        if not valid_determinism:
            errors.append(f"{path}.determinism must be one of {sorted(_VALID_DETERMINISM)}, got: {determinism!r}.")
        elif valid_test:
            expected: str = "fuzzy" if test_name in _FUZZY_STOCK_TESTS else "deterministic"
            if determinism != expected:
                reason: str = (
                    "gist tests are LLM-judged"
                    if test_name in _FUZZY_STOCK_TESTS
                    else "this stock test is mechanically evaluated"
                )
                errors.append(f"{path}.determinism must be '{expected}' for '{test_name}' because {reason}.")

    @staticmethod
    def _check_assertion_note(assertion: dict[str, Any], path: str, errors: list[str]) -> None:
        """
        Validate an assertion note, including the fuzzy-test requirement.

        :param assertion: Assertion dictionary to inspect.
        :param path: Human-readable path to the assertion.
        :param errors: Accumulator list; new errors are appended in-place.
        """
        note: Any = assertion.get("note")
        if "note" in assertion and (not isinstance(note, str) or not note.strip()):
            errors.append(f"{path}.note must be a non-empty string when provided.")
        if assertion.get("determinism") == "fuzzy" and (not isinstance(note, str) or not note.strip()):
            errors.append(
                f"{path}.note is required for fuzzy assertions to explain why a failure may not be a regression."
            )

    @staticmethod
    def _check_one_assertion(
        assertion: Any,
        index: int,
        turn_count: Any,
        assertion_triples: set[tuple[int, str, str]],
        errors: list[str],
    ) -> None:
        """
        Validate one assertion and add its identity to the seen triples.

        :param assertion: Candidate assertion value.
        :param index: Zero-based assertion index.
        :param assertion_triples: Previously seen assertion identities.
        :param errors: Accumulator list; new errors are appended in-place.
        """
        path: str = f"assertions[{index}]"
        if not isinstance(assertion, dict):
            errors.append(f"{path} must be a dictionary.")
            return
        ValidateCaptureSpec._check_assertion_shape(assertion, path, errors)
        valid_turn, turn = ValidateCaptureSpec._check_assertion_turn(assertion, path, turn_count, errors)
        valid_target, target = ValidateCaptureSpec._check_assertion_target(assertion, path, errors)
        valid_test, test_name = ValidateCaptureSpec._check_assertion_test(assertion, path, errors)
        ValidateCaptureSpec._check_assertion_determinism(assertion, path, test_name, valid_test, errors)
        ValidateCaptureSpec._check_assertion_note(assertion, path, errors)
        ValidateCaptureSpec._check_neutral_expected(assertion, path, test_name, errors)
        if valid_turn and valid_target and valid_test:
            triple = (turn, target, test_name)
            if triple in assertion_triples:
                errors.append(
                    f"{path} duplicates assertion triple {triple!r}; include at most one assertion per "
                    "(turn, target, test) combination and combine multiple expected values into one list."
                )
            assertion_triples.add(triple)

    def _check_assertions(
        self,
        capture_spec: dict[str, Any],
        errors: list[str],
    ) -> None:
        """
        Validate assertion shape, stock tests, determinism, and expected values.

        :param capture_spec: The capture specification to validate.
        :param errors: Accumulator list; new errors are appended in-place.
        """
        assertions: Any = capture_spec.get("assertions")
        if not isinstance(assertions, list) or not assertions:
            errors.append("'assertions' must be a non-empty list of dictionaries.")
            return
        assertion_triples: set[tuple[int, str, str]] = set()
        turn_count: Any = capture_spec.get("turn_count")
        for index, assertion in enumerate(assertions):
            self._check_one_assertion(
                assertion,
                index,
                turn_count,
                assertion_triples,
                errors,
            )

    @staticmethod
    def _check_fuzzy_attempts(
        capture_spec: dict[str, Any],
        scenario: dict[str, Any] | None,
        errors: list[str],
    ) -> None:
        """
        Ensure fuzzy assertions have repeated neutral scenario attempts.

        :param capture_spec: The capture specification to validate.
        :param scenario: Optional scenario annotated by the specification.
        :param errors: Accumulator list; new errors are appended in-place.
        """
        if scenario is None:
            return
        assertions: Any = capture_spec.get("assertions")
        if not isinstance(assertions, list):
            return
        fuzzy_count: int = sum(
            1 for assertion in assertions if isinstance(assertion, dict) and assertion.get("determinism") == "fuzzy"
        )
        if fuzzy_count == 0:
            return
        attempts: Any = scenario.get("attempts")
        if attempts == 1:
            errors.append(
                f"Neutral scenario attempts={attempts} allows only one attempt, but the capture spec "
                f"contains {fuzzy_count} fuzzy assertion(s). Fuzzy assertions need repeated attempts; "
                "suggest using attempts=3 and required_passes=2."
            )

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> Union[dict[str, Any], str]:
        """
        Validate a capture specification and optionally its annotated neutral scenario.

        :param args: A dictionary containing required ``capture_spec`` and optional
                ``scenario`` and ``scenario_format`` values.
        :param sly_data: Shared private agent data; unused by this validator.
        :return: ``{"valid": True}`` or ``{"valid": False, "errors": [...]}``.
        """
        logger = AndLogger(logging.getLogger(self.__class__.__name__))
        capture_spec: Any = args.get("capture_spec")
        if not isinstance(capture_spec, dict):
            return {"valid": False, "errors": ["'capture_spec' must be a dictionary."]}
        if "test_fixture" in args:
            return {"valid": False, "errors": ["'test_fixture' is not supported; provide 'scenario' instead."]}
        scenario: Any = args.get("scenario")
        if "scenario" in args and not isinstance(scenario, dict):
            return {"valid": False, "errors": ["'scenario' must be a dictionary when provided."]}
        scenario_format: Any = args.get("scenario_format")
        if scenario_format != _NEUTRAL_SCENARIO_FORMAT:
            return {
                "valid": False,
                "errors": [f"'scenario_format' must be '{_NEUTRAL_SCENARIO_FORMAT}', got: {scenario_format!r}."],
            }
        logger.info(">>>>>>>>>>>>>>>>>>>Validating Capture Spec>>>>>>>>>>>>>>>>>>")
        errors: list[str] = []
        self._check_top_level(capture_spec, errors)
        self._check_turn_count(capture_spec, scenario, errors)
        self._check_suggested_timeout_seconds(capture_spec, errors)
        self._check_sly_data_seeds(capture_spec, scenario, errors)
        self._check_state_reset(capture_spec, errors)
        self._check_capture_fields(capture_spec, errors)
        self._check_assertions(capture_spec, errors)
        self._check_fuzzy_attempts(capture_spec, scenario, errors)
        if errors:
            logger.warning("Validation failed with %d error(s).", len(errors))
            for error in errors:
                logger.warning("  - %s", error)
            return {"valid": False, "errors": errors}
        logger.info(">>>>>>>>>>>>>>>>>>>Validation PASSED>>>>>>>>>>>>>>>>>>")
        return {"valid": True}
