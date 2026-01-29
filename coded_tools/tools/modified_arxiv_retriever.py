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

from typing import List

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from coded_tools.tools.modified_arxiv_api_wrapper import ModifiedArxivAPIWrapper


class ModifiedArxivRetriever(BaseRetriever, ModifiedArxivAPIWrapper):
    """
    Extend ModifiedArxivAPIWrapper instead of ArxivAPIWrapper.
    This is needed for search queries like au: "Firstname Lastname".
    User can still ask questions normally since the template is handled by LLM

    From
    https://github.com/langchain-ai/langchain-community/blob/main/libs/community/langchain_community/retrievers/arxiv.py
    """

    get_full_documents: bool = False

    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun) -> List[Document]:
        if self.get_full_documents:
            return self.load(query=query)

        return self.get_summaries_as_docs(query)
