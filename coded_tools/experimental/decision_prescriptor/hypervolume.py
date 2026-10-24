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


# One measure with one entry point; splitting it further would not help a reader.
# pylint: disable=too-few-public-methods
class Hypervolume:
    """
    Volume of objective space dominated by a front, bounded by a reference point.

    Hypervolume is the standard single-number quality measure for a front because
    it rewards convergence and spread together. Objectives are minimized.
    """

    # Monte Carlo samples drawn when the caller does not supply a fixed set.
    DEFAULT_SAMPLES: int = 8000

    # Samples compared per block, so a large archive never builds a points-by-samples array at once.
    SAMPLE_CHUNK: int = 2048

    @staticmethod
    def compute(
        objectives: np.ndarray,
        reference: np.ndarray,
        samples: np.ndarray | None = None,
        box_volume: float | None = None,
    ) -> float:
        """
        Exact for one or two objectives via a sweep; estimated by Monte Carlo above
        that, where exact computation becomes expensive.

        For the Monte Carlo path the caller should pass a fixed `samples` array reused
        across a whole run. Re-drawing samples each call would make successive
        estimates differ by sampling noise as well as by real progress, which is
        enough to put visible dips in a curve that is supposed to be monotone.

        :param objectives: Array of shape (num_points, num_objectives), minimized.
        :param reference: Worst-case point that bounds the volume; must be dominated by the front.
        :param samples: Optional fixed sample points for the Monte Carlo path.
        :param box_volume: Volume of the box `samples` was drawn from. Required with `samples`.
        :return: The dominated hypervolume. Zero when no point beats the reference.
        """
        if objectives.size == 0:
            return 0.0

        # Only points strictly inside the reference box contribute.
        inside: np.ndarray = np.all(objectives < reference, axis=1)
        points: np.ndarray = objectives[inside]
        if points.shape[0] == 0:
            return 0.0

        num_objectives: int = points.shape[1]

        if num_objectives == 1:
            return float(reference[0] - np.min(points))

        if num_objectives == 2:
            # Sweep in ascending first objective, accumulating disjoint rectangles.
            order: np.ndarray = np.argsort(points[:, 0], kind="stable")
            volume: float = 0.0
            best_second: float = reference[1]
            for index in order:
                if points[index, 1] < best_second:
                    volume += (reference[0] - points[index, 0]) * (best_second - points[index, 1])
                    best_second = points[index, 1]
            return float(volume)

        if samples is None:
            lower: np.ndarray = np.min(points, axis=0)
            box_volume = float(np.prod(reference - lower))
            samples = np.random.default_rng(0).uniform(
                low=lower, high=reference, size=(Hypervolume.DEFAULT_SAMPLES, num_objectives)
            )
        if box_volume is None:
            raise ValueError("box_volume must accompany a supplied samples array")
        if box_volume <= 0.0:
            return 0.0

        # A sample counts if at least one front point dominates it.
        dominated_count: int = 0
        for start in range(0, samples.shape[0], Hypervolume.SAMPLE_CHUNK):
            block: np.ndarray = samples[start : start + Hypervolume.SAMPLE_CHUNK]
            dominated_count += int(
                np.count_nonzero(np.any(np.all(points[:, None, :] <= block[None, :, :], axis=2), axis=0))
            )

        return float(box_volume * dominated_count / samples.shape[0])
