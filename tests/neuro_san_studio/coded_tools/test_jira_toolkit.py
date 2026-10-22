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

"""Tests for the project-owned Jira toolkit."""

import json
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from neuro_san_studio.coded_tools.jira_toolkit import JiraAPIWrapper
from neuro_san_studio.coded_tools.jira_toolkit import JiraToolkit

BASE_URL = "https://jira.example.com"


def _wrapper() -> JiraAPIWrapper:
    """Create a wrapper around mocked, already-configured clients."""
    return JiraAPIWrapper(jira=MagicMock(), confluence=MagicMock())


def test_tool_names_and_argument_schema_match_previous_contract():
    """Agent networks keep seeing the same five tools with an instructions argument."""
    tools = JiraToolkit(jira_api_wrapper=_wrapper()).get_tools()

    assert [tool.name for tool in tools] == [
        "jql_query",
        "get_projects",
        "create_issue",
        "catch_all_jira_api",
        "create_confluence_page",
    ]
    assert all("instructions" in tool.args for tool in tools)


def test_jql_query_retains_compact_issue_shape():
    """JQL results retain the response fields exposed by the previous wrapper."""
    wrapper = _wrapper()
    wrapper.jira.jql.return_value = {
        "issues": [
            {
                "key": "TEST-1",
                "fields": {
                    "summary": "Example",
                    "created": "2026-08-15T10:00:00Z",
                    "assignee": None,
                    "priority": {"name": "Low"},
                    "status": {"name": "Open"},
                    "issuelinks": [],
                },
            }
        ]
    }

    result = wrapper.run("jql", "project = TEST")

    assert result == (
        "Found 1 issues:\n[{'key': 'TEST-1', 'summary': 'Example', 'created': '2026-08-15', "
        "'assignee': 'None', 'priority': 'Low', 'status': 'Open', 'related_issues': {}}]"
    )
    wrapper.jira.jql.assert_called_once_with("project = TEST")


def test_create_and_catch_all_operations_forward_json_arguments():
    """Write and catch-all tools preserve their JSON-string input contract."""
    wrapper = _wrapper()
    wrapper.jira.issue_create.return_value = {"key": "TEST-1"}
    wrapper.jira.projects.return_value = [{"key": "TEST"}]

    issue = wrapper.run("create_issue", json.dumps({"summary": "Example"}))
    projects = wrapper.run("other", json.dumps({"function": "projects"}))

    assert issue == {"key": "TEST-1"}
    assert projects == [{"key": "TEST"}]
    wrapper.jira.issue_create.assert_called_once_with(fields={"summary": "Example"})
    wrapper.jira.projects.assert_called_once_with()


@pytest.mark.parametrize("function_name", ["_session", "__class__", "request", "get", "post", "put", "delete"])
def test_catch_all_rejects_private_and_raw_http_methods(function_name):
    """Agent-controlled function names cannot access internals or raw HTTP methods."""
    wrapper = _wrapper()

    with pytest.raises(ValueError, match=f"Jira function not allowed: {function_name}"):
        wrapper.run("other", json.dumps({"function": function_name}))


def test_create_confluence_page_forwards_json_arguments():
    """The Confluence action continues sharing the Jira toolkit credentials."""
    wrapper = _wrapper()
    wrapper.confluence.create_page.return_value = {"id": "42"}

    result = wrapper.run("create_page", json.dumps({"space": "DEMO", "title": "Page", "body": "Body"}))

    assert result == {"id": "42"}
    wrapper.confluence.create_page.assert_called_once_with(space="DEMO", title="Page", body="Body")


def test_missing_credentials_are_reported_before_importing_optional_dependency(monkeypatch):
    """Misconfiguration produces a focused message without an unbound-client failure."""
    for variable in ("JIRA_USERNAME", "JIRA_API_TOKEN", "JIRA_OAUTH2", "JIRA_INSTANCE_URL", "JIRA_CLOUD"):
        monkeypatch.delenv(variable, raising=False)

    with pytest.raises(ValueError, match="Set JIRA_API_TOKEN or JIRA_OAUTH2"):
        JiraAPIWrapper()


def test_missing_cloud_configuration_is_reported(monkeypatch):
    """A missing JIRA_CLOUD value cannot silently select server authentication."""
    monkeypatch.setenv("JIRA_API_TOKEN", "secret")
    monkeypatch.setenv("JIRA_INSTANCE_URL", BASE_URL)
    monkeypatch.delenv("JIRA_CLOUD", raising=False)

    with pytest.raises(ValueError, match="Set JIRA_CLOUD"):
        JiraAPIWrapper()


@pytest.mark.parametrize("oauth2", ["not-json", "[]"])
def test_invalid_oauth2_configuration_has_clear_error(monkeypatch, oauth2):
    """Malformed or non-object OAuth2 configuration returns an instructive error."""
    monkeypatch.setenv("JIRA_OAUTH2", oauth2)
    monkeypatch.setenv("JIRA_INSTANCE_URL", BASE_URL)
    monkeypatch.setenv("JIRA_CLOUD", "true")
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)

    with pytest.raises(ValueError, match="JIRA_OAUTH2 must be a valid JSON object"):
        JiraAPIWrapper()


def test_token_only_authentication_is_shared_by_jira_and_confluence(monkeypatch):
    """PAT authentication uses the token argument for both Atlassian clients."""
    monkeypatch.setenv("JIRA_API_TOKEN", "secret")
    monkeypatch.setenv("JIRA_INSTANCE_URL", BASE_URL)
    monkeypatch.setenv("JIRA_CLOUD", "false")
    monkeypatch.delenv("JIRA_USERNAME", raising=False)
    jira_type = MagicMock()
    confluence_type = MagicMock()

    with (
        patch("neuro_san_studio.coded_tools.jira_toolkit.JIRA_TYPE", jira_type),
        patch("neuro_san_studio.coded_tools.jira_toolkit.CONFLUENCE_TYPE", confluence_type),
    ):
        JiraAPIWrapper()

    expected_args = {"url": BASE_URL, "cloud": False, "token": "secret"}
    jira_type.assert_called_once_with(**expected_args)
    confluence_type.assert_called_once_with(**expected_args)
