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

"""Grouped mutable state for one Network Consultant CLI run."""

import argparse
from dataclasses import dataclass

from neuro_san_studio.network_consultant.consultant_connection import ConsultantConnection
from neuro_san_studio.network_consultant.consultant_resources import ConsultantResources
from neuro_san_studio.network_consultant.consultant_round_state import ConsultantRoundState
from neuro_san_studio.network_consultant.consultant_score_state import ConsultantScoreState
from neuro_san_studio.network_consultant.consultant_target import ConsultantTarget
from neuro_san_studio.network_consultant.progress_tracker import ProgressTracker


@dataclass
class ConsultantRunContext:
    """Group independent connection, target, resource, score, and round state."""

    args: argparse.Namespace
    connection: ConsultantConnection
    target: ConsultantTarget
    resources: ConsultantResources
    scores: ConsultantScoreState
    round: ConsultantRoundState
    progress_tracker: ProgressTracker
