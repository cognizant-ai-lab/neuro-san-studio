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
Core semantic density engine ported from Xin's standalone demo.

Computes a 0-1 confidence score for LLM-generated answers by combining
diverse beam search token probabilities with NLI-based semantic distance.
"""

import logging
import threading
from typing import Any

import numpy as np
import torch
from scipy.spatial.distance import squareform
from transformers import AutoModelForCausalLM
from transformers import AutoModelForSequenceClassification
from transformers import AutoTokenizer

logger = logging.getLogger(__name__)

# Module-level singleton lock
_ENGINE_LOCK = threading.Lock()
_ENGINE_INSTANCE = None

# Default configuration
DEFAULT_GENERATION_MODEL = "Qwen/Qwen2.5-7B-Instruct"
DEFAULT_NLI_MODEL = "microsoft/deberta-large-mnli"
DEFAULT_NUM_BEAMS = 5
DEFAULT_NUM_BEAM_GROUPS = 5
DEFAULT_DIVERSITY_PENALTY = 1.0
DEFAULT_MAX_NEW_TOKENS = 256
DEFAULT_TEMPERATURE = 1.0
SYSTEM_PROMPT = "Answer the following question concisely in one or two sentences."


def get_engine(**kwargs: Any) -> "SemanticDensityEngine":
    """Return the module-level singleton engine, creating it on first call."""
    global _ENGINE_INSTANCE  # pylint: disable=global-statement
    if _ENGINE_INSTANCE is None:
        with _ENGINE_LOCK:
            if _ENGINE_INSTANCE is None:
                _ENGINE_INSTANCE = SemanticDensityEngine(**kwargs)
    return _ENGINE_INSTANCE


class SemanticDensityEngine:
    """
    Encapsulates the four core semantic density algorithm steps:

    1. Diverse beam search — generate multiple diverse answers
    2. Token probability extraction — logits to geometric-mean probabilities
    3. NLI semantic distance — pairwise contradiction/neutral scoring
    4. Semantic density — weighted density combining distance and probability
    """

    def __init__(
        self,
        generation_model: str = DEFAULT_GENERATION_MODEL,
        nli_model: str = DEFAULT_NLI_MODEL,
        device: str | None = None,
    ):
        self._generation_model_name = generation_model
        self._nli_model_name = nli_model

        if device is not None:
            self._device = device
        elif torch.cuda.is_available():
            self._device = "cuda"
        else:
            self._device = "cpu"

        self._gen_tokenizer = None
        self._gen_model = None
        self._nli_tokenizer = None
        self._nli_model = None

        logger.info(
            "SemanticDensityEngine created (device=%s, gen=%s, nli=%s)",
            self._device,
            self._generation_model_name,
            self._nli_model_name,
        )

    def _ensure_models_loaded(self) -> None:
        """Lazy-load models on first use."""
        if self._gen_model is None:
            logger.info("Loading generation model: %s", self._generation_model_name)
            self._gen_tokenizer = AutoTokenizer.from_pretrained(self._generation_model_name)
            # float32 required — group beam search has dtype mismatch bug with float16
            self._gen_model = AutoModelForCausalLM.from_pretrained(
                self._generation_model_name,
                torch_dtype=torch.float32,
            ).to(self._device)
            self._gen_model.eval()
            logger.info("Generation model loaded on %s", self._device)

        if self._nli_model is None:
            logger.info("Loading NLI model: %s", self._nli_model_name)
            self._nli_tokenizer = AutoTokenizer.from_pretrained(self._nli_model_name)
            self._nli_model = AutoModelForSequenceClassification.from_pretrained(
                self._nli_model_name,
            ).to(self._device)
            self._nli_model.eval()
            logger.info("NLI model loaded on %s", self._device)

    # ------------------------------------------------------------------
    # Step 1: Diverse beam search generation
    # ------------------------------------------------------------------
    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def generate_diverse_answers(
        self,
        question: str,
        num_beams: int = DEFAULT_NUM_BEAMS,
        num_beam_groups: int = DEFAULT_NUM_BEAM_GROUPS,
        diversity_penalty: float = DEFAULT_DIVERSITY_PENALTY,
        max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
    ) -> list[str]:
        """Generate multiple diverse answers via group beam search."""
        self._ensure_models_loaded()

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]
        prompt_text = self._gen_tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self._gen_tokenizer(prompt_text, return_tensors="pt").to(self._device)
        prompt_length = inputs["input_ids"].shape[1]

        with torch.no_grad():
            outputs = self._gen_model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                num_beams=num_beams,
                num_beam_groups=num_beam_groups,
                diversity_penalty=diversity_penalty,
                num_return_sequences=num_beams,
                output_scores=True,
                return_dict_in_generate=True,
            )

        answers = []
        for seq in outputs.sequences:
            generated_tokens = seq[prompt_length:]
            decoded = self._gen_tokenizer.decode(generated_tokens, skip_special_tokens=True)
            answers.append(decoded.strip())

        return answers

    # ------------------------------------------------------------------
    # Step 2: Token probability extraction
    # ------------------------------------------------------------------
    def compute_token_probabilities(
        self,
        question: str,
        answers: list[str],
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> list[float]:
        """
        Compute per-answer probability as geometric mean of token probabilities.

        For each answer, re-encode [prompt + answer], extract logits for
        answer tokens, apply temperature-scaled softmax, and take the
        geometric mean of the selected token probabilities.
        """
        self._ensure_models_loaded()

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]
        prompt_text = self._gen_tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        prompt_ids = self._gen_tokenizer(prompt_text, return_tensors="pt")["input_ids"]
        prompt_length = prompt_ids.shape[1]

        probabilities = []
        for answer in answers:
            geo_mean = self._compute_single_answer_probability(prompt_text, prompt_length, answer, temperature)
            probabilities.append(geo_mean)

        return probabilities

    def _compute_single_answer_probability(
        self,
        prompt_text: str,
        prompt_length: int,
        answer: str,
        temperature: float,
    ) -> float:
        """Compute geometric mean of token probabilities for a single answer."""
        full_text = prompt_text + answer
        inputs = self._gen_tokenizer(full_text, return_tensors="pt").to(self._device)
        input_ids = inputs["input_ids"]

        with torch.no_grad():
            logits = self._gen_model(**inputs).logits

        answer_logits = logits[0, prompt_length - 1 : input_ids.shape[1] - 1, :]
        answer_token_ids = input_ids[0, prompt_length:]

        scaled_logits = answer_logits / temperature
        token_probs = torch.softmax(scaled_logits, dim=-1)

        selected_probs = token_probs[
            torch.arange(answer_token_ids.shape[0]),
            answer_token_ids,
        ]

        log_probs = torch.log(selected_probs + 1e-10)
        return torch.exp(log_probs.mean()).item()

    # ------------------------------------------------------------------
    # Step 3: NLI semantic distance
    # ------------------------------------------------------------------
    def compute_nli_distances(self, answers: list[str]) -> np.ndarray:
        """
        Compute pairwise semantic distances using NLI.

        distance(a, b) = P(contradiction) + 0.5 * P(neutral), symmetrized.
        Returns a symmetric distance matrix.
        """
        self._ensure_models_loaded()

        num_answers = len(answers)
        condensed = []

        for i in range(num_answers):
            for j in range(i + 1, num_answers):
                dist_ij = self._nli_distance_pair(answers[i], answers[j])
                dist_ji = self._nli_distance_pair(answers[j], answers[i])
                symmetric_dist = (dist_ij + dist_ji) / 2.0
                condensed.append(symmetric_dist)

        if len(condensed) == 0:
            return np.zeros((num_answers, num_answers))

        distance_matrix = squareform(np.array(condensed))
        return distance_matrix

    def _nli_distance_pair(self, premise: str, hypothesis: str) -> float:
        """Compute NLI distance for a single (premise, hypothesis) pair."""
        inputs = self._nli_tokenizer(premise, hypothesis, return_tensors="pt", truncation=True, max_length=512).to(
            self._device
        )

        with torch.no_grad():
            logits = self._nli_model(**inputs).logits

        probs = torch.softmax(logits, dim=-1)[0]
        # DeBERTa-large-MNLI label order: [contradiction, neutral, entailment]
        p_contradiction = probs[0].item()
        p_neutral = probs[1].item()

        return p_contradiction + 0.5 * p_neutral

    # ------------------------------------------------------------------
    # Step 4: Semantic density score
    # ------------------------------------------------------------------
    def compute_semantic_density(
        self,
        probabilities: list[float],
        distance_matrix: np.ndarray,
    ) -> list[float]:
        """
        Compute semantic density for each answer.

        density(i) = sum_j( (1 - avg_distance(i,j)) * probability(j) ) / sum(probabilities)
        """
        prob_array = np.array(probabilities)
        prob_sum = prob_array.sum()
        if prob_sum == 0:
            return [0.0] * len(probabilities)

        densities = []
        num_answers = len(probabilities)
        for i in range(num_answers):
            density = 0.0
            for j in range(num_answers):
                similarity = 1.0 - distance_matrix[i, j]
                density += similarity * prob_array[j]
            density /= prob_sum
            densities.append(density)

        return densities

    # ------------------------------------------------------------------
    # Public high-level API
    # ------------------------------------------------------------------
    def evaluate(self, question: str) -> dict[str, Any]:
        """
        Run the full semantic density pipeline on a question.

        Returns a dict with:
            - confidence_score: float 0-1 (max density across answers)
            - interpretation: str (human-readable confidence label)
            - answers_with_scores: list of dicts with answer, probability, density
            - best_answer: str (answer with highest density)
            - distance_matrix: list of lists (for optional visualization)
        """
        self._ensure_models_loaded()

        logger.info("Generating diverse answers for: %s", question[:80])
        answers = self.generate_diverse_answers(question)

        logger.info("Computing token probabilities for %d answers", len(answers))
        probabilities = self.compute_token_probabilities(question, answers)

        logger.info("Computing NLI distances")
        distance_matrix = self.compute_nli_distances(answers)

        logger.info("Computing semantic densities")
        densities = self.compute_semantic_density(probabilities, distance_matrix)

        # Find best answer by density
        best_idx = int(np.argmax(densities))
        confidence_score = densities[best_idx]

        if confidence_score >= 0.7:
            interpretation = "high"
        elif confidence_score >= 0.4:
            interpretation = "moderate"
        else:
            interpretation = "low"

        answers_with_scores = []
        for i, answer in enumerate(answers):
            answers_with_scores.append(
                {
                    "answer": answer,
                    "probability": round(probabilities[i], 4),
                    "density": round(densities[i], 4),
                }
            )

        return {
            "confidence_score": round(confidence_score, 4),
            "interpretation": interpretation,
            "best_answer": answers[best_idx],
            "answers_with_scores": answers_with_scores,
            "distance_matrix": distance_matrix.tolist(),
        }
