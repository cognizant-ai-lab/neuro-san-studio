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

from langchain_community.retrievers import ArxivRetriever
from neuro_san.interfaces.coded_tool import CodedTool

from .base_rag import BaseRag

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ArxivRag(CodedTool):
    """
    CodedTool implementation which provides a way to do RAG on arXiv papers.
    """

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        Load arXiv papers based on queries, build an in-memory vector store, and run a query against it.

        :param args: Dictionary containing:
            "query": search string
            "top_k_results": number of top results to return (default is 3)
            "get_full_documents": whether to pull full paper text or only abstracts/summaries (default is True)
            "doc_content_chars_max": maximum number of characters to keep in each document (default is 4000)
            "load_all_available_meta": whether to load all available metadata (default is False)
            "continue_on_failure": whether to continue processing if an error occurs (default is True)

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

        :return: Result of the query against the vector store.
        """
        # Extract arguments from the input dictionary
        query: str = args.get("query", "").replace("<|endoftext|>", "")

        # Validate presence of required inputs
        if not query:
            logger.error("Missing required input: 'query' (retrieval question).")
            return "❌ Missing required1 input: 'query'."

        # Initialize ArxivRetriever with the provided arguments
        retriever = ArxivRetriever(
            top_k_results=int(args.get("top_k_results", 3)),
            get_full_documents=bool(args.get("get_full_documents", True)),
            doc_content_chars_max=int(args.get("doc_content_chars_max", 4000)),
            load_all_available_meta=bool(args.get("load_all_available_meta", False)),
            continue_on_failure=bool(args.get("continue_on_failure", True)),
        )

        return await BaseRag.query_retriever(retriever, query)
