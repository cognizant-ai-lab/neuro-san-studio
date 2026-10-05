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

"""Tests for the access-controlled Network Consultant run context."""

from unittest import TestCase
from unittest.mock import Mock

from neuro_san_studio.agent_network_consultant.consultant_options import ConsultantOptions
from neuro_san_studio.agent_network_consultant.consultant_resources import ConsultantResources
from neuro_san_studio.agent_network_consultant.consultant_round_state import ConsultantRoundState
from neuro_san_studio.agent_network_consultant.consultant_run_context import ConsultantRunContext
from neuro_san_studio.agent_network_consultant.consultant_score_state import ConsultantScoreState
from neuro_san_studio.agent_network_consultant.consultant_session import ConsultantSession
from neuro_san_studio.agent_network_consultant.consultant_target import ConsultantTarget
from neuro_san_studio.agent_network_consultant.progress_tracker import ProgressTracker


class TestConsultantRunContext(TestCase):
    """Verify collaborators are available through explicit accessors."""

    def test_returns_each_run_interface(self) -> None:
        """Return the exact collaborators supplied for one isolated run."""
        options = ConsultantOptions(use_case="Create a network")
        session = Mock(spec=ConsultantSession)
        target = ConsultantTarget("example.hocon", "example", "Preserve behavior", "registries/example.hocon")
        resources = ConsultantResources()
        scores = ConsultantScoreState()
        round_state = ConsultantRoundState()
        progress_tracker = ProgressTracker()
        context = ConsultantRunContext(
            options,
            session,
            target,
            resources,
            scores,
            round_state,
            progress_tracker,
        )

        self.assertIs(context.options(), options)
        self.assertIs(context.session(), session)
        self.assertIs(context.target(), target)
        self.assertIs(context.resources(), resources)
        self.assertIs(context.scores(), scores)
        self.assertIs(context.round_state(), round_state)
        self.assertIs(context.progress_tracker(), progress_tracker)
