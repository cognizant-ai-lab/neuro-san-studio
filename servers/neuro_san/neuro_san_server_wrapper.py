# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san-studio SDK Software in commercial settings.
#
"""
Wrapper module that initializes plugins before starting the server.

This module ensures that plugins are initialized in the same Python process as the Neuro SAN server,
allowing, for instance, proper tracing and observability.
"""
import os

from neuro_san.service.main_loop.server_main_loop import ServerMainLoop


class ServerMainLoopWrapper:
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
            from plugins.phoenix.phoenix_init import initialize_phoenix_if_enabled

            print("Initializing Phoenix in server process...")
            initialize_phoenix_if_enabled()
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
    wrapper = ServerMainLoopWrapper()
    wrapper.run()
