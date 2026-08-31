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

from datetime import datetime
from datetime import timezone
from logging import Logger
from logging import getLogger
from typing import Any

from neuro_san.interfaces.coded_tool import CodedTool

from neuro_san_studio.coded_tools.utils.safe_fetch import SafeFetch

MAX_CHARS: int = 20_000
SUPPORTED_CONTENT_TYPES: set[str] = {
    "application/atom+xml",
    "application/pdf",
    "application/rss+xml",
    "application/xhtml+xml",
    "application/xml",
    "text/csv",
    "text/html",
    "text/markdown",
    "text/plain",
    "text/xml",
}


class WebFetch(CodedTool):
    """
    CodedTool implementation that fetches a URL and returns its plain-text body.

    XML and feed responses are returned as extracted text; raw XML markup is not preserved.

    All validation and network access is delegated to the shared SSRF-hardened
    fetch path (SafeFetch): private/loopback/reserved hosts are rejected,
    DNS records are validated at connection time by GlobalOnlyResolver
    (anti DNS-rebinding), redirects are not followed, and response sizes are
    capped. HTML is stripped with BeautifulSoup; PDF bodies are parsed with pypdf.
    Use allowed_domains / blocked_domains for stricter control.

    Error types (raised as ValueError or aiohttp.ClientResponseError or aiohttp.ClientError with the specified message)
        invalid_input            – URL is missing, not a valid http/https URL, or a parameter has an invalid type.
        url_too_long             – URL exceeds the SafeFetch URL length limit.
        url_not_allowed          – URL targets a private/reserved host, is blocked by domain rules,
                                    or returns a redirect.
        url_not_accessible       – HTTP error or network failure while fetching the page.
        too_many_requests        – Server returned HTTP 429.
        unsupported_content_type – Content type is not an approved text, XML, feed, HTML, or PDF type.
        response_too_large       – Content-Length header or streamed body (text or PDF) exceeds the byte limit.
    """

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any]:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "url"               (str, required): The URL to fetch.
                    "allowed_domains"   (list[str], optional): Only fetch from these domains.
                    "blocked_domains"   (list[str], optional): Refuse to fetch from these domains.
                    "max_content_chars" (int, optional): Character cap on returned text.
                                        Defaults to MAX_CHARS. Must be a positive integer.

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                Keys expected for this implementation are:
                    None

        :return:
            A dictionary with the following keys:
                "url"          (str): The URL that was fetched.
                "content"      (str): Plain-text body of the fetched page.
                "retrieved_at" (str): ISO-8601 UTC timestamp when the content was retrieved.

        :raises ValueError: invalid_input, url_too_long, url_not_allowed,
                            unsupported_content_type, response_too_large.
        :raises aiohttp.ClientResponseError: url_not_accessible / too_many_requests (non-2xx response).
        :raises aiohttp.ClientError: url_not_accessible when PDF or text fetch fails.
        """
        url: str = SafeFetch.validate_url(
            args.get("url", ""), args.get("allowed_domains"), args.get("blocked_domains")
        )
        max_chars: int = self._validate_max_content_chars(args)

        logger: Logger = getLogger(self.__class__.__name__)
        logger.info("WebFetch: fetching %s", url)

        async with SafeFetch.open_session() as session:
            content_type, prefetched_text = await SafeFetch.get_content_type(url, session)
            # Route on the base media type only, case-insensitively (RFC 9110). A
            # parameter such as "; charset=..." or "; profile=text/plain" must not
            # affect the decision, and substring matching would misclassify types
            # like "image/png; profile=text/plain" or "application/x-text/plain".
            base_type: str = content_type.split(";", 1)[0].strip().lower()
            is_pdf: bool = SafeFetch.is_pdf(content_type, url)

            if not is_pdf and not self._is_supported_content_type(base_type):
                raise ValueError(
                    f"unsupported_content_type: Content type '{content_type}' is not supported. "
                    "Only approved text, XML, feed, HTML, and PDF types are accepted."
                )

            retrieved_at: str = datetime.now(timezone.utc).isoformat()
            if is_pdf:
                # Note: passing the PDF as base64 directly to the model would be
                # preferable once neuro-san supports multimodal input.
                text: str = await SafeFetch.fetch_pdf_text(url, session)
            elif prefetched_text is not None:
                # Body was already fetched during the 405 HEAD fallback GET; no second request needed.
                text = SafeFetch.parse_raw_text(prefetched_text)
            else:
                text = await SafeFetch.fetch_text(url, session)

        text = text[:max_chars]

        logger.info("WebFetch: returned %d characters from %s", len(text), url)

        # return format taken from Anthropic's webfetch tool
        return {
            "url": url,
            "content": text,
            "retrieved_at": retrieved_at,
        }

    @staticmethod
    def _is_supported_content_type(base_type: str) -> bool:
        """
        Report whether a base media type is exactly one of the supported text and PDF types.

        Exact membership (not substring) is required so an unsupported type that merely
        contains a supported token, such as "application/x-text/plain", or a parameter
        like "image/png; profile=text/plain" once reduced to its base, is rejected.

        :param base_type: The base media type with parameters removed, lower-cased.
        :return: True if base_type is exactly one of SUPPORTED_CONTENT_TYPES.
        """
        return base_type in SUPPORTED_CONTENT_TYPES

    @staticmethod
    def _validate_max_content_chars(args: dict[str, Any]) -> int:
        """
        Validate the optional max_content_chars argument and return its value.

        A present value must be a positive integer. 0 and negative values are
        rejected rather than silently falling back to MAX_CHARS: this is a
        deliberate change from an earlier revision, so a nonsensical cap surfaces
        as invalid_input instead of an unexpectedly huge default.

        :param args: The tool argument dictionary; "max_content_chars" is optional.
        :return: The validated positive-integer character cap, defaulting to MAX_CHARS
                 when the key is absent or None.
        :raises ValueError: invalid_input when the value is present but not a positive
                int (0, a negative number, a bool, or a non-int all fail).
        """
        value: Any = args.get("max_content_chars")
        if value is None:
            return MAX_CHARS
        # bool is a subclass of int, so reject it explicitly; True would otherwise
        # pass as 1 and silently truncate output to a single character.
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"invalid_input: 'max_content_chars' must be a positive integer, got {value!r}.")
        return value
