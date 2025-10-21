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

GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"
GOOGLE_SEARCH_TIMEOUT = 30.0
# The following parameters are from https://developers.google.com/custom-search/v1/reference/rest/v1/cse/list#request.
GOOGLE_SEARCH_QUERY_PARAMS = [
    "q",
    "c2coff",
    "cr",
    "cx",
    "dateRestrict",
    "exactTerms",
    "excludeTerms",
    "fileType",
    "filter",
    "gl",
    "googlehost",
    "highRange",
    "hl",
    "hq",
    "imgColorType",
    "imgDominantColor",
    "imgSize",
    "imgType",
    "linkSite",
    "lowRange",
    "lr",
    "num",
    "orTerms",
    "rights",
    "safe",
    "searchType",
    "siteSearch",
    "siteSearchFilter",
    "sort",
    "start",
]


class GoogleSearch(CodedTool):
    """
    CodedTool implementation which provides a way to search the web using Google search API
    For info on Google search, and to get a Google search API key and a custom search engine ID,
    go to https://python.langchain.com/docs/integrations/tools/google_search/
    """

    def __init__(self):
        self.google_api_key = os.getenv("GOOGLE_SEARCH_API_KEY")
        if self.google_api_key is None:
            logging.error("GOOGLE_API_KEY is not set!")

        self.google_cse_id = os.getenv("GOOGLE_SEARCH_CSE_ID")
        if self.google_cse_id is None:
            logging.error("GOOGLE_CSE_ID is not set!")

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
        google_url: str = args.get("google_url") or os.getenv("GOOGLE_SEARCH_URL") or GOOGLE_SEARCH_URL
        google_timeout: float = float(
            args.get("google_timeout") or os.getenv("GOOGLE_SEARCH_TIMEOUT") or GOOGLE_SEARCH_TIMEOUT
        )

        # Filter user-specified args using the GOOGLE_QUERY_PARAMS
        google_search_params = {
            param: param_value for param, param_value in args.items() if param in GOOGLE_SEARCH_QUERY_PARAMS
        }

        # Use user-specified query 'q' if available; otherwise fall back to LLM-provided 'search_terms'
        google_search_params.setdefault("q", args.get("search_terms"))

        # Set the API key and Custom Search Engine ID fields
        google_search_params["key"] = self.google_api_key
        google_search_params["cx"] = self.google_cse_id

        # Ensure a query was provided
        if not google_search_params.get("q"):
            return "Error: No 'search terms' or 'q' provided."

        logger = logging.getLogger(self.__class__.__name__)
        logger.info(">>>>>>>>>>>>>>>>>>>GoogleSearch>>>>>>>>>>>>>>>>>>")
        logger.info("GoogleSearch Terms: %s", google_search_params.get("q"))
        logger.info("GoogleSearch URL: %s", google_url)
        logger.info("GoogleSearch Timeout: %s", google_timeout)

        results: Dict[str, Any] = self.google_search(google_search_params, google_url, google_timeout)
        logger.info("GoogleSearch Results: %s", json.dumps(results, indent=4))

        results_list: List[Dict[str, Any]] = []
        # If there are results from search, get "title", "link", "description", and "snippet"
        # from each result. For a list of available fields in a response to a custom search request
        # go to https://developers.google.com/custom-search/v1/reference/rest/v1/Search
        if results:
            for item in results.get("items", []):
                result_dict: Dict[str, str] = {}
                result_dict["title"] = item["title"]
                result_dict["link"] = item["link"]
                result_dict["snippet"] = item["snippet"]
                results_list.append(result_dict)

        return results_list

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """Run invoke asynchronously."""
        return await asyncio.to_thread(self.invoke, args, sly_data)

    def google_search(
        self,
        google_search_params: Dict[str, Any],
        google_url: Optional[str] = GOOGLE_SEARCH_URL,
        google_timeout: Optional[float] = GOOGLE_SEARCH_TIMEOUT,
    ) -> Dict[str, Any]:
        """
        Perform a search request to the Google Search API.

        :param google_search_params: Dictionary of query parameters to include in the search request.
        :param google_url: The Google Search API endpoint to send the request to (default: GOOGLE_URL).
        :param google_timeout: Timeout for the request in seconds (default: GOOGLE_TIMEOUT).

        :return: The parsed JSON response from the Google Search API as a dictionary.
        """
        results: Dict[str, Any] = {}
        try:
            response = requests.get(google_url, params=google_search_params, timeout=google_timeout)
            response.raise_for_status()
            results = response.json()
        except HTTPError as http_err:
            logging.error("HTTP error occurred: %s - Status code: %s", http_err, response.status_code)
        except JSONDecodeError as json_err:
            logging.error("JSON decode error: %s", json_err)
        except RequestException as req_err:
            logging.error("Request error: %s", req_err)

        return results
