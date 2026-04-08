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

"""Simple process logger that drains subprocess pipes to console and file."""

import subprocess
import threading
from pathlib import Path

from neuro_san_studio.runner.process_logger_interface import ProcessLoggerInterface


class SimpleProcessLogger(ProcessLoggerInterface):  # pylint: disable=too-few-public-methods
    """Minimal process logger that forwards subprocess output to console and a log file.

    This is a lightweight fallback used when the full ProcessLogBridge plugin
    is not enabled. It spawns daemon threads to drain stdout/stderr, preventing
    pipe buffer deadlocks, and writes raw lines to both the console and a log file.
    """

    def attach_process_logger(self, process: subprocess.Popen[str], process_name: str, log_file: str) -> None:
        """Attach to a subprocess and drain its pipes with basic forwarding.

        Args:
            process: A running subprocess with .stdout and .stderr pipes.
            process_name: Human-readable label for the process.
            log_file: Path to the file where raw output should be mirrored.
        """
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        for pipe, label in [(process.stdout, "stdout"), (process.stderr, "stderr")]:
            if pipe is not None:
                thread = threading.Thread(
                    target=self._drain,
                    args=(pipe, process_name, label, log_file),
                    daemon=True,
                )
                thread.start()

    @staticmethod
    def _drain(pipe, process_name: str, label: str, log_file: str) -> None:
        """Read lines from a pipe, print to console, and append to a log file.

        Args:
            pipe: A file-like pipe (stdout or stderr) from a subprocess.
            process_name: Human-readable label for the process.
            label: Stream identifier ("stdout" or "stderr").
            log_file: Path to the log file for mirroring.
        """
        try:
            with open(log_file, "a", encoding="utf-8") as log:
                for line in iter(pipe.readline, ""):
                    text = line.rstrip("\n")
                    formatted = f"[{process_name}:{label}] {text}"
                    print(formatted)
                    log.write(formatted + "\n")
                    log.flush()
        finally:
            pipe.close()
