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

"""Access-controlled dependencies and state for one Network Consultant run."""

from dataclasses import dataclass

from neuro_san_studio.agent_network_consultant.consultant_options import ConsultantOptions
from neuro_san_studio.agent_network_consultant.consultant_resources import ConsultantResources
from neuro_san_studio.agent_network_consultant.consultant_round_state import ConsultantRoundState
from neuro_san_studio.agent_network_consultant.consultant_score_state import ConsultantScoreState
from neuro_san_studio.agent_network_consultant.consultant_session import ConsultantSession
from neuro_san_studio.agent_network_consultant.consultant_target import ConsultantTarget
from neuro_san_studio.agent_network_consultant.progress_tracker import ProgressTracker


@dataclass
class ConsultantRunContext:
    """Expose run collaborators only through explicit accessor methods."""

    _options: ConsultantOptions
    _session: ConsultantSession
    _target: ConsultantTarget
    _resources: ConsultantResources
    _scores: ConsultantScoreState
    _round_state: ConsultantRoundState
    _progress_tracker: ProgressTracker

    def options(self) -> ConsultantOptions:
        """
        Return the validated run options.

        :return: The run options interface.
        """
        return self._options

    def session(self) -> ConsultantSession:
        """
        Return the active Consultant session.

        :return: The Consultant session interface.
        """
        return self._session

    def target(self) -> ConsultantTarget:
        """
        Return the resolved target interface.

        :return: The target interface.
        """
        return self._target

    def resources(self) -> ConsultantResources:
        """
        Return the cleanup-resource interface.

        :return: The resource interface.
        """
        return self._resources

    def scores(self) -> ConsultantScoreState:
        """
        Return the score-state interface.

        :return: The score-state interface.
        """
        return self._scores

    def round_state(self) -> ConsultantRoundState:
        """
        Return the active round-state interface.

        :return: The round-state interface.
        """
        return self._round_state

    def progress_tracker(self) -> ProgressTracker:
        """
        Return the progress-tracking interface.

        :return: The progress-tracking interface.
        """
        return self._progress_tracker
