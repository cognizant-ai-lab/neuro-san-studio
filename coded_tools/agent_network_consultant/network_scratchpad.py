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

"""Per-network scratchpad used across Agent Network Consultant repair rounds."""

import logging
import os
import re
from pathlib import Path
from typing import Any
from typing import Union
from typing import override

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.agent_network_editor.and_logger import AndLogger
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_NAME
from neuro_san_studio.agent_network_consultant.consultant_state import ConsultantState
from neuro_san_studio.agent_network_consultant.sensitive_data_redactor import SensitiveDataRedactor
from neuro_san_studio.coded_tools.file_management.read_file import MAX_FILE_BYTES
from neuro_san_studio.coded_tools.file_management.read_file import ReadFile
from neuro_san_studio.coded_tools.file_management.write_file import WriteFile


class NetworkScratchpad(CodedTool):
    """
    Preserve append-only repair history for one network during one Agent Network Consultant run.

    Each run receives a unique identifier, so fresh and concurrent runs use separate files without deleting another
    run's history. Reading leaves the history unchanged, and writing appends the next outcome or attempted repair.
    """

    DIRECTORY_ENVIRONMENT_VARIABLE = "AGENT_NETWORK_CONSULTANT_SCRATCHPAD_DIR"
    DEFAULT_DIRECTORY = "logs/agent_network_consultant_scratchpad"
    RUN_ID_KEY = ConsultantState.AGENT_NETWORK_CONSULTANT_RUN_ID

    def __init__(self, scratchpad_directory: Path | None = None) -> None:
        """
        Resolve the directory that owns this tool's isolated run files.

        :param scratchpad_directory: An explicit scratchpad directory, primarily for isolated callers and tests.
        """
        configured_directory = os.environ.get(self.DIRECTORY_ENVIRONMENT_VARIABLE) or self.DEFAULT_DIRECTORY
        self._scratchpad_directory = (scratchpad_directory or Path(configured_directory)).resolve()

    def _safe_path(self, network_name: str, run_id: str) -> Path:
        """
        Return the network's path after constraining it to the scratchpad directory.

        :param network_name: The target network name.
        :param run_id: The identifier isolating one Agent Network Consultant run.
        :return: The resolved path within the configured scratchpad directory.
        """
        safe_name = re.sub(r"[^\w.\-]", "_", network_name)
        safe_run_id = re.sub(r"[^\w.\-]", "_", run_id)
        path = (self._scratchpad_directory / f"{safe_name}.{safe_run_id}.txt").resolve()
        path.relative_to(self._scratchpad_directory)
        return path

    def _file_args(self, path: Path) -> dict[str, Any]:
        """
        Build operator-controlled file-management arguments for one scratchpad.

        :param path: The resolved scratchpad file path.
        :return: Access rules restricted to the scratchpad directory and text files.
        """
        return {
            "file_path": str(path),
            "allowed_paths": [str(self._scratchpad_directory)],
            "allowed_file_extensions": [".txt"],
        }

    async def _existing_content(self, path: Path) -> str:
        """
        Read the current scratchpad content through the shared file-management tool.

        :param path: The resolved scratchpad file path.
        :return: Existing content, or an empty string when the file does not exist.
        :raises ValueError: If an existing scratchpad cannot be read safely.
        """
        file_args: dict[str, Any] = self._file_args(path)
        file_args.update({"max_content_chars": MAX_FILE_BYTES})
        try:
            result: dict[str, Any] = await ReadFile().async_invoke(file_args, None)
        except ValueError as exc:
            if str(exc).startswith("path_not_found:"):
                return ""
            raise
        return SensitiveDataRedactor.redact_text(str(result.get("content", "")))

    async def _write(
        self,
        path: Path,
        content: str,
        sly_data: dict[str, Any],
        logger: AndLogger,
    ) -> Union[dict[str, Any], str]:
        """
        Append one note to a network scratchpad.

        :param path: The resolved scratchpad file path.
        :param content: The note to append.
        :param sly_data: The shared agent runtime data.
        :param logger: The audit logger for this invocation.
        :return: The resulting value.
        """
        if not content:
            return "Error: No 'content' provided to write."
        try:
            existing_content: str = await self._existing_content(path)
            safe_content = SensitiveDataRedactor.redact_text(content.strip())
            file_args: dict[str, Any] = self._file_args(path)
            file_args.update(
                {
                    "content": existing_content + safe_content + "\n",
                    "overwrite": True,
                    "create_parents": True,
                }
            )
            await WriteFile().async_invoke(file_args, sly_data)
        except ValueError as exc:
            logger.error("Could not append to scratchpad %s: %s", path, exc)
            return f"Error: {exc}"
        logger.info("Wrote to scratchpad: %s", path)
        return {"saved": True}

    async def _read(
        self,
        path: Path,
        sly_data: dict[str, Any],
        logger: AndLogger,
    ) -> Union[dict[str, str], str]:
        """
        Read one network scratchpad without changing its history.

        :param path: The resolved scratchpad file path.
        :param sly_data: The shared agent runtime data.
        :param logger: The audit logger for this invocation.
        :return: The scratchpad content or an actionable error.
        """
        file_args: dict[str, Any] = self._file_args(path)
        file_args.update({"max_content_chars": MAX_FILE_BYTES})
        try:
            result: dict[str, Any] = await ReadFile().async_invoke(file_args, sly_data)
        except ValueError as exc:
            if str(exc).startswith("path_not_found:"):
                return {"content": ""}
            logger.error("Could not read scratchpad %s: %s", path, exc)
            return f"Error: {exc}"
        logger.info("Read scratchpad: %s", path)
        return {"content": SensitiveDataRedactor.redact_text(str(result.get("content", "")))}

    @override
    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> Union[dict[str, Any], str]:
        """
        Read or append the scratchpad isolated to the current network and run.

        :param args: The `read` or `write` action and optional content.
        :param sly_data: Shared runtime data containing the network name and unique Agent Network Consultant run ID.
        :return: The scratchpad content, save confirmation, or an actionable error.
        """
        logger = AndLogger(logging.getLogger(self.__class__.__name__))

        network_name: str = (sly_data or {}).get(AGENT_NETWORK_NAME, "")
        if not network_name:
            return "Error: No agent network is loaded (missing 'agent_network_name' in sly_data)."
        run_id: str = (sly_data or {}).get(self.RUN_ID_KEY, "")
        if not run_id:
            return "Error: No Agent Network Consultant run identifier is available in sly_data."
        action: str = args.get("action", "")
        if action not in ("read", "write"):
            return "Error: 'action' must be 'read' or 'write'."

        try:
            path = self._safe_path(network_name, run_id)
        except ValueError:
            return "Error: network_name resolves outside the scratchpad directory."

        if action == "write":
            return await self._write(path, args.get("content", ""), sly_data, logger)
        return await self._read(path, sly_data, logger)
