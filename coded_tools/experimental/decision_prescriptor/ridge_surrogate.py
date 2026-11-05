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

from typing import Self

import numpy as np


class RidgeSurrogate:
    """
    Closed-form ridge regression from (context, action) features to outcomes: the
    "predictor" half of Evolutionary Surrogate-assisted Prescription.

    It learns outcome = f(context, action) from historical data, and then stands in
    for reality during the search. That substitution is the whole point: evolution
    needs to score hundreds of thousands of candidate strategies, which is only
    affordable against a model, never against the real world.

    Ridge regression is used deliberately. It has a closed-form solution, so a fit is
    exact and reproducible with no training loop, no learning rate and no random
    seed to explain away. The regularization term also keeps the model finite when
    features are collinear, which is common in small decision datasets.

    Features are standardized internally so a single regularization strength is
    meaningful across columns measured in different units.
    """

    EPSILON: float = 1e-12

    def __init__(self, alpha: float = 1.0):
        """
        :param alpha: Regularization strength. Larger values shrink coefficients
            harder, trading fit for stability. Must be non-negative.
        """
        if alpha < 0.0:
            raise ValueError("alpha must be non-negative")
        self.alpha: float = float(alpha)
        self.coefficients: np.ndarray | None = None
        self.feature_mean: np.ndarray | None = None
        self.feature_scale: np.ndarray | None = None

    def fit(self, features: np.ndarray, targets: np.ndarray) -> Self:
        """
        Solve for the ridge coefficients in closed form.

        Uses (X'X + alpha*I)^-1 X'Y on standardized features with an unpenalized
        bias column appended, which is why the identity block skips that column.

        :param features: Array of shape (num_rows, num_features).
        :param targets: Array of shape (num_rows, num_targets).
        :return: self, so a fit can be chained.
        """
        features = np.asarray(features, dtype=float)
        targets = np.asarray(targets, dtype=float)

        if features.shape[0] != targets.shape[0]:
            raise ValueError(f"features has {features.shape[0]} rows but targets has {targets.shape[0]}")
        if features.shape[0] == 0:
            raise ValueError("cannot fit a surrogate on zero rows")

        self.feature_mean = features.mean(axis=0)
        scale: np.ndarray = features.std(axis=0)
        # A constant column carries no information; scaling it by 1 leaves it at zero.
        self.feature_scale = np.where(scale < self.EPSILON, 1.0, scale)

        design: np.ndarray = self._design_matrix(features)
        num_columns: int = design.shape[1]

        penalty: np.ndarray = self.alpha * np.eye(num_columns)
        # Do not penalize the bias column: shrinking the intercept would bias predictions.
        penalty[-1, -1] = 0.0

        self.coefficients = np.linalg.solve(design.T @ design + penalty, design.T @ targets)
        return self

    def predict(self, features: np.ndarray) -> np.ndarray:
        """
        Predict outcomes for new (context, action) rows.

        :param features: Array of shape (num_rows, num_features).
        :return: Predictions of shape (num_rows, num_targets).
        """
        if self.coefficients is None:
            raise RuntimeError("surrogate must be fit before predict is called")
        return self._design_matrix(np.asarray(features, dtype=float)) @ self.coefficients

    def r_squared(self, features: np.ndarray, targets: np.ndarray) -> np.ndarray:
        """
        Coefficient of determination per target, on the given rows.

        Reported back to the user because a prescriptor is only ever as
        trustworthy as the surrogate it was evolved against. A weak fit here means
        the Pareto front is a picture of the model, not of the world.

        :param features: Array of shape (num_rows, num_features).
        :param targets: Array of shape (num_rows, num_targets).
        :return: R-squared per target, shape (num_targets,).
        """
        targets = np.asarray(targets, dtype=float)
        residual: np.ndarray = np.sum((targets - self.predict(features)) ** 2, axis=0)
        total: np.ndarray = np.sum((targets - targets.mean(axis=0)) ** 2, axis=0)
        return np.where(total < self.EPSILON, 0.0, 1.0 - residual / np.where(total < self.EPSILON, 1.0, total))

    def _design_matrix(self, features: np.ndarray) -> np.ndarray:
        """
        Standardize features and append the bias column.

        :param features: Raw feature array of shape (num_rows, num_features).
        :return: Design matrix of shape (num_rows, num_features + 1).
        """
        standardized: np.ndarray = (features - self.feature_mean) / self.feature_scale
        return np.hstack([standardized, np.ones((standardized.shape[0], 1))])
