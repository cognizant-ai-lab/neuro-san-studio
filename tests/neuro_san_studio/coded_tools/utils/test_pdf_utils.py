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

"""Tests for PdfUtils.parse_pdf_bytes and PdfUtils.has_pdf_header."""

from io import BytesIO
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from pypdf import PdfWriter
from pypdf.errors import PdfReadError

from neuro_san_studio.coded_tools.utils.pdf_utils import PDF_HEADER_WINDOW
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

    @staticmethod
    def _minimal_pdf() -> bytes:
        """
        Build the smallest well-formed PDF pypdf will open: one blank page, no fonts.

        Unlike _build_pdf this needs no reportlab, so tests using it run in CI, where
        reportlab is not installed; pypdf is already a hard dependency of the repo.

        :return: The complete PDF file bytes.
        """
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        buf = BytesIO()
        writer.write(buf)
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
    def test_per_page_returns_list_in_page_order(self, mock_reader_cls):
        """parse_pdf_bytes_per_page returns one string per page, in page order."""
        mock_reader_cls.return_value = self._reader_with([self._make_page("Page 1"), self._make_page("Page 2")])
        assert PdfUtils.parse_pdf_bytes_per_page(b"fake") == ["Page 1", "Page 2"]

    @patch(f"{MODULE}.PdfReader")
    def test_per_page_none_coerced_to_empty_string(self, mock_reader_cls):
        """A page with no extractable text yields "" in the per-page list, never None."""
        mock_reader_cls.return_value = self._reader_with([self._make_page("A"), self._make_page(None)])
        assert PdfUtils.parse_pdf_bytes_per_page(b"fake") == ["A", ""]

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

    # --- has_pdf_header --------------------------------------------------- #
    @pytest.mark.parametrize(
        "head, expected",
        [
            # The common case: the file starts with the marker.
            pytest.param(b"%PDF-1.7 fake body", True, id="header_at_offset_zero"),
            # Junk before the marker is tolerated, as pypdf and Adobe's notes allow (first 1024 bytes).
            pytest.param(b"j" * 500 + b"%PDF-1.4 body", True, id="leading_junk_within_window"),
            # A marker first appearing at offset PDF_HEADER_WINDOW is outside the sniffed window.
            pytest.param(b"j" * PDF_HEADER_WINDOW + b"%PDF-1.4 body", False, id="marker_at_window_boundary"),
            pytest.param(b"j" * (PDF_HEADER_WINDOW + 300) + b"%PDF-1.4 body", False, id="marker_past_window"),
            # The marker's last byte is the window's last byte: still fully inside, so True.
            pytest.param(
                b"j" * (PDF_HEADER_WINDOW - 5) + b"%PDF-1.4 body", True, id="marker_ends_exactly_at_window_end"
            ),
            # Only "%PD" falls inside the window, so the full marker is not present.
            pytest.param(b"j" * (PDF_HEADER_WINDOW - 3) + b"%PDF-1.4 body", False, id="marker_straddles_boundary"),
            pytest.param(b"", False, id="empty_bytes"),
            # A /dev/zero-style NUL stream.
            pytest.param(b"\x00" * PDF_HEADER_WINDOW, False, id="nul_bytes"),
            # An HTML error page saved with a .pdf name.
            pytest.param(b"<html><body><h1>404 Not Found</h1></body></html>", False, id="html_page"),
        ],
    )
    def test_has_pdf_header(self, head: bytes, expected: bool) -> None:
        """
        The sniff accepts %PDF- anywhere in the first PDF_HEADER_WINDOW bytes and nothing else.

        :param head: The leading bytes handed to the sniff.
        :param expected: Whether the sniff must report a PDF header for those bytes.
        """
        assert PdfUtils.has_pdf_header(head) is expected

    def test_has_pdf_header_true_for_real_pdf(self) -> None:
        """A genuine PDF that real pypdf opens also passes the header sniff.

        Uses the hand-built minimal PDF rather than reportlab so this runs in CI; the
        pypdf parse first proves the fixture is a real PDF, not just header-shaped bytes.
        """
        data: bytes = self._minimal_pdf()
        assert len(PdfUtils.parse_pdf_bytes_per_page(data)) == 1
        assert PdfUtils.has_pdf_header(data) is True
        # The sniff only needs the leading window, which is all the local reader hands it.
        assert PdfUtils.has_pdf_header(data[:PDF_HEADER_WINDOW]) is True
