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
import os
from typing import Any
from typing import Dict
from typing import List
from typing import Tuple
from typing import Union

from aiohttp import ClientError
from aiohttp import ClientSession
from aiohttp import ClientTimeout
from neuro_san.interfaces.coded_tool import CodedTool

# Default parameters for Serply search
K = 10  # number of search results
GL = "us"  # country
HL = "en"  # language
TYPE = "search"  # search type
SERPLY_URL = "https://api.serply.io/v1"
SERPLY_TIMEOUT = 30.0
SEARCH_TYPES = {"search", "news", "scholar"}
MIN_K = 1  # minimum number of search results the API accepts
MAX_K = 100  # maximum number of search results the API accepts
# Serply sits behind Cloudflare, which rejects requests that carry no User-Agent header.
USER_AGENT = "neuro-san-studio"

# Each search type returns its results under a different key, with a different shape.
RESULT_KEYS = {"search": "results", "news": "entries", "scholar": "articles"}

logger = logging.getLogger(__name__)


class SerplySearch(CodedTool):
    """
    CodedTool implementation which provides a way to search Google through the Serply API.

    Serply returns Google organic results as JSON, and the same key also serves the
    Google News and Google Scholar verticals, selected here with the "type" argument.

    For info on Serply, and to get a Serply API key, go to https://serply.io
    """

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "query" the query to search for.

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
                A dictionary with the search type and a list of results.
            otherwise:
                a text string an error message in the format:
                "Error: <error message>"
        """
        request: Union[Tuple[str, int, Dict[str, Any]], str] = self.build_request(args)
        # build_request returns the coded tool error string when an argument is not usable.
        if isinstance(request, str):
            return request
        search_type, k, params = request

        serply_api_key: str = os.getenv("SERPLY_API_KEY")
        if not serply_api_key:
            return "Error: SERPLY_API_KEY is not set."

        settings: Union[Tuple[str, float], str] = self.client_settings(args)
        if isinstance(settings, str):
            return settings
        serply_url, serply_timeout = settings

        logger.info("SerplySearch %s request: %s", search_type, params)

        try:
            async with ClientSession(timeout=ClientTimeout(total=serply_timeout)) as session:
                async with session.get(
                    f"{serply_url}/{search_type}/",
                    headers={"X-Api-Key": serply_api_key, "User-Agent": USER_AGENT},
                    params=params,
                ) as response:
                    response.raise_for_status()
                    results: Dict[str, Any] = await response.json()
        except (ClientError, TimeoutError, ValueError) as error:
            logger.error("Serply request failed: %s", error)
            return f"Error: Serply request failed: {error}"

        return self.format_results(search_type, k, results)

    @staticmethod
    def build_request(args: Dict[str, Any]) -> Union[Tuple[str, int, Dict[str, Any]], str]:
        """
        Validate the tool arguments and turn them into a Serply request.

        Neuro SAN includes unused optional keys as JSON null, so "or" is used below to treat
        None the same as an omitted argument instead of sending it to the API.

        :param args: The argument dictionary passed to the coded tool.

        :return: A (search_type, k, query_params) tuple, or a text string error message in the format
                 "Error: <error message>".
        """
        query: str = args.get("query") or ""
        if query == "":
            return "Error: No query provided."

        # Type of search: "search" for Google organic results, "news" or "scholar" for those verticals
        search_type: str = args.get("type") or TYPE
        if search_type not in SEARCH_TYPES:
            return f"Error: Unsupported search type: {search_type}."

        # Number of top search results to retrieve
        k: Union[int, str] = SerplySearch.parse_k(args.get("k"))
        if isinstance(k, str):
            return k

        params: Dict[str, Any] = {
            "q": query,
            "num": k,
            # Language code for the search interface (e.g., "en" for English)
            "hl": args.get("hl") or HL,
            # Country code to localize search results (e.g., "us" for United States)
            "gl": args.get("gl") or GL,
        }
        # Search filter string (e.g., "qdr:d" for past day results); optional and can be used for time filtering
        tbs = args.get("tbs")
        if tbs:
            params["tbs"] = tbs

        return search_type, k, params

    @staticmethod
    def client_settings(args: Dict[str, Any]) -> Union[Tuple[str, float], str]:
        """
        Resolve the Serply base URL and request timeout.

        Both are taken from the tool arguments first, then from the SERPLY_URL and SERPLY_TIMEOUT
        environment variables, and finally fall back to the module defaults.

        :param args: The argument dictionary passed to the coded tool.

        :return: A (base_url, timeout_seconds) tuple, or a text string error message in the format
                 "Error: <error message>".
        """
        serply_url: str = (args.get("serply_url") or os.getenv("SERPLY_URL") or SERPLY_URL).rstrip("/")
        timeout_arg: Any = args.get("serply_timeout")
        if timeout_arg is None:
            timeout_arg = os.getenv("SERPLY_TIMEOUT") or SERPLY_TIMEOUT
        try:
            serply_timeout: float = float(timeout_arg)
        except (TypeError, ValueError):
            return f"Error: 'serply_timeout' must be a number, got: {timeout_arg!r}."
        return serply_url, serply_timeout

    @staticmethod
    def parse_k(value: Any) -> Union[int, str]:
        """
        Validate the requested number of results against the range the API accepts.

        :param value: The requested number of results, or None when the caller did not supply one.

        :return: The count as an int, or a text string error message in the format "Error: <error message>".
        """
        if value is None:
            return K
        try:
            k = int(value)
        except (TypeError, ValueError):
            return f"Error: 'k' must be an integer, got: {value!r}."
        if not MIN_K <= k <= MAX_K:
            return f"Error: 'k' must be between {MIN_K} and {MAX_K}, got: {k}."
        return k

    @staticmethod
    def format_results(search_type: str, k: int, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reduce a raw Serply response to the fields an agent needs.

        The raw payload also carries ads, shopping results, carousels and related questions, which would
        crowd the LLM context. Each search type has its own result shape: organic results carry a
        "description" and a "position", news entries carry a "published" date, and scholar articles carry
        the authors and venue in "description" plus a citation count.

        The news vertical does not honor "num", so the list is cut to k here for every type.

        :param search_type: The search type that was requested.
        :param k: The number of results that was requested.
        :param results: The parsed JSON response from the Serply API.

        :return: A dictionary with the search type and a list of results.
        """
        formatted: List[Dict[str, Any]] = []
        for result in results.get(RESULT_KEYS[search_type], []) or []:
            link = result.get("link")
            if not link:
                continue
            result_dict: Dict[str, Any] = {"title": result.get("title"), "link": link}
            if search_type == "search":
                result_dict["description"] = result.get("description")
                result_dict["position"] = result.get("position")
            elif search_type == "news":
                result_dict["published"] = result.get("published")
            else:
                result_dict["description"] = result.get("description")
                citations = (result.get("extras") or {}).get("citations") or {}
                if citations.get("count") is not None:
                    result_dict["citations"] = citations.get("count")
            formatted.append({key: value for key, value in result_dict.items() if value is not None})
            if len(formatted) >= k:
                break

        return {"type": search_type, "results": formatted}
