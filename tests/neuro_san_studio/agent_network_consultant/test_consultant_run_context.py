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

"""Tests for the access-controlled Agent Network Consultant run context."""

from unittest import TestCase
from unittest.mock import Mock

from neuro_san_studio.agent_network_consultant.consultant_options import ConsultantOptions
from neuro_san_studio.agent_network_consultant.consultant_run_context import ConsultantRunContext
from neuro_san_studio.agent_network_consultant.consultant_session import ConsultantSession
from neuro_san_studio.agent_network_consultant.consultant_target import ConsultantTarget


class TestConsultantRunContext(TestCase):
    """Verify collaborators are available through explicit accessors."""

    def test_returns_supplied_collaborators_and_owned_state(self) -> None:
        """Return supplied collaborators and stable state owned by one isolated run."""
        options = ConsultantOptions(use_case="Create a network")
        session = Mock(spec=ConsultantSession)
        target = ConsultantTarget("example.hocon", "example", "Preserve behavior", "registries/example.hocon")
        context = ConsultantRunContext(
            options=options,
            session=session,
            target=target,
        )
        scores = context.scores()
        round_state = context.round_state()
        progress_tracker = context.progress_tracker()

        self.assertIs(context.options(), options)
        self.assertIs(context.session(), session)
        self.assertIs(context.target(), target)
        self.assertIs(context.scores(), scores)
        self.assertIs(context.round_state(), round_state)
        self.assertIs(context.progress_tracker(), progress_tracker)
