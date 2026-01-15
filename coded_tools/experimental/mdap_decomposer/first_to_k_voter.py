# Copyright © 2025 Cognizant Technology Solutions Corp, www.cognizant.com.
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

from typing import Any

from asyncio import Future
from asyncio import gather

import logging

from coded_tools.experimental.mdap_decomposer.agent_caller import AgentCaller
from coded_tools.experimental.mdap_decomposer.voter import Voter


class FirstToKVoter(Voter):
    """
    Generic Voter implementation that returns the first solution that receives
    a certain number of votes (K).
    """

    def __init__(self, source: str,
                 discriminator_name: str,
                 candidates_key: str,
                 discriminator_caller: AgentCaller,
                 number_of_votes: int = 3,
                 winning_vote_count: int = 2):
        """
        Constructor.
        """

        self.source: str = source
        self.discriminator_name: str = discriminator_name
        self.candidates_key: str = candidates_key
        self.discriminator_caller: AgentCaller = discriminator_caller
        self.number_of_votes: int = number_of_votes
        self.winning_vote_count: int = winning_vote_count

    async def vote(self, problem: str, candidates: list[str]) -> tuple[list[int], int]:
        """
        Generic voting interface

        :param problem: The problem to be solved
        :param candidates: The candidate solutions
        :return: A tuple of (list of number of votes per candidate, winner index)
        """

        numbered: str = "\n".join(f"{i+1}. {candidate}" for i, candidate in enumerate(candidates))
        numbered = f"problem: {problem}, {numbered}"
        logging.info(f"{self.source} {self.discriminator_name} discriminator query: {numbered}")

        tool_args: dict[str, Any] = {
            "problem": problem,
            self.candidates_key: candidates
        }

        # Prepare a list of coroutines to parallelize
        coroutines: list[Future] = []
        for _ in range(self.number_of_votes):
            # All entries for parallelization do the same thing.
            # Note: Perhaps not the most token/cost efficient, but definitely good for time.
            coroutines.append(self.discriminator_caller.call_agent(tool_args))

        # Call the agents in parallel
        results: list[str] = await gather(*coroutines)

        # Process the votes
        votes: list[int] = [0] * len(candidates)
        winner_idx: int = None
        for vote_txt in results:
            logging.info(f"{self.source} raw vote: {vote_txt}")
            try:
                idx: int = int(vote_txt) - 1
                if idx >= len(candidates):
                    logging.error(f"Invalid vote index: {idx}")
                if 0 <= idx < len(candidates):
                    votes[idx] += 1
                    logging.info(f"{self.source} tally: {votes}")
                    if votes[idx] >= self.winning_vote_count:
                        winner_idx = idx
                        logging.info(f"{self.source} early winner: {winner_idx + 1}")
                        break
            except ValueError:
                logging.warning(f"{self.source} malformed vote ignored: {vote_txt!r}")

        if winner_idx is None:
            winner_idx = max(range(len(votes)), key=lambda v: votes[v])

        logging.info(f"{self.source} final winner: {winner_idx + 1} -> {candidates[winner_idx]!r}")

        return votes, winner_idx
