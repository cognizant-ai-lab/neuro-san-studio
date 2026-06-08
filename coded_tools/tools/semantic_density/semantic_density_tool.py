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

"""
CodedTool wrapper for the semantic density engine.

Exposes the full semantic density pipeline as an async tool that any
agent in a neuro-san network can invoke to evaluate answer confidence.
"""

import asyncio
import json
import logging
from typing import Any
from typing import Dict

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.tools.semantic_density.semantic_density_engine import SemanticDensityEngine

logger = logging.getLogger(__name__)


class SemanticDensityTool(CodedTool):
    """
    A CodedTool that evaluates answer confidence using semantic density.

    Given a question, generates diverse answers via beam search, computes
    token probabilities and NLI-based semantic distances, then returns a
    0-1 confidence score with interpretation.
    """

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        Run the semantic density pipeline asynchronously.

        :param args: Dictionary with:
            - "question" (str, required): The question to evaluate.
        :param sly_data: Out-of-band data (unused by this tool).
        :return: JSON string with confidence_score, interpretation,
                 best_answer, and answers_with_scores.
        """
        question = args.get("question")
        if not question:
            return json.dumps({"error": "No question provided."})

        engine = SemanticDensityEngine.get_instance()

        # GPU inference truly blocks — must run in a thread to keep the
        # async event loop responsive for other agents in the network.
        result = await asyncio.to_thread(engine.evaluate, question)

        return json.dumps(result)
