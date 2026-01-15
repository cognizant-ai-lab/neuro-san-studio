# Copyright © 2025 Cognizant Technology Solutions Corp, www.cognizant.com.
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

from typing import Any


class AgentCaller:
    """
    Generic interface for calling an agent
    """

    def get_name(self) -> str:
        """
        Get the name of the agent

        :return: The name of the agent
        """
        raise NotImplementedError

    async def call_agent(self, tool_args: dict[str, Any]) -> str:
        """
        Call an agent with text

        :param tool_args: A dictionary of arguments to pass to the agent
        :return: The text of the response
        """
        raise NotImplementedError
