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

"""Resolved Network Consultant target information."""


class ConsultantTarget:
    """Identify a target network through explicit accessors."""

    def __init__(self, hocon_file: str, network_name: str, direction: str, hocon_path: str) -> None:
        """
        Store one resolved target.

        :param hocon_file: The registries-relative target file.
        :param network_name: The target network name.
        :param direction: The behavior the Consultant must preserve.
        :param hocon_path: The local target path.
        """
        self._hocon_file = hocon_file
        self._network_name = network_name
        self._direction = direction
        self._hocon_path = hocon_path

    def hocon_file(self) -> str:
        """
        Return the registries-relative target file.

        :return: The target HOCON file.
        """
        return self._hocon_file

    def network_name(self) -> str:
        """
        Return the target network name.

        :return: The target network name.
        """
        return self._network_name

    def direction(self) -> str:
        """
        Return the behavior the Consultant must preserve.

        :return: The Consultant direction.
        """
        return self._direction

    def hocon_path(self) -> str:
        """
        Return the local target path.

        :return: The target HOCON path.
        """
        return self._hocon_path
