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

"""Interface for process loggers that drain subprocess pipes."""

import subprocess
from abc import ABC
from abc import abstractmethod


class ProcessLoggerInterface(ABC):  # pylint: disable=too-few-public-methods
    """Interface for consuming subprocess stdout/stderr pipes.

    Any class that drains subprocess pipes should implement this interface.
    This allows run.py to detect whether a plugin is handling pipe consumption
    and fall back to a simple logger if not.
    """

    @abstractmethod
    def attach_process_logger(self, process: subprocess.Popen[str], process_name: str, log_file: str) -> None:
        """Attach to a subprocess and drain its stdout/stderr pipes.

        Args:
            process: A running subprocess with .stdout and .stderr pipes.
            process_name: Human-readable label for the process.
            log_file: Path to the file where raw output should be mirrored.
        """
