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
Unit tests for the semantic density engine and CodedTool.

These tests mock the heavy ML models so they can run without GPU.
The engine module imports torch/transformers/scipy at the top level,
so we patch sys.modules before importing the engine.
"""

import json
import sys
from types import ModuleType
from unittest.mock import MagicMock
from unittest.mock import patch

import numpy as np
import pytest

# Stub out heavy dependencies so the engine module can be imported without them
_STUB_MODULES = [
    "torch",
    "torch.cuda",
    "scipy",
    "scipy.spatial",
    "scipy.spatial.distance",
    "transformers",
]

for _mod_name in _STUB_MODULES:
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = ModuleType(_mod_name)

# Provide the specific names the engine references
sys.modules["torch"].no_grad = MagicMock()
sys.modules["torch"].cuda = MagicMock()
sys.modules["torch"].cuda.is_available = MagicMock(return_value=False)
sys.modules["torch"].float32 = "float32"
sys.modules["scipy.spatial.distance"].squareform = lambda x: x  # passthrough for tests

sys.modules["transformers"].AutoModelForCausalLM = MagicMock()
sys.modules["transformers"].AutoModelForSequenceClassification = MagicMock()
sys.modules["transformers"].AutoTokenizer = MagicMock()

# pylint: disable=wrong-import-position
from coded_tools.tools.semantic_density.semantic_density_engine import SemanticDensityEngine  # noqa: E402
from coded_tools.tools.semantic_density.semantic_density_tool import SemanticDensityTool  # noqa: E402


def _make_engine():
    """Create an engine instance without loading real models."""
    engine = SemanticDensityEngine.__new__(SemanticDensityEngine)
    engine._generation_model_name = "test-model"  # pylint: disable=protected-access
    engine._nli_model_name = "test-nli"  # pylint: disable=protected-access
    engine._device = "cpu"  # pylint: disable=protected-access
    engine._gen_tokenizer = None  # pylint: disable=protected-access
    engine._gen_model = None  # pylint: disable=protected-access
    engine._nli_tokenizer = None  # pylint: disable=protected-access
    engine._nli_model = None  # pylint: disable=protected-access
    return engine


class TestSemanticDensityComputation:
    """Test the pure-math semantic density computation."""

    engine = None

    def setup_method(self):
        """Create an engine without loading models."""
        self.engine = _make_engine()

    def test_density_identical_answers(self):
        """All-zero distance matrix should give density equal to 1.0."""
        probabilities = [0.5, 0.5]
        distance_matrix = np.array([[0.0, 0.0], [0.0, 0.0]])
        densities = self.engine.compute_semantic_density(probabilities, distance_matrix)
        assert len(densities) == 2
        assert all(abs(d - 1.0) < 1e-6 for d in densities)

    def test_density_maximally_distant(self):
        """Max distance matrix should give density of 0.5 for equal probs."""
        probabilities = [0.5, 0.5]
        distance_matrix = np.array([[0.0, 1.0], [1.0, 0.0]])
        densities = self.engine.compute_semantic_density(probabilities, distance_matrix)
        assert len(densities) == 2
        assert all(abs(d - 0.5) < 1e-6 for d in densities)

    def test_density_zero_probabilities(self):
        """Zero probabilities should return zero densities."""
        probabilities = [0.0, 0.0]
        distance_matrix = np.array([[0.0, 0.5], [0.5, 0.0]])
        densities = self.engine.compute_semantic_density(probabilities, distance_matrix)
        assert all(d == 0.0 for d in densities)

    def test_density_single_answer(self):
        """Single answer should have density of 1.0."""
        probabilities = [0.8]
        distance_matrix = np.array([[0.0]])
        densities = self.engine.compute_semantic_density(probabilities, distance_matrix)
        assert len(densities) == 1
        assert abs(densities[0] - 1.0) < 1e-6

    def test_density_asymmetric_probabilities(self):
        """Higher-prob answers in a cluster should have higher density."""
        probabilities = [0.9, 0.1]
        distance_matrix = np.array([[0.0, 0.3], [0.3, 0.0]])
        densities = self.engine.compute_semantic_density(probabilities, distance_matrix)
        assert densities[0] > densities[1]

    def test_confidence_interpretation_high(self):
        """Score >= 0.7 should be 'high'."""
        with patch.object(SemanticDensityEngine, "_ensure_models_loaded"):
            with patch.object(
                self.engine,
                "generate_diverse_answers",
                return_value=["Paris"],
            ):
                with patch.object(
                    self.engine,
                    "compute_token_probabilities",
                    return_value=[0.9],
                ):
                    with patch.object(
                        self.engine,
                        "compute_nli_distances",
                        return_value=np.array([[0.0]]),
                    ):
                        result = self.engine.evaluate("What is the capital of France?")
                        assert result["interpretation"] == "high"
                        assert result["confidence_score"] == 1.0

    def test_evaluate_result_structure(self):
        """The evaluate result should contain all expected keys."""
        with patch.object(SemanticDensityEngine, "_ensure_models_loaded"):
            with patch.object(
                self.engine,
                "generate_diverse_answers",
                return_value=["Answer A"],
            ):
                with patch.object(
                    self.engine,
                    "compute_token_probabilities",
                    return_value=[0.8],
                ):
                    with patch.object(
                        self.engine,
                        "compute_nli_distances",
                        return_value=np.array([[0.0]]),
                    ):
                        result = self.engine.evaluate("Test question?")

        assert "confidence_score" in result
        assert "interpretation" in result
        assert "best_answer" in result
        assert "answers_with_scores" in result
        assert "distance_matrix" in result
        assert isinstance(result["answers_with_scores"], list)
        assert result["best_answer"] == "Answer A"


class TestSemanticDensityTool:
    """Test the CodedTool wrapper."""

    @pytest.mark.asyncio
    async def test_missing_question_returns_error(self):
        """Calling with no question should return an error JSON."""
        tool = SemanticDensityTool()
        result = await tool.async_invoke({}, {})
        parsed = json.loads(result)
        assert "error" in parsed

    @pytest.mark.asyncio
    async def test_invoke_returns_json(self):
        """Calling with a question returns valid JSON with expected keys."""

        mock_result = {
            "confidence_score": 0.85,
            "interpretation": "high",
            "best_answer": "Paris",
            "answers_with_scores": [
                {
                    "answer": "Paris",
                    "probability": 0.9,
                    "density": 0.85,
                }
            ],
            "distance_matrix": [[0.0]],
        }

        tool = SemanticDensityTool()
        with patch.object(SemanticDensityEngine, "get_instance") as mock_get:
            mock_engine = MagicMock()
            mock_engine.evaluate.return_value = mock_result
            mock_get.return_value = mock_engine

            result = await tool.async_invoke({"question": "What is the capital of France?"}, {})
            parsed = json.loads(result)
            assert parsed["confidence_score"] == 0.85
            assert parsed["interpretation"] == "high"
            assert parsed["best_answer"] == "Paris"
