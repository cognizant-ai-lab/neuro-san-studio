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

import asyncio
import logging
from typing import Any
from typing import Union

# pylint: disable=import-error
from ddgs import DDGS
from neuro_san.interfaces.coded_tool import CodedTool

# The following parameters are from https://github.com/deedy5/ddgs?tab=readme-ov-file#1-text.
DDGS_QUERY_PARAMS = [
    "query",
    "region",
    "safesearch",
    "timelimit",
    "max_results",
    "page",
    "backend",
]


class DdgsSearch(CodedTool):
    """
    CodedTool implementation which provides a way to utilize DDGS Search feature.
    """

    def invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> Union[dict[str, Any], str]:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "search_terms"

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                This dictionary is largely to be treated as read-only.
                It is possible to add key/value pairs to this dict that do not
                yet exist as a bulletin board, as long as the responsibility
                for which coded_tool publishes new entries is well understood
                by the agent chain implementation and the coded_tool implementation
                adding the data is not invoke()-ed more than once.

                Keys expected for this implementation are:
                    None

        :return:
            In case of successful execution:
                The URL to the app as a string.
            otherwise:
                a text string an error message in the format:
                "Error: <error message>"
        """

        # Filter user-specified args using the DDGS_QUERY_PARAMS
        ddgs_search_params = {param: param_value for param, param_value in args.items() if param in DDGS_QUERY_PARAMS}

        # Use user-specified "query" if available; otherwise fall back to LLM-provided "search_terms"
        ddgs_search_params.setdefault("query", args.get("search_terms"))

        # Ensure a query was provided
        if not ddgs_search_params.get("query"):
            return "Error: No 'search_terms' provided."

        logger = logging.getLogger(self.__class__.__name__)
        logger.info(">>>>>>>>>>>>>>>>>>>DDGS Search>>>>>>>>>>>>>>>>>>")
        logger.info("Search Terms: %s", ddgs_search_params.get("query"))

        results: list[dict[str, str]] = DDGS().text(**ddgs_search_params)
        # This returns a list of dictionary with keys; "title", "href", "body".

        logger.info(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
        logger.info("DDGS Search Results: %s", str(results))
        return results

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> Union[dict[str, Any], str]:
        """
        Run self.invoke(args, sly_data) in a thread so it won’t block the async event loop, and wait for it to finish
        """
        return await asyncio.to_thread(self.invoke, args, sly_data)
