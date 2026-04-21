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
Public API for the persistent-memory middleware package.

Re-exports the two user-facing classes so callers write

    from middleware.persistent_memory import PersistentMemoryMiddleware

rather than the longer fully-qualified module path. HOCON class-path strings
(which neuro-san's class loader resolves) still need the full dotted path to
the module, see ``registries/tools/persistent_memory.hocon``.
"""

from middleware.persistent_memory.memory_summariser import MemorySummariser
from middleware.persistent_memory.persistent_memory_middleware import PersistentMemoryMiddleware

__all__ = ["MemorySummariser", "PersistentMemoryMiddleware"]
