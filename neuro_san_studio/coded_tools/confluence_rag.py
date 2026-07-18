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

"""Tool module for doing RAG from confluence pages"""

import logging
import os
from asyncio import to_thread
from typing import Any
from typing import Dict
from typing import List

from bs4 import BeautifulSoup
from langchain_core.documents import Document
from neuro_san.interfaces.coded_tool import CodedTool

from neuro_san_studio.coded_tools.base_rag import BaseRag

INVALID_PATH_PATTERN = r"[<>:\"|?*\x00-\x1F]"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConfluenceRag(CodedTool, BaseRag):
    """
    CodedTool implementation which provides a way to do RAG on confluence pages
    """

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        Load confluence pages from URLs, build a vector store, and run a query against it.

        :param args: Dictionary containing:
          "query": search string

        :param sly_data: A dictionary whose keys are defined by the agent
            hierarchy, but whose values are meant to be kept out of the
            chat stream.

            This dictionary is largely to be treated as read-only.
            It is possible to add key/value pairs to this dict that do not
            yet exist as a bulletin board, as long as the responsibility
            for which coded_tool publishes new entries is well understood
            by the agent chain implementation and the coded_tool implementation
            adding the data is not invoke()-ed more than once.

            Keys expected for this implementation are:
                None
        :return: Text result from querying the built vector store,
            or error message
        """
        # Extract arguments from the input dictionary
        query: str = args.get("query", "")

        loader_args = {
            name: args[name]
            for name in ("url", "space_key", "page_ids", "username", "api_key", "cloud", "include_attachments")
            if name in args
        }

        # Check the env var for "username" and "api_key"
        loader_args.setdefault("username", os.getenv("JIRA_USERNAME"))
        loader_args.setdefault("api_key", os.getenv("JIRA_API_TOKEN"))

        # Validate presence of required inputs
        if not query:
            logger.error("Missing required input: 'query'")
            return "❌ Missing required input: 'query'."
        if not loader_args.get("url"):
            logger.error("Missing required input: 'url'")
            return "❌ Missing required input: 'url'.\nThis should look like: https://your-domain.atlassian.net/wiki/"
        if not loader_args.get("space_key") and not loader_args.get("page_ids"):
            logger.error("Missing both 'space_key' and 'page_ids'")
            return (
                "❌ Missing both 'space_key' and 'page_ids'.\n"
                "Provide at least one to locate the Confluence content to load.\n"
                "- 'space_key' is the identifier of the Confluence space (e.g., 'DAI').\n"
                "- 'page_ids' should be a list of page IDs you want to load, e.g., ['123456', '7891011'].\n\n"
                "Tip: You can find these values in a page URL like:\n"
                "https://your-domain.atlassian.net/wiki/spaces/<space_key>/pages/<page_id>/<title>"
            )

        # Save the generated vector store as a JSON file if True
        self.save_vector_store = args.get("save_vector_store", False)

        # Configure the vector store path
        self.configure_vector_store_path(args.get("vector_store_path"))

        # Prepare the vector store
        vectorstore = await self.generate_vector_store(loader_args=loader_args)

        # Run the query against the vector store
        return await self.query_vectorstore(vectorstore, query)

    async def load_documents(self, loader_args: Dict[str, Any]) -> List[Document]:
        """
        Load Confluence pages from the provided loader arguments.

        :param loader_args: Dictionary containing 'url', 'space_key', and/or 'page_ids' of the Confluence pages to load
        :return: List of loaded Confluence pages
        """
        url = loader_args.get("url")
        docs: List[Document] = []
        try:
            docs = await to_thread(self._load_pages, loader_args)
            logger.info("Successfully loaded Confluence pages from %s", url)
        except Exception as error:  # pylint: disable=broad-exception-caught
            logger.error("Failed to load Confluence pages from %s: %s", url, error)

        return docs

    @staticmethod
    def _load_pages(loader_args: Dict[str, Any]) -> List[Document]:
        """Load Confluence page bodies using ``atlassian-python-api`` directly."""
        # pylint: disable=import-error,import-outside-toplevel
        from atlassian import Confluence

        confluence = Confluence(
            url=loader_args["url"],
            username=loader_args.get("username"),
            password=loader_args.get("api_key"),
            cloud=loader_args.get("cloud", True),
        )
        pages: list[dict[str, Any]] = []
        for page_id in loader_args.get("page_ids") or []:
            pages.append(confluence.get_page_by_id(page_id, expand="body.storage,version,space"))
        if loader_args.get("space_key"):
            start = 0
            while True:
                batch = confluence.get_all_pages_from_space(
                    loader_args["space_key"],
                    start=start,
                    limit=100,
                    status="current",
                    expand="body.storage,version,space",
                )
                pages.extend(batch)
                if len(batch) < 100:
                    break
                start += len(batch)

        documents: list[Document] = []
        seen: set[str] = set()
        for page in pages:
            page_id = str(page.get("id", ""))
            if not page_id or page_id in seen:
                continue
            seen.add(page_id)
            html = page.get("body", {}).get("storage", {}).get("value", "")
            text = BeautifulSoup(html, "html.parser").get_text(separator="\n", strip=True)
            documents.append(
                Document(
                    page_content=text,
                    metadata={
                        "id": page_id,
                        "title": page.get("title", ""),
                        "source": f"{loader_args['url'].rstrip('/')}/pages/viewpage.action?pageId={page_id}",
                        "space_key": page.get("space", {}).get("key"),
                        "version": page.get("version", {}).get("number"),
                    },
                )
            )
        if loader_args.get("include_attachments"):
            logger.warning("include_attachments is not yet supported by the direct Confluence loader")
        return documents
