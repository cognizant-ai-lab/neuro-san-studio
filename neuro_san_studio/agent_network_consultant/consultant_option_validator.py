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
"""Validation for Agent Network Consultant command options."""

import re
from pathlib import PurePosixPath
from pathlib import PureWindowsPath

from neuro_san_studio.agent_network_consultant.consultant_options import ConsultantOptions


class ConsultantOptionValidator:
    """Validate one Consultant option set without loading the runtime orchestrator."""

    def __init__(self, options: ConsultantOptions) -> None:
        """
        Store the option values to validate.

        :param options: The typed options selected by the caller.
        """
        self._options = options

    def validate(self) -> str | None:
        """
        Validate inputs and normalize an existing-network path.

        :return: The normalized existing-network HOCON reference, when supplied.
        :raises ValueError: If an option is malformed or required target context is missing.
        """
        if self._options.max_iterations < 0:
            raise ValueError(f"--max-iterations must be zero or greater, got {self._options.max_iterations}.")
        if self._options.ungrounded not in ("stop", "continue"):
            raise ValueError(f"--ungrounded must be 'stop' or 'continue', got {self._options.ungrounded!r}.")
        ratio_match: re.Match[str] | None = re.fullmatch(
            r"([1-9]\d*)/([1-9]\d*)",
            self._options.success_ratio,
        )
        if ratio_match is None or int(ratio_match.group(1)) > int(ratio_match.group(2)):
            raise ValueError(
                "--success-ratio must use positive N/M values with N less than or equal to M "
                f"(e.g. '3/3'), got {self._options.success_ratio!r}."
            )
        has_use_case = bool(self._options.use_case and self._options.use_case.strip())
        has_hocon_file = bool(self._options.hocon_file and self._options.hocon_file.strip())
        if has_use_case == has_hocon_file:
            raise ValueError(
                "Provide exactly one of --use-case (to create a network) or --hocon-file "
                "(to iterate on an existing one)."
            )
        if not self._options.hocon_file:
            return None
        return self.normalize_hocon_reference(self._options.hocon_file)

    @staticmethod
    def normalize_hocon_reference(value: str) -> str:
        """
        Return a safe registries-relative HOCON reference.

        :param value: The path value to validate and normalize.
        :return: The safe registries-relative HOCON path.
        :raises ValueError: If the path is absolute, malformed, or not a HOCON file.
        """
        normalized = value.strip().replace("\\", "/")
        if normalized.startswith("registries/"):
            normalized = normalized[len("registries/") :]
        path = PurePosixPath(normalized)
        windows_path = PureWindowsPath(normalized)
        has_unsafe_part = False
        for part in normalized.split("/"):
            if part in {"", ".", ".."}:
                has_unsafe_part = True
                break
        is_unsafe_path = windows_path.drive or windows_path.root or path.is_absolute() or has_unsafe_part
        if is_unsafe_path or path.suffix != ".hocon":
            raise ValueError("HOCON file must be a safe .hocon path relative to registries/.")
        return path.as_posix()
