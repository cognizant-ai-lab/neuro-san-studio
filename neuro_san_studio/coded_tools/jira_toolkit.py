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

"""Jira and Confluence tools backed directly by atlassian-python-api."""

import json
import os
from typing import Any

from langchain_core.tools import BaseTool
from langchain_core.tools import BaseToolkit
from leaf_common.resolution.resolver_util import ResolverUtil
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import model_validator

CONFLUENCE_TYPE = ResolverUtil.create_type("atlassian.Confluence", raise_if_not_found=False)
JIRA_TYPE = ResolverUtil.create_type("atlassian.Jira", raise_if_not_found=False)
DISALLOWED_JIRA_FUNCTIONS = {"delete", "get", "post", "put", "request"}

JQL_QUERY_DESCRIPTION = """
Search for Jira issues using a JQL query string. For example:
project = Test AND assignee = currentUser()
"""
GET_PROJECTS_DESCRIPTION = "Fetch all Jira projects that the authenticated user can access."
CREATE_ISSUE_DESCRIPTION = """
Create a Jira issue. The input is a JSON object containing the fields accepted by Jira.issue_create.
"""
CATCH_ALL_DESCRIPTION = """
Call another atlassian-python-api Jira method. The input is a JSON object containing `function`, plus optional `args`
and `kwargs`. For example: {"function": "projects"}.
"""
CREATE_CONFLUENCE_PAGE_DESCRIPTION = """
Create a Confluence page. The input is a JSON object containing the arguments accepted by Confluence.create_page.
"""


def _parse_oauth2(value: dict[str, Any] | str | None) -> dict[str, Any] | None:
    """Parse and validate OAuth2 configuration supplied through the environment."""
    if not value:
        return None
    if isinstance(value, dict):
        return value
    try:
        parsed_value = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError("JIRA_OAUTH2 must be a valid JSON object.") from error
    if not isinstance(parsed_value, dict):
        raise ValueError("JIRA_OAUTH2 must be a valid JSON object.")
    return parsed_value


