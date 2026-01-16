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
from coded_tools.experimental.mdap_decomposer.voter import Voter


# pylint: disable=too-few-public-methods
class FirstToKVoter(Voter):
    """
    Generic Voter implementation that returns the first solution that receives
    a certain number of votes (K).
    """

    # pylint: disable=too-many-arguments, too-many-positional-arguments
    def __init__(
        self,
        source: str,
        discriminator_name: str,
        candidates_key: str,
        discriminator_caller: AgentCaller,
        number_of_votes: int = 3,
        winning_vote_count: int = 2,
    ):
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

        numbered: str = "\n".join(f"{i + 1}. {candidate}" for i, candidate in enumerate(candidates))
        numbered = f"problem: {problem}, {numbered}"
        logging.info("%s %s discriminator query: %s", self.source, self.discriminator_name, numbered)

        tool_args: dict[str, Any] = {"problem": problem, self.candidates_key: candidates}

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
            logging.info("%s raw vote: %s", self.source, vote_txt)
            try:
                idx: int = int(vote_txt) - 1
                if idx >= len(candidates):
                    logging.error("Invalid vote index: %d", idx)
                if 0 <= idx < len(candidates):
                    votes[idx] += 1
                    logging.info("%s tally: %s", self.source, str(votes))
                    if votes[idx] >= self.winning_vote_count:
                        winner_idx = idx
                        logging.info("%s early winner: %d", self.source, winner_idx + 1)
                        break
            except ValueError:
                logging.error("%s malformed vote ignored: %s", self.source, vote_txt)

        if winner_idx is None:
            winner_idx = max(range(len(votes)), key=lambda v: votes[v])

        logging.info("%s final winner: %d -> %s", self.source, winner_idx + 1, candidates[winner_idx])

        return votes, winner_idx
