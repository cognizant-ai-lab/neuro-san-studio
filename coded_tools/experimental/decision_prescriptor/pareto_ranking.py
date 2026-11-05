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


class ParetoRanking:
    """
    Dominance, front partitioning and crowding, as described for NSGA-II in Deb et al. (2002),
    "A Fast and Elitist Multiobjective Genetic Algorithm: NSGA-II".

    Convention: every objective here is MINIMIZED. Callers that want to maximize an
    objective negate it at the boundary and negate the result back.

    See nsga2.py for the search loop that drives these rankings.
    """

    # Guards a division by zero when an objective is constant across a front.
    EPSILON: float = 1e-12

    @staticmethod
    def dominates(objectives_a: np.ndarray, objectives_b: np.ndarray) -> bool:
        """
        Determine whether one objective vector Pareto-dominates another.

        Under minimization, a dominates b when a is no worse on every objective and
        strictly better on at least one. If neither dominates the other the two
        solutions are incomparable, which is what makes the trade-off real.

        :param objectives_a: Objective vector of the candidate solution.
        :param objectives_b: Objective vector it is compared against.
        :return: True if objectives_a dominates objectives_b.
        """
        return bool(np.all(objectives_a <= objectives_b) and np.any(objectives_a < objectives_b))

    @staticmethod
    def non_dominated_mask(objectives: np.ndarray, chunk_size: int = 512) -> np.ndarray:
        """
        Flag the solutions that nothing else dominates.

        This answers the same question as the first front of `fast_non_dominated_sort`
        but computes it with array operations instead of a Python double loop. The
        archive is re-derived every generation and grows into the thousands, which is
        exactly where the elementwise version becomes the cost of the whole run.

        Work is done in row blocks so peak memory stays proportional to
        `chunk_size * num_points` rather than the square of the population.

        :param objectives: Array of shape (num_points, num_objectives), minimized.
        :param chunk_size: Number of candidates compared per block.
        :return: Boolean mask, True where the solution is non-dominated.
        """
        num_points: int = objectives.shape[0]
        mask: np.ndarray = np.ones(num_points, dtype=bool)
        if num_points == 0:
            return mask

        for start in range(0, num_points, chunk_size):
            stop: int = min(start + chunk_size, num_points)
            block: np.ndarray = objectives[start:stop]

            # no_worse[i, j] : solution i is no worse than block j on every objective.
            no_worse: np.ndarray = np.all(objectives[:, None, :] <= block[None, :, :], axis=2)
            # strictly_better[i, j] : solution i beats block j on at least one objective.
            strictly_better: np.ndarray = np.any(objectives[:, None, :] < block[None, :, :], axis=2)
            mask[start:stop] = ~np.any(no_worse & strictly_better, axis=0)

        return mask

    @staticmethod
    def fast_non_dominated_sort(objectives: np.ndarray) -> list[list[int]]:
        """
        Partition a population into Pareto fronts.

        Front 0 holds the solutions nothing dominates. Front 1 holds those dominated
        only by front 0, and so on. This is Deb's O(M*N^2) formulation: for each
        solution count how many dominate it, then peel off the zero-count layer and
        decrement the counts of everything it dominated.

        :param objectives: Array of shape (population_size, num_objectives), minimized.
        :return: List of fronts, each a list of row indices into objectives, best front first.
        """
        population_size: int = objectives.shape[0]
        if population_size == 0:
            return []

        # dominated_by[i] lists the solutions that i dominates.
        dominated_by: list[list[int]] = [[] for _ in range(population_size)]
        # domination_count[i] is how many solutions dominate i.
        domination_count: np.ndarray = np.zeros(population_size, dtype=int)

        for i in range(population_size):
            for j in range(i + 1, population_size):
                if ParetoRanking.dominates(objectives[i], objectives[j]):
                    dominated_by[i].append(j)
                    domination_count[j] += 1
                elif ParetoRanking.dominates(objectives[j], objectives[i]):
                    dominated_by[j].append(i)
                    domination_count[i] += 1

        fronts: list[list[int]] = []
        current_front: list[int] = [i for i in range(population_size) if domination_count[i] == 0]

        while current_front:
            fronts.append(current_front)
            next_front: list[int] = []
            for i in current_front:
                for j in dominated_by[i]:
                    domination_count[j] -= 1
                    if domination_count[j] == 0:
                        next_front.append(j)
            current_front = sorted(next_front)

        return fronts

    @staticmethod
    def crowding_distance(objectives: np.ndarray, front: list[int]) -> np.ndarray:
        """
        Measure how isolated each solution is within its own front.

        For every objective the front is sorted and each solution receives the
        normalized gap between its two neighbours. The two extremes get infinity so
        elitist selection never discards the ends of the front. Summing across
        objectives gives a diversity score used as the tie-break inside a front:
        crowded regions lose, sparse regions survive, and the front stays spread out.

        :param objectives: Array of shape (population_size, num_objectives), minimized.
        :param front: Row indices belonging to a single Pareto front.
        :return: Array of distances aligned with the order of `front`.
        """
        front_size: int = len(front)
        distances: np.ndarray = np.zeros(front_size, dtype=float)
        if front_size <= 2:
            return np.full(front_size, np.inf)

        front_objectives: np.ndarray = objectives[front]
        num_objectives: int = front_objectives.shape[1]

        for objective_index in range(num_objectives):
            values: np.ndarray = front_objectives[:, objective_index]
            order: np.ndarray = np.argsort(values, kind="stable")
            spread: float = values[order[-1]] - values[order[0]]

            # A constant objective separates nobody, so it contributes nothing.
            if spread < ParetoRanking.EPSILON:
                continue

            distances[order[0]] = np.inf
            distances[order[-1]] = np.inf
            for position in range(1, front_size - 1):
                neighbour_gap: float = values[order[position + 1]] - values[order[position - 1]]
                distances[order[position]] += neighbour_gap / spread

        return distances

    @staticmethod
    def rank_and_crowding(objectives: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Compute the front index and crowding distance of every solution.

        :param objectives: Array of shape (population_size, num_objectives), minimized.
        :return: Tuple of (rank per solution, crowding distance per solution).
        """
        population_size: int = objectives.shape[0]
        ranks: np.ndarray = np.zeros(population_size, dtype=int)
        crowding: np.ndarray = np.zeros(population_size, dtype=float)

        for front_index, front in enumerate(ParetoRanking.fast_non_dominated_sort(objectives)):
            ranks[front] = front_index
            crowding[front] = ParetoRanking.crowding_distance(objectives, front)

        return ranks, crowding

    @staticmethod
    def environmental_selection(objectives: np.ndarray, survivors: int) -> np.ndarray:
        """
        Keep the best `survivors` solutions, front by front.

        Whole fronts are admitted while they fit. The front that straddles the cut is
        admitted partially, ordered by descending crowding distance, which is how
        NSGA-II preserves a spread-out front instead of collapsing onto one corner.

        :param objectives: Array of shape (population_size, num_objectives), minimized.
        :param survivors: Number of solutions to retain.
        :return: Indices of the retained solutions.
        """
        selected: list[int] = []

        for front in ParetoRanking.fast_non_dominated_sort(objectives):
            if len(selected) + len(front) <= survivors:
                selected.extend(front)
                continue

            remaining: int = survivors - len(selected)
            if remaining > 0:
                distances: np.ndarray = ParetoRanking.crowding_distance(objectives, front)
                # Descending crowding distance: the most isolated solutions survive.
                order: np.ndarray = np.argsort(-distances, kind="stable")
                selected.extend(int(front[position]) for position in order[:remaining])
            break

        return np.array(selected, dtype=int)

    @staticmethod
    def select_spread(objectives: np.ndarray, count: int) -> np.ndarray:
        """
        Pick a readable subset of a front that still spans its full extent.

        An unbounded archive is the right thing to measure progress against but the
        wrong thing to hand a reader: a thousand strategies is not a choice, it is a
        haystack. Selecting by crowding distance keeps the extremes, because they are
        the honest edges of what is achievable, and then fills in from the most
        isolated points inward, so the sample tracks the shape of the curve rather
        than bunching where solutions happen to be dense.

        :param objectives: Front objectives, shape (num_points, num_objectives).
        :param count: Maximum number of points to keep.
        :return: Indices into objectives, ordered as given.
        """
        num_points: int = objectives.shape[0]
        if count <= 0:
            return np.empty(0, dtype=int)
        if num_points <= count:
            return np.arange(num_points)

        distances: np.ndarray = ParetoRanking.crowding_distance(objectives, list(range(num_points)))
        chosen: np.ndarray = np.argsort(-distances, kind="stable")[:count]
        return np.sort(chosen)
