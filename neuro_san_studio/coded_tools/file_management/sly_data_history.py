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

from pathlib import Path
from typing import Any

from coded_tools.agent_network_editor.sly_data_lock import SlyDataLock


# pylint: disable=too-few-public-methods
class SlyDataHistory:
    """
    Shared session-scoped history recording for the file management tools.

    Each tool records the resolved paths it has touched (read_file_history,
    write_file_history, ...) so companion tools and operators can audit what a
    conversation has accessed or modified. Only resolved paths are recorded
    (deduped, insertion-ordered) — contents are intentionally not cached; see
    read_file._async_cache_read for the full rationale.
    """

    @staticmethod
    async def async_record(sly_data: dict[str, Any] | None, lock_name: str, history_key: str, file_path: Path) -> None:
        """Append a resolved path to a history list in sly_data (deduped, insertion-ordered).

        Lock-guarded so concurrent tool invocations don't race on the
        dedupe/append. A None sly_data (seen from some middleware paths) is
        tolerated as a no-op: history is best-effort bookkeeping and must never
        fail an operation whose side effect has already happened.
        """
        if sly_data is None:
            return
        async with await SlyDataLock.get_lock(sly_data, lock_name):
            history: list[str] = sly_data.setdefault(history_key, [])
            resolved_str: str = str(file_path)
            if resolved_str not in history:
                history.append(resolved_str)
