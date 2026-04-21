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

from logging import Logger
from logging import getLogger
from typing import Awaitable
from typing import Callable
from typing import override

from langchain.agents.middleware.types import AgentMiddleware
from langchain.agents.middleware.types import ContextT
from langchain.agents.middleware.types import ModelRequest
from langchain.agents.middleware.types import ModelResponse
from langchain.agents.middleware.types import ResponseT
from langchain_core.messages import BaseMessage
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langchain_core.tools import StructuredTool
from neuro_san.interfaces.agent_progress_reporter import AgentProgressReporter

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
        5. Agent calls ``edit_checklist_item`` to rewrite a step when the plan changes
        6. Current state is always visible to the agent via the injected system prompt

    Checklist Item Schema:
        Each item is a dict with:
        - ``item``: str — description of the task
        - ``status``: str — one of "pending", "in_progress", "done", "skipped"
        - ``notes``: str — optional notes (default empty string)

    Future Considerations:
        The checklist currently lives only in memory for the duration of the agent session.
        A future implementation may consider persisting the checklist (e.g. to a file or
        database) so that progress can survive agent restarts or be shared across sessions.

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
        progress_reporter: AgentProgressReporter | None = None,
    ) -> None:
        """Initialize the checklist middleware.

        :param checklist_title: Display title used in system prompt injection
        :param initial_checklist: Optional list of items to pre-populate.
            Each item should be a dict with ``item`` (required), ``status``
            (optional, defaults to "pending"), and ``notes`` (optional).
        :param progress_reporter: Optional progress reporter for emitting checklist
            progress (0.0–1.0) to the client. Injected automatically by the framework
            when ``"progress_reporter": null`` is listed in the middleware ``args``.
        """
        self.logger: Logger = getLogger(__name__)
        self.checklist_title: str = checklist_title
        self.checklist: list[dict[str, str]] = []
        self.progress_reporter: AgentProgressReporter | None = progress_reporter

        if initial_checklist:
            for entry in initial_checklist:
                self.checklist.append(self._normalize_item(entry))

        self.tools: list[BaseTool] = [
            self._create_create_checklist_tool(),
            self._create_update_checklist_item_tool(),
            self._create_edit_checklist_item_tool(),
        ]

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
        checklist_prompt: str = await self._format_checklist_prompt()

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

        :param items: List of item descriptions. If empty (or all blank), the checklist is cleared.
        :return: Formatted checklist prompt, or empty string if no items were provided
        """
        # Strip whitespace from each item and discard any that are blank after stripping
        stripped_items: list[str] = []
        for item in items:
            if item.strip():
                stripped_items.append(item.strip())

        # Reset the checklist with new items, all starting as "pending".
        # An empty input is treated as a no-op clear rather than an error,
        # since a dynamic generation process may legitimately produce zero items.
        self.checklist = []
        for item in stripped_items:
            self.checklist.append({"item": item, "status": "pending", "notes": ""})

        self.logger.info("Checklist created with %d items", len(self.checklist))

        # Returns the formatted checklist.
        # This is actually not necessary since the agent will see the updated checklist in the next model call,
        # but it can be helpful for debugging.
        return await self._format_checklist_prompt()

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
        :return: Formatted checklist prompt or error message
        """
        if not self.checklist:
            return "Error: No checklist exists. Use create_checklist first."

        if status not in VALID_STATUSES:
            return f"Error: Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}"

        # Convert to 0-based index
        idx: int = item_index - 1
        if idx < 0 or idx >= len(self.checklist):
            return (
                f"Error: Item index {item_index} is out of range. "
                f"Checklist has {len(self.checklist)} item(s) (use 1-based index)."
            )

        self.checklist[idx]["status"] = status
        if notes:
            self.checklist[idx]["notes"] = notes

        item_desc: str = self.checklist[idx].get("item", "Unknown item")
        self.logger.info("Checklist item %d updated to '%s': %s", item_index, status, item_desc)

        # Returns the formatted checklist.
        # This is actually not necessary since the agent will see the updated checklist in the next model call,
        # but it can be helpful for debugging.
        return await self._format_checklist_prompt()

    async def edit_checklist_item(self, item_index: int, new_item: str) -> str:
        """Rewrite the description of a checklist item without changing its status or notes.

        Use this when the plan changes and a step needs to be replaced with a different
        approach. The item's current status and notes are preserved.

        :param item_index: 1-based index of the item to edit
        :param new_item: New description for the item
        :return: Formatted checklist prompt or error message
        """
        if not self.checklist:
            return "Error: No checklist exists. Use create_checklist first."

        if not new_item or not new_item.strip():
            return "Error: new_item cannot be empty."

        idx = item_index - 1
        if idx < 0 or idx >= len(self.checklist):
            return (
                f"Error: Item index {item_index} is out of range. "
                f"Checklist has {len(self.checklist)} item(s) (use 1-based index)."
            )

        old_desc: str = self.checklist[idx].get("item", "Unknown item")
        self.checklist[idx]["item"] = new_item.strip()

        self.logger.info("Checklist item %d rewritten: '%s' -> '%s'", item_index, old_desc, new_item.strip())

        # Returns the formatted checklist.
        # This is actually not necessary since the agent will see the updated checklist in the next model call,
        # but it can be helpful for debugging.
        return await self._format_checklist_prompt()

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

    def _create_edit_checklist_item_tool(self) -> BaseTool:
        """Create tool for rewriting a checklist item's description.

        :return: StructuredTool for item text edits
        """
        return StructuredTool.from_function(
            coroutine=self.edit_checklist_item,
            name="edit_checklist_item",
            description=(
                "Rewrite the description of a checklist item when the plan changes. "
                "The item's status and notes are preserved — only the text is replaced. "
                "Use this instead of recreating the whole checklist when only one step needs to change."
            ),
            args_schema={
                "type": "object",
                "properties": {
                    "item_index": {
                        "type": "integer",
                        "description": "1-based index of the checklist item to rewrite",
                    },
                    "new_item": {
                        "type": "string",
                        "description": "New description to replace the current item text",
                    },
                },
                "required": ["item_index", "new_item"],
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

    async def _format_checklist_prompt(self) -> str:
        """Format checklist for injection into system prompt and report progress.

        If a ``progress_reporter`` was provided, emits the current completion ratio
        (done + skipped / total) as ``{"progress": float}`` to the client.

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
        done = 0
        skipped = 0
        for item in self.checklist:
            if item.get("status") == "done":
                done += 1
            elif item.get("status") == "skipped":
                skipped += 1
        lines.extend(["", f"Progress: {done}/{total} done, {skipped} skipped", ""])

        if self.progress_reporter is not None:
            progress: float = (done + skipped) / total if total > 0 else 0.0
            await self.progress_reporter.async_report_progress({"progress": progress})

        return "\n".join(lines)
