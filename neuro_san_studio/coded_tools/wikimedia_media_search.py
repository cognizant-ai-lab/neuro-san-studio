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

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any
from typing import Dict
from typing import List
from typing import Union

from neuro_san.interfaces.coded_tool import CodedTool

logger = logging.getLogger(__name__)


class WikimediaMediaSearch(CodedTool):
    """
    Searches Wikimedia Commons for media files (images, audio, video) and returns direct URLs.
    """

    WIKIMEDIA_API_ENDPOINT = "https://commons.wikimedia.org/w/api.php"
    # User-Agent header is required by Wikimedia API
    USER_AGENT = "test-agent"
    TIMEOUT_SECONDS = 10

    # MIME type prefixes for filtering
    MIME_TYPE_PREFIXES = {"image": "image/", "audio": "audio/", "video": "video/", "all": ""}

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        Searches Wikimedia Commons for media files.

        :param args: a dictionary with the following keys:
            - query: the search query for finding media
            - media_type: type of media to search for ("image", "audio", "video", or "all", default: "image")
            - limit: optional - maximum number of results to return (default: 1, max: 10)
            - offset: optional - result offset for pagination (default: 0, use 10, 20, etc. for different results)

        :param sly_data: a dictionary for shared context (not used in this tool)

        :return:
            In case of successful execution:
                A formatted string with media URLs and descriptions
            otherwise:
                a string error message in the format:
                "Error: <error message>"
        """
        logger.debug(">>>>>>>>>>>>>>>>>>> WikimediaMediaSearch >>>>>>>>>>>>>>>>>>")

        # Get query parameter
        query: str = args.get("query", "").strip()
        if not query:
            error = "Error: Please provide a search query for finding media."
            logger.debug("%s", error)
            return error

        # Get media_type parameter (default: "image")
        media_type: str = args.get("media_type", "image").lower()
        if media_type not in self.MIME_TYPE_PREFIXES:
            error = f"Error: Invalid media_type '{media_type}'. Must be one of: image, audio, video, all"
            logger.debug("%s", error)
            return error

        # Get limit parameter (default 1, max 10)
        limit: int = args.get("limit", 1)
        # Ensure limit is within valid range (1-10)
        limit = max(1, min(limit, 10))

        # Get offset parameter for pagination (default 0)
        offset: int = args.get("offset", 0)
        # Ensure offset is non-negative
        offset = max(0, offset)

        try:
            # Step 1: Search for files in Wikimedia Commons
            # We request more results initially to account for filtering by MIME type
            search_limit = limit * 3 if media_type != "all" else limit
            search_results = self._search_files(query, search_limit, offset)

            if not search_results:
                message = f"No {media_type} files found on Wikimedia Commons for query: '{query}'"
                logger.debug("%s", message)
                return message

            # Step 2: Get media info and filter by MIME type
            media_urls = self._get_media_urls(search_results, media_type, limit)

            if not media_urls:
                message = f"Found files but no {media_type} files matched for query: '{query}'"
                logger.debug("Found files but no %s files matched for query: '%s'", media_type, query)
                return message

            # Format the response
            response = self._format_response(query, media_urls, media_type)
            logger.debug("Response: %s", response)
            logger.debug(">>>>>>>>>>>>>>>>>>> DONE !!! >>>>>>>>>>>>>>>>>>")
            return response

        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            error = f"Error searching Wikimedia Commons: {str(exc)}"
            logger.error("%s", error, exc_info=True)
            return error

    def _search_files(self, query: str, limit: int, offset: int = 0) -> List[str]:
        """
        Search for files in Wikimedia Commons matching the query.

        :param query: search query
        :param limit: maximum number of results
        :param offset: result offset for pagination (default: 0)
        :return: list of file titles
        """
        # Build search query - search in File namespace (namespace 6)
        params = {
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": query,
            "srnamespace": "6",  # File namespace
            "srlimit": str(min(limit, 50)),  # API max is 50
            "srprop": "snippet",
            "sroffset": str(offset),  # Pagination offset
        }

        url = f"{self.WIKIMEDIA_API_ENDPOINT}?{urllib.parse.urlencode(params)}"
        logger.debug("Searching files with URL: %s?%s", self.WIKIMEDIA_API_ENDPOINT, urllib.parse.urlencode(params))

        # Create request with User-Agent header (required by Wikimedia)
        request = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT})
        with urllib.request.urlopen(request, timeout=self.TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))

        search_results = data.get("query", {}).get("search", [])
        file_titles = [result["title"] for result in search_results]

        logger.debug("Found %s files: %s", len(file_titles), file_titles)
        return file_titles

    # pylint: disable=too-many-locals
    def _get_media_urls(self, file_titles: List[str], media_type: str, limit: int) -> List[Dict[str, str]]:
        """
        Get direct media URLs for the given file titles, filtered by media type.

        :param file_titles: list of file titles from Wikimedia Commons
        :param media_type: type of media to filter by
        :param limit: maximum number of results to return
        :return: list of dictionaries with 'title', 'url', 'mime', and 'description'
        """
        if not file_titles:
            return []

        # Build query to get media info (imageinfo works for ALL file types!)
        params = {
            "action": "query",
            "format": "json",
            "titles": "|".join(file_titles),
            "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": "1024",  # Get a reasonably sized thumbnail for images
        }

        url = f"{self.WIKIMEDIA_API_ENDPOINT}?{urllib.parse.urlencode(params)}"
        logger.debug("Getting media URLs with URL: %s", url)

        # Create request with User-Agent header (required by Wikimedia)
        request = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT})
        with urllib.request.urlopen(request, timeout=self.TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))

        pages = data.get("query", {}).get("pages", {})
        mime_prefix = self.MIME_TYPE_PREFIXES[media_type]

        media_data = []
        for page_id, page_info in pages.items():
            _ = page_id  # Unused
            if "imageinfo" in page_info and len(page_info["imageinfo"]) > 0:
                img_info = page_info["imageinfo"][0]
                mime_type_value = img_info.get("mime", "")

                # Filter by MIME type if specified
                if mime_prefix and not mime_type_value.startswith(mime_prefix):
                    continue

                title = page_info.get("title", "Unknown")

                # For images, prefer thumbnail; for audio/video, use original URL
                if media_type == "image":
                    media_url = img_info.get("thumburl", img_info.get("url", ""))
                else:
                    media_url = img_info.get("url", "")

                # Extract description from metadata if available
                ext_metadata = img_info.get("extmetadata", {})
                description = ext_metadata.get("ImageDescription", {}).get("value", "")
                if description:
                    # Clean HTML tags from description
                    description = description.replace("<p>", "").replace("</p>", "").strip()
                    # Limit description length
                    if len(description) > 150:
                        description = description[:147] + "..."

                if media_url:
                    media_data.append(
                        {
                            "title": title,
                            "url": media_url,
                            "mime": mime_type_value,
                            "description": description or "No description available",
                        }
                    )

                    # Stop once we have enough results
                    if len(media_data) >= limit:
                        break

        logger.debug("Retrieved %s %s URLs", len(media_data), media_type)
        return media_data

    def _format_response(self, query: str, media_urls: List[Dict[str, str]], media_type: str) -> str:
        """
        Format the search results into a readable response.

        :param query: original search query
        :param media_urls: list of media data dictionaries
        :param media_type: type of media searched
        :return: formatted string response
        """
        media_label = media_type if media_type != "all" else "media"
        response_lines = [f"Found {len(media_urls)} {media_label} file(s) on Wikimedia Commons for '{query}':\n"]

        for i, media in enumerate(media_urls, 1):
            response_lines.append(f"{i}. {media['title']}")
            response_lines.append(f"   URL: {media['url']}")
            response_lines.append(f"   Type: {media['mime']}")
            if media["description"] and media["description"] != "No description available":
                response_lines.append(f"   Description: {media['description']}")
            response_lines.append("")  # Empty line for readability

        return "\n".join(response_lines)

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        Async version - delegates to synchronous invoke.
        Note: In production, you might want to use aiohttp for true async HTTP requests.
        """
        return self.invoke(args, sly_data)
