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
from leaf_common.resolution.resolver_util import ResolverUtil
from neuro_san.interfaces.coded_tool import CodedTool
from requests.exceptions import HTTPError

from neuro_san_studio.coded_tools.base_rag import BaseRag
from neuro_san_studio.coded_tools.utils.pdf_utils import PdfUtils

INVALID_PATH_PATTERN = r"[<>:\"|?*\x00-\x1F]"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PAGE_EXPANSIONS = "body.storage,version"
DEFAULT_PAGE_LIMIT = 50
DEFAULT_MAX_PAGES = 1000

CONFLUENCE_TYPE = ResolverUtil.create_type("atlassian.Confluence", raise_if_not_found=False)
API_PERMISSION_ERROR_TYPE = ResolverUtil.create_type("atlassian.errors.ApiPermissionError", raise_if_not_found=False)
API_PERMISSION_ERRORS = (API_PERMISSION_ERROR_TYPE,) if API_PERMISSION_ERROR_TYPE is not None else ()
IMAGE_OPEN = ResolverUtil.create_type("PIL.Image.open", raise_if_not_found=False)
IMAGE_TO_STRING = ResolverUtil.create_type("pytesseract.image_to_string", raise_if_not_found=False)
SVG_TO_DRAWING = ResolverUtil.create_type("svglib.svglib.svg2rlg", raise_if_not_found=False)
DRAW_TO_FILE = ResolverUtil.create_type("reportlab.graphics.renderPM.drawToFile", raise_if_not_found=False)
DOCX_PROCESS = ResolverUtil.create_type("docx2txt.process", raise_if_not_found=False)
READ_EXCEL = ResolverUtil.create_type("pandas.read_excel", raise_if_not_found=False)


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

        try:
            docs = await asyncio.to_thread(self._load_documents_sync, loader_args)
            logger.info("Successfully loaded Confluence pages from %s", url)
        except HTTPError as http_error:
            logger.error("HTTP error while loading from %s: %s", url, http_error)
            return []
        except API_PERMISSION_ERRORS as api_error:
            logger.error("API Permission error while loading from %s: %s", url, api_error)
            return []

        return docs

    def _load_documents_sync(self, loader_args: Dict[str, Any]) -> List[Document]:
        """Load and convert Confluence pages using the synchronous Atlassian client."""
        if CONFLUENCE_TYPE is None:
            logger.error("Confluence support requires the 'atlassian-python-api' package")
            return []

        url = loader_args["url"]
        confluence = CONFLUENCE_TYPE(
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
                    page_id = str(page.get("id", ""))
                    if not page_id:
                        logger.warning("Skipping Confluence page without an id")
                        continue
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
            response_page_id = str(page.get("id", "")) if page else ""
            if response_page_id:
                seen_page_ids.add(response_page_id)
                pages.append(page)
            elif page:
                logger.warning("Skipping Confluence page without an id")

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
        page_id = str(page.get("id", ""))
        html = page.get("body", {}).get("storage", {}).get("value", "")
        text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        if include_attachments and page_id:
            text += "".join(self._load_attachment_texts(confluence, base_url, page_id, ocr_languages))

        metadata = {
            "title": page.get("title", "Untitled"),
            "id": page_id,
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
            content = self._download_attachment(confluence, download_url)
            if content is None:
                continue

            try:
                extracted_text = self._extract_attachment_text(content, title, media_type, ocr_languages)
            except Exception as error:  # pylint: disable=broad-exception-caught
                logger.warning("Failed to extract text from attachment %s: %s", title, error)
                continue
            if extracted_text:
                texts.append(f"\n{title}\n{extracted_text}")
        return texts

    @staticmethod
    def _download_attachment(confluence: Any, download_url: str) -> bytes | None:
        """Download one attachment, returning None when that attachment is unavailable."""
        try:
            response = confluence.request(path=download_url, absolute=True)
            response.raise_for_status()
            return response.content
        except HTTPError as http_error:
            logger.warning("HTTP error while loading attachment from %s: %s", download_url, http_error)
        except API_PERMISSION_ERRORS as api_error:
            logger.warning("Permission error while loading attachment from %s: %s", download_url, api_error)
        return None

    @staticmethod
    def _extract_attachment_text(content: bytes, title: str, media_type: str, ocr_languages: str | None) -> str:
        """Extract text from an attachment according to its media type."""
        suffix = Path(title).suffix.lower()
        if media_type == "application/pdf" or suffix == ".pdf":
            return PdfUtils.parse_pdf_bytes(content)
        if media_type in {"image/png", "image/jpeg", "image/jpg"} or suffix in {".png", ".jpg", ".jpeg"}:
            return ConfluenceRag._extract_image_text(content, ocr_languages)
        if media_type == "image/svg+xml" or suffix == ".svg":
            return ConfluenceRag._extract_svg_text(content, ocr_languages)
        if suffix == ".docx":
            return ConfluenceRag._extract_docx_text(content)
        if suffix in {".xls", ".xlsx"}:
            return ConfluenceRag._extract_excel_text(content)

        logger.info("Skipping unsupported Confluence attachment type %s (%s)", media_type, title)
        return ""

    @staticmethod
    def _extract_image_text(content: bytes, ocr_languages: str | None) -> str:
        """Extract text from a raster image attachment."""
        if IMAGE_OPEN is None or IMAGE_TO_STRING is None:
            logger.error("Image attachments require the 'Pillow' and 'pytesseract' packages and Tesseract")
            return ""
        return IMAGE_TO_STRING(IMAGE_OPEN(BytesIO(content)), lang=ocr_languages)

    @staticmethod
    def _extract_svg_text(content: bytes, ocr_languages: str | None) -> str:
        """Extract text from an SVG attachment."""
        if any(processor is None for processor in (IMAGE_OPEN, IMAGE_TO_STRING, SVG_TO_DRAWING, DRAW_TO_FILE)):
            logger.error(
                "SVG attachments require the 'Pillow', 'pytesseract', 'reportlab', and 'svglib' packages and Tesseract"
            )
            return ""

        image_bytes = BytesIO()
        DRAW_TO_FILE(SVG_TO_DRAWING(BytesIO(content)), image_bytes, fmt="PNG")
        image_bytes.seek(0)
        return IMAGE_TO_STRING(IMAGE_OPEN(image_bytes), lang=ocr_languages)

    @staticmethod
    def _extract_docx_text(content: bytes) -> str:
        """Extract text from a DOCX attachment."""
        if DOCX_PROCESS is None:
            logger.error("DOCX attachments require the 'docx2txt' package")
            return ""
        return DOCX_PROCESS(BytesIO(content))

    @staticmethod
    def _extract_excel_text(content: bytes) -> str:
        """Extract text from an Excel attachment."""
        if READ_EXCEL is None:
            logger.error("Excel attachments require the 'pandas', 'openpyxl', and 'xlrd' packages")
            return ""
        sheets = READ_EXCEL(BytesIO(content), sheet_name=None, header=None)
        return "\n\n".join(f"{name}:\n{sheet.to_string(index=False, header=False)}" for name, sheet in sheets.items())
