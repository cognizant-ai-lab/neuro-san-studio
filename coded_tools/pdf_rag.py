"""Tool module for doing RAG from a pdf file"""

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
import os
from typing import Any
from typing import Dict
from typing import List

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore
from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.base_rag import BaseRag
from coded_tools.base_rag import PostgresConfig

INVALID_PATH_PATTERN = r"[<>:\"|?*\x00-\x1F]"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PdfRag(CodedTool, BaseRag):
    """
    CodedTool implementation which provides a way to do RAG on pdf files
    """

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        Load a PDF from URL, build a vector store, and run a query against it.

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
        urls: List[str] = args.get("urls", [])

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

    async def load_documents(self, loader_args: Dict[str, Any]) -> List[Document]:
        """
        Load PDF documents from URLs.

        :param loader_args: Dictionary containing 'urls' (list of PDF file URLs)
        :return: List of loaded PDF documents
        """
        docs: List[Document] = []
        urls: List[str] = loader_args.get("urls", [])

        for url in urls:
            try:
                loader = PyMuPDFLoader(file_path=url)
                doc: List[Document] = await loader.aload()
                docs.extend(doc)
                logger.info("Successfully loaded PDF file from %s", url)
            except FileNotFoundError:
                logger.error("File not found: %s", url)
            except ValueError as e:
                logger.error("Invalid file path or unsupported input: %s – %s", url, e)

        return docs
