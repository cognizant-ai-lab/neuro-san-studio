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

"""Tests for the Confluence RAG coded tool."""

# pylint: disable=protected-access

import asyncio
from unittest.mock import MagicMock
from unittest.mock import patch

from requests.exceptions import HTTPError

from neuro_san_studio.coded_tools import confluence_rag
from neuro_san_studio.coded_tools.confluence_rag import ConfluenceRag

BASE_URL = "https://your-domain.atlassian.net/wiki"


def _page(page_id: str, title: str = "Page") -> dict:
    """Create a representative Confluence API page."""
    return {
        "id": page_id,
        "title": title,
        "body": {"storage": {"value": "<h1>Heading</h1><p>Page text</p>"}},
        "version": {"when": "2026-08-01T12:00:00Z"},
        "_links": {"webui": f"/spaces/TEST/pages/{page_id}"},
    }


def test_get_pages_paginates_and_deduplicates_explicit_page_ids():
    """Space pages are paginated and duplicate explicit IDs are not fetched twice."""
    confluence = MagicMock()
    confluence.get_all_pages_from_space.side_effect = [[_page("1"), _page("2")], [_page("3")]]
    confluence.get_page_by_id.return_value = _page("4")

    pages = ConfluenceRag._get_pages(
        confluence,
        {"space_key": "TEST", "page_ids": ["2", "4"], "limit": 2, "max_pages": 10},
    )

    assert [page["id"] for page in pages] == ["1", "2", "3", "4"]
    assert confluence.get_all_pages_from_space.call_count == 2
    confluence.get_page_by_id.assert_called_once_with(page_id="4", expand="body.storage,version")


def test_page_to_document_converts_html_and_preserves_metadata():
    """Page content and metadata retain the previous loader's output shape."""
    document = object.__new__(ConfluenceRag)._page_to_document(
        MagicMock(), f"{BASE_URL}/", _page("42", "Runbook"), False, None
    )

    assert document.page_content == "Heading Page text"
    assert document.metadata == {
        "title": "Runbook",
        "id": "42",
        "source": f"{BASE_URL}/spaces/TEST/pages/42",
        "when": "2026-08-01T12:00:00Z",
    }


def test_page_to_document_appends_attachment_text():
    """Attachment text is retained when include_attachments is enabled."""
    tool = object.__new__(ConfluenceRag)
    with patch.object(tool, "_load_attachment_texts", return_value=["\nnotes.pdf\nAttachment text"]):
        document = tool._page_to_document(MagicMock(), BASE_URL, _page("42"), True, None)

    assert document.page_content == "Heading Page text\nnotes.pdf\nAttachment text"


def test_load_attachment_texts_skips_missing_attachment():
    """A missing attachment is logged and skipped without hiding other HTTP failures."""
    confluence = MagicMock()
    confluence.get_attachments_from_content.return_value = {
        "results": [
            {
                "title": "missing.pdf",
                "metadata": {"mediaType": "application/pdf"},
                "_links": {"download": "/download/missing.pdf"},
            }
        ]
    }
    response = MagicMock()
    error = HTTPError(response=MagicMock(status_code=404))
    response.raise_for_status.side_effect = error
    confluence.request.return_value = response

    texts = object.__new__(ConfluenceRag)._load_attachment_texts(confluence, BASE_URL, "42", None)

    assert not texts


def test_load_attachment_texts_skips_non_404_http_error():
    """One forbidden attachment does not discard the loaded page corpus."""
    confluence = MagicMock()
    confluence.get_attachments_from_content.return_value = {
        "results": [
            {
                "title": "forbidden.pdf",
                "metadata": {"mediaType": "application/pdf"},
                "_links": {"download": "/download/forbidden.pdf"},
            }
        ]
    }
    response = MagicMock()
    response.raise_for_status.side_effect = HTTPError(response=MagicMock(status_code=403))
    confluence.request.return_value = response

    texts = object.__new__(ConfluenceRag)._load_attachment_texts(confluence, BASE_URL, "42", None)

    assert not texts


def test_extract_attachment_text_uses_shared_pdf_util():
    """PDF attachment extraction delegates to the shared PDF utility."""
    with patch.object(confluence_rag.PdfUtils, "parse_pdf_bytes", return_value="PDF text") as parse_pdf:
        text = ConfluenceRag._extract_attachment_text(b"pdf bytes", "notes.pdf", "application/pdf", None)

    assert text == "PDF text"
    parse_pdf.assert_called_once_with(b"pdf bytes")


def test_load_attachment_texts_downloads_and_extracts_supported_attachment():
    """Enabled attachments are downloaded through the authenticated client and included."""
    confluence = MagicMock()
    confluence.get_attachments_from_content.return_value = {
        "results": [
            {
                "title": "notes.pdf",
                "metadata": {"mediaType": "application/pdf"},
                "_links": {"download": "/download/notes.pdf"},
            }
        ]
    }
    confluence.request.return_value.content = b"pdf bytes"
    tool = object.__new__(ConfluenceRag)

    with patch.object(tool, "_extract_attachment_text", return_value="Attachment text") as extract:
        texts = tool._load_attachment_texts(confluence, BASE_URL, "42", None)

    assert texts == ["\nnotes.pdf\nAttachment text"]
    confluence.request.assert_called_once_with(path=f"{BASE_URL}/download/notes.pdf", absolute=True)
    extract.assert_called_once_with(b"pdf bytes", "notes.pdf", "application/pdf", None)


def test_load_attachment_texts_skips_extraction_failure(caplog):
    """One unreadable attachment does not prevent later attachments from being extracted."""
    confluence = MagicMock()
    confluence.get_attachments_from_content.return_value = {
        "results": [
            {
                "title": "corrupt.pdf",
                "metadata": {"mediaType": "application/pdf"},
                "_links": {"download": "/download/corrupt.pdf"},
            },
            {
                "title": "notes.pdf",
                "metadata": {"mediaType": "application/pdf"},
                "_links": {"download": "/download/notes.pdf"},
            },
        ]
    }
    confluence.request.return_value.content = b"pdf bytes"
    tool = object.__new__(ConfluenceRag)

    with patch.object(tool, "_extract_attachment_text", side_effect=[ValueError("invalid PDF"), "Notes"]):
        texts = tool._load_attachment_texts(confluence, BASE_URL, "42", None)

    assert texts == ["\nnotes.pdf\nNotes"]
    assert "Failed to extract text from attachment corrupt.pdf: invalid PDF" in caplog.text


def test_load_documents_handles_permission_error():
    """Atlassian permission failures return no documents."""

    class ApiPermissionError(Exception):
        """Test replacement for the optional dependency exception."""

    tool = object.__new__(ConfluenceRag)

    with (
        patch.object(confluence_rag, "API_PERMISSION_ERRORS", (ApiPermissionError,)),
        patch.object(tool, "_load_documents_sync", side_effect=ApiPermissionError("denied")),
    ):
        documents = asyncio.run(tool.load_documents({"url": BASE_URL}))

    assert documents == []


def test_get_pages_skips_page_without_id():
    """Partial API responses without page IDs are skipped."""
    confluence = MagicMock()
    confluence.get_all_pages_from_space.return_value = [{"title": "Incomplete"}]

    pages = ConfluenceRag._get_pages(confluence, {"space_key": "TEST", "limit": 50, "max_pages": 100})

    assert not pages
