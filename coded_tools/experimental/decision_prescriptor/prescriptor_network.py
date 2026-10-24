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

import numpy as np


class PrescriptorNetwork:
    """
    A one-hidden-layer network mapping context to bounded actions: the
    "prescription" half of Evolutionary Surrogate-assisted Prescription.

    Its weights are never trained by gradient descent, because there are no labels
    to descend against: nobody knows the optimal action for a given context, which
    is the reason the problem exists at all. Instead the whole weight vector is
    evolved, and a candidate is judged by the outcomes the surrogate predicts when
    its actions are applied across the dataset (see PrescriptorEvaluator).

    Evolving a policy rather than a fixed action matters. The result is a rule that
    responds to circumstances, so a new situation gets its own action rather than a
    lookup of whatever suited the average case.

    The network is intentionally tiny. Evolution searches the weight space
    directly, so every added weight enlarges the search space, and a small
    network also stays interpretable enough to inspect after the fact.
    """

    # The architecture and the action bounds are all genuinely independent inputs.
    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def __init__(
        self,
        context_dim: int,
        action_dim: int,
        action_lower: np.ndarray,
        action_upper: np.ndarray,
        hidden_dim: int = 4,
    ):
        """
        :param context_dim: Number of context features fed to the network.
        :param action_dim: Number of action values the network emits.
        :param action_lower: Per-action lower bound, shape (action_dim,).
        :param action_upper: Per-action upper bound, shape (action_dim,).
        :param hidden_dim: Width of the single hidden layer.
        """
        if context_dim <= 0 or action_dim <= 0 or hidden_dim <= 0:
            raise ValueError("context_dim, action_dim and hidden_dim must all be positive")

        self.context_dim: int = int(context_dim)
        self.action_dim: int = int(action_dim)
        self.hidden_dim: int = int(hidden_dim)
        self.action_lower: np.ndarray = np.asarray(action_lower, dtype=float)
        self.action_upper: np.ndarray = np.asarray(action_upper, dtype=float)

        if self.action_lower.shape != (self.action_dim,) or self.action_upper.shape != (self.action_dim,):
            raise ValueError("action bounds must each have shape (action_dim,)")
        if np.any(self.action_upper < self.action_lower):
            raise ValueError("every action upper bound must be at least its lower bound")

    @property
    def num_weights(self) -> int:
        """
        :return: Length of the flat weight vector that evolution searches over.
        """
        return sum(size for size, _ in self._layer_shapes())

    def get_action_bounds(self) -> tuple[np.ndarray, np.ndarray]:
        """
        :return: Tuple of (per-action lower bound, per-action upper bound).
        """
        return self.action_lower, self.action_upper

    def actions(self, weights: np.ndarray, context: np.ndarray) -> np.ndarray:
        """
        Apply one prescriptor to a batch of contexts.

        A tanh hidden layer keeps activations bounded, and a logistic output
        squashed into the action range guarantees every prescribed action is
        feasible by construction. Evolution therefore never wastes effort on
        candidates that would have to be clipped or repaired.

        :param weights: Flat weight vector of length num_weights.
        :param context: Context rows of shape (num_rows, context_dim).
        :return: Actions of shape (num_rows, action_dim), inside the bounds.
        """
        weights = np.asarray(weights, dtype=float)
        if weights.shape != (self.num_weights,):
            raise ValueError(f"expected {self.num_weights} weights, got {weights.shape}")

        layers: list[np.ndarray] = []
        cursor: int = 0
        for size, shape in self._layer_shapes():
            layers.append(weights[cursor : cursor + size].reshape(shape))
            cursor += size
        # Layer order follows _layer_shapes: input-to-hidden, hidden bias, hidden-to-output, output bias.
        hidden: np.ndarray = np.tanh(context @ layers[0] + layers[1])
        # Logistic squash, then rescale onto [action_lower, action_upper].
        unit: np.ndarray = 1.0 / (1.0 + np.exp(-(hidden @ layers[2] + layers[3])))
        return self.action_lower + unit * (self.action_upper - self.action_lower)

    def _layer_shapes(self) -> list[tuple[int, tuple[int, ...]]]:
        """
        Describe how the flat weight vector is cut into layers, in order.

        :return: (size, shape) of the input-to-hidden weights, hidden bias,
            hidden-to-output weights and output bias.
        """
        return [
            (self.context_dim * self.hidden_dim, (self.context_dim, self.hidden_dim)),
            (self.hidden_dim, (self.hidden_dim,)),
            (self.hidden_dim * self.action_dim, (self.hidden_dim, self.action_dim)),
            (self.action_dim, (self.action_dim,)),
        ]
