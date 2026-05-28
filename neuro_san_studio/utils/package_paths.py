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

"""Locate the installed neuro-san-studio library on disk."""

import os

import neuro_san_studio


class PackagePaths:  # pylint: disable=too-few-public-methods
    """Resolve filesystem paths owned by the installed neuro-san-studio package."""

    @staticmethod
    def installed_library_root() -> str:
        """Return the directory that contains the library's bundled ``registries/``.

        Anchors on the ``neuro_san_studio`` package — a regular package whose
        ``__file__`` unambiguously points at the install location — rather than the
        ``registries`` namespace package, which gets shadowed by any ``registries/``
        directory on ``sys.path``, including the one ``ns init`` creates in the
        user's project.
        """
        pkg_dir = os.path.dirname(os.path.abspath(neuro_san_studio.__file__))
        install_root = os.path.dirname(pkg_dir)
        if os.path.exists(os.path.join(install_root, "registries", "manifest.hocon")):
            return install_root
        raise FileNotFoundError(
            "Cannot find neuro-san-studio installation. Make sure neuro-san-studio is installed via pip."
        )
