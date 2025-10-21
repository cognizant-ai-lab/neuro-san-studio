# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san-studio SDK Software in commercial settings.
#
# END COPYRIGHT

import asyncio
import json
import logging
import os
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Union

import requests
from neuro_san.interfaces.coded_tool import CodedTool
from requests import HTTPError
from requests import JSONDecodeError
from requests import RequestException

BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
BRAVE_TIMEOUT = 30.0
# The following parameters are from https://api-dashboard.search.brave.com/app/documentation/web-search/query.
BRAVE_QUERY_PARAMS = [
    "q",
    "country",
    "search_lang",
    "ui_lang",
    "count",
    "offset",
    "safesearch",
    "freshness",
    "text_decorations",
    "spellcheck",
    "result_filter",
    "goggles_id",
    "goggles",
    "units",
    "extra_snippets",
    "summary",
]


class BraveSearch(CodedTool):
    """
    CodedTool implementation which provides a way to search the web using Brave search API
    For info on Brave search, and to get a Brave search API key, go to https://brave.com/search/api/
    """

    def __init__(self):
        self.brave_api_key = os.getenv("BRAVE_API_KEY")
        if self.brave_api_key is None:
            logging.error("BRAVE_API_KEY is not set!")

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[List[Dict[str, Any]], str]:
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
                A list of dictionary of search results
            otherwise:
                a text string an error message in the format:
                "Error: <error message>"
        """

        # Extract URL and timeout from args, then environment variables, then fall back to defaults
        brave_url: str = args.get("brave_url") or os.getenv("BRAVE_URL") or BRAVE_URL
        brave_timeout: float = float(args.get("brave_timeout") or os.getenv("BRAVE_TIMEOUT") or BRAVE_TIMEOUT)

        # Filter user-specified args using the BRAVE_QUERY_PARAMS
        brave_search_params = {
            param: param_value for param, param_value in args.items() if param in BRAVE_QUERY_PARAMS
        }

        # Use user-specified query 'q' if available; otherwise fall back to LLM-provided 'search_terms'
        brave_search_params.setdefault("q", args.get("search_terms"))

        # Ensure a query was provided
        if not brave_search_params.get("q"):
            return "Error: No 'search terms' or 'q' provided."

        logger = logging.getLogger(self.__class__.__name__)
        logger.info(">>>>>>>>>>>>>>>>>>>BraveSearch>>>>>>>>>>>>>>>>>>")
        logger.info("BraveSearch Terms: %s", brave_search_params.get("q"))
        logger.info("BraveSearch URL: %s", brave_url)
        logger.info("BraveSearch Timeout: %s", brave_timeout)

        results: Dict[str, Any] = self.brave_search(brave_search_params, brave_url, brave_timeout)
        logger.info("BraveSearch Results: %s", json.dumps(results, indent=4))

        results_list: List[Dict[str, Any]] = []
        # If there are results from search, get "title", "url", "description", and "extra_snippets"
        # from each result
        if results:
            for result in results.get("web", {}).get("results"):
                result_dict: Dict[str, str] = {}
                result_dict["title"] = result.get("title")
                result_dict["url"] = result.get("url")
                result_dict["description"] = result.get("description")
                result_dict["extra_snippets"] = result.get("extra_snippets")
                results_list.append(result_dict)

        return results_list

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """Run invoke asynchronously."""
        return await asyncio.to_thread(self.invoke, args, sly_data)

    def brave_search(
        self,
        brave_search_params: Dict[str, Any],
        brave_url: Optional[str] = BRAVE_URL,
        brave_timeout: Optional[float] = BRAVE_TIMEOUT,
    ) -> Dict[str, Any]:
        """
        Perform a search request to the Brave Search API.

        :param brave_search_params: Dictionary of query parameters to include in the search request.
        :param brave_url: The Brave Search API endpoint to send the request to (default: BRAVE_URL).
        :param brave_timeout: Timeout for the request in seconds (default: BRAVE_TIMEOUT).

        :return: The parsed JSON response from the Brave Search API as a dictionary.
        """
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.brave_api_key,
        }
        results: Dict[str, Any] = {}
        try:
            response = requests.get(brave_url, headers=headers, params=brave_search_params, timeout=brave_timeout)
            response.raise_for_status()
            results = response.json()
        except HTTPError as http_err:
            logging.error("HTTP error occurred: %s - Status code: %s", http_err, response.status_code)
        except JSONDecodeError as json_err:
            logging.error("JSON decode error: %s", json_err)
        except RequestException as req_err:
            logging.error("Request error: %s", req_err)

        return results
