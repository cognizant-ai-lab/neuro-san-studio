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

import asyncio
import logging
import os
import re
from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from typing import Any
from typing import List
from typing import Literal
from typing import Optional

# pylint: disable=import-error
from asyncpg import InvalidCatalogNameError
from asyncpg import InvalidPasswordError
from langchain_community.vectorstores import InMemoryVectorStore
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore
from langchain_core.vectorstores.base import VectorStoreRetriever
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGEngine
from langchain_postgres import PGVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy.exc import ProgrammingError

# Invalid file path character pattern
INVALID_PATH_PATTERN = r"[<>:\"|?*\x00-\x1F]"
DEFAULT_TABLE_NAME = "vectorstore"
EMBEDDINGS_MODEL = "text-embedding-3-small"
VECTOR_SIZE = 1536

logger = logging.getLogger(__name__)


@dataclass
class PostgresConfig:
    """Configuration for PostgreSQL connection."""

    user: str
    password: str
    host: str
    port: str
    database: str
    table_name: str

    @property
    def connection_string(self) -> str:
        """Generate PostgreSQL connection string."""

        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class BaseRag(ABC):
    """
    Abstract Base Class for different types of RAG implementations.
    """

    def __init__(self):
        # Save the generated vector store as a JSON file if True
        self.save_vector_store: bool = False
        self.abs_vector_store_path: Optional[str] = None
        self.embeddings: Embeddings = OpenAIEmbeddings(model=EMBEDDINGS_MODEL, dimensions=VECTOR_SIZE)

    @abstractmethod
    async def load_documents(self, loader_args: Any) -> List[Document]:
        """
        Abstract method to load documents from a specific data source.
        """
        raise NotImplementedError

    def configure_vector_store_path(self, vector_store_path: Optional[str]):
        """
        Validate the vector store file path and set it as an absolute path.

        :param vector_store_path: Relative or absolute path to the vector store JSON file.
        :raises ValueError: If the path contains invalid characters or has an incorrect file extension.
        """
        if not vector_store_path:
            return

        # Check for obviously invalid characters in filenames (basic check)
        if re.search(INVALID_PATH_PATTERN, vector_store_path):
            logger.error("Invalid characters in vector_store_path: '%s'\n", vector_store_path)
            raise ValueError(f"Invalid vector_store_path: '{vector_store_path}'")

        # Check file extension
        if not vector_store_path.endswith(".json"):
            logger.error("vector_store_path must be a .json file, got: '%s'\n", vector_store_path)
            raise ValueError(f"vector_store_path must be a .json file, got: '{vector_store_path}'")

        if os.path.isabs(vector_store_path):
            # It's already an absolute path — use it directly
            self.abs_vector_store_path = vector_store_path
        else:
            # Combine to relative path to base path to make absolute path
            base_path: str = os.path.dirname(__file__)
            self.abs_vector_store_path = os.path.abspath(os.path.join(base_path, vector_store_path))

    async def generate_vector_store(
        self,
        loader_args: Any,
        postgres_config: Optional[PostgresConfig] = None,
        vector_store_type: Literal["in_memory", "postgres"] = "in_memory",
    ) -> Optional[VectorStore]:
        """
        Asynchronously loads documents from a given data source, splits them into
        chunks, and builds a vector store using OpenAI embeddings.

        :param loader_args: Arguments specific to the document loader
        :param postgres_config: PostgreSQL configuration (required for postgres vector store)
        :param vector_store_type: Type of vector store to create
        :return: Vector store containing the embedded document chunks
        """

        # If vector store type is unsupported, fallback to in-memory vector store
        if vector_store_type not in {"in_memory", "postgres"}:
            logger.warning(
                "Received %s as 'vector_store_typ'. Available types are 'in_memory' and 'postgres'\n",
                vector_store_type,
            )
            vector_store_type = "in_memory"

        # Validate postgres config if needed
        if vector_store_type == "postgres" and postgres_config is None:
            raise ValueError("postgres_config is required when vector_store_type is 'postgres'\n")

        # Try to load existing vector store for in-memory vector store
        if vector_store_type == "in_memory":
            existing_store = await self._load_existing_vector_store()
            if existing_store:
                return existing_store

        # Load and process documents
        vectorstore = await self._create_new_vector_store(loader_args, postgres_config, vector_store_type)

        # Save vector store if configured
        await self._save_vector_store(vectorstore, vector_store_type)

        return vectorstore

    async def _load_existing_vector_store(self) -> Optional[VectorStore]:
        """Try to load existing vector store from file."""

        if not self.abs_vector_store_path:
            return None

        try:
            vector_store: VectorStore = InMemoryVectorStore.load(
                path=self.abs_vector_store_path, embedding=self.embeddings
            )
            logger.info("Loaded vector store from: %s\n", self.abs_vector_store_path)
            return vector_store
        except FileNotFoundError:
            logger.info("Vector store not found at: %s. Creating from source.\n", self.abs_vector_store_path)
            return None

    async def _create_new_vector_store(
        self,
        loader_args: Any,
        postgres_config: Optional[PostgresConfig],
        vector_store_type: Literal["in_memory", "postgres"],
    ) -> Optional[VectorStore]:
        """Create a new vector store."""

        if vector_store_type == "in_memory":
            return await self._create_in_memory_vector_store(loader_args)

        return await self._create_postgres_vector_store(loader_args, postgres_config)

    async def _process_documents(self, loader_args: Any) -> List[Document]:
        """Load and split documents"""
        # Load documents and build the vector store
        docs: List[Document] = await self.load_documents(loader_args)

        # Split documents into smaller chunks for better embedding and retrieval
        text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(chunk_size=100, chunk_overlap=50)

        doc_chunks: List[Document] = text_splitter.split_documents(docs)
        logger.info("Processed %d document chunks\n", len(doc_chunks))

        return doc_chunks

    async def _create_in_memory_vector_store(self, loader_args) -> VectorStore:
        """Create an in-memory vector store."""
        doc_chunks: List[Document] = await self._process_documents(loader_args)
        logger.info("Creating in-memory vector store.")
        return await InMemoryVectorStore.afrom_documents(
            documents=doc_chunks,
            embedding=self.embeddings,
        )

    async def _create_postgres_vector_store(
        self, loader_args: Any, postgres_config: PostgresConfig
    ) -> Optional[VectorStore]:
        """Create a PostgreSQL vector store."""

        # Create engine and table
        pg_engine = PGEngine.from_connection_string(url=postgres_config.connection_string)
        table_name: str = postgres_config.table_name or DEFAULT_TABLE_NAME

        logger.info(
            "PostgreSQL connection details:\n"
            + "  Host: %s\n"
            + "  Port: %s\n"
            + "  Database: %s\n"
            + "  Table: %s\n",
            postgres_config.host,
            postgres_config.port,
            postgres_config.database,
            table_name,
        )

        try:
            # Initiaize vector store table
            await pg_engine.ainit_vectorstore_table(
                table_name=table_name,
                vector_size=VECTOR_SIZE,
            )

            doc_chunks: List[Document] = await self._process_documents(loader_args)

            logger.info("Creating postgres vector store from documents.")
            # Create vector store and load documents
            return await PGVectorStore.afrom_documents(
                documents=doc_chunks,
                embedding=self.embeddings,
                engine=pg_engine,
                table_name=table_name,
            )

        except ProgrammingError:
            # Table already exists. Create vector store from it.
            logger.info("Table %s already exists.\n", table_name)
            logger.info("Creating postgres vector store from existing table.\n")
            return await PGVectorStore.create(
                engine=pg_engine,
                table_name=table_name,
                embedding_service=self.embeddings,
            )

        except OSError as os_error:
            # Fail to create vector store due to connection error
            logger.error("Fail to create vector store due to connection error. %s\n", os_error)
            return None

        except InvalidPasswordError as invalid_password_error:
            # Fail to create vector store due to invalid username or password
            logger.error(
                "Fail to create vector store due to invalid username or password. %s\n", invalid_password_error
            )
            return None

        except InvalidCatalogNameError as invalid_catalog_error:
            # Fail to create vector store due to invalid DB name
            logger.error("Fail to create vector store due to invalid DB name. %s\n", invalid_catalog_error)
            return None

    async def _save_vector_store(self, vectorstore: VectorStore, vector_store_type: Literal["in_memory", "postgres"]):
        """Save vector store to file if configured."""
        should_save: bool = self.save_vector_store and self.abs_vector_store_path and vector_store_type == "in_memory"

        if not should_save:
            return None

        try:
            os.makedirs(os.path.dirname(self.abs_vector_store_path), exist_ok=True)
            vectorstore.dump(path=self.abs_vector_store_path)
            logger.info("Vector store saved to: %s\n", self.abs_vector_store_path)
        except OSError as os_error:
            logger.error("Failed to save vector store to %s: %s\n", self.abs_vector_store_path, os_error)

    async def query_vectorstore(self, vectorstore: VectorStore, query: str) -> str:
        """
        Query the given vector store using the provided query string
        and return the combined content of retrieved documents.

        :param vectorstore: The in-memory vector store to query
        :param query: The user query to search for relevant documents
        :return: Concatenated text content of the retrieved documents
        """
        try:
            # Create a retriever interface from the vector store
            retriever: VectorStoreRetriever = vectorstore.as_retriever()

            return await self.query_retriever(retriever, query)

        except AttributeError:
            return "Failed to create vector store. Please check the log for more information.\n"

    @staticmethod
    async def query_retriever(retriever: Any, query: str) -> str:
        """
        Query the retriever with the given query string and return the results.

        :param retriever: The retriever interface to query
        :param query: The user query to search for relevant documents
        :return: Concatenated text content of the retrieved documents
        """
        try:
            # Perform an asynchronous similarity search
            results: List[Document] = await retriever.ainvoke(query)

            if results:
                logger.info("Retrieval completed!\n")

            # Concatenate the content of all retrieved documents
            return "\n\n".join(doc.page_content for doc in results)

        except asyncio.TimeoutError as e:
            return f"Timed out while querying retriever: {e}"
