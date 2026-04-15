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
from typing import Awaitable
from typing import Callable
from typing import Literal
from typing import override

from langchain.agents.middleware.types import AgentMiddleware
from langchain.agents.middleware.types import AgentState
from langchain.agents.middleware.types import ContextT
from langchain.agents.middleware.types import ModelRequest
from langchain.agents.middleware.types import ModelResponse
from langchain.agents.middleware.types import ResponseT
from langchain_core.messages import BaseMessage
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langchain_core.tools import StructuredTool
from langgraph.runtime import Runtime

ChecklistStatus = Literal["pending", "in_progress", "done", "skipped"]

VALID_STATUSES: set[str] = {"pending", "in_progress", "done", "skipped"}

STATUS_SYMBOLS: dict[str, str] = {
    "pending": "[ ]",
    "in_progress": "[~]",
    "done": "[x]",
    "skipped": "[-]",
}


class AgentChecklistMiddleware(AgentMiddleware):
    """
    Middleware for managing a persistent in-memory checklist during agent execution.

    The checklist is stored as an instance variable so it persists across all model
    calls within a single agent session. The agent can create and update the checklist
    via registered tools, and the current checklist state is automatically injected
    into the system prompt before each model call.

    Usage Pattern:
        1. Optionally pre-populate with ``initial_checklist`` at init time
        2. ``awrap_model_call()``: injects current checklist state into system prompt
        3. Agent calls ``create_checklist`` to create or replace the checklist
        4. Agent calls ``update_checklist_item`` to mark items done/skipped/etc.
        5. Agent calls ``get_checklist`` to read the current checklist state

    Checklist Item Schema:
        Each item is a dict with:
        - ``item``: str — description of the task
        - ``status``: str — one of "pending", "in_progress", "done", "skipped"
        - ``notes``: str — optional notes (default empty string)

    Example:
        .. code-block:: python

            middleware = AgentChecklistMiddleware(
                checklist_title="Deployment Steps",
                initial_checklist=[
                    {"item": "Run tests", "status": "pending"},
                    {"item": "Build Docker image", "status": "pending"},
                ],
            )
    """

    def __init__(
        self,
        checklist_title: str = "Task Checklist",
        initial_checklist: list[dict[str, str]] | None = None,
    ) -> None:
        """Initialize the checklist middleware.

        :param checklist_title: Display title used in system prompt injection
        :param initial_checklist: Optional list of items to pre-populate.
            Each item should be a dict with ``item`` (required), ``status``
            (optional, defaults to "pending"), and ``notes`` (optional).
        """
        self.checklist_title: str = checklist_title
        self.checklist: list[dict[str, str]] = []

        if initial_checklist:
            for entry in initial_checklist:
                self.checklist.append(self._normalize_item(entry))

        self.tools: list[BaseTool] = [
            self._create_create_checklist_tool(),
            self._create_update_checklist_item_tool(),
            self._create_get_checklist_tool(),
        ]

        self.logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # AgentMiddleware hooks
    # ------------------------------------------------------------------

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
    ) -> ModelResponse[ResponseT]:
        """Inject current checklist state into system prompt before model call.

        :param request: Model request containing messages and state
        :param handler: Handler to execute the model call
        :return: Model response from handler
        """
        checklist_prompt: str = self._format_checklist_prompt()

        if checklist_prompt:
            system_message: BaseMessage | None = request.system_message
            if system_message is not None:
                original_content = system_message.content if isinstance(system_message.content, str) else ""
                system_message = SystemMessage(content=f"{original_content}\n\n{checklist_prompt}")
            else:
                system_message = SystemMessage(content=checklist_prompt)
            return await handler(request.override(system_message=system_message))

        return await handler(request)

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    async def create_checklist(self, items: list[str]) -> str:
        """Create or replace the checklist with a new list of items.

        All new items start with status "pending". Any existing checklist is
        replaced entirely.

        :param items: List of item descriptions
        :return: Confirmation message with the created checklist
        """
        if not items:
            return "Error: Cannot create an empty checklist. Provide at least one item."

        self.checklist = [{"item": item.strip(), "status": "pending", "notes": ""} for item in items if item.strip()]

        self.logger.info("Checklist created with %d items", len(self.checklist))
        return f"Checklist created with {len(self.checklist)} items.\n\n{self.get_checklist()}"

    async def update_checklist_item(
        self,
        item_index: int,
        status: str,
        notes: str = "",
    ) -> str:
        """Update the status (and optionally notes) of a checklist item.

        :param item_index: 1-based index of the item to update
        :param status: New status — one of "pending", "in_progress", "done", "skipped"
        :param notes: Optional notes to attach to the item
        :return: Confirmation message or error
        """
        if not self.checklist:
            return "Error: No checklist exists. Use create_checklist first."

        if status not in VALID_STATUSES:
            return f"Error: Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}"

        # Convert to 0-based index
        idx = item_index - 1
        if idx < 0 or idx >= len(self.checklist):
            return (
                f"Error: Item index {item_index} is out of range. "
                f"Checklist has {len(self.checklist)} item(s) (use 1-based index)."
            )

        self.checklist[idx]["status"] = status
        if notes:
            self.checklist[idx]["notes"] = notes

        item_desc = self.checklist[idx]["item"]
        self.logger.info("Checklist item %d updated to '%s': %s", item_index, status, item_desc)
        return f"Item {item_index} updated to '{status}': {item_desc}\n\n{self.get_checklist()}"

    def get_checklist(self) -> str:
        """Return the current checklist as a formatted string.

        :return: Formatted checklist or message if empty
        """
        if not self.checklist:
            return "Checklist is empty."

        lines: list[str] = [f"## {self.checklist_title}", ""]
        for i, entry in enumerate(self.checklist, start=1):
            symbol = STATUS_SYMBOLS.get(entry["status"], "[ ]")
            lines.append(f"{i}. {symbol} {entry['item']}")
            if entry.get("notes"):
                lines.append(f"   > {entry['notes']}")

        total = len(self.checklist)
        done = sum(1 for e in self.checklist if e["status"] == "done")
        skipped = sum(1 for e in self.checklist if e["status"] == "skipped")
        lines.extend(["", f"Progress: {done}/{total} done, {skipped} skipped"])

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Tool factories
    # ------------------------------------------------------------------

    def _create_create_checklist_tool(self) -> BaseTool:
        """Create tool for creating or replacing the checklist.

        :return: StructuredTool for checklist creation
        """
        return StructuredTool.from_function(
            coroutine=self.create_checklist,
            name="create_checklist",
            description=(
                "Create or replace the task checklist with a list of items. "
                "All items start as 'pending'. Any existing checklist is replaced entirely. "
                "Use this to set up the steps or tasks to be tracked."
            ),
            args_schema={
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of task descriptions to add to the checklist",
                    }
                },
                "required": ["items"],
            },
            tags=["langchain_tool"],
        )

    def _create_update_checklist_item_tool(self) -> BaseTool:
        """Create tool for updating a checklist item's status.

        :return: StructuredTool for item status updates
        """
        return StructuredTool.from_function(
            coroutine=self.update_checklist_item,
            name="update_checklist_item",
            description=(
                "Update the status of a checklist item. "
                "Valid statuses: 'pending', 'in_progress', 'done', 'skipped'. "
                "Use 1-based item index as shown in the checklist."
            ),
            args_schema={
                "type": "object",
                "properties": {
                    "item_index": {
                        "type": "integer",
                        "description": "1-based index of the checklist item to update",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "done", "skipped"],
                        "description": "New status for the item",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional notes to attach to the item (e.g. outcome, error message)",
                    },
                },
                "required": ["item_index", "status"],
            },
            tags=["langchain_tool"],
        )

    def _create_get_checklist_tool(self) -> BaseTool:
        """Create tool for reading the current checklist.

        :return: StructuredTool for checklist retrieval
        """
        return StructuredTool.from_function(
            # Synchronous — no I/O needed
            func=self.get_checklist,
            name="get_checklist",
            description=(
                "Get the current checklist with all items and their statuses. "
                "Use this to review what has been done and what remains."
            ),
            args_schema={
                "type": "object",
                "properties": {},
                "required": [],
            },
            tags=["langchain_tool"],
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _normalize_item(self, entry: dict[str, str]) -> dict[str, str]:
        """Normalize a checklist item dict, filling in defaults.

        :param entry: Raw item dict (may be missing ``status`` or ``notes``)
        :return: Normalized item with all required keys
        """
        status = entry.get("status", "pending")
        if status not in VALID_STATUSES:
            self.logger.warning("Invalid status '%s' in initial checklist item; defaulting to 'pending'", status)
            status = "pending"
        return {
            "item": entry.get("item", "").strip(),
            "status": status,
            "notes": entry.get("notes", ""),
        }

    def _format_checklist_prompt(self) -> str:
        """Format checklist for injection into system prompt.

        :return: Formatted checklist section, or empty string if checklist is empty
        """
        if not self.checklist:
            return ""

        lines: list[str] = [
            f"## {self.checklist_title}",
            "",
            "Track your progress using the checklist below. "
            "Update item statuses with `update_checklist_item` as you complete each step.",
            "",
        ]

        for i, entry in enumerate(self.checklist, start=1):
            symbol = STATUS_SYMBOLS.get(entry["status"], "[ ]")
            lines.append(f"{i}. {symbol} {entry['item']}")
            if entry.get("notes"):
                lines.append(f"   > {entry['notes']}")

        total = len(self.checklist)
        done = sum(1 for e in self.checklist if e["status"] == "done")
        skipped = sum(1 for e in self.checklist if e["status"] == "skipped")
        lines.extend(["", f"Progress: {done}/{total} done, {skipped} skipped", ""])

        return "\n".join(lines)
