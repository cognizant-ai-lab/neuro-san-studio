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

from asyncio import Lock
from typing import Any


# pylint: disable=too-few-public-methods
class SlyDataLock:
    """
    Class for getting a lock on the sly_data for modification.
    """

    @staticmethod
    async def get_lock(sly_data: dict[str, Any], lock_name: str = "lock") -> Lock:
        """
        Get a lock stored on the sly_data for atmoic modification of certain fields.
        If no lock is on the sly_data, then create one.

        :param sly_data: The sly_data to get a lock on.
        :return: A common lock for modifying the sly_data.
        """

        # Under normal circumstances we might be tempted to hold a synchronous lock
        # while looking for the existing async lock, but we know that async methods
        # should all be running in their own thread, so that's not necessary.
        lock: Lock = sly_data.get(lock_name)
        if lock is None:
            lock = sly_data[lock_name] = Lock()
        return lock
