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

"""Logger adapter for plugins in the system."""

import logging
from collections.abc import MutableMapping
from typing import Any

# Ensure a basic console handler exists so plugin log messages are visible
# even when ProcessLogBridge is not active.  This is idempotent — it only
# adds a handler when the root logger has none.
logging.basicConfig(level=logging.INFO, format="%(message)s")


class _PluginLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that auto-prefixes messages with [ClassName]."""

    def process(self, msg: Any, kwargs: MutableMapping[str, Any]) -> tuple[str, MutableMapping[str, Any]]:
        """Prepend the plugin class name to every log message."""
        return f"[{self.extra['plugin_name']}] {msg}", kwargs
