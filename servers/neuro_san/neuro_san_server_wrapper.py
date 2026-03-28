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
import importlib
import os
import signal
import sys
import json

from neuro_san.service.main_loop.server_main_loop import ServerMainLoop


class NeuroSanServerWrapper:
    """Wrapper that initializes plugins before starting the Neuro SAN server."""

    def __init__(self):
        """Initialize the plugins."""
        self.root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        if self.root_dir not in sys.path:
            sys.path.insert(0, self.root_dir)

        plugins_file = os.path.join(self.root_dir, "plugins", "default_plugins.json")
        try:
            with open(plugins_file, "r", encoding="utf-8") as f:
                self.user_plugins_config = json.load(f)
        except FileNotFoundError:
            print(f"No plugins file found at {plugins_file}. Continuing without plugins.")
            self.user_plugins_config = {}
        except json.JSONDecodeError as e:
            print(f"Failed to parse plugins file at {plugins_file}: {e}. Continuing without plugins.")
            self.user_plugins_config = {}
        
        self.plugin_classes = []
        for plugin_info in self.user_plugins_config.get("plugins", []):
            module = plugin_info.get("module")
            class_name = plugin_info.get("class")
            print(f"Loading plugin: {class_name} from module: {module}")
            self.plugin_classes.append(getattr(importlib.import_module(module), class_name))
        
        # Instantiate plugins now that args are fully built
        self.args = {}  # Placeholder for any args you want to pass to plugins
        self.plugins = [cls(self.args) for cls in self.plugin_classes]
        for plugin in self.plugins:
            print(f"Loaded plugin: {plugin}")

    def run(self):
        """Initialize Phoenix and Langfuse and run the server main loop."""
        for plugin in self.plugins:
            print(f"Initializing plugin: {plugin}")
            plugin.initialize()
            print(f"Plugin initialized: {plugin}")

        # Import and run the actual server main loop
        # Note: ServerMainLoop will parse sys.argv itself, so all command-line
        # arguments (--port, --http_port, etc.) are automatically passed through
        # Convert SIGTERM into SystemExit so Python unwinds through
        # the finally block below, allowing plugins to flush traces.
        # Tornado does not install a SIGTERM handler, so the default
        # action would terminate the process immediately.
        signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(0))

        try:
            ServerMainLoop().main_loop()
        finally:
            for plugin in self.plugins:
                print(f"Cleaning up plugin: {plugin}")
                plugin.cleanup()
                print(f"Plugin cleaned up: {plugin}")


if __name__ == "__main__":
    wrapper = NeuroSanServerWrapper()
    wrapper.run()
