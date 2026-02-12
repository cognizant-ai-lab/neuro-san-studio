# Copyright (C) 2025-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
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
Startup wrapper for the HOCON Config Editor.

Launches the config_editor FastAPI application via uvicorn.
Configurable via environment variables:
    CONFIG_EDITOR_HOST  (default: 0.0.0.0)
    CONFIG_EDITOR_PORT  (default: 4174)
"""

import os

import uvicorn

if __name__ == "__main__":
    host = os.environ.get("CONFIG_EDITOR_HOST", "0.0.0.0")
    port = int(os.environ.get("CONFIG_EDITOR_PORT", "4174"))
    uvicorn.run("config_editor.app:app", host=host, port=port)
