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

from collections.abc import Callable

import numpy as np

from coded_tools.experimental.decision_prescriptor.prescriptor_network import PrescriptorNetwork


# The search calls this object as its objective function; that is its only job.
# pylint: disable=too-few-public-methods
class PrescriptorEvaluator:
    """
    The objective function that the evolutionary search calls (see Nsga2.evolve).

    Each candidate prescriptor is applied across every context row, the surrogate
    predicts the outcome of those actions, and the predictions are averaged into
    one objective vector. Averaging over the whole dataset is what stops a
    prescriptor from winning by exploiting a single lucky situation.

    Two views of the same contexts are needed and must not be mixed up. The
    network reads standardized context, so no feature dominates on units alone.
    The surrogate reads raw context, because it standardizes internally using the
    statistics it was fit with. Actions come out in raw units either way.

    The objectives are always minimization-oriented, because that is the
    convention NSGA-II works in; objectives the user wants maximized are negated
    here and negated back for display.
    """

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def __init__(
        self,
        network: PrescriptorNetwork,
        network_context: np.ndarray,
        raw_context: np.ndarray,
        predict_outcomes: Callable[[np.ndarray], np.ndarray],
        maximize: list[bool],
    ):
        """
        :param network: The prescriptor architecture being evolved.
        :param network_context: Standardized context rows, shape (num_rows, context_dim).
        :param raw_context: The same rows in original units, shape (num_rows, context_dim).
        :param predict_outcomes: Maps raw (context, action) features to predicted outcomes.
        :param maximize: One flag per outcome; True where larger is better.
        """
        if network_context.shape != raw_context.shape:
            raise ValueError("standardized and raw context must have the same shape")

        self.network: PrescriptorNetwork = network
        self.network_context: np.ndarray = network_context
        self.raw_context: np.ndarray = raw_context
        self.predict_outcomes: Callable[[np.ndarray], np.ndarray] = predict_outcomes
        self.signs: np.ndarray = np.array([-1.0 if flag else 1.0 for flag in maximize], dtype=float)

    def __call__(self, population: np.ndarray) -> np.ndarray:
        """
        :param population: Weight vectors, shape (population_size, network.num_weights).
        :return: Minimization-oriented objectives, shape (population_size, num_outcomes).
        """
        objectives: np.ndarray = np.empty((population.shape[0], self.signs.shape[0]), dtype=float)
        for index, weights in enumerate(population):
            actions: np.ndarray = self.network.actions(weights, self.network_context)
            predicted: np.ndarray = self.predict_outcomes(np.hstack([self.raw_context, actions]))
            objectives[index] = predicted.mean(axis=0) * self.signs
        return objectives
