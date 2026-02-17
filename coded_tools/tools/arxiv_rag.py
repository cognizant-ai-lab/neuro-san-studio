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

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.tools.base_rag import BaseRag
from coded_tools.tools.modified_arxiv_retriever import ModifiedArxivRetriever

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
            "sort_by": options are `relevance`, `lastUpdatedDate`, and `submittedDate`. Default to `relevance`.
            "sort_order": options are `ascending` and `descending`. Default to `descending`.

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

        # Controls the shape of the data returned to the agent
        # - False (default): return metadata + summarized content
        # - True: return metadata only, and store full document content in sly_data
        get_full_document: bool = args.get("get_full_documents", False)

        # Initialize ArxivRetriever with the provided arguments
        retriever = ModifiedArxivRetriever(
            # LMMs can decide to set a "top_k_results" key to None in args. Make sure we always use an int by default.
            top_k_results=args.get("top_k_results") or 3,
            get_full_documents=get_full_document,
            doc_content_chars_max=args.get("doc_content_chars_max", 4000),
            load_all_available_meta=args.get("load_all_available_meta", False),
            continue_on_failure=args.get("continue_on_failure", True),
            sort_by=args.get("sort_by") or "relevance",
            sort_order=args.get("sort_order") or "descending",
        )

        # Query the retriever
        # Each result contains:
        # - content: summary or full document (depending on retriever config)
        # - metadata: document-level metadata (includes summary when full content is returned)
        results: list[dict[str, Any]] = await BaseRag.query_retriever(retriever, query)

        # If full documents are requested:
        # - Persist the full document text in sly_data (keyed by Entry ID)
        # - Return only metadata (with summaries) to the agent to reduce token usage
        if get_full_document:
            arxiv_contents: dict[str, str] = sly_data.get("arxiv_contents") or {}
            metadata_list: list[dict[str, str]] = []
            for result in results:
                entry_id: str = result.get("metadata", {}).get("Entry ID")
                content: str = result.get("content")
                arxiv_contents.update({entry_id: content})
                metadata_list.append(result.get("metadata", {}))
            # Store full document content outside chat history
            sly_data["arxiv_contents"] = arxiv_contents
            # Return metadata (which includes the summary)
            return metadata_list

        # Default behavior:
        # Return metadata with summarized content directly to the agent
        return results
