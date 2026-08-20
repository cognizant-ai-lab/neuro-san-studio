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


class CatalogLoadError(ValueError):
    """
    Raised when a designer catalog (see HoconCatalogCache) cannot be resolved,
    read, or parsed.

    The message carries the resolved path and the underlying cause — server-side
    detail. Each caller decides what (if anything) of it reaches clients: an
    exception escaping a model call becomes the turn's client-visible answer, so
    a security-gating caller must log this and re-raise something client-safe.
    """
