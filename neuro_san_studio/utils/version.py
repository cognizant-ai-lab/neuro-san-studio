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

import logging
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as library_version
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)

# The distribution name as published / installed (see pyproject `[project].name`).
DISTRIBUTION_NAME = "neuro-san-studio"

# Repo root (…/neuro_san_studio/utils/version.py -> two parents up), for the
# source-checkout fallback when the package isn't installed.
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Where the version was resolved from.
SOURCE_INSTALLED = "installed"
SOURCE_SCM = "source"
SOURCE_UNKNOWN = "unknown"


def studio_version() -> str:
    """Bare version string, for callers that don't care where it came from."""
    return resolve_version()[0]


def resolve_version() -> Tuple[str, str]:
    """Resolve ``(version, source)``, never raising: installed metadata, then scm, then unknown."""
    try:
        return str(library_version(DISTRIBUTION_NAME)), SOURCE_INSTALLED
    except PackageNotFoundError:
        logger.warning(
            "%s is not installed as a distribution; falling back to setuptools-scm.",
            DISTRIBUTION_NAME,
        )
    scm = _scm_version()
    if scm:
        return scm, SOURCE_SCM
    return "unknown", SOURCE_UNKNOWN


def _scm_version() -> str:
    """Version from setuptools-scm reading the repo, or '' if it isn't importable."""
    try:
        from setuptools_scm import get_version  # pylint: disable=import-outside-toplevel

        return str(get_version(root=str(_REPO_ROOT)))
    except (ImportError, LookupError, OSError):
        return ""
