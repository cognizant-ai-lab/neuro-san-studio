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

from coded_tools.logfix_ai.log_parser import LogParser


def test_db_timeout_extracts_incident_signals():
    """A database timeout should retain the evidence used for classification."""
    log_text = """2026-09-02 10:15:22 ERROR OrderService
HikariPool-1 - Connection is not available, request timed out after 30000ms.
java.sql.SQLTransientConnectionException:
orders-db - Connection is not available, request timed out after 30000ms.
API /orders returned HTTP 500"""

    result = LogParser().invoke({"log_text": log_text}, {})

    assert isinstance(result, dict)
    assert result["issue_type"] == "db_timeout"
    assert result["services"] == ["OrderService"]
    assert result["apis"] == ["/orders"]
    assert result["exceptions"] == ["java.sql.SQLTransientConnectionException"]
    assert result["http_statuses"] == ["500"]
    assert result["timeouts"] == ["30000ms"]
    assert result["pools"] == ["HikariPool-1"]


def test_api_failure_detects_upstream_status():
    """An upstream server error should be classified as an API failure."""
    log_text = """2026-09-02 11:05:10 ERROR PaymentService
HTTP 503 received from upstream fraud-check-service.
API /payments returned HTTP 500"""

    result = LogParser().invoke({"log_text": log_text}, {})

    assert isinstance(result, dict)
    assert result["issue_type"] == "api_failure"
    assert result["http_statuses"] == ["500", "503"]


def test_memory_issue_detects_out_of_memory_error():
    """A Java heap-space failure should be classified as a memory issue."""
    log_text = """2026-09-02 12:42:55 ERROR InventoryService
java.lang.OutOfMemoryError: Java heap space
API /inventory/search returned HTTP 500"""

    result = LogParser().invoke({"log_text": log_text}, {})

    assert isinstance(result, dict)
    assert result["issue_type"] == "memory_issue"
    assert result["exceptions"] == ["java.lang.OutOfMemoryError"]


def test_empty_log_returns_validation_error():
    """The parser should reject empty input without raising an exception."""
    result = LogParser().invoke({"log_text": "  "}, {})

    assert result == {"error": "log_text is required"}


def test_unmatched_log_is_unknown():
    """Unmatched evidence should remain unknown instead of inventing a cause."""
    result = LogParser().invoke({"log_text": "2026-09-02 INFO Worker completed task"}, {})

    assert isinstance(result, dict)
    assert result["issue_type"] == "unknown"
