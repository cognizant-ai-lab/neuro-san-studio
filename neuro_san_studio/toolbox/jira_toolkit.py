# Copyright © 2025-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Project-owned Jira toolkit backed directly by atlassian-python-api."""

import os
from typing import Any

from langchain_core.tools import BaseTool
from langchain_core.tools import StructuredTool
from langchain_core.tools.base import BaseToolkit


class JiraToolkit(BaseToolkit):
    """Expose the commonly used Jira operations without langchain-community."""

    def get_tools(self) -> list[BaseTool]:
        jira = self._create_client()

        def jql_query(query: str) -> Any:
            """Search Jira issues with a JQL query."""
            return jira.jql(query)

        def get_projects() -> Any:
            """Return Jira projects visible to the current user."""
            return jira.projects()

        def create_issue(fields: dict[str, Any]) -> Any:
            """Create a Jira issue from its fields dictionary."""
            return jira.issue_create(fields)

        def catch_all_jira_api(
            function: str, args: list[Any] | None = None, kwargs: dict[str, Any] | None = None
        ) -> Any:
            """Call an atlassian-python-api Jira method by name."""
            if function.startswith("_"):
                raise ValueError("Private Jira methods are not allowed")
            method = getattr(jira, function)
            if not callable(method):
                raise ValueError(f"Jira attribute '{function}' is not callable")
            return method(*(args or []), **(kwargs or {}))

        return [
            StructuredTool.from_function(jql_query),
            StructuredTool.from_function(get_projects),
            StructuredTool.from_function(create_issue),
            StructuredTool.from_function(catch_all_jira_api),
        ]

    @staticmethod
    def _create_client() -> Any:
        # pylint: disable=import-error,import-outside-toplevel
        from atlassian import Jira

        return Jira(
            url=os.environ["JIRA_INSTANCE_URL"],
            username=os.getenv("JIRA_USERNAME"),
            password=os.getenv("JIRA_API_TOKEN"),
            cloud=os.getenv("JIRA_CLOUD", "true").lower() == "true",
        )
