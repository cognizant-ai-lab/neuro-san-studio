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


class GeneticOperators:
    """
    The selection, crossover and mutation operators NSGA-II uses to breed a generation.

    Each operator takes a seeded generator so a whole run reproduces exactly.
    See nsga2.py for the loop that applies them.
    """

    # Guards a zero-width gene range in the mutation step.
    EPSILON: float = 1e-12

    @staticmethod
    def binary_tournament(
        ranks: np.ndarray,
        crowding: np.ndarray,
        num_winners: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """
        Select parents by the crowded-comparison operator.

        Two random candidates compete. The lower front wins; on a tie the less
        crowded one wins. This is the only place selection pressure enters, and it
        pushes on both convergence (rank) and diversity (crowding) at once.

        :param ranks: Front index per solution.
        :param crowding: Crowding distance per solution.
        :param num_winners: How many parent indices to draw.
        :param rng: Seeded generator, so a run is reproducible.
        :return: Array of selected indices of length num_winners.
        """
        population_size: int = ranks.shape[0]
        left: np.ndarray = rng.integers(0, population_size, size=num_winners)
        right: np.ndarray = rng.integers(0, population_size, size=num_winners)

        left_wins: np.ndarray = (ranks[left] < ranks[right]) | (
            (ranks[left] == ranks[right]) & (crowding[left] > crowding[right])
        )
        return np.where(left_wins, left, right)

    # Deb's operators take their distribution index and rates as explicit parameters
    # so a run can be tuned without editing the class.
    # pylint: disable=too-many-arguments,too-many-positional-arguments
    @staticmethod
    def sbx_crossover(
        parents_a: np.ndarray,
        parents_b: np.ndarray,
        lower: np.ndarray,
        upper: np.ndarray,
        rng: np.random.Generator,
        eta: float = 15.0,
        probability: float = 0.9,
    ) -> np.ndarray:
        """
        Simulated binary crossover.

        SBX mimics the behaviour of single-point crossover on binary strings while
        operating on real numbers: children land near their parents, and the spread
        parameter eta controls how near. Large eta keeps children tight to the
        parents, small eta explores further out.

        :param parents_a: First parent per pairing, shape (num_pairs, num_genes).
        :param parents_b: Second parent per pairing, same shape.
        :param lower: Per-gene lower bound.
        :param upper: Per-gene upper bound.
        :param rng: Seeded generator.
        :param eta: Distribution index; higher means children closer to parents.
        :param probability: Chance that a given pairing is crossed at all.
        :return: One child per pairing, shape (num_pairs, num_genes).
        """
        num_pairs, num_genes = parents_a.shape
        children: np.ndarray = parents_a.copy()

        # Draw the spread factor betaq from the SBX distribution.
        uniform: np.ndarray = rng.random(size=(num_pairs, num_genes))
        beta_q: np.ndarray = np.where(
            uniform <= 0.5,
            (2.0 * uniform) ** (1.0 / (eta + 1.0)),
            (1.0 / (2.0 * (1.0 - uniform))) ** (1.0 / (eta + 1.0)),
        )

        blended: np.ndarray = 0.5 * ((1.0 + beta_q) * parents_a + (1.0 - beta_q) * parents_b)

        # Apply per-pair, then per-gene, so some genes pass through untouched.
        pair_mask: np.ndarray = rng.random(size=(num_pairs, 1)) <= probability
        gene_mask: np.ndarray = rng.random(size=(num_pairs, num_genes)) <= 0.5
        children = np.where(pair_mask & gene_mask, blended, children)

        return np.clip(children, lower, upper)

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    @staticmethod
    def polynomial_mutation(
        population: np.ndarray,
        lower: np.ndarray,
        upper: np.ndarray,
        rng: np.random.Generator,
        eta: float = 20.0,
        probability: float | None = None,
    ) -> np.ndarray:
        """
        Polynomial mutation.

        Perturbs a gene by an amount drawn from a polynomial distribution centred on
        zero and scaled to the gene's own range, so a mutation is small far more
        often than it is large. The default per-gene rate of 1/num_genes means about
        one gene changes per individual.

        :param population: Array of shape (population_size, num_genes).
        :param lower: Per-gene lower bound.
        :param upper: Per-gene upper bound.
        :param rng: Seeded generator.
        :param eta: Distribution index; higher means smaller perturbations.
        :param probability: Per-gene mutation rate. Defaults to 1/num_genes.
        :return: Mutated copy of the population.
        """
        num_genes: int = population.shape[1]
        if probability is None:
            probability = 1.0 / num_genes

        span: np.ndarray = np.where(
            (upper - lower) < GeneticOperators.EPSILON, GeneticOperators.EPSILON, upper - lower
        )
        uniform: np.ndarray = rng.random(size=population.shape)

        delta: np.ndarray = np.where(
            uniform < 0.5,
            (2.0 * uniform) ** (1.0 / (eta + 1.0)) - 1.0,
            1.0 - (2.0 * (1.0 - uniform)) ** (1.0 / (eta + 1.0)),
        )

        mutation_mask: np.ndarray = rng.random(size=population.shape) <= probability
        mutated: np.ndarray = np.where(mutation_mask, population + delta * span, population)

        return np.clip(mutated, lower, upper)
