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
import logging
from typing import Any

import numpy as np
from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.experimental.decision_prescriptor.decision_keys import DecisionKeys
from coded_tools.experimental.decision_prescriptor.ridge_surrogate import RidgeSurrogate
from coded_tools.experimental.decision_prescriptor.training_arrays import TrainingArrays

logger = logging.getLogger(__name__)


class FitSurrogate(CodedTool):
    """
    Stage 2 of registries/experimental/decision_prescriptor.hocon: fit the predictor
    that stands in for reality during the search.
    """

    # Below this R-squared on any outcome, the front is flagged as indicative only.
    WEAK_FIT: float = 0.5

    def invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> str:
        """
        Fit ridge regression from (context, action) to outcomes and report its fit.

        The R-squared per outcome is returned rather than hidden, because it is
        the honest ceiling on everything downstream: a prescriptor evolved against
        a weak surrogate has optimized a bad map of the world, and the resulting
        front should not be trusted just because it is drawn precisely.

        :param args: May contain "alpha", the ridge regularization strength.
        :param sly_data: Must already hold the dataset; the fitted model is written here.
        :return: A human-readable summary of fit quality, or a message starting with "Error:".
        """
        rows: list[dict[str, Any]] | None = sly_data.get(DecisionKeys.DATASET)
        spec: dict[str, Any] | None = sly_data.get(DecisionKeys.SPEC)
        if not rows or not spec:
            return self._error("no decision problem loaded yet. Load the problem first.")

        try:
            alpha: float = float(args.get("alpha", 1.0))
        except (TypeError, ValueError):
            return self._error("'alpha' must be a number.")
        if alpha < 0:
            return self._error("'alpha' must be non-negative.")

        arrays: dict[str, np.ndarray] = TrainingArrays.build(
            rows, spec.get("context_fields"), spec.get("action_fields"), spec.get("outcome_fields")
        )
        features: np.ndarray = np.hstack([arrays.get("context"), arrays.get("action")])

        surrogate: RidgeSurrogate = RidgeSurrogate(alpha=alpha).fit(features, arrays.get("outcome"))
        scores: np.ndarray = surrogate.r_squared(features, arrays.get("outcome"))

        sly_data[DecisionKeys.SURROGATE] = surrogate

        reported: str = ", ".join(f"{name} R²={score:.3f}" for name, score in zip(spec.get("outcome_fields"), scores))
        weakest: float = float(np.min(scores))
        caveat: str = (
            " Fit is weak, so treat the front as indicative only."
            if weakest < self.WEAK_FIT
            else " Fit is strong enough to search against."
        )
        logger.info("Fitted surrogate on %d records, weakest R-squared %.3f", len(rows), weakest)
        return f"Surrogate fitted on {len(rows)} records (alpha={alpha:g}). {reported}.{caveat}"

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> str:
        """
        Run invoke in a worker thread, because the fit is blocking numeric work.

        :param args: See invoke.
        :param sly_data: See invoke.
        :return: See invoke.
        """
        return await asyncio.to_thread(self.invoke, args, sly_data)

    @staticmethod
    def _error(message: str) -> str:
        """
        Log a refused request and phrase it for the agent that called the tool.

        :param message: What was wrong with the request.
        :return: The message prefixed with "Error:", which the front man relays and stops on.
        """
        logger.warning("FitSurrogate refused the request: %s", message)
        return f"Error: {message}"
