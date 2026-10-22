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
# Note on the filename: conftest.py is the exact name pytest requires for
# fixtures that apply automatically to every test under this directory —
# pytest discovers and loads it by name, so it cannot be renamed to something
# more descriptive without the autouse fixture below silently ceasing to run.
# The inventory of the process-wide globals this fixture resets lives in
# coded_tools/agent_network_editor/globals.py.
import os

import pytest

from coded_tools.agent_network_editor.globals import ProcessGlobals


@pytest.fixture(autouse=True)
def restore_os_environ():
    """
    Undo any os.environ mutation a test makes, so env state cannot leak between tests.

    Covers writes that bypass monkeypatch -- e.g. ProjectEnvironment.apply()/set_pythonpath(),
    and the .env file the CLI's top-level callback loads via dotenv. Without this, a variable
    picked up during one test stays set for the rest of the session and silently changes what
    later tests see.
    """
    saved = os.environ.copy()  # setup: before the test
    yield  # <- test body runs here
    os.environ.clear()  # teardown: after, even if the test failed
    os.environ.update(saved)


@pytest.fixture(autouse=True)
def reset_process_globals():
    """
    Clear the process-wide caches before and after each test.

    Clearing before the test as well guards against state populated outside
    any test, e.g. during collection or session setup.
    """
    ProcessGlobals.clear_all_for_testing()
    yield
    ProcessGlobals.clear_all_for_testing()
