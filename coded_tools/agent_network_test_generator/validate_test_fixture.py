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
import re
from typing import Any
from typing import Union

from neuro_san.interfaces.coded_tool import CodedTool

# The complete set of stock tests recognised by the neuro-san test runner.
_VALID_STOCK_TESTS: frozenset[str] = frozenset(
    {
        "keywords",
        "not_keywords",
        "value",
        "not_value",
        "gist",
        "not_gist",
        "less",
        "not_less",
        "greater",
        "not_greater",
    }
)

# Fields that the LLM sometimes invents inside response.structure but that
# are not part of the test fixture schema.
_FORBIDDEN_META_FIELDS: frozenset[str] = frozenset(
    {
        "type",
        "required_keys",
        "properties",
        "required",
        "items",
        "description",
    }
)

# Keys that are allowed at the top level of a fixture.
_ALLOWED_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    {
        "agent",
        "success_ratio",
        "connections",
        "interactions",
    }
)

# Keys that are allowed inside each interaction.
_ALLOWED_INTERACTION_KEYS: frozenset[str] = frozenset(
    {
        "text",
        "timeout_in_seconds",
        "response",
        "sly_data",
    }
)

_SUCCESS_RATIO_PATTERN: re.Pattern[str] = re.compile(r"^\d+/\d+$")

# Stock tests that expect numeric values and must use float, not int.
_NUMERIC_STOCK_TESTS: frozenset[str] = frozenset(
    {
        "value",
        "not_value",
        "less",
        "not_less",
        "greater",
        "not_greater",
    }
)

# Maximum number of words allowed in a single keyword or not_keyword entry.
# Keywords should be short distinctive phrases, not full sentences.
_MAX_KEYWORD_WORDS: int = 5

# Stock tests whose values are lists of strings that should be short keywords.
_KEYWORD_STOCK_TESTS: frozenset[str] = frozenset(
    {
        "keywords",
        "not_keywords",
    }
)

# Keys that are managed internally by coded tools at runtime.
# These must NEVER appear in sly_data (they accumulate automatically).
# They MAY still appear in response.structure if the agent returns them.
_FORBIDDEN_RUNTIME_KEYS: frozenset[str] = frozenset(
    {
        "running_cost",
        "TopicMemory",
        "username",
    }
)


