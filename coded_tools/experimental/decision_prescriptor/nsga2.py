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

from coded_tools.experimental.decision_prescriptor.genetic_operators import GeneticOperators
from coded_tools.experimental.decision_prescriptor.hypervolume import Hypervolume
from coded_tools.experimental.decision_prescriptor.pareto_ranking import ParetoRanking


class Nsga2:
    """
    NSGA-II, implemented from the original description in Deb et al. (2002),
    "A Fast and Elitist Multiobjective Genetic Algorithm: NSGA-II".

    The search core is numpy only and free of any neuro-san import, so its
    behaviour can be unit-tested on its own. Every objective is MINIMIZED.
    Ranking lives in ParetoRanking, breeding in GeneticOperators and the progress
    measure in Hypervolume.
    """

    @staticmethod
    def update_archive(
        archive_genes: np.ndarray,
        archive_objectives: np.ndarray,
        new_genes: np.ndarray,
        new_objectives: np.ndarray,
        decimals: int = 9,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Merge new solutions into an unbounded archive of non-dominated solutions.

        The archive exists because the population alone is not a reliable record of
        progress. Once the first front grows past the population size, NSGA-II's
        crowding truncation has to discard genuinely non-dominated solutions, so the
        population's hypervolume can fall from one generation to the next. Anything
        dropped from the archive, by contrast, was dominated by something that
        remains, so the region the archive dominates can only ever grow.

        :param archive_genes: Current archive decision vectors, shape (n, num_genes).
        :param archive_objectives: Their objectives, shape (n, num_objectives).
        :param new_genes: Candidate decision vectors to merge in.
        :param new_objectives: Their objectives.
        :param decimals: Rounding used to drop duplicate objective vectors.
        :return: Tuple of (archive genes, archive objectives) after the merge.
        """
        merged_genes: np.ndarray = np.vstack([archive_genes, new_genes]) if archive_genes.size else new_genes
        merged_objectives: np.ndarray = (
            np.vstack([archive_objectives, new_objectives]) if archive_objectives.size else new_objectives
        )

        # Drop exact duplicates first, so the O(N^2) sort below stays small.
        _, unique_indices = np.unique(np.round(merged_objectives, decimals), axis=0, return_index=True)
        unique_indices = np.sort(unique_indices)
        merged_genes = merged_genes[unique_indices]
        merged_objectives = merged_objectives[unique_indices]

        keep: np.ndarray = ParetoRanking.non_dominated_mask(merged_objectives)
        return merged_genes[keep], merged_objectives[keep]

    # The search loop legitimately juggles population, archive, bounds and history.
    # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    @staticmethod
    def evolve(
        evaluate: Callable[[np.ndarray], np.ndarray],
        lower: np.ndarray,
        upper: np.ndarray,
        population_size: int = 60,
        generations: int = 40,
        seed: int = 0,
    ) -> dict[str, np.ndarray]:
        """
        Run NSGA-II and return the archived Pareto front plus its convergence history.

        The returned front comes from the unbounded archive rather than the final
        population, so it is never worse than the population's own front and the
        reported hypervolume history is non-decreasing by construction.

        :param evaluate: Maps a population of shape (n, num_genes) to objectives of
            shape (n, num_objectives). Must be minimization-oriented.
        :param lower: Per-gene lower bound.
        :param upper: Per-gene upper bound.
        :param population_size: Number of individuals carried between generations.
        :param generations: Number of generations to run.
        :param seed: Seed for the generator, so a run reproduces exactly.
        :return: Dict with the archived front's decision vectors and objectives, the
            final population and its objectives, and hypervolume per generation.
        """
        rng: np.random.Generator = np.random.default_rng(seed)
        num_genes: int = lower.shape[0]

        population: np.ndarray = rng.uniform(low=lower, high=upper, size=(population_size, num_genes))
        objectives: np.ndarray = evaluate(population)

        # Fixed across the run so the history is comparable generation to generation.
        num_objectives: int = objectives.shape[1]
        reference: np.ndarray = np.max(objectives, axis=0) + 1.0

        # For three or more objectives, fix the Monte Carlo sample set once. Reusing
        # the same points every generation is what makes the history exactly
        # non-decreasing instead of merely trending upward: a sample that is dominated
        # once stays dominated, because the archive's dominated region only grows.
        hypervolume_samples: np.ndarray | None = None
        sample_box_volume: float | None = None
        if num_objectives > 2:
            sample_lower: np.ndarray = np.min(objectives, axis=0)
            sample_box_volume = float(np.prod(reference - sample_lower))
            hypervolume_samples = rng.uniform(
                low=sample_lower, high=reference, size=(Hypervolume.DEFAULT_SAMPLES, num_objectives)
            )

        archive_genes, archive_objectives = Nsga2.update_archive(
            np.empty((0, num_genes)), np.empty((0, num_objectives)), population, objectives
        )

        history: list[float] = []

        for _ in range(generations):
            ranks, crowding = ParetoRanking.rank_and_crowding(objectives)

            parent_indices_a: np.ndarray = GeneticOperators.binary_tournament(ranks, crowding, population_size, rng)
            parent_indices_b: np.ndarray = GeneticOperators.binary_tournament(ranks, crowding, population_size, rng)
            children: np.ndarray = GeneticOperators.sbx_crossover(
                population[parent_indices_a], population[parent_indices_b], lower, upper, rng
            )
            children = GeneticOperators.polynomial_mutation(children, lower, upper, rng)

            # Elitist: parents and children compete for the next generation together,
            # so a good solution can never be lost to chance.
            combined: np.ndarray = np.vstack([population, children])
            combined_objectives: np.ndarray = np.vstack([objectives, evaluate(children)])

            keep: np.ndarray = ParetoRanking.environmental_selection(combined_objectives, population_size)
            population = combined[keep]
            objectives = combined_objectives[keep]

            archive_genes, archive_objectives = Nsga2.update_archive(
                archive_genes, archive_objectives, population, objectives
            )
            history.append(Hypervolume.compute(archive_objectives, reference, hypervolume_samples, sample_box_volume))

        return {
            "front_genes": archive_genes,
            "front_objectives": archive_objectives,
            "population": population,
            "objectives": objectives,
            "hypervolume_history": np.array(history, dtype=float),
            "reference": reference,
        }
