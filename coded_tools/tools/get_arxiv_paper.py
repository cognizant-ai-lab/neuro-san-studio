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

import logging
from typing import Any
from typing import Dict

from neuro_san.interfaces.coded_tool import CodedTool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GetArxivPaper(CodedTool):
    """
    CodedTool implementation which get arXiv papers content from sly data.
    """

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        Load arXiv papers based on entry ID.

        :param args: Dictionary containing:
            "entry_id": ID of the arxiv paper

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
                "arxiv_contents": content of the paper of the entry id

        :return: Result of the query against the vector store.
        """
        # Extract arguments from the input dictionary
        entry_id: str = args.get("entry_id")

        # Validate presence of required inputs
        if not entry_id:
            logger.error("Missing required input: 'entry_id'.")
            raise ValueError("❌ Missing required input: 'entry_id'.")

        # Ensure the ID always start with "http://arxiv.org/abs/"
        if not entry_id.startswith("http://arxiv.org/abs/"):
            entry_id = "http://arxiv.org/abs/" + entry_id

        return sly_data.get("arxiv_contents", {}).get(entry_id)
