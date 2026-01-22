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
from typing import Any
from typing import Dict

from langchain_community.retrievers import ArxivRetriever
from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.tools.base_rag import BaseRag

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
            raise ValueError("❌ Missing required input: 'query'.")

        # For the arXiv API, the query argument must follow a specific format,
        # for example: "au:del_maestro AND ti:checkerboard".
        #
        # References:
        # - https://lukasschwab.me/arxiv.py/arxiv.html#Search.query
        # - https://info.arxiv.org/help/api/user-manual.html#51-details-of-query-construction
        #
        # However, when `get_full_documents` is set to True, LangChain strips
        # characters such as ":" and "-", which makes the query invalid for arXiv.
        #
        # To avoid this issue, we remove the arXiv field prefixes in advance
        # when `get_full_documents` is enabled.
        get_full_documents = bool(args.get("get_full_documents", False))
        if get_full_documents:
            prefixes = ["ti:", "au:", "abs:", "co:", "jr:", "cat:", "rn:", "id_list:"]
            for prefix in prefixes:
                query = query.replace(prefix, "")

        # Initialize ArxivRetriever with the provided arguments
        retriever = ArxivRetriever(
            top_k_results=int(args.get("top_k_results", 3)),
            get_full_documents=get_full_documents,
            doc_content_chars_max=int(args.get("doc_content_chars_max", 4000)),
            load_all_available_meta=bool(args.get("load_all_available_meta", False)),
            continue_on_failure=bool(args.get("continue_on_failure", True)),
        )

        return await BaseRag.query_retriever(retriever, query)
