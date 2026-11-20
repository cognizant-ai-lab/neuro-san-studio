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

from coded_tools.logfix_ai.runbook_search import RunbookSearch


def test_known_issue_returns_grounded_runbook():
    """A supported classification should return its packaged runbook."""
    result = RunbookSearch().invoke({"issue_type": "db_timeout"}, {})

    assert isinstance(result, dict)
    assert result["issue_type"] == "db_timeout"
    assert result["matched_runbook"] == "runbook_db_timeout.md"
    assert "HikariPool" in result["runbook_text"]
    assert "Incident Update Template" in result["incident_update_template"]


def test_unsupported_issue_uses_known_patterns():
    """An unsupported classification should use the safe fallback reference."""
    result = RunbookSearch().invoke({"issue_type": "cache_failure"}, {})

    assert isinstance(result, dict)
    assert result["issue_type"] == "cache_failure"
    assert result["matched_runbook"] == "known_error_patterns.md"


def test_empty_issue_type_is_normalized_to_unknown():
    """Blank issue types should be normalized consistently."""
    result = RunbookSearch().invoke({"issue_type": " "}, {})

    assert isinstance(result, dict)
    assert result["issue_type"] == "unknown"
    assert result["matched_runbook"] == "known_error_patterns.md"
