# Copyright © 2025 Cognizant Technology Solutions Corp, www.cognizant.com.
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
from pathlib import Path
import re
from re import DOTALL
from re import Match
from typing import Any, Awaitable, Callable
from urllib.parse import urljoin

import aiofiles
from aiohttp import ClientError
from aiohttp import ClientSession
from aiohttp import ClientTimeout
from yaml import safe_load
from yaml import YAMLError

from langchain.agents.middleware.types import AgentMiddleware
from langchain.agents.middleware.types import AgentState
from langchain.agents.middleware.types import ContextT
from langchain.agents.middleware.types import ModelRequest
from langchain.agents.middleware.types import ModelResponse
from langchain.agents.middleware.types import ResponseT
from langchain_core.messages import BaseMessage
from langchain_core.messages import SystemMessage
from langchain_core.messages import ToolMessage
from langchain_core.messages.tool import ToolCall
from langchain_core.tools import BaseTool
from langchain_core.tools import StructuredTool
from langgraph.runtime import Runtime
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command


class AgentSkillsMiddleware(AgentMiddleware):
    """
    Middleware for loading and managing agent skills per Agent Skills specification.

    This middleware implements the Agent Skills specification (https://agentskills.io/specification)
    using a progressive disclosure pattern to minimize token usage while maintaining full capability.

    Progressive Disclosure Pattern:
        1. **At Initialization**: Skill metadata (name, description, path) loaded from all sources
        2. **On Demand**: Full SKILL.md content retrieved only when agent activates a skill
        3. **Selective**: Additional resources (scripts/, references/, assets/) loaded only when referenced

    Skill Sources:
        Supports both local filesystem paths and remote URLs:
        - Local: "/path/to/skills/my-skill/"
        - Remote: "https://example.com/skills/my-skill/"

    Available Tools:
        Three tools are registered for agent use:
        - `get_full_skill_content`: Loads complete SKILL.md with instructions
        - `load_skill_resource_local`: Loads additional files from local filesystem
        - `load_skill_resource_remote`: Loads additional files from remote URLs

    Execution Workflow:
        1. `abefore_agent()`: Scans skill sources and caches SKILL.md metadata
        2. `awrap_model_call()`: Injects available skills list into system prompt
        3. Agent decides to use a skill and calls `get_full_skill_content(skill_name='...')`
        4. Agent optionally loads additional resources via `load_skill_resource_*` tools
        5. `awrap_tool_call()`: Optionally intercepts tool calls to avoid putting skill content in the chat context
            (if keep_skill_in_context=False)
    """

    def __init__(
        self,
        skill_sources: list[str],
        keep_skill_in_context: bool = False,
        http_timeout: float = 30.0
    ) -> None:
        """Initialize the skills middleware.

        :param skill_sources: Directories or URLs to scan for SKILL.md files
        :param keep_skill_in_context: Whether to keep full skill content in chat context
        :param http_timeout: Timeout in seconds for HTTP requests (default: 30.0)
        """
        self.skill_sources: list[str] = skill_sources
        self.skills_dict: dict[str, dict[str, Any]] = {}
        self.keep_skill_in_context: bool = keep_skill_in_context

        # Session will be created in abefore_agent, and closed in aafter_agent
        self._session: ClientSession | None = None
        self._timeout = ClientTimeout(total=http_timeout, connect=http_timeout/3, sock_read=http_timeout)

        # Register tools per Agent Skills progressive disclosure pattern
        # This is equivalent to adding tools in the network hocon file
        # These tools are essentially calling the method in this middleware.
        self.tools: list[BaseTool] = [
            self._create_get_full_skill_content_tool(),
            self._create_load_skill_resource_local_tool(),
            self._create_load_skill_resource_remote_tool(),
        ]

        self.logger = logging.getLogger(__name__)

    async def get_full_skill_content(self, skill_name: str) -> str:
        """Get the full SKILL.md content for a specified skill.

        :param skill_name: Name of the skill as defined in YAML frontmatter
        :return: Full content of SKILL.md file or error message
        """
        skill: dict[str, Any] = self.skills_dict.get(skill_name)
        if not skill:
            available = ", ".join(self.skills_dict.keys())
            return f"Error: Skill '{skill_name}' not found. Available skills: {available}"

        content: str = skill.get("content", "")
        skill_path: str = skill.get("path", "")

        # Extract directory path for relative file references
        if skill_path.startswith(("http://", "https://")):
            # URL-based skill
            skill_dir = skill_path.rsplit("/", 1)[0]
            resource_tool: str = "load_skill_resource_remote"
        else:
            # Local filesystem skill
            skill_dir = str(Path(skill_path).parent)
            resource_tool = "load_skill_resource_local"

        # Prepend skill location info per progressive disclosure pattern
        full_content: str = f"""
## Skill Location Information

**Skill Directory**: `{skill_dir}`

**For Additional Resources**:
- This skill's files are located at: `{skill_dir}`
- To load additional files mentioned below, use `{resource_tool}` tool
- For relative paths like `references/REFERENCE.md`, construct full path as: `{skill_dir}/references/REFERENCE.md`

---

{content}
"""
        return full_content

    def _create_get_full_skill_content_tool(self) -> BaseTool:
        """
        Create tool to retrieve full SKILL.md content.

        :return: StructuredTool for loading skill content
        """
        return StructuredTool.from_function(
            # Use coroutine to have the tool run async
            coroutine=self.get_full_skill_content,
            name="get_full_skill_content",
            description=(
                "Load the complete SKILL.md content for a skill. "
                "Use this when you need full instructions for a specific skill. "
                "The skill name must match one of the available skills listed in the system prompt."
            ),
            args_schema={
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "Name of the skill (must match skill name from available skills list)"
                    }
                },
                "required": ["skill_name"]
            },
            # This is so neuro-san can write the journal and put tool response in context
            tags=["langchain_tool"]
        )

    async def load_skill_resource_local(self, resource_path: str) -> str:
        """Load additional skill resource from local filesystem.

        :param resource_path: Absolute or relative path to resource file
        :return: File content or error message
        """

        is_valid, error = await self._validate_resource_path(resource_path, is_url=False)
        if not is_valid:
            return error

        path = Path(resource_path)

        if not path.exists():
            return f"Error: Resource file not found: {resource_path}"

        try:
            async with aiofiles.open(path, mode='r', encoding='utf-8') as file:
                return await file.read()
        except UnicodeDecodeError as unicode_error:
            return f"Error: Unable to decode file as UTF-8: {unicode_error}"
        except IOError as io_error:
            return f"Error: Failed to read file: {io_error}"

    def _create_load_skill_resource_local_tool(self) -> BaseTool:
        """Create tool to load additional skill resources from filesystem.

        :return: StructuredTool for loading local resources
        """
        return StructuredTool.from_function(
            # Use coroutine to have the tool run async
            coroutine=self.load_skill_resource_local,
            name="load_skill_resource_local",
            description=(
                "Load additional skill resource files from local filesystem. "
                "Use this for files referenced in SKILL.md such as scripts/, references/, or assets/. "
                "Provide the full path as shown in the skill's location information."
            ),
            args_schema={
                "type": "object",
                "properties": {
                    "resource_path": {
                        "type": "string",
                        "description": (
                            "Full path to the resource file. "
                            "Example: skills/my-skill/references/REFERENCE.md"
                        )
                    }
                },
                "required": ["resource_path"]
            },
            # This is so neuro-san can write the journal and put tool response in context
            tags=["langchain_tool"]
        )

    async def load_skill_resource_remote(self, resource_url: str) -> str:
        """Load additional skill resource from remote URL.

        :param resource_url: Full URL to resource file
        :return: File content or error message
        """
        if self._session is None:
            return "Error: HTTP session not initialized. Skills must be loaded first."

        # Validate that URL is under an skill source to prevent security issue
        is_valid, error = await self._validate_resource_path(resource_url, is_url=True)
        if not is_valid:
            return error

        try:
            async with self._session.get(resource_url) as response:
                if response.status != 200:
                    return f"Error: HTTP {response.status} when fetching {resource_url}"
                message: str = await response.text()
        except asyncio.TimeoutError:
            message = f"Error: Timeout fetching {resource_url} (>{self._timeout.total}s)"
        except ClientError as client_error:
            message = f"Error: Network error loading {resource_url}: {client_error}"
        except UnicodeDecodeError as unicode_error:
            message = f"Error: Unable to decode response as UTF-8: {unicode_error}"

        return message

    def _create_load_skill_resource_remote_tool(self) -> BaseTool:
        """Create tool to load additional skill resources from URLs.

        :return: StructuredTool for loading remote resources
        """
        return StructuredTool.from_function(
            # Use coroutine to have the tool run async
            coroutine=self.load_skill_resource_remote,
            name="load_skill_resource_remote",
            description=(
                "Load additional skill resource files from remote URLs. "
                "Use this for files referenced in SKILL.md when the skill is hosted remotely. "
                "Provide the full URL as shown in the skill's location information."
            ),
            args_schema={
                "type": "object",
                "properties": {
                    "resource_url": {
                        "type": "string",
                        "description": (
                            "Full URL to the resource file. "
                            "Example: https://example.com/skills/my-skill/references/REFERENCE.md"
                        )
                    }
                },
                "required": ["resource_url"]
            },
            # This is so neuro-san can write the journal and put tool response in context
            tags=["langchain_tool"]
        )

    async def _validate_resource_path(self, resource_path: str, is_url: bool) -> tuple[bool, str]:
        """
        Validate that resource path is under a configured skill source.

        :param resource_path: Path or URL to validate
        :param is_url: True if validating URL, False if validating filesystem path
        :return: (is_valid, error_message) - error_message empty if valid
        """
        for skill_source in self.skill_sources:
            source_is_url = skill_source.startswith(("http://", "https://"))

            # Match type: URL validation for URLs, path validation for paths
            if source_is_url != is_url:
                continue

            if is_url:
                # URL validation
                base_url = skill_source.rstrip("/") + "/"
                if resource_path.startswith(base_url):
                    return True, ""
            else:
                # Filesystem path validation (resolve to prevent ../ attacks)
                try:
                    source_resolved = Path(skill_source).resolve()
                    resource_resolved = Path(resource_path).resolve()
                    if resource_resolved.is_relative_to(source_resolved):
                        return True, ""
                except (ValueError, OSError):
                    continue

        return False, f"Error: Path {resource_path} not under any configured skill source"

    async def _load_skills(self) -> None:
        """Scan all skill sources and load metadata from SKILL.md files.

        Implements progressive disclosure: only loads YAML frontmatter and description,
        full content of SKILL.md is cached for later retrieval via tools.

        :raises: Logs warnings for invalid skills but continues processing
        """

        for skill_source in self.skill_sources:
            is_url: bool = skill_source.startswith(("http://", "https://"))

            try:
                if is_url:
                    skill_md_url: str = urljoin(skill_source.rstrip("/") + "/", "SKILL.md")
                    content: str = await self.load_skill_resource_remote(skill_md_url)
                    skill_path: str = skill_md_url
                else:
                    source_path = Path(skill_source)
                    skill_md_path = source_path / "SKILL.md"
                    content: str = await self.load_skill_resource_local(str(skill_md_path))
                    skill_path = str(skill_md_path)

                if content.startswith("Error:"):
                    self.logger.warning("Skipping skill source %s: %s", skill_source, content)
                    continue

                parsed_skill: dict[str, Any] = await self._parse_skill_metadata(content, skill_path)
                if parsed_skill:
                    # Later sources override earlier ones (last one wins)
                    self.skills_dict[parsed_skill["name"]] = parsed_skill

            # pylint: disable=broad-exception-caught
            except Exception as error:
                self.logger.warning("Unexpected error loading skill from %s: %s", skill_source, error)

        self.logger.info("Loaded %d skills: %s", len(self.skills_dict), list(self.skills_dict.keys()))

    # pylint: disable=too-many-return-statements
    async def _parse_skill_metadata(
        self,
        content: str,
        skill_path: str,
    ) -> dict[str, Any] | None:
        """Parse YAML frontmatter and validate per Agent Skills specification (https://agentskills.io/specification).

        :param content: Full SKILL.md file content
        :param skill_path: Path or URL to SKILL.md (for error reporting)
        :return: Parsed skill metadata dictionary or None if invalid
        """
        # Extract YAML frontmatter per Agent Skills spec
        frontmatter_pattern: str = r"^---\s*\n(.*?)\n---\s*\n"
        match: Match[str] | None = re.match(frontmatter_pattern, content, DOTALL)

        if not match:
            self.logger.warning("No YAML frontmatter in %s (required per Agent Skills spec)", skill_path)
            return None

        try:
            frontmatter: dict[str, Any] = safe_load(match.group(1))
        except YAMLError as e:
            self.logger.warning("Invalid YAML frontmatter in %s: %s", skill_path, e)
            return None

        if not isinstance(frontmatter, dict):
            self.logger.warning("Frontmatter must be YAML mapping in %s", skill_path)
            return None

        # Validate required fields per Agent Skills spec
        name: str = frontmatter.get("name", "").strip()
        description: str = frontmatter.get("description", "").strip()

        if not name:
            self.logger.warning("Missing required 'name' field in %s", skill_path)
            return None

        if not description:
            self.logger.warning("Missing required 'description' field in %s", skill_path)
            return None

        # Validate name constraints per spec
        is_valid_skill_name: bool = await self._validate_skill_name(name)
        if not is_valid_skill_name:
            self.logger.warning(
                "Skill name '%s' in %s violates Agent Skills spec constraints "
                "(must be 1-64 chars, lowercase alphanumeric and hyphens only, "
                "no leading/trailing hyphens, no consecutive hyphens)",
                name,
                skill_path
            )
            return None

        # Validate description length per spec
        if len(description) > 1024:
            self.logger.warning(
                "Description exceeds 1024 character limit in %s (truncating)",
                skill_path
            )
            description = description[:1024]

        return {
            "name": name,
            "description": description,
            "content": content,
            "path": skill_path,
            "allowed_tools": await self._parse_allowed_tools(frontmatter.get("allowed-tools")),
            "license": frontmatter.get("license", "").strip() or None,
            "compatibility": frontmatter.get("compatibility", "").strip() or None,
        }

    async def _validate_skill_name(self, name: str) -> bool:
        """Validate skill name per Agent Skills specification.

        :param name: Skill name to validate
        :return: True if valid, False otherwise
        """
        if not name or len(name) > 64:
            return False

        if name.startswith("-") or name.endswith("-") or "--" in name:
            return False

        # Must be lowercase alphanumeric and hyphens only
        return all(
            c == "-" or (c.isalpha() and c.islower()) or c.isdigit()
            for c in name
        )

    async def _parse_allowed_tools(self, allowed_tools_value: None | str | list[str]) -> list[str]:
        """
        Parse allowed-tools field from YAML frontmatter.

        Handles multiple YAML formats:
        - None (key present but empty)
        - String (space-delimited tool names)
        - List (YAML list format)

        :param allowed_tools_value: Value from YAML frontmatter
        :return: List of tool names
        """
        if allowed_tools_value is None:
            return []

        if isinstance(allowed_tools_value, list):
            # YAML list format: ['tool1', 'tool2']
            return [str(tool).strip() for tool in allowed_tools_value if tool]

        if isinstance(allowed_tools_value, str):
            # Space-delimited string format: "tool1 tool2"
            return [tool.strip() for tool in allowed_tools_value.split() if tool.strip()]

        # Unexpected type - log warning and return empty
        self.logger.warning(
            "allowed-tools has unexpected type %s, expected str or list. Ignoring.",
            type(allowed_tools_value).__name__
        )
        return []

    async def _format_skills_prompt(self) -> str:
        """Generate skills section for system prompt per progressive disclosure pattern.

        :return: Formatted skills prompt section
        """
        if not self.skills_dict:
            return ""

        lines: list[str] = [
            "## Available Skills",
            "",
            "You have access to specialized skills that provide domain knowledge and structured workflows.",
            ""
        ]

        for skill in self.skills_dict.values():
            lines.append(f"**{skill['name']}**")
            lines.append(f"  - Description: {skill['description']}")
            lines.append(f"  - Location: `{skill['path']}`")

            if skill.get("compatibility"):
                lines.append(f"  - Compatibility: {skill['compatibility']}")

            if skill.get("allowed_tools"):
                lines.append(f"  - Recommended tools: {', '.join(skill['allowed_tools'])}")

            lines.append("")

        lines.extend([
            "## How to Use Skills (Progressive Disclosure)",
            "",
            "Skills follow the Agent Skills specification (https://agentskills.io/specification):",
            "",
            "1. **Identify relevant skill**: Match the user's request to a skill description above",
            "2. **Load full instructions**: Use `get_full_skill_content(skill_name='...')` to load SKILL.md",
            "3. **Follow the workflow**: Execute step-by-step instructions from SKILL.md",
            "4. **Load additional resources**: If SKILL.md references other files:",
            "   - For local skills: Use `load_skill_resource_local(resource_path='...')`",
            "   - For remote skills: Use `load_skill_resource_remote(resource_url='...')`",
            "   - Always use the full path/URL shown in the skill location information",
            "",
            "**Important**: Skills use relative paths. When you load a skill, you'll receive",
            "the skill directory location. Prepend this to any relative file references.",
            "",
        ])

        return "\n".join(lines)

    async def abefore_agent(
        self,
        state: AgentState,
        runtime: Runtime[ContextT]
    ) -> dict[str, Any] | None:
        """
        Create HTTP session and load skills metadata and cache the content of SKILL.md before agent execution starts.

        :param state: Current agent state
        :param runtime: Runtime context
        :return: None (skills loaded into instance variable, not state)
        """

        # Create shared session for this agent execution
        if self._session is None:
            self._session = ClientSession(timeout=self._timeout)

        # Load skills if not already loaded
        if not self.skills_dict:
            await self._load_skills()

    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
    ) -> ModelResponse[ResponseT]:
        """Inject skills metadata into system prompt before model call.

        :param request: Model request containing messages and state
        :param handler: Handler to execute the model call
        :return: Model response from handler
        """

        # Inject skills section into system message
        messages: list[BaseMessage] = list(request.messages)
        skills_prompt: str = await self._format_skills_prompt()

        # If there is a skills prompt to inject
        if skills_prompt:
            if messages and isinstance(messages[0], SystemMessage):
                original_content: str = messages[0].content
                new_content: str = f"{original_content}\n\n{skills_prompt}"
                messages[0] = SystemMessage(content=new_content)
            else:
                messages.insert(0, SystemMessage(content=skills_prompt))

        return await handler(request.override(messages=messages))

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]]
    ) -> ToolMessage | Command[Any]:
        """
        Tool messages for langchain BaseTool are written in the journal and put in chat context with
        JournalingCallbackHandler.on_tool_start() and JournalingCallbackHandler.on_tool_end().
        These can be prevented by intercepting the tool call request and calling the methods directly instead.

        :param request: Tool call request
        :param handler: Handler to execute the tool call
        :return: Skill content as Tool message if keep_skill_in_context is False,
                    otherwise original command from handler
        """
        tool_call: ToolCall = request.tool_call
        tool_name: str = tool_call.get("name", "")
        tool_call_id: str = tool_call.get("id", "")

        # If not keeping full content in context, bypasses the handler and calls middleware methods directly
        if not self.keep_skill_in_context and tool_name in {
            "get_full_skill_content",
            "load_skill_resource_local",
            "load_skill_resource_remote"
        }:

            content: str = ""
            # Call the method directly instead of executing the tool to get content
            if tool_name == "get_full_skill_content":
                skill_name = tool_call.get("args", {}).get("skill_name")
                if not skill_name:
                    content = "Error: No 'skill_name' provided"
                else:
                    content = await self.get_full_skill_content(skill_name)

            elif tool_name == "load_skill_resource_local":
                resource_path = tool_call.get("args", {}).get("resource_path")
                if not resource_path:
                    content = "Error: No 'resource_path' provided"
                else:
                    content = await self.load_skill_resource_local(resource_path)

            else:
                resource_url = tool_call.get("args", {}).get("resource_url")
                if not resource_url:
                    content = "Error: No 'resource_url' provided"
                else:
                    content = await self.load_skill_resource_remote(resource_url)

            # Return skill contents to the model
            return ToolMessage(content=content, tool_call_id=tool_call_id)

        # Execute tool and put all skill content in context
        return await handler(request)

    async def aafter_agent(
        self,
        state: AgentState,
        runtime: Runtime[ContextT]
    ) -> dict[str, Any] | None:
        """Close HTTP session after agent execution completes.

        :param state: Current agent state
        :param runtime: Runtime context
        :return: None
        """
        # Close the session
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None
