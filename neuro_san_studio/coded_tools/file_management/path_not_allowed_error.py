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


class PathNotAllowedError(ValueError):
    """
    Raised when a path fails the operator-configured allow/block rules.

    Subclasses ValueError so every existing caller and the documented per-tool
    error taxonomies (which promise ValueError with a "path_not_allowed:"
    message prefix) are unchanged. The dedicated type exists so code that must
    distinguish "this path is denied" from "the operator config is malformed"
    (e.g. list_directory turning a target denial into control flow) can catch it
    structurally instead of string-matching the message prefix — a rewording of
    one message must never turn a routine per-entry denial into an exception
    that aborts a whole listing, or vice versa.
    """
