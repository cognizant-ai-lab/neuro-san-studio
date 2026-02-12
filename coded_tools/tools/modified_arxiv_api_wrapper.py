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

import os
from logging import getLogger
from typing import Any
from typing import Iterator

# pylint: disable=import-error
from arxiv import SortCriterion
from arxiv import SortOrder
from langchain_community.utilities.arxiv import ArxivAPIWrapper
from langchain_core.documents import Document

logger = getLogger(__name__)


class ModifiedArxivAPIWrapper(ArxivAPIWrapper):
    """
    Override ArxivAPIWrapper.lazy_load() to not remove ":" and "-".
    This is needed for search queries like au: "Firstname Lastname".
    User can still ask questions normally since the template is handled by LLM

    - Add `sort_by` and `sort_order` attribute
    - Move `Entry ID` to main metadata when `get_full_documents` is True

    From
    https://github.com/langchain-ai/langchain-community/blob/main/libs/community/langchain_community/utilities/arxiv.py
    """

    sort_by: str = "relevance"
    sort_order: str = "descending"

    def _get_sort_criterion(self) -> SortCriterion:
        """Convert string sort_by to SortCriterion enum."""
        mapping = {
            "relevance": SortCriterion.Relevance,
            "lastUpdatedDate": SortCriterion.LastUpdatedDate,
            "submittedDate": SortCriterion.SubmittedDate,
        }
        return mapping.get(self.sort_by, SortCriterion.Relevance)

    def _get_sort_order(self) -> SortOrder:
        """Convert string sort_order to SortOrder enum."""
        mapping = {"ascending": SortOrder.Ascending, "descending": SortOrder.Descending}
        return mapping.get(self.sort_order, SortOrder.Descending)

    def _fetch_results(self, query: str) -> Any:
        """Helper function to fetch arxiv results based on query."""
        sort_criterion = self._get_sort_criterion()
        sort_order_enum = self._get_sort_order()

        if self.is_arxiv_identifier(query):
            return self.arxiv_search(
                id_list=query.split(),
                max_results=self.top_k_results,
                sort_by=sort_criterion,
                sort_order=sort_order_enum,
            ).results()
        return self.arxiv_search(
            query[: self.ARXIV_MAX_QUERY_LENGTH],
            max_results=self.top_k_results,
            sort_by=sort_criterion,
            sort_order=sort_order_enum,
        ).results()

    def lazy_load(self, query: str) -> Iterator[Document]:
        """
        Run Arxiv search and get the article texts plus the article meta information.
        See https://lukasschwab.me/arxiv.py/index.html#Search

        Returns: documents with the document.page_content in text format

        Performs an arxiv search, downloads the top k results as PDFs, loads
        them as Documents, and returns them.

        :param query: a plaintext search query
        """
        try:
            # pylint: disable=import-outside-toplevel
            import fitz
        except ImportError as import_error:
            raise ImportError(
                "PyMuPDF package not found, please install it with `pip install pymupdf`"
            ) from import_error

        try:
            results = self._fetch_results(query)  # Using helper function to fetch results
        except self.arxiv_exceptions as ex:
            logger.debug("Error on arxiv: %s", ex)
            return

        for result in results:
            try:
                doc_file_name: str = result.download_pdf()
                with fitz.open(doc_file_name) as doc_file:
                    text: str = "".join(page.get_text() for page in doc_file)
            except (FileNotFoundError, fitz.fitz.FileDataError) as f_ex:
                logger.debug(f_ex)
                continue
            except Exception as e:
                if self.continue_on_failure:
                    logger.error(e)
                    continue
                raise e
            if self.load_all_available_meta:
                extra_metadata = {
                    "published_first_time": str(result.published.date()),
                    "comment": result.comment,
                    "journal_ref": result.journal_ref,
                    "doi": result.doi,
                    "primary_category": result.primary_category,
                    "categories": result.categories,
                    "links": [link.href for link in result.links],
                }
            else:
                extra_metadata = {}
            metadata = {
                "Entry ID": result.entry_id,
                "Published": str(result.updated.date()),
                "Title": result.title,
                "Authors": ", ".join(a.name for a in result.authors),
                "Summary": result.summary,
                **extra_metadata,
            }
            yield Document(page_content=text[: self.doc_content_chars_max], metadata=metadata)
            os.remove(doc_file_name)
