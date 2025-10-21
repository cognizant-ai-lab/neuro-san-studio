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

import logging
from typing import Any
from typing import Dict

from langchain_community.retrievers import WikipediaRetriever
from neuro_san.interfaces.coded_tool import CodedTool

from .base_rag import BaseRag

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class WikipediaRag(CodedTool):
    """
    CodedTool implementation which provides a way to do RAG on Wikipedia articles.
    """

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        Retrieves relevant Wikipedia articles based on the provided query.

        :param args: Dictionary containing:
            "query": search string
            "lang": language code for Wikipedia articles (default is "en")
            "top_k_results": number of top results to return (default is 3)
            "doc_content_chars_max": maximum number of characters to keep in each document (default is 4000)

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

        :return: A string containing the concatenated content of the retrieved documents.
        """
        # Extract arguments from the input dictionary
        query: str = args.get("query", "")

        # Validate presence of required inputs
        if not query:
            logger.error("Missing required input: 'query' (retrieval question).")
            return "❌ Missing required input: 'query'."

        # Initialize WikipediaRetriever with the provided arguments
        retriever = WikipediaRetriever(
            lang=str(args.get("lang", "en")),
            top_k_results=int(args.get("top_k_results", 3)),
            doc_content_chars_max=int(args.get("doc_content_chars_max", 4000)),
        )

        return await BaseRag.query_retriever(retriever, query)
