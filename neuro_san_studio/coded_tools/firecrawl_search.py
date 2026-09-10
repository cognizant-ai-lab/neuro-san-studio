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

# Default parameters for Firecrawl Search
LIMIT = 5  # number of search results
COUNTRY = "us"  # ISO country code used to localize results
SOURCE = "web"  # result source
SCRAPE_CONTENT = True  # return cleaned Markdown for each result
FIRECRAWL_URL = "https://api.firecrawl.dev/v2/search"
# Scraping the result pages happens inside the request, so this needs to be well above a
# snippet-only search. The API's own per-request default is 60s.
FIRECRAWL_TIMEOUT = 120.0
SOURCES = {"web", "images", "news"}
CATEGORIES = {"developer", "research", "pdf"}
MAX_QUERY_LENGTH = 500
MIN_LIMIT = 1  # minimum number of search results the API accepts
MAX_LIMIT = 100  # maximum number of search results the API accepts

# Each source returns a different result shape, so they cannot share one field list.
# Field names are passed through exactly as the Firecrawl API documents them.
SOURCE_FIELDS: Dict[str, Tuple[str, ...]] = {
    "web": ("title", "url", "description"),
    "news": ("title", "url", "snippet", "date"),
    "images": ("title", "url", "imageUrl", "imageWidth", "imageHeight"),
}

FALSE_STRINGS = {"false", "0", "no", "off", ""}

logger = logging.getLogger(__name__)


