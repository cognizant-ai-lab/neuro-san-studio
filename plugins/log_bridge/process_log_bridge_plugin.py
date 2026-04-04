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

"""Plugin wrapper for ProcessLogBridge."""

import os

from neuro_san_studio.runner.process_logger_interface import ProcessLoggerInterface
from plugins.base_plugin import BasePlugin
from plugins.log_bridge.process_log_bridge import ProcessLogBridge


class ProcessLogBridgePlugin(BasePlugin, ProcessLoggerInterface):
    """
    Plugin wrapper for ProcessLogBridge.

    Implements ProcessLoggerInterface so that run.py can detect pipe draining
    via isinstance check and fall back to a simple logger if this plugin is disabled.
    """

    def __init__(self, args=None):
        """
        Initialize the plugin and its internal ProcessLogBridge instance.

        :param args (dict | None): Optional configuration for the logging bridge.
        """
        super().__init__("ProcessLogBridgePlugin", args)
        self.log_file = os.path.join(self.args.get("logs_dir", "."), "runner.log")
        self.log_bridge = ProcessLogBridge(
            level=self.args.get("log_level", "info"),
            runner_log_file=self.log_file,
        )

    def attach_process_logger(self, process, process_name: str, log_file: str) -> None:
        """Delegate to the internal ProcessLogBridge instance.

        Args:
            process: A running subprocess with .stdout and .stderr pipes.
            process_name: Human-readable label for the process.
            log_file: Path to the file where raw output should be mirrored.
        """
        self.log_bridge.attach_process_logger(process, process_name, log_file)

    def post_server_start_action(self):
        """Attach process logger after the server starts."""
        process = self.args.get("process")
        process_name = self.args.get("process_name", "UnnamedProcess")
        self.attach_process_logger(process, process_name, self.log_file)
