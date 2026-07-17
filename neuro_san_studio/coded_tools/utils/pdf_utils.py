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


class PdfUtils:  # pylint: disable=too-few-public-methods
    """Shared helpers for extracting text from PDF documents."""

    @staticmethod
    def parse_pdf_bytes(data: bytes) -> str:
        """Extract text from in-memory PDF bytes, joining pages with newlines."""
        reader = PdfReader(BytesIO(data))
        page_texts: list[str] = []
        for page in reader.pages:
            # extract_text() is typed Optional[str] in newer pypdf and can return
            # None for pages without extractable text (e.g. scanned images);
            # coerce to "" so the join never fails on a valid PDF.
            page_texts.append(page.extract_text() or "")
        return "\n".join(page_texts)