class JiraAPIWrapper(BaseModel):
    """Configure Atlassian clients and expose the operations used by the toolkit."""

    jira: Any = None
    confluence: Any = None
    jira_username: str | None = None
    jira_api_token: str | None = None
    jira_oauth2: dict[str, Any] | str | None = None
    jira_instance_url: str | None = None
    jira_cloud: bool | str | None = None

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    @model_validator(mode="before")
    @classmethod
    def configure_clients(cls, values: Any) -> Any:
        """Load credentials and construct Jira and Confluence clients."""
        if not isinstance(values, dict):
            return values

        values = dict(values)
        if values.get("jira") is not None and values.get("confluence") is not None:
            return values

        username = values.get("jira_username", os.getenv("JIRA_USERNAME", ""))
        api_token = values.get("jira_api_token", os.getenv("JIRA_API_TOKEN", ""))
        oauth2 = values.get("jira_oauth2", os.getenv("JIRA_OAUTH2", ""))
        instance_url = values.get("jira_instance_url", os.getenv("JIRA_INSTANCE_URL"))
        cloud_value = values.get("jira_cloud", os.getenv("JIRA_CLOUD"))

        oauth2 = _parse_oauth2(oauth2)

        if api_token and oauth2:
            raise ValueError("Provide either jira_api_token or jira_oauth2, not both.")
        if not api_token and not oauth2:
            raise ValueError("Set JIRA_API_TOKEN or JIRA_OAUTH2 before using jira_toolkit.")
        if not instance_url:
            raise ValueError("Set JIRA_INSTANCE_URL before using jira_toolkit.")
        if cloud_value is None:
            raise ValueError("Set JIRA_CLOUD before using jira_toolkit.")
        cloud = cloud_value if isinstance(cloud_value, bool) else str(cloud_value).lower() == "true"

        if CONFLUENCE_TYPE is None or JIRA_TYPE is None:
            raise ImportError(
                "Jira support requires 'atlassian-python-api'. Install it with: pip install atlassian-python-api"
            )

        common_args = {"url": instance_url, "cloud": cloud}
        if api_token:
            if username:
                jira_auth_args = {"username": username, "password": api_token}
            else:
                jira_auth_args = {"token": api_token}
            jira = JIRA_TYPE(**common_args, **jira_auth_args)
            confluence = CONFLUENCE_TYPE(**common_args, **jira_auth_args)
        else:
            jira = JIRA_TYPE(**common_args, oauth2=oauth2)
            confluence = CONFLUENCE_TYPE(**common_args, oauth2=oauth2)

        values.update(
            {
                "jira": jira,
                "confluence": confluence,
                "jira_username": username,
                "jira_api_token": api_token or None,
                "jira_oauth2": oauth2 or None,
                "jira_instance_url": instance_url,
                "jira_cloud": cloud,
            }
        )
        return values

    def search(self, query: str) -> str:
        """Search Jira and retain the established compact response format."""
        parsed_issues = []
        for issue in self.jira.jql(query)["issues"]:
            fields = issue["fields"]
            related_issues = {}
            for related_issue in fields.get("issuelinks", []):
                direction = "inwardIssue" if "inwardIssue" in related_issue else "outwardIssue"
                if direction not in related_issue:
                    continue
                linked_issue = related_issue[direction]
                related_issues = {
                    "type": related_issue["type"]["inward" if direction == "inwardIssue" else "outward"],
                    "key": linked_issue["key"],
                    "summary": linked_issue["fields"]["summary"],
                }
            assignee = fields.get("assignee") or {}
            parsed_issues.append(
                {
                    "key": issue["key"],
                    "summary": fields["summary"],
                    "created": fields["created"][:10],
                    "assignee": assignee.get("displayName", "None"),
                    "priority": (fields.get("priority") or {}).get("name"),
                    "status": fields["status"]["name"],
                    "related_issues": related_issues,
                }
            )
        return f"Found {len(parsed_issues)} issues:\n{parsed_issues}"

    def project(self) -> str:
        """List Jira projects and retain the established compact response format."""
        parsed_projects = [
            {
                "id": project["id"],
                "key": project["key"],
                "name": project["name"],
                "type": project.get("projectTypeKey"),
                "style": project.get("style"),
            }
            for project in self.jira.projects()
        ]
        return f"Found {len(parsed_projects)} projects:\n{parsed_projects}"

    def run(self, mode: str, instructions: str) -> Any:
        """Run one operation selected by a toolkit action."""
        if mode == "jql":
            return self.search(instructions)
        if mode == "get_projects":
            return self.project()

        params = json.loads(instructions)
        if mode == "create_issue":
            return self.jira.issue_create(fields=dict(params))
        if mode == "create_page":
            return self.confluence.create_page(**dict(params))
        if mode == "other":
            function_name = params["function"]
            if function_name.startswith("_") or function_name in DISALLOWED_JIRA_FUNCTIONS:
                raise ValueError(f"Jira function not allowed: {function_name}")
            jira_function = getattr(self.jira, function_name)
            return jira_function(*params.get("args", []), **params.get("kwargs", {}))
        raise ValueError(f"Unexpected Jira operation mode: {mode}")


class JiraAction(BaseTool):
    """One named operation exposed by JiraToolkit."""

    api_wrapper: JiraAPIWrapper = Field(default_factory=JiraAPIWrapper)
    mode: str

    def _run(self, instructions: str) -> Any:  # pylint: disable=arguments-differ
        """Delegate an invocation to the shared API wrapper."""
        return self.api_wrapper.run(self.mode, instructions)


class JiraToolkit(BaseToolkit):
    """Build the agent-facing Jira tools from a shared Atlassian client."""

    jira_api_wrapper: JiraAPIWrapper = Field(default_factory=JiraAPIWrapper)

    def get_tools(self) -> list[BaseTool]:
        """Return tools with names and arguments compatible with the previous toolkit."""
        operations = (
            ("jql_query", "jql", JQL_QUERY_DESCRIPTION),
            ("get_projects", "get_projects", GET_PROJECTS_DESCRIPTION),
            ("create_issue", "create_issue", CREATE_ISSUE_DESCRIPTION),
            ("catch_all_jira_api", "other", CATCH_ALL_DESCRIPTION),
            ("create_confluence_page", "create_page", CREATE_CONFLUENCE_PAGE_DESCRIPTION),
        )
        return [
            JiraAction(name=name, description=description, mode=mode, api_wrapper=self.jira_api_wrapper)
            for name, mode, description in operations
        ]
