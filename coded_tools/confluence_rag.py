"""Tool module for doing RAG from confluence pages"""

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

import inspect
import logging
import os
from typing import Any
from typing import Dict
from typing import List

# pylint: disable=import-error
from atlassian.errors import ApiPermissionError
from langchain_community.document_loaders.confluence import ConfluenceLoader
from langchain_core.documents import Document
from neuro_san.interfaces.coded_tool import CodedTool
from requests.exceptions import HTTPError

from .base_rag import BaseRag

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

        # Create a list of parameters of ConfluenceLoader
        # https://python.langchain.com/api_reference/community/document_loaders/langchain_community.document_loaders.confluence.ConfluenceLoader.html
        confluence_loader_params = [
            name for name in inspect.signature(ConfluenceLoader.__init__).parameters if name != "self"
        ]

        # Filter args from the above list
        loader_args = {arg: arg_value for arg, arg_value in args.items() if arg in confluence_loader_params}

        # Check the env var for "username" and "api_key"
        loader_args.setdefault("username", os.getenv("JIRA_USERNAME"))
        loader_args.setdefault("api_key", os.getenv("JIRA_API_TOKEN"))

        # Validate presence of required inputs
        if not query:
            logger.error("Missing required input: 'query'")
            return "❌ Missing required input: 'query'."
        if not loader_args.get("url"):
            logger.error("Missing required input: 'url'")
            return (
                "❌ Missing required input: 'url'.\n" "This should look like: https://your-domain.atlassian.net/wiki/"
            )
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
            loader = ConfluenceLoader(**loader_args)
            docs = await loader.aload()
            logger.info("Successfully loaded Confluence pages from %s", url)
        except HTTPError as http_error:
            logger.error("HTTP error while loading from %s: %s", url, http_error)
            return []
        except ApiPermissionError as api_error:
            logger.error("API Permission error while loading from %s: %s", url, api_error)

        return docs
