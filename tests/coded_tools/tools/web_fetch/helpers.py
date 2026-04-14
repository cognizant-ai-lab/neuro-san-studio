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

from unittest.mock import AsyncMock
from unittest.mock import MagicMock

from aiohttp import ClientResponseError


def make_request_info(url: str = "http://example.com") -> MagicMock:
    """Minimal RequestInfo mock required by ClientResponseError constructor."""
    info = MagicMock()
    info.url = url
    info.method = "HEAD"
    info.headers = {}
    info.real_url = url
    return info


def make_response_error(status: int, url: str = "http://example.com") -> ClientResponseError:
    """Build a minimal ClientResponseError with the given HTTP status code."""
    return ClientResponseError(request_info=make_request_info(url), history=(), status=status)


def make_head_session(
    status: int = 200,
    content_type: str = "text/html",
    content_length: int | None = None,
    raise_for_status_exc: Exception | None = None,
) -> tuple[MagicMock, MagicMock]:
    """Return (mock_session, mock_head_response) for HEAD-only tests."""
    headers: dict[str, str] = {"Content-Type": content_type}
    if content_length is not None:
        headers["Content-Length"] = str(content_length)

    head_response = MagicMock()
    head_response.status = status
    head_response.headers = headers
    head_response.raise_for_status = MagicMock(side_effect=raise_for_status_exc if raise_for_status_exc else None)

    head_cm = MagicMock()
    head_cm.__aenter__ = AsyncMock(return_value=head_response)
    head_cm.__aexit__ = AsyncMock(return_value=False)

    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.head = MagicMock(return_value=head_cm)

    return session, head_response


def make_get_response(
    status: int = 200,
    content_type: str = "text/html",
    body: str = "",
    charset: str = "utf-8",
    raise_for_status_exc: Exception | None = None,
) -> tuple[MagicMock, MagicMock]:
    """Return (mock_session, mock_get_response) for GET-only tests (_fetch_text)."""
    response = MagicMock()
    response.status = status
    response.headers = {"Content-Type": content_type}
    response.charset = charset
    response.raise_for_status = MagicMock(side_effect=raise_for_status_exc if raise_for_status_exc else None)
    response.text = AsyncMock(return_value=body)

    response_cm = MagicMock()
    response_cm.__aenter__ = AsyncMock(return_value=response)
    response_cm.__aexit__ = AsyncMock(return_value=False)

    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.get = MagicMock(return_value=response_cm)

    return session, response
