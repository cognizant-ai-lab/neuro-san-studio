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

"""Tests for PdfUtils.parse_pdf_bytes."""

from io import BytesIO
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from pypdf.errors import PdfReadError

from neuro_san_studio.coded_tools.utils.pdf_utils import PdfUtils

# Patch the name in the module under test, not "pypdf.PdfReader".
MODULE = "neuro_san_studio.coded_tools.utils.pdf_utils"


class TestPdfUtils:
    """Unit and end-to-end tests for PdfUtils.parse_pdf_bytes.

    Mocked tests patch PdfReader to pin the method's own logic (page joining,
    None coercion, stream wiring) without real PDF parsing. The real tests build
    actual PDFs with reportlab and exercise the full pypdf path; they skip
    automatically when reportlab is not installed.
    """

    # --- helpers ---------------------------------------------------------- #
    @staticmethod
    def _make_page(text):
        """Return a stand-in page whose extract_text() yields `text` (may be None)."""
        page = MagicMock(name="page")
        page.extract_text.return_value = text
        return page

    @staticmethod
    def _reader_with(pages):
        """Return a stand-in PdfReader instance exposing the given `pages`."""
        reader = MagicMock(name="PdfReader instance")
        reader.pages = pages
        return reader

    @staticmethod
    def _build_pdf(pages_text):
        """Build a real PDF from text, one page per string. Requires reportlab."""
        canvas = pytest.importorskip("reportlab.pdfgen.canvas")
        buf = BytesIO()
        c = canvas.Canvas(buf)
        for text in pages_text:
            c.drawString(72, 720, text)
            c.showPage()
        c.save()
        return buf.getvalue()

    # --- mocked unit tests ------------------------------------------------ #
    @patch(f"{MODULE}.PdfReader")
    def test_single_page(self, mock_reader_cls):
        """A one-page PDF returns that page's text verbatim."""
        mock_reader_cls.return_value = self._reader_with([self._make_page("Hello, world!")])
        assert PdfUtils.parse_pdf_bytes(b"fake") == "Hello, world!"

    @patch(f"{MODULE}.PdfReader")
    def test_multiple_pages_joined_with_newline(self, mock_reader_cls):
        """Multiple pages are concatenated in order, separated by a single newline."""
        mock_reader_cls.return_value = self._reader_with(
            [self._make_page("Page 1"), self._make_page("Page 2"), self._make_page("Page 3")]
        )
        assert PdfUtils.parse_pdf_bytes(b"fake") == "Page 1\nPage 2\nPage 3"

    @patch(f"{MODULE}.PdfReader")
    def test_page_returning_none_coerced_to_empty(self, mock_reader_cls):
        """A page with no extractable text (extract_text() -> None) becomes ""."""
        mock_reader_cls.return_value = self._reader_with([self._make_page(None)])
        assert PdfUtils.parse_pdf_bytes(b"fake") == ""

    @patch(f"{MODULE}.PdfReader")
    def test_mixed_text_and_none(self, mock_reader_cls):
        """A None page (e.g. a scanned image) coerces to "" while separators stay intact."""
        mock_reader_cls.return_value = self._reader_with(
            [self._make_page("Alpha"), self._make_page(None), self._make_page("Beta")]
        )
        assert PdfUtils.parse_pdf_bytes(b"fake") == "Alpha\n\nBeta"

    @patch(f"{MODULE}.PdfReader")
    def test_empty_string_page_preserved(self, mock_reader_cls):
        """An empty-string page still contributes a join separator."""
        mock_reader_cls.return_value = self._reader_with([self._make_page(""), self._make_page("x")])
        assert PdfUtils.parse_pdf_bytes(b"fake") == "\nx"

    @patch(f"{MODULE}.PdfReader")
    def test_no_pages_returns_empty_string(self, mock_reader_cls):
        """A PDF with zero pages yields an empty string rather than raising."""
        mock_reader_cls.return_value = self._reader_with([])
        assert PdfUtils.parse_pdf_bytes(b"fake") == ""

    @patch(f"{MODULE}.PdfReader")
    def test_input_is_wrapped_in_bytesio(self, mock_reader_cls):
        """The raw bytes are wrapped in a BytesIO and forwarded to PdfReader unchanged."""
        mock_reader_cls.return_value = self._reader_with([self._make_page("x")])
        data = b"%PDF-1.4 raw bytes"

        PdfUtils.parse_pdf_bytes(data)

        mock_reader_cls.assert_called_once()
        (stream,), _kwargs = mock_reader_cls.call_args
        assert isinstance(stream, BytesIO)
        assert stream.getvalue() == data

    @patch(f"{MODULE}.PdfReader")
    def test_reader_construction_errors_propagate(self, mock_reader_cls):
        """Errors from PdfReader bubble up, since the method does no error handling."""
        mock_reader_cls.side_effect = ValueError("bad pdf")
        with pytest.raises(ValueError, match="bad pdf"):
            PdfUtils.parse_pdf_bytes(b"nope")

    # --- real end-to-end tests (skip if reportlab missing) ---------------- #
    def test_real_single_page(self):
        """A genuine single-page PDF parsed through real pypdf contains its text."""
        data = self._build_pdf(["Hello from a real PDF"])
        assert "Hello from a real PDF" in PdfUtils.parse_pdf_bytes(data)

    def test_real_multi_page_separated_by_newline(self):
        """A genuine multi-page PDF places each page's text on its own line."""
        data = self._build_pdf(["First page text", "Second page text"])
        result = PdfUtils.parse_pdf_bytes(data)
        first_line, _, rest = result.partition("\n")
        assert "First page text" in first_line
        assert "Second page text" in rest

    def test_invalid_bytes_raise(self):
        """Non-PDF bytes cause real pypdf to raise rather than return silently."""

        with pytest.raises((PdfReadError, Exception)):
            PdfUtils.parse_pdf_bytes(b"this is definitely not a pdf")
