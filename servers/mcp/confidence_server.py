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
MCP server exposing the Confidence Assessment coded tool.

Wraps SemanticDensityEngine as an MCP tool so any agent network
(local or remote) can assess answer confidence over streamable HTTP.

Requires GPU access — run on a machine with CUDA and the Qwen/DeBERTa
models available.

Usage:
    CUDA_VISIBLE_DEVICES=7 python confidence_server.py
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ConfidenceAssessment", port=8100)


@mcp.tool()
def assess_confidence(question: str) -> dict:
    """Assess answer confidence using semantic density scoring.

    Runs diverse beam search, token probability extraction, and
    NLI-based semantic distance to produce a 0-1 confidence score.

    Args:
        question: The question to evaluate.

    Returns:
        Dictionary with confidence_score, interpretation, best_answer,
        and answers_with_scores.
    """
    # pylint: disable=import-outside-toplevel
    from coded_tools.tools.semantic_density.semantic_density_engine import SemanticDensityEngine

    engine = SemanticDensityEngine.get_instance()
    return engine.evaluate(question)


if __name__ == "__main__":
    # streamable-http is preferred over stdio as transport method.
    mcp.run(transport="streamable-http")
