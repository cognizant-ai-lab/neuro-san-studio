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

import logging
import re
from pathlib import Path
from typing import Any
from typing import Union

from neuro_san.interfaces.coded_tool import CodedTool
from typing_extensions import override

from coded_tools.agent_network_editor.and_logger import AndLogger
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_NAME
from middleware.agent_network_consultant.consultant_state import ConsultantState
from neuro_san_studio.coded_tools.file_management.read_file import MAX_FILE_BYTES
from neuro_san_studio.coded_tools.file_management.read_file import ReadFile
from neuro_san_studio.coded_tools.file_management.write_file import WriteFile

# Matches the Network Consultant runner's scratchpad directory. Each run uses a unique file;
# reads preserve its history and writes append to it.
SCRATCHPAD_DIR = Path("logs/network_consultant_scratchpad").resolve()


class NetworkScratchpad(CodedTool):
    """
    CodedTool for a per-network, per-run, cross-round scratchpad. A sub-agent like network_behavior_fixer
    is invoked fresh every round with no memory of its own prior attempts -- this lets it record
    what it already tried (and whether it worked) so a later round tries something new or more
    efficient instead of repeating a failed fix. Durable only for the current continuous run:
    NetworkConsultantOrchestrator assigns a unique run identifier and clears only that run's file before the
    iteration loop, so a fresh or concurrent run never inherits another run's notes.
    Reads preserve the complete history, and writes append new outcomes and attempts. The runner
    clears the file at the beginning of a fresh run so history never crosses run boundaries.
    """

    @staticmethod
    def _safe_path(network_name: str, run_id: str) -> Path:
        """
        Return the network's path after constraining it to the scratchpad directory.

        :param network_name: The target network name.
        :param run_id: The identifier isolating one Consultant run.
        :return: The resulting value.
        """
        safe_name = re.sub(r"[^\w.\-]", "_", network_name)
        safe_run_id = re.sub(r"[^\w.\-]", "_", run_id)
        path = (SCRATCHPAD_DIR / f"{safe_name}.{safe_run_id}.txt").resolve()
        path.relative_to(SCRATCHPAD_DIR)
        return path

    @staticmethod
    def clear_for_hocon_file(hocon_file: str, run_id: str) -> None:
        """
        Delete the scratchpad belonging to a fresh consultant run.

        :param hocon_file: The registries-relative HOCON file name.
        :param run_id: The identifier isolating one Consultant run.
        """
        NetworkScratchpad._safe_path(Path(hocon_file).stem, run_id).unlink(missing_ok=True)

    @staticmethod
    def _file_args(path: Path) -> dict[str, Any]:
        """
        Build operator-controlled file-management arguments for one scratchpad.

        :param path: The resolved scratchpad file path.
        :return: Access rules restricted to the scratchpad directory and text files.
        """
        return {
            "file_path": str(path),
            "allowed_paths": [str(SCRATCHPAD_DIR)],
            "allowed_file_extensions": [".txt"],
        }

    @staticmethod
    async def _existing_content(path: Path) -> str:
        """
        Read the current scratchpad content through the shared file-management tool.

        :param path: The resolved scratchpad file path.
        :return: Existing content, or an empty string when the file does not exist.
        :raises ValueError: If an existing scratchpad cannot be read safely.
        """
        file_args: dict[str, Any] = NetworkScratchpad._file_args(path)
        file_args["max_content_chars"] = MAX_FILE_BYTES
        try:
            result: dict[str, Any] = await ReadFile().async_invoke(file_args, None)
        except ValueError as exc:
            if str(exc).startswith("path_not_found:"):
                return ""
            raise
        return str(result.get("content", ""))

    @staticmethod
    async def _write(
        path: Path,
        content: str,
        sly_data: dict[str, Any],
        logger: AndLogger,
    ) -> Union[dict[str, Any], str]:
        """
        Append one note to a network scratchpad.

        :param path: The file or token path to process.
        :param content: The text content to process or persist.
        :param sly_data: The shared agent runtime data.
        :param logger: The logger value.
        :return: The resulting value.
        """
        if not content:
            return "Error: No 'content' provided to write."
        try:
            existing_content: str = await NetworkScratchpad._existing_content(path)
            file_args: dict[str, Any] = NetworkScratchpad._file_args(path)
            file_args["content"] = existing_content + content.strip() + "\n"
            file_args["overwrite"] = True
            file_args["create_parents"] = True
            await WriteFile().async_invoke(file_args, sly_data)
        except ValueError as exc:
            logger.error("Could not append to scratchpad %s: %s", path, exc)
            return f"Error: {exc}"
        logger.info("Wrote to scratchpad: %s", path)
        return {"saved": True}

    @staticmethod
    async def _read(
        path: Path,
        sly_data: dict[str, Any],
        logger: AndLogger,
    ) -> Union[dict[str, str], str]:
        """
        Read one network scratchpad without changing its history.

        :param path: The file or token path to process.
        :param sly_data: The shared agent runtime data.
        :param logger: The logger value.
        :return: The scratchpad content or an actionable error.
        """
        file_args: dict[str, Any] = NetworkScratchpad._file_args(path)
        file_args["max_content_chars"] = MAX_FILE_BYTES
        try:
            result: dict[str, Any] = await ReadFile().async_invoke(file_args, sly_data)
        except ValueError as exc:
            if str(exc).startswith("path_not_found:"):
                return {"content": ""}
            logger.error("Could not read scratchpad %s: %s", path, exc)
            return f"Error: {exc}"
        logger.info("Read scratchpad: %s", path)
        return {"content": str(result.get("content", ""))}

    @override
    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> Union[dict[str, Any], str]:
        """
        Async invoke.

        :param args: A dictionary with the following keys:
        :param sly_data: Shared runtime data containing the network name and unique Consultant run identifier.
        :return: The resulting value.
        """
        logger = AndLogger(logging.getLogger(self.__class__.__name__))

        network_name: str = (sly_data or {}).get(AGENT_NETWORK_NAME, "")
        if not network_name:
            return "Error: No agent network is loaded (missing 'agent_network_name' in sly_data)."
        run_id: str = (sly_data or {}).get(ConsultantState.NETWORK_CONSULTANT_RUN_ID, "")
        if not run_id:
            return "Error: No Consultant run identifier is available in sly_data."
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
