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

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as library_version

# The distribution name as published / installed (see pyproject `[project].name`).
DISTRIBUTION_NAME = "neuro-san-studio"


def studio_version() -> str:
    """Resolve the installed neuro-san-studio version.

    Reads the installed distribution metadata (populated by setuptools-scm at build
    time). Returns 'unknown' if it can't be found, so callers always get a string
    and never raise.
    """
    try:
        return str(library_version(DISTRIBUTION_NAME))
    except PackageNotFoundError:
        return "unknown"
