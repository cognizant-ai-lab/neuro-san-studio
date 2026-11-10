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


# A benchmark objective with one job; splitting it further would not help a reader.
# pylint: disable=too-few-public-methods
class Zdt1Benchmark:
    """
    The ZDT1 benchmark, whose true Pareto front is f2 = 1 - sqrt(f1), used by test_nsga2.py.
    """

    @staticmethod
    def evaluate(population: np.ndarray) -> np.ndarray:
        """
        :param population: Decision vectors in [0, 1], shape (n, num_genes).
        :return: Objectives of shape (n, 2), both minimized.
        """
        first: np.ndarray = population[:, 0]
        spread: np.ndarray = 1.0 + 9.0 * np.mean(population[:, 1:], axis=1)
        second: np.ndarray = spread * (1.0 - np.sqrt(first / spread))
        return np.column_stack([first, second])