class ValidateTestFixture(CodedTool):
    """
    CodedTool that programmatically validates a test fixture dictionary
    before it is persisted to disk.

    Returns a result dictionary with ``valid`` (bool) and, when invalid,
    an ``errors`` list describing every problem found.  The front-man agent
    can feed these errors back to the fixture builder for correction.
    """

    # ------------------------------------------------------------------
    # Top-level validation
    # ------------------------------------------------------------------

    @staticmethod
    def _check_top_level(fixture: dict[str, Any], errors: list[str]) -> None:
        """Validate required top-level keys and reject disallowed ones."""
        for key in ("agent", "success_ratio", "interactions"):
            if key not in fixture:
                errors.append(f"Missing required top-level key: '{key}'.")

        if "timeout_in_seconds" in fixture:
            errors.append(
                "Top-level 'timeout_in_seconds' is not allowed. Set it inside each individual interaction instead."
            )

        # Reject unexpected top-level keys.
        for key in fixture:
            if key not in _ALLOWED_TOP_LEVEL_KEYS:
                errors.append(
                    f"Unexpected top-level key: '{key}'. Allowed keys are: {sorted(_ALLOWED_TOP_LEVEL_KEYS)}."
                )

        # success_ratio must be a string like "1/1".
        ratio = fixture.get("success_ratio")
        if ratio is not None:
            if not isinstance(ratio, str) or not _SUCCESS_RATIO_PATTERN.match(ratio):
                errors.append(f"'success_ratio' must be a string in 'N/M' format (e.g. '1/1'), got: {ratio!r}.")

        interactions = fixture.get("interactions")
        if interactions is not None and not isinstance(interactions, list):
            errors.append("'interactions' must be a list.")

        # connections must be a list of valid connection types.
        # currently we only expected "direct", but this can be extended in the future.
        connections = fixture.get("connections")
        if connections is not None:
            if not isinstance(connections, list):
                errors.append("'connections' must be a list of strings (e.g. [\"direct\"]).")
            else:
                _VALID_CONNECTIONS = frozenset({"direct"})  # extend as needed
                for idx, conn in enumerate(connections):
                    if conn not in _VALID_CONNECTIONS:
                        errors.append(
                            f"connections[{idx}]: '{conn}' is not a valid connection type. "
                            f"Valid types are: {sorted(_VALID_CONNECTIONS)}."
                        )

    # ------------------------------------------------------------------
    # Per-interaction validation
    # ------------------------------------------------------------------

    @staticmethod
    def _check_interaction(
        interaction: dict[str, Any],
        index: int,
        errors: list[str],
    ) -> None:
        """Validate a single interaction entry."""
        prefix: str = f"interactions[{index}]"

        if not isinstance(interaction, dict):
            errors.append(f"{prefix}: must be a dictionary.")
            return

        # Required keys inside every interaction.
        if "text" not in interaction:
            errors.append(f"{prefix}: missing required key 'text'.")
        if "response" not in interaction:
            errors.append(f"{prefix}: missing required key 'response'.")
        if "timeout_in_seconds" not in interaction:
            errors.append(f"{prefix}: missing required key 'timeout_in_seconds'.")

        # Reject unexpected interaction keys.
        for key in interaction:
            if key not in _ALLOWED_INTERACTION_KEYS:
                errors.append(
                    f"{prefix}: unexpected key '{key}'. Allowed keys are: {sorted(_ALLOWED_INTERACTION_KEYS)}."
                )

        # Reject runtime-managed keys inside sly_data.
        sly_data: Any = interaction.get("sly_data")
        if isinstance(sly_data, dict):
            for sly_key in sly_data:
                if sly_key in _FORBIDDEN_RUNTIME_KEYS:
                    errors.append(
                        f"{prefix}.sly_data: '{sly_key}' is a runtime-managed key that coded tools "
                        "handle automatically. Remove it from sly_data and do NOT "
                        "create test scenarios that depend on this key. "
                        "Only include keys that override external inputs for determinism "
                        "(e.g. 'time' for TimeTool)."
                    )

        response: Any = interaction.get("response")
        if isinstance(response, dict):
            ValidateTestFixture._check_response(response, prefix, errors)

    # ------------------------------------------------------------------
    # Response validation
    # ------------------------------------------------------------------

    @staticmethod
    def _check_response(
        response: dict[str, Any],
        prefix: str,
        errors: list[str],
    ) -> None:
        """Validate the response block of an interaction."""
        has_text: bool = "text" in response
        has_structure: bool = "structure" in response

        if not has_text and not has_structure:
            errors.append(f"{prefix}.response: must contain either 'text' or 'structure'.")

        if has_text:
            text_val = response["text"]
            if isinstance(text_val, dict):
                ValidateTestFixture._check_stock_tests(text_val, f"{prefix}.response.text", errors)
            else:
                errors.append(
                    f"{prefix}.response.text: must be a dictionary of stock tests "
                    f'(e.g. {{"keywords": ["Beatles"]}}), '
                    f"not a {type(text_val).__name__}. "
                    "Do NOT use regex patterns."
                )

        if has_structure:
            struct_val = response["structure"]
            if isinstance(struct_val, dict):
                ValidateTestFixture._check_structure(struct_val, f"{prefix}.response.structure", errors)
            else:
                errors.append(f"{prefix}.response.structure: must be a dictionary, got {type(struct_val).__name__}.")

    # ------------------------------------------------------------------
    # Shared stock-test value validation
    # ------------------------------------------------------------------

    @staticmethod
    def _check_stock_test_value(
        key: str,
        val: Any,
        path: str,
        errors: list[str],
    ) -> None:
        """Validate a single stock test key/value for type and length rules."""
        # Numeric stock tests must use float, not int.
        if key in _NUMERIC_STOCK_TESTS and isinstance(val, int) and not isinstance(val, bool):
            errors.append(
                f"{path}.{key}: numeric value must be a float, not an int. "
                f"Use {float(val)} instead of {val}."
            )
        # Keywords / not_keywords entries must be short distinctive phrases.
        if key in _KEYWORD_STOCK_TESTS and isinstance(val, list):
            for kw_idx, kw_item in enumerate(val):
                if isinstance(kw_item, str) and len(kw_item.split()) > _MAX_KEYWORD_WORDS:
                    errors.append(
                        f"{path}.{key}[{kw_idx}]: keyword has {len(kw_item.split())} words "
                        f"(max {_MAX_KEYWORD_WORDS}). Keywords must be short distinctive "
                        "phrases, not full sentences. "
                        "Use `gist` for full-sentence meaning checks."
                    )

    # ------------------------------------------------------------------
    # Stock-test validation (for response.text)
    # ------------------------------------------------------------------

    @staticmethod
    def _check_stock_tests(
        block: dict[str, Any],
        path: str,
        errors: list[str],
    ) -> None:
        """Ensure every key in *block* is a recognised stock test."""
        for key, val in block.items():
            if key not in _VALID_STOCK_TESTS:
                errors.append(
                    f"{path}: '{key}' is not a valid stock test. Valid tests are: {sorted(_VALID_STOCK_TESTS)}."
                )
            ValidateTestFixture._check_stock_test_value(key, val, path, errors)

    # ------------------------------------------------------------------
    # Structure validation (for response.structure)
    # ------------------------------------------------------------------

    @staticmethod
    def _check_structure(
        structure: dict[str, Any],
        path: str,
        errors: list[str],
    ) -> None:
        """Validate response.structure entries.

        Each key should map to a dict of stock tests.  Reject common
        meta-fields the LLM tends to invent.
        """
        for key, value in structure.items():
            field_path: str = f"{path}.{key}"

            # Reject known meta-fields at the structure level.
            if key in _FORBIDDEN_META_FIELDS:
                errors.append(
                    f"{field_path}: '{key}' is a forbidden meta-field. "
                    "Structure keys must be actual response dictionary keys, "
                    "not schema descriptors."
                )
                continue

            if not isinstance(value, dict):
                errors.append(f"{field_path}: expected a dictionary of stock tests, got {type(value).__name__}.")
                continue

            # Each value under a structure key should be stock tests.
            for test_name, test_val in value.items():
                if test_name in _FORBIDDEN_META_FIELDS:
                    errors.append(
                        f"{field_path}.{test_name}: '{test_name}' is a forbidden meta-field inside a structure value."
                    )
                elif test_name not in _VALID_STOCK_TESTS:
                    errors.append(
                        f"{field_path}.{test_name}: '{test_name}' is not a "
                        f"valid stock test. Valid tests are: "
                        f"{sorted(_VALID_STOCK_TESTS)}."
                    )
                ValidateTestFixture._check_stock_test_value(test_name, test_val, field_path, errors)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> Union[dict[str, Any], str]:
        """
        Validate a test fixture dictionary and return the result.

        :param args: A dictionary with the following keys:
                "test_fixture": the fixture dictionary to validate.

        :param sly_data: A dictionary whose keys are defined by the agent
                hierarchy, but whose values are meant to be kept out of
                the chat stream.

                Keys expected for this implementation are:
                    None

        :return:
            A dictionary with:
                "valid": True/False
                "errors": list of error strings (only when invalid)
        """
        logger = logging.getLogger(self.__class__.__name__)

        test_fixture: dict[str, Any] = args.get("test_fixture", {})
        if not test_fixture:
            return {"valid": False, "errors": ["No 'test_fixture' provided."]}

        logger.info(">>>>>>>>>>>>>>>>>>>Validating Test Fixture>>>>>>>>>>>>>>>>>>")

        errors: list[str] = []

        # Top-level checks.
        self._check_top_level(test_fixture, errors)

        # Per-interaction checks.
        interactions: Any = test_fixture.get("interactions")
        if isinstance(interactions, list):
            for idx, interaction in enumerate(interactions):
                self._check_interaction(interaction, idx, errors)

        if errors:
            logger.warning("Validation failed with %d error(s).", len(errors))
            for err in errors:
                logger.warning("  - %s", err)
            return {"valid": False, "errors": errors}

        logger.info(">>>>>>>>>>>>>>>>>>>Validation PASSED>>>>>>>>>>>>>>>>>>")
        return {"valid": True}

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> Union[dict[str, Any], str]:
        """Run invoke asynchronously."""
        return await asyncio.to_thread(self.invoke, args, sly_data)
