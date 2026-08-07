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

"""Tool module for doing RAG from Confluence pages."""

import asyncio
import logging
import os
from io import BytesIO
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List

from bs4 import BeautifulSoup
from langchain_core.documents import Document
from neuro_san.interfaces.coded_tool import CodedTool
from requests.exceptions import HTTPError

from neuro_san_studio.coded_tools.base_rag import BaseRag

INVALID_PATH_PATTERN = r"[<>:\"|?*\x00-\x1F]"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PAGE_EXPANSIONS = "body.storage,version"
DEFAULT_PAGE_LIMIT = 50
DEFAULT_MAX_PAGES = 1000


class ConfluenceRag(CodedTool, BaseRag):
    """
    CodedTool implementation which provides a way to do RAG on confluence pages
    """

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        Load confluence pages from URLs, build a vector store, and run a query against it.

        :param args: Dictionary containing:
          "query": search string

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

        loader_args = {
            name: args[name]
            for name in (
                "url",
                "username",
                "api_key",
                "cloud",
                "space_key",
                "page_ids",
                "include_attachments",
                "limit",
                "max_pages",
                "ocr_languages",
            )
            if name in args
        }

        # Check the env var for "username" and "api_key"
        loader_args.setdefault("username", os.getenv("JIRA_USERNAME"))
        loader_args.setdefault("api_key", os.getenv("JIRA_API_TOKEN"))

        # Validate presence of required inputs
        if not query:
            logger.error("Missing required input: 'query'")
            return "❌ Missing required input: 'query'."
        if not loader_args.get("url"):
            logger.error("Missing required input: 'url'")
            return "❌ Missing required input: 'url'.\nThis should look like: https://your-domain.atlassian.net/wiki/"
        if not loader_args.get("space_key") and not loader_args.get("page_ids"):
            logger.error("Missing both 'space_key' and 'page_ids'")
            return (
                "❌ Missing both 'space_key' and 'page_ids'.\n"
                "Provide at least one to locate the Confluence content to load.\n"
                "- 'space_key' is the identifier of the Confluence space (e.g., 'DAI').\n"
                "- 'page_ids' should be a list of page IDs you want to load, e.g., ['123456', '7891011'].\n\n"
                "Tip: You can find these values in a page URL like:\n"
                "https://your-domain.atlassian.net/wiki/spaces/<space_key>/pages/<page_id>/<title>"
            )

        # Save the generated vector store as a JSON file if True
        self.save_vector_store = args.get("save_vector_store", False)

        # Configure the vector store path
        self.configure_vector_store_path(args.get("vector_store_path"))

        # Prepare the vector store
        vectorstore = await self.generate_vector_store(loader_args=loader_args)

        # Run the query against the vector store
        return await self.query_vectorstore(vectorstore, query)

    async def load_documents(self, loader_args: Dict[str, Any]) -> List[Document]:
        """
        Load Confluence pages from the provided loader arguments.

        :param loader_args: Dictionary containing 'url', 'space_key', and/or 'page_ids' of the Confluence pages to load
        :return: List of loaded Confluence pages
        """
        url = loader_args.get("url")
        # pylint: disable=import-outside-toplevel,import-error
        from atlassian.errors import ApiPermissionError

        try:
            docs = await asyncio.to_thread(self._load_documents_sync, loader_args)
            logger.info("Successfully loaded Confluence pages from %s", url)
        except HTTPError as http_error:
            logger.error("HTTP error while loading from %s: %s", url, http_error)
            return []
        except ApiPermissionError as api_error:
            logger.error("API Permission error while loading from %s: %s", url, api_error)
            return []

        return docs

    def _load_documents_sync(self, loader_args: Dict[str, Any]) -> List[Document]:
        """Load and convert Confluence pages using the synchronous Atlassian client."""
        # pylint: disable=import-outside-toplevel,import-error
        from atlassian import Confluence

        url = loader_args["url"]
        confluence = Confluence(
            url=url,
            username=loader_args.get("username"),
            password=loader_args.get("api_key"),
            cloud=loader_args.get("cloud", True),
        )
        pages = self._get_pages(confluence, loader_args)
        include_attachments = loader_args.get("include_attachments", False)
        ocr_languages = loader_args.get("ocr_languages")

        return [self._page_to_document(confluence, url, page, include_attachments, ocr_languages) for page in pages]

    @staticmethod
    def _get_pages(confluence: Any, loader_args: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch configured pages, preserving order and removing duplicates."""
        pages: List[Dict[str, Any]] = []
        seen_page_ids = set()

        space_key = loader_args.get("space_key")
        if space_key:
            limit = loader_args.get("limit", DEFAULT_PAGE_LIMIT)
            max_pages = loader_args.get("max_pages", DEFAULT_MAX_PAGES)
            start = 0
            while len(pages) < max_pages:
                batch = confluence.get_all_pages_from_space(
                    space=space_key,
                    start=start,
                    limit=min(limit, max_pages - len(pages)),
                    status="current",
                    expand=PAGE_EXPANSIONS,
                )
                if not batch:
                    break
                for page in batch:
                    page_id = str(page["id"])
                    if page_id not in seen_page_ids:
                        seen_page_ids.add(page_id)
                        pages.append(page)
                if len(batch) < limit:
                    break
                start += len(batch)

        for page_id in loader_args.get("page_ids") or []:
            page_id = str(page_id)
            if page_id in seen_page_ids:
                continue
            page = confluence.get_page_by_id(page_id=page_id, expand=PAGE_EXPANSIONS)
            if page:
                seen_page_ids.add(page_id)
                pages.append(page)

        return pages

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def _page_to_document(
        self,
        confluence: Any,
        base_url: str,
        page: Dict[str, Any],
        include_attachments: bool,
        ocr_languages: str | None,
    ) -> Document:
        """Convert one Confluence API page into a LangChain document."""
        html = page.get("body", {}).get("storage", {}).get("value", "")
        text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        if include_attachments:
            text += "".join(self._load_attachment_texts(confluence, base_url, str(page["id"]), ocr_languages))

        metadata = {
            "title": page["title"],
            "id": str(page["id"]),
            "source": base_url.rstrip("/") + page.get("_links", {}).get("webui", ""),
        }
        updated_at = page.get("version", {}).get("when")
        if updated_at:
            metadata["when"] = updated_at
        return Document(page_content=text, metadata=metadata)

    def _load_attachment_texts(
        self, confluence: Any, base_url: str, page_id: str, ocr_languages: str | None
    ) -> List[str]:
        """Download and extract text from supported page attachments."""
        attachments = confluence.get_attachments_from_content(page_id).get("results", [])
        texts = []
        for attachment in attachments:
            media_type = attachment.get("metadata", {}).get("mediaType", "")
            title = attachment.get("title", "")
            download_path = attachment.get("_links", {}).get("download")
            if not download_path:
                continue
            download_url = base_url.rstrip("/") + download_path
            try:
                response = confluence.request(path=download_url, absolute=True)
                response.raise_for_status()
            except HTTPError as http_error:
                if http_error.response is not None and http_error.response.status_code == 404:
                    logger.warning("Attachment not found at %s", download_url)
                    continue
                raise

            extracted_text = self._extract_attachment_text(response.content, title, media_type, ocr_languages)
            if extracted_text:
                texts.append(f"\n{title}\n{extracted_text}")
        return texts

    @staticmethod
    def _extract_attachment_text(content: bytes, title: str, media_type: str, ocr_languages: str | None) -> str:
        """Extract text from an attachment according to its media type."""
        # Attachment processors are optional dependencies and are imported only when needed.
        # pylint: disable=import-outside-toplevel,import-error
        suffix = Path(title).suffix.lower()
        if media_type == "application/pdf" or suffix == ".pdf":
            from pypdf import PdfReader

            return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(content)).pages)
        if media_type in {"image/png", "image/jpeg", "image/jpg"} or suffix in {".png", ".jpg", ".jpeg"}:
            import pytesseract
            from PIL import Image

            return pytesseract.image_to_string(Image.open(BytesIO(content)), lang=ocr_languages)
        if media_type == "image/svg+xml" or suffix == ".svg":
            import pytesseract
            from PIL import Image
            from reportlab.graphics import renderPM
            from svglib.svglib import svg2rlg

            image_bytes = BytesIO()
            renderPM.drawToFile(svg2rlg(BytesIO(content)), image_bytes, fmt="PNG")
            image_bytes.seek(0)
            return pytesseract.image_to_string(Image.open(image_bytes), lang=ocr_languages)
        if suffix == ".docx":
            import docx2txt

            return docx2txt.process(BytesIO(content))
        if suffix in {".xls", ".xlsx"}:
            import pandas

            sheets = pandas.read_excel(BytesIO(content), sheet_name=None, header=None)
            return "\n\n".join(
                f"{name}:\n{sheet.to_string(index=False, header=False)}" for name, sheet in sheets.items()
            )

        logger.info("Skipping unsupported Confluence attachment type %s (%s)", media_type, title)
        return ""
