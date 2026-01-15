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


class Voter:
    """
    Generic voter interface
    """

    async def vote(self, problem: str, candidates: list[str]) -> tuple[list[int], int]:
        """
        Generic voting interface

        :param problem: The problem to be solved
        :param candidates: The candidate solutions
        :return: A tuple of (list of number of votes per candidate, winner index)
        """
        raise NotImplementedError
