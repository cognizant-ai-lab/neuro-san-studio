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

"""Base class for all plugins in the system."""

import logging
import os
from abc import ABC

# Ensure a basic console handler exists so plugin log messages are visible
# even when ProcessLogBridge is not active.  This is idempotent — it only
# adds a handler when the root logger has none.
logging.basicConfig(level=logging.INFO, format="%(message)s")


class _PluginLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that auto-prefixes messages with [ClassName]."""

    def process(self, msg, kwargs):
        """Prepend the plugin class name to every log message."""
        return f"[{self.extra['plugin_name']}] {msg}", kwargs


class BasePlugin(ABC):
    """Abstract base class for all plugins in the system.

    Subclasses may override any of the following hook methods to customize
    plugin behavior.  All hooks have no-op defaults so subclasses only need
    to implement the ones they care about.

    Lifecycle hooks (called by the framework):
        do_initialize   -- Custom initialization logic (called by ``initialize``).
        do_cleanup       -- Custom cleanup logic (called by ``cleanup``).

    Server hooks (called around server start):
        pre_server_start_action  -- Runs before the server starts.
        post_server_start_action -- Runs after the server starts.

    Argument hooks (called during argument parsing):
        update_args_dict   -- Inject default values into the args dictionary.
        update_parser_args -- Add CLI flags to the argument parser.
    """

    def __init__(self, plugin_name: str, args: dict = None):
        """Initialize the base plugin with a name and optional arguments.

        Args:
            plugin_name: The name of the plugin.
            args: Optional dictionary of arguments for the plugin.
        """
        self.plugin_name = plugin_name
        self.args = args or {}
        raw_logger = logging.getLogger(self.__class__.__name__)
        self._logger = _PluginLoggerAdapter(raw_logger, {"plugin_name": self.__class__.__name__})

    def initialize(self):
        """Initialize the plugin. Logs entry/exit and delegates to do_initialize."""
        self._logger.info("Initializing (PID=%s)", os.getpid())
        self.do_initialize()
        self._logger.info("Initialized (PID=%s)", os.getpid())

    def do_initialize(self):
        """Hook: override to provide custom initialisation logic.

        Called by :meth:`initialize` between the entry and exit log messages.
        The default implementation does nothing.
        """

    def cleanup(self):
        """Cleanup resources. Logs entry/exit and delegates to do_cleanup."""
        self._logger.info("Cleaning up")
        self.do_cleanup()
        self._logger.info("Cleanup complete")

    def do_cleanup(self):
        """Hook: override to provide custom cleanup logic.

        Called by :meth:`cleanup` between the entry and exit log messages.
        The default implementation does nothing.
        """

    def pre_server_start_action(self):
        """Hook: override to run actions before the server starts.

        The default implementation does nothing.
        """

    def post_server_start_action(self):
        """Hook: override to run actions after the server starts.

        The default implementation does nothing.
        """

    @staticmethod
    def get_bool_env(var_name: str, default: bool) -> bool:
        """Parse a boolean environment variable.

        Args:
            var_name: Environment variable name
            default: Default value if variable is not set

        Returns:
            Boolean value parsed from environment variable
        """
        val = os.getenv(var_name)
        if val is None:
            return default
        return val.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def update_args_dict(args_dict: dict):
        """Hook: override to inject default values into the arguments dictionary.

        Args:
            args_dict: Dictionary of arguments to update.
        """

    @staticmethod
    def update_parser_args(parser):
        """Hook: override to add plugin-specific flags to the argument parser.

        Args:
            parser: The argument parser to update.
        """

    def __str__(self):
        return f"{self.plugin_name} Plugin"

    def __repr__(self):
        return f"{self.plugin_name} Plugin"
