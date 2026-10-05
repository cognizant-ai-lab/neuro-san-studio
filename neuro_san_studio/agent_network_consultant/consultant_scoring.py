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

"""Round scoring and rollback policy for Network Consultant runs."""

import logging
from typing import Any

GOOD_ENOUGH_RATIO = 0.8
logger = logging.getLogger("network_consultant")


class ConsultantScoring:
    """Score test rounds and restore the best target-network version."""

    @staticmethod
    def round_score(results: list[dict[str, Any]]) -> tuple[int, int]:
        """
        How good this round was, best-first, for the plateau counter and the HOCON snapshot.

        Fixture count alone is one bit per fixture, and a fixture is all-or-nothing -- so a network that went from
        meeting 4 of its 15 acceptance criteria to meeting 14 still reported the same "6 failing" three rounds
        running. The plateau counter fired on real progress, and because `improved` needs a STRICT gain the best-
        so-far snapshot never left iteration 1 -- whose snapshot is the original, pre-edit file, which the rollback
        then dutifully restored. That is the "ran three rounds and changed nothing" shape.

        Whole fixtures stay the primary term because passing them is the actual goal: 2 fixtures passing beats 0
        passing even if the second state meets more criteria overall. Criteria are the tiebreaker, and they are
        what lets the loop see itself working at all.

        :param results: The fixture result records.
        :return: The resulting values.
        """
        passing = 0
        criteria = 0
        for result in results:
            if result.get("passed"):
                passing += 1
            criteria += result.get("criteria_passed", 0)
        return passing, criteria

    @staticmethod
    def restore_best_hocon(hocon_path: str, best_text: str, best_iteration: int) -> None:
        """
        Roll the network HOCON back to the version that produced the best result, discarding the later edits that
        never beat it. No-op if the file already is that version.

        :param hocon_path: The target HOCON file path.
        :param best_text: The best-known HOCON source text.
        :param best_iteration: The iteration that produced the best result.
        """
        if best_text is None:
            return
        with open(hocon_path, encoding="utf-8") as current_file:
            if current_file.read() == best_text:
                return
        with open(hocon_path, "w", encoding="utf-8") as out_file:
            out_file.write(best_text)
        logger.info(
            "Rolled %s back to its iteration-%d version (the best result seen); the edits after that one never "
            "improved on it.",
            hocon_path,
            best_iteration,
        )

    @staticmethod
    def good_enough(passed: int, total: int) -> bool:
        """
        Whether a FULL-suite result clears the bar to stop fixing this network and move on.

        :param passed: Whether the fixture passed.
        :param total: The total number of fixtures.
        :return: Whether the requested condition is met.
        """
        return total > 0 and passed >= GOOD_ENOUGH_RATIO * total

    @staticmethod
    def extract_prefixed(response: str, prefix: str) -> list[str]:
        """
        Return the payload of every line in `response` that starts with `prefix`.

        :param response: The Consultant response text.
        :param prefix: The response-line prefix to select.
        :return: The collected values.
        """
        matches: list[str] = []
        for line in (response or "").splitlines():
            if line.strip().startswith(prefix):
                matches.append(line[len(prefix) :].strip())
        return matches
