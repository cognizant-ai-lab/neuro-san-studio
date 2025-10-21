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

from typing import Any
from typing import Dict
from typing import List

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import InMemoryVectorStore
from langchain_core.documents import Document
from langchain_core.vectorstores.base import VectorStoreRetriever
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from neuro_san.interfaces.coded_tool import CodedTool

PDF_FILE_URL = "https://www.replicon.com/wp-content/uploads/2016/06/RFP-Template_Replicon.pdf"


class Rag(CodedTool):
    """
    CodedTool implementation which provides a way to do RAG on a pdf file
    """

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]):
        """
        :param args: An argument dictionary whose keys are the parameters
            to the coded tool and whose values are the values passed for
            them by the calling agent.  This dictionary is to be treated as
            read-only.

        :param sly_data: A dictionary whose keys are defined by the agent
            hierarchy, but whose values are meant to be kept out of the
            chat stream.

            This dictionary is largely to be treated as read-only.
            It is possible to add key/value pairs to this dict that do not
            yet exist as a bulletin board, as long as the responsibility
            for which coded_tool publishes new entries is well understood
            by the agent chain implementation and the coded_tool
            implementation adding the data is not invoke()-ed more than
            once.
        """

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        Load a PDF from URL, build a vector store, and run a query against it.

        :param args: Dictionary containing 'query' (search string)
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

        # Validate presence of required inputs
        if not query:
            return "Error: No query provided."

        # Build the vector store and run the query
        vectorstore: InMemoryVectorStore = await self.generate_vector_store(PDF_FILE_URL)
        return await self.query_vectorstore(vectorstore, query)

    async def generate_vector_store(self, url: str) -> InMemoryVectorStore:
        """
        Asynchronously loads web documents from given URLs, split them into
        chunks, and build an in-memory vector store using OpenAI embeddings.

        :param urls: List of URLs to fetch and embed
        :return: In-memory vector store containing the embedded document chunks
        """

        loader = PyPDFLoader(file_path=url)
        docs: List[Document] = await loader.aload()

        # Split documents into smaller chunks for better embedding and
        # retrieval
        text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(chunk_size=100, chunk_overlap=50)
        doc_chunks: List[Document] = text_splitter.split_documents(docs)

        # Create an in-memory vector store with embeddings
        vectorstore: InMemoryVectorStore = await InMemoryVectorStore.afrom_documents(
            documents=doc_chunks,
            collection_name="rag-in-memory",
            embedding=OpenAIEmbeddings(),
        )

        return vectorstore

    async def query_vectorstore(self, vectorstore: InMemoryVectorStore, query: str) -> str:
        """
        Query the given vector store using the provided query string
        and return the combined content of retrieved documents.

        :param vectorstore: The in-memory vector store to query
        :param query: The user query to search for relevant documents
        :return: Concatenated text content of the retrieved documents
        """
        # Create a retriever interface from the vector store
        retriever: VectorStoreRetriever = vectorstore.as_retriever()

        # Perform an asynchronous similarity search
        results: List[Document] = await retriever.ainvoke(query)

        # Concatenate the content of all retrieved documents
        return "\n\n".join(doc.page_content for doc in results)
