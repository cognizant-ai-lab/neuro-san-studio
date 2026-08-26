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
Shared neuro-san stock-test facts for the neutral test-case and capture-spec validators.

This module deliberately contains no logic and imports nothing from the package.
It is a leaf module that breaks the circular import that arose when the neutral
validator imported these constants from ``validate_test_fixture`` while that
module imported capture validation. The restored DataDriven fixture validator
currently keeps equivalent local definitions so it can remain byte-identical
to HEAD. The module is named ``stock_test_constants`` rather than
``test_case_constants`` because pytest collects modules matching ``test_*.py``.
"""

# The complete set of assertion tests implemented by the neuro-san stock
# evaluator; anything outside it is rejected because no runner can execute it.
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

# sly_data keys populated by the platform at runtime; generated tests must
# never seed them because doing so would overwrite live session state.
_FORBIDDEN_RUNTIME_KEYS: frozenset[str] = frozenset(
    {
        "running_cost",
        "TopicMemory",
        "username",
    }
)

# Tests with numeric semantics: value/not_value also accept an exact string,
# while comparisons are float-only, so numeric and keyword sets stay separate.
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

# Tests whose expected values are lists of short phrases.
_KEYWORD_STOCK_TESTS: frozenset[str] = frozenset({"keywords", "not_keywords"})

# Keyword matching is substring-based, so long phrases are brittle; cap each
# phrase at five words.
_MAX_KEYWORD_WORDS: int = 5
