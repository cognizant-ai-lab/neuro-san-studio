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

from typing import Any

from requests import get
from requests import post
from requests.exceptions import HTTPError


class APIClient:
    """Handle API communication with neuro-san server."""

    def __init__(self, port: str):
        self.port = port
        self.base_url = f"http://localhost:{port}/api/v1"

    def call(self, endpoint: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Make API call to endpoint.

        :param endpoint: Server endpoint
        :param payload: Request payload for HTTP POST

        :return: Response in JSON format
        """
        url = f"{self.base_url}/{endpoint}"

        if endpoint == "list":
            response = get(url, timeout=30)
        else:
            response = post(url, json=payload, timeout=300)

        response.raise_for_status()
        return response.json()

    def test_connection(self, network_name: str) -> bool:
        """
        Test if network exists.

        :param network_name: Name of the agent network to check connection

        :return: True if the connection is valid, False otherwise
        """
        try:
            self.call(f"{network_name}/streaming_chat", {})
            return True
        except HTTPError:
            return False
