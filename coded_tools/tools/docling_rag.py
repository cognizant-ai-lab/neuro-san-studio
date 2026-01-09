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
import os
from typing import Any

from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore

# pylint: disable=import-error
from langchain_docling import DoclingLoader
from neuro_san.interfaces.coded_tool import CodedTool
from requests.exceptions import HTTPError

from coded_tools.tools.base_rag import BaseRag
from coded_tools.tools.base_rag import PostgresConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DoclingRag(CodedTool, BaseRag):
    """
    CodedTool implementation which provides a way to do RAG on multiple file formats.
    """

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> str:
        """
        Load documents from URL using DoclingLoader, build a vector store, and run a query against it.
        See https://python.langchain.com/docs/integrations/document_loaders/docling/ and
        https://docling-project.github.io/docling/

        :param args: Dictionary containing:
          "query": search string
          "urls": list of pdf files
          "save_vector_store": save to JSON file if True
          "vector_store_path": relative path to this file

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
        urls: list[str] = args.get("urls", [])

        # Validate presence of required inputs
        if not query:
            return "❌ Missing required input: 'query'."
        if not urls:
            return "❌ Missing required input: 'urls'."

        # Vector store type
        vector_store_type: str = args.get("vector_store_type", "in_memory")

        # Save the generated vector store as a JSON file if True
        self.save_vector_store = args.get("save_vector_store", False)

        # Configure the vector store path
        self.configure_vector_store_path(args.get("vector_store_path"))

        # For PostgreSQL vector store
        if vector_store_type == "postgres":
            postgres_config = PostgresConfig(
                user=os.getenv("POSTGRES_USER"),
                password=os.getenv("POSTGRES_PASSWORD"),
                host=os.getenv("POSTGRES_HOST"),
                port=os.getenv("POSTGRES_PORT"),
                database=os.getenv("POSTGRES_DB"),
                table_name=args.get("table_name"),
            )
        else:
            postgres_config = None

        # Prepare the vector store
        vector_store: VectorStore = await self.generate_vector_store(
            loader_args={"urls": urls}, postgres_config=postgres_config, vector_store_type=vector_store_type
        )

        # Run the query against the vector store
        return await self.query_vectorstore(vector_store, query)

    async def load_documents(self, loader_args: dict[str, Any]) -> list[Document]:
        """
        Load documents from URLs.

        :param loader_args: Dictionary containing 'urls' (list of file URLs)
        :return: List of loaded documents
        """
        docs: list[Document] = []
        urls: list[str] = loader_args.get("urls", [])

        loader = DoclingLoader(file_path=urls)
        async for doc in loader.alazy_load():
            try:
                docs.append(doc)
                logger.info("Successfully loaded PDF file from %s", doc.metadata.get("source", "unknown source"))
            except HTTPError as http_e:
                logger.error("HTTP error occurred: %s", http_e)
            except FileNotFoundError as fnf_e:
                logger.error("File not found: %s", fnf_e)
            except ValueError as val_e:
                logger.error("Value error: %s", val_e)

        return docs
