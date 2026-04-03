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


class BasePlugin:
    """Base class for all plugins in the system."""

    def __init__(self, plugin_name: str, args: dict = None):
        """Initialize the base plugin with a name and optional arguments.

        Args:
            plugin_name: The name of the plugin.
            args: Optional dictionary of arguments for the plugin.
        """
        self.plugin_name = plugin_name
        self.args = args or {}

    def pre_server_start_action(self):
        """Perform actions before the server starts."""

    def post_server_start_action(self):
        """Perform actions after the server starts."""

    def cleanup(self):
        """Cleanup resources when the plugin is being unloaded."""

    def initialize(self):
        """Initialize the plugin. This method is called during server startup."""

    @staticmethod
    def update_args_dict(args_dict: dict):
        """Update the arguments dictionary.

        Args:
            args_dict: Dictionary of arguments to update.
        """

    @staticmethod
    def update_parser_args(parser):
        """Update the argument parser with plugin-specific arguments.

        Args:
            parser: The argument parser to update.
        """

    def __str__(self):
        return f"{self.plugin_name} Plugin"

    def __repr__(self):
        return f"{self.plugin_name} Plugin"
