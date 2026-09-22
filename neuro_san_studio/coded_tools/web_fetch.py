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
    "application/json",
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

    XML and feed responses are returned as extracted text; raw XML markup is not
    preserved. JSON responses are returned verbatim (a JSON body does not start
    with "<", so the HTML stripper leaves it untouched).

    All validation and network access is delegated to the shared SSRF-hardened
    fetch path (SafeFetch): private/loopback/reserved hosts are rejected,
    DNS records are validated at connection time by GlobalOnlyResolver
    (anti DNS-rebinding), redirects are followed up to SafeFetch's MAX_REDIRECTS
    hops with every hop re-validated as a brand-new URL (including this tool's own
    allowed_domains / blocked_domains, which are forwarded to SafeFetch for that
    purpose), the body is fetched from the chain's final URL (reported as
    "final_url"), and response sizes are capped. HTML is stripped with BeautifulSoup;
    PDF bodies are sniffed for a "%PDF-" header while streaming, then parsed with
    pypdf. Use allowed_domains / blocked_domains for stricter control.

    Error types (raised as ValueError or aiohttp.ClientResponseError or aiohttp.ClientError with the specified message)
        invalid_input            – URL is missing, not a valid http/https URL, or a parameter has an invalid type.
        url_too_long             – URL exceeds the SafeFetch URL length limit.
        url_not_allowed          – URL targets a private/reserved host, is blocked by domain rules,
                                    or a redirect hop fails those checks / the chain exceeds MAX_REDIRECTS.
        url_not_accessible       – HTTP error or network failure while fetching the page.
        too_many_requests        – Server returned HTTP 429.
        unsupported_content_type – Content type is not an approved text, XML, feed, JSON, HTML, or PDF type.
        response_too_large       – Content-Length header or streamed body (text or PDF) exceeds the byte limit.
        not_a_pdf                – Body classified as PDF has no "%PDF-" header in its first bytes
                                    (e.g. an HTML error page served as application/pdf).
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
                "url"          (str): The URL that was requested.
                "final_url"    (str): The URL the content was fetched from, after any
                                      redirects (equal to "url" when there were none).
                "content"      (str): Plain-text body of the fetched page.
                "retrieved_at" (str): ISO-8601 UTC timestamp when the content was retrieved.

        :raises ValueError: invalid_input, url_too_long, url_not_allowed,
                            unsupported_content_type, response_too_large, not_a_pdf.
        :raises aiohttp.ClientResponseError: url_not_accessible / too_many_requests (non-2xx response).
        :raises aiohttp.ClientError: url_not_accessible when PDF or text fetch fails.
        """
        allowed_domains: Any = args.get("allowed_domains")
        blocked_domains: Any = args.get("blocked_domains")
        url: str = SafeFetch.validate_url(args.get("url", ""), allowed_domains, blocked_domains)
        max_chars: int = self._validate_max_content_chars(args)

        logger: Logger = getLogger(self.__class__.__name__)
        logger.info("WebFetch: fetching %s", url)

        # The domain rules are forwarded to every SafeFetch network call so they are
        # re-applied to each redirect hop: validating only the URL the agent supplied
        # would let an open redirect on an allowed domain lead to a blocked or
        # non-allowed one.
        async with SafeFetch.open_session() as session:
            content_type, prefetched_text, final_url = await SafeFetch.get_content_type(
                url, session, allowed_domains=allowed_domains, blocked_domains=blocked_domains
            )
            # Log the redirect before fetching, so the requested -> final link is on record
            # even when the body fetch below fails: SafeFetch's error message names only the
            # URL it was given, which is now final_url rather than the one logged above.
            if final_url != url:
                logger.info("WebFetch: %s redirected to %s", url, final_url)
            # Classify by the URL the headers actually came from, and fetch from it too.
            # A link that redirects to a .pdf served as a generic download type is a PDF
            # even though the requested URL carries no .pdf suffix. Starting the body
            # fetch at final_url instead of the requested URL avoids walking the redirect
            # chain a second time and guarantees the body comes from the same place the
            # classification did: a rotating or expiring redirect could otherwise send
            # the second walk elsewhere and hand a PDF body to the HTML stripper (or the
            # reverse). Nothing is skipped by this: the probe re-validated every hop under
            # the same domain rules, and the fetch re-validates final_url at entry again.
            is_pdf: bool = SafeFetch.is_pdf(content_type, final_url)

            if not is_pdf and not self._is_supported_content_type(content_type):
                raise ValueError(
                    f"unsupported_content_type: Content type '{content_type}' is not supported. "
                    "Only approved text, XML, feed, JSON, HTML, and PDF types are accepted."
                )

            retrieved_at: str = datetime.now(timezone.utc).isoformat()
            if is_pdf:
                # Note: passing the PDF as base64 directly to the model would be
                # preferable once neuro-san supports multimodal input.
                text: str = await SafeFetch.fetch_pdf_text(
                    final_url, session, allowed_domains=allowed_domains, blocked_domains=blocked_domains
                )
            elif prefetched_text is not None:
                # Body was already fetched during the 405 HEAD fallback GET; no second request needed.
                text = SafeFetch.parse_raw_text(prefetched_text)
            else:
                text = await SafeFetch.fetch_text(
                    final_url, session, allowed_domains=allowed_domains, blocked_domains=blocked_domains
                )

        text = text[:max_chars]

        logger.info("WebFetch: returned %d characters from %s", len(text), final_url)

        # return format taken from Anthropic's webfetch tool, plus final_url so the
        # agent can cite where the content actually came from
        return {
            "url": url,
            "final_url": final_url,
            "content": text,
            "retrieved_at": retrieved_at,
        }

    @staticmethod
    def _is_supported_content_type(content_type: str) -> bool:
        """
        Report whether a Content-Type's base media type is exactly one of the supported text and PDF types.

        The decision uses the base media type only, case-insensitively (RFC 9110): a
        parameter such as "; charset=..." or "; profile=text/plain" must not affect it.
        Exact membership (not substring) is required so an unsupported type that merely
        contains a supported token, such as "application/x-text/plain", or a parameter
        like "image/png; profile=text/plain" once reduced to its base, is rejected.

        :param content_type: The raw Content-Type header value, parameters included.
        :return: True if the base media type is exactly one of SUPPORTED_CONTENT_TYPES.
        """
        base_type: str = content_type.split(";", 1)[0].strip().lower()
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
