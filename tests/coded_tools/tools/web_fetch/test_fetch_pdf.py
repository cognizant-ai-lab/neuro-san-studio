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

import asyncio
from unittest import TestCase
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from aiohttp import ClientError
from langchain_core.documents import Document

from coded_tools.tools.web_fetch import WebFetch


class TestFetchPdf(TestCase):
    """Unit tests for WebFetch._fetch_pdf."""

    def setUp(self):
        self.tool = WebFetch()

    def test_returns_joined_page_content(self):
        """Tests that page content from all PDF pages is joined into a single newline-separated string."""
        docs = [Document(page_content="Page one"), Document(page_content="Page two")]
        mock_loader = MagicMock()
        mock_loader.aload = AsyncMock(return_value=docs)

        with patch("coded_tools.tools.web_fetch.PyPDFLoader", return_value=mock_loader):
            result = asyncio.run(self.tool._fetch_pdf("http://example.com/doc.pdf"))  # pylint: disable=protected-access

        self.assertEqual(result, "Page one\nPage two")

    def test_loader_exception_raises_client_error_with_prefix(self):
        """Tests that a loader exception raises ClientError with url_not_accessible prefix."""
        mock_loader = MagicMock()
        mock_loader.aload = AsyncMock(side_effect=Exception("download failed"))

        with patch("coded_tools.tools.web_fetch.PyPDFLoader", return_value=mock_loader):
            with self.assertRaises(ClientError) as ctx:
                asyncio.run(self.tool._fetch_pdf("http://example.com/doc.pdf"))  # pylint: disable=protected-access

        self.assertIn("url_not_accessible", str(ctx.exception))
