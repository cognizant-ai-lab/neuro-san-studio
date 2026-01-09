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
"""
Wrapper module that initializes plugins before starting the server.

This module ensures that plugins are initialized in the same Python process as the Neuro SAN server,
allowing, for instance, proper tracing and observability.
"""
import os

from neuro_san.service.main_loop.server_main_loop import ServerMainLoop


class NeuroSanServerWrapper:
    """Wrapper that initializes plugins before starting the Neuro SAN server."""

    def __init__(self):
        """Initialize the plugins."""
        # Phoenix
        self.phoenix_enabled = os.getenv("PHOENIX_ENABLED", "false").lower() in ("true", "1", "yes", "on")

    def _init_phoenix(self):
        """Initialize Phoenix instrumentation if enabled."""
        if not self.phoenix_enabled:
            return

        try:
            from plugins.phoenix.phoenix_plugin import PhoenixPlugin

            print("Initializing Phoenix in server process...")
            PhoenixPlugin().initialize()
            print("Phoenix initialization complete.")
        except ImportError:
            print("Warning: Phoenix plugin not installed.")
            print("Install with: pip install -r plugins/phoenix/requirements.txt")
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"Warning: Phoenix initialization failed: {e}")

    def run(self):
        """Initialize Phoenix and run the server main loop."""
        # Initialize Phoenix before starting the server
        self._init_phoenix()

        # Import and run the actual server main loop
        # Note: ServerMainLoop will parse sys.argv itself, so all command-line
        # arguments (--port, --http_port, etc.) are automatically passed through
        ServerMainLoop().main_loop()


if __name__ == "__main__":
    wrapper = NeuroSanServerWrapper()
    wrapper.run()
