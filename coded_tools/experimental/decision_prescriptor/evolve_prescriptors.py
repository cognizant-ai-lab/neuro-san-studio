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
import json
import logging
import time
from typing import Any

import numpy as np
from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.experimental.decision_prescriptor.decision_keys import DecisionKeys
from coded_tools.experimental.decision_prescriptor.nsga2 import Nsga2
from coded_tools.experimental.decision_prescriptor.pareto_ranking import ParetoRanking
from coded_tools.experimental.decision_prescriptor.prescriptor_evaluator import PrescriptorEvaluator
from coded_tools.experimental.decision_prescriptor.prescriptor_network import PrescriptorNetwork
from coded_tools.experimental.decision_prescriptor.ridge_surrogate import RidgeSurrogate
from coded_tools.experimental.decision_prescriptor.standardizer import Standardizer
from coded_tools.experimental.decision_prescriptor.training_arrays import TrainingArrays

logger = logging.getLogger(__name__)


class EvolvePrescriptors(CodedTool):
    """
    Stage 3 of registries/experimental/decision_prescriptor.hocon: evolve a Pareto
    front of prescriptor policies against the fitted surrogate.
    """

    # How many strategies a human is actually shown. The archive behind it stays whole.
    DISPLAY_LIMIT: int = 24

    # Upper limits on the search size, so one request cannot hold the server indefinitely.
    MAX_POPULATION: int = 500
    MAX_GENERATIONS: int = 500
    MAX_HIDDEN_DIM: int = 32

    # Every evolved weight is searched within [-WEIGHT_BOUND, WEIGHT_BOUND].
    WEIGHT_BOUND: float = 3.0

    # Wiring the dataset, network, evaluator, bounds and result together happens here.
    # pylint: disable=too-many-locals
    def invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> str:
        """
        Run NSGA-II over prescriptor weights and summarize the resulting front.

        :param args: May contain "population_size", "generations", "hidden_dim" and "seed".
        :param sly_data: Must hold the dataset, spec and fitted surrogate; the
            front and its history are written here.
        :return: A JSON summary of the trade-off found, or a message starting with "Error:".
        """
        rows: list[dict[str, Any]] | None = sly_data.get(DecisionKeys.DATASET)
        spec: dict[str, Any] | None = sly_data.get(DecisionKeys.SPEC)
        surrogate: RidgeSurrogate | None = sly_data.get(DecisionKeys.SURROGATE)
        if not rows or not spec:
            return self._error("no decision problem loaded yet. Load the problem first.")
        if surrogate is None:
            return self._error("the surrogate has not been fitted yet. Fit it before evolving prescriptors.")

        try:
            population_size: int = int(args.get("population_size", 60))
            generations: int = int(args.get("generations", 50))
            hidden_dim: int = int(args.get("hidden_dim", 4))
            seed: int = int(args.get("seed", 0))
        except (TypeError, ValueError):
            return self._error("population_size, generations, hidden_dim and seed must all be whole numbers.")
        if min(population_size, generations, hidden_dim) < 1:
            return self._error("population_size, generations and hidden_dim must all be at least 1.")
        if (
            population_size > self.MAX_POPULATION
            or generations > self.MAX_GENERATIONS
            or hidden_dim > self.MAX_HIDDEN_DIM
        ):
            return self._error(
                f"population_size, generations and hidden_dim are capped at {self.MAX_POPULATION}, "
                f"{self.MAX_GENERATIONS} and {self.MAX_HIDDEN_DIM}."
            )

        maximize: list[bool] = spec.get("maximize")
        outcome_fields: list[str] = spec.get("outcome_fields")
        arrays: dict[str, np.ndarray] = TrainingArrays.build(
            rows, spec.get("context_fields"), spec.get("action_fields"), outcome_fields
        )
        context: np.ndarray = arrays.get("context")
        action: np.ndarray = arrays.get("action")

        # Actions are held inside the range the historical data actually covers.
        # Outside it the surrogate is extrapolating, and its predictions there are
        # a property of the model rather than evidence about the world.
        network = PrescriptorNetwork(
            context_dim=context.shape[1],
            action_dim=action.shape[1],
            action_lower=action.min(axis=0),
            action_upper=action.max(axis=0),
            hidden_dim=hidden_dim,
        )

        network_context: np.ndarray = Standardizer(context).transform(context)
        evaluate = PrescriptorEvaluator(network, network_context, context, surrogate.predict, maximize)

        bounds: np.ndarray = np.full(network.num_weights, self.WEIGHT_BOUND)
        started: float = time.time()
        result: dict[str, np.ndarray] = Nsga2.evolve(
            evaluate,
            -bounds,
            bounds,
            population_size=population_size,
            generations=generations,
            seed=seed,
        )
        elapsed: float = time.time() - started

        # Back to display orientation: undo the negation applied to maximized outcomes.
        front_objectives: np.ndarray = result.get("front_objectives")
        signs: np.ndarray = np.array([-1.0 if flag else 1.0 for flag in maximize], dtype=float)
        front: np.ndarray = front_objectives * signs

        keep: np.ndarray = ParetoRanking.select_spread(front_objectives, self.DISPLAY_LIMIT)
        shown_front: np.ndarray = front[keep]
        shown_actions: np.ndarray = np.array(
            [network.actions(weights, network_context).mean(axis=0) for weights in result.get("front_genes")[keep]]
        )

        sly_data[DecisionKeys.RESULT] = {
            "front": shown_front,
            "actions": shown_actions,
            "population": result.get("objectives") * signs,
            "hypervolume_history": result.get("hypervolume_history"),
            "archive_size": int(front.shape[0]),
            "generations": generations,
            "elapsed_seconds": elapsed,
        }
        logger.info(
            "Evolved %d non-dominated strategies over %d generations in %.1fs", front.shape[0], generations, elapsed
        )

        return json.dumps(
            {
                "strategies_found": int(front.shape[0]),
                "strategies_shown": int(shown_front.shape[0]),
                "generations": generations,
                "seconds": round(elapsed, 2),
                "achievable_range": {
                    name: {
                        "best": round(float(shown_front[:, i].max() if flag else shown_front[:, i].min()), 4),
                        "worst": round(float(shown_front[:, i].min() if flag else shown_front[:, i].max()), 4),
                    }
                    for i, (name, flag) in enumerate(zip(outcome_fields, maximize))
                },
                "note": (
                    "Every strategy listed is non-dominated: none can be improved on one outcome "
                    "without giving something up on another. Choosing between them is a judgement "
                    "call, not a calculation."
                ),
            },
            indent=2,
        )

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> str:
        """
        Run invoke in a worker thread, because the search is seconds of blocking numeric work.

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
        logger.warning("EvolvePrescriptors refused the request: %s", message)
        return f"Error: {message}"