class FirecrawlSearch(CodedTool):
    """
    CodedTool implementation which provides a way to search the web using the Firecrawl Search API.

    Firecrawl Search returns ranked search results and, in the same call, the cleaned Markdown of each
    result page. This removes the usual "search, then fetch and clean each URL" round trip.

    For info on Firecrawl Search, and to get a Firecrawl API key, go to https://www.firecrawl.dev/search
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
                A dictionary of search results keyed by source, plus the number of credits used.
            otherwise:
                a text string an error message in the format:
                "Error: <error message>"
        """
        payload: Union[Dict[str, Any], str] = self.build_payload(args)
        # build_payload returns the coded tool error string when an argument is not usable.
        if isinstance(payload, str):
            return payload

        firecrawl_api_key: str = os.getenv("FIRECRAWL_API_KEY")
        if not firecrawl_api_key:
            return "Error: FIRECRAWL_API_KEY is not set."

        # Extract URL and timeout from args, then environment variables, then fall back to defaults
        firecrawl_url: str = args.get("firecrawl_url") or os.getenv("FIRECRAWL_URL") or FIRECRAWL_URL
        try:
            firecrawl_timeout: float = float(
                args.get("firecrawl_timeout") or os.getenv("FIRECRAWL_TIMEOUT") or FIRECRAWL_TIMEOUT
            )
        except (TypeError, ValueError):
            return f"Error: 'firecrawl_timeout' must be a number, got: {args.get('firecrawl_timeout')!r}."

        headers = {
            "Authorization": f"Bearer {firecrawl_api_key}",
            "Content-Type": "application/json",
        }

        logger.info("FirecrawlSearch query: %s", payload["query"])

        # The Search API timeout is milliseconds. Keep it aligned with the client timeout,
        # otherwise the server still uses its 60s default while aiohttp waits longer.
        payload["timeout"] = int(firecrawl_timeout * 1000)

        try:
            async with ClientSession(timeout=ClientTimeout(total=firecrawl_timeout)) as session:
                async with session.post(firecrawl_url, headers=headers, json=payload) as response:
                    results: Dict[str, Any] = await response.json(content_type=None)
                    if response.status >= 400:
                        error_message = (
                            results.get("error") if isinstance(results, dict) else None
                        ) or f"{response.status} {response.reason}"
                        logger.error("Firecrawl request failed: %s", error_message)
                        return f"Error: Firecrawl request failed: {error_message}"
        except (ClientError, TimeoutError, ValueError) as error:
            logger.error("Firecrawl request failed: %s", error)
            return f"Error: Firecrawl request failed: {error}"

        # A non-2xx status is already handled above, but guard against a body that reports failure
        # on an otherwise successful response rather than returning an empty result set.
        if results.get("success") is False:
            error_message = results.get("error") or "unknown error"
            logger.error("Firecrawl returned an unsuccessful response: %s", error_message)
            return f"Error: Firecrawl request failed: {error_message}"

        return self.format_results(results)

    @staticmethod
    def build_payload(args: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        Validate the tool arguments and turn them into a Firecrawl Search request body.

        :param args: The argument dictionary passed to the coded tool.

        :return: The request body, or a text string error message in the format "Error: <error message>".
        """
        # Get query from args. Neuro SAN includes unused optional keys as JSON null.
        query: str = args.get("query") or ""
        if query == "":
            return "Error: No query provided."
        if len(query) > MAX_QUERY_LENGTH:
            return f"Error: 'query' must be at most {MAX_QUERY_LENGTH} characters, got: {len(query)}."

        # Number of top search results to retrieve
        limit_arg: Any = LIMIT if args.get("limit") is None else args.get("limit")
        limit: Union[int, str] = FirecrawlSearch.parse_limit(limit_arg)
        if isinstance(limit, str):
            return limit

        # Result source (e.g., "news" for news results, or "web" for general).
        # Neuro SAN passes JSON null for unused optional args; dict.get(key, default)
        # does not apply the default when the key is present and None.
        source: str = args.get("source") or SOURCE
        if source not in SOURCES:
            return f"Error: Unsupported source: {source}."

        # Optional index to restrict the search to: "developer" (repos, issues, docs), "research" (papers),
        # or "pdf". Default is None, which searches the general web index.
        category: str = args.get("category") or None
        if category is not None and category not in CATEGORIES:
            return f"Error: Unsupported category: {category}."

        payload: Dict[str, Any] = {
            "query": query,
            "limit": limit,
            "sources": [{"type": source}],
            # ISO country code to localize search results (e.g., "us" for United States)
            "country": args.get("country") or COUNTRY,
        }
        if category is not None:
            payload["categories"] = [{"type": category}]
        # Search filter string (e.g., "qdr:d" for past day results); optional and can be used for time filtering
        tbs = args.get("tbs")
        if tbs:
            payload["tbs"] = tbs
        # Whether to also return the cleaned Markdown of each result page
        if FirecrawlSearch.as_bool(args.get("scrape_content"), SCRAPE_CONTENT):
            payload["scrapeOptions"] = {"formats": ["markdown"], "onlyMainContent": True}

        return payload

    @staticmethod
    def parse_limit(value: Any) -> Union[int, str]:
        """
        Validate the requested number of results against the range the API accepts.

        Checking locally turns an HTTP 400 into a message that names the offending argument, and
        saves a round trip.

        :param value: The requested limit.

        :return: The limit as an int, or a text string error message in the format
                 "Error: <error message>".
        """
        try:
            limit = int(value)
        except (TypeError, ValueError):
            return f"Error: 'limit' must be an integer, got: {value!r}."
        if not MIN_LIMIT <= limit <= MAX_LIMIT:
            return f"Error: 'limit' must be between {MIN_LIMIT} and {MAX_LIMIT}, got: {limit}."
        return limit

    @staticmethod
    def as_bool(value: Any, default: bool) -> bool:
        """
        Interpret a tool argument as a boolean.

        HOCON supplies a real boolean, but an LLM may supply the string "false", which is truthy
        to bool(). This maps the usual textual spellings to False instead.

        :param value: The argument value, or None when the caller did not supply one.
        :param default: The value to use when the caller did not supply one.

        :return: The resolved boolean.
        """
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() not in FALSE_STRINGS
        return bool(value)

    @staticmethod
    def format_results(results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reduce a raw Firecrawl Search response to the fields an agent needs.

        Each source returns a different shape: web results carry a "description", news results carry a
        "snippet" and a "date", and image results carry "imageUrl" and its dimensions. They are mapped
        per source so that a news or image search does not come back looking empty.

        The raw response also nests per-result metadata that duplicates the top-level fields. Dropping it
        keeps the scraped Markdown, which is the point of this tool, from crowding the LLM context.

        :param results: The parsed JSON response from the Firecrawl Search API.

        :return: A dictionary keyed by source ("web", "images", "news"), each holding a list of results,
                 plus "credits_used".
        """
        formatted: Dict[str, Any] = {}
        data: Dict[str, Any] = results.get("data", {})
        for source, fields in sorted(SOURCE_FIELDS.items()):
            source_results: List[Dict[str, Any]] = []
            for result in data.get(source, []):
                result_dict: Dict[str, Any] = {
                    field: result.get(field) for field in fields if result.get(field) is not None
                }
                # Only present when scrape_content is on, and never for image results.
                if result.get("markdown"):
                    result_dict["markdown"] = result.get("markdown")
                source_results.append(result_dict)
            if source_results:
                formatted[source] = source_results

        formatted["credits_used"] = results.get("creditsUsed")
        if results.get("warning"):
            formatted["warning"] = results.get("warning")

        return formatted
