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


# A shift-and-scale with one job; splitting it further would not help a reader.
# pylint: disable=too-few-public-methods
class Standardizer:
    """
    Applies the shift and scale of a reference array to any matching array.

    Context features are standardized before reaching the prescriptor network so
    that a feature measured in millions does not swamp one measured in single
    digits purely because of its units.
    """

    EPSILON: float = 1e-12

    def __init__(self, reference: np.ndarray):
        """
        :param reference: Reference array of shape (num_rows, num_features).
        """
        self.mean: np.ndarray = reference.mean(axis=0)
        scale: np.ndarray = reference.std(axis=0)
        self.scale: np.ndarray = np.where(scale < self.EPSILON, 1.0, scale)

    def transform(self, values: np.ndarray) -> np.ndarray:
        """
        :param values: Array with the same number of features as the reference.
        :return: The values shifted and scaled by the reference statistics.
        """
        return (values - self.mean) / self.scale
