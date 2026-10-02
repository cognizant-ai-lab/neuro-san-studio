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

"""Per-network scratchpad used across Network Consultant repair rounds."""

import asyncio
import logging
import re
from pathlib import Path
from typing import Any
from typing import Union

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.agent_network_editor.and_logger import AndLogger
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_NAME

# Matches apps/network_consultant/run.py's SCRATCHPAD_DIR -- that module clears this
# network's file once, at the very start of every fresh run, so nothing here ever leaks in
# from an earlier, unrelated run. Within one continuous run it persists across rounds.
SCRATCHPAD_DIR = Path("logs/network_consultant_scratchpad").resolve()


class NetworkScratchpad(CodedTool):
    """
    CodedTool for a per-network, cross-round scratchpad. A sub-agent like network_behavior_fixer
    is invoked fresh every round with no memory of its own prior attempts -- this lets it record
    what it already tried (and whether it worked) so a later round tries something new or more
    efficient instead of repeating a failed fix. Durable only for the current continuous run:
    apps/network_consultant/run.py deletes this network's file once at the very start of
    main(), before the iteration loop, so a fresh run never inherits a previous run's notes.
    Reading consumes it -- the file is deleted as part of the read, so notes don't just pile up
    forever; write again after reading if there's still something worth remembering.
    """

    @staticmethod
    def _safe_path(network_name: str) -> Path:
        """Return the network's path after constraining it to the scratchpad directory."""
        safe_name = re.sub(r"[^\w.\-]", "_", network_name)
        path = (SCRATCHPAD_DIR / f"{safe_name}.txt").resolve()
        path.relative_to(SCRATCHPAD_DIR)
        return path

    @staticmethod
    def clear_for_hocon_file(hocon_file: str) -> None:
        """Delete the scratchpad belonging to a fresh consultant run."""
        NetworkScratchpad._safe_path(Path(hocon_file).stem).unlink(missing_ok=True)

    @staticmethod
    def _write(path: Path, content: str, logger: AndLogger) -> Union[dict[str, Any], str]:
        """Append one note to a network scratchpad."""
        if not content:
            return "Error: No 'content' provided to write."
        SCRATCHPAD_DIR.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as scratch_file:
            scratch_file.write(content.strip() + "\n")
        logger.info("Wrote to scratchpad: %s", path)
        return {"saved": True}

    @staticmethod
    def _read(path: Path, logger: AndLogger) -> dict[str, str]:
        """Read and consume one network scratchpad."""
        if not path.is_file():
            return {"content": ""}
        content = path.read_text(encoding="utf-8")
        path.unlink()
        logger.info("Read and cleared scratchpad: %s", path)
        return {"content": content}

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> Union[dict[str, Any], str]:
        """
        :param args: A dictionary with the following keys:
                "action": "read" or "write".
                "content": required when action is "write" -- what was tried and the outcome.

        :param sly_data: Supplies "agent_network_name" (set by AgentNetworkDefinitionMiddleware,
            already wired onto this agent), used to key the scratchpad file. Not LLM-supplied, so
            it can't be typo'd or hallucinated into the wrong network's file.

        :return:
            For "read": {"content": <prior notes, or "" if none>}. Deletes the file.
            For "write": {"saved": True}.
            otherwise: A text string error message.
        """
        logger = AndLogger(logging.getLogger(self.__class__.__name__))

        network_name: str = (sly_data or {}).get(AGENT_NETWORK_NAME, "")
        if not network_name:
            return "Error: No agent network is loaded (missing 'agent_network_name' in sly_data)."
        action: str = args.get("action", "")
        if action not in ("read", "write"):
            return "Error: 'action' must be 'read' or 'write'."

        try:
            path = self._safe_path(network_name)
        except ValueError:
            return "Error: network_name resolves outside the scratchpad directory."

        if action == "write":
            return await asyncio.to_thread(self._write, path, args.get("content", ""), logger)
        return await asyncio.to_thread(self._read, path, logger)
