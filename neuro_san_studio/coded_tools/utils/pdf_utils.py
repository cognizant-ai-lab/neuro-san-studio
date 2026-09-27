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

from io import BytesIO

from pypdf import PdfReader

# How many leading bytes has_pdf_header inspects for the "%PDF-" marker. Adobe's
# PDF implementation notes allow the header to appear anywhere within the first
# 1024 bytes of the file (not only at offset 0), and pypdf tolerates that leading
# junk (it logs "invalid pdf header" and still parses the document). A strict
# startswith(b"%PDF-") check would therefore reject files pypdf reads fine.
PDF_HEADER_WINDOW: int = 1024


class PdfUtils:
    """Shared helpers for extracting text from PDF documents."""

    @staticmethod
    def has_pdf_header(head: bytes) -> bool:
        """
        Report whether the leading bytes of a file carry a PDF header marker.

        Cheap sanity check meant to run BEFORE a file is read in full or handed to
        pypdf: it lets callers reject an HTML error page saved as report.pdf, a NUL
        stream, or an empty file with a clear message instead of pypdf's
        "Stream has ended unexpectedly". It is not proof of a valid PDF; pypdf
        remains the authority on whether the bytes actually parse.

        :param head: The leading bytes of the candidate file (at least
            PDF_HEADER_WINDOW bytes when the file is that long; extra bytes are ignored).
        :return: True when "%PDF-" occurs within the first PDF_HEADER_WINDOW bytes.
        """
        return b"%PDF-" in head[:PDF_HEADER_WINDOW]

    @staticmethod
    def parse_pdf_bytes(data: bytes) -> str:
        """
        Extract text from in-memory PDF bytes, joining pages with newlines.

        :param data: The raw PDF bytes.
        :return: The extracted text of all pages, separated by newlines.
        """
        return "\n".join(PdfUtils.parse_pdf_bytes_per_page(data))

    @staticmethod
    def parse_pdf_bytes_per_page(data: bytes) -> list[str]:
        """
        Extract text from in-memory PDF bytes, one string per page.

        Callers that need page-level granularity (e.g. RAG loaders that record a
        page number in each Document's metadata) use this directly;
        parse_pdf_bytes is the joined-text convenience built on top of it.

        :param data: The raw PDF bytes.
        :return: The extracted text of each page, in page order.
        """
        reader = PdfReader(BytesIO(data))
        page_texts: list[str] = []
        for page in reader.pages:
            # extract_text() is typed Optional[str] in newer pypdf and can return
            # None for pages without extractable text (e.g. scanned images);
            # coerce to "" so callers never mix None into the page list.
            page_texts.append(page.extract_text() or "")
        return page_texts
