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

import logging
from asyncio import Future
from asyncio import gather
from typing import Any

from coded_tools.experimental.mdap_decomposer.agent_caller import AgentCaller
from coded_tools.experimental.mdap_decomposer.first_to_k_voter import FirstToKVoter
from coded_tools.experimental.mdap_decomposer.solver_parsing import SolverParsing
from coded_tools.experimental.mdap_decomposer.voter import Voter


# pylint: disable=too-many-instance-attributes
class NeuroSanSolver:
    """
    Generic solver implementation that uses Neuro SAN.
    """

    def __init__(
        self,
        winning_vote_count: int = 2,
        candidate_count: int = None,
        number_of_votes: int = None,
        solution_candidate_count: int = None,
    ):
        """
        Constructor.
        """

        if winning_vote_count is None:
            winning_vote_count = 2
        self.winning_vote_count: int = winning_vote_count

        default_count: int = (2 * winning_vote_count) - 1

        self.candidate_count: int = candidate_count
        if self.candidate_count is None:
            self.candidate_count = default_count

        self.number_of_votes: int = number_of_votes
        if self.number_of_votes is None:
            self.number_of_votes = default_count

        self.solution_candidate_count: int = solution_candidate_count
        if self.solution_candidate_count is None:
            self.solution_candidate_count = default_count

        self.parsing = SolverParsing()

        self.composition_discriminator_caller: AgentCaller = None
        self.decomposer_caller: AgentCaller = None
        self.problem_solver_caller: AgentCaller = None
        self.solution_discriminator_caller: AgentCaller = None

    def set_callers(
        self,
        composition_discriminator_caller: AgentCaller,
        decomposer_caller: AgentCaller,
        problem_solver_caller: AgentCaller,
        solution_discriminator_caller: AgentCaller,
    ):
        """
        Set AgentCallers.
        """

        if composition_discriminator_caller is not None:
            self.composition_discriminator_caller = composition_discriminator_caller
        if decomposer_caller is not None:
            self.decomposer_caller = decomposer_caller
        if problem_solver_caller is not None:
            self.problem_solver_caller = problem_solver_caller
        if solution_discriminator_caller is not None:
            self.solution_discriminator_caller = solution_discriminator_caller

    # pylint: disable=too-many-locals
    async def solve(self, problem: str, depth: int, max_depth: int, path: str = "0") -> dict[str, Any]:
        """
        Internal recursive solver that returns (response, trace_node).
        Builds a complete trace tree of the decomposition process.

        :return: The root trace node of the decomposition process
        """
        logging.info(
            "[solve] depth=%d path=%s problem: %s%s",
            depth,
            path,
            problem[:120],
            "..." if len(problem) > 120 else "",
        )

        node = {
            "depth": depth,
            "path": path,
            "problem": problem,
            "decomposition": None,
            "children": [],
            "sub_finals": None,
            "composition": None,
            "response": None,
            "final": None,
            "extracted_final": None,
            "atomic": None,
            # Not included: "final_num" and "error"
        }

        if depth >= max_depth:
            logging.info("[solve] depth=%d -> atomic (max depth)", depth)
            resp, finals, votes, winner_idx, solutions = await self._solve_atomic_with_voting(problem)
            _ = solutions
            node["response"] = resp
            node["final"] = finals[winner_idx]
            node["atomic"] = {
                "atomic_candidates": finals,
                "atomic_votes": votes,
                "atomic_winner_idx": winner_idx,
                "final_choice": finals[winner_idx],
            }
            node["extracted_final"] = self.parsing.extract_final(resp)
            return node

        p1, p2, c, decomp_meta = await self.decompose(problem)

        source: str = f"[solve] depth={depth}"
        if not p1 or not p2 or not c:
            logging.info("%s -> atomic (no decomp)", source)
            if decomp_meta:
                node["decomposition"] = {**decomp_meta, "decision": "no_decomposition"}
            resp, finals, votes, winner_idx, solutions = await self._solve_atomic_with_voting(problem)
            node["response"] = resp
            node["final"] = finals[winner_idx]
            node["atomic"] = {
                "atomic_candidates": finals,
                "atomic_votes": votes,
                "atomic_winner_idx": winner_idx,
                "final_choice": finals[winner_idx],
            }
            node["extracted_final"] = self.parsing.extract_final(resp)
            return node

        logging.info("%s using decomposition", source)
        node["decomposition"] = decomp_meta

        # Parallelize solving each sub-problem
        problems: list[str] = [p1, p2]
        coroutines: list[Future] = []
        for i in range(2):
            use_path: str = f"{path}.{i}"
            coroutines.append(self.solve(problems[i], depth + 1, max_depth, use_path))
        nodes: list[dict[str, Any]] = await gather(*coroutines)

        node["children"] = nodes
        s1: str = nodes[0].get("extracted_final")
        s2: str = nodes[1].get("extracted_final")
        node["sub_finals"] = {"s1_final": s1, "s2_final": s2}

        logging.info("%s sub-answers -> s1_final=%s, s2_final=%s", source, s1, s2)

        comp_prompt = self._compose_prompt(c, s1, s2)
        logging.info("%s composing with C=%s", source, c)

        resp, finals, votes, winner_idx, solutions = await self._solve_generic(comp_prompt, source)

        node["response"] = resp
        node["final"] = finals[winner_idx]
        node["composition"] = {
            "c_text": c,
            "composed_candidates": finals,
            "composition_votes": votes,
            "composition_winner_idx": winner_idx,
            "final_choice": finals[winner_idx],
        }
        node["extracted_final"] = self.parsing.extract_final(resp)

        return node

    def _compose_prompt(self, c: str, s1: str, s2: str) -> str:
        """
        Build a prompt for the final composition solve: C(s1, s2).
        We pass the original problem, the composition description, and the sub-solutions.
        """
        return f"Solve C(P1, P2) such that C={c}, P1={s1}, P2={s2}"

    async def _solve_atomic_with_voting(self, problem: str) -> tuple[str, list[str], list[int], int, list[str]]:
        """
        Generate multiple atomic solutions and vote on them.
        Returns (chosen_response, finals, votes, winner_idx, solutions).
        """
        return await self._solve_generic(problem, "[atomic]")

    async def _solve_generic(self, problem: str, source: str) -> tuple[str, list[str], list[int], int, list[str]]:
        """
        Generate multiple atomic solutions and vote on them.
        Returns (chosen_response, finals, votes, winner_idx, solutions).
        """
        solutions: list[str] = []
        finals: list[str] = []
        tool_args: dict[str, Any] = {"problem": problem}

        # Parallelize finding different solutions for the problem
        coroutines: list[Future] = []
        for k in range(self.solution_candidate_count):
            coroutines.append(self.problem_solver_caller.call_agent(tool_args))
        results: list[str] = await gather(*coroutines)

        for k, r in enumerate(results):
            solutions.append(r)
            finals.append(self.parsing.extract_final(r))
            logging.info("%s candidate %d: %s", source, k + 1, finals[-1])

        voter: Voter = FirstToKVoter(
            source,
            "composition",
            "solutions",
            self.composition_discriminator_caller,
            self.number_of_votes,
            self.winning_vote_count,
        )
        votes, winner_idx = await voter.vote(problem, finals)

        return solutions[winner_idx], finals, votes, winner_idx, solutions

    # pylint: disable=too-many-locals
    async def decompose(self, problem: str) -> tuple[str | None, str | None, str | None, dict]:
        """
        Collect CANDIDATE_COUNT decompositions from the 'decomposer' agent,
        then run a voting round via 'solution_discriminator'.
        Returns (p1, p2, c, metadata_dict).
        """
        candidates: list[str] = []
        tool_args: dict[str, Any] = {"problem": problem}

        # Parallelize finding different decompositions for the problem
        coroutines: list[Future] = []
        for _ in range(self.candidate_count):
            coroutines.append(self.decomposer_caller.call_agent(tool_args))
        results: list[str] = await gather(*coroutines)

        for resp in results:
            cand: str = self.parsing.extract_decomposition_text(resp)
            if cand:
                candidates.append(cand)

        for i, candidate in enumerate(candidates, 1):
            logging.info("[decompose] candidate %d: %s", i, candidate)

        if not candidates:
            return None, None, None, {}

        voter: Voter = FirstToKVoter(
            "[decompose]",
            "solution",
            "decompositions",
            self.solution_discriminator_caller,
            self.number_of_votes,
            self.winning_vote_count,
        )
        votes, winner_idx = await voter.vote(problem, candidates)

        p1, p2, c = self.parsing.parse_decomposition(candidates[winner_idx])

        metadata = {
            "candidates": candidates,
            "winner_idx": winner_idx,
            "votes": votes,
            "chosen": candidates[winner_idx],
            "p1": p1,
            "p2": p2,
            "c": c,
        }

        return p1, p2, c, metadata
