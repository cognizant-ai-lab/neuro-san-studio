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
from typing import Any

from neuro_san.interfaces.coded_tool import CodedTool

AGENT_NETWORK_QUERIES: str = "agent_network_queries"


class SetSampleQueries(CodedTool):
    """
    CodedTool implementation which sets the sample queries of the agent network in sly data.
    """

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> str:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "sample_queries": sample queries for the agent network.

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                This dictionary is largely to be treated as read-only.
                It is possible to add key/value pairs to this dict that do not
                yet exist as a bulletin board, as long as the responsibility
                for which coded_tool publishes new entries is well understood
                by the agent chain implementation and the coded_tool implementation
                adding the data is not invoke()-ed more than once.

                Keys expected for this implementation are:
                    "agent_network_queries": a list of sample queries

        :return:
            In case of successful execution:
                a text string indicating the sample queries were successfully set in the sly data.
            otherwise:
                a text string an error message in the format:
                "Error: <error message>"
        """
        sample_queries: list[str] = args.get("sample_queries")
        if not sample_queries:
            raise ValueError("Error: No sample_queries provided.")
        if not isinstance(sample_queries, list):
            raise ValueError("Error: sample_queries must be a list of strings.")
        if not all(isinstance(sample_query, str) for sample_query in sample_queries):
            raise ValueError("Error: sample_queries must be a list of strings.")

        logger = logging.getLogger(self.__class__.__name__)
        logger.info(">>>>>>>>>>>>>>>>>>>Set Sample Queries>>>>>>>>>>>>>>>>>>")
        sly_data[AGENT_NETWORK_QUERIES] = sample_queries
        logger.info("The Sample queries: %s", str(sample_queries))

        logger.info(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
        return "Sample queries have been set successfully."
